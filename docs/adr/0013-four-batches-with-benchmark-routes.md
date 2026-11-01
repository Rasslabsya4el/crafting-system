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

## Amendment: B5 as grilled ([Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103), 2026-11-01)

The grill fixed what B5 contains; the designs are ADR-0040 to ADR-0044.

- **In B5**: the strand count on the item and the cut of tiers (ADR-0040); the declaration of cut and spend on every action (ADR-0041); the weight readings of the kept tiers as a rule axis (ADR-0042); the Orb of Remembrance, stranded purchases and the three Foulborn orbs (ADR-0043); the Orb of Unravelling, marked approximate (ADR-0044).
- **Not in B5**: the Genesis Tree and every other way of acquiring an item (owner: the final item does not differ, so a Genesis-born item is a start item); identification (admitted, unused); the three bench rerolls (no action, no route); Hinekora's Lock (B8); Allflame crafting.
- **Benchmarks**: none of R01 to R30 uses strands, and the map gave B5 none. B5 passes on (1) the published numbers as acceptance tests (the wiki's table, the 1,902 sheet rows, the Foulborn list, the 2,255 Remembrance results, the Unravelling samples, ADR-0040 and ADR-0044), and (2) given routes with strands: published 3.29 crafts that use them if the route-finding research ticket finds any, otherwise **test routes** that an agent writes (stranded variants of B1 routes, a Remembrance-then-craft base, an Unravelling finish) and evaluates at equal prices. The owner accepted this: the system must reproduce the evidence gathered as closely as possible; matching the real game beyond that is not required.
