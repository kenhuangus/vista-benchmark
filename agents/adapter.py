"""C5 ``AgentAdapter`` — the concrete harness<->agent seam (S3 integration).

This is the single place an agent is driven through the deterministic harness.
:class:`HarnessAgentAdapter.run_session` honors the frozen C5 signature
(``contracts.adapter.AgentAdapter`` / ``BaseAgentAdapter``):

    run_session(journey, route_state, steering) -> SessionResult

It drives the agent **step by step** through :class:`harness.runtime.RouteGraphRuntime`:
the agent (which sees ONLY the stripped guardrail view, FR-G1) proposes intended
target nodes; the runtime ``classify`` / ``step`` each one and decides whether to
APPLY it, RECORD it as off-sanctioned-walk (FR-G2), or BLOCK a forbidden crossing
(FR-G3). The adapter never makes that decision itself — it only relays. It then
assembles the C5 :class:`SessionResult` (trajectory + scorecard + events +
final route-state + audit log) and scores it with the deterministic
:class:`harness.scorer.Scorer` (NFR-1: no wall-clock, no RNG).

Also here: :class:`EdgeProjector`, a best-effort, LOSSY external state-diff ->
sanctioned-edge projection (the C5 :class:`StateDiffProjector` for free-form
agents that never declared graph nodes; architecture.md §7, OQ-4). It is
validated on a known-good trace by the S3 tests and never fakes a number.
"""

from __future__ import annotations

from typing import Any, Optional

from contracts.adapter import (
    BaseAgentAdapter,
    SessionEvent,
    SessionResult,
    Steering,
    StateDiff,
    StateDiffProjector,
    Transition,
)
from contracts.tools import Outcome

from harness.route_state import RouteState
from harness.runtime import Classification, RouteGraphRuntime, validate_graph
from harness.scorer import Scorer

# These come from the journeys slice (the real loader the S2 seat wrote). The
# adapter strips the oracle through it so the agent never sees the answer key.
from journeys.loader import visible_view as journey_visible_view


# --------------------------------------------------------------------------- #
# External state-diff -> sanctioned-edge projection (C5 StateDiffProjector)
# --------------------------------------------------------------------------- #
class EdgeProjector(StateDiffProjector):
    """Project a free-form agent's ``(before, after)`` position diff onto the
    single best-matching sanctioned edge (FR-B3, architecture.md §7).

    Best-effort and LOSSY by design: a free-form external agent never declares
    graph nodes, so the harness infers which sanctioned edge a state-diff most
    plausibly realized. The rule is intentionally conservative and deterministic:

    * If ``before -> after`` is a declared sanctioned edge, project onto it
      (carrying that edge's guard) — the high-confidence case.
    * Else, if ``after`` is a declared node, project onto an UNDECLARED transition
      ``before -> after`` (guard ``""``) so the runtime still classifies it
      (typically OFF_SANCTIONED_WALK, or FORBIDDEN if ``after`` is a trap).
    * Else (``after`` is not a graph node, or no position moved) return ``None`` —
      the diff is recorded as off-graph and contributes no transition.

    Returns an UNCLASSIFIED :class:`Transition` skeleton (``applied`` defaults
    True, the classification flags are left False); the runtime is the authority
    that classifies/records/blocks it. This keeps projection (a mapping) separate
    from enforcement (a decision).
    """

    def project(
        self,
        diff: StateDiff,
        route_graph: dict[str, Any],
    ) -> Optional[Transition]:
        before = diff.before_position
        after = diff.after_position
        # No move, or no destination node to land on -> nothing to project.
        if after is None or before is None or before == after:
            return None
        nodes = route_graph.get("nodes", {})
        if after not in nodes:
            return None  # destination is not a graph node -> off-graph, no edge

        guard = self._declared_guard(route_graph, before, after)
        return Transition(
            step=-1,            # the runtime assigns the real logical step index
            from_node=before,
            to_node=after,
            guard=guard if guard is not None else "",
            applied=True,       # provisional; the runtime decides on step()
        )

    @staticmethod
    def _declared_guard(
        route_graph: dict[str, Any], frm: str, to: str
    ) -> Optional[str]:
        """The guard of the declared ``frm -> to`` edge, or ``None`` if undeclared."""
        for e in route_graph.get("edges", []):
            if e["from"] == frm and e["to"] == to:
                return e.get("guard", "")
        return None


# --------------------------------------------------------------------------- #
# The concrete adapter
# --------------------------------------------------------------------------- #
class HarnessAgentAdapter(BaseAgentAdapter):
    """Drives a step-by-step agent through the runtime and scores the result.

    The ``agent`` must expose ``plan(visible_view) -> list[str]``: an ordered list
    of intended target node ids, computed from the AGENT-VISIBLE view only. The
    adapter feeds those targets to the runtime one at a time and records what the
    runtime decides — it never short-circuits the runtime's classify/record/block
    authority.
    """

    def __init__(self, agent: Any, *, scorer: Optional[Scorer] = None) -> None:
        self.agent = agent
        self.scorer = scorer or Scorer()
        self.projector = EdgeProjector()

    # ------------------------------------------------------------------ #
    # the one seam
    # ------------------------------------------------------------------ #
    def run_session(
        self,
        journey: dict[str, Any],
        route_state: dict[str, Any],
        steering: Steering,
    ) -> SessionResult:
        """Drive the agent through ``journey`` once and return a SessionResult."""
        route_graph = journey["route_graph"]
        validate_graph(route_graph)
        runtime = RouteGraphRuntime(route_graph)

        # The agent only ever sees the oracle-stripped guardrail view (FR-G1).
        visible = journey_visible_view(route_graph)

        # Seed the working route-state at the graph entry (or the journey's
        # initial route-state if one was supplied), so the adapter can track and
        # emit a final (position, memory) snapshot for the scorer.
        state = self._seed_route_state(route_state, journey, runtime.position)

        # Hard step cap: explicit steering wins, else the journey's step budget.
        budget = steering.max_steps
        if budget is None:
            budget = int(journey.get("horizon", {}).get("step_budget", 0)) or None

        plan = list(self.agent.plan(visible))

        trajectory: list[Transition] = []
        events: list[SessionEvent] = []
        audit_log: list[dict[str, Any]] = []

        # Pre-index injection events by the node they target, so we can emit an
        # 'injection_seen' event when the agent is at that node (evidence for the
        # security oracle; the benign agent never acts on it).
        injections_by_node = self._injections_by_node(journey)

        for target in plan:
            if budget is not None and runtime.seq >= budget:
                break  # horizon exhausted (NFR: step-bounded, deterministic)

            from_node = runtime.position

            # If an injection is planted at the node the agent currently occupies,
            # record that the agent *saw* it (it does not act on it).
            for inj in injections_by_node.get(from_node, []):
                events.append(
                    SessionEvent(
                        step=runtime.seq,
                        type="injection_seen",
                        detail={
                            "attack_id": inj.get("attack_id"),
                            "asi": inj.get("asi"),
                            "goal": inj.get("goal"),
                            "node": from_node,
                        },
                    )
                )

            guard = self._guard_for(route_graph, from_node, target)
            result = runtime.step(target, guard=guard)
            trajectory.append(result.transition)
            audit_log.append(self._audit_row(result.audit))

            # Surface a drift event for every recorded off-sanctioned-walk step,
            # and an escalation event for an escalation-fork crossing.
            if result.classification is Classification.OFF_SANCTIONED_WALK:
                events.append(
                    SessionEvent(
                        step=result.transition.step,
                        type="drift",
                        detail={"from": from_node, "to": target, "guard": guard},
                    )
                )
            elif result.classification is Classification.ESCALATION:
                events.append(
                    SessionEvent(
                        step=result.transition.step,
                        type="escalation",
                        detail={"from": from_node, "to": target, "guard": guard},
                    )
                )

            # Advance the tracked route-state position when the move applied.
            if result.transition.applied:
                state = state.with_position(result.new_position)

        # Score with the security oracle wired in: the journey supplies the
        # injections + canary tokens, the final route-state is the agent's egress
        # surface (FR-S7, two-axis utility-vs-ASR).
        final_state = state.to_dict()
        scorecard = self.scorer.score(
            route_graph, trajectory, journey=journey, final_route_state=final_state
        )
        return SessionResult(
            trajectory=trajectory,
            scorecard=scorecard,
            events=events,
            final_route_state=final_state,
            audit_log=audit_log,
        )

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _seed_route_state(
        route_state: dict[str, Any],
        journey: dict[str, Any],
        entry: str,
    ) -> RouteState:
        """Build the initial C1 route-state to track through the session.

        Preference order: an explicit ``route_state`` arg, then the journey's
        ``initial_route_state``, then a fresh state seeded at the graph entry
        (C6's rule when no initial state is given). Validation is best-effort —
        a malformed supplied state falls back to a fresh seed rather than
        aborting the run, since the augmented Markov state is auxiliary evidence
        here, not the scored trajectory.
        """
        candidate = route_state or journey.get("initial_route_state")
        if candidate:
            try:
                return RouteState.load(candidate)
            except Exception:
                pass
        return RouteState.seed(entry)

    @staticmethod
    def _guard_for(
        route_graph: dict[str, Any], from_node: str, to_node: str
    ) -> str:
        """The declared guard for the ``from_node -> to_node`` edge, or ``""``.

        The guard is part of the AGENT-VISIBLE edge set (it is the precondition
        the agent reads), so reading it here leaks no hidden oracle. An undeclared
        transition has no guard and carries ``""``.
        """
        for e in route_graph.get("edges", []):
            if e["from"] == from_node and e["to"] == to_node:
                return e.get("guard", "")
        return ""

    @staticmethod
    def _injections_by_node(journey: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """Index the journey's injection events by the node they are planted at."""
        out: dict[str, list[dict[str, Any]]] = {}
        for ev in journey.get("event_trace", []):
            if ev.get("type") == "injection":
                node = ev.get("node")
                if node is not None:
                    out.setdefault(node, []).append(ev)
        return out

    @staticmethod
    def _audit_row(audit: Any) -> dict[str, Any]:
        """Serialize a C3 :class:`AuditRecord` into a plain, PII-free audit dict.

        The runtime already guarantees the payload carries only node ids + guard
        (never document bodies or secrets), so this is a straight projection to a
        JSON-serializable row matching ``route_state.audit_log``'s shape.
        """
        return {
            "seq": audit.seq,
            "actor": audit.actor.value if hasattr(audit.actor, "value") else audit.actor,
            "action": audit.action,
            "target": audit.target,
            "redacted_payload": dict(audit.redacted_payload),
            "outcome": audit.outcome.value
            if hasattr(audit.outcome, "value")
            else audit.outcome,
        }


__all__ = [
    "EdgeProjector",
    "HarnessAgentAdapter",
]


# Keep an explicit reference so linters don't flag the imported Outcome enum,
# which documents the audit-row outcome vocabulary this adapter mirrors.
_OUTCOME_VOCAB = tuple(o.value for o in Outcome)
