# Spec: retain every cell of the cached CoE metamod table

Worktree: `.worktrees/coe-metamod-table` (branch `w-coe-metamod-table`).
You may touch ONLY `src/craftoracle/coe_metamods.py`, `tools/build_coe_metamods.py`,
`data/rules/coe_metamods.json`, `tests/test_coe_metamods.py`.

## Why
Owner answer 10 requires the complete S14 matrix, including qualifications. This is a
literal source observation, not a declaration that every historical action exists today.

## Requirements
1. Parse ONLY the cached HTML with Python standard-library HTMLParser. No network or browser.
   Lead supplies `sources/raw/coe/metamods.html` inside this worktree. Keep third-party HTML
   ignored. Produce our own JSON representation of factual table cells, not CoE application code.
2. Preserve source order, the four column labels, every action label, and group headings.
   Use `General` for the unheaded first group. Each action has exactly four cells, each with
   its literal CSS status (`yes`, `no`, `na`, `yesno`, or empty string), note text (empty when
   absent), and source line. Preserve typos and asymmetries; do not interpret or correct them.
3. Include S14 id, URL https://www.craftofexile.com/?page=metamods, cache path, original read
   date 2026-09-20, extraction date 2026-09-21, SHA256 of input, and the complete warning
   text with whitespace normalized. Confidence `reimplemented-from-CoE`; scope explicitly
   `frozen-source-observation`, with current-game applicability requiring a lead fact sheet.
4. Builder CLI accepts input and output paths; deterministic bytes on repeated builds.
   Missing/duplicate columns, unknown status class, malformed row dimensions, missing
   warning or table must fail explicitly. A blank source status must remain blank, not false.
5. Tests cover structural validation with small inline HTML fixtures and the committed
   132-cell data. Source-dependent reproducibility test can use the supplied cache in this
   worktree. Do not run the whole repository suite: run this focused test module only.

## Facts this implements
S14 `sources/raw/coe/metamods.html`, table `mmode_none coe_tbl`, read by lead 2026-09-21.
`docs/mechanics/bench_metamods.md` explains why source-cell classes and notes both matter.
No game rules or confidence decisions beyond the explicit source-observation scope above.

## Numbers a test must reproduce
- 33 action rows x 4 metamods = 132 cells; 33 cells contain a note.
- Groups: General 16, Harvest 10, Beastcrafting 2, Scourge 2, Eldritch 3.
- Eldritch Chaos Orb: statuses `no,no,"",""` (two unknown cells).
- General Fossils and Essences: `no,no,na,na`, all four notes `Prevents usage`.
- Harvest Reroll and Reroll+: `yes,yes,yesno,yesno`; last two notes
  `Only for the first added modifier`.
- General Veiled orb: `yes,yes,no,no`.
- Beastcrafting Suffix > Prefix: caster column literally says
  `Will not protects attack mods from removal`; preserve the source typo.
- SHA256 `979a268175e91f2a073545dd50df7ef62054cdb8382e06e36e92efb62f384aef`.

## Numbers to report
Rows, columns, cells, nonempty notes, blank statuses, group sizes, SHA256 and pytest summary.
Report commits and files. No edits to lead-owned docs. Final report begins `=== FINAL REPORT ===`.
