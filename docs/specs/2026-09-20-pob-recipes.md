# Spec: literal bench and essence recipe projections

Worktree: `.worktrees/pob-recipes` (branch `w-pob-recipes`). You may touch ONLY:
`src/craftoracle/pob_recipes.py`, `tools/build_pob_recipes.py`,
`tests/test_pob_recipes.py`, `data/pob_bench.json`, `data/pob_essences.json`.

## Why
Close the two remaining differently shaped Phase 0 data tables. Preserve source definitions;
do not decide prices, eligibility beyond literal fields, or action probabilities.
Budget about 25 minutes; no single command over 10 minutes. Inputs are in this worktree.

## Requirements
1. Parse sources/pob/Data/ModMaster.lua and Essence.lua as bounded generated literal tables;
   no Lua execution/network. Existing modules may be read/reused but not changed.
2. Bench source has anonymous rows: preserve their 1-based source ordinal as source_index,
   source_path/source_line, type, affix, level, group, ordered modTags/statOrder, top-level
   unnamed stat strings as stat_text, and full types boolean map. Do not invent game IDs or weights.
3. Essence records have id, name, integer type, integer tier, full mods class->ID map,
   source_path/source_line. Preserve names/classes/IDs verbatim and source order.
4. Reject malformed required/projected fields, duplicate fields or map keys/essence IDs,
   non-row content inside return table, missing closure and unsupported projected expressions
   with ValueError identifying source line. Quoted commas/braces must not split strings.
   Nested strings must not enter bench stat_text. No silent skips; no interpreting expressions.
5. Separate deterministic own JSON outputs (UTF-8 LF sorted keys/2-space indent/newline).
   Each has schema_version, projection_fields, source path/byte SHA-256/record_count and
   version metadata PoB 2.67.2 / PoE 3.29, owner-supplied snapshot/upstream unverified (Q8).
   Arrays bench/essences retain source order. CLI defaults are repo local; report counts/hashes.
6. Tests first: authored small/malformed fixtures plus frozen source checks below. Missing
   ignored snapshots may skip only snapshot checks with an explicit reason. No prices or rule logic.

## Facts this implements
S1/S11 ModMaster.lua, S22 Essence.lua (read 2026-09-20); mechanics/bench_metamods.md and
mechanics/essences.md. Essence tier is the source field, NOT the numeric suffix of its ID.
Bench group is a PoB label, not independently proven complete exclusion families (Q16).

## Numbers a test must reproduce
- Bench: 732 rows, lines 5 through 736. First has source_index 1, type Prefix, affix Upgraded,
  level 15, group IncreasedLife, modTags ['resource','life'], statOrder [1594], stat_text
  ['+(15-25) to maximum Life'], types has 9 true entries including Helmet and Ring.
- Last row: source_index 732, line 736, group ItemGenerationCannotRollCasterAffixes,
  type Suffix, statOrder [24], stat_text ['Cannot roll Caster Modifiers'].
- Essence: 105 rows, lines 5 through 109; 2310 class->mod mappings, 22 per row.
  Tier counts: 1:4, 2:8, 3:12, 4:16, 5:20, 6:20, 7:20, 8:5.
- CurrencyEssenceRage4 (full Metadata/Items/Currency/ prefix) is Shrieking Essence of Rage,
  type 9, tier 6; Helmet maps Strength8. First ID CurrencyEssenceHatred1 tier 1/type 0;
  last CurrencyEssenceFaridun1 name Essence of Desolation/type 24/tier 8.
- Authored duplicated class key or essence ID and missing required field each raise ValueError.
  Authored one stat string containing a comma/brace remains exactly one stat string.
- Two builds produce byte-identical outputs for both files.

## Numbers to report
All counts/fixture values above; zero skips/errors; source hashes; output bytes/SHA-256;
two-build equality; exact pytest summary; commits/files changed. Report any unresolved shape
without guessing. Final report begins `=== FINAL REPORT ===`.
