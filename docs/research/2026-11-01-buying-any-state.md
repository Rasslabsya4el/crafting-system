# Can the planner choose what to buy, and how is a bought state priced

Research ticket [#337](https://github.com/Rasslabsya4el/crafting-system/issues/337), written 2026-11-01 against patch 3.29.3.3 and the Allflame league. Related: ADR-0007, ADR-0008, ADR-0009, ADR-0011, ADR-0022, ADR-0031, ADR-0033, ADR-0035, ADR-0043, [#102](https://github.com/Rasslabsya4el/crafting-system/issues/102) / [#329](https://github.com/Rasslabsya4el/crafting-system/issues/329) / [#330](https://github.com/Rasslabsya4el/crafting-system/issues/330) (vendor recipes), [#211](https://github.com/Rasslabsya4el/crafting-system/issues/211) (donors), [#312](https://github.com/Rasslabsya4el/crafting-system/issues/312) (exact merging), [#323](https://github.com/Rasslabsya4el/crafting-system/issues/323) (user inputs), [#325](https://github.com/Rasslabsya4el/crafting-system/issues/325) (map v2).

The owner narrowed the question while this note was written (main chat messages of 2026-11-01): the general "buy any compressed state" mechanism is a v2 hypothesis, and v1 may hold only simple cases that need no per-state trade query, each decided on cost, query count and how sure we are that the item exists to buy. The note is in three parts in that order (sections 1, 2, 3), then the recommended design and the questions (sections 4, 5). Section 6 maps every point of the issue to a section; section 7 lists the sources and what was not found. Scripts: `2026-11-01-buying-any-state-checks.py` (small checks and the trade probe), `-count.py` (the buy-key count on the three routes, run on GitHub), `-ilvl.py` (the three routes planned at several item levels, run on GitHub).

## Answer in brief

1. **The start base, its item level and its influence can be chosen from one bulk fetch, with no trade query.** poe.ninja's `BaseType` list has 8,977 rows for Allflame today, one per base, item level 82 to 86 and influence set; 3,054 have the 5 observations the price rule needs. It has no row for a fractured, synthesised or corrupted base and nothing below level 82. Offering a start only when such a row exists is realistic by construction as far as the base goes (a row is not proof of an instant-buyout listing, section 1.2) and costs nothing at plan time. The item level the target needs is a **floor**, and it is lower than the target files say: R13 and R08 both need only 84 (tier-1 Fire and Cold Resistance, tier-1 Energy Shield), not 86. That gives each of them **two extra plans** (levels 84 and 85 against 86). Planned at those levels (GitHub run 41335111645, `-ilvl.py`): R13 costs **5,492 Chaos at level 84** (start 1.7 plus 5,490.5), 5,638 at 85 and 6,311 at 86, so the file's level costs **819 Chaos, 13%**, and almost all of that is the smaller pool, not the base price (1.7 against 10 Chaos). R08 costs 77.2, 81.5 and 83.7 Chaos at 84, 85 and 86 with poe.ninja's base prices (106.0 at 86 with the trade price in the fixture). R05 moves by 2%.
2. **The recombinator trick for item level does not pay on the three routes, and can pay only marginally elsewhere.** The output level cannot exceed the higher input, so one input must already be as high as the target needs; the second base, two magic upgrades and one combine (about 7 Chaos) are extra cost, and the output base is either input at random. No mod that can spawn needs a level above 86 (section 1.4, case 1).
3. **A fractured base with one wanted fractured mod is the one simple case that needs the trade API, and it is worth a query only where the route can use it.** A candidate costs 2 requests plus one for the stat list on a cold cache. On R08 it is the biggest saving found: a rare Sorcerer Boots with a fractured tier-1 Energy Shield % has 122 listings at item level 84 and up (14 at 86 and up), the five cheapest average 6.6 Chaos, and the solved graph says a boots with that mod costs 4.0 Chaos more to finish at best (probably the bench Movement Speed craft; I did not check its price; the graph's states with that mod range from 4.0 to 76.2 depending on the boots' other mods), about 10.6 in all at best against 77.2 to 106.0 for the plan from a bare base. On R13 it is worth nothing: the route has no Scouring or Chaos Orb, so a rare belt is a dead end whatever it carries. On R05 the start is already a fractured ring (602 listings, 2.6 Chaos). A normal or magic base with one wanted mod has no bulk source, 2 magic belts with tier-1 Life are for sale at level 86 and up, and on R13 such a belt saves 5.1 Chaos of 6,311, so it stays out of v1.
4. **How many wanted mods a bought rare may carry is not a fixed number; it is a stock count that moves with the item level floor, the base and the league.** On Leather Belts, rare, instant buyout: tier-1 Life alone has 255 listings at item level 86 and up, tier-1 Life and Fire Resistance 39, and with Cold Resistance 3. At the real floor of 84 the same three-mod belt has **117 listings, the five cheapest averaging 11 Chaos**, against 6,311 Chaos for the planner's craft on R13. The owner's "two yes, three no" is not borne out for this belt and this league; the item-level floor matters more than the mod count. The test that works is a listing count from one search request.
5. **The value of a bought item is concentrated in the states close to the goal, and the route decides which.** On R13 a magic belt with tier-1 Life saves 5.1 Chaos of 6,311, and every rare belt that is not nearly finished is worth nothing (no Scouring Orb, so a rare with junk restarts at 6,311); only 45 of 240 buy keys cost less than the plan, and the large gain (11 Chaos for a belt with the three mods against 6,311) is in the nearly finished item, the owner's v2 case (the price does not include the finishing bench craft, and whether the belt has an open affix for it is not known). On R08 every state costs the same 76 Chaos until the Energy Shield is in, and then 4.0 at best (up to 76.2 when the boots' other mods block the finish): one mod, the fractured-base case above, is where the money is. So whether a one-mod purchase pays depends on the route's actions and the mod, which is why the candidate list needs a bound, not a rule.
6. **The general mechanism has one simple core: a bought item replaces the one in hand, so every buy offer is a reset to a priced state and the family collapses into the cost `B` of the best reset;** `restart` (ADR-0011) is the case with one candidate. Lazy generation needs few queries on the three routes only if a bound on the finishing cost exists (18 to 24 queries on R13 at the measured price growth with the best possible bound, all 240 without one), and ADR-0031's bound exists for erasing rerolls, not for R13's Augmentation and Regal route (sections 3.3 and 3.4). But it needs a trade query per candidate state, which GGG's developer documentation does not support as an automated, unattended use. That is why it is v2.

The recommended v1/v2 split is in section 4, the owner's questions in section 5.

---

## 0. What exists today

- A target names a concrete start item; its price is the name under `start_price` in the price file (ADR-0008). The only buy action is `restart`, `BuyStartItem`, which buys that same item again at every state (`cli/_offers.py`; `cli/_plan.py` adds `Offer(RESTART, BuyStartItem(target.start_item), ...)` priced with the start item).
- A start item is priced from poe.ninja (bases, per item level and influence: `Leather Belt (ilvl 86)`) or by the trade API for a buy spec (`prices/trade_pricing.py`: the stat list once a week, one search, one fetch of up to 10 listings, the mean of the 5 cheapest instant-buyout listings, at least 3 usable, cached 24 hours per query and 7 days in the price file; the request budget of a run defaults to 4). ADR-0007 fixes that the trade fetcher runs only when the owner starts it, and that the solver reads only a dated local price file.
- The query model (`prices/trade_query.py`) writes: base type or category, rarity, item level min and max, corrupted and mirrored, `fractured_item`, stat filters with a minimum, the six influence pseudo stats, the listing status (`securable` = instant buyout, the default since #133) and the listing age. The rate limiter (`prices/trade_http.py`) reads the `X-Rate-Limit-*` headers of every response, waits, stops on 401, 403, 429 or a Cloudflare page, and bounds a run by a request budget. This note cites that limiter and does not re-research it.
- ADR-0043 already has one planner-chosen buy: a purchase with a minimum Memory Strand count, where the planner does not ask for all 100 counts and offers only the counts at which a cut class begins, which is "a choice of which prices to fetch". ADR-0049 (quality) and ADR-0053 (the extra crafted slot) follow the same line: quality is bought as currency, the extra slot only as a start item that already has it, priced from the trade. The pattern recommended below is the same: a short candidate list that the target itself fixes, priced through the price file.
- The compressed state (ADR-0009) already separates what a buy could name from what it could not: flags (rarity, influences), fractured mods, one status (absent, below, passing) per target leaf, and the other mods as slots (junk, kept only when an enabled action reads it). Item level is not a state field: the abstraction is built for one item level (`cli/_plan.py`).

---

## 1. The v1 slice: choose the start base, item level and influence from one bulk fetch

### 1.1 What poe.ninja's base list covers

Source: `GET https://poe.ninja/poe1/api/economy/stash/current/item/overview?league=Allflame&type=BaseType`, read once on 2026-11-01 (4.09 MB; the documented endpoint of https://poe.ninja/docs/api; the repo reads it in `prices/ninja_items.py`). Counted by the `ninja` check of `docs/research/2026-11-01-buying-any-state-checks.py` over the saved answer.

| Question | Answer |
|---|---|
| Rows | **8,977**, 830 distinct base names. A row is one base at one level and one influence set. |
| Fields of a row | `id`, `name`, `icon`, `levelRequired`, `variant` (only when influenced), `itemClass`, `itemType`, `sparkLine`, `chaosValue`, `exaltedValue`, `divineValue`, `count`, `listingCount`, `detailsId`. The answer has no other top-level key. |
| Item levels | **82 to 86 only**: 707, 1,331, 1,388, 3,308 and 2,243 rows. Nothing below 82 and nothing above 86. The level field is `levelRequired`; the repo reads it as the item level (`base_price_name(name, level, influences)`). |
| Influences | Plain 3,083 rows; the six single influences Shaper 1,597, Elder 1,342, Hunter 708, Warlord 624, Redeemer 593, Crusader 595; 15 variant strings of two influences (431 rows; the order of the two names varies) and one string that names all six (4 rows). |
| Fractured | **No row.** No string of any row mentions it. A fractured base cannot be priced from this list. |
| Synthesised | **No row.** (Same check. Synthesis can no longer be crafted in 3.29 and B4 dropped it, ADR-0013, so a synthesised start is out of v1 anyway.) |
| Corrupted, quality, sockets, mods | None. A row is the base alone. |
| Enough observations | `count` is the number of observations behind the price. With the repo's rule (`MIN_COUNT = 5`, ADR-0007) **3,054 rows** are priced: 1,920 plain, 1,134 influenced. 5,923 rows are too thin. 123 priced rows are above 1,000 Chaos (a few observations of mirror-tier bases). |
| Freshness | The response carries `Cache-Control: public, max-age=1800` (seen 2026-11-01). The poe.ninja documentation says responses are HTTP-cached for roughly 5 minutes (ETag), that PoE 1 overviews refresh about every 15 minutes, and that clients making excessive use of the economy endpoints are blocked; it asks for a descriptive User-Agent with a contact and gives no numeric rate limit. The two cache figures disagree (5 and 30 minutes); neither matters for a price file that is allowed to be 7 days old (ADR-0007). |
| History | `GET .../stash/current/item/history?league=...&type=BaseType&id=<row id>` (undocumented, used by `prices/ninja_history.py`) returns 100 daily rows `{count, value, daysAgo}`. For the plain item-level-86 Leather Belt: `count` 14 on day 99, 399 at the samples of days 89, 79, 69 and 59 (it looks capped there), 262 on day 49, 61 on day 19, 37 today; `value` 2.0, 10.0, 20.0 (day 69), 5.0 (day 29), 10.0 today. A row's observation count moves by an order of magnitude inside one league. |

Second bulk source: poe.watch `GET https://api.poe.watch/get?category=bases&league=Allflame` (12 MB, 20,655 rows, read by `prices/poe_watch.py`). It has `itemLevel` 83 to 86 (4,202, 4,019, 6,164, 5,726 rows) and one anchor row each at levels 1, 50, 68 and 75 (136 each), an `influences` string with single and dual sets, an integer-rounded `mean` and a `lowConfidence` flag (6,814 rows are low confidence), and `explicits` and `implicits` that are empty on every row. So it adds levels 68 and 75 and a second opinion, not fractured or mod information. The repo already treats poe.ninja as the primary and poe.watch as a fallback (ADR-0007).

Craft of Exile's market data (the local copy under `.claude/scratch/coe/`, git-ignored; only its shape is described here, no code): the price file `poec_prices` holds, per league, the sections `currency` (102 lines), `fossils` (25), `resonators` (4), `essences` and `beasts` (empty) and `harvest` (null). **It has no base, no rare and no item-state price.** Its numbers are also not current: its Divine Orb is 104.9 Chaos against 383 on poe.ninja today, so this note uses it for nothing but its shape.

### 1.2 "Realistic by construction", and what it does not guarantee

A start option is offered only if a bulk row lists it: the target's base (the target already fixes the base), an item level 82 to 86 and an influence set that the row names, with `count` of at least 5. If the list has no row, the option does not exist for the planner: no guessing, no price, no query. Three things stay true about such a row:

- It prices **a base**, not a rare. The planner models the start as a normal or rare item with the mods the target or the route says (ADR-0008; R08's rare boots with no mod), and the price is the price of the base. That is the existing convention.
- **A row does not prove an instant-buyout listing exists.** The trade site's count for the plain item-level-86 Leather Belt is 15 instant-buyout listings (one search, rarity normal, item level 86 and up, 2026-11-01; 148 at 84 and up), against 1,168 `listingCount` and 37 `count` in poe.ninja's row. The two measure different things, and I did not find which of poe.ninja's listings are priced buyouts. The owner's rule is instant buyout (#133). So a bulk row is an offer that is cheap to make and weakly tied to that rule; closing the gap costs one search request per option (the `total` only, no fetch). Whether v1 accepts the row as a proxy or requires that check is an owner question (section 5, question 3).
- **A row's coverage and price move, and the two sources can disagree.** The R08 start item shows both. When R08's buy spec was written (2026-10-31) poe.ninja listed no plain Sorcerer Boots above item level 82 (2 observations), so the start was priced from the trade API: a normal item level 86 base at 29.8 Chaos (22 instant-buyout listings, 2026-11-01), against R09's 5.0 Chaos for another boots base (37 listings). Today's poe.ninja has a row for Sorcerer Boots at 86: 7.4 Chaos, 32 observations, about a quarter of the trade figure. Either the row is cheaper because it counts non-buyout listings, or the market moved in a day; I cannot tell which. A bulk row is therefore a cheap, query-free offer and a lower-confidence price: the report names its source and observation count, and a trade-priced figure covers the name where both exist (ADR-0007 already lets a trade price cover a name).

### 1.3 How many extra plans a target adds, and what they are worth

A plan differs between two start options only through (a) the pool of mods the item level opens, (b) the influence set, and (c) the price. Item levels that open the same pool are one plan, priced at the cheapest row that is at least the lowest level of the group. The target's item level is not the floor: it is whatever the author wrote, and the floor is the lowest level at which every leaf can be met. Tiers are absolute (`tier_table` is per base, not per level), so the floor follows from the tiers the target asks for. In the pinned data (the `pools` and `leaves` checks, and the tier table of the three bases):

| Route | Base | What fixes the floor | Floor | Pool groups from the floor to 86 | Plain rows with `count >= 5` (price, observations) |
|---|---|---|---|---|---|
| R13 | Leather Belt | tier-1 Fire and Cold Resistance `+(46-48)%` need level 84; tier-1 Life `+(130-144)` needs 64 | **84** | 84 / 85 / {86 to 100} | 84: 1.7 c (176); 85: 1.0 c (275); 86: 10.0 c (37) |
| R08 | Sorcerer Boots | tier-1 Energy Shield % needs 84; the Movement Speed leaf accepts a bench craft (level 68) beside the rolled 35% (level 86) | **84** | 84 / 85 / {86 to 100} | 84: 1.0 c (36); 85: 5.3 c (84); 86: 7.4 c (32) |
| R05 | Amethyst Ring | the start is a fractured ring (trade-priced, section 1.4 case 2); the plain ring only sets the pool | 75 (guide) | {82,83} / 84 / {85 to 100} above 81 | 5 plain rows, 82 to 86 |

So the benchmark routes **do** offer a choice: R13 and R08 each add two plans (84 and 85) next to the one the target file fixes (86). A plan at a lower level has a smaller pool (R13: 137 mods at 84, 139 at 85, 141 at 86), which cuts junk and raises the chance of a wanted mod, so the planned cost can fall as well as the price. The run planned each route at those levels (the target file with its `item_level` changed, poe.ninja's base prices as the start price, everything else as the fixture; R05 keeps its fractured ring at 2.6 Chaos):

| Route | Item level | Start price | Mean cost from the start | Total | Against the file's level |
|---|---|---|---|---|---|
| R13 | 84 | 1.7 | 5,490.5 | **5,492.2** | -818.6 (-13.0%) |
| R13 | 85 | 1.0 | 5,637.2 | 5,638.2 | -672.6 (-10.7%) |
| R13 | 86 (the file) | 10.0 | 6,300.8 | 6,310.8 | |
| R08 | 84 | 1.03 | 76.20 | **77.22** | -6.4 (-7.7%) against the 86 row; the 27% (-28.8) against the fixture's trade-priced start compares two price sources |
| R08 | 85 | 5.33 | 76.20 | 81.53 | -2.1 |
| R08 | 86 (the file) | 7.43 | 76.22 | 83.65 | (106.05 with the fixture's trade price, 29.8 + 76.2) |
| R05 | 75 / 82 / 84 / 86 | 2.6 | 9.61 / 9.59 / 9.46 / 9.44 | 12.2 / 12.2 / 12.1 / 12.0 | within 2% |

On R13 a lower level is worth 13% in the plan itself (the pool shrinks from 141 mods to 137; the mods of levels 85 and 86 that leave it presumably dilute the wanted ones, but I did not isolate the cause), and the base is 8 Chaos cheaper besides; on R08 the plans differ by 0.03% and the whole gain is the base price. So the choice of level is a real saving on R13 and a price effect on R08, and it needs a plan per level (per level on the runner: R13 7 to 8 s, R05 18 to 19 s, R08 106 to 151 s; three R08 levels are about six minutes, against the owner's wish for an exact answer in about a minute, #81). The prices are poe.ninja's rows of 2026-11-01; the R08 row is the doubtful one (section 1.2).

Influenced rows add plans only where the target needs an influence mod; the comparison there is large:

| Route to an influenced item | Price today |
|---|---|
| Influenced base row, Leather Belt ilvl 86 | Shaper 4.2 c (13 obs), Elder 5.0 c (20 obs); Crusader (2 obs), Redeemer (1 obs), Hunter (3 obs) are too thin; no Warlord row at 86 |
| A conqueror Exalted Orb on a plain base (poe.ninja Currency overview, read 2026-11-01) | Redeemer's 134.3, Elder's 136.8, Shaper's 200.4, Crusader's 383.0, Warlord's 395.4, Hunter's 477.6 Chaos (Divine Orb: 383.0) |

An influenced base at 4 to 5 Chaos is 27 to 48 times cheaper than a conqueror Exalt where a priced row exists, and where no row has 5 observations the conqueror route is the only one. The solver needs no new action for this; it is a different start item priced like today's. Planning several options is not free of change, because the item level is fixed per abstraction (section 0): each level or influence set is its own plan, the cheapest total wins, and each plan restarts to its own start (an upper bound on the joint optimum; section 3.2).

### 1.4 The three simple cases, one by one

#### Case 1. The base and its item level, including the recombinator trick

- **Price source.** poe.ninja `BaseType` (section 1.1), with poe.watch as the fallback already in the fetcher. **Trade queries per plan: 0.**
- **Realism test.** A row with `count >= 5` at the wanted level and influence set (3,054 of 8,977 rows pass today); optionally one search `total` (section 1.2).
- **The trick.** ADR-0033: the output item level is `min(floor((A+B)/2 + 2), max(A,B))`, both inputs magic or rare of one item class, neither corrupted, and the output base is either input with probability 1/2. The output never exceeds the higher input. So reaching level `N` needs an input that is already at least `N`, and that input could be the start item itself. The second input then only needs `A + B >= 2N - 4`. A pair costs the high input, the low input, two Transmutations to make plain bases magic, and one combine at about 7 Chaos (ADR-0035), and the output has the target's base only half the time. On R13 (Leather Belt at 86: 10 Chaos; at 82: 1 Chaos) that is at least 18 Chaos, and about 36 with the base lottery, for an item the 10 Chaos row already is. It can pay only where the high-level copy of the target's own base is scarce and a different base of the same class at that level is cheap: to reach level 86 for R08's boots, Sorcerer Boots 84 (1.0 c) plus Two-Toned Boots 86 (5.0 c) plus a combine is about 13 Chaos, 26 with the base lottery, against the 29.8 Chaos trade price of the start at 86; but R08's floor is 84, where a 1.0 Chaos Sorcerer Boots row exists and the trick has nothing to save. The owner's example (an item level 80 and one of 90 giving 87) works arithmetically (`floor(min(87, 90)) = 87`) but needs a level 90 item that neither bulk source lists. The formula agrees with the community threads the GPT researcher found (Reddit, September 2024 to April 2026: average plus two, never above the higher input, unpredictable recombinator only).
- **Does any mod need more than 86?** I checked every mod of an item domain with a positive spawn weight in the 3.29.3.3 data: the highest required level is **86** (21 mods), so on the three benchmark bases the pools at 86, 87, 88, 90, 95 and 100 are identical. There are 142 item-domain mods that need level 87 to 95, all with spawn weight 0 (for example the Maven-tier `...UberMaven` mods); no random pool draws them, and 113 of them are in the elevated-mod mapping (`src/crafting_system/data/elevated.json`, ADR-0030) that the Awakener's Orb uses (ADR-0032). ADR-0032 states only a floor of 68 on the inputs; whether the level of an elevated mod gates the result is not in that ADR and I did not check it. So no random pool changes above 86, and no target that is built from drawn mods can ask for level 87.
- **Decision.** v1: choose the base level and influence from the list; **do not offer the recombinator as an item-level source** (it is dominated on every price I have, and ties at best). Its other use, combining the mods of two donors, is #211 (section 3.2).

#### Case 2. A fractured base with one wanted fractured mod

- **Price source.** The trade API only (a fractured base is in no bulk list). The query exists: `fractured_item: true` plus a `fractured.stat_*` filter with a minimum roll (the R05, R10, R11 and R12 start items were priced this way and recorded, `tests/fixtures/trade/recorded/start_items/`).
- **What exists today** (search `total` of the recorded runs of 2026-10-31, instant buyout, any listing age): R05 ring, fractured all attributes 13+, item level 75+: **602** listings, 2.6 c (mean of the 5 cheapest); R10 Sorcerer Boots, fractured Movement Speed 30+, item level 84+: **156**, 17 c; R11 Lion Pelt, fractured Chaos Resistance 31+: **42**, 20 c; R12 amulet, fractured Lightning Resistance: **909**, 1 c. New today, for R08's base: a rare Sorcerer Boots with a fractured tier-1 Energy Shield % (92+) has **122** listings at item level 84 and up and **14** at 86 and up; the ten cheapest at 84 and up cost 4, 5, 6, 8 and 10 Chaos (six times), listed between 2026-08-03 and 2026-09-25 at item level 84 or 85, so the mean of the five cheapest is 6.6 Chaos. For R13's base: a rare Leather Belt with a fractured tier-1 Life (130+) has **77** listings at item level 84 and up and **3** at 86 and up; at tier 2 or better (115+) and 86 and up, 9 listings with the cheapest at 1, 15, 20, 25, 44, 45 and 99 Chaos and 1 Divine twice (mean of the five cheapest 21 Chaos; 1 Divine = 383 Chaos today).
- **Against making it.** A Fracturing Orb costs 264.8 Chaos today (poe.ninja Currency overview; 260.4 in the price file of 2026-10-31) and fractures one random mod of an item with 4 or more mods, so a given wanted mod takes four orbs or more on average and the item is lost on a miss. A fractured base at 1 to 21 Chaos (R08's Energy Shield boots 6.6) is 12 to 260 times cheaper than one orb. Reddit (reported by the GPT researcher, not opened by me): the common advice is to buy a fractured base on the trade site and finish it with essences, reforges or fossils (r/PathOfExileBuilds, 2024-09-22 and 2025-11-18); one poster priced a fractured +1 arrow quiver at 30 Divine against 3 Divine for an almost perfectly rolled alternative, and argued against buying it (r/pathofexile, 2023-09-24); another regretted a 60 Divine boot craft and wrote he should have bought the fracture (2024-08-06).
- **Does the route use it?** A fractured start pays only where the route's actions can rework a rare item. R13 offers Transmutation, Alteration, Augmentation, Regal, the bench and Remove Crafted Mods (no Scouring, no Chaos), so every rare belt in its solved graph that is not nearly finished is a dead end valued at the restart cost, 6,310.8: a fractured rare belt gains nothing and its queries are wasted. R08 (fossils, bench) and R05 (essences, bench, a fractured ring already) can use one. The 10.6 Chaos for R08's boots (6.6 plus 4.0) is a best-case estimate, because the graph's states with the Energy Shield passing range from 4.0 to 76.2 Chaos by the boots' other mods, and the estimate is also not a plan started from the bought boots: 4.0 is the lowest solved value of the graph's states with the Energy Shield passing and no Movement Speed; a bought boots would also carry the fractured flag and its own other mods. So the candidate list must be cut by the route before any query. The cut is the bound below or, cheaper, the rule "some offered action rerolls a rare item".
- **Candidates and queries per plan.** The candidate fractured mods are the stat texts of the target's leaves that the base can roll; I counted them from the pool and the leaves (the `leaves` check, one trade stat per stat text with its numbers as `#`): R05 five (All Attributes, Life, three resistances), R08 two (Energy Shield %, Movement Speed), R13 five (which the rule above removes). Several tiers of one stat text are one query (the minimum roll of the lowest accepted tier). Each candidate is **one search and one fetch = 2 requests** (`price_buy_spec`), plus one request for the stat list on a cold cache. The item level filter must name a pool group (a minimum and a maximum), because a listing at 86 has the 86 pool and its plan costs 13% more on R13: for a floor of 84 that is up to three queries per candidate (84, 85, 86 and up). So R08: 2 candidates, up to 3 level groups, 13 requests at the most; R05, if its other candidates are worth asking: 5 candidates, 31 requests. With the recorded limits of 2026-10-30 (search `5:10:60,15:60:300,30:300:1800,600:21600:3600`, fetch `12:4:10,16:12:300,50:300:300,1000:21600:1800`, as hits:seconds:restricted-seconds per rule) 13 requests are under every window except the 5-searches-per-10-seconds one, where the client waits about 10 seconds; the existing client stops a run near 29 queries. The default request budget of a run (4) must be raised.
- **Realism test.** The search `total` and at least `MIN_LISTINGS = 3` usable listings (the repo's rule; the 5 cheapest are averaged). Candidates with fewer are not offered; the report lists them with the count found. The 3-listing belt at 86 and up passes the rule by a hair and fails any threshold of 10; at 84 and up it has 77. R08's Energy Shield boots have 122 and 14.
- **Bound before querying.** A candidate is worth a query only if its best case can beat the incumbent plan: `price floor + lower bound of finishing from it < cost of the incumbent`. The lower bound of finishing is ADR-0031's `rho` (section 3.3). On R08 the Energy Shield candidate passes (the solved graph has a state with that mod at 4.0 against 76.2); on R05, whose start already is the fractured ring, another fractured mod passes only if its bound is below the plan (12.2 Chaos); on R13 none passes. ADR-0031's `rho` is derived for erasing rerolls only (section 3.3), so on routes like R13 the cut has to be the simple rule above. I did not build these bounds.
- **Decision.** v1 **as an owner-run priced list**, nothing at plan time: the planner derives the candidate buy specs from the target, the owner runs one command that prices them into the price file (the flow of `prices trade` exists), the planner offers each priced candidate as a start option and keeps the cheapest total. This is ADR-0043's strand-count pattern. The listing-freshness caveat of section 2.1 applies.

#### Case 3. A base with one wanted mod, normal or magic

- **Price source.** The trade API only; neither bulk list has mods. There is no few-query pricing: one search (and one fetch) per (base, mod, tier).
- **Stock today.** Magic Leather Belt, tier-1 Life, instant buyout: **2** listings at 86 and up (84 and up was not searched). A rare with the one mod is plentiful (tier-1 Life: 255 at 86 and up) but see "what it would save".
- **What it would save.** From the solved R13 graph (`...-count.py`, section 3.4): the normal start belt costs 6,300.8 Chaos to finish; a magic belt with tier-1 Life costs 6,295.8 at best, **a saving of 5.1 Chaos**, less than a base (10 Chaos at 86, 1 to 2 at 84 and 85). A rare belt with the one mod saves nothing: the route offers no Scouring Orb, so every rare belt that is not nearly finished is a dead end whose value is the restart cost (6,310.8). On R08 every state before the Energy Shield is in costs the same 76.2 Chaos.
- **Realism test.** Same as case 2 (total and 3 usable listings); on today's belt the magic item has 2 and fails.
- **Decision.** **Not in v1.** It needs a query per candidate for a thin market and saves a few Chaos of thousands. Under v2 it is one more key.

#### 1.4a Strands, quality and the extra crafted slot

The issue lists these as choices a bought item could carry. They are already decided as purchases and need no new mechanism: a stranded start item is a buy with a minimum strand count at the counts where a cut class begins (ADR-0043 item 2, priced with the `memory_level` filter); quality is currency bought before the orbs (ADR-0049, no market item); the extra crafted slot is a start item that already has it, priced from the trade like any bought start (ADR-0053). Each is a case-2 query (one more stat or misc filter) and would join the same owner-run list; none is a bulk-priced case.

### 1.5 Summary of the three cases

| Case | Price source | Queries per plan (cached) | Realism test | Stock seen today | Verdict |
|---|---|---|---|---|---|
| 1. Base, item level, influence | poe.ninja `BaseType` (poe.watch fallback) | **0** (optionally 1 search per option for the buyout check) | row with `count >= 5` | 3,054 of 8,977 rows | **v1**; no recombinator for item level |
| 2. Fractured base, one fractured mod | trade API | 2 per candidate and level group plus 1 for the stat list: about 13 on R08, none on R13 (dead end), up to 31 on R05; 24 h query cache, 7 d price file; limiter of `trade_http.py`; owner-run | search total, at least 3 usable listings | 3 to 909 listings; 1 to 21 Chaos; R08's candidate 122 listings, 6.6 Chaos | **v1** as an owner-run priced list, cut by the route |
| 3. One wanted mod on a normal or magic base | trade API | 2 per candidate | same | 2 (magic belt, tier-1 Life, 86 and up) | **v2**; saves 5.1 of 6,311 Chaos on R13 |

---

## 2. A realism rule for bought rares without per-state queries

### 2.1 What the evidence says about "how many wanted mods may a bought rare carry"

The owner's intuition: two wanted mods on a rare is realistic, three or more usually is not, and it depends on the league. Evidence I could get:

**Measured stock, by number of wanted mods** (anonymous searches of 2026-11-01, totals only, instant buyout, not corrupted, not mirrored, any listing age, no session; Allflame; Leather Belt unless stated; belt tiers from the pinned data: Life tier 1 `+(130-144)`, tier 2 `+(115-129)`; Fire and Cold Resistance tier 1 `+(46-48)%`, tier 2 `+(42-45)%`):

| Rare belt, wanted mods | Tier 2 or better, level 86+ | Tier 1, level 86+ | Tier 1, level 84+ |
|---|---|---|---|
| Life | 466 | 255 | not searched |
| Life + Fire Resistance | 112 | 39 | 757 |
| Life + Fire + Cold Resistance | 25 | 3 | **117** |
| Life, **fractured** | 9 | 3 | 77 |
| Life, magic | 2 | 2 | not searched |
| no mod, normal (tiers do not apply) | 15 (at 86+) | | 148 (at 84+) |

Ring, item level 75+, fractured All Attributes 13+ and Life 100+ (tier 1 on a ring): 79 listings (602 with the fractured mod alone).

Each extra wanted mod cuts the stock by 4.2 to 13 times; moving the item level floor from 86 to 84 changes it by 10 to 39 times (the three-mod tier-1 belt: 3 listings at 86+, 117 at 84+; the normal belt 15 and 148). **The price of the three-mod tier-1 belt at level 84+ (one fetch of its 10 cheapest, 2026-11-01):** 10, 10, 10, 11, 15, 20, 20, 20, 20 and 25 Chaos (mean of the five cheapest 11.2), listed between 2026-08-04 and 2026-10-11 (an instant-buyout listing stays buyable, #133). At level 86+ the three listings were 30 Chaos, 1 Divine and 10 Divine. The planner's cost for R13 at the fixture prices is 6,310.8 Chaos (the run of section 3.4). **So on a belt, three tier-1 mods are on sale (117 listings) at about 560 times less than the craft costs.** Whether the bought belt also has an open affix for the bench damage craft R13 ends with, and whether a buyer finds the one he wants, is not in these numbers.

**What this says about the owner's rule.** For this base and league, three wanted mods are not unrealistic if the item level floor is the real one (84). The rule "two yes, three no" is a safe default for a plan run without a fresh count, but the evidence refutes it as a statement about existence here, and I would expect it to hold better for bases whose top tiers have several competing mods (a ring or an amulet with six or seven wanted mod families) than for a belt.

**Freshness of listings.** The ten cheapest three-mod belts at level 84+ were listed between 2026-08-04 and 2026-10-11, that is 3 to 13 weeks before the search; R08's ten cheapest Energy Shield boots between 2026-08-03 and 2026-09-25. The repo's recorded run of 2026-10-30 (R12 amulet, `tests/fixtures/trade/recorded/README.md`) found 17 listings within a week against 910 at any age. An instant-buyout listing stays buyable until it is sold, so age alone is not staleness, but the counts above are stocks of old listings, not a flow, and the cheapest listings are the ones that did not sell. The query model has a listing-age window (`indexed`, off by default since #133); a window of 2 weeks or a month is the cautious variant of the stock test, with far smaller counts.

**League dependence.** poe.ninja's own history of one row (section 1.1) shows the observation count of the plain item-level-86 Leather Belt falling from 399 to 37 in 100 days of the league. The history shows the count rising to its cap of 399 within the first week and then falling to 37 over the following 90 days; I found no series for the trade site. I found no published series of listing counts by mod count: **no source found** for a typical number of listings of rares with 2 to 3 specific tier-1 mods in 3.28 or 3.29 (the GPT researcher also found none).

**Community.** Reported by the GPT researcher and not opened by me, with dates: players say a fractured base is easier to get than a finished item they would accept (r/PathOfExileBuilds 2024-09-22); they craft when they expect it to be clearly cheaper and buy when it is not (r/pathofexile 2023-06-01 and 2024-05-19); and they complain of price fixing, that is low listings with no intent to sell (r/pathofexile 2020-07-10, 2021-11-21, 2024-04-10). So the cheapest listing is not always buyable; the mean of the 5 cheapest instant-buyout listings (the repo's statistic) damps one bait listing but not a cluster of them. The three-mod belt's ten cheapest are in a tight band (10 to 25 Chaos), which is not the shape of one bait listing.

**A bulk source for rares: none.** poe.ninja has no rare lines. Craft of Exile's market data is currency only and stale. poeprices.info (a machine-learning price predictor for rares that Awakened PoE Trade called, per the GPT researcher) is not usable: fetching `https://www.poeprices.info/` on 2026-11-01 redirected to a domain-for-sale page (the GPT researcher reported the site loaded; I could not reproduce that). GGG's own currency-exchange endpoint (`/api/currency-exchange`, in the developer documentation) is hourly, historical and currency-only. **No source found** that prices a rare by its mods in bulk.

### 2.2 The rule I recommend

1. **A stock count, not a mod count, is the proof of existence.** Offer a bought item only when its search `total` is at least `T` and at least 3 of the fetched listings are usable (the repo's existing rule). The test costs **one request** (the search; the `total` is in its answer, no fetch), the cheapest league-dependent signal there is.
2. **When no fresh count exists (a plan run from a snapshot), cap the wanted mods a bought item may already carry.** Default **1 in v1** (a fractured mod, or none): beyond that nothing in v1 says the item exists. In v2 the cap is replaced by the stock test. The owner's "two" is a defensible v2 default for a plan with no count, with the measured counts above as the reason it can be raised.
3. **Bulk rows (case 1): `count >= 5`.** It is what ADR-0007 already does for priced bases.
4. **Staleness.** A count older than the price file's 7 days is a warning, as for any trade price; a snapshot older than that does not offer the option.
5. **The report names every refused option** and the count that refused it, as it does for dropped offers, so the owner can lower `T` knowing what he gives up.
6. **Expected purchases against stock.** A plan that resets often buys often. The report states the expected number of purchases (the expected number of restarts plus one) next to the listing count; a plan that needs 50 purchases of an item with 9 listings is not realistic. The plain restart has the same issue today.

The threshold `T` (3, 10, 25) is a taste question (section 5).

---

## 3. The general mechanism, as a v2 hypothesis for #325

This part answers the issue's own shape (a buy offer at compressed states, `V(s) = min(craft, buy s)`, coarse bands, lazy offers with admissible bounds). It is a hypothesis to test, not a v1 design.

### 3.1 What a trade query can name

The trade search takes the following, all of which the compressed state of ADR-0009 carries (`prices/trade_query.py` writes the first six; the pseudo stats of the last row exist on the live site and are **not** in `TradeQuery` yet):

| Compressed-state field | Trade filter |
|---|---|
| Rarity | `type_filters.rarity` |
| Item level band | `misc_filters.ilvl` min and max |
| Influences | pseudo stats `pseudo.pseudo_has_<name>_influence` (minimum 1) |
| Fractured mods | `fractured.stat_*` ids and `misc_filters.fractured_item` |
| Target-leaf status "passing" / "below" | `explicit.stat_*` filters with a minimum roll (the tier is a roll threshold) |
| Corrupted | `misc_filters.corrupted` |
| Mods per side, free slots | pseudo stats `# Prefix Modifiers`, `# Suffix Modifiers`, `# Empty Prefix Modifiers`, `# Empty Suffix Modifiers`, `# Crafted Modifiers`, `# Fractured Modifiers` (ids `pseudo.pseudo_number_of_prefix_mods` and so on, present in the stat list recorded 2026-10-31) |

What it cannot name is **which junk the item carries**: junk families (ADR-0009 keeps them as slots only when an enabled action reads them) have no filter that says "any junk except...". It can exclude by `not` groups, but the planner does not know which to exclude. A listing is a concrete item, so after the fetch its mods are known; a priced listing is a **deterministic offer to one concrete state**, not a lottery over junk. The price of a class is then the price of its cheapest listing, and the state a class buys is only known for that listing. How much that matters is measurable: in the solved graphs the cost-to-go varies by at most 0.08% among states with one key on R13 (median 0%), while on R05 and R08 the maximum spread is 1,656 and 19 times, from a few near-goal keys (section 3.4).

Price rules already in the repo: sort by price ascending, `securable` status, the mean of the `k = 5` cheapest usable listings, at least 3. Awakened PoE Trade's source (`pathofexile-trade.ts`, read through a page reader) does the same query shape: status `securable`/`available`/`online`, price ascending, pseudo stats for influence and empty modifiers, a `count` group for "at least 1 of these", one `fetch` of the first ids, rate-limit rules for search and fetch read from the headers, and it sets no User-Agent; it chooses no single price (it returns the rows and the caller shows them). I found no automatic outlier removal in it.

### 3.2 The reset view: every buy offer is a restart to a priced state

A bought item replaces the item in hand, whatever it was. So a buy offer's price and result do not depend on the current state `s`. With buy offers `K` (price `p(k)`, result state `k`),

    V(s) = min( Qcraft(s) , B ),     B = min over k of ( p(k) + V(k) )

where `Qcraft(s)` is the value of the best crafting action at `s` (with `V` at its successors), and `B` is the same constant at every state. Today's `restart` is `K = {start}`, `B = price(start) + V(start)`. Consequences:

- **Buying at the start and buying mid-route are one mechanism.** The best buy is a state `k*`; the plan starts there if `B` beats crafting from the target's start, and returns there after a failure instead of returning to the target's start item.
- **The solver needs one fixed point, not an action per offer.** `B` is a number. `f(B) = B - min_k (p(k) + V_B(k))` is piecewise linear and convex in `B` (`V_B` is concave and nondecreasing in `B`), so a Newton step from `B_0 = restart cost` falls monotonically and converges in a few solves, where plain iteration would converge only at the rate of the reset probability. Each solve reuses the kernels cached by pool signature. A reset to a candidate adds the states reachable from it.
- **Assumptions it makes, to be stated in an ADR:** the old item is discarded (resale is not modelled, as today); supply is unlimited at the quoted price (hence the expected-purchases line of section 2.2); and a class price stands for one state, which is exact for a concrete listing and otherwise optimistic with `V_min(k)` and pessimistic with `V_max(k)`.
- **Several abstractions.** Item level is fixed per abstraction (section 0). Options that differ in level or base are separate abstractions and cannot be one joint restart; planning each with its own restart gives an upper bound on the joint optimum, tight unless a partial state of one option beats another option's restart. Options that share an abstraction (fractured mods at one level) can be joint. #330 (separate plans per recipe start) has the same property.
- **The reset view does not hold for donors.** A recombinator or Awakener consumes the item in hand together with a donor, and the output's mods come from both (ADR-0033: both inputs are destroyed, the result is a new item): the result depends on the current state, so it is not a reset. A donor is a `Need`, an acquisition sub-problem whose goal is a state, with buying as one of its actions (ADR-0022: "Buying a donor is an ordinary action of its process (ADR-0011)"). #211 stays separate: a bought donor with a chosen base and item level is a buy offer inside the `Need` process, priced the same way (bulk rows for the base and level, trade queries for mods).

### 3.3 Lazy generation and admissible bounds

A price is unknown until asked. Four values of a price, kept in the price file with their date:

- **quoted** (`p`, listing count, date): the offer exists.
- **none** (date): a successful search answered `total = 0`. The offer does not exist **now**; this is not "unknown", the trade site said so. It holds for every stricter key too (a listing that matches more filters also matches fewer), so one empty search (total 0) closes a whole cone of keys with no more requests.
- **thin**: the search found 1 or 2 usable listings. It is neither quoted (the repo needs 3, `MIN_LISTINGS`) nor none; it is kept with its count and not offered. A thin query closes the cone of "quoted" for every stricter key (it has at most as many listings, so it can never reach 3) but not the cone of "none".
- **unknown**: never asked, refused by the limiter (429, 403, Cloudflare), or too old. The solver treats it as not offered, and the answer says so.

**Admissible lower bound of an unknown price.** Let `m(j)` be the price of the single cheapest usable listing of a query `j` (the first row of the sorted answer). A listing that matches a stricter key `k` also matches every relaxation `j` of it, so `m(k) >= m(j)`, and the planned price of `k` (the mean of its 5 cheapest, at least 3 usable) is at least `m(k)`. The mean of the 5 cheapest itself is **not** monotone: a thin stricter key with 3 cheap listings can have a lower mean than the broad one. Valid relaxations are: drop a stat filter, widen the item level band, lower a minimum roll, drop `fractured_item`. Dropping an influence filter is **not** one, because the repo drops listings whose influences differ from the spec (`_chaos_of`), so that rule depends on the spec. Where nothing is quoted, 0 is the bound.

**Admissible lower bound of the finishing cost** from a candidate state `k`: ADR-0031's `rho = min cost / pbar` over the offers, a lower bound on the cost to make the necessary leaves not yet PASSING at `k` all PASSING (a single use enters that set with chance at most `pbar`, from `reach_bound`, an upper bound on that chance computed from the pool alone). ADR-0031 derives it per goal set and states it as a limit that offers which change the flags or the fractured mods are not covered; a buy changes both, so `rho` has to be re-derived per shape (the ADR names "a per-shape rho" as the fix). `reach_bound` is derived for erasing rerolls (a Chaos Orb, a fossil or essence reroll; `abstraction/_bound.py`), so it covers R05 and R08 but **not R13's Augmentation, Regal and bench route**: no admissible finishing bound is known for that route, and its numbers in section 3.4 are the oracle, the best case. The oracle is the solved `V_min(k)` over the states of the key. Together (the price factor `g` of section 3.4 is unrelated to ADR-0031's `rho`):

    skip k  when  LB_price(k) + LB_finish(k) >= B_current

which is the pruning test of ADR-0031 applied to buy offers instead of fossil sets. What is left unqueried is certified: the answer carries two bounds, `B_pess` (best quoted offer) and `B_opt` (adds every unknown offer at its lower bound), the pattern of ADR-0023 / `solve_bounds`. If `B_pess - B_opt` is within the tolerance, the answer is exact for the market as quoted; otherwise the report lists the unknown keys in order of `B_current - (LB_price + LB_finish)`, the most promising query first. Fit with #312: the buy offers add at most `|K|` restart candidates and no transition probability; with the envelope search of research note 3 (the LAO*-style search that expands only what the current best policy reaches and stops when every unexpanded region has a lower bound no better than the incumbent) an unexpanded buy offer is such a region with exactly this bound; exact merging (#312) shrinks the key set because keys are classes.

**Cached snapshot, zero queries.** The price file is the snapshot (ADR-0007): quoted, none and unknown entries with dates. A plan reads it and never touches the network; it offers the quoted keys and reports the unknown keys that could lower the cost. This is the default mode and the only one compatible with section 3.5.

### 3.4 What it would cost on R05, R08 and R13

`docs/research/2026-11-01-buying-any-state-count.py` ran on GitHub (run 41334133692 for the counts; run 41336043055 repeated it with the sweep starting at `g` = 1): each route is planned at the fixture prices exactly as `make_plan` does, then every solved state is projected to its buy key (rarity, influences, fractured mods, the status of each target leaf; junk dropped) and to the same key with the number of other prefixes and suffixes (a trade query can pin them with the pseudo stats of section 3.1).

| | R05 | R08 | R13 |
|---|---|---|---|
| Plan time on the runner (two runs) | 31 to 32 s | 151 to 153 s | 8 to 14 s |
| States in the solved graph (goal states) | 761 (62) | 87 (17) | 4,066 (6) |
| Offers (with `restart`) | 72 | 10,675 | 10 |
| Cost: start price + mean from the start | 2.6 + 9.6 = 12.2 | 29.8 + 76.2 = 106.0 | 10.0 + 6,300.8 = 6,310.8 |
| **Buy keys** (junk dropped) | **78** | **21** | **240** |
| Buy keys with side counts pinned | 290 | 87 | 470 |
| Keys whose best state is cheaper than the plan | 78 | 21 | 45 |
| Largest cost-to-go spread inside one key | 1,656 times (median 1.0) | 19 times (median 1.0) | 1.0008 times |

**Eager generation** asks one query per key: 78, 21 and 240 queries (290, 87 and 470 with side counts), two requests each. The binding rule is 30 searches per 300 s, so R13's 240 keys take about 40 minutes of limiter time (470 about 80 minutes), well under the 600-per-6-hours cap; but the existing client stops a run when it would have to wait more than 120 s, which is after about 29 queries, so that is nine to seventeen runs, not one. **Lazy generation** with the monotone price bound of section 3.3 asks fewer, and what decides the number is the bound on the finishing cost. The price model is made up (price = start price times a factor `g` per extra constraint; a status below counts 1, passing 2, a fractured mod 1, an influence 1; the script calls the factor `rho`), so the sweep is a range, not a prediction. Keys a lazy search queries, with the keys that turn out cheaper than the plan in brackets, with no bound on the finishing cost ("price only") and with the solved cost-to-go as the bound ("with bound": the best any bound could do). ADR-0031's bound covers erasing rerolls, so it applies to R05 and R08, where it is 1.3 to 2.8 times loose on boots and the real counts lie between the two columns; for R13 no bound is known and "with bound" is the best case:

| `g` per constraint | R05 price only / with bound | R08 price only / with bound | R13 price only / with bound | Best total with buys: R05, R08, R13 |
|---|---|---|---|---|
| 1.0 (every key costs the start price) | 78 / 72 (72) | 21 / 7 (6) | 240 / 24 (22) | 2.6, 29.8, 10.0 |
| 1.25 | 78 / 23 (19) | 21 / 7 (6) | 240 / 18 (12) | 4.1, 50.6, 38.3 |
| 2 | 35 / 10 (2) | 10 / 2 (0) | 240 / 18 (9) | 10.4, 106.0, 640.1 |
| 4 | 16 / 6 (1) | 3 / 2 (0) | 155 / 9 (0) | 12.2, 106.0, 6,310.8 |
| 8 | 6 / 6 (1) | 3 / 2 (0) | 112 / 9 (0) | 12.2, 106.0, 6,310.8 |
| 16 | 6 / 6 (1) | 3 / 2 (0) | 68 / 9 (0) | 12.2, 106.0, 6,310.8 |

(With side counts pinned the price-only numbers rise to 290, 87 and 470 at `g` up to 1.25 and the bounded ones are about the same: 215 / 21 / 24 at `g` = 1.) Read it as follows. **A bound on the finishing cost is what would make lazy generation fit one run**: with the best bound R13 needs 9 to 24 queries (18 to 24 at the measured `g`) and R08 2 to 7; without any bound R13 needs all 240 up to `g` = 2 (155 at 4, 112 at 8, 68 at 16), and the measured belt is inside that range (11.2 Chaos for six constraints is `g` = 1.02 against the level-86 start of 10 Chaos and about 1.5 against a level-85 start of 1.0 Chaos; at that `g` the bounded count is 18 to 24). R05 needs up to 72 at flat prices. **At steep prices (`g` of 4 or more) no buy ever beats the plan, and a handful of queries proves it.** So for R13, where no bound exists yet, the honest cost of general lazy generation today is the whole 240-key list.

Two structural facts hold at any price: **the value is concentrated in the last states** (R13: only 45 of 240 keys are cheaper than the plan, none with at most 2 constraints saves more than 5.1 Chaos; R08: 76.2 Chaos at every state until the Energy Shield is in; R05: the start is already a fractured ring, every key has at least 3 constraints), and **junk barely changes the value inside a key on R13** (spread 1.0008), so a class price is accurate there.

### 3.5 Terms and the limiter: why the general mechanism is v2

GGG's developer documentation (https://www.pathofexile.com/developer/docs) says it supports only the resources of its API Reference and its Data Exports, and that reverse-engineering endpoints outside that documentation is against the Terms of Use, section 7i. The trade search, fetch and stats endpoints (`/api/trade/search`, `/fetch`, `/data/stats`) are not in the reference. A GGG web developer gave the same answer in 2021 to a question about the trade data endpoints (forum thread 3108772, 2021-05-04; I read the thread). The documentation also says the rate limits are dynamic and can change at any time, that a 429 carries `Retry-After`, that exceeding limits frequently gets an application's access revoked, and that macros must be started manually by the user (timers and other automated triggers are not allowed); it lets a website cache more broadly. The Terms of Use, as read through a page reader and not checked against the page itself, list among the restrictions (7c, 7e, 7f, 7i) automated software or bots, connecting through software other than the game client, data-gathering tools on the website, and reverse engineering. The repo's own conclusion (ADR-0007, 2026-10-30) is the cautious reading: the fetcher runs only when the owner starts it, with few requests. Tools in wide use (Awakened PoE Trade, Path of Building's trade query) send the same queries from the user's machine on a user action, and a GGG post of 2025-06-26 (reported by the GPT researcher, not opened by me) says a tool's rate limit also limits the user on the website.

The practical limits from the recorded headers (2026-10-30; the limiter reads the live ones): the search rule allows 5 hits per 10 s, 15 per 60 s, 30 per 300 s and 600 per 6 hours; breaking them restricts for 60 s, 300 s, 1,800 s and 3,600 s. The fetch rule allows 12 per 4 s, 16 per 12 s, 50 per 300 s and 1,000 per 6 hours. A priced state is one search plus one fetch, so **a run gets about 28 to 30 queries (the 300 s window, with the limiter's margin of one hit; it stops when a wait exceeds 120 s) and a day at most about 2,400 (4 x 600)**. The 26 requests I made today (21 searches, 5 fetches, in groups of at most 7) drew no 429.

So "lazy generation during the solve" cannot mean an unattended loop of queries: it means **a list of next queries that the owner's command runs, then a re-plan**, unless the owner widens ADR-0007. That is an owner decision (section 5, v2).

---

## 4. Recommended design

**v1 (no trade query at plan time):**

1. **Start options from the bulk base list.** For a target, the start options are the rows of the price file for its base: the item levels from the target's real floor up to 86, one plan per equal-pool group (the cheapest row in the group among rows with at least 5 observations; the report shows the observations, because the cheapest row is often the least observed), influenced rows only when the target asks for an influence mod. The target's `item_level` becomes a floor (the planner derives the true floor from the tiers its leaves ask for, or the author states it). A bought item is priced from its row; a row with fewer than 5 observations does not exist for the planner. Each option is its own plan with its own restart; the answer is the cheapest total start price plus plan, with the other options listed with their totals.
2. **No recombinator as an item-level source.** Say so in the explanation of the plan rather than offer it.
3. **Fractured one-mod starts as an owner-run priced list.** Candidates from the target, cut first by the route (a fractured start is asked for only if an offered action can rework a rare item: 5 candidates on R05, 2 on R08, none on R13) and by the bound where one exists, each priced for one pool group of item levels by the existing trade flow into the price file, each offered if the stock test passes; the start options are the cheapest of all. This is also the place for the recipe-made starts of #330 (same list, a constructed price instead of a quoted one), and for stranded or extra-slot starts (section 1.4a).
4. **`max_bought_target_mods = 1` and the stock test of section 2.2**, both visible settings (and #323 item 9 becomes: buy offers off / start base only / start base and one fractured mod / more, with the stock test).
5. **Cached snapshot is the only mode.** The report lists the candidate options that had no price and the order of queries that would settle them.

**v2:**

6. The general mechanism (sections 3.2 and 3.3): buy keys at compressed states, the reset fixed point `B`, quoted/none/unknown prices with the monotone bound, the two-bound answer with the next-query list, after #312's solver is in. Its first and largest use is buying the nearly finished item (R13: 11 Chaos for a belt with the three mods, plus the finishing bench craft that is not priced, against 6,311), which needs a finishing-cost bound for routes that are not erasing rerolls (R13's Augmentation and Regal route has none).
7. Concrete listings as offers (fetch the 10 cheapest, map each to its compressed state, one offer per distinct state), which needs the listing's mods mapped to game mods.
8. Donors as buy offers inside `Need` (#211), mid-route bought intermediates, mods carried by a bought rare above the v1 cap, one-mod normal or magic bases, SSF mode (no prices), and the budget interplay (#323).

## Decisions (owner, 2026-11-01)

The owner answered the v1 questions of section 5. The design is recorded in [ADR-0061](../adr/0061-the-planner-chooses-its-start-base-and-a-fractured-start-from-a-priced-list.md) and, for the refresher, in an amendment to ADR-0007.

- **Q1 yes.** The target's item level is a floor the planner may go below when the needed mods stay reachable.
- **Q2 yes, with a change.** The user never refreshes anything: the system keeps the trade price list fresh with a scheduled refresher, anonymous requests at an interval within a request budget, through the existing limiter in `prices/trade_http.py` (it reads the `X-Rate-Limit-*` headers and stops on 429). It is a service component of the website, not a CLI step. ADR-0007 is amended for that refresher only. Risk, in one line: GGG's documentation does not list the trade endpoints and calls reverse-engineering outside it a Terms of Use breach (7i), so unattended use may be refused or the IP restricted.
- **Q3 yes, revised.** poe.ninja is often delayed or off, so the price source is a profile setting (with the #323 user inputs) with three values: `ninja`, `trade`, `both`. The default is `both`: the refresher fetches both, the planner prices with the trade data (instant buyout, the owner's reading), and when the trade data is missing or stale it falls back to poe.ninja and marks the price so. The answer shows both prices side by side and flags a gap above 20% (configurable). This applies to bases, not only to fractured ones; a fractured base has no poe.ninja row, so it is trade-only.
- **Rate limits are found empirically.** The refresher reads the policy from the `X-Rate-Limit-*` headers of every response (each window's limit and current use), keeps a configurable margin below each window, honours `Retry-After` and backs off on a 429, and logs the observed limits so they can be checked over time. It does not probe by hitting a limit.
- **Q4 yes.** A market exists at 10 or more listings; the price is the mean of the 5 cheapest.
- **Q5 yes.** A bought rare carries at most 1 wanted mod in v1.
- **Realism rails.** The owner accepts the listing-count rule but does not know whether it or a mod-count rule works better. Both are configurable rails (listing-count threshold, default 10; maximum wanted mods, default 1), and the planner reports which rail cut which offer, so they can be compared later.
- **Recombinator item-level trick:** dropped, as section 1.4 says.
- **Q6 to Q9 stay open v2 questions** (on #325). Q6 is partly answered by Q2: the system sends its own queries, rate-limited; what stays open is whether the planner may also ask for a state it needs during a plan (a bounded loop) rather than only list it for the refresher.

## 5. Questions for the owner's design grill

Questions 1 to 5 are answered in the Decisions section above; questions 6 to 9 are open v2 questions.

### v1

1. **May the planner choose the base's item level between the target's real floor and 86, and how many plans may that cost?** Today the file's number is the level. If yes, R13 and R08 each get two more plans (levels 84 and 85); the measured gain is 13% on R13 (819 of 6,311 Chaos) and 8% on R08 against the same price source; each R08 plan takes 106 to 151 s on a runner, so three levels are about 6 minutes, against your wish for an exact answer in about a minute. Options: all levels (best answer, slow), or only the cheapest two by price, or a target-file key `item_level_floor` that the author sets. The floor cannot be derived when the author wrote a level to mean "the top tier at that level" (R05's resistances are tier 2 because its level is 75), so the planner may lower a level only where the tiers are stated absolutely or the author gives the floor. Recommendation: yes, derive the floor from stated tiers, run all levels, and order them cheapest first so the report can show the best total early.
2. **May v1 depend on a priced list that you refresh with one command (about 13 requests for R08), or only on the bulk list that needs none?** With the list, R08 falls from 77 to 106 Chaos to about 10.6 at best (a fractured tier-1 Energy Shield boots at 6.6 Chaos plus the 4.0 the graph shows left to finish; 122 listings today); without it, R08 keeps its price. The list is stale after 7 days and each refresh is your command (ADR-0007). Recommendation: yes, behind a setting, with the cut by route so R13 asks nothing.
3. **A bulk row is not a proof of an instant-buyout listing. Do you accept the row as enough in v1 (price from the row, the report names its observations), or must every start option pass one trade search `total`?** The check is one request per option and needs your command. Recommendation: accept the row, and say in the report "not checked against instant buyout".
4. **How thin may a market be for an option to count as existing?** Three usable listings is the repo's rule today; ten shuts out the 3-listing fractured belt at 86 and up but not the 77-listing one at 84 and up, and 14 of R08's boots at 86 and up pass either way. A recent-listings window (two weeks) would shrink every count (R12's amulet: 17 of 910 within a week). Recommendation: 5 observations for bulk rows (the repo's rule), 10 listings at any age for trade-priced options, one setting.
5. **How many wanted mods may a bought rare already carry in v1?** Recommendation: 1 (a fractured mod). Two or three need a stock test of a live search, which is v2 unless you allow that search in v1. The evidence says a three-mod belt exists (117 listings at level 84 and up), so a cap of 2 or 3 is defensible if you accept a stock test.

### v2 (#325)

6. **May the planner send trade queries itself in a bounded loop, or only list the next queries for you to run?** GGG's documentation calls these endpoints unsupported and says macros must be started by the user; the cautious reading of ADR-0007 is the list. A loop is one command and about 30 queries per run; the list means you run each batch of about 30, and R13's full key list is 240 queries (nine runs) until a finishing bound exists. Recommendation: the list.
7. **Is "three or more skipped steps is unrealistic" (#325) a count of crafting steps skipped, or a stock test?** The stock test measures existence; the step count measures how reproducible the route is for other players. They disagree: 117 belts with three tier-1 mods exist at level 84 and up, and the craft they replace is thousands of Chaos. Recommendation: a stock test, with the skipped steps shown in the report.
8. **When a bought item beats the craft by a factor of hundreds (R13: 11 Chaos against 6,311), should the answer lead with "buy this" instead of a route?** Options: lead with the purchase and its price, with the route below it for the user who wants to craft; or show only the route, as the tool does today. Recommendation: lead with the purchase.
9. **In SSF (solo self-found play, where nothing can be bought) buy offers are off by definition. Do you want the user to be able to state which bases or items he already owns, free, and have the planner choose among those as start options (#323 item 9)?** That reuses the start-option list of v1 with a price of zero and no query. Recommendation: yes, as the first SSF input.

## 6. Where each point of the issue is answered

| Point of the issue | Where |
|---|---|
| Can the trade API price "an item matching state X" (filters) | 3.1 |
| Rate limits, freshness, sparsity | 3.5 (limits), 1.1 and 2.1 (freshness, sparsity) |
| Cache and "no listing" (not buyable vs unknown) | 3.3 |
| Other sources: poe.ninja, Craft of Exile, any public price API | 1.1, 2.1 |
| Instant-buyout only | 0, 1.2, 3.1 |
| A buy offer fits the SSP-MDP | 3.2 |
| Interaction with #312's solver; bounds admissible with an unknown price | 3.3 |
| The base, item level, influence, fractured mod, strands, quality, extra slot as choices | 1.3, 1.4, 1.4a |
| Vendor recipes (#329, #330) | 3.2 (several abstractions), 4 item 3 |
| Donors (#211) | 1.4 case 1, 3.2 (donors) |
| What #323 item 9 becomes | 4 item 4, 5 questions 5 and 9 |
| Queries per route on R05, R08, R13; zero-query snapshot | 1.3, 1.4 (v1 slice), 3.4 (v2), 3.3 (snapshot) |
| The owner's narrowing: three parts, three cases, realism rule | 1, 2, 1.4, 2.2 |
| Recommended design; v1/v2 questions | 4, 5 |

## 7. Sources, and what was not found

Primary:

- GGG developer documentation: https://www.pathofexile.com/developer/docs (policies, User-Agent, rate-limit headers, `Retry-After`, 429, "macros must be invoked manually", the section 7i sentence), https://www.pathofexile.com/developer/docs/reference (currency exchange: hourly, historical; public stash API needs the `service:psapi` scope; no trade-search endpoint), Terms of Use https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy (read through a page reader; clauses 7c, 7e, 7f, 7i and 22).
- GGG forum thread 3108772 (2021-05-04, a GGG "Web Developer"): the 7i answer, read by me.
- poe.ninja: https://poe.ninja/docs/api (stash overview, `BaseType`, caching, no numeric limit), the `BaseType` overview, one history row, and the Currency exchange overview, read 2026-11-01.
- poe.watch `get?category=bases`, read 2026-11-01.
- The repo: ADR-0007, 0008, 0009, 0011, 0013, 0022, 0031, 0032, 0033, 0035, 0043, 0049, 0053; `src/crafting_system/prices/trade_http.py`, `trade_pricing.py`, `trade_query.py`, `trade_stats.py`, `ninja_items.py`, `poe_watch.py`; `src/crafting_system/cli/_offers.py`, `_plan.py`; the recorded trade answers and headers in `tests/fixtures/trade/recorded/` (2026-10-30 and 2026-10-31) and the price fixture `tests/fixtures/prices/routes-allflame-2026-10-31.json`; `docs/research/2026-10-30-3-multi-item-recombinators.md`; `docs/research/2026-10-31-vendor-recipes.md`.
- Craft of Exile's local copy (git-ignored): the shape of its price file only.
- Awakened PoE Trade source, https://github.com/SnosMe/awakened-poe-trade `renderer/src/web/price-check/trade/pathofexile-trade.ts`, read through a page reader.
- My own measurements: 26 anonymous trade requests of 2026-11-01 (21 searches for totals and 5 fetches), no session, none refused; the poe.ninja and poe.watch answers; the pool counts per item level, the mod levels and the tiers from the pinned data; the two GitHub runs of the planner on R05, R08 and R13.

Second-hand, from the GPT researcher (job `20261101-183427-0bf1`, model luna) and not opened by me: the Reddit threads and quotes of sections 1.4 and 2.1, the 2018 and 2021 forum posts on caching and per-IP limits, a GGG post of 2025-06-26 on tool and website limits, the item-level formula threads of 2024 to 2026, the wiki's Recombinator page, Awakened PoE Trade's discussion #735. They agree with what I read first-hand and none carries a number the design depends on.

**Not found:** a typical number of listings for rares with 2 to 3 specific tier-1 mods across 3.28 and 3.29; general price bands for fractured mods or for item level 84, 86 and 87 bases; a measure of how liquid half-finished items are; a bulk source for rares, fractured bases or items with mods; any GGG statement that permits unattended use of the trade endpoints (the documentation says the opposite for endpoints it does not document); which poe.ninja listings are priced buyouts; the trade site's query-complexity limit (the answers showed `complexity` 12 to 15 and no refusal); whether poeprices.info is alive; a source that someone prices recombinator donors by trade search; whether the level of an elevated mod gates the Awakener's Orb.
