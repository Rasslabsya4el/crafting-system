# Fracturing Orb in 3.29 (ordinary)

Ticket: [#12](https://github.com/Rasslabsya4el/crafting-system/issues/12) (map #1; evidence rule: #2 Q2). Patch 3.29.3.3. Date checked: 2026-10-30. Claim-id prefix `FRA`.

**Answer.** The Fracturing Orb works on a **rare** item with **at least 4 modifiers** that is **not influenced, not fractured, not synthesised, not corrupted, not mirrored**; Eldritch-implicit and Split items are allowed. It fractures **exactly one explicit modifier, chosen "at random"**, rerolls nothing, ignores the prefix/suffix-lock metamods, and the fracture can never be undone (Imprint, vendor recipes). A fractured modifier is a normal prefix/suffix that Annulment, Scouring, Chaos-style rerolls and the bench cannot remove and Divine cannot change; Scouring leaves a Magic item (one fractured mod). **No admitted source states the selection distribution**: "random" is all GGG and the wiki say, and no large-sample experiment exists. So the 1/n rule used by the prototype is **not admitted** (OPEN-01), and which modifiers count toward the 4 and may be picked (crafted, metamods, unrevealed veiled) is also open (OPEN-02..04). Counts: **30 admitted claims, 11 open items.**

Source kinds: `official` = GGG patch notes (pathofexile.com forum); `wiki` = poewiki.net (revision ids in section 6); `datamined` = repoe-fork 3.29.3.3 (`https://repoe-fork.github.io/<file>`). No `experiment` or `owner` claim exists for this ticket. All claims checked 2026-10-30.

---

## 1. Admitted claims

### 1.1 Valid inputs

**FRA-01 Rarity.** A Fracturing Orb can only be used on a Rare item.
- official, [3.20.0 notes, #newcontentandfeatures](https://www.pathofexile.com/forum/view-thread/3323944#newcontentandfeatures): "Introduced the Fracturing Orb, which can be used to fracture a random modifier on a rare item with at least 4 modifiers, locking it in place."
- Patch 3.20.0 (introduced); unchanged in 3.29 (all 3.20-3.29 patch-note first posts grepped, no change). Corroborated by FRA-28 (datamined item text at 3.29.3.3).

**FRA-02 Minimum count.** The item must have at least 4 modifiers (4 allowed). What the count includes is open (OPEN-02).
- official, same post and quote as FRA-01. wiki, [Fracturing Orb#Mechanics](https://www.poewiki.net/wiki/Fracturing_Orb#Mechanics): "This item will randomly fracture one explicit modifier on a rare item with 4 or more modifiers." Patch 3.20.0 / 3.29 page.

**FRA-03 Influenced items are invalid.** Not usable on items with Shaper/Elder/Conqueror influence.
- official, 3.20.0 notes (same post): "This can't be used on Influenced, Synthesised or Fractured items." Also datamined, FRA-28. wiki, [Influenced item#Mechanics](https://www.poewiki.net/wiki/Influenced_item#Mechanics): "Conversely, influenced items cannot be fractured or synthesised". Patch 3.20.0, unchanged 3.29.

**FRA-04 Already-fractured items are invalid.** The orb cannot be used on an item that already has a fractured modifier, so an orb never produces a second fractured modifier.
- official, 3.20.0 notes (same quote as FRA-03); datamined FRA-28 ("Cannot be used on Influenced or Fractured items."). Patch 3.20.0, unchanged 3.29.

**FRA-05 Synthesised items are invalid.** Existing synthesised items (only in Standard in 3.29) cannot be fractured.
- official, [3.29.0 notes, #itemchanges](https://www.pathofexile.com/forum/view-thread/3985332#itemchanges): "These items still cannot be applied to existing Synthesised Items in Standard leagues." (the preceding sentence says Fracturing Orbs, Fractured Fossils and Reflecting Mists "no longer explicitly state they don't work on Synthesised Items"). Patch 3.29.0. Item text no longer says it (FRA-28); wiki [Synthesised item](https://www.poewiki.net/wiki/Synthesised_item): "Synthesised items cannot be fractured or given influenced modifiers."

**FRA-06 Eldritch-implicit items are valid and are not "influenced".** An Exarch/Eater implicit does not block the orb; the fractured modifier is still an explicit one.
- wiki, [Fracturing Orb#Mechanics](https://www.poewiki.net/wiki/Fracturing_Orb#Mechanics): "This item can be used on items with Eldritch implicit modifiers." wiki, [Eldritch implicit modifier](https://www.poewiki.net/wiki/Eldritch_implicit_modifier) (lead): "Items that have Eldritch implicit modifiers are not considered influenced. They can be split or fractured." Patch 3.29 (page rev 2026-07-31).

**FRA-07 Split items are valid.**
- wiki, Fracturing Orb#Mechanics: "This item can be used on Split items." Patch 3.29 page. (New Split items can no longer be made in 3.29, see FRA-27, but existing ones remain.)

**FRA-08 Corrupted items are invalid.** Corrupted items cannot be modified except by the listed exceptions (socket bench crafts, Tainted currency, Tainted Catalyst/Oil, some uniques, Djinn-Touched Vaal Orb); the Fracturing Orb is not an exception.
- wiki, [Corrupted#Modifying_corrupted_items](https://www.poewiki.net/wiki/Corrupted#Modifying_corrupted_items): "Corrupted items cannot be modified, with the following exceptions:" (list does not name the Fracturing Orb). Derived from the general rule, not from a Fracturing-Orb-specific sentence. Patch 3.29 (page rev 2026-09-01).

**FRA-09 Mirrored items are invalid.**
- wiki, [Mirrored](https://www.poewiki.net/wiki/Mirrored) (lead): "Mirrored items cannot be altered in any way except through the use of currency items that explicitly affect mirrored items, such as Reflective Oil." The Fracturing Orb is not such an item. Same derivation caveat as FRA-08. Page rev 2024-12-21 (no later change known).

**FRA-10 Metamods are ignored.** Prefix/suffix-lock and attack/caster metamods do not protect any modifier from being fractured and do not block use.
- wiki, Fracturing Orb#Mechanics: "This item does not respect metamods." Patch 3.29 page. (The [Metamod](https://www.poewiki.net/wiki/Metamod#Rules_and_Exceptions) table has no row for the orb; its only "Fracture a Modifier: Ignored" row is the removed 3.19 Harvest craft.)

### 1.2 Effect and selection

**FRA-11 Effect.** The orb fractures exactly one modifier of the item and changes nothing else: the other modifiers and all values stay as they are.
- wiki, Fracturing Orb#Mechanics: "This item does not reroll the modifiers of an item." and "This item will randomly fracture one explicit modifier". official, 3.20.0 notes: "...locking it in place." Patch 3.20.0 / 3.29. Note: the wiki's reference for the first sentence (forum thread 3324396, Crucible Q&A) does not contain it; admitted as wiki text.

**FRA-12 Candidate class and "random".** The modifier is picked at random from the item's **explicit** modifiers; implicit modifiers (including Eldritch implicits) are not fractured. The probability law is not given by any admitted source (OPEN-01).
- wiki, Fracturing Orb#Mechanics: "This item will randomly fracture one explicit modifier on a rare item with 4 or more modifiers." official, 3.20.0 notes: "fracture a random modifier". Patch 3.20.0 / 3.29.

**FRA-13 A crafted (bench) modifier can be a fractured modifier.** The state "fractured crafted modifier" exists. This does not say the orb picks crafted modifiers (OPEN-03).
- wiki, [Crafting Bench#Using_the_crafting_bench](https://www.poewiki.net/wiki/Crafting_Bench#Using_the_crafting_bench): "This cannot replace crafted modifiers that are fractured, if the item has multiple crafted modifiers, or if the item is corrupted, mirrored, or unmodifiable." Patch 3.29 (page rev 2026-08-16).

**FRA-14 Fracturing is irreversible by Imprint.** Imprints cannot be made of, or applied to, fractured items; an imprint of the pre-fracture item cannot undo the fracture.
- wiki, [Imprint#Mechanics](https://www.poewiki.net/wiki/Imprint#Mechanics): "Further clarification: imprints of a non-fractured item cannot undo its Fractured modifier if a Fracturing Orb was used on it." (previous sentence: "Imprints cannot be made of or used on Fractured items."). Also datamined `base_items.json` ids `Metadata/Items/Currency/CurrencyImprintOrb` and `.../CurrencyImprint`: `properties.description` ends "Can't be applied to Fractured Items". Patch 3.29 (page rev 2026-09-04; item text 3.29.3.3).

**FRA-15 Vendor recipes cannot remove a fracture.**
- official, [3.25.0 notes, Bug Fixes](https://www.pathofexile.com/forum/view-thread/3531661): "Fixed a bug where some vendor recipes could un-Fracture Fractured Items." Patch 3.25.0 (2024-07-19); nothing later contradicts.

### 1.3 What a fractured modifier changes for later actions

**FRA-16 Not removable by Annulment or Scouring.** A fractured modifier is never removed by Orb of Annulment, Orb of Scouring "etc."; so it is never a removal candidate.
- wiki, [Fractured item#Mechanics](https://www.poewiki.net/wiki/Fractured_item#Mechanics): "These mods cannot be removed (by Orb of Annulment or Orb of Scouring, etc.) or have its values changed by Divine Orb." wiki, [Modifier#Explicit_modifiers](https://www.poewiki.net/wiki/Modifier#Explicit_modifiers): "Fractured items have at least one modifier that's permanently locked to the item, being unable to be rerolled or removed." Patch 3.29 (page rev 2026-08-17; its table lists nothing after 3.20.0).

**FRA-17 Divine Orb does not change its value.**
- wiki, [Divine Orb#Crafting](https://www.poewiki.net/wiki/Divine_Orb#Crafting): "Fractured modifiers cannot have their values rerolled." (same as FRA-16 quote). Patch 3.29 (page rev 2026-07-26).

**FRA-18 Not rerolled.** Rerolls of the item's modifiers leave the fractured modifier in place (Chaos Orb and other reforges). How many new modifiers a reroll adds around it is open (OPEN-06).
- wiki, Modifier#Explicit_modifiers: "being unable to be rerolled or removed" (quote in FRA-16). Patch 3.29.

**FRA-19 Scouring leaves a Magic item.** Orb of Scouring on a fractured item removes the other modifiers and leaves a Magic item when it has one fractured modifier (Rare when it has two or three; not reachable with the orb).
- wiki, Fractured item#Mechanics: "When using an Orb of Scouring on a fractured item, it will turn into a Magic item if it had one fractured mod or a Rare item if it had two or three fractured mods." wiki, [Tainted Chaos Orb#Mechanics](https://www.poewiki.net/wiki/Tainted_Chaos_Orb#Mechanics): "fractured mods will not be removed, leaving the item at the lowest eligible rarity. For items with one fractured prefix and/or one fractured suffix modifier, this results in a magic item". Patch 3.29.

**FRA-20 A fractured modifier is an ordinary prefix or suffix.** It sits in a prefix or suffix slot (it is what makes a Magic-sized item hold it).
- wiki, Fractured item (lead): "...have at least one affix coloured in gold (◼) that is permanently fixed on the item." wiki, Modifier (Terminology): "Affix | Either a prefix or a suffix." Slot occupancy is read from these plus FRA-19; no sentence says "counts toward the 3+3 limit". Patch 3.29.

**FRA-21 The bench cannot remove or replace a fractured crafted modifier.**
- wiki, Crafting Bench#Using_the_crafting_bench: quote in FRA-13. Patch 3.29.

**FRA-22 Orb of Chance cannot turn it unique.**
- wiki, [Orb of Chance#Mechanics](https://www.poewiki.net/wiki/Orb_of_Chance#Mechanics): "Synthesised items and fractured items cannot be turned into a unique item." Patch 3.29 (page rev 2026-07-26).

**FRA-23 Influence-adding orbs and Awakener's Orb cannot be used on fractured items.**
- wiki, Fractured item#Mechanics: "Fractured items cannot be turned into an influenced item. Influenced Exalted Orbs and Awakener's Orbs cannot be used on them." wiki, [Shaper's Exalted Orb](https://www.poewiki.net/wiki/Shaper%27s_Exalted_Orb) (lead): "non-fractured". Patch 3.29.

**FRA-24 Eldritch currency (Ember/Ichor) is usable on fractured items.**
- wiki, Eldritch implicit modifier (lead): "...they provide significant power to non-influenced Ward base types, Fractured items, and Grasping Mails which do not normally have implicit modifiers." Patch 3.29 (rev 2026-07-31).

### 1.4 Fractured Fossil and other 3.29 fracture sources (touch the same state; algorithms belong to #9 and the beast ticket)

**FRA-25 Fractured Fossil in 3.29 fractures a random modifier.** It no longer splits; it cannot be used on fractured or influenced items.
- official, 3.29.0 notes #itemchanges (https://www.pathofexile.com/forum/view-thread/3985332#itemchanges): "Fractured Fossils now Fracture a random Modifier, and cannot be used on Fractured and Influenced items." Patch 3.29.0. wiki, [Fractured Fossil#Mechanics](https://www.poewiki.net/wiki/Fractured_Fossil#Mechanics): "fracturing one of the modifiers it rolls at random" (page flagged "describe behavior prior to 3.29"; the pick is among the modifiers the resonator rolls, order inside the craft unknown, OPEN in #9).

**FRA-26 Datamined Fractured Fossil record.** `https://repoe-fork.github.io/fossils.json`, id `Metadata/Items/Currency/CurrencyDelveCraftingMirror`: `descriptions = {"Fracture": "Fracture a random modifier"}`, `mirrors = false`, `added_mods = []`, `forced_mods = []`, `positive_mod_weights = []`, `negative_mod_weights = []`. Item text (`base_items.json`, same id): "Fracture a random modifier\r\nCannot be used on Influenced or Fractured items". Patch 3.29.3.3.

**FRA-27 Beastcrafting fracture crafts (replace splitting).** Fracture one modifier on a Rare Talisman with at least 4 modifiers; fracture two modifiers on a Rare Talisman with at least 6.
- official, 3.29.0 notes #itemchanges: "The Beastcrafting option to Split an item into two has been replaced with a new option that Fractures a Modifier on a Rare Talisman with at least 4 Modifiers." (and "...into three ... Fractures two Modifiers on a Rare Talisman with at least 6 Modifiers."). Patch 3.29.0. Splitting is gone, so no new Split items.

### 1.5 Datamined facts

**FRA-28 Fracturing Orb record at 3.29.3.3.** `https://repoe-fork.github.io/base_items.json`, id `Metadata/Items/Currency/CurrencyFractureRare`: `name = "Fracturing Orb"`, `drop_level = 68`, `release_state = "released"`, `properties.stack_size = 20`, `properties.description = "Fracture a random modifier on a rare item with at least 4 modifiers, locking it in place"`, `properties.directions = "Right click this item then left click a rare item to apply it. Cannot be used on Influenced or Fractured items."` The text has no "Synthesised" (FRA-05). No mod, tag or weight in `mods.json`, `mod_types.json`, `tags.json`, `crafting_bench_options.json` or `fossils.json` encodes fracture selection (scanned all 40355 mod ids and 765 bench options for "fracture": only drop-source, monster and map mods, and no bench option). Patch 3.29.3.3.

**FRA-29 Corrupting does not change fractured modifiers (jewels, maps, contracts).**
- official, [3.20.2 notes](https://www.pathofexile.com/forum/view-thread/3351563): "Fixed a bug where Fractured modifiers on Jewels, Maps, or Heist Contracts could be changed when corrupting the item." Patch 3.20.2. The rule for equipment is not stated (OPEN-09).

**FRA-30 Metamod records occupy affix slots.** `https://repoe-fork.github.io/mods.json`: `StrMasterItemGenerationCannotChangePrefixes` (text "Prefixes Cannot Be Changed") `domain = crafted`, `generation_type = suffix`; `DexMasterItemGenerationCannotChangeSuffixes` ("Suffixes Cannot Be Changed") `crafted`, `prefix`; `IntMasterItemGenerationCannotRollAttackAffixes` ("Cannot roll Attack Modifiers") `crafted`, `suffix`; `StrDexMasterItemGenerationCannotRollCasterAffixes` ("Cannot roll Caster Modifiers") `crafted`, `suffix`; `StrIntMasterItemGenerationCanHaveMultipleCraftedMods` ("Can have up to 3 Crafted Modifiers") `crafted`, `suffix`. All have `spawn_weights = []`. Patch 3.29.3.3. (Bears on OPEN-02..03; whether the orb counts or picks them is not stated.)

---

## 2. Open (not admitted)

**OPEN-01 [blocks coding] Probability of each candidate being fractured.** Known (admitted): "random modifier" (FRA-01, FRA-12), nothing more. Not admitted: prototype says uniform 1/n from Craft of Exile code (`poec_simApplyCraftGO` 2280-2281, reimplemented-from-CoE); PoE Vault guide "There is a 25% chance of success" with exactly 4 mods; Reddit r/pathofexile 1000x6r (2022-12-31): one player "27-30% hit rate" over an unstated number of tries, others suspect weighting; forum 3589504 (player: "always a 25% chance"). No GGG statement found (all 3.19-3.29 first posts, forum search, Reddit). No experiment with a stated N >= 100 found. Settles it: a GGG staff statement; a large-sample experiment (N >= 400 uses on 4-mod rares with mods of very different weight/tier/side; standard error at p = 0.25 is 2.2 points); or an `owner` decision in a grill ticket. Without one of these the primitive can validate inputs and produce the set of possible outcomes but not their probabilities.

**OPEN-02 Which modifiers count toward "at least 4".** Admitted only "modifiers" (item text) and wiki "explicit". Open: crafted modifiers; metamods (FRA-30: they sit in prefix/suffix slots); unrevealed veiled; essence/drop-only (surely count as explicit, not stated). Evidence not admitted: wiki [Crafting](https://www.poewiki.net/wiki/Crafting) table says "at least 4 explicit mods" (and garbles the other conditions); forum bug report 3329926 (2022-12-16): "alt/augment, regal to rare, craft 4th mod, hit with fracturing orb" worked on bows (3 natural + 1 crafted). Settles it: one in-game try with 3 natural explicit + 1 crafted modifier (deterministic yes/no), repeated with a metamod as the 4th.

**OPEN-03 Can crafted modifiers and metamods be the one picked, and with what odds?** FRA-13 shows a fractured crafted mod exists. Not admitted: forum 3329926 (player: 6 of 6 fractures hit the crafted mod on 4-mod bows, N = 6, no GGG reply); forum 3589504 (player: "Crafted modifiers can be fractured"); forum 3336876 item dump `Master Crafted Prefix ... +70(56-70) to maximum Life (fractured)`; prototype claims "all affixes without side protection". Settles it: GGG statement or an experiment with N >= 100 on 4-mod items with one crafted mod (expected 25% if uniform; 6/6 would be p = 0.0002).

**OPEN-04 Veiled modifiers.** Whether an unrevealed (or revealed) veiled modifier is a candidate and counts toward 4. Known: wiki [Fractured item#How_to_obtain](https://www.poewiki.net/wiki/Fractured_item#How_to_obtain) says the Pillage and Plunder passive makes Syndicate members drop items with a fractured veiled mod (a drop source, not the orb). Prototype: "veiled-placeholder exclusion is PoE 2 only" (unbacked). Settles it: staff statement or in-game test.

**OPEN-05 Rarity after fracturing.** No source states the item stays Rare (all readings agree; FRA-19 and the Regal+Annul recipe in wiki Fractured item imply it).

**OPEN-06 Reroll size around a retained fractured modifier.** For Chaos, Alchemy-style, Essence, Fossil and Harvest reforges: is the 4/5/6 (8:3:1) total counted including the fractured modifier, and how are slots filled? The wiki says only "unable to be rerolled or removed" (FRA-16/18). Prototype (CoE `poec_simRerollItem` 2428-2433): "retained fractured mods consume slots; draw only the remaining slots to the normal count total" (not admitted). Belongs to #6, #7, #8, #9, #10; listed here because the fracture-then-spam routes (R04, R10-R12, R22-R24) depend on it. Also open for Essence: forced mod whose family equals the fractured one (prototype: rejected, CoE).

**OPEN-07 Removal and family rules with a fractured mod.** Annulment/other removal when only fractured modifiers remain; whether the removal pick is uniform over non-fractured modifiers (#7). The fractured mod still blocks its family from being added again: this follows from the established Q2 fact (Modifier#Group/family: "Only one modifier from any given group may appear on an object") plus FRA-20, but no page says it for fractured mods.

**OPEN-08 Magic and normal-rarity currencies on fractured Magic items.** Alteration, Augmentation, Regal, Transmutation behaviour when the Magic item holds a fractured modifier (after Scouring, FRA-19): no per-currency wiki or official sentence (Orb of Alteration, Regal, etc. pages never mention fractured). Prototype: Alteration "retains fractures" (CoE). #7.

**OPEN-09 Vaal Orb on fractured equipment.** FRA-29 covers jewels, maps, contracts only. Reddit (non-admitted) anecdote: fractured mod changed by Vaal. B4 batch.

**OPEN-10 3.29 bench rerolls vs a fractured modifier.** New 3.29 bench crafts "Reroll 3 Modifiers on a Rare Item" and "Reroll a Modifier on a Rare Item" (datamined `crafting_bench_options.json` entries 754, 755: `reroll_rare_mods = 3`/`1`, cost `CurrencyRerollRare` x3 / x8): does the pick exclude the fractured modifier? Unstated. #11.

**OPEN-11 Item classes.** Where the orb applies (jewels, flasks, maps, contracts, Talismans, cluster jewels). Text says "a rare item". Equipment is the target of v1, so low priority. Also not covered: Allflame crafting (3.29 league mechanic; wiki [Allflame crafting](https://www.poewiki.net/wiki/Allflame_crafting) lists the orb with up to 2 "Ghostly Copies" outcomes) and Recombinator rules for fractured modifiers (B3).

**Blocks coding the primitive:** OPEN-01 (probabilities) for any use of the orb; OPEN-02/03 only for items carrying crafted modifiers or metamods (the benchmark routes R04/R05/R10-R12 fracture ordinary 4-mod items, so they are not blocked by it); OPEN-06 for the first spam step after the fracture.

---

## 3. Prototype re-audit

Source: `archive/prototype:docs/mechanics/fracturing.md` (P-lines), plus fracture lines in other fact sheets and `docs/specs/2026-09-21-fractured-item-actions.md`.

| Prototype claim | Result |
|---|---|
| Effect: locks one explicit modifier of a rare item with at least four explicit modifiers, no reroll of others | Confirmed with change: FRA-01, FRA-02, FRA-11, FRA-12. Admitted text says "4 modifiers"; "explicit" appears only in wiki mechanics; what counts is OPEN-02 |
| Excludes influenced, synthesised, already fractured items | Confirmed: FRA-03, FRA-04, FRA-05 |
| Allows Eldritch implicits and Split; Eldritch implicits a separate state property from influence | Confirmed: FRA-06, FRA-07 |
| Excludes strongboxes | Confirmed by wiki ("Cannot be used to modify Strongboxes"); irrelevant to equipment crafting, not given an id |
| 3.29 removed "synthesised" from item text, restriction kept on existing Standard items | Confirmed: FRA-05, FRA-28 |
| Corrupted / mirrored eligibility "remains in Q9" | Resolved by the general rules: FRA-08, FRA-09 (derived, caveat stated) |
| Step 3: failed-target states kept, an unwanted fracture is not an unchanged retry | Confirmed in substance: FRA-14, FRA-15 (no way back); modelling choice, not a source claim |
| Selection uniform 1/n over all existing affixes (S3 `poec_simApplyCraftGO` 2280-2281) | Unbacked: OPEN-01 |
| "Veiled-placeholder exclusion is PoE 2 only" | Unbacked: OPEN-04 |
| Wiki "random" alone does not prove equal odds | Confirmed: still no admitted equal-odds sentence |
| Metamods ignored (S33) | Confirmed: FRA-10 |
| S3 selects from all affixes without side protection (crafted, metamods included) | Side-protection part confirmed (FRA-10); "all affixes incl. crafted/metamod" unbacked: OPEN-03 |
| Imprints cannot undo fracturing | Confirmed: FRA-14 |
| Bench/veiled target eligibility not audited | Still open: OPEN-03, OPEN-04 |
| Worked examples: 4 mods -> 1/4 each; two acceptable -> 1/2; six mods one target -> 1/6 | Arithmetic of OPEN-01's assumption; unbacked until OPEN-01 is settled |
| Royal Burgonet / Envy3 numbers (p = .0610..., 627/10000) | Model calculations, not source claims; no entry |
| Fractured Life9 value 132 kept through Divine | Confirmed: FRA-17 |
| patch_3_29.md: legacy synthesised items stay blocked | Confirmed: FRA-05 |
| patch_3_29.md: Fractured Fossil fractures a random modifier, excludes fractured/influenced | Confirmed: FRA-25, FRA-26; selection/order inside the resonator and the mod-count gate stay open (#9) |
| patch_3_29.md: beast splitting replaced by fracture crafts (rare Talisman, 4 / 6 modifiers) | Confirmed: FRA-27 |
| basic_currency.md: Annulment excludes fractured mods; Scouring keeps fractures and then sets rarity from retained affixes; Divine skips fractured | Confirmed: FRA-16, FRA-17, FRA-19 |
| basic_currency.md: Scouring with a fracture on one prefix and one suffix -> rare (CoE `poec_simClearItem`) | Conflicts with wiki (Tainted Chaos Orb: one fractured prefix and/or one suffix -> magic); only reachable with 2 fractures, so not used by the orb. Wiki wins; unbacked |
| basic_currency.md / affix_generation.md: Alteration/Chaos retain fractures; retained fractured mods consume slots and count toward the 4/5/6 total (CoE) | Retention confirmed (FRA-18); count/slot-total unbacked: OPEN-06 |
| essences.md: Essence rejects a fractured-group conflict, retains fracture + forced mod | Unbacked: OPEN-06 |
| harvest.md: Harvest reroll retains fractures | Retention follows FRA-18; detail unbacked: OPEN-06 |
| eldritch_currency.md: Chaos/Annul details on fractured items; "fractured items can carry these implicits" | Carry confirmed: FRA-24; the rest unbacked (CoE) |
| veiled.md: Veiled Chaos rejects retained fractured veiled equivalents | Unbacked: OPEN-04, OPEN-06 |
| beast_crafting.md: fractured items cannot be imprinted/restored, including fractured after the imprint | Confirmed: FRA-14. Splitting legacy: FRA-27 |
| influence_orbs.md: influence orbs exclude fractured | Confirmed: FRA-23 |
| synthesis.md: synthesised base still cannot be fractured after Eldritch implicit | Confirmed (wiki Synthesised item: "The item base will still be Synthesised (e.g. still cannot be fractured)."): FRA-05 |
| fossils_resonators.md: S56 "weights do not affect Fractured Fossil fracture selection" | Unbacked (#9) |
| corruption.md: mirrored/fractured special-state checks open | FRA-29 for jewels/maps/contracts; equipment still OPEN-09 |
| recombinators*.md: fractured candidates count only when their own base is chosen | Out of scope here (B3); not checked |

---

## 4. Cross-checks (not evidence)

- Craft of Exile: per the prototype (not re-read in this run; the CoE site is not scrapable by the tools here) its code draws uniformly over all existing affixes, which agrees with the 1/n assumption and with the 25% in the PoE Vault guide. The CoE [how-to-use](https://www.craftofexile.com/how-to-use) page does not mention the Fracturing Orb.
- Path of Building (`src/Classes/Item.lua`, dev branch): only parses/stores/prints the `{fractured}` flag (`Craft` copies `affix.fractured`); no selection logic in the first 100000 characters (file read truncated).
- poedb [Fracturing Orb](https://poedb.tw/us/Fracturing_Orb): same item text as FRA-28; no distribution, no crafted/metamod statement.
- PoE Vault guide (https://www.poe-vault.com/guides/shrapnel-ballista-hierophant-gear-flasks, route R04): "Make sure your quiver has exactly 4 explicit modifiers." and "There is a 25% chance of success." Agrees with uniform 1/4; no sample.
- Reddit / forum (players, no sample or tiny): r/pathofexile 1000x6r (2022-12-31, "27-30% hit rate", "around 14 hits out of 20", opposing opinions on weighting); r/pathofexile 193f5rb (2024-01-10, 51 failures in a row on physical mods, opinion "weighted"); forum 3589504, 3329926, 3336876, 3378241 (player replies, none from GGG). They neither settle uniformity nor contradict it.
- Wiki internal oddities: [Crafting](https://www.poewiki.net/wiki/Crafting) table row for the orb reads "non-fractured, synthesised, and influenced" (typo for "non-"); the Fracturing Orb sentence "does not reroll" cites a thread that does not say it.

---

## 5. Not covered

Allflame crafting copies, Recombinator behaviour with fractured modifiers, Ruthless, PoE 2 (the poe2wiki "Fracture" page is a different game), Harbinger shard recipes and drop sources.

## 6. Sources read

Official (pathofexile.com forum, read 2026-10-30): 3.20.0 [3323944](https://www.pathofexile.com/forum/view-thread/3323944) (posted 2022-12-01); 3.29.0 [3985332](https://www.pathofexile.com/forum/view-thread/3985332) (Stacey_GGG, 2026-07-17); 3.25.0 [3531661](https://www.pathofexile.com/forum/view-thread/3531661) (2024-07-19); 3.20.2 [3351563](https://www.pathofexile.com/forum/view-thread/3351563); 3.19.0d/e [3298509](https://www.pathofexile.com/forum/view-thread/3298509), [3299392](https://www.pathofexile.com/forum/view-thread/3299392) (Harvest predecessor, 4-mod gate); 3.28.0 [3913392](https://www.pathofexile.com/forum/view-thread/3913392) (drop pool); first posts of all 314 patch-note threads 3.19.0-3.28.x and of every 3.29.x thread (3.29.0 hotfixes, 3.29.0b, 3.29.1, 3.29.2, 3.29.3 and hotfixes, 3.29.3b) grepped for "fractur"; forum threads 3324396, 3589504, 3329926, 3336876, 3378241 (cross-check).

Wiki (revision ids, timestamps): [Fracturing Orb](https://www.poewiki.net/wiki/Fracturing_Orb) 1681353 (2026-07-26); [Fractured item](https://www.poewiki.net/wiki/Fractured_item) 1701034 (2026-08-17); [Crafting Bench](https://www.poewiki.net/wiki/Crafting_Bench) 1700860 (2026-08-16); [Metamod](https://www.poewiki.net/wiki/Metamod) 1700578; [Corrupted](https://www.poewiki.net/wiki/Corrupted) 1702221; [Mirrored](https://www.poewiki.net/wiki/Mirrored) 1493172; [Eldritch implicit modifier](https://www.poewiki.net/wiki/Eldritch_implicit_modifier) 1697697; [Imprint](https://www.poewiki.net/wiki/Imprint) 1702288; [Divine Orb](https://www.poewiki.net/wiki/Divine_Orb) 1681165; [Modifier](https://www.poewiki.net/wiki/Modifier) 1703013; [Fractured Fossil](https://www.poewiki.net/wiki/Fractured_Fossil) 1701036; [Orb of Chance](https://www.poewiki.net/wiki/Orb_of_Chance) 1681150; [Influenced item](https://www.poewiki.net/wiki/Influenced_item) 1635654; [Synthesised item](https://www.poewiki.net/wiki/Synthesised_item) 1675552; [Crafting](https://www.poewiki.net/wiki/Crafting) 1697718; also Tainted Chaos Orb, Shaper's Exalted Orb, Beastcrafting, Fenumal Plagued Arachnid, Allflame crafting, Harvest crafting, Orb of Annulment/Scouring/Alteration, Chaos Orb, Exalted Orb, Essence, Vaal Orb (no fracture-specific statement beyond those cited), Version 3.29.0, Talk:Fractured item. Wiki access: poewiki.net through the built-in browser; the Cloudflare challenge appeared intermittently and cleared by waiting.

Datamined (repoe-fork 3.29.3.3, exported 2026-10-19): `base_items.json` (`CurrencyFractureRare`, `CurrencyFractureRareShard`, `CurrencyDelveCraftingMirror`, `CurrencyImprintOrb`, `CurrencyImprint`), `mods.json` (metamod ids; full scan for "fracture"), `fossils.json`, `crafting_bench_options.json`. Scripts: `.claude/scratch/research-fracturing-orb/q1.py`..`q6.py`.

Non-admitted, cross-check only: poedb Fracturing Orb; PoE Vault guide; PoB `Item.lua`; Craft of Exile how-to-use; Reddit threads 1000x6r, 193f5rb, 1pcqi4s via the `gpt-research` tool (Reddit not directly openable); prototype `archive/prototype` fact sheets listed in section 3.
