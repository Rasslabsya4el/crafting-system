# Recorded trade-API responses

One owner-approved smoke test, 2026-10-30 21:21 UTC, anonymous (no session), patch 3.29, league
`Allflame`: three requests from `crafting_system.prices.trade_http` with the query built from
`../r12_buy_spec.yaml` (rare Amulet, item level 75+, fractured Lightning Resistance, not corrupted,
not mirrored).

- `stats_excerpt.json`: an excerpt of `GET /api/trade/data/stats` (the full list is 2 MB).
- `search_r12.json`: `POST /api/trade/search/Allflame`, unchanged (910 listings, 100 ids returned).
- `fetch_r12.json`: `GET /api/trade/fetch/<first 10 ids>?query=<search id>`, with the seller account,
  stash position, whisper data, fee, icon and item text removed; price, listing date and the item's mods kept.
- `headers_*.json`: status and the headers that matter (`content-type`, `date`, `x-rate-limit-*`) of each
  response. The site also sets an anonymous `POESESSID` cookie on responses; it is deliberately not kept.

The synthetic `../stats_excerpt.json` (made-up hashes, a deliberate duplicate text) stays for the
error-path tests of the stat mapping; these recorded files are the real shape.

## Listing-age window (#40), 2026-10-30 21:44 UTC

A second anonymous run (2 requests) of the same R12 query with the listing-age filter
`trade_filters.filters.indexed.option = "1week"` added (`search_body_r12_1week.json` is the body that
was sent). The site answered 17 listings instead of 910: the other 893 were listed more than a week
ago, and the cheapest of those was a 1-Chaos listing from August.

- `search_r12_1week.json`, `headers_search_1week.json`: the search answer and its headers.
- `fetch_r12_1week.json`: the first 10 listings, trimmed as above. Every `listing.indexed` is within 7 days of the run.
- `filters_indexed.json`: the `indexed` filter as `GET /api/trade/data/filters` lists it (the allowed `option` ids).

## Status since #133

Both recordings were made with `status: available`. From #133 the query sends `securable` (instant
buyout) and no listing-age window by default; the tests that compare a body with `search_body_r12_1week.json`
swap in the new status. The recorded listings stay the price data of those tests.

## Start items of the real routes (#163), 2026-10-31

Four anonymous runs of `python -m crafting_system.prices trade --spec examples/buy/<spec>.yaml` against
`Allflame` (patch 3.29), each one search and one fetch, with the #133 query: instant buyout (`status: securable`),
no listing-age window, the mean of the 5 cheapest of the first 10 listings. `start_items/` keeps, per route
(`r10` boots, `r11` helmet, `r05` ring, `r12` amulet):

- `search_body_<route>.json`: the body that was sent (the buy spec of `examples/buy/` turned into stat ids).
- `search_<route>.json`, `headers_search_<route>.json`: the search answer, unchanged, and its headers.
- `fetch_<route>.json`, `headers_fetch_<route>.json`: the first 10 listings, trimmed as above; price, listing date
  and the item's mods kept.

| route | buy spec | search | price |
|---|---|---|---|
| R10 | `r10-start-boots.yaml` | fractured Movement Speed 30+, ilvl 84+, Sorcerer Boots | 17 c |
| R11 | `r11-start-helmet.yaml` | fractured Chaos Resistance 31+ (tier 1), ilvl 84+, Lion Pelt | 20 c |
| R05 | `r05-start-ring.yaml` | fractured +# to all Attributes 13+, ilvl 75+ | 2.6 c |
| R12 | `r12-start-amulet.yaml` | fractured Lightning Resistance (any roll), ilvl 75+ | 1 c |

Each price sits in `../../prices/routes-allflame-2026-10-31.json` with its date, listing count, query and query hash;
`tests/test_prices_start_items.py` replays the recording against it. The instant-buyout cheapest listings of any age
are often months old (July and August); that is the #133 rule, not a mistake of the recording.

## The full stat list (#165), 2026-10-31 12:39 UTC

- `stats_full.json.gz`: the whole `GET /api/trade/data/stats` answer in the shape of the trade cache file
  `<cache dir>/trade/stats.json` (`fetched_at`, `stats`), gzipped. The route page tests of
  `test_cli_routes_real.py` unpack it into a temporary cache folder, so the buy step's trade link is
  compared against the same stat list on every machine and CI needs no network for it.
