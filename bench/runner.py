"""Multi-run benchmark driver + versioned results archival (S6).

The scorer produces ONE scorecard per run; a benchmark needs *reliability over
repeated runs* and a *reproducible, versioned record*. This module adds both:

* :func:`run_journey_k` — run an agent ``k`` times on one journey (seeds
  ``seed_base … seed_base+k-1``), collect the binary per-run pass predicate, and
  compute ``pass^k`` (:func:`harness.scorer.pass_hat_k`, τ-bench style).
* :func:`run_benchmark` — do that across the whole corpus and aggregate by split
  and domain.
* :func:`archive` — write the result to ``results/v{X.Y}/{bench}-{agent}-{ts}.json``.

Determinism (NFR-1): the SCORES are a pure function of (agent, journey, seed);
the reference agents are deterministic, so all ``k`` runs of a journey are
byte-identical and ``pass^k`` collapses to the single-run pass. The machinery is
built for STOCHASTIC (LLM) agents whose runs vary by seed — there ``pass^k`` and
the per-run spread become meaningful. The ONLY wall-clock in this module is the
archival ``timestamp`` (metadata, never an input to a score); it is injectable so
the scored content is fully testable and reproducible.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Optional

from contracts.adapter import Steering

from harness.scorer import JourneyRunResult, pass_hat_k

from agents.adapter import HarnessAgentAdapter
from agents.naive_agent import NaiveAgent
from agents.ranger import RangerAgent

from journeys import corpus as _corpus

BENCH_NAME = "vista"
VISTA_VERSION = "0.1"

AGENTS: dict[str, Callable[..., Any]] = {"naive": NaiveAgent, "ranger": RangerAgent}


# --------------------------------------------------------------------------- #
# One journey, k runs
# --------------------------------------------------------------------------- #
def _run_once(agent_factory: Callable[..., Any], journey: dict, seed: int) -> dict:
    """Run one agent through one journey at one seed; return its scorecard."""
    adapter = HarnessAgentAdapter(agent_factory(seed=seed))
    return adapter.run_session(
        journey, journey.get("initial_route_state", {}), Steering(seed=seed)
    ).scorecard


def run_journey_k(
    agent_factory: Callable[..., Any],
    journey: dict,
    *,
    k: int,
    seed_base: int = 0,
) -> dict:
    """Run ``k`` trials of one journey and compute ``pass^k`` over them."""
    if k < 1:
        raise ValueError("k must be >= 1")
    scorecards = [_run_once(agent_factory, journey, seed_base + i) for i in range(k)]

    run_results = []
    for sc in scorecards:
        pp = sc["pass_predicate"]
        run_results.append(JourneyRunResult(
            goal_reached=pp["goal_reached"],
            no_forbidden_crossing=pp["no_forbidden_crossing"],
            all_targeted_asr_zero=pp["all_targeted_asr_zero"],
        ))

    # All k runs identical? (true for deterministic agents — reported honestly.)
    canonical = {json.dumps(sc, sort_keys=True) for sc in scorecards}
    head = scorecards[0]
    return {
        "journey": journey["id"],
        "domain": journey["domain"],
        "split": journey["split"],
        "k": k,
        "passed_runs": sum(1 for r in run_results if r.passed),
        "pass_hat_k": pass_hat_k(run_results, k),
        "deterministic": len(canonical) == 1,
        "headline": {
            "verification_calibration_recall":
                head["axes"]["axis06_verification_calibration"]["recall"],
            "progress_rate": head["graph_oracle_metrics"]["progress_rate"],
            "optimality_gap": head["graph_oracle_metrics"]["optimality_gap"],
            "drift_count": head["graph_oracle_metrics"]["drift_count"],
            "targeted_asr_mean":
                head["axes"]["axis07_security_abuse_resistance"]["targeted_asr_mean"],
        },
    }


# --------------------------------------------------------------------------- #
# The whole corpus
# --------------------------------------------------------------------------- #
def run_benchmark(
    agent_name: str,
    *,
    k: int = 5,
    seed_base: int = 0,
    version: str = VISTA_VERSION,
    timestamp: Optional[str] = None,
    journeys: Optional[list[dict]] = None,
) -> dict:
    """Run ``agent_name`` ``k`` times across the corpus; return the full report.

    ``timestamp`` is archival metadata only (never an input to a score); pass a
    fixed value for reproducible tests, or leave ``None`` to stamp UTC now.
    """
    if agent_name not in AGENTS:
        raise KeyError(f"unknown agent {agent_name!r}; known: {sorted(AGENTS)}")
    factory = AGENTS[agent_name]
    corpus_journeys = journeys if journeys is not None else _corpus.full_corpus()

    per_journey = [
        run_journey_k(factory, j, k=k, seed_base=seed_base) for j in corpus_journeys
    ]
    return {
        "benchmark": BENCH_NAME,
        "version": version,
        "timestamp": timestamp if timestamp is not None else _utc_now_iso(),
        "agent": agent_name,
        "k": k,
        "seed_base": seed_base,
        "corpus": _corpus.summary(),
        "per_journey": per_journey,
        "aggregate": _aggregate(per_journey),
        "determinism_note": (
            "Reference agents are deterministic: all k runs per journey are "
            "byte-identical, so pass^k == the single-run pass. The machinery "
            "reports pass^k (and would report mean ± CI on continuous axes) for "
            "STOCHASTIC (LLM) agents whose runs vary by seed."
        ),
    }


def _aggregate(per_journey: list[dict]) -> dict:
    n = len(per_journey)
    if n == 0:
        return {"journeys": 0}
    by_split: dict[str, list[float]] = {}
    by_domain: dict[str, list[float]] = {}
    for p in per_journey:
        by_split.setdefault(p["split"], []).append(p["pass_hat_k"])
        by_domain.setdefault(p["domain"], []).append(p["pass_hat_k"])
    return {
        "journeys": n,
        "pass_hat_k_mean": sum(p["pass_hat_k"] for p in per_journey) / n,
        "fully_passing_journeys": sum(1 for p in per_journey if p["pass_hat_k"] == 1.0),
        "mean_calibration_recall":
            sum(p["headline"]["verification_calibration_recall"] for p in per_journey) / n,
        "mean_optimality_gap":
            sum(p["headline"]["optimality_gap"] for p in per_journey) / n,
        "pass_hat_k_by_split": {s: sum(v) / len(v) for s, v in sorted(by_split.items())},
        "pass_hat_k_by_domain": {d: sum(v) / len(v) for d, v in sorted(by_domain.items())},
        "all_runs_deterministic": all(p["deterministic"] for p in per_journey),
    }


def _utc_now_iso() -> str:
    # Archival metadata only — NOT an input to any score (NFR-1 preserved).
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Archival — results/v{X.Y}/{bench}-{agent}-{timestamp}.json
# --------------------------------------------------------------------------- #
def archive(result: dict, *, root: str = "results") -> str:
    """Write ``result`` to ``{root}/v{version}/{bench}-{agent}-{ts}.json`` and
    return the path. Creates the version directory if needed."""
    version = result["version"]
    ts_safe = result["timestamp"].replace(":", "").replace("-", "")
    out_dir = os.path.join(root, f"v{version}")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{result['benchmark']}-{result['agent']}-{ts_safe}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    return path


__all__ = [
    "BENCH_NAME",
    "VISTA_VERSION",
    "AGENTS",
    "run_journey_k",
    "run_benchmark",
    "archive",
]
