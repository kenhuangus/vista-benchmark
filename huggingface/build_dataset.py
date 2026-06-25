#!/usr/bin/env python3
"""Export the VISTA journey corpus to a HuggingFace-loadable dataset.

The published dataset is the union of two provably-valid sources:

* **curated** (6) — `journeys.corpus.full_corpus()`: 3 hand-authored domain seeds +
  3 canonical synthesized journeys (the set the analysis/leaderboard reports cite).
* **synthesized-scaled** (384) — `scaled_corpus(per_cell=4, domains=ALL_DOMAINS)`:
  the parametric synthesizer swept over a stratified grid
  `6 domains × 4 splits × 4 difficulty tiers × 4 attack vectors`. The first three
  domains are the fixed analysis core; finance / legal / support broaden the published
  corpus (held to the same fail→pass + reference-premium bar — see
  `journeys/tests/test_scaled_corpus.py::TestExtendedDomains`).

= **390 journeys**, and **every one is re-proven valid (fail→pass) at build time**
(`journeys.generator.verify_journey`) before it enters the file — so the published
labels are correct *by construction*, not asserted (see `docs/oracle-validity.md`).
Determinism (NFR-1): the corpus is a pure function, byte-identical every build.

It writes, next to this file:

* ``vista_corpus.jsonl``    — every journey, one JSON object per line, each enriched
  with provenance columns (``source``, ``difficulty_tier``, ``num_subgoals``,
  ``num_high_risk_forks``, ``attack_asi``, ``verified``);
* ``splits/<split>.jsonl``  — the same journeys grouped by train/dev/test/challenge;
* ``dataset_summary.json``  — counts by domain / split / source / tier / ASI + schema.

Run from the repo root::

    python huggingface/build_dataset.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from journeys.corpus import full_corpus  # noqa: E402
from journeys.scaled_corpus import scaled_corpus, ALL_DOMAINS  # noqa: E402
from journeys.generator import verify_journey  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))

# 6 domains × 4 splits × 4 difficulty tiers × 4 attack vectors = 384 scaled journeys.
_SCALED_PER_CELL = 4
_SCALED_DOMAINS = ALL_DOMAINS


def _source(jid: str) -> str:
    if jid.startswith("scaled-"):
        return "synthesized-scaled"
    if jid.startswith("synth-"):
        return "synthesized-core"
    return "handauthored"


def _tier(jid: str) -> str:
    return jid.rsplit("-", 2)[1] if jid.startswith("scaled-") else "curated"


def _attack_asi(journey: dict) -> str | None:
    for e in journey.get("event_trace", []):
        if e.get("type") == "injection":
            return e.get("asi")
    return None


def _enrich(journey: dict) -> dict:
    rg = journey["route_graph"]
    return {
        **journey,
        "source": _source(journey["id"]),
        "difficulty_tier": _tier(journey["id"]),
        "num_subgoals": len(rg.get("subgoal_states", [])),
        "num_high_risk_forks": sum(1 for e in rg.get("edges", []) if e.get("risk") == "high"),
        "attack_asi": _attack_asi(journey),
        "verified": True,
    }


def build_corpus() -> list[dict]:
    """The full published corpus, every journey re-proven valid (fail→pass) and
    enriched with provenance columns. Pure + deterministic; raises if any journey
    fails verification or any id collides (the export is self-gating)."""
    raw = list(full_corpus()) + list(scaled_corpus(_SCALED_PER_CELL, domains=_SCALED_DOMAINS))
    rows: list[dict] = []
    for j in raw:
        res = verify_journey(j)
        if not res.verified:
            raise AssertionError(f"journey {j['id']} failed fail->pass verification")
        rows.append(_enrich(j))
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        dupes = [i for i, c in Counter(ids).items() if c > 1]
        raise AssertionError(f"duplicate journey ids in dataset: {dupes}")
    return rows


def build_summary(rows: list[dict]) -> dict:
    def counts(key):
        return dict(sorted(Counter(r[key] for r in rows).items()))
    # The parametric grid only (domain x split x difficulty tier); the 6 curated rows
    # are not grid points, so they are excluded — this is the systematic-coverage number.
    base_configs = {
        (r["domain"], r["split"], r["difficulty_tier"])
        for r in rows if r["source"] == "synthesized-scaled"
    }
    return {
        "total": len(rows),
        "by_domain": counts("domain"),
        "by_split": counts("split"),
        "by_source": counts("source"),
        "by_difficulty_tier": counts("difficulty_tier"),
        "by_attack_asi": dict(sorted(Counter(r["attack_asi"] for r in rows if r["attack_asi"]).items())),
        "num_base_task_configurations": len(base_configs),
        "num_attack_asi_categories": len({r["attack_asi"] for r in rows if r["attack_asi"]}),
        "all_verified": all(r["verified"] for r in rows),
        "schema_keys": sorted(rows[0].keys()),
        "journey_ids_sample": [r["id"] for r in rows[:12]],
    }


def _write_jsonl(path: str, rows) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def main() -> int:
    rows = build_corpus()
    _write_jsonl(os.path.join(_HERE, "vista_corpus.jsonl"), rows)

    splits_dir = os.path.join(_HERE, "splits")
    os.makedirs(splits_dir, exist_ok=True)
    by_split: dict[str, list[dict]] = {}
    for r in rows:
        by_split.setdefault(r["split"], []).append(r)
    for split, srows in by_split.items():
        _write_jsonl(os.path.join(splits_dir, f"{split}.jsonl"), srows)

    summ = build_summary(rows)
    with open(os.path.join(_HERE, "dataset_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summ, fh, indent=2, sort_keys=True)

    print(f"wrote {len(rows)} journeys -> huggingface/vista_corpus.jsonl (all verified)")
    print(f"by source: {summ['by_source']}")
    print(f"by domain: {summ['by_domain']}  by split: {summ['by_split']}")
    print(f"by tier: {summ['by_difficulty_tier']}  ASI categories: {summ['num_attack_asi_categories']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
