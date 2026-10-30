# One ruleset at a time, with a diff on every patch

The planner supports one ruleset: the current PoE 1 patch in ordinary mode, now 3.29.3.3, pinned in config. On a new patch one command fetches the data and prints a diff (mods, weights, families, tags, bench, essences, fossils). Every registry entry records the patch it was verified on (ADR-0004), the patch notes mark which entries to recheck, and the benchmarks rerun. Older patches live only in git tags.

Out of scope: Ruthless, PoE 2, and several rulesets side by side (map [Crafting system v1](https://github.com/Rasslabsya4el/crafting-system/issues/1), "Out of scope", citing Q17).

Origin: [Design grill round 2: data, batches, repo](https://github.com/Rasslabsya4el/crafting-system/issues/3) Q17.
