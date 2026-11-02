# CI: the whole suite on GitHub (ticket #165)

The full test suite, the real-data tests included, runs on GitHub's machines in 8 shards per system. Nothing needs the
35-minute local run any more.

## Where each system runs (ticket #321)

| Event | Systems | Test jobs | Who it is for |
|---|---|---|---|
| a push to a pull request | Ubuntu | 8, plus `CI summary` | the PR's own session: feedback while it works |
| `workflow_dispatch` of `ci.yml` | Ubuntu and Windows | 16, plus `CI summary` | the integration run, and on-demand runs of `main` or any branch |

No PR lands on its own CI. The main chat lands PRs only after an integration run: a `workflow_dispatch` of `ci.yml` on
an `integ/...` branch that holds current `main` plus the PRs. That run is where Windows is checked, so the landing rule
"green on Ubuntu and Windows" is met by it. A PR that needs Windows feedback early gets it by starting the workflow on
its branch: `gh workflow run ci.yml --ref my-branch`.

Why: 11 open PRs once held 121 CI jobs on the repository's 20 runners, and the oldest jobs waited 20 minutes. Running
Windows on every PR push doubled that load for a result no landing used.

## How `main` is verified

A push to `main` starts no CI run (ticket #308): the run would repeat a result already known. `main` is verified by
the integration run: the main chat merges only a head, or an integration branch, whose tree it has just tested in CI,
and checks that `main` equals that tested tree after landing. To test `main` (or any ref) on demand, start the
workflow by hand: `gh workflow run ci.yml --ref main`.

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
  when every shard of every system that ran (8 on a PR push, 16 on a dispatch) left its results, no test failed, each
  shard ran exactly the tests it was given, the shards together hold exactly the tests collected, and no test skipped
  for lack of the game data. It prints passed and skipped totals per system, the skips by reason, the slowest shard
  and the slowest tests, and it uploads the measured seconds as the artifact `shard-durations` (on a PR push these are
  the Ubuntu seconds alone, not the mean of both systems).

The tests that cannot run on GitHub skip, and the summary lists them: those of `tests/test_proto_coe_comparison.py`
need a local copy of Craft of Exile, which is third-party data that stays out of the repo (ADR-0003).

## Landing a pull request

1. Build the integration branch `integ/<date>-x`: current `main` plus the PRs to land.
2. Dispatch `ci.yml` on it (`gh workflow run ci.yml --ref integ/<date>-x`) and wait for `CI summary` to be green:
   that run is the Ubuntu and Windows check. A PR's own `CI summary` (Ubuntu only) is feedback for its session, not a
   landing condition.
3. Merge with `gh pr merge N --match-head-commit <sha of the tested head>`, so a push after the check cannot slip in.

## Running the suite on your own machine

The serial command is unchanged:

    CRAFTING_CACHE_DIR=<cache> uv run --frozen pytest -q -p no:cacheprovider

(`uv run ... data fetch` fills the cache first.) A shard can be run locally the same way CI does it:

    uv run python .github/scripts/run_shard.py --shard 3/8 --procs 4 --out out -- -p no:cacheprovider --shard-durations tests/shard_durations.json

## Heavy runs on GitHub: the runner budget (#249)

**Nothing heavy runs on the owner's PC.** Locally only quick, targeted tests (under a minute, one process); the full suite goes to CI and benchmarks, profiling, sweeps, solves and measurements go to a heavy run, because a local multi-process sweep pins his machine at 100%. `.github/workflows/run.yml`
checks out a branch, puts the pinned game data in place with the same step CI uses (`.github/actions/real-data`),
runs a bash command from the repository root on 1 to 16 runners and uploads what the command wrote into `$OUT_DIR`
(plus `output.log`, its console output). The command sees `RUNNER_INDEX` (1..N) and `RUNNER_COUNT`, so N runners can
split a sweep; `CRAFTING_CACHE_DIR` already holds the data. GitHub only lets a workflow be started by hand when its
file is on the default branch; the code that runs is the code of `--ref`.

The repository has **20 runner jobs at once**. One PR push takes 8 of them (Ubuntu only) and one dispatched CI run 16
(Ubuntu and Windows), each for about 7 minutes; a heavy run takes up to 16 for hours, so unchecked heavy runs would stall every pull request. **Every heavy run therefore goes through the
dispatcher, never `gh workflow run run.yml`:**

    python .github/scripts/heavy_dispatch.py run --ref my-branch --runners 4 --command 'uv run --no-sync python bench.py --part $RUNNER_INDEX/$RUNNER_COUNT --out $OUT_DIR'
    python .github/scripts/heavy_dispatch.py status

(Use `../../scratch/uv-venv/Scripts/python.exe` or any Python 3.10+; the script is standard library only. It takes its
token from `GH_TOKEN`, else `gh auth token`, else `git credential fill`.) The dispatcher waits on your PC, which costs
no runner, polls every 60 seconds and prints one line per poll. It reads the live jobs of `ci.yml` and `run.yml` and
dispatches only while

    heavy_in_flight + requested <= HEAVY_BUDGET
    HEAVY_BUDGET = max(HEAVY_FLOOR, 20 - CI_RESERVE - ci_jobs_queued_or_running)

| Variable (repository, Actions variables) | Default | Meaning |
|---|---|---|
| `HEAVY_FLOOR` | 4 | Runners heavy runs always may use, even when CI is busy. |
| `CI_RESERVE` | 4 | Runners kept free for merge CI on top of the jobs it already has. |

With the defaults heavy runs may use 16 runners when no CI run is waiting, 8 when one pull request run is queued
(8 jobs), and only the floor of 4 when two are (or one dispatched run, 16 jobs). The main chat turns the knobs without a commit (Settings, Secrets and variables, Actions, Variables, or
`gh variable set HEAVY_FLOOR --body 6`); the next poll of every waiting dispatcher sees the new value. A heavy run that
is queued or running counts against the budget from the moment it is dispatched, so two sessions cannot both take the
same free runners (sessions on one PC also share a lock while they decide).

Options of `run`:

- `--runners N` is a **maximum**. `--min-runners M` lets it start smaller when only M to N fit (the work must then be
  split by `RUNNER_INDEX`/`RUNNER_COUNT` and still finish inside the timeout); the default is `--runners`, never smaller.
- `--timeout-minutes` defaults to 60 and is refused above 60 unless `--long` is given, which needs `--runners 1` and is
  for a single indivisible solve. **Split a long sweep into more, shorter parts** (more `--runners`, or several runs
  each with its slice) so runners free up regularly for CI.
- `--os`, `--max-wait MINUTES` (give up), `--no-wait` (exit 3 if it does not fit now), `--dry-run` (decide, dispatch nothing).

`status` shows the budget, the runner jobs in use by kind (CI per pull request, heavy per branch), the queue with how long
it has waited, and the runs older than their own timeout or silent for 30 minutes (each with its `gh run cancel` line).

After dispatching, wait for the run and download as before:

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
    D='python .github/scripts/heavy_dispatch.py run --ref my-branch'
    $D --command "$S levels --prices default --goal A --out \$OUT_DIR"
    $D --command "$S levels --prices cheap --goal A --out \$OUT_DIR"
    $D --command "$S levels --prices default --goal B --out \$OUT_DIR"
    $D --command "$S endtoend --prices default --out \$OUT_DIR"
    $D --long --timeout-minutes 360 --command "$S exact --prices default --yes-exact --out \$OUT_DIR"
    $D --long --timeout-minutes 360 --command "$S exact --prices cheap --yes-exact --out \$OUT_DIR"
    $D --long --timeout-minutes 120 --command "$S refusals --out \$OUT_DIR"

`levels` takes `--spreads 3000,2000,1500,1000,500` (the default) and gives, per spread, the pools, blocks, certified lower
and upper bound, gap, the seconds of `solve_level` and of the pooling, and the size of the block models (variant actions
and edges); `endtoend` gives the decision of `decide` at the rates it measures (levels, whether the pilot walk was
complete, predicted and pilot seconds) and, when it is approximate, the answer of `climb`; `exact` (only with
`--yes-exact`) the states, edges, seconds and value of the exact graph, which the intervals of `levels` must bracket;
`refusals` the text the product gives for the R04-like quiver and for the metamods of R14 proper.

### Counting a graph and playing a route (#70)

R04 and R14 are too large for the exact solver, and these two scripts measure them (never run them on a PC):

    S='uv run --no-sync python .github/scripts'
    gh workflow run run.yml --ref my-branch -f timeout_minutes=360 -f command="$S/count_states.py examples/targets/r04-penetrating-quiver.yaml --out \$OUT_DIR"
    gh workflow run run.yml --ref my-branch -f timeout_minutes=300 -f command="$S/simulate_route.py examples/targets/r14-hunter-bow.yaml examples/routes/r14-hunter-bow.yaml --runs 2000 --out \$OUT_DIR"

`count_states.py` walks the exact graph of a target (every offer and `restart`) and prints, every 30 seconds, the states
found and expanded, the transitions and the resident memory; it stops at `--max-rss-mb` (default 13,000, a runner has 16 GB)
and writes `<target>.count.json`. `simulate_route.py` plays a given route on concrete items (`make_plan(solve_it=False)` and
`cli/_route_sim.py`) and writes its success rate, mean, p50 and p90 with intervals; a state no rule covers stops that run,
and with `--skip-refused` a rule whose action the game refuses is skipped (for the `*-restart.yaml` routes).

### Planning the big routes on the packed solver (#374)

R04, R14 and S02 are solved exactly by `make_plan` since the packed solve (ADR-0063 point 1): the graph is walked into
arrays, merged into its exact classes, solved by policy iteration and certified. `.github/scripts/packed_routes.py` runs
them and the cross-check against the object solver on a runner (never on a PC):

    D='python .github/scripts/heavy_dispatch.py run --ref my-branch --runners 1'
    $D --command 'uv run --no-sync python .github/scripts/packed_routes.py plan --route r04 --out $OUT_DIR'
    $D --long --timeout-minutes 150 --command 'uv run --no-sync python .github/scripts/packed_routes.py plan --route r14 --out $OUT_DIR'
    $D --command 'uv run --no-sync python .github/scripts/packed_routes.py check --route r05 --out $OUT_DIR'

`plan` writes `<route>.json` (mean cost, certified error bound, states, seconds, risk, peak memory) and prints each phase
of the walk, merge and solve as it ends; `check` plans the route with `solver="object"` and `solver="packed"` and writes
their relative difference. The goldens of `tests/test_packed_heavy.py` (R04, R14, S02) are rewritten from such a run with
`CRAFTING_HEAVY=1 UPDATE_GOLDEN=1 ... pytest tests/test_packed_heavy.py` and are tied to the commit of `main` they were
taken on.

## Keeping the shards balanced

After a run, download the artifact `shard-durations` and commit it as `tests/shard_durations.json`. It holds the
seconds and the number of tests of each group (a module, or a module and one route), not of single tests, because
a test id can carry a path and `test_no_absolute_paths` forbids those in the repo. Do it when tests were added or
got slower; a stale file only makes the shards less even, never wrong: a group that grew costs the median test for
each new test, and a new group costs its tests at the median.
