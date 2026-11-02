# Audit INPUTS: game data, prices, claims, hand-written example files (ticket #396)

Scope read in full: `data/` (model, normalize, load, elevated, resolve), `prices/` (price_file, price_names, price_source, trade_market,
trade_pricing, trade_query, trade_stats, fetch, poe_ninja, ninja_items, ninja_history, poe_watch, previous_league, fallbacks, default_prices,
http_json, __main__), `rules/registry.py`, `rules/stale.py`, all 44 claims files (statements, kinds, patches, values), `examples/buy/*.yaml`,
all `examples/targets/*.yaml` (start items and prices), both price fixtures, the recorded trade fixtures, the tests that use them.
Skimmed only: `data/diff.py`, `impact.py`, `candidate.py`, `pin.py`, `fetch.py`, `__main__.py` (patch-update tooling), `trade_http.py` rate-limit internals.
Nothing was sent to the trade API or a price service. Real data: `local/cache/repoe-fork/3.29.3.3`. Helper scripts are in the session scratchpad
(`recon.py` reconciles every target with its buy spec; `chk_tiers.py` checks every written start-mod tier).

Reconciliation matrix produced by `recon.py` (target base vs buy spec), the base of most findings below:

| route | target base, ilvl | buy spec / price | verdict |
|---|---|---|---|
| R04 | Penetrating Arrow Quiver (QuiverNew5), 81 | poe.ninja line of ilvl 85 stored as "(ilvl 81)" | other item, other source (INPUTS-4) |
| R05 | Amethyst Ring, 75 | category ring, no base | other item (INPUTS-1) |
| R08 | Sorcerer Boots, 86 | normal Sorcerer Boots 86+, plus a hand-added Alchemy | hidden step (INPUTS-5) |
| R09 | Two-Toned Boots (BootsAtlas1), 86 | `type: Two-Toned Boots` (3 bases share the name) | ambiguous (INPUTS-6) |
| R10, R11 | Sorcerer Boots 84, Lion Pelt 84 | same base, ilvl 84+ | consistent |
| R12 | Paua Amulet, 84 | category amulet, no base, ilvl 75+, no tier | other item (INPUTS-1, 9) |
| R13 | Leather Belt, 86 | poe.ninja line, no spec | not the owner's source (INPUTS-12) |
| R14 | Thicket Bow Hunter, 78 | `rarity: nonunique` against a "normal" comment | wider than described (INPUTS-13) |
| V01 | Lion Pelt, 84 | hand price | invented (INPUTS-12) |
| R03, R06, J01 | Velour Boots 100 (fractured T1 mod), Hunter Heavy Belt 75, Cobalt Jewel | no `start_price` | start counted free (INPUTS-8) |

---

### INPUTS-1: R05 and R12 buy specs name no base, so the priced item is not the planned item   [CONFIRMED] [impact: high]
- Where: `examples/buy/r05-start-ring.yaml:5-9` (`category: accessory.ring`, no `base_type`), `examples/buy/r12-start-amulet.yaml` (`category: accessory.amulet`, `item_level_min: 75`, no `minimum` on the mod); targets `examples/targets/r05-strength-ring.yaml` (base Amethyst Ring, ilvl 75) and `r12-lightning-amulet.yaml` (base Paua Amulet, ilvl 84); fixture entries `R05 start ring` 2.6 c and `R12 start amulet` 1.0 c.
- What it does: the trade search covers every ring (602 listings) or amulet (909 listings); the planner then starts from an Amethyst Ring / Paua Amulet and charges the floor of the whole category. The comment in the spec says "every plain ring has the same pool of mods".
- What it should do (owner rule: a bought item is "the tier priced on the trade site"; one fact in one place): price the base the plan starts from, or plan from the base that was priced.
- Evidence: the recorded answers `tests/fixtures/trade/recorded/start_items/fetch_r05.json` and `fetch_r12.json` hold the ten cheapest listings the price was made of. R05's five cheapest (mean 2.6): Paua Ring 1 c, Paua Ring 2 c, Moonstone Ring 3 c, Bone Ring 3 c, Bone Ring 4 c; no Amethyst Ring among all ten. R12: ten listings, all 1 c: Turquoise x2, Agate x4, Lapis, Seaglass (an atlas base), Coral, one Paua Amulet (ilvl 78); the five used are Turquoise, Agate, Lapis, Turquoise, Seaglass, so the price (1.0) is a floor with no information in it. The claim "same pool" is false for the Bone Ring: tags `ring_can_roll_minion_modifiers`; pool at ilvl 75 by `spawn_weight`: Bone Ring 210 mods, Amethyst Ring 188 (22 minion mods more) and 3 of R05's 5 priced rings are Bone Rings. R12's spec searches ilvl 75+ while the target plans ilvl 84 with `tiers_top_at_item_level: true` (recorded ilvls 78 to 85); its comment says 75 is the level the +1 Lightning prefix needs (true: `GlobalLightningGemLevel1` level 75) and the target's 84 is a second hand-written level for the same item. The mod has no `minimum`, so any of the 8 tiers of Lightning Resistance qualifies, while the target writes one mod (INPUTS-9).
- Impact: R05, R12 start prices and everything built on them (R05 mean, benchmark, the owner's page). The Chaos error itself is small for R12, unknown for R05, but the mechanism makes a price mean something other than what the page says. No test reconciles a spec with its target (`grep` of tests: none).
- Origin: `3c123fc` (#60, 2026-10-31) "R10, R11 and R05 end to end"; R12 spec from #26; the spec wording was a convenience ("the guide says only rare ring") and nobody compared it with `base: Amethyst Ring`.
- Pattern: one fact (the start item) described by hand in two files with nothing that compares them.

### INPUTS-2: the plan reads the raw start price; age, listing rail, league and the `price_source` setting are never applied   [CONFIRMED] [impact: high]
- Where: `cli/_plan.py:216-237` (`resolve_start_price`: `prices.prices.get(name)` then `.chaos`), `cli/_starts.py:plain_candidate`; the owner-rule code is `prices/trade_market.py:offer` and `prices/price_source.py:source_price`, which no code outside `prices/` calls (grep). `cli/_main.py` docstring: "The plain start item and recipe starts do not read it".
- What it does: any entry under the start name is used: a 670-day-old trade price, a 3-listing "thin" price, another league's price, a poe.watch or Standard price.
- What it should do (owner: "Prices refresh by the system itself", "stale sources lose"; ADR-0007 amendment of #337: a quote older than 7 days is not offered): use the price only if `offer()` says it is offered, else say so.
- Evidence (run): fixture `R05 start ring` copied with `detail.date = 2025-01-01` and `listings = 3`; `resolve_start_price(...)` returns `StartPrice(name='R05 start ring', chaos=2.6, source='trade-api')`; `source_price(..., 'trade', date(2026,11,2)).reason` for the same file says "trade price is 670 days old (limit 7)". `--price-source` and `crafting.toml price_source / price_gap_percent` change nothing for any current target (config docstring and CLI help say they choose "which price a bought start item is priced with"). `stale_trade_warnings` is called only by `prices check`; `stale_warning` in the CLI counts the date of the poe.ninja fetch (`fetched_at`), which a re-fetch renews while it keeps older trade prices (`merge_trade_prices`).
- Impact: every route with a bought start; a refresher that lags (it is not built; #360) leaves the planner pricing on week-old or month-old quotes with a clean page. The trade prices in both fixtures become "stale" under the rule from 2026-11-08 (R05, R10, R11, R12 dated 10-31) and 2026-11-09 (R08, R09, R14 dated 11-01) and nothing in the planner would notice.
- Origin: #26 (`2dcbe31`) wrote `resolve_start_price`; #355/#357 (market rule, `price_source`) added the rule as a separate module and left the planner out; ADR-0061 decision 2.
- Pattern: a rule built as a module and not wired to the code path it was written for; two prices paths (raw and rule-checked).

### INPUTS-3: the route page drops the source and age of every price   [CONFIRMED] [impact: high]
- Where: `cli/_route_view.py:388` (`for name, count_, chaos, _ in priced.parts`: the source is thrown away), `:471` and `buy_row` (start price: no source, no date), `:553` ("Prices: league X, fetched DATE" is the only provenance); the text report prints `[source]` for the start item only (`_report.py:305`). `cli/_interval.py:229` marks only `default` (Dust/Gold) and only on the interval path.
- What it does: a price from `poe.ninja-previous-league` (another league, 99 days old), `poe.ninja-standard`, `poe.watch`, `poe.ninja-history`, `hand`, `override`, `default`, or a stash price "kept" from an old fetch after a failed overview, appears as a plain number. A hand override (`price_overrides.toml`) has no date and no mark and beats a fresh fetched price forever; the file-level date is the date of the last fetch even if some entries are kept from an older one.
- What it should do (owner: "unknowns get the best estimate and an approximate mark", "stale sources lose"): mark every price that is not a current price of this league, with its source and date.
- Evidence: fixture `routes-allflame-2026-10-31.json` contains 7 essences priced from the previous league Mirage at league day 99 (`Screaming Essence of Anguish/Hatred/Loathing/Spite`, `Shrieking Essence of Fear/Hatred/Spite`) and 3 from poe.watch (`Screaming Essence of Zeal`, `Shrieking Essence of Rage/Wrath`); `grep` for `previous`, `poe.watch`, `hand` in `cli/` finds nothing that prints them. The warning exists only as a line printed at fetch time (`previous_league.py` "a different economy, check it") and as the entry note, which no output reads.
- Impact: any route using such an essence/fossil/base; the JSON report keeps `price_source` per part (`_report.py:535`), the owner's page does not.
- Origin: #40 (fallback chain, 2026-10-30) built the stamps; the route view (#78, `0c28c70`) was written against `parts` and kept the first three of four tuple fields.
- Pattern: provenance recorded at write time and discarded at read time.

### INPUTS-4: R04's start price is a different item from a different source, picked as the cheapest line   [CONFIRMED] [impact: medium]
- Where: fixture `Penetrating Arrow Quiver (ilvl 81)` = 9.0, source `poe.ninja`; `examples/buy/r04-start-quiver.yaml:1-7`; `examples/targets/r04-penetrating-quiver.yaml` (`start_price`, `item_level: 81`, `tiers_top_at_item_level: true`); `tests/golden/packed_values.json` (R04 69,257.54).
- What it does: the stored name says ilvl 81, the price is poe.ninja's cheapest normal line of ilvl 85 (43 observations), chosen as the minimum over lines; the trade search for the spec found 3 listings, mean 130 Chaos (the spec comment says so). The planner plans a quiver of ilvl 81 priced as an ilvl-85 one.
- What it should do: owner rule is the trade price (3 listings is `thin` under the 10-listing rail, so the fallback to poe.ninja is legitimate) but then with the line's real ilvl and a mark; the name should not claim 81. Taking the minimum of several noisy lines is a biased pick, not "mean of the cheapest few".
- Evidence: fixture note quoted above; the price can never be refreshed by the system: `prices/__main__.py:200` and `trade_pricing.refuse_name_collision` refuse a `trade` run on a name that holds a poe.ninja price, and the spec name equals that name by design.
- Impact: R04's total (start 9 c vs the 130 c the trade site showed) and the golden values (`R04 69,257.54`) which freeze it.
- Origin: `d2432f4` (#70, 2026-11-01).
- Pattern: hand-picked price filed under a name that claims more than it is.

### INPUTS-5: R08 and R09 fold an Orb of Alchemy into a `trade-api` price (a hidden step) and a test freezes it   [CONFIRMED] [impact: medium]
- Where: fixture `R08 start boots` 29.82716 and `R09 start boots` 5.02716 (note: "trade price of a normal base ... plus one Orb of Alchemy (0.02716): the start item is that base made rare; see the target"); `examples/buy/r08-start-boots.yaml:8-12`; targets `start_item: {rarity: rare, mods: []}`; `tests/test_cli_r08_r09_real.py:35,60-66` (`test_the_start_boots_cost_their_trade_price_plus_an_alchemy`).
- What it does: the spec buys a normal base, the target starts from a rare with no mods (a state that cannot exist), the cost of the Alchemy that makes it rare is added by hand to a number labelled `trade-api` whose `detail` (query hash, listings 22) is that of the unmodified search. The page shows "Buy R08 start boots 29.83" and no Alchemy step.
- What it should do (owner: "Show every in-game step; never hide one"): the Alchemy is an action of the route (the claims and action exist: `alchemy.*`), priced from the file; the price entry is the trade quote alone.
- Evidence: fixture entries above; a refresh by the scheduled refresher rewrites the entry to 29.8 and silently drops the Alchemy.
- Impact: R08/R09 pages (a missing step), their start price (0.027 c, negligible in Chaos but the entry no longer equals its own query), and the test treats the fold as the specification.
- Origin: `60013ba` (#63, 2026-11-01).
- Pattern: a computed sum stored as a measured value; a test whose oracle is the fixture it checks.

### INPUTS-6: one price key per base *name*, but several bases share a name (R09 has three, R04 two)   [CONFIRMED] [impact: medium]
- Where: `examples/buy/r09-start-boots.yaml` (`base_type: Two-Toned Boots`), target `r09-life-boots.yaml` (`base: Metadata/Items/Armours/Boots/BootsAtlas1`); `price_names.base_price_name` (name + ilvl + influences); `trade_query.TradeQuery.type`.
- What it does: the game data has three released bases named "Two-Toned Boots": BootsAtlas1 (dex/int: Evasion 126-145 + Energy Shield 26-30, cold and lightning resistance implicit), BootsAtlas2 (str/dex: Armour + Evasion), BootsAtlas3 (str/int: Armour + Energy Shield). The target pins BootsAtlas1 by id; the buy spec, the stored query (`"type": "Two-Toned Boots"`) and the poe.ninja key `"Two-Toned Boots (ilvl 86)"` cannot tell them apart, so the 5.03 c is the mean over whichever variants are cheapest. Same for `Penetrating Arrow Quiver` (QuiverNew5 vs the legacy Quiver12 tagged `trade_market_legacy_item`), `Leather Belt` / `Heavy Belt` (a Royale copy each, harmless because `not_for_sale`).
- What it should do: a price is for one base id (or the spec must carry the trade site's discriminator); a name shared by several bases should be refused, as `targets/resolve.py` already does for the target side.
- Evidence: `recon.py` output ("3 released bases are called Two-Toned Boots"), data dump of the three bases above.
- Impact: R09 start price and the item the trade link on the page searches.
- Origin: #63 (R09 spec); the target side was fixed with an id (comment in r04 target), the price side never was.
- Pattern: the same entity named by a string on one side and an id on the other.

### INPUTS-7: the buy step on the page does not print the base, and is titled by the internal price key   [CONFIRMED] [impact: medium]
- Where: `cli/_route_trade.py:74-98` (`_accepts`: rarity, item level, influence, corrupted, mods; no `base_type`, no `category`), `cli/_route_view.py:471` (`title = f"Buy {price.name}"`).
- What it does: "Buy R05 start ring / Accepts: Rare, item level 75 or more, no influence, not corrupted, fractured: +# to all Attributes (at least 13)": a reader cannot see that no base is asked for (INPUTS-1), nor that R09 means one of three bases (INPUTS-6); the title is a route id that the owner never wrote ("R05 start ring"). The name doubles as price key and display text (`BuySpec.name`).
- What it should do: say what to buy in words a player uses ("a rare Amethyst Ring..."), keep the price key out of the page.
- Evidence: reading of `_accepts`; `tests/test_cli_route_view.py:195` asserts the title `"Buy R12 start amulet"`.
- Impact: every route page with a bought start.
- Origin: `0c28c70` (#78).
- Pattern: an internal key shown as a label.

### INPUTS-8: a target without `start_price` has a free start item (R03, R06, J01)   [CONFIRMED] [impact: medium]
- Where: `cli/_plan.py:228-229`; `examples/targets/r03-avoid-shock-boots.yaml` (comment: "no price: the file has no buy spec for it, so the planner treats it as free until one is added"), `r06-strength-heavy-belt.yaml`, `j01-cobalt-life-attack-speed.yaml`.
- What it does: R03 starts from Velour Boots ilvl 100 with a fractured tier-1 Suppress Spell Damage mod, R06 from a Hunter-influenced Heavy Belt, J01 from a rare Cobalt Jewel; all three cost 0. The page prints "Cost per use: free" (`_route_view.py:465`), which reads as "this is free in the game", not "no price known".
- What it should do (owner: the best estimate and an approximate mark; "a bought start item is the tier priced on the trade site"): refuse, or estimate and mark.
- Evidence: `recon.py`; `resolve_start_price`.
- Impact: the means of these three targets omit the largest cost of the first two (a fractured T1 base, an influenced base).
- Origin: `f6861f1` (#19) default, kept when #26 added prices.
- Pattern: a default that decides an economic question.

### INPUTS-9: written start-mod tiers are never checked against the data; R12's is wrong (T3 for a tier-7 mod)   [CONFIRMED] [impact: medium]
- Where: `examples/targets/r12-lightning-amulet.yaml` (`mod: LightningResist2, tier: 3, values: [14]`), `targets/parse.py:1062-1088` (`read_start_mod` stores `tier` as written; docs: "tier derivation is not built yet", but `items/tiers.py` exists since #23).
- What it does: `LightningResist2` is "of the Squall", level 13, +(12-17)%; on Amulet1 `mod_tier` gives **7** (levels 84, 72, 60, 49, 37, 25, 13, 1). The start card of the page shows the written 3. The buy spec prices any tier and any roll. The same script over all other start mods (R03, R05, R10 x2, R11) found the written tier equal to the computed one and values inside the range.
- What it should do: derive tier from the data (`mod_tier`) or refuse a written tier that disagrees; or let a bought mod say "unknown tier" (the spec prices `minimum` only).
- Evidence (run): `chk_tiers.py` prints `r12 ... written tier 3 computed 7 values [14] range [(12, 17)]`.
- Impact: R12 start card; any rule that reads the item's stored tier (tier-based requirements, recombinator odds if R12-like starts feed them). Also each start mod has one hand-picked roll (`values: [14]`, `[33]`, `[14]`) while the buy spec accepts a range.
- Origin: `f6861f1` (#19, 2026-10-30) "tier taken as written": the docs block of `targets/__init__.py` and the R12 target were written together (`mod: LightningResist2, tier: 3, values: [14]`) before tier derivation (#23, `590a731`); the R12 file was never revisited.
- Pattern: a documentation example promoted to a real example; a value the code could derive left to be typed.

### INPUTS-10: previous-league and Standard fallbacks take the Chaos number unscaled across economies   [CONFIRMED in code; size SUSPECTED] [impact: medium]
- Where: `prices/previous_league.py:119` (median of the old league's Chaos rows, stored as the price), `ninja_history.exchange_rows` (`pair id == "chaos"`).
- What it does: a Chaos price in Mirage at day 99 is stored as Allflame's price. The units move: Allflame has 1 Divine = 372.2 Chaos; the research note records another economy at 104.9 Chaos per Divine (CoE) and Allflame's 383, so the factor between leagues can be several-fold. The price should pass through Divines (old price / old Divine rate x current rate).
- What it should do (owner: stale sources lose; wrong economy is not a price): scale through the Divine rate of both leagues, or leave the name unpriced.
- Evidence: reading of `take()`; fixture has 7 such prices (INPUTS-3).
- Impact: only names with no current price; today essences. Unknown magnitude.
- Origin: #40 (2026-10-30), ADR-0007 ("a different economy and say so", but the warning only).
- Pattern: a unit read as comparable across contexts.

### INPUTS-11: the bench is documented as refused below the craft's item level, and no code refuses   [CONFIRMED (docs vs code); game effect SUSPECTED] [impact: medium]
- Where: `actions/bench.py:13` (docstring: "refused ... below the mod's required item level"), `BenchCraft.outcomes` (`:207-251`: no level test), no claim in `bench_craft.yaml`.
- What it does: the data gives the crafts required levels 60 to 81 for about 700 of the 732 options (`required_level` histogram: 20:36, 30:56, 40:50, 50:52, 60:180, 68:47, 72:129, 75:34, 80:6, 81:126). Run: `BenchCraft('EinharMasterIncreasedLife2').outcomes(data, Item(Ring10, 30, RARE, ...))` is accepted although the craft has required level 40.
- What it should do: either the gate (game: the bench lists an item-level requirement per craft; the source for it should be a claim) or the docstring corrected and a claim saying the data's level is ignored.
- Evidence (run): `benchgate.py` prints `EinharMasterIncreasedLife2 required_level 40 on an ilvl 30 item: ACCEPTED`.
- Impact: any route using a bench craft on an item below the craft's level; which example routes cross the line was not measured (the ring offers only the level-40 Life craft; boots, helmets, belts offer the higher ones).
- Origin: `85b36ce` (#334 moved the module), the gate was promised in the original bench ticket.
- Pattern: a docstring that states a behaviour the code lacks; code behaviour with no claim.

### INPUTS-12: the committed fixtures freeze hand, poe.ninja and folded prices against the owner's trade rule   [CONFIRMED] [impact: medium]
- Where: `tests/fixtures/prices/vendor-v01-2026-11-01.json`: `Lion Pelt (ilvl 84)` 2.0, `Sorcerer Boots (ilvl 84)` 3.0, `General's Helmet (ilvl 84)` 2.0, `Quicksilver Flask` 1.5, `Vendor recipe gems (minion, 40% quality)` 6.0, source `hand`; `routes-allflame-2026-10-31.json`: `Leather Belt (ilvl 86)` 10.0 source poe.ninja, "a normal Leather Belt"; tests `test_vendor_benchmark_real.py`, `test_cli_r13_real.py`, `test_cli_routes_real.py`, `packed_values.json`.
- What it does: V01's start and goods are numbers a person typed; R13's start is a poe.ninja base line (the line carries no rarity: the word "normal" is the note's). The research of 2026-11-01 (`docs/research/2026-11-01-buying-any-state.md` lines 58-59) found the trade site has 15 instant-buyout listings of the plain ilvl-86 Leather Belt against poe.ninja's 1,168, and R08's poe.ninja row at 7.4 c against 29.8 c on the trade site: the same item, a four-fold difference by source.
- What it should do (owner: instant buyout, mean of the cheapest few): the trade price where the market rule holds, else poe.ninja marked, and no typed number as a price.
- Evidence: the fixtures and the research lines above. Provenance is also loose: both fixtures say `fetched_at 2026-10-31T12:37:32Z` while entry notes are dated 2026-11-01 (poe.ninja overviews "2026-11-01"), and the V01 file is named 11-01; `hand` entries live in `prices.json`, which the next `fetch` rewrites (only `price_overrides.toml` survives).
- Impact: the V01 and R13 benchmark means, golden values; tests assert them as truth.
- Origin: #331 (V01), #63; V01 notes say "the refresher does not fetch this line yet (#360)".
- Pattern: fixtures standing in for the source the owner named.

### INPUTS-13: R14's spec asks "nonunique" and says "normal"   [CONFIRMED] [impact: low]
- Where: `examples/buy/r14-start-bow.yaml:4,8` (comment "as it drops (normal)", `rarity: nonunique`); fixture 13.0 c over 164 listings.
- What it does: the query admits magic and rare bows with the Hunter influence (a rare with good mods costs more, a junk one less); `_chaos_of` filters influence and fractured but never rarity.
- What it should do: `rarity: normal` as the target starts normal, or mark that the market is thin for normal.
- Evidence: `recon.py`: "spec rarity nonunique vs start item normal". Commit `d2432f4` has no reason for the choice.
- Impact: R14 start price.
- Origin: `d2432f4` (#70).
- Pattern: spec text and spec value disagree.

### INPUTS-14: the owner's minimum sample is applied to stash lines only   [SUSPECTED] [impact: low]
- Where: `poe_ninja.py:79` (`thin = volume <= 0`), `fetch.py` (`MIN_COUNT = 5` only for stash lines).
- What it does: an exchange line traded once is priced. The fixture holds round low-sample essence prices: `Screaming Essence of Dread` 5.0, `Fear` 4.0, `Torment` 5.0, `Envy` 1.0, `Shrieking Essence of Torment` 10.0.
- What it should do: a stated minimum for all lines, or the rule named as stash-only in the ADR.
- Evidence: reading; the fixture values.
- Impact: essence and fossil costs on routes that use them.
- Origin: #21 (2026-10-30), #40 (stash minimum).
- Pattern: a rule applied where it was easy to apply.

### INPUTS-15: two imprint claims say "UNVERIFIED ... 2014 ... not rechecked for 3.29" and are not marked approximate, yet code reads them   [CONFIRMED] [impact: medium]
- Where: `rules/claims/imprint.yaml` `imprint.consumed_on_restore`, `imprint.several_per_item` (`patch_verified: "1.1.0"`, `source_kind: experiment`, forum threads read second-hand); read by `actions/imprint.py:61-62`; the other 11 "UNVERIFIED/UNSOURCED" claims are not read by code, and the recombinator Dust/Gold ones are `approximate: true` as they should be.
- What it does: an imprint is a consumed single-use object and many may be held, on the strength of two 2014 forum answers; ADR-0028 would list the claim on every answer only if `approximate: true`.
- What it should do: `approximate: true` with a reason (the registry supports it), or an in-game check on the owner's list.
- Evidence: `claims_unverified` scan (statements starting UNVERIFIED), `grep consumed_on_restore src`.
- Impact: any plan using an imprint restore; no example target does today.
- Origin: batch B5 (ADR-0060, #219).
- Pattern: provenance written in the free text and not in the machine field.

### INPUTS-16: `items/tiers.py` and `mod_tier.scope_is_mod_type` say no tier ties exist; 14 groups of veiled-domain mods tie   [CONFIRMED] [impact: low]
- Where: `items/tiers.py` module docstring ("No such tie exists on a released base in 3.29.3.3"), claim `mod_tier.scope_is_mod_type`.
- What it does: groups `(type, generation, domain)` in the `unveiled` domain share one required level (60): e.g. `JunMasterVeiledLocalIncreasedArmourAndLife_` (+17-19 Life), `...Med___` (+19-22), `...High` (+23-26) are all tier 1 on str armour (the clear case); 14 such groups in all (six hybrid defence + Life groups with Low/Med/High, and eight weapon groups where the one-hand and two-hand variants tie on some bases: elemental damage + ailment, minion, damage-over-time multipliers).
- What it should do: the docstring/claim says what the data does, and the tiers of the Low/Med/High triple are told apart (or the claim says they are one tier).
- Evidence (run): `ties.py` over all 211 distinct base tag sets; 14 groups with ties, all `unveiled`.
- Impact: veiled-armour routes (R03 style) that name a tier of the hybrid Life mods.
- Origin: `590a731` (#23).
- Pattern: a data property asserted in a comment and not tested over the whole data.

### INPUTS-17: ADR-0007 still says the trade query keeps "only listings from the last week by default"   [CONFIRMED] [impact: low]
- Where: `docs/adr/0007-prices-from-a-dated-local-file.md`, paragraph on #40; code `trade_query.DEFAULT_INDEXED = None` (#133, any age, the owner's rule), `tests/fixtures/trade/recorded/README.md` says the same as the code.
- What it does: the ADR says the opposite of the owner's rule, "so an old listing cannot set a floor price"; the recorded floors are in fact July and August listings.
- What it should do: the ADR amended (it was amended for #337 and #355, not for #133).
- Evidence: the two texts.
- Impact: a reader of the ADR builds the wrong query.
- Origin: `e4dc3e7` (#40) wrote it; #133 changed the code only.
- Pattern: a decision changed in one place.

### INPUTS-18: `trade_market._offer_from_entry` invents a usable count for old entries   [CONFIRMED] [impact: low]
- Where: `prices/trade_market.py:121-127` (`usable = max(detail["used"], MIN_USABLE)`).
- What it does: an entry without `usable` is assumed to have at least 3 usable listings, so it is quoted whatever it really had.
- What it should do: `unknown` for an entry that lacks the count (as for a missing `listings`).
- Evidence: reading; no committed entry lacks `usable`, so it is latent.
- Impact: none today.
- Origin: #355.
- Pattern: a placeholder standing in for a measured count.

### INPUTS-19: what `normalize` drops, and what it passes through   [CONFIRMED, informational] [impact: low]
- Where: `data/normalize.py`, `data/model.py`.
- What it does: it keeps what the planner reads and drops: mod `grants_effects` (1,663 mods) and `gold_value` (all null); base `properties` (armour, evasion, energy shield, movement speed, block, weapon damage and speed, flask fields), `requirements.level`, `inherits_from`, sizes, `grants_buff`, `skills_granted`, `visual_identity`; fossil `descriptions`, `blocked_descriptions`, `sell_price_mods`. Nothing in `src/` reads any of them (`grep`). `attribute_requirements` is right: all 94+ rings, amulets, belts and quivers have `requirements: null` in the export and (0,0,0) is the game's value. `release_state` (54 unreleased, 15 unique_only, 9 legacy bases) is read only by `actions/draw.py:92`; legacy and `trade_market_legacy_item` bases stay in `base_items` and can be chosen by id. 420 of 445 fossil records are the nameless `RandomFossilOutcome*` records (the Tangled outcomes).
- What it should do: nothing now; the next feature that needs a base's defence values (quality on armour, ADR-0049 "base defence values", imprint restore) will meet a dropped field, as `attribute_requirements` did until #229.
- Evidence: raw key census (`mods.json`, `base_items.json`, `fossils.json`, `essences.json`, bench) against the `Mod`/`BaseItem` fields.
- Impact: none today.
- Origin: ADR-0003 ("keeps only what the project reads").
- Pattern: a model that grows by the field a ticket needs; the seed (#229) was the first case.

---

## Patterns seen in this area

1. **One fact written by hand in two places, nothing compares them** (INPUTS-1, 4, 6, 9, 12, 13): the start item lives in the target file (base, level, tier, roll) and again in the buy spec (category, level, rarity, mods); the price key is a string in one and an id in the other; no test reconciles a spec with its target.
2. **A rule built beside the path that needed it** (INPUTS-2, 3): `offer()`, `source_price()`, the stale warnings, the `price_source` setting all exist and are tested in isolation; the planner and the page read the raw price file, so staleness, thin markets, other leagues and hand prices pass unmarked.
3. **Provenance recorded at write time, dropped at read time** (INPUTS-3, 15): sources, dates and "UNVERIFIED" live in notes and free text, not in a machine field the output reads.
4. **A computed or hand-picked number stored as a measured one** (INPUTS-4, 5, 12, 18): Alchemy added to a trade quote, the cheapest of several ninja lines under another ilvl's name, typed V01 prices, an invented usable count.
5. **Defaults that decide a question** (INPUTS-8, 14, 18): no `start_price` is "free", a one-trade exchange line is a price, a missing count is "at least 3".
6. **A docstring or ADR states what the code does not do, or what a later decision reversed** (INPUTS-11, 16, 17): bench item-level gate, "no ties", "last week".
7. **Tests whose oracle is the fixture they load** (INPUTS-5, 12, 4): the R08/R09 test asserts the folded price, the golden values freeze R04's mismatched price, `test_prices_start_items` proves the price equals its recording but not that the recording searched the planned item.
8. **A price key doubling as a display name** (INPUTS-7, 6): "Buy R05 start ring" on the page; names shared by several bases.
