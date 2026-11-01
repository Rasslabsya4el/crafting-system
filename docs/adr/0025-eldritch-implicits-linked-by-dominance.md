# Eldritch implicits are two graded sides, and dominance is derived from the grades

ADR-0002 planned the Eldritch implicits (Eater of Worlds and Searing Exarch) as a sub-problem joined to the main model by "a single dominance flag". [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) designs the link and replaces the flag: the state keeps what each side holds, and **dominance is computed from it, never stored**. This amends ADR-0002 (the flag) and ADR-0009 (the state gains two small fields). The mechanics are in [the Eldritch research](https://github.com/Rasslabsya4el/crafting-system/issues/85).

## What the state keeps

For each of the two sides (Searing Exarch, Eater of Worlds):

- the **Eldritch grade**: 0 for no implicit, then 1 Lesser, 2 Greater, 3 Grand, 4 Exceptional, 5 Exquisite, 6 Perfect. It is the wiki's order and the reverse of `Tier` (mod tier 1 is the best; grade 6 is the best). Grade 5 and 6 come only from the Orb of Conflict;
- what the implicit gives each requirement (the same "what the mod gives" a slot holds), and **its family only when a requirement names it**. An Ember or Ichor draws by weight inside the tier and may return the family the side already had, so a family nobody asks for decides nothing and is not kept.

**Dominance** is derived: the side with the higher grade is dominant; a lone implicit is dominant by itself; equal grades, or no implicit, give no dominance. Searing Exarch dominant means the prefixes, Eater of Worlds dominant the suffixes. Eldritch Chaos, Exalted and Annulment act on the dominant side only and are not offered when nothing is dominant. The Orb of Dominance (influence) shares the word only; see ADR-0030.

## The currencies

- **Embers and Ichors** (Lesser to Exceptional, grades 1 to 4) add a Searing Exarch or an Eater implicit of that grade on a normal, magic or rare body armour, boots, gloves or helmet, replacing every implicit except the other side's. Shaper, Elder and Conqueror items refuse them; fractured items take them. The mod is drawn by weight among the mods of that side, item class and grade (grade 1 base mods; grade 2 adds the "Unique Enemy" variants at half weight; grade 3 and up adds the "Pinnacle Boss" variants at a fifth). No item-level gate (the owner: an Ember of any grade applies to level-60 boots). The same family may come back after a replacement (Craft of Exile, marked approximate). Eldritch implicits on amulets are out of v1.
- **Eldritch Chaos Orb** rerolls the dominant side of a rare item and leaves the other side and the fractured mods. It ignores `Prefixes/Suffixes Cannot Be Changed` and respects `Cannot roll Attack/Caster Modifiers`. How many modifiers it puts back is documented nowhere since 3.17.2; the planner takes **Craft of Exile's count**: a total drawn from the Chaos Orb's 4/5/6 table, less the modifiers that stay (the other side and the fractured ones), clamped to the dominant side's capacity. Marked approximate.
- **Eldritch Exalted Orb** adds one modifier to the dominant side of a rare item, **Eldritch Annulment** removes one (uniformly among the removable ones, Craft of Exile, marked approximate). Both respect the side locks and the Attack/Caster blocks. An item that gets an Eldritch implicit is not influenced and, until the owner's optional in-game check says otherwise, refuses the six influenced Exalted Orbs (ADR-0030).

## The Orb of Conflict

On a non-unique item with both implicits, Conflict raises one implicit by one grade and lowers the other by one. The planner follows the 525-use sample of the research (owner, round 2), kind `experiment`, marked approximate:

> the implicit with the higher grade `g` against the lower `g'` is raised with `p = 1 / (1 + exp(-(0.10 - 0.52 d)))`, `d = g - g' >= 0`; the lower one is raised with `1 - p`; at equal grades each side is raised with 1/2.

Two rules from the sample: **raising a grade-6 implicit does nothing**, and the other implicit is still lowered (a 6/4 item goes to 5/5 in 68% of uses); **a lowered grade 1 is removed** (grade 0). The owner approved the formula; applying it to the higher implicit is the main chat's reading, because the fitted curve applied to both implicits would make the two chances sum to more than one (it is not symmetric at `d = 0`), and the sample's 0.61 at 3/3 is a skew its author names. The sample covers `d` up to +3 and, read from the lower implicit, down to -2; with `d >= 0` here, a difference of 4 or more is extrapolation: the answer says so, and shows the cost with its spread (the three fits of the research differ there) and a mark. A flat 50% (the owner's first reading, and Craft of Exile's) is not used; the sample and the wiki's "about 11% a grade" disagree with it.

## What this changes in the solver

- The compressed state (ADR-0009) holds the two fields above, and the pool signature of an Eldritch action includes the class, the side, the grade and the dominant side.
- The actions read and add implicits through the contract extension of ADR-0027.
- None of these actions is block-invariant (ADR-0023): until a ticket proves one, it refuses the coarse state, and a query that enables it is exact or says no approximate level is available.
- Every claim here that rests on Craft of Exile or on the sample carries `approximate` (ADR-0028).

Origin: [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93), comments of 2026-10-31 (decisions, owner round 1 and round 2); [Eldritch implicits and currencies](https://github.com/Rasslabsya4el/crafting-system/issues/85); ADR-0002, ADR-0009, ADR-0013.

## Amendment: the actions ([#151](https://github.com/Rasslabsya4el/crafting-system/issues/151))

`actions/eldritch.py` holds the eight Embers and Ichors (`EldritchImplicitCurrency(side, grade)`), the three Eldritch orbs and the Orb of Conflict; their claims are `rules/claims/eldritch.yaml`. Decisions the build made, none of them a change of the rules above:

- **Dominance** is `items.dominant_side(exarch_grade, eater_grade)`, a function of the two grades (0 for none); `item_dominant_side` reads it from an item. Every Eldritch action refuses a corrupted item, an influenced item (Eldritch implicits and influence exclude each other) and a class other than body armour, boots, gloves and helmet.
- **The pool of an Ember** is read from the game data: the mods of the side and grade with a positive spawn weight on the base's tags, so a patch moves the weights with the data pin. A result holds the new implicit at its lowest values (a roll limit on an implicit is [#158](https://github.com/Rasslabsya4el/crafting-system/issues/158)).
- **Chaos** removes the unfractured mods of the dominant side, then draws the total of 4, 5 or 6 (8:3:1) less the mods that stay, up to the free slots of that side, through the ordinary pool restricted to it. A lock metamod on the other side stays and a metamod on the dominant side goes with it, as in the Chaos Orb. **Exalted** is the ordinary add restricted to the dominant side; **Annulment** is uniform among the dominant side's mods that are not fractured, locked or protected by an Attack/Caster metamod.
- **Conflict's chance** is the fit of ADR-0025 rounded to six decimals (in decimal arithmetic, so it is the same on every machine) to keep every result an exact fraction. A raised or lowered implicit is the mod of the same family and variant one grade away; a lowered Unique-Enemy or Pinnacle-Boss variant can land on a grade whose weight is 0, and Conflict keeps it (the data has the mod; no source says the game refuses it). The marks of the Conflict claims are all on its answers; `conflict_is_extrapolated(d)` says when `d` is above 3.
- **Not planner kinds yet**: the five kinds are registered with `planner=False`, because a target cannot name an Eldritch implicit yet and the dominance-limited kernels are [#152](https://github.com/Rasslabsya4el/crafting-system/issues/152). Their kernels are exact (layer 1 passes for each on fixtures).
