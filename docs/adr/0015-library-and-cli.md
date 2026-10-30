# v1 is a Python library and a CLI: YAML in, JSON policy and text tree out

v1 has no HTTP service and no HTML report. Input is a YAML target file: base, item level, influence, requirements by English stat text or family id with a minimum tier or roll, k-of-n requirements, an optional start item, the price file path. Output is a JSON policy (for each state reachable under it: the action, the expected remaining cost, the chance to get there, the transitions) and a short text tree in the terminal (the main line, where to go on a miss, odds, mean cost, p90). Modifier text is English.

Origin: [Design grill round 2: data, batches, repo](https://github.com/Rasslabsya4el/crafting-system/issues/3) Q15.

## Considered options

- The old prototype's HTML report and an HTTP service: out of v1; Docker comes only with an HTTP service (ADR-0014).
