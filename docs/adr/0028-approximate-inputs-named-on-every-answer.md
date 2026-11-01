# Approximate inputs are named on every answer

B2 admits mechanics that no source settles beyond Craft of Exile's code or a fitted curve: the count an Eldritch Chaos Orb puts back, the odds of the Orb of Conflict, where a veil lands beside a lock, the odds of a Harvest add and remove. The evidence rule admits them ([#28](https://github.com/Rasslabsya4el/crafting-system/issues/28), ADR-0005), but an answer built on them is less sure than one built on the data, and the owner must see which. [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) decided how.

## The mark

A claim carries `approximate` (with a one-line reason) when **no other source settles it**: its only support is Craft of Exile's code or data, a fit to a sample, a wiki formula the owner has not checked, or a default the main chat chose for a point the sources leave open. A claim that Craft of Exile repeats but the wiki, the data, an official note or the owner also support is not marked. A claim may mark part of its range: the Conflict odds are `approximate` everywhere and `extrapolated` for `d` outside -2 to +3 (ADR-0025).

Every answer lists **the approximate claims that the actions of the policy read**: actions the policy can take, not every action in the catalog. The list is in the text report (a line "Approximate inputs", each with its claim id and reason), in the JSON (`approximate_inputs`, a list) and on the route page. An answer with no marked claim says nothing.

## Not the certified gap

This is not ADR-0023's approximate answer. The certified gap measures the error of the solver's merge **given the model**; an approximate input is an uncertainty **in the model**. They are independent: an exact answer (gap 0) can read an approximate claim, and an approximate answer can read none. The JSON keys differ (`approximate` with `lower`, `upper`, `gap` for ADR-0023; `approximate_inputs` here), and a report never joins the two into one percentage: nothing here is a bound.

Origin: [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) (decisions list); ADR-0005, ADR-0023.

## As built for the interval answer ([#221](https://github.com/Rasslabsya4el/crafting-system/issues/221))

`cli/_interval.py` words the result of the interval driver (`risk.solve_readings`, #220) and `cli/_report.py` and `cli/_route_view.py` print it; the shapes are fixed here, the planner that calls them waits for the recombinator to become a planner kind (#217).

- **The block** ("Plan and its interval" in the text, `interval` in the JSON, fields of the goal card on the route page, all from one list of facts): the axis in words and the grid; the plan and its cost at the plan reading; the cost interval of the plan over the **whole** grid with the reading of its cheapest and dearest point and one line a reading; the best route without recombinators beside it (none for an axis that has no comparison route, the Awakener's conflict); the route with the smallest worst case, named when it is not the plan; the certified bracket of that worst case, called a gap when it is open; the expected number of recombinations of the plan and what one costs; the Dust and Gold prices with their sources. Totals include the start item, like the policy's own. The block says the interval is the plan's cost at each reading and not a bound.
- **When it is absent.** A plan whose actions read no rule axis (`Offer.axes`) has no block, no `interval` key and no word about alpha, and its list of approximate inputs holds no recombinator claim. An axis the plan does not read is not named, and readings that differ only in such an axis are one row.
- **The approximate inputs** are the claims read by the actions of every route the block shows (the plan, the route with the smallest worst case, the route without recombinators), with the runs of donors followed through `extra_inputs`. Five claims carry their spread, in words and as `interval` in the JSON: the selection exponent (`plan` and `grid`), the count table of the guide and of the wiki (the largest difference between the two, in points of a row), and the three cost claims (`point`, `low`, `high`). A claim without a spread has the same two keys as before.
- **The expected number of recombinations** is `risk.expected_total(policy, start, is_goal, weight)`, the expected total of a weight over the executions of a fixed policy, the runs of its donors included (the visits of `evaluate`'s own chain, certified the same way). It is given at the plan reading. The cost rule alone is read off the same visits: the plan's mean with every combine at the low end and at the high end of `Recombinator.resource_bounds` (the route does not change; the influenced-input factor and the Gold of the junk mods have no interval).
