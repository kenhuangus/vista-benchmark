"""Human-validated subset — does the deterministic oracle agree with human judgment?

A scoring oracle is only credible if its verdicts match what an expert reviewer
would conclude. This package holds a small, individually-adjudicated GOLD set
(``validation/gold/human_validated_subset.json``) and an agreement harness
(:mod:`validation.agreement`) that runs the oracle on each case and compares its
verdict to the human label, per dimension.

Honesty: the gold labels are **author-adjudicated** (``adjudicated_by: author``,
``review_status: author_gold``) with a written rationale per case, structured so
an independent reviewer can confirm or overturn each one. This is a seeded v0 gold
set in the SWE-bench-Verified spirit — not a claim of blind third-party annotation.
"""

from validation.agreement import (
    adjudicate,
    load_gold,
    run_validation,
)

__all__ = ["adjudicate", "load_gold", "run_validation"]
