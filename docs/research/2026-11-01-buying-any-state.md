# Can the planner choose what to buy, and how is a bought state priced

Research ticket [#337](https://github.com/Rasslabsya4el/crafting-system/issues/337), written 2026-11-01 against patch 3.29.3.3 and the Allflame league. Related: ADR-0007, ADR-0008, ADR-0009, ADR-0011, ADR-0022, ADR-0031, ADR-0033, ADR-0035, ADR-0043, [#102](https://github.com/Rasslabsya4el/crafting-system/issues/102) / [#329](https://github.com/Rasslabsya4el/crafting-system/issues/329) / [#330](https://github.com/Rasslabsya4el/crafting-system/issues/330) (vendor recipes), [#211](https://github.com/Rasslabsya4el/crafting-system/issues/211) (donors), [#312](https://github.com/Rasslabsya4el/crafting-system/issues/312) (exact merging), [#323](https://github.com/Rasslabsya4el/crafting-system/issues/323) (user inputs), [#325](https://github.com/Rasslabsya4el/crafting-system/issues/325) (map v2).

The owner narrowed the question while this note was written (main chat messages of 2026-11-01): the general "buy any compressed state" mechanism is a v2 hypothesis; v1 may hold only simple cases that need no per-state trade query, each decided on cost, query count and how sure we are that the item exists to buy. The note is therefore in three parts in that order (sections 1, 2, 3), then the recommended design and the questions (sections 4, 5). Section 6 maps every point of the issue to a section, section 7 lists the sources and what was not found.

## Answer in brief

1. **The start base, its item level and its influence can be chosen from one bulk fetch, with no trade query.** poe.ninja's `BaseType` list has 8,977 rows for Allflame today: one row per base, per item level 82 to 86 and per influence set (the six influences and 16 dual sets), 3,054 of them with the 5 observations our price rule needs. It has no row for a fractured, synthesised or corrupted base and nothing below item level 82. "Offer a start only if a row with at least 5 observations exists" is realistic by construction and costs nothing at plan time. On R05, R08 and R13 it adds **no extra plan** (R13 and R08 need item level 86, the top pool; R05 starts from a fractured ring, which this list cannot price) and at most two on a target with a lower floor.
2. **The recombinator trick for item level never pays.** The output level cannot exceed the higher input (`min(floor((A+B)/2+2), max(A,B))`, ADR-0033), so one input must already be as high as the target needs and could be bought alone; adding a second base, two magic upgrades and one combine (about 7 Chaos, ADR-0035) only adds cost. Also, no equipment mod in the 3.29.3.3 data needs an item level above 86, so no pool changes above 86 (section 1.5).
3. **A fractured base with one wanted fractured mod is the one simple case that needs the trade API.** It costs 2 requests per candidate mod (one search, one fetch), 4 to 10 requests per target on R05, R08 and R13, inside one run of the existing limiter; the listings exist today (602, 156, 42 and 909 for the four recorded start items, 9 for a belt with a fractured tier-1 Life) at 1 to 20 Chaos, against 160 to 260 Chaos for one Fracturing Orb that picks a mod at random. A normal or magic base with one wanted mod has no bulk source and almost no stock (2 magic belts with tier-1 Life), so it stays out of v1.
4. **"How many wanted mods may a bought rare carry" is not a fixed number; it is a stock count that moves with the base and the league.** On Leather Belts of item level 86 the instant-buyout listings fall by about 4.3 times per extra tier-1 mod (466, 112, 25 for one, two, three), and poe.ninja's own observation count for the plain item-level-86 belt fell from 399 to 37 within the league. A rule "at most 2" is a fair default when no fresh count exists; the real test is a listing count from one search request.
5. **The general mechanism has one simple core: a bought item replaces the one in hand, so every buy offer is a reset to a priced state, and the whole family collapses into the cost `B` of the best reset.** `restart` (ADR-0011) is the case with one candidate. That makes the lazy generation, the admissible bounds and the cached-snapshot mode (zero queries) cheap to specify (section 3), but it needs a trade query per candidate state, which GGG's developer documentation does not support as an automated, unattended use. That is why it is v2.

The recommended v1/v2 split is in section 4, the owner's questions in section 5.

---

## 0. What exists today

- A target names a concrete start item; its price is the name under `start_price` in the price file (ADR-0008). The only buy action is `restart`, `BuyStartItem`, which buys that same item again at every state (`cli/_offers.py`, `cli/_plan.py`: `Offer(RESTART, BuyStartItem(target.start_item), ...)` priced with the start item).
- A start item is priced from poe.ninja (bases, per item level and influence: `Leather Belt (ilvl 86)`) or by the trade API for a buy spec (`prices/trade_pricing.py`: one search, one fetch of up to 10 listings, the mean of the 5 cheapest instant-buyout listings, at least 3 usable, cached 24 hours per query and 7 days in the price file; the request budget of a run defaults to 4). ADR-0007 fixes that the trade fetcher runs only when the owner starts it, and that the solver reads only a dated local price file.
- The query model (`prices/trade_query.py`) already writes: base type or category, rarity, item level min and max, corrupted and mirrored, `fractured_item`, stat filters with a minimum, the six influence pseudo stats, the listing status (`securable` = instant buyout, the default since #133) and the listing age; the rate limiter (`prices/trade_http.py`) reads the `X-Rate-Limit-*` headers of every response, waits, stops on 401, 403, 429 or a Cloudflare page, and bounds a run by a request budget. This note cites that limiter and does not re-research it.
- ADR-0043 already has one planner-chosen buy: a purchase with a minimum Memory Strand count, where "the planner does not ask for all 100 counts", it "offers the counts at which a cut class begins", which is "a choice of which prices to fetch". The pattern recommended below is the same: a short candidate list that the target itself fixes, priced through the price file.
- The compressed state (ADR-0009) already separates what a buy would name from what it could not: flags (rarity, influences), fractured mods, one status (absent, below, passing) per target leaf, and the other mods as slots (junk, kept only when an enabled action reads it).

---

## 1. The v1 slice: choose the start base, item level and influence from one bulk fetch

### 1.1 What poe.ninja's base list covers

Source: `GET https://poe.ninja/poe1/api/economy/stash/current/item/overview?league=Allflame&type=BaseType`, read once on 2026-11-01 (4.09 MB; the documented endpoint of https://poe.ninja/docs/api; the repo reads it in `prices/ninja_items.py`). Counted by the `ninja` check of `docs/research/2026-11-01-buying-any-state-checks.py` over the saved answer.

| Question | Answer |
|---|---|
| Rows | **8,977**, 830 distinct base names. A row is one base at one level and one influence set. |
| Fields of a row | `id`, `name`, `icon`, `levelRequired`, `variant` (only when influenced), `itemClass`, `itemType`, `sparkLine`, `chaosValue`, `exaltedValue`, `divineValue`, `count`, `listingCount`, `detailsId`. The answer has no other top-level key. |
| Item levels | **82 to 86 only**: 707, 1,331, 1,388, 3,308 and 2,243 rows. Nothing below 82 and nothing above 86. The level field is `levelRequired`; the repo reads it as the item level (`base_price_name(name, level, influences)`). |
| Influences | Plain 3,083 rows; the six single influences Shaper 1,597, Elder 1,342, Hunter 708, Warlord 624, Redeemer 593, Crusader 595; **16 dual sets** (435 rows, e.g. `Shaper/Warlord`, `Hunter/Redeemer`), no triple set. Every `variant` is made of the six influences. |
| Fractured | **No row.** No string of any row mentions it. A fractured base cannot be priced from this list. |
| Synthesised | **No row.** (Same check; synthesised bases are not a v1 start anyway, ADR-0027 keeps no such field.) |
| Corrupted, quality, sockets, mods | None. A row is the base alone. |
| Enough observations | `count` is the number of observations behind the price. With the repo's rule (`MIN_COUNT = 5`, ADR-0007) **3,054 rows** are priced: 1,920 plain, 1,134 influenced. 5,923 rows are too thin. 123 priced rows are above 1,000 Chaos (a few observations of mirror-tier bases). |
| Freshness | The response carries `Cache-Control: public, max-age=1800` (seen 2026-11-01). The poe.ninja documentation says responses are HTTP-cached for roughly 5 minutes (ETag), that PoE 1 overviews refresh about every 15 minutes, and that clients making excessive use of the economy endpoints are blocked; it asks for a descriptive User-Agent with a contact and gives no numeric rate limit. The two cache figures disagree (5 and 30 minutes); neither matters for a price file that is allowed to be 7 days old (ADR-0007). |
| History | `GET .../stash/current/item/history?league=...&type=BaseType&id=<row id>` (undocumented, used by `prices/ninja_history.py`) returns 100 daily rows `{count, value, daysAgo}`. For the plain item-level-86 Leather Belt: `count` 14 on day 99, capped at 399 from day 89 to day 59, 262 on day 49, 61 on day 19, 37 today; `value` 2.0, 10.0, 20.0 (day 69), 5.0 (day 29), 10.0 today. So a row's observation count moves by an order of magnitude inside one league. |

Second bulk source: poe.watch `GET https://api.poe.watch/get?category=bases&league=Allflame` (12 MB, 20,655 rows, read by `prices/poe_watch.py`). It has `itemLevel` 83 to 86 (4,202, 4,019, 6,164, 5,726 rows) and one anchor row each at levels 1, 50, 68 and 75 (136 each), an `influences` string with single and dual sets, an integer-rounded `mean` and a `lowConfidence` flag (6,814 rows are low confidence), and `explicits` and `implicits` that are empty on every row. So it adds levels 68 and 75 and a second opinion, not fractured or mod information. Both lists are third-party, undocumented in details, and the repo already treats poe.ninja as the primary and poe.watch as a fallback (ADR-0007).

Craft of Exile's market data (the local copy under `.claude/scratch/coe/`, git-ignored; only its shape is described here, no code): the price file `poec_prices` holds, per league, the sections `currency` (102 lines), `fossils` (25), `resonators` (4), `essences`, `beasts` and `harvest`, and its league index names the poe.ninja league it is read from. **It has no base, no rare and no item-state price.** It is poe.ninja's currency data under another front, useful only as a cross-check of currency (below: conqueror Exalts, Fracturing Orb).

### 1.2 "Realistic by construction"

A start option is offered only if a bulk row lists it: the target's base (the target already fixes the base; choosing between bases of one class is a separate question, section 5), an item level 82 to 86 and an influence set that the row names, with `count` of at least 5. If the list has no row, the option does not exist for the planner: no guessing, no price, no query. Two things stay true about such a row:

- It prices **a base**, not a rare. Everything else on the item (its mods) is whatever the seller left on it; the planner models the start as a normal or rare item with the mods the target or the route says (ADR-0008, R08's rare boots with no mod), and the price is the price of the base. That is the existing convention.
- Rows count listings in poe.ninja's observation, not instant-buyout listings. The trade site's own count for the plain item-level-86 Leather Belt is **15** instant-buyout listings (one search, `status: securable`, rarity normal, item level 86 and up, 2026-11-01), against 1,168 `listingCount` and 37 `count` in poe.ninja's row. The two measure different things, and I did not find which of poe.ninja's listings are priced buyouts. A cautious v1 does not need to resolve it: the row is the price; the instant-buyout rule of the owner is met by the trade check in section 1.4, which is an owner-run step.

### 1.3 How many extra plans a target adds

A plan differs between two start options only through (a) the pool of mods the item level opens, (b) the influence set, and (c) the price. Item levels that open the same pool are one plan, priced at the cheapest row that is at least the lowest level of the group. I counted the groups in the pinned data for the three routes by building the rare pool at item levels 70 to 100 (the `pools` check of `docs/research/2026-11-01-buying-any-state-checks.py`; the count script of section 3.4 repeats it on the runner):

| Route | Base | Pools by item level (equal-pool groups) | Floor the target needs | Plain rows with `count >= 5` at or above the floor | Extra plans |
|---|---|---|---|---|---|
| R05 | Amethyst Ring | 70 / 75 / 80 / {82,83} / 84 / {85 to 100} | 75 (guide: "75+"); the start is a fractured ring | 5 (levels 82 to 86) | 0 for the plain base (the start is fractured, so its price is a trade price, section 1.4); at most 2 if a plain ring could start R05 |
| R08 | Sorcerer Boots | 70 / 75 / 80 / {82,83} / 84 / 85 / {86 to 100} | 86 (35% Movement Speed) | 4 plain rows; only the item-level-86 row (7.4 c, 32 observations) reaches the floor | 0 |
| R13 | Leather Belt | 70 / 75 / 80 / 82 / 83 / 84 / 85 / {86 to 100} | 86 (tier-1 Life) | 5 plain rows; only item level 86 (10.0 c, 37 observations) reaches the floor | 0 |

So on the three benchmark routes the choice is already made by the target; the mechanism earns its keep on a target with a lower floor, where it adds **at most the number of equal-pool groups between the floor and 86 that have a priced row** (3 for a ring with floor 75: {82,83}, 84, {85,86}). Influenced rows add plans only where the target needs an influence mod; there the comparison is large:

| Route to an influenced item | Price today |
|---|---|
| Influenced base row, Leather Belt ilvl 86 | Shaper 4.2 c (13 obs), Elder 5.0 c (20 obs); Crusader (2 obs), Redeemer (1 obs), Hunter (3 obs) are too thin; no Warlord row at 86 |
| A conqueror Exalted Orb on a plain base (Craft of Exile's currency copy, 2026-11-01) | Elder's 105.4, Redeemer's 107.3, Crusader's 111.5, Warlord's 161.4, Shaper's 165, Hunter's 268.4 Chaos |

A ready influenced base at 4 to 5 Chaos is 20 to 40 times cheaper than a conqueror Exalt where a priced row exists, and the same data say that the conqueror route is the only one when no row has 5 observations. The solver needs no change for this: it is a different start item, planned and priced like today's. The price of an influenced item is its row.

### 1.4 The three simple cases, one by one

#### Case 1. The base and its item level, including the recombinator trick

- **Price source.** poe.ninja `BaseType` (section 1.1), with poe.watch as the fallback already in the fetcher. **Trade queries per plan: 0.**
- **Realism test.** A row with `count >= 5` at the wanted level and influence set (3,054 of 8,977 rows pass today).
- **The trick.** ADR-0033: the output item level is `min(floor((A+B)/2 + 2), max(A,B))`, both inputs magic or rare, neither corrupted. The output never exceeds the higher input. So reaching level `N` needs an input that is already at least `N`, and that input could be the start item itself. The trick can lower the cost only if the cheap second input is dearer than the high one, which it is not: one input of level 86 (10 Chaos for a belt) plus an input of level 82 or more (1 Chaos; `A + B >= 2N - 4`), two Transmutations to make plain bases magic, and one combine at about 7 Chaos (ADR-0035) is at least 18 Chaos for an item that the 10 Chaos base already is. The owner's example (an item level 80 and one of 90 giving 87) works arithmetically (`floor(min(87, 90)) = 87`) and needs a level 90 item; nothing at 87 or more is listed by either bulk source (both stop at 86), and for these bases the pool is the same at 86 and at 100. The reading of the formula agrees with the community threads the GPT researcher found (Reddit, September 2024 to April 2026: average plus two, never above the higher input, for the unpredictable recombinator only) and with the wiki's Recombinator page.
- **Does any mod need more than 86?** I checked every mod of an item domain with a positive spawn weight in the 3.29.3.3 data: the highest required level is **86** (21 mods); the only mods above 86 are 62 `delve_area` (map) mods (the `maxlevel` check). On the three benchmark bases the pools at item levels 86, 87, 88, 90, 95 and 100 are identical. **No target can ask for item level 87 or more in 3.29.3.3.**
- **Decision.** v1: choose the base level and influence from the list; **do not offer the recombinator as an item-level source**. Its other use (combining mods of two donors) is #211, section 3.

#### Case 2. A fractured base with one wanted fractured mod

- **Price source.** The trade API only (a fractured base is in no bulk list). The query already exists: `fractured_item: true` plus a `fractured.stat_*` filter with a minimum roll (R05, R10, R11, R12 start items were priced this way and recorded, `tests/fixtures/trade/recorded/start_items/`).
- **What exists today** (search `total` of the recorded runs of 2026-10-31, instant buyout, any listing age): R05 ring, fractured all attributes 13+, item level 75+: **602** listings, 2.6 c (mean of the 5 cheapest); R10 Sorcerer Boots, fractured Movement Speed 30+, item level 84+: **156**, 17 c; R11 Lion Pelt, fractured Chaos Resistance 31+: **42**, 20 c; R12 amulet, fractured Lightning Resistance: **909**, 1 c. New today: a rare Leather Belt of item level 86+ with a fractured Life of 115+ (the tier-1 roll): **9** listings; the cheapest ten were 1, 15, 20, 25, 44, 45 and 99 Chaos and 1 Divine twice (1 Divine = 372.2 Chaos in the price file).
- **Against making it.** A Fracturing Orb costs 159.6 Chaos (Craft of Exile's copy) or 260.4 (price file of 2026-10-31) and fractures one mod of an item with 4 or more mods at random, so a given wanted mod takes four orbs on average and the plain base plus the mods is lost on a miss. The fractured base is 10 to 100 times cheaper than the orb alone. Reddit (reported by the GPT researcher, not opened by me): the common advice is to buy a fractured base on the trade site and finish it with essences, reforges or fossils (r/PathOfExileBuilds, 2024-09-22 and 2025-11-18); one poster priced a fractured +1 arrow quiver at 30 Divine against 3 Divine for an almost perfectly rolled alternative, and argued against buying it (r/pathofexile, 2023-09-24); another regretted a 60 Divine boot craft and wrote he should have bought the fracture (2024-08-06).
- **Candidates and queries per plan.** The candidate fractured mods are the stat texts of the target's leaves that the base can roll and the target accepts; I counted them from the pool and the leaves (the `leaves` check, one trade stat per stat text with its numbers as `#`): R05 five (All Attributes, Life, three resistances), R08 two (Energy Shield %, Movement Speed), R13 five (Life, three resistances, Elemental Damage with Attack Skills, which the target's damage leaf also accepts). Several tiers of one stat text are one query (the minimum roll of the lowest accepted tier). Each candidate is **one search and one fetch = 2 requests** (`price_buy_spec`), so **10, 4 and 10 requests** for R05, R08 and R13. With the recorded limits of 2026-10-30 (search `5:10:60,15:60:300,30:300:1800,600:21600:3600`, fetch `12:4:10,16:12:300,50:300:300,1000:21600:1800`, as hits:seconds:restricted-seconds per rule) that is under every short window: one run, about a minute. The default request budget of a run (4) must be raised to twice the candidate count.
- **Realism test.** The search `total` and at least `MIN_LISTINGS = 3` usable listings (the repo's rule; 5 cheapest used). Candidates with fewer are not offered; the report lists them with the count found.
- **Bound before querying.** A candidate is worth a query only if its best case can beat the plan: `price floor + lower bound of finishing from it < cost of the incumbent plan`. The lower bound of finishing is the `reach_bound` of ADR-0031 (a lower bound on the cost to make the unfinished leaves PASSING, from the pool alone). For R13 (the plan costs 6,311 Chaos at the fixture prices, #66) every candidate passes; for R05, whose start already is the fractured ring, a different fractured mod passes only if its bound is below the current plan. I could not measure the bounds without a build ticket; section 3.4 says how many candidate keys the plans have.
- **Decision.** v1 **as an owner-run priced list**, nothing at plan time: the planner derives the candidate buy specs from the target, the owner runs one command that prices them into the price file (the flow of `prices trade` exists), the planner offers each priced candidate as a start option and keeps the cheapest total. This is ADR-0043's strand-count pattern.

#### Case 3. A base with one wanted mod, normal or magic

- **Price source.** The trade API only; neither bulk list has mods. There is no few-query pricing: one search (and one fetch) per (base, mod, tier).
- **Stock today.** Magic Leather Belt, item level 86+, Life 115+ (tier 1), instant buyout: **2** listings. Normal Leather Belt, item level 86+: 15. The market sells rare items; a magic or normal item with one chosen mod is rare to find because it is not a thing players make for sale.
- **What it would save.** It replaces the first step of an Alteration or Transmutation spam, which is cheap per try (Alteration 0.18 Chaos in the price copy) and, by the numbers of the run in section 3.4, [FILL] for the one-constraint states of R13. A one-mod item that costs more than the spam saves nothing.
- **Realism test.** Same as case 2 (total and 3 usable listings), which on today's belt fails (2 < 3).
- **Decision.** **Not in v1.** It needs one query per candidate for a thin market and saves little. Revisit under v2 with the general mechanism, where "one wanted mod, normal or magic" is just one more key.

### 1.5 Summary of the three cases

| Case | Price source | Queries per plan (cached) | Realism test | Stock seen today | Verdict |
|---|---|---|---|---|---|
| 1. Base, item level, influence | poe.ninja `BaseType` (poe.watch fallback) | **0** | row with `count >= 5` | 3,054 of 8,977 rows | **v1**; no recombinator for item level |
| 2. Fractured base, one fractured mod | trade API | 2 per candidate mod, **4 to 10** on R08, then R05 and R13; 24 h query cache, 7 d price file; limiter of `trade_http.py`; owner-run | search total, at least 3 usable listings | 9 to 909 listings; 1 to 20 Chaos | **v1** as an owner-run priced list |
| 3. One wanted mod on a normal or magic base | trade API | 2 per candidate | same | 2 (magic belt, tier-1 Life) | **v2** |

---

## 2. A realism rule for bought rares without per-state queries

### 2.1 What the evidence says about "how many wanted mods may a bought rare carry"

The owner's intuition: two wanted mods on a rare is realistic, three or more usually is not, and it depends on the league. Evidence I could get:

**Measured stock, by number of wanted mods** (anonymous searches of 2026-11-01, totals only, instant buyout, rare, not corrupted, not mirrored, any listing age, no session; 7 searches, Allflame):

| Item | Wanted mods (all at the tier-1 roll) | Listings |
|---|---|---|
| Leather Belt, item level 86+ | Life 115+ | **466** |
| same | Life 115+ and Fire Resistance 42+ | **112** |
| same | Life 115+, Fire 42+ and Cold 42+ | **25** |
| same, magic | Life 115+ | 2 |
| same, rare, **fractured** Life 115+ | one | 9 |
| Ring, item level 75+ | fractured All Attributes 13+ and Life 100+ | **79** (602 with the fractured mod alone) |
| Leather Belt, normal, item level 86+ | none | 15 |

Each extra wanted mod cuts the stock by 4.2 to 4.5 times on the belt and 7.6 times on the ring. The price of the three-mod belt (one fetch of its 10 cheapest, 2026-11-01): 10, 30, 40, 50, 120 and 155 Chaos, then 1 Divine four times (372 Chaos); the 10 and 30 Chaos listings were listed on 2026-10-13 and 2026-10-28, the others in July and August. The planner's own cost for R13 at the fixture prices is 6,311 Chaos (issue #66; the run in section 3.4 gives today's figure). **So on a belt, three tier-1 mods are on sale, 25 listings, at 1 to 100 times less than the craft costs.** Whether a buyer can find the one he wants, and whether the 3-mod belt has the open affix the bench craft needs, is not in these numbers.

**League dependence.** poe.ninja's own history of one row (section 1.1) shows the observation count of the plain item-level-86 Leather Belt falling from 399 to 37 in 100 days of the league. The same holds for the trade site by the nature of the market: a young league has few listings of anything with tier-1 mods. I found no published series of listing counts by mod count; **no source found** for a typical number of listings of rares with 2 to 3 specific tier-1 mods in 3.28 or 3.29 (the GPT researcher also found none).

**Community.** Reported by the GPT researcher and not opened by me, with dates: players say a fractured base is easier to get than a finished item they would accept (r/PathOfExileBuilds 2024-09-22); they craft when they expect it to be clearly cheaper and buy when it is not (r/pathofexile 2023-06-01 and 2024-05-19); and they complain of price fixing, that is low listings with no intent to sell (r/pathofexile 2020-07-10, 2021-11-21, 2024-04-10). So the cheapest listing is not always buyable; the mean of the 5 cheapest instant-buyout listings (the repo's statistic) damps one bait listing but not a cluster of them.

**A bulk source for rares: none.** poe.ninja has no rare lines. Craft of Exile's market data is currency only. poeprices.info (a machine-learning price predictor for rares that Awakened PoE Trade called) is not usable: fetching `https://www.poeprices.info/` on 2026-11-01 redirected to a domain-for-sale page (the GPT researcher reported the site loaded; I could not reproduce that). GGG's own currency-exchange endpoint (`/api/currency-exchange`, in the developer documentation) is hourly, historical and currency-only. **No source found** that prices a rare by its mods in bulk.

### 2.2 The rule I recommend

1. **Never a fixed mod count as the proof.** Offer a bought item only when a stock test passes: the search `total` for its query is at least `T` listings, and at least 3 of the fetched ones are usable (the repo's existing rule). The test costs **one request** (the search; the `total` is in its answer, no fetch), which is why it is the cheapest league-dependent signal there is.
2. **When no fresh count exists (a plan run from a snapshot), cap the wanted mods a bought item may already carry.** The owner's "two" is a reasonable default: on the belt, one and two mods have 466 and 112 listings, three have 25. The cap is a setting (`max_bought_target_mods`), default **1 in v1** (exactly the cases of section 1: a fractured mod, or none) and 2 in v2 with a stock test. Higher caps need a stock test.
3. **Bulk rows (case 1): `count >= 5`.** It is what ADR-0007 already does for priced bases.
4. **Staleness.** A count older than the price file's 7 days is a warning, as for any trade price; a snapshot older than that does not offer the option.
5. **The report names every refused option** and the count that refused it, as it does for dropped offers, so the owner can lower `T` knowing what he gives up.

The threshold `T` (3, 10, 25) is a taste question: it sets how thin a market the owner is willing to rely on (section 5).

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

What it cannot name is **which junk the item carries**: junk families (ADR-0009 keeps them as slots only when an enabled action reads them) have no filter that says "any junk except...". It can exclude by `not` groups, but the planner does not know which to exclude. A listing is a concrete item, so after the fetch its mods are known. This is why the reset view below works: a priced listing is a **deterministic offer to one concrete state**, not a lottery over junk.

Price rules already in the repo: sort by price ascending, `securable` status (instant buyout, owner's rule, #133), the mean of the `k = 5` cheapest usable listings, at least 3. Awakened PoE Trade's source (`pathofexile-trade.ts`) does the same query shape: status `securable`/`available`/`online`, price ascending, pseudo stats for influence and empty modifiers, a `count` group for "at least 1 of these", one `fetch` of the first ids, rate-limit rules for search and fetch read from the headers, and it sets no User-Agent; it chooses no single price (it returns the rows and the caller shows them). I found no automatic outlier removal in it.

### 3.2 The reset view: every buy offer is a restart to a priced state

A bought item replaces the item in hand, whatever it was. So a buy offer's price and result do not depend on the current state `s`. With buy offers `K` (price `p(k)`, result state `k`),

    V(s) = min( Qcraft(s) , B ),     B = min over k of ( p(k) + V(k) )

where `Qcraft(s)` is the value of the best crafting action at `s` (with `V` at its successors), and `B` is the same constant at every state. Today's `restart` is `K = {start}`, `B = price(start) + V(start)`. Consequences:

- **Buying at the start and buying mid-route are one mechanism.** The best buy is a state `k*`; the plan starts there if `B` beats crafting from the target's start, and returns there after a failure instead of returning to the target's start item. A bought item is "mid-route" only in that it is bought when the route went wrong.
- **The solver needs one fixed point, not an action per offer.** `B` is a number: iterate `B_0 = restart cost`, solve once with restart price `B_i` (the kernels are cached by pool signature, so a re-solve over the same graph is far cheaper than building it), set `B_{i+1} = min_k (p(k) + V_{B_i}(k))`; it falls monotonically and stops when it no longer moves. A reset to a candidate adds the states reachable from it; the kernel cache is keyed by pool signature, so most of them are shared with the graph already built.
- **The separate plans per start option of #330 are exact only if each option restarts to itself.** The optimum restarts to the cheapest start overall; planning each option with its own restart gives an upper bound, and the difference is the fixed point above. #330 can pass the best known start as the restart of every option plan.
- **The reset view does not hold for donors.** A donor is consumed together with the item in hand (recombinator, Awakener, ADR-0022): the item in hand survives, so a donor is a `Need`, an acquisition sub-problem whose goal is a state, with buying as one of its actions (ADR-0022 already says "Buying a donor is an ordinary action of its process (ADR-0011)"). #211 stays separate: a bought donor with chosen base and item level is a buy offer inside the `Need` process, priced the same way (bulk rows for the base and level, trade queries for mods); the owner's 80+90 example is dominated by the argument of case 1.

### 3.3 Lazy generation and admissible bounds

A price is unknown until asked. Three values of a price, kept in the price file with their date:

- **quoted** (`p`, listing count, date): the offer exists.
- **none** (date): a successful search answered `total = 0`. The offer does not exist **now**. Not "unknown": the trade site said so. It holds for every stricter key too (a listing that matches more filters also matches fewer), so one empty search closes a whole cone of keys with no more requests.
- **unknown**: never asked, refused by the limiter (429, 403, Cloudflare), or too old. The solver treats it as not offered, and the answer says so.

**Admissible lower bound of an unknown price.** A listing that matches the stricter key `k` also matches every relaxation `j` of it, so the cheapest `k` listing costs at least the cheapest `j` listing, and the mean of the `k` cheapest of a subset is at least the same mean of the superset: `p(k) >= p(j)` for every quoted relaxation `j` (drop a filter, widen the item level band, lower a minimum roll). Where nothing is quoted, 0 is the bound. This holds for the `k`-cheapest statistic, not for a single listing price, and it needs the drop rules (unknown currency, wrong influence) to be per listing, as in `_chaos_of`.

**Admissible lower bound of the finishing cost** from a candidate state: ADR-0031's `reach_bound` rho times the unfinished leaves, or the solved `V_min(k)` over the states of the key (oracle, tighter). Together:

    skip k  when  LB_price(k) + LB_finish(k) >= B_current

which is the pruning test of ADR-0031 applied to buy offers instead of fossil sets. What is left unqueried is certified: the answer carries two bounds, `B_pess` (best quoted offer) and `B_opt` (adds every unknown offer at its lower bound), the pattern of ADR-0023 / `solve_bounds`. If `B_pess - B_opt` is within the tolerance, the answer is exact for the market as quoted; otherwise the report lists the unknown keys in order of `B_current - (LB_price + LB_finish)`, the most promising query first. Fit with #312: the buy offers add at most `|K|` restart candidates to the graph and no state; with the envelope search of research note 3 (an LAO*-style search "expand only states ... reachable under the current best policy ... stop only when every unexpanded region has a lower bound no better than the incumbent") an unexpanded buy offer is such a region with exactly this bound. Exact merging (#312) shrinks `V_min(k)` lookups because keys are classes. Nothing here changes a transition probability.

**Cached snapshot, zero queries.** The price file is the snapshot (ADR-0007): quoted, none and unknown entries with dates. A plan reads it and never touches the network; it offers the quoted keys and reports the unknown keys that could lower the cost. This is the default mode and is the only mode compatible with section 3.5.

### 3.4 What it would cost on R05, R08 and R13

The count is computed by `docs/research/2026-11-01-buying-any-state-count.py`, run on GitHub through the dispatcher (the plan of each route at the fixture prices, then every solved state projected to its buy key). **[RESULTS]**

### 3.5 Terms and the limiter: why the general mechanism is v2

GGG's developer documentation (https://www.pathofexile.com/developer/docs) says it supports only the resources of its API Reference and its Data Exports, and that reverse-engineering endpoints outside that documentation is against the Terms of Use, section 7i. The trade search, fetch and stats endpoints (`/api/trade/search`, `/fetch`, `/data/stats`) are not in the reference. A GGG web developer gave the same answer in 2021 to a question about the trade data endpoints (forum thread 3108772, 2021-05-04; I read the thread). The documentation also says the rate limits are dynamic and can change at any time, that a 429 carries `Retry-After`, that exceeding limits frequently gets an application's access revoked, and that macros must be started manually by the user (timers and other automated triggers are not allowed); it lets a website cache more broadly. The Terms of Use, as read through a page reader and not checked against the page itself, list among the restrictions (7c, 7e, 7f, 7i) automated software or bots, connecting through software other than the game client, data-gathering tools on the website, and reverse engineering. The repo's own conclusion (ADR-0007, 2026-10-30) is the cautious reading: the fetcher runs only when the owner starts it, with few requests. Tools in wide use (Awakened PoE Trade, Path of Building's trade query) send the same queries from the user's machine on a user action, and a GGG post of 2025-06-26 (reported by the GPT researcher, not opened by me) says a tool's rate limit also limits the user on the website.

The practical limits from the recorded headers (2026-10-30, the limiter reads the live ones): the search rule allows 5 hits per 10 s, 15 per 60 s, 30 per 300 s and 600 per 6 hours; breaking them restricts for 60 s, 300 s, 1,800 s and 3,600 s. The fetch rule allows 12 per 4 s, 16 per 12 s, 50 per 300 s and 1,000 per 6 hours. A priced state is one search plus one fetch, so **a run gets about 30 queries (the 300 s window; the limiter stops a wait over 120 s) and a day at most about 2,400 (4 x 600)**. The eleven requests I made today (7 searches, 2 searches and 2 fetches) drew no 429.

So "lazy generation during the solve" cannot mean an unattended loop of queries: it means **a list of next queries that the owner's command runs, then a re-plan**, unless the owner widens ADR-0007. That is an owner decision (section 5, v2).

---

## 4. Recommended design

**v1 (no trade query at plan time):**

1. **Start options from the bulk base list.** Extend the planner so that, for a target, the start options are the rows of the price file for its base: the item levels at or above the target's floor, one plan per equal-pool group (cheapest row in the group), influenced rows only when the target asks for an influence mod. The target's `item_level` becomes a floor; a bought item is priced from its row; a row with fewer than 5 observations does not exist for the planner. Answer: the cheapest total start price plus plan. `restart` returns to the cheapest start, so the options are planned jointly (section 3.2), not one by one.
2. **No recombinator as an item-level source.** Say so in the explanation of the plan (the trick is dominated) rather than offer it.
3. **Fractured one-mod starts as an owner-run priced list.** Candidates from the target (5, 2 and 5 for R05, R08 and R13), priced by the existing trade flow into the price file, each offered if the stock test passes; the start options are the cheapest of all. This is also the place for the recipe-made starts of #330: same list, a constructed price instead of a quoted one.
4. **`max_bought_target_mods = 1` and the stock test of section 2.2**, both visible settings (and #323 item 9 becomes: buy offers off / start base only / start base and one fractured mod / more, with the stock test).
5. **Cached snapshot is the only mode.** The report lists the candidate options that had no price and the order of queries that would settle them.

**v2:**

6. The general mechanism (sections 3.2 and 3.3): buy keys at compressed states, the reset fixed point `B`, quoted/none/unknown prices with the monotone bound, the two-bound answer with the next-query list, after #312's solver is in.
7. Concrete listings as offers (fetch the 10 cheapest, map each to its compressed state, one offer per distinct state), which needs the listing's mods mapped to game mods.
8. Donors as buy offers inside `Need` (#211), mid-route bought intermediates, mods carried by a bought rare above the v1 cap, one-mod normal or magic bases, SSF mode (no prices), and the budget interplay (#323).

## 5. Questions for the owner's design grill

### v1

1. **May the planner choose the start base level and influence by itself, treating the target's item level as a floor?** Today the target fixes it. Consequence if yes: extra plans only where a target has a low floor (0, 0 and 0 on R05, R08, R13), and a route page that names the base level it bought. Recommendation: yes.
2. **Is a priced fractured-base list (2 requests per candidate mod, 4 to 10 per target, run by the owner) acceptable in v1, or does the first v1 ship only the bulk base list?** Consequence: with the list, R05, R08 and R13 get 5, 2 and 5 fractured options, each a solve of its own unless the options share one graph (a build ticket measures it). Recommendation: include it, behind the setting.
3. **How thin may a market be for an option to count as existing?** 3 usable listings is the repo's rule today; 10 or 25 shuts out the 9-listing fractured belt. Your taste on risk of a mirage listing; recommendation: 3 for bulk-priced, 10 for trade-priced, one setting.
4. **How many wanted mods may a bought rare already carry in v1?** Recommendation: 1 (a fractured mod), because beyond that only a stock test of a live search says whether the item exists; on a belt three tier-1 mods are on sale at 25 listings, so a cap of 2 or 3 is defensible if you accept a stock test later.
5. **Which price of a listing do you trust?** The mean of the 5 cheapest instant-buyout listings (today), or the median of the 10 cheapest, which damps a cluster of bait listings. Recommendation: keep the mean of 5, flag a spread above 10 times.
6. **When the plan cannot reach the cheapest start (for example it wants a fractured mod that has no listing), may it fall back to the target's own start item silently?** Recommendation: yes, with the report line.

### v2 (#325)

7. **May the planner send trade queries itself in a bounded loop, or only list the next queries for you to run?** GGG's documentation calls these endpoints unsupported and unattended use unwelcome (section 3.5); the cautious reading of ADR-0007 is the list. This decides whether lazy generation is a loop or a to-do list.
8. **Is "three or more skipped steps is unrealistic" (#325) a count of crafting steps skipped, or a stock test?** The stock test measures existence; the step count measures how reproducible the route is for other players. The two can disagree (25 belts with three tier-1 mods exist).
9. **A bought item is priced as one concrete listing or as a class with optimistic junk?** Recommendation: concrete listings (exact), at the price of a mapping ticket.
10. **How much of the saved cost should the answer show?** A buy that beats the craft by 100 times (R13: 6,311 Chaos against 10 to 155 Chaos for a belt with three tier-1 mods and an open affix) may mean the target is not worth crafting; should the report say "buy this" instead of a route?
11. **SSF and budgets (#323).** With no prices, buy offers do not exist; with a budget, a reset has a cost the budget must count. Does the owner want the buy fixed point inside the budget search from the first day?

## 6. Where each point of the issue is answered

| Point of the issue | Where |
|---|---|
| Can the trade API price "an item matching state X" (filters) | 3.1 |
| Rate limits, freshness, sparsity | 3.5 (limits), 1.1 and 2.1 (freshness, sparsity) |
| Cache and "no listing" (not buyable vs unknown) | 3.3 |
| Other sources: poe.ninja, Craft of Exile, any public price API | 1.1, 2.1 |
| Instant-buyout only | 0, 3.1 |
| A buy offer fits the SSP-MDP | 3.2 |
| Interaction with #312's solver; bounds admissible with an unknown price | 3.3 |
| Vendor recipes (#329, #330) and #211 as special cases | 3.2 (restart fixed point, donors), 4 item 3 |
| What #323 item 9 becomes | 4 item 4 |
| Queries per route on R05, R08, R13; zero-query snapshot | 1.3, 1.4 (v1), 3.4 (v2), 3.3 (snapshot) |
| Recommended design; v1/v2 questions | 4, 5 |

## 7. Sources, and what was not found

Primary:

- GGG developer documentation: https://www.pathofexile.com/developer/docs (policies, User-Agent, rate-limit headers, `Retry-After`, 429, "Macros must be invoked manually", section 7i sentence), https://www.pathofexile.com/developer/docs/reference (currency exchange: hourly, "purely historical"; public stash API needs the `service:psapi` scope; no trade-search endpoint), Terms of Use https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy (clauses 7c, 7e, 7f, 7i; clause 22 "You must comply with Grinding Gear Games' technical documentation and policies").
- GGG forum thread 3108772 (2021-05-04, a GGG "Web Developer"): the 7i answer, read by me.
- poe.ninja: https://poe.ninja/docs/api (stash overview, `BaseType`, caching, no numeric limit), the `BaseType` overview and one history row, read 2026-11-01.
- poe.watch `get?category=bases`, read 2026-11-01.
- The repo: ADR-0007, 0008, 0009, 0011, 0022, 0031, 0033, 0035, 0043; `src/crafting_system/prices/trade_http.py`, `trade_pricing.py`, `trade_query.py`, `trade_stats.py`, `ninja_items.py`, `poe_watch.py`; `src/crafting_system/cli/_offers.py`, `_plan.py`; the recorded trade answers and headers in `tests/fixtures/trade/recorded/` (2026-10-30 and 2026-10-31) and the price fixture `tests/fixtures/prices/routes-allflame-2026-10-31.json`; `docs/research/2026-10-30-3-multi-item-recombinators.md`; `docs/research/2026-10-31-vendor-recipes.md`.
- Craft of Exile's local copy (git-ignored): the shape of its price file only.
- Awakened PoE Trade source, https://github.com/SnosMe/awakened-poe-trade `renderer/src/web/price-check/trade/pathofexile-trade.ts`, read through a page reader.
- My own measurements: 11 anonymous trade requests of 2026-11-01 (7 searches for totals, then 2 searches and 2 fetches), no session, none refused; the poe.ninja and poe.watch answers; the pool counts per item level and the mod levels from the pinned data.

Second-hand, from the GPT researcher (job `20261101-183427-0bf1`, model luna) and not opened by me: the Reddit threads and quotes of sections 1.4 and 2.1, the 2018 and 2021 forum posts on caching and per-IP limits, a GGG post of 2025-06-26 on tool and website limits, the item-level formula threads of 2024 to 2026, Awakened PoE Trade's discussion #735. They agree with what I read first-hand and none carries a number the design depends on.

**Not found:** a typical number of listings for rares with 2 to 3 specific tier-1 mods across 3.28 and 3.29; general price bands for fractured mods or for item level 84, 86 and 87 bases; a measure of how liquid half-finished items are; a bulk source for rares, fractured bases or items with mods; any GGG statement that permits unattended use of the trade endpoints (the documentation says the opposite for endpoints it does not document); which poe.ninja listings are priced buyouts; the trade site's query-complexity limit (the answers showed `complexity` 12 to 15 and no refusal); whether poeprices.info is alive; a source that someone prices recombinator donors by trade search.
