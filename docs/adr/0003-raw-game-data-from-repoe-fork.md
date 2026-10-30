# Raw game data from repoe-fork is the source for mod generation

Mod generation reads raw game data through [repoe-fork](https://repoe-fork.github.io) (PoE 3.29.3.3, exported 2026-10-19): ordered `spawn_weights`, `generation_weights`, `adds_tags`, `implicit_tags` and multi-valued `groups` (families). Path of Building is a cross-check only, because its `group` is the mod type and not the family (187 of 533 item families span several types, so it under-excludes) and it drops `adds_tags` on 517 mods. The older RePoE repositories are stale.

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q1, [Design grill round 2: data, batches, repo](https://github.com/Rasslabsya4el/crafting-system/issues/3) Q10, [Design grill round 3: modules, verification, process](https://github.com/Rasslabsya4el/crafting-system/issues/4) Q25.

## Consequences

- repoe-fork's version and file hashes are pinned in config. One command fetches the full dumps (GGG data, about 65 MB) into a configurable cache directory; they are never committed. Small excerpt fixtures are committed for tests.
- If repoe-fork lags a patch, the fallback is our own export through `pathofexile-dat` and `dat-schema`.
- The data covers every item class from day one, not only the classes of the first benchmarks.
- No exporter holds Harvest, Fracturing Orb or Divine Orb behaviour as data; those rules come from the sources of ADR-0005.
- Local third-party snapshots in `sources/` (the Path of Building data, the Craft of Exile copy, wiki caches) stay git-ignored for good.
