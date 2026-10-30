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
