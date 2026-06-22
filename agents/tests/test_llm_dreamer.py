"""LLM Dreamer wiring — deterministic tests with a STUB model (no CLI call).

The model-backed Dreamer turns a raw completion into a ``GraphEditProposal`` and
feeds it to the SAME RSI gate the deterministic Ranger uses. These tests pin that
wiring with a stub that returns canned JSON, so they prove — without any model —
that (a) a safe edit is accepted, (b) an edit opening a forbidden path is rejected
by the gate (the axis10 invariant), (c) a heal removes a reachable trap, and
(d) malformed / empty output degrades to "no proposal" instead of crashing.

Run from the repo root::

    python -m unittest discover -s agents -p 'test_*.py'
"""

from __future__ import annotations

import copy
import unittest

from agents.llm_dreamer import LLMDreamer
from harness.rsi import (
    apply_edit, evaluate_edit, reachable_forbidden, run_rsi,
)


class _StubAgent:
    """Stands in for an LLMAgent: returns a fixed completion, tracks usage."""

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.usage = {"calls": 0}

    def complete(self, prompt: str) -> str:
        self.usage["calls"] += 1
        return self._reply


def _graph():
    # a -> b -> c (goal); x is a forbidden trap, unreachable in the clean graph.
    return {
        "entry": "a", "goal": "c",
        "nodes": {"a": {"kind": "task"}, "b": {"kind": "task"},
                  "c": {"kind": "absorbing"}, "x": {"kind": "forbidden"}},
        "edges": [{"from": "a", "to": "b", "guard": "", "cost": 1, "risk": "low"},
                  {"from": "b", "to": "c", "guard": "", "cost": 1, "risk": "low"}],
    }


class TestLLMDreamer(unittest.TestCase):
    def test_safe_shortcut_is_accepted(self) -> None:
        g = _graph()
        reply = '{"add_edges":[{"from":"a","to":"c","cost":1,"risk":"low"}],"remove_edges":[],"rationale":"learned express completion"}'
        props = LLMDreamer(_StubAgent(reply)).propose_cycle(g, cycle=1)
        self.assertEqual(len(props), 1)
        self.assertTrue(evaluate_edit(g, props[0]).accepted)

    def test_edit_opening_forbidden_path_is_rejected(self) -> None:
        """The axis10 invariant: an edit that makes the trap reachable is rejected."""
        g = _graph()
        reply = '{"add_edges":[{"from":"a","to":"x"}],"remove_edges":[]}'
        props = LLMDreamer(_StubAgent(reply)).propose_cycle(g, cycle=1)
        verdict = evaluate_edit(g, props[0])
        self.assertFalse(verdict.accepted)
        self.assertIn("forbidden", verdict.rejected_reason)

    def test_heal_removes_reachable_trap(self) -> None:
        poisoned = copy.deepcopy(_graph())
        poisoned["edges"].append({"from": "b", "to": "x", "guard": "", "cost": 1, "risk": "low"})
        self.assertEqual(reachable_forbidden(poisoned, {"x"}), {"x"})
        reply = '{"add_edges":[],"remove_edges":[{"from":"b","to":"x"}],"rationale":"heal poisoned reconstruction"}'
        props = LLMDreamer(_StubAgent(reply)).propose_cycle(poisoned, cycle=1)
        self.assertTrue(evaluate_edit(poisoned, props[0]).accepted)
        healed = apply_edit(poisoned, props[0])
        self.assertEqual(reachable_forbidden(healed, {"x"}), set())

    def test_malformed_or_empty_output_yields_no_proposal(self) -> None:
        g = _graph()
        self.assertEqual(LLMDreamer(_StubAgent("sorry, no json")).propose_cycle(g, cycle=1), [])
        self.assertEqual(
            LLMDreamer(_StubAgent('{"add_edges":[],"remove_edges":[]}')).propose_cycle(g, cycle=1), [])

    def test_gate_on_rejects_off_applies_through_run_rsi(self) -> None:
        """End-to-end through run_rsi: the gate rejects the unsafe edit; the ungated
        ablation applies it (forbidden becomes reachable) — exactly axis10's signal."""
        g = _graph()
        reply = '{"add_edges":[{"from":"a","to":"x"}],"remove_edges":[]}'
        _, gated, _ = run_rsi(g, LLMDreamer(_StubAgent(reply)), cycles=1, gated=True)
        self.assertEqual((gated[0].accepted, gated[0].rejected), (0, 1))
        _, ungated, final = run_rsi(g, LLMDreamer(_StubAgent(reply)), cycles=1, gated=False)
        self.assertEqual(ungated[0].accepted, 1)
        self.assertEqual(reachable_forbidden(final, {"x"}), {"x"})


if __name__ == "__main__":
    unittest.main()
