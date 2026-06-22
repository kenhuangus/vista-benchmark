"""AB2 role-isolation ablation — deterministic, no model calls.

Pins each role's unique contribution: Scout escalation calibration (ranger recall 1.0
vs naive 0.0), Worker privilege separation (no authority methods), and axis10
reachability only via the Dreamer (single-policy agent has no Dreamer seam).

    python -m unittest analysis.tests.test_role_ablation
"""

from __future__ import annotations

import unittest

from analysis.role_ablation import build_report, run


class TestRoleAblation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = run()

    def test_scout_separates_recall(self) -> None:
        s = self.data["scout"]
        self.assertEqual(s["ranger_mean"], 1.0)
        self.assertEqual(s["naive_mean"], 0.0)
        self.assertEqual(len(s["per_journey"]), 6)

    def test_worker_has_no_authority_methods(self) -> None:
        for present in self.data["worker"].values():
            self.assertFalse(present)

    def test_axis10_reachable_only_with_dreamer(self) -> None:
        d = self.data["dreamer"]
        self.assertFalse(d["single_policy_has_dreamer"])
        self.assertTrue(d["full_ranger_has_dreamer"])
        self.assertTrue(d["axis10_computed_for_full_ranger"])
        self.assertEqual(d["axis10_score"], 1.0)

    def test_report_is_byte_reproducible(self) -> None:
        self.assertEqual(build_report(run()), build_report(run()))


if __name__ == "__main__":
    unittest.main()
