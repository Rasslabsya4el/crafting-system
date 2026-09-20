# Spec: source-preserving weighted modifier family projection

Worktree: `.worktrees/pob-mod-families` (branch `w-pob-mod-families`). You may touch ONLY:
`src/craftoracle/pob_mod_families.py`, `tools/build_pob_mod_families.py`,
`tests/test_pob_mod_families.py`, `data/pob_mod_families.json`.

## Why
Close the remaining weighted-table portion of Phase 0 and preserve stat text that the initial
explicit projection omitted. This is literal extraction, not a pool resolver or game-rule implementation.
Budget: about 30 minutes; no single command over 10 minutes. All inputs are copied into this worktree.

## Requirements
1. Parse the generated literal rows of ModExplicit, ModVeiled, ModEldritch, ModCorrupted,
   ModDelve and ModSynthesis in sources/pob/Data. Never execute Lua or use network.
2. Preserve source order and exact IDs. Every record contains source_path/source_line,
   id/type/affix/level/group, ordered weightKey/weightVal/modTags, ordered top-level unnamed
   stat strings as stat_text, and ordered statOrder integers. Preserve optional tags,
   weightMultiplierKey/weightMultiplierVal literally; use null for absent fields, not invented defaults.
   Numeric ranges remain literal text; do not infer numeric stat IDs, tiers or exclusions.
3. Read fields at the row's top level; nested tradeHashes strings are NOT stat_text.
   Respect quoted commas/braces and escaped quotes. A bounded literal parser is sufficient.
   Malformed required/projected fields, duplicate IDs in one file, duplicate projected keys,
   unequal parallel weight arrays, non-row content inside the returned table, missing closure,
   or unsupported expressions in projected values raise ValueError with source line. No silent skips.
   Unknown unprojected fields may be skipped structurally. Existing modules are read-only.
4. Deterministic own JSON, UTF-8 LF sorted keys/2-space indent/newline. Root schema_version,
   projection_fields, sources (path, byte SHA-256, record_count), mods; version metadata PoB 2.67.2,
   PoE 3.29, authority owner-supplied snapshot, upstream revision unverified (Q8).
   IDs only unique within source: never collapse across files. File order is the order in requirement 1.
5. CLI defaults to the repo-local inputs/output; report counts, zero skips/errors and SHA-256.
   Test authored tiny fixtures including malformed structure and duplicate keys, then frozen snapshot counts.
   Missing ignored snapshots may skip ONLY snapshot tests with a clear reason. No game rules in code.

## Facts this implements
S1/S24/S25 and local named files, read 2026-09-20. These fields are datamined definitions,
not evidence of current accessibility or unveil/synthesis probabilities. See mechanics/pool_resolution.md
Q16/Q17, mechanics/veiled.md, mechanics/patch_3_29.md. Empty/all-zero weights MUST remain so.

## Numbers a test must reproduce
Lead counted literal rows from source on 2026-09-20:
- Explicit 4310; Veiled 258 (162 Prefix/96 Suffix); Eldritch 4086 (2016 Exarch/2070 Eater);
  Corrupted 371; Delve 186 (9 DelveImplicit/74 Prefix/103 Suffix); Synthesis 1344. Total 10555.
- Every file starts its first row at line 5. Veiled first row has 2 stat strings,
  statOrder [1869,1877], weights [0,0]; ID JunMasterAvoidStunAndElementalStatusAilments1.
- Eldritch first ID IncreasedAttackSpeedEldritchImplicit1 has level 75, stat text
  '8% increased Attack Speed', weightVal [0,1000,0]. Source row 5.
- Synthesis first ID SynthesisImplicitLife1 has both weight arrays empty and stat text
  '+(8-10) to maximum Life'. Source row 5. Do not invent a default weight.
- An authored fixture with one top-level stat 'Adds (1-2), {test}' and one nested tradeHashes
  text projects exactly 1 stat string; duplicate IDs and mismatched arrays each raise ValueError.
- Two independent builds produce byte-identical output.

## Numbers to report
Counts per file and total; type counts above; first-row fixture values; skipped/malformed rows;
optional-field present counts per file; two-build equality; output bytes/SHA-256; exact pytest summary;
commits and files changed. Final report starts `=== FINAL REPORT ===`.
