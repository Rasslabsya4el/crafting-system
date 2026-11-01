# Corruption is the last step: a corrupted item is final, and the target says when it wants one

A corrupted item takes no ordinary currency and no mod craft; only Tainted currency and the bench socket crafts touch it ([wiki "Corrupted"](https://www.poewiki.net/wiki/Corrupted#Mechanics), claim `corruption.corrupted_modifiable_exceptions`). B4 offers neither, so in B4 **every corrupted item is final**: it is the goal, or a dead end. [Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95) took the rules of [the research](https://github.com/Rasslabsya4el/crafting-system/issues/92) and the owner's answers of 2026-11-01. The Vaal Orb is ADR-0037, the Bloodstained Fossil and the Locus of Corruption are ADR-0038, prices, quality and verification are ADR-0039.

## What B4 contains

- **The Vaal Orb** (equipment, jewellery, quivers, jewels), **the Bloodstained Fossil** and **the Locus of Corruption** (owner, answer 4: in, against the main chat's recommendation).
- **Out of B4** (owner, answer 3 for the first three): Tainted Chaos Orb, Tainted Exalted Orb and Tainted Divine Teardrop (no source publishes their odds, so no route could be exact); Tainted Jeweller's, Fusing, Chromatic and the bench's socket crafts on corrupted items (they need sockets in the state, so they go to B6, [#104](https://github.com/Rasslabsya4el/crafting-system/issues/104)); Tainted Oil (anointments are not targets, [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81)); Merrick's Ducat (Allflame is out); Tainted Catalyst, Armourer's Scrap and Whetstone (already out in B2, ADR-0013); Hinekora's Lock on a corrupting action (B8, [#106](https://github.com/Rasslabsya4el/crafting-system/issues/106)); synthesis (it can no longer be crafted in 3.29, [#29](https://github.com/Rasslabsya4el/crafting-system/issues/29)).
- **Admitted rules**: the research's 27 draft claims (`corruption.yaml` 17, `tainted.yaml` 10) as written, with the edits and additions named in ADR-0037 (the brick claim marked `approximate`; a new `approximate` claim for the jewel brick's affix count) and ADR-0038 (two `owner` claims: the Bloodstained Fossil never fails, the Locus's double-implicit share). No action reads the Tainted claims; they stay so that the registry says why those currencies are not offered (ADR-0004: what no admitted rule answers is invisible to the solver). Single-player edge reports (Tainted Exalted at 6 mods and at 1 mod, a Syndicate Tainted Exalted craft) stay open points, not claims.

## A corrupted item is final

A corrupting action (the Vaal Orb, a Bloodstained resonator, the Locus) turns every outcome into a corrupted item or no item. Nothing later can change a corrupted item, so each outcome is already decided: the item meets the target (**goal**) or it does not (**dead end**, and the plan restarts from the start item as ADR-0011 and the existing `restart` do). Consequences for the design:

- The kernel of a corrupting action has **no continuing state**. It is one number per state: the chance `p` that the outcome is a goal. The action costs its resources, reaches the goal with `p` and a dead end with `1 - p`. The compressed state gets no corrupted shape, no corrupted-implicit status and no new field; it needs only what the target needs to judge the outcome (the explicit requirements met or not, the fractured mods, the side locks, the influences, the item level).
- A corrupted item that is **a start item** (a bought corrupted item, ADR-0011's buy action) is already final: goal or an impossible target.
- The prototype's idea of "imprint, Vaal, restore" is not a route (ADR-0034 refuses imprints on corrupted items).

## What a target says (owner, answers 1 and 2)

A target may require a corrupted implicit (answer 1). **A corrupting action is offered only when the target asks for a corrupted implicit or allows a corrupted item** (answer 2); an item never arrives corrupted unasked.

- **`corrupted: true` on an `implicits:` entry** (ADR-0027). The entry's selector (family, `stat`, `mod`, `min_roll`) is resolved **among the corrupted mods of the base's item class that can occur at the target's item level** (ADR-0037's pool), and only among them. Without the key a selector never sees corrupted mods, so "all Elemental Resistances" on a Prismatic Ring's own implicit and on a corrupted ring stay two different requirements. A target with such an entry asks for a corrupted item.
- **`allow_corrupted: true`**, a key of the target file. It lets the goal be a corrupted item that has no corrupted implicit. The only corrupting outcome that can then help is the brick (ADR-0037). A target without either key can never be met by a corrupted item: `Target.is_met_by` is false for a corrupted item unless the target asks or allows, and a corrupted start item under such a target is rejected when the file is read.
- **Impossible targets are errors when the file is read** (as [#141](https://github.com/Rasslabsya4el/crafting-system/issues/141) already does for impossible targets): a corrupted implicit that no mod of the class has at that item level; more corrupted implicits than the corrupting kinds the target allows can give (one for the Vaal Orb and the Bloodstained resonator, two for the Locus; the target file's `actions:` key narrows the kinds, so a target that asks for a corrupted implicit and leaves out every corrupting kind has none); two corrupted implicits of one mod group when the Locus would draw them (ADR-0038). These errors do not apply when the target buys its item: a buy spec that names the corrupted implicits supplies them, and a start item that already holds them is final (above); more implicit requirements in all than the item holds after the corrupting action (a base implicit asked together with a corrupted one on a one-implicit base, since the corrupted implicit replaces the base's). The message names the cause and the nearest valid mod.
- **A quality** requirement of the target is finished **before** the corrupting action (ADR-0039).

## When a corrupting action is offered

A corrupting action carries its `Adds` declaration (ADR-0024): it corrupts, and it adds an implicit drawn from the corrupted pool of the class (the extension of #142's declarations). The planner's offer filter (the #60 rule, ADR-0024) keeps it only if the target asks for a corrupted implicit that the pool can give, or allows a corrupted item; for every other target the action is absent from the offers and the plan, and the report says nothing about it.

For a target that **asks** for a corrupted implicit, the Vaal Orb and the Locus are offered **only from a state in which every other requirement already passes** (explicit mods and the other implicits; the quality is not in the state but paid on each try, ADR-0039). This is an exact pruning in the sense of ADR-0031: the outcome is final, so an outcome of a state with an unmet requirement can never be a goal (the brick is a dead end for such a target, ADR-0037), and the offer would only add a dead end that a restart reaches cheaper. The Bloodstained resonator is not pruned this way: it rerolls the explicit mods itself (ADR-0038). For a target that **allows** a corrupted item without asking for an implicit, the Vaal Orb and the Locus are offered at any state, because the brick can end in the goal.

## Buying

A buy spec may name a corrupted implicit (`corrupted: true` already exists in the trade query, `prices/trade_query.py`). The planner then compares "craft, corrupt, restart on a miss" with buying a finished corrupted item. It matters: one Vaal Orb gives a ring with "all Elemental Resistances" with chance 0.78% (ADR-0039), so on average 127 rings and 127 orbs for one hit.

## Not in this ADR

How the outcome chance `p` is computed (ADR-0037, ADR-0038), what the Locus costs (ADR-0038), the catalysts and the prices (ADR-0039). The jewel gap (jewels cannot be rerolled by any action yet) is [#201](https://github.com/Rasslabsya4el/crafting-system/issues/201); until it lands a jewel target reaches a corrupting action from a bought jewel.

Origin: [Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95) (owner answers 1 to 5, 2026-11-01); [Corruption and Tainted currencies in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/92); ADR-0004, ADR-0011, ADR-0013, ADR-0024, ADR-0027, ADR-0031.
