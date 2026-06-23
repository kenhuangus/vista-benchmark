"""Tests for the deterministic analysis layer.

The statistics helpers and report determinism are pinned unconditionally (they need
no artifacts). The value checks that read ``results/`` are skipped when the artifacts
are absent (a fresh clone), so the suite stays green everywhere while still verifying
real numbers wherever the data is present.

Run from the repo root::

    python -m unittest analysis.tests.test_analyze
"""

from __future__ import annotations

import os
import unittest

from analysis.analyze import (
    bootstrap_passk_ci, build_report, load_passk, pass_hat_k, pass_hat_k_curve,
    pearson, wilson, _RESULTS,
)

_HAS_PASSK = os.path.isdir(os.path.join(_RESULTS, "pillar-a-passk"))


class TestStatistics(unittest.TestCase):
    def test_pass_hat_k_unbiased(self) -> None:
        # 2 of 5 runs pass: pass^1 = 2/5, pass^2 = C(2,2)/C(5,2) = 1/10, pass^3 = 0.
        self.assertAlmostEqual(pass_hat_k(2, 5, 1), 0.4)
        self.assertAlmostEqual(pass_hat_k(2, 5, 2), 0.1)
        self.assertEqual(pass_hat_k(2, 5, 3), 0.0)
        self.assertEqual(pass_hat_k(5, 5, 5), 1.0)
        self.assertEqual(pass_hat_k(0, 5, 1), 0.0)
        self.assertEqual(pass_hat_k(3, 5, 6), 0.0)  # k > n

    def test_pass_hat_k_curve_matches_sequence(self) -> None:
        self.assertEqual(pass_hat_k_curve([1, 0, 0, 0, 1]), [0.4, 0.1, 0.0, 0.0, 0.0])
        self.assertEqual(pass_hat_k_curve([1, 1, 1, 1, 1]), [1.0, 1.0, 1.0, 1.0, 1.0])
        self.assertEqual(pass_hat_k_curve([0, 0, 0, 0, 0]), [0.0, 0.0, 0.0, 0.0, 0.0])

    def test_wilson_boundaries(self) -> None:
        lo, hi = wilson(0, 5)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.43, places=2)   # 0/5 upper bound ~0.43, not 0
        lo, hi = wilson(5, 5)
        self.assertEqual(hi, 1.0)
        self.assertGreater(lo, 0.5)                   # 5/5 lower bound well above 0.5
        self.assertEqual(wilson(0, 0), (0.0, 0.0))

    def test_bootstrap_is_seeded_and_degenerate_at_boundaries(self) -> None:
        self.assertEqual(bootstrap_passk_ci([1, 1, 1, 1, 1], 5), (1.0, 1.0))
        self.assertEqual(bootstrap_passk_ci([0, 0, 0, 0, 0], 5), (0.0, 0.0))
        # seeded => identical across calls
        self.assertEqual(bootstrap_passk_ci([1, 0, 0, 0, 1], 2),
                         bootstrap_passk_ci([1, 0, 0, 0, 1], 2))

    def test_pearson_zero_variance_is_none_perfect_is_one(self) -> None:
        self.assertIsNone(pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]))  # x constant
        self.assertAlmostEqual(pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]), 1.0)
        self.assertAlmostEqual(pearson([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]), -1.0)


class TestReportDeterminism(unittest.TestCase):
    def test_report_is_byte_reproducible(self) -> None:
        # The only stochastic step is a fixed-seed bootstrap -> identical every run,
        # whether or not results/ is present (missing files degrade to empty tables).
        self.assertEqual(build_report(), build_report())

    def test_report_has_all_sections(self) -> None:
        rep = build_report()
        for marker in ("## A1", "## A2", "## A3", "## A4", "## A6", "## A7", "## A8"):
            self.assertIn(marker, rep)


@unittest.skipUnless(_HAS_PASSK, "results/pillar-a-passk artifacts not present")
class TestRealValues(unittest.TestCase):
    def test_reliability_is_non_monotone_in_price(self) -> None:
        passk = load_passk()
        # Robust counter-finding (stable across re-runs, unlike any single model's exact
        # pass^k): price does not buy reliability on this stepwise task — the best FREE
        # model is at least as reliable as the best PAID one, and a paid model exists.
        free = [a for a in passk.values() if a["cost_usd"] == 0.0]
        paid = [a for a in passk.values() if a["cost_usd"] > 0.0]
        self.assertTrue(free and paid, "need both a free and a paid model present")
        self.assertGreaterEqual(
            max(a["goal_reach_rate"] for a in free),
            max(a["goal_reach_rate"] for a in paid),
            "a free model should match or beat the best paid model's reliability here",
        )

    def test_long_view_premium_present_in_report(self) -> None:
        # ranger - naive recall premium is +1.00 on the corpus (H1).
        self.assertIn("**+1.00**", build_report())


if __name__ == "__main__":
    unittest.main()
