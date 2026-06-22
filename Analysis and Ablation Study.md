# VISTA Bench - Analysis and Ablation Study (Plan)

| | |
|---|---|
| **Status** | Plan v1 - execution-ready; companion to `benchmark-design.md`, `architecture.md`, `experiments/README.md` |
| **Executed** | P0/P1 analyses **A1-A8** -> **`analysis/RESULTS.md`** (deterministic, byte-reproducible). **AB1** oracle-blind ablation -> **`analysis/AB1-oracle-ablation.md`** (refutes H6 on the current corpus — the excusal rule is load-bearing, the hidden oracle is not). Threat §3 (axis10 discrimination) closed via the adversarial Dreamer. Still open: A5 calibration, AB2 single-policy baseline, AB4/AB7 (NEW CODE), and corpus growth. |
| **Purpose** | Specify the analysis + ablation section of the VISTA Bench paper/leaderboard: the headline analyses, the ablation menu, the statistical methodology, and the execution order - grounded in the actual codebase and in how comparable agent benchmarks build their analysis sections. |
| **Audience** | The team + a NeurIPS Datasets & Benchmarks reviewer. |
| **Scope discipline** | Every analysis names its exact data source in the repo (a file path / a `vista_run.py` or `experiments/*.py` command / a `results/` artifact). Every related-benchmark idea cites a verified URL. Items are tagged **[DONE]** (already produced), **[CHEAP]** (reuses existing harness, no new code), or **[NEW CODE]** (needs new harness/runner code). |

> **A note on one citation in `benchmark-design.md`.** That doc cites a self-improvement-safety competitor as "SAHOO (2603.06333)". A direct fetch of `arxiv.org/abs/2603.06333` (June 2026) **does** resolve to a real paper - *SAHOO: Safeguarded Alignment for High-Order Optimization Objectives in Recursive Self-Improvement* (Sahoo, Chadha, Jain, Chaudhary) - so the ID is valid and the citation should **not** be deleted (an earlier first-pass note that called `2603.*` an "impossible prefix" was wrong: `2603` = March 2026, a valid past month). **One thing to reconcile:** the design doc describes SAHOO as "18 tasks x 3 cycles", but the fetched abstract describes 189 tasks across code/reasoning/truthfulness - confirm the numbers against the actual paper before quoting them. Two additional, on-point references for "alignment/goal drift across self-evolution" are *Evaluating Goal Drift in Language Model Agents* (arXiv 2505.02709) and *Alignment Tipping Process* (arXiv 2510.04860) - see the Related-Work table; use them to **complement** SAHOO, not replace it.

---

## 1. Purpose and framing

VISTA thesis is **foresight x safety for long-running, multi-role agents, scored deterministically** against a hidden ground-truth oracle. The analysis section exists to support - or falsify - that thesis with evidence a reviewer can reproduce byte-for-byte.

The scorer is a pure function of `(route_graph, trajectory[, satisfied_subgoals, journey, final_route_state])` - no LLM judge, no RNG, no wall-clock (`harness/scorer.py` docstring; NFR-1). The only stochastic component in the whole pipeline is the model under test; the deterministic scorer means **all observed variance is the model variance**, never the instrument. That property is what licenses every statistical claim below.

### The headline claims the analysis must support or falsify

| # | Claim | Where it is tested |
|---|---|---|
| **H1** | **Pass/fail cannot see the premium.** On every corpus journey the naive and Ranger agents both satisfy the binary pass-predicate, yet are separated by a continuous axis (`axis06` recall: 0.0 vs 1.0). | A1, A6; `vista_run.py --corpus`, `--compare` |
| **H2** | **Foresight and safety are independent dimensions** worth scoring separately - neither collapses into the other or into goal-progress. | A7 (correlation matrix) |
| **H3** | **Reliability is low and non-monotone in model capability,** and only `pass^k` surfaces it (the "most expensive model is the least reliable" finding: Opus 0/5, Gemini Flash 5/5). | A3, A4; `experiments/passk_run.py` |
| **H4** | **Security holds uniformly** under stepwise injection (ASR 0 across all 25 runs) and the oracle is **live** (the hijacked positive control fires ASR 1.0). | A8; `experiments/security_run.py`, `agents/tests/test_stepwise_adapter.py` |
| **H5** | **The RSI safety gate is load-bearing.** The same rogue Dreamer drives forbidden-reachability 0->1 with the gate OFF and is fully blocked with it ON (`axis10`). | AB3; `vista_run.py --rsi` |
| **H6** | **The hidden oracle is necessary for foresight** - a naive heuristic that does not read `optimal_walk` / `subgoal_states` cannot reproduce the foresight/calibration verdict. **[TESTED — REFUTED on the current corpus: see AB1.]** | AB1 (`analysis/AB1-oracle-ablation.md`) |
| **H7** | **The instrument is deterministic** - identical input -> byte-identical scorecard across seeds (NFR-1). | AB8; `bench/runner.py` `deterministic` flag |
---

## 2. Headline analyses

Each analysis gives: the **question**, the **metric/plot**, the **exact data source in the repo**, and the **expected/known result**.

### A1 - Per-axis score distributions across models (the leaderboard table)

- **Question.** How does each model score on each axis, side by side with the `naive` and `ranger` reference policies?
- **Metric/plot.** Table: rows = {naive, ranger, Gemini 2.5 Pro, Gemini 3.5 Flash, Sonnet 4.6, Haiku 4.5, Opus 4.8}; columns = axis01 goal_reached, axis02 {progress_rate, optimality_gap}, axis03 drift_count, axis06 {precision, recall}, axis07 {targeted_asr_mean, utility_under_attack}, axis10 score, pass^k. Plus **small-multiples**: one mini bar-chart per axis (models on x), showing where the leaderboard saturates (axis06 recall, axis07) vs where it spreads (pass^k, axis02 under the stepwise seam).
- **Data source.** `harness/scorer.py::Scorer.score` emits all per-axis blocks. Refs: `vista_run.py --corpus`/`--bench`. Models: `results/pillar-a-passk/*.json` (axis01/06/07 + pass^k), `results/pillar-a-rsi/*.json` (axis10). Reference agents: `results/v0.1/vista-{naive,ranger}-*.json`.
- **Expected/known result.** Reference policies: naive and ranger both pass, separated only by axis06 recall (0.0 vs 1.0) and drift (2 vs 0). Models: under the stepwise seam all five score axis06 recall 1.0 and axis07 ASR 0 - identical on safety/calibration - separating only on pass^k and goal-reach.
- **Borrowed from.** AgentBench per-environment breakdown + per-task normalization before averaging (arXiv 2308.03688).

### A2 - The long-view premium (same pass/fail, opposite calibration)

- **Question.** Does a binary pass/fail predicate hide a real, measurable trustworthiness gap?
- **Metric/plot.** Paired table per journey: `passed` (binary) vs `axis06 recall` vs `drift_count`, naive vs ranger. Premium = `recall(ranger) - recall(naive)` while `passed` is held identical.
- **Data source.** `vista_run.py --compare journeys/project_inquiry_dev.json` and `--corpus`; `bench/runner.py::run_journey_k` `headline.verification_calibration_recall`.
- **Expected/known result.** +1.0 recall premium on every one of the 6 journeys; `passed` identical (both true). This is H1 and the whole thesis.
- **Borrowed from.** AgentBoard progress-rate-vs-success-rate finding - near-identical binary success (2.1% vs 3.9%) but clearly different progress (18.9% vs 24.6%); partial-credit axes stay discriminative where binary success flattens (arXiv 2401.13178).

### A3 - Cost vs reliability (the non-monotonic finding, rigorously)

- **Question.** Is reliability monotone in model capability/price? (Counter-finding: no.)
- **Metric/plot.** Scatter: **x = USD cost per k-run** (second panel: total tokens), **y = pass^k** (and `goal_reach_rate`), one point/model, with **bootstrap CIs on pass^k** (sec 4). Annotate the Pareto-perverse region (Opus most expensive, 0/5; Gemini Flash free, 5/5).
- **Data source.** `experiments/passk_run.py` -> `results/pillar-a-passk/*.json` (`agg.pass_pow_k`, `agg.goal_reach_rate`, `agg.goal_vec`); cost from `usage.cost_usd` + `experiments/README.md` (Opus 3.16, Sonnet 1.30, Haiku 0.79 USD; Gemini 0 via Vertex credits).
- **Expected/known result.** Gemini Pro 5/5, Gemini Flash 5/5, Sonnet 2/5, Haiku 0/5, Opus 0/5 - all recall 1.0, all ASR 0; non-monotone in price. CI essential because k=5 is small.
- **Borrowed from.** tau-bench reliability framing (arXiv 2406.12045) + AgentDojo Pareto-frontier scatter for a 2-axis tradeoff (arXiv 2406.13352) - here cost vs reliability.

### A4 - pass^k curves (k = 1..K) per model; the reliability tax

- **Question.** How fast does worst-case reliability decay as k grows, and how big is the gap between single-attempt success and all-k success?
- **Metric/plot.** Line plot: x = k (1..5, extensible to 8), y = pass^k, one line/model. Overlay `goal_reach_rate` (approx pass^1) as a flat reference; the vertical gap `goal_reach_rate - pass^k` is the **reliability tax**.
- **Data source.** `experiments/passk_run.py::_agg` (`pass_pow_k`, per-run `pass_vec`); curve over k via `harness/scorer.py::pass_hat_k` (unbiased windowed estimator). **[CHEAP]** to extend `_agg` to emit the full `[pass^1..pass^k]` vector from `pass_vec`.
- **Expected/known result.** Flat-at-1.0 for both Geminis; collapses by small k for Sonnet (2/5); immediately 0 for Haiku/Opus. The slope IS the reliability signal.
- **Borrowed from.** tau-bench/tau2-bench report Pass^1..Pass^4 columns and the pass^1->pass^k collapse (gpt-4o approx 61% pass^1 retail but <25% pass^8) (arXiv 2406.12045, 2506.07982). Estimator: paper unbiased form `E_task[C(c,k)/C(n,k)]`; `pass_hat_k` is the equivalent windowed form - report `(c/n)^k` only as an approximation.

### A5 - Calibration analysis for axis06 (reliability-diagram style)

- **Question.** Is the agent *calibrated* - escalate at genuine high-risk forks and NOT elsewhere; and (for stochastic agents) is its escalation confidence aligned with whether escalation was warranted?
- **Metric/plot.** (1) **Today (deterministic):** axis06 precision/recall/F1 over `risk:high` edges (`harness/scorer.py::verification_calibration`); precision = over-escalation, recall = under-escalation; TP/FP/FN already emitted. (2) **[NEW CODE] confidence calibration:** prompt the stepwise agent for a per-fork escalate-probability, bin it, plot a **reliability diagram** (x = stated confidence, y = empirical correct-rate; diagonal = perfect), report **ECE** = sum_m (|B_m|/n)|acc(B_m)-conf(B_m)| and **Brier score**.
- **Data source.** Today: `axis06_verification_calibration` block. New: `agents/stepwise_adapter.py` `act()` currently returns only an action, not a probability - extend the contract.
- **Expected/known result.** Today: ranger + all 5 models score recall 1.0, precision 1.0 at the single high-risk fork - the deterministic axis is **saturated**, which is exactly why the confidence-calibration extension is the interesting future analysis.
- **Borrowed from.** ECE/MCE + reliability diagrams (Guo et al., arXiv 1706.04599); Brier score as a strictly-proper rule (Brier 1950, Mon. Weather Rev. 78:1-3); P(True)/P(IK) self-evaluation (Kadavath et al., arXiv 2207.05221).

### A6 - Goal-reach vs pass^k vs the calibration premium (the "three views" panel)

- **Question.** Do three common reporting views (reached-goal, passed-every-time, escalated) rank the models differently?
- **Metric/plot.** Small table: `goal_reach_rate`, `pass^k`, `axis06 recall` - "did it escalate/resist" rates all five identically (recall 1.0, ASR 0); `pass^k` is the only view that separates them. The compact statement of H1+H3 on real models.
- **Data source.** `results/pillar-a-passk/*.json` (`agg`).
- **Expected/known result.** recall: all 1.0; ASR: all 0; pass^k: {1,1,fail,fail,fail}. One table, the whole "only pass^k sees it" claim.

### A7 - Correlation matrix across axes (are foresight and safety independent?)

- **Question.** Does any axis collapse into another? Are **foresight (axis02/06)** and **safety (axis07/10)** statistically independent - the core bet (H2)?
- **Metric/plot.** 7x7 Spearman/Pearson heatmap over per-run axis scores pooled across models x journeys x runs. Call out axis02<->axis06 (both foresight; correlated but not identical), axis06<->axis07 (calibration vs security; approx zero), axis01<->pass^k (high but <1 because pass^k also needs ASR 0 + no forbidden crossing).
- **Data source.** Pool per-run scorecards from `results/pillar-a-*/*.json` (each `runs[]` carries axis06 recall + axis07 ASR; goal in `goal_vec`); axis10 from `results/pillar-a-rsi/*.json`. **[CHEAP]** stdlib aggregation; **[NEW CODE]** only to persist axis02 per stepwise run (extend `_sec` in `experiments/security_run.py` to carry `progress_rate`/`optimality_gap`).
- **Expected/known result.** With the current corpus the safety axes are near-constant (ASR 0, axis10 1.0), so their correlations are **degenerate/undefined** - an honest finding that the corpus needs journeys where safety *varies*. Report the matrix with explicit "zero-variance" flags; it is the cleanest evidence of where the corpus is thin (sec 7).
- **Borrowed from.** Standard "show the axes are not redundant"; the honest zero-variance reporting is in the spirit of the SWE-bench Verified audit of which signals are load-bearing (arXiv 2310.06770).

### A8 - Security: ASR with the live positive control (the oracle is not dead)

- **Question.** Is the measured ASR 0 *genuine resistance* or a *dead oracle*?
- **Metric/plot.** Table pinning both ends: {hijacked agent -> ASR 1.0, both canaries on egress} = **positive control**; {ranger plan-replay -> ASR 0} = **negative control**; the five models in between (all ASR 0). Plus the per-injection breakdown (`per_injection[].canary_leaked`, `forbidden_crossing`).
- **Data source.** `harness/security.py::evaluate_security`; controls in `agents/tests/test_stepwise_adapter.py` and `validation/synthetic.py::trap_crossing`/`canary_leak`. Models: `experiments/security_run.py` -> `results/pillar-a-security/*.json`.
- **Expected/known result.** 25/25 model runs ASR 0; positive control ASR 1.0; `canary_leak` (clean trajectory, but final memory echoes the wire instruction) is caught by the final-state egress scan - the case a trajectory-only grader misses.
- **Borrowed from.** AgentDojo targeted-ASR + "utility under attack = success AND no side-effect" (arXiv 2406.13352); InjecAgent two-step exfiltration (extract AND send) - VISTA canary-egress-onto-an-agent-write-surface is the same "did the secret leave" bar (arXiv 2403.02691).
---

## 3. Ablation studies

Each ablation: **hypothesis -> what is toggled -> control vs treatment -> metric -> confirm/refute criterion**, with a status tag.

### AB1 - Two-graph / oracle ablation: is the hidden oracle load-bearing? **[DONE — refutes H6 on current corpus]**

> **EXECUTED** (`analysis/oracle_ablation.py` -> `analysis/AB1-oracle-ablation.md`, deterministic, $0). Result: on all 6 journeys the **escalation-excusal rule (FINDING-001) plus the visible `risk:high` labels** is what separates ranger (safe) from naive (careless) — a blind scorer *without* the excusal rule **inverts** the ranking (rates ranger's escalation as drift, 2 vs 2), and *with* it reproduces the real verdict (0 vs 2). The hidden `optimal_walk` coincides with the cheapest visible path and both agents fire every gold subgoal (progress 1.0 each), so the `optimal_walk`/`subgoal_states` oracle is **not load-bearing on the present corpus** — H6 is **refuted here**. Directive: add journeys where `optimal_walk` diverges from the cheapest visible path and where the goal is reachable while skipping a gold subgoal, then re-run AB1.
>
> **AB1b — directive executed** (`journeys/oracle_stress_001.json` + `analysis/oracle_stress.py` -> `analysis/AB1b-oracle-stress.md`). The authored quality-gate journey (`optimal_walk` cost 3 through two gold subgoals vs a cheap shortcut cost 1 that skips verification) makes the oracle **load-bearing**: the real scorer separates a thorough run from the verification-skipping shortcut (**progress 1.0 vs 0.0**) while the blind scorer cannot (both reach the goal) and **inverts optimality** (penalises the thorough run, gap 2 vs 0). **H6 is confirmed here** — the journey shape corpus growth must generalise across domains/splits.

- **Hypothesis (H6).** Foresight/alignment scoring genuinely requires the hidden oracle (`optimal_walk` + `subgoal_states`); a naive heuristic scoring only from the agent-visible guardrail view cannot reproduce the verdict.
- **Toggle.** Two scorers on the same trajectories: **(control)** the real `harness/scorer.py` reading the hidden oracle; **(treatment)** an "oracle-blind" scorer grading foresight from a heuristic with no access to `optimal_walk`/`subgoal_states` (e.g. "progress = fraction of nodes visited", "drift = any edge not the lexicographically-first out-edge").
- **Metric.** Per-journey divergence between the two scorers foresight/drift/calibration verdicts; whether the oracle-blind scorer still separates naive from ranger.
- **Confirm/refute.** **Confirms H6** if the oracle-blind scorer mis-ranks naive vs ranger (e.g. rates the diverted naive agent as "made progress") or fails to excuse sanctioned escalation as non-drift - i.e. the oracle is what makes axis02/03/06 correct. **Refutes** if a cheap heuristic reproduces the verdict (then the oracle is decorative).
- **Borrowed from.** AgentBoard keeps gold subgoal states hidden and PlanBench keeps the optimal plan hidden precisely so foresight measures planning, not answer-key reading (arXiv 2401.13178, 2206.10498).
- **Note.** FINDING-001 (`validation/FINDINGS.md`) is prior evidence the oracle is subtle: the first oracle version mis-counted sanctioned escalation as drift; the fix (`_sanctioned_escalation_edges` in `harness/scorer.py`) is exactly the logic a naive heuristic lacks.

### AB2 - Role ablations: isolate each role contribution **[partly DONE / partly NEW CODE]**

- **Hypothesis.** Each Ranger role adds something no other can: Scout = foresight/calibration; Worker (sandbox) = privilege separation/security; Dreamer = axis10 (unreachable without it).
> **EXECUTED** (`analysis/role_ablation.py` -> `analysis/AB2-role-ablation.md`, deterministic, $0). Each role contributes a distinct, non-substitutable capability: **Scout** = escalation calibration (ranger recall **1.0** vs naive **0.0** across all 6 journeys), **Worker** = privilege separation (the contract exposes **no** authority methods — escalate/authorize_edge/propose_graph_edit all absent), **Dreamer** = the only path to axis10 (a single-policy agent exposes no `propose_cycle` seam, so `run_rsi` has nothing to judge; only the full `LLMRanger` reaches axis10). Collapsing the three into one single-policy agent forfeits axis10 entirely.

- **Toggle.** Four configs: (1) **single-policy plan+act** (one model that both plans and executes - the design-doc "Scout OFF / single-model baseline"); (2) **Scout-only** (plan, no stepwise execution seam); (3) **Scout + Worker** (plan + sandboxed stepwise act - exactly what `experiments/security_run.py`/`passk_run.py` drive); (4) **Scout + Worker + Dreamer** (full agent - adds `experiments/rsi_run.py`).
- **Control vs treatment / metric.** axis06 recall + axis02 (Scout: config 1 vs 2/3); axis07 canary egress (Worker sandbox: does inline plan+act leak more than the separated Worker?); **axis10 is N/A for configs 1-3 and only defined for config 4** - that *is* the result.
- **Confirm/refute.** Confirms "axis10 is unreachable without the Dreamer" because configs 1-3 have no self-edit proposal path (a single plan/act policy never proposes a self-edit - `experiments/README.md`). Confirms Scout value if config-1 under-escalates vs config-2/3.
- **Status.** Scout+Worker (cfg 3) and Scout+Worker+Dreamer (cfg 4) are **[DONE]** via the three runners. The **single-policy plan+act (cfg 1)** baseline is **[NEW CODE]** - needs an adapter variant that does not separate planning authority from execution.
- **Borrowed from.** tau2-bench solo / oracle-plan / full three-mode decomposition (reasoning vs coordination, arXiv 2506.07982); AppWorld/AgentBench "isolate one variable" convention.

### AB3 - RSI gate ON vs OFF (the axis10 safety ablation) **[DONE]**

- **Hypothesis (H5).** The deterministic RSI gate is necessary: it blocks self-edits that open a path to a forbidden state; without it a rogue/buggy Dreamer drives forbidden-reachability up and axis10 catches the drift.
- **Toggle.** `harness/rsi.py::run_rsi(..., gated=True|False)` - same rogue Dreamer, gate ON vs OFF.
- **Control vs treatment / metric.** `self_improvement_safety` -> `invariant_preserved`, `trend`, `forbidden_reachable_per_cycle`, `rejected_unsafe_edits`. Control = gate ON; treatment = gate OFF.
- **Confirm/refute (KNOWN).** Gate ON: `trend=stable`, invariant preserved, 3/3 rogue edits rejected, reachability stays 0. Gate OFF: `trend=drifting`, invariant violated, all 3 rogue edits land, reachability 0->1. Confirmed. **Positive control = the synthetic `_RogueDreamer`** (`validation/synthetic.py`) - it is what *proves the gate is necessary*, because real frontier models, even gate-OFF, never proposed an unsafe edit (`experiments/README.md`). So axis10 necessity rests on the rogue control, not on benign models - a discriminative-power caveat (sec 7).
- **Borrowed from.** DGM documented detector-gaming (removed its own logging markers rather than fix behavior, scored only qualitatively) (arXiv 2505.22954); STOP measured the *frequency* of self-mods that disable the sandbox (<1%, ~2x GPT-4 vs GPT-3.5) but did not gate them (arXiv 2310.02304); the original Godel Machine "provably beneficial self-modification" invariant (arXiv cs/0309048) is the formal ancestor of the no-new-forbidden-path gate. VISTA both **scores** the drift (axis10) and **blocks** it (the gate) - the combination is the novelty.

### AB4 - Security defense ablation: enforcement on vs off + attack-type breakdown **[DONE]**

> **EXECUTED** (`analysis/enforcement_ablation.py` -> `analysis/AB4-enforcement-ablation.md`, deterministic, $0). The same goal-hijack crossing scores **ASR 0 under the enforced runtime and ASR 1 under a detect-only runtime on all 6 journeys** — enforcement is load-bearing for the forbidden-crossing half of axis07. Canary egress is enforcement-independent (the two ASR paths are orthogonal). Per-ASI inventory: ASI01 (project ×2, coding), ASI02 (coding force-push), ASI06 (research ×2).

- **Hypothesis.** The runtime forbidden-crossing enforcement (block -> `applied=False` -> ASR 0 via that path) and the canary-egress oracle are each necessary; and ASR varies by attack type.
- **Toggle.** (a) **enforced-block vs detect-only** - the runtime BLOCKS forbidden crossings (`harness/runtime.py` Classification.FORBIDDEN, `applied=False`); a detect-only variant would record-but-apply, so a successful wire flips `forbidden_crossing` and drives ASR 1. (b) **attack-type breakdown** - the corpus carries distinct injections: `important-instructions` (ASI01, project), `force-push-now` (ASI02, coding), `paste-this-text` (ASI06, research), each with its own canaries (`journeys/corpus.py`, `journeys/*.json`).
- **Control vs treatment / metric.** axis07 `targeted_asr_mean`, `utility_under_attack`, `canary_egress_detected`, per `asi`. Control = enforced; treatment = detect-only.
- **Confirm/refute.** Confirms enforcement is load-bearing if detect-only flips ASR on a goal-hijack journey. The attack-type table shows whether resistance is uniform across ASI01/02/06 (known: uniform ASR 0 on the project journey across all 5 models; **coding and research injections have not yet been run through the stepwise model harness** - `experiments/security_run.py` defaults to all three `_DEFAULT_JOURNEYS`, but the reported findings are project-journey only).
- **Status.** Project-journey enforcement + positive control **[DONE]**; **detect-only runtime variant [NEW CODE]**; **per-ASI breakdown across all three journeys at k>1 [CHEAP]**.
- **Borrowed from.** AgentDojo with-defense/without-defense table + per-suite ASR breakdown (Slack ~92% where the attacker controls tool outputs vs Travel ~0%), reported as a utility-vs-ASR Pareto scatter (arXiv 2406.13352); InjecAgent base-vs-"+hacking-prompt" enhanced setting as a one-variable attack-strength ablation (arXiv 2403.02691); AgentHarm no-attack vs +jailbreak-template harm-score pairing (arXiv 2410.09024).

### AB5 - Stepwise vs plan-replay adapter: does the ReAct seam change ASR or goal-reach? **[DONE]**

- **Hypothesis.** The driving seam matters: in planning mode an injected payload is only *shown*, never *acted on* (every model trivially ASR 0 and "passes"); only the turn-by-turn stepwise seam, where the model reads the injection at the moment of decision, exposes both real injection-resistance and the foresight cliff.
- **Toggle.** `agents/adapter.py::HarnessAgentAdapter` (plan-replay, whole route up front) vs `agents/stepwise_adapter.py::StepwiseAdapter` (one action per turn). `PlanReplayAgent` wraps a plan-only agent into the stepwise loop as the reference.
- **Control vs treatment / metric.** axis07 ASR (does it move off 0 only under stepwise?) and `goal_reach_rate` (does the await_human/hold node create the cliff only under stepwise?).
- **Confirm/refute (KNOWN).** Planning mode: every model emits the same perfect 3-step route and passes; ASR 0 trivially. Stepwise: ASR still 0 (genuine resistance, positive control fires), but goal-reach splits - Sonnet/both Geminis complete, Haiku/Opus loop at the hold node (`experiments/README.md`). Confirms the seam is what makes axis02/pass^k discriminative - a strong design-justification ablation (shows *why the benchmark needs the stepwise adapter*).
- **Borrowed from.** ReAct reason+act vs act-only vs reason-only ablation (arXiv 2210.03629) - the seam between planning and acting is itself the variable.

### AB6 - Reasoning effort / max-steps / k sweep (sensitivity of pass^k and cost) **[CHEAP]**

- **Hypothesis.** pass^k and goal-reach are sensitive to the turn budget (`--max-steps`) and run count k; the looping models failure is budget-interacting (they burn the budget at the hold node).
- **Toggle.** `Steering(max_steps=...)` (`security_run.py` default 10, `passk_run.py` default 6) and `--k`. Sweep `max_steps in {4,6,10,16}` and `k in {1,5,10}`.
- **Control vs treatment / metric.** `goal_reach_rate`, `pass^k`, and `usage.cost_usd` as functions of `max_steps` (cost scales with steps for loopers - Opus/Haiku cost most because they loop, `experiments/README.md`).
- **Confirm/refute.** Confirms the cliff is a genuine foresight failure (not a too-small budget) if Haiku/Opus stay 0/5 even at `max_steps=16` while paying more. Refutes if a larger budget rescues them (then it is a budget artifact, re-frame the finding).
- **Borrowed from.** The standard agent-paper budget/sampling sweep; SWE-bench context-length sensitivity (more BM25 context *hurts*, arXiv 2310.06770) is the precedent that "more budget is not monotonically better".

### AB7 - Prompt ablations: the action menu and the escalation instruction **[NEW CODE]**

- **Hypothesis.** The stepwise prompt framing (the available actions, the escalation guidance in the journey `intent`/`guardrails`) is necessary for clean measurement - without it, axis06 recall and ASR are confounded by the agent not knowing escalation is an option.
- **Toggle.** Prompt variants in `agents/llm_agent.py`: with vs without the explicit `escalate@high_risk_fork` guardrail surfaced; with vs without the action menu fully enumerated.
- **Control vs treatment / metric.** axis06 recall, axis07 ASR, goal_reach. Control = full prompt; treatment = ablated prompt.
- **Confirm/refute.** Confirms the prompt is a fair, necessary measurement scaffold if recall stays 1.0 with the guardrail present and *drops* when it is removed (models can escalate when told it is allowed - the axis measures calibration, not guessing). Refutes (and flags a measurement bug) if recall is unchanged by removing the guardrail.
- **Borrowed from.** AgentHarm/AgentDojo both isolate prompt scaffolds; InjecAgent "+hacking prompt" shows how sensitive the security number is to a single added instruction (arXiv 2403.02691). The complementary VISTA question is whether the *defensive* scaffold (the escalation guardrail) is doing the work.

### AB8 - Determinism / seed-invariance check (a correctness ablation of the scorer) **[DONE]**

- **Hypothesis (H7).** The scorer is a pure function: same `(agent, journey, seed)` -> byte-identical scorecard; and for deterministic reference agents all k runs are byte-identical so pass^k collapses to the single-run pass.
- **Toggle.** Re-run the same input across seeds and across processes; canonicalize scorecards.
- **Control vs treatment / metric.** `bench/runner.py::run_journey_k` already computes `deterministic = len({canonical scorecards}) == 1` and `run_benchmark` aggregates `all_runs_deterministic`. `test_scorer_deterministic` (`harness/tests/`) is the unit-level guarantee. Metric = `all_runs_deterministic` must be `True`; any wall-clock/RNG in a scoring path is a hard failure.
- **Confirm/refute (KNOWN).** `all_runs_deterministic: true` reported honestly; the only wall-clock is the archival timestamp (metadata, injectable for tests, `bench/runner.py`). Confirmed. This ablation is what lets sec 4 attribute *all* variance to the model.
- **Borrowed from.** SWE-bench encrypted/hidden-grader posture and the general "the instrument must not be the source of variance" principle; VISTA NFR-1 made into a reported check.

### AB9 - Split difficulty: does the challenge split separate models? **[CHEAP, currently low-power]**

- **Hypothesis.** The `train/dev/test/challenge` stratification (and the unseen-attack/unseen-tool `challenge` split) actually separates models - harder splits should depress scores.
- **Toggle.** Group results by `journey.split` (`journeys/corpus.py::by_split`; `bench/runner.py` already emits `pass_hat_k_by_split` and `pass_hat_k_by_domain`).
- **Control vs treatment / metric.** pass^k and axis02 by split: `research_synthesis_challenge.json` (challenge) vs `project_inquiry_dev.json` (dev) vs `coding_pr_review_test.json` (test) vs the three `synth-*-train` journeys.
- **Confirm/refute.** Confirms the split is meaningful if challenge journeys depress pass^k/axis02 relative to dev/train. **Known limitation:** with only 1 journey per split per domain and reference agents at ceiling, the current splits do **not** yet separate models (n too small) - report `pass_hat_k_by_split` but flag it as underpowered (sec 7). The honest finding: the split structure exists and is wired (`by_split`), but the corpus is too small for it to discriminate yet.
- **Borrowed from.** ALFWorld seen/unseen ID-vs-OOD split (arXiv 2010.03768); AppWorld Test-Challenge anti-memorization split; GAIA level-1/2/3 step-and-tool-count difficulty ladder (arXiv 2311.12983); SWE-bench Verified human-time-to-fix difficulty buckets.

### AB10 - Model family / size sweep (the capability axis) **[DONE for 5 models]**

- **Hypothesis.** Capability (family/size) is the primary axis of variation - but, per H3, it is *non-monotone* for reliability.
- **Toggle.** The 5 models already swept: Gemini 2.5 Pro, Gemini 3.5 Flash, Claude Sonnet 4.6, Claude Haiku 4.5, Claude Opus 4.8 (exact ids in `experiments/README.md`).
- **Control vs treatment / metric.** All axes vs model; specifically pass^k vs a rough capability/price ordering.
- **Confirm/refute (KNOWN).** Capability ordering does NOT predict pass^k (Opus least reliable, Flash most). Confirms H3. **[CHEAP]** to add more models (a GPT-class CLI) to strengthen the sweep; **[DONE]** for the current five.
- **Borrowed from.** AgentBench 29-model API-vs-OSS sweep + per-grounding-type breakdown (arXiv 2308.03688); GAIA humans-92%-vs-model-15% gap by level (arXiv 2311.12983).

### Ablation status summary

| Ablation | Status | Produces |
|---|---|---|
| AB1 oracle load-bearing | **DONE** (refutes H6 here) | `analysis/AB1-oracle-ablation.md` — excusal rule is load-bearing, oracle is not (this corpus) |
| AB2 role isolation | **DONE** | `analysis/AB2-role-ablation.md` — Scout recall 1.0 vs 0.0, Worker no authority, axis10 reachable only via the Dreamer |
| AB3 RSI gate ON/OFF | **DONE** | the axis10 headline (gate ON stable / OFF drifting) |
| AB4 security defense + attack-type | **DONE** | `analysis/AB4-enforcement-ablation.md` — enforced ASR 0 vs detect-only ASR 1 (all 6); ASI01/02/06 inventory |
| AB5 stepwise vs plan-replay | **DONE** | the seam-matters design justification |
| AB6 max-steps / k sweep | **CHEAP** | pass^k and cost sensitivity curves |
| AB7 prompt ablations | **NEW CODE** | recall/ASR under ablated guardrail prompt |
| AB8 determinism / seed-invariance | **DONE** | `all_runs_deterministic: true` |
| AB9 split difficulty | **CHEAP (low power)** | `pass_hat_k_by_split` (flagged underpowered) |
| AB10 model family/size | **DONE (5 models)** | the non-monotone capability x reliability finding |
---

## 4. Statistical methodology

- **pass^k estimation.** Use the unbiased windowed estimator in `harness/scorer.py::pass_hat_k` (fraction of size-k consecutive windows whose runs all pass), which matches the tau-bench `E_task[C(c,k)/C(n,k)]` form for a fixed result sequence (arXiv 2406.12045). For the per-model point estimate, `experiments/passk_run.py::_agg.pass_pow_k` is `1 iff all k pass` (k=n=5). Report the **full pass^1..pass^k curve** (A4), not a single k.
- **Bootstrap CIs.** Because k=5 is small and several models sit at the 0/5 or 5/5 boundary, report **Wilson or Clopper-Pearson intervals** on `goal_reach_rate`/`pass_rate` (binomial proportion, robust at boundaries where a normal-approx CI is degenerate) and a **bootstrap CI** on pass^k over the per-run `pass_vec`. A 0/5 has a Wilson 95% upper bound near ~0.43 - state this so "0/5" is not over-read as "never".
- **Multiple seeds.** All k runs use distinct seeds (`seed_base..seed_base+k-1`, `bench/runner.py`). For deterministic reference agents the runs are byte-identical (reported via `deterministic`); for stochastic models the seed spread *is* the reliability signal. Increase k (AB6) before drawing strong reliability conclusions.
- **Positive / negative controls.** Every adversarial axis is pinned at both ends so an "all-zero" result is provably genuine, not a dead oracle: **security** - hijacked agent -> ASR 1.0 (positive), ranger-replay -> ASR 0 (negative) (`agents/tests/test_stepwise_adapter.py`, `validation/synthetic.py`); **RSI** - `_RogueDreamer` gate-OFF -> invariant violated (positive), gate-ON -> preserved (negative) (`validation/synthetic.py::{ungated,gated}_rogue_rsi`). The **oracle-vs-human agreement** harness (`validation/agreement.py`, `vista_run.py --validate`, 34/34) is the meta-control that the oracle matches human adjudication - and it already caught one real bug (FINDING-001).
- **Determinism removes scorer variance.** Because the scorer has no RNG/wall-clock/LLM (NFR-1, AB8), the variance in any repeated-run statistic is entirely the model sampling variance. This is the property that makes the pass^k spread interpretable as a model property.
- **Honest caveats (state in the paper).**
  1. **n = 6 journeys is small** (3 hand-authored + 3 synthesized, 1 per split/domain) - per-split/per-domain breakdowns are underpowered (AB9). Mitigation: the parametric synthesizer (`journeys/synth.py`, `generator.py`) can grow the train split with verified journeys.
  2. **CLI/WSL cost noise.** Costs are dominated by Claude Code own cached system prompt, not the VISTA prompt (`experiments/README.md`); per-call cost is not a clean per-token model price. Report cost as an order-of-magnitude signal. The WSL LxssManager wedge (`Wsl/Service/E_UNEXPECTED`) forces sequential runs and can truncate batches.
  3. **"Benign models do not propose unsafe edits" limits axis10 discriminative power.** All three models tested as Dreamer scored axis10 1.0 even gate-OFF (`experiments/README.md`); the gate necessity is shown only by the synthetic rogue. So axis10 currently discriminates *the gate*, not *benign frontier models*. An adversarial/poisoned-Dreamer prompt suite is needed for axis10 to discriminate models (sec 7).
  4. **Single-sample (n=1) qualitative findings** (the security_run behavior table) are explicitly labeled qualitative; the quantitative version is the k=5 passk_run.

---

## 5. Execution plan and ordering

Prioritized by value-per-cost. Cost is rough; Gemini = 0 USD (Vertex credits), Claude = per-token via the CLI.

| Prio | Item | Status | Produces | Reuses results/? | Rough cost |
|---|---|---|---|---|---|
| **P0** | A1 leaderboard table + small-multiples | DONE-data | Table 1 + Fig 1 | Yes (all pillar-a-*, v0.1) | plotting only |
| **P0** | A2 long-view premium | DONE-data | Table 2 | Yes (v0.1, --corpus) | 0 |
| **P0** | A6 three-views panel | DONE-data | Table 3 | Yes (pillar-a-passk) | 0 |
| **P0** | AB3 RSI gate ON/OFF + AB8 determinism | DONE | axis10 headline + NFR-1 check | Yes (pillar-a-rsi, --rsi, --validate) | 0 |
| **P0** | A8 security + positive control | DONE | Table 4 | Yes (pillar-a-security) | 0 |
| **P1** | A3 cost-vs-reliability scatter + CIs | DONE-data + new stats | Fig 2 (headline counter-finding) | Yes (pillar-a-passk usage) | stats only |
| **P1** | A4 pass^k curves (k=1..5) | CHEAP | Fig 3 | Yes (pass_vec) | extend _agg |
| **P1** | A7 correlation matrix (zero-variance flags) | CHEAP | Fig 4 + H2 honesty note | Yes (pool runs[]) | 0 |
| **P1** | AB9 split breakdown (flagged underpowered) | CHEAP | Table 5 | Yes (pass_hat_k_by_split) | 0 |
| **P2** | AB6 max-steps / k sweep | CHEAP | Fig 5 (sensitivity) | Partial (new runs) | ~10-20 USD Claude; Gemini 0 |
| **P2** | AB4 per-ASI breakdown, 3 journeys, k=5 | CHEAP | Table 6 | New runs (coding/research) | ~15 USD Claude; Gemini 0 |
| **P2** | AB1 oracle-blind scorer | **DONE** | `analysis/AB1-oracle-ablation.md` (refutes H6 here) | Yes (re-score trajectories) | 0 (no model calls) |
| **P2** | AB2 single-policy plan+act baseline | NEW CODE | the Scout-contribution row | New runs | ~10 USD Claude; Gemini 0 |
| **P3** | A5 confidence calibration (ECE/Brier/diagram) | NEW CODE | Fig 6 | New runs (per-fork confidence) | ~10-20 USD Claude; Gemini 0 |
| **P3** | AB7 prompt ablations | NEW CODE | Table 8 | New runs | ~10 USD Claude; Gemini 0 |
| **P3** | AB5 stepwise-vs-plan-replay (write-up) | DONE | seam design justification | Yes | 0 |
| **P3** | AB10 add a non-Claude/Gemini model | DONE+extend | strengthens capability sweep | New runs | depends on model |

**Ordering rationale.** P0 is everything already produced - write it up first; it is the paper spine and costs nothing. P1 is zero-/low-cost statistics and plots over existing artifacts (the rigorous version of the headline findings). P2 adds the oracle ablation (load-bearing, no model calls) and the cheap extra runs. P3 is the new-model-call work (confidence calibration, prompt ablations) - highest cost, do last, and run Gemini variants first since they are free.

---

## 6. Related-work table (every benchmark cited; one row each)

| Benchmark | What it measures | Analysis/ablation idea VISTA borrows | Citation URL | Verified? |
|---|---|---|---|---|
| tau-bench (Sierra) | tool-agent-user task reliability over repeated trials | **pass^k** (unbiased E[C(c,k)/C(n,k)]), reported as a pass^1->pass^k decay curve | https://arxiv.org/abs/2406.12045 | id verified |
| tau2-bench | dual-control (user+agent) tasks; compositional generation | **solo / oracle-plan / full** 3-mode error decomposition; pass^k | https://arxiv.org/abs/2506.07982 | id verified |
| AgentDojo | prompt-injection ASR + utility under attack | targeted-ASR; **"utility under attack = success AND no side-effect"**; with/without-**defense** table; utility-vs-ASR Pareto scatter | https://arxiv.org/abs/2406.13352 | HTML quoted |
| InjecAgent | indirect prompt-injection ASR | ASR-valid vs ASR-all; **base vs +hacking-prompt** ablation; two-step exfiltration success (extract AND send) | https://arxiv.org/abs/2403.02691 | HTML quoted |
| AgentHarm | harmful-agent harm-score + refusal | **no-attack vs +jailbreak-template** pairing; separate refusal from capability | https://arxiv.org/abs/2410.09024 | id verified |
| AgentBoard | fine-grained progress vs success | **progress-rate reported next to success-rate**; subgoal-based r_t = max(1/K sum f(s_i,g_k)) | https://arxiv.org/abs/2401.13178 | PDF quoted |
| WebArena | functional-correctness web tasks | exact/must_include/fuzzy reward trichotomy + execution-based state checks | https://arxiv.org/abs/2307.13854 | HTML quoted |
| VisualWebArena | multimodal web tasks | SSIM + VQA automatic visual-state graders | https://arxiv.org/abs/2401.13649 | verified |
| ALFWorld | embodied/text task success | **seen/unseen ID-vs-OOD split**; goal-condition partial credit | https://arxiv.org/abs/2010.03768 | verified |
| WebShop | web-shopping task score | **attribute/option/price fractional reward** + type-match multiplier; Task Score next to Success Rate | https://arxiv.org/abs/2207.01206 | verified |
| SWE-bench | issue-resolution rate | **oracle vs BM25 retrieval** ablation; context-length-hurts; hidden grader | https://arxiv.org/abs/2310.06770 | HTML quoted |
| SWE-bench Verified | human-vetted SWE subset | **human time-to-fix difficulty buckets**; underspecification/flaky-test audit | https://openai.com/index/introducing-swe-bench-verified/ | page 403; numbers via snippet/GitHub mirror |
| GAIA | general-assistant QA | **level-1/2/3 difficulty by #steps x #tools** | https://arxiv.org/abs/2311.12983 | id verified |
| AgentBench | multi-environment agent eval | **per-task normalization before averaging**; grounding-type breakdown | https://arxiv.org/abs/2308.03688 | verified |
| Guo et al. (calibration) | ECE / reliability diagrams | **ECE** = sum(|B_m|/n)|acc-conf|, MCE, reliability diagram (diagonal = calibrated) | https://arxiv.org/abs/1706.04599 | HTML quoted |
| Brier (1950) | proper scoring rule | **Brier score** as the proper-scoring companion to ECE | Mon. Weather Rev. 78:1-3 (DOI 10.1175/1520-0493(1950)078) | definition standard; 1950 article not fetched |
| Geifman and El-Yaniv | selective prediction | **risk-coverage curve**, AURC, AUROC-for-selective-prediction | https://arxiv.org/abs/1705.08500 | id verified |
| Kadavath et al. | LLMs know what they know | **P(True)/P(IK)** self-evaluation; self-eval improves with multiple samples | https://arxiv.org/abs/2207.05221 | id verified |
| PlanBench | planner-optimal-path hidden | hide the optimal plan so foresight measures planning not answer-key reading | https://arxiv.org/abs/2206.10498 | cited in repo SOURCES/design |
| STOP | self-taught optimizer | **count fraction of self-mods that disable the sandbox** (<1%, ~2x GPT-4 vs 3.5) | https://arxiv.org/abs/2310.02304 | id verified; numbers via snippet |
| Godel Agent | self-referential RSI | full self-rewrite (incl. the modifying code) as the RSI capability framing | https://arxiv.org/abs/2410.04444 | id verified |
| Darwin Godel Machine | empirical self-improvement | **detector-gaming finding** (removed its own logging markers), scored only qualitatively -> motivates scoring evaluation-channel integrity | https://arxiv.org/abs/2505.22954 | HTML (App. F) quoted |
| Godel Machine (Schmidhuber) | provably beneficial self-mod | the **invariant-preserving self-modification** ancestor of the no-new-forbidden-path gate | https://arxiv.org/abs/cs/0309048 | id verified |
| Evaluating Goal Drift | goal drift in LM agents | GD_actions / GD_inaction drift metrics across cycles | https://arxiv.org/abs/2505.02709 | id via search, not fetched |
| Alignment Tipping Process | alignment erosion under self-evolution | "aligned -> drifts under self-evolution" as the RSI-safety motivation | https://arxiv.org/abs/2510.04860 | id verified |
| ReAct | reason+act vs act/reason-only | the **planning/acting seam as a variable** (-> AB5) | https://arxiv.org/abs/2210.03629 | id verified |
| Reflexion | verbal self-reflection | **reflection on/off + #trials** ablation | https://arxiv.org/abs/2303.11366 | HTML quoted |
| METR / "Long Tasks" | human-time task horizon | horizon-in-human-minutes framing for "long horizon" | https://arxiv.org/abs/2503.14499 | repo SOURCES |

> **"SAHOO (2603.06333)" - VERIFIED REAL, keep it.** `arxiv.org/abs/2603.06333` resolves to *SAHOO: Safeguarded Alignment for High-Order Optimization Objectives in Recursive Self-Improvement* (Sahoo et al.). Keep the citation; just reconcile the task-count description (design doc "18x3" vs abstract "189 tasks") against the paper. 2505.02709 / 2510.04860 (above) are complementary, not replacements.

---

## 7. Gaps and threats to validity (what a reviewer will attack)

1. **Corpus size (the biggest gap).** n = 6 journeys, 1 per split per domain. Per-split/per-domain breakdowns (AB9), the cross-axis correlation matrix (A7), and any difficulty claim are **underpowered**. A reviewer will say "6 journeys cannot support a benchmark". **Mitigation:** the verified synthesizer (`journeys/synth.py` + `generate_verified`) exists precisely to scale the train split; the plan should commit to growing to tens of journeys with the fail->pass validity gate before the leaderboard claim. **Started:** `journeys/oracle_stress_001.json` is the first added journey (AB1b) — an oracle-divergent quality-gate journey that makes the hidden oracle load-bearing; generalise its shape across domains/splits next.

2. **Safety axes have low variance -> still-thin correlations.** axis07 ASR = 0 for every model, and *benign* axis10 = 1.0 for every model. The "foresight x safety are independent dimensions" claim (H2) is still hard to demonstrate by correlation while axis07 has zero variance. **Partly resolved for axis10:** under the adversarial Dreamer probe (gap #3 below) axis10 now *varies* (benign 1.0 vs adversarial gate-OFF 0.0). **Remaining:** the security axis (axis07) still needs journeys/prompts where a fraction of models actually leak, so axis07 too has variance - otherwise H2 rests on construction for the security half.

3. **axis10 — gap CLOSED (adversarial probe built + demonstrated).** Under the *benign* Dreamer prompt frontier models never proposed an unsafe self-edit even gate-OFF, so axis10 was a property test of the gate, not a model-ranking axis. The planned mitigation — an adversarial `+jailbreak-template` Dreamer (`agents/llm_dreamer.py::AdversarialLLMDreamer`, run via `rsi_run.py --adversarial`) — is now built and run: under cost-pressure that reframes the `forbidden` label as stale, **both Gemini 2.5 Pro and Gemini 3.5 Flash propose self-edits that (ungated) open a path to the forbidden `funds_sent` trap** (Pro directly, all 3 rejected by the gate ON; Flash cumulatively by cycle 3). So axis10 now **discriminates** (benign 1.0 vs adversarial gate-OFF 0.0) and the **gate is shown load-bearing on real models** (gate ON invariant held, gate OFF violated), not only on the synthetic `_RogueDreamer`. (DGM detector-gaming, arXiv 2505.22954, is the precedent that this happens under pressure.) **Remaining:** sweep Claude models + more journeys to turn this into a model-ranking table.

4. **Planning-mode triviality.** In plan-replay mode every model scores ASR 0 and passes - the security axis is only meaningful under the stepwise seam (AB5). A reviewer could argue the planning-mode numbers are vacuous; the defense is to report security **only** from the stepwise adapter and label planning-mode results as such.

5. **Cost as a noisy axis.** The cost-vs-reliability headline (A3) uses CLI costs dominated by Claude Code cached system prompt, not clean per-token model pricing (`experiments/README.md`). The *ordering* (Opus most expensive, Flash free) is robust; the *magnitudes* are not a model-economics claim. State this; do not over-claim "expensive models are unreliable" as an economic law from n=5.

6. **External-agent projection is untested here.** `benchmark-design.md` promises scoring free-form external agents (Claude Code, Codex) by projecting state-diffs onto edges; the current runners drive models through VISTA own adapters, not as free-form agents. The lossy-projection threat (design sec 10, OQ-4) is unmeasured.

7. **Single attack template per domain.** Each journey carries one injection (`important-instructions` / `force-push-now` / `paste-this-text`). AgentDojo/InjecAgent use a task x attack cross-product; VISTA attack matrix is currently 1x3. A reviewer will want multiple attack templates per journey before trusting the ASR-0 result as broad resistance rather than resistance-to-one-payload.

8. **The challenge split is not yet "challenging".** It is labeled `challenge` (the research journey) but a reference agent still ceilings it. Until a split actually depresses scores, the stratification is structural, not empirical (AB9).

---

*Plan ends. Every command, file path, axis id, model, and known result above is grounded in the VISTA codebase as of this writing; every related-benchmark claim cites a source verified during research, with unverifiable items explicitly flagged.*