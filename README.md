# crafting-system

A crafting planner for Path of Exile: for a target item it finds the cheapest crafting policy and reports its cost and risk. Vocabulary is in [GLOSSARY.md](GLOSSARY.md); the design decisions are in [docs/adr/](docs/adr/).

## Install and test

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then, from the repository root (Windows or Linux):

```
uv sync
uv run pytest
```

uv downloads the pinned Python (3.14) by itself.

## Directories

The data, cache and output directories come from, in order of priority: an environment variable, the config file `crafting.toml` at the project root (or the file named by `CRAFTING_CONFIG`, used instead), then the built-in default. All defaults are inside the project and git-ignored. Relative paths in a config file count from that file's directory; in environment variables and defaults, from the project root. An empty variable counts as unset.

| Directory | Environment variable    | Config key (`[paths]`) | Default        |
|-----------|-------------------------|------------------------|----------------|
| data      | `CRAFTING_DATA_DIR`     | `data`                 | `local/data`   |
| cache     | `CRAFTING_CACHE_DIR`    | `cache`                | `local/cache`  |
| output    | `CRAFTING_OUTPUT_DIR`   | `output`               | `local/output` |

## Plan a target

```
python -m crafting_system.cli examples/targets/r12-lightning-amulet.yaml
```

This reads the target, the pinned game data in the cache (`python -m crafting_system.data fetch` puts it there) and the price file in the data directory (`python -m crafting_system.prices fetch`, plus hand prices in `price_overrides.toml` beside it). It prints the cheapest policy as a short text tree (what to do in each state, the odds of each outcome, the mean cost and p50/p90 in Chaos with a Divine equivalent) and writes the same policy as JSON to `<output dir>/<target name>.policy.json`, or to the path given with `--json`.

- The cost of the start item is the price stored under the target's `start_price` name (R12: `R12 start amulet`, priced from the trade site by `python -m crafting_system.prices trade --spec <buy spec>`). A hand override wins; `--start-price CHAOS` wins for one run.
- A Harvest reforge costs its lifeforce (Lightning: 50 Primal Crystallised Lifeforce, rules registry `harvest_reforge.lifeforce_cost`) at the price in the price file. An action with a missing price is dropped and listed.
- The model offers, for the target's item class: a Chaos Orb, the Harvest reforge of Lightning, every essence of level 5 and up that gives a mod on that class, Remove Crafted Mods, the bench crafts whose mod counts toward one of the target's requirements (the other crafts are left out and listed: while every other action erases crafted mods, such a craft can never lower the mean, and offering all of them makes the state space explode), and `restart`, buying the start item again at its price from any state but the start. Essences, crafts and restarts are named in a given route as the policy prints them (`Shrieking Essence of Spite`, `Bench craft +# to maximum Life`, `restart`).
- The benchmark routes R10, R11 and R05 have their targets in `examples/targets/`, the buy specs of their start items in `examples/buy/` and the guides' routes in `examples/routes/`. A given route may also ask for `open_prefixes` / `open_suffixes` (at least that many free slots), when a bench action is offered.
- `--verify` plays the policy on concrete items (`--runs`, default 10,000, about a minute on R12; `--seed`) and checks that the simulated mean agrees with the computed one within five standard errors. Its interval is a normal approximation, and the output states the smallest error of the computed mean the run can reject (about 5% for 10,000 runs, since a craft's cost is as spread as its mean; more `--runs` see smaller errors). Exit code 2 means it did not agree.
- `--route ROUTE.yaml` evaluates a **given route** (a crafting route written as rules, see `examples/routes/r12-lightning-amulet.yaml`) exactly, at the same prices, and prints its success chance, mean, p50 and p90 next to the solver's, the first state where the two choose different actions, and any state the rules do not cover. The rules may only speak of what the compressed state holds today: rarity, corrupted, fractured mods, whether the item has a crafted mod, and the status of each requirement.
- `python -m crafting_system.cli benchmark [--out DIR]` runs the solver and the given route of every benchmark route that has both (today R12, R10, R11 and R05), checks the guide's published odds, and writes `benchmark.json` with the machine (OS, CPU, Python, commit) and run times to the output directory. It records the results and never fails on them.
