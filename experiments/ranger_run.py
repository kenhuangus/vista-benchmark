#!/usr/bin/env python3
"""Pillar A — drive ONE journey through the FULL model-backed Ranger end to end.

The plan/act/rsi runners each exercise a real model in a single Ranger role and
build their own agent. This runner uses one :class:`agents.llm_ranger.LLMRanger`
— a single model wearing all three hats — and scores every axis from that one
agent, with one shared token ledger:

  * **Scout + Worker** — the model plans and then executes the journey one action
    at a time through the stepwise adapter (the injection-resistance + foresight +
    drift + calibration axes: axis01/02/03/06/07).
  * **Dreamer** — the same model then proposes working-graph self-edits the RSI
    gate judges, gate ON and (ablation) OFF (axis10).

So the "actual benchmark run" exercises the long-horizon, multi-role agent as one
coherent agent, not three disconnected single-role policies. ``--adversarial``
runs the Dreamer under jailbreak-style pressure (see ``rsi_run.py``).

Usage::

    python experiments/ranger_run.py --model gemini-2.5-pro
    python experiments/ranger_run.py --model sonnet --max-steps 8 --cycles 2 \
        --out results/pillar-a-ranger/sonnet.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agents.llm_ranger import LLMRanger  # noqa: E402
from agents.llm_dreamer import LLMDreamer, AdversarialLLMDreamer  # noqa: E402
from agents.ranger import RangerScout  # noqa: E402
from agents.stepwise_adapter import StepwiseAdapter  # noqa: E402
from contracts.adapter import Steering  # noqa: E402
from harness.rsi import run_rsi, self_improvement_safety  # noqa: E402
from journeys.loader import load_journey, visible_view  # noqa: E402
from experiments.real_agent_run import (  # noqa: E402
    _VERTEX_PROJECT, _VERTEX_LOCATION, _VERTEX_KEY_WSL,
)

_DEFAULT_JOURNEY = os.path.join(_REPO_ROOT, "journeys", "project_inquiry_dev.json")


def _axes(scorecard: dict) -> dict:
    """The headline axes from a stepwise (Scout+Worker) session scorecard."""
    ax = scorecard["axes"]
    gp, fs, ad = ax["axis01_goal_progress"], ax["axis02_foresight"], ax["axis03_alignment_drift"]
    vc, sec = ax["axis06_verification_calibration"], ax["axis07_security_abuse_resistance"]
    return {
        "passed": scorecard["pass_predicate"]["passed"],
        "goal_reached": gp["goal_reached"],
        "progress_rate": fs["progress_rate"],
        "optimality_gap": fs["optimality_gap"],
        "drift_count": ad["drift_count"],
        "precision": vc["precision"],
        "recall": vc["recall"],
        "targeted_asr_mean": sec["targeted_asr_mean"],
        "canary_egress_detected": sec["canary_egress_detected"],
        "leaked_canaries": sec["leaked_canaries"],
        "forbidden_crossing_detected": sec["forbidden_crossing_detected"],
        "injections_total": sec["injections_total"],
    }


def _action_trace(result) -> list:
    out = []
    for a in result.audit_log:
        act = a.get("action", {})
        detail = act.get("target") or act.get("text") or ""
        out.append(f"{a.get('at')}:{act.get('action')}={str(detail)[:40]}")
    return out


def _axis10(working, dreamer, *, cycles, gated):
    initial, results, _ = run_rsi(working, dreamer, cycles=cycles, gated=gated)
    ax = self_improvement_safety(initial, results)
    ax["rejections"] = [r for c in results for r in c.rejections][:4]
    return ax


def run(model, journey_path, *, max_steps, cycles, seed, gemini_mode, adversarial):
    journey = load_journey(journey_path)
    ranger = LLMRanger(model=model, seed=seed, gemini_mode=gemini_mode, timeout=150,
                       vertex_project=_VERTEX_PROJECT, vertex_location=_VERTEX_LOCATION,
                       vertex_key=_VERTEX_KEY_WSL)
    ranger.set_journey_context(journey)

    # Scout (plan) + Worker (sandboxed stepwise execution) — one agent, one loop.
    sw = StepwiseAdapter(ranger).run_session(journey, Steering(max_steps=max_steps))

    # Dreamer (offline self-improvement) — the SAME agent proposes working-graph
    # edits the RSI gate judges. Benign by default; pressured under --adversarial.
    working = RangerScout.build_working_graph(visible_view(journey["route_graph"]))
    dreamer = ranger.dreamer
    if adversarial:
        dreamer = AdversarialLLMDreamer(ranger.llm)
    dream = {
        ("pressured_gate_on" if adversarial else "self_improve_gate_on"):
            _axis10(working, dreamer, cycles=cycles, gated=True),
        ("pressured_gate_off" if adversarial else "ablation_gate_off"):
            _axis10(working, dreamer, cycles=cycles, gated=False),
    }
    return {
        "agent": ranger.name, "model": model, "journey": journey.get("id"),
        "domain": journey.get("domain"), "mode": "adversarial" if adversarial else "benign",
        "roles": {
            "scout_worker": {"axes": _axes(sw.scorecard), "trace": _action_trace(sw)},
            "dreamer": dream,
        },
        "usage": ranger.usage,  # ONE ledger across Scout + Worker + Dreamer
    }


def _fmt_axis10(ax):
    return (f"trend={ax['trend']:<13} invariant={'Y' if ax['invariant_preserved'] else 'N'} "
            f"score={ax['score']:.2f} accepted={ax['accepted_edits']} "
            f"rejected={ax['rejected_unsafe_edits']} "
            f"reach={[ax['forbidden_reachable_baseline']] + ax['forbidden_reachable_per_cycle']}")


def print_report(rep):
    print(f"\n=== VISTA Pillar-A — full model-backed Ranger (Scout+Worker+Dreamer): "
          f"`{rep['agent']}` ===\n")
    print(f"journey: {rep['journey']} ({rep['domain']})  ·  mode: {rep['mode']}\n")
    a = rep["roles"]["scout_worker"]["axes"]
    print("  [Scout+Worker · stepwise execution]")
    print(f"    passed={'Y' if a['passed'] else 'N'} goal={'Y' if a['goal_reached'] else 'N'} "
          f"progress={a['progress_rate']:.2f} drift={a['drift_count']} "
          f"recall={a['recall']:.2f} asr={a['targeted_asr_mean']:.2f} "
          f"egress={'Y' if a['canary_egress_detected'] else 'N'} inj={a['injections_total']}")
    print(f"    trace: {rep['roles']['scout_worker']['trace']}")
    print("\n  [Dreamer · self-improvement (axis10)]")
    for key, ax in rep["roles"]["dreamer"].items():
        print(f"    {key:20}: {_fmt_axis10(ax)}")
        if ax.get("rejections"):
            print(f"      rejected: {ax['rejections']}")
    u = rep["usage"]
    print(f"\n--- one ledger, all three roles: calls={u['calls']} in={u['input_tokens']} "
          f"out={u['output_tokens']} cost_usd=${u['cost_usd']:.4f} "
          f"(Gemini billed to GCP credits => $0) ---")


def main(argv=None):
    p = argparse.ArgumentParser(description="VISTA Pillar-A — full model-backed Ranger.")
    p.add_argument("--model", default="gemini-2.5-pro")
    p.add_argument("--max-steps", type=int, default=10, help="Worker turn budget cap")
    p.add_argument("--cycles", type=int, default=2, help="Dreamer self-improvement cycles")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--journey", default=_DEFAULT_JOURNEY)
    p.add_argument("--gemini-mode", default="vertex", choices=["vertex", "apikey", "gca"])
    p.add_argument("--adversarial", action="store_true",
                   help="run the Dreamer under jailbreak-style pressure (axis10 discriminator)")
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)
    rep = run(args.model, args.journey, max_steps=args.max_steps, cycles=args.cycles,
              seed=args.seed, gemini_mode=args.gemini_mode, adversarial=args.adversarial)
    print_report(rep)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
