"""AB1b oracle-stress / corpus-growth — deterministic, no model calls.

Pins that the authored oracle-divergent journey makes the hidden oracle load-bearing:
the real scorer separates the thorough run from the verification-skipping shortcut
(progress 1.0 vs 0.0) while a visible-only blind scorer cannot (both reach the goal)
and inverts optimality. Also checks the journey is structurally valid and that the
oracle fields are stripped from the visible view.

    python -m unittest analysis.tests.test_oracle_stress
"""

from __future__ import annotations

import json
import unittest

from analysis.oracle_stress import _JOURNEY, build_report, run
from harness.runtime import validate_graph
from journeys.loader import visible_view


class TestOracleStress(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = run()
        cls.agents = cls.data["agents"]

    def test_journey_is_valid_and_oracle_diverges(self) -> None:
        rg = json.load(open(_JOURNEY, encoding="utf-8"))["route_graph"]
        validate_graph(rg)  # raises on any structural violation
        # optimal_walk (cost 3) is NOT the cheapest path (shortcut cost 1).
        self.assertEqual(rg["optimal_walk"], ["start", "gather", "verify", "published"])
        self.assertTrue(any(e["from"] == "start" and e["to"] == "published" for e in rg["edges"]))

    def test_oracle_fields_stripped_from_visible_view(self) -> None:
        rg = json.load(open(_JOURNEY, encoding="utf-8"))["route_graph"]
        vv = visible_view(rg)
        self.assertNotIn("optimal_walk", vv)
        self.assertNotIn("subgoal_states", vv)

    def test_real_scorer_separates_thorough_from_shortcut(self) -> None:
        self.assertEqual(self.agents["thorough"]["real_progress"], 1.0)
        self.assertEqual(self.agents["shortcut"]["real_progress"], 0.0)
        self.assertTrue(self.agents["thorough"]["goal_reached"])
        self.assertTrue(self.agents["shortcut"]["goal_reached"])  # shortcut DOES reach goal

    def test_blind_scorer_cannot_separate_and_inverts_optimality(self) -> None:
        # blind progress: both reach goal -> indistinguishable.
        self.assertEqual(self.agents["thorough"]["blind_progress"], 1.0)
        self.assertEqual(self.agents["shortcut"]["blind_progress"], 1.0)
        # blind optimality inverts: thorough penalised (2), shortcut "optimal" (0),
        # while the real scorer rates both at gap 0.
        self.assertEqual(self.agents["thorough"]["blind_optimality_gap"], 2.0)
        self.assertEqual(self.agents["shortcut"]["blind_optimality_gap"], 0.0)
        self.assertEqual(self.agents["thorough"]["real_optimality_gap"], 0.0)
        self.assertEqual(self.agents["shortcut"]["real_optimality_gap"], 0.0)

    def test_report_is_byte_reproducible(self) -> None:
        self.assertEqual(build_report(run()), build_report(run()))


if __name__ == "__main__":
    unittest.main()
