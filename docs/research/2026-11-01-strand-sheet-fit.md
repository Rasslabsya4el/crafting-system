# The strand sheet, fitted: what the kept tiers weigh, how strands are spent, how Unravelling and Remembrance behave

Research ticket [#271](https://github.com/Rasslabsya4el/crafting-system/issues/271) (B5 R1) of the design [#103](https://github.com/Rasslabsya4el/crafting-system/issues/103); it refines the [#98 note](2026-10-31-memory-strands.md) and the choices of ADR-0040 to ADR-0044. Read on 2026-11-01 against the pinned export (repoe-fork 3.29.3.3). The data are the public "Memory Strand Testing" sheet of the author of the 3.29 strands post (u/Macookta): the three tabs the ticket names ("foulborn and misc currency data", "Unravelling data", "remembrance data") and, for the spend law and the weights, the two Alteration tabs of the same sheet ("ilvl 86+ int body, orb of alteration" with 9,944 rows and "ilvl 85+ str helm, orb of alteration" with 7,436), which hold 17,380 of the 18,285 crafts the post counts. Scripts, extracts of the output and the result files are in `research/271/` (see "Reproduce"); claim drafts in [`2026-11-01-strand-sheet-claims/`](2026-11-01-strand-sheet-claims/).

Rules of the snapshot kept throughout: the system is built on today's evidence; an unknown gets a best estimate marked `approximate`; nothing here waits for an in-game check, and what the sheet cannot answer is listed in section 8 for the main chat.

## Answer in brief

| # | Question | Statistic | Verdict |
|---|---|---|---|
| a | Which weight reading predicts the mods drawn after a cut? | log-likelihood of 18,264 crafts: reading 2 (refactored, kept weight times T/K) -96,794.0; reading 1 (redistribution) -96,871.0; reading 3 (delete only) -96,968.7. Exponent g of (T/K)^g: 1.00, 95% interval 0.90 to 1.11 | **Settled: reading 2.** Reading 1 loses by 77.0 (SE 10.4), reading 3 by 174.7 (SE 18.1); in each of the three tabs and each band of strands |
| b | Spend law per currency; the Exalted ceilings | Uniform integer on 0..ceiling, cut at the count, is not rejected for any currency (p from 0.08 to 0.84). Exalted spends reach 33 with 4 mods before and 38 with 5 mods before | **Settled: uniform for all, no bins for Chaos and Alchemy** (the bins counted rows, not crafts). **Narrowed: the Exalted table is indexed by the mods after the craft** (shift by one mod). Identification spends 0 |
| c | The Unravelling chance below the breakpoint | With our weights: p = min(1, a x), a = 1.0011 (SE 0.0005); exponents of s and of the weight ratio 1.000 and 1.000 (SE 0.012); 40 free bins gain 11.4 log-likelihood for 39 parameters | **Settled: ADR-0044's formula is exact within error** for amulets, wands, rings, gloves, body armours. The author's excess was his wand weights |
| c | The destination reading | Rank step 1:2:3 exact on equal weights (smallest of 11 tests p = 0.078). On unequal weights B (cumulative) minus A (rank multipliers) +14.9 log-likelihood; replays: A out by 5.8 SD, B by 2.1 SD (p = 0.015) | **Narrowed: A is rejected, B is the better reading, not exact.** Not cut by the strands: 10,721 of 23,494 raised mods went to a tier the cut would have removed |
| d | Does Remembrance depend on the old count? | Each row against the one before (2,254 pairs): correlation 0.017 (95% half-width 0.041), chi-square of independence p = 0.73 | **Narrowed, strictly not answerable:** no dependence if the rows are consecutive orbs on one item; the tab records only the new count |
| e | Any Foulborn row on a 0-strand item? | 0 of 491 Foulborn crafts; fewest strands 1 (18 crafts have 5 or fewer) | **Not answerable from the sheet.** The size of the bonus itself is exactly 75 |

Axes: `tier_weights` (ADR-0042, three readings) **collapses to reading 2**; `unravel_destination` (ADR-0044, two readings) **collapses to B** with `approximate` kept. After both, the strand axes contribute one reading each to ADR-0042's product ceiling of 24.

One defect of our pool found on the way: four Battle Royale mods of the export spawn on ordinary bases and are not in the game (section 1.4). It matters to the cut and to the Unravelling chance and must be fixed before the acceptance tests of ADR-0040.

## 0. The data, and the unit

- **The unit is the craft, not the row.** The tab "foulborn and misc currency data" lists a multi-mod craft (Alchemy, Chaos, Scroll of Wisdom) once for each mod it produced, with the same item text before and after. Its 1,903 rows are 902 crafts: 427 Foulborn Augmentation, 155 Chaos, 148 Alchemy, 84 Exalted, 64 Foulborn Regal, 13 Regal, 11 Scroll of Wisdom. The earlier note and ADR-0041 counted rows in the tests of the spend law (section 2).
- **Left out:** 16 Alchemy crafts on items that were not normal (what they did is unexplained; spends 0 to 29); three entries of the Alteration tabs with a spend of 40, 97 and 11 (typing errors; among 17,380); one row with no mods in each Alteration tab (for the weights).
- **Our pool.** Every craft is put on the project's pool (`pool_candidates` of the pinned export): base from the item name, item level from the text, the mods before and after from their names and tiers (4,218 mod lines of the foulborn tab, all resolved), the families on the item excluded, a side with no free slot closed. The Alteration tabs name no base; the pool depends on it only through its tags, so a top-tier base of the armour type stands in (Vaal Regalia at item level 86, Royal Burgonet at 85).
- **Emulator first.** The local copy of Craft of Exile (data 3.29.0.3, fetched 2026-09-20; never copied into the repo) models no strand craft, so it cannot test the cut, the spends, Remembrance or Unravelling. What it can check is the pool weights this research stands on: the sum of the tier weights of each side at the item level, from its data.

  | Base, item level | Ours | Craft of Exile | The sheet's own sums |
  |---|---|---|---|
  | Amulet, 86 (prefix / suffix) | 88,600 / 125,250 | 88,600 / 125,250 | 88,600 / 125,250 |
  | Ring, 86 | 60,250 / 103,600 | 60,250 / 103,600 | 60,250 / 103,600 |
  | Wand, 85 | 64,836 / 65,342 | 64,832 / 65,842 | 79,166 / 76,842 |

  Ours agree with the emulator on amulets and rings exactly and on wands within 0.8%; the sheet's wand sums are higher because they lack the 0.5 weight of attack mods on wands, as the author himself found later. The amulet figure is the one that exposed the defect of section 1.4: with the four duplicate mods ours was 126,050.

## 1. (a) What the kept tiers weigh

### 1.1 Method

The cut of ADR-0040 is taken as given (`K = floor(200 (T-1) / D) + 1`, pre-spend count). The readings of ADR-0042 differ in one thing, the weight a kept tier gets. They are written as one family: a kept tier weighs `w (T/K)^g (W_all/W_kept)^b`, with `(g, b)` = (0, 1) redistribution (reading 1: the type keeps its total), (1, 0) refactored weight (reading 2), (0, 0) delete only (reading 3). For each craft the probability of the mods that came out is computed exactly: draws without replacement from the pool, each draw taking a mod by weight among the mods whose family is not yet on the item and whose side has room, the order unknown, so the probability of the set sums over the orders (a recursion over the subsets). The number of mods of the craft is not modelled; it does not depend on the reading. The tier chosen inside a type is the same in all readings; they differ only in the chance of the type against the others.

The three data sets are independent: 886 crafts of the foulborn tab (single adds: Foulborn Augmentation, Foulborn Regal, Regal, Exalted; multiple: Alchemy, Chaos, Scroll of Wisdom), 9,943 Alteration crafts on intelligence body armour, 7,435 on strength helmets.

Checks that the pool is right: our count of tiers `T` of the mod type that came out equals the sheet's own `total_tiers` on all 1,834 mods of the foulborn tab, all 14,927 of the int body tab and all 11,125 of the helmet tab (after section 1.4; before it, 31 of 1,834 differed). No craft has probability 0 under any of the three readings: every observed mod is among the kept tiers, so the cut itself is again confirmed (leaving the cut out costs 1,800 to 12,300 log-likelihood per tab). The Foulborn bonus: with the bonus to the rating at 75 (ADR-0040) the 491 Foulborn crafts have log-likelihood -1,809.6; at 72.5 it is -1,823.1, at 62.5 -1,831.8, at 50 -1,845.1, at 0 -1,927.1, and a bonus of 76 or more makes an observed craft impossible. So 75 is the largest bonus the data allow and the likelihood is still rising toward it: the `+75` is confirmed to within about a point.

### 1.2 Result

| Data | Crafts | Reading 1 | Reading 2 | Reading 3 | 2 minus 1 (z) | 2 minus 3 (z) |
|---|---:|---:|---:|---:|---:|---:|
| foulborn and misc currency tab | 886 | -6,022.1 | **-5,988.7** | -6,014.6 | 33.5 (4.7) | 25.9 (3.8) |
| Alteration, int body | 9,943 | -52,719.8 | **-52,699.3** | -52,774.4 | 20.4 (3.1) | 75.0 (6.5) |
| Alteration, str helmet | 7,435 | -38,129.2 | **-38,106.0** | -38,179.7 | 23.1 (7.1) | 73.7 (6.0) |
| All | 18,264 | -96,871.0 | **-96,794.0** | -96,968.7 | 77.0 (7.4) | 174.7 (9.7) |

The bootstrap over crafts (4,000 resamples) gives 95% intervals of 57.0 to 97.3 for reading 2 over reading 1 and 139.6 to 210.8 over reading 3. Reading 2 is ahead in every subset: crafts with one added mod (9,292) by 28.2 over reading 1, with two or more (8,972) by 48.9, Foulborn crafts (491) by 11.1, other crafts (17,773) by 65.9; in each band of effective strands (0-19, 20-49, 50-79, 80 and more; a Foulborn craft counts 30 more) by 15.0, 11.2, 28.5 and 22.3 over reading 1. By currency in the foulborn tab reading 2 leads in six of seven and is 1.3 behind reading 3 on the 11 Scroll of Wisdom crafts. Reading 1 against reading 3: reading 1 ahead by 54.6 and 50.6 in the two Alteration tabs, behind by 7.6 in the foulborn tab (not significant).

**Exponent.** With `b = 0` and `g` free, the total log-likelihood is -96,968.7 at g = 0, -96,891.7 at 0.25, -96,837.3 at 0.5, -96,805.0 at 0.75, **-96,794.0 at 1**, -96,803.9 at 1.25, -96,834.2 at 1.5, -96,954.5 at 2: the maximum is 1.00 and the 95% interval (a drop of 1.92) is 0.90 to 1.11. With `g = 0` and `b` free the best is b = 0.75 at -96,841.7, 48 below reading 2. Over the grid of both, the best point is (1, 0); (0.75, 0.25) is 3.4 below it.

**Where the readings part.** They agree on a mod type whose tiers weigh the same; they differ on a type whose kept tiers carry little of its weight. For the single draws (9,292 crafts), grouped by `rho = (T/K) / (W_all/W_kept)`, the factor by which reading 2 weighs a type above reading 1:

| Group | Draws seen | Reading 1 expects | Reading 2 expects | Reading 3 expects |
|---|---:|---:|---:|---:|
| rho up to 0.6 | 53 | 105.6 (SD 10.0) | **48.7** (SD 6.9) | 41.2 (SD 6.3) |
| rho 0.6 to 0.85 | 6 | 6.5 | 7.1 | 6.6 |
| rho 0.85 to 1.15 | 9,233 | 9,179.9 (SD 92.4) | 9,236.2 | 9,244.3 |

The first group is the hybrid life-and-defence prefix (41 seen; 59.7, 35.0, 27.4 expected) and the three flat elemental damage prefixes of amulets and wands (12 seen; 33.0, 10.5, 10.4): where the top tiers are rare, reading 1 predicts them twice as often as they came. Grouped by the trimming ratio T/K alone, reading 3 misses (not trimmed: 29 seen against 46.8; T/K above 2: 5,153 against 4,974.2) and readings 1 and 2 do not.

### 1.3 What it means

- Reading 2 is the rule the wiki's Foulborn page states ("N/K") and that no test had supported; the datamined tree text (reading 1) and Craft of Exile's code (reading 3) are both beaten, by 77 and 175 log-likelihood units. The tree text describes the Genesis passive, not the strand cut, so the two need not disagree on their own ground; Craft of Exile's Genesis code is moot because the tree is out (ADR-0043).
- The effect of reading 2: a type that loses `T - K` low tiers is drawn `T/K` times as often as its kept weight alone says. A cut therefore helps the top tiers of a common mod type more than reading 1 assumed: by up to a factor `T/K`, whatever the weights of the tiers it lost.
- **The axis `tier_weights` collapses to reading 2** by a claim, `memory_strands.weights_of_kept_tiers` (draft in the claim file). It stays `approximate` (one author's data, no first-party statement). The cost interval over three readings, the "best route without strands" beside it for this axis, and the one-at-a-time sweep of ADR-0042 are no longer needed for it.
- Limits: the fit is on strand cuts of Alteration, Alchemy, Chaos, Exalted, Regal, Foulborn Augmentation and Regal, and identification. Fossils, Harvest and essences are not in the sheet. The Alteration base is a stand-in with the right tags.

### 1.4 A defect found in our pool

Our `T` was one too high for 31 of 1,834 mods of the foulborn tab, and the amulet suffix total was 800 above the sheet's and the emulator's. All of it comes from four mods of the export: `MovementVelocity2Royale` ("Sprinter's"), `IncreasedCastSpeed2Royale` ("of Nimbleness"), `IncreasedAttackSpeed2Royale` and `LocalIncreasedAttackSpeed2Royale____` (both "of Ease"), Battle Royale copies of ordinary tiers at required level 4 or 5 that carry spawn weights on amulets, wands, boots, gloves, weapons and more. The game does not roll them: the sheet's `total_tiers` is exact without them, the sheet's Unravelling weights lack them, and Craft of Exile's amulet total is 125,250. With them left out, `T` agrees on 27,886 of 27,886 mods. In our pool they add a tier to the movement speed, cast speed and attack speed types (so `T` and `K` of the cut, and the tier numbers of `items.tier_table`, are off for them) and 800 to 1,500 to the side totals. The claim draft `affix_pool.royale_duplicates_do_not_spawn` lists the four ids. This is a data fix for the build, not part of the ticket's questions; the acceptance test of ADR-0040 (the sheet's `total_tiers` and `lowest_expected_tier` as a fixture) needs it.

## 2. (b) The spend law

Per craft, the spend `x` is compared with the model "draw U uniformly on 0..C, lose min(U, s)". The test is a quadratic-form chi-square on the counts of the spends in bins (5 bins; 9 for Alteration), with the exact probability of each craft (the censoring at its count included) and the exact covariance of the counts.

| Currency | Crafts (sheet rows) | Strands before (median) | Largest spend | Planned ceiling | Test of uniform | Verdict |
|---|---:|---:|---:|---:|---|---|
| Orb of Alteration | 17,377 | 35 | 8 | 8 | chi-square 4.15, 8 df, p = 0.84 | confirmed |
| Foulborn Orb of Augmentation | 427 | 48 | 32 | 32 | 5.39, 4 df, p = 0.25 | confirmed |
| Foulborn Regal Orb | 64 | 28 | 43 | 48 | 6.19, 4 df, p = 0.19 | consistent |
| Regal Orb | 13 | 82 | 16 | 16 | 8.25, 4 df, p = 0.08 | consistent (13 crafts, one count) |
| Chaos Orb | 155 (615) | 25 | 48 | 50 | 2.75, 4 df, p = 0.60 | uniform |
| Orb of Alchemy | 132 (580) | 42 | 50 | 50 | 3.60, 4 df, p = 0.46 | uniform |
| Exalted Orb, 4 mods before | 41 | 29 | 33 | 32 | on 0..34: 1.09, 3 df, p = 0.78 | ceiling above the plan |
| Exalted Orb, 5 mods before | 43 | 23 | 38 | 34 | on 0..38: 0.59, 3 df, p = 0.90 | ceiling above the plan |
| Scroll of Wisdom | 11 (51) | 82 | 0 | none | | spends none |

- **Chaos and Alchemy are uniform; the bins of ADR-0041 come from counting rows.** The old histograms of 130 (Chaos) and 260 (Alchemy) "uses with at least 50 strands" are rows; they are 33 and 55 crafts. Counted as rows the same data give chi-square 16.0 (p = 0.003) and 36.1 (p = 3e-7); counted as crafts, the 33 Chaos crafts start with spends 12 / 7 / 6 / 5 / 3 in bins of ten (p = 0.23) and the 55 Alchemy crafts 13 / 3 / 13 / 14 / 12 (p = 0.12), and the censored test over all crafts has p = 0.60 and 0.46. A dependence of the Chaos spend on the mods of the result is not visible (mean 20.0 with 4 mods, 18.7 with 5, 15 with one craft of 6). So the claim `memory_strands.spend_law_uniform` replaces the bins. My counts of the old bins differ a little from ADR-0041's (41 / 27 / 29 / 16 / 17 for Chaos against 45 / 27 / 25 / 21 / 12); the conclusion does not depend on that.
- **The Exalted ceiling is a function of the mods after the craft.** The planned table (16, 22, 26, 32, 34 for 1 to 5 mods before) is broken by the data twice: a craft on an item with 4 mods before spent 33 (row 1901: 48 strands to 15) and one on 5 mods before spent 38 (row 1292: 49 to 11). Moving the table by one mod, so that the figures belong to the item as it is after the orb (wiki: "# of modifiers 0 1 2 3 4 5", with the Tainted 6-mod row 38), gives 34 for 4 mods before and 38 for 5, and the spends are uniform on them (p = 0.78 and 0.90). The new table by mods before the craft: 0: 16, 1: 22, 2: 26, 3: 32, 4: 34, 5: 38. The rows for 0 to 3 mods before have no data and are the wiki's figures shifted. The Foulborn Exalted row (ADR-0041: the Exalted row times 62/34) shifts with it: 29, 40, 47, 58, 62 for 1 to 5 mods after, 69 for 6.
- **Identification spends nothing**: 11 of 11 Scroll of Wisdom crafts at 82 strands left the count unchanged while cutting the revealed mods. The wiki's table lists no spend for it either; ADR-0040 calls identification "cut" and ADR-0041 says nothing of its spend.
- The ceilings of Alteration (8), Foulborn Augmentation (32), Regal (16), Chaos (50), Alchemy (50) are all reached or approached and never exceeded. Foulborn Regal's 48 is not reached (largest 43 of 64 crafts) and not contradicted.

## 3. (c) The Orb of Unravelling

One row is one mod of one orb; the 36,598 rows are the 9,373 orbs of the post. Each row's `W_up` and `W_side` are recomputed from our pool (the four Royale mods left out) and compared with the author's columns: `W_up` equals his on 36,597 of 36,598 rows; `W_side` equals his on every row of every base except wands, where it differs on 8,655 of 8,702 rows because his sums lack the 0.5 weight of attack mods on wands (he found that later, the sheet was not recomputed).

### 3.1 The chance

With `x = s W_up / (2 W_side)` from our weights, the observed share of raised mods follows `min(1, x)` in every bin:

| x from | Mods | Raised | Predicted |
|---:|---:|---:|---:|
| 0 | 823 | 2.92% | 2.87% |
| 0.05 | 950 | 8.11% | 7.49% |
| 0.1 | 2,011 | 15.32% | 15.32% |
| 0.2 | 1,897 | 25.41% | 25.18% |
| 0.3 | 2,073 | 34.39% | 35.37% |
| 0.4 | 1,673 | 46.56% | 45.63% |
| 0.5 | 1,844 | 54.18% | 55.47% |
| 0.6 | 1,748 | 65.33% | 65.98% |
| 0.7 | 1,553 | 74.82% | 75.83% |
| 0.8 | 1,473 | 85.61% | 85.62% |
| 0.9 | 964 | 93.05% | 92.73% |
| 0.95 | 3,507 | 98.35% | 98.34% |

- `p = min(1, a x)`: a = 1.0011 (SE 0.0005); `p = 1 - (1 - x)^k`: k = 0.992; `p = min(1, a s^b r^c)` with r = W_up / (2 W_side): a = 1.0012 (SE 0.0017), b = 1.0000 (SE 0.012), c = 1.0000 (SE 0.012). Forty free bins of x give -9,152.4 against -9,163.8 for the formula, 11.4 for 39 parameters: no sign of a different curve. The mods on the item (1, 3, 4, 5, 6) do not change the rate.
- The breakpoint: all 12,201 mods with x of 1 or more were raised; none of the 3,881 mods already at the top tier was. Among the 3,507 mods with x from 0.95 to 1, 58 were not raised (1.65%; the formula says 1.66%); the largest x of a mod not raised is 0.9946.
- **The author's own columns** (his weights) give the curve he worried about: `p = min(1, x)` is 195.8 log-likelihood worse (-9,359.7), the free exponent of the concave family 1.09 (k), and the excess of observed over predicted of 3 to 5 points in the middle bins. On the 27,896 mods that are not on wands his columns and ours fit the same (a = 1.0011 for both). The "not sure it is linear" of the post was the wand sums.
- Verdict: **settled** for the five classes in the data (amulets 24,698 mods, wands 8,702, rings 2,924, gloves 197, body armours 77). The claim `memory_strands.unravelling_chance_model` loses `approximate`; its statement names the classes.

### 3.2 The destination

For the 23,494 mods that rose, the destination among the tiers above (those the pool allows at the item level):

| Reading | Log-likelihood | |
|---|---:|---|
| A: rank multipliers (ADR-0044's plan) | -29,706.9 | |
| B: cumulative (own weight plus the weights above) | **-29,691.9** | |
| C: weights only | -31,924.9 | |
| D: uniform | -32,809.9 | |

- **The rank step is exact.** With a rank power g on equal weights the log-likelihood peaks at g = 1.00 (0.75: -125.8, 1.25: -102.5 against 1). On the mods whose candidate weights are all equal (A and B are the same there), the shares follow 1:2:3:... from the top for every candidate count from 2 to 12: eleven chi-square tests with p between 0.078 and 0.95. Weights are used (C is 323 below A on the unequal ones).
- **A against B.** They differ only where the candidate weights differ: 4,354 mods (1,790 on amulets, 2,475 on wands, 89 on rings). B minus A is +14.9 (SE of the sum 8.0). That sum alone is hard to read, so the same mods were replayed 4,000 times from each reading: if A is true the difference is -31.6 (SD 8.0) and the observed +14.9 is 5.8 SD above it (none of 4,000 replays reached it); if B is true it is +32.1 (SD 8.0) and the observed +14.9 is 2.1 SD below it (1.5% of replays). **A is rejected; B is not rejected at 1% but sits short of its own expectation.** The best mixture of the two puts weight 0.73 on B (95% 0.49 to 0.98). The post's wand test favours A on its 257 mods (chi-square 0.63 for A, 4.35 for B); the mods that favour B are spell damage on weapon (+4.0) and mana on weapon (+3.3), also wand mods. A third reading between A and B would fit best; none is known.
- **Not cut by the strands.** 10,721 of the 23,494 raised mods went to a tier a cut at the item's count would have removed.
- Verdict: **narrowed.** The axis `unravel_destination` collapses to B (claim `memory_strands.unravelling_destination_tier`, `approximate` with the reason above); reading A leaves the model. The wand test numbers of ADR-0044's "Tests that are published numbers" (2.03 / 16.89 / 81.08 under A) become the numbers under B (4.05 / 20.95 / 75.0, observed 2.72 / 16.73 / 80.54) with the SD above beside them.

## 4. (d) Does Remembrance depend on the old count?

The tab "remembrance data" is one column of the 2,255 counts after each orb, in the order of use, with the author's summary cells (mean 41.56, quartiles 26, 39, 55). It does not record the count before. Taken as consecutive orbs on one item (the post's talisman "rolled to 100 with orbs of remembrance" is that), the previous row is the old count: correlation of each row with the one before 0.017 (permutation p = 0.41, 95% half-width 0.041), slope 0.017 (SE 0.021), chi-square of independence on 3 by 3 bins 2.0 (4 df, p = 0.73), next result after a result below 25 averaging 40.6 (501 rows) against 41.9 after one of 50 or more (746 rows), z = 1.2; lag 2: 0.009. A result that depends on the old count by more than about 0.04 in correlation is excluded.

**Verdict: narrowed, not answerable strictly.** If the rows are consecutive orbs on one item there is no dependence; the sheet does not say so, and a sample of orbs on different items would say nothing. The claim `memory_strands.remembrance_independent_of_old_count` states it with that condition and stays `approximate`.

The shape of the count was checked again under five ways of cutting and rounding a normal(35, 25) (ADR-0043 takes accept 10 <= x < 100.5, round): the maximised log-likelihoods are -9,701.2 to -9,702.7 for the four that allow a result of 100 and -11,750.0 for the one that cuts down at exactly 100, so only "no 100 at all" is excluded. The count at 10 (20 seen) is 13.2 expected for a half cell at 10 and 25.9 for a whole one. **Not answerable:** the choice of bounds and rounding is open within about 2 log-likelihood units and stays `approximate`; the mean and the chi-square of `N(35, 25)` hold in all of them (6.8 to 7.3 on 17 df).

## 5. (e) Foulborn on a 0-strand item

None of the 491 Foulborn crafts (427 Augmentation, 64 Regal) starts at 0 strands; the fewest strands before is 1, 18 crafts have 5 or fewer and 42 have 10 or fewer. A second Foulborn use after the first emptied the item does not occur. **Not answerable from the sheet.** The wiki's list of kept tiers (1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7 for 1 to 13 tiers, which fixes `D = 175`) stays the only basis of the 0-strand case, `approximate`. What the sheet does settle is the size of the bonus on an item with strands (section 1.1).

## 6. The axes, in one place

| Axis | Readings (ADR) | After this research |
|---|---|---|
| `tier_weights` | redistribution, refactored, delete only (ADR-0042) | **collapses to refactored** (reading 2); no interval |
| `unravel_destination` | rank multipliers A, cumulative B (ADR-0044) | **collapses to B**; A leaves; `approximate` stays |

The strand axes then multiply with those of B3 (five for the recombinator exponent, two for the Awakener) as 1 x 1 x 5 x 2, far inside the ceiling of 24 that ADR-0042 sets.

## 7. What changes in the project (for the main chat to take or leave)

- **ADR-0042**: the plan reading becomes reading 2 (refactored weight) and the three-reading table, the answer's interval and the "evidence that could still collapse it" section are closed by this note. The pool signature sentence ("under reading 1 a family's total weight is unchanged") turns round: the share of a family in its side changes with the cut class, and the kernel tables are keyed by cut class and `T/K` alone.
- **ADR-0041**: Chaos and Alchemy use the uniform law (the "two currencies fail the test" paragraph goes); the Exalted row is indexed by the mods after the craft; identification spends 0; the Alteration, Foulborn Augmentation and Regal ceilings are confirmed.
- **ADR-0044**: the chance formula is confirmed and loses `approximate`; the destination is reading B; the axis `unravel_destination` goes; "the destination is not cut" is confirmed by data.
- **ADR-0040**: the cut and the Foulborn `+75` are confirmed on 27,886 mods (T agrees on every one once the four Royale mods are out). The acceptance fixture needs the pool fix of section 1.4.
- **Build tickets** (from the resolution of #103): B5-2 needs the Royale fix and builds only reading 2; **B5-7 ([#280](https://github.com/Rasslabsya4el/crafting-system/issues/280)) loses its main content** (no `tier_weights` axis, no interval for it), what remains is the report line for the approximate inputs; B5-3 takes the uniform law and the Exalted shift; B5-5's test "chi-square of the 91-probability table against the 2,255 results" is unchanged; B5-8 ([#281](https://github.com/Rasslabsya4el/crafting-system/issues/281)) takes reading B and the exact chance.
- **Claims**: nine drafts in [`2026-11-01-strand-sheet-claims/`](2026-11-01-strand-sheet-claims/): `weights_of_kept_tiers` (new), `spend_law_uniform` (new, replaces the bins), `spend_exalted_by_mod_count` (changed), `identification_spends_none` (new), `unravelling_chance_model` (changed), `unravelling_destination_tier` (changed), `unravelling_destination_not_cut` (new), `remembrance_independent_of_old_count` (new) and `affix_pool.royale_duplicates_do_not_spawn` (new). They replace the older drafts of the same id in `2026-10-31-memory-strands-claims/`.

## 8. What the sheet cannot answer (for the main chat)

None of these gates a plan; each has the default named, and the planner already runs on it.

1. **Foulborn on a 0-strand item** (section 5): default `D = 175` from the wiki's list, `approximate`.
2. **Remembrance and the old count** (section 4): default independent, now with the sequence test behind it; the sheet cannot tell consecutive orbs on one item from orbs on different items.
3. **Exalted ceilings for 0 to 3 mods before** and for the **Foulborn Exalted Orb** at any count: default the wiki's figures shifted by one mod, Foulborn scaled by 62/34; no sheet row.
4. **Unravelling on classes and mods outside the data**: jewels, belts, boots, helmets, weapons other than wands; fractured, veiled, desecrated, enchanted mods and influenced mods near their elevated form (ADR-0044 excludes them, `approximate`). 91% of the data are amulets and wands.
5. **Which draws are cut at all** (fossils, Harvest, essences, Vaal, recombinators): the sheet holds none; ADR-0041's inference stands.
6. **The bounds and rounding of the Remembrance normal** (section 4): within 2 log-likelihood units.
7. **Transmutation and Augmentation without Foulborn** spend 0 to 8 by the wiki; only Alteration (same ceiling) and Foulborn Augmentation are in the sheet.

Lines for the owner's in-game list ([#182](https://github.com/Rasslabsya4el/crafting-system/issues/182)), optional and none urgent, are posted there as a comment: items 1, 2 and 3 above (the tooltip of a plain Exalted Orb on items with 1 to 3 mods is free to read), and the one place where Craft of Exile's code disagrees with the fit (it deletes low tiers and keeps weights, the sheet rejects that by 175 log-likelihood units; it matters only for its Genesis rating, which is out of scope, so it needs no check).

## Reproduce

```
python research/271/fetch_sheet.py RAW_DIR                                   # the five tabs as CSV
python research/271/fitpool.py   RAW_DIR CACHE_DIR research/271/fit_pool_result.json
python research/271/spend.py     RAW_DIR research/271/spend_result.json
python research/271/unravel.py   RAW_DIR CACHE_DIR research/271/unravel_result.json
python research/271/remembrance.py RAW_DIR research/271/remembrance_result.json
```

`CACHE_DIR` holds the pinned export (`python -m crafting_system.data fetch`); the scripts need numpy and the project on the path. The raw CSV files (65 MB for the Unravelling tab) are not kept in the repository. The result files in `research/271/` are the output of these commands. A full run takes about ten minutes of one core; the claims were checked with `load_registry(Path("docs/research/2026-11-01-strand-sheet-claims"))` (9 rules load; the longest quote is 258 characters).

## Limits

- One author's sheet, in one league (3.29.0); the post's last numbers are from 2026-09-27. No 3.29.x note read changes strands or Unravelling.
- The Alteration tabs do not name a base; a stand-in with the same tags was used, and the item level is the tab's lower bound. The agreement of `T` with the sheet's `total_tiers` on every mod shows the pools are alike where it matters.
- The probability model for Alchemy, Chaos and the Scroll of Wisdom assumes sequential draws with the pool of the pre-craft count; the readings are compared on the same assumption, so a different order of draws would shift them alike.
- The destination analysis uses our weights, which agree with the author's on `W_up` in all but one row; the wand weights carry the 0.5 factor.
