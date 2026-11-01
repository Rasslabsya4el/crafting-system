# A recombination costs Dust and Gold at prices in the price file, by a per-combine rule

Every recombination costs Thaumaturgic Dust and Gold. No source gives a formula: PoEDB lists two constants (multiplier 3, exponent 0.75) whose use is not documented, and the client tables hold no cost table. [Research #177](https://github.com/Rasslabsya4el/crafting-system/issues/177) measured thirteen windows of the 3.25 guide author's sheet and collected 3.26 reports; [grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94) (round 1 answer 2) decided the pricing.

## Prices

**Dust and Gold are two prices in the price file** (ADR-0007), changeable by the owner. Defaults: **150,000 Thaumaturgic Dust per Chaos** and **500 Chaos per million Gold**. Neither is on the trade site or the currency exchange; the Dust default is at the cheap end of the market comments the research read (10,000 to 100,000 per Chaos), and it is the owner's to change.

## The cost of one combine

Rule data `recombinator_cost`, from the reports; the planner does **not** compute Dust from the mods, because no formula supports it. Marked `approximate` (ADR-0028), each with its interval:

| | Point | Interval |
|---|---|---|
| Gold per combine | 12,000 | 8,000 to 20,000 |
| Dust per combine | 100,000 | 25,000 to 250,000 |
| Dust factor with a low-tier non-exclusive craft on each input | 0.5 | 0.11 to 0.5 |

At the defaults one combine costs about 7 Chaos (4 to 12), Gold being 86% to 96% of it. The plan uses the point values; the answer lists the cost rule among its approximate inputs with the intervals, and the policy's expected number of recombinations is in the risk output, so the spread of the cost rule can be read as that number times the interval of one combine. An influenced input raised the cost by 50% in the 3.25 data (one line, no window, no word on Dust or Gold alone). R29 has influenced inputs, so the planner multiplies **both** Dust and Gold by 1.5 for a combine with an influenced input (the main chat's default, marked `approximate`, replaced by the owner's readings). One project estimate in the research would put Gold at 40,000 to 80,000; the interval above is the reports'.

## The junk craft is an option, off by default

The owner noted that the Dust drops a lot when an item carries a crafted mod. The research found the cause is a low level or tier, not "crafted", and that Gold does not follow the discount (3.25 data). The **junk-craft step** (craft the cheapest non-exclusive mod on the open side of each input, Dust times 0.5) is registered as an optional variant of the recombinator action, **offered only when a setting turns it on**. At the default prices it does not pay (it saves at most about 0.6 Chaos, and costs about 1 Chaos in extra Gold and the craft); it pays if Dust is priced at or below about 33,000 per Chaos, which is inside the market's spread, so the owner can ask for it.

## In-game readings

The owner reads the Dust and Gold of eight item pairs once all in-game checks are collected in one list ([#182](https://github.com/Rasslabsya4el/crafting-system/issues/182), answer 4e). They replace the table above when they come; until then the claims keep the "reports" provenance. The rank-4 bench "25% reduced Recombination Cost" stays unset until read from the game (it may already be inside every report).

Origin: [Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94) (round 1 answer 2, new point from the owner); [Research #177](https://github.com/Rasslabsya4el/crafting-system/issues/177) and its [note](../research/2026-11-01-recombinator-dust-gold-cost.md); ADR-0007, ADR-0028.
