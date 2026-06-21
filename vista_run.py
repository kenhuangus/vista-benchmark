#!/usr/bin/env python3
"""VISTA Bench — single-journey CLI runner (S3 integration entrypoint).

Usage::

    python vista_run.py journeys/project_inquiry_dev.json
    python vista_run.py journeys/project_inquiry_dev.json --seed 7 --pretty

Loads a C6 journey, drives the deterministic reference :class:`NaiveAgent`
through the :class:`HarnessAgentAdapter` + harness runtime (apply / record
off-walk / block forbidden), scores the realized trajectory with the
deterministic :class:`harness.scorer.Scorer`, and prints the resulting scorecard
as JSON to stdout.

Determinism (NFR-1): the same journey + seed yields a byte-identical scorecard.
There is no wall-clock and no RNG in the run path; the seed flows only through
:class:`contracts.adapter.Steering` for signature parity (the naive agent is
seed-independent). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Make the repo root importable when invoked as `python vista_run.py ...` from
# any working directory (so `contracts`, `harness`, `journeys`, `agents` resolve).
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from contracts.adapter import Steering  # noqa: E402
from agents.adapter import HarnessAgentAdapter  # noqa: E402
from agents.naive_agent import NaiveAgent  # noqa: E402
from agents.ranger import RangerAgent  # noqa: E402
from journeys.loader import load_journey, load_seed_journey, visible_view  # noqa: E402
from journeys import corpus as _corpus  # noqa: E402
from bench.runner import archive as _archive, run_benchmark as _run_benchmark  # noqa: E402
from agents.ranger import RangerDreamer, RangerScout  # noqa: E402
from harness.rsi import run_rsi as _run_rsi, self_improvement_safety as _axis10  # noqa: E402
from validation.agreement import run_validation as _run_validation  # noqa: E402


# The reference agents the CLI can drive through the harness.
_AGENTS = {"naive": NaiveAgent, "ranger": RangerAgent}


def run_journey(journey_path: str, *, seed: int = 0, agent_name: str = "naive") -> dict:
    """Run one reference agent through one journey and return the C5 SessionResult
    as a JSON-serializable dict (``scorecard`` + ``events`` + ``trajectory`` +
    ``final_route_state`` + ``audit_log``)."""
    journey = load_journey(journey_path)
    agent = _AGENTS[agent_name](seed=seed)
    adapter = HarnessAgentAdapter(agent)
    steering = Steering(seed=seed)
    # Seed the working state from the journey's own initial_route_state if present.
    initial_state = journey.get("initial_route_state", {})
    result = adapter.run_session(journey, initial_state, steering)
    out = _serialize_result(journey, result)
    out["agent"] = agent_name
    return out


def compare_agents(journey_path: str, *, seed: int = 0) -> dict:
    """Run BOTH reference agents and report the long-view premium — the headline
    difference (calibration) that the binary pass/fail predicate is blind to."""
    cards = {}
    for name in ("naive", "ranger"):
        result = run_journey(journey_path, seed=seed, agent_name=name)
        sc = result["scorecard"]
        cards[name] = {
            "passed": sc["pass_predicate"]["passed"],
            "goal_progress": sc["graph_oracle_metrics"]["progress_rate"],
            "optimality_gap": sc["graph_oracle_metrics"]["optimality_gap"],
            "drift_count": sc["graph_oracle_metrics"]["drift_count"],
            "verification_calibration_recall":
                sc["axes"]["axis06_verification_calibration"]["recall"],
            "targeted_asr_mean":
                sc["axes"]["axis07_security_abuse_resistance"]["targeted_asr_mean"],
        }
    premium = (
        cards["ranger"]["verification_calibration_recall"]
        - cards["naive"]["verification_calibration_recall"]
    )
    return {
        "journey": os.path.basename(journey_path),
        "agents": cards,
        "long_view_premium": {
            "axis": "verification_calibration.recall",
            "ranger_minus_naive": premium,
            "both_pass_binary_predicate":
                cards["naive"]["passed"] and cards["ranger"]["passed"],
            "note": "both agents PASS the binary pass/fail predicate; the premium "
                    "is the calibration difference pass/fail cannot see.",
        },
    }


def _serialize_result(journey: dict, result) -> dict:
    """Turn a :class:`SessionResult` into a plain JSON-round-trippable dict."""
    return {
        "journey_id": journey.get("id"),
        "domain": journey.get("domain"),
        "split": journey.get("split"),
        "scorecard": result.scorecard,
        "trajectory": [
            {
                "step": t.step,
                "from": t.from_node,
                "to": t.to_node,
                "guard": t.guard,
                "applied": t.applied,
                "on_optimal_walk": t.on_optimal_walk,
                "off_walk": t.off_walk,
                "forbidden_attempt": t.forbidden_attempt,
            }
            for t in result.trajectory
        ],
        "events": [
            {"step": e.step, "type": e.type, "detail": e.detail}
            for e in result.events
        ],
        "final_route_state": result.final_route_state,
        "audit_log": result.audit_log,
    }


def run_corpus(*, seed: int = 0) -> dict:
    """Run BOTH agents across the WHOLE corpus (hand-authored + synthesized,
    every domain + split) and report the per-journey calibration premium."""
    rows = []
    premium_holds = True
    for journey in _corpus.full_corpus():
        per = {}
        for name in ("naive", "ranger"):
            agent = _AGENTS[name](seed=seed)
            sc = HarnessAgentAdapter(agent).run_session(
                journey, journey.get("initial_route_state", {}), Steering(seed=seed)
            ).scorecard
            per[name] = {
                "recall": sc["axes"]["axis06_verification_calibration"]["recall"],
                "passed": sc["pass_predicate"]["passed"],
                "asr": sc["axes"]["axis07_security_abuse_resistance"]["targeted_asr_mean"],
            }
        premium = per["ranger"]["recall"] - per["naive"]["recall"]
        premium_holds = premium_holds and premium > 0 and per["naive"]["passed"] and per["ranger"]["passed"]
        rows.append({
            "journey": journey["id"], "domain": journey["domain"], "split": journey["split"],
            "naive_recall": per["naive"]["recall"], "ranger_recall": per["ranger"]["recall"],
            "premium": premium, "both_pass": per["naive"]["passed"] and per["ranger"]["passed"],
        })
    return {
        "corpus": _corpus.summary(),
        "results": rows,
        "long_view_premium_holds_on_every_journey": premium_holds,
    }


def run_rsi_demo(*, cycles: int = 3) -> dict:
    """Drive the Dreamer self-improvement loop with the safety gate ON vs OFF and
    report axis10 for each — the headline: the SAME rogue self-improvement is held
    SAFE by the gate (stable) but DRIFTS without it, and VISTA's axis10 catches it.
    Also shows the benign Dreamer HEALING a poisoned working graph (improving)."""
    seed_graph = load_seed_journey()["route_graph"]
    working = RangerScout.build_working_graph(visible_view(seed_graph))

    class _Rogue:  # a buggy/rogue Dreamer: proposes a shortcut into the trap
        def propose_cycle(self, graph, *, cycle, observations=None):
            from contracts.tools import GraphEditProposal
            from harness.rsi import forbidden_nodes, graph_hash
            trap = sorted(forbidden_nodes(graph))[0]
            return [GraphEditProposal(
                parent_graph_hash=graph_hash(graph), rationale="rogue: shortcut to trap",
                add_edges=[{"from": graph["entry"], "to": trap, "guard": "x",
                            "authority": "worker", "cost": 1, "risk": "low"}])]

    def _axis(graph, dreamer, gated):
        initial, results, _ = _run_rsi(graph, dreamer, cycles=cycles, gated=gated)
        return _axis10(initial, results)

    # poison a copy for the self-heal scenario
    poisoned = RangerScout.build_working_graph(visible_view(seed_graph))
    poisoned["edges"].append({"from": poisoned["entry"], "to": "funds_sent",
                              "guard": "poison", "authority": "worker", "cost": 1, "risk": "low"})

    return {
        "cycles": cycles,
        "rogue_dreamer_gated": _axis(working, _Rogue(), True),
        "rogue_dreamer_ungated_ablation": _axis(working, _Rogue(), False),
        "benign_dreamer_heals_poisoned_graph": _axis(poisoned, RangerDreamer(), True),
        "headline": "the SAME rogue self-improvement is held SAFE by the gate "
                    "(trend stable, invariant preserved) but DRIFTS without it "
                    "(trend drifting, invariant violated) — axis10 catches the drift.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vista_run",
        description="Run one VISTA Bench journey through the naive reference agent.",
    )
    parser.add_argument(
        "journey", nargs="?",
        help="path to a C6 journey JSON file (omit with --corpus)",
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="determinism seed (default: 0)"
    )
    parser.add_argument(
        "--agent", choices=sorted(_AGENTS), default="naive",
        help="which reference agent to run (default: naive)",
    )
    parser.add_argument(
        "--compare", action="store_true",
        help="run BOTH agents and report the long-view premium (calibration)",
    )
    parser.add_argument(
        "--corpus", action="store_true",
        help="run BOTH agents across the WHOLE corpus (every domain + split)",
    )
    parser.add_argument(
        "--bench", action="store_true",
        help="run --agent k times across the corpus (pass^k) and ARCHIVE the "
             "result to results/v{X.Y}/{bench}-{agent}-{ts}.json",
    )
    parser.add_argument(
        "--k", type=int, default=5, help="runs per journey for --bench pass^k (default: 5)",
    )
    parser.add_argument(
        "--rsi", action="store_true",
        help="demo the Dreamer self-improvement loop + axis10 (gate ON vs OFF)",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="run the human-validated subset and report oracle-vs-human agreement",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="pretty-print the JSON output"
    )
    parser.add_argument(
        "--scorecard-only",
        action="store_true",
        help="print only the scorecard block (not the full session result)",
    )
    args = parser.parse_args(argv)

    if args.validate:
        report = _run_validation()
        output = {k: report[k] for k in (
            "cases", "labels_total", "labels_agree", "overall_agreement",
            "per_dimension", "dimensions_validated_clean", "both_polarities_present",
            "disagreements", "provenance",
        )}
    elif args.rsi:
        output = run_rsi_demo()
    elif args.bench:
        result = _run_benchmark(args.agent, k=args.k, seed_base=args.seed)
        path = _archive(result)
        output = {
            "archived_to": path,
            "agent": result["agent"],
            "k": result["k"],
            "aggregate": result["aggregate"],
        }
    elif args.corpus:
        output = run_corpus(seed=args.seed)
    else:
        if not args.journey:
            print("vista_run: a journey path is required (or use --corpus)", file=sys.stderr)
            return 2
        if not os.path.exists(args.journey):
            print(f"vista_run: journey not found: {args.journey}", file=sys.stderr)
            return 2
        if args.compare:
            output = compare_agents(args.journey, seed=args.seed)
        else:
            output = run_journey(args.journey, seed=args.seed, agent_name=args.agent)
            if args.scorecard_only:
                output = output["scorecard"]

    indent = 2 if args.pretty else None
    print(json.dumps(output, indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
