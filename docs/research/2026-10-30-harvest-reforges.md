# Harvest reforges in PoE 1 3.29 (ordinary)

Ticket: [#10 Harvest reforges in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/10) (map #1, claim prefix `HRV`). Date checked: **2026-10-30**. Patch: **3.29.3.3**. Evidence rule: [#2 Q2](https://github.com/Rasslabsya4el/crafting-system/issues/2). Script for the R12 numbers: `docs/research/2026-10-30-harvest-reforges-r12.py` (stdlib only; run `python -I <script> <repoe-3.29.3.3 folder>`).

## Answer

- **What exists.** 3.29 has 16 tagged rare reforges ("Reforge a Rare item with random modifiers, including a X modifier": Fire, Cold, Lightning, Physical, Life, Defence, Chaos, Attack, Caster, Speed, Critical, plus Minion, Elemental, Attribute, Mana, Drop which also cost Crystallised Rancour), two "more / less likely to receive the same modifier types" reforges (200 Wild each) and two influence reforges. The **keep-prefixes / keep-suffixes reforges do not exist** in 3.29. Costs: HRV-02, HRV-13, HRV-15.
- **What is admitted about the mechanism.** A tagged reforge rerolls the modifiers of a Rare item "similar to a Chaos Orb" and guarantees one modifier with the tag; it cannot be used if the item's pool has no such modifier; Prefixes / Suffixes Cannot Be Changed are respected (open slots on that side may be filled); a fractured modifier is permanent; since 3.27.0 the craft "respects" Cannot roll Attack / Caster Modifiers (HRV-03, 04, 10, 11, 12).
- **What is NOT admitted, and blocks coding the primitive.** (1) How the guaranteed modifier is picked (pool = tagged mods the item can roll, weighted by spawn weight, drawn before the rest?). (2) Whether the 3.27.0 restriction covers only the guaranteed draw or every new draw, and whether it needs Suffixes Cannot Be Changed. (3) The mod-count distribution for a Harvest reforge (only Chaos Orb's 4/5/6 = 8:3:1 is on a wiki page) and how locked / fractured modifiers count in it. (4) The multiplier of the more / less likely reforges. No Harvest craft table exists in the repoe-fork export, so none of this has a datamined source. See O-01 to O-06.
- **R12.** The guide's three numbers are **single-draw weight shares** (weight of the target / weight of a pool), not the chance that a finished item has the mod. With 3.29 weights: 1.338% and 2.88% reproduce exactly (200/14,950 and 200/6,950); the Chaos figure is 0.0932% (200/214,650) against the guide's 0.0935% (200/213,850), a pool-total difference of 800. The exact per-click probability under candidate draw rules is 0.473% (Chaos), 1.722% (Reforge Lightning), 3.17% or 3.32% (with fractured Lightning Resistance): so R12's "2.88%" can be acceptance-tested only as a formula on weights, not as the solver's output (section 5).

## 1. Admitted claims

Source kinds: `official`, `wiki`, `datamined`, `owner`. "Checked" is 2026-10-30 for all. Wiki revisions read: Harvest crafting rev 1699145 (edited 2026-08-05, history to 3.29.0), List of harvest crafting options rev 1699144 (2026-08-05), Metamod rev 1700578 (2026-08-11, history to 3.27.0), Modifier rev 1703013 (2026-10-10), Chaos Orb rev 1681144 (2026-07-26), Fractured item rev 1701034 (2026-08-17). Lifeforce columns on the wiki table are Wild, Vivid, Primal, Sacred (Sacred Crystallised Lifeforce) and Rancour (Crystallised Rancour); the numbers are item counts.

### The crafts

**HRV-01** (wiki) Sixteen tagged rare reforge crafts exist: Fire, Cold, Lightning, Physical, Life, Defence, Chaos, Attack, Caster, Speed, Critical, Minion, Elemental, Attribute, Mana, Drop. Each is offered for a Rare item. Patch 3.29. URL: https://www.poewiki.net/wiki/List_of_harvest_crafting_options#Core_game (same table in https://www.poewiki.net/wiki/Harvest_crafting#List_of_harvest_crafting_options). Quote: "Reforge a Rare item with random modifiers, including a Lightning modifier".

**HRV-02** (wiki; amounts for Attack / Caster also `official`) Lifeforce cost per use of a tagged reforge (Wild / Vivid / Primal / Sacred / Rancour): Fire 50 Wild; Cold 50 Vivid; Lightning 50 Primal; Physical 50 Vivid; Life 75 Wild; Defence 75 Primal; Chaos 100 Vivid; Attack 75 Wild; Caster 75 Primal; Speed 150 Vivid; Critical 150 Primal; Minion 200 Primal + 3 Rancour; Elemental 200 Wild + 1 Rancour; Attribute 200 Vivid + 2 Rancour; Mana 200 Primal + 2 Rancour; Drop 200 Vivid + 1 Rancour. Patch 3.29 (Rancour crafts added in 3.28.0, marked "[Undocumented]" by the wiki, so no GGG note). URL: https://www.poewiki.net/wiki/List_of_harvest_crafting_options#Core_game. Quote (row): "Reforge a Rare item with random modifiers, including a Lightning modifier 0 0 50 0 0". Official corroboration for the 75 (Kieren_GGG, 3.19.0e, 2022-08-25, https://www.pathofexile.com/forum/view-thread/3299392): "now have a cost of 75 (previously 125)".

**HRV-03** (wiki) A tagged reforge rerolls the modifiers of a Rare item as a Chaos Orb does and guarantees one modifier with the chosen tag. Patch 3.29 (page rev 1703013). URL: https://www.poewiki.net/wiki/Modifier#Harvest_Crafting. Quote: "will completely reforge the modifiers of a Rare item, similar to a Chaos Orb, while guaranteeing a modifier with the specified tag".

**HRV-04** (wiki) The craft cannot be used when the item's mod pool holds no modifier with the chosen tag. Patch 3.29. URL: https://www.poewiki.net/wiki/Modifier#Harvest_Crafting. Quote: "no valid tags in the mod pool to roll for the selected item, the craft cannot be used".

**HRV-05** (wiki) The tag of a Harvest craft is the mod tag shown on the modifier when the player holds Alt; the same tags drive Catalysts, Fossils and the Cannot roll Attack / Caster metamods. Patch: 3.12.0 onward, page state 3.29. URLs: https://www.poewiki.net/wiki/Modifier#Mod_tag ("These tags can interact with Catalysts, Fossils, Harvest crafting, and Heist enchantments."), https://www.poewiki.net/wiki/Metamod#Version_history (3.12.0: "the tags displayed when holding alt (which were previously used for fossil and Harvest crafting)"). Caveat: which repoe-fork field carries these tags is O-05.

**HRV-06** (wiki; restated from #2 facts) A modifier shares a family with others; only one modifier of a family can be on an item, so a family already on the item (a kept or fractured modifier) is excluded from every later draw. Patch 3.29. URL: https://www.poewiki.net/wiki/Modifier#Group/family. Quote: "Only one modifier from any given group may appear on an object".

**HRV-07** (wiki; restated) Spawn weight of a modifier for a base: take the base's tags, the left-most tag that appears in the modifier's spawn-weight list decides the weight; weight 0 discards the modifier. Patch 3.29. URL: https://www.poewiki.net/wiki/Modifier#Spawn_weight_tag. Quote: "If multiple tags apply, the left-most tags are most important".

**HRV-08** (wiki) A modifier's required level is the minimum item level at which it can appear on an item. Patch 3.29. URL: https://www.poewiki.net/wiki/Modifier#Mod_Level. Quote: "The required level of the relevant entity. For example, this can be the required item level". (That the guaranteed draw also honours it is O-07.)

**HRV-09** (wiki + owner) A Chaos Orb on a regular item produces a Rare with 4, 5 or 6 affixes at 8:3:1, i.e. 2/3, 1/4, 1/12. Patch 3.29 (Chaos Orb page rev 1681144, version history to 3.28.0e). URLs: https://www.poewiki.net/wiki/Chaos_Orb#Mechanics; owner decision https://github.com/Rasslabsya4el/crafting-system/issues/2 (Q2 round text: "Rare reroll 4/5/6 = 8:3:1 is accepted (wiki)"). Quote: "affix count of 4, 5, or 6 at a ratio of 8:3:1". Whether the Harvest reforge uses this distribution is O-03.

### Metamods and locked modifiers

**HRV-10** (wiki) A tagged reforge respects Prefixes Cannot Be Changed and Suffixes Cannot Be Changed: modifiers on the locked side are kept, and open slots on that side may still be filled by new modifiers. Patch 3.29 (Metamod rev 1700578). URL: https://www.poewiki.net/wiki/Metamod#Rules_and_Exceptions. Quote (Harvest row): "Respected, but open prefixes may be filled" (suffix cell: "Respected, but open suffixes may be filled").

**HRV-11** (official; wiki agrees) Since 3.27.0 a tagged reforge respects modifiers that restrict modifier types (Cannot roll Attack Modifiers, Cannot roll Caster Modifiers). The statement does not say which draws. Patch 3.27.0 (Stacey_GGG, 2025-10-24). URL: https://www.pathofexile.com/forum/view-thread/3869068 (League Changes). Quote: "will now respect modifiers on items which restrict modifier types". Wiki (https://www.poewiki.net/wiki/Metamod#Rules_and_Exceptions): "Respected (as of 3.27)", with a "[confirmation needed because of : may require Suffixes Cannot Be Changed]" flag (scope: O-02). Patch notes 3.29.0 (3985332), 3.29.0b (3989412), 3.29.1 (3991672), 3.29.3 (3996516), 3.29.3b (4001117) contain no later change (HRV-22).

**HRV-12** (wiki) A fractured modifier is permanent: it cannot be rerolled or removed, so a reforge leaves it on the item, in its slot. Patch 3.29 (Modifier rev 1703013; Fractured item rev 1701034). URLs: https://www.poewiki.net/wiki/Modifier#Explicit_modifiers; https://www.poewiki.net/wiki/Fractured_item#Mechanics ("These mods cannot be removed (by Orb of Annulment or Orb of Scouring, etc.)"). Quote: "permanently locked to the item, being unable to be rerolled or removed". No Harvest-specific exception is listed on the Harvest crafting, Metamod or Fractured item pages. How fractured modifiers count in the 4/5/6 total: O-04.

### Other reforges and removed crafts

**HRV-13** (wiki; amount also `official`) Two reforges exist: "Reforge a Rare item, being more likely to receive the same modifier types" and "... being less likely ...", each 200 Wild. The multiplier is not documented (O-06). Patch 3.29. URL: https://www.poewiki.net/wiki/List_of_harvest_crafting_options#Core_game. Official (Kieren_GGG, 3.19.0e, 2022-08-25, https://www.pathofexile.com/forum/view-thread/3299392): "Reforge a Rare item, being more likely to receive the same modifier types now has a cost of 200 (previously 300)"; also "We have also increased the more/less likely chances of these two crafting outcomes".

**HRV-14** (wiki) No "keep all prefixes" or "keep all suffixes" reforge is in the 3.29 list of Harvest crafts; the wiki calls the former removed. Patch 3.29 (removal patch not located, O-08). URLs: https://www.poewiki.net/wiki/Harvest_crafting (infographic caption), https://www.poewiki.net/wiki/List_of_harvest_crafting_options#Core_game (no such row). Quote: "(removed) "Reforge an item keeping all prefixes" craft".

**HRV-15** (wiki; amounts also `official`) Two influence reforges exist: "Randomise the Influence types on an Influenced Normal, Magic or Rare Item, as well as reforging the item with new random modifiers" (1000 Primal) and "Reforge an Influenced Rare item with random modifiers, including a Influence modifier" (5000 Primal + 1 Sacred). Patch 3.29. URL: https://www.poewiki.net/wiki/List_of_harvest_crafting_options#Core_game. Official amounts (3.19.0e): "now has a cost of 1000 (previously 10000)", "now has a cost of 5000 (previously 50000)". (Influence behaviour belongs to batch B2.)

**HRV-16** (wiki) The influence-randomising reforge respects Prefixes / Suffixes Cannot Be Changed (open slots may be filled) but cannot be used if any modifier on the locked side is influenced. Patch 3.29. URL: https://www.poewiki.net/wiki/Metamod#Rules_and_Exceptions. Quote: "usage is prevented if any prefix is influenced".

**HRV-17** (wiki; amounts also `official`) Add / remove crafts exist for 11 tags: "Add a new Fire modifier and remove another random modifier from a non-Influenced item" (Fire, Cold, Lightning, Physical 15,000 each of Wild / Vivid / Primal / Vivid; Life 17,500 Wild, Defence 17,500 Primal, Chaos 17,500 Vivid, Attack 17,500 Wild, Caster 17,500 Primal; Speed 20,000 Vivid, Critical 20,000 Primal), each also +1 Sacred. No Rancour tags have an add / remove craft. Patch 3.29. URL: https://www.poewiki.net/wiki/List_of_harvest_crafting_options#Core_game. Official amounts (3.19.0e): "now have a cost of 15000 (previously 25000)", 17500, 20000. Quote: "remove another random modifier from a non-Influenced item".

**HRV-18** (wiki) For add / remove crafts the added modifier obeys Cannot roll Attack / Caster and the prefix / suffix locks; the removal step ignores Cannot roll Attack / Caster, and a metamod never protects a modifier from Harvest removal. Patch 3.29. URLs: https://www.poewiki.net/wiki/Harvest_crafting#Mechanics; https://www.poewiki.net/wiki/Metamod#Rules_and_Exceptions (cell "Respected when adding, ignored when removing"); https://www.poewiki.net/wiki/Modifier#Metamods ("The metamod does not protect mods from removal when used with other crafts that remove a single modifier").

**HRV-19** (wiki) Six resistance-swap crafts exist ("Change a modifier that grants Cold Resistance into a similar-tier modifier that grants Fire Resistance" and the five other ordered pairs), 500 each (Wild for target Fire, Vivid for Cold, Primal for Lightning); six damage-swap crafts, 500 + 1 Rancour; the swap keeps the tier and rerolls the value inside the tier. Since 3.28.0 hotfix 8 the damage swap does not work on critical strike multiplier modifiers. Patch 3.29. URLs: https://www.poewiki.net/wiki/List_of_harvest_crafting_options#Core_game; https://www.poewiki.net/wiki/Modifier#Harvest_Crafting ("This craft preserves the tier, but not the roll within that tier."); https://www.poewiki.net/wiki/Harvest_crafting#Version_history (3.28.0).

**HRV-20** (official) Removed in 3.29.0: the Harvest craft that synthesises an item and the Horticrafting Station craft that turns a random socket white. Patch 3.29.0 (Stacey_GGG, 2026-07-17). URL: https://www.pathofexile.com/forum/view-thread/3985332. Quote: "The Harvest crafting option to Synthesise an item has been removed."

**HRV-21** (wiki) The Harvest craft that fractures a random modifier was removed in 3.20.0 (replaced by the Fracturing Orb). Patch 3.20.0. URL: https://www.poewiki.net/wiki/Harvest_crafting#Version_history. Quote: "have removed the Harvest Craft that fractures a random modifier on an item".

**HRV-22** (official; scan result) The official notes 3.29.0, 3.29.0b, 3.29.1, 3.29.3 and 3.29.3b change no Harvest reforge, no lifeforce cost and no metamod interaction (3.29.3 only fixes "Harvest could fail to begin"). Notes for 3.29.2 and for the hotfix threads were not read here; the sibling bench-metamods report (its O-12, keyword "Harvest reforge/craft") scanned 3.29.0 hotfixes 1-3, 3.29.0b hotfixes 1-4, 3.29.1 + hotfix, 3.29.2 + hotfixes 1-3 and 3.29.3 + hotfix 1 and found no Harvest-craft change (not re-verified here). A change in 3.28.0 or earlier is covered by the wiki history of HRV-01. URLs: https://www.pathofexile.com/forum/view-thread/3985332, /3989412, /3991672, /3996516, /4001117.

**HRV-23** (wiki) Lifeforce is itemised currency; each craft can be used any number of times while the player holds the lifeforce for it. Patch 3.19.0 onward. URL: https://www.poewiki.net/wiki/Harvest_crafting#Version_history (3.19.0). Quote: "They can be used as many times as you like, as long as you have the necessary lifeforce."

### Datamined records used by R12 (repoe-fork 3.29.3.3, https://repoe-fork.github.io/mods.json)

**HRV-24** (datamined) The target is `GlobalLightningGemLevel1`: domain `item`, generation_type `prefix`, required_level 75, spawn_weights `[{amulet: 200}, {default: 0}]`, groups `["GlobalDamageTypeGemLevel"]`, implicit_tags `["elemental", "lightning", "gem"]`, text "+1 to Level of all Lightning Skill Gems". Patch 3.29.3.3.

**HRV-25** (datamined) The other 22 amulet modifiers with implicit tag `lightning` (all domain `item`; weights from spawn_weights tag `amulet`): `AddedLightningDamage1..8` prefix, levels 3/13/22/28/35/44/52/64, weight 500 each, family `LightningDamage`; `AddedLightningDamage9` prefix level 76 weight 250, family `LightningDamage`; `LightningResist1..8` suffix levels 1/13/25/37/49/60/72/84, weight 1000 each, family `LightningResistance`; `LightningDamagePercent1..5` suffix levels 10/23/36/50/64, weight 500 each, family `LightningDamagePercentage`. Sum at item level 84 or higher = 14,950; family `LightningResistance` = 8,000; family `LightningDamage` = 4,250; `LightningDamagePercentage` = 2,500. Patch 3.29.3.3.

**HRV-26** (datamined) `GlobalDamageTypeGemLevel` has five amulet members, all prefix, level 75, weight 200: `GlobalFireGemLevel1_`, `GlobalColdGemLevel1__`, `GlobalLightningGemLevel1`, `GlobalPhysicalGemLevel1_`, `GlobalChaosGemLevel1`. Any one of them on the item excludes the other four. Patch 3.29.3.3.

## 2. Open (not admitted)

Each item: what is known, from which non-admitted source, and what would settle it.

**O-01 How the guaranteed modifier is chosen** (blocks the tagged-reforge primitive). Admitted: only "guaranteeing a modifier with the specified tag" and "the mod pool ... for the selected item" (HRV-03, HRV-04). Not admitted: that the pool is the tagged modifiers the item can roll, that the pick is proportional to spawn weight, that it is drawn first and the rest afterwards from the full pool, and whether the guaranteed pick can overlap later picks. Known from: PoE Vault guide (14,950 total; 200/14,950 uses exactly this model); Craft of Exile code per the prototype notes ("add one tagged mod first"). Settle by: a GGG statement (none found, searches of forum and wiki 2026-10-30), or a large-sample experiment. Design: reforge an amulet (item level 84+) with Reforge Lightning at least 2,000 times and count `+1 to Level of all Lightning Skill Gems`; the weight-proportional model predicts 1.72% (section 5), a uniform pick over the 23 tagged mods 4.7% (computed with the same script logic), so even 300 trials separate those two; telling weight-proportional from a boosted-weight variant needs 20,000+ trials.

**O-02 Scope of Cannot roll Attack / Caster Modifiers on a tagged reforge** (the prototype's Q6). Admitted: the craft respects them since 3.27.0 (HRV-11). Not admitted: whether only the guaranteed draw is restricted or every new draw, and whether Suffixes Cannot Be Changed is required (the metamod is itself a suffix, and the wiki marks the cell "confirmation needed"). Known from: Craft of Exile's metamod page (first added modifier only; Craft of Exile is not evidence); a November 2025 forum bug thread (https://www.pathofexile.com/forum/view-thread/3874125) with only player replies, no sample. Settle by: a GGG reply, or an experiment: item with Cannot roll Attack Modifiers and Suffixes Cannot Be Changed, Reforge Caster, count results containing an attack-tagged modifier other than the guaranteed one (if later draws are unrestricted the rate is large; 100 trials suffice); repeat without the suffix lock. Until settled, a tagged reforge on an item that carries either metamod is not an admitted action; a plain tagged reforge is not affected.

**O-03 Mod-count distribution of a Harvest reforge** (blocks the primitive unless the main chat extends the owner's Q2 decision). Admitted: Chaos Orb 4/5/6 = 8:3:1 (HRV-09) and "similar to a Chaos Orb" (HRV-03). Not stated anywhere: that a Harvest reforge draws its total from the same distribution, and whether the guaranteed modifier is inside the total. Candidate C1: same 8:3:1, guaranteed modifier inside the total (used in section 5). Settle by: one line from the owner that "Rare reroll" in #2 covers Harvest reforges, or an experiment (count affixes over 1,000+ tagged reforges: C1 predicts 66.7% / 25% / 8.3% for 4 / 5 / 6).

**O-04 Locked and fractured modifiers inside the count.** Admitted: the fractured modifier stays (HRV-12) and its family is excluded (HRV-06). Not admitted: whether it counts toward the 4/5/6 total (candidate F-in: total includes it, so n-1 new modifiers; candidate F-out: n new modifiers, so the item can reach 7). Same question for the locked side of Prefixes / Suffixes Cannot Be Changed (the prototype subtracted retained affixes: candidate F-in). Settle by: experiment, 500+ tagged reforges on an item with one fractured modifier, tally total affixes ({4,5,6} against {5,6,7}). R12 is computed under both (section 5).

**O-05 Which datamined field is the tag.** The Harvest tag is the Alt-tooltip tag (HRV-05); repoe-fork exposes `implicit_tags` per mod. No source states the two are the same field. Consistency check run on 3.29.3.3 (script in scratch, not committed): all 16 craft tag names occur as `implicit_tags` values (the craft "Defence" is tag `defences`); `ChanceToAvoidElementalStatusAilments1` has fire, cold and lightning, as the wiki's examples say; for 23 text patterns taken from the wiki's tag examples, 20 agree with the tag on at least 86% of matching mods (lowest: Caster 67%, Curse 78%, Minion 81%, where the text pattern over-matches unrelated mods); and the 14,950 total of the PoE Vault guide is reproduced exactly with `implicit_tags`. Settle by: the wiki Cargo definition of the mod `tags` field, or an in-game Alt check of a few mods (hybrid and gem-level mods).

**O-06 More / less likely reforge: multiplier and meaning of "same modifier types".** Only "increased the more/less likely chances" (3.19.0e) and the cost. Unknown: the multiplier, whether "type" means repoe `type`, family or tag, whether the effect applies to every draw. Settle by: GGG statement or an experiment with at least 1,000 crafts per craft (share of kept mod types).

**O-07 Does the guaranteed draw honour item level and the base's tags?** The general rule is HRV-07, HRV-08; no Harvest-specific text. (The wiki's Metamod page records that beastcrafting ignores item level; nothing is recorded for Harvest.) Settle by: one experiment: Reforge Lightning on an item level 76 amulet and an item level 84+ amulet; `LightningResist8` (level 84) must not appear on the first.

**O-08 Removal patch of the keep-prefix / keep-suffix reforges.** Present in 2020 (official 3.11 announcement, https://www.pathofexile.com/forum/view-thread/2874544: "Reroll a Rare item, keeping all Prefixes"), gone from the 3.29 list (HRV-14). Not located in the 3.13.0, 3.14.0, 3.19.0 wiki patch notes. Low priority: absence in 3.29 is what the model needs.

**O-09 Item restrictions of the tagged reforge beyond "Rare".** Not stated: influenced, corrupted, mirrored, synthesised items; whether the craft is refused when every slot is locked. (Batch B1 uses non-influenced rares; the prototype's "reject if both sides locked" is unbacked.)

**O-10 Add / remove crafts (adjacent).** The order of add and remove, whether the added modifier can be the one removed (the prototype says probability 0 from Craft of Exile), whether the removal is uniform, and what happens on a full item. Only HRV-17 and HRV-18 are admitted.

**O-11 Acceptance meaning of R12** (a decision, not a fact): see section 5; the guide's numbers are not per-click probabilities.

Blocks coding the tagged-reforge primitive: O-01, O-03, O-04 (counts and draw rule), O-05 (pool); blocks only the metamod combinations: O-02; blocks only the more / less likely craft: O-06.

## 3. Prototype re-audit (`docs/mechanics/harvest.md`, `docs/OPEN_QUESTIONS.md` Q4, Q6, Q26 on `archive/prototype`)

| # | Prototype claim | Verdict |
|---|---|---|
| 1 | S42 lists rare reforges that guarantee a tag, and add-tagged / remove-another crafts for non-influenced items | confirmed: HRV-01, HRV-03, HRV-17 |
| 2 | Modern "augment" is not an unconditional extra modifier | confirmed: HRV-17 (add and remove) |
| 3 | More / less likely reforges, resistance / damage conversions, influence randomisation exist | confirmed: HRV-13, HRV-19, HRV-15 |
| 4 | Keep-prefix / keep-suffix reforges, standalone tagged annuls, Harvest synthesis are not current | confirmed: HRV-14, HRV-20; standalone annuls: "Most Annulment-type crafts" removed in 3.14.0 (wiki, https://www.poewiki.net/wiki/Harvest_crafting#Version_history), not in the 3.29 list |
| 5 | Tag table: 11 base tags + Minion / Elemental / Attribute / Mana / Drop via Rancour | confirmed: HRV-01, HRV-02 |
| 6 | Public spelling "defence" maps to PoB `defences` | confirmed as a label: the repoe-fork tag id is `defences` (O-05) |
| 7 | Owner-confirmed Minion / Elemental / Attribute / Mana availability, Drop not enabled | out of scope: owner decisions of the old project, not in #2 to #4; the crafts exist (HRV-01) |
| 8 | Fire reforge 50 Wild, Life 75 Wild, Fire add / remove 15000 Wild + 1 Sacred | confirmed: HRV-02, HRV-17 |
| 9 | CoE step 1-2: rare reroll, retains fractures and protected sides, clears the rest | changed: retains fractured (HRV-12) and locked sides with open slots refillable (HRV-10) are admitted; "rebuilds metamod flags from survivors" unbacked |
| 10 | Tagged mod added first, then the rest through shared weighted selection | unbacked: O-01 |
| 11 | Draw total 4/5/6 at 8:3:1, subtract retained / forced counts | partly: 8:3:1 for Chaos Orb (HRV-09); application to Harvest and the subtraction: O-03, O-04 |
| 12 | 3.27 respects modifier-type restrictions (S19) | confirmed: HRV-11 |
| 13 | First-draw-only interpretation ("owner row 2") | unbacked: O-02; not an owner decision in #2 to #4 |
| 14 | Add / remove: removal ignores attack / caster blocks, add respects them, side locks apply | confirmed: HRV-18 |
| 15 | Add / remove: removal excludes the new mod; full item rejected; failed atomic restore (Craft of Exile 2342-2344, 2707-2708) | unbacked: O-10 |
| 16 | Legacy `crsim_hnerf` toggle | not applicable: Craft of Exile internal |
| 17 | Side protection: existing protected affixes survive, free slots may be filled | confirmed: HRV-10 |
| 18 | Empty guaranteed pool rejects the action | confirmed: HRV-04 |
| 19 | "Both sides completely protected and no slot, reject" | unbacked: O-09 |
| 20 | All draws exclude chosen families, occupied groups and capacities | confirmed for families: HRV-06; capacity (3 + 3) is the affix-draw ticket |
| 21 | Weights, groups, item level from PoB | changed: datamined repoe-fork is the source (#2 Q1); PoB `group` is a type |
| 22 | Royal Burgonet item level 86, eligible life prefixes weigh 13,000 (ten `IncreasedLife` + three `LocalBaseArmourAndLife` at 1,000) | confirmed on 3.29.3.3 (`HelmetStr10`, tags str_armour / helmet / armour / default): 13 mods, 13,000; families are `IncreasedLife` and `BaseLocalDefencesAndLife` |
| 23 | Q6: suffix lock needed for Cannot roll Attack / Caster to affect later draws? | open: O-02 |
| 24 | Q4: 8:3:1 independently verified? | wiki + owner: HRV-09 (not datamined) |
| 25 | Q26: Rancour tags part of the loadout | crafts exist (HRV-01); loadout choice is a target / config matter |
| 26 | More / less likely weighting needs verified tables (Q12) | still open: O-06 |
| 27 | Renewal-formula examples (A + (c + b*A)/p) | arithmetic fixtures, not mechanics claims |

## 4. Interactions summary (what the primitive may do today)

Admitted and codable now: availability and costs (HRV-01, 02, 13, 15, 17), the pool-empty refusal (HRV-04), Prefixes / Suffixes Cannot Be Changed (HRV-10), fractured permanence and family exclusion (HRV-12, 06). Not codable until an admitted source or owner decision: the guaranteed draw (O-01), the count (O-03, O-04), metamod Cannot roll scope (O-02), more / less likely (O-06).

## 5. R12 reconstruction

Guide: https://www.poe-vault.com/guides/early-endgame (not evidence). Its text, read 2026-10-30: natural odds 0.094% (weight 200 of 213,850), Reforge Lightning 200 / 14,950 = 1.338%, with Lightning Resistance fractured 200 / 6,950 = 2.88%. The guide states no item level and no base name; the R12 record in `2026-10-30-5-reference-routes.md` has item level null. Target: `GlobalLightningGemLevel1` (a prefix, level 75, weight 200 on every amulet; HRV-24). Base: an ordinary amulet (11 bases in `base_items.json` carry exactly the tags `amulet`, `default`; talismans add `talisman` and are not R12; a few not_for_sale / experimental bases add other tags), pool = domain `item`, prefix and suffix mods with weight above 0 on those tags and required_level at most the item level.

**Pool by item level (3.29.3.3):** total weight 211,550 at 84, 214,350 at 85, 214,650 at 86 and above (prefix 88,600 + suffix 126,050 at 86); Lightning-tagged weight 14,950 at 84 and above (HRV-25), 13,950 at 76-83, 13,700 at 75. Without the `LightningResistance` family: 6,950 at every item level from 76 to 100 (at 84+: 14,950 - 8,000; at 76-83: 13,950 - 7,000).

**Side check on `generation_weights` (affix-draw ticket, AFX-17 / O-02).** Five amulet-pool mods carry a second weight list (`LifeLeechPermyriadSuffix1..3`, `ManaLeechPermyriadSuffix1..2`); on an amulet only its `default: 100` entry matches. If that entry is a neutral 100% multiplier nothing changes; if it replaced the spawn weight, the item-level-86 total would fall by 3,250 to 211,400. Neither reading gives the guide's 213,850, and none of the 23 Lightning-tagged mods has such a list, so 14,950 and 6,950 do not depend on it. Capacity 3 + 3 and "a full side closes" used below are AFX-10 and AFX-14 of that ticket.

**Formula F1 (what the guide computes; one draw, weight share):**
- Chaos: `w_T / sum(w, all pool)`
- Reforge Lightning: `w_T / sum(w, lightning-tagged)`
- Fractured Lightning Resistance: `w_T / (sum(w, lightning-tagged) - sum(w, family LightningResistance))`
with `w_T = 200`. The Reforge Lightning step is admitted only as far as the pool (HRV-04) and the Chaos-like reroll (HRV-03); the "weight-proportional pick from the tagged pool" step is O-01 (candidate H1). Under candidate H2 (uniform over tagged mods) the same lines give 1/23 = 4.35% and 1/15 = 6.67%.

| Number | Guide | 3.29 weights, item level 86 | item level 84 | Difference |
|---|---|---|---|---|
| Chaos | 200 / 213,850 = 0.0935% (printed 0.094%) | 200 / 214,650 = 0.0932% | 200 / 211,550 = 0.0945% | pool total: 214,650 against 213,850 (+800) |
| Reforge Lightning | 200 / 14,950 = 1.338% | 200 / 14,950 = 1.338% | same | none (needs item level 84+; 1.434% at 76-83) |
| fractured Lightning Resistance | 200 / 6,950 = 2.88% | 200 / 6,950 = 2.877% | same | none (any item level 76+) |

The +800 equals the weight of one 800-weight modifier; the only 3.29 modifier of weight 800 that enters between item levels 84 and 86 is `AllAttributes9_` (level 85), which would explain 800 only at item level 86+, whereas item level 85 gives +500; the guide's data cannot be reproduced, so the cause stays unnamed. The guide's 0.094% is the rounded 0.0935%; 3.29 gives 0.093% (86+) or 0.095% (84).

**Formula F2 (the chance that the finished item holds the mod, which is what the solver computes).** Candidate draw rules, none admitted (section 2): count n in {4,5,6} at 8:3:1 (HRV-09, O-03); successive weighted draws without replacement from the eligible modifiers, one family at most (HRV-06), at most 3 prefixes and 3 suffixes (affix-draw ticket); for a tagged reforge the first draw is from the tagged modifiers only, proportional to weight (O-01 H1), the other n-1 draws from the whole pool; the gem-level family is drawn first as a family (weight 1,000) and the member is picked 200/1,000. The script evaluates it exactly (successive sampling as an exponential race, integrated as a polynomial in exact fractions; first checked against brute-force enumeration on 40 random small pools; independently against a 150,000-trial simulation of the real pool: 0.462 / 1.731 / 3.123 / 3.302%, within 1 sigma of the exact values).

| Case (item level 86) | F1 (guide formula) | F2 exact |
|---|---|---|
| Chaos, no fractured | 0.0932% | 0.4732% |
| Reforge Lightning, no fractured | 1.338% | 1.7223% |
| Reforge Lightning, fractured Lightning Resistance, fractured counts inside n (F-in) | 2.877% | 3.1668% |
| same, fractured is extra to n (F-out) | 2.877% | 3.3216% |

Item level 84: 0.4800 / 1.7280 / 3.1712 / 3.3282%. Item level 85: 0.4744 / 1.7234 / 3.1676 / 3.3231%. Under candidate H2 (guaranteed pick uniform over the tagged mods, item level 86): 4.709% (no fractured), 6.943% (F-in), 7.091% (F-out). Chaos on the fractured item: 0.4186% (F-in), 0.5970% (F-out).

**Consequences for the acceptance test (#4 Q22).** The guide's three numbers are F1 on weights and reproduce on 3.29 data except the Chaos total (+800). The solver's output for the same action is F2, 5.1x (Chaos), 1.29x (Reforge Lightning) and 1.10x to 1.16x (fractured) the published figure, because later draws also can hit the mod and because F1 ignores the count. So "published odds match 2.88%" can hold only for the weight-share formula; the main chat or the owner must decide whether the R12 test asserts F1 on the pool builder (recommended, as Q22 words it) and F2 as the solver's expected value, since a per-click 2.88% would contradict the model.

## 6. Cross-checks (not evidence)

- **PoE Vault guide:** agrees with F1 and with 14,950 / 6,950 from 3.29 data; its 213,850 differs from 214,650 (above). It also states that a fractured modifier stays and that reforges still add the tagged modifier; both match HRV-12 and the model but are unsourced there.
- **poedb metamods** (https://poedb.tw/metamods, Craft of Exile-sourced, undated): still lists "Reforge keeping prefix / suffix" rows, which the 3.29 wiki list does not; disagrees with HRV-14. Warns that tables lag behind the game.
- **Craft of Exile:** prototype notes say its reforge adds one tagged modifier first, then fills with ordinary draws, and passes `igcrca=true` to the forced draw (ignores type restrictions). Consistent with O-01 H1 and with the pre-3.27 behaviour; says nothing for 3.27+.
- **Path of Building:** has no Harvest reforge model; used by the prototype only for weights, now replaced by repoe-fork.
- **Forum bug thread 3874125** (players only, Nov 2025): "Reforge can add prefixes, because it's a reforge" is consistent with HRV-10 (open slots may be filled); no staff reply.

## 7. Sources read

- Wiki (read with the built-in browser, 2026-10-30): https://www.poewiki.net/wiki/Harvest_crafting ; /wiki/List_of_harvest_crafting_options ; /wiki/Metamod ; /wiki/Modifier ; /wiki/Chaos_Orb ; /wiki/Fracturing_Orb ; /wiki/Fractured_item ; /wiki/Crafting ; /wiki/Guide:Harvest_crafting_quick_guide (no mechanics) ; /wiki/Version_3.19.0 ; /wiki/Version_3.19.0d ; /wiki/Version_3.13.0 ; search "keeping all prefixes". `/wiki/Fractured_modifier` does not exist. Raw wikitext fetch (`action=raw`) hit the bot challenge and was not retried.
- Official: https://www.pathofexile.com/forum/view-thread/3869068 (3.27.0) ; /3985332 (3.29.0) ; /3989412 (3.29.0b) ; /3991672 (3.29.1) ; /3996516 (3.29.3) ; /4001117 (3.29.3b) ; /3299392 (3.19.0e) ; /2874544 (Harvest announcement 2020) ; /3324396 (no relevant text) ; /3874125 (player thread). Not read here: 3.29.2 notes, the 3.29.x hotfix threads, the 3.28.0 notes (the wiki marks the Rancour crafts as undocumented, so no GGG note is expected). No thread named 3.29.3.3 was found.
- Datamined: https://repoe-fork.github.io/ , /poe1.html (file list: no Harvest craft file; `mods.json` contains only Harvest map / league mods), /data-formats/mods.html (no field descriptions), `mods.json`, `base_items.json`, `tags.json` from the local 3.29.3.3 copy.
- Could not open: Reddit. Two runs of the GPT-assisted Reddit/forum search (skill gpt-research, job ids 20261030-190011-74ed and 20261030-190635-ecd4) died or aborted at the time limit with no findings, so **no Reddit thread, GGG Reddit reply or large-sample experiment was read**; O-01 to O-04 and O-06 are open partly for that reason. WebSearch for a GGG statement on the tagged draw also found none. The wiki raw-wikitext endpoint hit the bot challenge.
- Non-admitted: https://www.poe-vault.com/guides/early-endgame ; https://poedb.tw/metamods ; prototype branch `archive/prototype` (`docs/mechanics/harvest.md`, `docs/OPEN_QUESTIONS.md`, `docs/SOURCES.md`, `docs/mechanics/patch_3_29.md`) ; `docs/research/2026-10-30-5-reference-routes.md` (R12).
