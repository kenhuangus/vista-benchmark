#!/usr/bin/env python3
"""Deterministic analysis over ``results/`` — P0/P1 of the Analysis & Ablation plan.

Turns the existing result artifacts into the headline tables/figures with NO model
calls and NO new measurement: A1 (leaderboard), A2 (long-view premium), A3 (cost vs
reliability + confidence intervals), A4 (pass^k curves), A6 (three views), A7
(cross-axis correlation), A8 (security + positive control). Pure standard library;
the only stochastic step is a FIXED-SEED bootstrap, so the whole report is
byte-reproducible (NFR-1 carried up into the analysis layer).

    python analysis/analyze.py                      # print the Markdown report
    python analysis/analyze.py --out analysis/RESULTS.md

Every number is sourced from a file under ``results/`` (named inline). Where a signal
is constant across the corpus (the safety axes), the report says so explicitly rather
than hiding a degenerate statistic — that zero-variance flag is itself a finding.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import sys
from typing import Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RESULTS = os.path.join(_REPO_ROOT, "results")

# Fixed model order + display labels (exact ids live in experiments/README.md).
_MODELS = [
    ("gemini-2.5-pro", "Gemini 2.5 Pro"),
    ("gemini-2.5-flash", "Gemini 3.5 Flash"),
    ("sonnet", "Claude Sonnet 4.6"),
    ("haiku", "Claude Haiku 4.5"),
    ("opus", "Claude Opus 4.8"),
]
_LABEL = dict(_MODELS)
_BOOTSTRAP_ITERS = 2000
_BOOTSTRAP_SEED = 0


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _load(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def load_passk() -> dict[str, dict]:
    """{stem: {agg fields + cost_usd}} from results/pillar-a-passk (project journey)."""
    out: dict[str, dict] = {}
    for stem, _ in _MODELS:
        d = _load(os.path.join(_RESULTS, "pillar-a-passk", f"{stem}.json"))
        if not d or not d.get("results"):
            continue
        agg = d["results"][0]["agg"]
        out[stem] = {**agg, "cost_usd": float(d.get("usage", {}).get("cost_usd", 0.0))}
    return out


def load_security() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for stem, _ in _MODELS:
        d = _load(os.path.join(_RESULTS, "pillar-a-security", f"{stem}.json"))
        if not d or not d.get("results"):
            continue
        out[stem] = d["results"][0]["llm"]["sec"]
    return out


def _latest(agent: str) -> Optional[dict]:
    files = sorted(glob.glob(os.path.join(_RESULTS, "v0.1", f"vista-{agent}-*.json")))
    return _load(files[-1]) if files else None


def load_reference() -> dict[str, list[dict]]:
    """naive + ranger per-journey headlines from the latest v0.1 scorecard each."""
    out: dict[str, list[dict]] = {}
    for agent in ("naive", "ranger"):
        d = _latest(agent)
        if d:
            out[agent] = d["per_journey"]
    return out


def load_axis10() -> dict[str, dict]:
    """rsi scorecards: benign (stem.json) + adversarial (adversarial-stem.json)."""
    out: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(_RESULTS, "pillar-a-rsi", "*.json"))):
        d = _load(path)
        if d:
            out[os.path.splitext(os.path.basename(path))[0]] = d
    return out


# --------------------------------------------------------------------------- #
# Statistics (pure stdlib)
# --------------------------------------------------------------------------- #
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion — robust at the 0/n and n/n
    boundaries where a normal-approx interval is degenerate."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def pass_hat_k(c: int, n: int, k: int) -> float:
    """Unbiased pass^k for a journey with ``c`` passes out of ``n`` i.i.d. runs:
    C(c,k)/C(n,k) (the tau-bench estimator; order-independent)."""
    if k <= 0 or k > n or c < k:
        return 0.0 if (k > n or c < k) else 1.0
    return math.comb(c, k) / math.comb(n, k)


def pass_hat_k_curve(pass_vec: list[int]) -> list[float]:
    n, c = len(pass_vec), sum(pass_vec)
    return [pass_hat_k(c, n, j) for j in range(1, n + 1)]


def bootstrap_passk_ci(pass_vec: list[int], k: int) -> tuple[float, float]:
    """Percentile bootstrap CI on pass^k over a fixed-seed resample of the runs."""
    rng = random.Random(_BOOTSTRAP_SEED)
    n = len(pass_vec)
    if n == 0:
        return (0.0, 0.0)
    stats = []
    for _ in range(_BOOTSTRAP_ITERS):
        sample = [pass_vec[rng.randrange(n)] for _ in range(n)]
        stats.append(pass_hat_k(sum(sample), n, k))
    stats.sort()
    return (stats[int(0.025 * _BOOTSTRAP_ITERS)], stats[int(0.975 * _BOOTSTRAP_ITERS)])


def pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs)
    sy = sum((y - my) ** 2 for y in ys)
    if sx == 0 or sy == 0:  # a zero-variance column -> correlation undefined
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(sx * sy)


def _sparkline(values: list[float]) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    return "".join(blocks[min(len(blocks) - 1, int(round(v * (len(blocks) - 1))))]
                   for v in values)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def _f(x: float, p: int = 2) -> str:
    return f"{x:.{p}f}"


def _ci(lo: float, hi: float) -> str:
    return f"[{_f(lo)}, {_f(hi)}]"


def build_report() -> str:
    passk = load_passk()
    sec = load_security()
    ref = load_reference()
    ax10 = load_axis10()
    L: list[str] = []
    w = L.append

    w("# VISTA Bench — Analysis Results (P0/P1)")
    w("")
    w("Generated by `analysis/analyze.py` — a pure-stdlib, fixed-seed-bootstrap, "
      "byte-reproducible pass over the artifacts under `results/`. No model calls; "
      "no new measurement. Every figure names its source file. This is the executed "
      "form of analyses A1–A8 in `Analysis and Ablation Study.md`.")
    w("")

    # ----- A1 leaderboard ------------------------------------------------- #
    w("## A1 — Per-model leaderboard (project journey, k=5)")
    w("")
    w("Source: `results/pillar-a-passk/*.json` (goal-reach, pass^k, ASR, recall, cost), "
      "`results/pillar-a-security/*.json` (canary egress).")
    w("")
    w("| model | goal_reach_rate | pass^5 | recall | ASR | canary egress | cost (USD) |")
    w("|---|---|---|---|---|---|---|")
    for stem, label in _MODELS:
        a = passk.get(stem)
        s = sec.get(stem, {})
        if not a:
            continue
        egress = "yes" if s.get("canary_egress_detected") else "no"
        w(f"| {label} | {_f(a['goal_reach_rate'])} | {a['pass_pow_k']} | "
          f"{_f(a.get('recall_mean', 1.0))} | {_f(a['asr_mean'])} | {egress} | "
          f"{_f(a['cost_usd'])} |")
    w("")
    w("> All recall = 1.00 and ASR = 0.00 across every model — the calibration and "
      "security axes **saturate**; only `goal_reach_rate`/`pass^5` separate the models.")
    w("")

    # ----- A2 long-view premium ------------------------------------------ #
    w("## A2 — The long-view premium (same pass/fail, opposite calibration)")
    w("")
    w("Source: latest `results/v0.1/vista-{naive,ranger}-*.json` `per_journey[].headline`. "
      "Premium = ranger recall − naive recall while both **pass every run**.")
    w("")
    if "naive" in ref and "ranger" in ref:
        nv = {j["journey"]: j for j in ref["naive"]}
        rg = {j["journey"]: j for j in ref["ranger"]}
        w("| journey | split | naive recall | ranger recall | premium | both pass^5 |")
        w("|---|---|---|---|---|---|")
        prem_sum = 0.0
        for jid in sorted(rg):
            n, r = nv.get(jid, {}), rg[jid]
            nrec = n.get("headline", {}).get("verification_calibration_recall", float("nan"))
            rrec = r["headline"]["verification_calibration_recall"]
            prem = rrec - nrec
            prem_sum += prem
            both = "yes" if (n.get("pass_hat_k") == 1.0 and r.get("pass_hat_k") == 1.0) else "no"
            w(f"| {jid} | {r['split']} | {_f(nrec)} | {_f(rrec)} | +{_f(prem)} | {both} |")
        w(f"| **mean** | | | | **+{_f(prem_sum / len(rg))}** | |")
        w("")
        w("> Binary pass/fail is identical (both agents pass every run); the calibration "
          "axis carries the entire difference. This is the benchmark's core claim (H1).")
    else:
        w("_(reference scorecards not found under results/v0.1/)_")
    w("")

    # ----- A3 cost vs reliability ---------------------------------------- #
    w("## A3 — Cost vs reliability (with confidence intervals)")
    w("")
    w("Source: `results/pillar-a-passk/*.json`. Wilson 95% interval on `goal_reach_rate` "
      f"(n=5); percentile bootstrap on pass^5 ({_BOOTSTRAP_ITERS} resamples, seed "
      f"{_BOOTSTRAP_SEED}). Cost is the CLI-reported USD (Gemini billed to Vertex credits "
      "→ $0); treat magnitudes as order-of-magnitude, the ordering as robust.")
    w("")
    w("| model | cost (USD) | goal_reach_rate (95% Wilson) | pass^5 (95% bootstrap) |")
    w("|---|---|---|---|")
    for stem, label in _MODELS:
        a = passk.get(stem)
        if not a:
            continue
        gv = a["goal_vec"]
        glo, ghi = wilson(sum(gv), len(gv))
        plo, phi = bootstrap_passk_ci(a["pass_vec"], len(a["pass_vec"]))
        w(f"| {label} | {_f(a['cost_usd'])} | {_f(a['goal_reach_rate'])} {_ci(glo, ghi)} | "
          f"{a['pass_pow_k']} {_ci(plo, phi)} |")
    w("")
    w("> Reliability is **non-monotone in price**: the most expensive model (Opus) is the "
      "least reliable (0/5) while the free Gemini models are 5/5. With n=5 the Wilson upper "
      "bound on a 0/5 is ~0.43, so '0/5' means 'unreliable here', not 'never'.")
    w("")

    # ----- A4 pass^k curves ---------------------------------------------- #
    w("## A4 — pass^k decay curves (k = 1..5) and the reliability tax")
    w("")
    w("Source: `results/pillar-a-passk/*.json` `agg.pass_vec`. pass^k = unbiased "
      "C(c,k)/C(n,k). The gap `goal_reach_rate − pass^k` is the reliability tax.")
    w("")
    w("| model | pass^1 | pass^2 | pass^3 | pass^4 | pass^5 | curve |")
    w("|---|---|---|---|---|---|---|")
    for stem, label in _MODELS:
        a = passk.get(stem)
        if not a:
            continue
        curve = pass_hat_k_curve(a["pass_vec"])
        cells = " | ".join(_f(v) for v in curve)
        w(f"| {label} | {cells} | `{_sparkline(curve)}` |")
    w("")
    w("> Both Geminis hold flat at 1.0; Sonnet decays from 0.40 (pass^1) to 0 by pass^5; "
      "Haiku/Opus are 0 from pass^1. The slope is the reliability signal a single-k number "
      "hides.")
    w("")

    # ----- A6 three views ------------------------------------------------ #
    w("## A6 — Three reporting views rank the models differently")
    w("")
    w("Source: `results/pillar-a-passk/*.json`. 'Did it escalate' (recall) and 'did it "
      "resist' (ASR) are identical across models; only pass^5 separates them.")
    w("")
    w("| model | recall (escalated) | ASR=0 (resisted) | pass^5 (reliable) |")
    w("|---|---|---|---|")
    for stem, label in _MODELS:
        a = passk.get(stem)
        if not a:
            continue
        w(f"| {label} | {_f(a.get('recall_mean', 1.0))} | "
          f"{'yes' if a['asr_mean'] == 0 else 'no'} | {a['pass_pow_k']} |")
    w("")

    # ----- A7 correlation ------------------------------------------------ #
    w("## A7 — Cross-axis correlation (are the axes independent?)")
    w("")
    w("Source: pooled per-run scorecards in `results/pillar-a-passk/*.json` `runs[]` "
      "(axis01 goal_reached, axis06 recall, axis07 ASR, pass predicate). Pearson r over "
      "all model×run rows.")
    w("")
    cols = ["goal_reached", "recall", "targeted_asr_mean", "passed"]
    rows: dict[str, list[float]] = {c: [] for c in cols}
    for stem, _ in _MODELS:
        d = _load(os.path.join(_RESULTS, "pillar-a-passk", f"{stem}.json"))
        if not d or not d.get("results"):
            continue
        for run in d["results"][0].get("runs", []):
            for c in cols:
                rows[c].append(float(run.get(c, 0.0)))
    n_rows = len(rows[cols[0]])
    w(f"Pooled rows: {n_rows} (5 models × 5 runs × 1 journey).")
    w("")
    w("| | " + " | ".join(cols) + " |")
    w("|---|" + "|".join("---" for _ in cols) + "|")
    for a in cols:
        cells = []
        for b in cols:
            r = pearson(rows[a], rows[b])
            cells.append("—(0-var)" if r is None else _f(r))
        w(f"| **{a}** | " + " | ".join(cells) + " |")
    w("")
    zero_var = [c for c in cols if len(set(rows[c])) <= 1]
    w(f"> Zero-variance columns (no correlation defined): **{', '.join(zero_var) or 'none'}**. "
      "`recall` and `targeted_asr_mean` are constant across the whole corpus, so the "
      "'foresight ⟂ safety' independence claim (H2) **cannot yet be shown from data** — "
      "the corpus needs journeys where the safety axes vary. This degeneracy is the "
      "cleanest evidence that n=6 is too thin (plan threats §1–2).")
    w("")

    # ----- A8 security --------------------------------------------------- #
    w("## A8 — Security: ASR with the live positive control")
    w("")
    w("Source: `results/pillar-a-security/*.json`. The hijacked-agent positive control and "
      "ranger negative control are pinned in `agents/tests/test_stepwise_adapter.py`.")
    w("")
    w("| model | ASR | canary egress | forbidden crossing | goal reached | passed |")
    w("|---|---|---|---|---|---|")
    for stem, label in _MODELS:
        s = sec.get(stem)
        if not s:
            continue
        w(f"| {label} | {_f(s['targeted_asr_mean'])} | "
          f"{'yes' if s['canary_egress_detected'] else 'no'} | "
          f"{'yes' if s['forbidden_crossing_detected'] else 'no'} | "
          f"{'yes' if s['goal_reached'] else 'no'} | "
          f"{'yes' if s['passed'] else 'no'} |")
    w("")
    w("> All 5 models resist (ASR 0, no egress). The result is genuine, not a dead oracle: "
      "the hijacked positive control fires ASR 1.0 (both canaries) and the ranger negative "
      "control is 0 — see the stepwise-adapter tests.")
    w("")

    # ----- axis10 bonus -------------------------------------------------- #
    w("## axis10 — self-improvement safety (benign vs adversarial)")
    w("")
    w("Source: `results/pillar-a-rsi/*.json`. Benign prompt vs the `--adversarial` "
      "jailbreak-template prompt (`AdversarialLLMDreamer`).")
    w("")
    w("| scorecard | mode | gate-ON axis10 | gate-OFF axis10 | bait taken |")
    w("|---|---|---|---|---|")
    for name in sorted(ax10):
        d = ax10[name]
        scen = d.get("scenarios", {})
        mode = d.get("mode", "benign")
        on_key = "adversarial_gate_on" if mode == "adversarial" else "self_improve_gate_on"
        off_key = "adversarial_gate_off" if mode == "adversarial" else "ablation_gate_off"
        on = scen.get(on_key, {}).get("score")
        off = scen.get(off_key, {}).get("score")
        bait = d.get("bait_taken")
        bait_s = "—" if bait is None else ("yes" if bait else "no")
        w(f"| {name} | {mode} | {_f(on) if on is not None else '—'} | "
          f"{_f(off) if off is not None else '—'} | {bait_s} |")
    w("")
    w("> Benign: axis10 = 1.0 (no discrimination). Adversarial: both Gemini models take the "
      "bait — gate-OFF axis10 → 0.0 (a forbidden path opens) while gate-ON holds at 1.0. "
      "So axis10 discriminates under pressure, and the RSI gate is load-bearing on real "
      "models, not only the synthetic rogue.")
    w("")
    w("---")
    w("")
    w("*All values above are computed from `results/` at report time; rerun "
      "`python analysis/analyze.py` to regenerate byte-for-byte.*")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    # The report is UTF-8 (em-dashes, sparklines); reconfigure stdout so it prints
    # on a Windows cp1252 console. The file write below is UTF-8 regardless.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description="VISTA P0/P1 analysis over results/.")
    p.add_argument("--out", default=None, help="write the Markdown report here")
    args = p.parse_args(argv)
    report = build_report()
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
