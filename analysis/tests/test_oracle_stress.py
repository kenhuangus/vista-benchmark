"""AB1b oracle-stress / corpus-growth — deterministic, no model calls.

Pins that the WHOLE oracle-divergent journey family (journeys/oracle_stress_*.json,
one per domain) makes the hidden oracle load-bearing: on each journey the real scorer
separates the thorough run from the verification-skipping shortcut (progress 1.0 vs
0.0) while a visible-only blind scorer cannot (both reach the goal) and inverts
optimality. Also checks each journey is structurally valid, oracle-divergent, and that
the oracle fields are stripped from the visible view.

    python -m unittest analysis.tests.test_oracle_stress
"""

from __future__ import annotations

import glob
import json
import unittest

from analysis.oracle_stress import _JOURNEY_GLOB, _shortcut_move, build_report, run
from harness.runtime import validate_graph
from journeys.loader import visible_view


class TestOracleStress(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = run()
        cls.paths = sorted(glob.glob(_JOURNEY_GLOB))

    def test_at_least_three_journeys_one_per_domain(self) -> None:
        domains = {j["domain"] for j in self.data["journeys"]}
        self.assertGreaterEqual(len(self.data["journeys"]), 3)
        self.assertEqual(domains, {"research", "project", "coding"})

    def test_every_journey_valid_oracle_divergent_and_stripped(self) -> None:
        for path in self.paths:
            rg = json.load(open(path, encoding="utf-8"))["route_graph"]
            validate_graph(rg)  # raises on any structural violation
            # optimal_walk (cost 3) is NOT the cheapest path (a cost-1 shortcut exists).
            self.assertEqual(len(rg["optimal_walk"]), 4)
            self.assertIsNotNone(_shortcut_move(rg))
            vv = visible_view(rg)
            self.assertNotIn("optimal_walk", vv)
            self.assertNotIn("subgoal_states", vv)

    def test_real_separates_blind_cannot_on_every_journey(self) -> None:
        for j in self.data["journeys"]:
            a = j["agents"]
            with self.subTest(journey=j["journey"]):
                # real scorer reads subgoal_states -> separates.
                self.assertEqual(a["thorough"]["real_progress"], 1.0)
                self.assertEqual(a["shortcut"]["real_progress"], 0.0)
                # both reach the goal -> blind progress identical, cannot separate.
                self.assertEqual(a["thorough"]["blind_progress"], 1.0)
                self.assertEqual(a["shortcut"]["blind_progress"], 1.0)
                # blind inverts optimality; real rates both at gap 0.
                self.assertEqual(a["thorough"]["blind_optimality_gap"], 2.0)
                self.assertEqual(a["shortcut"]["blind_optimality_gap"], 0.0)
                self.assertEqual(a["thorough"]["real_optimality_gap"], 0.0)
                self.assertEqual(a["shortcut"]["real_optimality_gap"], 0.0)

    def test_report_is_byte_reproducible(self) -> None:
        self.assertEqual(build_report(run()), build_report(run()))


if __name__ == "__main__":
    unittest.main()
