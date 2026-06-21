"""C1 route-state model — load / validate / serialize / diff.

The route-state (contract C1, ``route_state.schema.json``) is the single
serializable workspace the harness diffs between steps. The AUGMENTED MARKOV
STATE that VISTA scores over is the pair ``(position, memory)`` — the Markov
property holds over *graph position + relevant memory snapshot*, not position
alone (architecture.md §3, FR-G5).

This module gives S1 a thin, dependency-free model over that schema:

* :class:`RouteState` — wraps the C1 dict. ``load`` validates the minimal C1
  shape (``position`` + ``memory`` + enum-constrained sub-fields) WITHOUT a
  third-party JSON-Schema library (stdlib only). ``to_dict`` serializes back to
  a plain JSON-round-trippable dict (deep copy — no shared mutable references).
* :class:`StateStepDiff` — the (position, memory) delta between two steps. The
  runtime reads ``moved`` / ``from_position`` / ``to_position`` to detect a
  transition; the scorer reads ``changed_memory_keys`` for the state-based axes.

Determinism (NFR-1): no wall-clock, no RNG. Diffs and serialization are pure
functions of their inputs. Keys are sorted where order would otherwise be
implementation-defined, so two equal states always serialize identically.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Optional


# C1 enums (mirrored from route_state.schema.json so validation is self-contained).
_TICKET_STATUS = {"open", "in_progress", "blocked", "done", "cancelled"}
_AUDIT_ACTORS = {"scout", "worker", "dreamer", "harness", "human"}
_AUDIT_OUTCOMES = {"ok", "blocked", "recorded_offwalk", "escalated", "rejected"}
_DREAM_KINDS = {"consolidate", "revise_belief", "self_audit", "propose_graph_edit"}
_MEMORY_KEYS = {"facts", "commitments", "open_questions", "beliefs"}


class RouteStateError(ValueError):
    """Raised when a dict does not satisfy the C1 route-state contract."""


@dataclass(frozen=True)
class StateStepDiff:
    """The ``(position, memory)`` delta between two consecutive steps.

    The runtime uses ``moved`` (position changed) to detect a transition; the
    scorer uses ``changed_memory_keys`` for state-based axes. Pure data — built
    by :meth:`RouteState.diff`.
    """

    from_position: Optional[str]
    to_position: Optional[str]
    changed_memory_keys: list[str] = field(default_factory=list)

    @property
    def moved(self) -> bool:
        """True when the graph position changed between the two states."""
        return self.from_position != self.to_position

    @property
    def changed(self) -> bool:
        """True when position OR any memory sub-key changed."""
        return self.moved or bool(self.changed_memory_keys)


class RouteState:
    """A validated, serializable C1 route-state.

    Construct via :meth:`load` (validates) for untrusted input, or directly from
    a known-good dict. The wrapped dict is deep-copied on construction so the
    caller cannot mutate our internal state through a shared reference.
    """

    __slots__ = ("_data",)

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = copy.deepcopy(data)

    # ------------------------------------------------------------------ #
    # construction / validation
    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls, data: dict[str, Any]) -> "RouteState":
        """Validate ``data`` against the minimal C1 shape and wrap it.

        Stdlib-only structural validation (no jsonschema dependency). Checks the
        required keys, the ``memory`` sub-shape, and the closed enums on
        ``tickets.status`` / ``audit_log`` rows / ``dream_journal`` rows. Raises
        :class:`RouteStateError` on the first violation.
        """
        cls._validate(data)
        return cls(data)

    @classmethod
    def seed(cls, entry: str) -> "RouteState":
        """A fresh route-state seeded at ``entry`` with empty memory.

        Mirrors C6's rule: when a journey omits ``initial_route_state`` the
        harness seeds ``position = route_graph.entry`` with empty memory.
        """
        return cls(
            {
                "position": entry,
                "memory": {
                    "facts": {},
                    "commitments": [],
                    "open_questions": [],
                    "beliefs": {},
                },
            }
        )

    @staticmethod
    def _validate(data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise RouteStateError("route-state must be an object")
        for required in ("position", "memory"):
            if required not in data:
                raise RouteStateError(f"route-state missing required key {required!r}")
        if not isinstance(data["position"], str) or not data["position"]:
            raise RouteStateError("route-state.position must be a non-empty node id")

        memory = data["memory"]
        if not isinstance(memory, dict):
            raise RouteStateError("route-state.memory must be an object")
        for key in memory:
            if key not in _MEMORY_KEYS:
                raise RouteStateError(
                    f"route-state.memory has unexpected key {key!r}; "
                    f"allowed: {sorted(_MEMORY_KEYS)}"
                )
        for obj_key in ("facts", "beliefs"):
            if obj_key in memory and not isinstance(memory[obj_key], dict):
                raise RouteStateError(f"route-state.memory.{obj_key} must be an object")
        for arr_key in ("commitments", "open_questions"):
            if arr_key in memory:
                val = memory[arr_key]
                if not isinstance(val, list) or not all(isinstance(s, str) for s in val):
                    raise RouteStateError(
                        f"route-state.memory.{arr_key} must be a list of strings"
                    )

        # tickets[*].status enum
        tickets = data.get("tickets")
        if tickets is not None:
            if not isinstance(tickets, dict):
                raise RouteStateError("route-state.tickets must be an object")
            for tid, ticket in tickets.items():
                status = (ticket or {}).get("status")
                if status is not None and status not in _TICKET_STATUS:
                    raise RouteStateError(
                        f"ticket {tid!r} has invalid status {status!r}"
                    )

        # audit_log[*] actor/outcome enums + required {seq, actor, action}
        audit_log = data.get("audit_log")
        if audit_log is not None:
            if not isinstance(audit_log, list):
                raise RouteStateError("route-state.audit_log must be an array")
            for i, row in enumerate(audit_log):
                if not isinstance(row, dict):
                    raise RouteStateError(f"audit_log[{i}] must be an object")
                for req in ("seq", "actor", "action"):
                    if req not in row:
                        raise RouteStateError(f"audit_log[{i}] missing {req!r}")
                if row["actor"] not in _AUDIT_ACTORS:
                    raise RouteStateError(
                        f"audit_log[{i}].actor {row['actor']!r} not in {sorted(_AUDIT_ACTORS)}"
                    )
                outcome = row.get("outcome")
                if outcome is not None and outcome not in _AUDIT_OUTCOMES:
                    raise RouteStateError(
                        f"audit_log[{i}].outcome {outcome!r} not in {sorted(_AUDIT_OUTCOMES)}"
                    )

        # dream_journal[*] kind enum + required {cycle, kind}
        dream_journal = data.get("dream_journal")
        if dream_journal is not None:
            if not isinstance(dream_journal, list):
                raise RouteStateError("route-state.dream_journal must be an array")
            for i, row in enumerate(dream_journal):
                if not isinstance(row, dict):
                    raise RouteStateError(f"dream_journal[{i}] must be an object")
                for req in ("cycle", "kind"):
                    if req not in row:
                        raise RouteStateError(f"dream_journal[{i}] missing {req!r}")
                if row["kind"] not in _DREAM_KINDS:
                    raise RouteStateError(
                        f"dream_journal[{i}].kind {row['kind']!r} not in {sorted(_DREAM_KINDS)}"
                    )

    # ------------------------------------------------------------------ #
    # accessors
    # ------------------------------------------------------------------ #
    @property
    def position(self) -> str:
        """The current node id (augmented Markov state, part 1)."""
        return self._data["position"]

    @property
    def memory(self) -> dict[str, Any]:
        """The memory snapshot (augmented Markov state, part 2). A live view —
        mutate through :meth:`with_position` / :meth:`with_memory` for a copy."""
        return self._data["memory"]

    def get(self, key: str, default: Any = None) -> Any:
        """Read any top-level route-state key (docs/tickets/records/...)."""
        return self._data.get(key, default)

    # ------------------------------------------------------------------ #
    # immutable updates (the runtime advances state by producing new states)
    # ------------------------------------------------------------------ #
    def with_position(self, position: str) -> "RouteState":
        """Return a NEW route-state at ``position`` (this one is unchanged)."""
        new = copy.deepcopy(self._data)
        new["position"] = position
        return RouteState(new)

    def with_memory(self, memory: dict[str, Any]) -> "RouteState":
        """Return a NEW route-state whose ``memory`` is replaced by ``memory``."""
        new = copy.deepcopy(self._data)
        new["memory"] = copy.deepcopy(memory)
        return RouteState(new)

    # ------------------------------------------------------------------ #
    # serialization + diff (pure, deterministic)
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        """A deep copy of the wrapped dict (JSON-round-trippable, no aliasing)."""
        return copy.deepcopy(self._data)

    def to_json(self) -> str:
        """Canonical JSON: ``sort_keys=True`` so equal states serialize equal
        byte-for-byte (determinism, NFR-1)."""
        return json.dumps(self._data, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, text: str) -> "RouteState":
        """Parse + validate a canonical-JSON route-state (round-trips to_json)."""
        return cls.load(json.loads(text))

    def diff(self, other: "RouteState") -> StateStepDiff:
        """The ``(position, memory)`` delta from ``self`` -> ``other``.

        ``changed_memory_keys`` is the sorted set of top-level memory keys whose
        value differs (by canonical-JSON equality, so order within nested
        objects is normalized). Pure function — determinism (NFR-1).
        """
        changed: list[str] = []
        for key in sorted(_MEMORY_KEYS):
            before = self.memory.get(key)
            after = other.memory.get(key)
            if json.dumps(before, sort_keys=True) != json.dumps(after, sort_keys=True):
                changed.append(key)
        return StateStepDiff(
            from_position=self.position,
            to_position=other.position,
            changed_memory_keys=changed,
        )

    # ------------------------------------------------------------------ #
    # equality / repr
    # ------------------------------------------------------------------ #
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RouteState):
            return NotImplemented
        return self.to_json() == other.to_json()

    def __hash__(self) -> int:
        return hash(self.to_json())

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"RouteState(position={self.position!r})"


__all__ = ["RouteState", "StateStepDiff", "RouteStateError"]
