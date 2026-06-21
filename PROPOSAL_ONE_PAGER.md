# StewardBench: Proposal One-Pager

> Capstone **Direction B — "a philosophically different take on agents."**
> The brief asks: could a company survive if a team worked through one shared
> agent that did most of the work, and the team simply verified it? StewardBench
> is the benchmark that answers whether such an agent can be *trusted over time*.

## Pitch

We want to build StewardBench, a new benchmark for the shared "team agent".

Most agent benchmarks ask whether an agent can complete a bounded task. StewardBench asks whether one shared agent — the kind a whole team would work through and only verify — can act as a persistent steward of shared work over time. The agent must preserve context, update plans when facts change, ask humans for verification at the right moments, leave behind a workspace another human or agent can safely continue from, **consolidate asynchronously between days (dream)**, and **stay safe under attack** — including a memory-poisoning attempt aimed at that very dream.

## Why This Matters

Real organizations will not deploy agents only for clean one-shot tasks. They will want shared agents that sit inside projects, watch for updates, track unresolved work, coordinate handoffs, and keep momentum while humans are away.

That is a different capability than web browsing, coding, or tool calling. It is continuity.

## What We Will Build

A runnable benchmark environment with:

- simulated project workspace
- documents, tickets, messages, records, and deadlines
- asynchronous event stream over simulated days
- agent tools for reading, updating, messaging, and requesting verification
- an **asynchronous dreaming phase** between days for offline consolidation
- **adversarial security events** (prompt injection, impersonation, PII exfiltration, memory poisoning)
- automated scoring across nine axes including dream consolidation and security & abuse resistance
- 9 to 12 benchmark scenarios across project management, customer operations, and research stewardship

A working MVP already exists: a deterministic harness, one full scenario with
drift + security + a dream phase, three baseline agents, multi-axis scoring, and
a passing test suite. On that scenario the naive baseline scores 22/100 and the
good-steward reference scores 100/100 — the benchmark discriminates. (See
`IMPLEMENTATION.md`.)

## What Makes It New

StewardBench is not just a longer task benchmark. It evaluates the health of the maintained work state.

An agent can fail even if it produces a plausible final answer, because the benchmark checks whether it:

- remembered prior commitments
- revised stale assumptions
- handled conflicting messages
- escalated high-risk decisions
- avoided unnecessary human interruptions
- left an auditable handoff
- dreamed: consolidated lessons and caught a slow-burn anomaly while idle
- refused injection, impersonation, and a memory-poisoning attempt — leaking no PII

The naive baseline illustrates the philosophical point: it is *safe only by being
useless*. It forwards every message (including the injected PII) and stewards
nothing. In a Direction-B world you want the agent to do the work — and doing the
work is what creates the attack surface. StewardBench rewards agents that are safe
**and** useful.

## Research Foundation

The proposal builds on recent agent benchmarks:

- WebArena and OSWorld: realistic interactive environments
- TheAgentCompany: simulated workplace tasks
- METR/HCAST: human-calibrated autonomy and task time horizons
- Vending-Bench: long-term coherence failures
- Gaia2 / ARE: asynchronous dynamic environments
- Odysseys: long-horizon web tasks with rubric scoring and efficiency
- LongMemEval, Memora, RealMem: long-term memory and stale-belief updating
- SoK / CLASP: evaluating closed-loop security agents

The gap is persistent shared-work continuity — graded on the maintained state,
with an asynchronous dream phase and security as first-class axes. See
`SOURCES.md` and `RESEARCH_MEMO.md` for the head-to-head novelty delta.

## Demo Goal

By the final presentation, we will demo one long-running scenario where the shared agent starts with a project plan, receives changing stakeholder updates, detects stale assumptions, asks for one targeted human verification, refuses an impersonated request to leak a customer's SSN, refuses a memory-poisoning attempt during its nightly dream, surfaces a slow-burn signup decline while dreaming, updates the workspace, and leaves a handoff summary. We will run a naive baseline and the steward side by side and show the scoring report — not just whether the task was completed, but whether the agent made the team more reliable. The MVP already produces this report today.

