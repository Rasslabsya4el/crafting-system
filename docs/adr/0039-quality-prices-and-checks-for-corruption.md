# Catalysts go on before a corrupting action, the prices are named, and B4 is checked on its own numbers

The loose ends of [Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95): how a catalyst quality target meets a corrupted implicit (ADR-0029 amended), where each price comes from, and how B4 is verified when no reference route uses corruption.

## Catalysts come first, and cost per try

A corrupted item cannot take an ordinary catalyst (a Tainted Catalyst is out, ADR-0013), and the quality survives corruption (wiki: the brick "will retain all of its other properties, including ... quality"; the other three outcomes do not touch it). So for a target with a `quality:` requirement and a corrupted implicit, the quality is finished **before** the corrupting action (ADR-0036 offers a Vaal Orb or a Locus only from a state where it already passes).

ADR-0029 charges the finish cost on the goal state. For these targets the cost moves to the corrupting action: **each use of a Vaal Orb, a Locus or a Bloodstained resonator pays the expected catalysts for the target quality at the item level, once**, because the corrupted result is final and every try uses a new item that had its own catalysts. Every restart pays it again, which is why the cost of a quality-bearing corrupted target is dominated by the number of tries. A target without a corrupted implicit keeps ADR-0029 as written.

The quality and the roll meet in one place. A requirement on a corrupted implicit's value is a base roll (ADR-0027), and a catalyst of the matching type scales the displayed value by `(100 + quality) / 100`, rounded down (ADR-0029, a wiki formula already marked `approximate`). The catalysts stop at the first quality at or above the target, and the last catalyst can pass it (a gain is `floor(f)` or one more). The chance `p` of a corrupting action therefore **averages the base-roll threshold over the exact distribution of the realized quality**, computed from the same gain rule, instead of using the target percent alone. A corrupted implicit whose tags the quality type does not scale is not scaled.

## Where each price comes from

- **The Vaal Orb**: the currency prices of the price file (ADR-0007), like any orb.
- **The Bloodstained Fossil**: priced as every fossil (the placeholders of [#118](https://github.com/Rasslabsya4el/crafting-system/issues/118) until the real ones land).
- **The Locus of Corruption**: a price-file entry "Locus of Corruption (use)", owner-editable, default 0 Chaos (ADR-0038).
- **A bought corrupted item**: a buy spec with `corrupted: true` and an implicit (ADR-0036). Nothing new in the price file.

## How B4 is verified (ADR-0019)

1. **Layer 1.** The kernel of each corrupting action equals brute-force enumeration over concrete items, in exact fractions: for the Vaal Orb every pool implicit and every implicit it can replace; for the Bloodstained Fossil the fossil kernel times the implicit draw; for the Locus every ordered pair of pool mods with its group exclusion and every replaced pair; for the allowing case the six-affix fill. On fixtures, a brick merges into one dead state for a target that asks for a corrupted implicit, and the enumeration proves the merge exact.
2. **Layer 2.** The simulator samples the three actions from the registry claims (the four outcomes, the pool, the replacement rule, the Locus share), not from the kernel code. The mean over many runs lies within five standard errors of the solver's value.
3. **Layer 3.** The solver matches the LP and brute force on a toy of "craft, corrupt, restart on a miss".
4. **Pools are pinned on the real export** (ADR-0037), and the Craft of Exile comparison of ring, amulet and belt joins the local Craft of Exile comparisons (the emulator tool of [#198](https://github.com/Rasslabsya4el/crafting-system/issues/198) checks the draws when it can).
5. **Acceptance numbers** (no reference route uses corruption, so these stand in for layer 5; computed from the research's pool for a ring of item level 83 or more, W = 31,850):

| Target | Vaal Orb | Locus (25% share, CoE's group rule) |
|---|---|---|
| "+(14-16)% to all Elemental Resistances" (weight 1000) | 1000 / 31,850 / 4 = 0.785% per orb, 127.4 orbs and items per hit | 1.686% per use, 59.3 uses |
| "+1 to Maximum Frenzy Charges" (weight 200, level 75) | 0.157%, 637 | 0.341%, 293 |
| all-resistances and chaos-resistance together | out of reach (one implicit) | 0.0252%, 3,962 |
| all-resistances, ring of item level 80 (W = 31,100) | 0.804%, 124.4 | 1.731%, 57.8 |

The first row is the headline: a quarter of the orbs give an implicit and 3.14% of those give the wanted one, so a ring with the wanted implicit costs about 127 rings and 127 orbs, and buying a finished corrupted ring may be cheaper than crafting one, which is why the buy spec exists (ADR-0036). The third row is an error when the file is read if the Locus is left out of the target's `actions:` (ADR-0036).

## The benchmark

B4 has no R-route. A `finder` looks for one or two published corruption methods (Vaal Orbs on bought rare jewels, Bloodstained crafting) and an agent writes them down as given routes (ADR-0013); the owner writes none. If none is found, the acceptance numbers above are the bar for B4, and ADR-0013 says so. The owner's in-game list ([#182](https://github.com/Rasslabsya4el/crafting-system/issues/182)) holds one B4 entry: the Vaal brick on a fractured and locked item (ADR-0037). Nothing in B4 waits for it.

Origin: [Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95); [Research #92](https://github.com/Rasslabsya4el/crafting-system/issues/92); ADR-0007, ADR-0013, ADR-0019, ADR-0027, ADR-0029, ADR-0036, ADR-0037, ADR-0038.
