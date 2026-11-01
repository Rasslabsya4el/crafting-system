# What the kept tiers weigh after a cut is a rule axis of three readings

ADR-0040 says which tiers remain. It does not say what the remaining tiers weigh, and the sources disagree. [Research #98](https://github.com/Rasslabsya4el/crafting-system/issues/98) found three readings, no test that separates them, and the point matters for every cut draw whenever the tier weights of a mod type differ. [Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103) applies the pattern of grill B3 (ADR-0033, "The rule axis"; ADR-0012 amended): plan on the best estimate, show the cost over every reading beside the best route without the mechanic. The owner had no new question here.

## The three readings

Take a mod type with four tiers, T1 to T4, weights 100, 200, 400, 800 (the wiki's example), and a cut that keeps T1 and T2.

| Reading | Rule | Kept weights | Total of the type | Who says it |
|---|---|---|---|---|
| **1. Redistribution** | the removed tiers' weight goes to the kept tiers of the same type, by their weights | 500, 1000 | 1500, unchanged | the in-game text of the Genesis passive (datamined): "distributing their roll chance among higher tier Modifiers of the same Modifier type" |
| **2. Refactored weight** | each kept weight times (tiers before) / (tiers kept) | 200, 400 | 600 | the wiki's Foulborn page |
| **3. Delete only** | the kept tiers keep their weights | 100, 200 | 300 | Craft of Exile's code (its redistribution branch is empty) |

The tier chosen inside the type is the same in all three (the kept weights stand in the same ratios). What differs is the **chance of the mod type against the other types** of its side: a Life prefix keeps its whole share under 1, loses most of it under 3. All three agree when the tier weights of a type are equal. They differ on the common mods whose lowest tiers carry most of the weight, which are the very mods a cut matters for.

## The plan and the axis

- **The plan reads reading 1**: it is the only first-party statement and the one the wiki's Modifier page describes as the in-game rule. It is marked `approximate` (ADR-0028), reason: *three readings in the sources, none tested; the plan takes the datamined in-game text*.
- **The axis** `tier_weights` has the three readings. A model's rule set is the product of the axes the enabled actions read (ADR-0033): this axis is read when the model has any cutting action (ADR-0041) on an item that can hold strands, or a Foulborn orb. Each reading is one ordinary model; nothing in the solver learns what an axis is.
- **The answer** shows the plan's cost, the cost interval over the three readings, the route with the smallest worst case when it differs, and **the best route without strands** beside them (ADR-0012 as amended). A route with no cut, or a cut on tiers of equal weight, has no interval.
- **The product has a ceiling.** The strand axes (three readings here, two for the Unravelling destination in ADR-0044) multiply with those of B3 (five for the recombinator's exponent, two for the Awakener's group conflict). Up to 24 readings are solved and cross-evaluated in full (ADR-0022: `k` solves, `k^2` evaluations). Beyond that, the axes are swept one at a time around the plan's readings, and the report says that the joint extremes are not covered. This ceiling is the main chat's default for the main chat to confirm; a stranded base with a recombinator (3 x 5 = 15) is inside it, and adding an Awakener's Orb or an Unravelling (30) goes past it.

## The pool signature

Under reading 1 a family's total weight is unchanged, so only the tier inside the family moves, and the family types of design D (ADR-0009) do not change. Under readings 2 and 3 the share of a family in its side changes too. In all three, the kernel reads the cut class (ADR-0040) through the **pool signature**; the build does not need a second mechanism, only the weights computed by the reading. The kept-tier tables are cached by cut class and reading.

## The evidence that could still collapse it

The first author's raw sheet holds, for every craft, the item text before and after and the strand count, so the draw frequency of a mod type under a cut can be compared with each reading once the pool weights are taken from our data. That analysis is a research ticket of the B5 chart (the sheet fit); if it settles the point, the axis collapses to one reading by a claim change, and the answers lose their interval. It is evidence already gathered, not an in-game check, and the plan does not wait for it: the three readings above are the model today.

Origin: [Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103) (draft decisions; the standing rule); [Research #98](https://github.com/Rasslabsya4el/crafting-system/issues/98) (section "Modifier Tier Rating and the weights of the kept tiers"); ADR-0009, ADR-0012, ADR-0022, ADR-0028, ADR-0033, ADR-0040, ADR-0041.
