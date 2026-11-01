# Ticket #271: fit the strand sheet

Scripts and results behind `docs/research/2026-11-01-strand-sheet-fit.md`. The data are five tabs of the public
"Memory Strand Testing" sheet (the raw CSV files are not kept in the repo; the Unravelling tab is 65 MB).

- `fetch_sheet.py RAW_DIR` downloads the tabs as CSV (standard library only).
- `fitpool.py RAW_DIR CACHE_DIR fit_pool_result.json` question (a): the exact likelihood of the mods of 18,264 crafts under
  the three readings of ADR-0042 (and the family between them), on our pool; the profile of the exponent, the bootstrap, the
  calibration table, the Foulborn bonus.
- `spend.py RAW_DIR spend_result.json` questions (b) and (e): the spend of every currency, the censored uniform test, the
  Exalted ceilings by mods before the craft, the Foulborn crafts by strands before.
- `unravel.py RAW_DIR CACHE_DIR unravel_result.json` question (c): the chance curve and the destination reading on the
  36,598 mods of the Unravelling tab, with our weights and with the author's columns.
- `remembrance.py RAW_DIR remembrance_result.json` question (d): the order of the 2,255 results, the shape under five
  ways of cutting and rounding.
- `itemtext.py`, `sheetpool.py`, `stats_util.py`: the item-text parser, the mapping of the sheet's names to the pinned
  export (and the four Battle Royale mods left out of the pool), small statistics helpers.

`CACHE_DIR` holds the pinned export (`python -m crafting_system.data fetch`). The scripts need numpy and the project
(`src/`), Python 3.12 or later, and are run from the repository root. The `*_result.json` files are their output
(`fitpool.py` about five minutes of one core, the others about a minute each).
