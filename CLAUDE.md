# CLAUDE.md — VISTA Bench operating rules

> Loads in every Claude Code session rooted at `C:\Users\kenhu\vista-benchmark`.
> User-level and direct user instructions override this file; otherwise this
> file overrides default behavior.

VISTA Bench is a **deterministic benchmark for long-running agents** — it scores
*foresight × safety* over a long horizon, not just task success — plus **Ranger**,
a 3-role reference agent. The headline result is the one pass/fail cannot see: on
every journey the naive and careful (Ranger) agents **both pass** the binary
predicate, separated only by the continuous `verification_calibration` axis
(Ranger 1.0 vs naive 0.0).

This is a **research artifact aimed at publication** (NeurIPS D&B / ICLR / AAAI /
ICML). Correctness, determinism, and honesty of reported results matter more than
speed. Never fabricate or hand-tune a result.

---

## Non-negotiables

### Determinism (NFR-1) — the core invariant
- The **scorer and journeys** must be a pure function of `(agent, journey, seed)`:
  **no LLM-as-judge, no RNG, no wall-clock** in any scoring path. Same inputs →
  byte-identical scorecard.
- `Date.now()` / `Math.random()` / argless `new Date()` equivalents are forbidden
  in `harness/` and `journeys/`. The only sanctioned wall-clock is the **archival
  timestamp** in `--bench` results (never a score input; injectable for tests).
- The **analysis layer** (`analysis/`) may use a **fixed-seed** bootstrap
  (`random.Random(0)`) — that is deterministic and reproducible. Never an unseeded
  RNG, never a wall-clock that changes output.

### The two-graph model
- Each journey is a sanctioned route-graph with **two layers**: an *agent-visible*
  guardrail view, and a *hidden oracle* (`optimal_walk` + ordered `subgoal_states`).
  **The agent never sees the oracle.** The scorer reads the hidden layer to grade
  the realized trajectory. Do not leak oracle fields into anything the agent reads.

### Generate-with-verifier (label validity)
- Every journey ships an `(init, solution, assertion)` triple and is **proven valid**
  before use: the goal assertion FAILS on the empty init and PASSES after the optimal
  walk (the fail→pass gap). `journeys/synth.py::generate_verified` raises if a journey
  doesn't verify — an invalid journey must never enter a corpus. Labels are correct
  *by construction*, not by assertion (see `docs/oracle-validity.md`).

### Honest results
- **No fake green.** Don't skip failing tests, weaken assertions, or mock away the
  behavior under test. If a test pins a fragile stochastic value that drifts on
  re-run, replace it with the robust qualitative invariant — don't delete coverage.
- Generated reports (`analysis/*.md`) must be **data-driven** — narratives derive
  from the artifacts they read, never hardcoded numbers that can drift from their
  own tables.
- Document verification gaps explicitly (missing creds, flaky CLI, compute limits).

---

## Stack & layout

- **Pure Python 3 standard library — no dependencies, no install.** Tests are
  `unittest`. Run the whole suite: `python -m unittest discover -s . -p 'test_*.py'`.
- The suite must be **green before any commit** (0 failures, 0 unexpected skips).

```
contracts/    C1–C6 frozen contracts (route_state, route-graph, tools, rubric, adapter, journey)
harness/      deterministic spine: runtime, scorer, security oracle, RSI gate (axis10), scheduler
agents/       NaiveAgent + RangerAgent (Scout/Worker/Dreamer) + the harness adapter + llm_agent
journeys/     corpus: hand-authored seeds, parametric synthesizer, generate-with-verifier, scaled_corpus
bench/        pass^k multi-run driver + versioned results archival
analysis/     pure-stdlib analysis + report generators (RESULTS.md, SCALED-STATS.md, VALIDITY.md, AB7…)
experiments/  model-run drivers (passk_run, security_run, scaled_run, prompt_ablation_run)
validation/   human-validated gold subset + oracle-vs-human agreement harness (+ FINDINGS.md)
vista_run.py  the CLI (single / --compare / --corpus / --bench / --rsi / --validate)
results/      archived runs (GITIGNORED — never commit)
submissions/  conference paper drafts
docs/         oracle-validity.md, scaled-corpus.md, …
```

The 7 axes (axis01 goal_progress, axis02 foresight, axis03 alignment_drift, axis06
verification_calibration, axis07 security_abuse_resistance, axis10
self_improvement_safety, pass^k) and the 3-role Ranger (Scout has authority; Worker
and Dreamer do not) are documented in `README.md` and `benchmark-design.md`.

---

## Running model experiments (the LLM agents)

- `experiments/*_run.py` drive real model CLIs. **claude / gemini run via WSL**
  (`wsl -d Ubuntu …`; claude on subscription, gemini on Vertex/GCP credits → $0);
  **grok runs native on Windows** (OAuth, `~/.grok/bin/grok.exe`, $0).
- **Cost awareness:** gemini and grok are ~$0; **Claude Opus/Sonnet/Haiku passk
  re-runs cost real money** (a full 3-model passk sweep ≈ $6). Confirm before large
  paid re-runs.
- **WSL flakiness:** long multi-journey **stepwise** sweeps intermittently die with
  `Wsl/Service/E_UNEXPECTED` and write nothing. Mitigation: **split the sweep
  per-journey/per-domain** (each invocation ~10–15 calls is survivable) and merge
  the JSONs; planning-seam runs (one call/journey) are far more robust than stepwise.
- Model results live under `results/` (gitignored). Reports regenerate from them via
  `analysis/*.py`. After a scorer change, re-run affected models and regenerate the
  reports — don't leave a committed report inconsistent with the fixed scorer.

---

## Git

- **No AI attribution, ever** — never add `Co-Authored-By: Claude …` or
  `🤖 Generated with Claude Code` to any commit message, PR title/body, or comment.
  A factual model-name mention in methodology (e.g. "scored gemini-2.5-flash") is not
  attribution and is fine.
- **Direct-merge to `main` is the norm here** (private repo, solo author) — commit
  and push straight to `main` when the suite is green; no PR required.
- Commit format: `type(scope): short description`
  (e.g. `fix(scorer): close the degenerate-recall loophole in axis06`).
- **Never commit** `results/`, secrets/credentials, or `.env` files. Keep only
  NAMES of secrets in docs, never values.
- Remote: `https://github.com/kenhuangus/vista-benchmark.git`.

---

## Loop

For any feature/fix: clarify scope → add/adjust a `unittest` test for the boundary
you're changing → implement the smallest correct change → run the focused tests then
the full suite → for benchmark-semantics changes (scorer, journeys, axes) re-run the
affected model experiments and regenerate the reports → update the relevant
`docs/`/`analysis/` artifacts in the same change → commit. Keep paths **absolute**
when surfacing them.
