# Acquisition cost and multi-input actions exist from B1

The acquisition cost of an item in a given state (the cheaper of crafting it and buying it) is a first-class value from B1, and buying an item is an action, its first user. The action format allows several inputs from the start, so B3's two-input actions (beast imprint, Awakener's Orb, recombinators) arrive without changing the action format or the solver's interface. The branching (least fixed point) solver that two-input actions need arrives in B3.

Origin: [Design grill round 2: data, batches, repo](https://github.com/Rasslabsya4el/crafting-system/issues/3) Q13; "buying an item is an action" in [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2), "Settled before the grill"; [multi-item and recombinators research](../research/2026-10-30-3-multi-item-recombinators.md).
