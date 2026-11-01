# The Bloodstained Fossil never fails to add its implicit; the Locus of Corruption is in, at a double-implicit share of 25%

Two more ways to put a corrupted implicit on an item. Both follow ADR-0036 (the result is final) and draw from the pool of ADR-0037. [Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95) answers 4 and 5 decided the two points the sources leave open.

## The Bloodstained Fossil

A resonator with a Bloodstained Fossil rerolls the item as its other fossils say (the fossil kernel of [#61](https://github.com/Rasslabsya4el/crafting-system/issues/61) and [#62](https://github.com/Rasslabsya4el/crafting-system/issues/62)), **and** corrupts it, **and** adds one corrupted implicit "similar to the outcome of using a Vaal Orb" (wiki, since 3.16.0). The implicit is not affected by the other fossils. With a Gilded Fossil it replaces every implicit; otherwise it replaces one implicit chosen uniformly, as the Vaal Orb does.

- **It never fails to add the implicit** (owner, answer 5: as far as he knows it does not happen). The wiki's word "attempt" leaves room; the owner's knowledge decides it. A claim `corruption.bloodstained_never_fails` (source `owner`) is admitted, not marked `approximate`, and no in-game check is asked. The draw is the Vaal Orb's pool of ADR-0037, at the item's level.
- **The chance of the goal** is the product of two independent numbers: the chance that the fossil reroll leaves the explicit mods meeting every explicit requirement (the existing fossil kernel, summed over its goal leaves), and the chance that the implicit draw gives the wanted corrupted implicit and the kept implicits still meet their requirements. A resonator is a reroll, so it is offered from any rare item, not only from a finished one (ADR-0036).
- **It is offered only to a target that asks for a corrupted implicit** that the pool can give. For a target that merely allows a corrupted item it adds a price and an implicit nobody wants to a fossil set that exists without it, so it is never useful there. Sets that hold the Bloodstained Fossil are the existing fossil sets with one more member and the same twin and bound pruning (ADR-0031).
- The Bloodstained Fossil is priced like every fossil (the price file; the fossil prices are still the placeholders of [#118](https://github.com/Rasslabsya4el/crafting-system/issues/118)). `actions/fossil.py` stops refusing it with `OutOfScopeError`; the claim `fossils.bloodstained_is_corruption` is reworded to point here.

## The Locus of Corruption

The Corruption Altar of a tier 3 Incursion room (the Temple of Atzoatl) corrupts one uncorrupted item of any class the Vaal Orb takes (weapons, armour, jewellery, quivers, jewels) and applies one of four outcomes with chance 1/4 each (wiki; Craft of Exile's code agrees). **The owner put it in** (answer 4), against the recommendation to leave it out.

1. **Two corrupted implicits.** They replace implicits: an item with three or more loses two at random, with two loses both, with one loses it and the second is added (the order is Craft of Exile's: replace existing slots first, append the rest). The first is drawn by weight from the pool of ADR-0037. **The second is drawn from the pool without the mods that share a mod group with the first** (Craft of Exile's `modgroups` test; the wiki is silent). The claim `corruption.locus_second_implicit_other_group` (source `coe`) is marked `approximate`: it is the only support. The chance of two named mods A and B of different groups is `wA/W * wB/(W - gA) + wB/W * wA/(W - gB)`, with `gX` the total weight of X's group; the tests check it against enumeration.
2. **Every white socket turns non-white** (3.29.0). Nothing until B6 (ADR-0037).
3. **An influenced rare** of the same base with random affixes, respecting metamods (wiki); Craft of Exile gives it one random influence of the six when the base can carry one and then rerolls to a rare. For a target that asks for a corrupted implicit it is a dead end, as the Vaal Orb's brick. For a target that only allows a corrupted item it is a full-item fill with one random influence (marked `approximate`, `coe` only), handled as ADR-0037's brick.
4. **The item is destroyed**: a dead end, and the restart pays a new start item.

The altar has no Hinekora's Lock preview (3.23.0; claim `corruption.locus_no_preview`), which is moot because Hinekora's Lock on a corrupting action is B8.

### The double-implicit share: 25%, approximate

Sources disagree. The wiki and Craft of Exile say 1/4. One self-recorded player sheet (3.23, 52 runs of named unique items) counts 427 double corruptions in 1,612 items, 26.5% (95% interval 24.3% to 28.6%). Every other count found is far lower: 14 in about 160 tries, 8.8% (3.23 to 3.25; item type unique or not stated). Nobody counted rare items, and no 3.29 sample exists. The owner decided **25%, to be corrected later if evidence says otherwise** (answer 4).

- The claim `corruption.locus_two_implicit_share_decision` (source `owner`, value 0.25) is marked `approximate` with the reason "sources disagree: wiki, Craft of Exile and one sheet 25% to 26.5%; other counts 8.8%" and the interval 0.088 to 0.265. The earlier claim `corruption.locus_two_implicit_share_observed` stays as the evidence. The plan uses 0.25; the answer lists the share among its approximate inputs with the interval (ADR-0028, the form of ADR-0035), and prints the expected number of Locus uses of the policy, so that the spread can be read as that number scaled by 0.25 over the share: for a route that only repeats a try, 2.8 times as many uses at 8.8%. The in-game count (100 to 289 temple tries) is not asked of the owner; the evidence rule (ADR-0005) is: the best estimate stands until a source changes it.

### What a use costs

The Locus has no currency price. **A price-file entry "Locus of Corruption (use)", editable by the owner, default 0 Chaos** (the temple is not bought per use). The 1/4 destruction is modelled as the dead end it is, so a Locus try still pays the item it destroys, which the restart buys again. A target's `actions:` list (the key of the target file that names the kinds the planner may use, ADR-0024) can leave the Locus out for an owner who has no temple; the report names the entry and its default when a route uses the Locus.

### Against the Vaal Orb

For a ring of item level 83 or more and "+(14-16)% to all Elemental Resistances" (weight 1000 of 31,850): the Vaal Orb hits with chance 0.785% per orb, 127.4 orbs and 127.4 items per hit; the Locus hits with chance 1/4 times (3.14% + 3.60%) = 1.686% per use, 59.3 uses and 59.3 items per hit (ADR-0039). With an uncosted temple it is the cheaper route by default, which is the owner's decision made visible by the listed price and share. A target that asks for **two** corrupted implicits (of different groups) is reached only by the Locus; more than two, or two of one group, is an error when the file is read (ADR-0036).

Origin: [Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95) (owner answers 4 and 5); [Research #92](https://github.com/Rasslabsya4el/crafting-system/issues/92); ADR-0005, ADR-0024, ADR-0028, ADR-0031, ADR-0035, ADR-0036, ADR-0037.
