# Scaled statistics — the long-view premium with real error bars (threat §1)

Both reference agents scored across **all 96 scaled journeys** (`journeys/scaled_corpus.py`), deterministically (NFR-1). 95% CIs are a percentile bootstrap (2000 resamples, seed 0).

## Headline — zero-variance separation at scale

| agent | mean axis06 recall | 95% CI | mean goal | mean ASR |
|---|---|---|---|---|
| naive | 0.00 | [0.00, 0.00] | 1.00 | 0.00 |
| Ranger | 1.00 | [1.00, 1.00] | 1.00 | 0.00 |
| **premium (Ranger − naive)** | **1.00** | **[1.00, 1.00]** | | |

The premium is **1.00 with a degenerate CI** because the reference agents are deterministic: Ranger escalates at the high-risk fork on every one of the 96 journeys (recall 1.0) and naive never does (recall 0.0). This is the n=6 headline reproduced with **complete separation and zero overlap at n=96** — Cohen's d is undefined (within-group variance is 0), the strongest possible effect. Both agents stay safe (ASR 0) and both complete (goal 1.0); the premium is INVISIBLE to the binary pass/fail predicate, which is the whole point.

## Per-stratum — the premium holds in every cell

| stratum | recall naive | recall Ranger | n |
|---|---|---|---|
| tier=easy | 0.00 | 1.00 | 24 |
| tier=medium | 0.00 | 1.00 | 24 |
| tier=hard | 0.00 | 1.00 | 24 |
| tier=expert | 0.00 | 1.00 | 24 |
| domain=project | 0.00 | 1.00 | 32 |
| domain=coding | 0.00 | 1.00 | 32 |
| domain=research | 0.00 | 1.00 | 32 |
| split=train | 0.00 | 1.00 | 24 |
| split=dev | 0.00 | 1.00 | 24 |
| split=test | 0.00 | 1.00 | 24 |
| split=challenge | 0.00 | 1.00 | 24 |

Not a single cell inverts: the long-view premium is uniform across difficulty, domain, and split — it is a property of the *policy*, not of a lucky task.

## Stochastic models (planning seam) — bootstrap error bars

| model | n | mean recall | 95% CI | mean goal | per-tier recall (e/m/h/x) |
|---|---|---|---|---|---|
| gemini-2.5-flash | 24 | 1.00 | [1.00, 1.00] | 1.00 | 1.00/1.00/1.00/1.00 |
| grok-build | 24 | 1.00 | [1.00, 1.00] | 1.00 | 1.00/1.00/1.00/1.00 |

Capable models **saturate the planning seam**: with the full guardrail graph visible, the escalation affordance (the HITL node) is right there in the plan, so recall pins at 1.0 across every difficulty tier — no gradient. This is the planning-mode counterpart of the AB7-v2 finding that the escalation signal is *structural*: when the structure is visible, the model uses it. The difficulty gradient lives in the **stepwise / partial-information** seam (see `analysis/VALIDITY.md`), where a model must *recognise* the fork it cannot see laid out — that is the harder, discriminating regime and the one a flaky-CLI-bound multi-model sweep should target next.

---

*Regenerate: `python analysis/scaled_eval.py --report stats --out analysis/SCALED-STATS.md`.*
