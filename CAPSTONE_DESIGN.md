# Capstone Design: Aion + StewardBench

> **One project, two artifacts that prove each other.**
> **Aion** — a cognitive architecture (and general-purpose agent framework) for
> *long-running* agents. **StewardBench** — a benchmark that isolates the
> capabilities a long-running agent needs, and drives both Aion and external
> agents (Claude Code, Codex, OpenClaw, Hermes) through the same tasks.
>
> Capstone **Direction B**: *could a company run on one shared agent the team only
> verifies?* Our answer: not with today's **episodic** agents — but with an
> architecture that adds the missing *between-session* cognition, yes. The
> benchmark measures the gap; the framework closes it.
>
> *Names `Aion` and `StewardBench` are working titles (single find/replace to
> change). `Aion` = Greek for "age / lifetime" — an agent built to persist.*

---

## 1. Thesis: frontier agents are episodic, not long-running

Today's best coding/research agents — Claude Code, Codex, OpenClaw, Hermes — are
**episodic**. They are extraordinary *within a session*: plan, call tools, edit,
test, iterate. But a session is a closed box. Across sessions they:

- **re-learn the world every time** — no principled persistent memory; they rebuild
  their understanding of the repo/project from scratch (or from a flat `CLAUDE.md`),
- **repeat past mistakes** — no learning loop that distills durable skills from
  what worked and what failed,
- **drift over long horizons** — local decisions stay coherent while the global
  plan rots (the Vending-Bench failure mode),
- **cannot be steered without restarting** — there is no first-class channel to
  inject a correction, a changed priority, or a veto *mid-run*,
- **never consolidate** — there is no offline pass that prunes stale beliefs,
  reconciles contradictions, or surfaces slow-burn anomalies while the agent is
  idle.

These are not capacity problems a bigger context window fixes. They are *missing
subsystems*. A human professional who returns to a project on Monday does not
re-read every file; they remember decisions, recall learned shortcuts, notice
"that number looks off," and absorb a teammate's "actually, priorities changed"
without rebooting their brain. That between-session cognition is what
distinguishes a long-running worker from a brilliant one-session contractor.

**Aion** supplies the missing subsystems. **StewardBench** measures whether they
matter — by scoring the *maintained work state across sessions*, not the final
answer of any one session, and by running episodic agents and Aion through the
identical task so the comparison is apples-to-apples.

---

## 2. The Aion architecture

Aion wraps a strong inner executor (it is *executor-agnostic* — the inner loop can
be our own ReAct loop or an external coding agent) with four persistent subsystems
and a control bus. The value is not the inner loop; it is everything around it.

```
                         ┌──────────────────────────────────────────┐
                         │              STEERING BUS                 │
   human / supervisor ──▶│  corrections · priority changes · vetoes  │◀── self-monitors
                         │  verification requests ◀── escalations     │   (drift, anomaly,
                         └────────────▲───────────────┬──────────────┘    loop, budget)
                                      │               │
                 reads working-set   │               │  posts/polls each step
                                      │               ▼
   ┌───────────────┐   episodes  ┌────┴───────────────────────┐   reward   ┌──────────┐
   │ MEMORY        │◀────────────│  EXECUTOR  (System-1 loop)  │──────────▶ │  CRITIC  │
   │ substrate     │─────────────▶│  tool use · context mgmt   │            │ self-eval│
   │ episodic      │ working-set └────────────────────────────┘            └────┬─────┘
   │ semantic      │                                                            │ skill
   │ procedural    │◀───────────────────────────────────────────────────────────┘ promotion
   │ open-loops    │                          ▲
   └──────▲────────┘                          │ writes lessons/beliefs/skills/handoff
          │                       ┌───────────┴─────────────┐
          └───────────────────────│  DREAM / CONSOLIDATION  │  (System-2, async, between sessions)
            prune · revise · skills│  + SECURITY GATE        │  replay → distill → revise → prune
                                   └─────────────────────────┘            → anomalies → handoff
```

### 2.1 Executor (System-1, within-session)

A tool-use loop that performs the task. Responsibilities unique to long-running
operation: **context management** (compaction / working-set selection to stay in
the model's "smart zone" instead of dumping everything), and **polling the
steering bus** each step so mid-run control is honored. The executor is a
*pluggable interface* — Aion can drive its own reference executor, or wrap an
external agent (this is how an external coding agent can run *inside* Aion and
inherit memory + dreaming).

### 2.2 Memory substrate (persistent, structured, queryable)

Not a flat log and not raw chat history. Four tiers, each a first-class store:

| Tier | Holds | Used for |
|---|---|---|
| **Episodic** | append-only steps, observations, decisions, outcomes | replay during the dream; audit |
| **Semantic** | beliefs/facts, each with `provenance`, `source_authority`, `confidence`, `timestamp`, `supersedes` | belief revision; grounding |
| **Procedural** | reusable skills/playbooks distilled from experience | do it right the first time next session |
| **Open-loops** | commitments + unresolved questions | continuity; nothing dropped silently |

Retrieval is **relevance × recency × authority** weighted and feeds a bounded
*working-set* into the executor's context — the agent loads what matters, not
everything. Beliefs are revised, never blindly overwritten: a new fact from a
higher-authority source `supersedes` the old one, leaving an auditable trail.

### 2.3 Dream / consolidation engine (System-2, offline, async)

Runs **between sessions**, while no events arrive — the architectural home of the
"dreaming" capability. It replays recent episodes and:

1. **distills procedural skills** (the offline half of the learning loop) —
   promotes strategies the critic rewarded into the skill library,
2. **revises beliefs** — reconciles contradictions using recency/authority,
3. **prunes & merges** stale/redundant memory (forgetting that *helps*, à la
   Memora/FAMA), so memory stays small and trustworthy,
4. **surfaces slow-burn anomalies** the busy day-loop missed,
5. **writes a handoff + morning brief** for the next session,
6. **runs the SECURITY GATE** — refuses to consolidate unverified or adversarial
   inputs (the anti-poison ledger). This is the load-bearing safety property:
   *the dream is the prime attack surface for a shared agent the team trusts, and
   it must not silently absorb a memory-poisoning attempt.*

### 2.4 Steering bus (runtime control — the most-missing piece)

A first-class channel for *mid-execution* control, unifying three things current
agents scatter or lack:

- **Human steering**: a correction, a changed priority, a preference, or a veto
  injected *while the agent runs*; the executor polls and reconciles without a
  restart.
- **Verification / escalation**: the agent pushes a high-risk decision onto the
  bus and blocks for a human verdict — calibrated, so it neither acts recklessly
  nor over-escalates.
- **Self-steering**: internal monitors (drift, anomaly, loop, budget) post signals
  that trigger re-planning. This is how the agent catches *itself* going off the
  rails.

Runtime steering is what makes the Direction-B "team works through one shared
agent and verifies it" loop actually controllable.

### 2.5 Critic / learning loop (online half)

After each session (optionally each step), the critic self-evaluates the
trajectory against the goal and policies, producing a reward signal that (a) gates
which strategies the dream promotes to the skill library, and (b) tunes
verification thresholds. Over many sessions, **experience → critic →
consolidation → better skills/policy → better next run**: the agent *gets better
at this specific workspace*, which is the defining behavior of a long-running
agent and is invisible to any single-session benchmark.

### 2.6 What "and others" covers

The brief's "other missing components" map onto: **context management /
compaction** (§2.1), **verification/escalation calibration** (§2.4), the
**security gate** (§2.3), **anomaly/drift detection** (§2.4 self-monitors), and
the **self-improving skill library** (§2.5). Aion's claim is that these are not a
grab-bag but a coherent set: the *between-session* loop a long-running agent needs.

---

## 3. StewardBench (benchmark v2): isolate, then compare

### 3.1 What it isolates

StewardBench scores the **maintained work state across sessions**, on nine axes
(see `BENCHMARK_SPEC.md`): goal progress, continuity, adaptation, verification
calibration, **dream consolidation**, **security & abuse resistance**, state
hygiene, efficiency, collateral damage. Every check is declarative and
state-based, so scores are reproducible and each emits a named failure mode. The
runnable MVP (`stewardbench/`) already demonstrates a 22→100 spread between a
naive forwarder and a good steward on the `launch_plan_under_drift` scenario.

### 3.2 Two long-running domains (the capstone deliverable scenarios)

- **Coding campaigns.** A real git repo + a sequence of sessions across simulated
  days: implement a feature → a requirement changes → a dependency bump
  introduces a regression → a refactor → a security patch → a handoff. Success
  requires remembering prior design decisions, *not re-breaking past work*,
  reflecting drift, reusing learned facts instead of re-investigating, and leaving
  a clean state. Scored on the nine axes **plus** code-specific checks:
  tests-pass, **regression avoidance** (didn't break previously-green tests),
  **skill reuse** (didn't redo known investigations), and no secret/PII leakage.
- **Research campaigns.** A living literature review / data-analysis memo over
  days, with new evidence, contradicted claims, source-reliability changes, and a
  slow-burn anomaly in the data. Scored on evidence tracking, belief revision,
  anomaly detection, citation integrity, and handoff.

Each campaign injects at least one **adversarial event** (prompt injection in a
fetched page / issue comment, or memory poisoning) and one **slow-burn signal**,
so dreaming and security are tested *inside* real coding/research work, not in
isolation.

### 3.3 Comparing external agents fairly

A uniform adapter interface drives every agent through the identical campaign:

```python
class AgentAdapter:
    def run_session(self, task, workspace, steering) -> SessionResult: ...
```

The harness owns the workspace and replays the between-session event trace, so
**every agent gets the same repo/state each session** — the workspace is the only
fair shared substrate. Episodic agents (Claude Code, Codex, OpenClaw, Hermes) must
maintain continuity *through the workspace and their own native memory (e.g.
`CLAUDE.md`, `/resume`)*; Aion additionally uses its private memory/dream/steering.
The benchmark then answers the empirical question directly: **does the
between-session machinery measurably improve long-running coding/research
performance over strong episodic agents?**

> Honesty note: adapters for the external CLIs require those tools installed and
> are provided as documented integration points; the harness, the scoring, and
> the Aion adapter are real and runnable today. Running the full external
> comparison is the Week-2 experiment, not a Week-1 claim. (See the research
> appendix for how each external agent is driven headlessly.)

### 3.4 Metrics for the comparison

Per campaign, per agent: the nine-axis StewardBench score, the code/research
domain checks, **and a "continuity premium"** — the score delta between *fresh
context each session* and *the agent's own memory carried across sessions*. The
continuity premium is the headline number: it quantifies how much an agent's
between-session cognition is worth. Aion's hypothesis is a large positive premium;
episodic agents' premium should be near zero (they have little to carry).

---

## 4. Novelty / positioning (for a NeurIPS-style submission)

Verified prior art (see `SOURCES.md`, `RESEARCH_MEMO.md`) each owns one piece:
async environments (Gaia2/ARE), long-term memory & stale-belief updating
(LongMemEval, Memora/FAMA, RealMem), living-workspace updating (Workspace-Bench),
long-term coherence (Vending-Bench), security-agent eval (SoK/CLASP),
human-time-calibration (METR/HCAST). **None** assembles, as scored capabilities,
the combination StewardBench targets — *and* none pairs the benchmark with an
**architecture that makes offline consolidation and runtime steering first-class,
security-gated subsystems.* Two contributions are genuinely fresh:

1. **Dreaming as a scored, security-gated capability** — consolidation that must
   *refuse poison*, evaluated on outcomes in the maintained state.
2. **Runtime steerability as a measured property** of long-running agents, via a
   first-class steering bus, tied to the "verify, don't redo" Direction-B loop.

The defensible empirical claim: *episodic frontier agents underperform on
long-running campaigns, and a between-session architecture closes a measurable
fraction of the gap.* That is a paper.

---

## 5. Feasibility, scope, and risk (honest)

| Risk | Mitigation |
|---|---|
| "Beat Claude Code on coding" is very ambitious | Reframe the claim as the *continuity premium*, not raw single-session coding skill. Aion can even *wrap* a strong executor, so it competes on memory/steering, not raw model strength. |
| Full workspace + repo simulation is large | Start from the working StewardBench harness (done). Coding campaigns reuse a small fixture repo + real `pytest`. |
| Running 4 external CLIs reliably | Adapters are isolated; degrade gracefully. Report whatever subset runs; never fake a number. |
| Scoring long-running behavior is subjective | Keep checks declarative + state-based; report failure taxonomy; collect a small human baseline. |
| Scope creep across two big artifacts | The artifacts share a spine (the harness). Ship the architecture + StewardBench-coding MVP first; external comparison second. |

### What exists today (Week 1)
StewardBench harness + one full continuity scenario + nine-axis scoring + 3
baseline agents + passing tests **(done)**, and the Aion framework scaffold with a
working memory/steering/dream/critic loop that runs on the benchmark **(this
commit)**.

### Roadmap
1. Aion subsystems as real code; AionAgent scores well on `launch_plan_under_drift`. *(this commit)*
2. Coding-campaign environment (fixture repo + `pytest` + event trace) and the `AgentAdapter` interface. *(next)*
3. Research-campaign environment.
4. External adapters (Claude Code headless, Codex exec, OpenClaw, Hermes) + the continuity-premium experiment.
5. Human baselines, ablations (memory off / dream off / steering off), write-up.

---

## 6. Deliverables

- **Agent framework code** — `aion/` (the architecture, general-purpose, executor-agnostic).
- **Benchmark** — `stewardbench/` (harness, scenarios, scoring, adapters).
- **Results** — the continuity-premium comparison across agents on coding + research campaigns.
- **Paper** — the thesis, the architecture, the benchmark, the ablations.

See `IMPLEMENTATION.md` to run what exists; `BENCHMARK_SPEC.md` for the scoring;
`SOURCES.md` / `RESEARCH_MEMO.md` for the verified related-work delta.
