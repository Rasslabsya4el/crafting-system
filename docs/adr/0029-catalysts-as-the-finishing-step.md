# Catalysts are the finishing step and cost expected catalysts

Catalyst quality changes no odds since 3.15.0: it no longer raises the chance of a matching mod, and the Augmentation, Regal and Exalted Orb no longer use it up. So no crafting action depends on it, and nothing a policy does earlier changes what a catalyst does later. [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) therefore plans catalysts **last, as a finish cost**, and keeps quality out of the compressed state unless an enabled action reads it (ADR-0027). The mechanics are in [the catalyst research](https://github.com/Rasslabsya4el/crafting-system/issues/89).

## What is modelled

- **The catalysts**: the ten regular ones (Abrasive, Accelerating, Fertile, Imbued, Intrinsic, Noxious, Prismatic, Tempering, Turbulent, Unstable) and Sinistral and Dextral, on rings, amulets and belts. **Tainted Catalysts are out** (corrupted items only, random type and amount, odds unpublished).
- **One quality type**: a different catalyst replaces the quality and restarts from 0%. The cap is 20%; a catalyst that would pass it is capped (`min(20, q + gain)`).
- **Gain per catalyst** depends on the item level: `f = max(1, min(30*e^(-ilvl/30) - 0.3, 20))`, and one catalyst adds `floor(f)` points, or one more with probability `frac(f)`. The cost to 20% is the expected number of catalysts times their price: about 9.5 at item level 75, 13.3 at 84, 20 from 95 up.
- **Scaling**: a modifier with a matching tag (implicit or explicit) is multiplied by `(100 + quality) / 100` on its stored integer, **rounded down**, once per modifier (wiki formula, marked approximate: the owner checks in game only if a route sits on a rounding edge).
- **The target form** is `quality: {type, min_percent}`. A requirement on a value is a base roll (ADR-0027); under a quality the planner finds the base roll that shows the displayed minimum.

## How the planner uses it

The search ends at the goal state without quality; the finish cost, the expected catalysts for the target quality at the item level, is added to the value of a goal state, so a restart that buys a new base pays it again. A target without a `quality` has no finish cost. A quality already on a start item is read from `Item` (ADR-0027) and counts toward the gain.

Which lines the quality scales on a fractured or a bench-crafted mod, and that no other currency touches quality, rest on the research claims, which state their limits themselves; a claim that depends on the wiki formula carries `approximate` (ADR-0028).

## Amendment (grill B7): enchantments finish the same way

The enchantment of a weapon or body armour is a second finish step of the same shape ([ADR-0050](0050-enchantments-as-a-finish-step.md)): nothing earlier changes what it costs, so the search ends without it and its expected cost (orbs for the chance of the target's acceptable set, or the Lifeforce of a Harvest quality enchant) is added to the value of a goal state, and a restart pays it again. A target with neither `quality:` nor `enchantment:` has no finish cost. The two steps never meet on one item: catalysts act on rings, amulets and belts, enchantments on weapons and body armour. The plain quality a body armour or weapon needs for a quality enchant is a closing report line; its expected cost is carried by the Harvest side of the enchant's finish comparison, and its scraps follow the gain rule above ([ADR-0052](0052-harvest-quality-enchants-and-the-quality-line.md)).

Origin: [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) (decisions list, owner round 1 point 7); [Blessed Orb, catalysts and Orb of Chance](https://github.com/Rasslabsya4el/crafting-system/issues/89); ADR-0024, ADR-0027.

## Amendment: the finish generalises to sockets ([Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104), 2026-11-01)

The idea of this ADR, plan the part no mod action changes last and add its cost to the value of a goal state, also covers sockets and the quality of weapons and armour, which no B1 to B3 action changes. Sockets are not a closed-form cost: the finish is a small decision problem of its own (ADR-0045). The quality of a weapon or armour uses this ADR's formula for the gain per currency item (ADR-0049).

## Amendment: a corrupted implicit makes the finish cost per try ([Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95), ADR-0039)

A corrupted item takes no ordinary catalyst, so for a target that has a `quality` and asks for a corrupted implicit the catalysts go on **before** the Vaal Orb, the Locus or the Bloodstained resonator. The finish cost is then charged on each use of the corrupting action, not once on the goal state: every try uses a new item with its own catalysts, so every restart pays it again. The chance that the corrupted implicit's roll passes is averaged over the exact distribution of the realized quality (the last catalyst can pass the target percent). A target without a corrupted implicit keeps the rule above unchanged.

## Amendment: the catalysts as actions ([#157](https://github.com/Rasslabsya4el/crafting-system/issues/157))

`actions/catalyst.py` holds `ApplyCatalyst(type)` for the twelve types. It moves the item's `Quality` and nothing else (`Reads.quality`, `Adds.quality`), so the contract suite and layer 1 of the compressed state pass on it. The gain per catalyst is the formula above as **exact fractions**: `f` is computed with 60 decimal digits (`Decimal.exp` is correctly rounded, so every machine gets the same fractions), and the wiki's table is that law to two decimals. The mean catalysts to 20% from 0% are `expected_catalysts(item_level)`: 9.53, 13.35, 14.42 and 20 at item level 75, 84, 86 and 95; `expected_catalysts_for(item, type, target)` takes the quality the item already holds when it is of that type. A catalyst is refused (`NotApplicableError`) on an item that is no ring, amulet or belt, on a corrupted item, and on one that holds 20% of its type already; another type at 20% is replaced, restarting from 0%.

The scaling is `scale_value(v, q) = v * (100 + q) // 100`; `boosts(mod, type)` reads the table of `catalyst.match_by_implicit_tags` (a regular type by `implicit_tags`, once per modifier; Sinistral prefixes and Dextral suffixes, never an implicit); `base_roll_for(displayed, q)` is the smallest stored roll that shows the displayed value (R06: 35 x 1.2 = 42; "14%" needs the roll 12). The claims for the cap past 20, the random rounding of the gain, the rounding down of a scaled value and the side rule are marked approximate, so an answer that reads them names them (ADR-0028). The `catalyst` kind is not a planner kind: adding the finish cost to a goal state and offering a catalyst last is [#158](https://github.com/Rasslabsya4el/crafting-system/issues/158).
