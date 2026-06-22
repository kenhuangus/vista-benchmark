#!/usr/bin/env python3
"""AB7 — prompt ablation: is the escalation guardrail a measurement scaffold or a crutch?

Runs the SAME model through the stepwise adapter twice per journey: once with the full
prompt and once with `prompt_ablation="no_escalation_guardrail"` (the explicit "you may
escalate at this fork" guidance removed — see `agents/llm_agent._render_guardrails`).
Comparing axis06 recall and axis07 ASR isolates how much of the agent's escalation
behaviour comes from the defensive scaffold vs the model's own judgement:

  * recall drops when the guardrail is removed  -> the scaffold is load-bearing; the
    benchmark must surface it for a fair axis06 (and report that it does).
  * recall holds  -> the model escalates from context; axis06 measures judgement, not
    prompt-following.

Either way the result is reported honestly. Deterministic prompt-construction is pinned
by `agents/tests/test_prompt_ablation.py`; this runner is the empirical half.

    python experiments/prompt_ablation_run.py --model gemini-2.5-flash
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agents.llm_agent import LLMAgent  # noqa: E402
from agents.stepwise_adapter import StepwiseAdapter  # noqa: E402
from contracts.adapter import Steering  # noqa: E402
from journeys.loader import load_journey  # noqa: E402
from experiments.real_agent_run import (  # noqa: E402
    _DEFAULT_JOURNEYS, _VERTEX_PROJECT, _VERTEX_LOCATION, _VERTEX_KEY_WSL,
)


def _axes(scorecard: dict) -> dict:
    ax = scorecard["axes"]
    return {
        "recall": ax["axis06_verification_calibration"]["recall"],
        "precision": ax["axis06_verification_calibration"]["precision"],
        "asr": ax["axis07_security_abuse_resistance"]["targeted_asr_mean"],
        "goal_reached": ax["axis01_goal_progress"]["goal_reached"],
    }


def _run_variant(journey, *, model, seed, gemini_mode, ablation, max_steps):
    llm = LLMAgent(model=model, seed=seed, gemini_mode=gemini_mode,
                   vertex_project=_VERTEX_PROJECT, vertex_location=_VERTEX_LOCATION,
                   vertex_key=_VERTEX_KEY_WSL, prompt_ablation=ablation)
    llm.set_journey_context(journey)
    result = StepwiseAdapter(llm).run_session(journey, Steering(max_steps=max_steps))
    return _axes(result.scorecard), llm.usage


def run(model, journey_paths, *, seed, gemini_mode, max_steps):
    rows, calls, cost = [], 0, 0.0
    for path in journey_paths:
        journey = load_journey(path)
        full, u1 = _run_variant(journey, model=model, seed=seed, gemini_mode=gemini_mode,
                                ablation=None, max_steps=max_steps)
        ablated, u2 = _run_variant(journey, model=model, seed=seed, gemini_mode=gemini_mode,
                                   ablation="no_escalation_guardrail", max_steps=max_steps)
        calls += u1["calls"] + u2["calls"]
        cost += u1["cost_usd"] + u2["cost_usd"]
        rows.append({"journey": journey.get("id"), "full": full, "ablated": ablated})
    return {"model": model, "results": rows,
            "usage": {"calls": calls, "cost_usd": cost}}


def print_report(rep):
    print(f"\n=== VISTA AB7 prompt ablation (escalation guardrail): `{rep['model']}` ===\n")
    full_r = [r["full"]["recall"] for r in rep["results"]]
    abl_r = [r["ablated"]["recall"] for r in rep["results"]]
    for r in rep["results"]:
        f, a = r["full"], r["ablated"]
        print(f"[{r['journey']}]")
        print(f"  full   : recall={f['recall']:.2f} asr={f['asr']:.2f} goal={'Y' if f['goal_reached'] else 'N'}")
        print(f"  ablated: recall={a['recall']:.2f} asr={a['asr']:.2f} goal={'Y' if a['goal_reached'] else 'N'}")
    fm = sum(full_r) / len(full_r)
    am = sum(abl_r) / len(abl_r)
    print(f"\nmean recall: full={fm:.2f} ablated={am:.2f} delta={fm - am:+.2f}")
    print("=> escalation guardrail is " +
          ("LOAD-BEARING (recall drops without it)" if fm - am > 0.1 else
           "NOT load-bearing (model escalates from context)"))
    u = rep["usage"]
    print(f"--- calls={u['calls']} cost_usd=${u['cost_usd']:.4f} (Gemini => $0) ---")


def main(argv=None):
    p = argparse.ArgumentParser(description="VISTA AB7 prompt ablation run.")
    p.add_argument("--model", default="gemini-2.5-flash")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--journeys", nargs="*", default=None)
    p.add_argument("--gemini-mode", default="vertex", choices=["vertex", "apikey", "gca"])
    p.add_argument("--max-steps", type=int, default=8)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)
    rep = run(args.model, args.journeys or _DEFAULT_JOURNEYS, seed=args.seed,
              gemini_mode=args.gemini_mode, max_steps=args.max_steps)
    print_report(rep)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
