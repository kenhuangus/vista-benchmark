"""VISTA Bench multi-run harness + results archival (S6).

Turns single scorecards into reproducible, versioned benchmark numbers:
``pass^k`` reliability across the corpus and a ``results/v{X.Y}/{bench}-…json``
archive. See :mod:`bench.runner`.
"""

from bench.runner import (
    BENCH_NAME,
    VISTA_VERSION,
    archive,
    run_benchmark,
    run_journey_k,
)

__all__ = [
    "BENCH_NAME",
    "VISTA_VERSION",
    "archive",
    "run_benchmark",
    "run_journey_k",
]
