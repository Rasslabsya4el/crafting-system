# Spec: keep rule-mutation regression on a hand-checkable tiny pool

Worktree: `.worktrees/bound-cache-regression` (branch `w-bound-cache-regression`).
May touch ONLY `tests/test_policies.py`. Five-minute task; no production changes.

## Why
Final394-test suite is green but takes1.036minute. Its rule-cache test alone repeats
two full helmet enumerations (0.104minute); the real helmet fixture already verifies
the accepted numbers. D23 requires bounded regression workloads with numerical coverage.

## Requirements
1. Replace ONLY the fixture inside test_cache_key_changes_when_action_rules_change
   with tiny synthetic ActionData and a target requiring modifier A. Keep exercising the
   real _chaos_policy with the same caller cache and mutated ActionData rules object;
   never mock the distribution or cache implementation.
2. Two eligible equal-weight modifiers A/B in distinct Prefix groups. Caps3/3.
   First rare_count_weights {"1":1}: target probability1/2. Mutate that same rules
   object to {"2":1}: target probability1. Each complete outcome then has A and B.
   These are mathematical fixtures, not claims about actual rare mod counts.
3. Assert the two exact probabilities and corresponding fixed Chaos means using
   setup Alchemy0.5, Chaos1, base0:2.5 then1.5. Assert changed raw distributions and
   separate cache entries. Include a docstring with this hand derivation/spec pointer.
4. Leave every other test and all real helmet assertions unchanged. Remove an import
   only if this replacement makes it unused. Run this test and the whole test_policies
   module; do not run full suite or any full plan.

## Facts and numbers to report
No new game rules; this tests cache freshness from changed resolved draw counts.
Report p1/2→1, mean2.5→1.5, cache size, focused test summary/time in minutes,
commit and changed file. Final begins `=== FINAL REPORT ===`.
