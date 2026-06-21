"""VISTA Bench — S3 agent seam + reference agent (the integration slice).

This package wires an agent to the deterministic harness through the ONE frozen
seam (C5 ``contracts.adapter.AgentAdapter``). It contains:

* :mod:`agents.adapter` — :class:`HarnessAgentAdapter`, the concrete
  ``run_session`` that drives an agent step-by-step through the
  :class:`harness.runtime.RouteGraphRuntime` (apply / record off-walk / block
  forbidden per :meth:`classify`), assembles the C5 ``SessionResult``, and scores
  it with the deterministic :class:`harness.scorer.Scorer`. Also a simple
  external state-diff -> sanctioned-edge projector (:class:`EdgeProjector`).
* :mod:`agents.naive_agent` — :class:`NaiveAgent`, a trivial DETERMINISTIC
  reference agent that sees ONLY the visible guardrail view, greedily walks
  toward the goal, and takes at least ONE declared detour OFF the optimal walk
  (via ``handle_diversion``) so an off-sanctioned-walk step is recorded. It never
  crosses ``funds_sent``.

Everything is built STRICTLY against the frozen contracts (C2/C5) and the real
interfaces the other seats wrote in ``harness/`` and ``journeys/``. Standard
library only; deterministic (NFR-1: no wall-clock, no RNG).
"""

from __future__ import annotations

from agents.adapter import EdgeProjector, HarnessAgentAdapter
from agents.naive_agent import NaiveAgent

__all__ = [
    "EdgeProjector",
    "HarnessAgentAdapter",
    "NaiveAgent",
]
