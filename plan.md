# Plan — Ranger / VISTA Bench

| | |
|---|---|
| **Status** | Draft v1 (2026-06-20) |
| **Companion docs** | [prd.md](prd.md) (the *what/why*), [architecture.md](architecture.md) (the *how* + contract schemas) |
| **Owns** | Execution model, contract freeze, roles, work breakdown, the CI enforcement gate, timeline, risks |
| **Showcase** | Mon **Jun 29**, 10-minute live demo |

The organizing principle: **the contracts are the work-breakdown.** Freeze C1–C6 day one, then
each of 3–4 people builds behind one contract in parallel, and a **CI contract-test gate** is the
single thing that lets them merge. Nothing below is novel process — it is what makes parallel safe.

---

## 1. Execution model — contracts-first parallel

1. **Freeze the six contracts** (C1–C6, [architecture.md §6](architecture.md#6-the-contracts-the-enforcement-surface)) before any module code.
2. Each owner builds **behind** their contract; consumers code against the frozen interface, not the impl.
3. **CI is the gate**: a PR merges only if `pytest contracts/tests` is green (every module still honors C1–C6).
4. A contract change is a deliberate event: PR + one reviewer **per affected role**, raised at standup —
   never silently worked around.

This is the entire reason the team can split four ways and still integrate.

## 2. Contract freeze (Day 1, Jun 21)

| # | Contract | File | Owner | Affected reviewers on change |
|---|---|---|---|---|
| C1 | Route-state schema | `contracts/route_state.schema.json` | Benchmark | all |
| **C2** | **Sanctioned route-graph schema** (intent-alignment surface) | `contracts/route_graph.schema.json` | Benchmark + Scout | Scout, Worker, Dreamer |
| C3 | Agent-tool API | `contracts/tools.py` | Worker | Scout, Dreamer |
| C4 | Scoring rubric | `contracts/rubric.schema.json` | Benchmark | all |
| C5 | AgentAdapter | `contracts/adapter.py` | Worker | Benchmark |
| **C6** | **Journey / dataset schema** | `contracts/journey.schema.json` | Benchmark | all |

> **C2 (the sanctioned route-graph) is what makes "intent alignment" enforceable instead of
> aspirational** (see [prd.md §2](prd.md#2-the-reframe--intent-alignment-is-staying-on-a-predefined-markov-route-graph)),
> so it is co-owned by the Benchmark and Scout leads and frozen first. **Ranger's *working* route-graph
> — built by the Scout, edited by the Dreamer — is an agent artifact, NOT a contract**; it is scored
> against C2, never the reverse. **C6** (the journey/dataset: event trace + oracle bindings + split) is
> the sixth contract.

**Definition of "frozen":** the schema/stub file exists, validates, and has at least its
contract-test skeleton in `contracts/tests/` (red is fine; the *shape* is fixed).

## 3. Team roles & ownership (3–4 people)

| Role | Owns | Primary deliverable | Contracts |
|---|---|---|---|
| **Benchmark lead** | VISTA harness, event scheduler, route-graph runtime, the 10-axis scorer + **graph oracle**, journeys, scoreboard | Runnable harness + 3 journeys + scoring | C1, C2, C4, C6 |
| **Scout lead** | Planner model, plan-as-walk-over-graph, drift re-planning, escalation policy, foresight signals | Scout module + foresight checks | C2, C3 |
| **Worker lead** | Sandboxed executor, tool API impl, privilege separation, AgentAdapter + external adapters | Worker module + adapter harness | C3, C5 |
| **Dreamer / research lead** | Consolidation loop, belief revision, **working-route-graph-edit proposals**, RSI guardrails, OWASP self-audit, paper + demo | Dreamer module + results + demo | C2, C3, C4 |

With **3 people**, Dreamer + Benchmark pair up; with **4**, they split.

## 4. Work breakdown by module (each maps to an FR set in the PRD)

- **Harness** (Benchmark) → FR-B1…B5, FR-G2/G3: scheduler, route-graph runtime (off-sanctioned-walk detection),
  scorecard, audit log.
- **Route-graph + oracle** (Benchmark+Scout) → FR-G1…G5, FR-S1/S2/S4: C2 schema, well-formedness +
  reachability checks, foresight/drift scoring, invariant diff.
- **Scout** (Scout) → FR-A1: plan as graph walk, re-plan, escalation calibration.
- **Worker** (Worker) → FR-A2, FR-Sec2: one-authorized-edge-at-a-time executor, no authority/secrets.
- **Dreamer** (Dreamer) → FR-A3/A4, FR-S3: consolidate, propose graph diffs, lineage + capped budget.
- **Adapters** (Worker) → FR-B3: C5 for Ranger; Week-2 external CLIs.
- **Security fixtures** (Dreamer/research) → FR-Sec1/Sec3: inert ASI payloads + defense checks.

## 5. Collaboration & tooling (Claude Code / Codex)

**Repo & branching.** One repo; `main` protected; no direct pushes. Each role works on
`feat/<role>/<topic>` and opens PRs. Optional **git worktrees** let one person run several Claude Code
agents in parallel on separate branches without clobbering.

**Shared agent context.** A repo-root **`CLAUDE.md`** (mirror **`AGENTS.md`** for Codex) is the single
source of truth: the six contracts, the directory map ([architecture.md §9](architecture.md#9-directory-layout-target)),
test commands, and skill-routing. Every agent session loads it, so all four developers' AI assistants
share the same ground rules.

**Per-developer setup.**
- *Claude Code:* `claude` in the role's worktree; interactive for design, headless
  `claude -p "<task>" --output-format json` for scripted/CI runs. Use `--allowedTools` / permission
  modes to keep the executor sandboxed during Worker-adapter testing.
- *Codex (alt):* `codex exec "<task>" --json --full-auto --output-schema <C4 schema>`; context in
  `AGENTS.md`; `codex exec resume` to continue. Gotchas: Codex hard-fails on approval prompts unless
  `--full-auto`; Claude Code's `--bare` drops ambient memory/MCP — bake both into CI defaults.

## 6. CI — the enforcement gate

This section *is* "so the contracts can be enforced."

1. **Contract suite (blocking):** `pytest contracts/tests` runs the named tests from
   [architecture.md §6](architecture.md#6-the-contracts-the-enforcement-surface) — `test_graph_wellformed`,
   `test_offgraph_detected`, `test_invariant_preserved`, `test_worker_no_authority`,
   `test_scorer_deterministic`, `test_adapter_protocol`, etc. Green → mergeable.
2. **Journey-regression (nightly):** runs the full benchmark on reference Ranger + naive baseline and
   asserts the score spread holds (catches silent scorer/agent regressions).
3. **No-PII / privilege check:** asserts FR-Sec2/Sec3 — Scout never sees untrusted data; no secrets in
   logs/audit/scorecards.
4. **Contract-change protocol:** any diff under `contracts/` requires a PR + one reviewer per affected
   role (table in §2) and a standup note.

A change that doesn't break a contract test never blocks a teammate; one that does is caught before `main`.

## 7. Timeline

| Date | Milestone |
|---|---|
| **Jun 20** | PRD + Architecture + Plan written; **C2 route-graph reframe** folded in. |
| **Jun 21** | **Freeze C1–C6**; `contracts/tests` skeletons stand up (red ok); harness skeleton. |
| **Jun 22** | First journey end-to-end through the AgentAdapter; route-graph runtime detects off-sanctioned-walk transitions. |
| **Jun 23–25** | 3 MVP journeys; the graph oracle (foresight/drift); Scout + Worker + Dreamer behind contracts; first **long-view premium**. |
| **Jun 26–27** | OWASP-ASI attack journeys; the **self-improvement-safety** axis + invariant diff; single-model baseline; ablations begin. |
| **Jun 28** | External-agent adapters (best-effort); final demo path; report + visuals; freeze artifacts. |
| **Jun 29** | **Live 10-minute demo + results.** |

## 8. Cadence & integration freezes

- Daily 15-min standup **against the contracts** — anything needing a contract change is raised here.
- Mid-week integration freeze **Jun 25**; pre-demo freeze **Jun 28**.

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| RSI is double-edged (DGM hacked its reward; Anthropic shows it generalizes) | Dreamer is the **guardrailed** exception (verified signal, lineage, capped diff, invariant check); **VISTA catches drift** — that's the contribution. |
| "Isn't the graph just Salesforce Agent Graph?" | Yes — cite it head-on as validation. Our novelty is the **benchmark over the graph** + **safe graph evolution**, not the mechanism ([prd.md §2](prd.md#2-the-reframe--intent-alignment-is-staying-on-a-predefined-markov-route-graph)). |
| A predefined graph is brittle / can't enumerate reality | Explicit **escape/HITL node** + Dreamer-grown graph; measure adherence, keep the LLM inside nodes (guided, not full, determinism). |
| Markov assumption too strong for long horizon | Score over the **augmented state** (position + memory), not position alone; cap memory in state (OQ-2). |
| Scoring gamed/subjective | The **graph oracle** makes foresight/drift mechanical; other axes are declarative state checks vs hidden ground truth; never a final-answer grade. |
| Driving 4 external CLIs reliably | One adapter (C5); degrade gracefully; **never fake a number** — report whatever subset runs. |
| Parallel work blocking | The five **frozen contracts** + CI gate + daily standup. |

## 10. Definition of done / deliverables

**Deliverables:** VISTA harness + journeys + scorer (with graph oracle); the Ranger three-model agent;
the long-view-premium and self-improvement-trend results; a short paper; the live demo.

**Done** = the PRD acceptance criteria (AC-1…AC-6) pass, the contract suite is green on `main`, and the
demo runs a journey end-to-end showing (1) a defensible benchmark gap, (2) deterministic foresight ×
safety scoring over a horizon via the route-graph, (3) failures invisible to pass/fail, (4) a positive
long-view premium, and (5) the first evidence on whether safety **rises or drifts** across self-improvement.
