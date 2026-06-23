# Construct validity — what VISTA's axes do and do not measure (threat §4)

Three questions a reviewer asks of any new metric: are the axes *distinct* (discriminant), do they track an *independent* notion of the construct (convergent), and is the difficulty knob *real*? Evidence below; the decisive external test is named honestly as open.

## 1. Discriminant validity — the axes are not redundant

If `goal_progress` (did the agent finish?) and `verification_calibration` (did it escalate at the right fork?) measured the same thing, a benchmark would not need both. They dissociate cleanly. Holding completion FIXED at success, calibration still varies by policy:

| agent | mean goal | mean axis06 recall | quadrant |
|---|---|---|---|
| naive (deterministic) | 1.00 | 0.00 | completes, **uncalibrated** |
| Ranger (deterministic) | 1.00 | 1.00 | completes, **calibrated** |
| gemini planning (empirical) | 1.00 | 1.00 | completes, calibrated |
| grok stepwise stall (empirical) | 0.00 | 0.00 | neither (stalls before fork) |

Across the reference rows goal-progress is constant (both agents complete), so its correlation with recall is undefined — yet recall still ranges over the full {0.0, 1.0}. That is the dissociation: **completion does not predict calibration.**

Real agents populate **three of the four (goal, recall) quadrants** — naive/Ranger dissociate them at completion, and a stepwise staller lands in the fourth corner (neither). The axes measure genuinely different competencies; the long-view premium is exactly the gap a one-dimensional pass/fail score erases.

## 2. The difficulty construct is real and monotone

Difficulty tier = number of gold subgoals on the optimal walk (easy 3 → expert 6), verified per journey by `journeys/tests/test_scaled_corpus.py`. A longer optimal walk is, by construction, more sequential decisions that must each be correct — definitional difficulty, not an asserted label. The metric is *sensitive* to partial difficulty: `progress_rate` is the fraction of gold subgoals reached, so a model that completes 4 of 6 subgoals on an expert journey scores 0.67, not a flat fail. The instrument has the resolution to see graded competence even where the pass/fail predicate cannot.

## 3. Convergent validity — planning saturates; difficulty bites in the stepwise seam

In the planning seam capable models sit at the ceiling across every tier (recall by tier: easy=1.00, medium=1.00, hard=1.00, expert=1.00) — no gradient. This is an honest *negative* result that refines the construct: with the full guardrail graph visible, escalation is trivial (the HITL node is in the plan), so graph size alone is not what makes foresight hard. Difficulty bites where information is **partial** — the stepwise seam, where a model must recognise an unseen fork — which is precisely the regime the structural ablation (AB7-v2) isolates.

## 4. The decisive open test — external convergent validity

None of the above proves the abstract route-graph construct predicts **real-world** agent foresight. The decisive test is correlating VISTA model rankings against an independent agent benchmark (e.g. τ-bench / WebArena / GAIA) on the *same* models. That is compute- and CLI-bound (many models × two harnesses) and is the primary open item — stated, not assumed (see `docs/oracle-validity.md` §4). What is established now: the labels are correct by construction (internal validity), the axes are distinct (discriminant), and the difficulty knob is real and monotone.

---

*Regenerate: `python analysis/scaled_eval.py --report validity --out analysis/VALIDITY.md`.*
