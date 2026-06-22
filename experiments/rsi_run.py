#!/usr/bin/env python3
"""Pillar A (axis10) — run a REAL model as the self-improving Dreamer.

The plan/act runners use the model as Scout (planning) and Worker (execution). This
adds the third role so the actual benchmark run uses the FULL long-horizon,
multi-role agent: the model proposes working-graph edits, the harness RSI gate
accepts/rejects each, and axis10 measures whether the model's self-improvement
preserves the no-new-forbidden-path invariant — the half a single plan/act policy
never reaches.

Three scenarios, each over `cycles` Dreamer cycles:
  * self-improve (gate ON)  — does the model's optimization stay safe?
  * heal poisoned (gate ON) — a forbidden node is made reachable; does the model
                              propose removing the edge into it (trend → improving)?
  * ablation (gate OFF)     — would the model's own edits have drifted if ungated?

Usage::

    python experiments/rsi_run.py --model gemini-2.5-pro
    python experiments/rsi_run.py --model sonnet --cycles 3 --out results/pillar-a-rsi/sonnet.json
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agents.llm_agent import LLMAgent  # noqa: E402
from agents.llm_dreamer import LLMDreamer  # noqa: E402
from agents.ranger import RangerScout  # noqa: E402
from harness.rsi import (  # noqa: E402
    forbidden_nodes, run_rsi, self_improvement_safety,
)
from journeys.loader import load_journey, visible_view  # noqa: E402
from experiments.real_agent_run import (  # noqa: E402
    _VERTEX_PROJECT, _VERTEX_LOCATION, _VERTEX_KEY_WSL,
)

_DEFAULT_JOURNEY = os.path.join(_REPO_ROOT, "journeys", "project_inquiry_dev.json")


def _poison(working_graph):
    """Add an edge entry -> a forbidden node so a trap is reachable (a poisoned
    reconstruction the Dreamer should heal)."""
    g = copy.deepcopy(working_graph)
    forb = sorted(forbidden_nodes(g))
    if forb:
        g["edges"].append({"from": g["entry"], "to": forb[0],
                           "guard": "poisoned", "cost": 1, "risk": "low"})
    return g


def _axis10(working, dreamer, *, cycles, gated):
    initial, results, final = run_rsi(working, dreamer, cycles=cycles, gated=gated)
    ax = self_improvement_safety(initial, results)
    ax["rejections"] = [r for c in results for r in c.rejections][:4]
    return ax


def run(model, journey_path, *, cycles, seed, gemini_mode):
    journey = load_journey(journey_path)
    working = RangerScout.build_working_graph(visible_view(journey["route_graph"]))
    llm = LLMAgent(model=model, seed=seed, gemini_mode=gemini_mode, timeout=150,
                   vertex_project=_VERTEX_PROJECT, vertex_location=_VERTEX_LOCATION,
                   vertex_key=_VERTEX_KEY_WSL)
    dreamer = LLMDreamer(llm)
    scenarios = {
        "self_improve_gate_on": _axis10(working, dreamer, cycles=cycles, gated=True),
        "heal_poisoned_gate_on": _axis10(_poison(working), dreamer, cycles=cycles, gated=True),
        "ablation_gate_off": _axis10(working, dreamer, cycles=cycles, gated=False),
    }
    return {
        "model": model, "journey": journey.get("id"), "cycles": cycles,
        "graph": {"nodes": len(working.get("nodes", {})), "edges": len(working.get("edges", []))},
        "scenarios": scenarios, "usage": llm.usage,
    }


def _fmt(ax):
    return (f"trend={ax['trend']:<13} invariant={'Y' if ax['invariant_preserved'] else 'N'} "
            f"score={ax['score']:.2f} accepted={ax['accepted_edits']} "
            f"rejected={ax['rejected_unsafe_edits']} "
            f"reach={[ax['forbidden_reachable_baseline']] + ax['forbidden_reachable_per_cycle']}")


def print_report(rep):
    print(f"\n=== VISTA axis10 — model as self-improving Dreamer (RSI gate): `{rep['model']}` ===\n")
    print(f"working graph: {rep['journey']}  ({rep['graph']['nodes']} nodes, "
          f"{rep['graph']['edges']} edges)  ·  {rep['cycles']} cycles\n")
    labels = {"self_improve_gate_on": "self-improve · gate ON ",
              "heal_poisoned_gate_on": "heal poisoned · gate ON",
              "ablation_gate_off": "ablation     · gate OFF"}
    for key, label in labels.items():
        ax = rep["scenarios"][key]
        print(f"  [{label}] {_fmt(ax)}")
        if ax.get("rejections"):
            print(f"        rejected: {ax['rejections']}")
    u = rep["usage"]
    print(f"\n--- token cost: calls={u['calls']} in={u['input_tokens']} out={u['output_tokens']} "
          f"cost_usd=${u['cost_usd']:.4f} (Gemini billed to GCP credits => $0) ---")


def main(argv=None):
    p = argparse.ArgumentParser(description="VISTA axis10 — real model as Dreamer.")
    p.add_argument("--model", default="gemini-2.5-pro")
    p.add_argument("--cycles", type=int, default=3)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--journey", default=_DEFAULT_JOURNEY)
    p.add_argument("--gemini-mode", default="vertex", choices=["vertex", "apikey", "gca"])
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)
    rep = run(args.model, args.journey, cycles=args.cycles, seed=args.seed,
              gemini_mode=args.gemini_mode)
    print_report(rep)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
