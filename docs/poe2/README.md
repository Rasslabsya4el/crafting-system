# Path of Exile 2 crafting knowledge (for a later port of the planner)

Everything known about crafting in Path of Exile 2, kept in the same formats as this repository's PoE1 knowledge, so that a port of the planner to PoE2 can start from it. Collected 2026-11-24 on the branch `claude/research-poe2-crafting-c00c9f`; no PoE1 code, data, test or doc is changed. **Version of every fact: PoE2 0.5.5.10 (patch line 0.5.5h; leagues Runes of Aldur and Forbidden Rites) unless a claim says otherwise. PoE2 1.0 launches 2026-12-11 with a new crafting system: refresh before porting** (`PORT-PLAN.md`, top).

Start with `PROGRESS.md` (summary in Russian for the owner, then the log).

## Index

| File | What it holds | PoE1 counterpart |
|---|---|---|
| `PROGRESS.md` | summary for the owner, running log, sources that refused | – |
| `PORT-PLAN.md` | PoE1 method → PoE2 (same / changed / gone / new), reusable action classes, what PoE2 breaks in the model, ranked unknowns | – |
| `METHODS.md` | every PoE2 method (P2-01 to P2-52, P2X rows): preconditions, outcome, cost unit, weights, proposed batch | `docs/research/2026-10-30-crafting-methods-inventory.md` |
| `DATA-PLAN.md` | which export gives which table, what is missing | ADR-0003, `src/crafting_system/data/PIN.json` |
| `GLOSSARY-POE2.md` | PoE2 terms in `GLOSSARY.md` form | `GLOSSARY.md` |
| `COMPLETENESS.md` | the completeness pass: 604 of 604 crafting items named by a claim | – |
| `claims/*.yaml` | 463 claims in 53 mechanic families, in the exact schema of the PoE1 rules registry (ADR-0004) | `src/crafting_system/rules/claims/` |
| `notes/*.md` | confidence (high/medium/low) per claim id, conflicts between sources, in-game checks | open sections of `docs/research/` notes |
| `research/*.md` | the raw research per area, with every source and quote: patch history, currency and omens, essences/augments/corruption/abyss, items and modifiers, data sources, Reddit evidence, the PoE1 format inventory | `docs/research/` |
| `../../research/poe2/data/` | `PIN.json` (repoe-fork/poe2 0.5.5.10 + 42 dat-export tables + Craft of Exile beta data), `fetch_poe2.py`, `derive_tables.py`, `completeness.py`, the official trade site's lists of 2026-11-24, readable extracts in `derived/` | `src/crafting_system/data/` |

## How to use the claims

They load with the PoE1 loader unchanged (it validates the schema):

```bash
OMP_NUM_THREADS=1 uv run --no-sync python -c "from pathlib import Path; from crafting_system.rules.registry import load_registry; print(len(load_registry(Path('docs/poe2/claims'))))"
```

`patch_verified` is the PoE2 version a fact is stated for (game data 0.5.5.10, or the patch whose notes say it); `history` keeps what a fact was before a patch; `approximate: true` marks every claim of medium or low confidence (the notes give which). `source_kind` follows ADR-0005: `datamined` (the game's own text and tables), `official` (patch notes), `wiki` (poe2db pages and guides), `coe` (Craft of Exile's PoE2 emulator code and data), `experiment` (large player samples, our own API reads).

To refresh after a patch: re-pin (`python -I research/poe2/data/fetch_poe2.py pin <repoe-fork/poe2 commit>`, and the dat-export commit in `PIN.json`), run `derive_tables.py` and `completeness.py`, and re-check every claim whose source changed.

## Paths and the PoE1 tests

No PoE1 test reads `docs/poe2/` or `research/poe2/`: the tests name single files under `docs/` and import from `research/312` and `research/376` only. The two repository-wide scans are respected: no YAML here has a top-level `requirements:` key (`tests/test_every_target_file_parses.py`), and no tracked file here holds an absolute path (`tests/test_no_absolute_paths.py`; every commit was scanned with its detector). Details: `research/poe1-formats.md`.

## Methods to claims

| Methods (`METHODS.md`) | Claim families |
|---|---|
| P2-01 to P2-06 core orbs | `transmutation`, `augmentation`, `regal_orb`, `alchemy`, `exalted_orb`, `chaos_orb`, `modifier_level`, `affix_limits`, `affix_pool`, `item_level`, `rarity` |
| P2-07 to P2-09 | `annulment_orb`, `divine_orb`, `fracturing_orb` |
| P2-10 to P2-12, P2-39 | `essence`, `alloy` |
| P2-13 to P2-17, P2-22 to P2-24 | `omen`, `sanctification`, `divine_orb` |
| P2-18 | `market` |
| P2-19 | `hinekora_lock` |
| P2-20 to P2-22 | `desecration`, `abyss_reveal`, `omen` |
| P2-25, P2-26 | `catalyst`, `breach_catalyst`, `quality_currency`, `quality` |
| P2-27, P2-45 | `distilled_emotion` |
| P2-28, P2-31, P2-49 | `verisium`, `expedition_items` |
| P2-29, P2-30 | `reforging_bench`, `reforging_recipes`, `salvage_bench` |
| P2-32 to P2-38 | `vaal_orb`, `corruption`, `corruption_outcomes`, `temple_currency` |
| P2-40 to P2-44 | `artificers_orb`, `sockets`, `augment`, `rune`, `soul_core`, `idol`, `jewellers_orb`, `temple_currency` |
| P2-46 to P2-48, P2-50 to P2-52 | `orb_of_chance`, `uniques`, `mirror`, `jewels_and_others`, `omen` (waystone omens), `quality_currency` |
| P2X rows | `recombinator`, `item_classes`, `omen` (retired), `shards`, `item_rules`, `socketable_rules` |
