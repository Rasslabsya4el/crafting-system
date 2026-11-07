# A bought start item whose mods the target does not name is the item the market sells: a draw of the orb that makes its rarity

Ticket [#640](https://github.com/Rasslabsya4el/crafting-system/issues/640), found by the review of PR #607 ([#576](https://github.com/Rasslabsya4el/crafting-system/issues/576)). Rules: OR-4, OR-6, OR-12, OR-17, OR-23, OR-26. Amends ADR-0008 (what `start_item` and `rarity` mean) and ADR-0043 (a start item is given or bought).

## The problem

R13 and R14 start from a bought Magic base, R08 and R09 from a bought Rare one. The target names none of its mods, and the planner held the item with **no mods**: "any mod or empty" (OR-17) read as empty. A Magic item in the game holds 1 or 2 mods, a Rare one 4 to 6, so the model's item did not exist, and the planner used it: both R13 and R14 opened with an Orb of Augmentation, legal only on a Magic item with 1 mod. The guides open with an Alteration (R13: "Alt spam for T1 Life and a resist"; R14: "Alteration roll a Hunter Thicket Bow"), which is the move that is legal on every Magic item.

## Decision: one rule for every bought start whose mods the target does not name

A bought start item is **the item the market sells**, a draw of the orb that makes its rarity:

| `start_item` of a bought start, with no mod listed | The mods it holds |
|---|---|
| Normal | none (as before) |
| Magic | what an Orb of Alteration leaves on that base: 1 or 2 mods, 1/2 each, from the base's pool at its game weights, the mods of the item's influences included |
| Rare | what an Orb of Alchemy leaves on that base: 4, 5 or 6 mods (8:3:1) |

The start price is the price of the listing, as before; a restart pays it again. The planner's first decision is made on each outcome of the draw, so an Augmentation is chosen only where the item holds 1 mod, and an Alteration (or whatever is cheapest) where it holds 2. The mods no requirement asks for are junk, counted and not told apart (OR-10), so the draw adds few states.

The rule is in `targets` (`start_item` and `rarity` in the docs of `targets/__init__.py`) and is read in one place, `actions.listing.unopened_listing`. A bought start item with a mod listed (a fractured mod: R03, R05, R10, R11, R12) names mods, so it is not drawn (the mods it does not list are a separate open point, ticket [#656](https://github.com/Rasslabsya4el/crafting-system/issues/656)); a given start item is a concrete item the player holds (OR-6), so it is not drawn either (J01).

## How it is modelled: a free first chance step, so no solver changes

Two ways looked possible:

1. a start distribution the plan supports: the plan starts in a distribution of states;
2. a free first chance step whose outcomes are the drawn states.

**Chosen: the second.** The solvers, the envelope bound and the route evaluators all hold a single start state, and the restart goes to it (`BuyStartItem`, `builder.kernel([0], [1])`). A distribution of starts would need a change in every one of them, and the restart would have to return to the distribution, not to a state. A chance step is what every solver already solves.

* The start state is the **unopened listing**: a Normal item with no mod and the flag `Item.unopened` (`Flags.unopened` in the compressed state). The restart returns to it.
* The one action that works there is `OpenListing` (`actions/listing.py`, `Action.opens_listing`): its result is exactly the result of the Orb of Alteration (Magic) or the Orb of Alchemy (Rare) on the listing opened, so the kernel, the pool at the base's weights and the junk of the abstraction are the ones those orbs already have. The abstraction refuses every other action on an unopened state and the draw on every other state (`Abstraction._prepare`), so the draw is not a free reroll and the unopened state is reached by the restart only.
* The draw is an offer of the plan with a label, so it is a step of the policy, of a given route (every route takes it first; `parse_route`), of the report and of the page. The page shows it like any step with chances, in player words.
* The draw costs `DRAW_COST_SHARE` (0.1) of the cheapest offer that costs something, not zero. The solver needs a positive cost on every action, and this one lies on every cycle of a restart: the certified error of a component is about (m + 2) * epsilon * value / g for its smallest constant term g (`solver/_certify.py`), and a cost of 1e-6 of the cheapest orb gave R13 an error of 8.7e-4, past the 1e-6 the solvers accept. At 0.1 it is about 1.3e-7, and a mean moves by 0.1 of the cheapest orb per draw (R13: 0.0016 Chaos of 6,568), inside the tolerance the solvers accept. The start price is the listing's, unchanged. Making the draw exactly free is ticket [#657](https://github.com/Rasslabsya4el/crafting-system/issues/657).

## What this changes

* R13, R14: from the Magic base with 1 or 2 mods; R08, R09: from a Rare with 4 to 6. Their means, first actions and state counts are in the PR of #640 and in the issue.
* The vendor-recipe starts name their mod (ADR-0059), the fractured starts too, and R04, R06 and V01 start from a Normal item: none of them is drawn.
* `Target.start_item` stays what the target says (the Magic belt with no mods); the plan's start is the unopened listing.
