"""VISTA Bench — S2 graph & dataset slice.

The SANCTIONED ground-truth route-graph plus ONE complete project-stewardship
journey, built STRICTLY against the frozen contracts in ``contracts/`` (C2
route-graph, C6 journey, C1 route-state).

Public surface:

* :data:`JOURNEYS_DIR`          — directory holding the journey JSON instances.
* ``project_inquiry_dev.json``  — the seed journey (architecture.md §6.1 example).
* :mod:`journeys.loader`        — load + validate a journey vs C6 and its graph
  vs C2; ``visible_view`` strips the hidden oracle layer (FR-G1).
* :mod:`journeys.generator`     — a small generate-with-verifier stub (τ²-bench
  style) that builds the seed journey from atomic (init, solution, assertion)
  pieces and asserts the goal-reached oracle holds.

No third-party deps — standard library only (NFR: deterministic, stdlib-only).
"""

from __future__ import annotations

import os

JOURNEYS_DIR = os.path.dirname(os.path.abspath(__file__))

#: The seed journey filename (a C6 instance, validated against the contracts).
SEED_JOURNEY = "project_inquiry_dev.json"

__all__ = ["JOURNEYS_DIR", "SEED_JOURNEY"]
