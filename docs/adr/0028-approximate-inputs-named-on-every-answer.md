# Approximate inputs are named on every answer

B2 admits mechanics that no source settles beyond Craft of Exile's code or a fitted curve: the count an Eldritch Chaos Orb puts back, the odds of the Orb of Conflict, where a veil lands beside a lock, the odds of a Harvest add and remove. The evidence rule admits them ([#28](https://github.com/Rasslabsya4el/crafting-system/issues/28), ADR-0005), but an answer built on them is less sure than one built on the data, and the owner must see which. [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) decided how.

## The mark

A claim carries `approximate` (with a one-line reason) when **no other source settles it**: its only support is Craft of Exile's code or data, a fit to a sample, a wiki formula the owner has not checked, or a default the main chat chose for a point the sources leave open. A claim that Craft of Exile repeats but the wiki, the data, an official note or the owner also support is not marked. A claim may mark part of its range: the Conflict odds are `approximate` everywhere and `extrapolated` for `d` outside -2 to +3 (ADR-0025).

Every answer lists **the approximate claims that the actions of the policy read**: actions the policy can take, not every action in the catalog. The list is in the text report (a line "Approximate inputs", each with its claim id and reason), in the JSON (`approximate_inputs`, a list) and on the route page. An answer with no marked claim says nothing.

## Not the certified gap

This is not ADR-0023's approximate answer. The certified gap measures the error of the solver's merge **given the model**; an approximate input is an uncertainty **in the model**. They are independent: an exact answer (gap 0) can read an approximate claim, and an approximate answer can read none. The JSON keys differ (`approximate` with `lower`, `upper`, `gap` for ADR-0023; `approximate_inputs` here), and a report never joins the two into one percentage: nothing here is a bound.

Origin: [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) (decisions list); ADR-0005, ADR-0023.
