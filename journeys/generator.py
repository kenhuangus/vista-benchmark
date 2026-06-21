"""Generate-with-verifier stub for the seed journey (S2).

τ²-bench (2506.07982) style: a journey is built from atomic
``(init, solution, assertion)`` triples so the generator emits BOTH the journey
and its oracle, with *provable* validity — the goal-reached assertion must FAIL
on the empty init and PASS only after the solution walk is applied. That fail->
pass gap is what makes the oracle trustworthy rather than asserted.

This is intentionally small but genuine: the solution actually drives a
route-state along the hidden ``optimal_walk``, satisfying one gold subgoal per
sanctioned step, and the assertion is a real predicate over the resulting state
(position == goal AND every gold subgoal reached AND no forbidden crossing).
Deterministic: no wall-clock, no RNG (NFR-1).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable

from journeys.loader import load_seed_journey, validate_journey


# --------------------------------------------------------------------------- #
# Atomic pieces
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Triple:
    """One atomic generate-with-verifier unit.

    * ``init``      — the starting route-state (C1 shape).
    * ``solution``  — an ordered list of step appliers; each advances the
      route-state one sanctioned edge along the optimal walk and records the
      subgoal it satisfied.
    * ``assertion`` — the goal-reached oracle: a pure predicate over a
      route-state that returns True only when the journey's goal is genuinely met.
    """

    init: dict[str, Any]
    solution: list[Callable[[dict[str, Any]], None]]
    assertion: Callable[[dict[str, Any]], bool]


@dataclass
class GenerationResult:
    """Outcome of generate-with-verifier: the journey, plus the proof that the
    assertion FAILED on init and PASSED after the solution (validity gap)."""

    journey: dict[str, Any]
    failed_on_init: bool
    passed_after_solution: bool
    steps_applied: int = 0
    subgoals_reached: list[str] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        """A journey is verified iff the assertion FAILS before the solution and
        PASSES after — the τ²-bench provable-validity condition."""
        return self.failed_on_init and self.passed_after_solution


# --------------------------------------------------------------------------- #
# Building the assertion + solution from the (hidden) oracle layer
# --------------------------------------------------------------------------- #
def _goal_reached_assertion(graph: dict[str, Any]) -> Callable[[dict[str, Any]], bool]:
    """Compile the goal-reached oracle for a graph: position is the goal, every
    gold subgoal predicate is satisfied in memory.facts, and no forbidden node
    was ever crossed."""
    goal = graph["goal"]
    subgoals = list(graph["subgoal_states"])
    forbidden = {nid for nid, d in graph["nodes"].items() if d["kind"] == "forbidden"}

    def assertion(state: dict[str, Any]) -> bool:
        if state.get("position") != goal:
            return False
        if set(state.get("position_history", [])) & forbidden:
            return False
        reached = state.get("memory", {}).get("facts", {}).get("_subgoals_reached", [])
        return all(sg in reached for sg in subgoals)

    return assertion


def _solution_from_optimal_walk(graph: dict[str, Any]) -> list[Callable[[dict[str, Any]], None]]:
    """Build the solution as one step-applier per edge along the hidden
    optimal_walk. Each applier moves position and, when the step's guard names a
    gold subgoal, records that subgoal as reached."""
    walk = graph["optimal_walk"]
    subgoals = set(graph["subgoal_states"])
    edge_guard = {(e["from"], e["to"]): e["guard"] for e in graph["edges"]}

    steps: list[Callable[[dict[str, Any]], None]] = []
    for frm, to in zip(walk, walk[1:]):
        guard = edge_guard[(frm, to)]

        def step(state: dict[str, Any], _to: str = to, _guard: str = guard) -> None:
            state["position"] = _to
            state.setdefault("position_history", []).append(_to)
            if _guard in subgoals:
                reached = state["memory"]["facts"].setdefault("_subgoals_reached", [])
                if _guard not in reached:
                    reached.append(_guard)

        steps.append(step)
    return steps


def _empty_init(graph: dict[str, Any]) -> dict[str, Any]:
    """The empty starting state: position=entry, empty memory. The assertion must
    FAIL here (goal not reached, no subgoals)."""
    return {
        "position": graph["entry"],
        "position_history": [graph["entry"]],
        "memory": {"facts": {}, "commitments": [], "open_questions": [], "beliefs": {}},
    }


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def verify_journey(journey: dict[str, Any]) -> GenerationResult:
    """Generate-with-verifier for ANY journey (the generic prover).

    Validates the journey against the contracts, derives the (init, solution,
    assertion) triple from its hidden oracle layer, then PROVES validity: the
    goal-reached assertion FAILS on the empty init and PASSES after the solution
    walk (the τ²-bench validity gap). Pure + deterministic — works on a packaged
    seed, a hand-authored journey, or a synthesized one alike.
    """
    validate_journey(journey)  # contract gate first
    graph = journey["route_graph"]
    triple = Triple(
        init=_empty_init(graph),
        solution=_solution_from_optimal_walk(graph),
        assertion=_goal_reached_assertion(graph),
    )
    return run_with_verifier(journey, triple)


def build_seed_journey() -> GenerationResult:
    """Generate-with-verifier for the packaged seed journey (thin wrapper around
    :func:`verify_journey`)."""
    return verify_journey(load_seed_journey())


def run_with_verifier(journey: dict[str, Any], triple: Triple) -> GenerationResult:
    """Apply the verifier protocol to a journey + its triple and return the
    proof. Pure and deterministic."""
    # 1. Assertion must FAIL on the untouched init (the validity gap's lower edge).
    init_state = copy.deepcopy(triple.init)
    failed_on_init = not triple.assertion(init_state)

    # 2. Apply the solution walk step by step.
    state = copy.deepcopy(triple.init)
    steps_applied = 0
    for step in triple.solution:
        step(state)
        steps_applied += 1

    # 3. Assertion must PASS after the solution (the validity gap's upper edge).
    passed_after_solution = triple.assertion(state)

    subgoals_reached = list(
        state.get("memory", {}).get("facts", {}).get("_subgoals_reached", [])
    )
    return GenerationResult(
        journey=journey,
        failed_on_init=failed_on_init,
        passed_after_solution=passed_after_solution,
        steps_applied=steps_applied,
        subgoals_reached=subgoals_reached,
    )


__all__ = [
    "Triple",
    "GenerationResult",
    "verify_journey",
    "build_seed_journey",
    "run_with_verifier",
]
