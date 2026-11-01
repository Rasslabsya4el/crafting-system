# The Awakener's Orb merges one influenced mod of each input and rerolls the rest

[Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94) takes the Awakener's Orb as a two-input action (ADR-0022): the item in hand is the **receiver**, the **donor** is an input priced by its acquisition cost (ADR-0011), and the donor is destroyed. The rules are A1 to A12 of [the research](https://github.com/Rasslabsya4el/crafting-system/issues/90), as written; this ADR names what the planner does with them and the two points no source settles.

## The action

- **Inputs.** Two non-corrupted, non-mirrored items of one item class, each rare or magic with **exactly one influence**, the two influences different (A1 to A3). Item level 68 or more (Craft of Exile; an influenced item always has it, so the rule never bites). The research left the list for fractured and synthesised items open; the planner refuses them too, which costs nothing because in 3.29 neither can carry an influence.
- **The result** is a rare receiver with both influences. Base type, item level, sockets, links, quality and enchantments stay (A4). One influenced mod of each input is kept: the tier stays, the value is rerolled; if an input has several, the pair is drawn **uniformly among the valid pairs** (receiver mod, donor mod), valid meaning a different mod, and not one of the mod groups made mutually exclusive since 3.10 (A5, A9; such a pair is not drawn, it never reaches the conflict below). Two valid mods that share a mod group are drawn like any pair and reach the group conflict. The kept mods may be a prefix or a suffix.
- **The rest** is rerolled as a Chaos Orb rerolls a rare: a total of 4, 5 or 6 mods (8:3:1) **minus the kept mods that remain**, which count inside the total (owner, grill B3; with a group conflict one kept mod remains, so one is subtracted; the code of Craft of Exile is the reference and the build ticket checks it), drawn by the shared draw (item level, family exclusion, weights). The metamods (`Prefixes Cannot Be Changed` and the like) are ignored by the reforge (A8), so they do not protect anything; every mod that is not kept goes.
- **Cost** of an attempt: the orb's market price (A12; drop-restricted) plus the acquisition cost of the donor state. A retry pays both again (ADR-0022).
- **Imprint.** An imprint of the receiver made before the orb restores the receiver; the donor cannot be restored (A10).

## The two points no source settles

1. **Two kept mods of one group** (A6). The wiki says one is dropped at random, Craft of Exile keeps the receiver's, a 2020 player report lost the receiver's. The owner does not know ([grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94), answer 4c; it is on his list of in-game checks, [#182](https://github.com/Rasslabsya4el/crafting-system/issues/182)). The plan follows Craft of Exile: **the receiver's mod survives**, and the donor's influence is still added. The claim is marked `approximate` (ADR-0028) and the **other outcome, the donor's mod survives, is the interval**: the Awakener's Orb has a rule axis of two readings (ADR-0012, amended). A route that avoids the case by construction (R18 and R19 do) has no axis and no interval.
2. **Do the kept mods count inside the total** (A7). Only Craft of Exile says so; the owner chose it, which is a decision and not a check, so the claim is marked `approximate` (ADR-0028). No axis: the owner will not be asked again unless a route sits on the edge.

## What this changes

- The action is a two-input action of kind `awakener`; it needs the action contract to carry inputs (ADR-0024, "Limits").
- The donor is a `Need` whose wanted state holds the influence and the influenced mod the route wants carried over, and nothing else of the donor matters to the result: the compressed state of the donor is its influence and that mod, as a **want** that the acquisition meets at the first donor with that projection, whatever else it holds (ADR-0062).
- R18's Assassin's Mark text is checked against the 3.29 data before its target is written (owner, grill B3).

Origin: [Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94) (round 1, answers 4c and 4d; decisions list); [Awakener's Orb, recombinators and imprints in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/90); ADR-0011, ADR-0022, ADR-0028.
