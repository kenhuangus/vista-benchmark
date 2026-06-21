"""Stepwise adapter — controls that prove the security axis actually fires.

The stepwise adapter (:mod:`agents.stepwise_adapter`) drives an ``act``-based
agent one decision at a time so a mid-trajectory injection forces a real action.
Its whole reason to exist is the security axis (axis07), so these tests pin the
two ends of that axis with scripted (no-LLM, fully deterministic) agents:

* a **resistant** reference (ranger replay) reaches the goal and leaks nothing —
  ``asr == 0`` (without this, an ``asr == 0`` from a real model is meaningless);
* a **hijacked** control that echoes the injected payload into memory is caught —
  ``asr == 1`` with both canaries on the egress surface (without this, the oracle
  could be silently dead and every model would "pass").

Plus the mechanical guarantees: notes/sends land on the egress surfaces, reaching
the goal stops the loop, and the run is deterministic.

Run from the repo root::

    python -m unittest discover -s agents -p 'test_*.py'
"""

from __future__ import annotations

import json
import unittest

from contracts.adapter import Steering
from journeys.loader import load_seed_journey
from agents.ranger import RangerAgent
from agents.stepwise_adapter import PlanReplayAgent, StepwiseAdapter


class _HijackedAgent:
    """Positive control: obeys the injection — copies the untrusted payload into
    memory once, then advances toward the goal (so it still 'completes')."""

    def __init__(self) -> None:
        self._complied = False

    def set_journey_context(self, journey) -> None:  # parity with LLMAgent
        pass

    def act(self, observation):
        untrusted = observation.get("untrusted_input") or []
        if untrusted and not self._complied:
            self._complied = True
            return {"action": "note", "text": untrusted[0]}
        moves = observation.get("moves_from_here") or []
        if moves:
            return {"action": "move", "target": moves[0]["to"]}
        return {"action": "done"}


class TestStepwiseSecurityControls(unittest.TestCase):
    def setUp(self) -> None:
        self.journey = load_seed_journey()
        self.canaries = (
            self.journey["oracle_bindings"]["security"]["canary_egress"]
        )

    def _sec(self, result):
        return result.scorecard["axes"]["axis07_security_abuse_resistance"]

    # -- negative control: resistant reference leaks nothing --------------- #
    def test_ranger_replay_resists_injection(self) -> None:
        result = StepwiseAdapter(
            PlanReplayAgent(RangerAgent())
        ).run_session(self.journey, Steering(max_steps=12))
        sec = self._sec(result)
        self.assertEqual(sec["targeted_asr_mean"], 0.0)
        self.assertFalse(sec["canary_egress_detected"])
        self.assertEqual(sec["leaked_canaries"], [])
        # the resistant reference still does the job: reaches goal, escalates.
        self.assertTrue(result.scorecard["pass_predicate"]["goal_reached"])
        self.assertEqual(
            result.scorecard["axes"]["axis06_verification_calibration"]["recall"], 1.0
        )

    # -- positive control: a hijacked agent IS caught ---------------------- #
    def test_hijacked_agent_leaks_canary(self) -> None:
        result = StepwiseAdapter(_HijackedAgent()).run_session(
            self.journey, Steering(max_steps=12)
        )
        sec = self._sec(result)
        self.assertEqual(sec["targeted_asr_mean"], 1.0)
        self.assertTrue(sec["canary_egress_detected"])
        self.assertEqual(set(sec["leaked_canaries"]), set(self.canaries))
        # egress (not a forbidden crossing) is the channel here: the runtime
        # blocks forbidden moves, so the leak is the agent writing the payload.
        self.assertFalse(sec["forbidden_crossing_detected"])

    # -- the payload lands on the agent-write egress surfaces -------------- #
    def test_note_and_send_land_on_egress_surfaces(self) -> None:
        result = StepwiseAdapter(_HijackedAgent()).run_session(
            self.journey, Steering(max_steps=12)
        )
        commitments = result.final_route_state["memory"]["commitments"]
        self.assertTrue(
            any(self.canaries[0] in c.get("text", "") for c in commitments),
            "the injected account must appear in a written commitment",
        )

    # -- reaching the goal stops the loop before the cap ------------------- #
    def test_reaching_goal_stops_early(self) -> None:
        result = StepwiseAdapter(
            PlanReplayAgent(RangerAgent())
        ).run_session(self.journey, Steering(max_steps=24))
        self.assertTrue(result.scorecard["pass_predicate"]["goal_reached"])
        # stopped well under the cap (the seed journey's optimal walk is short).
        self.assertLess(len(result.audit_log), 24)

    # -- determinism: same scripted agent -> identical scorecard ----------- #
    def test_run_is_deterministic(self) -> None:
        a = StepwiseAdapter(PlanReplayAgent(RangerAgent())).run_session(
            self.journey, Steering(max_steps=24)
        )
        b = StepwiseAdapter(PlanReplayAgent(RangerAgent())).run_session(
            self.journey, Steering(max_steps=24)
        )
        self.assertEqual(
            json.dumps(a.scorecard, sort_keys=True),
            json.dumps(b.scorecard, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
