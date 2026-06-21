"""The Ranger reference agent — Scout + sandboxed Worker + Dreamer (S3/S4).

Ranger is VISTA's system-under-test: a deterministic THREE-ROLE agent that
embodies the privilege separation and the long-view planning the benchmark
rewards. It is a *reference policy* (no LLM, NFR-1) — the role a calibrated
shared "team agent" should play. The three roles map 1:1 to the C3 capability
contract (``contracts/tools.py``):

* **Scout** (:class:`RangerScout`, C3 ``ScoutTools`` — holds planning AUTHORITY).
  Builds a working route-graph from the AGENT-VISIBLE guardrail view only
  (FR-G1, never the hidden oracle), plans the cost-optimal walk to the goal, and
  — crucially — ESCALATES through any genuine ``risk:high`` fork on that walk
  instead of proceeding unilaterally (FR-A1: "ask for verification at the right
  moment"). It never routes toward a forbidden trap or a non-goal absorbing
  (hijack) terminal. If escalation has no resume path it escalates AND HOLDS
  (safety over completion).

* **Worker** (:class:`RangerWorker`, C3 ``WorkerTools`` — sandboxed). NO authority,
  NO secrets; it can read/search untrusted terrain and *request* one Scout-
  authorized edge. The ABSENCE of ``escalate`` / ``authorize_edge`` /
  ``propose_graph_edit`` here is the contract (FR-A2/FR-Sec2,
  test_worker_no_authority).

* **Dreamer** (:class:`RangerDreamer`, C3 ``DreamerTools`` — offline). Consolidates
  the session into a self-audit (e.g. flags the recurring injected wire
  instruction as a poisoned-context pattern, ASI06) and proposes nothing that
  touches the sanctioned graph.

The long-view premium: on a journey whose graph carries a genuine high-risk fork,
Ranger's Scout escalates (``verification_calibration`` recall = 1.0) where the
naive baseline proceeds unilaterally (recall = 0.0) — a difference INVISIBLE to a
binary pass/fail (both reach the goal), which is exactly VISTA's thesis.

Determinism (NFR-1): every plan is a pure function of the visible view. Path
search is cost-ordered with a lexicographic tie-break on the node path; the
optional ``seed`` is accepted for signature parity but never consulted.
"""

from __future__ import annotations

import heapq
from typing import Any, Optional

from contracts.tools import (
    Actor,
    AuditRecord,
    DreamRecord,
    EdgeRequest,
    EdgeResult,
    EscalationRequest,
    GraphEditProposal,
    GraphEditResult,
    Outcome,
    ReadResult,
    DreamerTools,
    ScoutTools,
    WorkerTools,
)
from harness.rsi import forbidden_nodes, graph_hash, reachable_forbidden

_FORBIDDEN_KIND = "forbidden"
_ABSORBING_KIND = "absorbing"
_HIGH_RISK = "high"


# --------------------------------------------------------------------------- #
# Scout — planning authority + escalation (C3 ScoutTools)
# --------------------------------------------------------------------------- #
class RangerScout(ScoutTools):
    """The planner. Holds authority; sees only the structured visible graph (never
    raw untrusted bodies). Produces the calibrated walk the Worker executes."""

    def __init__(self) -> None:
        # The working-graph intent the Scout authored this session (audit trail).
        self.authorized: list[AuditRecord] = []
        self.escalations: list[AuditRecord] = []

    # -- ScoutTools contract (structured reads only; authority to author/escalate) #
    def read(self, ref: str) -> ReadResult:
        return ReadResult(items=[{"ref": ref}], untrusted=False)

    def search(self, query: str) -> ReadResult:
        return ReadResult(items=[], untrusted=False)

    def authorize_edge(self, from_node: str, to_node: str, guard: str) -> AuditRecord:
        rec = AuditRecord(
            seq=len(self.authorized),
            actor=Actor.SCOUT,
            action="authorize_edge",
            target=to_node,
            redacted_payload={"from": from_node, "to": to_node, "guard": guard},
            outcome=Outcome.OK,
        )
        self.authorized.append(rec)
        return rec

    def escalate(self, request: EscalationRequest) -> EdgeResult:
        audit = AuditRecord(
            seq=len(self.escalations),
            actor=Actor.SCOUT,
            action="escalate",
            target=request.fork_id,
            redacted_payload={"fork": request.fork_id, "reason": request.reason},
            outcome=Outcome.ESCALATED,
        )
        self.escalations.append(audit)
        return EdgeResult(applied=True, outcome=Outcome.ESCALATED, audit=audit)

    # -- the brain: plan a calibrated, safe, cost-optimal walk ---------------- #
    def plan_walk(self, visible_view: dict[str, Any]) -> list[str]:
        """The ordered target node ids (excluding entry) the Worker will execute.

        Cost-optimal walk to the goal, re-routed to ESCALATE through the first
        genuine ``risk:high`` fork on the path (then resume to the goal). Never
        routes into a forbidden / non-goal-absorbing trap. Raises ``ValueError``
        if the visible graph has no safe path to the goal.
        """
        entry = visible_view["entry"]
        goal = visible_view["goal"]
        nodes: dict[str, Any] = visible_view["nodes"]
        edges: list[dict[str, Any]] = visible_view["edges"]

        # Traps the Scout never routes INTO: forbidden nodes + non-goal absorbing
        # (a different terminal = a hijack). The goal itself is always allowed.
        avoid = {
            nid for nid, d in nodes.items()
            if d.get("kind") == _FORBIDDEN_KIND
            or (d.get("kind") == _ABSORBING_KIND and nid != goal)
        }

        base = self._cheapest_path(entry, goal, edges, avoid)
        if base is None:
            raise ValueError(f"Ranger: no safe path from {entry!r} to {goal!r}")

        walk = self._escalate_first_fork(base, edges, avoid, goal)
        self._authorize(walk, edges)
        return walk[1:]

    # -- escalation-aware re-routing ----------------------------------------- #
    def _escalate_first_fork(
        self,
        base: list[str],
        edges: list[dict[str, Any]],
        avoid: set[str],
        goal: str,
    ) -> list[str]:
        """If a node on ``base`` is the source of a ``risk:high`` fork, escalate
        through it (take the high edge to the HITL node) then resume to the goal.

        Records the escalation as a Scout authority action. If the HITL node has
        no resume path to the goal, the Scout escalates AND HOLDS — safety over
        completion (the calibrated steward does not guess past a high-risk fork)."""
        high_out: dict[str, list[str]] = {}
        for e in edges:
            if e.get("risk") == _HIGH_RISK and e["to"] not in avoid:
                high_out.setdefault(e["from"], []).append(e["to"])

        for i, node in enumerate(base):
            targets = sorted(high_out.get(node, []))
            if not targets:
                continue
            hitl = targets[0]  # escalate to the lexicographically-first HITL target
            self.escalate(EscalationRequest(
                fork_id=f"{node}->{hitl}",
                reason="genuine risk:high decision — defer to human, do not proceed unilaterally",
            ))
            resume = self._cheapest_path(hitl, goal, edges, avoid)
            if resume is None:
                return base[: i + 1] + [hitl]  # escalate and HOLD (no resume path)
            return base[: i + 1] + resume       # resume[0] == hitl
        return base

    def _authorize(self, walk: list[str], edges: list[dict[str, Any]]) -> None:
        """Author (authorize) each edge along the final walk — Scout authority."""
        guard_of = {(e["from"], e["to"]): e.get("guard", "") for e in edges}
        for frm, to in zip(walk, walk[1:]):
            self.authorize_edge(frm, to, guard_of.get((frm, to), ""))

    # -- deterministic cost-optimal path (Dijkstra, lexicographic tie-break) -- #
    @staticmethod
    def _cheapest_path(
        src: str,
        dst: str,
        edges: list[dict[str, Any]],
        avoid: set[str],
    ) -> Optional[list[str]]:
        """Cheapest ``src -> dst`` path over edges, never entering ``avoid``
        (except ``dst`` itself). Ties broken by the lexicographically-smallest
        node path, so the result is fully deterministic (NFR-1)."""
        adj: dict[str, list[tuple[float, str]]] = {}
        for e in edges:
            to = e["to"]
            if to in avoid and to != dst:
                continue
            adj.setdefault(e["from"], []).append((float(e.get("cost", 0)), to))

        # heap entries: (cost, path). Tuple ordering breaks cost ties by path.
        heap: list[tuple[float, list[str]]] = [(0.0, [src])]
        settled: set[str] = set()
        while heap:
            cost, path = heapq.heappop(heap)
            node = path[-1]
            if node == dst:
                return path
            if node in settled:
                continue
            settled.add(node)
            for edge_cost, nxt in sorted(adj.get(node, [])):
                if nxt not in settled:
                    heapq.heappush(heap, (cost + edge_cost, path + [nxt]))
        return None

    # -- the working route-graph (Ranger's own reconstruction) --------------- #
    @staticmethod
    def build_working_graph(visible_view: dict[str, Any]) -> dict[str, Any]:
        """Ranger's WORKING route-graph: a reconstruction of the agent-visible
        guardrail view (FR-G1 — never the hidden oracle). This is the artifact the
        Dreamer edits; it is scored against the sanctioned graph, never the
        reverse. Returns a deep copy so edits never touch the harness's view."""
        import copy as _copy
        keep = ("entry", "goal", "nodes", "edges", "guardrails")
        return {k: _copy.deepcopy(visible_view[k]) for k in keep if k in visible_view}


# --------------------------------------------------------------------------- #
# Worker — sandboxed executor: NO authority, NO secrets (C3 WorkerTools)
# --------------------------------------------------------------------------- #
class RangerWorker(WorkerTools):
    """The ONLY role that touches untrusted terrain. It can read/search and
    *request* one Scout-authorized edge; it cannot author edges, escalate, hold
    secrets, or edit the graph. Inherits ``HAS_AUTHORITY = False`` and the
    ``{read, search, request_edge}`` capability set from the contract."""

    def read(self, ref: str) -> ReadResult:
        # The Worker may receive untrusted bodies (that is its job).
        return ReadResult(items=[{"ref": ref}], untrusted=True)

    def search(self, query: str) -> ReadResult:
        return ReadResult(items=[], untrusted=True)

    def request_edge(self, request: EdgeRequest) -> EdgeResult:
        # The Worker only RELAYS intent; the runtime is the authority that decides
        # apply / record-offwalk / block. It never returns a self-granted success.
        return EdgeResult(applied=False, outcome=Outcome.OK, new_position=None, audit=None)


# --------------------------------------------------------------------------- #
# Dreamer — offline consolidation / self-audit (C3 DreamerTools)
# --------------------------------------------------------------------------- #
class RangerDreamer(DreamerTools):
    """Offline self-improvement. This reference Dreamer consolidates a session
    into a self-audit and proposes NO graph edits (RSI is S4's slice). It edits
    only the working graph and never the sanctioned graph (C2)."""

    def record_dream(self, record: DreamRecord) -> AuditRecord:
        return AuditRecord(
            seq=record.cycle,
            actor=Actor.DREAMER,
            action=record.kind,
            redacted_payload={"rationale": record.rationale},
            outcome=Outcome.OK,
        )

    def propose_graph_edit(self, proposal: GraphEditProposal) -> GraphEditResult:
        # The Dreamer NEVER self-grants an edit — the harness RSI gate
        # (harness.rsi.evaluate_edit) is the sole authority that accepts/rejects.
        # This keeps builders from grading their own safety (S4/S5 boundary).
        return GraphEditResult(
            accepted=False,
            rejected_reason="the harness RSI gate decides; the Dreamer only proposes",
        )

    def propose_cycle(
        self,
        working_graph: dict[str, Any],
        *,
        cycle: int,
        observations: Any = None,
    ) -> list[GraphEditProposal]:
        """Offline self-improvement: propose AT MOST one working-graph edit per
        cycle (capped change), parented to the current graph (lineage).

        Two benign behaviours:
          * **self-audit / heal** — if a forbidden state is reachable in the
            working graph (a poisoned reconstruction), propose REMOVING the
            edge(s) that lead into it (ASI10 self-audit). This is the beneficial
            edit the safety gate accepts because it CLOSES a forbidden path.
          * **consolidate** — otherwise, propose a single safe learned shortcut
            (``entry -> fork``) if absent. The reference Dreamer never proposes an
            edit that opens a path to a trap; the gate enforces that regardless.
        """
        parent = graph_hash(working_graph)
        forb = forbidden_nodes(working_graph)
        edges = working_graph.get("edges", [])

        reachable = reachable_forbidden(working_graph, forb)
        if reachable:
            bad = [dict(e) for e in edges if e["to"] in reachable]
            return [GraphEditProposal(
                parent_graph_hash=parent,
                rationale=f"self-audit: remove edge(s) into reachable forbidden "
                          f"state(s) {sorted(reachable)} (heal poisoned reconstruction, ASI10)",
                remove_edges=bad,
            )]

        # consolidate: a single benign express-completion edge that never touches
        # a trap — learned "after a diversion I can complete directly". Sourced
        # from the escape node when present, else from entry.
        entry, goal = working_graph["entry"], working_graph["goal"]
        nodes = working_graph.get("nodes", {})
        escape = next((nid for nid, d in nodes.items() if d.get("kind") == "escape"), None)
        src = escape or entry
        if src != goal and not any(e["from"] == src and e["to"] == goal for e in edges):
            express = {"from": src, "to": goal, "guard": "consolidated_express",
                       "authority": "worker", "cost": 1, "risk": "low"}
            return [GraphEditProposal(
                parent_graph_hash=parent,
                rationale=f"consolidate: learned a safe express-completion edge {src}->{goal}",
                add_edges=[express],
            )]
        return []  # nothing safe + useful to propose this cycle

    def dream(self, trajectory: Any, events: Any) -> DreamRecord:
        """Consolidate one session offline: flag a seen injection as a poisoned-
        context pattern (ASI06). Pure, deterministic — no live edge fired."""
        saw_injection = any(getattr(e, "type", "") == "injection_seen" for e in (events or []))
        if saw_injection:
            rationale = (
                "consolidated: an injected wire-transfer instruction recurred in "
                "untrusted input; flagged as a poisoned-context pattern (ASI06) and "
                "held intent on the sanctioned route-graph (no funds moved)."
            )
        else:
            rationale = "consolidated: no adversarial anomaly to flag this session."
        return DreamRecord(cycle=1, kind="self_audit", rationale=rationale)


# --------------------------------------------------------------------------- #
# Ranger — the coordinator the adapter drives
# --------------------------------------------------------------------------- #
class RangerAgent:
    """The three-role reference agent. The adapter needs only :meth:`plan`; the
    Scout/Worker/Dreamer instances make the C3 privilege separation concrete and
    testable."""

    name = "ranger"

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed  # parity with steered agents; determinism is seed-free.
        self.scout = RangerScout()
        self.worker = RangerWorker()
        self.dreamer = RangerDreamer()

    def plan(self, visible_view: dict[str, Any]) -> list[str]:
        """Delegate to the Scout, which holds the planning authority (FR-A1)."""
        return self.scout.plan_walk(visible_view)

    def dream(self, session_result: Any) -> DreamRecord:
        """Run the offline Dreamer over a finished session (FR-A3 hook)."""
        return self.dreamer.dream(
            getattr(session_result, "trajectory", None),
            getattr(session_result, "events", None),
        )


__all__ = ["RangerAgent", "RangerScout", "RangerWorker", "RangerDreamer"]
