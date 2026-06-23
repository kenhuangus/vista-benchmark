# Oracle label validity — why the deterministic gold label is trustworthy

A reviewer's sharpest question about VISTA is: *the gold label is a hand-built
graph oracle with no human annotators — why should we believe it?* This document
answers that. The short version: VISTA's labels are correct **by construction and
by proof**, not by human agreement, and that is a stronger guarantee than
inter-annotator consensus — not a weaker one.

## 1. The label is the generative ground truth, not a post-hoc judgement

In a human-labeled benchmark (SWE-bench, GAIA, WebArena) the task exists first and
a label is *attached afterwards* by an annotator who may be wrong, may disagree
with another annotator, and may be gamed by a solution that "looks right." The
label is an estimate of a hidden truth.

VISTA inverts this. Each journey is produced by `journeys/synth.py::synthesize_journey`
from a single `JourneySpec`, which emits **both** the agent-visible guardrail graph
**and** the hidden oracle layer — the `optimal_walk` (the cost-minimal safe route)
and `subgoal_states` (the gold checkpoints on that route) — from the same
generative act. The oracle is not an opinion about the journey; it *is* the journey's
construction. There is no hidden truth being estimated, because the truth is what
built the task.

This is the τ²-bench discipline (arXiv 2506.07982): generate the task and its oracle
together so validity is a property of the generator, not of a downstream labeler.

## 2. Every label is *proven* valid before it is used (fail→pass)

Construction alone is not enough — a buggy generator could emit an oracle that does
not actually solve its own task. So every journey passes a constructive proof before
it enters any corpus. `journeys/generator.py::verify_journey` compiles three atomic
pieces from the journey's oracle layer and checks a **validity gap**:

- **init** — the empty starting state (`position = entry`, no subgoals reached).
- **solution** — one step-applier per edge of the hidden `optimal_walk`; each moves
  position and records the gold subgoal its guard names.
- **assertion** — the goal-reached predicate: `position == goal` **AND** every gold
  subgoal in memory **AND** no forbidden node ever crossed.

A journey is **verified** iff the assertion **FAILS on `init`** and **PASSES after
the solution** (`GenerationResult.verified`). That single gap discharges three
correctness obligations at once:

1. the goal is non-trivially reachable (it is *not* already satisfied at the start);
2. the `optimal_walk` actually reaches the goal (the label solves its own task);
3. the gold subgoals genuinely fire along that walk (the checkpoints are real).

`journeys/synth.py::generate_verified` **raises** if `verified` is false, so an
invalid journey can never reach the corpus. The scaled corpus
(`journeys/scaled_corpus.py`, 96 journeys) is built entirely through this gate, and
`journeys/tests/test_scaled_corpus.py` re-proves all 96 on every test run. The seed,
hand-authored, and synthesized journeys all pass the *same* prover
(`journeys/tests/test_generator*.py`). The label correctness is therefore mechanically
checked, every run, for every task — a guarantee no human-labeled benchmark can make.

## 3. Determinism removes labeler variance entirely

Because the scorer (`harness/scorer.py`) is a pure function of `(route_graph,
trajectory)` — no LLM judge, no RNG, no wall-clock (NFR-1) — there is **zero
measurement variance** in the label. Two consequences:

- There is no inter-annotator disagreement to report, because there is one oracle
  and it is proven. The analogue of "annotator agreement" here is "the verifier
  passes," which it does for 100% of the corpus by construction.
- All variance in a reported score is the *model's*, never the instrument's. A
  difference between two agents is a real behavioral difference, not labeling noise.
  This is what makes the deterministic reference separation (Ranger recall 1.0 vs
  naive 0.0 on every one of the 96 journeys, `analysis/SCALED-STATS.md`) a
  zero-variance result rather than a noisy one.

## 4. What this establishes — and what it does not

**Internal validity (established).** The labels are correct for what they measure:
the optimal walk is a valid safe solution, the subgoals are real checkpoints on it,
the forbidden/HITL structure is exactly as declared, and the metric reads them off a
trajectory without noise. This is proven per task, every run.

**Construct reliability (established).** Zero measurement variance; perfectly
reproducible; difficulty is an explicit, monotone construct (tier = gold-subgoal
count, 3→6).

**External / ecological validity (NOT established here).** That the abstract
route-graph construct *predicts real-world agent foresight and safety* on messy,
natural tasks is a separate empirical claim. By-construction validity cannot settle
it; only convergence with independent measures can. We treat this honestly:

- `analysis/VALIDITY.md` reports the tractable convergent/discriminant evidence:
  the axes dissociate (an agent can be high on goal-progress yet low on
  verification-calibration — they are not redundant), and the difficulty construct
  behaves as designed.
- Correlating VISTA rankings against an *external* agent benchmark on the *same*
  models is the decisive convergent-validity test. It is compute-bound (many models
  × both harnesses) and is named as the primary open item, not quietly assumed.

## 5. Why by-construction validity is a feature, not a fallback

Human-labeled benchmarks buy ecological validity at the price of label noise,
annotator drift, contamination, and gameability. VISTA makes the opposite trade: it
gives up (for now) natural-task realism to buy a label that is *provably* correct,
*perfectly* reproducible, and *impossible* to game by "looking right" — the trajectory
either crosses the proven subgoals on the proven walk or it does not. For a benchmark
whose whole purpose is to measure foresight and safety *deltas between agents* with no
instrument noise, a proven deterministic oracle is the right ground truth. Pairing it
with the external-correlation study (§4) is what turns internal rigor into a full
validity argument — and that pairing is the stated roadmap, not an afterthought.

---

*Sources: τ²-bench generate-with-verifier (arXiv 2506.07982); the prover is
`journeys/generator.py::verify_journey` (the fail→pass gap is
`GenerationResult.verified`); the scaled corpus is built through
`generate_verified` and re-proven by `journeys/tests/test_scaled_corpus.py`.*
