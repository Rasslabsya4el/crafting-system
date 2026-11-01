"""The runner budget of heavy runs (ticket #249): the dispatcher waits while merge CI needs the runners.

No network: the API is a fake that serves a recorded snapshot of the live repository (busy_snapshot.json: four CI runs
and four heavy runs, taken with the free plan's 20 runners all in use)."""

import copy
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "heavy_dispatch.py"
spec = importlib.util.spec_from_file_location("heavy_dispatch", SCRIPT)
heavy = importlib.util.module_from_spec(spec)
sys.modules["heavy_dispatch"] = heavy
spec.loader.exec_module(heavy)

SNAPSHOT = json.loads((Path(__file__).parent / "fixtures" / "heavy_dispatch" / "busy_snapshot.json").read_text(encoding="utf-8"))


class FakeApi:
    """Serves runs and jobs from a list of {run..., jobs: [...]}, answers the variables, records the dispatch."""

    def __init__(self, runs, variables=None):
        self.runs = copy.deepcopy(runs)
        self.variables = {"HEAVY_FLOOR": 4, "CI_RESERVE": 4} if variables is None else variables
        self.dispatched = []
        self.on_poll = None  # called after every snapshot, to change the world between two polls

    def variable(self, name, default):
        return self.variables.get(name, default)

    def active_runs(self):
        return [{k: v for k, v in run.items() if k != "jobs"} for run in self.runs]

    def jobs(self, run_id):
        jobs = next(run["jobs"] for run in self.runs if run["id"] == run_id)
        if self.on_poll:
            self.on_poll(self)
        return jobs

    def last_output(self, job_id):
        return None

    def call(self, path, method="GET", body=None, tries=4):
        if method == "POST":
            self.dispatched.append(body)
            return {}
        # the runs list used after a dispatch to find the new run
        stamp = dt.datetime.now(dt.timezone.utc).isoformat()
        return {"workflow_runs": [{"id": 9_000_000 + len(self.dispatched), "created_at": stamp, "html_url": "https://example.test/run"}]
                if self.dispatched else []}


def ci_run(run_id, queued=0, running=0, done=0, title="a pull request"):
    jobs = [{"id": run_id * 100 + n, "name": f"tests (ubuntu-latest, shard {n}/8)", "status": status, "created_at": "2026-11-01T10:00:00Z",
             "started_at": "2026-11-01T10:00:05Z" if status != "queued" else None}
            for n, status in enumerate(["queued"] * queued + ["in_progress"] * running + ["completed"] * done)]
    return {"id": run_id, "path": ".github/workflows/ci.yml", "display_title": title, "head_branch": f"branch-{run_id}",
            "created_at": "2026-11-01T10:00:00Z", "run_started_at": "2026-11-01T10:00:00Z", "pull_requests": [], "jobs": jobs}


def heavy_run(run_id, runners, queued=0, running=0, title=None):
    title = title or f"heavy {runners}x ubuntu-latest t60: sweep"
    jobs = [{"id": run_id * 100 + n, "name": f"run (ubuntu-latest, runner {n}/{runners})", "status": status,
             "created_at": "2026-11-01T10:00:00Z", "started_at": "2026-11-01T10:00:05Z" if status != "queued" else None}
            for n, status in enumerate(["queued"] * queued + ["in_progress"] * running)]
    return {"id": run_id, "path": ".github/workflows/run.yml", "display_title": title, "head_branch": f"heavy-{run_id}",
            "created_at": "2026-11-01T10:00:00Z", "run_started_at": "2026-11-01T10:00:00Z", "pull_requests": [], "jobs": jobs}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(heavy, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(heavy.time, "sleep", lambda seconds: None)


def counts(api, ledger=None):
    seen = heavy.snapshot(api, ledger or {})
    return heavy.totals([(run, occ) for run, _, occ in seen])


# ---- the formula ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "floor, reserve, ci_jobs, expected",
    [
        (4, 4, 0, 16),  # no PR waiting: heavy runs may use 16
        (4, 4, 16, 4),  # one PR run: 20 - 4 - 16 = 0, the floor holds
        (4, 4, 32, 4),  # two PR runs queued: the floor only
        (4, 4, 8, 8),  # half a CI run left
        (4, 4, 41, 4),  # more CI jobs than runners
        (2, 6, 0, 14),  # other knob values
        (8, 4, 16, 8),  # a higher floor wins over a busy CI
    ],
)
def test_budget_is_the_runners_ci_and_its_reserve_leave_but_never_below_the_floor(floor, reserve, ci_jobs, expected):
    assert heavy.heavy_budget(floor, reserve, ci_jobs) == expected


@pytest.mark.parametrize(
    "in_flight, requested, minimum, budget, expected",
    [
        (0, 4, 4, 16, 4),  # fits
        (12, 4, 4, 16, 4),  # fits exactly
        (13, 4, 4, 16, 0),  # one too many and no smaller start allowed: wait
        (13, 4, 1, 16, 3),  # smaller split: the 3 that fit
        (15, 4, 2, 16, 0),  # only 1 fits and 2 is the least: wait
        (5, 1, 1, 4, 0),  # over the budget already
        (0, 16, 1, 4, 4),  # a request over the floor starts as the floor
    ],
)
def test_run_starts_in_full_or_as_small_as_allowed_or_waits(in_flight, requested, minimum, budget, expected):
    assert heavy.runners_to_start(in_flight, requested, minimum, budget) == expected


# ---- counting the live jobs on the recorded snapshot ---------------------------------------------------------------


def test_recorded_busy_snapshot_counts_ci_and_heavy_jobs_and_gives_the_floor():
    api = FakeApi(SNAPSHOT["runs"])
    ci_jobs, heavy_jobs = counts(api)
    assert (ci_jobs, heavy_jobs) == (41, 5)  # 2+14, 5+10, the summary alone, 9 running; 1+1+1+1 running and 1 queued heavy
    assert heavy.heavy_budget(4, 4, ci_jobs) == 4
    assert heavy.runners_to_start(heavy_jobs, 4, 4, 4) == 0  # waits


def test_a_ci_run_whose_jobs_are_not_created_yet_counts_as_all_16():
    fresh = ci_run(1)
    assert counts(FakeApi([fresh]))[0] == heavy.CI_JOBS_PER_RUN == 16
    fresh["event"] = "workflow_dispatch"  # the integration run: Ubuntu and Windows
    assert counts(FakeApi([fresh]))[0] == 16


def test_a_pull_request_ci_run_whose_jobs_are_not_created_yet_counts_as_the_8_ubuntu_jobs():
    fresh = ci_run(1)
    fresh["event"] = "pull_request"  # ticket #321: a PR push runs Ubuntu only
    assert counts(FakeApi([fresh]))[0] == heavy.CI_JOBS_PER_PR_RUN == 8


def test_a_heavy_run_before_its_matrix_exists_counts_as_the_runners_it_asked_for():
    named = heavy_run(2, 8)  # no jobs yet: only the plan job at most
    named["jobs"] = [{"id": 1, "name": "plan", "status": "queued", "created_at": "2026-11-01T10:00:00Z", "started_at": None}]
    assert counts(FakeApi([named]))[1] == 8
    old = copy.deepcopy(named)
    old["display_title"] = "Run a command"  # a branch from before run-name: the dispatcher's ledger says how many
    assert counts(FakeApi([old]), ledger={"2": 5})[1] == 5
    assert counts(FakeApi([old]))[1] == 1  # nothing known: the plan job itself


def test_queued_heavy_jobs_count_so_a_second_request_does_not_pile_on():
    api = FakeApi([heavy_run(3, 6, queued=6)])
    assert counts(api)[1] == 6


def test_parse_run_name():
    assert heavy.parse_run_name("heavy 12x windows-latest t45: uv run ...") == (12, "windows-latest", 45)
    assert heavy.parse_run_name("Run a command") is None


# ---- the wait / dispatch decision ----------------------------------------------------------------------------------


def args(**options):
    values = dict(ref="my-branch", command="echo hi", runners=4, min_runners=None, os="ubuntu-latest", timeout_minutes=60,
                  long=False, max_wait=0, no_wait=False, dry_run=False)
    values.update(options)
    return type("Args", (), values)()


def test_a_request_larger_than_the_budget_waits_while_ci_is_busy_then_starts_when_ci_finishes():
    api = FakeApi([ci_run(10, queued=10, running=6)])  # one full CI run: budget = the floor 4, request 8 does not fit
    polls = []

    def finish_ci(fake):
        polls.append(1)
        if len(polls) >= 3:  # CI finishes on the third poll
            fake.runs = []

    api.on_poll = finish_ci
    code = heavy.cmd_run(api, args(runners=8))
    assert code == 0
    assert len(polls) >= 3
    assert len(api.dispatched) == 1
    assert api.dispatched[0]["inputs"]["runners"] == "8"
    assert api.dispatched[0]["ref"] == "my-branch"


def test_a_smaller_split_starts_at_once_when_min_runners_allows_it():
    api = FakeApi([ci_run(10, running=8)])  # budget = max(4, 20 - 4 - 8) = 8
    code = heavy.cmd_run(api, args(runners=12, min_runners=2))
    assert code == 0
    assert api.dispatched[0]["inputs"]["runners"] == "8"


def test_does_not_shrink_by_default_and_no_wait_exits_with_3():
    api = FakeApi([ci_run(10, running=8)])
    assert heavy.cmd_run(api, args(runners=12, no_wait=True)) == 3
    assert api.dispatched == []


def test_heavy_runs_already_in_flight_use_up_the_budget():
    api = FakeApi([heavy_run(5, 14, running=14)])  # budget 16, 14 held: 4 more do not fit, 2 do
    assert heavy.cmd_run(api, args(runners=4, no_wait=True)) == 3
    assert heavy.cmd_run(api, args(runners=2, no_wait=True)) == 0
    assert api.dispatched[0]["inputs"]["runners"] == "2"


def test_gives_up_after_max_wait(monkeypatch):
    api = FakeApi([ci_run(10, queued=16)])
    clock = iter(range(0, 10_000, 4000))
    monkeypatch.setattr(heavy.time, "time", lambda: next(clock))
    assert heavy.cmd_run(api, args(runners=8, max_wait=1)) == 2
    assert api.dispatched == []


def test_the_knobs_are_read_from_the_variables_with_defaults():
    api = FakeApi([ci_run(10, running=16)], variables={"HEAVY_FLOOR": 8, "CI_RESERVE": 0})
    heavy.cmd_run(api, args(runners=8, no_wait=True))  # budget = max(8, 20 - 0 - 16) = 8
    assert len(api.dispatched) == 1
    bare = FakeApi([], variables={})
    assert bare.variable("HEAVY_FLOOR", heavy.DEFAULT_FLOOR) == 4
    heavy.cmd_run(bare, args(runners=16, no_wait=True))  # defaults: 20 - 4 - 0 = 16
    assert bare.dispatched[0]["inputs"]["runners"] == "16"


def test_a_request_that_can_never_fit_is_refused_at_once():
    api = FakeApi([], variables={"HEAVY_FLOOR": 4, "CI_RESERVE": 8})
    with pytest.raises(SystemExit):
        heavy.cmd_run(api, args(runners=16))  # at most 12 ever


def test_dry_run_dispatches_nothing():
    api = FakeApi([])
    assert heavy.cmd_run(api, args(dry_run=True)) == 0
    assert api.dispatched == []


# ---- refusals of long jobs -----------------------------------------------------------------------------------------


def test_timeout_over_60_is_refused_without_long_and_long_needs_one_runner():
    with pytest.raises(SystemExit, match="Split the sweep"):
        heavy.check_args(args(timeout_minutes=61))
    with pytest.raises(SystemExit, match="--runners 1"):
        heavy.check_args(args(timeout_minutes=120, long=True, runners=2))
    heavy.check_args(args(timeout_minutes=360, long=True, runners=1))
    heavy.check_args(args(timeout_minutes=60, runners=16))


@pytest.mark.parametrize("options", [dict(runners=0), dict(runners=17), dict(timeout_minutes=0), dict(timeout_minutes=361, long=True, runners=1),
                                      dict(runners=4, min_runners=5)])
def test_out_of_range_requests_are_refused(options):
    with pytest.raises(SystemExit):
        heavy.check_args(args(**options))


# ---- the queue view ------------------------------------------------------------------------------------------------


def test_status_shows_budget_kinds_and_queue_on_the_recorded_snapshot(capsys):
    api = FakeApi(SNAPSHOT["runs"])
    assert heavy.cmd_status(api, type("S", (), {"no_logs": True})()) == 0
    out = capsys.readouterr().out
    assert "CI 41" in out and "heavy 5" in out
    assert "Heavy budget 4 = max(HEAVY_FLOOR=4, 20 - CI_RESERVE=4 - CI jobs 41)" in out
    assert "CI    " in out and "heavy " in out
    assert "queued" in out and "Queue (waiting for a runner)" in out


def test_stale_runs_older_than_their_own_timeout_or_silent_are_flagged():
    now = dt.datetime(2026, 11, 1, 14, 0, tzinfo=dt.timezone.utc)
    old = heavy_run(7, 1, running=1, title="heavy 1x ubuntu-latest t60: x")
    old["jobs"][0]["started_at"] = "2026-11-01T12:00:00Z"  # 120 minutes ago, timeout 60
    assert "its timeout is 60 min" in heavy.stale_reason(old, old["jobs"], now, None)
    fresh = heavy_run(8, 1, running=1)
    fresh["jobs"][0]["started_at"] = "2026-11-01T13:50:00Z"
    assert heavy.stale_reason(fresh, fresh["jobs"], now, None) is None
    silent = dt.datetime(2026, 11, 1, 13, 15, tzinfo=dt.timezone.utc)
    assert "no log output for 45 min" in heavy.stale_reason(fresh, fresh["jobs"], now, silent)
    queued_only = heavy_run(9, 2, queued=2)
    assert heavy.stale_reason(queued_only, queued_only["jobs"], now, None) is None  # waiting is not running
    stuck_ci = ci_run(11, running=2)
    stuck_ci["run_started_at"] = "2026-11-01T12:00:00Z"
    assert "its timeout is 45 min" in heavy.stale_reason(stuck_ci, stuck_ci["jobs"], now, None)


# ---- hardening after the checker's review --------------------------------------------------------------------------


def test_a_github_error_while_waiting_is_retried_not_fatal():
    api = FakeApi([])
    calls = []
    real = api.active_runs

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("GET /actions/workflows/ci.yml/runs: HTTP 502")
        return real()

    api.active_runs = flaky
    assert heavy.cmd_run(api, args(runners=2)) == 0
    assert len(calls) == 3  # two failed polls, then the one that dispatched
    assert len(api.dispatched) == 1  # dispatched once, not once per retry


def test_runs_held_before_any_job_exists_are_asked_for_and_counted():
    api = FakeApi([])
    asked = []
    api.call = lambda path, *a, **k: asked.append(path) or {"workflow_runs": []}
    api.active_runs = lambda: heavy.Api.active_runs(api)
    heavy.Api.active_runs(api)
    statuses = {path.split("status=")[1].split("&")[0] for path in asked}
    assert {"queued", "in_progress", "pending", "waiting", "requested"} <= statuses
    pending_ci = ci_run(12)  # a push held by the concurrency group: status pending, no jobs
    assert counts(FakeApi([pending_ci]))[0] == heavy.CI_JOBS_PER_RUN


def test_run_name_pattern_matches_the_run_name_of_run_yml():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "run.yml").read_text(encoding="utf-8")
    line = next(line for line in workflow.splitlines() if line.startswith("run-name:"))
    rendered = line.split(":", 1)[1].strip().strip('"')
    for name, value in (("runners", "7"), ("os", "windows-latest"), ("timeout_minutes", "45"), ("command", "echo x")):
        rendered = rendered.replace("${{ inputs." + name + " }}", value)
    assert heavy.parse_run_name(rendered) == (7, "windows-latest", 45)


def test_log_stamp_pattern_finds_the_last_line_time():
    text = chr(10).join(["2026-11-01T12:00:01.1234567Z first", "2026-11-01T12:31:09.9999999Z last", "no stamp here"])
    import re

    assert re.findall(heavy.LOG_STAMP, text, re.MULTILINE)[-1] == "2026-11-01T12:31:09"


def test_lock_is_released_only_by_its_owner(tmp_path):
    first = heavy.DispatchLock()
    with first:
        stolen = heavy.DispatchLock()
        stolen.token = "someone else"
        stolen.__exit__()  # not the owner: the lock stays
        assert (first.path / "owner").exists()
    assert not first.path.exists()
