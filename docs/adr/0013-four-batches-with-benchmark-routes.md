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

## Amendment: B3 as grilled ([Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94), 2026-11-01)

The grill fixed what B3 contains; the designs are ADR-0032 to ADR-0035, with ADR-0012 and ADR-0022 amended.

- **In B3**: the Awakener's Orb (ADR-0032); the **unpredictable** recombinator (ADR-0033); imprints from beasts (ADR-0034); the Dust and Gold cost (ADR-0035). The solver for two-input actions is ADR-0022.
- **Not in B3**: the predictable recombinator, which waits for a route that needs it.
- **Out of v1**: the Eternal Orb (Standard only); Ducats and the other Allflame crafts; jewels in the recombinator; the exclusive-mod padding of the 3.25 guide (dead since 3.26).
- **Benchmarks**: R15, R17 to R19 and R25 to R29. R16 has no two-input step (Harvest only) and moves to B2's Harvest end to end ([#150](https://github.com/Rasslabsya4el/crafting-system/issues/150)). R17 starts from a bought Talisman with the wanted implicit. R18's Assassin's Mark text is checked against the 3.29 data. R26 is benchmarked without its exclusive-mod steps. R27 without Ducat padding. R29 without Hinekora's Lock (it waits for B8) and without the Runesmith enchant (historical).

## Amendment: B6 as grilled ([Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104), 2026-11-01)

The grill fixed what B6 contains; the designs are ADR-0045 to ADR-0049. Sockets, links and colours were among the methods added on 2026-10-30 without a batch; this is their batch.

- **In B6**: Jeweller's Orb, Orb of Fusing, Chromatic Orb, the 13 socket bench crafts, the Omens of the Jeweller, Connections and Trichromatism, Orb of Binding, the two Black Mórrígan recipes, Blacksmith's Whetstone and Armourer's Scrap.
- **Not in B6**: the Tainted socket orbs, bench crafts on corrupted items and Vaal or Locus colour outcomes (B4); Saqawine Rhoa and Vulture; jewellery sockets; items with an Abyssal-socket mod.
- **Benchmarks R31 to R33**, given routes written from guides (no route of R01 to R30 uses sockets): **R31**, a six-link body armour of item level 84 (Scraps to 20%, Jeweller's Orbs to six sockets, about 215, Orbs of Fusing to six links, about 1,000; the bench route is 350 plus 1,500); **R32**, a five-link body armour (about 36 Jeweller's Orbs to five or more sockets, then about 93 Orbs of Fusing on six sockets or 121 on five; the bench is 70 plus 150); **R33**, a four-link helmet of item level 84 with a red, green and blue socket (Fusing about 5 for four links, plain Chromatic Orbs about 78 for the three colours, the Omen of Trichromatism route one orb and the Omen).
- **Pass rule for B6** (on top of the one above; the comparison with the given route and the bench is recorded, never a failing test): the solver's route should cost no more than the given route at equal prices and no more than the bench route for the same count and links (the bench is a certain ceiling; it names no colours, so colours have none). The published numbers are checked as tests: the link tables of ADR-0047, the 8 aggregated cells of Siveran's data (the model inside the 95% interval of each), the 215 Jeweller's Orbs to six sockets, and Siveran's calculator as an oracle for Chromatic costs.

## Amendment: B4 as grilled ([Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95), 2026-11-01)

The grill fixed what B4 contains; the designs are ADR-0036 to ADR-0039.

- **B4 is corruption without synthesis.** Synthesis can no longer be crafted in 3.29 ([#29](https://github.com/Rasslabsya4el/crafting-system/issues/29)), so the "and synthesis" of the list above is dropped.
- **In B4**: the Vaal Orb, the Bloodstained Fossil and the Locus of Corruption (owner, answer 4: in, with a double-implicit share of 25%, approximate). A target may require a corrupted implicit (answer 1); a corrupting action is offered only for a target that asks for one or allows a corrupted item (answer 2). A corrupted item is final, so the corrupting actions are one chance of the goal each (ADR-0036).
- **Out of B4, no batch assigned**: Tainted Chaos, Exalted and Teardrop (answer 3: no published odds); they come back when a route or a measurement gives their odds.
- **Out of v1**: Tainted Oil (anointments are not targets); Merrick's Ducat (Allflame is out of scope).
- **From B6**: B6 (ADR-0045) hands B4 the Tainted socket orbs, the bench socket crafts on corrupted items and the Vaal and Locus socket outcomes. B4 takes them (ADR-0036, "Sockets"), built after B6's socket state; Tainted Chromatic is out with the other Tainted orbs whose odds are unmeasured. Hinekora's Lock on a corrupting action goes to B8.
- **Benchmark**: B4 has no R-route; none of R01 to R30 uses corruption. A finder looks for one or two published corruption methods to use as given routes; if there is none, the acceptance numbers of ADR-0039 are the bar for B4.

## Amendment: B8 as grilled ([Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106), 2026-11-01)

The grill fixed what B8 contains; the designs are ADR-0054 to ADR-0057.

- **B8 is built**, the last batch, although at the Lock's price (about 270 Divine on 2026-10-31) it rarely enters a plan: the planner takes it only where it saves more than it costs, and every plan prints a line about it (owner, answers 1 and 4).
- **In B8**: Hinekora's Lock as a `Peek` action (ADR-0054) with the previewable set of ADR-0055, which includes the Vaal Orb that B4 handed over (ADR-0036), and the burn and relock of ADR-0056. The previews of different currencies are independent (owner, from play).
- **Out of v1 for the Lock**: the Awakener's Orb as a preview option; a foreseeing start item; the beast, drop and card ways to a Lock; the Sacred Orb (no action).
- **Benchmarks**: R29 gets its Lock step back (ADR-0057). B3's R29 without the Lock stays as the baseline, and a synthetic target with a low Lock price shows the Lock appearing when it pays, and a corrupted-implicit target of B4 shows the Lock in front of the Vaal Orb. The pass rule is unchanged.
