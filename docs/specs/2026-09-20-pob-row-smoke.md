# Spec: parse one PoB modifier row to prove worker delegation

Worktree: `.worktrees/pob-row-smoke` (branch `w-pob-row-smoke`). Target duration: 5 minutes.
You may touch ONLY `src/craftoracle/pob_row.py`, `tests/test_pob_row.py`, and `pytest.ini`.
The lead provides an ignored copy of `sources/pob/Data/ModExplicit.lua` inside your worktree.

## Why
Prove the complete worker cycle before delegating larger data extraction: isolated worktree,
tests first, explicit commit, measured report, and lead acceptance. This is a limited parser smoke
test, not a complete Lua reader or a mod-pool resolver.

## Requirements
1. Read your local source row with key `Strength1`. Implement a pure
   `parse_mod_row(row: str) -> dict` in `src/craftoracle/pob_row.py`.
2. Return exactly the fields `id`, `type`, `affix`, `level`, `group`, `weightKey`,
   `weightVal`, `modTags`. Preserve array order and integer values. Do not resolve game eligibility.
   Other fields in the row (stat text, statOrder, tradeHashes) are outside this projection.
3. Support this single-line generated format, with quoted strings, decimal non-negative integers,
   and flat arrays for the requested fields. Never execute Lua or evaluate source code.
   Missing requested fields, a non-row input, or unequal weight-array lengths must raise `ValueError`.
   Document this limited scope; do not claim whole-file or general Lua support.
4. Write exactly two pytest test functions before implementation: the successful real `Strength1`
   projection and validation of missing `level` / unequal weights / non-row input (multiple assertions
   or parametrization inside the latter are acceptable). Each test names this spec or the PoB key as
   its source. Use the ignored local PoB file for the real row; no third-party fixture is committed.
   A missing local source should fail with an informative message, not silently pass.
5. `pytest.ini` may set `pythonpath = src`. No new dependencies. Run `python -m pytest -q`
   in your worktree, then commit only the three explicitly allowed paths. Do not edit lead docs.

## Facts this implements
Source S1: `sources/pob/Data/ModExplicit.lua`, key `Strength1`, line 5, read 2026-09-20.
Confidence: `datamined` for the recorded fields, with PoB version inherited from AGENTS.md
(v2.67.2 / PoE 3.29). Parsing does not establish any crafting rule.

## Numbers a test must reproduce
- `id = Strength1`, `type = Suffix`, `affix = of the Brute`, `level = 1`, `group = Strength`.
- `weightKey = [ring, amulet, belt, str_armour, str_dex_armour, str_int_armour,
  str_dex_int_armour, sword, mace, sceptre, staff, axe, default]`.
- `weightVal = [1000, 1000, 1000, 1000, 500, 500, 333, 500, 1000, 500, 500, 500, 0]`.
- `modTags = [attribute]`; 13 keys, 13 weights, weight sum 8333, 8 returned fields.
- Three malformed inputs (remove level, remove one weight, use `return {`) each raise `ValueError`.
All source numbers above are from S1 key Strength1; 8333 is the arithmetic sum of the listed weights.

## Numbers to report
1. Successful source rows parsed: 1.
2. Returned fields: 8.
3. Weight keys / values: 13 / 13; weight sum: 8333.
4. Level: 1; final default weight: 0.
5. Malformed inputs rejected: 3.
6. Test functions: 2; exact pytest summary; elapsed duration in minutes.

Rules of the house: `docs/WORKER_RULES.md`; AGENTS.md sections 1, 2, 3, 5; tests green;
explicit `git add` paths. Final message begins `=== FINAL REPORT ===` and includes every
required report field. No network, other processes, external paths, or additional agents.
