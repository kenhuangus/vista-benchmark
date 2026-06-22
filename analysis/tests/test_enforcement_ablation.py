"""AB4 enforcement ablation — deterministic, no model calls.

Pins the load-bearing claim: the same goal-hijack crossing scores ASR 0 under the
enforced runtime and ASR 1 under a detect-only runtime, on every journey.

    python -m unittest analysis.tests.test_enforcement_ablation
"""

from __future__ import annotations

import unittest

from analysis.enforcement_ablation import build_report, run


class TestEnforcementAblation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = run()["rows"]

    def test_covers_corpus_with_targets(self) -> None:
        self.assertEqual(len(self.rows), 6)
        for r in self.rows:
            self.assertTrue(r["target"])

    def test_enforced_blocks_every_hijack(self) -> None:
        for r in self.rows:
            self.assertEqual(r["enforced_asr"], 0.0)
            self.assertFalse(r["enforced_crossing"])

    def test_detect_only_lets_every_hijack_succeed(self) -> None:
        for r in self.rows:
            self.assertEqual(r["detect_asr"], 1.0)
            self.assertTrue(r["detect_crossing"])

    def test_report_is_byte_reproducible(self) -> None:
        self.assertEqual(build_report({"rows": self.rows}),
                         build_report({"rows": run()["rows"]}))


if __name__ == "__main__":
    unittest.main()
