# Spec: literal base-tag projection for five equipment classes

Worktree `.worktrees/pob-base-tags`, branch `w-pob-base-tags`. Target 15 minutes; report a blocker
instead of expanding scope. May touch ONLY `src/craftoracle/pob_bases.py`,
`tools/build_pob_bases.py`, `tests/test_pob_bases.py`, `data/pob_bases.json`.

## Why
Phase 0 requires base tags for a five-class mod cross-check. Extract literal PoB data without
deciding weight precedence, item eligibility, influence or tier rules. BRIEF 3b remains the core
contract: these data must not be filtered to a particular desired item or utility threshold.

## Requirements
1. Read `docs/WORKER_RULES.md` and AGENTS sections 1,2,3,5. Standard library only, offline, no Lua
   execution/eval or subprocesses except ordinary tests/Git. No files outside this worktree.
2. Build only helmet.lua, bow.lua, ring.lua, body.lua, gloves.lua, in that explicit order, from
   `sources/pob/Data/Bases/`. Lead supplies ignored copies and ModExplicit for existing tests.
   Generated files assign multiline objects to `itemBases["Name"]`. Use a string-aware balanced
   reader to isolate each record. Comments, braces inside quoted strings and nested tables must
   not corrupt boundaries. Only header `local itemBases = ...`, blank lines and full-line comments
   are allowed outside records. Reject unexpected outside content and malformed/unclosed records
   with source file and line. Do not execute or interpret the remaining fields.
3. Extract literal `name`, `type`, optional `subType` (absent -> null), optional `socketLimit`
   (absent -> null), `tags` (string -> bool map), `influenceTags` (string -> string map),
   and `source` with relative file path and one-based line of assignment. Only top-level fields
   count. Required fields absent/duplicate, duplicate source path/line identities and malformed
   projected values must fail. Do not assign default sockets or infer class from the filename.
4. Retain every record, including unusual/legacy/not_for_sale tags; do not filter availability.
   Document the limited projection (no defence/weapon properties, implicit text, reqs or resolver).
5. CLI `python tools/build_pob_bases.py`, anchored to its own worktree, no args, import side-effect
   free. Root JSON has schema_version 1, projection_fields, sources (ordered metadata per file:
   path, raw-byte sha256, record_count), pob_version 2.67.2, poe_version 3.29,
   version_authority "AGENTS.md section 1 (owner supplied; upstream revision unverified)",
   bases in file/source order. Deterministic sorted keys, UTF-8/LF/trailing newline, no timestamps.
   Validate all inputs before replacing output. Nothing from CoE is copied.
6. Tests first with authored tiny fixtures: nested ignored tables, quoted braces, order/provenance,
   absent optional fields, repeated names retained, duplicate source identities, bad required maps, unclosed record and unexpected
   outside content. Source lines must refer to text.splitlines() positions (raw decoded source).
   Real build twice, byte compare. Existing suite remains green. Do not change lead docs.
7. Commit allowed explicit paths only; final report with hash, tests, elapsed minutes, all numbers,
   any unsupported syntax/questions; starts `=== FINAL REPORT ===`.

## Facts and numbers to test/report
Lead read local PoB S1 files 2026-09-20. Values are file observations, not eligibility rules.
Counts / first / last / raw SHA-256:
- helmet: 95, Iron Hat / Golden Wreath,
  bb5f8a66c491ae5073350d9c5b0c45edafc137712d5a555435a9421d0419db8e
- bow: 29, Crude Bow / Ethereal Bow,
  ad420096d028a4aadaef230e880f7b9d5feb57fbe8613d8e3722b3b4238e38f0
- ring: 48, Iron Ring / Jet Ring,
  6db93137a173e81f2e16374ba96e845536004903bc01f12443bd754785bca86d
- body: 123, Plate Vest / Golden Mantle,
  b764b6065a41af36d8433dd26838a6290ce0abd17431c3b7090ab935534f9557
- gloves: 80, Iron Gauntlets / Golden Bracers,
  6c251c4582062109de151ad9c7b5bf9583c4b51fb6fa27e7f9d1648d6ead2217
Total 375 records, no skips; 371 distinct display names. Ring has 48 records / 44 names:
Two-Stone Ring occurs at lines 105/114/123, Shadowed Ring at 312/321/330.
Retain all occurrences: identity is (source.path, source.line), not display name. No Lua execution
or overwrite semantics are inferred. Duplicate source identities fail. This correction was made
after worker found the counterexample and lead verified the raw file; D9 records the choice.
Iron Hat: type Helmet, subType Armour, sockets 4, exactly 4 tags
{armour:true, default:true, helmet:true, str_armour:true}; 8 influence tags,
shaper -> helmet_shaper. Crude Bow: type Bow, null subType, sockets 6,
6 tags {bow,default,ranged,two_hand_weapon,twohand,weapon}: all true; 8 influence tags.
Iron Ring: type Ring, null subType and socketLimit, tags {default:true,ring:true}.
Missing subType counts: 1/29/48/0/1 for helmet/bow/ring/body/gloves (79 total).
Missing socketLimit counts: 0/0/48/0/0 (48 total).
Synthetic one comment/header/record layout: assert exact assignment line and 2 ordered records;
4 invalid classes minimum (duplicate source identity, malformed tags, unclosed record, unexpected outside).
A repeated-name fixture must yield 2 records with different source lines; never collapse them.
Report source hashes, output hash, all counts/keys above, deterministic comparison result.
