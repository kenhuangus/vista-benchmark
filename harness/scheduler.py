"""Deterministic event scheduler.

The scheduler is the deterministic clock of the harness (architecture.md §5,
step 1): given a journey (C6, ``journey.schema.json``), it yields the journey's
``event_trace`` **in declared order**. There is NO wall-clock and NO RNG — the
event ``t`` fields are LOGICAL sim-time labels (leg / step), never timestamps
(NFR-1). The order is exactly the array order in the journey, so the same
journey always replays the same stream.

The scheduler does not interpret events (facts vs drifts vs injections) — that
is the runtime's / agent's job. It only guarantees ordered, typed, replayable
delivery and a stable per-event index that downstream code can use as a logical
step anchor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator


# C6 event types (mirrored from journey.schema.json so the scheduler can reject
# an unknown type rather than silently passing it on).
_EVENT_TYPES = {"fact", "drift", "escalation_fork", "injection", "slow_burn"}


class SchedulerError(ValueError):
    """Raised when a journey's event_trace is malformed."""


@dataclass(frozen=True)
class ScheduledEvent:
    """One event handed out by the scheduler, with a stable logical index.

    ``index`` is the 0-based position in the event_trace (a deterministic
    logical step anchor). ``t`` is the journey's own logical sim-time label.
    ``payload`` is the original event dict (read-only by convention).
    """

    index: int
    t: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventScheduler:
    """Yields a journey's ``event_trace`` in order, deterministically.

    Construct with a journey dict (C6). :meth:`events` returns a fresh iterator
    each call, so the same scheduler can be replayed any number of times and
    always produces an identical stream.
    """

    __slots__ = ("_events",)

    def __init__(self, journey: dict[str, Any]) -> None:
        trace = journey.get("event_trace")
        if trace is None:
            raise SchedulerError("journey is missing required 'event_trace'")
        if not isinstance(trace, list):
            raise SchedulerError("journey.event_trace must be an array")

        scheduled: list[ScheduledEvent] = []
        for i, ev in enumerate(trace):
            if not isinstance(ev, dict):
                raise SchedulerError(f"event_trace[{i}] must be an object")
            for req in ("t", "type"):
                if req not in ev:
                    raise SchedulerError(f"event_trace[{i}] missing required {req!r}")
            etype = ev["type"]
            if etype not in _EVENT_TYPES:
                raise SchedulerError(
                    f"event_trace[{i}].type {etype!r} not in {sorted(_EVENT_TYPES)}"
                )
            t = ev["t"]
            if not isinstance(t, str):
                raise SchedulerError(f"event_trace[{i}].t must be a logical-time string")
            scheduled.append(ScheduledEvent(index=i, t=t, type=etype, payload=dict(ev)))
        self._events: tuple[ScheduledEvent, ...] = tuple(scheduled)

    def __len__(self) -> int:
        return len(self._events)

    def events(self) -> Iterator[ScheduledEvent]:
        """Yield every scheduled event in declared order (fresh each call)."""
        yield from self._events

    def of_type(self, etype: str) -> Iterator[ScheduledEvent]:
        """Yield only events of ``etype``, in order (e.g. all injections)."""
        for ev in self._events:
            if ev.type == etype:
                yield ev

    def as_list(self) -> list[ScheduledEvent]:
        """A list snapshot of the ordered stream (convenience for tests)."""
        return list(self._events)


__all__ = ["EventScheduler", "ScheduledEvent", "SchedulerError"]
