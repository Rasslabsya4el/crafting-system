# The enchant pools are weighted by the players' sample, marked approximate

GGG publishes no weights for the Tempering Orb or the Tailoring Orb, and the dump has empty `spawn_weights` for all 256 Heist enchant mods. Players counted them. The owner decided ([grill B7](https://github.com/Rasslabsya4el/crafting-system/issues/105), answer 1) that the planner uses the players' sample, marks the answer approximate and buys no measurement. The standing rule of the same grill applies throughout: the system is the most faithful model of the known evidence, every unknown gets its best estimate from that evidence with the mark `approximate`, and no design here says "measure later".

## The pools

| | in the dump | removed by the 3.29.0 note | pool of 3.29 |
|---|---|---|---|
| Tempering Orb (weapon) | 181 | 45 (12 white-socket, 33 one-colour) | **136** (the wiki's list) |
| Tailoring Orb (body armour) | 75 | 21 (6 white, 15 one-colour) | **54** (derived: the wiki page still lists 75) |

A pool is the mods of group `EnchantmentHeistWeapon` or `EnchantmentHeistArmour` without a white-socket or all-sockets-one-colour stat (claims `enchantment.weapon_pool_136`, `enchantment.armour_pool_54`; the second is derived from the dump and the patch note, so it carries `approximate`). The 14 Harvest quality enchants are not in these pools (ADR-0052).

## The weights

The weights are the counts of the players' sample of Grand Heist Curio Displays (13,845 wings, leagues 3.23 to 3.27; 7,742 enchanted weapons and 5,078 enchanted body armours), restricted to the 3.29 pool and renormalised.

- **Body armour**: one weight per **kind** of enchant, as the chi-square of every hybrid kind supports (about its degrees of freedom). Single 8% tag with the tags told apart (mean 480: Life 752, Defence 690, Resistance 504, Attribute 227, Mana 227); "40% reduced Attribute Requirements" 456; "8% plus no colour" 44; "6% plus 6%" 39; "6% plus 25% less requirements" 40; "All Sockets Linked" 45; "-3 maximum sockets" 22; "200% requirements" 21; "penalty hybrid" 18; "6% plus linked" 4.4 (claim `enchantment.body_armour_weight_classes`).
- **Weapon**: one weight **per enchant**, from the raw count. The kinds scatter 2.8 to 6.7 times their degrees of freedom around the kind mean, so the data reject pooling (claim `enchantment.weapon_weights_depend_on_tag`). The noise of one count of 15 to 50 is 15% to 25% and is left in: a set of several enchants averages most of it.
- **The table is data, not code.** The claim's `value` (admitted by the build ticket from the research note; the draft YAML carries only the kind means for armour) holds the counts (the armour per-kind table and the weapon per-enchant table, keyed by mod id), reproduced by the research branch's `enchantments-samples.py`; a test recomputes the shares from it.

## The assumptions, named

Each is an `approximate` claim whose reason the report prints (ADR-0028). None of them is the certified gap of ADR-0023: that measures the solver's merge, these are uncertainty in the model.

| Assumption | Evidence for it | Why it stays unquantified |
|---|---|---|
| The orb draws from the Curio table | The 263-click Tailoring tally fits the Curio shares (chi-square 5.0 on 5 degrees), but it lacks the Life and Resistance rows, so those two shares rest on the Curio sample alone; nothing else reproduces the players' "extremely common 8% Defence". For weapons there is no tally, so it is an inference | No source states that the two use one table |
| GGG kept every weight at 3.29.0 and only dropped enchants | The note says only that enchants were removed | The sample ends at 3.27 |
| The shares hold at every item level | 81% of the sample is from area level 83; level-69 and level-70 enchants appear from area level 61 | No gate is measured; the planner applies none |
| The extra crafted slot keeps its Curio weight in the draw as a click that misses (it is never an acceptable result of the orb route) | Claim `enchantment.extra_crafted_modifier_curio_display_rate` keeps `orb_probability: null`; the weight stays so that the pool is the game's 136 and 54 | If the orb cannot roll it the orb cost is overstated by under 1% (clean Life 4.9 orbs instead of 5.0, clean Critical 8.4 instead of 8.5); ADR-0053 |

The report names these four reasons under "Approximate inputs" whenever a plan uses the orb route. There is **no interval**: the sampling error of the main shares is a few percent of the cost, and the real uncertainties (Curio equals orb, weights kept after 3.29.0) have no bound to give, so they are named and not quantified. A report line stays "approximate" and never becomes a number such as "plus or minus 5%".

## What is checked in the emulator and what goes to the owner

The Craft of Exile code and data in the repo's `sources/raw/coe` hold no Tempering Orb, Tailoring Orb or Heist enchant mechanic, so the emulator ([#198](https://github.com/Rasslabsya4el/crafting-system/issues/198)) is asked first and, where it has none either, the in-game list [#182](https://github.com/Rasslabsya4el/crafting-system/issues/182) carries the few questions that sharpen the model (stacking of the crafted slot, the colour mapping of the three "no colour" enchants, the socket reforge). The plan runs on the best estimate above whether or not they are answered; a later answer is a claim edit with no code change (ADR-0024).

## The closed forms the tests use

Computed from the counts above (armour with the kind means, so a test compares within the rounding of the digits shown), a hand oracle independent of the code:

- body armour, clean Life (4 enchants): 20.1% per click, **5.0** orbs; any Life: 23.2%, 4.3; clean Resistance 14.4%, 7.0; clean Defence 18.5%, 5.4;
- weapon, clean Critical (9 enchants): 11.8% per click, **8.5** orbs; clean Speed 12.7%, 7.9; clean Physical 9.4%, 10.6.

Prices are not asserted here. The orb prices come from the price file, whose source (#13) disagrees with the research's single-snapshot figures by a factor of 24; the plan uses the price layer's, not a number from a note.

Origin: [Grill B7](https://github.com/Rasslabsya4el/crafting-system/issues/105) (round 1, answer 1; the standing rule); [the research #100](https://github.com/Rasslabsya4el/crafting-system/issues/100), sections 2, 3 and 6; ADR-0004, ADR-0005, ADR-0028.
