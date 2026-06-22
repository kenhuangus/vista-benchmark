#!/usr/bin/env python3
"""Export the VISTA journey corpus to a HuggingFace-loadable dataset.

The corpus (:mod:`journeys.corpus`) is a *pure function* — three hand-authored
domain seeds on disk plus three synthesized journeys, each proven valid
(fail->pass) before inclusion. This script materializes it as line-delimited JSON
so it can be published as a HF dataset and loaded with::

    from datasets import load_dataset
    ds = load_dataset("<user>/vista-bench-corpus")

It writes, next to this file:

* ``vista_corpus.jsonl``        — every journey, one JSON object per line;
* ``splits/<split>.jsonl``      — the same journeys grouped by train/dev/test/challenge;
* ``dataset_summary.json``      — counts by domain / split + the schema key list.

Run from the repo root::

    python huggingface/build_dataset.py
"""

from __future__ import annotations

import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from journeys.corpus import full_corpus, by_split, summary  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))


def _write_jsonl(path: str, rows) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def main() -> int:
    corpus = full_corpus()
    _write_jsonl(os.path.join(_HERE, "vista_corpus.jsonl"), corpus)

    splits_dir = os.path.join(_HERE, "splits")
    os.makedirs(splits_dir, exist_ok=True)
    for split, rows in by_split().items():
        _write_jsonl(os.path.join(splits_dir, f"{split}.jsonl"), rows)

    summ = summary()
    summ["schema_keys"] = sorted(corpus[0].keys())
    summ["journey_ids"] = [j["id"] for j in corpus]
    with open(os.path.join(_HERE, "dataset_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summ, fh, indent=2, sort_keys=True)

    print(f"wrote {len(corpus)} journeys -> huggingface/vista_corpus.jsonl")
    print(f"splits: { {k: len(v) for k, v in by_split().items()} }")
    print(f"domains: {summ['by_domain']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
