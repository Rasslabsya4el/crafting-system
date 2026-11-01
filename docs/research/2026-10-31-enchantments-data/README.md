# Player samples of the Heist enchant pools (ticket #100)

CSV exports of two public Google Sheets, fetched 2026-10-31 (`/spreadsheets/d/<id>/export?format=csv&gid=<gid>`, no sign-in). Copies, so the numbers of the note survive a later edit of the sheets.

| File | Sheet | gid | Found through |
|---|---|---|---|
| `curio_summary.csv` | "PoE Curio Case Rates", sheet Summary | 1552361136 | u/developershins in https://www.reddit.com/r/pathofexile/comments/1g93nen/_/lt3ptsj/ (2024-10-22) |
| `curio_by_area_level.csv` | same, sheet "Rewards by alvl" | 126356215 | same |
| `curio_instructions.csv` | same, sheet INSTRUCTIONS | 710775455 | same |
| `tailoring_tally.csv` | "PoE Tailoring Orb weights", Sheet1 (Sheet2 is empty) | 0 | u/Aldunas in https://www.reddit.com/r/pathofexile/comments/1gcr4is/_/ltvy0hq/ (2024-10-26) |

Sheet ids: Curio `1dDDMRc3GAE4G0X-lJeLXSHaGtLLNf612nrFiOyCo0Vs`, tally `1uGDcF2U0qlTmR8O890a6wB8w0A7iad6XgTziTyyf1fo`. The Curio data are community contributions (22 contributors, leagues 3.23 to 3.27, 13,845 wings, 69,225 items); the tally has an unnamed author. Neither is GGG data. Reproduce the note's numbers with `python -I docs/research/2026-10-31-enchantments-samples.py <repoe-fork 3.29.3.3 folder> docs/research/2026-10-31-enchantments-data`.
