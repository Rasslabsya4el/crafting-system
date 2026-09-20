# Spec: deterministic source-linked projection of PoB explicit rows

Worktree: `.worktrees/pob-explicit-projection` (branch `w-pob-explicit-projection`).
Target: 15 minutes; report a blocker rather than broaden scope. You may touch ONLY
`src/craftoracle/pob_data.py`, `tools/build_pob_explicit.py`, `tests/test_pob_data.py`,
`data/pob_mod_explicit.json`. Do not change the existing smoke parser or lead docs.
The lead provides ignored `sources/pob/Data/ModExplicit.lua` in your worktree.

## Why
Phase 0 needs a repeatable data builder. The existing parser projects eight fields from one row;
wrap it to account for every row of this frozen file with provenance. This output is a limited
projection, not a complete mod-pool resolver or item model. BRIEF 3b distributions and value
tables are future consumers; never pre-filter this data to a particular target.

## Requirements
1. Standard library only, no network, Lua execution, eval, external paths or additional agents.
   Reuse `craftoracle.pob_row.parse_mod_row`; do not copy game tables or CoE data into code.
2. Pure function accepts source text and returns source-order rows with `source_line` plus the
   eight existing fields. Accept blank lines and full-line `--` comments, exactly one `return {`
   wrapper and its closing `}`. No rows before/after the wrapper. Reject an unexpected nonblank
   line, bad wrapper, malformed row, duplicate ID or empty file with line-bearing ValueError.
   Do not skip parser failures. This is explicitly a generated-file subset, not general Lua.
3. CLI: `python tools/build_pob_explicit.py` reads the in-worktree source and writes
   `data/pob_mod_explicit.json`. No arguments required. Paths are anchored inside this worktree,
   not the caller's current directory or the parent checkout. It must import cleanly with no
   build on import. Create the output only after successful parsing/validation.
4. JSON root: `schema_version:1`, `projection_fields` (the eight parser fields plus source_line),
   `source` with relative `path`, raw-byte SHA-256, `pob_version:"2.67.2"`,
   `poe_version:"3.29"`, `version_authority:"AGENTS.md section 1 (owner supplied; upstream revision unverified)"`,
   and `record_count`; `mods` with the source-order rows. Deterministic UTF-8, LF, trailing newline,
   sorted object keys and no build timestamp. No absolute path in output.
5. Do not infer tiers, ranges, eligibility, influence, first-matching-weight behavior or scores.
   The eight projected fields are literal source data. Mark the module/output documentation as
   incomplete for a resolver (stat lines and other source fields are not projected).
6. Tests first on tiny authored strings for wrapper/order/line provenance, duplicates, unexpected
   input, malformed rows, and deterministic serialization. Preserve existing tests. Also run
   the real build twice, confirm byte-identical output and all source rows accounted for.
7. Commit only explicit allowed paths. Final report begins `=== FINAL REPORT ===` and includes
   all numbers below, test summary, elapsed minutes, commit hash, files, and questions.

## Facts this implements
S1/S10 in `docs/SOURCES.md`; PoB data `ModExplicit.lua` keys Strength1, Strength8 and
DeepwaterSwordGrantedSkillGhostCannons. Lead counted and parsed 4310 rows on 2026-09-20,
zero failures, 4310 distinct IDs. Raw source SHA-256:
`6d400101f60ec48f854daad9a5ca2479b43e9e405f92724e80631b276eaf4568`.
These are file observations, not game rules. Test values below are directly from those keys.

## Numbers a test must reproduce / report
- Full file: 4310 rows, 4310 distinct IDs, 0 skipped rows, 0 parse failures; 9 projected fields
  per row including source_line. First row Strength1 at line 5; last row
  DeepwaterSwordGrantedSkillGhostCannons at line 4314.
- Strength1: level 1, 13 keys/13 weights, weight sum 8333, final/default weight 0.
- Strength8: level 74, group Strength, type Suffix.
- Last row: level 60, type Prefix, keys [deepwater_sword, default], weights [2500, 0], no modTags.
- Synthetic fixture with exactly one comment on line 1, return wrapper on line 2, two authored
  rows on lines 3/4, closing wrapper on line 5: 2 records, source_line [3,4], preserve order.
- Reject at least duplicate ID, unexpected line, missing wrapper, malformed row: 4 failures.
- Same validated input serialized twice: 1 byte-identity comparison. Real build twice: 1 more.
- Report source/output SHA-256, all counts/keys above, and complete pytest result.

Rules: `docs/WORKER_RULES.md` and AGENTS.md sections 1, 2, 3, 5.
