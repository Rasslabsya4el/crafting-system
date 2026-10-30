# poe.ninja recorded responses

Recorded on 2026-10-30 at 20:24 UTC with one real read-only GET per endpoint, league `Allflame` (patch 3.29), then trimmed to a handful of lines each so they stay small. The trimming only dropped lines, `sparkline` blocks and `image` paths; every kept field is as poe.ninja sent it. Tests never touch the network.

| File | Endpoint |
|---|---|
| `leagues.json` | `GET /poe1/api/economy/leagues` |
| `overview_currency.json` | `GET /poe1/api/economy/exchange/current/overview?league=Allflame&type=Currency` |
| `overview_fossil.json` | same, `type=Fossil` |
| `overview_resonator.json` | same, `type=Resonator` |
| `overview_essence.json` | same, `type=Essence` |
| `details_hollow_fossil.json` | `GET /poe1/api/economy/exchange/current/details?league=Allflame&type=Fossil&id=hollow-fossil` (undocumented; only the newest 10 daily rows kept) |

Host: `https://poe.ninja`. Request header: a descriptive `User-Agent` with the repo URL.

## Bases, beasts, stash history and old leagues (#40)

Recorded on 2026-10-30 at 21:40-21:50 UTC, one real read-only GET per endpoint, then trimmed. Trimming only dropped lines, history rows, `icon`, `sparkLine` and `flavourText`; every kept field is as poe.ninja sent it. Host and header as above. Dates: current league `Allflame` started 2026-07-24; `Mirage` ran 2026-03-06 to 2026-07-20 (the last day its history has).

| File | Endpoint | Kept |
|---|---|---|
| `stash_beast.json` | `GET /poe1/api/economy/stash/current/item/overview?league=Allflame&type=Beast` | 6 of 195 lines, counts 201, 2, 6, 5, 4 and a Vivid Vulture |
| `stash_basetype.json` | same, `type=BaseType` | 10 of 9,205 lines: Stygian Vise 85 (plain, Hunter, Elder, `Warlord/Hunter` count 2, Crusader), count 5 and count 4 lines, a count-1 line at 2 million Chaos, a line without `variant` |
| `stash_history_basetype_34026.json` | `GET .../stash/current/item/history?league=Allflame&type=BaseType&id=34026` (undocumented; Stygian Vise 85 Hunter) | newest 10 rows (`daysAgo` 0 is the fetch day) |
| `stash_history_basetype_34026_mirage.json` | same, `league=Mirage` | newest 51 rows; `daysAgo` 0 is the league's last day, 2026-07-20 (the answer header `x-league-endat` says so; the last row equals the Mirage overview line) |
| `stash_history_basetype_34026_standard.json` | same, `league=Standard` | newest 10 rows |
| `stash_history_beast_167860.json` | same, `type=Beast`, Allflame (Aboriginal Chieftain, a thin line) | newest 10 rows, all `count` below 5 |
| `dumps.json` | `GET /poe1/api/data/dumps` (undocumented) | last 6 of 41 leagues: `leagueName`, `minDate`, `maxDate` |
| `details_hollow_fossil_mirage.json` | `GET .../exchange/current/details?league=Mirage&type=Fossil&id=hollow-fossil` | `chaos` pair only, rows from 2026-05-25 to 2026-07-20 |
| `details_hollow_fossil_standard.json` | same, `league=Standard` | `chaos` pair only, newest 10 rows, every `volumePrimaryValue` is 0 |

Item line ids are the same in every league (id 34026 is Stygian Vise 85 Hunter in Allflame, Mirage and Standard).
