#!/usr/bin/env python3
"""Pillar A — run a REAL frontier model through VISTA and score it.

This is the first VISTA experiment in which the system-under-test is an actual
LLM, not a deterministic reference policy. It drives the model through the *same*
:class:`agents.adapter.HarnessAgentAdapter` + deterministic scorer the reference
agents use, so the model's scorecard is directly comparable to ``naive`` and
``ranger``. The model is invoked via the Claude Code CLI on a subscription login
(:class:`agents.llm_agent.LLMAgent`); token usage and equivalent USD cost are
accumulated and reported.

Usage (run from the repo root, Windows Python; the CLI is reached in WSL)::

    python experiments/real_agent_run.py --model sonnet
    python experiments/real_agent_run.py --model opus --runs 3
    python experiments/real_agent_run.py --model sonnet --journeys journeys/coding_pr_review_test.json

What it exercises: goal progress, foresight (progress-rate / optimality-gap),
alignment drift, the headline verification-calibration axis (does the model
escalate at the genuine ``risk:high`` fork?), and security-abuse-resistance (does
the model route toward the forbidden ``funds_sent`` state after reading the
injected wire-transfer payload?). The deterministic baselines are run alongside
for reference.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from contracts.adapter import Steering  # noqa: E402
from agents.adapter import HarnessAgentAdapter  # noqa: E402
from agents.naive_agent import NaiveAgent  # noqa: E402
from agents.ranger import RangerAgent  # noqa: E402
from agents.llm_agent import LLMAgent, LLMAgentError  # noqa: E402
from journeys.loader import load_journey  # noqa: E402

_DEFAULT_JOURNEYS = [
    "journeys/project_inquiry_dev.json",
    "journeys/coding_pr_review_test.json",
    "journeys/research_synthesis_challenge.json",
]

# Vertex defaults for Gemini models (overridable by env or CLI flags). The
# service-account key lives OUTSIDE the repo so it can never be committed.
_VERTEX_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentready-0615152320")
_VERTEX_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
_VERTEX_KEY_WSL = os.environ.get("VERTEX_SA_KEY_WSL", "/mnt/c/Users/kenhu/.vista/vertex-sa.json")


def _metrics(scorecard: dict) -> dict:
    """Pull the comparable headline metrics out of a VISTA scorecard."""
    ax = scorecard["axes"]
    return {
        "passed": scorecard["pass_predicate"]["passed"],
        "goal_reached": ax["axis01_goal_progress"]["goal_reached"],
        "progress_rate": ax["axis02_foresight"]["progress_rate"],
        "optimality_gap": ax["axis02_foresight"]["optimality_gap"],
        "realized_cost": ax["axis02_foresight"]["realized_cost"],
        "drift_count": ax["axis03_alignment_drift"]["drift_count"],
        "recall": ax["axis06_verification_calibration"]["recall"],
        "precision": ax["axis06_verification_calibration"]["precision"],
        "targeted_asr_mean": ax["axis07_security_abuse_resistance"]["targeted_asr_mean"],
        "forbidden_crossing": ax["axis07_security_abuse_resistance"]["forbidden_crossing_detected"],
    }


def _applied_path(result) -> list:
    """The node ids the agent actually moved to (applied transitions only)."""
    return [t.to_node for t in result.trajectory if t.applied]


def _score(journey: dict, agent, *, seed: int, is_llm: bool) -> dict:
    if is_llm:
        agent.set_journey_context(journey)
    adapter = HarnessAgentAdapter(agent)
    result = adapter.run_session(
        journey, journey.get("initial_route_state", {}), Steering(seed=seed)
    )
    out = {"metrics": _metrics(result.scorecard), "path": _applied_path(result)}
    if is_llm:
        out["raw_plan"] = list(agent.last_plan_raw)
    return out


def run(model: str, journey_paths: list, *, runs: int, seed: int,
        gemini_mode: str = "vertex") -> dict:
    rows = []
    # one agent -> usage accumulates across all of its calls
    llm = LLMAgent(
        model=model, seed=seed, gemini_mode=gemini_mode,
        vertex_project=_VERTEX_PROJECT, vertex_location=_VERTEX_LOCATION,
        vertex_key=_VERTEX_KEY_WSL,
    )
    for path in journey_paths:
        journey = load_journey(path)
        jid = journey.get("id", os.path.basename(path))
        ref = {
            "naive": _score(journey, NaiveAgent(seed=seed), seed=seed, is_llm=False),
            "ranger": _score(journey, RangerAgent(seed=seed), seed=seed, is_llm=False),
        }
        llm_runs = []
        for r in range(runs):
            try:
                llm_runs.append(_score(journey, llm, seed=seed, is_llm=True))
            except LLMAgentError as exc:
                llm_runs.append({"error": str(exc)})
        rows.append({
            "journey": jid, "domain": journey.get("domain"), "split": journey.get("split"),
            "reference": ref, "llm_runs": llm_runs,
        })
    return {"model": model, "runs_per_journey": runs, "results": rows, "usage": llm.usage}


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def _fmt(m: dict) -> str:
    return (
        f"pass={'Y' if m['passed'] else 'N'} "
        f"goal={'Y' if m['goal_reached'] else 'N'} "
        f"recall={m['recall']:.2f} drift={m['drift_count']} "
        f"opt_gap={m['optimality_gap']:.1f} asr={m['targeted_asr_mean']:.2f} "
        f"forbidden={'Y' if m['forbidden_crossing'] else 'N'}"
    )


def print_report(report: dict) -> None:
    model = report["model"]
    print(f"\n=== VISTA Pillar-A: real model `{model}` vs deterministic baselines ===\n")
    for row in report["results"]:
        print(f"[{row['journey']}]  ({row['domain']}/{row['split']})")
        print(f"  naive   : {_fmt(row['reference']['naive']['metrics'])}")
        print(f"  ranger  : {_fmt(row['reference']['ranger']['metrics'])}")
        for i, lr in enumerate(row["llm_runs"]):
            if "error" in lr:
                print(f"  {model} #{i+1}: ERROR {lr['error']}")
            else:
                print(f"  {model} #{i+1}: {_fmt(lr['metrics'])}")
                print(f"            plan={lr['raw_plan']}  applied_path={lr['path']}")
        print()
    u = report["usage"]
    print("--- token cost (subscription-billed; USD is API-equivalent from the CLI) ---")
    print(f"  calls={u['calls']}  input_tokens={u['input_tokens']}  output_tokens={u['output_tokens']}")
    print(f"  cache_read={u['cache_read_input_tokens']}  cache_creation={u['cache_creation_input_tokens']}")
    print(f"  cost_usd=${u['cost_usd']:.4f}")
    for mid, mu in u["by_model"].items():
        print(f"    {mid}: in={mu['input_tokens']} out={mu['output_tokens']} ${mu['cost_usd']:.4f}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run a real LLM through VISTA Bench (Pillar A).")
    p.add_argument("--model", default="sonnet", help="model alias for the claude CLI (sonnet|opus|...)")
    p.add_argument("--runs", type=int, default=1, help="LLM runs per journey (pass^k variance)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--journeys", nargs="*", default=None, help="journey paths (default: 3 hand-authored)")
    p.add_argument("--gemini-mode", default="vertex", choices=["vertex", "apikey", "gca"],
                   help="how the Gemini CLI authenticates (default: vertex)")
    p.add_argument("--json", action="store_true", help="also print the full result JSON")
    p.add_argument("--out", default=None, help="write the full result JSON to this path")
    args = p.parse_args(argv)

    journeys = args.journeys or _DEFAULT_JOURNEYS
    report = run(args.model, journeys, runs=args.runs, seed=args.seed,
                 gemini_mode=args.gemini_mode)
    print_report(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
        print(f"\nwrote {args.out}")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
