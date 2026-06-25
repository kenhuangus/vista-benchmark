---
license: cc-by-4.0
language:
  - en
pretty_name: VISTA Bench Corpus
size_categories:
  - n<1K
task_categories:
  - other
tags:
  - agents
  - llm-agents
  - agent-benchmark
  - ai-safety
  - long-horizon
  - prompt-injection
  - planning
  - evaluation
configs:
  - config_name: default
    data_files:
      - split: train
        path: splits/train.jsonl
      - split: dev
        path: splits/dev.jsonl
      - split: test
        path: splits/test.jsonl
      - split: challenge
        path: splits/challenge.jsonl
---

# VISTA Bench Corpus

**A deterministic benchmark for long-running agents — scoring *foresight × safety*
over a long horizon, not just task success.**

VISTA Bench asks the question ordinary pass/fail metrics don't:

> *Could a team run on one shared agent that does most of the work while people only
> verify it — and would you trust it over a long horizon?*

Most agent benchmarks ask **"did the agent finish the task?"** VISTA instead scores
the **route** the agent took, deterministically, against a hidden ground-truth
oracle: *did it show foresight, escalate at the genuine high-risk forks, resist
injected attacks, and stay safe along the way — or did it get there recklessly?*

This repository hosts the **journey corpus** — the dataset the benchmark runs over.
The scorer, reference agent, and harness live in the
[GitHub repo](https://github.com/kenhuangus/vista-benchmark).

---

## What's in the dataset

Each row is one **journey**: a long-horizon task encoded as a *sanctioned
route-graph* plus a hidden answer key. **198 journeys**, and **every one is re-proven
valid (fail→pass) at build time** — so the published labels are correct *by
construction*, not asserted.

| source | count | how it's made |
|---|---|---|
| `handauthored` | 3 | hand-written domain seeds (project / coding / research), contract-validated |
| `synthesized-core` | 3 | the canonical synthesized journeys the leaderboard cites |
| `synthesized-scaled` | 192 | the parametric synthesizer over a stratified grid (below) |

The **synthesized-scaled** set is a `3 domains × 4 splits × 4 difficulty tiers × 4
attack vectors` sweep (= 54 base task-configurations × 4 injected attacks). Difficulty
is the number of hidden gold subgoals on the optimal walk (**3 → 6**, `easy → expert`):
a longer optimal walk demands longer-horizon foresight. Coverage:

- **domains** (66 each): project · coding · research
- **splits** (~49–51 each): train · dev · test · challenge
- **difficulty** (48 each + 6 curated): easy(3) · medium(4) · hard(5) · expert(6) subgoals
- **attacks** — 9 of the 10 OWASP Agentic-Security categories: **ASI01–ASI09**

Every record also carries provenance columns for filtering — `source`,
`difficulty_tier`, `num_subgoals`, `num_high_risk_forks`, `attack_asi`, `verified` —
alongside the journey fields below. Full breakdown in `dataset_summary.json`.

```python
from datasets import load_dataset

ds = load_dataset("<user>/vista-bench-corpus")        # splits: train / dev / test / challenge
expert = ds["test"].filter(lambda r: r["difficulty_tier"] == "expert")
asi01  = ds["train"].filter(lambda r: r["attack_asi"] == "ASI01")
```

(Or read the line-delimited JSON directly: `vista_corpus.jsonl`, or per-split files
under `splits/`.)

---

## The route-graph — two layers that play opposite roles

A journey ships a route-graph with an **agent-visible** layer and a **hidden
oracle** the agent never sees. The scorer reads the hidden layer to grade the
agent's realized trajectory.

| field | role | shown to agent? |
|---|---|---|
| `route_graph.nodes` | states: `task` / `hitl` / `escape` / `absorbing` / `forbidden` | ✅ visible |
| `route_graph.edges` | sanctioned transitions with `guard`, `authority`, `cost`, `risk` | ✅ visible |
| `route_graph.entry` / `goal` | start and the *intended* absorbing state | ✅ visible |
| `route_graph.optimal_walk` | the cheapest sanctioned path (the foresight target) | ❌ **hidden oracle** |
| `route_graph.subgoal_states` | ordered checkpoints for the progress metric | ❌ **hidden oracle** |
| `oracle_bindings` | per-axis ground truth: high-risk forks, forbidden set, canary tokens | ❌ **hidden oracle** |
| `event_trace` | the in-world event stream: facts, the injected payload, policy drift | ✅ visible (payload is *untrusted*) |
| `initial_route_state` | starting memory / docs / messages | ✅ visible |
| `intent` | natural-language task statement | ✅ visible |
| `horizon` | step budget | ✅ visible |

> ⚠️ **The corpus ships the answer key.** `optimal_walk`, `subgoal_states`, and
> `oracle_bindings` are the hidden oracle. To evaluate an agent fairly, strip them
> from the view you hand the model (the reference harness does this via
> `journeys.loader.visible_view`). They are included here so the dataset is
> self-contained and the oracle is auditable.

---

## What the benchmark measures (the scoring axes)

The deterministic scorer grades each trajectory on continuous axes — **no
LLM-as-judge, no RNG, no wall-clock**:

| axis | question |
|---|---|
| **axis01** goal_progress | reached the *intended* absorbing state (not a hijack)? |
| **axis02** foresight | progress over hidden subgoals + optimality gap vs the optimal walk |
| **axis03** alignment_drift | off-walk drift + blocked forbidden crossings (safe escalation excused) |
| **axis06** verification_calibration | escalate at the `risk:high` forks and *not* elsewhere (precision/recall) |
| **axis07** security_abuse_resistance | targeted-ASR + canary egress under the injected attack |
| **axis10** self_improvement_safety | does self-improvement preserve the no-new-forbidden-path invariant? |
| **pass^k** | binary-predicate reliability over repeated runs |

**The headline result the dataset is built to expose:** on every journey, a *naive*
agent and a *careful* agent **both pass** the binary predicate — they are separated
only by `axis06` (calibrated escalation), where the careful agent scores **1.0** and
the naive one **0.0**. Same pass/fail, opposite trustworthiness.

---

## Intended use & limitations

- **Use.** Benchmarking long-horizon agent foresight, calibrated escalation,
  prompt-injection resistance, and self-improvement safety against a single
  deterministic, by-construction-valid oracle. Research on the science of agent
  evaluation.
- **Scale.** 198 journeys (6 curated + 192 synthesized) — comparable in size to
  τ-bench (~165) and AgentDojo (~97). The corpus is **parametric**: the 192 derive from
  a small, transparent set of domain templates × 4 difficulty tiers × 4 attack vectors,
  so the count reflects *systematic coverage of those axes* rather than 198 independent
  hand-written tasks. The generator (`journeys/scaled_corpus.py`) is open and extends to
  more domains / attacks / tiers on demand.
- **Validity.** Every journey is re-proven (fail→pass) at build time, and the long-view
  premium (careful vs naive on `axis06`) holds on **all** of them — the powered
  counterpart of the headline result. Internal validity (labels correct) and construct
  reliability (zero measurement variance) are established; external validity against a
  real-world agent benchmark is the stated open item (see `docs/oracle-validity.md` in
  the repo).
- **Scope.** English; three white-collar domains (project / coding / research); injected
  attacks map to OWASP **ASI01–ASI09** (ASI10 Rogue-Agents not yet covered).
- **Not** a real-world PII dataset — all entities are synthetic (fictional account ids /
  `@*.test` addresses used as attack canaries).

---

## Citation

```bibtex
@misc{vistabench2026,
  title  = {VISTA Bench: A Deterministic Benchmark for Foresight and Safety in Long-Running Agents},
  author = {Huang, Ken and contributors},
  year   = {2026},
  howpublished = {\url{https://github.com/kenhuangus/vista-benchmark}}
}
```

Design rationale and the head-to-head against prior agent benchmarks (WebArena,
TheAgentCompany, AgentDojo, METR/HCAST, Vending-Bench, Gaia2/ARE, SAHOO, DGM, STOP)
are in `benchmark-design.md` and `SOURCES.md` in the GitHub repo.

*License: CC-BY-4.0 (dataset). Regenerate from source with
`python huggingface/build_dataset.py`.*
