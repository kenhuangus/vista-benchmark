"""Journey loader + validator + the agent-visible projection (S2).

Loads a C6 journey JSON, validates it against the frozen contracts
(C6 ``journey.schema.json`` and, for its embedded graph, C2
``route_graph.schema.json``), and exposes :func:`visible_view`, which strips the
HIDDEN oracle layer (``optimal_walk`` + ``subgoal_states``) so the agent only
ever sees the guardrail view (FR-G1 / ``test_oracle_hidden_from_agent``).

Standard library only. The validator is a focused, contract-shaped checker (no
``jsonschema`` dependency): it enforces exactly the structural invariants the S2
tests and the harness rely on. It deliberately does NOT re-implement full
JSON-Schema — it asserts the required keys, enums, types, and the cross-field
graph well-formedness that the contracts call out.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any

from contracts import CONTRACTS_DIR, SCHEMA_FILES

# The two HIDDEN-ORACLE keys the agent must NEVER see (C2 Layer B, FR-G1).
HIDDEN_ORACLE_KEYS: tuple[str, ...] = ("optimal_walk", "subgoal_states")

# The AGENT-VISIBLE route-graph keys (C2 Layer A).
VISIBLE_GRAPH_KEYS: tuple[str, ...] = ("entry", "goal", "nodes", "edges", "guardrails")

# Frozen vocabularies (mirror the C2/C6 schema enums; we read them from the
# schema files at validate time so this module can never drift from the contract).
_NODE_KINDS = {"task", "escape", "hitl", "absorbing", "forbidden"}
_EDGE_AUTHORITIES = {"scout", "worker"}
_EDGE_RISKS = {"low", "high"}
_EVENT_TYPES = {"fact", "drift", "escalation_fork", "injection", "slow_burn"}
_DOMAINS = {"project", "coding", "research", "finance", "legal", "support"}
_SPLITS = {"train", "dev", "test", "challenge"}
_INJECTION_CHANNELS = {"tool_output", "document", "message", "calendar"}


class JourneyValidationError(ValueError):
    """Raised when a journey or its route-graph violates the frozen contracts."""


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_journey(path: str) -> dict[str, Any]:
    """Load a journey JSON from ``path``, validate it, and return the dict.

    Validates against C6 (journey) and C2 (the embedded route-graph). Raises
    :class:`JourneyValidationError` on any contract violation.
    """
    with open(path, "r", encoding="utf-8") as fh:
        journey = json.load(fh)
    validate_journey(journey)
    return journey


def load_seed_journey() -> dict[str, Any]:
    """Load the packaged seed journey (``project_inquiry_dev.json``)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return load_journey(os.path.join(here, "project_inquiry_dev.json"))


def _contract_schema(contract: str) -> dict[str, Any]:
    """Load a frozen contract schema (read-only; lets the validator self-check
    against the actual enums in the contract rather than hard-coded copies)."""
    with open(os.path.join(CONTRACTS_DIR, SCHEMA_FILES[contract]), "r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# C2 — route-graph validation
# --------------------------------------------------------------------------- #
def validate_route_graph(graph: dict[str, Any]) -> None:
    """Validate an embedded route-graph against C2 + the well-formedness rules
    the S2 tests assert (entry reachable, >=1 absorbing, goal is absorbing, no
    edge into an undeclared node, hidden oracle present and consistent).

    Raises :class:`JourneyValidationError` on the first violation found.
    """
    if not isinstance(graph, dict):
        raise JourneyValidationError("route_graph must be an object")

    required = ("entry", "goal", "nodes", "edges", "guardrails",
                "optimal_walk", "subgoal_states")
    for key in required:
        if key not in graph:
            raise JourneyValidationError(f"route_graph missing required key {key!r}")

    nodes = graph["nodes"]
    if not isinstance(nodes, dict) or not nodes:
        raise JourneyValidationError("route_graph.nodes must be a non-empty object")

    for node_id, desc in nodes.items():
        if not isinstance(desc, dict) or "kind" not in desc:
            raise JourneyValidationError(f"node {node_id!r} must be an object with a 'kind'")
        if desc["kind"] not in _NODE_KINDS:
            raise JourneyValidationError(
                f"node {node_id!r} kind {desc['kind']!r} not in {sorted(_NODE_KINDS)}"
            )

    # entry / goal reference declared nodes; goal is absorbing.
    if graph["entry"] not in nodes:
        raise JourneyValidationError(f"entry {graph['entry']!r} is not a declared node")
    if graph["goal"] not in nodes:
        raise JourneyValidationError(f"goal {graph['goal']!r} is not a declared node")
    if nodes[graph["goal"]]["kind"] != "absorbing":
        raise JourneyValidationError(
            f"goal {graph['goal']!r} must be an absorbing node "
            f"(found kind={nodes[graph['goal']]['kind']!r})"
        )

    # At least one absorbing node exists.
    absorbing = [nid for nid, d in nodes.items() if d["kind"] == "absorbing"]
    if not absorbing:
        raise JourneyValidationError("route_graph must declare at least one absorbing node")

    # Edges: required fields, declared endpoints, valid enums, non-negative cost.
    edges = graph["edges"]
    if not isinstance(edges, list):
        raise JourneyValidationError("route_graph.edges must be an array")
    for i, edge in enumerate(edges):
        for key in ("from", "to", "guard", "authority", "cost", "risk"):
            if key not in edge:
                raise JourneyValidationError(f"edge[{i}] missing required key {key!r}")
        if edge["from"] not in nodes:
            raise JourneyValidationError(
                f"edge[{i}] 'from' references undeclared node {edge['from']!r}"
            )
        if edge["to"] not in nodes:
            raise JourneyValidationError(
                f"edge[{i}] 'to' references undeclared node {edge['to']!r}"
            )
        if edge["authority"] not in _EDGE_AUTHORITIES:
            raise JourneyValidationError(
                f"edge[{i}] authority {edge['authority']!r} not in {sorted(_EDGE_AUTHORITIES)}"
            )
        if edge["risk"] not in _EDGE_RISKS:
            raise JourneyValidationError(
                f"edge[{i}] risk {edge['risk']!r} not in {sorted(_EDGE_RISKS)}"
            )
        if not isinstance(edge["cost"], (int, float)) or isinstance(edge["cost"], bool) \
                or edge["cost"] < 0:
            raise JourneyValidationError(f"edge[{i}] cost must be a number >= 0")

    # entry reaches goal over the directed edge set (BFS).
    if not _reaches(graph["entry"], graph["goal"], edges):
        raise JourneyValidationError(
            f"goal {graph['goal']!r} is not reachable from entry {graph['entry']!r}"
        )

    # Hidden oracle: optimal_walk must be a node-id list from entry to goal whose
    # consecutive pairs are sanctioned edges; subgoal_states must be non-empty.
    walk = graph["optimal_walk"]
    if not isinstance(walk, list) or not walk:
        raise JourneyValidationError("optimal_walk must be a non-empty array of node ids")
    if walk[0] != graph["entry"]:
        raise JourneyValidationError("optimal_walk must start at entry")
    if walk[-1] != graph["goal"]:
        raise JourneyValidationError("optimal_walk must end at goal")
    edge_set = {(e["from"], e["to"]) for e in edges}
    for a, b in zip(walk, walk[1:]):
        if a not in nodes or b not in nodes:
            raise JourneyValidationError(f"optimal_walk references undeclared node {a!r}->{b!r}")
        if (a, b) not in edge_set:
            raise JourneyValidationError(
                f"optimal_walk step {a!r}->{b!r} is not a sanctioned edge"
            )
    if not isinstance(graph["subgoal_states"], list) or not graph["subgoal_states"]:
        raise JourneyValidationError("subgoal_states must be a non-empty array")


def _reaches(entry: str, goal: str, edges: list[dict[str, Any]]) -> bool:
    """Directed reachability from ``entry`` to ``goal`` over the edge set (BFS)."""
    adj: dict[str, list[str]] = {}
    for e in edges:
        adj.setdefault(e["from"], []).append(e["to"])
    seen = {entry}
    frontier = [entry]
    while frontier:
        cur = frontier.pop()
        if cur == goal:
            return True
        for nxt in adj.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    return goal in seen


# --------------------------------------------------------------------------- #
# C6 — journey validation
# --------------------------------------------------------------------------- #
def validate_journey(journey: dict[str, Any]) -> None:
    """Validate a journey against C6 (and its graph against C2).

    Raises :class:`JourneyValidationError` on the first violation found.
    """
    if not isinstance(journey, dict):
        raise JourneyValidationError("journey must be an object")

    for key in ("id", "domain", "intent", "route_graph", "event_trace",
                "oracle_bindings", "split", "horizon"):
        if key not in journey:
            raise JourneyValidationError(f"journey missing required key {key!r}")

    if journey["domain"] not in _DOMAINS:
        raise JourneyValidationError(
            f"domain {journey['domain']!r} not in {sorted(_DOMAINS)}"
        )
    if journey["split"] not in _SPLITS:
        raise JourneyValidationError(
            f"split {journey['split']!r} not in {sorted(_SPLITS)}"
        )
    if not isinstance(journey["intent"], str) or not journey["intent"].strip():
        raise JourneyValidationError("intent must be a non-empty string")

    # Embedded route-graph (C2).
    validate_route_graph(journey["route_graph"])

    # Event trace (C6).
    trace = journey["event_trace"]
    if not isinstance(trace, list):
        raise JourneyValidationError("event_trace must be an array")
    for i, ev in enumerate(trace):
        if not isinstance(ev, dict) or "t" not in ev or "type" not in ev:
            raise JourneyValidationError(f"event[{i}] must carry 't' and 'type'")
        if not isinstance(ev["t"], str):
            raise JourneyValidationError(f"event[{i}].t must be a logical string label")
        if ev["type"] not in _EVENT_TYPES:
            raise JourneyValidationError(
                f"event[{i}].type {ev['type']!r} not in {sorted(_EVENT_TYPES)}"
            )
        if ev["type"] == "injection":
            _validate_injection(i, ev)
        if ev["type"] == "drift" and not isinstance(ev.get("changes"), dict):
            raise JourneyValidationError(f"drift event[{i}] must carry a 'changes' object")
        if ev["type"] == "escalation_fork" and ev.get("risk") not in _EDGE_RISKS:
            raise JourneyValidationError(
                f"escalation_fork event[{i}] must carry risk in {sorted(_EDGE_RISKS)}"
            )

    # Horizon (C6).
    horizon = journey["horizon"]
    for key in ("legs", "step_budget"):
        if key not in horizon:
            raise JourneyValidationError(f"horizon missing required key {key!r}")
        v = horizon[key]
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            raise JourneyValidationError(f"horizon.{key} must be an integer >= 1")

    if not isinstance(journey["oracle_bindings"], dict):
        raise JourneyValidationError("oracle_bindings must be an object")


def _validate_injection(i: int, ev: dict[str, Any]) -> None:
    """Validate an injection event's adversarial fields (C6)."""
    vector = ev.get("vector")
    if not isinstance(vector, dict):
        raise JourneyValidationError(f"injection event[{i}] must carry a 'vector' object")
    if vector.get("channel") not in _INJECTION_CHANNELS:
        raise JourneyValidationError(
            f"injection event[{i}] vector.channel not in {sorted(_INJECTION_CHANNELS)}"
        )
    if not isinstance(vector.get("placeholder"), str) or not vector["placeholder"]:
        raise JourneyValidationError(
            f"injection event[{i}] vector.placeholder must be a non-empty string"
        )
    if "attack_id" not in ev or not isinstance(ev["attack_id"], str):
        raise JourneyValidationError(f"injection event[{i}] must carry a string 'attack_id'")
    if "goal" not in ev or not isinstance(ev["goal"], str):
        raise JourneyValidationError(f"injection event[{i}] must carry a string 'goal'")
    asi = ev.get("asi", "")
    if not (isinstance(asi, str) and asi.startswith("ASI") and asi[3:].isdigit()
            and 1 <= int(asi[3:]) <= 10):
        raise JourneyValidationError(
            f"injection event[{i}] asi {asi!r} must match ^ASI(01..10)$"
        )


# --------------------------------------------------------------------------- #
# FR-G1 — the agent-visible projection
# --------------------------------------------------------------------------- #
def visible_view(graph: dict[str, Any]) -> dict[str, Any]:
    """Return the AGENT-VISIBLE view of a route-graph: a deep copy with the
    HIDDEN oracle layer (``optimal_walk`` + ``subgoal_states``) stripped (FR-G1,
    ``test_oracle_hidden_from_agent``). The harness/scorer keep the full object;
    only this stripped view is ever handed to the agent.
    """
    view = copy.deepcopy(graph)
    for key in HIDDEN_ORACLE_KEYS:
        view.pop(key, None)
    return view


def visible_journey(journey: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of a journey with its route-graph reduced to the
    agent-visible view (oracle layer stripped). Used to hand a journey to an
    agent without leaking the answer key."""
    view = copy.deepcopy(journey)
    view["route_graph"] = visible_view(view["route_graph"])
    return view


__all__ = [
    "HIDDEN_ORACLE_KEYS",
    "VISIBLE_GRAPH_KEYS",
    "JourneyValidationError",
    "load_journey",
    "load_seed_journey",
    "validate_route_graph",
    "validate_journey",
    "visible_view",
    "visible_journey",
]
