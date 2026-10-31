# v1 is a Python library and a CLI: YAML in, JSON policy and text tree out

v1 has no HTTP service and no HTML report. Input is a YAML target file: base, item level, influence, requirements by English stat text or family id with a minimum tier or roll, k-of-n requirements, an optional start item, the price file path. Output is a JSON policy (for each state reachable under it: the action, the expected remaining cost, the chance to get there, the transitions) and a short text tree in the terminal (the main line, where to go on a miss, odds, mean cost, p90). Modifier text is English.

Built in [R12 end to end: CLI, JSON policy and text tree](https://github.com/Rasslabsya4el/crafting-system/issues/26): `python -m crafting_system.cli TARGET.yaml` prints the text and writes the JSON (the format is `crafting-system-policy/1`: totals with certified intervals, and per state the action, its cost, the expected remaining cost, the chance the policy ever gets there and the transitions). `--verify` runs the simulator on about 10,000 concrete crafts and agrees when its mean is within five standard errors of the computed one; its interval is a normal approximation. The report and the command line are one package, `cli`.

Origin: [Design grill round 2: data, batches, repo](https://github.com/Rasslabsya4el/crafting-system/issues/3) Q15.

## Considered options

- The old prototype's HTML report and an HTTP service: out of v1; Docker comes only with an HTTP service (ADR-0014).
