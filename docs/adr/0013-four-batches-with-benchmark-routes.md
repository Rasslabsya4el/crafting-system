# v1 comes in four batches, each with benchmark routes and its own grill

Every crafting method in scope is part of v1 (owner amendment to round 1 Q7), but it is built in batches, ordered so each needs only what the batch before it built: single-item actions before two-input ones, which need the branching solver. "v1 done" means every batch passes its benchmark routes.

- **B1, core actions**: Transmutation, Alteration, Augmentation, Regal, Alchemy, Chaos, Exalted, Annulment, Scouring, Divine; Essences; Fossils and resonators; the 3.29 Harvest reforges; bench crafts including the five metamods (`Prefixes Cannot Be Changed`, `Suffixes Cannot Be Changed`, `Cannot roll Attack Modifiers`, `Cannot roll Caster Modifiers`, `Can have up to 3 Crafted Modifiers`); Fracturing Orb; buy item. Benchmarks R04, R05, R08–R14.
- **B2, single-item additions**: Eldritch currency and Conflict (ADR-0002), influence Exalts, Dominance, Veiled Chaos / Veiled Exalted and unveil, single-item beasts (aspects, prefix/suffix swap), Blessed, catalysts. Benchmarks R02, R03, R06, R07, R20, R22, R23, R24, R30.
- **B3, two-input actions**: beast imprint, Awakener's Orb, recombinators (ADR-0012). Benchmarks R15–R19, R25–R29.
- **B4**: corruption and synthesis.

Pass rule: at equal prices the solver's route costs no more than the guide's, and published odds match; the old prototype's helmet and bow numbers are a "no more expensive than" bar. Guides state no cost, so the guide's cost is its **given route** (an agent writes the route down as a YAML file, a fixed policy) evaluated exactly with `risk.evaluate` at the same prices as the solver's route; the `benchmark` command records both, and the check on the solver's route is recorded, never a failing test. The benchmark routes are R01–R30 of the [reference routes research](../research/2026-10-30-5-reference-routes.md).

Batch-specific design (the Eldritch link, the branching solver, imprint as acquiring a copy, the recombinator interval computation) is grilled at the start of its batch, not before.

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q7, [Design grill round 2: data, batches, repo](https://github.com/Rasslabsya4el/crafting-system/issues/3) Q12, [Design grill round 3: modules, verification, process](https://github.com/Rasslabsya4el/crafting-system/issues/4) Q23.

## Consequences

- Every bench craft counts as unlocked (main chat, 2026-10-30, in [Owner decisions on B1 mechanics no source or Craft of Exile settles](https://github.com/Rasslabsya4el/crafting-system/issues/28)).
- Methods the owner added to v1 on 2026-10-30 without a batch yet (Orb of Chance; sockets, links and colours; Harvest crafts other than reforges; Rog; Runesmithing; Foulborn currencies, Memory Strands and Orb of Remembrance; Hinekora's Lock; Tainted currencies) get their batch from [Every crafting method in 3.29 and its batch](https://github.com/Rasslabsya4el/crafting-system/issues/29).
- Out of v1: Necropolis gravecrafting and the 3.29 league mechanic (owner, 2026-10-30).

## Amendment: B2 as grilled ([Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93), 2026-10-31)

The grill fixed what B2 contains; the designs are ADR-0025 to ADR-0030.

- **Added to B2**: Harvest add/remove and the resistance and damage swaps; the Wild Bristle Matron and the side-swap beasts; aspects; the Talisman single and double fractures; the beast influence recipes, modelled as that influence's Exalted Orb and marked unverified.
- **Not in B2**: Orb of Chance (no route uses it and the magic/rare split is unmeasured); it has no batch, so it stays out of v1 until one is charted.
- **Out of v1**: Eldritch implicits on amulets; Randomise Influence; the Talisman base reroll; start items with a signature or double veil; Tainted catalysts.
- **Route notes**: R20 starts from a bought base in B2 (the Awakener's Orb that makes its dual influence is B3). R07 is re-read in 3.29: the veiled Trigger mod has weight 0, so its route is the bench Trigger plus the unveiled minion speed. R05 gains its catalyst line (ADR-0029).

## Amendment: B3 as grilled ([Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94), 2026-11-01)

The grill fixed what B3 contains; the designs are ADR-0032 to ADR-0035, with ADR-0012 and ADR-0022 amended.

- **In B3**: the Awakener's Orb (ADR-0032); the **unpredictable** recombinator (ADR-0033); imprints from beasts (ADR-0034); the Dust and Gold cost (ADR-0035). The solver for two-input actions is ADR-0022.
- **Not in B3**: the predictable recombinator, which waits for a route that needs it.
- **Out of v1**: the Eternal Orb (Standard only); Ducats and the other Allflame crafts; jewels and idols in the recombinator; the exclusive-mod padding of the 3.25 guide (dead since 3.26).
- **Benchmarks**: R15, R17 to R19 and R25 to R29. R16 has no two-input step (Harvest only) and moves to B2's Harvest end to end ([#150](https://github.com/Rasslabsya4el/crafting-system/issues/150)). R17 starts from a bought Talisman with the wanted implicit. R18's Assassin's Mark text is checked against the 3.29 data. R26 is benchmarked without its exclusive-mod steps. R27 without Ducat padding. R29 without Hinekora's Lock (it waits for B8) and without the Runesmith enchant (historical).

