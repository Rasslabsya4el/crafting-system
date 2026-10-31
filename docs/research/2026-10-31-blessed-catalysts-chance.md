# Blessed Orb, catalysts and Orb of Chance in 3.29

Ticket: [#89 Blessed Orb, catalysts and Orb of Chance in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/89) (map #1; inventory rows M-20, M-27, M-28; benchmark R05). Claim-id prefixes `BLE` (Blessed), `CAT` (catalysts), `CHA` (Orb of Chance).
Date checked: 2026-10-31. Patch: PoE 1 3.29.3.3, ordinary (non-Ruthless). Datamined = repoe-fork export of 3.29.3.3 (exported 2026-10-19, local copy `.claude/scratch/repoe-3.29.3.3`).

**Answer.**

- **Blessed Orb**: rerolls the *values* of the implicits of an item, never their identity; usable only where an implicit has a range (71 of the 115 ring/amulet/belt bases, 24 of 46 rings, 36 of 53 amulets, 11 of 16 belts). New values are drawn inside the implicit's range. The one open fork is whether the old value can come up again: the wiki says no, Craft of Exile's code does not exclude it (`BLE-04`, O-01). Nothing in the 3.25–3.29 notes changes it.
- **Catalysts**: 13 exist in the data (10 regular + Tainted + Sinistral + Dextral), all for rings, amulets and belts, stack 20, Ultimatum is the only source since 3.29.0. One quality type at a time; a different catalyst wipes the old quality. One catalyst adds `floor(f)` or `floor(f)+1` points, `f = max(1, min(30·e^(−ilvl/30) − 0.3, 20))` with random rounding (ilvl 75: 2 or 3 points; ilvl 84: 1 or 2; ilvl 95+: always 1), capped at 20%. The wiki's probability table matches this formula to the last digit. At 20% a matching modifier is multiplied by 1.20 on its stored integer and **rounded down**; the match is by the modifier's tag (a modifier with two matching tags is boosted once). Catalyst quality neither changes mod weights nor is removed by crafting (since 3.15.0), so it behaves as a separate, finish-line cost: expected catalysts to 20% = 9.5 at ilvl 75, 13.3 at ilvl 84, 20 at ilvl 95+.
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

**CAT-07 Catalyst quality is persistent state.** Since 3.15.0 it no longer changes the chances of rolling matching modifiers when crafting and is no longer removed by crafting currency.
- official (reproduced on the wiki): https://www.poewiki.net/wiki/Version_3.15.0: "Catalysts no longer affect the chances of rolling related modifiers on jewellery through crafting, and Quality on jewellery is no longer removed when crafting with specific Currency." [chk 2026-10-31]
- wiki: https://www.poewiki.net/wiki/Catalyst#Version_history repeats it ("Prior to version 3.15.0 ... Each time one of these currency items was used on the item, its quality percentage would be reduced."). [chk 2026-10-31]

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
- official (staff): Mark_GGG, 2013-08-01, https://web.archive.org/web/2021/https://www.pathofexile.com/forum/view-thread/485201/filter-account-type/staff : "They do not have a flat chance to obtain a unique, regardless of how "rare" that unique is supposed to be. If the only unique of a base type is a rarely occurring one, then chances have a low chance to get uniques on that base type. Adding a more common unique to the same type means that chances on that item will have an significantly increased chance to roll uniques". [chk 2026-10-31]
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
- That the odds equal the Orb's is assumed from "same effect" (O-04).

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
- **O-13 Reddit samples not obtained.** Reddit is reachable only through `gpt-research`; seven runs (terra and luna, 15–45 minutes each) ended `timed out`, `worker process died before finishing`, or `rejected` (model call aborted after 1,514 s, no text), so no Reddit post backs or contradicts anything here. The questions they carried are exactly the gaps O-01 (a second source for the Blessed repeat claim), O-02 (a large Chance sample), O-05 (a player sample of catalyst gain). A rerun, or a person searching r/pathofexile for "orb of chance" tallies, could close O-02 cheaply. What did succeed instead: GGG staff posts from 2013 (web.archive.org captures) and a 2022 Mark_GGG post (devtrackers.gg), both quoted above.

## 6. Questions for the owner (the main chat asks; each has a recommended answer)

1. **Do we ship the Orb of Chance in B2 even though its odds are unknown?** It is a rarity step that never beats Alchemy for a rare unless its price is low enough, and a unique result is a failure; but it is the cheapest "magic or rare from white" and the only route for some jobs. *Options*: (a) ship it with the split as a measured input, `p_magic`, `p_rare` set from a number the owner (or a tester) supplies, and refuse to plan with it while unset; (b) ship it with a placeholder 50/50 flagged as a guess; (c) leave it out of v1. *Recommendation*: (a), bench variant and scour-chance variant as two actions, plus the Omen left out.
2. **Can you (or someone) run the three cheap in-game checks?** (i) 15 Blessed Orbs on a Prismatic Ring (about 15 Blessed, one afternoon); (ii) 40 catalysts on an ilvl 84 belt, recording each increment; (iii) about 1,000 scour-chances on a base with no unique to size the magic/rare split. *Recommendation*: ask for (i) and (ii) first (cheap, decisive); (iii) only if Chance stays in B2.
3. **Blessed rule while it is unverified**: exclude the old value (wiki) or not (Craft of Exile)? *Recommendation*: follow the wiki (exclude), because a wrong guess costs at most 10% more or fewer Orbs on the usual 11-value ranges and the wiki states it outright; switch if the test says otherwise.
4. **Which catalysts in B2?** *Recommendation*: the ten regular ones plus Sinistral and Dextral (data-only: tag = side), no Tainted (corrupted items are closed to everything else, odds unpublished).
5. **How is "catalyst quality as a target" written?** *Recommendation*: a target says `quality: {type, min_percent}` (e.g. R05: Intrinsic, 20); the planner prices it as the finish-line cost `E[catalysts] × price` from the formula (9.5 at ilvl 75, 13.3 at ilvl 84, 20 at ilvl 95+ for 20%) and applies the catalysts at the end (they do not change any odds and survive crafting). Value targets stay on the *stored* roll; a target given in displayed numbers is translated with `ceil(100·N/(100+q))` when quality is part of the target.

---

## Appendix A. Draft claims for `src/crafting_system/rules/claims/`

Families: `blessed_orb`, `catalyst`, `orb_of_chance`, `omen_of_fortune`, `scour_chance`, `bench_craft` (one added rule). Seven provenance fields each.

```yaml
rules:
  - id: blessed_orb.needs_ranged_implicit
    statement: A Blessed Orb needs an item with at least one implicit that has a range of values; items without implicits or with fixed-value implicits are not valid inputs. A corrupted item takes none (as for the ten basic orbs, CUR-21).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Blessed_Orb#Mechanics
    quote: "It cannot be used on items without implicit modifiers or whose implicit modifiers do not have a range of values."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: blessed_orb.rerolls_implicit_values_only
    statement: A Blessed Orb rerolls the values of the item's implicit modifiers inside each implicit's own range; the implicit's identity and every explicit modifier stay as they are.
    source_kind: datamined
    url: https://repoe-fork.github.io/base_items.json
    quote: "Randomises the values of the implicit modifiers of an item"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: blessed_orb.special_implicits_allowed
    statement: Synthesised implicits and Eldritch implicits can be rerolled by a Blessed Orb (whether both Eldritch implicits are rerolled is not stated).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Blessed_Orb#Mechanics
    quote: "They can be used on items with special implicits, such as synthesised items items with Eldritch implicit modifiers."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: blessed_orb.new_value_uniform_in_range
    statement: Each rolled integer implicit value is drawn uniformly over the implicit's range, both ends included (decimal ranges in hundredths).
    source_kind: coe
    url: https://www.craftofexile.com/packages/package.js
    quote: "poec_simRerollImplicits ... poec_rand(useimplicits[i].nvalues[j][0],useimplicits[i].nvalues[j][1]+1,!0)"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: blessed_orb.old_value_excluded
    statement: PROVISIONAL (open O-01). A Blessed Orb cannot roll the same implicit value the item had before, so the new value is uniform over the range without the old value; Craft of Exile does not exclude it, and the planner follows the wiki until an in-game test (15 Blessed Orbs on a Prismatic Ring) says otherwise. For an item with several ranged implicit values the scope of the exclusion (each value or the whole set) is not known.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Blessed_Orb#Mechanics
    quote: "Blessed Orbs can not roll the same implicit value that the original item had."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.thirteen_items_for_jewellery
    statement: There are thirteen catalysts (Abrasive, Accelerating, Fertile, Imbued, Intrinsic, Noxious, Prismatic, Tempering, Turbulent, Unstable, Sinistral, Dextral, Tainted); each applies to a ring, amulet or belt only, stacks to 20, and replaces other quality types. Tainted works on corrupted jewellery only.
    source_kind: datamined
    url: https://repoe-fork.github.io/base_items.json
    quote: "Right click this item then left click a ring, amulet or belt to apply it. Has greater effect on lower item level, non-unique jewellery. The maximum quality is 20%."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.single_quality_type
    statement: An item carries one catalyst quality type; a catalyst of a different type replaces it and quality starts again from 0%; a catalyst of the same type adds to it. Quality is capped at 20%.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Catalyst
    quote: "Using a different type of catalyst on an item that already has quality will replace the quality type, starting again from 0%."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.source_ultimatum_only
    statement: Since 3.29.0 Ultimatum is the only source of catalysts and a stack holds 20; they are bought, not made, in a plan.
    source_kind: official
    url: https://www.poewiki.net/wiki/Version_3.29.0
    quote: "Ultimatum is now the exclusive source of Catalysts."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.gain_depends_on_item_level
    statement: The quality a non-unique catalyst adds depends on the item's level and not on its rarity.
    source_kind: official
    url: https://www.pathofexile.com/forum/view-thread/3531661
    quote: "the amount of Quality they provide is now based on the item level"
    patch_verified: "3.25.0"
    date_checked: 2026-10-31

  - id: catalyst.gain_formula_and_rounding
    statement: With f = max(1, min(30*exp(-ilvl/30) - 0.3, 20)), one catalyst adds floor(f) points with probability 1 - frac(f) and floor(f)+1 points with probability frac(f); an integer f adds exactly f. Examples (ilvl 75: +2 83.75% / +3 16.25%; ilvl 84: +1 47.57% / +2 52.43%; ilvl 86: +1 59.34% / +2 40.66%; ilvl 95 and up: +1 always). The wiki's table equals this formula; no player sample confirms the random rounding.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Quality#Amount
    quote: "max(1, min(30*e^(-1/30*ilvl) - 3/10, 20))"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.quality_capped_at_20
    statement: Catalyst quality never exceeds 20%; a catalyst whose gain passes 20 leaves the item at 20 (the overflow case is not described by any source, open O-06).
    source_kind: datamined
    url: https://repoe-fork.github.io/base_items.json
    quote: "The maximum quality is 20%."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.quality_survives_crafting
    statement: Catalyst quality does not change which modifiers an Augmentation, Regal, Exalted or Annulment draws and is not removed by crafting currency; it is a state that persists with the item.
    source_kind: official
    url: https://www.poewiki.net/wiki/Version_3.15.0
    quote: "Catalysts no longer affect the chances of rolling related modifiers on jewellery through crafting, and Quality on jewellery is no longer removed when crafting with specific Currency."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.magnitude_multiplier
    statement: A modifier that matches the catalyst type, implicit or explicit, has its value multiplied by (100 + quality) / 100 (20% quality = x1.20).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Quality
    quote: "Increased modifier magnitude based on catalyst tag; affects implicit and explicit affixes"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.magnitude_multiplier_in_code
    statement: Craft of Exile adds quality/100 to a factor 1 for the first matching catalyst tag (so x1.20 at 20%, once per modifier); Path of Building returns (100 + quality) / 100 on the first matching tag. The three sources agree.
    source_kind: coe
    url: https://www.craftofexile.com/packages/package.js
    quote: "val+=(crsim_catalyst.val/100);break"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.rounding_floor
    statement: A catalyst-scaled value is the stored integer stat value times (100 + quality) / 100, rounded down; in integer arithmetic scaled = (v * (100 + q)) // 100 on the repoe stat integer. A displayed target N at quality q needs a stored roll v >= ceil(100 * N / (100 + q)). (Floor versus nearest is not separated by the one GGG example, open O-08.)
    source_kind: coe
    url: https://www.craftofexile.com/packages/package.js
    quote: "function poec_simApplyCatMod(val,mod){if(mod!=1){if(val-Math.floor(val)!=0){return Math.floor(((val*100)*mod))/100}else{return Math.floor(val*mod)}}else{return val}}"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.rounding_example_ggg
    statement: GGG's example of a catalyst-scaled life regeneration roll - the stored value is an integer, the scaled value is stored rounded down (20997 x 1.2 = 25196.4 stored as 25196).
    source_kind: official
    url: https://devtrackers.gg/pathofexile/p/c038cd2a-ggg-help-please-catalyst-no-worky-on-immortal-flesh
    quote: "With the quality modifier, the base roll of 20997 becomes 25196.4, which rounds down to 25196 as the stored value."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.match_by_implicit_tags
    statement: Which modifiers a regular catalyst boosts is decided by the modifier's implicit_tags - Abrasive attack; Accelerating speed; Fertile resource; Imbued caster; Intrinsic attribute; Noxious physical_damage or chaos_damage; Prismatic resistance; Tempering defences; Turbulent elemental_damage; Unstable critical. A modifier counts once however many tags match, and may match two catalyst types. On the 312 ordinary ring/amulet/belt modifier records of 3.29.3.3, PoEDB's tag list and Path of Building's tag list pick exactly the same records for all ten catalysts.
    source_kind: datamined
    url: https://poedb.tw/us/Catalyst
    quote: "Fertile Catalyst resource"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: catalyst.sinistral_dextral_by_side
    statement: A Sinistral Catalyst boosts the prefix modifiers and a Dextral Catalyst the suffix modifiers of the item (Mirage-only items); implicits are not prefixes or suffixes and are taken as not boosted (open O-07).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Catalyst
    quote: "Adds quality that enhances Prefix modifiers on a ring, amulet or belt"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: orb_of_chance.normal_to_random_rarity
    statement: An Orb of Chance is used on a normal item only and turns it into a magic, a rare or a unique item.
    source_kind: datamined
    url: https://repoe-fork.github.io/base_items.json
    quote: "Upgrades a normal item to a random rarity"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: orb_of_chance.unique_is_failure
    statement: A unique result of an Orb of Chance (or of the bench rarity reroll) counts as a failed try; unique items are never a target.
    source_kind: owner
    url: https://github.com/Rasslabsya4el/crafting-system/issues/81
    quote: "Unique items are never a target. An Orb of Chance that makes a unique counts as a failed try"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: orb_of_chance.unique_chance_depends_on_base
    statement: The chance of a unique is not a flat number; it depends on which drop-anywhere uniques exist on the base and their tiers (rough odds T5/T4 1 in a few hundred down to T0 1 in hundreds of thousands); a base with no eligible unique cannot give one, and the unique roll then falls back to another rarity. The item level of the base is ignored.
    source_kind: official
    url: https://web.archive.org/web/2021/https://www.pathofexile.com/forum/view-thread/485201/filter-account-type/staff
    quote: "They do not have a flat chance to obtain a unique, regardless of how \"rare\" that unique is supposed to be."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: orb_of_chance.no_unique_from_special_items
    statement: Fractured items, synthesised items, items with an Eldritch implicit and items with a Runesmithing enchantment cannot become unique, so an Orb of Chance on them gives magic or rare only.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Orb_of_Chance#Mechanics
    quote: "Synthesised items and fractured items cannot be turned into a unique item."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: orb_of_chance.magic_rare_split_unknown
    statement: OPEN O-02. The split between magic and rare results is not published; the planner carries it as an input (p_magic, p_rare) that must be set before the Orb of Chance is planned with.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Orb_of_Chance#Mechanics
    quote: "the resulting item is more likely to become a magic or rare item"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: omen_of_fortune.forces_unique
    statement: The Omen of Fortune makes the next Orb of Chance on an item that can become unique produce a unique, and is not consumed when the base has none; under the owner's rule (a unique is a failure) it has no use and is not an action.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Omen_of_Fortune#Mechanics
    quote: "If no uniques exist for the basetype, it will not consume the Omen."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: scour_chance.scouring_returns_to_normal
    statement: Scour-chancing is an Orb of Scouring (magic or rare back to normal, scouring rules as CUR-16/CUR-17) followed by an Orb of Chance on the same base; holding Alt while using an Orb of Chance switches to a Scouring.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Orb_of_Chance#Mechanics
    quote: "The process of using a Orb of Scouring to make a magic or rare item white again to repeat the process with the same base is referred to as \"scour-chancing\"."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: bench_craft.reroll_rarity
    statement: The bench option "Reroll the Rarity of a non-Unique item" costs 1 Orb of Chance (no Scouring), is unlocked from the start, is offered on 40 item classes including ring, amulet, belt and jewel, rerolls the rarity of the magic or rare item in place like Scouring plus Orb of Chance, and can produce a unique (it did on synthesised items until 3.26.0c).
    source_kind: datamined
    url: https://repoe-fork.github.io/crafting_bench_options.json
    quote: "reroll_rarity: true ... cost: Metadata/Items/Currency/CurrencyUpgradeRandomly: 1 ... Niko, Master of the Depths"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
```

## Appendix B. How the numbers were produced

Scripts (not committed, scratch): tag census on `mods.json`/`base_items.json` (counts above), quality-gain distribution and application-count recursion (`min(20, q+gain)` absorbing at 20), implicit-range census. Wiki, PoEDB, PoB and Mark_GGG posts read in the built-in browser pane on 2026-10-31; the Cloudflare-protected official forum pages were read from web.archive.org captures (2021) of the staff-only view.
