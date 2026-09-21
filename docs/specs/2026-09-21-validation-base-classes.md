# Spec: add the two base classes needed by the offline validation pack

Worktree: `.worktrees/validation-base-classes` (branch `w-validation-base-classes`).
May touch ONLY src/craftoracle/pob_bases.py (descriptive text), tools/build_pob_bases.py,
tests/test_pob_bases.py, data/pob_bases.json.

## Why
GOAL2 requires real amulet and boots cases. Existing literal projection already parses both
files; extend the selected inputs, not parser semantics or item eligibility.

## Requirements
1. Append amulet.lua and boots.lua to the five selected source files, preserving their order.
   The lead supplies all seven raw files inside your worktree. No network or other sources.
2. Regenerate own JSON with the existing parser/provenance. Update misleading five-file
   comments in the allowed files. No resolver or crafting-rule changes.
3. Extend the real fixture with counts, hashes, first/last records, missing fields and
   first-record tag checks below. Retain existing validation and duplicate-name checks.
4. Run focused tests/test_pob_bases.py only; compare two actual builder outputs byte-for-byte.
   Do not add dependencies. No large re-audit: existing parser is accepted.

## Facts and numbers a test must reproduce
PoB Data/Bases literal files, owner-supplied2.67.2/PoE3.29, read2026-09-21:
- amulet105 records/96 distinct names; first Paua Amulet at line6, last Monkey Paw Talisman (Frenzy).
  SHA256 dcc6f48d8a7aaea4d75a18b0557ca1f8bfceaf6e83e5b83638b7745d03cf850c.
  subType missing20, socketLimit missing105. Paua type Amulet, subType/socketLimit null,
  tags amulet=true/default=true, eight influenceTags, shaper=amulet_shaper.
- boots81/81; first Iron Greaves at line6, last Golden Caligae.
  SHA256 7634f2c366c79a83614520dbee74239fd3a742a4297d1e1c166a78610be68eb7.
  subType missing1, socketLimit missing0. Iron Greaves type Boots, subType Armour,
  socketLimit4, tags armour/boots/default/str_armour=true, eight influenceTags,
  shaper=boots_shaper.
- Seven-file counts95/29/48/123/80/105/81 =561 records and548 distinct names.
  Original five-file records/fields remain byte-equivalent after JSON parsing.
This is a literal source projection, not approval of every projected base for ordinary crafting.

## Numbers to report
Counts, first/last names, hashes, missing-field counts, total/distinct names, deterministic
byte comparison and pytest summary. Report commit/files/questions. Final begins
`=== FINAL REPORT ===`.
