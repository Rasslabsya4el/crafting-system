"""Reconciliation checks for facts written in two places (ticket #412, audit #396 class 2, rebuild step 2).

Each fact about a start item is written by hand in several files: the target (`base`, `item_level`,
`start_item`), the buy spec, the price entry, and the game data knows it too. Nothing else keeps them
equal, so this package reads the files themselves and says where they disagree.

The principle is independence: the package imports nothing from `crafting_system` and uses the
standard library and `yaml` only, plus the one module `tests/independent/ladder.py` that it shares with `tests/oracle/` (ticket #419; `test_reconcile_independence.py` scans the imports). It may read
`src/` to learn a file format; what a fact MEANS comes from the game data and `docs/owner-rules.md`.

- `export`: the raw repoe-fork files in `CRAFTING_CACHE_DIR`.
- `ladder`: the natural tier ladder of a mod on a base (the rules are in `tests/independent/ladder.py`) and the stat and pool helpers.
- `files`: the target, the buy spec and the price entry as they are written.
- `checks`: the reconciliation itself, one named slot per fact and place pair.
- `known`: the disagreements that exist today, each with its issue and its owner rule.
"""
