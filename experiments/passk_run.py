#!/usr/bin/env python3
"""Pillar A (pass^k) — repeat the stepwise run k times per model so the
foresight-cliff finding becomes a statistic, not an n=1 anecdote.

The single-shot security run (``security_run.py``) showed a split that pass/fail
and planning-mode both hide: under the turn-by-turn seam, Sonnet and both Geminis
reach the goal while Haiku and Opus loop at a hold node. That was one sample per
model. This runs each model k times on the same journey and aggregates:

* ``goal_reach_rate``  — fraction of runs that reach the goal (the cliff metric);
* ``pass_rate``        — fraction passing the full pass predicate (pass@1 estimate);
* ``pass_pow_k``       — 1 iff ALL k runs pass (worst-case reliability, the pass^k
                          spirit: a long-horizon agent you can trust every time);
* ``asr_mean`` / ``asr_any`` — injection-resistance, averaged and worst-case.

The per-run vectors are printed too: if a model is effectively deterministic on
this task the vectors are flat (itself worth knowing); if it's flaky the spread is
the point. The model is the only stochastic part — the scorer stays deterministic.

Usage::

    python experiments/passk_run.py --model gemini-2.5-pro --k 5
    python experiments/passk_run.py --model opus --k 5 --max-steps 6 --out results/pillar-a-passk/opus.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agents.ranger import RangerAgent  # noqa: E402
from agents.llm_agent import LLMAgent  # noqa: E402
from agents.stepwise_adapter import StepwiseAdapter, PlanReplayAgent  # noqa: E402
from contracts.adapter import Steering  # noqa: E402
from journeys.loader import load_journey  # noqa: E402
from journeys.corpus import full_corpus  # noqa: E402
from journeys.scaled_corpus import scaled_corpus, ALL_DOMAINS  # noqa: E402
from experiments.real_agent_run import (  # noqa: E402
    _VERTEX_PROJECT, _VERTEX_LOCATION, _VERTEX_KEY_WSL,
)
from experiments.security_run import _sec  # noqa: E402

# The cliff lives on the project journey (the injection + the await_human hold).
_DEFAULT_JOURNEY = os.path.join(_REPO_ROOT, "journeys", "project_inquiry_dev.json")


def _tier(jid: str) -> str:
    """Difficulty tier from a scaled journey id; 'curated' for the seed journeys."""
    return jid.rsplit("-", 2)[1] if jid.startswith("scaled-") else "curated"


def _published_corpus() -> list[dict]:
    """The same 390-journey published corpus the HF dataset exports — so a stepwise
    pass^k run can generalize beyond the single seed journey, by id, reproducibly."""
    return list(full_corpus()) + list(scaled_corpus(4, domains=ALL_DOMAINS))


def _resolve_journeys(paths, ids):
    """Journeys to evaluate: explicit corpus ids (reproducible generalization sample),
    else file paths, else the single canonical cliff journey."""
    if ids:
        lut = {j["id"]: j for j in _published_corpus()}
        missing = [i for i in ids if i not in lut]
        if missing:
            raise SystemExit(f"unknown journey ids (not in published corpus): {missing}")
        return [lut[i] for i in ids]
    if paths:
        return [load_journey(p) for p in paths]
    return [load_journey(_DEFAULT_JOURNEY)]


def _agg(secs):
    k = len(secs) or 1
    goal = [1 if s["goal_reached"] else 0 for s in secs]
    passed = [1 if s["passed"] else 0 for s in secs]
    asr = [s["targeted_asr_mean"] for s in secs]
    recall = [s["recall"] for s in secs]
    return {
        "k": len(secs),
        "goal_reach_rate": sum(goal) / k,
        "pass_rate": sum(passed) / k,
        "pass_pow_k": int(all(passed) and bool(passed)),
        "asr_mean": sum(asr) / k,
        "asr_any": max(asr) if asr else 0.0,
        "recall_mean": sum(recall) / k,
        "goal_vec": goal,
        "pass_vec": passed,
        "asr_vec": asr,
    }


def run(model, journeys, *, k, seed, gemini_mode, max_steps, grok_permission_mode="plan"):
    llm = LLMAgent(model=model, seed=seed, gemini_mode=gemini_mode,
                   vertex_project=_VERTEX_PROJECT, vertex_location=_VERTEX_LOCATION,
                   vertex_key=_VERTEX_KEY_WSL, grok_permission_mode=grok_permission_mode)
    steering = Steering(max_steps=max_steps)
    rows = []
    for journey in journeys:
        ranger_sc = StepwiseAdapter(
            PlanReplayAgent(RangerAgent())
        ).run_session(journey, steering).scorecard
        secs = []
        for _ in range(k):
            llm.set_journey_context(journey)
            sc = StepwiseAdapter(llm).run_session(journey, steering).scorecard
            secs.append(_sec(sc))
        rows.append({
            "journey": journey.get("id"), "domain": journey.get("domain"),
            "difficulty_tier": _tier(journey.get("id", "")),
            "ranger": _sec(ranger_sc), "agg": _agg(secs), "runs": secs,
        })
    return {"model": model, "k": k, "max_steps": max_steps,
            "permission_mode": grok_permission_mode if str(model).startswith("grok") else None,
            "journey_ids": [j.get("id") for j in journeys],
            "results": rows, "usage": llm.usage}


def print_report(rep):
    print(f"\n=== VISTA pass^k security (k={rep['k']}, stepwise, "
          f"max_steps={rep['max_steps']}): `{rep['model']}` ===\n")
    for row in rep["results"]:
        a = row["agg"]
        r = row["ranger"]
        print(f"[{row['journey']}] ({row['domain']})")
        print(f"  ranger : goal={'Y' if r['goal_reached'] else 'N'} "
              f"asr={r['targeted_asr_mean']:.2f} recall={r['recall']:.2f}")
        print(f"  {rep['model']:6}: goal_rate={a['goal_reach_rate']:.2f} "
              f"pass_rate={a['pass_rate']:.2f} pass^k={a['pass_pow_k']} "
              f"asr_mean={a['asr_mean']:.2f} asr_any={a['asr_any']:.2f} "
              f"recall={a['recall_mean']:.2f}")
        print(f"           goal_vec={a['goal_vec']} asr_vec={a['asr_vec']}")
        print()
    u = rep["usage"]
    print(f"--- token cost: calls={u['calls']} in={u['input_tokens']} "
          f"out={u['output_tokens']} cost_usd=${u['cost_usd']:.4f} "
          f"(Gemini billed to GCP credits => $0) ---")


def main(argv=None):
    p = argparse.ArgumentParser(description="VISTA pass^k stepwise run.")
    p.add_argument("--model", default="gemini-2.5-pro")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--journeys", nargs="*", default=None, help="explicit journey file paths")
    p.add_argument("--journey-ids", nargs="*", default=None,
                   help="select journeys from the published corpus by id (reproducible "
                        "generalization sample beyond the single seed journey)")
    p.add_argument("--grok-permission-mode", default="plan",
                   choices=["default", "acceptEdits", "auto", "dontAsk",
                            "bypassPermissions", "plan"],
                   help="Grok CLI permission mode (confound ablation: 'default' lets it "
                        "act, isolating plan-mode disposition as the stepwise-stall cause)")
    p.add_argument("--gemini-mode", default="vertex", choices=["vertex", "apikey", "gca"])
    p.add_argument("--max-steps", type=int, default=6)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)
    journeys = _resolve_journeys(args.journeys, args.journey_ids)
    rep = run(args.model, journeys, k=args.k, seed=args.seed,
              gemini_mode=args.gemini_mode, max_steps=args.max_steps,
              grok_permission_mode=args.grok_permission_mode)
    print_report(rep)
    if args.out:
        if os.path.dirname(args.out):
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
