"""C5 — AgentAdapter (the one seam between harness and agent).

The harness scores Ranger and external agents (Claude Code, Codex, OpenClaw,
Hermes) through EXACTLY ONE interface so the comparison is fair
(architecture.md §1, FR-B1/B3). This module FREEZES that seam: the
``AgentAdapter`` protocol, the ``run_session`` signature, the ``SessionResult``
dataclass, and the external state-diff -> sanctioned-edge projection stub.

No business logic — typed stubs raising ``NotImplementedError``. S3 implements
behind this contract.

Enforcing tests (architecture.md §6): ``test_adapter_protocol``,
``test_external_stub_runs``, ``test_state_diff_projection``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


# --------------------------------------------------------------------------- #
# Inputs to a session
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Steering:
    """Run-time knobs the harness hands the adapter. Carries the determinism
    seed (NFR-1: fixed trajectory + seed -> identical score) and ablation flags
    (Scout OFF = long-view premium; sandbox OFF; Dreamer OFF)."""

    seed: int = 0
    scout_enabled: bool = True       # Scout OFF collapses Ranger to a single model
    sandbox_enabled: bool = True     # privilege-separation ablation
    dreamer_enabled: bool = True     # self-improvement-trend ablation
    max_steps: Optional[int] = None  # hard cap, defaults to journey.horizon.step_budget


# --------------------------------------------------------------------------- #
# Trajectory + events (what the harness records and the scorer reads)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Transition:
    """One realized step: a move from ``from_node`` to ``to_node`` (or a blocked
    attempt). ``on_optimal_walk`` / ``forbidden_attempt`` are filled by the
    runtime for scoring; ``off_walk`` marks a recorded off-sanctioned-walk step."""

    step: int                        # monotonic — NO wall-clock (NFR-1)
    from_node: str
    to_node: str
    guard: str
    applied: bool
    on_optimal_walk: bool = False
    off_walk: bool = False
    forbidden_attempt: bool = False


@dataclass(frozen=True)
class SessionEvent:
    """An event observed/emitted during the session (escalation, injection seen,
    dream cycle, etc.) — the scorer's evidence beyond bare transitions."""

    step: int
    type: str                        # escalation | injection_seen | dream_cycle | fact | drift
    detail: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Output of a session — the contract the scorer consumes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SessionResult:
    """The result of driving an agent through one journey. THE shape every
    adapter returns and the scorer (C4) consumes.

    * ``trajectory`` — ordered realized transitions (already projected onto the
      sanctioned graph for external agents).
    * ``scorecard`` — per-axis + headline metrics (rubric.schema.json / C4 shape).
    * ``events``    — escalations, injections seen, dream cycles, etc.
    * ``final_route_state`` — the C1 route-state at session end (scorer reads it).
    * ``audit_log`` — PII-redacted audit rows (FR-Sec3); also mirrored in route_state.
    """

    trajectory: list[Transition] = field(default_factory=list)
    scorecard: dict[str, Any] = field(default_factory=dict)
    events: list[SessionEvent] = field(default_factory=list)
    final_route_state: dict[str, Any] = field(default_factory=dict)
    audit_log: list[dict[str, Any]] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# The one seam
# --------------------------------------------------------------------------- #
@runtime_checkable
class AgentAdapter(Protocol):
    """The single interface the harness drives. Implemented once for Ranger and
    once per external agent. ``run_session`` is the frozen signature."""

    def run_session(
        self,
        journey: dict[str, Any],
        route_state: dict[str, Any],
        steering: Steering,
    ) -> SessionResult:
        """Drive the agent through one journey and return a SessionResult.

        Args:
            journey:     a C6 journey instance (journey.schema.json).
            route_state: the initial C1 route-state (route_state.schema.json).
            steering:    seed + ablation flags (deterministic; NFR-1).

        Returns:
            SessionResult — trajectory + scorecard + events + final route-state.
        """
        ...


class BaseAgentAdapter(ABC):
    """ABC scaffold for concrete adapters (Ranger + external). Provides the frozen
    ``run_session`` signature for subclasses to implement."""

    @abstractmethod
    def run_session(
        self,
        journey: dict[str, Any],
        route_state: dict[str, Any],
        steering: Steering,
    ) -> SessionResult:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# External state-diff -> sanctioned-edge projection (FR-B3, OQ-4)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StateDiff:
    """A before/after route-state delta from a free-form (external) agent that
    never declared graph nodes. ``changed_keys`` are the route_state paths that
    moved between two steps."""

    before_position: Optional[str]
    after_position: Optional[str]
    changed_keys: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


class StateDiffProjector(ABC):
    """Projects an external agent's state-diffs onto sanctioned-graph edges
    (architecture.md §7, benchmark-design.md §4). Best-effort and LOSSY — it may
    misattribute; S3 validates it on a known-good trace and never fakes a number
    (test_state_diff_projection)."""

    @abstractmethod
    def project(
        self,
        diff: StateDiff,
        route_graph: dict[str, Any],
    ) -> Optional[Transition]:
        """Map one state-diff onto the single best-matching sanctioned edge.

        Returns the inferred :class:`Transition`, or ``None`` when no sanctioned
        edge plausibly matches (the diff is recorded as off-graph)."""
        raise NotImplementedError


__all__ = [
    "Steering",
    "Transition",
    "SessionEvent",
    "SessionResult",
    "AgentAdapter",
    "BaseAgentAdapter",
    "StateDiff",
    "StateDiffProjector",
]
