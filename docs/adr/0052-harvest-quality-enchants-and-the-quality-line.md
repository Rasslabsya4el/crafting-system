# Harvest quality enchants are bought, and the plan ends with one quality line

The Harvest craft table holds 14 quality enchants: 8 for body armour and 6 for weapons (claim `enchantment.harvest_quality_enchants_14`). Each stops quality adding Defences or physical damage and gives another stat per percent of quality instead: for body armour +1 Maximum Life, Maximum Mana, Strength, Dexterity or Intelligence per 2%, or +1% to a Fire, Cold or Lightning resistance; for weapons range, area, accuracy, attack speed, critical strike chance or elemental damage. [Grill B7](https://github.com/Rasslabsya4el/crafting-system/issues/105) (answer 4) decided what the planner does with the quality they work from.

## The action

- Each enchant is a **`Finite` one-outcome action** (ADR-0024) in its own file `actions/harvest_quality.py`: no draw, the item gets that enchant in the enchantment slot. The cost is Lifeforce, priced from the price file by type (claim `enchantment.harvest_quality_enchant_costs`): body armour 3,250 each (Life, Strength and Fire resistance Wild; Dexterity and Cold resistance Vivid; Mana, Intelligence and Lightning resistance Primal); weapon 5,000 each (Range and Area Wild; Accuracy and Attack Speed Vivid; Critical and Elemental Primal).
- It **replaces** a Tempering or Tailoring enchant and is replaced by one (claim `enchantment.quality_enchant_replaces_heist_enchant`: the wiki's one-slot rule plus two player quotes, no counter-example; marked `approximate` as an inference, ADR-0028). So a target that lists a quality enchant and a pool enchant together is read as alternatives (ADR-0050), never as both.
- Refusals: a mirrored or corrupted item and the wrong class (the 8 are for body armour, the 6 for weapons). The enchant changes only its stat; it does not touch sockets or links (claim `enchantment.quality_enchant_changes_only_its_stat`).
- The finish cost (ADR-0050) takes it as the **Harvest route**: its Lifeforce price against the orb route's expected cost, the cheaper one.

## The quality line

The enchant's stat is worth only as much quality as the item has: +1 Life per 2% is 10 Life at 20%, 0 at 0%. The quality of a body armour or weapon was left a target only for sockets (B6, [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81)), so B7 gives it **one closing line and no search** (owner, answer 4):

> Bring quality to 20%: N Armourer's Scraps (or Blacksmith's Whetstones), about M Chaos.

- It is printed when the policy ends with a quality enchant (from the target or from the start item), after the enchant step.
- **N** is the expected number of scraps to take the item from its quality to 20% at its item level, by the rule of ADR-0029: a currency adds `floor(f)` points or one more with probability `frac(f)`, `f = max(1, min(30*e^(-ilvl/30) - 0.3, 20))`, capped at 20%. The official 3.25 note (forum thread 3531661, copy in `sources/raw/research/official-quality-3.25.txt`) puts them under one rule: "The rarity of the item is no longer relevant when applying Cartographer's Chisels, Blacksmith's Whetstones, Armourer's Scraps, Glassblower's Baubles, and Catalysts to non-Unique items. Instead, the amount of Quality they provide is now based on the item level." The gain is therefore the catalysts' gain. The build ticket admits it as the claim `quality_enchant.scrap_gain_follows_catalyst_formula`, marked `approximate`: the note says the amount depends on the item level, the formula is the wiki's Quality page, and no source checks it on scraps.
- **M** is N times the scrap's or whetstone's price from the price file.
- The line is **not part of the search over mods**. For a given item level it is a constant, so it cannot change which explicit-mod route is cheapest. It enters one comparison: the Harvest route of the finish cost (ADR-0050) carries it, so that the quality enchant is not cheaper than the orb only because its scraps were left out. The report prints the line with its cost and, beside the plan's mean cost, "Total with the quality line", so the owner sees both.
- The start item's quality is read when `Item` has a place for it; the line assumes 0% for a start item that records none and says so in its text; B6 ([#104](https://github.com/Rasslabsya4el/crafting-system/issues/104)) decides where a plain quality is stored. Quality helps socket rolls since 3.29.0, a gain the plan does not count.

## Rejected

- **No line at all** (the enchant alone): a Life-per-quality enchant at 0% quality does nothing, so a plan that stopped there would look cheaper than it is.
- **Quality of body armour and weapons as a full target in B7**: more work, overlaps B6, and the owner left quality a target only for sockets.

Origin: [Grill B7](https://github.com/Rasslabsya4el/crafting-system/issues/105) (round 1, answer 4); [the research #100](https://github.com/Rasslabsya4el/crafting-system/issues/100) (ENC-14 to ENC-17); ADR-0024, ADR-0028, ADR-0029, ADR-0050.
