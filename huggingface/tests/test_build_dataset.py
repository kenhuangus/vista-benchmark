"""Gating tests for the published HuggingFace dataset export.

These lock in *defensibility*: the dataset cannot silently shrink back to the
6-journey seed, every published journey must re-prove valid (fail->pass) at build
time, and the stratified coverage (domains / splits / difficulty tiers / ASI attack
categories) must hold. `build_corpus()` itself raises on an unverified journey or an
id collision, so importing it here is already a verification pass; the assertions pin
the shape callers and the dataset card depend on.
"""

from __future__ import annotations

import json
import unittest

from huggingface.build_dataset import build_corpus, build_summary

# The defensibility floor. The dataset is built at 198; if a refactor drops it below
# this it stops being comparable to tau-bench (~165) / AgentDojo (~97) and the test
# should fail loudly rather than ship a 6-journey "benchmark".
_MIN_JOURNEYS = 150
_EXPECTED = 390

_CORE_FIELDS = {
    "id", "domain", "split", "intent", "horizon",
    "route_graph", "oracle_bindings", "event_trace", "initial_route_state",
}
_PROVENANCE_FIELDS = {
    "source", "difficulty_tier", "num_subgoals", "num_high_risk_forks",
    "attack_asi", "verified",
}


class TestBuildDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = build_corpus()           # raises on any unverified journey / dup id
        cls.summ = build_summary(cls.rows)

    def test_size_meets_defensibility_floor(self):
        self.assertGreaterEqual(len(self.rows), _MIN_JOURNEYS)
        self.assertEqual(len(self.rows), _EXPECTED)

    def test_every_journey_is_verified(self):
        self.assertTrue(all(r["verified"] for r in self.rows))
        self.assertTrue(self.summ["all_verified"])

    def test_ids_unique(self):
        ids = [r["id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_records_carry_core_and_provenance_fields(self):
        for r in self.rows:
            missing = (_CORE_FIELDS | _PROVENANCE_FIELDS) - set(r.keys())
            self.assertFalse(missing, f"{r['id']} missing {missing}")

    def test_stratified_coverage(self):
        self.assertEqual(
            set(self.summ["by_domain"]),
            {"project", "coding", "research", "finance", "legal", "support"},
        )
        self.assertEqual(set(self.summ["by_split"]), {"train", "dev", "test", "challenge"})
        self.assertTrue(
            {"easy", "medium", "hard", "expert"}.issubset(self.summ["by_difficulty_tier"])
        )
        # All 10 OWASP ASI categories are exercised across the published corpus.
        self.assertEqual(self.summ["num_attack_asi_categories"], 10)

    def test_provenance_breakdown(self):
        by_source = self.summ["by_source"]
        self.assertEqual(by_source.get("synthesized-scaled"), 384)
        self.assertEqual(by_source.get("handauthored"), 3)
        self.assertEqual(by_source.get("synthesized-core"), 3)

    def test_num_subgoals_matches_graph(self):
        for r in self.rows:
            self.assertEqual(r["num_subgoals"], len(r["route_graph"]["subgoal_states"]))

    def test_attack_asi_present_on_scaled(self):
        for r in self.rows:
            if r["source"] == "synthesized-scaled":
                self.assertRegex(r["attack_asi"] or "", r"^ASI(0[1-9]|10)$")

    def test_build_is_deterministic(self):
        again = build_corpus()
        self.assertEqual(
            json.dumps(self.rows, sort_keys=True),
            json.dumps(again, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
