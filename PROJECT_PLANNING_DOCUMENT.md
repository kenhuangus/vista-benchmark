# Project Planning Document — Ranger / VISTA Bench

**Capstone direction:** B — *a philosophically different take on agents.*
**Deliverable:** Project Planning Document (due Wed Jun 17). **Showcase:** Mon Jun 29.
**Team size:** 3–4.

> **One line.** We build **VISTA Bench**, the first benchmark that measures whether
> a long-running agent holds the *long view* — **foresight (planning quality) ×
> safety**, sustained over a multi-day horizon and *improving* rather than
> decaying as the agent self-improves — graded against the **OWASP Top 10 for
> Agentic Applications**; and **Ranger**, a three-model agent (Scout · Worker ·
> Dreamer) built to win it.

---

## 1. Problem & thesis

Agents already take long sequences of steps. What no one can **measure** is whether
they hold the long view: plan far ahead, stay aligned to the principal's intent as
the terrain shifts, resist adversarial hijacking, and get **safer** — not more
drift-prone — as they self-improve. Long-horizon failure is real and measured
(METR; *Illusion of Diminishing Returns*, ICLR 2026): the failures are *execution,
not reasoning*. The long view breaks three ways, and **no existing benchmark
measures them together over a horizon**:

1. the agent **drifts off-plan** (loses intent) — OWASP **ASI01 Agent Goal Hijack**;
2. untrusted terrain **hijacks it** (security) — ASI02–ASI07;
3. it **self-improves in the wrong direction** — reward-hacking / goal drift, as the
   Darwin Gödel Machine and Anthropic's production-RL study both documented.

**Thesis.** A long-running agent that a team can verify-not-redo must be measured
on *foresight × safety over time*, and built to keep both rising as it learns. The
novelty is the **benchmark**; the agent (Ranger) instantiates published patterns.

---

## 2. Proposed system

### 2.1 VISTA Bench — the instrument

A deterministic harness that replays a multi-day **journey** (an evolving
workspace + event trace) against any agent, and scores the **maintained
route-state** on nine axes. Journeys are seeded with **OWASP agentic attacks**
(injection, goal-hijack, memory-poisoning) and a **slow-burn signal** only
consolidation catches. Three domains: project stewardship, **coding**, and
**research** campaigns.

**The nine axes** (each declarative + state-based, mapped to OWASP ASI threats):

| Axis | What it scores | OWASP tie |
|---|---|---|
| Goal progress | Did the plan reach the intended end-state? | ASI01 |
| Continuity | Commitments / open questions preserved? | ASI08 |
| Adaptation | Stale assumptions + changed facts reflected? | ASI01, ASI08 |
| **Foresight** | Plan quality: milestones, look-ahead, ordering | (new) |
| Verification calibration | Escalated the right forks, not every step? | ASI09 |
| **Self-improvement safety** | Does safety **rise** across Dreamer cycles? | ASI10 |
| Security & abuse resistance | Refused injection / poison / exfil? | ASI02–ASI07 |
| State hygiene + handoff | Coherent, recoverable, auditable? | ASI07, T8 |
| Collateral damage | No corruption of unrelated state; no PII leak | ASI03 |

The headline metrics: the **long-view premium** (score with the Scout/plan ON vs
OFF) and the **self-improvement trend** (does safety/alignment go up or down across
Dreamer cycles — the axis no prior benchmark measures).

### 2.2 Ranger — the three-model agent

| Model | Role | Grounding |
|---|---|---|
| **Scout** | High-level planner: maps long-distance milestones, holds the route map, re-plans under drift, escalates the few high-risk forks. | Plan-and-Act (2503.09572), ReWOO, ADaPT |
| **Worker** | Heavily sandboxed executor: runs immediate steps with **no authority and no secrets**; the only component that touches untrusted data. | Dual-LLM (Willison) → CaMeL (2503.18813); Design Patterns (2506.08837) |
| **Dreamer** | Offline **guardrailed recursive self-improvement** between legs: consolidate skills, revise poisoned/false beliefs, self-audit vs the OWASP Top-10. | Reflexion (2303.11366), Generative Agents (2304.03442), Voyager (2305.16291), Sleep-time Compute (2504.13171) |

**Privilege separation = the security boundary** (CaMeL pattern): the goal-holding
Scout never touches untrusted terrain; the untrusted-data-handling Worker has no
authority to change the plan or exfiltrate. The Dreamer's improvement is gated by
**verified eval signals + traceable lineage + capped per-cycle change**, because
ungated RSI amplifies misalignment (the DGM hacked its own reward function — the
failure we explicitly design against).

---

## 3. Research basis (citations verified on live arXiv)

- **Long-horizon is hard + measured:** METR 2503.14499 · Vending-Bench 2502.15840 · *Illusion of Diminishing Returns* 2509.09677.
- **Planner/executor security:** CaMeL 2503.18813 · Design Patterns 2506.08837 · Dual-LLM (Willison, 2023).
- **Plan-then-execute helps long horizon:** Plan-and-Act 2503.09572 · ReWOO 2305.18323 · ADaPT 2311.05772 · LLMCompiler 2312.04511.
- **Offline self-improvement / consolidation:** Reflexion 2303.11366 · Generative Agents 2304.03442 · Voyager 2305.16291 · Sleep-time Compute 2504.13171 · STOP 2310.02304 · Darwin Gödel Machine 2505.22954.
- **RSI risk (design against):** DGM reward-hacking (sakana.ai/dgm) · Anthropic "Natural Emergent Misalignment from Reward Hacking" 2511.18397.
- **Threat taxonomy:** OWASP **Top 10 for Agentic Applications** (ASI01–ASI10, OWASP GenAI Security Project, Dec 2025) + the 15-threat "Agentic AI – Threats & Mitigations" guide (Feb 2025).
- **Closest prior art (cite head-on):** AgentLAB 2602.16901 + AgentHarm 2410.09024 (long-horizon attacks, but score attack-success, never planning) · SafeEvalAgent / Meta-Agent Challenge (safety **decays** across self-improvement) · single-session security: AgentDojo 2406.13352, InjecAgent 2403.02691, ST-WebAgentBench 2410.06703, SafeArena 2503.04957.

Honest novelty delta: every *mechanism* is published; the contribution is the
**combined foresight × safety benchmark over a horizon, with a self-improvement-safety
axis no one else measures.**

---

## 4. The contracts (the heart of collaborating in parallel)

Four interfaces are **frozen on day one** in `contracts/`. Once frozen, each owner
builds behind their contract without blocking anyone; a **contract test suite** in
CI is the single gate to merge. Changing a contract requires a PR + one reviewer
from each affected role.

| # | Contract | File | Defines | Consumed by |
|---|---|---|---|---|
| C1 | **Route-state schema** | `contracts/route_state.schema.json` | The shared workspace: docs, tickets, records, messages, calendar, memory, audit log, dream journal | everyone |
| C2 | **Agent-tool API** | `contracts/tools.py` (typed stubs) | The tools Scout/Worker/Dreamer call (read/write/search/escalate/record_dream/...), with PII-redacted audit | Scout, Worker, Dreamer leads |
| C3 | **Scoring rubric** | `contracts/rubric.schema.json` | The 9 axes as declarative checks + the OWASP-ASI attack/defense check types | Benchmark lead; everyone reads |
| C4 | **AgentAdapter** | `contracts/adapter.py` | `run_session(journey, route_state, steering) -> SessionResult` — drives Ranger AND external agents | Benchmark + Worker leads |

A change that doesn't break a contract test never blocks a teammate. A change that
does is caught in CI before it reaches `main`.

---

## 5. Team roles (3–4 people)

The architecture *is* the work-breakdown — each person owns one module behind a contract.

| Role | Owns | Primary deliverable | Depends on |
|---|---|---|---|
| **Benchmark lead** | VISTA harness, event scheduler, the 9-axis scorer, OWASP-ASI journeys, scoreboard/report | Runnable harness + 3 journeys + scoring | C1, C3 |
| **Scout lead** | Planner model, milestone/route schema, drift re-planning, escalation policy, the *foresight* score signals | Scout module + foresight checks | C1, C2 |
| **Worker lead** | Sandboxed executor, tool API impl, privilege separation, external-agent **adapters** (Claude Code / Codex / OpenClaw / Hermes) | Worker module + adapter harness | C2, C4 |
| **Dreamer / research lead** | Consolidation loop, belief revision, RSI guardrails (lineage, capped change), OWASP self-audit, paper + demo | Dreamer module + results write-up + demo | C1, C2, C3 |

(With 3 people, the Dreamer and Benchmark roles pair up; with 4, they split.)

---

## 6. Collaboration & tooling (Claude Code / Codex)

**Repo & branching.** One repo; `main` is protected. No direct pushes — each role
works on `feat/<role>/<topic>` branches and opens PRs. Optional **git worktrees**
let one person run several Claude Code agents in parallel on separate branches
without clobbering each other.

**Shared agent context.** A repo-root **`CLAUDE.md`** (and mirror **`AGENTS.md`**
for Codex) is the single source of truth for: the four contracts, the directory
map, the test commands, and skill-routing rules. Every agent session loads it, so
all four developers' AI assistants share the same ground rules.

**Per-developer setup.**
- *Claude Code:* `claude` in the role's worktree; interactive for design, headless
  `claude -p "<task>" --output-format json` for scripted/CI runs. Use
  `--allowedTools` / permission modes to keep the executor sandboxed during
  Worker-adapter testing. Sub-agents handle parallel research/refactor within a
  module. Add an MCP server only if a contract needs one (none required for MVP).
- *Codex (alternative):* `codex exec "<task>" --json --full-auto --output-schema
  <C3 schema>`; project context in `AGENTS.md`; `codex exec resume` to continue.
  Note: Codex hard-fails on approval prompts unless `--full-auto`, and Claude
  Code's `--bare` drops ambient memory/MCP — bake both into CI defaults.

**The integration gate (this is what makes parallel safe).** Every PR must pass the
**contract test suite** (`make contracts` / `pytest contracts/tests`) — it asserts
each module honors C1–C4. A second, slower **journey-regression** suite runs the
full benchmark on the reference Ranger and the naive baseline and asserts the score
spread holds (catches silent regressions). Green contract tests → merge; the
journey suite gates the nightly integration build.

**Cadence.** Daily 15-min standup against the contracts (anything that needs a
contract change is raised here, not silently worked around). Mid-week (Jun 22) and
pre-demo (Jun 27) integration freezes.

---

## 7. Scope

**Minimum shippable (Week 1):**
- VISTA harness + **3 multi-day journeys** (project · coding · research), each seeded with an OWASP-ASI attack + a slow-burn signal.
- Ranger (Scout + sandboxed Worker + guardrailed Dreamer) scoring at the top of the range.
- Head-to-head vs a strong **single-model agent**; report the **long-view premium**.
- The new measurement: does safety **rise or drift** across Dreamer cycles?

> *Status:* a prototype harness + one journey + a reference agent were built and
> validated end-to-end (a clear naive-vs-steward score spread); the team rebuilds
> it cleanly **against the frozen contracts** in Week 1. (Implementation is
> intentionally not carried forward from the prototype at proposal stage.)

**Ambitious (Week 2):**
- 9–12 journeys; full OWASP agentic Top-10 coverage.
- Adapters driving **Claude Code, Codex, OpenClaw, Hermes** through identical journeys (Harbor-style).
- Ablations: **Scout off / sandbox off / Dreamer off** + a small human baseline.
- A paper: the first benchmark where **safety is measured across self-improvement cycles**.

---

## 8. Timeline

| Date | Milestone |
|---|---|
| **Jun 15** | Concept + direction frozen; team formed; this planning doc drafted. |
| **Jun 16** | **Freeze contracts C1–C4**; harness skeleton + contract test suite stand up; first journey end-to-end through the AgentAdapter. |
| **Jun 17** | **Planning document submitted.** At least one journey runnable through the agent interface. |
| **Jun 18–21** | Build the 3 MVP journeys; the 9-axis scorer; Scout + Worker + Dreamer behind contracts; first long-view premium number. |
| **Jun 22–25** | OWASP-ASI attack journeys; the self-improvement-safety axis; single-model baseline; tighten reproducibility; ablations begin. |
| **Jun 26–28** | External-agent adapters (best-effort); final demo path; report + visuals; freeze artifacts. |
| **Jun 29** | **Live 10-minute demo + results.** |

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| RSI is double-edged (amplifies misalignment — DGM, Anthropic) | The Dreamer is the **guardrailed** exception (verified signal, traceable lineage, capped change); **VISTA's job is to catch drift** — measuring it is the contribution. |
| Scoring long-horizon behavior can be gamed/subjective | Declarative **state-based** checks + hidden ground truth + a failure taxonomy mapped to OWASP ASI; never a final-answer grade. |
| Driving 4 external CLIs reliably | One **Harbor-style adapter** (C4); degrade gracefully; **never fake a number** — report whatever subset runs. |
| Novelty challenge ("isn't this CaMeL / AgentLAB?") | Cite them head-on; the contribution is the **benchmark + the foresight×safety + self-improvement-safety axes**, not the mechanism. |
| Parallel work blocking | The four **frozen contracts** + CI contract-test gate; daily standup raises contract changes explicitly. |
| Scope creep across two artifacts | They share one spine (the harness); ship the MVP + premium first, external comparison second. |

---

## 10. Deliverables & success criteria

**Deliverables:** the VISTA harness + journeys + scorer; the Ranger three-model
agent; the long-view-premium and self-improvement-safety results; a short paper;
the live demo.

**Success** = we demonstrate (1) a clear, defensible benchmark gap; (2) a runnable
harness scoring real agents on foresight × safety over a horizon; (3) journeys that
expose meaningful failures invisible to pass/fail; (4) a measurable long-view
premium for the three-model design; and (5) the first evidence on whether an
agent's safety **rises or drifts** as it self-improves.
