# Sources

Verified citations for VISTA Bench. Every arXiv id below was checked against its
live arXiv abstract page.

## Long-Horizon and Long-Running Agent Benchmarks

- TheAgentCompany: Benchmarking LLM Agents on Consequential Real World Tasks
  - https://arxiv.org/abs/2412.14161
  - Workplace simulation with web browsing, coding, running programs, and coworker communication.

- Odysseys: Benchmarking Web Agents on Realistic Long Horizon Tasks
  - https://arxiv.org/abs/2604.24964
  - 200 long-horizon web tasks from real browsing sessions; argues for rubric scoring and trajectory efficiency.

- Gaia2: Benchmarking LLM Agents on Dynamic and Asynchronous Environments
  - https://arxiv.org/abs/2602.11964
  - Dynamic asynchronous environments with temporal constraints, ambiguity, noise, and multi-agent collaboration.

- Vending-Bench: A Benchmark for Long-Term Coherence of Autonomous Agents
  - https://arxiv.org/abs/2502.15840
  - Long-running vending machine business simulation showing coherence failures over time.

- METR Task-Completion Time Horizons of Frontier AI Models
  - https://metr.org/time-horizons/
  - Human-time-calibrated task horizon methodology, updated May 8, 2026.

- Measuring AI Ability to Complete Long Tasks
  - https://arxiv.org/abs/2503.14499
  - Introduces 50-percent task-completion time horizon and reports rapid growth in agent task duration.

- HCAST: Human-Calibrated Autonomy Software Tasks
  - https://arxiv.org/abs/2503.17354
  - 189 tasks with human baselines across ML engineering, cybersecurity, software engineering, and reasoning.

- WebArena: A Realistic Web Environment for Building Autonomous Agents
  - https://arxiv.org/abs/2307.13854
  - Realistic reproducible web environments and functional-correctness evaluation.

- OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments
  - https://arxiv.org/abs/2404.07972
  - Real desktop and web app tasks across operating systems with execution-based evaluation.

- AppWorld: A Controllable World of Apps and People for Benchmarking Interactive Coding Agents
  - https://arxiv.org/abs/2407.18901
  - Controllable app world with state-based unit tests and collateral-damage checks.

- tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains
  - https://arxiv.org/abs/2406.12045
  - Simulated user conversations, API tools, domain policies, and reliability over repeated trials.

- Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces
  - https://arxiv.org/abs/2601.11868
  - Hard terminal tasks from real workflows with human-written solutions and tests.

- GAIA: a benchmark for General AI Assistants
  - https://arxiv.org/abs/2311.12983
  - Real-world assistant questions requiring reasoning, multimodality, web browsing, and tool use.

> Citation note: every arXiv id above was checked against its live arXiv abstract
> page. One title correction: 2503.14499 is "Measuring AI Ability to Complete Long
> Tasks" (no "Software"). The Gaia2 benchmark (2602.11964) and the ARE *platform*
> it runs in (2509.17158) are separate papers — both are cited below.

## Closest Prior Art (novelty positioning)

These are the nearest existing benchmarks to VISTA Bench's framing — scoring a
maintained, shared work state under asynchronous change, with dreaming and
security as axes. Each owns one piece; none assembles the whole. Cited here so the
proposal distinguishes itself honestly rather than ignoring overlap. (arXiv ids
below were each verified against the live abstract/listing.)

- ARE: Scaling Up Agent Environments and Evaluations (+ Gaia2 benchmark)
  - https://arxiv.org/abs/2509.17158 (platform) and https://arxiv.org/abs/2602.11964 (Gaia2)
  - Asynchronous, dynamic environments; 1,120 scenarios. Owns the "async world"
    axis VISTA Bench leans on. Difference: scores per-scenario task success, not a
    persistently maintained artifact across a long-running session, and has no
    dream phase or security-as-axis.

- LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory
  - https://arxiv.org/abs/2410.10813
  - 500 questions over multi-session chat histories; explicitly tests "knowledge
    updates". The canonical "update stale info" memory benchmark. Difference: Q&A
    over chat history — no workspace artifact, no async drift events, no handoff,
    no security.

- Memora — From Recall to Forgetting: Benchmarking Long-Term Memory for Personalized Agents
  - https://arxiv.org/abs/2604.20006
  - Introduces FAMA (Forgetting-Aware Memory Accuracy), penalizing reliance on
    obsolete/invalidated memory. Closest on "prune stale assumptions". Difference:
    measures a belief state about a *user*, not a shared editable workspace, and
    has no verification-prompting, dreaming, or adversarial dimension.

- RealMem: Benchmarking LLMs in Real-World Memory-Driven Interaction
  - https://arxiv.org/abs/2601.06966
  - 2,000+ cross-session, project-oriented dialogues with dynamic memory updating.
    Difference: scores *responses to queries* about memory, not the maintained
    state of a shared work artifact.

- Workspace-Bench 1.0: Benchmarking AI Agents on Workspace Tasks with Large-Scale File Dependencies
  - https://arxiv.org/abs/2605.03596
  - Realistic large workspaces where agents identify, reason over, and *update*
    file dependencies. Closest on "living workspace". Difference: single-shot,
    static per task — no asynchronous change arriving mid-run, no continuity of
    commitments over time, no dream, no security axis.

- SoK: Measuring What Matters for Closed-Loop Security Agents
  - https://arxiv.org/abs/2510.01654
  - Proposes CLASP, a framework for evaluating autonomous security agents across a
    closed reconnaissance→exploitation→remediation→validation loop. Relevant to
    VISTA Bench's *security* axis as prior art on evaluating security agents.
    (Note: an earlier research pass over-attributed "continuity-of-artifacts as a
    first-class metric" to this paper; the abstract does not use that framing, so
    we do not claim it as a continuity competitor.)

- REALM-Bench: Evaluating Multi-Agent Systems on Real-World, Dynamic Planning and Scheduling
  - https://arxiv.org/abs/2502.18836
  - Dynamic planning/scheduling with disruptions. Adjacent on "dynamic plans";
    differs in that it targets multi-agent planning, not a single shared agent
    stewarding an auditable workspace under verification.

