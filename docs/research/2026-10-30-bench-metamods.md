# Bench crafts and metamods in 3.29 (research for ticket #11)

Ticket: https://github.com/Rasslabsya4el/crafting-system/issues/11 (map #1). Date checked: 2026-10-30. Patch: 3.29.3.3 (repoe-fork page "RePoE - PoE version 3.29.3.3", https://repoe-fork.github.io/poe1.html).

**Answer.** The bench export holds 765 options: 732 add one fixed crafted mod (never drawn at random), 15 flask enchants, 13 socket options, and 5 rerolls/removals (Remove Crafted Mods 1 Scouring; Reroll rarity 1 Chance; Reroll 3 / 1 random mods 3 / 8 Chaos). The five metamods are bench crafts at tier 0 for 24 equipment classes: Prefixes Cannot Be Changed (a suffix) 2 Divine, Suffixes Cannot Be Changed (a prefix) 2 Divine, Can have up to 3 Crafted Modifiers (suffix) 2 Divine, Cannot roll Attack Modifiers (suffix) 1 Divine, Cannot roll Caster Modifiers (suffix) 1 Divine. An item takes one crafted mod by default; multimod raises that to three counting itself; metamods are crafted mods and take a slot on their own side. Side locks protect existing mods of the locked side from removal and reroll but never forbid filling an open slot; Attack/Caster locks make the game skip mods carrying the Attack/Caster mod tag (GGG, 3.12.0) when adding, and make Orb of Annulment skip them when removing. The per-action respect table (26 rows) is admitted from the wiki. The tags `no_attack_mods` / `no_caster_mods` do not exist in the 3.29.3.3 export; the tag test is `implicit_tags` (not `adds_tags`). Not settled: what the two new Chaos rerolls do, what "Remove Crafted Mods" does with several crafted mods, Harvest reforge draw order under Attack/Caster locks, and which crafts the player has unlocked.

## Admitted claims

Datamined claims cite `https://repoe-fork.github.io/crafting_bench_options.json` ("bench"), `https://repoe-fork.github.io/mods.json` ("mods") or `https://repoe-fork.github.io/base_items.json`, patch 3.29.3.3, checked 2026-10-30. `bench[i]` is the array index (the file has no record id; mod-adding records are keyed by `actions.add_explicit_mod`, a key of `mods`). The exporter's own description (https://repoe-fork.github.io/): "Describes master crafting options. Defines which masters can craft them at which level on which items." Wiki claims cite pages that were read in the built-in browser; each page's newest version-history row and last-edit date are in "Sources read".

### Bench export: shape, fields, costs (datamined)

**BEN-01** `bench` is an array of 765 records with exactly the keys `actions`, `bench_tier`, `cost`, `item_classes`, `master`; each record has exactly one non-null entry in `actions`. There is no unlock, quest or level-requirement field. Source kind: datamined. URL: bench. Quote: `len=765; keys={actions,bench_tier,cost,item_classes,master}; non-null actions per record = 1 (765/765)`. Patch 3.29.3.3. chk 2026-10-30.

**BEN-02** Action kinds (count of records with that `actions.<kind>` non-null): `add_explicit_mod` 732, `add_enchant_mod` 15, `change_socket_count` 5, `link_sockets` 5, `color_sockets` 3, `reroll_rare_mods` 2, `remove_crafted_mods` 1, `remove_enchantments` 1, `reroll_rarity` 1. Source kind: datamined. URL: bench. Quote: the counts themselves, e.g. `bench[20].actions.remove_crafted_mods=true`. Patch 3.29.3.3. chk 2026-10-30.

**BEN-03** The 732 `add_explicit_mod` options name 732 distinct ids that all exist in `mods` with `domain`="crafted"; 408 are `generation_type`="prefix", 324 "suffix". None can be drawn at random: `generation_weights` is `[]` for all 732, `spawn_weights` is `[]` for 313 and all-zero for the other 419. Mod-id prefixes: `JunMaster...` 419, `EinharMaster...` 300, `HelenaMaster...` 7, `CraftedTravelSkillsCannotBeExerted` 1, the five metamod ids 5. Source kind: datamined. URL: mods, bench. Quote: `bench[760].actions.add_explicit_mod="StrMasterItemGenerationCannotChangePrefixes"; mods[that id]: domain="crafted", generation_type="suffix", spawn_weights=[], generation_weights=[]`. Patch 3.29.3.3. chk 2026-10-30.

**BEN-04** `cost` maps currency base-item ids (`Metadata/Items/Currency/<Name>`) to integer amounts; 750 records have one currency, 15 (flask enchants) two. The ids resolve to names in `base_items.json` (e.g. `CurrencyModValues` = Divine Orb, `CurrencyConvertToNormal` = Orb of Scouring, `CurrencyRerollRare` = Chaos Orb, `CurrencyRerollMagic` = Orb of Alteration, `CurrencyUpgradeToMagic` = Orb of Transmutation, `CurrencyUpgradeToRare` = Orb of Alchemy, `CurrencyAddModToRare` = Exalted Orb, `CurrencyAddModToMagic` = Orb of Augmentation, `CurrencyUpgradeMagicToRare` = Regal Orb, `CurrencyUpgradeRandomly` = Orb of Chance, `CurrencyCorrupt` = Vaal Orb). Source kind: datamined. URL: bench, base_items. Quote: `base_items["Metadata/Items/Currency/CurrencyModValues"].name="Divine Orb"`; `bench[762].cost={"Metadata/Items/Currency/CurrencyModValues":2}`. Patch 3.29.3.3. chk 2026-10-30.

Compact summary of the 732 mod-adding options by cost currency (options; amounts x number of options):

| currency | options | amounts |
|---|---|---|
| Chaos Orb | 266 | 1x8, 2x71, 3x51, 4x116, 6x3, 8x17 |
| Orb of Alchemy | 184 | 1x18, 2x118, 3x28, 4x17, 6x1, 8x2 |
| Orb of Alteration | 109 | 1x1, 4x26, 6x30, 8x47, 9x5 |
| Orb of Transmutation | 51 | 1x3, 4x35, 6x5, 8x8 |
| Exalted Orb | 28 | 4x28 |
| Vaal Orb | 26 | 1x2, 2x3, 3x2, 4x3, 6x8, 8x8 |
| Orb of Augmentation | 25 | 1x3, 3x4, 4x4, 6x14 |
| Orb of Chance | 18 | 2x3, 3x5, 4x8, 6x1, 8x1 |
| Regal Orb | 9 | 1x2, 2x3, 3x3, 4x1 |
| Glassblower's Bauble | 7 | 2x1, 4x1, 6x5 |
| Divine Orb | 5 | 1x2, 2x3 (the five metamods) |
| Armourer's Scrap | 3 | 8x3 |
| Gemcutter's Prism | 1 | 8x1 |

`bench_tier` of the mod-adding options: 0 x51 (five metamods + 46 others), 1 x257, 2 x254, 3 x163, 4 x6, 5 x1.

**BEN-05** `item_classes` lists the equipment classes an option is offered for. All five metamods and the Remove Crafted Mods option use the same 24 classes: Dagger, Rune Dagger, One Hand Axe, One Hand Mace, One Hand Sword, Claw, Sceptre, Thrusting One Hand Sword, Two Hand Axe, Two Hand Mace, Two Hand Sword, Staff, Warstaff, Wand, Bow, Body Armour, Gloves, Boots, Helmet, Shield, Ring, Amulet, Belt, Quiver. That is every `domain`="item" class in `base_items` except FishingRod and HiddenItem; flasks, jewels, maps and the rest are not offered. Source kind: datamined. URL: bench, base_items. Quote: `bench[760..764].item_classes` and `bench[20].item_classes` identical, length 24. Patch 3.29.3.3. chk 2026-10-30.

**BEN-06** The `master` field cannot be used as the in-game master: it reads "Niko, Master of the Depths" for all 747 records that are neither sockets nor metamods (including `JunMaster...`, `EinharMaster...`, `HelenaMaster...` ids), "Jun, Veiled Master" for the 13 socket records, "Einhar, Beastmaster" for the 5 metamod records. `bench_tier` runs 0 to 5. Which crafts a player has unlocked is not in the export. Source kind: datamined. URL: bench. Quote: `bench[1].master="Jun, Veiled Master"`; cross-tab of mod-id prefix vs `master`: Jun/Einhar/Helena -> "Niko, Master of the Depths". Patch 3.29.3.3. chk 2026-10-30.

**BEN-07** Remove Crafted Mods is one option: `remove_crafted_mods` true, cost 1 Orb of Scouring, `bench_tier` 0, the 24 classes of BEN-05. (Remove Enchantments is separate: `bench[309]`, 3 Orbs of Scouring, 29 classes incl. flasks.) Source kind: datamined. URL: bench. Quote: `bench[20].actions.remove_crafted_mods=true, cost={"Metadata/Items/Currency/CurrencyConvertToNormal":1}, bench_tier=0`. Patch 3.29.3.3. chk 2026-10-30.

**BEN-08** The three reroll options: `reroll_rarity` costs 1 Orb of Chance (`bench[753]`); `reroll_rare_mods`=3 costs 3 Chaos Orbs (`bench[754]`); `reroll_rare_mods`=1 costs 8 Chaos Orbs (`bench[755]`); all `bench_tier` 0 with the same 40 classes (24 equipment, 5 flask classes, Jewel, AbyssJewel, Map, Tincture, FishingRod, MapKey, MiscMapItem, HeistContract, HeistBlueprint, ExpeditionLogbook, DeepwaterChart). Rarity conditions ("Rare Item") are not in the export. Source kind: datamined. URL: bench. Quote: `bench[754].actions.reroll_rare_mods=3, cost={"Metadata/Items/Currency/CurrencyRerollRare":3}`; `bench[755].actions.reroll_rare_mods=1, cost={"Metadata/Items/Currency/CurrencyRerollRare":8}`. Patch 3.29.3.3. chk 2026-10-30.

**BEN-09** 3.29.0 added the two Chaos-cost rerolls of BEN-08 and made them available from the start. Source kind: official. URL: https://www.pathofexile.com/forum/view-thread/3985332 (3.29.0 notes, "New Content and Features"). Quote: "Added 2 new crafting bench options, unlocked by default." (the bullet continues with "Reroll 3 random Modifiers on a Rare Item for a cost of 3 Chaos Orbs" and "Reroll a random Modifier on a Rare Item for a cost of 8 Chaos Orbs"; text read through WebFetch because the Cloudflare check never cleared in the browser pane). Corroborated by wiki https://www.poewiki.net/wiki/Crafting_Bench#Version_history (3.29.0 row, same bullet). Patch 3.29.0. chk 2026-10-30.

**BEN-10** Since 3.28.0 bench options that used to cost 1-3 Exalted Orbs generally cost 4; the export agrees (28 options, all 4 Exalted). Source kind: official. URL: https://www.pathofexile.com/forum/view-thread/3913392 (3.28.0 notes, "Item Changes"). Quote: "Crafting Bench Options that previously cost a number of Exalted Orbs, now generally cost 4 Exalted Orbs (previously 1-3)." Patch 3.28.0. chk 2026-10-30.

**BEN-11** Most bench crafts must be unlocked as recipes found in specific places; some start unlocked. The five metamods are unlocked in unique maps: Cannot roll Attack Modifiers at Caer Blaidd, Wolfpack's Den; Suffixes Cannot Be Changed at Oba's Cursed Trove; Prefixes Cannot Be Changed at The Coward's Trial; Can have up to 3 Crafted Modifiers at The Putrid Cloister; Cannot roll Caster Modifiers at Whakawairua Tuahu. Remove Crafted Mods, Remove Enchantments and Reroll the Rarity of a non-Unique item "Starts unlocked". Source kind: wiki. URL: https://www.poewiki.net/wiki/Crafting_Bench#Metacrafting_modifiers and #Other_crafts. Quote: "Additional crafting options can be unlocked by finding recipes, which are interactable objects found in specific areas" and "Starts unlocked | Remove Crafted Mods | 1x Orb of Scouring". Patch: page newest row 3.29.0, last edited 2026-08-16. chk 2026-10-30.

### The five metamods (datamined; costs also in the wiki Metacrafting table, BEN-11 page)

All five: `mods` `domain`="crafted", `required_level` 1, `spawn_weights` [], `generation_weights` [], `adds_tags` [], `implicit_tags` [], `is_essence_only` false, `groups` = [`type`] = the group below, one stat with min 1 max 1; bench record `bench_tier` 0, the 24 classes of BEN-05. Wiki cross-read: https://www.poewiki.net/wiki/Metamod#Overview lists the same five names with the same sides and the costs in the wiki Metacrafting table are 2/2/2/1/1 Divine Orb.

| id | bench idx | mod id | text (name) | side | group = type | stat id | cost |
|---|---|---|---|---|---|---|---|
| BEN-12 | 760 | `StrMasterItemGenerationCannotChangePrefixes` | Prefixes Cannot Be Changed ("of Prefixes") | suffix | `ItemGenerationCannotChangePrefixes` | `item_generation_cannot_change_prefixes` | 2 Divine Orb |
| BEN-13 | 761 | `DexMasterItemGenerationCannotChangeSuffixes` | Suffixes Cannot Be Changed ("Suffixed") | prefix | `ItemGenerationCannotChangeSuffixes` | `item_generation_cannot_change_suffixes` | 2 Divine Orb |
| BEN-14 | 762 | `StrIntMasterItemGenerationCanHaveMultipleCraftedMods` | Can have up to 3 Crafted Modifiers ("of Crafting") | suffix | `ItemGenerationCanHaveMultipleCraftedMods` | `item_generation_can_have_multiple_crafted_mods` | 2 Divine Orb |
| BEN-15 | 763 | `IntMasterItemGenerationCannotRollAttackAffixes` | Cannot roll Attack Modifiers ("of Spellcraft") | suffix | `ItemGenerationCannotRollAttackAffixes` | `item_generation_cannot_roll_attack_affixes` | 1 Divine Orb |
| BEN-16 | 764 | `StrDexMasterItemGenerationCannotRollCasterAffixes` | Cannot roll Caster Modifiers ("of Weaponcraft") | suffix | `ItemGenerationCannotRollCasterAffixes` | `item_generation_cannot_roll_caster_affixes` | 1 Divine Orb |

Each row is its own claim. Source kind: datamined. URL: bench, mods. Quote: the row's mod id with `generation_type` and `cost` as listed (e.g. `bench[761].cost={"Metadata/Items/Currency/CurrencyModValues":2}`, `mods["DexMasterItemGenerationCannotChangeSuffixes"].generation_type="prefix"`). Patch 3.29.3.3. chk 2026-10-30. The "Cannot Be Changed" mods sit on the opposite side from the one they lock.

**BEN-17** Each metamod has its own group, and no other exported mod carries these five groups or stat ids, so an item holds at most one of each. Source kind: datamined (uniqueness) + wiki (family rule, restated from issue #2 Q2). URL: mods; https://www.poewiki.net/wiki/Modifier. Quote: "Only one modifier from any given group may appear on an object". Patch 3.29.3.3 / wiki page last edited 2026-10-10. chk 2026-10-30.

### Crafted-mod limits and bench rules (wiki)

Source for BEN-18 to BEN-23: https://www.poewiki.net/wiki/Crafting_Bench (newest version-history row 3.29.0; last edited 2026-08-16), read 2026-10-30.

**BEN-18** By default an item takes one crafted mod, and crafting follows the ordinary affix rules: the item cannot already have a mod of that type (family) and must have an open slot on the side of the crafted mod (no 4th prefix/suffix on a rare, no 2nd on a magic item). Anchor #Using_the_crafting_bench. Quote: "Typically, only one crafted modifier may be added to an item" and "The item must have a prefix or suffix slot open as appropriate." Patch 3.29. chk 2026-10-30.

**BEN-19** The multimod (`Can have up to 3 Crafted Modifiers`) lets an item carry up to three crafted mods and counts itself as one of the three (two more crafts). Source kinds: wiki (two pages). URLs: #Using_the_crafting_bench (quote: "It is possible to craft more than one mod onto an item with the of Crafting meta-crafting mod") and https://www.poewiki.net/wiki/Version_3.9.0 (quoting the official 3.9.0 notes, thread 2687400): "now allows you to craft up to three mods on the item" and "items with the mod will now be limited to 2 additional crafts". Patch 3.9.0, no later change found. chk 2026-10-30.

**BEN-20** Metamods are crafted modifiers that take an affix slot on their own side (sides in BEN-12 to BEN-16), so crafting one needs a free slot there and counts toward the crafted-mod limit of BEN-18/BEN-19. Source kind: wiki. URLs: https://www.poewiki.net/wiki/Metamod#Overview: "of Prefixes - Prefixes Cannot Be Changed (Suffix)"; https://www.poewiki.net/wiki/Wild_Bristle_Matron: "The beastcraft cannot be used on an item that already has a crafted mod (unless the existing mod is Can have up to 3 Crafted Modifiers)."; Metamod#Examples (three crafted mods on one item: multimod, a temporary crafted mod, Prefixes Cannot Be Changed). Patch: Metamod newest row 3.27.0 (last edited 2026-08-11). chk 2026-10-30.

**BEN-21** Veiled modifiers are not crafted modifiers, so they do not count toward the limit. Source kind: wiki. URL: #Version_history (3.15.0 row) of https://www.poewiki.net/wiki/Crafting_Bench. Quote: "Veiled modifiers are no longer considered Crafted modifiers." Patch 3.15.0. chk 2026-10-30.

**BEN-22** Using a craft on an item that already has a crafted mod replaces that mod and costs one extra Orb of Scouring; it cannot replace a fractured crafted mod, cannot replace when the item has several crafted mods, and cannot be done on corrupted, mirrored or unmodifiable items. Anchor #Using_the_crafting_bench. Quote: "the craft will attempt to replace the current crafted modifier for the cost of an additional Orb of Scouring." Patch 3.29. chk 2026-10-30.

**BEN-23** The bench removes a crafted mod from an item for 1 Orb of Scouring, available from the start. Anchors #Using_the_crafting_bench, #Other_crafts. Quote: "Players can remove a crafted mod from an item using the crafting bench for the cost of an Orb of Scouring." Cost and classes also in BEN-07. Patch 3.29. chk 2026-10-30.

### What the metamods do

**BEN-24** Prefixes / Suffixes Cannot Be Changed protect the existing mods of the locked side; they do not stop new mods being added into open slots of that side. Source kind: wiki. URL: https://www.poewiki.net/wiki/Metamod#Overview. Quote: "It will not, however, prevent adding a new modifier, such as through an Exalted Orb or Chaos Orb, as it only applies to existing modifiers." Also official, Chris 2015: https://www.pathofexile.com/forum/view-thread/1401804: "Removal counts as a change." Patch: wiki newest row 3.27.0; GGG post 2015 (2.x), reaffirmed by the wiki table. chk 2026-10-30.

**BEN-25** The Cannot roll Attack / Caster Modifiers metamods act on the Attack and Caster mod tags (the tags shown on a mod with Alt held). Source kind: official. URL: https://www.pathofexile.com/forum/view-thread/2935368 (Bex_GGG, 2020-09-15, "Path of Exile: Heist Balance Manifesto", heading "Changes to the Mod Tag System"). Quote: "The “Cannot roll Attack Mods” and “Cannot roll Caster Mods” meta-crafts now simply use the Attack and Caster tags." Patch 3.12.0; the wiki (https://www.poewiki.net/wiki/Metamod#Version_history, 3.12.0 row; Modifier#Metamods, edited 2026-10-10) still describes it that way for 3.29. chk 2026-10-30.

**BEN-26** In the 3.29.3.3 export the mod tags are the `implicit_tags` lists, not `adds_tags`: the 24 fossil weight tags (attack, caster, fire, ...) in `fossils.json` are all members of the `implicit_tags` vocabulary (45 tags), and the official 3.12.0 mod list (https://www.pathofexile.com/public/news/2020-09-15/mods.html) gives the first rank of non-local "Adds 1 to 2 Cold Damage to Attacks" the tags "Damage, Elemental, Cold, Attack", equal to `mods["AddedColdDamage1"].implicit_tags` = [elemental_damage, damage, elemental, cold, attack]. Counts over the 4,369 item-domain prefix/suffix mods: `attack` without `caster` 954, `caster` without `attack` 427, both 28; of the 2,725 that can spawn (some positive spawn weight): 590 / 304 / 10. Source kind: datamined (+ official sample row). URL: mods, https://repoe-fork.github.io/fossils.json. Quote: `mods["AttackAndCastSpeed1"].implicit_tags=["attack","caster","speed"]`. Patch 3.29.3.3 (list: 3.12.0). chk 2026-10-30. Full equivalence of `implicit_tags` with the in-game tags is checked on samples only: see O-04.

**BEN-27** The strings `no_attack_mods` and `no_caster_mods` occur in none of the eight exported files (`mods.json`, `mods_by_base.json`, `base_items.json`, `tags.json`, `crafting_bench_options.json`, `essences.json`, `fossils.json`, `mod_types.json`); no mod has a spawn-weight tag about attack/caster mods (the only `attack_*` spawn tags are base-type tags `attack_dagger`, `attack_staff`). `adds_tags` `has_attack_mod` (2,299 mods) and `has_caster_mod` (1,370) are a different, smaller set: of the 4,369 item-domain prefix/suffix mods 982 carry the `attack` tag but only 553 carry `has_attack_mod` (539 overlap, 14 have the flag without the tag), so 443 Attack-tagged mods (e.g. `AddedColdDamage1`) lack the flag and `adds_tags` must not be used as the Attack/Caster test. Source kind: datamined. URL: mods, https://repoe-fork.github.io/tags.json. Quote: zero matches for `no_attack_mods|no_caster_mods`; `mods["AddedColdDamage1"].adds_tags=[]` vs `mods["LocalAddedColdDamage1"].adds_tags=["has_attack_mod"]`. Patch 3.29.3.3. chk 2026-10-30. (The prior-art report claim that `AddedColdDamage1` has `no_attack_mods` is not reproduced.)

**BEN-28** With Cannot roll Attack Modifiers on the item, an Exalted Orb cannot add a modifier with the Attack tag. Source kind: wiki. URL: https://www.poewiki.net/wiki/Modifier#Metamods. Quote: "the Exalted Orb cannot add modifiers with the "Attack" tag." Patch: Modifier page last edited 2026-10-10. chk 2026-10-30.

**BEN-29** An Orb of Annulment on an item with Cannot roll Caster (resp. Attack) Modifiers does not remove modifiers with the Caster (Attack) tag; this is specific to Orbs of Annulment and does not hold for other single-removal crafts (beastcrafting, Harvest, Veiled Orb). Source kind: wiki. URL: https://www.poewiki.net/wiki/Modifier#Metamods. Quote: "it will not remove any modifiers with the "Caster" tag." and "This behaviour is specific to Orbs of Annulment." Attack case: same page names both metamods; Orb of Annulment page: "Orbs of Annulment respect metamods, including Cannot roll Caster/Attack Modifiers." Patch: edited 2026-10-10. chk 2026-10-30.

### Per-action respect table (wiki)

Rows BEN-30 to BEN-55; each row is one claim. Source kind: wiki. URL: https://www.poewiki.net/wiki/Metamod#Rules_and_Exceptions (tables "Basic Currencies", "Harvest Crafting", "Miscellaneous Crafting Options"). Patch: version history newest row 3.27.0; page last edited 2026-08-11; no official 3.28.0 to 3.29.3b note found that changes it (see Sources read). chk 2026-10-30. Quote per row = the four cells, in the order PCBC (Prefixes Cannot Be Changed), SCBC (Suffixes Cannot Be Changed), CRA (Cannot roll Attack), CRC (Cannot roll Caster). "open-fill P/S" = "Respected, but open prefixes may be filled" / "Respected, but open suffixes may be filled". "R" = "Respected", "I" = "Ignored", "—" = no entry (lock irrelevant to the action).

| id | action | PCBC | SCBC | CRA | CRC |
|---|---|---|---|---|---|
| BEN-30 | Orb of Alteration | open-fill P | open-fill S | — | — |
| BEN-31 | Orb of Augmentation | — | — | R | R |
| BEN-32 | Regal Orb | — | — | R | R |
| BEN-33 | Orb of Scouring | R | R | I | I |
| BEN-34 | Divine Orb | R | R | — | — |
| BEN-35 | Chaos Orb | open-fill P | open-fill S | "When used with Suffixes Cannot Be Changed" | "When used with Suffixes Cannot Be Changed" |
| BEN-36 | Orb of Annulment | R | R | R | R |
| BEN-37 | Exalted Orb and Conqueror variants | open-fill P | open-fill S | R | R |
| BEN-38 | Eldritch Chaos Orb | I | I | R | R |
| BEN-39 | Eldritch Exalted Orb | open-fill P | open-fill S | R | R |
| BEN-40 | Eldritch Orb of Annulment | R | R | R | R |
| BEN-41 | Orb of Dominance | R | R | I | I |
| BEN-42 | Awakener's Orb | I | I | I | I |
| BEN-43 | Tainted Exalted Orb | open-fill P | open-fill S | R | R |
| BEN-44 | Tainted Divine Teardrop | I | I | I | I |
| BEN-45 | Fossils | "Usage Prevented" | "Usage Prevented" | "Usage Prevented" | "Usage Prevented" |
| BEN-46 | Essences | "Usage Prevented" | "Usage Prevented" | "Usage Prevented" | "Usage Prevented" |
| BEN-47 | Veiled Exalted Orb | R | R | "Ignored" | "Ignored" |
| BEN-48 | Harvest: Add a new [Type] modifier and remove another random modifier from a non-Influenced item | open-fill P | open-fill S | "Respected when adding, ignored when removing" | same |
| BEN-49 | Harvest: Reforge a Rare item with random modifiers, including a [Type] modifier | open-fill P | open-fill S | "Respected (as of 3.27)" (wiki adds "confirmation needed because of : may require Suffixes Cannot Be Changed": O-03) | same |
| BEN-50 | Harvest: Change Element of Resistance | R | R | — | — |
| BEN-51 | Harvest: Reforge a Rare item, being more/less likely to receive the same modifier types | open-fill P | open-fill S | "When used with Suffixes Cannot Be Changed" | CRC cell carries "confirmation needed" (O-03) |
| BEN-52 | Harvest: Randomise the Influence types on an Influenced Normal, Magic or Rare Item, as well as reforging the item with new random modifiers | "Respected, but usage is prevented if any prefix is influenced, and open prefixes may be filled" | same for suffixes | "Unknown" (not admitted, O-03) | "Unknown" (not admitted) |
| BEN-53 | Harvest: Fracture a Modifier | I | I | I | I |
| BEN-54 | Beastcraft Add Prefix Remove Suffix | open-fill P | "Will add without removing" | "Does not protect attack modifiers" | "Does not protect caster modifiers" |
| BEN-55 | Beastcraft Add Suffix Remove Prefix | "Will add without removing" | open-fill S | "Does not protect attack modifiers" | "Does not protect caster modifiers" |

Reading of "Respected": the locked side (or the tagged mods) is not touched by removal/reroll; "open-fill": the action may still add mods into open slots of that side (BEN-24). Chaos under CRA/CRC works only with SCBC present because the metamods are suffixes that Chaos would otherwise reroll away (consequence of BEN-12/BEN-15/BEN-16 and the cell text).

**BEN-56** Essences and fossil resonators cannot be used on an item with a metamod, except the multimod; the game refuses with "Failed to apply item: You can't use this currency on items with a modifier that affects mod outcomes". Source kind: wiki. URL: https://www.poewiki.net/wiki/Metamod#Essence_and_Fossil. Quote: "When using essence or fossil on an item with metamod (other then the multi-craft mod), the game will warn you". Also https://www.poewiki.net/wiki/Resonator: "resonators cannot be used on items with metamods". Patch: Metamod newest row 3.27.0. chk 2026-10-30.

**BEN-57** Orb of Scouring on an item with Prefixes Cannot Be Changed removes every suffix, including that metamod, and keeps every prefix; with Suffixes Cannot Be Changed it removes every prefix, including that metamod, and keeps every suffix. Source kind: wiki. URL: https://www.poewiki.net/wiki/Metamod#Orb_of_Scouring. Quote: "the Orb of Scouring will remove ALL suffix (including Prefixes Cannot Be Changed) and keep ALL prefix of the item". Patch: newest row 3.27.0. chk 2026-10-30.

**BEN-58** Awakener's Orbs ignore all metamods (since 3.9.1b). Source kind: wiki. URL: https://www.poewiki.net/wiki/Metamod#Version_history (3.9.1b row). Quote: "Awakener's Orbs now ignore Mastercrafting Metamods." Patch 3.9.1b. chk 2026-10-30.

**BEN-59** Harvest reforge crafts that guarantee a modifier type respect items that restrict modifier types (such as Cannot Roll Attack Mods). Source kind: official. URL: https://www.pathofexile.com/forum/view-thread/3869068 (3.27.0 notes, "League Changes"). Quote: "will now respect modifiers on items which restrict modifier types" (WebFetch text; the bullet starts "Harvest reforge crafts which guarantee a certain modifier type"); full bullet also in https://www.poewiki.net/wiki/Version_3.27.0. Patch 3.27.0. chk 2026-10-30.

**BEN-60** The three reroll crafts (Reroll the Rarity of a non-Unique item; Reroll 3 random modifiers on a Rare Item; Reroll a random modifier on a Rare Item) consume 0-50 Memory Strands from an item that has them; other bench crafts consume none. Source kind: wiki. URL: https://www.poewiki.net/wiki/Memory_strand (section Mechanics). Quote: "the following crafting options do remove 0-50 memory strands, similar to Orb of Chance or Chaos Orb". Patch: page newest row 3.28.0. chk 2026-10-30.

**BEN-61** The Wild Bristle Matron beastcraft adds one metamod at random to a non-unique item, only if allowed; it can be forced to add Suffixes Cannot Be Changed by filling all suffixes and leaving a prefix open. Source kind: wiki. URL: https://www.poewiki.net/wiki/Wild_Bristle_Matron. Quote: "so it is possible to force it to add Suffixes Cannot Be Changed by filling all the suffixes and have open prefix before using this beastcraft." (Beastcrafting is B2; listed for the crafted-mod limit, BEN-20.) chk 2026-10-30.

## Open (not admitted)

**O-01 What the two Chaos rerolls do.** Known: names, costs, classes, unlocked, newest official line "Reroll 3 random Modifiers on a Rare Item" (BEN-08/BEN-09); consume Memory Strands (BEN-60). Unknown: whether the chosen mods are replaced by new random mods or only re-valued, uniform selection or weighted, whether fractured / crafted / metamod mods can be picked, how the affix count and slot sides are kept, the weights of the new mods. Non-admitted source: prototype `patch_3_29.md` ("selection versus value reroll, protection rules" listed as missing). Settles it: a wiki sentence or GGG statement; a large-sample experiment (affix counts and picked slots over thousands of rerolls). Blocks coding both rerolls.

**O-02 Remove Crafted Mods with several crafted mods.** Known: 1 Orb of Scouring, starts unlocked (BEN-07/BEN-23). Unknown: whether it removes all crafted mods or one, whether metamods are removed by it (they are crafted mods, BEN-20), and whether side locks matter. The wiki says "a crafted mod" (singular). Settles it: wiki sentence or GGG statement. Blocks the "remove crafted" action when more than one crafted mod is present.

**O-03 Harvest reforge draw order under Attack/Caster locks; wiki "confirmation needed" cells.** BEN-59 and BEN-49 admit that reforge crafts respect CRA/CRC since 3.27.0, but not whether every added mod or only the first is filtered, nor whether Suffixes Cannot Be Changed is required (wiki flag "may require Suffixes Cannot Be Changed"). Cells BEN-51 (CRC) and BEN-52 (CRA/CRC "Unknown") are also not admitted. Non-admitted: Craft of Exile note "Only for the first added modifier" (prototype Q6). Settles it: GGG statement or a large-sample experiment. Blocks Harvest tagged reforges on CRA/CRC items; owned by the Harvest ticket.

**O-04 Is `implicit_tags` exactly the in-game Attack/Caster tag for every 3.29.3.3 mod?** BEN-26 is admitted on the field vocabulary and one official sample row; the official 2020 list (3.12.0) and the export were not compared mod by mod, and mods added since 3.12 have no official list. Settles it: owner decision to adopt `implicit_tags`, or an audit of the 2020 list against the export for mods unchanged since 3.12. Needed before coding the CRA/CRC filter.

**O-05 Mods that carry both Attack and Caster tags.** 28 item mods (10 spawnable) have both. The tag rule (BEN-25) implies either metamod blocks them; not stated for the both-tag case. Settles it: wiki sentence or experiment.

**O-06 Bench crafts onto items with Cannot roll Attack / Caster Modifiers.** Whether the bench can add a crafted mod that carries the Attack/Caster tag (110 / 64 / 12 offered crafted mods carry `attack` / `caster` / both in `implicit_tags`) while the matching metamod is on the item is not stated; the wiki rules cover random draws only. Settles it: wiki sentence or test report.

**O-07 Locks and the bench replace step.** BEN-22 replaces a crafted mod by removing it; whether that removal is blocked when the crafted mod sits on a side protected by Prefixes/Suffixes Cannot Be Changed (and whether replacing the lock itself is allowed) is not stated.

**O-08 Which crafts the player has unlocked.** Unlock is per player (BEN-11, locations in the wiki Cargo table), not in the export (BEN-06). Needs an owner decision: model all crafts as available, or take an "unlocked set" input. Blocks nothing for the five metamods if all are assumed unlocked.

**O-09 Annulment candidate set under Prefixes/Suffixes Cannot Be Changed.** BEN-36 says the locked side is respected; that the metamod itself (a suffix/prefix on the other side) can be removed by Annulment is the natural reading of BEN-57 and BEN-20 but no admitted sentence states it for Annulment (same as basic-currency O-06).

**O-10 How retained mods count for Chaos / Alteration on locked items.** BEN-35 and BEN-30 give the shape (open slots may be filled) but not the affix-count distribution (wiki example: "the Orbs may add 1 prefix as well as 0 to 3 suffixes"); same as basic-currency O-03. Blocks Chaos on locked items.

**O-11 Memory Strands.** Items with strands change the tier odds of added mods (wiki Memory strand, introduced 3.26.0) and three bench crafts consume them (BEN-60). The model needs an owner decision to assume items without strands. Not a rule gap for the five metamods.

**O-12 Absence of later changes.** My own scan (WebFetch, keyword list: crafting bench, bench craft/recipe, metamod, Cannot Be Changed, Cannot roll, Crafted Modifier, Remove Crafted, Scouring, Harvest reforge/craft, Reroll ... Modifiers) covered the 3.29.0 notes in full, 3.29.0 Hotfix 1-3 and Restart fix, 3.29.0b + Hotfix 1-4, 3.29.1 + Hotfix + Maintenance, 3.29.2 + Hotfix 1-3, 3.29.3 + Hotfix 1, and the first 100,000 characters of the 3.28.0 notes. It found no change to metamods or bench rules beyond BEN-09, BEN-10, 3.29.1 ("Fixed a bug where the crafts 'Reroll the Rarity of a non-Unique item', 'Reroll 3 random modifiers on a Rare item' and 'Reroll a random modifier on a Rare item' could not be used on Maps ..."), 3.29.2 ("Added a crafting bench to the Menagerie.") and 3.29.3 ("Fixed the descriptions of the Frenzy and Power Charge Bench Craft Recipe being swapped."). Not scanned by me (HTTP 429 or not tried): 3.27.0a to 3.28.0j threads, 3.28.0k / 3.28.0l, 3.29.3 Hotfix 2-7, 3.29.3b, the last 32,433 characters of the 3.28.0 notes. A sibling report (basic-currency CUR-32) scanned 3.25.x to 3.29.3b first posts for "Metamod", "Cannot Be Changed", "Cannot Roll", "crafting bench" and found no metamod change, but that scan is not mine. The wiki does not mark its table outdated; Craft of Exile / poedb warn that GGG changes metamod interactions without notes, so this is absence of evidence only.

**O-13 Other multi-craft sources.** The wiki says Tempering Orbs, Tailoring Orbs and certain Grand Heist items give a "similar enchantment" allowing several crafted mods; out of scope for the five metamods (B2+).

**O-14 Legacy metamod.** `PvPMasterLevel28Crafting` ("of Dueling": Cannot roll Modifiers with Required Level above 28, suffix, `domain` crafted) exists in `mods` but is offered by no bench option (BEN-03); the wiki says it exists only on old items. Out of scope.

## Prototype re-audit

Source: `git show archive/prototype:docs/mechanics/bench_metamods.md` (every claim), plus the Bench-rerolls row of `patch_3_29.md` and the metamod rows of `basic_currency.md` that restate this sheet.

| # | prototype claim | verdict |
|---|---|---|
| 1 | Bench operations select a crafted mod instead of a random one; class support, group conflict and a free prefix/suffix slot must be checked | confirmed: BEN-05, BEN-18 |
| 2 | The S3 helper removes old bench crafts as part of a configured bench operation; must not become an undocumented atomic game action | changed: the bench documents the replace step with an extra Scouring and its limits (BEN-22); no hidden atomic action needed |
| 3 | Five datamined identities with PoB `level` 1, empty `modTags`, affix sides (Prefixes CBC suffix, Suffixes CBC prefix, multimod / attack / caster suffixes), PoB groups | confirmed: BEN-12 to BEN-16 (PoB agrees, see Cross-checks) |
| 4 | Supported classes include Helmet, Ring, Amulet, Belt | confirmed and completed: all 24 equipment classes, BEN-05 |
| 5 | Treat the added crafted mod as occupying an affix slot and a group | confirmed: BEN-18, BEN-20, BEN-17 (590 of 732 offered crafted mods share a group with an item-domain prefix/suffix) |
| 6 | Normal allowance 1; multimod 3 including itself | confirmed: BEN-18, BEN-19 |
| 7 | Side locks and attack/caster exclusions are not universal immunity; interpretation is per action | confirmed: BEN-30 to BEN-55 |
| 8 | Rebuild flags when their carrier mod is removed or retained | unbacked as an algorithm (CoE helper). The effect exists only while the metamod is on the item (stats in BEN-12 to BEN-16; Scouring/Chaos remove it, BEN-57, BEN-35); nothing further to open |
| 9 | Matrix row Chaos: locks protect existing locked-side mods; attack/caster apply when carrier retained, with suffix lock | confirmed: BEN-35 |
| 10 | Exalted: locks do not prevent additions to open slots; attack/caster filter additions | confirmed: BEN-37, BEN-24, BEN-28 |
| 11 | Annulment: excludes protected side; protects matching attack/caster mods from removal | confirmed: BEN-36, BEN-29 |
| 12 | Scouring / Divine preserve protected-side mods / values; cannot-roll not applicable | confirmed for locks (BEN-33, BEN-34, BEN-57); changed for Scouring and CRA/CRC: wiki says "Ignored" (the metamod is removed like any suffix) rather than "not applicable" |
| 13 | Essence / fossil: usage prevented for outcome-affecting locks, multimod alone exempt | confirmed: BEN-45, BEN-46, BEN-56 |
| 14 | Awakener: not respected | confirmed: BEN-42, BEN-58 |
| 15 | Harvest add/remove: side locks apply to removal; attack/caster apply to addition, not removal | confirmed: BEN-48 |
| 16 | Harvest reforge preserves side locks; exact attack/caster draw condition uncertain (Q6) | partly confirmed: BEN-49, BEN-59; draw order stays open: O-03 |
| 17 | Eldritch Chaos: side locks not respected (S14/S17), attack/caster respected (S17) | confirmed: BEN-38 |
| 18 | Multimod cost 2 Divine (owner row 5; S13's "2 Exalted" stale) | confirmed: BEN-14 (datamined 2 Divine; wiki Metacrafting table 2x Divine Orb); the Exalted prose is stale (wiki Exalted Orb page: recipes changed to Divine in 3.19.0) |
| 19 | S14 warns that undocumented game changes lag the matrix | not a rule; the wiki table replaces it as source (BEN-30 to BEN-55); the lag risk stays (O-12) |
| 20 | S19 official 3.27.0: tagged Harvest reforges respect modifier-type restrictions | confirmed: BEN-59 |
| 21 | Worked example: multimod occupies 1 suffix and 1 of 3 allowances | confirmed: BEN-19, BEN-20 |
| 22 | Worked example: blocked-family weight changes single-add odds 2/10 to 2/7 | consistent with BEN-17 (family exclusion) and BEN-18; synthetic weights, not a game fact |
| 23 | Worked example: two prefixes + prefix lock, Scour keeps 2 prefixes, removes the lock | confirmed: BEN-57 (the resulting rarity is basic-currency CUR-17) |
| 24 | Unlock availability belongs in loadout inputs | confirmed as a need: BEN-06, BEN-11; decision O-08 |
| 25 | `patch_3_29.md`: bench rerolls "three random mods for 3 Chaos, or one random mod for 8 Chaos, on rares" | costs confirmed: BEN-08, BEN-09; mechanics unbacked: O-01 |
| 26 | `basic_currency.md`: side locks block removal but not additions (`nchg_pre` / `nchg_suf`) | confirmed: BEN-24 |
| 27 | Prior-art report 1 (not the prototype): Attack/Caster block is a `no_attack_mods` spawn-weight tag (example `AddedColdDamage1`) | changed: not in the 3.29.3.3 export; the test is the `implicit_tags` Attack/Caster tag: BEN-25 to BEN-27 |

## Cross-checks (not evidence)

- **Path of Building** (`src/Data/ModMaster.lua` lines 732-736, PathOfBuildingCommunity/PathOfBuilding `dev`, fetched 2026-10-30): the five metamods with `type` Suffix / Prefix / Suffix / Suffix / Suffix, affixes "of Prefixes", "Suffixed", "of Crafting", "of Spellcraft", "of Weaponcraft", the same group names, `level = 1`, `modTags = {}`; agrees with BEN-12 to BEN-16. PoB carries no costs and no interaction rules.
- **Craft of Exile metamod table** (read through the poedb.tw/us/metamods mirror and craftofexile.com/?page=metamods, 2026-10-30; page warns "These interactions are often changed in the game without any mention in the patch notes"): agrees with the wiki on Alteration, Augmentation, Regal, Scouring, Divine, Chaos (attack/caster with suffix lock), Annulment (protects attack/caster mods), Exalted, Orb of Dominance, Awakener, Fossil / Essence (usage prevented), Veiled orb, Harvest add/remove, Beastcrafting. Disagrees: Tainted Divine Teardrop (CoE: both locks respected; wiki BEN-44: ignored); Harvest "more likely" (CoE: attack/caster not respected; wiki BEN-51: with Suffixes Cannot Be Changed); Eldritch Chaos attack/caster (CoE: not listed; wiki BEN-38: respected); Harvest Reroll / Reroll+ (CoE: attack/caster respected only for the first added modifier; wiki BEN-49: respected since 3.27, flagged "confirmation needed"). Per the evidence rule the wiki wins.
- **poedb.tw/us/Crafting_Bench** (2026-10-30): metamod costs 2/2/2/1/1 Divine Orb; Remove Crafted Mods 1x Orb of Scouring, Default unlock; unlock places equal to BEN-11. A WebFetch read of the wiki-like prose says one crafted modifier by default and several with "of Crafting".
- **Wiki Veiled Exalted Orb row (BEN-47)** cites a Guy_GGG post (https://www.pathofexile.com/forum/view-thread/3315559, 2022-09-30) that only says the Fandom wiki is not affiliated with GGG; the cell is admitted as wiki behaviour but has weak backing. The Veiled Exalted Orb page itself says "The mod removal does not respect cannot roll attack/caster modifiers, but does respect prefixes/suffixes cannot be changed."
- **Essences sibling report** records an older GGG line (Chris, 2016-08-22, thread 1713551) "Essences will ignore master metamods when rolling an item" against the wiki's "Usage Prevented" (BEN-46, BEN-56); under the evidence rule the wiki wins (see that report's O-09).
- **GPT research helper** (opencode): two runs failed ("timed out"; "worker process died before finishing"); no player-experiment leads were added, so no large-sample experiment is cited for any claim here.

## Sources read

Wiki (built-in browser, tab opened and closed by this task): https://www.poewiki.net/wiki/Metamod (rendered text and wikitext; newest version-history row 3.27.0; last edit 2026-08-11 20:42); https://www.poewiki.net/wiki/Crafting_Bench (rendered sections and wikitext; newest row 3.29.0; last edit 2026-08-16); https://www.poewiki.net/wiki/Modifier (§ Mod tag, § Metamods, § Group/family; last edit 2026-10-10); https://www.poewiki.net/wiki/Version_3.9.0; https://www.poewiki.net/wiki/Version_3.27.0; https://www.poewiki.net/wiki/Version_3.28.0; https://www.poewiki.net/wiki/Version_3.29.0; https://www.poewiki.net/wiki/Version_3.29.1; https://www.poewiki.net/wiki/Memory_strand; https://www.poewiki.net/wiki/Wild_Bristle_Matron; https://www.poewiki.net/wiki/Beastcrafting; https://www.poewiki.net/wiki/Harvest_crafting (lines on metamods); https://www.poewiki.net/wiki/Orb_of_Annulment; https://www.poewiki.net/wiki/Orb_of_Scouring; https://www.poewiki.net/wiki/Veiled_Exalted_Orb; https://www.poewiki.net/wiki/Awakener%27s_Orb; https://www.poewiki.net/wiki/Fossil; https://www.poewiki.net/wiki/Resonator; https://www.poewiki.net/wiki/Essence; https://www.poewiki.net/wiki/Exalted_Orb (metamod lines only, via wikitext).

Official (pathofexile.com forum, read with WebFetch text extraction; the browser pane stayed on the Cloudflare check and was not bypassed, so short quotes could not be re-read in the browser): https://www.pathofexile.com/forum/view-thread/2935368 (Bex_GGG 2020-09-15, 3.12.0 mod tag system); https://www.pathofexile.com/public/news/2020-09-15/mods.html (official 3.12.0 mod/tag list, first 100,000 of 402,933 characters); https://www.pathofexile.com/forum/view-thread/1401804 (Chris 2015, Master Crafting Metamods); https://www.pathofexile.com/forum/view-thread/3869068 (3.27.0); https://www.pathofexile.com/forum/view-thread/3913392 (3.28.0, first 100,000 of 132,433 characters); https://www.pathofexile.com/forum/view-thread/3985332 (3.29.0); the patch-note threads 3987816, 3987917, 3988043, 3988602, 3989412, 3990009, 3990158, 3990172, 3990687, 3991672 (3.29.1), 3991769, 3991893, 3994431 (3.29.2), 3994498, 3994902, 3995749, 3996516 (3.29.3), 3996584; https://www.pathofexile.com/forum/view-thread/3315559 (Guy_GGG 2022); https://www.pathofexile.com/forum/view-thread/3481865 (player thread, not cited as evidence). Not opened: https://www.pathofexile.com/forum/view-thread/2687400 (3.9.0 notes; HTTP 429, cited through the wiki Version 3.9.0 page).

Datamined: https://repoe-fork.github.io/crafting_bench_options.json, mods.json, base_items.json, tags.json, fossils.json, mods_by_base.json, mod_types.json, essences.json (local copies in `.claude/scratch/repoe-3.29.3.3/`; scripts in `.claude/scratch/research-bench-metamods/inspect*.py`); https://repoe-fork.github.io/ and https://repoe-fork.github.io/data-formats/crafting_bench_options.html (schema: no field descriptions).

Cross-check only: PoB ModMaster.lua; https://poedb.tw/us/metamods; https://poedb.tw/us/Crafting_Bench; https://www.craftofexile.com/?page=metamods; earlier reports `docs/research/2026-10-30-1-prior-art-and-data.md`, sibling reports basic-currency and essences (leads only).
