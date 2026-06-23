#!/usr/bin/env python3
"""Run a model (planning seam) across the scaled corpus — stochastic error bars + the
difficulty gradient (threat §1 / construct validity).

Planning is a SINGLE CLI call per journey (no stepwise loop), so it is far more robust
to WSL glitches than the security/pass^k sweeps. Per-journey failures are caught and
recorded as coverage gaps rather than crashing the run, so a 96-journey sweep completes
even if a few calls flake.

    python experiments/scaled_run.py --model gemini-2.5-flash
    python experiments/scaled_run.py --model grok-build --per-domain-tier 1
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agents.adapter import HarnessAgentAdapter  # noqa: E402
from agents.llm_agent import LLMAgent, LLMAgentError  # noqa: E402
from contracts.adapter import Steering  # noqa: E402
from journeys.scaled_corpus import scaled_specs, scaled_corpus  # noqa: E402
from experiments.real_agent_run import (  # noqa: E402
    _VERTEX_PROJECT, _VERTEX_LOCATION, _VERTEX_KEY_WSL,
)


def _tier(jid: str) -> str:
    return jid.rsplit("-", 2)[1]


def _axes(scorecard: dict) -> dict:
    ax = scorecard["axes"]
    f = ax["axis02_foresight"]
    return {
        "recall": ax["axis06_verification_calibration"]["recall"],
        "progress_rate": f.get("progress_rate"),
        "optimality_gap": f.get("optimality_gap"),
        "drift_count": ax["axis03_alignment_drift"].get("drift_count"),
        "asr": ax["axis07_security_abuse_resistance"]["targeted_asr_mean"],
        "goal_reached": ax["axis01_goal_progress"]["goal_reached"],
    }


def _sample(per_domain_tier: int):
    """A stratified sample: the first ``per_domain_tier`` variants of each
    (domain, tier) — keeps the sweep bounded while spanning the difficulty range."""
    specs = scaled_specs()
    journeys = scaled_corpus()
    by_key: dict[tuple, int] = {}
    picked = []
    for spec, j in zip(specs, journeys):
        key = (spec.domain, _tier(spec.id))
        if by_key.get(key, 0) < per_domain_tier:
            by_key[key] = by_key.get(key, 0) + 1
            picked.append(j)
    return picked


def run(model, *, seed, gemini_mode, per_domain_tier):
    llm = LLMAgent(model=model, seed=seed, gemini_mode=gemini_mode,
                   vertex_project=_VERTEX_PROJECT, vertex_location=_VERTEX_LOCATION,
                   vertex_key=_VERTEX_KEY_WSL)
    rows, failures = [], []
    for j in _sample(per_domain_tier):
        if hasattr(llm, "set_journey_context"):
            llm.set_journey_context(j)
        try:
            sc = HarnessAgentAdapter(llm).run_session(
                j, j.get("initial_route_state", {}), Steering(seed=seed)).scorecard
            rows.append({"journey": j["id"], "domain": j["domain"], "split": j["split"],
                         "tier": _tier(j["id"]), **_axes(sc)})
        except LLMAgentError as exc:
            failures.append({"journey": j["id"], "error": str(exc)[:200]})
    return {"model": model, "results": rows, "failures": failures, "usage": llm.usage}


def main(argv=None):
    p = argparse.ArgumentParser(description="VISTA scaled-corpus model sweep (planning).")
    p.add_argument("--model", default="gemini-2.5-flash")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--gemini-mode", default="vertex", choices=["vertex", "apikey", "gca"])
    p.add_argument("--per-domain-tier", type=int, default=2,
                   help="variants per (domain, tier); 2 -> 24 journeys, full grid")
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)
    rep = run(args.model, seed=args.seed, gemini_mode=args.gemini_mode,
              per_domain_tier=args.per_domain_tier)
    n, f = len(rep["results"]), len(rep["failures"])
    rec = [r["recall"] for r in rep["results"]]
    goal = [r["goal_reached"] for r in rep["results"]]
    print(f"{args.model}: {n} scored, {f} failed | "
          f"mean recall={sum(rec)/len(rec):.2f} goal_rate={sum(goal)/len(goal):.2f} | "
          f"cost=${rep['usage']['cost_usd']:.4f}")
    out = args.out or os.path.join(_REPO_ROOT, "results", "pillar-a-scaled", f"{args.model}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2, sort_keys=True)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
