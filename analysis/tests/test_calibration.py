"""A5 calibration metrics — deterministic unit tests (no model calls).

    python -m unittest analysis.tests.test_calibration
"""

from __future__ import annotations

import unittest

from analysis.calibration import (
    ascii_diagram, brier, build_report, ece, mce, reliability_bins,
)


class TestCalibrationMetrics(unittest.TestCase):
    def test_brier_bounds(self) -> None:
        self.assertEqual(brier([1.0], [1]), 0.0)
        self.assertEqual(brier([0.0], [1]), 1.0)
        self.assertAlmostEqual(brier([0.5, 0.5], [1, 0]), 0.25)
        self.assertEqual(brier([], []), 0.0)

    def test_perfectly_calibrated_has_zero_ece(self) -> None:
        # confidence 0.0 -> outcome 0, confidence 1.0 -> outcome 1: each bin's acc
        # equals its mean confidence exactly.
        conf = [0.0, 0.0, 1.0, 1.0]
        out = [0, 0, 1, 1]
        self.assertEqual(ece(conf, out), 0.0)

    def test_overconfident_has_large_ece(self) -> None:
        conf = [0.95] * 10
        out = [1, 1, 1, 1, 1, 1, 0, 0, 0, 0]  # acc 0.6, stated 0.95
        self.assertAlmostEqual(ece(conf, out), 0.35, places=2)
        self.assertAlmostEqual(mce(conf, out), 0.35, places=2)

    def test_reliability_bins_partition(self) -> None:
        conf = [0.05, 0.15, 0.95, 1.0]
        out = [0, 0, 1, 1]
        bins = reliability_bins(conf, out, n_bins=10)
        self.assertEqual(sum(b["count"] for b in bins), 4)
        self.assertEqual(bins[-1]["count"], 2)   # 0.95 and 1.0 in the top decile

    def test_ascii_diagram_shape(self) -> None:
        diagram = ascii_diagram([0.05, 0.95], [0, 1], n_bins=10)
        self.assertEqual(len(diagram), 10)

    def test_report_runs_and_is_reproducible(self) -> None:
        # synthetic §1 always present; §2 reflects cached probes (may be absent).
        rep = build_report()
        self.assertEqual(rep, build_report())
        joined = "\n".join(rep)
        self.assertIn("## 1. Tooling validation", joined)
        self.assertIn("## 2. Real per-fork", joined)


if __name__ == "__main__":
    unittest.main()
