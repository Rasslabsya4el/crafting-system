# Socket odds come from three sources, and the marks they carry are listed

Nothing GGG publishes gives the odds of the Jeweller's Orb, the Orb of Fusing or the Chromatic Orb. [The sockets research](https://github.com/Rasslabsya4el/crafting-system/issues/99) found a third party's fit for the Chromatic Orb, a 2017 count for the Orb of Fusing and two item-generation tables for the Jeweller's Orb. [Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) takes them as the most faithful model of the evidence now (the owner's standing rule: no route-driven measurements, no "measure later"), marks what is thin as ADR-0028 asks, and sends what only the game can settle to [#182](https://github.com/Rasslabsya4el/crafting-system/issues/182). Craft of Exile has no socket orb (its crafting methods and its shipped code hold none, checked 2026-11-01), so the emulator ([#198](https://github.com/Rasslabsya4el/crafting-system/issues/198)) cannot check any of them.

## Chromatic Orb: Siveran's formula is the rule

The owner's answer: the Chromatic formula has not changed, so Siveran's formula is the rule, and no mark goes on it for being a third party's fit. Siveran maintains the Vorici Chromatic Calculator and published 2,836 results (`calc.html`, "Last updated July 24, 2026"; the research refitted them and the formula sits inside the 95% interval of each of the 8 cells).

- Every socket rolls independently, non-white with `p = 0.00375 × max(ilvl − 14, 1) × (1 + min(quality, 30) / 100)`. The formula covers every item level and quality as the calculator does. The data sample item levels 2 to 50, 85 and 100, qualities 0 to 20 and 60, and six-socket items only; between item level 51 and 84, for qualities 30 to 59 and for fewer than six sockets the formula interpolates, which the owner's answer accepts without a mark (the cells and the cap of 30 are also in the claim text). Quality from currency stops at 20%, so the cap binds only for a start item.
- A non-white socket takes its colour by the item's requirements: with one attribute `a`, that colour `0.9 (10 + a) / (a + 20)` and each other `0.05 + 0.9 × 5 / (a + 20)`; with two attributes `0.9 a / total` and the missing colour 0.1; with three `a / total`.
- **Only if every socket rolled white** is the first socket made non-white. So on a **one-socket item the socket always becomes coloured** (owner, answer 3b; the same rule).
- **A Chromatic Orb cannot return the colours the item already has** (owner, answer 3d; Siveran's commit log mentions it): the result is the roll conditioned on differing from the current colours. It applies to every Chromatic Orb use, with an Omen too, and not to the bench craft.
- **The forced socket's colour** uses the same weights (Siveran's, the plan). The data show a flatter colour (about 47, 27, 26% for a strength item of requirement 25 or 180; 24, 52, 24% for dexterity 65); one third of the weights plus two thirds uniform stays within four points of all three cells, and is the second reading. It matters only for a target that needs exactly one coloured socket: a forced result colours one socket, so with two or more needed it is never a goal and the next roll rerolls everything. The second reading's number is the plan's policy evaluated at it, and only for such a target. Marked `approximate`.
- Marked `approximate` too: the repeat exclusion (the owner's belief and a commit-log line; checked on #182), and the colour weights ignoring requirement-changing mods (the finish is solved before the mods are known and such mods are rare).

## Orb of Fusing: sequential group sizes at 20% quality

Fusing links by sequential group sizes: from the first unlinked socket a group size is drawn from one weight table cut to the sockets that remain and renormalised, then the next group starts. At 20% quality the fitted weights for sizes 1 to 6 are 0.17818, 0.34818, 0.26766, 0.19672, 0.00826, 0.00100, giving all linked 66.1%, 33.7%, 19.9%, 0.83% and 0.10% for 2 to 6 sockets (rechecked at design time). Marked `approximate` (one 2017 dataset of 100,000 orbs; nothing says it changed). The table exists for 20% quality only, so **Fusing is offered at 20% quality or more and uses the 20% table above it** (pessimistic); below 20% the finish buys quality first (ADR-0049). Fusing is refused on one socket and on an item whose sockets are all linked. **Omen of Connections** links all the sockets (exact).

## Jeweller's Orb: the wiki table, the 2014 table beside it

The orb rerolls the count to a number **different from the current one**, never above the class maximum or the item-level gate, and cannot be used at the maximum. Weights are the item-generation table, renormalised without the current count: for the six- and three-socket classes 50, 120, 100, 30, 5, 1 for 1 to 6 sockets (the wiki Developer table, the plan); the four-socket classes use 100, 90, 80, 30. The second reading, for the six- and three-socket classes, is the 2014 table of GGG's chris_wilson, 100, 90, 80, 30, 5, 1. That the orb uses the generation weights is an inference; the 2014 numbers are the only official statement. From any count to six sockets at item level 84 the plan needs about 215 orbs and the second reading about 223, to five or more about 36 and 37: under 4% apart. **Quality has no effect in the model** (the wiki says each 1% improves the result by 1% without saying how; ignoring it is pessimistic). Both are `approximate`. **Omen of the Jeweller** makes the next Jeweller's Orb roll the maximum of class and item level (exact); the surviving sockets follow ADR-0046.

## The bench, exact except one craft

The bench sets the count exactly (2 to 6 for 1, 3, 10, 70, 350 Jeweller's Orbs) and links exactly (2 to 6 for 1, 3, 5, 150, 1500 Orbs of Fusing) on the 20 weapon and armour classes (datamined, exact; the count up to the class maximum, any item level; the link craft makes the first N sockets one group and leaves the rest unlinked, `approximate` because no source says which sockets). "At least 2, 3 or 4 non-white" costs 5, 20, 75 Chromatic Orbs and is the Chromatic roll conditioned on at least that many non-white sockets, `approximate` (nothing says how the roll goes beyond the minimum). A bench craft is priced as its orb count times the orb price (data names, as `bench_craft.option_cost` does). The colour crafts for one named colour no longer exist.

## Omen of Trichromatism

The next Chromatic Orb gives at least one red, one green and one blue socket: the roll conditioned on that, `approximate` (the mechanism is not documented; a conditioned roll is the simplest reading). On fewer than three sockets the owner expects an error (answer 3e); the planner does not offer it there, and the check goes to #182. Priced as the Omen plus the orb. (On a four-socket dexterity-intelligence helmet at item level 84 and 20% quality, getting red, green and blue by plain Chromatic Orbs takes about 78; with the Omen it takes one orb and the Omen.)

## Marks and claims

| Input | Mark |
|---|---|
| Chromatic non-white chance, natural colours, forced socket, one-socket rule | none |
| Chromatic forced-socket colour; repeat exclusion; requirement-changing mods | `approximate` |
| Fusing group-size table (20% quality) | `approximate` |
| Jeweller's table and its no-quality-effect default; removal of sockets; bench link position; bench and Omen conditioned rolls; Trichromatism mechanism | `approximate` |
| Class maximum (wiki; unnamed exceptions for small low-level bases) | `approximate` |
| Bench count, link and colour prices; Omens of the Jeweller and Connections | none |

The claims go into `rules/claims/sockets.yaml`: the 25 draft claims of the research (branch `research/sockets`, c5376ae), with the Binding claim replaced (ADR-0048), the three claims confirmed on the wiki on 2026-11-01 (class maximum, the quality currencies' gain by item level, Binding as an Alchemy), and the owner's answers as claims of kind `owner` (surviving sockets, one-socket Chromatic, no repeat, Trichromatism on fewer than three sockets, Binding, the beasts). The Siveran data enter the tests as the eight aggregated cells (item level, quality, sockets rolled, non-white count), not the file.

Origin: [Grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) (round 1 answers 1 to 3 and the standing rule); [Sockets, links and colours in 3.29](https://github.com/Rasslabsya4el/crafting-system/issues/99) and its note; ADR-0012, ADR-0028, ADR-0045, ADR-0046.

## Amendment: the Jeweller's table as a rule axis, Fusing below 20% ([#228](https://github.com/Rasslabsya4el/crafting-system/issues/228))

The Jeweller's table is a **rule axis** (ADR-0033): `jeweller_table`, with the readings `wiki_developer_table` (the plan) and `chris_wilson_2014`, so a model that asks for all readings of `JewellersOrb` gets both; the Omen of the Jeweller rolls no table and has no axis. The four-socket classes have one table in both readings. An Orb of Fusing on a weapon or armour below 20% quality is `OutOfScopeError` (no admitted rule gives its odds): "offered at 20% or more" is the planner's rule for S5, the action refuses below it, and uses the 20% table at 20% and above. The expected orbs by value iteration over the kernel, item level 84: plan 214.9 to six sockets from one socket (214.7 to 215.1 from the others) and 35.7 to five or more; second reading 222.6 (222.6 to 222.9) and 36.9 from three sockets (36.8 from one); the design's single figure for "any count" is reached from the starts named and every start lies within 0.4 of it.
