# CI: the whole suite on GitHub (ticket #165)

Every pull request and every push to `main` runs the full test suite, the real-data tests included, on GitHub's
machines: Ubuntu and Windows, 8 shards each, 16 jobs at once. Nothing needs the 35-minute local run any more.

## What one run does

- **Game data.** Each shard restores the pinned repoe-fork export from `actions/cache`, keyed by the system and a
  hash of `src/crafting_system/data/PIN.json`, and on a miss fetches it with `python -m crafting_system.data fetch`
  (hashes checked; five tries). A new pin is a new key, so the data follows the pin without anyone touching CI.
  `data verify` then checks the cache against the pin on every job. Nothing else is cached: test results are never
  reused between runs.
- **The trade site's stat list** that the route page tests compare against is a recorded file in the repo,
  `tests/fixtures/trade/recorded/stats_full.json.gz`, so no test needs a network.
- **Sharding.** `pytest --shard SLOT/TOTAL` runs one slot of the suite (`tests/conftest.py`, `tests/shard_support.py`).
  A slot is whole *groups* of tests: a module, or a module and one value of a module-scoped parametrized fixture
  (the three real routes of `test_cli_routes_real.py` are three groups). A group is never split, so a route is
  solved once, in one process. The groups are dealt out longest first by the seconds stored in
  `tests/shard_durations.json`; a test with no stored time counts as the median one. A job runs 4 slots at once
  (`.github/scripts/run_shard.py`), so 8 jobs x 4 slots = 32 slots per system.
- **The summary check, `CI summary`**, is the one to wait for (`.github/scripts/ci_summary.py`). It is green only
  when all 16 shards left their results, no test failed, each shard ran exactly the tests it was given, the shards
  together hold exactly the tests collected, and no test skipped for lack of the game data. It prints passed and
  skipped totals per system, the skips by reason, the slowest shard and the slowest tests, and it uploads the
  measured seconds as the artifact `shard-durations`.

The tests that cannot run on GitHub skip, and the summary lists them: those of `tests/test_proto_coe_comparison.py`
need a local copy of Craft of Exile, which is third-party data that stays out of the repo (ADR-0003).

## Landing a pull request

1. Update the PR branch with `main` (so the checks ran on what will be merged).
2. Wait for `CI summary` to be green.
3. Merge with `gh pr merge N --match-head-commit <sha of the tested head>`, so a push after the check cannot slip in.

## Running the suite on your own machine

The serial command is unchanged:

    CRAFTING_CACHE_DIR=<cache> uv run --frozen pytest -q -p no:cacheprovider

(`uv run ... data fetch` fills the cache first.) A shard can be run locally the same way CI does it:

    uv run python .github/scripts/run_shard.py --shard 3/8 --procs 4 --out out -- -p no:cacheprovider --shard-durations tests/shard_durations.json

## Keeping the shards balanced

After a run, download the artifact `shard-durations` and commit it as `tests/shard_durations.json`. Do it when
tests were added or got slower; a stale file only makes the shards less even, never wrong.
