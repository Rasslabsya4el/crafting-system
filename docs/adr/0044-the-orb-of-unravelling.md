# The Orb of Unravelling spends all strands to raise explicit mods in place, at a fitted chance and a two-reading destination

The Orb of Unravelling is the one action that turns strands into better tiers at the end of a craft instead of at each draw. [Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103) (round 1, answer 1): **it is in the plans, marked approximate.** Its odds are one player's fit on 9,373 orbs; its other rules are on the wiki. The sources are [research #98](https://github.com/Rasslabsya4el/crafting-system/issues/98) (the wiki page, the post and its sheet, the community calculator).

## The action

- **Inputs.** An identified item, not corrupted or mirrored, with `s >= 1` and at least one eligible mod (below). Planner items are identified; an unidentified item is refused, as the 3.26.0d fix made it in the game. It is a single-item action, offered only when the query has strands on (ADR-0040).
- **Result.** The count becomes **0**. Each eligible mod is tried **on its own**, with the chance below; several mods can rise in one use, and none may ("it is possible to consume all memory strands without upgrading any"). Having other upgradable mods does not hurt a mod's chance; "other T1 affixes do not affect the chance" (wiki).
- **Eligible mods.** Explicit mods that are not at the top of their tier table, with the exceptions of the wiki: a **crafted** mod is never raised into a regular one (3.26.0d), and an **influenced** mod is never raised into its Elevated form (its higher tiers are the regular ones of its own table). The metamods `Prefixes/Suffixes cannot be changed` are **ignored**: a protected mod can rise. Implicits and Eldritch implicits are not touched, and neither are veiled mods, whose tier is unknown until they are unveiled (`approximate`). **Fractured mods are excluded** (the game never changes a fractured mod, and no source says Unravelling is an exception): `approximate`, in the claim that the build ticket writes (the research has none for it).
- **Price.** The orb's price from the price file (ADR-0007). The action is not offered without one.

## The chance of one mod

`p = min(1, s * W_up / (2 * W_side))`

- `W_up` is the sum of the weights of the regular tiers above the mod in its table that pass the pool's level gate at the item's level; `W_side` is the total spawn weight of the **whole side pool** (prefixes or suffixes) of the base at its item level with the item's influence tags, whatever mods the item holds (the post's own examples; the 0.5 weight of attack mods on wands is included, `affix_pool.generation_weight_multiplier`).
- The count changes only the chance, not how many tiers a mod climbs.
- **Evidence:** 36,598 mods on 9,373 orbs, no mod the formula calls guaranteed failed to rise; T9 attribute mods on amulets at 32 strands rose 310 of 310, at 31 strands 14 of 15 (99% predicted); at 15 strands 63 of 150 rose (42%), the formula says 47.9% (1.4 standard errors); the correlation of predicted chance and outcome is 0.796. The author is "not 100% confident the chance scales linearly, but confident in the breakpoints where the chance is guaranteed".
- The claim is `approximate` with that reason. The plan uses the formula. The sheet-fit research ticket of the B5 chart is told to fit the curve below the breakpoint on the public "Unravelling data" tab (about two million lines, with the chance and weights per mod); a better curve replaces the formula through the claim history. It is evidence in hand, not an in-game check.

## The destination

A mod that rises goes to one of its higher tiers, drawn by weight times a multiplier. Two readings; they agree when the tier weights are equal and differ when they are not:

| Reading | Weight of an upper tier | Wand test (T4 lightning damage to spells; weights T4 800, T3 800, T2 250, T1 60; final tier 1, 2, 3) |
|---|---|---|
| **A. Rank multipliers** (the plan) | the tier's weight times 1 for the highest tier, 2 for the second, 3 for the third … | 2.03 / 16.89 / 81.08% predicted; observed 2.72 / 16.73 / 80.54% on 257 cases (chi-square 0.62) |
| **B. Cumulative** | the tier's own weight plus the weights of the tiers above it | 4.05 / 20.95 / 75.0% predicted (chi-square 4.3, p = 0.12) |

The archive copy of the post and the community calculator ([unravel.port8080.sh](https://unravel.port8080.sh/)) say A; a later edit of the post, known only from the earlier note, says B. Both survive the wand data, A fits better, and on equal weights the tests (T9: 1,611 cases, p = 0.86; T4: 3,825 cases, p = 0.48) cannot tell them apart. The destination is **not cut** by the item's strands (the number of tiers climbed does not depend on them). The two readings are the rule axis `unravel_destination` (ADR-0042, ADR-0033); the answer shows the cost over both beside the best route without strands.

## What it asks of the code

An Unravelling changes the tier of a mod **in place**, the limit of ADR-0024 that [#71](https://github.com/Rasslabsya4el/crafting-system/issues/71) lifts for values (a Divine Orb). The kernel is a product over the eligible mods; each mod either stays or moves to a higher tier of its own table, so the compressed state must tell the tiers of a mod type apart wherever a requirement names a tier. A new part of the action's components (as #71's rerolled part) carries the changed mods; the build waits for #71's machinery and does not redesign it. Layer 1 (ADR-0019) enumerates the finished items on fixtures.

## Tests that are published numbers (layer 5)

310 of 310 at 32 strands for the T9 amulet case (the formula gives `p = 1` there, and `p = 1` wherever `s * W_up >= 2 * W_side`); 14 of 15 at 31 strands within the formula's 99%; the wand case 2.03 / 16.89 / 81.08% under A and 4.05 / 20.95 / 75.0% under B.

Origin: [Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103) (round 1 answer 1); [Research #98](https://github.com/Rasslabsya4el/crafting-system/issues/98); ADR-0019, ADR-0024, ADR-0028, ADR-0033, ADR-0040, ADR-0041, ADR-0042.
