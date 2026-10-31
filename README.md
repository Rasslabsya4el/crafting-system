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
- `--verify` plays the policy on concrete items (`--runs`, default 10,000, about a minute on R12; `--seed`) and checks that the simulated mean agrees with the computed one within five standard errors. Its interval is a normal approximation. Exit code 2 means it did not agree.
