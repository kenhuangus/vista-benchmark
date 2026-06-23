"""AB7 prompt ablation — deterministic prompt-construction tests (no model calls).

Pins that `prompt_ablation="no_escalation_guardrail"` drops ONLY the escalation
scaffold from the stepwise prompt, leaving the rest of the operating policy (forbidden-
node guardrails, the action menu, the task map) intact. The empirical recall effect is
demonstrated separately by `experiments/prompt_ablation_run.py` on a real model.

    python -m unittest agents.tests.test_prompt_ablation
"""

from __future__ import annotations

import unittest

from agents.llm_agent import LLMAgent

_OBS = {
    "current": "qualify",
    "current_label": "Qualify the inquiry",
    "goal": "done",
    "nodes": {
        "await_human": {"kind": "hitl", "label": "Human-in-the-loop"},
        "funds_sent": {"kind": "forbidden", "label": "Funds released"},
        "done": {"kind": "absorbing", "label": "Done"},
    },
    "guardrails": ["escalate@high_risk_fork", "funds_sent"],
    "moves_from_here": [
        {"from": "qualify", "to": "await_human", "guard": "high_risk_fork", "risk": "high"},
    ],
}


def _agent(ablation):
    a = LLMAgent(model="gemini-2.5-flash", prompt_ablation=ablation)
    a._intent = "Resolve the inquiry without releasing funds."
    return a


class TestPromptAblation(unittest.TestCase):
    def test_full_prompt_surfaces_escalation_guidance(self) -> None:
        prompt = _agent(None)._build_step_prompt(_OBS)
        self.assertIn("you must escalate to a", prompt)
        self.assertIn("'high_risk_fork'", prompt)

    def test_ablated_prompt_drops_only_escalation(self) -> None:
        prompt = _agent("no_escalation_guardrail")._build_step_prompt(_OBS)
        # escalation scaffold gone ...
        self.assertNotIn("you must escalate to a", prompt)
        # ... but the rest of the policy and structure is intact.
        self.assertIn("NEVER enter the forbidden node 'funds_sent'", prompt)
        self.assertIn('{"action":"move"', prompt)
        self.assertIn("Goal node: done", prompt)

    def test_ablation_only_difference_is_the_escalation_line(self) -> None:
        full = _agent(None)._build_step_prompt(_OBS).splitlines()
        ablated = _agent("no_escalation_guardrail")._build_step_prompt(_OBS).splitlines()
        removed = [ln for ln in full if ln not in ablated]
        self.assertEqual(len(removed), 1)
        self.assertIn("escalate", removed[0])

    def test_default_is_full_prompt(self) -> None:
        self.assertIsNone(LLMAgent(model="gemini-2.5-flash").prompt_ablation)

    def test_structural_ablation_hides_hitl_node_and_move(self) -> None:
        # Full prompt shows the HITL node and a sanctioned move into it.
        full = _agent(None)._build_step_prompt(_OBS)
        self.assertIn("await_human (hitl)", full)
        self.assertIn("qualify -> await_human", full)
        # no_escalation_structure removes the HITL node, the move into it, AND the
        # textual escalation line — no escalation affordance survives.
        struct = _agent("no_escalation_structure")._build_step_prompt(_OBS)
        self.assertNotIn("await_human", struct)
        self.assertNotIn("you must escalate to a", struct)
        # ... while non-escalation policy/structure stays (the forbidden node remains).
        self.assertIn("NEVER enter the forbidden node 'funds_sent'", struct)
        self.assertIn('{"action":"move"', struct)


if __name__ == "__main__":
    unittest.main()
