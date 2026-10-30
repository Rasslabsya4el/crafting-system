# Basic currency outcomes in 3.29 (Transmutation to Divine)

Ticket: [#7 Basic currency outcomes in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/7) (map #1, evidence rule #2 Q2). Claim-id prefix `CUR`.
Date checked: 2026-10-30. Patch: PoE 1 3.29.3.3, ordinary (non-Ruthless). Datamined = repoe-fork export of 3.29.3.3 (exported 2026-10-19).

**Answer.** Admitted sources fix the *inputs and the shape* of all ten orbs, and the item-state and metamod rules around them, but not several probability tables. Fixed: which rarity each orb accepts, that Augmentation / Regal / Exalted add exactly one affix and Annulment removes exactly one, that Chaos and Alchemy give 4 to 6 affixes (Chaos 4/5/6 = 8:3:1), that Scouring leaves normal / magic / rare for 0 / 1 / 2+ retained mods, that Divine rerolls explicit values inside the same mod's range (integers uniform, inclusive) and never changes the tier, that fractured mods are permanent, that corrupted and mirrored items are closed, and the per-orb matrix of `Prefixes Cannot Be Changed` / `Suffixes Cannot Be Changed` / `Cannot roll Attack|Caster Modifiers`. Not admitted (Open): the 1-vs-2 mod split for magic items, whether Alchemy uses the same 8:3:1 as Chaos, how retained (locked or fractured) mods count toward the 4/5/6 or 1/2 totals, whether Annulment picks uniformly, the exact Annulment behaviour under the attack/caster metamods, and the prefix-vs-suffix side choice (belongs to #6). No official note from 3.25.0 to 3.29.3b changes what any of the ten orbs does; 3.29.0 changed only items around them (CUR-32).

Conventions. Source kinds: `official` (GGG notes or staff posts), `wiki` (poewiki.net), `datamined` (repoe-fork 3.29.3.3), `owner`. "Patch" is the patch the source speaks for; for wiki pages it is the page's last behaviour-relevant "Version history" row (no later row changes the quoted behaviour). Every line carries `[chk 2026-10-30]`. Wiki table cells are quoted as rendered text.

---

## 1. Admitted claims

### 1.1 Item shape (caps, sides)

**CUR-01 Magic cap.** A magic item holds at most 1 prefix and 1 suffix.
- wiki: https://www.poewiki.net/wiki/Rarity#Magic: "up to one prefix and one suffix". Patch: no behaviour row after introduction (last row 3.25.0, drops only). [chk 2026-10-30]
- datamined: `base_items.json` `Metadata/Items/Currency/CurrencyAddModToMagic` `properties.directions` = "... Magic items can have up to two random modifiers." Patch 3.29.3.3. [chk 2026-10-30]

**CUR-02 Rare cap.** A rare equipment item holds at most 3 prefixes and 3 suffixes (6 total). Rare jewels hold at most 2 + 2 (jewels are outside the v1 target set).
- datamined: `base_items.json` `Metadata/Items/Currency/CurrencyAddModToRare` `properties.directions` = "... Rare items can have up to six random modifiers." Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Rarity#Rare: "they have at most six affixes – up to three prefixes and up to three suffixes". Patch: as CUR-01. [chk 2026-10-30]
- wiki (jewels): https://www.poewiki.net/wiki/Modifier#Explicit_modifiers: "with the exception of some items like jewels, which can only have (1 to 2) prefixes and (1 to 2) suffixes". Patch: version table last row 3.28.0 (unrelated). [chk 2026-10-30]

**CUR-03 Every random explicit has exactly one side.** A prefix or suffix mod is a prefix xor a suffix, given by its `generation_type`.
- datamined: `mods.json` `IncreasedLife1` `domain`=item, `generation_type`=prefix; `Strength1` `generation_type`=suffix. Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Modifier#Terminology: Prefix "Refers to the "Prefix" generation type." Patch: version table last row 3.28.0 (unrelated). [chk 2026-10-30]

**CUR-04 Crafted mods occupy a slot.** A bench-crafted mod is a prefix or suffix and needs an open slot on its side, so it counts toward the caps of CUR-01 and CUR-02.
- wiki: https://www.poewiki.net/wiki/Crafting_Bench#Using_the_crafting_bench: "The item must have a prefix or suffix slot open as appropriate." Patch: page speaks for 3.29 (version table mentions 3.29.0 socket rework). [chk 2026-10-30]
- datamined: `mods.json` domain `crafted` has 926 prefix and 675 suffix records (counted by script). Patch 3.29.3.3. [chk 2026-10-30]

### 1.2 The ten orbs

**CUR-05 Orb of Transmutation: input and output.** Accepts a normal item only; the result is magic.
- datamined: `base_items.json` `Metadata/Items/Currency/CurrencyUpgradeToMagic` `properties.description` = "Upgrades a normal item to a magic item", `properties.directions` = "Right click this item then left click a normal item to apply it." Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Crafting#Upgrading_rarity: "Only usable on normal items". Patch: the page has no version table but lists the 3.27.0 Foulborn orbs, so it was edited at or after 3.27; used here only as corroboration of the datamined text. [chk 2026-10-30]

**CUR-06 Transmutation: outcome shape.** The new magic item gets a prefix, a suffix, or both, each rolled from the item's pool at its item level. The probabilities of "one" vs "both" are Open (O-01).
- wiki: https://www.poewiki.net/wiki/Orb_of_Transmutation#Spending: "The resulting item may have a prefix, suffix, or both, each randomly rolled according to the possibilities afforded the original item, also taking into account its item level." Patch: version table has only "Introduced to the game" (no change). [chk 2026-10-30]

**CUR-07 Orb of Alteration.** Accepts a magic item only; discards the item's random modifiers and rolls new ones (same outcome shape as CUR-06). Fractured mods are kept (CUR-23); locked sides are kept (CUR-28).
- datamined: `Metadata/Items/Currency/CurrencyRerollMagic` `description` = "Reforges a magic item with new random modifiers", `directions` = "Right click this item then left click a magic item to apply it." Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Orb_of_Alteration: "can be used to re-roll the random modifiers on a piece of magic equipment". Patch: last row 3.27.0 (Alt-swap UI only). [chk 2026-10-30]

**CUR-08 Orb of Augmentation.** Accepts a magic item with exactly one affix; adds exactly one random affix. The side is forced: it is the missing side, because the other side is already full.
- datamined: `Metadata/Items/Currency/CurrencyAddModToMagic` `description` = "Augments a magic item with a new random modifier". Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Orb_of_Augmentation: "This can only be used on an item with one affix, since magic items can have at most one prefix and one suffix." Patch: last row 3.28.0 (keybind only). [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Rarity#Magic: "can have a second property of the missing type added to it by using an Orb of Augmentation". Patch: as CUR-01. [chk 2026-10-30]

**CUR-09 Regal Orb.** Accepts a magic item only; the result is rare; all current modifiers are kept and exactly one new random affix is added (2 to 3 mods total from 1 to 2).
- datamined: `Metadata/Items/Currency/CurrencyUpgradeMagicToRare` `description` = "Upgrades a magic item to a rare item", `directions` = "... Current modifiers are retained and a new one is added." Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Regal_Orb: "The current modifiers are all retained and one new random affix is added."; "Regal Orbs can only be used on magic items." Patch: last row 3.28.0 (rarity of drops only). [chk 2026-10-30]

**CUR-10 Orb of Alchemy.** Accepts a normal item only (not flasks or tinctures); the result is rare with 4 to 6 random affixes (3 to 4 on jewels). The probabilities inside 4..6 are Open (O-02).
- datamined: `Metadata/Items/Currency/CurrencyUpgradeToRare` `description` = "Upgrades a normal item to a rare item", `directions` = "Right click this item then left click a normal item to apply it." Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Orb_of_Alchemy#Spending: "has a random number of affixes (ranging from four to six (three to four if used on jewels))". Patch: last row 3.28.0 (keybind only). [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Crafting#Upgrading_rarity: Alchemy "Cannot be used on flasks/tinctures". Patch: as CUR-05. [chk 2026-10-30]

**CUR-11 Rare items made by Alchemy (or found) have at least 4 affixes; 2 or 3 affixes arise only through Regal or Annulment.**
- wiki: https://www.poewiki.net/wiki/Rarity#Rare: "will always have at least 4 affixes, but it is possible to get a rare item with only 2 or 3 by using a Regal Orb or Orb of Annulment". Patch: as CUR-01. [chk 2026-10-30]

**CUR-12 Chaos Orb: input and effect.** Accepts a rare item only; rerolls all modifiers and the number of modifiers (subject to CUR-23 fractured mods and CUR-27 to CUR-31 metamods).
- datamined: `Metadata/Items/Currency/CurrencyRerollRare` `description` = "Reforges a rare item with new random modifiers", `directions` = "Right click this item then left click a rare item to apply it." Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Chaos_Orb#Mechanics: "they reroll all modifiers (and the number of modifiers) on a rare item". Patch: last row 3.28.0e (Alt-swap UI only). [chk 2026-10-30]

**CUR-13 Rare affix count after Chaos is 4, 5 or 6 in the ratio 8:3:1 (2/3, 1/4, 1/12) for regular items.** (Already admitted in #2; restated with source.) How retained mods count toward this total is Open (O-03).
- wiki: https://www.poewiki.net/wiki/Chaos_Orb#Mechanics: "For regular items, Chaos Orbs result in a rare item with an affix count of 4, 5, or 6 at a ratio of 8:3:1." Patch: as CUR-12. [chk 2026-10-30]
- owner: grill #2 Q2, "Rare reroll 4/5/6 = 8:3:1 is accepted (wiki)". [chk 2026-10-30]

**CUR-14 Exalted Orb.** Accepts a rare item with at least one open affix slot; adds exactly one random explicit modifier; a modifier already present on the item cannot be added (family exclusion as in #2).
- datamined: `Metadata/Items/Currency/CurrencyAddModToRare` `description` = "Augments a rare item with a new random modifier". Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Exalted_Orb#Mechanics: "Exalted Orbs add a random explicit modifier to a rare item."; "If a modifier is present on the rare item before usage, that modifier cannot be added by an Exalted Orb."; "adding a random affix to a rare item that has at least one empty affix". Patch: last row 3.28.0 (drop rarity). [chk 2026-10-30]

**CUR-15 Orb of Annulment.** Accepts a magic or rare item; removes exactly one modifier; never changes rarity (a magic item left with 0 mods stays magic; a rare left with 2 or 3 mods stays rare). Which modifier (uniform or not) is Open (O-04).
- datamined: `Metadata/Items/Currency/CurrencyRemoveMod` `description` = "Removes a random modifier from an item", `directions` = "Right click this item then left click on a magic or rare item to apply it." Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Orb_of_Annulment#Mechanics: "Unlike Orb of Scouring, Orbs of Annulment never downgrade rarity." Patch: last row 3.15.0 (catalyst help text). [chk 2026-10-30]

**CUR-16 Orb of Scouring: input and effect.** Accepts a magic or rare item; removes every random modifier that is not protected (fractured CUR-23, locked side CUR-28); keeps implicit modifiers, quality, sockets and links.
- datamined: `Metadata/Items/Currency/CurrencyConvertToNormal` `description` = "Removes all modifiers from an item", `directions` = "... left click on a magic or rare item to apply it." Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Orb_of_Scouring: "Implicit modifiers, quality, sockets, and links are not removed, as well as affixes protected by meta-crafting mods." Patch: last row 0.9.5 (drop rates), no later change. [chk 2026-10-30]

**CUR-17 Scouring result rarity follows the number of mods left.** 0 left: normal. 1 left: magic. 2 or more left: rare.
- wiki: https://www.poewiki.net/wiki/Orb_of_Scouring: "When an Orb of Scouring removes all but one modifier, the item will be downgraded to magic instead of normal. (With two modifiers, the item will remain rare.)" Patch: as CUR-16. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Crafting#Augmenting_and_removing_modifiers: Scouring "Removes all modifiers, downgrading the item to the lowest possible rarity". Patch: as CUR-05. [chk 2026-10-30]
- Note: "2 or more left: rare" for 3 or more is the same rule read from "downgrading to the lowest possible rarity" (magic cannot hold 3); it is not separately quoted.

**CUR-18 Divine Orb: input and scope.** Accepts a magic, rare or unique item; rerolls the values of explicit modifiers only (implicit values are Blessed Orb's job). Only stats that have a range change.
- datamined: `Metadata/Items/Currency/CurrencyModValues` `description` = "Randomises the values of the random modifiers on an item", `directions` = "Right click this item then left click a magic, rare or unique item to apply it." Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Divine_Orb#Crafting: "Divine Orbs re-roll the values of explicit values of modifiers when used on an item."; "Only the values of affixes that have a range of values will be randomized." Patch: last row 3.28.0 (highlight UI only). [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Crafting#Randomising_numerical_values: Blessed "Randomises the values of implicit modifiers", Divine "Randomises the values of explicit modifiers". Patch: as CUR-05. [chk 2026-10-30]

**CUR-19 Divine never changes mod identity or tier.** The new value is drawn inside the same mod record's range.
- wiki: https://www.poewiki.net/wiki/Divine_Orb#Crafting: "A Divine Orb will not change the tier of the affix; it will only re-roll within its current tier." Patch: as CUR-18. [chk 2026-10-30]
- datamined: `mods.json` keeps one `stats[].min/max` range per mod id (tier = mod id): `IncreasedLife1` `base_maximum_life` min 10 max 24. Patch 3.29.3.3. [chk 2026-10-30]

**CUR-20 Integer stat values are rolled uniformly over [min, max] inclusive.** A stat 1..3 gives 1, 2, 3 with 1/3 each; a roll equal to the old value is allowed.
- wiki: https://www.poewiki.net/wiki/Modifier#Conditions: "can either be 1, 2 or 3 at 1/3 chance for each value". Patch: version table last row 3.28.0 (unrelated); stated for stat values generally. [chk 2026-10-30]
- Scope note: the wiki states this rule for modifier stat values in general (Modifier page), not inside the Divine section. Multi-stat (hybrid) mods: see O-11.

### 1.3 Item states

**CUR-21 Corrupted items accept none of the ten orbs.** The only exceptions are Tainted currency and a few named uniques.
- wiki: https://www.poewiki.net/wiki/Corrupted#Modifying_corrupted_items: "Corrupted items cannot be modified, with the following exceptions:" (Tainted currency, bench sockets, named uniques). Patch: last row 3.29.0. [chk 2026-10-30]

**CUR-22 Mirrored items accept none of the ten orbs.**
- wiki: https://www.poewiki.net/wiki/Mirrored: "Mirrored items cannot be altered in any way except through the use of currency items that explicitly affect mirrored items, such as Reflective Oil." Patch: only row 0.6.7 (introduced); no change since. [chk 2026-10-30]

**CUR-23 Fractured mods are permanent.** No orb removes one (Annulment and Scouring cannot remove it; Chaos and Alteration keep it); Divine does not change its value. The fractured mod occupies its slot like any other (needs CUR-01/02 slot accounting).
- wiki: https://www.poewiki.net/wiki/Fractured_item#Mechanics: "These mods cannot be removed (by Orb of Annulment or Orb of Scouring, etc.) or have its values changed by Divine Orb." Patch: last row 3.20.0; Fracturing Orb page row 3.29.0 does not change it. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Fractured_item: "Fractured items are of a special type of item base that have at least one affix coloured in gold (◼) that is permanently fixed on the item." [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Divine_Orb#Crafting: "Fractured modifiers cannot have their values rerolled." Patch: as CUR-18. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Fractured_item#Mechanics lists the orbs that cannot be used on a fractured item: "Influenced Exalted Orbs and Awakener's Orbs cannot be used on them." No exclusion is listed for the ten orbs here, so a fractured item is a valid input for them. Patch: as above. [chk 2026-10-30]
- Note: "Chaos and Alteration keep it" rests on "permanently fixed" and "etc."; the count semantics are Open (O-03).

**CUR-24 Scouring a fractured item.** With 1 fractured mod the result is magic; with 2 or 3 it is rare (the case of CUR-17).
- wiki: https://www.poewiki.net/wiki/Fractured_item#Mechanics: "it will turn into a Magic item if it had one fractured mod or a Rare item if it had two or three fractured mods". Patch: as CUR-23. [chk 2026-10-30]

**CUR-25 Influenced items accept the ten orbs and keep their influence.** Influence does not guarantee an influenced mod after modification.
- wiki: https://www.poewiki.net/wiki/Influenced_item#Mechanics: "Items retain their influences when modified, even if an Orb of Scouring is used."; "Modifying the item will not guarantee an influence modifier." Patch: last row 3.28.0 (unrelated numbers). [chk 2026-10-30]

**CUR-26 Non-unique synthesised items no longer arise in 3.29 except by corruption, so they are irrelevant to the ten orbs.**
- official: https://www.pathofexile.com/forum/view-thread/3985332 (3.29.0 notes, Stacey_GGG, 2026-07-17, "Item Changes"): "Non-Unique Synthesised Items can no longer be obtained, except through Corrupting Synthesis Unique Items to be Rare items." Patch 3.29.0. [chk 2026-10-30]

### 1.4 Metamods (`Prefixes Cannot Be Changed` = PCBC, `Suffixes Cannot Be Changed` = SCBC, `Cannot roll Attack Modifiers` = CRA, `Cannot roll Caster Modifiers` = CRC)

**CUR-27 Metamods are affixes that take a slot on the opposite side, and are removable like any affix on their side.** PCBC is a suffix, SCBC is a prefix, CRA / CRC / multimod are suffixes.
- datamined: `mods.json` `StrMasterItemGenerationCannotChangePrefixes` `domain`=crafted `generation_type`=suffix `text`="Prefixes Cannot Be Changed" stat `item_generation_cannot_change_prefixes` 1..1; `DexMasterItemGenerationCannotChangeSuffixes` `generation_type`=prefix `text`="Suffixes Cannot Be Changed"; `IntMasterItemGenerationCannotRollAttackAffixes` `generation_type`=suffix; `StrDexMasterItemGenerationCannotRollCasterAffixes` `generation_type`=suffix; `StrIntMasterItemGenerationCanHaveMultipleCraftedMods` `generation_type`=suffix `text`="Can have up to 3 Crafted Modifiers". Patch 3.29.3.3. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Metamod#Examples: "Can have up to 3 Crafted Modifiers is a suffix." Patch: last row 3.27.0. [chk 2026-10-30]

**CUR-28 PCBC / SCBC protect existing affixes of the named side from removal and from Divine; they never forbid adding to an open slot of that side.** Per orb (wiki matrix, "Basic Currencies"):
- Alteration, Chaos, Exalted: "Respected, but open prefixes may be filled" (PCBC) and "Respected, but open suffixes may be filled" (SCBC): existing affixes of the locked side survive and the open slots of that side can still be filled by the new roll.
- Augmentation, Regal: "n/a" (a magic item has at most 2 affixes, rarity change adds one).
- Annulment, Scouring, Divine: "Respected" (the locked side is never touched).
- wiki: https://www.poewiki.net/wiki/Metamod#Rules_and_Exceptions (table "Basic Currencies"). Patch: last row 3.27.0; the table has no 3.28-3.29 row. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Metamod#Overview: "It will not, however, prevent adding a new modifier, such as through an Exalted Orb or Chaos Orb, as it only applies to existing modifiers." Patch: as above. [chk 2026-10-30]
- official: https://www.pathofexile.com/forum/view-thread/1401804 (Chris, 2015-08-21, "Master Crafting Metamods"): "locking all of an item's prefixes in place and then scouring/divining the remaining ones" and "Removal counts as a change." Patch: the metamods of Forsaken Masters (2.0.x, 2014), post dated 2015-08-21 on the forum (the wiki cites it as Aug 20); restated for 3.27+ by the wiki table above; no later GGG statement found that contradicts it (change audit CUR-32). [chk 2026-10-30]

**CUR-29 Scouring with a side lock removes every affix of the other side, including the metamod itself, and keeps every affix of the locked side.**
- wiki: https://www.poewiki.net/wiki/Metamod#Examples: "the Orb of Scouring will remove ALL suffix (including Prefixes Cannot Be Changed) and keep ALL prefix of the item, if the item has crafted with the mod Prefixes Cannot Be Changed." Patch: last row 3.27.0. [chk 2026-10-30]
- Rarity after that follows CUR-17 on the retained count (a lone retained prefix gives magic; 2 or more give rare).

**CUR-30 Chaos with PCBC rerolls the other side, including the metamod, and the item can end with zero suffixes.**
- wiki: https://www.poewiki.net/wiki/Metamod#Examples: "the Prefixes Cannot Be Changed is the only suffix, the Orbs may add 1 prefix as well as 0 to 3 suffixes to the item". Patch: as CUR-28. [chk 2026-10-30]
- Only the shape (metamod is rerolled away, 0 to 3 suffixes) is admitted; the chance of each count is Open (O-03).

**CUR-31 CRA / CRC stop mods carrying the attack / caster mod tag from being added.** Respected by Augmentation, Regal and Exalted; ignored by Scouring (the metamod is removed like any suffix); Chaos respects them only when the same item also has SCBC (otherwise the metamod suffix is itself rerolled away).
- wiki: https://www.poewiki.net/wiki/Metamod#Rules_and_Exceptions ("Basic Currencies"): Augmentation "Respected", Regal "Respected", Exalted "Respected", Scouring "Ignored", Chaos "When used with Suffixes Cannot Be Changed". Patch: last row 3.27.0. [chk 2026-10-30]
- wiki: https://www.poewiki.net/wiki/Metamod#Examples: "prevent any item with the attack mod tag ... spawn on the item". Patch: as above. [chk 2026-10-30]
- Annulment's row is "Respected" for CRA / CRC; its exact meaning is Open (O-05). Alteration and Divine are "n/a".

### 1.5 Change audit (3.25 to 3.29.3b)

**CUR-32 The effect of none of the ten orbs changed between 3.25.0 and 3.29.3b.** The only entries naming them are UI or supply entries.
- official: scanned the first post of 148 patch-note threads titled 3.25.x to 3.28.x (3.25.0 to 3.28.0l) and 29 threads from 3.28.0k to 3.29.3b (https://www.pathofexile.com/forum/view-forum/patch-notes), with a keyword filter (the ten orb names, Fracturing Orb, "Fractured Mod", Metamod, Cannot Be Changed, "Cannot Roll", "crafting bench", "number of affixes|modifiers"), then read the hits. Hits touching these orbs: 3.27.0d (Alt-swap hotkeys, thread 3880147), 3.28.0 ("Relative rarities of several currencies have been adjusted. Most notably, Exalted and Regal Orbs will now be comparatively more common.", "Hovering an item while applying a Divine Orb or a Blessed Orb now highlights the specific modifier values that will be rerolled.", thread 3913392), 3.28.0e ("While using Chaos Orbs, you can now hold Alt to swap to using an Exalted Orb.", thread 3924293), 3.29.2 ("Hovering over items while in the application state for Divine Orb, Blessed Orb, or Volatile Vaal Orb now displays non-advanced modifiers by default.", thread 3994431). 3.29.0 (thread 3985332): the only entries naming crafting currency are supply ("Mercenary Rucksacks in Endgame Maps can no longer generate Orbs of Transmutation or Orbs of Augmentation."), Fractured Fossils, Fracturing Orb text, Volatile Vaal Orbs, Ancient Orbs, the two bench rerolls, and uniques that "can be updated with a Divine Orb". Patch: 3.25.0 to 3.29.3b. [chk 2026-10-30]
- Limits: only the first post of each thread was read, by keyword; hits about unique-item updates, drops, Heist trinkets, Ultimatums, shops and bench option costs were dropped before reading; a change worded without any filter term would be missed. The Alteration Alt-swap of 3.27.0 is known from the wiki row only.
- wiki version tables agree: Alteration 3.27.0, Augmentation 3.28.0, Regal 3.28.0, Alchemy 3.28.0, Chaos 3.28.0e, Exalted 3.28.0, Divine 3.28.0, Annulment 3.15.0, Scouring 0.9.5, Transmutation none (all UI, hotkey, rarity or help-text rows). [chk 2026-10-30]

**CUR-33 Catalyst quality no longer interacts with these orbs.** Since 3.15.0 catalysts do not change the spawn weights, and quality is not removed by these currencies.
- wiki: https://www.poewiki.net/wiki/Regal_Orb#Version_history (3.15.0): "Catalysts no longer affect the chances of rolling related modifiers on jewellery through crafting, and Quality on jewellery is no longer removed when crafting with specific Currency." The Orb of Annulment page has the same row; the Orb of Augmentation and Exalted Orb pages say "Quality from catalyst no longer affect the spawn weight". Patch 3.15.0. [chk 2026-10-30]

**CUR-34 The Foulborn Orb of Augmentation / Regal / Exalted are separate items, not part of the ten.** (Eldritch, Veiled, influence-adding and Tainted Exalted / Chaos / Annulment variants are likewise separate items in the wiki Crafting tables; they belong to later batches.)
- official: https://www.pathofexile.com/forum/view-thread/3869068 (3.27.0 notes): "Introduced the Foulborn Orb of Augmentation, which augments a Magic item with a new random modifier with higher level modifiers being more likely." Patch 3.27.0. [chk 2026-10-30]

---

## 2. Open (not admitted)

Each item: what is known and from which non-admitted source, and what would settle it. "Blocks" means a primitive cannot be coded without it.

**O-01 Magic item mod count (Transmutation, Alteration).** Probability of 1 mod vs 2 mods, and of prefix-only vs suffix-only. *Blocks Transmutation and Alteration.* Known: prototype / Craft of Exile use 1/2 each (`numOfAffixes[1]`, reimplemented-from-CoE); a 2017 player thread (https://www.pathofexile.com/forum/view-thread/1897121) says "Seems 25% prefix, 25% suffix, 50% double, but i have done just 50" on poedb's simulator (not an experiment, not a sample). The wiki, poedb pages and 3.25-3.29 notes give no number. Settles it: a GGG staff statement, or a counted experiment of at least a few thousand Alterations / Transmutations (one-mod vs two-mod, with the item level and base), or an explicit owner decision.

**O-02 Alchemy 4/5/6 split.** The wiki gives "four to six" for Alchemy and 8:3:1 only on the Chaos page. Whether Alchemy uses the same 8:3:1 is not stated. *Blocks Alchemy.* Prototype: same table (2/3, 1/4, 1/12), CoE-derived. Settles it: a wiki or GGG statement tying the two, a counted experiment of Alchemy results (sample size), or an owner decision "Alchemy = Chaos table".

**O-03 How retained mods count (locks, fractured).** When Chaos / Alchemy-style rerolls keep mods (PCBC / SCBC side, fractured), is the 4/5/6 draw the *total* affix count (retained included) or the number of *new* mods? Same question for a magic item with a fractured mod or a side lock under Alteration (total 1/2?). The wiki example (CUR-30) gives ranges for new suffixes but no probabilities. *Blocks Chaos and Alteration on locked or fractured items (bench metamod routes, fracture routes).* Prototype: "count table is conditional on caps" (CoE, `numOfAffixes[(prefix_cap+suffix_cap)/2]`, retained mods consume slots). Settles it: a GGG statement, or a counted experiment on PCBC / fractured items (number of mods after Chaos, by retained count).

**O-04 Annulment selection weights.** The sources say "a random modifier"; uniform 1/N among removable mods is not stated, and a weighting by side or tier is not excluded. *Blocks Annulment cost.* Prototype: 1/N (CoE equal weights 1000). Reddit and guides quote 33% / 50% only as assumptions. Settles it: a GGG statement, or a counted experiment (hundreds of annuls on 2-4 mod items with known mods), or an owner decision "uniform".

**O-05 Annulment under CRA / CRC.** The wiki says Annulment "respect[s] metamods, including Cannot roll Caster/Attack Modifiers" and the table says "Respected" for all four, but not which mods become safe or removable (are attack-tagged mods protected from removal? are non-attack mods?). Source cited by the wiki is a Reddit thread (qz2axm, 2021-11-21), not an admitted source. *Blocks Annulment on CRA / CRC items only.* Prototype: "attack/caster removal protection" (CoE). Settles it: a GGG statement or a counted experiment; until then the solver must not use Annulment on items with CRA / CRC.

**O-06 Annulment under PCBC / SCBC: candidate set.** CUR-28 admits that the locked side is protected; that the *metamod itself* (an affix on the other side) is a removal candidate is the natural reading of CUR-27 and CUR-29 but is not stated for Annulment. Settles it: one sentence in the wiki or a GGG post, or a short experiment.

**O-07 Prefix vs suffix choice for Alteration, Augmentation-on-empty, Regal, Chaos, Exalted, Transmutation, Alchemy.** CUR-03 gives each mod its side, and the wiki says tags and weights set "the relative chance to be randomly applied" (https://www.poewiki.net/wiki/Modifier#Conditions), but no admitted text says whether the side is chosen by a pooled weighted draw over all eligible mods of both open sides or by a separate coin flip. *Belongs to ticket #6 (affix draw); do not code a side coin.*

**O-08 Pool exhausted or no legal mod.** What Augmentation / Regal / Exalted / Chaos do when no eligible mod fits an open slot (everything blocked by family, level, attack/caster metamod): refusal without consuming the orb, consumption with no change, or a shorter roll. Prototype: "error if no mod can be added" (CoE). Settles it: a GGG statement or an in-game test report. Low impact on benchmarks.

**O-09 Crafted (non-meta) mods under Chaos, Alteration, Annulment, Scouring.** CUR-29 / CUR-30 admit that crafted *metamods* are removed by Scouring and rerolled by Chaos; that an ordinary crafted mod (e.g. +life) behaves the same as an unprotected affix is the natural reading but not stated. Also: whether Divine rerolls crafted mod values (1474 crafted records in `mods.json` have a rollable range). Settles it: the wiki Crafting Bench page or a GGG statement.

**O-10 Special item states with the ten orbs.** Split items (`Split (item modifier)` page not readable: the bot challenge persisted for that URL), unmodifiable items (wiki says no changes at all), items with an Eldritch implicit (wiki: Fracturing Orb works; nothing for the ten), jewels, flasks, tinctures, maps (cap and count tables differ: CUR-02 gives only the jewel cap). Settles it: wiki lines per state; most are outside the v1 target set (armour, weapons, jewellery).

**O-11 Divine details.** (a) Whether each stat of a hybrid mod (1296 of 4369 item prefix/suffix records have 2+ stats) is rolled independently. (b) Whether Eldritch or corruption implicits are rerolled by Divine (CUR-18 says explicit only; the wiki is silent for those implicit types). (c) Divine on an item whose rollable mods are all fixed (715 of 4369 records have min = max): the 3.29.0 note "Volatile Vaal Orbs can now be used on items that have no modifiers that can scale outside of range, to be more consistent with Divine Orbs" (thread 3985332) implies Divine is usable but does not say it. (d) Divine on veiled placeholders (B2). Settles it: wiki or GGG statement; (a) by a count of paired rolls.

**O-12 Influenced pools.** The wiki says influenced items have an "expanded pool of exclusive modifiers" (https://www.poewiki.net/wiki/Influenced_item), but no admitted text says that Alteration, Chaos, Exalted or Regal draw influenced mods on such an item (CUR-25 only says influence is kept). The pool itself belongs to #6; this is the orb-side confirmation. Settles it: #6 and the wiki Influenced item page.

## 3. Prototype re-audit

Source: `git show archive/prototype:docs/mechanics/basic_currency.md` (every claim), plus the count table of `affix_generation.md` and the Bench-rerolls row of `patch_3_29.md`. All prototype confidence labels are `reimplemented-from-CoE`, so nothing carried over without a source above.

| # | Prototype claim | Verdict |
|---|---|---|
| 1 | Transmutation: normal -> magic | confirmed (CUR-05) |
| 2 | Transmutation: reroll at magic caps; count 1 or 2 at 1/2 each | caps confirmed (CUR-01); 1/2 each unbacked (O-01) |
| 3 | Alteration: magic only; reroll; "retain fractures and side locks through metaprot" | input confirmed (CUR-07); fractured kept (CUR-23); side locks respected with open slots fillable (CUR-28); count table unbacked (O-01, O-03) |
| 4 | Augmentation: magic, open affix; add 1 weighted mod respecting side and attack/caster | confirmed (CUR-08, CUR-31); weights belong to #6 (O-07) |
| 5 | Regal: magic; set rare then add 1; keep mods; base `is_rare` | confirmed (CUR-09); `is_rare` = flasks, tinctures, relics cannot be rare (CUR-10, https://www.poewiki.net/wiki/Rarity "Flasks, Tinctures, and Relics cannot be of rare rarity") |
| 6 | Alchemy: normal, `is_rare`; rare; counts 4/5/6 at 2/3, 1/4, 1/12 | input and 4..6 range confirmed (CUR-10, CUR-11); the 8:3:1 for Alchemy unbacked (O-02) |
| 7 | Chaos: rare; reroll with `metaprot`; count table conditional on caps | input confirmed (CUR-12); 8:3:1 for regular items confirmed (CUR-13); "conditional on caps" unbacked (O-03) |
| 8 | Exalted: rare, `is_rare`, open affix; add 1 eligible weighted mod | confirmed (CUR-14); "error if no mod can be added" unbacked (O-08) |
| 9 | Annulment: non-normal, >= 1 affix; remove 1 eligible non-fractured; side locks and attack/caster removal protection | magic/rare input and fractured protection confirmed (CUR-15, CUR-23); side-lock protection confirmed (CUR-28); attack/caster protection changed to "respected, semantics unknown" (O-05) |
| 10 | Annulment candidate weights 1000 each, probability 1/N | unbacked (O-04) |
| 11 | Scouring: non-normal; clear unprotected explicits; preserve fractures and locked sides; rarity from retained affixes | confirmed (CUR-16, CUR-17, CUR-23, CUR-24, CUR-29); "non-normal" narrowed to magic or rare |
| 12 | Scouring rarity: "retained counts above one on either side yield rare, otherwise normally magic; fracture with one prefix and one suffix yields rare" | changed: the wiki rule is total retained mods, 1 -> magic, 2+ -> rare, 0 -> normal (CUR-17); it gives the same result for the prototype's examples |
| 13 | Divine: non-normal, >= 1 affix; reroll numerical values within existing ranges; retain identity and tier | changed: input is magic, rare or unique (CUR-18); tier kept confirmed (CUR-19) |
| 14 | Divine skips fractured and locked-side mods | confirmed (CUR-23, CUR-28) |
| 15 | Divine skips veiled placeholders | unbacked (O-11d, B2) |
| 16 | Integer Divine ranges `[low, high+1)`, both endpoints can occur; 10..12 gives 1/3 each | confirmed (CUR-20) |
| 17 | "No currency exchange rates are asserted" | not a mechanics claim (prices come from #5 / price sources) |
| 18 | Side lock preserves existing mods, no blanket ban on adding to an empty slot of that side | confirmed (CUR-28) |
| 19 | Augment / Regal / Exalt filter attack/caster tags but not side locks for additions | confirmed (CUR-28, CUR-31) |
| 20 | Chaos rebuilds metamods from retained affixes; a cannot-roll attack/caster suffix affects the replacement pool only if retained (conjunction with SCBC) | confirmed (CUR-30, CUR-31); a removed metamod is not applied to the new roll (wiki: Chaos "When used with Suffixes Cannot Be Changed") |
| 21 | Ordinary actions blocked on corrupted items | confirmed (CUR-21) |
| 22 | Mirrored / destroyed / split applicability "needs an audit" | mirrored confirmed (CUR-22); destroyed not a game state in the sources read; split open (O-10) |
| 23 | Catalyst quality: `poec_remCatQuality` empty, "no rule" | confirmed in effect: catalysts do not interact since 3.15.0 (CUR-33) |
| 24 | Foulborn variants outside this sheet | confirmed (CUR-34) |
| 25 | S13 prose says Scouring / Chaos remove all explicits; sheet says protected mods are exceptions | confirmed: CUR-16 / CUR-28 / CUR-29; the protected-mod rule is documented (wiki + Chris 2015) |
| 26 | Example 1: Augment on a 1-prefix magic item adds a suffix | confirmed (CUR-08) |
| 27 | Example 2: Regal on 1 prefix + 1 suffix gives a rare with 3 explicits | confirmed (CUR-09) |
| 28 | Example 3: rare with 2 prefixes + PCBC: Scour keeps the 2 prefixes, removes the lock, stays rare | confirmed (CUR-29, CUR-17) |
| 29 | Example 4: Annul with 1 fracture + 3 eligible: success 1/3, fracture removal 0 | fracture protection confirmed (CUR-23); 1/3 unbacked (O-04) |
| 30 | Example 5: Divine 10..12, 3 values 1/3 each, tier changes 0 | confirmed (CUR-19, CUR-20) |
| 31 | `affix_generation.md` count table cap-sum/2 = 3: 4/5/6 = 2/3, 1/4, 1/12 | confirmed for Chaos (CUR-13: 8:3:1 = 8/12, 3/12, 1/12); other orbs O-02 |
| 32 | `affix_generation.md` cap-sum/2 = 2.5: 4 -> 2/3, 5 -> 1/3 | unbacked (no admitted source for non-3/3 caps) |
| 33 | `affix_generation.md` cap-sum/2 = 2 (jewels): 3 -> 0.65, 4 -> 0.35 | range 3..4 for Alchemy on jewels confirmed (CUR-10); probabilities unbacked |
| 34 | `affix_generation.md` cap-sum/2 = 1.5: 3 -> 1 | unbacked |
| 35 | `affix_generation.md` cap-sum/2 = 1 (magic): 1 -> 1/2, 2 -> 1/2 | unbacked (O-01) |
| 36 | `patch_3_29.md`: bench rerolls "three random mods for 3 Chaos, or one random mod for 8 Chaos" on rares | the cost lines are quoted in the official 3.29.0 notes ("Reroll 3 random Modifiers on a Rare Item for a cost of 3 Chaos Orbs"); mechanics belong to the bench ticket, not this one |

## 4. Cross-checks (not evidence)

- **Craft of Exile** (via the prototype's code read of 2026-09-20, not re-opened today): agrees with the wiki on inputs, "rarity from retained mods", 8:3:1 for the 4/5/6 draw, "respected, open slots fillable" for side locks, Chaos respecting CRA / CRC only with SCBC. It adds numbers the admitted sources do not give: magic 1 vs 2 at 1/2 each (O-01), Alchemy = Chaos table (O-02), Annulment uniform 1/N (O-04), retained mods consume slots (O-03). The prototype also records a literal RNG defect in CoE's weighted draw (`poec_rand` excludes the upper bound): not copied.
- **poedb** (WebFetch 2026-10-30 of `poedb.tw/us/Orb_of_Alteration` and `/Chaos_Orb`): descriptive text only ("re-roll the random modifiers on a piece of magic equipment", "left click a rare item"); no 1-vs-2 split, no 8:3:1. Earlier report `2026-10-30-1-prior-art-and-data.md` records the same: poedb says Chance / Alchemy give at least four affixes and Chaos gives 4 to 6, without ratios. Agrees with the wiki, adds no number.
- **Path of Building**: holds mod data and groups, no orb mechanics; nothing to cross-check for these ten orbs.
- **Player thread** https://www.pathofexile.com/forum/view-thread/1897121 (2017): 50 tries on poedb, "25% prefix, 25% suffix, 50% double": consistent with 1/2 two-mod split, sample far too small; not evidence.
- **Reddit qz2axm** (cited by the wiki Annulment page, 2021-11-21): not read. Reddit cannot be opened here and three `gpt-research` runs (two broad, one for this thread) failed ("worker process died" twice, "timed out" once); it is cited only as the wiki's own reference for O-05.

## 5. Sources read

Wiki (poewiki.net, read in the built-in browser pane): [Orb of Transmutation](https://www.poewiki.net/wiki/Orb_of_Transmutation), [Orb of Alteration](https://www.poewiki.net/wiki/Orb_of_Alteration), [Orb of Augmentation](https://www.poewiki.net/wiki/Orb_of_Augmentation), [Regal Orb](https://www.poewiki.net/wiki/Regal_Orb), [Orb of Alchemy](https://www.poewiki.net/wiki/Orb_of_Alchemy), [Chaos Orb](https://www.poewiki.net/wiki/Chaos_Orb), [Exalted Orb](https://www.poewiki.net/wiki/Exalted_Orb), [Orb of Annulment](https://www.poewiki.net/wiki/Orb_of_Annulment), [Orb of Scouring](https://www.poewiki.net/wiki/Orb_of_Scouring), [Divine Orb](https://www.poewiki.net/wiki/Divine_Orb), [Fracturing Orb](https://www.poewiki.net/wiki/Fracturing_Orb), [Crafting](https://www.poewiki.net/wiki/Crafting), [Rarity](https://www.poewiki.net/wiki/Rarity), [Modifier](https://www.poewiki.net/wiki/Modifier), [Metamod](https://www.poewiki.net/wiki/Metamod), [Fractured item](https://www.poewiki.net/wiki/Fractured_item), [Corrupted](https://www.poewiki.net/wiki/Corrupted), [Mirrored](https://www.poewiki.net/wiki/Mirrored), [Unmodifiable](https://www.poewiki.net/wiki/Unmodifiable), [Synthesised item](https://www.poewiki.net/wiki/Synthesised_item), [Influenced item](https://www.poewiki.net/wiki/Influenced_item), [Crafting Bench](https://www.poewiki.net/wiki/Crafting_Bench). Not opened: `Split (item modifier)` (bot challenge persisted; not bypassed). Search and `api.php` also returned the challenge and were not used.

Official (pathofexile.com forum): [3.29.0 notes, thread 3985332](https://www.pathofexile.com/forum/view-thread/3985332); [Master Crafting Metamods, Chris, thread 1401804](https://www.pathofexile.com/forum/view-thread/1401804); patch-note threads 3.25.0 (3531661), 3.26.0 (3787013), 3.27.0 (3869068), 3.27.0d (3880147), 3.28.0 (3913392), 3.28.0e (3924293), 3.29.2 (3994431) plus the keyword scan of all 3.25.x-3.29.3b threads listed in [patch-notes forum](https://www.pathofexile.com/forum/view-forum/patch-notes); player thread [1897121](https://www.pathofexile.com/forum/view-thread/1897121).

Datamined: https://repoe-fork.github.io/base_items.json (ten `Metadata/Items/Currency/*` records), https://repoe-fork.github.io/mods.json (`IncreasedLife1`, `Strength1`, five metamod records, domain / generation_type counts); local copy `.claude/scratch/repoe-3.29.3.3/`, scripts `.claude/scratch/research-basic-currency/q1.py..q4.py`.

Prototype / reports: `archive/prototype:docs/mechanics/basic_currency.md`, `affix_generation.md`, `patch_3_29.md`, `docs/OPEN_QUESTIONS.md`; `docs/research/2026-10-30-1-prior-art-and-data.md`; poedb pages above (cross-check only).
