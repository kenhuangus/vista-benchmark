# Research Memo: Long-Running and Long-Horizon Agent Benchmarks

## Executive Summary

The benchmark landscape is moving from static question answering toward realistic agent work. The strongest recent benchmarks test web navigation, desktop control, coding tasks, terminal workflows, tool use, workplace simulation, human-calibrated time horizons, and asynchronous environments.

The opportunity for a new capstone benchmark is not "make tasks longer." That is crowded and easy to attack. The defensible gap is persistent continuity: evaluating whether an agent can act as a reliable steward of shared work across time, interruptions, changed facts, and human verification checkpoints.

StewardBench should position itself as a benchmark for agent continuity under organizational drift.

## What Existing Benchmarks Measure

| Benchmark | What it tests | Relevance | Gap for StewardBench |
|---|---|---|---|
| WebArena | Realistic web tasks in reproducible websites | Shows agents struggle with complex web workflows | Mostly bounded task episodes, not persistent team state |
| OSWorld | Multimodal computer-use tasks across real desktop apps | Strong model for execution-based verification | Focuses on computer control, not long-lived organizational memory |
| AppWorld | API-based app world with realistic users and state tests | Good precedent for controllable simulated apps | Tasks are rich but not centered on multi-day stewardship |
| tau-bench | Tool-agent-user interaction and policy following | Useful model for consistency over repeated trials | Conversation episodes, not persistent project continuity |
| SWE-bench / Terminal-Bench | Real technical work with automated tests | Shows how to package verifiable hard tasks | Narrower technical environments, less social/asynchronous context |
| TheAgentCompany | Simulated software company with web, code, and coworkers | Closest prior art for workplace realism | Evaluates professional tasks, not primarily continuity as the target capability |
| METR Time Horizons / HCAST | Human-calibrated task duration and autonomy | Best framework for relating performance to human work time | Mostly clean, self-contained tasks; authors note real jobs are messier |
| Vending-Bench | Long-term coherence in a simple business simulation | Direct evidence that agents can derail over long horizons | Single business loop, not shared team work with verification |
| Gaia2 | Dynamic asynchronous environments | Strong support for time-flowing worlds | General dynamic scenarios, not specifically shared workplace stewardship |
| Odysseys | Long-horizon multi-site web tasks with rubric scoring and efficiency | Strong scoring precedent for long workflows | Open-web research/use tasks, not persistent institutional memory |

## Key Lessons

### 1. Realism matters, but it must be scoped

WebArena and OSWorld show that realistic environments expose failures that synthetic tasks miss. TheAgentCompany shows the same for professional work. But realistic full-stack environments are expensive to build. For this capstone, a controlled API-based workspace can be more defensible than a fragile browser clone.

### 2. Binary success is too crude

TheAgentCompany uses partial credit, AppWorld uses state-based tests, and Odysseys argues for rubric-based scoring in long-horizon tasks. StewardBench should use multi-axis scoring: final outcome, continuity, verification, recovery, efficiency, and collateral damage.

### 3. Human calibration makes claims legible

METR and HCAST make a compelling move: evaluate AI tasks by how long skilled humans take. StewardBench can borrow this by estimating human time for each scenario and reporting success by duration bucket. Even a small capstone version can collect rough human baselines from team members.

### 4. Long-running is not the same as long-horizon

A long-horizon task can still be one clean episode. A long-running task has time, interruptions, state drift, and new information. Vending-Bench and Gaia2 are important because they test what happens when the world keeps moving.

### 5. The new benchmark should measure the work state, not just the answer

In real teams, an agent can produce a correct final answer while leaving the shared workspace confused, undocumented, or unsafe. StewardBench should score the maintained state as a first-class artifact.

## Proposed Gap Statement

Existing benchmarks ask whether an agent can complete bounded tasks in realistic environments. StewardBench asks whether **one shared agent the team only verifies** (capstone Direction B) can preserve and improve a shared work state while the environment changes over time — including while it consolidates asynchronously (dreaming) and while it is under attack.

This is defensible because it isolates a deployment-critical capability:

- continuity across sessions
- memory use without blind trust in memory
- appropriate human verification
- recovery from stale assumptions
- handoff quality
- auditability
- low collateral damage
- **asynchronous consolidation** that prunes staleness and catches slow-burn anomalies
- **abuse resistance under continuity**, where the dream itself is the prime attack surface

## Novelty Delta vs The Closest Prior Art

The honest read after a citation-verified prior-art pass: the four-part construct
(preserve commitments + update stale assumptions + verify at the right moment +
clean handoff) does not appear assembled in one benchmark, but each pillar is
individually claimed by recent work. StewardBench's defensible novelty is the
**combination plus the scoring target**, and two pillars the brief demands that
prior art does not cover.

| Closest prior art | Owns | What StewardBench adds |
|---|---|---|
| Gaia2 / ARE (2602.11964 / 2509.17158) | asynchronous, dynamic environments | grades a persistently *maintained shared artifact* across the session, not per-scenario success; adds dream + security axes |
| LongMemEval (2410.10813) | "knowledge updates" in long chat memory | a shared editable workspace + drift events + handoff, not Q&A over chat history |
| Memora / FAMA (2604.20006) | penalizing reliance on stale memory | the same pruning, but inside an *asynchronous dream*, plus resistance to memory-*poisoning* |
| RealMem (2601.06966) | cross-session, project-oriented memory | scores the *work state itself*, not responses to queries about memory |
| Workspace-Bench (2605.03596) | updating a large living workspace | continuity over time under *injected async change*, not single-shot static tasks |
| SoK / CLASP (2510.01654) | evaluating closed-loop security agents | security as one axis of *stewardship*, with the dream as the attack target |

The two freshest contributions: **the asynchronous dreaming phase as a scored
capability**, and **the dream as a security attack surface** (memory poisoning
that only pays off if it is consolidated as a durable lesson while no human is
watching). The "ask-for-verification-at-the-right-moment" behavior is the
least-covered of the stewardship pillars and is worth emphasizing.

## Benchmark Design Principles

1. Use realistic but controlled workspaces.
2. Make time and events first-class.
3. Evaluate state, not just messages.
4. Include changed facts and stale assumptions.
5. Reward concise verification, not maximal autonomy or maximal escalation.
6. Use reproducible event traces.
7. Use task families with several variants to reduce overfitting.
8. Report efficiency and continuity separately from final success.

## Research-Informed Positioning

StewardBench should not claim to replace WebArena, OSWorld, TheAgentCompany, Gaia2, or Odysseys. It should claim a narrower missing capability:

"Can a long-running shared agent remain a trustworthy steward of evolving work?"

That is the philosophical difference. The agent is not being evaluated as a solo problem solver. It is being evaluated as infrastructure for a team.

## MVP Recommendation

Build a small but deep benchmark:

- 3 domains
- 3 to 4 scenarios per domain
- 6 to 12 simulated hours or days per scenario
- 20 to 60 events per scenario
- automated verifiers plus rubric checkpoints
- at least 2 agent baselines

The quality bar should be: after a run, a human can inspect the workspace and understand what happened, what remains unresolved, and whether the agent made the team more or less capable.

