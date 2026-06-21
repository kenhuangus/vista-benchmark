"""C3 — Agent-tool API (typed stubs, the capability surface).

This module FREEZES the tool interface the Ranger sub-agents call. It is a
contract: typed ``Protocol`` / ``ABC`` + ``dataclass`` shapes with NO business
logic. Every method raises ``NotImplementedError`` — S3 (Worker/Scout) and S4
(Dreamer) implement *behind* this contract.

The capability split (architecture.md §4, FR-A2 / FR-Sec2) is encoded in the
TYPES, not just in prose:

* ``WorkerTools``  — touches untrusted data; can READ/SEARCH and *request* a
  guarded edge, but has **no authority** to author edges and **no secrets**.
* ``ScoutTools``   — holds planning **authority**; authors edges and escalates;
  by construction it never receives raw untrusted data (only structured results).
* ``DreamerTools`` — offline; records consolidations and *proposes* working-graph
  edits (lineage + capped budget); never the sanctioned graph.

PII hygiene (FR-Sec3): every tool call yields an :class:`AuditRecord` whose
payload is **already redacted** (SSN/secret/PII -> last-4 or hash AFTER dropping
PII keys). Raw PII must never reach an audit row, a log, or a scorecard.

Enforcing tests (architecture.md §6): ``test_tool_signatures``,
``test_worker_no_authority``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable


# --------------------------------------------------------------------------- #
# Capability / role taxonomy
# --------------------------------------------------------------------------- #
class Authority(str, Enum):
    """Who may fire / author an edge (mirrors C2 edge.authority)."""

    SCOUT = "scout"
    WORKER = "worker"


class Actor(str, Enum):
    """Audit-row actor identities."""

    SCOUT = "scout"
    WORKER = "worker"
    DREAMER = "dreamer"
    HARNESS = "harness"
    HUMAN = "human"


class Outcome(str, Enum):
    """The result of a tool call / transition (mirrors route_state.audit_log.outcome)."""

    OK = "ok"
    BLOCKED = "blocked"                  # forbidden-state crossing blocked (FR-G2)
    RECORDED_OFFWALK = "recorded_offwalk"  # off-sanctioned-walk transition recorded (FR-G2)
    ESCALATED = "escalated"              # routed to a HITL edge (FR-G4 / calibration)
    REJECTED = "rejected"                # e.g. Worker tried to author an edge (no authority)


# --------------------------------------------------------------------------- #
# PII-redacted audit record (FR-Sec3)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AuditRecord:
    """A single PII-REDACTED audit row appended to ``route_state.audit_log``.

    ``redacted_payload`` MUST already have SSNs/secrets/PII reduced to last-4 or
    hashed (after dropping PII keys). Constructing an AuditRecord with raw PII is
    a contract violation — the redaction happens BEFORE this object exists.
    """

    seq: int                      # monotonic step index — NO wall-clock (NFR-1)
    actor: Actor
    action: str
    target: Optional[str] = None
    redacted_payload: dict[str, Any] = field(default_factory=dict)
    outcome: Outcome = Outcome.OK


@dataclass(frozen=True)
class ReadResult:
    """Structured result of a read/search. ``untrusted`` flags data the Scout must
    never receive raw (only the Worker handles ``untrusted=True`` bodies)."""

    items: list[dict[str, Any]] = field(default_factory=list)
    untrusted: bool = False


@dataclass(frozen=True)
class EdgeRequest:
    """A Worker's *request* to fire one guarded edge (it cannot author edges)."""

    from_node: str
    to_node: str
    guard: str


@dataclass(frozen=True)
class EdgeResult:
    """Outcome of an attempted edge fire, as decided by the runtime."""

    applied: bool
    outcome: Outcome
    new_position: Optional[str] = None
    audit: Optional[AuditRecord] = None


@dataclass(frozen=True)
class EscalationRequest:
    """A request to take a HITL / escalation edge at a risk:high fork."""

    fork_id: str
    reason: str


@dataclass(frozen=True)
class DreamRecord:
    """A Dreamer cycle entry (consolidation / belief-revision / self-audit)."""

    cycle: int
    kind: str           # consolidate | revise_belief | self_audit | propose_graph_edit
    rationale: str
    parent_graph_hash: Optional[str] = None  # lineage (FR-A4)


@dataclass(frozen=True)
class GraphEditProposal:
    """A reviewable WORKING-graph diff (never the sanctioned graph, FR-A3/A4)."""

    parent_graph_hash: str          # lineage
    rationale: str
    add_edges: list[dict[str, Any]] = field(default_factory=list)
    remove_edges: list[dict[str, Any]] = field(default_factory=list)
    merge_nodes: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class GraphEditResult:
    """Verdict on a proposed edit. ``rejected_reason`` is set when reachability
    analysis finds a new path to a forbidden state, or the budget is exceeded
    (FR-S4 / FR-A4)."""

    accepted: bool
    rejected_reason: Optional[str] = None


# --------------------------------------------------------------------------- #
# Common (read-only) tools — available to every component
# --------------------------------------------------------------------------- #
@runtime_checkable
class ReadTools(Protocol):
    """Read/search the shared workspace. The ONLY capability the Scout shares with
    the Worker — but the Scout receives ``untrusted=False`` results only."""

    def read(self, ref: str) -> ReadResult: ...
    def search(self, query: str) -> ReadResult: ...


# --------------------------------------------------------------------------- #
# Worker — sandboxed executor: NO authority, NO secrets (FR-A2 / FR-Sec2)
# --------------------------------------------------------------------------- #
class WorkerTools(ABC):
    """The ONLY component that touches untrusted terrain. It can read/search and
    *request* one Scout-authorized guarded edge — it CANNOT author edges, hold
    secrets, escalate on its own authority, or edit the graph. The ABSENCE of
    ``escalate`` / ``propose_graph_edit`` / authority here is the contract
    (test_worker_no_authority)."""

    #: Declared, machine-checkable capability set — asserted by the contract test.
    CAPABILITIES: frozenset[str] = frozenset({"read", "search", "request_edge"})
    #: The Worker holds no planning authority and no secrets.
    HAS_AUTHORITY: bool = False
    HAS_SECRETS: bool = False

    @abstractmethod
    def read(self, ref: str) -> ReadResult:
        """Read a workspace ref (may return untrusted bodies)."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str) -> ReadResult:
        """Search the workspace (may return untrusted bodies)."""
        raise NotImplementedError

    @abstractmethod
    def request_edge(self, request: EdgeRequest) -> EdgeResult:
        """Request that the runtime fire ONE guarded, Scout-authorized edge. The
        runtime applies it, records an off-walk step, or blocks a forbidden
        crossing. The Worker never decides the outcome itself."""
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Scout — planner: holds AUTHORITY; never receives raw untrusted data
# --------------------------------------------------------------------------- #
class ScoutTools(ABC):
    """Holds planning authority: authors edges (sets intent) and escalates the
    few risk:high forks. By construction it sees only STRUCTURED results, never
    raw untrusted text — so an injection in a tool output cannot reach the
    component with planning authority (architecture.md §4)."""

    CAPABILITIES: frozenset[str] = frozenset(
        {"read", "search", "authorize_edge", "escalate"}
    )
    HAS_AUTHORITY: bool = True
    HAS_SECRETS: bool = False

    @abstractmethod
    def read(self, ref: str) -> ReadResult:
        """Read STRUCTURED results only (untrusted bodies are withheld)."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str) -> ReadResult:
        """Search; results are structured, untrusted-data-free."""
        raise NotImplementedError

    @abstractmethod
    def authorize_edge(self, from_node: str, to_node: str, guard: str) -> AuditRecord:
        """Author (authorize) an edge on the working graph — sets intent that the
        Worker may then request. Worker-only callers must NOT have this method."""
        raise NotImplementedError

    @abstractmethod
    def escalate(self, request: EscalationRequest) -> EdgeResult:
        """Take a HITL / escalation edge at a risk:high fork instead of guessing."""
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Dreamer — offline RSI: record cycles, PROPOSE working-graph edits (gated)
# --------------------------------------------------------------------------- #
class DreamerTools(ABC):
    """Offline, guardrailed self-improvement. Records consolidations / belief
    revisions / self-audits and PROPOSES working-graph edits as reviewable diffs
    with lineage + a capped budget. It edits ONLY Ranger's working graph, never
    the sanctioned graph (C2)."""

    CAPABILITIES: frozenset[str] = frozenset(
        {"read", "search", "record_dream", "propose_graph_edit"}
    )
    HAS_AUTHORITY: bool = False  # cannot fire/author live edges; only proposes
    HAS_SECRETS: bool = False

    @abstractmethod
    def record_dream(self, record: DreamRecord) -> AuditRecord:
        """Append a consolidation / belief-revision / self-audit entry to the
        dream_journal (lineage required for graph-edit kinds, FR-A4)."""
        raise NotImplementedError

    @abstractmethod
    def propose_graph_edit(self, proposal: GraphEditProposal) -> GraphEditResult:
        """Propose a WORKING-graph diff. The scorer rejects it if reachability
        analysis finds a new path to a forbidden state, or the per-cycle budget
        is exceeded (FR-S4 / FR-A4)."""
        raise NotImplementedError


__all__ = [
    "Authority",
    "Actor",
    "Outcome",
    "AuditRecord",
    "ReadResult",
    "EdgeRequest",
    "EdgeResult",
    "EscalationRequest",
    "DreamRecord",
    "GraphEditProposal",
    "GraphEditResult",
    "ReadTools",
    "WorkerTools",
    "ScoutTools",
    "DreamerTools",
]
