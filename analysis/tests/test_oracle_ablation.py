"""AB1 oracle-blind ablation — deterministic, runs the reference agents (no model).

Pins the separation facts the AB1 report draws its conclusion from, so the claim
"the excusal rule is load-bearing, the hidden oracle is not (on this corpus)" can't
silently rot: the real scorer and the blind-EXCUSED scorer separate ranger from naive
on drift, while the blind-RAW scorer (no excusal) does not, and the optimality gap is
identical with or without the oracle. Also checks the report is byte-reproducible.

    python -m unittest analysis.tests.test_oracle_ablation
"""

from __future__ import annotations

import unittest

from analysis.oracle_ablation import build_report, run, _separates


class TestOracleAblation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = run()
        cls.rows = cls.data["rows"]

    def test_corpus_covered(self) -> None:
        self.assertEqual(len(self.rows), 6)
        for r in self.rows:
            self.assertIn("naive", r["agents"])
            self.assertIn("ranger", r["agents"])

    def test_real_scorer_separates_safe_from_careless(self) -> None:
        self.assertTrue(_separates(self.rows, "real_drift", "real_drift"))

    def test_blind_raw_fails_to_separate_the_finding001_inversion(self) -> None:
        # Without the excusal rule, ranger's escalation == naive's diversion (both 2).
        self.assertFalse(_separates(self.rows, "blind_drift_raw", "blind_drift_raw"))
        for r in self.rows:
            self.assertEqual(r["agents"]["ranger"]["blind_drift_raw"],
                             r["agents"]["naive"]["blind_drift_raw"])

    def test_blind_excused_reproduces_the_real_verdict(self) -> None:
        self.assertTrue(_separates(self.rows, "blind_drift_excused", "blind_drift_excused"))
        for r in self.rows:
            self.assertEqual(r["agents"]["ranger"]["blind_drift_excused"],
                             r["agents"]["ranger"]["real_drift"])

    def test_optimality_gap_does_not_need_the_oracle_on_this_corpus(self) -> None:
        for r in self.rows:
            for name in ("naive", "ranger"):
                a = r["agents"][name]
                self.assertAlmostEqual(a["real_optimality_gap"], a["blind_optimality_gap"])

    def test_report_is_byte_reproducible(self) -> None:
        self.assertEqual(build_report(run()), build_report(run()))


if __name__ == "__main__":
    unittest.main()
