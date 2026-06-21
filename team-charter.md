# Team Charter — VISTA Bench / Ranger (production build)

| | |
|---|---|
| **Status** | Charter v1 (2026-06-20) — *staffing & ownership; no code yet* |
| **Team** | 1 orchestrator + 6 specialists (production-grade) |
| **Companion docs** | [prd.md](prd.md) · [architecture.md](architecture.md) · [plan.md](plan.md) · [benchmark-design.md](benchmark-design.md) |
| **Execution model** | Contracts frozen day 0 → each seat builds in its own git worktree behind its contract → CI contract-gate is the only merge path |

> **The bar.** *Research-grade production*: deterministic + reproducible, `pip`-installable with a real CLI,
> CI-gated, documented, with a public leaderboard and a paper. **Not** enterprise SaaS (no HA, multi-tenant,
> RBAC, billing, or uptime SLAs). Build to that bar — no further.

---

## 1. The team at a glance

| Seat | Role | Owns (contracts) | Owns (modules) |
|---|---|---|---|
| **S0** | Orchestrator / integrator | the **contract set** + CI | `contracts/`, CI config, merge queue |
| **S1** | Harness & scoring | **C1**, **C4** | scheduler · route-graph runtime · scorer + graph oracle |
| **S2** | Graph & dataset | **C2**, **C6** | sanctioned graph · journey generator · attack matrix · human-validated subset |
| **S3** | Ranger agent + adapters | **C3**, **C5** | Scout · Worker · AgentAdapter · external state-diff projection |
| **S4** | Dreamer / RSI | (consumes C2/C3/C4) | Dreamer · working-graph edits · RSI guardrails |
| **S5** | Security / red-team *(independent)* | (consumes C4/C6) | OWASP ASI fixtures · canary egress · adversarial journeys |
| **S6** | Infra / reproducibility / release | (consumes C4/C5) | CI · packaging + CLI · determinism harness · `results/v{X.Y}` · docs · leaderboard · paper |

**Contract → owner → enforcing test** (the enforcement spine):

| Contract | Owner (co-reviewers) | Enforcing test |
|---|---|---|
| C1 route_state | S1 (all) | `test_route_state_roundtrip` |
| C2 sanctioned route-graph | S2 (S1, S3) | `test_graph_wellformed`, `test_offgraph_detected`, `test_oracle_hidden_from_agent` |
| C3 tools | S3 (S4) | `test_tool_signatures`, `test_worker_no_authority` |
| C4 rubric | S1 (S5) | `test_rubric_axes_complete`, `test_scorer_deterministic` |
| C5 adapter | S3 (S1) | `test_adapter_protocol`, `test_state_diff_projection` |
| C6 journey/dataset | S2 (S5) | `test_journey_wellformed`, `test_attack_matrix_reachable` |

---

## 2. Per-seat charters

Each card: **Mandate** · **Owns** · **Definition of Done** · **Must make pass** · **Boundaries (must NOT)** · **Depends on**.

### S0 — Orchestrator / integrator
- **Mandate.** Hold the contracts; keep `main` green; decompose work; merge; re-run the full suite after every merge.
- **Owns.** `contracts/` integrity, CI config, the merge queue, the cross-seat schedule.
- **DoD.** Contracts frozen + skeletons day 0; every merged PR passed the contract gate; journey-regression spread holds on `main`.
- **Must make pass.** The aggregate `pytest contracts/tests` + nightly journey-regression.
- **Boundaries.** Does not implement seat modules; does not relax a contract test to unblock a seat — a contract change is a PR with affected-seat review.
- **Depends on.** Nothing (goes first).

### S1 — Harness & scoring
- **Mandate.** The deterministic spine every agent is scored on.
- **Owns.** C1 (route_state), C4 (rubric); event scheduler; route-graph runtime (**records** off-sanctioned-walk, **blocks** forbidden crossings); scorer + graph oracle (progress-rate, optimality-gap, drift, verification-calibration, **pass^k**, collateral allowlist).
- **DoD.** A fixed trajectory + seed → identical scorecard; ten axes computed; PII-redacted journey log emitted.
- **Must make pass.** `test_route_state_roundtrip`, `test_rubric_axes_complete`, `test_scorer_deterministic`, `test_offgraph_detected`.
- **Boundaries.** Never imports agent internals; the scorer reads only route-state + the sanctioned graph (incl. its hidden oracle), never the agent's reasoning.
- **Depends on.** C1, C4 frozen (its own).

### S2 — Graph & dataset
- **Mandate.** The ground truth and the data — the part that makes the benchmark *publishable*.
- **Owns.** C2 (two-layer sanctioned route-graph: given guardrails / hidden `optimal_walk`+`subgoal_states`), C6 (journey schema); the **generate-with-verifier** journey generator; the task×attack matrix; train/dev/test/**challenge** splits; the **human-validated headline subset**.
- **DoD.** 3 domains (project/coding/research) generate valid journeys whose oracles provably hold; a severity-filtered human-validated subset exists; the challenge split uses unseen attacks/tools.
- **Must make pass.** `test_graph_wellformed`, `test_oracle_hidden_from_agent`, `test_journey_wellformed`, `test_attack_matrix_reachable`.
- **Boundaries.** Never leaks `optimal_walk`/`subgoal_states` into the agent-visible view; attack *content* is co-designed with S5 but the matrix wiring is S2's.
- **Depends on.** C1 (route-state shape) from S1.

### S3 — Ranger agent + adapters
- **Mandate.** The system under test, and the one seam to external agents.
- **Owns.** C3 (tools), C5 (adapter); the **Scout** (builds the *working* route-graph, plans, re-plans, escalates); the **sandboxed Worker** (no authority/secrets, fires one Scout-authorized edge); the **AgentAdapter** + **external state-diff→edge projection**.
- **DoD.** Ranger runs every journey unchanged through the adapter; privilege separation holds; ≥1 external agent (Claude Code or Codex) is driven + scored via projection.
- **Must make pass.** `test_tool_signatures`, `test_worker_no_authority`, `test_adapter_protocol`, `test_state_diff_projection`.
- **Boundaries.** The Worker never holds authority/secrets; the Scout never receives raw untrusted data; the working graph is scored against the sanctioned graph, never the reverse.
- **Depends on.** C1, C2 (to consume the guardrail view); C4/C5 shape.

### S4 — Dreamer / RSI
- **Mandate.** The novel, risk-bearing component — offline self-improvement that must get *safer*, not drift.
- **Owns.** The Dreamer (consolidate, revise poisoned beliefs, self-audit vs OWASP); **working-route-graph edits** as reviewable diffs; RSI guardrails (verified eval signal, traceable lineage, capped per-cycle change, forbidden-state-reachability rejection); the self-improvement-safety axis.
- **DoD.** A measured self-improvement trend across cycles; a working-graph edit that opens a path to a forbidden state is **rejected** in a test; every edit carries lineage + respects the budget.
- **Must make pass.** `test_invariant_preserved`, plus its axis-10 scoring path in C4.
- **Boundaries.** Edits **only Ranger's working graph — never the sanctioned graph (C2)**; ungated/unlineaged edits are rejected.
- **Depends on.** C2, C3, C4.

### S5 — Security / red-team *(kept independent of S1–S4)*
- **Mandate.** Adversarially grade the safety the builders shouldn't grade themselves.
- **Owns.** The OWASP ASI attack fixtures (ASI01–ASI03, ASI05–ASI10), canary tokens + egress checks, the two-axis utility-vs-ASR validation, adversarial + memory-poisoning journeys (incl. the slow-burn signal aimed at the Dreamer), the privilege-separation assertions.
- **DoD.** Each adversarial event maps to a specific ASI threat + a programmatic defense check; canary exfil is detectable; the privilege-separation tests fail loudly if S3 regresses.
- **Must make pass.** `test_worker_no_authority` (jointly with S3), the per-attack `security()` predicates in C6.
- **Boundaries.** Does not build the agent or the harness it attacks; files findings as failing tests/journeys, not as patches to S1–S4 code.
- **Depends on.** C4, C6; needs S1's harness + S3's adapter to run attacks (joins phase 2).

### S6 — Infra / reproducibility / release
- **Mandate.** The difference between a research artifact and a benchmark others can install and trust.
- **Owns.** CI (contract + journey-regression gates), packaging (`pip` + a real CLI), the determinism/seed harness, **`results/v{X.Y}/{bench}-{timestamp}.json`** archival, the docs site, the public leaderboard, and the experiments/paper (long-view premium, ablations, self-improvement trend, human baseline).
- **DoD.** `pip install` + `vista run …` works on a clean machine; CI gates merges; results are versioned + reproducible to the same numbers; leaderboard + paper draft exist.
- **Must make pass.** The full suite in CI; a reproducibility test (same seed → same archived result).
- **Boundaries.** Does not change contracts or scoring logic to make numbers look better; reports whatever subset of external adapters actually runs — **never fakes a number**.
- **Depends on.** C4, C5; consumes everyone's output (joins phase 3).

---

## 3. How the agent team runs

1. **Contracts first (S0, day 0).** Freeze C1–C6 + write the contract-test skeletons (red is fine; the *shape* is fixed). Nothing else starts before this.
2. **Worktree isolation.** Each seat works in its own git worktree on `feat/<seat>/<topic>` — concurrent file edits never collide. (For an agent team: spawn each seat with `isolation: "worktree"`.)
3. **The CI contract-gate is the only merge path.** A PR merges iff `pytest contracts/tests` is green. A change under `contracts/` needs a PR + one reviewer per affected seat.
4. **S0 re-runs the full suite after each merge** (journey-regression) to catch silent breakage.
5. **Independence is structural.** S5 (security) and S6 (experiments) grade work they didn't build.
6. **Cadence.** Daily 15-min standup against the contracts; anything needing a contract change is raised there, never silently worked around. Mid-week + pre-release integration freezes.

## 4. Sequencing — which seats are hot when

| Phase | Active seats | Exit criterion |
|---|---|---|
| **0 — Contracts** | S0 | C1–C6 frozen; test skeletons in `contracts/tests/` |
| **1 — Spine + first journey** | S1, S2 | one journey runs end-to-end through the adapter stub; off-sanctioned-walk detected |
| **2 — Agent + Dreamer + attacks** | S3, S4, S5 | Ranger scores a journey; first long-view premium; first adversarial journey graded |
| **3 — Harden + scale + publish** | S6 (+ all) | `pip`-installable; CI green; `results/v{X.Y}` archival; leaderboard + paper draft; external adapter(s) |

S5 and S6 join in phases 2–3 (they need the harness + adapter first); the first push concentrates in S1–S4.

## 5. Definition of "production-ready done" (project-level)

- ✅ `pip install` + `vista run <journey>` works on a clean machine (S6).
- ✅ Deterministic instrument: same seed → identical archived scorecard; LLM agents reported mean ± CI over k runs (S1, S6).
- ✅ Contract suite + journey-regression green on `main`; no contract bypass (S0).
- ✅ 3 domains, human-validated subset, challenge split, full OWASP ASI coverage (S2, S5).
- ✅ Ranger + ≥1 external agent scored through one adapter; long-view premium + self-improvement trend reported (S3, S4, S6).
- ✅ Docs site + public leaderboard + paper draft; PII never in logs/results (S6, S5).

## 6. Team-structure risks

| Risk | Mitigation |
|---|---|
| A seat silently relaxes a contract test to unblock itself | Contract changes are PRs with affected-seat review; S0 owns the gate, not the seats. |
| Builders grade their own safety | S5 is structurally independent; its attacks are failing tests S1–S4 must satisfy. |
| Dreamer corrupts the ground truth | Hard boundary: Dreamer edits only the *working* graph; `test_invariant_preserved` + lineage enforce it. |
| External-adapter projection misattributes actions | S3 validates projection on a known-good trace; S6 reports it as best-effort, never fakes a number. |
| Parallel seats drift apart | Frozen contracts + CI gate + daily standup + S0's post-merge full-suite run. |
