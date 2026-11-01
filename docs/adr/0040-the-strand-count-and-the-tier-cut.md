# The item stores its Memory Strand count, and one strand or more cuts the tiers of a random draw

[Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103) designs the tier tilt: Memory Strands, the Foulborn orbs, the Orb of Remembrance and the Orb of Unravelling. The rules are those of [the research](https://github.com/Rasslabsya4el/crafting-system/issues/98) ([its note](../research/2026-10-31-memory-strands.md)); this ADR is the part every other one stands on: where the count lives and what it does to a draw. The owner's standing rule governs the whole batch: the system models everything known today, every unknown gets a best estimate marked `approximate` (ADR-0028), and no plan stops to ask for an in-game check.

## What the item stores

`Item.memory_strands`, an integer from 0 to 100, 0 by default. It is declared like the implicits of ADR-0027: `Reads` and `Adds` can name it, so the compressed state keeps it only when an enabled action reads it. An item built before B5 has 0 and behaves as it did.

- **A start item** carries it: the key `memory_strands: N` in the item YAML, and the pasted item text line `Memory Strands: N` is parsed. A Genesis-born item or any bought item that shows the line enters the same way (ADR-0043).
- **A target never asks for strands.** They are a tool, not a goal ([#81](https://github.com/Rasslabsya4el/crafting-system/issues/81), round 2 answer 10).
- **The count changes** by the spend of a craft (ADR-0041), by an Orb of Remembrance (ADR-0043), by an Orb of Unravelling (ADR-0044), by restoring an imprint ([ADR-0034](0034-imprints-from-beasts.md)) and by a recombination, whose output takes the count of its base ([ADR-0033](0033-the-unpredictable-recombinator.md), ADR-0041). Nothing else moves it.

## Strands are off unless the query has them

With no strands in the start item, a query leaves strands out: the Orb of Remembrance, the Foulborn orbs, the Orb of Unravelling and the stranded buy offers are not in the catalog, `s` stays 0 and **no answer of B1 to B4 changes by a bit**. The query turns them on with the setting `memory_strands = true` (`crafting.toml`, or `--strands`), and a start item with `s >= 1` turns them on by itself. The text report says in one line that strands were not considered, so the omission is never hidden.

Why a switch: the count can take up to 101 values (0 to 100 on a start item, 10 to 100 after a Remembrance), and it enters the exact state. A default of "always on" would multiply every B1 state space and push B1 benchmarks into approximate answers. This is the main chat's default, not an owner answer; flagged in the resolution of #103 for the main chat to confirm.

## The cut

An item with `s >= 1` strands sees, in every random mod draw that cuts (ADR-0041), only the highest tiers of each tier table. A tier does not depend on the item level (`items.tier_table`), so the cut counts what the draw can roll: `T` is the number of tiers of the mod type that pass the pool's level gate at the item's level (for an essence, the lower of the item level and the essence's cap) (Craft of Exile's own code counts only those too), and the draw keeps the `K` best of those, not tiers 1 to K of the table. With `T` such tiers the draw keeps

`K = floor(100 (T - 1) / D) + 1` top tiers, with `D = 100 + [s >= 1] (2.5 s + 47.5) + [Foulborn] 75`.

In integers, multiplying numerator and denominator by 2: `K = floor(200 (T - 1) / (200 + [s >= 1] (5 s + 95) + [Foulborn] 150)) + 1`. Never floats: at 8 tiers 81 strands is exactly 2.0 before the floor, so K is 3 and 82 strands gives 2.

- **0 strands, no Foulborn orb**: `D = 100`, K = T, no cut.
- **s >= 1**: `D = 2.5 s + 147.5`, the wiki's formula (`rollable_tiers`), checked against every cell of its breakpoint table and against all 1,902 usable rows of the first author's raw sheet: 0 rows below the bound, 814 exactly on it.
- **A Foulborn orb** adds 75 to `D` (the wiki: "+75 to the Modifier Tier Rating", the same as 30 strands). On a stranded item `D = 2.5 s + 222.5`; the author tested this on 491 Foulborn rows. **On a 0-strand item `D = 175`** (100 + 75), which gives exactly the wiki's list of kept tiers for N = 1 to 13 eligible: 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7. That case rests on the wiki alone (a private Discord test): `approximate`.
- **The cut uses the count before the craft.** The craft's own spend comes after (ADR-0041). The sheet has no row below the bound with the pre-spend count and the post-spend count would let weaker tiers through.
- **What the kept tiers weigh** is open and is its own rule axis (ADR-0042). The cut only says which tiers remain.

The cut touches draws of explicit mods. Implicits, fixed mods (an essence's guaranteed mod, a crafted mod, a fractured mod), and mods the bench picks are not drawn from a tier table by chance, so they are not cut. **Identification** is cut too in the game (a Scroll of Wisdom on a stranded item); the claim is admitted but unused, because the planner's items are identified and an unidentified buy is out of scope.

## The state

`s` is stored **exactly** in the compressed state: the spend depends on the exact count, so lumping counts into classes is not exact.

- **The pool signature** (the glossary) gains the cut class: the class of `s` and the Foulborn flag, which together fix the kept tiers of every table. For tables up to 13 tiers the cut takes 22 different values over 0 to 100 strands (28 up to 15 tiers; with a Foulborn orb 14 and 19), so the kernel cache grows by that factor and no more. The classes are `0 | 1 | 2-3 | 4-5 | 6-7 | 8-9 | 10-11 | 12-13 | 14 | 15-21 | 22-29 | 30-31 | 32-34 | 35-37 | 38-41 | 42-47 | 48-51 | 52-61 | 62-74 | 75-81 | 82-87 | 88-100` (for 13 tiers; the build computes them for the real tables).
- **The family types do not depend on `s`.** What a family gives the goal (its kinds, ADR-0009) is a property of its tiers; the cut changes only the weights of its draw, so only the pool signature sees it.
- **`s` rarely rises.** Only an Orb of Remembrance, an imprint restore and a recombination (the output takes its base's count, and the base is the donor half the time, [ADR-0033](0033-the-unpredictable-recombinator.md)) can raise it; every other action leaves it or lowers it, so a loop that spans several values of `s` must pass through one of those. The build ticket records the measured state growth on the sized B5 cases.
- **Past the time budget** the cut classes become the blocks of an ADR-0023 coarse state, each evaluated per member, with the certified gap of at most 1%. This extends the variants of [#172](https://github.com/Rasslabsya4el/crafting-system/issues/172) to actions that add mods.

## Buying a base with strands

A buy offer may name a strand count. The price comes from the trade API with the `memory_level` minimum filter (the slot already exists in `trade_query.py`), instant buyout (#133), cached in the price file (ADR-0007). The planner offers the counts at which a cut class begins for a table the target needs, usually two to four per query. Details in ADR-0043.

## What this replaces

- **ADR-0008**: "v1 start items carry no Memory Strands" is dropped for B5 (amendment there).
- **Claims**: `affix_pool.no_memory_strands` and `bench_craft.rerolls_not_b1_actions` (its quote repeats the sentence) are superseded through the claim history (#120). `NO_MEMORY_STRANDS` leaves `actions/pool.py`; the pool takes the item's count and the Foulborn flag instead. The 25 draft claims of the research on strands and Foulborn orbs become the rules registry's `memory_strands.yaml` and `foulborn.yaml`; the four Genesis Tree claims stay in the research folder (ADR-0043).

## Verification

Published numbers are acceptance tests (ADR-0019, layer 5): every cell of the wiki's breakpoint table, the 1,902 sheet rows as a committed fixture of numbers (strands before, currency, tiers, observed tier, lowest expected tier; the bound must equal the sheet's own column), the Foulborn list for N = 1 to 13. The kernel equals brute force with `s` on fixture items for every reading (layer 1). The simulator samples the cut, the spend and the Remembrance count from the claims, not from the kernel (layer 2).

Origin: [Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103) (round 1; the owner's standing rule); [Research #98](https://github.com/Rasslabsya4el/crafting-system/issues/98); ADR-0008, ADR-0009, ADR-0019, ADR-0023, ADR-0027, ADR-0028.

## Amendment: the claims and the setting are built ([#274](https://github.com/Rasslabsya4el/crafting-system/issues/274), 2026-11-01)

The strand and Foulborn claims are in the rules registry (`memory_strands.yaml`, `foulborn.yaml`); `affix_pool.no_memory_strands` and `bench_craft.rerolls_not_b1_actions` are rewritten with their old text in `history`. `Item.memory_strands` exists; the start item takes `memory_strands: N` or the pasted line `Memory Strands: N`; the setting is `[planner] memory_strands = true` in `crafting.toml` or `--strands`; the text report says `Memory Strands: not considered` under the start item when it is off. Until the cut and the spend are built (the next tickets of batch B5) a run with strands on is refused with a message instead of silently ignoring them. The research of [#271](https://github.com/Rasslabsya4el/crafting-system/issues/271) confirms the cut and the `+75` added to the strand denominator (the larger of two cuts is rejected) and finds four Battle Royale duplicate mods that the pool must leave out (claim `affix_pool.royale_duplicates_do_not_spawn`; the pool fix is the next ticket). The 0-strand Foulborn case (`D = 175`) stays `approximate`: the emulator rates the orb at 100.
