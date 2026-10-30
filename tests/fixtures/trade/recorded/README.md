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
