# Every action declares whether it cuts tiers and what strands it spends

The cut of ADR-0040 applies to some crafts and not to others, and most crafts spend a random part of the count. [Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103) fixes both per action, and what to do where no source answers. The owner's standing rule decides the unknowns: **a best estimate from the evidence, marked `approximate` (ADR-0028), never a check mid-plan and never "measure later".** The sources are [research #98](https://github.com/Rasslabsya4el/crafting-system/issues/98): the wiki's spend table, the first author's raw sheet and his comments.

## The declaration

An action's contract (ADR-0024) answers two things:

- **`cuts`**: whether its random draws of explicit mods see the cut of ADR-0040. A fixed result (an essence's guaranteed mod, a bench mod) is never cut.
- **`spend`**: the law of the strands it uses up: a ceiling and a shape. The craft draws `x` from the law and the count becomes `max(0, s - x)` after the cut, which used the count before. The data never show a count below 0, so a spend larger than the count empties it.

**The shape is a uniform integer on 0 to the ceiling**, unless the sheet rejects uniform at the 1% level (chi-square above 13.3 on the the five equal bins of the sheet count (read as 0-9, 10-19, 20-29, 30-39, 40-50; the means below are bin-centre means, and the sheet-fit research refits the edges)): then the measured five-bin frequencies, uniform inside a bin, are the law. Two currencies fail the test and use their bins: **Chaos Orb** (130 uses with at least 50 strands: 45, 27, 25, 21, 12; chi-square 22.5; mean spend 19.5, not 25) and **Orb of Alchemy** (260 uses: 67, 16, 55, 65, 57; chi-square 33.2; mean 26.1, close to uniform's 25). The Foulborn Augmentation (306 uses, five bins over 0 to 32: 64, 50, 62, 59, 71; chi-square 3.8) and the rest are uniform. Every shape is `approximate`: the bins are one author's sample and the ceiling may depend on the mod count of a reroll; the sheet-fit research ticket of the B5 chart replaces them through the claim history (#120) when it lands.

An action that has **not declared** anything is **refused on an item with `s >= 1`** (the default of ADR-0004), so no later action can silently ignore strands. It is a guard for code that was added without a declaration; every action the plan knows has its row below.

## The table

| Action | Cuts | Spend ceiling | Basis |
|---|---|---|---|
| Orb of Transmutation, Augmentation, Alteration | yes | 8 | wiki table; the sheet (Foulborn Augmentation) |
| Regal Orb | yes | 16 | wiki; 13 sheet rows |
| Orb of Alchemy, Orb of Binding (ADR-0048: it mods as an Alchemy) | yes | 50, bins | wiki lists both at 0-50; 649 Alchemy sheet rows |
| Chaos Orb | yes | 50, bins | wiki; 615 sheet rows |
| Exalted Orb and the influenced Exalted Orbs (ADR-0030) | yes | by the mods on the item before the craft: 1: 16, 2: 22, 3: 26, 4: 32, 5: 34 | wiki; 83 sheet rows. The note counts spends up to 38 against the table's largest ceiling of 34, so the sheet-fit research reads those rows by mod count and where a row shows a spend above the table's ceiling for the mod count read from its item text, the row's spend becomes the ceiling for that count |
| Essences | the random mods; the guaranteed mod is fixed | 80 | wiki spend table; the cut is the wiki's general sentence on "currency that replaces or adds mods", no test: `approximate` |
| Eldritch Chaos 60, Veiled Chaos 80 | yes | as named | wiki; each lands with its action (B5 follow-ups) |
| Awakener's Orb ([ADR-0032](0032-the-awakeners-orb.md)) | the rerolled mods | 100, on the receiver | wiki; the donor is destroyed, its count is gone |
| Foulborn Augmentation, Regal, Exalted (ADR-0043) | yes, with `+75` | 32; 48; the Exalted row times 62/34 | wiki; 491 sheet rows for the cut |
| Fossils and resonators, Harvest crafts, beast crafts (aspects, swaps, influence recipes), bench crafts and metamods, Veiled Exalted Orb | no | none | wiki: "not consumed by … resonators, Harvest crafting, Beastcrafting, or crafting benches" and the Veiled Exalted by name |
| Scouring, Annulment, Divine, Fracturing | no | none | not in the wiki's spend list: `approximate` |
| Vaal Orb (B4) | no | none; the brick keeps the count | [ADR-0037](0037-the-vaal-orb.md), wiki: the corrupted item keeps its memory strands |
| Tainted currencies | not offered | | out of B4 ([ADR-0036](0036-corruption-is-the-last-step.md)); a later batch declares them (wiki ceilings: Tainted Chaos 0-60, Tainted Exalted 6 mods 0-38) |
| Jeweller's, Fusing and Chromatic Orbs, the socket bench crafts and Omens, quality orbs and bench quality (B6, ADR-0045 to 0049), enchantments and the Tailoring Orb (B7, ADR-0050; its claim `enchantment.tailoring_orb_leaves_memory_strands`) | no | none | not in the spend list; the Tailoring Orb by claim: `approximate` |
| Blessed Orb, catalysts, Embers and Ichors, Orb of Conflict, Orb of Dominance, unveil | no | none | not in the spend list: `approximate` |
| Recombinator ([ADR-0033](0033-the-unpredictable-recombinator.md)) | no | none; the output takes the count of its base, which is either input with probability 1/2, so the donor's count enters the result | the author's play: recombination "doesn't interact with strands", he buys cheap stranded bases "to transfer to": `approximate` |
| Imprint restore ([ADR-0034](0034-imprints-from-beasts.md)) | no | none; restores the count | wiki: "restored with imprints" |
| Orb of Remembrance, Orb of Unravelling | see ADR-0043, ADR-0044 | | |
| The three bench rerolls ("reroll 3 random modifiers", "reroll a random modifier", "reroll the rarity") | not an action in B1 to B5 | 50 | their claim (`bench_craft`) says "spend up to 50" instead of "v1 items carry none" |

- **Why spend and cut go together.** The wiki ties the effect to the consumption: the craft "will deplete a random quantity of Memory Strands, and make it more likely to have outcomes of higher modifier tier". The first author adds a trade-site observation: "there are almost no results for items with memory strands and modifiers that would be prevented from rolling at that strand amount. The only listings would come from people rolling items using methods that don't interact with strands." Items that carry strands and mods the cut forbids come from methods that do not touch strands, so those methods do not cut. A fossil, a Harvest craft or a beast is therefore **not cut**, and an item with strands can be fossilled without the cut; this is an inference from that evidence, marked `approximate`.
- **Exalted at the Foulborn rate.** The Foulborn Exalted Orb's ceiling is published only at 5 mods (62; PoEDB lists one figure, 28 against its Exalted 16). The plan scales the Exalted row by 62/34, rounded: 29, 40, 47, 58, 62 for 1 to 5 mods. The first row agrees with PoEDB's 28 to one strand. `approximate`.
- **Unknowns and the in-game list.** Where an entry above is `approximate` and only the game can settle it, [#182](https://github.com/Rasslabsya4el/crafting-system/issues/182) lists an optional check. Craft of Exile's local copy models no strand craft (its data holds the two map mods that give strands; its only tier-cut code is the Genesis rating, which is where reading 3 of ADR-0042 comes from), so its emulator cannot answer these. The plan never waits for them.
- **Allflame crafting** with listed currency spends as the currency does (wiki), but Allflame crafting is out of v1 (inventory X-02).

## Hinekora's Lock

A lock previews a craft's spend exactly (wiki). It belongs to B8, not here.

Origin: [Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103) (draft decisions; the standing rule); [Research #98](https://github.com/Rasslabsya4el/crafting-system/issues/98); ADR-0004, ADR-0024, ADR-0028, ADR-0040.

## Amendment: what the claims say after the sheet fit ([#274](https://github.com/Rasslabsya4el/crafting-system/issues/274), research [#271](https://github.com/Rasslabsya4el/crafting-system/issues/271) and [#273](https://github.com/Rasslabsya4el/crafting-system/issues/273))

- **Every spend is a uniform whole number on 0 to its ceiling** (claim `memory_strands.spend_law_uniform`, `approximate`). The Chaos and Alchemy bins above came from counting the sheet's rows, not its crafts; counted as crafts both are uniform (p = 0.60 and 0.46). The "two currencies fail the test" paragraph and the word "bins" in the table no longer apply.
- **The Exalted ceilings by the mods before the craft are 16, 22, 26, 32, 34, 38 for 0 to 5 mods** (claim `memory_strands.spend_exalted_by_mod_count`): the wiki's row moved by one mod, because two sheet crafts exceeded 32 and 34. The **Foulborn Exalted** row is the emulator's, moved the same way: 46, 52, 56, 60, 62, 66 (claim `foulborn.exalted_spend_by_mod_count`, `approximate`); the scaling 29, 40, 47, 58, 62 is dropped.
- **Identification spends nothing** (claim `memory_strands.identification_spends_none`).
- The inference "fossils, Harvest and beasts do not cut; Scouring, Annulment and Divine keep the count" now has player reports and the emulator's code behind it (claims `fossil_harvest_not_cut`, `cut_follows_spend_table`, `annulment_keeps_strands`, `scouring_keeps_strands`, `divine_keeps_strands`), still `approximate`. A recombination neither cuts nor spends and its output takes either base's count (claims `recombination_neither_cuts_nor_spends`, `recombinator_strands_from_either_base`).
