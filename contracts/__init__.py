"""VISTA Bench — the SIX frozen contracts (C1-C6).

These are the shared interface every seat builds behind. The contract-test
suite in ``contracts/tests`` is the single CI merge gate.

* C1 ``route_state.schema.json``  — shared workspace + augmented Markov state
* C2 ``route_graph.schema.json``  — sanctioned route-graph (given guardrails / hidden oracle)
* C3 ``tools.py``                 — agent-tool API + capability split + PII-redacted audit
* C4 ``rubric.schema.json``       — ten axes + graph-oracle metrics + OWASP ASI ties
* C5 ``adapter.py``               — AgentAdapter.run_session -> SessionResult + state-diff projection
* C6 ``journey.schema.json``      — journey/dataset instance (event trace + oracle bindings + split)

Python stubs (C3, C5) are importable; JSON Schemas (C1, C2, C4, C6) load as
plain JSON. ``CONTRACTS_DIR`` is the directory holding all six files.
"""

from __future__ import annotations

import os

CONTRACTS_DIR = os.path.dirname(os.path.abspath(__file__))

SCHEMA_FILES = {
    "C1": "route_state.schema.json",
    "C2": "route_graph.schema.json",
    "C4": "rubric.schema.json",
    "C6": "journey.schema.json",
}

STUB_MODULES = {
    "C3": "tools.py",
    "C5": "adapter.py",
}

__all__ = ["CONTRACTS_DIR", "SCHEMA_FILES", "STUB_MODULES"]
