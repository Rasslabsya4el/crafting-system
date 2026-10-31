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
