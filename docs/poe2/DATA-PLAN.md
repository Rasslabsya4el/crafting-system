# PoE2 data plan: which source gives which table, and what is missing

Date checked 2026-11-24, game data 0.5.5.10. The PoE1 planner reads five repoe-fork files pinned in `src/crafting_system/data/PIN.json` (ADR-0003) and a dated price file (ADR-0007). This plan says where each PoE2 counterpart comes from. Details, API shapes and access tests per source: `docs/poe2/research/data-sources.md`.

## What is pinned on this branch

`research/poe2/data/PIN.json`, fetched and checked by `python -I research/poe2/data/fetch_poe2.py fetch` into `$CRAFTING_CACHE_DIR/repoe-fork-poe2/0.5.5.10/` (never committed):

1. **repoe-fork/poe2** commit `1905f2ad` (export 0.5.5.10, 2026-11-19): `mods.json`, `base_items.json`, `item_classes.json`, `augments.json`, `mods_by_base.json`, `tags.json`, `tag_details.json`, `uniques.json`, four `stat_translations/*.json`.
2. **repoe-fork/dat-export** commit `85174b65` (2026-11-23, game 0.5.5.10), 42 client tables as CSV from `current/poe2/heuristics/csv/`: `BaseItemTypes`, `ItemClasses`, `Mods`, `ModFamily`, `ModType`, `Stats`, `Tags`, `TieredCurrency`, `CurrencyItems`, `Essences`, `EssenceMods`, `EssenceTargetItemCategories`, `SoulCores`, `SoulCoreStats`, `AbyssBenchTicketTypes`, `Incursion2Crafting`, `RecombinableClasses`, `Expedition2VerisiumCrafts`, `Expedition2Recipes`, `CurrencyExchange`, and others (the list is the pin).
3. **Craft of Exile beta** `json/poe2/0.5.5.5/data.json` (cache only, no licence): the community weight estimates.

Committed snapshots: `research/poe2/data/trade-api-2026-11-24/` (the official trade site's `static`, `items`, `stats`, `filters`, `leagues`), and the readable extracts in `research/poe2/data/derived/` made by `derive_tables.py`.

## Table by table

| Planner input (PoE1 source) | PoE2 source | State | Notes |
|---|---|---|---|
| Mods: generation type, domain, families, required level, stats, tags (`mods.json`) | repoe-fork/poe2 `mods.json` | **complete** | Same shape as PoE1. Domains `item` and `desecrated`; `crafted` and many others are PoE1 leftovers. |
| Spawn weights (`mods.json` `spawn_weights`) | **none in game data**: every positive weight is 1 | **missing** | The tags (which mod can spawn where) are right; the numbers are not. Estimates: Craft of Exile beta `classmods` and poe2db `DropChance` (one origin, Krakenbul, recombinator and trade-listing measurements, on a breakpoint scale). About 2,000 to 4,000 mod entries have no measurement (stand-in 1). |
| Tiers per class (computed from `mods.json` in PoE1) | computed the same way; `mods_by_base.json` gives the pool per class and tag set | complete | Tier 1 is the best, as in PoE1. |
| Base items, item classes, tags (`base_items.json`) | repoe-fork/poe2 `base_items.json`, `item_classes.json` | complete, with a trap | `release_state` says "released" for bases not in the game (swords, axes, daggers, claws; PoE1 leftovers). The truth of "in the game" is the trade site's `items` list. |
| Essence → mod per class (`essences.json`) | dat-export `Essences`, `EssenceMods`, `EssenceTargetItemCategories` (extract: `derived/essences.md`); also PoB-PoE2 `Essence.lua`, Craft of Exile, poe2db | complete (178 rows) | repoe-fork has no `essences.json`. The column `Essences.Tier` holds 0–2 and is not the grade: the grade is in the name. |
| Fossils (`fossils.json`) | – | not in PoE2 | |
| Bench options (`crafting_bench_options.json`) | – | not in PoE2 | No crafting bench. |
| Minimum modifier level of Greater/Perfect orbs | dat-export `TieredCurrency` (extract: `derived/tiered-currency.md`) | complete | 44/70 and 35/50. The top-tier exception is a rule (claims), not data. |
| Bones: classes, max item level, min mod level | dat-export `AbyssBenchTicketTypes` (`derived/abyss-bones.md`) | complete | Two columns unnamed (chance 0.08 and a flag: likely the lords' mods). |
| Desecrated mods and lords' mods | `mods.json` domain `desecrated` + tags `kurgal_mod`, `amanamu_mod`, `ulaman_mod` | complete for the list | Reveal option weights: **missing** (estimates only). |
| Omens and currency rules | `base_items.json` description text; dat-export `CurrencyItems` | text only | No machine rule anywhere: the rules are the claims (`docs/poe2/claims/omen.yaml` and the orb files). |
| Augments (runes, soul cores, idols) | repoe-fork `augments.json`; dat-export `SoulCores`, `SoulCoreStats` (`derived/socketables.md`) | complete | |
| Augment sockets per base | Craft of Exile data; base properties | partial | 2 on body armour and two-handers, 1 elsewhere; corruption and Exceptional bases add one. |
| Corruption outcomes | `mods.json` generation type `corrupted` (the enchantment pool); outcome odds | pool complete, **odds missing** | Craft of Exile assumes 25% each. |
| Temple benches | dat-export `Incursion2Crafting` (`derived/temple-benches.md`) | complete | |
| Recombinator | dat-export `RecombinableClasses` | data present, mechanic disabled | |
| Verisium crafts | dat-export `Expedition2VerisiumCrafts`, `Expedition2Recipes` (`derived/verisium-crafts.md`) | complete for bases | What runeforging does to mods: open. |
| Stat texts | `stat_translations/*.json` | complete | |
| Trade stat ids (for price queries) | official `api/trade2/data/stats` (committed snapshot) | complete | |
| Prices (PoE1: a dated poe.ninja file) | poe.ninja `poe2/api/economy/exchange/current/overview?league=<league>&type=<Currency\|Essences\|Ritual\|Abyss\|Runes\|SoulCores\|...>` (answers the server; the web page is 403); poe2scout API (keys by metadata path); GGG's hourly exchange digest `web.poecdn.com/api/currency-exchange/poe2/<hour>` | available | Values in Divine Orbs; the PoE2 base currency of trade is the Exalted Orb (1 divine ≈ 450 exalted on 2026-11-24). The planner's cost unit must change from Chaos to Exalted or Divine. Rare items: the trade site `api/trade2/search` and `fetch`. |

## What is missing, ranked

1. **Spawn weights** (all mods). The estimates have one origin and many holes. Without them no outcome distribution of a Transmutation, Augmentation, Regal, Alchemy, Exalted, Chaos, bone reveal or Vaal reroll is exact. See `PORT-PLAN.md`, unknown U1.
2. **Reveal option weights** and how many options appear (3 per Craft of Exile).
3. **Vaal Orb outcome odds** per item kind, and Architect's Orb odds.
4. **Quality per use** of the quality currencies and catalysts.
5. **Orb of Chance odds** (uniques only; out of the planner).
6. **Mods after runeforging** and the reforging bench's equipment recipes.
7. **1.0 (2026-12-11)**: the new Reforging system (Crimson Iron), its data tables, and whatever 1.0 changes in the tables above. Re-pin on 1.0: `python -I research/poe2/data/fetch_poe2.py pin <new repoe-fork/poe2 commit>`, then update the dat-export commit in `PIN.json` and run `derive_tables.py` again.
