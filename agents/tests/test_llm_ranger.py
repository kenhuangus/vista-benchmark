"""Model-backed three-role Ranger — wiring tests with a STUB model (no CLI call).

These pin the one property that makes :class:`LLMRanger` the model-backed mirror
of :class:`RangerAgent`: a SINGLE agent fills Scout (plan), Worker (act), and backs
the Dreamer (propose_cycle), so all three roles share one object and one usage/cost
ledger. A stub stands in for the LLMAgent so nothing contacts a model.

Run from the repo root::

    python -m unittest discover -s agents -p 'test_*.py'
"""

from __future__ import annotations

import unittest

from agents.llm_ranger import LLMRanger


class _StubLLM:
    """Stands in for an LLMAgent: plan/act/complete each bump the shared ledger."""

    def __init__(self) -> None:
        self.model = "stub-model"
        self.seed = 7
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        self.ctx = None

    def set_journey_context(self, journey) -> None:
        self.ctx = journey

    def plan(self, visible_view):
        self.usage["calls"] += 1
        return ["b", "c"]

    def act(self, observation):
        self.usage["calls"] += 1
        return {"action": "done"}

    def complete(self, prompt: str) -> str:
        self.usage["calls"] += 1
        return '{"add_edges":[],"remove_edges":[]}'


def _graph():
    return {
        "entry": "a", "goal": "c",
        "nodes": {"a": {"kind": "task"}, "b": {"kind": "task"}, "c": {"kind": "absorbing"}},
        "edges": [{"from": "a", "to": "b", "guard": "", "cost": 1, "risk": "low"},
                  {"from": "b", "to": "c", "guard": "", "cost": 1, "risk": "low"}],
    }


class TestLLMRanger(unittest.TestCase):
    def test_three_roles_share_one_agent(self) -> None:
        stub = _StubLLM()
        r = LLMRanger(llm=stub)
        self.assertIs(r.scout, stub)
        self.assertIs(r.worker, stub)
        self.assertIs(r.dreamer.agent, stub)
        self.assertIs(r.usage, stub.usage)

    def test_name_and_seed_read_from_the_injected_agent(self) -> None:
        r = LLMRanger(llm=_StubLLM())
        self.assertEqual(r.name, "llm-ranger:stub-model")
        self.assertEqual(r.model, "stub-model")
        self.assertEqual(r.seed, 7)

    def test_context_and_seams_delegate(self) -> None:
        stub = _StubLLM()
        r = LLMRanger(llm=stub)
        r.set_journey_context({"id": "j1"})
        self.assertEqual(stub.ctx, {"id": "j1"})
        self.assertEqual(r.plan({"nodes": {"b": {}, "c": {}}, "entry": "a"}), ["b", "c"])
        self.assertEqual(r.act({"current": "a"}), {"action": "done"})

    def test_all_three_roles_bill_the_one_ledger(self) -> None:
        stub = _StubLLM()
        r = LLMRanger(llm=stub)
        r.plan({"nodes": {}, "entry": "a"})           # Scout
        r.act({"current": "a"})                        # Worker
        r.dreamer.propose_cycle(_graph(), cycle=1)     # Dreamer (one complete() call)
        self.assertEqual(r.usage["calls"], 3)          # one shared ledger, all roles


if __name__ == "__main__":
    unittest.main()
