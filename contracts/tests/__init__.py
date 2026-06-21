"""Contract-test suite for VISTA Bench (C1-C6).

The named tests here ARE the CI merge gate (architecture.md §6, plan.md §6).
Trivially-true checks (schemas load, stubs import, capability split holds) are
GREEN now; behavior owned by S1/S2 is marked ``skipTest('pending S1/S2')`` until
those seats land it.
"""
