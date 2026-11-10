# CI: the whole suite on GitHub (ticket #165)

The full test suite, the real-data tests included, runs on GitHub's machines in 8 shards per system. Nothing needs the
35-minute local run any more.

## Where each system runs (ticket #321)

| Event | Systems | Test jobs | Who it is for |
|---|---|---|---|
| a push to a pull request | Ubuntu | 8, plus `CI summary` | the PR's own session: feedback while it works |
| `workflow_dispatch` of `ci.yml` | Ubuntu and Windows | 16, plus `CI summary` | the integration run, and on-demand runs of `main` or any branch |

No PR lands on its own CI. The main chat lands PRs only after an integration run (a process-text PR excepted, see "Landing a pull request"): a `workflow_dispatch` of `ci.yml` on
an `integ/...` branch that holds current `main` plus the PRs. That run is where Windows is checked, so the landing rule
"green on Ubuntu and Windows" is met by it. A PR that needs Windows feedback early gets it by starting the workflow on
its branch: `gh workflow run ci.yml --ref my-branch`.

Why: 11 open PRs once held 121 CI jobs on the repository's 20 runners, and the oldest jobs waited 20 minutes. Running
Windows on every PR push doubled that load for a result no landing used.

## How `main` is verified

A push to `main` starts no CI run (ticket #308): the run would repeat a result already known. `main` is verified by
the integration run: the main chat merges only a head, or an integration branch, whose tree it has just tested in CI,
and checks that `main` equals that tested tree after landing (after a process-text PR, up to those text files). To test `main` (or any ref) on demand, start the
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

**A process-text PR** skips steps 1 and 2 (owner, 2026-11-10): one whose every changed file is a `.md` file under
`CLAUDE.md`, `README.md`, `docs/ci.md`, `docs/agents/`, `.claude/agents/`, `.claude/skills/`.
No test reads those files. Other `.md` files are read by tests (`docs/owner-rules.md` by `tests/reconcile/test_reconcile_real.py`,
`tests/golden/reachability.md`, notes under `docs/research/` and ADRs under `docs/adr/`), so a PR touching them, or any file of another
kind (a docstring in a script included), takes the full run. Check with `git diff --name-only origin/main...<branch>`; the `checker`
confirms that no test or script opens a file of the PR (a mention in a comment does not count). It still reviews the PR, and
the merge is step 3 on the reviewed head. `main` then differs from the last tested tree only in those files; the next integration run tests it.

## Running the suite on your own machine

The serial command is unchanged:

    CRAFTING_CACHE_DIR=<cache> uv run --frozen pytest -q -p no:cacheprovider

(`uv run ... data fetch` fills the cache first.) A shard can be run locally the same way CI does it:

    uv run python .github/scripts/run_shard.py --shard 3/8 --procs 4 --out out -- -p no:cacheprovider --shard-durations tests/shard_durations.json

### The tests' clock (#542)

A price ages with the calendar (`MAX_AGE_DAYS` = 7), so no test may read it against the day it runs on. Code takes `today` / `now`
as arguments; the four places that default to `datetime.now(UTC)` (`CLOCK_READERS` in `tests/clock_support.py`) read the fixed
`FIXED_NOW` (2026-11-01 12:00 UTC) in every test, by the autouse fixture `fixed_clock` in `tests/conftest.py`. A new place that reads
the clock is added to `CLOCK_READERS`. `CRAFTING_TEST_REAL_CLOCK=1` turns the fixture off. The rule itself (7 days fresh, 8 stale) is
pinned on the committed price files in `tests/test_price_age_rule.py`. To check that the suite does not depend on the date, run it
under a faked one on a runner: `sudo apt-get install -y faketime` and `faketime '2026-12-01 12:00:00' <the shard command>`.

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
no runner, polls every 3 minutes and prints one line per poll. It reads the jobs of `ci.yml` and `run.yml` and
dispatches only while

    heavy_in_flight + requested <= HEAVY_BUDGET
    HEAVY_BUDGET = max(HEAVY_FLOOR, 20 - CI_RESERVE - ci_jobs_queued_or_running)

| Variable (repository, Actions variables) | Default | Meaning |
|---|---|---|
| `HEAVY_FLOOR` | 4 (the repository variable is **6** since 2026-11-08) | Runners heavy runs always may use, even when CI is busy. |
| `CI_RESERVE` | 4 (the repository variable is 4) | Runners kept free for merge CI on top of the jobs it already has. |

With `CI_RESERVE` 4, heavy runs may use 16 runners when no CI run is waiting (20 - 4 - 0), 8 when one pull request run is queued
(8 jobs: 20 - 4 - 8), and only the floor when two are (or one dispatched run, 16 jobs: 20 - 4 - 16 = 0): 6 now, 4 with the script's default. The main chat turns the knobs without a commit (Settings, Secrets and variables, Actions, Variables, or
`gh variable set HEAVY_FLOOR --body 6`); the next poll of every waiting dispatcher sees the new value. A heavy run that
is queued or running counts against the budget from the moment it is dispatched, so two sessions cannot both take the
same free runners (sessions on one PC also share a lock while they decide).

The 5,000 GitHub API calls an hour are **one limit for every agent and session**: the dispatchers on one PC share a
snapshot of the runs for 90 seconds (`snapshot.json` in the dispatcher's temp folder, read and written under that lock and
dropped when a run is dispatched), and a dispatcher that meets the rate-limit refusal waits for its reset (at most an hour,
one line printed) instead of retrying; for GitHub's secondary limit (a refusal with `Retry-After`) it waits that many
seconds, at most 10 minutes (`RETRY_AFTER_CAP_SECONDS`). Nobody should poll a run more often than every 4 minutes
(tickets #565, #567). A run started by something else (a CI push, an integration dispatch by the main chat) can be
seen up to `SNAPSHOT_SECONDS` (90 seconds) late; the cost is runners queued on GitHub, not a failure. A dispatcher
waiting for the PC's lock obeys `--max-wait` and `--no-wait` too, and prints who holds the lock and since when.

Options of `run`:

- `--runners N` is a **maximum**. `--min-runners M` lets it start smaller when only M to N fit (the work must then be
  split by `RUNNER_INDEX`/`RUNNER_COUNT` and still finish inside the timeout); the default is `--runners`, never smaller.
- `--timeout-minutes` defaults to 60 and is refused above 60 unless `--long` is given, which needs `--runners 1` and is
  for a single indivisible solve. **Split a long sweep into more, shorter parts** (more `--runners`, or several runs
  each with its slice) so runners free up regularly for CI.
- `--os`, `--max-wait MINUTES` (give up), `--no-wait` (exit 3 if it does not fit now), `--dry-run` (decide, dispatch nothing).

`status` shows the budget, the runner jobs in use by kind (CI per pull request, heavy per branch), the queue with how long
it has waited, and the runs older than their own timeout or silent for 30 minutes (each with its `gh run cancel` line).

**Nobody polls a run inside a turn** (ticket #711: polling loops cost coders 76% of their hours and grew their contexts past
400k tokens). The main chat dispatches with `--no-wait` and notes the run id and
what the run must show; a helper (`finder`, `checker`) never waits on a run: it reports the id and what to do with the result, and ends its turn:

    python .github/scripts/heavy_dispatch.py run --no-wait --ref my-branch --runners 4 --command '...'

Exit 0 prints `dispatched run <id> on <branch> ...`; exit 3 means there is no room now: the command is noted (by a helper, in its report)
instead of waiting for room. The session waits for the run in the background, so its exit is the notification, and goes on (or resumes the helper):

    python .github/scripts/wait_runs.py <run id> [<run id> ...] [--timeout-minutes 90]

`wait_runs.py` takes the runs of any workflow (PR CI, integration run, heavy run). When it starts it reads each run's `node_id` once
(`gh api repos/R/actions/runs/ID --jq .node_id`, one call per run); a run id that is not a run of the repository gets a 404 and the script
exits 2 at once, so a typo costs two calls, not a wait. From then on it makes **one GitHub API call per poll** for all the runs (one GraphQL call over
the node ids), at least 240 s apart (`--poll-seconds` below that is refused). A rate-limit refusal, at start or in a poll, is printed on stderr and retried
one poll interval later. When a run completes it prints one line: `run <id>  <branch>  <workflow>  <conclusion>  jobs: success 17`.
Exit codes: 0 every run succeeded, 1 one did not (or GitHub kept failing), 2 a bad argument or a run id that is not a run of the repository,
3 `--timeout-minutes` ran out (the poll that finds the time up ends it, so it can overshoot by one poll). It never reads or prints a token; it calls `gh api`. Then download the files as before:

    gh run download <run id> --dir results        # one folder per runner: run-ubuntu-latest-1, -2, ...

**A heavy run that commits its own result (`--commit`, ticket #711).** A command that re-records files (a golden, a recorded fixture) does
not need a download, a copy and a commit by hand: add `--commit PATH [PATH ...]` and the workflow commits the files the command changed under
those paths onto the branch the run ran on.

    python .github/scripts/heavy_dispatch.py run --no-wait --ref my-branch --runners 1 --commit tests/golden/real_r05.html --command 'UPDATE_GOLDEN=1 uv run --no-sync python -m pytest ...'

- **Allowed:** paths under `tests/golden/` and `tests/fixtures/` only (a file or a folder), made of letters, digits and `. _ / + = @ -`; no `..`,
  no absolute path. **Refused:** the refs `main` and `integ/*`. The dispatcher checks this before it waits, and `run.yml` checks it again in
  its `plan` job (bash), so a hand dispatch cannot get around it. The paths reach the workflow as the input `commit_paths`; no input reaches a
  shell except through `env:`.
- **Collecting.** After the command succeeded, each runner uploads the files it changed (new or modified, not deleted) under the paths as the
  artifact `commit-<n>` (a symlink is skipped). The last job, `commit`, is the only one with `contents: write` (`plan` and `run` keep `contents: read`); it merges the artifacts with
  `.github/scripts/merge_commit_files.py`, which checks every path against the same rules again. It does not rely on the layout `download-artifact` gives (one matching artifact is extracted straight into the folder, several into one folder each; run 42467788169 showed it): a runner's root is the folder that holds its `runner-collected.txt`, and a file under no root is refused. Two runners that wrote the same path with
  different bytes make the job refuse and commit nothing.
- **Committing.** One commit `Re-record <paths> (heavy run <id>)` on top of the commit the run tested (`github.sha`). The job pushes only when the
  branch still points at that commit (a lease on that sha); if the branch moved, the job fails, says so in its error and summary, and pushes nothing.
  The session that dispatched it then pulls, and dispatches again.
- **No change.** If nothing under the paths changed, there is no commit; the run succeeds and its job summary says so.
- **No CI run follows the push.** A push made with the workflow token starts no PR CI run (GitHub's rule against loops). The PR's CI starts
  at the next push by hand; an integration run is dispatched by hand as before (`gh workflow run ci.yml --ref integ/...`).

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

    D='python .github/scripts/heavy_dispatch.py run --no-wait --ref my-branch --runners 1 --long'
    S='uv run --no-sync python .github/scripts'
    $D --timeout-minutes 360 --command "$S/count_states.py examples/targets/r04-penetrating-quiver.yaml --out \$OUT_DIR"
    $D --timeout-minutes 300 --command "$S/simulate_route.py examples/targets/r14-hunter-bow.yaml examples/routes/r14-hunter-bow.yaml --runs 2000 --out \$OUT_DIR"

`count_states.py` walks the exact graph of a target (every offer and `restart`) and prints, every 30 seconds, the states
found and expanded, the transitions and the resident memory; it stops at `--max-rss-mb` (default 13,000, a runner has 16 GB)
and writes `<target>.count.json`. `simulate_route.py` plays a given route on concrete items (`make_plan(solve_it=False)` and
`cli/_route_sim.py`) and writes its success rate, mean, p50 and p90 with intervals; a state no rule covers stops that run,
and with `--skip-refused` a rule whose action the game refuses is skipped (for the `*-restart.yaml` routes).

### The benchmark over all routes, split over the runners (#554)

`benchmark` prints, for each route with a given route, the divergences of the guide from the planner, the ratio of the two means and a "needs a human" row below `[benchmark] review_ratio` of `crafting.toml` (default 0.5, a prompt for a person and not a cut of the search). A route a person has taken apart has a verdict in `src/crafting_system/cli/_benchmark_verdicts.py` (#634: real find / the guide is wrong / our completion, the issues, the ratio and the date at review, the hashes of the target file and of the route file, the planner's first divergent action) and prints `reviewed: real find (#591), ratio at review 0.057` instead; it prints "NEEDS A HUMAN AGAIN" with the reason when its ratio moves from the one at review by more than `[benchmark] review_tolerance` (default 0.2 of that ratio, either way), a hash changes, or the planner's first divergent action changes. Under every such row the chance one use ends in the target and the cost of one use (each price part) are told for the planner's action and the guide's at the first divergence (#617). The start-boots emulator checks of #617 are recorded on Windows runners with `tools/coe_emulator/record_runs.sh` (see `tools/coe_emulator/README.md`). The summary lines are the output of one heavy run; `.github/scripts/benchmark_routes.py IDS OUT_DIR` runs `benchmark --heavy` on the routes `IDS` (comma separated) with the committed price snapshot, and prints each phase of the packed solver and of the visit chances as it ends. Four runners split the ten routes by `$RUNNER_INDEX` (measured on 2026-11-07: R14 alone took 25 minutes in run 42410659176 and 44 in run 42377921091, R04 alone 16 in run 42410659176; the time follows the walk of the day, so give R14 a runner of its own and a timeout of 60):

    $D --runners 4 --command 'case $RUNNER_INDEX in 1) R=R14;; 2) R=R04;; 3) R=R08,R09,R13;; 4) R=R12,R10,R11,R05,V01;; esac; uv run --no-sync python -u .github/scripts/benchmark_routes.py $R $OUT_DIR/part'

### The naive crafter's long simulation (#555)

`tests/naive_crafter/` plays a guide's route on concrete items by Monte Carlo, with rules written from the published mechanics and no import of
the planner, and `tests/test_naive_crafter_routes.py` puts its mean (and the spend of each step) beside `risk.evaluate`'s mean of the given route within
4 of its own standard errors. In CI each route plays a short run (R05, R10, R11: 3,000 plays; R13: 16, because one R13 play is about 100,000 orb uses and its mean
is 12,000 Chaos, so its standard error there is about a quarter of the mean and 4 standard errors catch only an error of two to three times: in CI R13 is checked only for gross errors). The real precision of R13 is this heavy run, which runs the same test file with
`NAIVE_RUNS` plays, `NAIVE_SEED` (the runner's index) and `NAIVE_OUT` (a folder for each route's tally) and then pools the tallies of all the runners:

    D='python .github/scripts/heavy_dispatch.py run --ref my-branch --runners 2'
    $D --command 'export NAIVE_SEED=$RUNNER_INDEX NAIVE_OUT=$OUT_DIR; if [ "$RUNNER_INDEX" = "2" ]; then NAIVE_RUNS=30000 uv run --no-sync pytest -q -p no:cacheprovider -k "R05 or R10 or R11" tests/test_naive_crafter_routes.py; fi; NAIVE_RUNS=1000 uv run --no-sync pytest -q -p no:cacheprovider -k R13 tests/test_naive_crafter_routes.py'
    gh run download <run id> --dir results
    PYTHONPATH=tests python -m naive_crafter merge results        # pools the runners of a route, judges the pool, exits 1 on a disagreement

An R13 play takes about 1.6 seconds, so 1,000 plays are about 30 minutes on one runner; the three cheap routes at 30,000 plays take a few minutes
together. More runners (one `NAIVE_SEED` each, the `case $RUNNER_INDEX` form of the other sections) give R13 a smaller standard error.

Since #608 to #610 it plays R08 and R09 (fossils), R12 (the Harvest reforge) and R04 and R14 (Exalted, Annulment and Fracturing Orbs, metamods, Remove Crafted Mods).
R08, R09 and R12 are cheap like R05 (about 1 ms to 2 ms a play). R04 and R14 are heavy on both sides: a play takes about 0.5 s (R04, mean about 200,000 Chaos) and 0.06 s (R14, mean about 13,000
Chaos), and their planner side is a solve of 177,242 and 816,153 states. Their mean is therefore not computed in the test but read from
`tests/fixtures/naive_crafter/benchmark_means.json`, which `tests/naive_planner_side.py` writes: for each route the mean of the completed route (the route file with a restart)
WITHOUT the price of the bought start item (`mean_without_start`, as the naive mean is; `benchmark` prints `mean + start price`, so never copy `completed_route.mean` from its
JSON), the start price and `mean_with_start` beside it, the bracket `(success_low, success_high)` and the printed `success_value` of the guide's route as written (issue #683),
the run id, the commit, the game-data pin and what they were computed from (the sha256 of the target and route files and the cost of one use of each action of the route at the
price file). A quick test in every CI run fails when one of these differs from the files as they are; it does not see a change of the planner's code, so record again after one.
To record it again (R04 about 10 minutes, R14 about 45 on a runner):

    D='python .github/scripts/heavy_dispatch.py run --ref my-branch --runners 2'
    $D --command 'case $RUNNER_INDEX in 1) R=R14;; 2) R=R04;; esac; PYTHONPATH=tests:src uv run --no-sync python -u tests/naive_planner_side.py plan $R $OUT_DIR'
    gh run download <run id> --dir results
    PYTHONPATH=tests:src python tests/naive_planner_side.py write results --run <run id> --commit <sha of the run>

(`write` keeps the naive shares of the heavy run recorded under `naive_heavy`; update them from `python -m naive_crafter merge` when the long simulation is run again.)

The long simulation of these two then runs with `NAIVE_HEAVY=1` (which also plays enough for the mean tests and runs the mutation tests of the two routes). One runner doing all of it
took 39 to over 59 minutes (run 42436780459: one of three hit the timeout), so the work is split by `-k` over five runners, each its own `NAIVE_SEED` (run 42441281288, the slowest runner 25 minutes):
the base tests of R04 (2,000 plays), of R14 twice (10,000 plays each), the Annulment mutation of R04 (1,000 plays, 14 minutes) and the other three mutations (12 minutes). The mutation runners
set `NAIVE_RUNS=20`, because the fixture still plays that many plays of the base route before the mutation test starts and does not use them:

    $D --runners 5 --command 'export NAIVE_HEAVY=1 NAIVE_SEED=$RUNNER_INDEX NAIVE_OUT=$OUT_DIR; T="uv run --no-sync pytest -q -p no:cacheprovider -rP --durations=6 tests/test_naive_crafter_routes.py"; case $RUNNER_INDEX in 1) NAIVE_RUNS=2000 $T -k "R04 and not each_law";; 2|3) NAIVE_RUNS=10000 $T -k "R14 and not each_law";; 4) NAIVE_RUNS=20 $T -k "each_law and Annulment";; 5) NAIVE_RUNS=20 $T -k "each_law and not Annulment";; esac'
    gh run download <run id> --dir results
    PYTHONPATH=tests python -m naive_crafter merge results

### R04 and R14 end to end (#70)

Since the packed solver the two routes are planned by the CLI itself: with the default budget the decision finds no approximate level
(a route with an Attack/Caster metamod has none) and `make_plan` goes on to the packed solver, noting why in the plan. The tests
that run the CLI (`--verify`, the completed given route) and `benchmark --heavy` on them are `tests/test_cli_r04_r14_heavy.py`; one
runner each, since each plans its route once. Measured on 2026-11-08 (runs 42429256936, 42433918807; 42415865107 and 42419193048 on the #619 branch, without #642 or #621, took the same 42 and 46 minutes, so the time is the walk and not this solver): the whole file for R04 takes about
33 minutes on one runner; the two halves for R14 take 42 to 46 minutes each, almost all of it the plan that each half makes (the `setup` line of `--durations=0`), so the whole file for R14
on one runner does not fit in 60 minutes (run 42429317814 was cancelled by the timeout) and R14 always goes in two (`-k "not benchmark"`, `-k benchmark`). The split:

    D='python .github/scripts/heavy_dispatch.py run --ref my-branch --runners 4 --timeout-minutes 60'
    $D --command 'case $RUNNER_INDEX in 1) R=R04; K="not benchmark";; 2) R=R04; K=benchmark;; 3) R=R14; K="not benchmark";; 4) R=R14; K=benchmark;; esac; CRAFTING_ROUTES=$R CRAFTING_HEAVY=1 uv run --no-sync pytest -q -p no:cacheprovider --durations=0 -s tests/test_cli_r04_r14_heavy.py -k "$K"'

The rule of that split, checked by the quick guard test `test_every_bench_test_is_named_for_it_and_every_such_name_takes_bench` in the same file: a test that takes `bench` has "benchmark" in its name, and a test that takes `cli` does not.

`chain_dump.py` plans a route and writes its lumped policy chain (`<route>.chain.npz`, with `--risk` also the risk the product code
gives), the data to work on the risk without the walk; `cli_stages.py` times the stages after the plan (report, text, JSON, route
page, `--verify`).

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

`.github/scripts/evaluation_probe.py --route r04|r14 --out DIR` plans the route the same way and records, for every evaluation of a policy
(`solver/_packed_solve.evaluate_policy`), its seconds, the peak resident memory while it ran and the counters it left (iterations, true residual,
backward error, and the exact solve by the cycles of the policy's chain when it was made); it writes `DIR/<route>.evaluation.json`. Run on two refs
(`--ref main-with-the-probe` and `--ref my-branch`) it gives the time and memory of the evaluation before and after a change of the solve (#621).
`--force-exact` makes the iteration give up at once so that every evaluation takes the exact solve by the cycles: what that fallback costs on the
route's own policy (or, when the cycles do not fit in the memory of the run, the refusal that names what they would have cost):

    $D --long --timeout-minutes 120 --command 'uv run --no-sync python -u .github/scripts/evaluation_probe.py --route r14 --out $OUT_DIR'
    $D --command 'uv run --no-sync python -u .github/scripts/evaluation_probe.py --route r04 --force-exact --out $OUT_DIR'

### Counting a route's page (#465, #466)

`.github/scripts/page_size.py` makes the plan of a route the way `packed_routes.py plan` does, draws the route page of the planner's own
policy and writes `<route>.page.json` (steps, rows, HTML megabytes, the states of the policy and of its lumped view, seconds of each phase,
peak memory) and `<route>.rows.txt` (every row of the page as text, tier lines included). It is how the size of a big route's page is
measured, before and after a change of the page: run it on two refs and compare the files.

    D='python .github/scripts/heavy_dispatch.py run --ref my-branch --runners 1'
    $D --long --timeout-minutes 120 --command 'uv run --no-sync python .github/scripts/page_size.py --route r14 --out $OUT_DIR'

### Where a route's cost sits (#599)

`.github/scripts/divergence_costs.py R04 OUT_DIR [EXTRA_ROUTE.yaml ...]` plans a benchmark route (R04 takes about 10 minutes on a runner),
then for the planner, the guide as written, its completed form and each extra route file writes `OUT_DIR/costs.json` and prints: the uses and
the Chaos carried by each action (they add up to the mean), every divergence of the planner's main line with the expected visits of the state
under each side and what each carries (the whole list that `benchmark.json` cuts to ten), the gaps of the guide, and, for each route, its mean
when it takes the planner's action in the states of one group of divergences (and of one pair of actions, and of all of them, which must give the
planner's own mean; and, since #619, the mean of the planner's policy everywhere but where the route's action stays in that group, which is finite where the single
adoption is not). For a completed route it also splits the uses of `restart` by the rule that fires them, with the rule's line and whether the guide has it (the start
items bought per run are those plus 1). `START_PRICE=744` in the command solves the planner and prices the restarts at another start price, the price file untouched.
The visits are the exact row of `(I - Q)^-1` (OR-20), not the bounds `reach_of` gives on R04's chain of 28 million edges.

    D='python .github/scripts/heavy_dispatch.py run --ref my-branch --runners 1'
    $D --command 'uv run --no-sync python .github/scripts/divergence_costs.py R04 $OUT_DIR/costs examples/routes/my-trial.yaml 2>&1 | tee $OUT_DIR/costs.log'

### The rule of a completed route on every state (#599, #628)

`.github/scripts/completion_check.py R04 OUT_DIR` plans the route, reads its completed route on the walked graph and lists every state where a `restart` that
the guide does not have fires while an action of the guide's own rules is legal (`cli/_route_completion.py`, the rule in `cli/_route.py`). Exit code 0: none.
The small, hand-built version of the same check runs in CI (`tests/test_route_completion.py`). R04 takes about 10 minutes, R14 about 40 (`--long`); both pass (R14 since #619).

    D='python .github/scripts/heavy_dispatch.py run --ref my-branch --runners 1'
    $D --command 'uv run --no-sync python .github/scripts/completion_check.py R04 $OUT_DIR/completion 2>&1 | tee $OUT_DIR/completion.log'
    $D --long --timeout-minutes 120 --command 'uv run --no-sync python .github/scripts/completion_check.py R14 $OUT_DIR/completion 2>&1 | tee $OUT_DIR/completion.log'

### What the `actions:` key of a target hides (#475)

`.github/scripts/actions_key.py` plans each of the seven routes that carry an `actions:` key (J01, R04, R08, R09, R13, R14, V01) in three variants of
a copy of the target's text (the committed file is never written): `kept`, `removed` (the key deleted: the kinds offered by default, the opt-in kinds
such as Exalted Orb, Annulment, Fracturing Orb and the fossil sets not among them) and `all` (every kind the planner can use named, which is what OR-5
asks for), each with the default solver (`auto`) and with `solver="envelope"`. Every job is a child process under a wall-clock cap (8 to 20 minutes,
45 for the committed R14) and a memory cap (13 GB); the envelope also gets its own time and memory net. A job that does not finish leaves where it
was: the last progress line, the `CompressedState` objects alive and the peak memory. 42 jobs are dealt over the runners, longest first, so that the
caps on one runner add up to at most 50 minutes (`actions_key.py plan --count N --variants kept` prints the deal). One dispatch per variant keeps each run small
enough for the runner budget: 7 runners for `kept`, 5 for `removed`, 5 for `all`. The V01 numbers of the bloat step (`state_bloat.py run --route V01`) go
on one runner of the first, and `summary` joins the records of the three into the table of the ticket:

    D='python .github/scripts/heavy_dispatch.py run --ref my-branch --timeout-minutes 60'
    $D --runners 7 --command 'if [ $RUNNER_INDEX = 4 ]; then uv run --no-sync python .github/scripts/state_bloat.py run --route V01 --out $OUT_DIR/bloat; fi; uv run --no-sync python -u .github/scripts/actions_key.py batch --variants kept --index $RUNNER_INDEX --count $RUNNER_COUNT --out $OUT_DIR/jobs'
    $D --runners 5 --command 'uv run --no-sync python -u .github/scripts/actions_key.py batch --variants removed --index $RUNNER_INDEX --count $RUNNER_COUNT --out $OUT_DIR/jobs'
    $D --runners 5 --command 'uv run --no-sync python -u .github/scripts/actions_key.py batch --variants all --index $RUNNER_INDEX --count $RUNNER_COUNT --out $OUT_DIR/jobs'
    python .github/scripts/actions_key.py summary --dir DOWNLOADED_ARTIFACTS --out OUT --runs 'run IDs'

A job the caps stopped is looked at again with more time: `actions_key.py jobs --jobs R08-kept-envelope --cap-minutes 52 --out DIR` (one runner each, up to the runner's 60 minutes).
`actions_key.py probe --routes J01,V01 --index $RUNNER_INDEX --count $RUNNER_COUNT --out DIR` adds the kinds the key does not name to the key of a small route one at a time
(45 seconds each, both solvers), which names the kind that makes a graph of 8 states explode.

### Where the bound's build spends its time (#626)

`.github/scripts/bound_build.py profile --route R08 --variant kept|all --cap-minutes N --out DIR [--search]` builds the walk-free bound alone for a route (with `--search` the search runs on to the end of the plan under the same sampler) (the first thing `make_plan(solver="envelope")` does)
with a sampler of the main thread's stack and a timer around the stages of the build (`Pattern.members`, `Abstraction.kernel_key`, `Abstraction.kernel`, the fracture entries, the packing, the solve),
and writes `profile-ROUTE-VARIANT.txt` and `.json`. `actions_key.py` records, for an envelope job, `bound_keys`, `bound_expanded`, `bound_offers`, `bound_seconds` and `bound_stopped` (the net that
ended the bound's build, if one did). The build's own net is the share `BUILD_SHARE` (half) of the time net and all of the memory net (`cli/_envelope_plan.py`).

### The cycles of a route's chain (#572, #490, #584, #600)

`.github/scripts/chain_structure.py --route r04|r14 --out DIR` plans the route, makes the item-state chain of the planner's policy and writes
`<route>.structure.json`: the strongly connected components of the chain (how many, the biggest), the rows that several states share (a reroll
sends every state that takes it to the same thousands of outcomes, a restart sends every one back to the start), and the components that remain
when those rows are cut. These are the numbers the exact visit chances work from (`solver/_packed_chain.py`: the cost is one solve for each
distinct shared row, however many states ask). It also checks the visits and the entry chances of every step (`entry chances unsettled`). A solve
of the route page or of the benchmark is accepted on its true residual (`|b - A x| / |b|` for BiCGSTAB, measured with one more product; the
backward error of the route flow), never on the residual BiCGSTAB claims of its own recurrence, which drifts from the true one on a stiff system.

## The reachability report (ticket #414)

`.github/scripts/reachability_report.py` writes a Markdown report of what a plan can reach today: which action kinds some
benchmark target's planner entry offers (and, for those none is offered, the reason the code gives), which settings and
flags any code reads (an AST search of `src/`, not a grep of the name), and whether the planning path calls the modules the
audit says are built and not wired. It reads the planner's own code, so unlike an oracle it imports `crafting_system`; it
solves nothing (`make_plan(solve_it=False)` for each target of `examples/targets/`), and takes about 30 seconds, most of it
the two fossil targets R08 and R09. A target whose entry takes over `--target-seconds` (30) is reported as "not measured,
too slow".

- **In CI.** The `test` job of shard 1 on Ubuntu runs it after the shard (no extra runner job): the report goes to that
  job's summary and to the artifact `reachability` (`reachability.md`).
- **The golden copy.** `tests/golden/reachability.md` is the committed report, and `tests/test_reachability_report.py` fails
  with a unified diff when the report differs. A PR that makes a kind reachable, gives a setting a reader or removes a gate
  therefore changes the file, and the change is read in review. To update it, take the artifact `reachability` of the PR's CI
  run (the real game data is needed, so a PC without the cache cannot make it), check it, and commit it as
  `tests/golden/reachability.md`; `UPDATE_GOLDEN=1 pytest tests/test_reachability_report.py` writes the same file where the
  data is.
- **By hand.** `CRAFTING_CACHE_DIR=<cache> uv run python .github/scripts/reachability_report.py --out reachability.md`
  (a quick run, one process; it never starts a solve).

## Golden files: how to read and update a change (ticket #436)

The golden files under `tests/golden/` (`*.html` pages, `*.json`, `*.txt`, `reachability.md`) are the saved output of a test, and a
change to one is a change to what the owner sees. Their bytes are kept as they are (single-line HTML sections included); what is readable
is the **view** `tests/golden_diff.py` makes of them, and the same view is used in three places.

- **The view.** HTML is reduced to its structure and visible text, one block per line: every block element (`div`, `li`, `tr`, `h3`, ...)
  starts a line with its start tag, indented by its depth; inline elements (`span`, `a`) stay in their block's line; a link address is
  shown percent-decoded; `<style>` is one CSS rule per line; whitespace is collapsed as a browser collapses it. JSON is pretty-printed
  with sorted keys. Text and Markdown go line by line. A line longer than 160 characters is cut after its commas and semicolons, the
  continuation starting with `~`, so no line of the view is long.
- **A failing golden test** prints that view as a unified diff (`-` is the golden file, `+` what the test produced), at most 120
  lines. Every comparison with a golden file goes through `golden_diff.check` (bytes) or `golden_diff.check_objects` (parsed values):
  `assert_golden` and `assert_golden_json`, the V01 JSON, the risk and B1 fingerprints, `plans_118.json` (its `start`, `mean_remaining` and `policy` fields; its `states` count is a plain bound, `<=` or `==`), `reachability.md`. The scalar
  numbers of `packed_values.json` are compared by `check_objects(..., rel=1e-9)` in the heavy tests (the tolerance `approx` had), and
  they fail with the same title and diff. When the bytes differ but the view is equal, the message says the readable view is equal and
  the bytes differ (case, entity, encoding, key order or whitespace), and shows the first differing characters.
- **A pull request** that changes a golden file gets the same diff for every such file in the job summary of the `Golden changes against
  main` step (`.github/scripts/golden_changes.py`; it runs once, on Ubuntu, in shard 1 of a PR's CI, and is information, not a gate). By
  hand: `python3 .github/scripts/golden_changes.py --base origin/main` from the branch, no game data needed; `--lines N` cuts each file's diff.
  A file that differs from main only in line endings gets one line saying so, not an empty diff. The file sections of the report
  stay under 900,000 bytes (UTF-8), below the 1 MiB a job summary may hold; a file that would pass it is left out with a note.

To update a golden file, run its test with `UPDATE_GOLDEN=1` (the test writes the file, then compares), read the diff of the step above
in the PR, and commit the file (a golden that needs the real game data is re-recorded on a runner by a heavy run with `--commit`, below). Do not accept a change you have not read: the diff is what a reviewer reads. A golden file made from the
real game data is taken from where it is made, since a PC without the cache cannot make it. `reachability.md` is the artifact
`reachability` of the PR's CI run (uploaded by the "Reachability report" step above). The `real_*` pages (`tests/golden/real_r05.html`,
`real_r10.html`, `real_r11.html`) are not CI artifacts: `assert_golden` in `tests/route_view_support.py` rewrites each one when
`UPDATE_GOLDEN=1` is set, and `tests/test_cli_routes_real.py` makes them on a runner or machine that has the real game data in its
cache (`CRAFTING_CACHE_DIR`). Regenerate them through a heavy run that copies the three files into `$OUT_DIR`, with this command (`BRANCH` is the branch to run):

    python .github/scripts/heavy_dispatch.py run --ref BRANCH --runners 1 --command 'UPDATE_GOLDEN=1 uv run --no-sync python -m pytest tests/test_cli_routes_real.py -k route_view_page_is_the_golden_file -q && cp tests/golden/real_r05.html tests/golden/real_r10.html tests/golden/real_r11.html "$OUT_DIR"/'

With `--commit` the run itself commits them (see "A heavy run that commits its own result" above), so there is nothing to download or copy:

    python .github/scripts/heavy_dispatch.py run --no-wait --ref BRANCH --runners 1 --commit tests/golden/real_r05.html tests/golden/real_r10.html tests/golden/real_r11.html --command 'UPDATE_GOLDEN=1 uv run --no-sync python -m pytest tests/test_cli_routes_real.py -k route_view_page_is_the_golden_file -q'

(`BRANCH` is never `main` or `integ/*`.) The commit lands on the branch, so pull it, and read the diff of the `Golden changes against main` step on the PR before it is accepted. Without `--commit`, `gh run download <run id>` puts the pages in `run-ubuntu-latest-1/`, and you copy them over `tests/golden/real_r05.html`, `real_r10.html` and `real_r11.html`, read the diff, then commit. A reformat of a golden file is never mixed with a content change: it is its own commit, with a test that the parsed content is equal.

## Keeping the shards balanced

After a run, download the artifact `shard-durations` and commit it as `tests/shard_durations.json`. It holds the
seconds and the number of tests of each group (a module, or a module and one route), not of single tests, because
a test id can carry a path and `test_no_absolute_paths` forbids those in the repo. Do it when tests were added or
got slower; a stale file only makes the shards less even, never wrong: a group that grew costs the median test for
each new test, and a new group costs its tests at the median.

## The measurement chain (ticket #399)

- **Start it:** push a branch named `measure/trial` (about an hour: a short slice of every step) or `measure/full` (the
  week-long run). A branch name with `trial` in it is a trial; so is a dispatch of `measure.yml` with `trial` ticked.
  Once `measure.yml` is on `main`, `gh workflow run measure.yml --ref main` starts it too.
- **Where it reports:** issue #398, in Russian, one comment after each step (`.github/scripts/measure_diary.py`): the
  result, the headline, the next step and its expected end. The last comment links to the artifact `measure-report`.
- **The report:** `report.md` (`.github/scripts/measure_summary.py`) holds every step's `summary.md` under its heading.
- **A failed step does not stop the chain:** its note says so, and the next step starts.
- **Runners:** every matrix of the chain keeps `max-parallel: 16`, so 4 of the repository's 20 runner jobs stay free for CI.
- **Measuring a few modules again (ticket #413):** the week's artifacts `measure-mutplan` and `measure-mut-*` hold the plan and the
  outcome of every mutant. `research/413/mutation_rerun.py` turns them and the files of the module(s) into two small plans in the same
  format (`plan-before.json`: the mutants not killed, with the week's tests; `plan-after.json`: the same with the new test files first;
  a mutant is matched to the week's by its text, not its line). Run a plan through the dispatcher, one slice per runner, then merge
  with `.github/scripts/mutation_summary.py`:
  `heavy_dispatch.py run --ref BRANCH --runners 16 --min-runners 4 --command 'mkdir -p "$OUT_DIR/res" && uv run --no-sync python .github/scripts/mutation_run.py --plan research/413/plan-after.json --out "$OUT_DIR/res" --round 1 --job "$RUNNER_INDEX" --jobs "$RUNNER_COUNT" --minutes 48'`.
  A slice stops starting mutants after `--minutes`; the ids it did not reach go into a second plan. About 460 mutants took 11 to 22
  minutes on 7 runners.
