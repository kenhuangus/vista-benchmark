# VISTA scaled corpus catalog

**96 journeys**, each PROVEN valid (fail->pass) by the generate-with-verifier (`journeys.synth.generate_verified`) before inclusion — labels correct *by construction* (see `docs/oracle-validity.md`). Generated deterministically by `journeys/scaled_corpus.py` (NFR-1: byte-identical every run).

- by domain: {'project': 32, 'coding': 32, 'research': 32}
- by split: {'train': 24, 'dev': 24, 'test': 24, 'challenge': 24}
- by difficulty tier (= gold-subgoal count): {'easy': 3, 'medium': 4, 'hard': 5, 'expert': 6} x {'easy': 24, 'medium': 24, 'hard': 24, 'expert': 24}

Stratification grid: 3 domains x 4 splits x 4 tiers x 2 variants = 96. Within a stratum, variants rotate the attack vector (ASI category) and guard vocabulary, so journeys are genuinely distinct.

| id | domain | split | tier | #subgoals | attack ASI |
|---|---|---|---|---|---|
| `scaled-project-train-easy-00` | project | train | easy | 3 | ASI01 |
| `scaled-project-train-easy-01` | project | train | easy | 3 | ASI03 |
| `scaled-project-train-medium-00` | project | train | medium | 4 | ASI01 |
| `scaled-project-train-medium-01` | project | train | medium | 4 | ASI03 |
| `scaled-project-train-hard-00` | project | train | hard | 5 | ASI01 |
| `scaled-project-train-hard-01` | project | train | hard | 5 | ASI03 |
| `scaled-project-train-expert-00` | project | train | expert | 6 | ASI01 |
| `scaled-project-train-expert-01` | project | train | expert | 6 | ASI03 |
| `scaled-project-dev-easy-00` | project | dev | easy | 3 | ASI01 |
| `scaled-project-dev-easy-01` | project | dev | easy | 3 | ASI03 |
| `scaled-project-dev-medium-00` | project | dev | medium | 4 | ASI01 |
| `scaled-project-dev-medium-01` | project | dev | medium | 4 | ASI03 |
| … | | | | | |

*(first 12 of 96 shown; full set is enumerable via `scaled_specs()`)*

Note: `full_corpus()` remains the curated 6-journey contract set (stable invariant tests + model leaderboard); this scaled corpus is the powered reference set for per-stratum statistics (threat §1).

