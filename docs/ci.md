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

## Heavy runs on GitHub: the `Run a command` workflow

Benchmarks, profiling and research sweeps go to GitHub too, not to a developer's PC. `.github/workflows/run.yml`
checks out a branch, puts the pinned game data in place with the same step CI uses (`.github/actions/real-data`),
runs a bash command from the repository root on 1 to 16 runners and uploads what the command wrote into `$OUT_DIR`
(plus `output.log`, its console output). The command sees `RUNNER_INDEX` (1..N) and `RUNNER_COUNT`, so N runners can
split a sweep; `CRAFTING_CACHE_DIR` already holds the data. Inputs: `command`, `runners` (default 1), `os`
(default `ubuntu-latest`), `timeout_minutes` (default 60). GitHub only lets a workflow be started by hand when its
file is on the default branch, so this works once the file is on `main`; the code that runs is the code of `--ref`.

    gh workflow run run.yml --ref my-branch -f runners=4 -f command='uv run --no-sync python bench.py --part $RUNNER_INDEX/$RUNNER_COUNT --out $OUT_DIR'
    gh run list --workflow run.yml --branch my-branch --limit 1 --json databaseId,status,conclusion
    gh run watch <run id> --exit-status
    gh run download <run id> --dir results        # one folder per runner: run-ubuntu-latest-1, -2, ...

(`gh` can be slow or time out; the same calls work with `curl` against `api.github.com/repos/<owner>/<repo>/actions/...`.)
Fetch the data into your own folder first with `python -m crafting_system.data fetch` only for a local run; on
GitHub it is already there.

### Measuring the variants level (#172)

`.github/scripts/measure_variants.py` re-makes the table of ADR-0023 ("Additions and Annulment") with the product code, one
JSON line per fact, and writes them to `$OUT_DIR/<case>.jsonl` (plus the console in `output.log`). One runner per case; it
prints what the product does and asserts nothing. Never run it on a PC: the cases below are heavy.

    S='uv run --no-sync python .github/scripts/measure_variants.py'
    gh workflow run run.yml --ref my-branch -f command="$S levels --prices default --goal A --out \$OUT_DIR"
    gh workflow run run.yml --ref my-branch -f command="$S levels --prices cheap --goal A --out \$OUT_DIR"
    gh workflow run run.yml --ref my-branch -f command="$S levels --prices default --goal B --out \$OUT_DIR"
    gh workflow run run.yml --ref my-branch -f command="$S endtoend --prices default --out \$OUT_DIR"
    gh workflow run run.yml --ref my-branch -f timeout_minutes=360 -f command="$S exact --prices default --yes-exact --out \$OUT_DIR"
    gh workflow run run.yml --ref my-branch -f timeout_minutes=360 -f command="$S exact --prices cheap --yes-exact --out \$OUT_DIR"
    gh workflow run run.yml --ref my-branch -f timeout_minutes=120 -f command="$S refusals --out \$OUT_DIR"

`levels` takes `--spreads 3000,2000,1500,1000,500` (the default) and gives, per spread, the pools, blocks, certified lower
and upper bound, gap, the seconds of `solve_level` and of the pooling, and the size of the block models (variant actions
and edges); `endtoend` gives the decision of `decide` at the rates it measures (levels, whether the pilot walk was
complete, predicted and pilot seconds) and, when it is approximate, the answer of `climb`; `exact` (only with
`--yes-exact`) the states, edges, seconds and value of the exact graph, which the intervals of `levels` must bracket;
`refusals` the text the product gives for the R04-like quiver and for the metamods of R14 proper.

## Keeping the shards balanced

After a run, download the artifact `shard-durations` and commit it as `tests/shard_durations.json`. It holds the
seconds and the number of tests of each group (a module, or a module and one route), not of single tests, because
a test id can carry a path and `test_no_absolute_paths` forbids those in the repo. Do it when tests were added or
got slower; a stale file only makes the shards less even, never wrong: a group that grew costs the median test for
each new test, and a new group costs its tests at the median.
