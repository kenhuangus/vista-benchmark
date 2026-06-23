"""Scaled corpus (threat §1) — generation, stratification, and the POWERED premium.

Proves the dataset scales: ~100 journeys, each PROVEN valid (fail->pass) by the
generate-with-verifier, stratified across domain x split x difficulty — and that the
long-view premium (Ranger recall 1.0 vs naive 0.0, both safe) holds on EVERY one of
them, not just the curated 6. This is the powered counterpart of
agents/tests/test_corpus_eval.py.

    python -m unittest journeys.tests.test_scaled_corpus
"""

from __future__ import annotations

import unittest

from contracts.adapter import Steering
from agents.adapter import HarnessAgentAdapter
from agents.naive_agent import NaiveAgent
from agents.ranger import RangerAgent
from journeys.scaled_corpus import (
    DOMAINS, SPLITS, TIERS, scaled_corpus, scaled_specs, scaled_summary,
)


def _score(agent, journey) -> dict:
    return HarnessAgentAdapter(agent).run_session(
        journey, journey.get("initial_route_state", {}), Steering(seed=0)
    ).scorecard


class TestScaledCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.specs = scaled_specs()
        cls.corpus = scaled_corpus()  # raises if any journey fails fail->pass verification

    def test_scaled_to_roughly_a_hundred(self) -> None:
        self.assertEqual(len(self.corpus), 96)
        self.assertGreaterEqual(len(self.corpus), 50)  # the "tens to hundreds" bar

    def test_unique_ids(self) -> None:
        ids = [j["id"] for j in self.corpus]
        self.assertEqual(len(ids), len(set(ids)))

    def test_stratification_balanced(self) -> None:
        s = scaled_summary()
        self.assertEqual(set(s["by_domain"]), set(DOMAINS))
        self.assertEqual(set(s["by_split"]), set(SPLITS))
        self.assertEqual(set(s["by_tier"]), set(TIERS))
        # every cell equally populated.
        self.assertEqual(len(set(s["by_domain"].values())), 1)
        self.assertEqual(len(set(s["by_tier"].values())), 1)

    def test_difficulty_increases_subgoal_count(self) -> None:
        # easy=3 subgoals ... expert=6 subgoals (longer-horizon foresight).
        by_tier_subgoals = {}
        for spec, j in zip(self.specs, self.corpus):
            tier = spec.id.rsplit("-", 2)[1]
            by_tier_subgoals.setdefault(tier, set()).add(len(j["route_graph"]["subgoal_states"]))
        for tier, n in TIERS.items():
            self.assertEqual(by_tier_subgoals[tier], {n})

    def test_long_view_premium_holds_on_every_scaled_journey(self) -> None:
        for j in self.corpus:
            n = _score(NaiveAgent(), j)["axes"]["axis06_verification_calibration"]["recall"]
            r = _score(RangerAgent(), j)["axes"]["axis06_verification_calibration"]["recall"]
            with self.subTest(journey=j["id"]):
                self.assertEqual(n, 0.0)
                self.assertEqual(r, 1.0)

    def test_both_agents_safe_and_complete_on_every_scaled_journey(self) -> None:
        for j in self.corpus:
            for Agent in (NaiveAgent, RangerAgent):
                sc = _score(Agent(), j)
                with self.subTest(journey=j["id"], agent=Agent.__name__):
                    self.assertTrue(sc["pass_predicate"]["goal_reached"])
                    self.assertEqual(
                        sc["axes"]["axis07_security_abuse_resistance"]["targeted_asr_mean"], 0.0)


if __name__ == "__main__":
    unittest.main()
