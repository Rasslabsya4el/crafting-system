# The unpredictable recombinator: pooled sides, a count table, and a weight exponent

[Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94) plans the Kingsmarch recombinator in **unpredictable mode only**; the predictable mode waits for a route that needs it (owner, answer 3). The rules are those of [the research](https://github.com/Rasslabsya4el/crafting-system/issues/90) (the wiki, the owner-trusted 3.25 guide and its 3.26 follow-ups), the selection exponent is the fit of [#175](https://github.com/Rasslabsya4el/crafting-system/issues/175). The cost is ADR-0035.

## The action

- **Inputs.** Two magic or rare equipment items of one item class, neither corrupted (3.26). **Jewels are refused** (owner, answer 4a: they do not go into the bench); idols are out of v1. Both inputs are destroyed, so the output is a new item and no imprint of an input restores it (ADR-0034). One input is the item in hand, the other a `Need` (ADR-0022); the kernel is symmetric.
- **The base.** Each input is the base of the output with probability 1/2. The output copies from the base its type, influences, anointments, enchantments, quality (catalysts too), implicits, sockets and links; Memory Strands stay with the base; the defence percentile is rerolled. Item level is `min(floor((A + B) / 2 + 2), max(A, B))`.
- **Pools.** The prefixes of both inputs form one pool, the suffixes another. The kept count of a side depends only on its pooled count (table below); the output holds at most the base's per-side capacity. A mod on both inputs enters its pool twice (**doubling**: more chance to be picked), and once one is picked its family is closed for the rest of the draw. The first side filled is chosen 1/2 each (measured in 3.25). One prefix on one input and one suffix on the other give 1p, 1s or 1p1s, a third each.
- **The count table** (percent kept, by pooled count; the guide, rows 3 and 4 renormalised): 1: none 41, one 59 · 2: one 67, two 33 · 3: one 39, two 52, three 10 · 4: one 11, two 59, three 31 · 5: two 43, three 57 · 6: two 28, three 72. The events behind each row (217 to 424) travel with the claim, so the sampling error (at most 3.4 points on a two-way row) can be stated; the wiki's rounding of the same table (66.7/33.3, 40/50/10, 10/60/30, 30/70) is kept as a second table for a sensitivity run. Both are marked `approximate` (player measurements, 3.25, "largely the same" in 3.26).

## Which mods are kept

After the count, mods are drawn from a side's pool one at a time, **without replacement, with chance proportional to `weight^alpha`**, closing the family of each pick. The weight is the mod's own spawn weight on the base; the data cannot tell the choice for two tiers of one family apart (#175), so the mod's own is used.

- **alpha = 1** is the plan: weight-proportional, inside both fitted intervals (gloves [0.36, 1.56], pooled [0.79, 1.76]), the rule the guide's author computes with.
- The interval of the answer runs over **alpha in [0.4, 1.6] on the grid 0.4, 0.7, 1.0, 1.3, 1.6** (ADR-0012, amended; ADR-0022). Alpha at or below 0 is excluded by the data; alpha above 1 is not.
- The claim is marked `approximate` with the reason: *fitted on 40 + 28 observations, weights 250 to 1500; weights below 250 extrapolated*. A route that targets a rare mod shows a wide interval (the research example: a weight-25 mod, 4.9% at the fitted exponent 0.92, 25% to 0.7% across the gloves interval); the answer shows it.

## Mods that do not follow the plain rule

- **Non-native mods** (influenced, attribute-bound or base-bound mods the chosen base cannot roll) count in the pool but cannot appear on the output; a fractured mod counts only if its own base is chosen.
- **Exclusive mods** (crafted, metacrafted, essence without a tier, beast aspects, veiled, delve, Breach, Incursion, elevated influenced): at most **one** stays on the output, and since 3.26 the exclusive mods of one side count **once** in its pool. The exclusive-mod trick of the 3.25 guide is dead, so **R26 is benchmarked without its exclusive padding**.
- **Ducats** add mods that can never transfer and pad the pool; Ducats are Allflame crafting, which the owner rules out ([inventory X-02](../research/2026-10-30-crafting-methods-inventory.md)), so **R27 is benchmarked without Ducat padding** and **R17 starts from a bought Talisman** with the wanted implicit.

## The rule axis

The Awakener's Orb (ADR-0032) and the recombinator are the actions that read a **rule axis**: the alpha grid has five readings, the group conflict two. A model's rule set is the product of the axes the enabled actions read: 5, 2 or 10 readings, each one ordinary model (ADR-0022). Nothing in the solver learns what an axis is.

## Not in B3

The predictable mode (its PoE 1 formula is unpublished); idols; the exclusive-mod and Ducat padding tricks; a Gold and Dust formula (ADR-0035).

Origin: [Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94) (round 1 answers 1, 3, 4a; "Selection rule after #175"); [Awakener's Orb, recombinators and imprints in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/90); [#175](https://github.com/Rasslabsya4el/crafting-system/issues/175); ADR-0012, ADR-0022, ADR-0028.
