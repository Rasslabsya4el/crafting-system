# The Vaal Orb: four equal outcomes, a weighted implicit pool, and a brick that is a dead end or a six-affix fill

The Vaal Orb corrupts an item and applies one of four outcomes ([research #92](https://github.com/Rasslabsya4el/crafting-system/issues/92), section 2.1). Its kernel follows ADR-0036: one chance `p` that the item ends as the goal, a dead end otherwise. [Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95) accepted the main chat's technical decisions below; the owner's answers only decided what is offered (ADR-0036).

## The four outcomes

Each has chance 1/4 ("Each outcome has an equal chance of occurring", wiki; Craft of Exile draws uniformly from a four-entry table; GGG staff statements of 2014 and 2015 that the wiki cites). Not marked `approximate`: the wiki and Craft of Exile's code agree, though no 3.29 count exists.

1. **A corrupted implicit.** One mod is drawn by weight from the pool below. It **replaces one implicit of the item, chosen uniformly among the item's implicits** (base and Eldritch ones alike); an item with no implicit gains it. Each stat of the mod rolls uniformly in its range, integers, independently. Explicit mods are not touched.
2. **A socket.** Since 3.29.0 one random white socket turns non-white (it changes nothing with no white socket). The state has no sockets until B6, so it is "nothing" for now and B6 gives it its effect.
3. **The brick.** The item becomes a rare of the same base with six random affixes and random sockets and links; it keeps enchantments, quality, memory strands and base values (wiki). Below.
4. **Nothing** (the item is only corrupted).

## The corrupted implicit pool

Datamined: repoe 3.29.3.3 `mods.json`, `generation_type: corrupted`, `domain: item` (jewels: `misc` and `abyss_jewel`). A mod's weight is that of the first spawn tag the item matches; the pool depends only on the item class. The gate on item level is the mod's `required_level` at most the item level (Craft of Exile cuts its corrupted mods the same way; the wiki: "from a pool dependent on the item's item category and item level"). Every mod is its own draw, so a family with three tiers (weights 1000, 1000 and 250 for Added Cold Damage on a ring) counts three times. Weights are 1000, 500, 250 or 200.

Pinned by tests on the real export: ring 39 mods, total weight 31,850; amulet 30 and 28,500; belt 19 and 18,500; jewel 21 and 21,000; abyss jewel 21 and 21,000; and every class of the research's table (section 4). Ring, amulet and belt are equal to Craft of Exile's data mod by mod (claim `corruption.implicit_pool_matches_coe`). A ring of item level 80 loses the three Added-damage tiers of level 81 to 83 (W = 31,100). The pools JSON of the research becomes a test fixture.

## The brick, in two cases (ADR-0036)

- **The target asks for a corrupted implicit.** A brick adds no corrupted implicit and nothing can act on its result, so **a brick never reaches the goal**: it is a dead end whatever the item held. The kernel needs nothing about what a brick does to fractured mods, locks or sockets, and the two sources that disagree about it (below) do not matter.
- **The target allows a corrupted item and asks for no corrupted implicit.** Then the brick can be the goal, and its chance is a draw, computed by the existing draw machinery (the same as the fill of repeated Exalted draws): a rare has at most three prefixes and three suffixes, so six affixes means **a full item**, three of each. Each side that is not locked is filled to full with ordinary draws (item level, family exclusion, weights, influence, the Attack and Caster blocks), and the chance that the result meets the target is summed over the compressed leaves. Fractured mods and sides locked by `Prefixes/Suffixes Cannot Be Changed` are kept and respected by default, as a Chaos Orb does: the wiki states that the brick "respects metamods", and keeping fractured mods is this project's inference from it (the wiki says nothing about them). The brick does not touch implicits, so an implicit requirement stands as the state had it. Craft of Exile's code reads otherwise (`metaprot = false`, `remfrac = true`: it removes fractured mods and ignores protection). That conflict is a recorded rule axis: the claim `corruption.vaal_brick_rare_six_mods` is marked `approximate` ("wiki: metamods respected, nothing on fractured mods; Craft of Exile: neither") and its second reading is the CoE one, shown as an interval once B3's rule-axis machinery (ADR-0032, ADR-0033) exists. A question to the owner's in-game list, [#182](https://github.com/Rasslabsya4el/crafting-system/issues/182), records it because the emulator cannot settle it (it is the other side of the conflict); the planner does not wait for it.

## Jewels

- **Pool**: 21 mods with weight 1000 for ordinary jewels and 21 for abyss jewels; four of each need item level 33, 40, 40 or 60. Cluster and Timeless jewels are refused (their pools are not checked, ADR-0004).
- **Outcomes** (wiki, four equal): a jewel corrupted implicit; a rare jewel of the same base; a corruption-exclusive unique jewel; nothing. Only the Cobalt, Crimson and Viridian bases have such a unique; on every other base that outcome has no effect and counts as **nothing** (so "nothing" has chance 1/2 there). A unique result is a **dead end** for this project (unique items are never a target, [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81)).
- **The rare jewel** is the brick. A jewel holds at most two prefixes and two suffixes, so a brick fills it to four mods. The wiki does not say how many; Craft of Exile rolls six and caps at the jewel's limit. The claim `corruption.jewel_brick_fills_to_limit` (source `coe`) is marked `approximate`; it is the best estimate from the evidence, and no in-game question is asked. For a target that asks for a corrupted implicit the brick is a dead end and the count does not matter.
- No action rerolls a jewel yet ([#201](https://github.com/Rasslabsya4el/crafting-system/issues/201)); until it lands a jewel target reaches the Vaal Orb from a bought jewel.

## When the Vaal Orb is refused

Corrupted, mirrored and unique items; classes with no pool in the table. (A target without the two keys of ADR-0036 never offers it, but that is the offer filter, not a refusal.) The Orb is accepted on normal, magic and rare items alike. Allflame crafting is not in v1 and refuses the Vaal Orb anyway (claim `corruption.vaal_incompatible_with_allflame`).

## What it declares

`Reads` names the implicits, and for the allowing case the fractured mods, the side locks, the influences and the item level; `Adds` says it corrupts and adds an implicit from the corrupted pool (ADR-0036), and that it erases the explicit mods only in the brick. Whether it can declare block invariance (ADR-0023) is decided by the contract suite's comparison of block members, as for any action; its answer is one number per state, so a failed comparison costs only speed.

Origin: [Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95); [Research #92](https://github.com/Rasslabsya4el/crafting-system/issues/92); ADR-0004, ADR-0023, ADR-0027, ADR-0028, ADR-0036.
