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

Origin: [Grill B2](https://github.com/Rasslabsya4el/crafting-system/issues/93) (decisions list, owner round 1 point 7); [Blessed Orb, catalysts and Orb of Chance](https://github.com/Rasslabsya4el/crafting-system/issues/89); ADR-0024, ADR-0027.

## Amendment: a corrupted implicit makes the finish cost per try ([Grill B4](https://github.com/Rasslabsya4el/crafting-system/issues/95), ADR-0039)

A corrupted item takes no ordinary catalyst, so for a target that has a `quality` and asks for a corrupted implicit the catalysts go on **before** the Vaal Orb, the Locus or the Bloodstained resonator. The finish cost is then charged on each use of the corrupting action, not once on the goal state: every try uses a new item with its own catalysts, so every restart pays it again. The chance that the corrupted implicit's roll passes is averaged over the exact distribution of the realized quality (the last catalyst can pass the target percent). A target without a corrupted implicit keeps the rule above unchanged.
