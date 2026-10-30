# poe.watch recorded responses

Recorded on 2026-10-30 at 21:35-21:45 UTC, one real read-only GET per endpoint, league `Allflame` (patch 3.29), then trimmed to a handful of items each. Trimming only dropped items, history rows and `icon` paths; every kept field is as poe.watch sent it. Host `https://api.poe.watch`, header: the descriptive `User-Agent` of the fetcher. Tests never touch the network.

| File | Endpoint | Kept |
|---|---|---|
| `leagues.json` | `GET /leagues` | all 7 leagues (`name`, `start_date`, `end_date`; `Allflame` started 2026-07-24T20:00:00Z) |
| `ratios.json` | `GET /exchange/ratios?league=Allflame&game=poe1` (answer `{"items": [...]}`) | 7 of 1,035 items: Hollow Fossil, Prismatic Fossil, Deafening Essence of Hatred, Divine Orb, a low-confidence card and essence, and Alchemy Shard, which has **no `price` block** (83 items lack it) |
| `get_beast.json`, `get_essence.json`, `get_fossil.json`, `get_bases.json` | `GET /get?league=Allflame&category=beast|essence|fossil|bases` (a list) | a few items each; `bases` has `itemLevel` and `influences` (comma-separated, lower case, `""` for none) and rows whose values repeat across item levels, as poe.watch sent them |
| `history_850_allflame.json` | `GET /history?league=Allflame&id=850` (Prismatic Fossil) | newest 12 of 97 rows |

Item ids are the same in `/exchange/ratios`, `/get` and `/history`, and in every league.
