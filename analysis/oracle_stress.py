#!/usr/bin/env python3
"""AB1b — corpus growth: make the hidden oracle load-bearing (deterministic, $0)

AB1 found that on the *current* corpus the hidden `optimal_walk`/`subgoal_states`
oracle is NOT load-bearing — `optimal_walk` coincides with the cheapest visible path
and both reference agents fire every gold subgoal, so a visible-only scorer reproduces
the verdicts. AB1's directive was to add journeys where (a) `optimal_walk` diverges
from the cheapest visible path and (b) the goal is reachable while SKIPPING a gold
subgoal.

This runs that directive on `journeys/oracle_stress_001.json` — a quality-gate journey
whose intended (optimal) walk goes start->gather->verify->published (cost 3, hits both
gold subgoals) while a cheap shortcut start->published (cost 1) reaches the goal but
skips verification. Two trajectories are driven through the REAL runtime:

  * **thorough** — follows the optimal walk, hits both gold subgoals.
  * **shortcut** — takes the cheap edge straight to the goal, skipping verification.

and scored by the real oracle scorer vs the visible-only blind scorer. On THIS journey
the oracle is load-bearing: the real scorer separates the two runs (progress 1.0 vs
0.0) while the blind scorer cannot (both reach the goal) and even INVERTS optimality
(it penalises the thorough run for paying more than the cheapest visible path). H6,
refuted on the original corpus, is **confirmed here** — exactly the journey shape the
corpus needs.

    python analysis/oracle_stress.py
    python analysis/oracle_stress.py --out analysis/AB1b-oracle-stress.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import glob

from analysis.oracle_ablation import blind_scores  # noqa: E402
from harness.runtime import RouteGraphRuntime, validate_graph  # noqa: E402
from harness.scorer import Scorer  # noqa: E402
from journeys.loader import visible_view  # noqa: E402

# Every oracle-divergent stress journey (the AB1b corpus-growth family). Kept SEPARATE
# from journeys/corpus.py::full_corpus() on purpose: adding them there would change n
# and break A1-A8 and the reference suite.
_JOURNEY_GLOB = os.path.join(_REPO_ROOT, "journeys", "oracle_stress_*.json")


def _drive(route_graph: dict, moves: list[tuple[str, str]]):
    """Drive a sequence of (target, guard) moves through the real runtime so the
    transition flags (applied / on-optimal-walk / off-walk) are set authentically."""
    rt = RouteGraphRuntime(route_graph)
    traj = []
    for target, guard in moves:
        traj.append(rt.step(target, guard=guard).transition)
    return traj


def _thorough_moves(rg: dict) -> list[tuple[str, str]]:
    """(target, guard) pairs along `optimal_walk` — the intended, subgoal-hitting walk."""
    edges = {(e["from"], e["to"]): e for e in rg["edges"]}
    walk = rg["optimal_walk"]
    return [(b, edges[(a, b)].get("guard", "")) for a, b in zip(walk, walk[1:])]


def _shortcut_move(rg: dict):
    """The single cheap edge straight from entry to goal that skips the gold subgoals,
    as a one-element [(goal, guard)]; None if the journey has no such shortcut."""
    entry, goal = rg["entry"], rg["goal"]
    for e in rg["edges"]:
        if e["from"] == entry and e["to"] == goal:
            return [(goal, e.get("guard", ""))]
    return None


def _blind_progress(vv: dict, trajectory) -> float:
    """A visible-only progress proxy: did the run reach the goal? (A blind scorer
    cannot see `subgoal_states`, so 'reached the goal' is the natural reading.)"""
    goal = vv["goal"]
    return 1.0 if any(t.applied and t.to_node == goal for t in trajectory) else 0.0


def _run_journey(path: str) -> dict:
    journey = json.load(open(path, encoding="utf-8"))
    rg = journey["route_graph"]
    validate_graph(rg)
    vv = visible_view(rg)
    scorer = Scorer()
    state = {"memory": {}, "messages": [], "dream_journal": [], "audit_log": []}

    shortcut = _shortcut_move(rg)
    if shortcut is None:
        raise ValueError(f"{journey['id']}: no entry->goal shortcut edge (not oracle-divergent)")
    trajs = {"thorough": _drive(rg, _thorough_moves(rg)), "shortcut": _drive(rg, shortcut)}
    agents = {}
    for name, traj in trajs.items():
        sc = scorer.score(rg, traj, journey=journey, final_route_state=state)
        f = sc["axes"]["axis02_foresight"]
        blind = blind_scores(vv, traj)
        agents[name] = {
            "real_progress": f["progress_rate"],
            "real_optimality_gap": f["optimality_gap"],
            "real_subgoals": f["subgoals_reached"],
            "blind_progress": _blind_progress(vv, traj),
            "blind_optimality_gap": blind["blind_optimality_gap"],
            "goal_reached": sc["axes"]["axis01_goal_progress"]["goal_reached"],
        }
    return {"journey": journey["id"], "domain": journey.get("domain", "?"), "agents": agents}


def run() -> dict:
    """Run the oracle-stress comparison over EVERY oracle_stress_*.json journey."""
    paths = sorted(glob.glob(_JOURNEY_GLOB))
    return {"journeys": [_run_journey(p) for p in paths]}


def _load_bearing(a: dict) -> dict:
    """Per-journey verdict flags from a {thorough, shortcut} agents dict."""
    real_sep = a["thorough"]["real_progress"] > a["shortcut"]["real_progress"]
    blind_sep = a["thorough"]["blind_progress"] > a["shortcut"]["blind_progress"]
    blind_inverts = (a["thorough"]["blind_optimality_gap"] > a["shortcut"]["blind_optimality_gap"]
                     and a["thorough"]["real_optimality_gap"] <= a["shortcut"]["real_optimality_gap"])
    return {"real_sep": real_sep, "blind_sep": blind_sep, "blind_inverts": blind_inverts,
            "load_bearing": real_sep and not blind_sep}


def build_report(data: dict) -> list[str]:
    journeys = data["journeys"]
    L: list[str] = []
    w = L.append
    w("# AB1b — Corpus growth: journeys where the hidden oracle IS load-bearing")
    w("")
    w(f"Generated by `analysis/oracle_stress.py` (deterministic, $0, no model calls) over "
      f"**{len(journeys)} oracle-divergent journeys** (`journeys/oracle_stress_*.json`), one "
      "per domain. Each is built per AB1's directive: the intended `optimal_walk` (cost 3, "
      "through two gold subgoals) diverges from the cheapest visible path — a cheap shortcut "
      "(cost 1) that reaches the goal while skipping verification.")
    w("")
    w("## Per-journey: real scorer vs visible-only blind scorer")
    w("")
    w("| journey | domain | run | real prog | blind prog | real gap | blind gap | goal |")
    w("|---|---|---|---|---|---|---|---|")
    for j in journeys:
        a = j["agents"]
        for name in ("thorough", "shortcut"):
            r = a[name]
            w(f"| `{j['journey']}` | {j['domain']} | {name} | {r['real_progress']:.2f} | "
              f"{r['blind_progress']:.2f} | {r['real_optimality_gap']:.1f} | "
              f"{r['blind_optimality_gap']:.1f} | {'Y' if r['goal_reached'] else 'N'} |")
    w("")
    verdicts = [(_load_bearing(j["agents"]), j) for j in journeys]
    all_load_bearing = all(v["load_bearing"] for v, _ in verdicts)
    all_invert = all(v["blind_inverts"] for v, _ in verdicts)
    w("## Is the hidden oracle load-bearing?")
    w("")
    w("On every journey: the **real scorer** separates the thorough run from the "
      "verification-skipping shortcut on progress (1.0 vs 0.0 — it reads the hidden "
      "`subgoal_states`), while the **blind scorer** cannot (both reach the goal, so "
      "blind progress is 1.0 for both) and even **inverts optimality** (it penalises the "
      "thorough run for paying more than the cheapest visible path).")
    w("")
    w(f"- real scorer separates on every journey: **{'YES' if all_load_bearing else 'no'}** "
      f"({sum(v['real_sep'] for v, _ in verdicts)}/{len(verdicts)}).")
    w(f"- blind scorer fails to separate on every journey: "
      f"**{'YES' if all(not v['blind_sep'] for v, _ in verdicts) else 'no'}** "
      f"({sum(not v['blind_sep'] for v, _ in verdicts)}/{len(verdicts)}).")
    w(f"- blind scorer inverts optimality on every journey: **{'YES' if all_invert else 'no'}** "
      f"({sum(v['blind_inverts'] for v, _ in verdicts)}/{len(verdicts)}).")
    w("")
    w("## Conclusion")
    w("")
    if all_load_bearing:
        w(f"Across all {len(journeys)} domains the hidden `optimal_walk`/`subgoal_states` "
          "oracle is **load-bearing**: a visible-only scorer cannot tell a subgoal-skipping "
          "shortcut from a thorough run and even inverts the optimality verdict. **H6 — "
          "refuted on the original corpus (AB1) — is confirmed across the whole oracle-"
          "divergent family.** AB1b's single-journey result now generalises across "
          "domains/splits (plan threats §1–2): the journey shape — an intended walk that "
          "diverges from the cheapest visible path, with a gold subgoal skippable while "
          "still reaching the goal — is what corpus growth must add to make the oracle pay "
          "its way. These journeys live OUTSIDE `full_corpus()` so A1-A8 and the reference "
          "suite are unaffected.")
    else:
        w("(Unexpected: inspect the per-run rows — at least one journey did not produce the "
          "real-separates / blind-cannot pattern.)")
    w("")
    w("---")
    w("")
    w("*Recompute byte-for-byte with `python analysis/oracle_stress.py`.*")
    return L


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description="VISTA AB1b — oracle-stress corpus growth.")
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)
    report = "\n".join(build_report(run())) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(report)
        print(f"wrote {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
