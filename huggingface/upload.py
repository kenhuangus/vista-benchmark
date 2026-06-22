#!/usr/bin/env python3
"""Push the VISTA corpus to a HuggingFace dataset repo.

Prerequisites:
  * ``pip install huggingface_hub``
  * a write-scoped token in ``HF_TOKEN`` (or ``--token``), or ``huggingface-cli login``.

Regenerate the data first, then upload::

    python huggingface/build_dataset.py
    HF_TOKEN=hf_xxx python huggingface/upload.py --repo kenhuangus/vista-bench-corpus

The card (``README.md``), ``vista_corpus.jsonl``, the per-split files, and the
summary are uploaded; nothing else in the folder is.
"""

from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="Upload the VISTA corpus to HuggingFace.")
    p.add_argument("--repo", required=True,
                   help="HF dataset repo id, e.g. kenhuangus/vista-bench-corpus")
    p.add_argument("--private", action="store_true", help="create the HF repo private")
    p.add_argument("--token",
                   default=os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
                   or os.environ.get("HUGGING_FACE_HUB_TOKEN"))
    args = p.parse_args()

    if not args.token:
        sys.exit("No HF token found. Set HF_TOKEN (write scope) or pass --token, "
                 "or run `huggingface-cli login` first.")
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("huggingface_hub not installed. Run: pip install huggingface_hub")

    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(here, "vista_corpus.jsonl")):
        sys.exit("vista_corpus.jsonl missing — run `python huggingface/build_dataset.py` first.")

    api = HfApi(token=args.token)
    api.create_repo(args.repo, repo_type="dataset", private=args.private, exist_ok=True)
    api.upload_folder(
        folder_path=here,
        repo_id=args.repo,
        repo_type="dataset",
        allow_patterns=["README.md", "vista_corpus.jsonl", "splits/*.jsonl",
                        "dataset_summary.json"],
        commit_message="Publish VISTA Bench corpus",
    )
    print(f"published: https://huggingface.co/datasets/{args.repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
