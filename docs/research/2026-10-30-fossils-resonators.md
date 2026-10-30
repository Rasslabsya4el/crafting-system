# Fossils and resonators in 3.29

Ticket: [#9 Fossils and resonators in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/9) (map [#1](https://github.com/Rasslabsya4el/crafting-system/issues/1)). Date checked: 2026-10-30. Patch: 3.29.3.3, ordinary (non-Ruthless). Evidence rule: [#2, Q2](https://github.com/Rasslabsya4el/crafting-system/issues/2). Claim ids `FOS-nn`; open items `OPEN-nn`.

**Answer.** A fossil craft is a Chaos-Orb-style reroll of a **rare** item (all explicit mods, 4/5/6 mods at 8:3:1) done with a **fully socketed Chaotic resonator**; each socketed fossil changes the pool weights of mods through their tags (`implicit_tags`), and a few fossils do something else (force a mod, add mods, corrupt, fracture, lucky rolls, a random tag pair). The game files hold 25 fossils; every one is obtainable from Delve in 3.29; Alchemical (normal-item) resonators are not obtainable in ordinary 3.29. Weight effects are exact numbers in `fossils.json` (weight/100 = multiplier; 0 = block) and match the wiki row by row. Stacking across fossils is an owner decision (FOS-08). The only 3.29 fossil change is Fractured Fossil (official, FOS-20). What cannot be coded yet: the exact additive formula and the Corroded/Prismatic overlap case (OPEN-01, OPEN-02), mod count when a fossil forces a mod (OPEN-06), Glyphic candidate weights (OPEN-07), Tangled pair distribution (OPEN-04), Sanctified combination (OPEN-03), and the socket counts of three of the four resonator sizes (OPEN-05).

Counts: **33 admitted claims, 12 open items.** The 18 tag-weight fossils (Scorched, Frigid, Metallic, Jagged, Aberrant, Pristine, Dense, Aetheric, Serrated, Lucent, Shuddering, Deft, Fundamental, Bound, Opulent, Corroded, Prismatic, Faceted) are codable from FOS-02..FOS-10, FOS-15, FOS-25..FOS-27 and FOS-33, except the overlap cases named in OPEN-01 and OPEN-02. The other 7 (Bloodstained, Hollow, Fractured, Glyphic, Tangled, Sanctified, Gilded) are special (FOS-11..FOS-20).

Source abbreviations used in claims: official = pathofexile.com forum (GGG staff post); wiki = poewiki.net (page revision in "Sources read"); datamined = repoe-fork 3.29.3.3 export (`https://repoe-fork.github.io/<file>`, record id as key).

---

## 0. Reading the data: `fossils.json` fields

`fossils.json` is keyed by item metadata id (`Metadata/Items/Currency/<key>`). 445 records: **25 named fossils** (table T1) and **420 unnamed `RandomFossilOutcome1..420`** (the Tangled Fossil's outcomes, FOS-13). Fields (meaning from the repoe-fork field docs, `https://github.com/repoe-fork/repoe/blob/master/RePoE/docs/fossils.md`, and checked against the data):

| field | meaning |
|---|---|
| `positive_mod_weights` | list of `{tag, weight}`: a mod carrying `tag` gets multiplier `weight/100` (1000 = x10, 600 = x6, 3000 = x30). |
| `negative_mod_weights` | list of `{tag, weight}`: a mod carrying `tag` gets multiplier `weight/100`; `weight` 0 = the mod cannot be rolled ("No X"); 15 = x0.15 ("Fewer X"). |
| `added_mods` | mod ids added to the pool of rollable mods while this fossil is socketed. |
| `forced_mods` | mod ids guaranteed to appear (like an essence mod). |
| `allowed_tags` | item must have at least one of these tags, else the fossil cannot be used. |
| `forbidden_tags` | item must have none of these tags. |
| `sell_price_mods` | mod ids; one is picked as an implicit (Gilded only). |
| `corrupted_essence_chance` | chance (percent) of a forced random corrupted-essence mod. Glyphic 100; Tangled 10 (legacy residue, OPEN-04). |
| `rolls_lucky` | numeric values rolled twice, better kept (Sanctified only). |
| `changes_quality`, `rolls_white_sockets`, `mirrors` | legacy flags; `false` for all 25 in 3.29.3.3 (FOS-22, FOS-20). |
| `descriptions`, `blocked_descriptions` | tooltip text. `blocked_descriptions` are description lines of *other* fossils this one hides; the field docs call it "cosmetic only". It carries no weight rule: the effect lives in the tag weights. |
| `name` | empty for the 420 Tangled outcome records. |

Tag matching field: the weights are matched against the mod's `implicit_tags` in `mods.json` (FOS-03). Mods have `adds_tags` too (`has_attack_mod`, `has_caster_mod`), a different thing.

### T1. All 25 fossils (datamined, `fossils.json`, 3.29.3.3)

Weight shown as written in the file; multiplier = weight/100. "-" = empty. Every record has `changes_quality=false`, `mirrors=false`, `rolls_white_sockets=false`, `sell_price_mods=[]`, `allowed_tags=[]`, `forbidden_tags=[]` unless stated in the "special" column.

| Fossil | record key | positive (tag weight) | negative (tag weight) | added mods | forced mods | special |
|---|---|---|---|---|---|---|
| Scorched | `CurrencyDelveCraftingFire` | fire 1000 | cold 0 | - | - | - |
| Frigid | `CurrencyDelveCraftingCold` | cold 1000 | fire 0 | - | - | - |
| Metallic | `CurrencyDelveCraftingLightning` | lightning 1000 | physical 0 | - | - | - |
| Jagged | `CurrencyDelveCraftingPhysical` | physical 1000 | chaos 0 | - | - | - |
| Aberrant | `CurrencyDelveCraftingChaos` | chaos 1000 | lightning 0 | - | - | - |
| Pristine | `CurrencyDelveCraftingLife` | life 1000 | defences 0 | - | - | - |
| Dense | `CurrencyDelveCraftingDefences` | defences 1000 | life 0 | - | - | - |
| Corroded | `CurrencyDelveCraftingBleedPoison` | bleed 1000, poison 1000 | elemental 0 | - | - | - |
| Prismatic | `CurrencyDelveCraftingElemental` | elemental 600 | bleed 0, poison 0 | - | - | - |
| Aetheric | `CurrencyDelveCraftingCasterMods` | caster 1000 | attack 15 | - | - | - |
| Serrated | `CurrencyDelveCraftingAttackMods` | attack 1000 | caster 15 | - | - | - |
| Lucent | `CurrencyDelveCraftingMana` | mana 1000 | speed 0 | - | - | - |
| Shuddering | `CurrencyDelveCraftingSpeed` | speed 1000 | mana 0 | - | - | - |
| Bound | `CurrencyDelveCraftingMinionsAuras` | minion 1000, aura 1000, curse 1000 | - | - | - | - |
| Opulent | `CurrencyDelveCraftingQuality` | drop 1000 | - | - | - | "No Tagless modifiers" only as description key `NoTagless`; no numeric field (FOS-10) |
| Deft | `CurrencyDelveCraftingEnchant` | critical 1000 | attribute 0 | - | - | - |
| Fundamental | `CurrencyDelveCraftingSockets` | attribute 1000 | critical 0 | - | - | - |
| Faceted | `CurrencyDelveCraftingGemLevel` | gem 1000 | - | `DelveStrengthGemLevel1`, `DelveDexterityGemLevel1`, `DelveIntelligenceGemLevel1` | - | - |
| Bloodstained | `CurrencyDelveCraftingVaal` | - | - | - | - | `forbidden_tags`: heist_contract, heist_blueprint, heist_equipment; description "Has a Corrupted implicit modifier" |
| Hollow | `CurrencyDelveCraftingAbyss` | - | - | - | `DelveAbyssJewelSocket1` | `allowed_tags`: weapon, helmet, boots, gloves, body_armour |
| Fractured | `CurrencyDelveCraftingMirror` | - | - | - | - | description "Fracture a random modifier"; `mirrors=false` |
| Glyphic | `CurrencyDelveCraftingCorruptEssence` | - | - | - | - | `corrupted_essence_chance=100`; `allowed_tags`: weapon, body_armour, gloves, boots, helmet, shield, amulet, belt, ring, quiver |
| Tangled | `CurrencyDelveCraftingRandom` | - | - | 11 legacy ids (OPEN-04) | - | `corrupted_essence_chance=10` (legacy, OPEN-04); description "Random effects revealed when resonator is fully socketed" |
| Sanctified | `CurrencyDelveCraftingLuckyModRolls` | - | - | - | - | `rolls_lucky=true` |
| Gilded | `CurrencyDelveCraftingSellPrice` | - | - | - | - | `sell_price_mods`: `DoubleModSellPrice1..9` |

Tags present in `mods.json` `implicit_tags` of normally spawnable item prefixes/suffixes (2,725 mods, 3.29.3.3) with counts of mods carrying each fossil tag: fire 255, cold 234, lightning 217, physical 328, chaos 121, life 144, defences 295, bleed 36, poison 37, elemental 769, caster 314, attack 600, mana 145, speed 148, minion 82, aura 38, curse 18, drop 12, critical 151, attribute 62, gem 262, ailment 175, damage 1128, resistance 76; tagless (empty `implicit_tags`) 71. Script: `.claude/scratch/research-fossils-resonators/tagless.py`.

---

## 1. Admitted claims

Format: rule; then `Src` = kind, URL, quote, patch, checked 2026-10-30.

### Weight effects

**FOS-01 — The fossil set.** There are exactly 25 fossils in 3.29.3.3 (names in T1). Perfect, Enchanted and Encrusted no longer exist as separate items (renamed Opulent, Deft, Fundamental).
Src: datamined, `https://repoe-fork.github.io/fossils.json`, 25 records with non-empty `name`, e.g. `Metadata/Items/Currency/CurrencyDelveCraftingFire` `name`="Scorched Fossil"; same 25 `CurrencyDelveCrafting*` ids in `base_items.json` (`item_class` StackableCurrency, `release_state` released); patch 3.29.3.3. Renames: wiki, `https://www.poewiki.net/wiki/Fossil#Version_history`, "Perfect Fossils have been renamed to Opulent Fossils" (3.25.0) and 3.16.0 rows for Deft and Fundamental; patch 3.29. Checked 2026-10-30.

**FOS-02 — Weight to multiplier.** For each socketed fossil, a mod that carries a `positive_mod_weights` tag gets the multiplier `weight/100` of that fossil; a mod that carries a `negative_mod_weights` tag gets `weight/100`; negative weight 0 means the mod cannot be rolled while that fossil is socketed. Values: positive 1000 (x10), 600 (x6; Prismatic only), 3000 (x30; Tangled outcomes); negative 15 (x0.15; Aetheric, Serrated), 0 (blocks).
Src: datamined + wiki. Datamined: `fossils.json` `CurrencyDelveCraftingCasterMods` `positive_mod_weights`=[{caster,1000}], `negative_mod_weights`=[{attack,15}]; `CurrencyDelveCraftingElemental` positive [{elemental,600}]; `RandomFossilOutcome1` positive [{speed,3000}], negative [{resistance,0}]; all other values in T1. Wiki: `https://www.poewiki.net/wiki/Fossil#Mechanics`, table row "Aetheric Fossil … "Caster" x10 … "Attack" x0.15", and Tangled row `"<Random tag>" x30`, Prismatic `x6`; every one of the 19 weight-bearing wiki rows equals weight/100 of the matching record (checked row by row). Patch 3.29.3.3 (datamined), 3.29 (wiki rev 1702302). Checked 2026-10-30.

**FOS-03 — Matching field.** A fossil tag matches a mod when it is in the mod's `implicit_tags`. (`adds_tags` is not used: it holds only `has_attack_mod`-style tags; the repoe `fossils.md` sentence "matched against `mod["adds_tags"]`" is stale and contradicts the data.)
Src: datamined, `https://repoe-fork.github.io/mods.json`, field `implicit_tags`; repoe docs `mods.md`: "A list of the tags which apply to crafting methods like fossils and harvest crafting."; example `LocalAddedFireDamageTwoHand10` `implicit_tags`=[elemental_damage, damage, elemental, fire, attack], `adds_tags`=[has_attack_mod]. All 24 distinct fossil tags (fire, cold, lightning, physical, chaos, life, defences, bleed, poison, elemental, caster, attack, mana, speed, minion, aura, curse, drop, critical, attribute, gem, ailment, damage, resistance) occur in `implicit_tags` and none in `adds_tags`. Patch 3.29.3.3. Checked 2026-10-30.

**FOS-04 — The multiplier set is T1.** The tag effects of the 25 fossils are exactly the `positive_mod_weights`/`negative_mod_weights` in T1. The wiki's "Weight blockers" column = negative weight 0; "Fewer weight multipliers" = negative weight 15.
Src: datamined, `https://repoe-fork.github.io/fossils.json`, T1 records (values quoted in T1); wiki `https://www.poewiki.net/wiki/Fossil#Mechanics` table agrees in all rows (FOS-02). Wiki hedges this as "the interpretation most widely agreed upon by the community"; the numbers themselves are datamined. Patch 3.29.3.3. Checked 2026-10-30.

**FOS-05 — Corroded and Prismatic hybrid wording equals plain tags.** Corroded's "(Physical AND Ailment) OR (Chaos AND Ailment)" is the tags `bleed`, `poison` (x10 each, one boost per mod, FOS-06). Prismatic's "Elemental OR Fire OR Cold OR Lightning" is the tag `elemental` (x6). Prismatic blocks `bleed` and `poison`; Corroded blocks `elemental`. Implement per tag; the sets coincide on every spawnable item mod in 3.29.3.3 (72 mods carry bleed or poison; every mod with physical+ailment or chaos+ailment is among them and vice versa; every fire/cold/lightning mod also carries `elemental`; no mod carries both `elemental` and `bleed`/`poison`).
Src: datamined + wiki. Datamined: `fossils.json` `CurrencyDelveCraftingBleedPoison` positive [{bleed,1000},{poison,1000}] negative [{elemental,0}]; `CurrencyDelveCraftingElemental` positive [{elemental,600}] negative [{bleed,0},{poison,0}]; coincidence verified with `.claude/scratch/research-fossils-resonators/hybrid.py` over `mods.json`. Wiki: `https://www.poewiki.net/wiki/Fossil#Mechanics`, "(\"Physical\" AND \"Ailment\") OR (\"Chaos\" AND \"Ailment\") x10". Patch 3.29.3.3. Checked 2026-10-30. (The overlap behaviour with *other* fossils is OPEN-02.)

**FOS-06 — One boost per fossil per mod.** A single fossil affects a given mod at most once, even if several of its tags match (Bound: a mod tagged minion and aura gets x10, not x100 or x20).
Src: wiki, `https://www.poewiki.net/wiki/Fossil#Mechanics`, "Each fossil only affects a modifier once, even if multiple tags from the same fossil apply."; patch 3.29 (rev 1702302). Checked 2026-10-30.

**FOS-07 — Blocks beat boosts; opposing fossils may be socketed together.** If any socketed fossil blocks a mod (negative weight 0), the mod's weight is 0 regardless of any boost from another fossil. Conflicting fossils (e.g. Scorched + Frigid) can be socketed together; the `blocked_descriptions` field is display only.
Src: wiki, `https://www.poewiki.net/wiki/Resonator`, "Fossil modifiers that prevent certain types of modifiers from appearing supersede modifiers that grant more of a modifier type."; patch 3.29 (rev 1675208; no later row on this point). Datamined: repoe `fossils.md` calls `blocked_descriptions` "cosmetic only". Checked 2026-10-30.

**FOS-08 — Stacking across several fossils (owner decision).** Positive factors of different fossils add, negative factors multiply, blocks win. Reading used by the code (CoE convention, see OPEN-01 for the exact additive formula): for a mod, let P be the set of socketed fossils with a matching positive tag (each counted once, FOS-06) and N the set with a matching negative tag; if any matched negative weight is 0 the weight is 0; otherwise effective weight = base weight x (sum of the factors of P, or 1 if P is empty) x (product of the factors of N).
Src: owner, `https://github.com/Rasslabsya4el/crafting-system/issues/2#issuecomment-6529150116`, "Fossil factors stack as Craft of Exile does (additive positive factors, negatives multiply, blocks win)."; decided 2026-10-30; applies to patch 3.29.3.3. Checked 2026-10-30. (Wiki: "It is disputed whether different "More" multipliers stack additively or multiplicatively, though additive is the more widely accepted theory." — `https://www.poewiki.net/wiki/Fossil#Mechanics`.)

**FOS-09 — What the multipliers act on.** Fossil weight multipliers also apply to the weights of fossil-exclusive explicit mods (those from Glyphic and Faceted), but do not influence Bloodstained's corrupted-implicit outcome nor which mod Fractured Fossil fractures.
Src: wiki, `https://www.poewiki.net/wiki/Fossil#Mechanics`, "These weight multipliers also affect the weights of rolling fossil-exclusive explicit modifiers, such as from Glyphic Fossil or Faceted Fossil"; patch 3.29 (rev 1702302). Checked 2026-10-30.

**FOS-10 — Opulent.** Opulent multiplies the weight of mods tagged `drop` by 10 and removes every mod that has no tags at all (empty `implicit_tags`; 71 spawnable item mods in 3.29.3.3, e.g. group `ChanceToSuppressSpells` 10 mods, `StunRecovery`, `StunThresholdReduction`, `WarcryCooldownSpeed`). The tagless block is not a numeric field in the data; it rests on the wiki and the description key.
Src: wiki + datamined. Wiki: `https://www.poewiki.net/wiki/Opulent_Fossil#Mechanics`, "Tagless modifiers are those without any tags."; `https://www.poewiki.net/wiki/Fossil#Mechanics` "Opulent Fossil … "Drop" x10 … No tagless modifiers". Datamined: `fossils.json` `CurrencyDelveCraftingQuality` positive [{drop,1000}], `descriptions` {MoreDrop, NoTagless}. Patch 3.25.0 change (Perfect renamed, no quality), valid for 3.29. Checked 2026-10-30.

**FOS-11 — Sanctified lucky rolls.** With a Sanctified Fossil every numeric value of the rerolled mods is rolled twice and the better result is kept.
Src: wiki + datamined. Wiki: `https://www.poewiki.net/wiki/Sanctified_Fossil#Mechanics`, "the numerical values are each rolled twice and the better result is taken"; datamined `fossils.json` `CurrencyDelveCraftingLuckyModRolls` `rolls_lucky`=true. Patch 3.29 (rev 1701073; row 3.4.0 only). Checked 2026-10-30.

**FOS-12 — Sanctified weight factor.** Sanctified multiplies the weight of every mod by `1 + 0.01 x (mod required level - 40)` (required level 1 gives 0.61, level 83 gives 1.43). Required level = `required_level` in `mods.json`. Derived from a 1,000-roll player experiment (sectoidfodder, 2020-04-10) that the wiki states as the fact; the wiki page words it "data collected that suggests". How it combines with other fossils: OPEN-03.
Src: wiki + experiment (n=1000 Sanctified rolls, as cited by the wiki). `https://www.poewiki.net/wiki/Fossil#Mechanics`, "All modifiers x (1 + 0.01 * (<modifier's required level> - 40))"; `https://www.poewiki.net/wiki/Sanctified_Fossil#Further_analysis`, "the mod weight is increased by 1% per level required above 40 and reduced by 1% per level below"; experiment cited: `https://www.reddit.com/r/pathofexile/comments/fykyuv/data_from_1000_sanctified_fossil_rolls_and_a/` (not opened here: Reddit unreachable and the helper job failed twice). Patch 3.29 (rev 1702302 / 1701073). Checked 2026-10-30.

### Special fossils

**FOS-13 — Tangled picks a random tag pair.** When the resonator is fully socketed, a Tangled Fossil adds one "Greatly more P" effect (factor x30) and one "No N" effect (block), with tags P and N different, from the 21 tags ailment, attack, attribute, aura, caster, chaos, cold, critical, curse, damage, defences, elemental, fire, gem, life, lightning, mana, minion, physical, resistance, speed. The game data holds exactly the 21 x 20 = 420 ordered pairs, each once (`RandomFossilOutcome1..420`: positive tag weight 3000, negative tag weight 0). One pair applies per craft. The probability of each pair is OPEN-04.
Src: wiki + datamined. Wiki: `https://www.poewiki.net/wiki/Tangled_Fossil#Mechanics`, "Tangled Fossils adds a random Greatly more X and No X modifier to the resonator once all fossils are socketed." and "It cannot roll the same "Greatly more X" and "No X" tag."; datamined `fossils.json` `RandomFossilOutcome1` positive [{speed,3000}] negative [{resistance,0}] … `RandomFossilOutcome420`; counts verified with `.claude/scratch/research-fossils-resonators/tangled.py` (420 records, 21 distinct positive tags x 20, 420 distinct pairs, no pair with equal tags). Patch: change in 3.16.0, valid 3.29. Checked 2026-10-30.

**FOS-14 — Tangled adds no mods.** Since 3.16.0 Tangled no longer grants fossil-exclusive modifiers; "Greatly more Gem" does not unlock Faceted's gem-level mods.
Src: wiki, `https://www.poewiki.net/wiki/Tangled_Fossil#Version_history`, "Tangled Fossils now makes a random Modifier type much more likely, and prevents another random modifier type (previously granted any Fossil modifiers)." and `#Mechanics` "\"Greatly more Gem\" does not enable the +1 to Level of Socketed <Attribute> Gems modifiers exclusive to Faceted Fossil."; patch 3.16.0, valid 3.29 (rev 1702251). The datamined record still lists 11 `added_mods` (OPEN-04). Checked 2026-10-30.

**FOS-15 — Faceted adds three mods.** While a Faceted Fossil is socketed, three Delve-domain suffixes are added to the pool: `DelveStrengthGemLevel1` "+1 to Level of Socketed Strength Gems", `DelveDexterityGemLevel1`, `DelveIntelligenceGemLevel1` (same text with Dexterity/Intelligence). Each: domain `delve`, `generation_type` suffix, `required_level` 1, `implicit_tags` [attribute, gem], own family (`groups` `DelveStrengthGemLevel`, `DelveDexterityGemLevel`, `DelveIntelligenceGemLevel`). Spawn weights (first matching tag wins, in this order, `abyss_jewel` 0 and `jewel` 0 first, `default` 0):
- Strength: staff 1000, sceptre 1000, mace 1600, axe 1000, sword 1000, bow 750, dagger 750, claw 750, wand 750, str_armour 1600, int_armour 750, dex_armour 750, str_dex_armour 1000, str_int_armour 1000, dex_int_armour 750, str_dex_int_armour 1000, unset_ring 1000.
- Dexterity: staff 750, sceptre 750, mace 750, axe 1000, sword 1000, bow 1600, dagger 1000, claw 1000, wand 750, str_armour 750, int_armour 750, dex_armour 1600, str_dex_armour 1000, str_int_armour 750, dex_int_armour 1000, str_dex_int_armour 1000, unset_ring 1000.
- Intelligence: staff 1000, sceptre 1000, mace 750, axe 750, sword 750, bow 750, dagger 1000, claw 1000, wand 1600, str_armour 750, int_armour 1600, dex_armour 750, str_dex_armour 750, str_int_armour 1000, dex_int_armour 1000, str_dex_int_armour 1000, unset_ring 1000.
Being tagged `gem`+`attribute` they are boosted by Faceted (gem) and Fundamental (attribute) and blocked by Deft (attribute 0) under FOS-02/07/08.
Src: wiki + datamined. Wiki: `https://www.poewiki.net/wiki/Faceted_Fossil#Added_mods`, "The following fossil exclusive mods are added to the crafting pool when using this fossil:"; datamined `fossils.json` `CurrencyDelveCraftingGemLevel` `added_mods`; `mods.json` the three ids (fields as above). Patch 3.12.0 / 3.10.0, valid 3.29 (rev 1701033). Checked 2026-10-30.

**FOS-16 — Hollow forces an Abyssal socket suffix.** A Hollow Fossil guarantees the suffix `DelveAbyssJewelSocket1` "Has 1 Abyssal Socket" (group `AbyssJewelSocket`, `required_level` 1; spawn weights weapon/helmet/boots/gloves/body_armour 2000) and restricts use to weapons, helmets, gloves, boots and body armours. The mod replaces one of the item's sockets with an abyssal socket.
Src: wiki + datamined. Wiki: `https://www.poewiki.net/wiki/Hollow_Fossil#Mechanics`, "A resonator containing a Hollow Fossil has the effect of guaranteeing a suffix that grants Has 1 Abyssal Socket."; datamined `fossils.json` `CurrencyDelveCraftingAbyss` `forced_mods`=[DelveAbyssJewelSocket1], `allowed_tags`=[weapon, helmet, boots, gloves, body_armour]. Patch 3.29 (rev 1701069). Checked 2026-10-30. (Does the forced mod count in the 4–6 total: OPEN-06.)

**FOS-17 — Glyphic forces a corrupted-essence mod.** A Glyphic Fossil guarantees one essence modifier taken from the corrupted essences Essence of Delirium, Horror, Hysteria and Insanity (the mod listed for the item's class in `essences.json`; 22 classes each), is usable only on weapons, body armours, gloves, boots, helmets, shields, amulets, belts, rings and quivers, and other fossils still apply to which essence mod can appear (Jagged blocks essence mods with the chaos tag). Which candidate and with what weights: OPEN-07.
Src: wiki + datamined. Wiki: `https://www.poewiki.net/wiki/Glyphic_Fossil#Mechanics`, "guaranteeing an essence modifier from any of the corrupted essences, which are Essence of Delirium, Essence of Horror, Essence of Hysteria and Essence of Insanity"; datamined `fossils.json` `CurrencyDelveCraftingCorruptEssence` `corrupted_essence_chance`=100, `allowed_tags` (10 listed); `essences.json` `CurrencyEssenceDelirium1`, `CurrencyEssenceHorror1`, `CurrencyEssenceHysteria1`, `CurrencyEssenceInsanity1` (`type` {is_corruption_only: true, tier: 6}). Patch 3.29 (rev 1701071). Checked 2026-10-30.

**FOS-18 — Bloodstained corrupts.** A Bloodstained Fossil rerolls the item's modifiers (together with the other fossils), makes the item corrupted and adds a corrupted implicit; the implicit is not affected by the other socketed fossils; it replaces other existing implicits only when a Gilded Fossil is in the same resonator. Not usable on Heist contracts, blueprints, ally equipment. Which implicit: corruption ticket (B4), not here.
Src: wiki + datamined. Wiki: `https://www.poewiki.net/wiki/Bloodstained_Fossil#Mechanics`, "The implicit modifier added is not affected by other fossils, if used with a resonator with multiple fossil slots"; and "The item will reroll all modifiers (in combination with other Fossils) and become corrupted". Datamined `fossils.json` `CurrencyDelveCraftingVaal` `forbidden_tags`=[heist_contract, heist_blueprint, heist_equipment]. Patch 3.16.0, valid 3.29 (rev 1701024). Checked 2026-10-30.

**FOS-19 — Gilded adds a vendor implicit.** A Gilded Fossil adds the implicit "Item sells for much more to vendors" in addition to existing implicits (does not overwrite them). One of 9 variants is chosen by weight (`DoubleModSellPrice1..9`, weights 6000, 1000, 6000, 1000, 6000, 10, 2000, 1, 1000). It has no effect on explicit-mod outcomes.
Src: wiki + datamined. Wiki: `https://www.poewiki.net/wiki/Gilded_Fossil#Mechanics`, "This implicit mod is separate from the item's actual implicit mod(s) and will not overwrite other implicit mods when applied"; datamined `mods.json` `DoubleModSellPrice1` `spawn_weights` [{default,6000}] … `DoubleModSellPrice8` [{default,1}]; `fossils.json` `CurrencyDelveCraftingSellPrice` `sell_price_mods`. Patch 3.29 (rev 1701040). Checked 2026-10-30.

**FOS-20 — Fractured Fossil in 3.29.** From 3.29.0 a Fractured Fossil fractures one of the modifiers the resonator rolls, chosen at random; it cannot be used on fractured or influenced items (and, per the wiki, not on existing synthesised items). It no longer creates a split copy. Fossil weights do not affect which mod is fractured (FOS-09).
Src: official + wiki + datamined. Official: `https://www.pathofexile.com/forum/view-thread/3985332`, "Item Changes": "Fractured Fossils now Fracture a random Modifier, and cannot be used on Fractured and Influenced items."; patch 3.29.0 (thread created 2026-07-17). Wiki: `https://www.poewiki.net/wiki/Fractured_Fossil#Mechanics`, "A resonator containing a Fractured Fossil has the effect of fracturing one of the modifiers it rolls at random." (rev 1701036). Datamined `fossils.json` `CurrencyDelveCraftingMirror` `descriptions` {Fracture: "Fracture a random modifier"}, `mirrors`=false. Checked 2026-10-30. (Uniformity of the choice: OPEN-08.)

**FOS-21 — Fossil-exclusive explicit mods in 3.29.** Since 3.10.0 fossils craft no prefix/suffix that cannot be obtained elsewhere, except those from Faceted, Bloodstained and Hollow; Bloodstained's were removed in 3.16.0. So in 3.29 the only fossil-exclusive explicit mods are Faceted's three (FOS-15) and Hollow's one (FOS-16). The other Delve-domain mods in `mods.json` (186 records, domain `delve`) are not reachable by any 3.29 fossil.
Src: wiki, `https://www.poewiki.net/wiki/Fossil#Version_history`, "Fossils can no longer craft any prefix or suffix mods that cannot be obtained elsewhere, with the exception of those granted by Faceted, Bloodstained and Hollow Fossils." (3.10.0); `https://www.poewiki.net/wiki/Modifier#Domain`, "(exclusive mods from Bloodstained Fossil are removed in version 3.16.0)". Datamined cross-point: `fossils.json` `added_mods`/`forced_mods` of the 22 other fossils are empty (only Faceted, Hollow, and Tangled's legacy list are not). Patch 3.29 (Fossil rev 1702302, Modifier rev 1703013). Checked 2026-10-30.

**FOS-22 — No fossil changes quality or socket colours.** In 3.29.3.3 no fossil sets quality, rolls white sockets or enchants: `changes_quality` and `rolls_white_sockets` are false for all 25. (Perfect's quality is gone since 3.25.0; Fundamental's sockets and Deft's enchant since 3.16.0.)
Src: datamined, `https://repoe-fork.github.io/fossils.json`, all 25 records `changes_quality`=false, `rolls_white_sockets`=false; wiki `https://www.poewiki.net/wiki/Opulent_Fossil#Version_history`, "it no longer grants Improved Quality." (3.25.0), and `https://www.poewiki.net/wiki/Fossil#Version_history` 3.16.0 row for Fundamental ("previously granted more Sockets, with the possibility of White Sockets"). Patch 3.29.3.3 (datamined), 3.25.0/3.16.0 (wiki). Checked 2026-10-30.

### Obtaining

**FOS-23 — All 25 fossils are obtainable in ordinary 3.29, from Delve only.** Since 3.28.0 fossils have no source outside Delve; every fossil has a Delve source (Fractured: Humid Fissure nodes in Sulphur Vents; Hollow: Crystal Spire; Tangled: Haunted Tomb; Faceted: Molten Cavity; Bloodstained: Stonewood Hollow; Glyphic: Time-Lost Cavern; the other 19 drop from Fossilised Remains in listed biomes, some behind fractured walls only). Niko also sells fossils for Azurite. Prices/availability belong to the price file, not the rules.
Src: official + wiki. Official: `https://www.pathofexile.com/forum/view-thread/3913392` (Content Update 3.28.0, Stacey_GGG, 2026-02-26), Delve: "Removed sources of Fossils from places other than Delve throughout the game."; wiki `https://www.poewiki.net/wiki/Fossil#Acquisition`, "Fractured Fossil … Drops from completing a Humid Fissure node in Sulphur Vents biomes in the Azurite Mine." and the biome table listing all 25 names; patch 3.28.0, valid 3.29 (no 3.29.x note changes it, FOS-24 note below). Checked 2026-10-30.

**FOS-24 — Nothing else in 3.29.x changes fossils or resonators.** The 3.29.0 notes (2026-07-17) contain one fossil change (Fractured Fossil, FOS-20, plus the no-longer-states-Synthesised wording) and no resonator change; the other 25 3.29.x threads (3.29.0 hotfixes and restart fix, 3.29.0b, 3.29.1, 3.29.2, 3.29.3, 3.29.3b notes, hotfixes and maintenance) contain no line mentioning Fossil, Resonator or Chaos Orb (3.29.0 mentions Delve only for Abyssal Jewels in Abyss biomes and Heist reward chests).
Src: official, thread ids 3985332, 3987816, 3987917, 3988043, 3988602, 3989412, 3990009, 3990158, 3990172, 3990687, 3991672, 3991769, 3991893, 3994431, 3994498, 3994902, 3995749, 3996516, 3996584, 3996608, 3997633, 3999213, 3999365, 3999550, 4000431, 4001117 (all `https://www.pathofexile.com/forum/view-thread/<id>`), quote: none (negative result); cross-read in full text on the wiki mirrors `https://www.poewiki.net/wiki/Version_3.29.0` (fossil lines: only the two Fractured Fossil bullets), `Version_3.29.0b`, `Version_3.29.1`, `Version_3.29.2`, `Version_3.29.3`, `Version_3.29.3b` (0 hits for fossil/resonator/delve/chaos orb). Patch 3.29.0–3.29.3b. Checked 2026-10-30. Limit: the forum threads were read through WebFetch summaries (direct HTTP is blocked, 403), not a full-text grep; the full-text check is the wiki mirrors.

### Resonators

**FOS-25 — A resonator must be fully socketed, and is consumed with its fossils.** The craft works only when every socket holds a fossil; a partially filled resonator is not usable. Fossils can be taken out of a partly filled resonator; once it is full they cannot be reclaimed. One craft uses one resonator and all its fossils.
Src: wiki, `https://www.poewiki.net/wiki/Resonator`, "allow for the crafting of rare items when fully socketed with fossils" and "Fossils can be removed from a partially-socketed resonator, but once a resonator has been fully socketed, the fossils cannot be reclaimed."; patch 3.29 (rev 1675208). Checked 2026-10-30.

**FOS-26 — No duplicate fossil in one resonator.** At most one fossil of each type per resonator (so at most one Tangled, one Sanctified).
Src: official + wiki. Official: `https://www.pathofexile.com/forum/view-thread/2197540` (Delve FAQ, Bex_GGG, 2018-08-15): "Can we stack copies of the same fossils in a Resonator?" "No."; wiki `https://www.poewiki.net/wiki/Resonator`, "Resonators cannot be socketed with multiple of the same fossil."; patch 3.4.0 (official), 3.29 (wiki). Checked 2026-10-30.

**FOS-27 — A Chaotic resonator works like a Chaos Orb on a rare item.** A fully socketed Chaotic resonator rerolls all explicit modifiers (and their number) of a rare item, as a Chaos Orb does, with the pool weights changed by the fossils. The pool, family exclusion and ilvl rules are those of the Chaos Orb (ticket on the affix draw).
Src: official + wiki. Official: `https://www.pathofexile.com/forum/view-thread/2197540`, "There are two types of Resonators - Chaotic and Alchemical. These have the functionality of Chaos Orbs and Orbs of Alchemy respectively."; wiki `https://www.poewiki.net/wiki/Resonator#Mechanics`, "Chaotic and Alchemical Resonators function similarly to Chaos Orb and Orb of Alchemy respectively."; `https://www.poewiki.net/wiki/Crafting`, "Most Fossils | Only usable on rare items | Reforges a rare item's modifiers; increases the spawn weights of certain modifier tags and reduces or nullifies the spawn weights of other modifier tags". Patch 3.4.0 (official), 3.29 (wiki, Crafting rev 1697718). Checked 2026-10-30.

**FOS-28 — Chaotic resonators accept rare items only.** All four Chaotic resonators (Primitive, Potent, Powerful, Prime) are used on rare items; not on normal and not on magic items. Size does not change the rarity rule.
Src: datamined + wiki. Datamined `base_items.json` `Metadata/Items/Delve/DelveStackableSocketableCurrencyReroll1..4`: `properties.description`="Reforges a rare item with new random modifiers", `properties.directions`="Right click this item then left click a rare item to apply it." (same four in the old class `DelveSocketableCurrencyReroll1..4`); wiki `https://www.poewiki.net/wiki/List_of_resonators`, Chaotic resonators table, "Reforges a rare item with new random modifiers". Patch 3.29.3.3. Checked 2026-10-30. Answers the old Q30: NO, a normal item cannot take a newly obtained resonator.

**FOS-29 — Alchemical resonators are not obtainable in ordinary 3.29.** Alchemical resonators ("Upgrades a normal item to a rare item", normal items only) were removed from all sources in 3.16.0 (existing ones still work) and exist as a source only in Ruthless (3.20.0). In ordinary 3.29 only pre-existing legacy copies exist; the planner must not offer them as a craft step unless the owner adds a legacy/buy input.
Src: wiki. `https://www.poewiki.net/wiki/List_of_resonators`, "Alchemical resonators are drop disabled in the core game, but any existing ones can still be used in permanent leagues."; `https://www.poewiki.net/wiki/Resonator#Version_history` 3.16.0 "Alchemical Resonators are no longer purchasable from Niko, and can no longer be obtained from chests or any other sources." and 3.20.0 "Alchemical Resonators can now be found only in Ruthless mode."; `#Ruthless_mode` "can only be applied to normal rarity items". Datamined `base_items.json` `DelveStackableSocketableCurrencyUpgrade1..4` description "Upgrades a normal item to a rare item". Patch 3.29 (rev 1675208/1675209). Checked 2026-10-30.

**FOS-30 — Chaotic resonators are obtainable.** Primitive, Potent, Powerful and Prime Chaotic resonators drop in the core game (drop levels 34, 34, 34, 68) and Niko sells resonators for Azurite.
Src: wiki + datamined. `https://www.poewiki.net/wiki/List_of_resonators`, "Chaotic resonators can drop in the core game."; `https://www.poewiki.net/wiki/Niko,_Master_of_the_Depths`, "He also sells Fossils and Resonators for Azurite."; datamined `base_items.json` `DelveStackableSocketableCurrencyReroll1..4` `drop_level` 34, 34, 34, 68, inventory 1x1, 1x2, 2x2, 2x2. Patch 3.29. Checked 2026-10-30.

**FOS-31 — Socket counts: only Powerful = 3 is stated.** There are four Chaotic sizes (Primitive, Potent, Powerful, Prime). The Powerful Chaotic Resonator has 3 fossil sockets. 1-socket and 3-socket resonators exist (so the number of sockets varies by size); "ones with many sockets are harder to find". The counts for the other three sizes are OPEN-05.
Src: wiki + official. Wiki: `https://www.poewiki.net/wiki/Powerful_Chaotic_Resonator`, "3 fossils can be inserted into this item." (rev 1681394); official: `https://www.pathofexile.com/forum/view-thread/2197540` "Each can have a number of sockets. Ones with many sockets are harder to find than ones with few." and 3.8.0e notes (wiki mirror `https://www.poewiki.net/wiki/Version_3.8.0e`) "1-socket Resonators were more rare than intended and 3-socket Resonators were more common than intended". Patch 3.29 (wiki), 3.4.0/3.8.0e (official). Checked 2026-10-30.

**FOS-32 — Resonators inherit fossil use restrictions; metamods block them.** A resonator cannot be used on an item that any socketed fossil forbids (allowed/forbidden item categories in FOS-16, 17, 18) and cannot be used on items with a metamod ("Prefixes Cannot Be Changed", "Suffixes Cannot Be Changed", "Cannot roll Attack Modifiers", "Cannot roll Caster Modifiers"); the multimod "Can have up to 3 Crafted Modifiers" does not block.
Src: wiki. `https://www.poewiki.net/wiki/Resonator`, "Resonators also inherit item use restrictions from socketed fossils." and "Unlike these orbs, resonators cannot be used on items with metamods"; `https://www.poewiki.net/wiki/Metamod#Rules_and_Exceptions` ("Fossils | Usage Prevented" for each metamod; "When using essence or fossil on an item with metamod (other then the multi-craft mod), the game will warn you that Failed to apply item"). Patch 3.29 (Resonator rev 1675208, Metamod rev 1700578; latest Metamod row 3.27.0, unrelated). Checked 2026-10-30.

**FOS-33 — Mod count after a fossil craft.** A fossil craft on a rare item gives a rare item with 4, 5 or 6 explicit mods in the ratio 8:3:1, the Chaos Orb count (FOS-27: the resonator has "the functionality of" a Chaos Orb). Whether fossils that force or add mods change how the 4–6 is counted: OPEN-06.
Src: wiki + official. Wiki: `https://www.poewiki.net/wiki/Chaos_Orb#Mechanics`, "For regular items, Chaos Orbs result in a rare item with an affix count of 4, 5, or 6 at a ratio of 8:3:1."; with FOS-27 sources. Also accepted by the owner for rare rerolls ([#2](https://github.com/Rasslabsya4el/crafting-system/issues/2) Settled before the grill: "Rare reroll 4/5/6 = 8:3:1 is accepted (wiki)"). Patch 3.29 (Chaos Orb rev 1681144). Checked 2026-10-30. Composition note: no source states the 8:3:1 for fossil crafts in these words; it follows from "functionality of Chaos Orbs" (official) and "function similarly" (wiki). No large-sample fossil-specific count experiment found.

---

## 2. Open (not admitted)

| id | question | what is known (source kind, not admitted) | what settles it |
|---|---|---|---|
| OPEN-01 | Exact additive formula for positive factors across fossils: sum of the factors (10 + 10 = 20) or 1 + sum of (factor - 1) (= 19)? | Owner decision says "as Craft of Exile does"; prototype reading of CoE code `poec_getModdedWeight` is the sum (Scorched+Serrated on a weight-126 mod = 2520), CoE (not evidence). Wiki says additive "more widely accepted" but disputed. | Owner confirms "sum of factors, 1 if none". A large-sample experiment (two fossils matching one mod) would make it evidence. **Blocks multi-fossil codes.** |
| OPEN-02 | Do Corroded (bleed/poison) and Prismatic (elemental) factors bypass other fossils' single-tag factors for the same mod (CoE "hybrid" behaviour: Corroded+Jagged on a bleed mod = 10) or add with them as plain tags (data-literal: 10+10 = 20)? Concerns 72 spawnable mods (all 36 bleed mods carry physical, all 37 poison mods carry chaos) and fossil sets like Corroded+Jagged, Corroded+Aberrant, Corroded+Serrated (route R07 uses Corroded+Jagged+Metallic+Shuddering). | CoE (via prototype trace, cross-check only): bypass. Datamined tag lists (FOS-05): no hybrid concept in the data. Wiki: "(Physical AND Ailment) OR (Chaos AND Ailment) x10" and "Each fossil only affects a modifier once", silent on interaction with other fossils. | Large-sample experiment (Corroded+Jagged vs Corroded alone, count bleed mods on a base that rolls them) or a GGG statement. Owner decision may substitute. **Blocks Corroded/Prismatic combinations with a matching second fossil.** |
| OPEN-03 | How does Sanctified's level factor combine with tag factors and blocks (multiply? add? is it one of the "positive" additive terms? does it apply to Faceted/Glyphic added mods)? Is the factor floored/rounded? | Wiki lists it in the same "multipliers" table; example numbers on Sanctified page use it alone (`25*(1+(0.83-0.40)) = 35.75`). The experiment (n=1000, wiki citation) tested Sanctified alone as far as the wiki says. | Experiment with Sanctified + a tag fossil, or owner decision (e.g. multiply the whole weight). |
| OPEN-04 | Tangled: probability of each of the 420 pairs; whether it may pick a tag another fossil already boosts or blocks (wiki: may pick one already boosted; blocked "unknown, likely not"); whether the legacy data (11 `added_mods`, `corrupted_essence_chance`=10) still acts. | Wiki Tangled page: "It does not appear to have significant weightings between the different tags." (cites a Reddit post); "It ''can'' roll the same tag as a "More X" from other socketed fossils."; 3.16.0 note says it no longer grants fossil modifiers. Data: all 420 records exist once each; legacy fields remain. | Large-sample experiment on Tangled outcomes (revealed in the resonator tooltip) or GGG statement; or owner decision "uniform over the 420 pairs, legacy fields ignored", or leave Tangled out of v1. |
| OPEN-05 | Fossil sockets of Primitive, Potent and Prime Chaotic resonators. Expected 1, 2, 4 (Powerful 3 is admitted). | Inventory sizes 1x1, 1x2, 2x2, 2x2 and names; official 3.8.0e confirms 1- and 3-socket resonators exist; CoE offers a cap of 1–4 (prototype); poedb page does not state counts. | Wiki/official statement per size, or the owner reads the in-game tooltip of one of each. Affects only the choice and price of the resonator for k = 1, 2, 4 fossils, not the weight math. |
| OPEN-06 | Mod count with forced or added mods: does the forced Hollow suffix or Glyphic essence mod count inside the 4/5/6 total (then the rest is rolled to fill it), or is it on top? Does Faceted's added pool change the count? | Prototype/CoE: forced mod counts inside the total (not evidence). Wiki says only "guaranteeing a suffix". The essences ticket treats the analogous question for essences. | Large-sample experiment (Hollow crafts, count mods) or GGG statement. **Blocks Hollow and Glyphic.** |
| OPEN-07 | Glyphic: base weights of the candidate corrupted-essence mods and how the one forced mod is drawn (the four essence mods for the item's class have `spawn_weights` [{default,0}] in `mods.json`, i.e. no weight in the data; fossil weights then multiply them per FOS-09). Also exclusion against fractured/existing mods. | Prototype/CoE: each candidate base weight 1000, then fossil-transformed (not evidence). | Experiment on Glyphic outcomes per item class, or owner decision (equal base weight). **Blocks Glyphic.** |
| OPEN-08 | Fractured Fossil: is the fractured mod chosen uniformly among the rolled explicit mods (including a forced Hollow/Glyphic mod and Faceted's added mods)? When is it chosen (after the full reroll)? | Wiki: "fracturing one of the modifiers it rolls at random"; Fracturing Orb page: "randomly fracture one explicit modifier". Fossil weights do not influence it (FOS-09). | Same resolution as the Fracturing Orb ticket (uniform among explicit mods), or a sample. |
| OPEN-09 | Are effective weights rounded to integers in the game (e.g. 126 x 0.15 = 18.9)? | Prototype: CoE keeps fractions. No source. | Not settleable cheaply; default to exact rationals unless a source shows rounding. |
| OPEN-10 | Combinations of fossils that both force a mod, and general legality of a fossil craft on corrupted, mirrored, synthesised (non-unique, Standard only), influenced, fractured or unidentified items; whether item classes such as jewels, flasks, maps accept fossils. Only the fossil-specific lists are admitted (FOS-16..20, 32). | Wiki Fossil 3.12.4: usable on Heist contracts, blueprints, ally equipment; Fractured page: not on synthesised. | The generic eligibility ticket / wiki "Corrupted", "Mirrored" pages; Hollow+Glyphic by experiment. |
| OPEN-11 | Exact meaning of `blocked_descriptions` and `descriptions` ordering: display only? | repoe docs: "cosmetic only". Guide routes (e.g. Corroded + Metallic) show opposing fossils can be socketed together. | Accepted as display only (FOS-07); mark settled if the owner agrees. |
| OPEN-12 | Does the Sanctified/other fossil pool use the item's `generation_weights` percentages (attack_dagger, wand_can_roll_caster_modifiers) before or after the fossil factor? (Order matters only if weights are rounded.) | None. | Covered by OPEN-09 and the affix-draw ticket. |

**Blocks coding the fossil primitive:** OPEN-01 (owner confirm, one line), OPEN-02 (only for sets containing Corroded or Prismatic plus a second matching fossil), OPEN-06 (Hollow, Glyphic), OPEN-07 (Glyphic). Tangled (OPEN-04), Sanctified combination (OPEN-03) and Fractured (OPEN-08) can be coded behind an "unsettled" switch or left out of v1. OPEN-05 only affects resonator pricing.

---

## 3. Prototype re-audit

Source: `docs/mechanics/fossils_resonators.md` on `archive/prototype` (all its claims were `reimplemented-from-CoE` or player-report unless noted), `docs/OPEN_QUESTIONS.md` Q30, `docs/mechanics/patch_3_29.md`.

| prototype claim | verdict |
|---|---|
| Ordinary path = rerolls a rare item with fossil-adjusted weights | confirmed: FOS-27 |
| Base must be `is_fossil`; magic excluded; normal permitted by CoE metadata | changed: magic and normal both excluded for Chaotic resonators (FOS-28); Alchemical not obtainable (FOS-29) |
| Outcome-affecting metamods block the craft; multimod alone exempt | confirmed: FOS-32 |
| CoE offers resonator-size cap 1–4 | partly confirmed: sizes exist, only Powerful = 3 admitted (FOS-31, OPEN-05) |
| Zero marks a blocked tag, otherwise percentage/100 = factor | confirmed against game files: FOS-02 |
| Positive factors add (mode `a`), negatives multiply, blocks win | owner decision: FOS-08; exact formula OPEN-01 |
| Multiplicative sensitivity retained | dropped: owner decision fixes additive (FOS-08) |
| Hybrid tag entries bypass the single-tag factors; matched block = 0 | unbacked as a bypass: OPEN-02; the hybrids themselves are plain tags: FOS-05 |
| Missing positive/negative factor defaults to 1 | consistent with FOS-08 formula (1 when set is empty) |
| Opulent has a separate untagged-mod zero path | confirmed: FOS-10 |
| Dispatcher: special fossils branch separately | confirmed in kind: FOS-13..20 |
| Examples with synthetic inputs (100 x 3, 100 x 4 = 700) | arithmetic only; 700 equals the sum reading (OPEN-01) |
| Weights returned without integer rounding (126 x 0.15 = 18.9) | unbacked: OPEN-09 |
| Fractured Fossil replaced in 3.29 (S39) | confirmed: FOS-20 (official 3.29.0) |
| Fractured Fossil old special path (split) must not be used | confirmed obsolete: FOS-20 |
| Named table (S56): Serrated Attack x10 / Caster x0.15; Aetheric Caster x10 / Attack x0.15; Scorched, Frigid, Metallic, Jagged, Aberrant, Pristine, Dense, Lucent, Shuddering, Deft, Fundamental x10 with the opposite tag blocked; Bound minion/aura/curse x10; Faceted gem x10; Opulent drop x10 + tagless blocked; Prismatic elemental x6; Corroded physical+ailment / chaos+ailment x10 | confirmed row by row: FOS-02, FOS-04, FOS-05, FOS-10 (now datamined, no longer player interpretation) |
| Prismatic wiki wording "Elemental OR Fire OR Cold OR Lightning" vs CoE "elemental only" | resolved: identical on 3.29.3.3 mods, `elemental` only in the data: FOS-05 |
| Fossil applies once even if several tags match: Bound on a minion+aura mod = 1000, CoE gives 2000 (Q13.01) | changed: wiki says once per fossil (FOS-06); the CoE 2000 is rejected |
| Sanctified factor `1 + .01*(required level - 40)`, level 80 gives 1.4 | confirmed: FOS-12 (level 80 -> 1.40); combination OPEN-03 |
| Tangled: random boosted tag x30 and a different blocked tag; overlap with other fossils unconfirmed | confirmed: FOS-13; overlap OPEN-04 |
| Glyphic: base-compatible corrupted-essence candidates, each base weight 1000, then fossil transform, one forced mod | partly confirmed: forced corrupted-essence mod (FOS-17); base weight 1000 unbacked: OPEN-07 |
| Perfect: quality 15–30, 16 values | changed: Perfect no longer exists since 3.25.0, no fossil changes quality: FOS-22 |
| Gilded: append vendor-value implicit only if absent | changed: adds an implicit on top of existing ones (FOS-19); "only if absent / no duplicate" unbacked, no effect on explicit mods |
| Hollow: force an Abyss-socket suffix, occupying 1 suffix | confirmed: FOS-16; counting in the 4–6 total OPEN-06 |
| Weights do not affect Bloodstained implicit or Fractured selection (S56) | confirmed: FOS-09 |
| Ordinary Chaotic resonators reforge rares; Alchemical target normal items, now Ruthless/legacy | confirmed: FOS-28, FOS-29 |
| Resonator must be full; no duplicate type; block overrides boost; fossils contribute use restrictions; 2-slot with 1 fossil unusable | confirmed: FOS-25, FOS-26, FOS-07, FOS-32 |
| Completed sockets lock the fossils, the preparation consumes inputs | confirmed: FOS-25 |
| Primitive/Potent/Powerful/Prime = 1/2/3/4 sockets; rarity depends on type not size | rarity: confirmed (FOS-28); socket counts: only 3 admitted (OPEN-05) |
| Two fossils on the same mod through different tags add (Scorched+Serrated, weight 126 -> 2520) | follows from FOS-08 (sum reading); OPEN-01 |
| S4 table of 16 ordinary fossils (CoE ids) | confirmed against `fossils.json` (T1) |
| Prismatic boosts elemental only x6; Corroded boosts hybrids x10 and blocks elemental | confirmed: FOS-05 |
| Offline hybrid trace (Corroded+Jagged on physical,ailment = 1000; Corroded+Serrated = 2000; Prismatic+Scorched on elemental,fire = 1600) | CoE-only; unbacked: OPEN-02 |
| Glyphic/Hollow/Sanctified have separate rules | confirmed: FOS-11, 12, 16, 17 |
| Q30: newly obtained resonator on a normal item = NO | confirmed: FOS-28, FOS-29 |
| 3.29 patch deltas: Fractured Fossil fractures a random mod and excludes fractured/influenced inputs | confirmed: FOS-20 |
| "18 supported fossils" in the prototype adapter | consistent: 18 tag-weight fossils here, 7 special (FOS-01) |

---

## 4. Cross-checks (not evidence)

- **Craft of Exile (via the prototype's reading of `package.js` and `poec_data.json`, and the earlier research report `docs/research/2026-10-30-1-prior-art-and-data.md`).** Agrees on every multiplier of the 16 plain fossils and on x6/x10 for Prismatic/Corroded. Disagrees or differs on: hybrid bypass (OPEN-02), several tags of one fossil adding (Bound 2000 vs wiki 1000; wiki wins, FOS-06), Perfect Fossil quality (obsolete since 3.25.0), Fractured Fossil (old split path), no integer rounding (OPEN-09), Glyphic base weight 1000 (OPEN-07). Its Sanctified formula is also from the 1,000-roll data and CoE's FAQ says an assumption remains (report line 61).
- **poedb (`https://poedb.tw/us/Fossil`, `https://poedb.tw/us/Resonator`, read 2026-10-30 through WebFetch).** Shows qualitative lines ("More Physical Ailment or Chaos Ailment modifiers", "No Elemental modifiers"); no numeric multipliers, no statement on how several fossils combine, no socket counts for the four Chaotic resonators; confirms the four Chaotic resonators say "Reforges a rare item with new random modifiers".
- **Path of Building:** not checked in this ticket (PoB does not model fossil crafting).
- **Earlier report 1 (prior art):** "I did not find primary GGG evidence … proving the combination operator for two fossils affecting the same mod" agrees with the status here: stacking is an owner decision (FOS-08), not evidence.
- **repoe-fork field docs:** `fossils.md` says weights are matched against `adds_tags`; the data and `mods.md` show `implicit_tags` (FOS-03). `fossils.md` mentions fields `enchants`, `changes_quality` ("between 15 and 30") that are empty or false in 3.29.3.3.

---

## 5. Sources read

Official (pathofexile.com forum):
- Content Update 3.29.0 (Curse of the Allflame): https://www.pathofexile.com/forum/view-thread/3985332 (Item Changes read; WebFetch)
- 3.29.0 hotfix threads 3987816, 3987917, 3988043, 3988602; 3.29.0b 3989412, 3990009, 3990158, 3990172, 3990687; 3.29.1 3991672, 3991769, 3991893; 3.29.2 3994431, 3994498, 3994902, 3995749; 3.29.3 3996516, 3996584, 3996608, 3997633, 3999213, 3999365, 3999550, 4000431; 3.29.3b 4001117 (all `https://www.pathofexile.com/forum/view-thread/<id>`, WebFetch; forum index https://www.pathofexile.com/forum/view-forum/patch-notes)
- Content Update 3.28.0: https://www.pathofexile.com/forum/view-thread/3913392
- Delve FAQ (Bex_GGG, 2018-08-15): https://www.pathofexile.com/forum/view-thread/2197540
- 3.4.0 patch notes https://www.pathofexile.com/forum/view-thread/2201187 and Delve items thread https://www.pathofexile.com/forum/view-thread/2201188 (no resonator/fossil mechanics text)

Wiki (poewiki.net, revisions read 2026-10-30): [Fossil](https://www.poewiki.net/index.php?title=Fossil&oldid=1702302), [Resonator](https://www.poewiki.net/index.php?title=Resonator&oldid=1675208), [List of resonators](https://www.poewiki.net/index.php?title=List_of_resonators&oldid=1675209), [Fractured Fossil](https://www.poewiki.net/index.php?title=Fractured_Fossil&oldid=1701036), [Sanctified Fossil](https://www.poewiki.net/index.php?title=Sanctified_Fossil&oldid=1701073), [Glyphic Fossil](https://www.poewiki.net/index.php?title=Glyphic_Fossil&oldid=1701071), [Hollow Fossil](https://www.poewiki.net/index.php?title=Hollow_Fossil&oldid=1701069), [Tangled Fossil](https://www.poewiki.net/index.php?title=Tangled_Fossil&oldid=1702251), [Faceted Fossil](https://www.poewiki.net/index.php?title=Faceted_Fossil&oldid=1701033), [Bloodstained Fossil](https://www.poewiki.net/index.php?title=Bloodstained_Fossil&oldid=1701024), [Gilded Fossil](https://www.poewiki.net/index.php?title=Gilded_Fossil&oldid=1701040), [Opulent Fossil](https://www.poewiki.net/index.php?title=Opulent_Fossil&oldid=1701053), [Chaos Orb](https://www.poewiki.net/index.php?title=Chaos_Orb&oldid=1681144), [Metamod](https://www.poewiki.net/index.php?title=Metamod&oldid=1700578), [Crafting](https://www.poewiki.net/index.php?title=Crafting&oldid=1697718), [Modifier](https://www.poewiki.net/index.php?title=Modifier&oldid=1703013), [Fractured item](https://www.poewiki.net/index.php?title=Fractured_item&oldid=1701034), [Powerful Chaotic Resonator](https://www.poewiki.net/index.php?title=Powerful_Chaotic_Resonator&oldid=1681394); also Primitive/Potent/Prime Chaotic and the four Alchemical resonator pages, Perfect Fossil (redirect), Fracturing Orb, Orb of Alchemy, Niko, Delve, Item socket, Version 3.4.0, 3.8.0, 3.8.0e, 3.28.0, 3.29.0, 3.29.0b, 3.29.1, 3.29.2, 3.29.3, 3.29.3b.

Datamined (repoe-fork 3.29.3.3, local copy in `.claude/scratch/repoe-3.29.3.3/`): `fossils.json`, `mods.json`, `base_items.json`, `essences.json`; docs https://github.com/repoe-fork/repoe/blob/master/RePoE/docs/fossils.md and `.../mods.md`; file list https://repoe-fork.github.io/. Query scripts: `.claude/scratch/research-fossils-resonators/*.py`.

Owner: https://github.com/Rasslabsya4el/crafting-system/issues/2#issuecomment-6529150116.

Cross-check only: https://poedb.tw/us/Fossil, https://poedb.tw/us/Resonator; prototype `archive/prototype:docs/mechanics/fossils_resonators.md`, `docs/OPEN_QUESTIONS.md`, `docs/SOURCES.md`, `docs/mechanics/patch_3_29.md`; `docs/research/2026-10-30-1-prior-art-and-data.md`.

Not opened / failed: the Reddit experiment posts cited by the wiki (Sanctified 1,000 rolls; Tangled) — Reddit is unreachable from WebFetch and the `gpt-research` helper job died twice ("worker process died before finishing"), so no large-sample experiment was obtained for any open item; the wiki API (`api.php`) answered with the bot challenge and was not used; the forum threads were readable only through WebFetch summaries (HTTP 403 direct).
