"""VISTA Bench — the deterministic harness (S1).

The harness is a deterministic INSTRUMENT (NFR-1): a fixed trajectory + seed
produces an identical scorecard, every time. There is NO wall-clock and NO RNG
anywhere in this package — time is a logical step index, and the seed flows in
only through :class:`contracts.adapter.Steering` for the (out-of-scope) agent.

Modules
-------
* :mod:`harness.route_state` — C1 route-state model: load / validate / serialize
  / diff. Carries the augmented Markov state ``(position, memory)``.
* :mod:`harness.scheduler`   — deterministic event scheduler: yields a journey's
  ``event_trace`` in order.
* :mod:`harness.runtime`     — the route-graph runtime: tracks the current
  position, classifies an attempted transition (ON_OPTIMAL_WALK /
  OFF_SANCTIONED_WALK / FORBIDDEN / ESCALATION), records off-walk steps, blocks
  forbidden-state crossings, and exposes ``visible_view`` (which NEVER leaks the
  hidden oracle).
* :mod:`harness.scorer`      — the graph oracle + axes for this slice
  (goal_progress, foresight = progress_rate + optimality_gap, alignment_drift,
  verification_calibration, pass_hat_k). Emits a scorecard dict. NO LLM judge,
  NO randomness.

Everything here is built STRICTLY against the frozen contracts in
``contracts/`` (C1, C2, C3, C4, C5). The contracts are read-only.
"""

from __future__ import annotations

from harness.route_state import RouteState, StateStepDiff
from harness.scheduler import EventScheduler
from harness.runtime import (
    Classification,
    RouteGraphRuntime,
    visible_view,
)
from harness.scorer import Scorer, score_session

__all__ = [
    "RouteState",
    "StateStepDiff",
    "EventScheduler",
    "Classification",
    "RouteGraphRuntime",
    "visible_view",
    "Scorer",
    "score_session",
]
