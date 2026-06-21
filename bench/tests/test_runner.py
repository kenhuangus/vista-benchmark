"""Multi-run benchmark driver + archival tests (S6).

Proves the reproducible-numbers layer:
  * pass^k over k runs (deterministic agent => pass^k == single-run pass);
  * a reckless agent that attempts the forbidden trap drives pass^k to 0;
  * run_benchmark aggregates across the corpus by split + domain, and the
    calibration premium survives aggregation (ranger 1.0 vs naive 0.0) even
    though BOTH reliably pass the binary predicate;
  * the scored content is reproducible (fixed timestamp -> identical report);
  * archival writes a versioned results/v{X.Y}/{bench}-{agent}-{ts}.json file.

Run from the repo root::

    python -m unittest discover -s bench -p 'test_*.py'
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from typing import Any

from agents.naive_agent import NaiveAgent
from agents.ranger import RangerAgent

from journeys.loader import load_seed_journey

from bench.runner import archive, run_benchmark, run_journey_k


class _RecklessAgent:
    """A mock UNSAFE agent: it plans straight at the forbidden trap. The runtime
    blocks the crossing (records a forbidden_attempt), so the journey FAILS the
    pass predicate — exercising a pass^k below 1.0."""

    name = "reckless"

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def plan(self, visible_view: dict[str, Any]) -> list[str]:
        trap = next(n for n, d in visible_view["nodes"].items() if d["kind"] == "forbidden")
        return [trap]


class TestRunJourneyK(unittest.TestCase):
    def setUp(self) -> None:
        self.journey = load_seed_journey()

    def test_deterministic_agent_passhatk_equals_single_pass(self) -> None:
        row = run_journey_k(RangerAgent, self.journey, k=5)
        self.assertEqual(row["k"], 5)
        self.assertEqual(row["passed_runs"], 5)
        self.assertEqual(row["pass_hat_k"], 1.0)
        self.assertTrue(row["deterministic"], "deterministic agent => identical k runs")
        self.assertEqual(row["headline"]["verification_calibration_recall"], 1.0)

    def test_reckless_agent_fails_passhatk(self) -> None:
        row = run_journey_k(_RecklessAgent, self.journey, k=3)
        self.assertEqual(row["passed_runs"], 0)
        self.assertEqual(row["pass_hat_k"], 0.0)

    def test_rejects_bad_k(self) -> None:
        with self.assertRaises(ValueError):
            run_journey_k(NaiveAgent, self.journey, k=0)


class TestRunBenchmark(unittest.TestCase):
    def test_aggregate_over_corpus(self) -> None:
        ranger = run_benchmark("ranger", k=3, timestamp="2026-06-20T00:00:00Z")
        naive = run_benchmark("naive", k=3, timestamp="2026-06-20T00:00:00Z")

        # Both reliably PASS the binary predicate on every journey...
        self.assertEqual(ranger["aggregate"]["pass_hat_k_mean"], 1.0)
        self.assertEqual(naive["aggregate"]["pass_hat_k_mean"], 1.0)
        self.assertEqual(ranger["aggregate"]["fully_passing_journeys"], 6)
        # ...but the calibration premium survives aggregation (pass/fail can't see it).
        self.assertEqual(ranger["aggregate"]["mean_calibration_recall"], 1.0)
        self.assertEqual(naive["aggregate"]["mean_calibration_recall"], 0.0)
        # pass^k is broken out per split + domain.
        self.assertEqual(set(ranger["aggregate"]["pass_hat_k_by_split"]),
                         {"train", "dev", "test", "challenge"})
        self.assertEqual(set(ranger["aggregate"]["pass_hat_k_by_domain"]),
                         {"project", "coding", "research"})
        self.assertTrue(ranger["aggregate"]["all_runs_deterministic"])

    def test_report_is_reproducible(self) -> None:
        a = run_benchmark("ranger", k=4, timestamp="2026-06-20T00:00:00Z")
        b = run_benchmark("ranger", k=4, timestamp="2026-06-20T00:00:00Z")
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_unknown_agent_raises(self) -> None:
        with self.assertRaises(KeyError):
            run_benchmark("gpt9", k=1)


class TestArchive(unittest.TestCase):
    def test_writes_versioned_results_file(self) -> None:
        result = run_benchmark("ranger", k=2, timestamp="2026-06-20T12:34:56Z")
        with tempfile.TemporaryDirectory() as root:
            path = archive(result, root=root)
            self.assertTrue(os.path.exists(path))
            # path: <root>/v0.1/vista-ranger-20260620T123456Z.json
            self.assertIn(os.path.join("v0.1", "vista-ranger-"), path)
            self.assertTrue(path.endswith(".json"))
            with open(path, "r", encoding="utf-8") as fh:
                reloaded = json.load(fh)
            self.assertEqual(reloaded["benchmark"], "vista")
            self.assertEqual(reloaded["version"], "0.1")
            self.assertEqual(reloaded["agent"], "ranger")
            self.assertEqual(reloaded["aggregate"]["pass_hat_k_mean"], 1.0)


if __name__ == "__main__":
    unittest.main()
