# The extra crafted slot is a base that already has it

"Can have 1 additional Crafted Modifier" exists once in each pool (required level 80, stat `local_can_have_additional_crafted_mods`; claim `enchantment.crafted_slot_enchant`). It lets an item hold two bench-crafted mods instead of one, takes no affix slot, does not lift the six-mod limit (claims `enchantment.crafted_slot_allows_two_crafts`, `enchantment.crafted_slot_takes_no_affix_slot`, `enchantment.crafted_slot_enchant_allows_several_bench_crafts`). It is the most valuable result of the two orbs, and the one that changes other actions. [Grill B7](https://github.com/Rasslabsya4el/crafting-system/issues/105) (answer 2) decided how the planner reaches it.

## Only by buying a base that has it

Players disagree on whether the orb can roll it at all: reports of 600 to 1,000 clicks without a hit and "drop only", against streamer hits and one first-hand Tailoring hit on a unique base. The Curio sample shows it on 0.83% of enchanted armour and 0.48% of enchanted weapons (the 3.29 pool), but that is the rate on items found in Curio Displays, **not an orb chance**. The claim `enchantment.extra_crafted_modifier_curio_display_rate` keeps `orb_probability: null`, and no action treats the Curio rate as one.

The planner therefore reaches the enchant **only as a start item that already holds it**: a bought base, priced from the trade like any bought start item (ADR-0011). It never plans clicks for it. This follows the evidence as it stands: the sources contradict each other on whether the orb rolls it, so no orb rule is admitted (ADR-0004), and the drop-only route has a market price, which is a fact.

- A target that lists the extra crafted slot in `enchantment: {any_of: [...]}` is **satisfied by the start item** if it holds it, at no finish cost. If the start item lacks it, the target is refused with the message: "this enchantment cannot be reached by clicking orbs; give a start item that already has it, with its price".
- Because it is bought, it falls under ADR-0011's acquisition cost: a route that restarts buys another base with the enchant, and the start item's price is the price of such a base.

## What it changes in other actions

The limit counts crafted mods **held**, the multimod counted as one (claim `metamods.multimod_raises_crafted_limit`: three with the multimod, so itself and two crafts). With the extra slot it is **2** (two crafts); with neither it is 1; with the multimod 3. The enchant is a constant of the problem: no action of B1 to B4 adds or removes it, so it is not in the compressed state (ADR-0050), and `crafted_limit(data, item)` cannot read it from the item the search is at. The build ticket carries the start item's enchant as a problem-level constant to the two places that compute the limit: `crafted_limit` in `actions/metamods.py` (used per item by `bench.py` and `beast_mods.py`) and the limit in `abstraction/_estimate.py`, which today derives it from the state's metamods.

## Stacking with the multimod

Whether the extra slot and the multimod add (a fourth craft) is not answered by any source: the thread's poster combined them and three crafts were made, nobody states a fourth. The planner's rule, a default chosen under the standing rule of the grill and marked `approximate` (ADR-0028): **the limit is the larger of the two held-counts, never their sum**, so with both it is 3 (the multimod and two crafts); the sum would be a fourth held mod, three crafts. The claim is `enchantment.crafted_slot_with_multimod_takes_the_larger`, admitted by the build ticket. The enchant therefore adds no craft next to the multimod; what it buys is two crafts **without** the multimod's affix slot. The repo's copy of the Craft of Exile data has no enchant mechanic, so the emulator ([#198](https://github.com/Rasslabsya4el/crafting-system/issues/198)) is asked first; where it cannot answer, the question is on the in-game list [#182](https://github.com/Rasslabsya4el/crafting-system/issues/182). The plan does not wait for an answer.

## Rejected

- **Planning clicks at the Curio rate** (grill option b): about 120 Tailoring Orbs on armour or 208 Tempering Orbs on a weapon, which is hundreds of Divine, for an enchant the orb may never give. A plan could send the owner to spend them in vain.
- **No use of the enchant at all** (option c): a bought base with it is a real, priced route.
- **The sum of the two limits** (three crafts beside the multimod): no source supports it, and a limit too high produces a plan that cannot be crafted.

Origin: [Grill B7](https://github.com/Rasslabsya4el/crafting-system/issues/105) (round 1, answer 2); [the research #100](https://github.com/Rasslabsya4el/crafting-system/issues/100) (ENC-10, sections 3.4 and 3.5); ADR-0004, ADR-0011, ADR-0028, ADR-0050.
