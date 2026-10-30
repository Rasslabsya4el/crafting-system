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
