#!/usr/bin/env python3
"""Statistically-powered grok stepwise study — DEPTH + BREADTH + CONFOUND.

The committed pass^k leaderboard is k=5 on ONE journey (a 0/5 has a Wilson CI of
[0, 43%] — not publishable). This driver upgrades the grok finding to a defensible,
paper-grade result with three phases:

  * DEPTH    — canonical cliff journey, k=20, plan mode  → tight Wilson CI on the
               headline goal-reach rate (rule-of-three: 0/20 ⇒ 95% upper bound ~16%).
  * BREADTH  — one easy-tier test-split journey per domain (6 domains), k=5 each
               → the stall generalizes across domains, not a single-journey artifact.
  * CONFOUND — canonical journey, k=10, grok permission-mode 'default' (not 'plan')
               → rules out plan-mode disposition as the cause of the stepwise stall.

Run UNBUFFERED and DETACHED (the harness's Bash background tasks are killed at the
10-minute cap; this is a multi-hour job, so it must be its own OS process):

    python -u experiments/grok_stepwise_study.py

It is RESUMABLE and crash/sleep-safe: every single run is appended (flush+fsync) to
``results/grok-stepwise-study/progress.jsonl`` the instant it finishes, and the
deterministic Ranger baselines to ``ranger.jsonl``. On restart it skips every run
already present, so a kill loses at most the one in-flight run. When all runs for a
phase exist it assembles the phase JSON in the exact ``passk_run`` shape, so
``analysis/grok_stepwise.py`` (Wilson + fixed-seed bootstrap CIs) consumes it
unchanged. A grok CLI proxy failure is recorded as an error and excluded from the
rate denominators — never silently counted as a non-goal.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agents.ranger import RangerAgent  # noqa: E402
from agents.llm_agent import LLMAgent, LLMAgentError  # noqa: E402
from agents.stepwise_adapter import StepwiseAdapter, PlanReplayAgent  # noqa: E402
from contracts.adapter import Steering  # noqa: E402
from experiments.security_run import _sec  # noqa: E402
from experiments.passk_run import _tier, _agg, _resolve_journeys  # noqa: E402

_MODEL = "grok-build"
_SEED = 0
_OUT_DIR = os.path.join(_REPO_ROOT, "results", "grok-stepwise-study")
_PROGRESS = os.path.join(_OUT_DIR, "progress.jsonl")
_RANGER = os.path.join(_OUT_DIR, "ranger.jsonl")
_LOG = os.path.join(_OUT_DIR, "study.log")

_BREADTH_IDS = [f"scaled-{d}-test-easy-00"
                for d in ("project", "coding", "research", "finance", "legal", "support")]

# (name, journey_ids, k, permission_mode, max_steps)
_PHASES = [
    ("depth", ["project-stewardship-inquiry-001"], 20, "plan", 6),
    ("breadth", _BREADTH_IDS, 5, "plan", 8),
    ("confound", ["project-stewardship-inquiry-001"], 10, "default", 6),
]


def _log(msg: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _append(path: str, obj: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _load_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _key(phase: str, jid: str, perm: str, run_idx: int) -> str:
    return f"{phase}|{jid}|{perm}|{run_idx}"


def main() -> int:
    os.makedirs(_OUT_DIR, exist_ok=True)
    done_runs = {_key(r["phase"], r["journey"], r["perm"], r["run_idx"])
                 for r in _load_jsonl(_PROGRESS)}
    done_ranger = {f"{r['phase']}|{r['journey']}" for r in _load_jsonl(_RANGER)}
    total = sum(k * len(ids) for _, ids, k, _, _ in _PHASES)
    _log(f"=== grok stepwise study start · {total} runs planned · "
         f"{len(done_runs)} already done (resume) ===")

    for name, ids, k, perm, max_steps in _PHASES:
        journeys = _resolve_journeys(None, ids)
        _log(f"### PHASE {name} · {len(ids)} journey(s) · k={k} · perm={perm} · "
             f"max_steps={max_steps}")
        llm = LLMAgent(model=_MODEL, seed=_SEED, grok_permission_mode=perm)
        steering = Steering(max_steps=max_steps)
        for journey in journeys:
            jid = journey["id"]
            # Deterministic Ranger baseline — compute once per (phase, journey).
            if f"{name}|{jid}" not in done_ranger:
                rsc = StepwiseAdapter(PlanReplayAgent(RangerAgent())).run_session(
                    journey, steering).scorecard
                _append(_RANGER, {"phase": name, "journey": jid,
                                  "domain": journey.get("domain"),
                                  "tier": _tier(jid), "sec": _sec(rsc)})
                _log(f"    ranger baseline {jid}: goal={_sec(rsc)['goal_reached']}")
            for run_idx in range(k):
                if _key(name, jid, perm, run_idx) in done_runs:
                    continue
                rec = {"phase": name, "journey": jid, "domain": journey.get("domain"),
                       "tier": _tier(jid), "perm": perm, "run_idx": run_idx}
                try:
                    llm.set_journey_context(journey)
                    sc = StepwiseAdapter(llm).run_session(journey, steering).scorecard
                    sec = _sec(sc)
                    rec["sec"] = sec
                    _append(_PROGRESS, rec)
                    _log(f"    {name} {jid} {perm} run {run_idx+1}/{k}: "
                         f"goal={sec['goal_reached']} pass={sec['passed']} "
                         f"asr={sec['targeted_asr_mean']:.2f} recall={sec['recall']:.2f}")
                except LLMAgentError as exc:
                    rec["error"] = str(exc)[:200]
                    _append(_PROGRESS, rec)
                    _log(f"    {name} {jid} {perm} run {run_idx+1}/{k}: ERROR {rec['error'][:80]}")

    _assemble()
    _log("=== study COMPLETE — all phase JSONs written ===")
    return 0


def _assemble() -> None:
    """Build depth.json / breadth.json / confound.json in the passk_run shape."""
    runs = _load_jsonl(_PROGRESS)
    rangers = {f"{r['phase']}|{r['journey']}": r for r in _load_jsonl(_RANGER)}
    for name, ids, k, perm, max_steps in _PHASES:
        rows = []
        for jid in ids:
            jr = [r for r in runs if r["phase"] == name and r["journey"] == jid]
            secs = [r["sec"] for r in sorted(jr, key=lambda x: x["run_idx"]) if "sec" in r]
            n_error = sum(1 for r in jr if "error" in r)
            rb = rangers.get(f"{name}|{jid}", {})
            rows.append({
                "journey": jid, "domain": rb.get("domain"), "difficulty_tier": rb.get("tier"),
                "ranger": rb.get("sec"), "agg": _agg(secs), "runs": secs, "n_error": n_error,
            })
        rep = {"model": _MODEL, "k": k, "max_steps": max_steps, "permission_mode": perm,
               "phase": name, "journey_ids": ids, "results": rows}
        with open(os.path.join(_OUT_DIR, f"{name}.json"), "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())
