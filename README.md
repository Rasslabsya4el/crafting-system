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
