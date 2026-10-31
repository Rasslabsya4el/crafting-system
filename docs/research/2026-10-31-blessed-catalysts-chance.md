# Blessed Orb, catalysts and Orb of Chance in 3.29

Ticket: [#89 Blessed Orb, catalysts and Orb of Chance in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/89) (map #1; inventory rows M-20, M-27, M-28; benchmark R05). Claim-id prefixes `BLE` (Blessed), `CAT` (catalysts), `CHA` (Orb of Chance).
Date checked: 2026-10-31. Patch: PoE 1 3.29.3.3, ordinary (non-Ruthless). Datamined = repoe-fork export of 3.29.3.3 (exported 2026-10-19, local copy `.claude/scratch/repoe-3.29.3.3`).

**Answer.**

- **Blessed Orb**: rerolls the *values* of the implicits of an item, never their identity; usable only where an implicit has a range (71 of the 115 ring/amulet/belt bases, 24 of 46 rings, 36 of 53 amulets, 11 of 16 belts). New values are drawn inside the implicit's range. The one open fork is whether the old value can come up again: the wiki says no, Craft of Exile's code does not exclude it (`BLE-04`, O-01). Nothing in the 3.25–3.29 notes changes it.
- **Catalysts**: 13 exist in the data (10 regular + Tainted + Sinistral + Dextral), all for rings, amulets and belts, stack 20, Ultimatum is the only source since 3.29.0. One quality type at a time; a different catalyst wipes the old quality. One catalyst adds `floor(f)` or `floor(f)+1` points, `f = max(1, min(30·e^(−ilvl/30) − 0.3, 20))` with random rounding (ilvl 75: 2 or 3 points; ilvl 84: 1 or 2; ilvl 95+: always 1), capped at 20%. The wiki's probability table matches this formula to the last digit. At 20% a matching modifier is multiplied by 1.20 on its stored integer and **rounded down**; the match is by the modifier's tag (a modifier with two matching tags is boosted once). Catalyst quality does not change mod weights and Augmentation, Regal and Exalted no longer use it up (since 3.15.0; nothing says another currency touches it), so it behaves as a separate, finish-line cost: expected catalysts to 20% = 9.5 at ilvl 75, 13.3 at ilvl 84, 20 at ilvl 95+.
- **Orb of Chance**: normal item → magic, rare or unique. **The magic/rare split is not published anywhere I could reach**; the unique chance is not a flat number: it depends on which drop-anywhere uniques exist on the base and their tiers (GGG staff 2013 + wiki), rough odds 1 in a few hundred (T4/T5) to 1 in hundreds of thousands (T0). A base with no eligible unique cannot give a unique (the unique roll falls back to another rarity). Omen of Fortune forces a unique, so it has no role when a unique is a failed try. The bench craft "Reroll the Rarity of a non-Unique item" costs 1 Orb of Chance (no Scouring), works on magic/rare directly, and *can* create uniques (it did on synthesised items until 3.26.0c).

Conventions. Source kinds: `official` (GGG notes or staff posts), `wiki` (poewiki.net), `datamined` (repoe-fork 3.29.3.3), `coe` (Craft of Exile code or data), `third-party code` (Path of Building, PoEDB), `owner`. "Patch" is the patch the source speaks for; for wiki pages it is the page's last behaviour-relevant "Version history" row. Wiki permalinks: Orb_of_Chance oldid=1681150 (edited 2026-07-26), Blessed_Orb oldid=1681166 (2026-07-26), Catalyst oldid=1675910 (2026-07-21), Quality oldid=1673652 (2026-07-16), Omen_of_Fortune oldid=1702543 (2026-09-20), Crafting_Bench oldid=1700860 (2026-08-16), Unique_item oldid=1699287 (2026-08-07), Guide:Analysis_of_unique_item_tiers oldid=1702744 (2026-09-26). Every line carries `[chk 2026-10-31]`. Wiki table cells are quoted as rendered text.

---

## 1. Blessed Orb (M-20)

**BLE-01 Input.** A Blessed Orb is applied to "another item"; it needs at least one implicit with a range of values. Items without implicits or with fixed implicits are not valid inputs.
- datamined: `base_items.json` `Metadata/Items/Currency/CurrencyRerollImplicit` `description` = "Randomises the values of the implicit modifiers of an item", `directions` = "Right click this item then left click another item to apply it." Patch 3.29.3.3. [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Blessed_Orb#Mechanics: "It cannot be used on items without implicit modifiers or whose implicit modifiers do not have a range of values." Patch: last behaviour row 3.28.0 (map bosses and highlight only). [chk 2026-10-31]

**BLE-02 Effect: values only, identity kept.** It rerolls the values of the implicit modifier(s), the "top values of an item above the line"; explicit modifiers are Divine Orb's job (CUR-18).
- wiki: https://www.poewiki.net/wiki/Blessed_Orb: "re-roll values of the implicit modifiers on a piece of equipment. (This means the top values of an item above the line and not the bottom 6 values)". [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Crafting#Randomising_numerical_values (quoted in CUR-18): Blessed "Randomises the values of implicit modifiers". [chk 2026-10-31]

**BLE-03 Special implicits are valid.** Synthesised items and items with Eldritch implicits take it. Corrupted items do not (CUR-21).
- wiki: https://www.poewiki.net/wiki/Blessed_Orb#Mechanics: "They can be used on items with special implicits, such as synthesised items items with Eldritch implicit modifiers. They cannot be used to alter implicit modifiers on corrupted items". Patch 3.28.0. [chk 2026-10-31]
- Note: the sentence is garbled ("synthesised items items with Eldritch"); read as "synthesised items and items with Eldritch implicit modifiers". Whether *both* Eldritch implicits (Eater and Exarch) are rerolled is not stated (O-12).

**BLE-04 New value: inside the range, uniform; whether the old value is excluded is Open.**
- coe: https://www.craftofexile.com/packages/package.js `poec_simRerollImplicits` (local copy `sources/raw/coe/package.js`, line 2546): each integer range is drawn as `poec_rand(low, high+1, true)`, i.e. uniform over low…high inclusive; decimal ranges in hundredths; the old value is not excluded. [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Blessed_Orb#Mechanics: "Blessed Orbs can not roll the same implicit value that the original item had. If the current implicit value is low, then on average you have better odds of rolling a high implicit value, and vice versa." No citation on the page; version history never mentions it. Patch: page text unchanged since 2026-07-26. [chk 2026-10-31]
- Conflict, not resolved by sources (prototype Q24 says the same). See O-01 for the effect size and the 15-orb test.

**BLE-05 Catalyst quality is applied on top of the rolled base value.** The stored roll is the base value; the catalyst factor multiplies it afterwards (CAT-10). Evidence: R06 asks for "42 Strength" implicit on a Heavy Belt at 20% Intrinsic; the Heavy Belt implicit is `StrengthImplicitBelt1` 25–35 and 35 × 1.2 = 42, i.e. the maximum base roll.
- datamined: `mods.json` `StrengthImplicitBelt1` `additional_strength` min 25 max 35; `Metadata/Items/Belts/Belt4` (Heavy Belt) implicits = [`StrengthImplicitBelt1`]. Patch 3.29.3.3. [chk 2026-10-31]
- third-party code: Path of Building `src/Modules/ItemTools.lua` `itemLib.formatValue` (commit f6f230c, 2026-10-29): the mod's base value is resolved first, then `floorSymmetric(value * valueScalar)` "apply modifier magnitude". [chk 2026-10-31]
- Scope: R06 is a guide's text (PoE Vault, 2026); the 42 = 35 × 1.2 match is arithmetic, not a second proof.

**BLE-06 Where Blessed applies (census, datamined).** Of released bases with an implicit: ranged implicit present on Amulet 36/53, Ring 24/46, Belt 11/16, Shield 29/87, Wand 20/29, Rune Dagger 15/18, Quiver 15/22, Gloves 13/13, Bow 12/15, Boots 10/14, Dagger 7/13, Helmet 4/10, Claw 3/28, Staff 3/16, Body Armour 3/5, One Hand Sword 1/30. Eldritch implicits exist in the data as 2,070 `eater_of_worlds_implicit` and 2,016 `searing_exarch_implicit` mod records. Patch 3.29.3.3. [chk 2026-10-31] (counted by script on `base_items.json` + `mods.json`).
- Smallest ranges on jewellery: 3 values (Prismatic Ring +(8–10)% all Elemental Resistances, Formless Ring, Vermillion Ring, Cerulean Ring, Pearlescent Amulet, Splitnewt and Longtooth Talismans); the only two-value implicit is Steel Ring `Adds (3-4) to (10-14) Physical Damage to Attacks`.

**BLE-07 3.29.0 retunes three dagger implicit ranges and tells players to refresh old items with a Blessed Orb.**
- official (reproduced on the wiki): https://www.poewiki.net/wiki/Version_3.29.0: "Dagger Base Types with 30% increased Global Critical Strike Chance Implicit modifiers now have values of 40-45%. Existing items can be updated using a Blessed Orb." (same for 40%→50–55%, 50%→60–65%). [chk 2026-10-31]
- Consequence for the data model: Blessed rerolls into the *current* range; items in the planner are built from current data, so nothing to model.

**BLE-08 Change audit 3.25.0–3.29.2.** Backlinks of `Blessed_Orb` from Version pages 3.25+: 3.26.0b (usable on Expedition Logbooks), 3.28.0 (rerolls Conqueror/Elder Guardian maps; highlights the values), 3.29.0 (dagger note above). None changes the equipment effect. Pages 3.29.1 and 3.29.2 link to none of Blessed, Chance, Omen of Fortune or the catalyst pages. Late-3.29.3 hotfix notes (3.29.3 to 3.29.3.3) were not scanned for these items. [chk 2026-10-31]

---

## 2. Catalysts (M-28)

### 2.1 The items

**CAT-01 Thirteen catalysts, stack 20, for rings, amulets and belts.**
- datamined: `base_items.json`, tag `catalyst`, 13 items `Metadata/Items/Currency/CurrencyJewelleryQuality*`: Abrasive (Attack), Accelerating (Speed), Fertile (Life and Mana), Imbued (Caster), Intrinsic (Attribute), Noxious (Physical and Chaos Damage), Prismatic (Resistance), Tempering (Defence), Turbulent (Elemental Damage), Unstable (Critical), Sinistral (Prefix), Dextral (Suffix), Tainted (random type and amount, corrupted jewellery only). `properties.stack_size` = 20; `directions` = "Right click this item then left click a ring, amulet or belt to apply it. Has greater effect on lower item level, non-unique jewellery. The maximum quality is 20%."; `description` ends "Replaces other quality types". Patch 3.29.3.3. [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Catalyst (List of catalysts): same texts; drop level 68 for Fertile, Prismatic and Tempering, 1 for the rest. [chk 2026-10-31]

**CAT-02 Source and stack.** Since 3.29.0 Ultimatum is the only source and the stack is 20 (was 10). Priced by trade only, no crafting-side acquisition.
- official (reproduced on the wiki): https://www.poewiki.net/wiki/Version_3.29.0: "Catalysts now have a maximum stack size of 20 (previously 10)."; "Ultimatum is now the exclusive source of Catalysts." [chk 2026-10-31]

**CAT-03 Quality type is single; a different catalyst replaces it and restarts from 0%.**
- wiki: https://www.poewiki.net/wiki/Catalyst: "Using a different type of catalyst on an item that already has quality will replace the quality type, starting again from 0%." Patch: current page (3.29), version rows 3.25.0 and later unrelated. [chk 2026-10-31]
- datamined: all 13 `description`s: "Replaces other quality types". [chk 2026-10-31]

**CAT-04 Quality cap is 20%.**
- datamined: `directions` of every catalyst: "The maximum quality is 20%." [chk 2026-10-31]
- Overflow (a catalyst whose gain would pass 20%): the sources say "maximum 20%", not how an overflow is handled. Modelled as `min(20, q + gain)` (O-06).

### 2.2 How much quality one catalyst adds

**CAT-05 Gain per catalyst depends on item level, not rarity (3.25.0).**
- official: https://www.pathofexile.com/forum/view-thread/3531661 (3.25.0 notes, read 2026-09-21 and kept in `sources/raw/research/official-quality-3.25.txt`): "The rarity of the item is no longer relevant when applying Cartographer's Chisels, Blacksmith's Whetstones, Armourer's Scraps, Glassblower's Baubles, and Catalysts to non-Unique items. Instead, the amount of Quality they provide is now based on the item level. These currencies now apply 20% Quality to very low-level equipment, with this amount reducing as the item level increases." Patch 3.25.0. [chk 2026-10-31, text from the 2026-09-21 copy; the live thread sits behind a Cloudflare check I did not pass]
- wiki: https://www.poewiki.net/wiki/Quality#Amount: "The amount of quality given by a quality-increasing currency item depends on the equipment's item level. The higher the item level, the less quality each currency item will give." Patch: version row 3.25.0. [chk 2026-10-31]

**CAT-06 The formula and the random rounding.** `f(ilvl) = max(1, min(30·e^(−ilvl/30) − 0.3, 20))`; one application adds `floor(f)` points with probability `1 − frac(f)` and `floor(f)+1` points with probability `frac(f)` (no fraction → exactly `f`). Unique items always get 1 (outside v1).
- wiki: https://www.poewiki.net/wiki/Quality#Amount: formula "f(x) = max(1, min(30·e^(−1/30×ilvl) − 3/10, 20))" and the table of "probabilities for different levels of items and their amount of quality that will be added by the currency". Patch: as CAT-05. [chk 2026-10-31]
- Check by script (this note): the formula reproduces the table's rows exactly: ilvl 75 → 83.75% for +2 and 16.25% for +3; ilvl 80 → 21.55% / 78.45% (+1 / +2); ilvl 84 → 47.57% / 52.43%; ilvl 86 → 59.34% / 40.66%; ilvl 90 → 80.64% / 19.36%; ilvl 95+ → 100% for +1; ilvl 12 → 19.04% (+19) / 80.96% (+20). The table is the wiki's reading of the formula, not a game dump: no experiment confirms the *random rounding* (O-05).
- Derived (script, formula): application count to reach 20% from 0: ilvl 60 → 5.75 mean (p90 6); 65 → 6.81 (7); 70 → 7.99 (9); 75 → 9.53 (10); 80 → 11.45 (12); 82 → 12.36 (14); 84 → 13.35 (15); 85 → 13.87 (15); 86 → 14.42 (16); 90 → 16.89 (19); 95 and up → 20 (20). The prototype got 14.4237 / p90 16 at ilvl 86, the same.

**CAT-07 Catalyst quality is no longer a crafting input or consumable for Augmentation, Regal, Exalted.** Since 3.15.0 quality does not raise the chance of rolling a modifier with a matching tag, and Augmentation, Regal Orb, Exalted Orb and Elderslayer's Exalted Orb no longer use it up. The 3.15.0 note says only "specific Currency"; nothing says Chaos, Scouring, Annulment, essences or bench crafts change catalyst quality, and none did before. That they leave it alone is an inference from silence (O-09), consistent with PoB and CoE keeping quality as plain item state.
- official (reproduced on the wiki): https://www.poewiki.net/wiki/Version_3.15.0: "Catalysts no longer affect the chances of rolling related modifiers on jewellery through crafting, and Quality on jewellery is no longer removed when crafting with specific Currency." [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Catalyst#Version_history: "Prior to version 3.15.0, catalyst quality on jewellery also increased the chances of hitting a modifier with matching tags when using an Orb of Augmentation, a Regal Orb, an Exalted Orb, or an Elderslayer's Exalted Orb on the item." [chk 2026-10-31]

### 2.3 What quality does to a modifier

**CAT-08 Matching modifiers are multiplied by (100 + quality)/100, implicits and explicits alike.**
- wiki: https://www.poewiki.net/wiki/Catalyst: "Catalyst quality on jewellery improves the effect of the implicit and explicit modifiers of the specified type, depending on the modifier tags." and https://www.poewiki.net/wiki/Quality (table): "Increased modifier magnitude based on catalyst tag; affects implicit and explicit affixes". [chk 2026-10-31]
- coe: `poec_simParseCatValue` (package.js line 2183): `val = 1; ... val += catalyst.val/100`. [chk 2026-10-31]
- third-party code: Path of Building `src/Classes/Item.lua` `getCatalystScalar`: `return (100 + quality) / 100`. Commit 356bc5c (2026-10-29), v2.67.2. [chk 2026-10-31]
- Three independent implementations agree on 1 + q/100; no GGG sentence gives the number.

**CAT-09 One boost per modifier; a catalyst type only ever matches by tag (or side).** The first matching catalyst tag counts, no stacking inside a modifier. An item carries one catalyst type, so two types never meet.
- coe: `poec_simParseCatValue` `break` after the first match. third-party code: PoB `getCatalystScalar` returns on the first match. [chk 2026-10-31]
- Hybrid modifiers: every stat of a matching modifier is scaled (PoB scales each value of a line; CoE scales each value); Open only in that no in-game sample was found (O-09).

**CAT-10 Rounding: the stored (integer) value is multiplied and rounded down.**
- third-party code: PoB `src/Modules/ItemTools.lua:134` `value = floorSymmetric(value * valueScalar) -- apply modifier magnitude`, applied on the integer in the stat's internal unit; commit f6f230c, 2026-10-29. [chk 2026-10-31]
- coe: `poec_simApplyCatMod(val, mod)` = `Math.floor(val*mod)` for integers and `Math.floor(val*100*mod)/100` for values with decimals. [chk 2026-10-31]
- official (staff, example, not a rule statement): https://devtrackers.gg/pathofexile/p/c038cd2a-ggg-help-please-catalyst-no-worky-on-immortal-flesh (Mark_GGG, 2022): "Stat values are inherently integers."; "With the quality modifier, the base roll of 20997 becomes 25196.4, which rounds down to 25196 as the stored value." The example's fraction is .4, so it fits floor and nearest alike (O-08).
- Integer rule for the planner (no floating point): `scaled = (v · (100 + q)) // 100` on the repoe stat integer. A target "displayed value ≥ N at quality q" is a base-roll threshold `v ≥ ceil(100·N / (100 + q))`.
- R05/R06 check: R06 "14% Increased Attributes" at 20%: T1 `PercentageAllAttributesInfluence2` is 10–12; 12 × 1.2 = 14.4 → 14, so the target means "roll the maximum 12". Threshold `ceil(1400/120)` = 12. Consistent.

**CAT-11 Which modifiers each catalyst boosts: by `implicit_tags` of the modifier.**

| Catalyst | Tags | Ring/amulet/belt mod records boosted (of 312) |
|---|---|---|
| Abrasive | `attack` | 56 |
| Accelerating | `speed` | 6 |
| Fertile | `resource` (life and mana mods carry it; PoB also lists `life`, `mana`) | 55 |
| Imbued | `caster` | 10 |
| Intrinsic | `attribute` | 37 |
| Noxious | `physical_damage`, `chaos_damage` | 8 |
| Prismatic | `resistance` | 36 |
| Tempering | `defences` (PoB also lists `armour`, `evasion`, `energyshield`) | 47 |
| Turbulent | `elemental_damage` | 48 |
| Unstable | `critical` | 12 |
| Sinistral | modifier is a prefix | all prefixes |
| Dextral | modifier is a suffix | all suffixes |

- third-party code: https://poedb.tw/us/Catalyst "Catalyst / Tags" table (read 2026-10-31): Turbulent `elemental_damage`, Imbued `Caster`, Abrasive `Attack`, Tempering `Defences`, Fertile `resource`, Prismatic `Resistance`, Intrinsic `Attribute`, Noxious `physical_damage` + `chaos_damage`, Accelerating `Speed`, Unstable `Critical`. [chk 2026-10-31]
- third-party code: PoB `Item.lua` `catalystTags` (lines 16–29) with the same list plus Dextral = `suffix`, Sinistral = `prefix`, set from the modifier line's side (`mod.prefix` / `mod.suffix`, lines 48–53). [chk 2026-10-31]
- coe: `poec_data.json` `catalysts.seq` (10 regular; no Tainted, Sinistral, Dextral): same tags, in its own `jewellery_*` types (`jewellery_resource`, `jewellery_defense`, `jewellery_elemental` ...). [chk 2026-10-31]
- datamined check (script on `mods.json` 3.29.3.3, 312 non-influence ring/amulet/belt prefix/suffix records in 51 families): the PoEDB set and the PoB set boost *exactly the same records* for each of the ten catalysts (0 differences), because every life and mana mod carries `resource` and every defence mod carries `defences`. 209 records match one catalyst, 53 match two (e.g. `AddedFireDamage1`: Turbulent or Abrasive; `IncreasedAttackSpeed1`: Abrasive or Accelerating; life leech: Abrasive or Fertile), 50 match none (flask, gem level, rarity, light radius ...). [chk 2026-10-31]
- Build-time rule: derive "catalysts that boost this modifier" from the modifier's `implicit_tags` (and its side for Sinistral/Dextral); do not keep a hand-written list.

**CAT-12 Non-scalable lines.** Among 99 distinct ring/amulet/belt modifier lines (explicit and implicit) only `#% increased Explicit/Prefix/Suffix Modifier magnitudes` implicits are flagged not scalable in PoB's generated table `src/Data/ModScalability.lua` (979 not-scalable lines of about 11,700). None of these carries a catalyst tag. [chk 2026-10-31]
- third-party code: PoB `Data/ModScalability.lua` ("This file is automatically generated ... Item data (c) Grinding Gear Games"), commit 356bc5c. Lines flagged `isScalable = false`.

**CAT-13 Crafted (bench) and fractured modifiers.** The wiki says "implicit and explicit modifiers"; PoB applies the scalar to every modifier line of the item (no crafted/fractured exception); CoE applies it to all `iaffixes`. No in-game sample (O-09). R05's step order (catalyst, then bench) suggests the bench craft is boosted too.
- wiki/PoB/CoE as in CAT-08. [chk 2026-10-31]

**CAT-14 Tainted Catalyst is outside the ordinary rules.** Corrupted ring, amulet or belt only; random quality type and amount; odds unpublished; a corrupted item takes none of the ten orbs (CUR-21), so it can only be the last step. Candidate for B4 only.
- datamined: `CurrencyJewelleryQualityVaal` description "Applies a random quality type and amount of quality to a Corrupted ring, amulet or belt". [chk 2026-10-31]

**CAT-15 Vendor recipes** (3 same catalysts → 1 random catalyst; 20% quality normal jewellery → matching catalyst; jewellery with ≥40% total of one type → catalyst) exist on the wiki; they never beat buying and are not modelled. [chk 2026-10-31]

---

## 3. Orb of Chance (M-27)

**CHA-01 Input and result.** A normal item; the result is a random rarity: magic, rare or unique. Items of other rarities are refused.
- datamined: `CurrencyUpgradeRandomly` `description` = "Upgrades a normal item to a random rarity", `directions` = "Right click this item then left click a normal item to apply it." Patch 3.29.3.3. [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Orb_of_Chance: "the resulting item is more likely to become a magic or rare item". Patch: last behaviour row 3.27.0d (Alt swap), 3.28.0 keybind. [chk 2026-10-31]

**CHA-02 The split between magic and rare is unpublished.** The wiki gives no number; the 2013 staff posts say only that rarity is rolled first. In the 3.29.3.3 data the Orb has no weights: the roll is item-generation code, not data.
- wiki: Orb_of_Chance page has no magic/rare figure; its odds section gives unique tiers only (CHA-04). [chk 2026-10-31]
- Open: O-02, with the sample size an in-game test needs (section 5).

**CHA-03 Rarity is rolled first, then the unique (and which one).** Chancing and dropping roll the rarity first; if the unique roll lands where the base has no eligible unique, the result is a rare or magic instead.
- official (staff): Mark_GGG, 2013-08-04, https://web.archive.org/web/2021/https://www.pathofexile.com/forum/view-thread/488664/filter-account-type/staff : "The game DOES roll rarity first"; "Rhys's comment is correct in the case of repeatedly chance/scouring" (the comment: "You'd most likely have 7 rare/magic vestments instead"). [chk 2026-10-31] (2013; the wiki Unique_item page cites it as current.)
- wiki: https://www.poewiki.net/wiki/Guide:Analysis_of_unique_item_tiers#Currency_outcomes: "When using a Tainted Mythic Orb or Orb of Chance, if a tier is rolled for which there are no eligible outcomes a unique item will not be produced, instead the item will be destroyed (mythic orb) or a different rarity will be rolled. The exception is Tier 4 and Tier 5, which are believed to be bundled together into a super-tier". Marked on the page "believed". [chk 2026-10-31]

**CHA-04 The unique chance depends on the uniques that exist on the base, not on a flat number.**
- official (staff, patch of the source: 2013-08-01, in the 0.10.7 to 1.0.0g era per the wiki's version history; the wiki still repeats it for the current game, nobody re-tested it on 3.29.3.3): Mark_GGG, 2013-08-01, https://web.archive.org/web/2021/https://www.pathofexile.com/forum/view-thread/485201/filter-account-type/staff : "They do not have a flat chance to obtain a unique, regardless of how "rare" that unique is supposed to be. If the only unique of a base type is a rarely occurring one, then chances have a low chance to get uniques on that base type. Adding a more common unique to the same type means that chances on that item will have an significantly increased chance to roll uniques". [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Orb_of_Chance#Mechanics: "The chance for an Orb of Chance to hit a unique item depends on its unique item tier; these odds get exponentially worse with higher tier items"; "T5/T4: 1 in a few hundred; T3: 1 in a few thousands; T2: 1 in a couple tens of thousands; T1: 1 in multiple tens of thousands; T0: 1 in multiple hundreds of thousands" (footnote: "Preliminary testing from Prohibited Library prior to version 3.21.0; better estimates in progress"). Patch: pre-3.21 testing; page text unchanged since 2026-07-26. [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Guide:Analysis_of_unique_item_tiers: "Any data regarding unique tiers beyond version 3.14.0 is based on black box testing and estimates"; Orb of Chance "believed to use the MoreValuable distribution" (pre-3.19 weights T5 40.8%, T4 39.8%, T3 17.3%, T2 1.9%, T1 0.13%, T0 0.026%; the page says the tier-first model is "likely outdated"); "Orb of Chance ignores item level of the base item". [chk 2026-10-31]
- Rule for the planner: the unique result is a failure; its probability enters only as a loss from the magic/rare success (about 1/several hundred at worst for a base that has a common unique). See O-03.

**CHA-05 Items that can never become unique** (so the Orb can only give magic or rare): synthesised, fractured, with an Eldritch implicit, with a Runesmithing enchantment.
- wiki: https://www.poewiki.net/wiki/Orb_of_Chance#Mechanics: "Synthesised items and fractured items cannot be turned into a unique item. Items with Eldritch implicit modifiers or a Runesmithing enchantment also cannot be turned into a unique item." (Gilded Fossil implicit items are allowed.) [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Unique_item: "It is impossible to transform a non-unique fractured or synthesised item or an item with an Eldritch implicit modifier into a unique item." [chk 2026-10-31]
- Influenced bases stay influenced: Unique_item: "It is possible to get an influenced version of a unique item ... by using an Orb of Chance on an influenced version of the base item." [chk 2026-10-31]

**CHA-06 Unique items are not a target (owner).** A unique result is a failed try; unique items are never a target.
- owner: https://github.com/Rasslabsya4el/crafting-system/issues/81 decision 4 (2026-10-31, in chat): "Unique items are never a target. An Orb of Chance that makes a unique counts as a failed try". Decision 5 of the same issue: "quality from catalysts is a target (B2, R05's catalyst quality)". Decision 3: equipment, jewellery and jewels only (so the Orb of Chance and the bench reroll apply to jewels too; catalysts do not). [chk 2026-10-31]

**CHA-07 Omen of Fortune.** Consumed when an Orb of Chance is used on an item that can become unique, forcing a unique; not consumed if the base has no eligible unique; one Omen per combat area; drops as a Ritual reward (drop restricted, drop level 80); exists in 3.29.3.3 data.
- datamined: `Metadata/Items/Currency/AncestralOmenOnChanceMakeUnique` "Omen of Fortune" released, drop level 80, `description` = "Will be Consumed when you use an Orb of Chance on an item which can become Unique to ensure it does so". [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Omen_of_Fortune#Mechanics: "If no uniques exist for the basetype, it will not consume the Omen. If only one unique exists for the basetype, it will always become that unique. If multiple items exist for the basetype, it will randomly become any of the possible uniques, weighted by their rarity tier." [chk 2026-10-31]
- Role: none when a unique is a failure; excluded from the action list.

**CHA-08 Scour-chancing.** Orb of Scouring takes a magic or rare item back to normal (CUR-16, CUR-17); holding Alt while using an Orb of Chance switches to an Orb of Scouring (3.27.0d).
- wiki: Orb_of_Chance#Mechanics: "The process of using a Orb of Scouring to make a magic or rare item white again to repeat the process with the same base is referred to as "scour-chancing"." Version row 3.27.0d. [chk 2026-10-31]
- Cost of one scour-chance try = 1 Orb of Chance + 1 Orb of Scouring; 4 Orbs of Chance trade for 1 Orb of Scouring at several vendors (wiki), a fixed exchange, not a price.

**CHA-09 Bench craft "Reroll the Rarity of a non-Unique item".** Costs 1 Orb of Chance (no Scouring), is unlocked from the start, is available on 40 item classes including Ring, Amulet, Belt and Jewel, works on the magic or rare item in place, and can produce a unique.
- datamined: `crafting_bench_options.json` entry with `actions.reroll_rarity` = true, `bench_tier` 0, `cost` = {`CurrencyUpgradeRandomly`: 1}, master "Niko, Master of the Depths", 40 item classes. Patch 3.29.3.3. [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Crafting_Bench: row "Starts unlocked | Reroll the Rarity of a non-Unique item | 1x Orb of Chance"; version history 3.26.0c "Fixed a bug where the Crafting Bench option "Reroll the rarity of a non-Unique item" could be used on Synthesised items"; note: "Between version 3.26.0 and version 3.26.0c Hotfix 5, it was temporarily possible to use the "Reroll the Rarity of a non-Unique item" craft to create otherwise unobtainable versions of items, such as unique items with synthesised implicit modifiers". [chk 2026-10-31]
- wiki Orb_of_Chance: the craft "has the same effect and cost as using an Orb of Chance (and an Orb of Scouring)"; it does not count for the "Left to Chance" achievement. [chk 2026-10-31]
- Reddit confirms the bench craft yields uniques (section 7, thread 1pbq771) and "combines chances and scourings" (thread 1nyue7c). That the odds equal the Orb's is assumed from "same effect" (O-04).

**CHA-10 Change audit.** The wiki version history of the Orb: 0.10.7 "much more likely to create common Unique items", 1.0.0g (ilvl limit removed), 3.27.0d (Alt swap), 3.28.0 (keybind). No Version page from 3.25.0 to 3.29.2 changes the outcomes. [chk 2026-10-31]

---

## 4. Re-audit of the prototype (`git show archive/prototype:docs/mechanics/...`)

| Prototype statement | Verdict |
|---|---|
| `blessed_orb.md`: wiki excludes the old value, CoE does not; open (Q24) | Same finding here (BLE-04, O-01); added a test that settles it |
| `quality_catalysts.md`: increment law (S47), 14.4237 applications at ilvl 86, p90 16 | Re-derived and extended to a table (CAT-06) |
| `quality_catalysts.md`: "magnitude rounding, tag overlap and Tainted odds remain unsourced" | Rounding: floor, three sources (CAT-10). Tag overlap: no stacking, a modifier counts once, and a modifier may match two catalyst types (CAT-09, CAT-11). Tainted: still unpublished |
| CoE's own increments 5/2/1 by rarity | Stale (pre-3.25); not used |
| CoE `catFullEffect = 0.2` weight boost for catalysts | Stale since 3.15.0 (CAT-07); the CoE emulator still shows catalyst-weighted odds |

---

## 5. Open points

- **O-01 Blessed: can the old value come up again?** Wiki: no (uncited). CoE code: yes (uniform over the full range). Effect: with an n-value range and a target value other than the current one, the hit chance per Blessed is 1/(n−1) (wiki) or 1/n (CoE), so the expected number of Blessed Orbs differs by the ratio n/(n−1) (a Heavy Belt Strength implicit 25–35, 11 values: 10 vs 11 Orbs for one specific value, 10%). **Test**: put Blessed Orbs on a Prismatic Ring (+(8–10)% all Elemental Resistances, 3 values) in a row; with the wiki rule no value ever repeats the previous one; under the CoE rule each step repeats with probability 1/3, so 15 Orbs show at least one repeat with probability 1 − (2/3)^15 = 99.8%. A 15-Orb run is decisive. Second test on a Steel Ring (two stats: 3–4 and 10–14) answers whether the exclusion covers each value or only the whole pair. Multi-value exclusion is otherwise unspecified.
- **O-02 Orb of Chance: magic vs rare vs unique split.** Unpublished. To estimate P(rare) to ±3 percentage points (95%) one needs about 1,070 results, to ±2 points about 2,400, to ±1 point about 9,600 (p ≈ 0.5). Do it on a base with no unique at all (so unique-fallback does not move the split), once on a base that has uniques, using Alt-held scour-chancing (1 Orb of Chance + 1 Orb of Scouring per try). A first rough look needs 200 tries (±7 points) and costs about 200 Orbs of Chance plus 200 Scouring. If the bench craft has the same split (O-04), 1 Orb of Chance per try on a magic/rare item halves the cost.
- **O-03 Unique probability per base.** Rough tier odds only (T5/T4 1 in a few hundred); no per-base table; the wiki guide lists uniques by tier for drop-anywhere uniques (Section 4 of the guide). Because a unique is a failure, the effect is small: about 0.3% per try or less (1 in a few hundred at worst, T5/T4). The planner can ignore it in v1 (treat `p_unique` as 0 and fold it into the split) or take it from a table the owner supplies.
- **O-04 Is the bench craft's outcome the Orb's outcome?** "Same effect and cost" (wiki) vs the repoe cost of 1 Chance and the history that it could make uniques. Assumed equal. A paired sample (300 each) would show a difference larger than 7 points only.
- **O-05 Random rounding of the catalyst gain** is the wiki's table of the formula; no player sample found. **Test**: 40 catalysts on a normal ilvl 84 belt, recording each increment (expected 1 or 2 with 48% / 52%); stop at 20%.
- **O-06 Overflow past 20%.** `min(20, q + gain)` assumed; the alternative (refusal when the gain does not fit) is not described anywhere. Seen for free in O-05 when the quality is 19% or 20%.
- **O-07 Sinistral/Dextral on implicits.** PoB flags only prefix/suffix modifier lines, so implicits are not boosted; the wiki says "Prefix modifiers"/"Suffix modifiers"; the source only tells "side". Treat implicits as not boosted; Mirage-only item, rare in a planner.
- **O-08 Floor vs nearest.** PoB and CoE floor; the GGG example (25196.4 → 25196) has fraction .4, so it fits both. **Test**: one catalyst-boosted value with fraction ≥ .5 (e.g. a base roll of 9 with 20%: 10.8 → shows 10 under floor, 11 under nearest), found on any item with a stat of 9, 19, 29 ...
- **O-09 Catalysts and crafted/fractured/hybrid modifiers**: all assumed scaled (CAT-13). One look at an item with a bench-crafted matching mod after the catalyst settles it.
- **O-10 Mod counts of a Chance result.** Whether a rare from the Orb has 4–6 modifiers like Alchemy/Chaos (CUR-10, CUR-13) and a magic from it 1–2: assumed as dropped items; unknown whether an Orb of Chance gives the same number mix as a drop (a drop-style 4/5/6 pattern is not the Chaos 8:3:1). A few dozen results show it.
- **O-11 Hotfix notes 3.29.3 to 3.29.3.3** were not scanned for these items (the Version pages stop at 3.29.2 in the wiki's backlinks).
- **O-12 Blessed on Eldritch implicits**: whether both implicits are rerolled and with which ranges is not stated; Eldritch is a later batch.
- **O-13 Reddit, redone 2026-10-31 with the archive.** Threads read first-hand through the Arctic Shift archive are in section 7. They give roughly measured *unique* odds and confirm the bench craft; they give **nothing** on the magic/rare split (O-02), the Blessed repeat claim (O-01), the catalyst gain and its rounding (O-05, O-08), crafted/fractured/hybrid scaling (O-09), Sinistral/Dextral on implicits (O-07), or the mod counts of a Chance result (O-10): "not found", with the searches listed in section 7.

## 6. Questions for the owner (the main chat asks; each has a recommended answer)

1. **Do we ship the Orb of Chance in B2 even though its odds are unknown?** It is a rarity step that never beats Alchemy for a rare unless its price is low enough, and a unique result is a failure; but it is the cheapest "magic or rare from white" and the only route for some jobs. *Options*: (a) ship it with the split as a measured input, `p_magic`, `p_rare` set from a number the owner (or a tester) supplies, and refuse to plan with it while unset; (b) ship it with a placeholder 50/50 flagged as a guess; (c) leave it out of v1. *Recommendation*: (a), bench variant and scour-chance variant as two actions, plus the Omen left out.
2. **Can you (or someone) run the three cheap in-game checks?** (i) 15 Blessed Orbs on a Prismatic Ring (about 15 Blessed, one afternoon); (ii) 40 catalysts on an ilvl 84 belt, recording each increment; (iii) about 1,000 scour-chances on a base with no unique to size the magic/rare split. *Recommendation*: ask for (i) and (ii) first (cheap, decisive); (iii) only if Chance stays in B2.
3. **Blessed rule while it is unverified**: exclude the old value (wiki) or not (Craft of Exile)? *Recommendation*: follow the wiki (exclude), because a wrong guess costs at most 10% more or fewer Orbs on the usual 11-value ranges and the wiki states it outright; switch if the test says otherwise.
4. **Which catalysts in B2?** *Recommendation*: the ten regular ones plus Sinistral and Dextral (data-only: tag = side), no Tainted (corrupted items are closed to everything else, odds unpublished).
5. **How is "catalyst quality as a target" written?** *Recommendation*: a target says `quality: {type, min_percent}` (e.g. R05: Intrinsic, 20); the planner prices it as the finish-line cost `E[catalysts] × price` from the formula (9.5 at ilvl 75, 13.3 at ilvl 84, 20 at ilvl 95+ for 20%) and applies the catalysts at the end (they do not change any odds and survive crafting). Value targets stay on the *stored* roll; a target given in displayed numbers is translated with `ceil(100·N/(100+q))` when quality is part of the target.

---

## Appendix A. Draft claims for `src/crafting_system/rules/claims/`

In the folder [`2026-10-31-blessed-catalysts-chance.claims/`](2026-10-31-blessed-catalysts-chance.claims/) beside this note, one file per family so each can be copied into `src/crafting_system/rules/claims/` as it is: `blessed_orb.yaml` (4 rules), `catalyst.yaml` (13), `orb_of_chance.yaml` (5), `omen_of_fortune.yaml` (1), `scour_chance.yaml` (1), and `bench_craft.yaml` (a full copy of the shipped file, taken from `main` on 2026-10-31, with `bench_craft.other_options_not_mod_crafts` amended and two rules added: `bench_craft.reroll_rarity`, `bench_craft.reroll_rarity_spends_memory_strands`, 0 to 50 strands from #98). Checked: all files copied beside the shipped claims load with `load_registry` (138 rules). Not claims, kept as open points: the Blessed old-value exclusion (O-01) and the magic/rare split of the Orb of Chance (O-02).

## Appendix B. How the numbers were produced

Scripts (not committed, scratch): tag census on `mods.json`/`base_items.json` (counts above), quality-gain distribution and application-count recursion (`min(20, q+gain)` absorbing at 20), implicit-range census. Wiki, PoEDB, PoB and Mark_GGG posts read in the built-in browser pane on 2026-10-31; the Cloudflare-protected official forum pages were read from web.archive.org captures (2021) of the staff-only view.

## 7. Reddit evidence (read through the Arctic Shift archive, 2026-10-31)

Method. `reddit_archive.py` and my own client with back-off (`posts/search?title=...`, `posts/ids`, `comments/tree?link_id=...`). The archive answered `429 Too many requests` or `422 Timeout. Maybe slow down a bit` to most title searches of more than a month or two of data (shared by about twenty agents), so every search below that is marked "timed out" returned nothing, not "no thread". Two `gpt-research` runs (terra, one brief for all open points; stopped after ten minutes in which 14 of 17 fetches were 429/422/403) found nothing the archive reads below do not hold.

**Threads read first-hand (all r/pathofexile, PoE 1):**

- https://www.reddit.com/r/pathofexile/comments/1mvdwvf/ "Chancing uniques" (aldencordova1, 2025-08-20, 15 comments). socialjusticeinme: "On normal mode it's about 10k chance orbs to hit a t3 unique, so you'd need to keep picking up bases and slamming it, or farm scour orbs then scour chance spam." daroar: "You won't hit it with chance orbs realistically, 1:10k is far too rare. If you try it, get a new base everytime, never scour one." toiletpaper_salad: "Item level does not matter for chance orbs." (Matches CHA-04: ilvl ignored.)
- https://www.reddit.com/r/pathofexile/comments/1oz94ni/ "Chancing question" (PhantasmDragon, 2025-11-17, 5 comments). Interesting-Bus6935: "I would say you would need about 1200-1300 attempts on average. For example i chanced warlord crown of eyes (t3) this league, and it took about 2000 attempts, but i got 2 time someone's trickery that is also t3 unique." ConsistentAd1176: "Influence does not matter for chancing." Samples of 800 to 2,000 attempts per unique for T3 bases, a single player each; the second claim is the same band as the first.
- https://www.reddit.com/r/pathofexile/comments/15q3sm6/ (Blitzilla, 2023-08-13): "chanced this beauty with under 6k chance/scour orbs (asked in chat, average seems to be 10-12k)"; DevilsWon: "I did over 30k on my shield and the guy I bought it off said he used 45k"; WeedMoneyBitches: "Pretty sure average is 30k for t1 unique." Anecdotal, 2023 (3.21-3.22 era, before the Kalandra-style tier rework the wiki mentions).
- https://www.reddit.com/r/pathofexile/comments/1nyue7c/ (Visible_Resource_409, 2025-10-05): "The new bench combines chances and scourings, thanks @ggg for that!"; romicide07: "It's 1000 ancient orbs on average to hit on a lvl 70 base" (that is the Ancient Orb, not the Chance).
- https://www.reddit.com/r/pathofexile/comments/1pbq771/ "Chancing Influenced bases" (Low_Pollution_993, 2025-12-01): "Chancing through the bench i got belt of the deceiver but it's not influenced and I cannot go back." and, in the follow-up, a second influenced belt chanced into a double-influenced unique. **The bench craft produces uniques** (CHA-09), and an unique result of an influenced base can keep or lose influence.
- https://www.reddit.com/r/pathofexile/comments/1l3tghc/ (Erionns, 2025-06-05, score 1989): title "Orb of Chance + Scour bench craft confirmed for 3.26"; no numbers.

**What this changes.** Unique odds per try for a T3 unique are about 1 in 800 to 10,000 in these reports, so the unique result takes well under 0.2% of tries; the wiki's "T5/T4 1 in a few hundred" is the largest loss. O-03 stays "ignore in v1". CHA-09 gets a first-hand report that the bench craft yields uniques. Nothing contradicts the wiki on any other point.

**Not found (each with its searches).**

- O-02 magic/rare split: title searches `orb of chance`, `chancing`, `chanced`, `scour chance`, `scour-chance`, `chance orb` (windows from 2023-01 to 2026-11; those over 3.25-3.29 that returned: 1ey2pjx "Why are orb of chance so cheap?", 1mbdjq7, 1l3bdnl, 1l3cua8, 1edd8b0, 1epgamw); threads read: the six above plus 1m68jz5, 1ey2pjx; none gives a count of magic or rare outcomes. The 2013 staff view (CHA-03) remains the only statement.
- O-01 Blessed repeat claim: title searches `blessed` (2026-01 to 2026-03 and 2026-07 to 2026-11 only; the other windows timed out); the hits are unrelated ("Blessed Call", "Harbinger gone BUT Fracturing + Ancient Orbs now core drops and Blessed Orbs reroll Guardian maps" 1rfmav2, 2026-02-26, 301 points, 97 comments, not read: about map bosses). Not found.
- O-05, O-08, O-09, O-07 catalysts: title search `catalyst` (every window 2024-07 to 2026-11 timed out except 2026-01 to 2026-04, which returned no thread). Not found.
- O-10 mod counts of a Chance result, O-06 overflow: not found.
- Full-text comment search (`comments/search?body=...`): every attempt, mine and the GPT run's, was 422/429 or timed out. A person with direct access to Reddit search ("Blessed Orb" "same implicit", "catalyst" "ilvl" "20%") is the way to close these; the archive cannot be queried reliably at the moment.
