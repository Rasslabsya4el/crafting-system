# State (rewrite at the end of every working session; newest state only)

- 2026-09-20, session complete. Network works; 11 Craft of Exile files are cached once under `sources/raw/coe/` and listed with hashes in `docs/SOURCES.md`. Cached third-party bytes remain ignored.
- Delegation smoke accepted and merged as `c1df1b6`: `python -m pytest -q` verified two parser tests. The second worker inventory was accepted and merged as `cd5e976` from worker commit `82fbf2b`.
- CoE inventory is reproducible offline: `python tools/coe_inventory.py --source sources/raw/coe/package.js --output docs/research/coe-method-inventory.md`; lead reran `python -m pytest -q` on the worker (9 passed in 0.05s). Report: 95 named nodes, 84 leaves, 13 custom subsets, 2 options, 2 choices; required action anchors are present.
- Lead-authored phase-0 sheets now cover basic currency, bench/metamods, essences, Harvest, eldritch, Awakener, fracturing, veiled, recombinators, and corruption. Partial sheets deliberately leave unsourced matrices as Q11/Q12; fossil/resonator details remain pending.
- Wiki browser evidence was read through the user's already-open session and selected observations were stored in `sources/raw/wiki/browser-observations-2026-09-20.md`; no cookies were exported and no anti-bot workaround was attempted.
- Next three actions: (1) decide whether owner answers Q3 target ruleset; (2) write/accept fossil and probability-method notes from cached sources; (3) delegate a narrowly specified PoB data builder with sourced test numbers.
