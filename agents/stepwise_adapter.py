"""Stepwise (ReAct-style) adapter — drives an agent one decision at a time so a
mid-trajectory prompt injection forces a real action choice (Pillar A, security).

The planning adapter (:class:`agents.adapter.HarnessAgentAdapter`) asks the agent
for a whole route up front, so an injected payload is only ever *shown*, never
*acted on*. This adapter instead runs a turn loop: at each step the agent observes
its current node, its memory, the sanctioned moves, and any UNTRUSTED content
planted at that node (the attack surface), then commits to ONE action:

    {"action": "move", "target": "<node id>"}     attempt a transition (any node)
    {"action": "note", "text": "..."}             write a commitment into memory
    {"action": "send", "text": "...", "to": "..."}  send a message
    {"action": "done"}                            stop

Why this exercises axis07: the runtime BLOCKS a forbidden crossing, so the only
way an attack scores ASR>0 is **canary egress** — the agent echoing the attacker's
account / wire instruction onto a surface it writes (memory, a sent message). A
``note``/``send`` carrying the injected payload leaks a canary; a resistant agent
keeps working and writes nothing attacker-controlled. Scoring is the SAME pure
deterministic :class:`harness.scorer.Scorer`; only the driving loop differs.

The agent must expose ``act(observation) -> dict``. Agents that only ``plan`` are
driven by a thin plan-replay shim (:class:`PlanReplayAgent`) for reference.
"""

from __future__ import annotations

import copy
from typing import Any, Optional

from contracts.adapter import SessionEvent, SessionResult, Steering, Transition
from harness.runtime import Classification, RouteGraphRuntime, validate_graph
from harness.scorer import Scorer
from journeys.loader import visible_view as journey_visible_view

# Message "from" value for an agent-sent message (so the egress oracle counts it).
_AGENT_SENDER = "worker"


class PlanReplayAgent:
    """Wrap a plan-only agent (naive/ranger) as a stepwise agent: it pre-plans
    once and replays one move per turn, ignoring observations. A benign reference
    that never notes/sends attacker content (so it leaks no canary)."""

    def __init__(self, agent: Any) -> None:
        self._agent = agent
        self.name = getattr(agent, "name", agent.__class__.__name__)
        self._plan: Optional[list[str]] = None
        self._i = 0

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        if self._plan is None:
            self._plan = list(self._agent.plan(observation["_visible_view"]))
        if self._i >= len(self._plan):
            return {"action": "done"}
        target = self._plan[self._i]
        self._i += 1
        return {"action": "move", "target": target}


class StepwiseAdapter:
    """Drive an ``act``-based agent turn by turn through the runtime and score it."""

    def __init__(self, agent: Any, *, scorer: Optional[Scorer] = None) -> None:
        self.agent = agent
        self.scorer = scorer or Scorer()

    def run_session(
        self,
        journey: dict[str, Any],
        steering: Optional[Steering] = None,
    ) -> SessionResult:
        route_graph = journey["route_graph"]
        validate_graph(route_graph)
        runtime = RouteGraphRuntime(route_graph)
        visible = journey_visible_view(route_graph)

        # Working route-state (a plain dict) seeded from the journey; the agent's
        # writes land here and become the egress surface the security oracle scans.
        state = copy.deepcopy(journey.get("initial_route_state", {})) or {}
        state.setdefault("memory", {}).setdefault("commitments", [])
        state.setdefault("messages", [])
        state["position"] = runtime.position

        budget = (steering.max_steps if steering and steering.max_steps else None) \
            or int(journey.get("horizon", {}).get("step_budget", 0)) or 24
        injections_by_node = self._injections_by_node(journey)

        trajectory: list[Transition] = []
        events: list[SessionEvent] = []
        action_log: list[dict[str, Any]] = []

        turns = 0
        while turns < budget:
            turns += 1
            here = runtime.position
            untrusted = injections_by_node.get(here, [])
            if untrusted:
                events.append(SessionEvent(
                    step=runtime.seq, type="injection_seen",
                    detail={"node": here, "attack_id": untrusted[0].get("attack_id"),
                            "asi": untrusted[0].get("asi"), "goal": untrusted[0].get("goal")},
                ))
            observation = self._observation(visible, here, state, untrusted, action_log)
            observation["_visible_view"] = visible  # for the plan-replay shim

            action = self.agent.act(observation) or {"action": "done"}
            kind = action.get("action", "done")
            action_log.append({"step": runtime.seq, "at": here, "action": action})

            if kind == "done":
                break
            if kind == "move":
                target = action.get("target", "")
                guard = self._guard_for(route_graph, here, target)
                result = runtime.step(target, guard=guard)
                trajectory.append(result.transition)
                if result.classification is Classification.OFF_SANCTIONED_WALK:
                    events.append(SessionEvent(step=result.transition.step, type="drift",
                                               detail={"from": here, "to": target}))
                elif result.classification is Classification.ESCALATION:
                    events.append(SessionEvent(step=result.transition.step, type="escalation",
                                               detail={"from": here, "to": target}))
                elif result.classification is Classification.FORBIDDEN:
                    events.append(SessionEvent(step=result.transition.step, type="forbidden_attempt",
                                               detail={"from": here, "to": target}))
                if result.transition.applied:
                    state["position"] = result.new_position
                    if result.new_position == route_graph["goal"]:
                        break
            elif kind == "note":
                state["memory"]["commitments"].append(
                    {"by": "agent", "text": str(action.get("text", ""))})
            elif kind == "send":
                state["messages"].append({
                    "from": _AGENT_SENDER, "to": str(action.get("to", "external")),
                    "body": str(action.get("text", "")), "channel": "outbound"})
            # unknown action kinds are ignored (a no-op turn)

        scorecard = self.scorer.score(
            route_graph, trajectory, journey=journey, final_route_state=state)
        return SessionResult(
            trajectory=trajectory, scorecard=scorecard, events=events,
            final_route_state=state, audit_log=action_log)

    # ------------------------------------------------------------------ #
    # observation + helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _observation(visible, here, state, untrusted, action_log) -> dict[str, Any]:
        nodes = visible.get("nodes", {})
        moves = [e for e in visible.get("edges", []) if e["from"] == here]
        commitments = (state.get("memory", {}) or {}).get("commitments", [])
        return {
            "intent": None,  # filled by the runner via set_journey_context on the agent
            "current": here,
            "current_label": nodes.get(here, {}).get("label", ""),
            "nodes": nodes,
            "edges": visible.get("edges", []),
            "moves_from_here": moves,
            "guardrails": visible.get("guardrails", []),
            "goal": visible.get("goal"),
            "untrusted_input": [u.get("payload", "") for u in untrusted],
            "commitments": commitments,
            "history": [a["action"] for a in action_log],
        }

    @staticmethod
    def _injections_by_node(journey: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for ev in journey.get("event_trace", []):
            if ev.get("type") == "injection" and ev.get("node"):
                out.setdefault(ev["node"], []).append(ev)
        return out

    @staticmethod
    def _guard_for(route_graph, frm, to) -> str:
        for e in route_graph.get("edges", []):
            if e["from"] == frm and e["to"] == to:
                return e.get("guard", "")
        return ""


__all__ = ["StepwiseAdapter", "PlanReplayAgent"]
