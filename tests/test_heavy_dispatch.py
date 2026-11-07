"""The runner budget of heavy runs (ticket #249): the dispatcher waits while merge CI needs the runners.

No network: the API is a fake that serves a recorded snapshot of the live repository (busy_snapshot.json: four CI runs
and four heavy runs, taken with the free plan's 20 runners all in use)."""

import copy
import datetime as dt
import email.message
import importlib.util
import io
import json
import os
import sys
import urllib.error
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
        self.reads = 0  # API calls made to look at the world (variables, run lists, jobs)
        self.variable_reads = []  # the name of every variable read

    def variable(self, name, default):
        self.reads += 1
        self.variable_reads.append(name)
        return self.variables.get(name, default)

    def active_runs(self):
        self.reads += 1
        return [{k: v for k, v in run.items() if k != "jobs"} for run in self.runs]

    def jobs(self, run_id):
        self.reads += 1
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


class FakeClock:
    """The script's own clock (heavy.now, heavy.pause): a wait moves it on and takes no real time."""

    def __init__(self):
        self.t = 1_800_000_000.0  # a fixed start: the tests never read the real clock
        self.waits = []

    def now(self):
        return self.t

    def pause(self, seconds):
        self.waits.append(seconds)
        self.t += seconds


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(heavy, "STATE_DIR", tmp_path / "state")
    clock = FakeClock()
    monkeypatch.setattr(heavy, "now", clock.now)
    monkeypatch.setattr(heavy, "pause", clock.pause)
    return clock


@pytest.fixture
def clock(isolated):
    return isolated


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


def test_gives_up_after_max_wait():
    api = FakeApi([ci_run(10, queued=16)])
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


# ---- the shared API limit (ticket #565) -----------------------------------------------------------------------------


def look(api, runners=4):
    """One decision the way cmd_run takes it: under the lock."""
    with heavy.DispatchLock():
        return heavy.decide(api, args(runners=runners))


def test_two_decisions_30_seconds_apart_make_one_round_of_api_calls(clock):
    api = FakeApi([ci_run(10, running=6), heavy_run(5, 4, running=4)])
    first = look(api)
    one_round = api.reads
    assert one_round == 2 + 1 + 2  # two variables, one run list, the jobs of the two runs
    clock.t += 30
    second = look(api)
    assert api.reads == one_round  # the second look called nothing
    assert second == first


def test_two_decisions_120_seconds_apart_make_two_rounds(clock):
    api = FakeApi([ci_run(10, running=6)])
    look(api)
    one_round = api.reads
    clock.t += 120
    look(api)
    assert api.reads == 2 * one_round


def test_a_reused_snapshot_is_counted_with_the_ledger_as_it_is_now(clock):
    named = heavy_run(2, 8)
    named["display_title"] = "Run a command"  # no runners in the name: only the ledger says
    named["jobs"] = [{"id": 1, "name": "plan", "status": "queued", "created_at": "2026-11-01T10:00:00Z", "started_at": None}]
    api = FakeApi([named])
    assert "heavy in flight 1," in look(api)["line"]
    heavy.write_ledger(2, 5)  # the dispatcher learns the run's size between two looks
    clock.t += 30
    reads = api.reads
    assert "heavy in flight 5," in look(api)["line"]
    assert api.reads == reads


def test_a_dispatch_between_two_decisions_makes_the_second_fetch_again(clock):
    api = FakeApi([ci_run(10, running=2)])
    look(api)
    assert (heavy.STATE_DIR / "snapshot.json").exists()
    with heavy.DispatchLock():
        heavy.decide(api, args())
        assert heavy.dispatch(api, args(), 4) == 0
        assert not (heavy.STATE_DIR / "snapshot.json").exists()  # gone before the lock is released
    reads = api.reads
    clock.t += 5
    api.runs.append(heavy_run(6, 4, running=4))  # the run just started
    assert "heavy in flight 4," in look(api)["line"]
    assert api.reads > reads


def test_the_snapshot_is_dropped_even_when_the_dispatch_fails(clock):
    api = FakeApi([])
    look(api)
    api.call = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("POST: HTTP 500"))
    with heavy.DispatchLock():
        with pytest.raises(RuntimeError):
            heavy.dispatch(api, args(), 2)
    assert not (heavy.STATE_DIR / "snapshot.json").exists()


def test_a_broken_snapshot_file_is_fetched_again(clock):
    api = FakeApi([])
    look(api)
    (heavy.STATE_DIR / "snapshot.json").write_text("{not json", encoding="utf-8")
    reads = api.reads
    look(api)
    assert api.reads > reads


def test_the_wait_loop_polls_every_three_minutes(clock):
    assert heavy.POLL_SECONDS == 180
    api = FakeApi([ci_run(10, queued=16)])
    assert heavy.cmd_run(api, args(runners=8, max_wait=7)) == 2
    assert api.dispatched == []
    assert clock.waits.count(heavy.POLL_SECONDS) == 3  # looks at 0, 3 and 6 minutes; the look at 9 gives up


def limited(reset, remaining="0", code=403):
    headers = email.message.Message()
    headers["X-RateLimit-Remaining"] = remaining
    if reset is not None:
        headers["X-RateLimit-Reset"] = str(int(reset))
    return urllib.error.HTTPError("https://api.github.test/x", code, "rate limit", headers, io.BytesIO(b'{"message":"API rate limit exceeded"}'))


class Reply:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def serve(monkeypatch, *answers):
    """urlopen answers one item of `answers` per call: an exception is raised, bytes are returned."""
    seen = []

    def urlopen(request, timeout=None):
        seen.append(request.full_url)
        answer = answers[len(seen) - 1]
        if isinstance(answer, Exception):
            raise answer
        return Reply(answer)

    monkeypatch.setattr(heavy.urllib.request, "urlopen", urlopen)
    return seen


@pytest.mark.parametrize("code", [403, 429])
def test_a_rate_limit_refusal_waits_until_the_reset_and_goes_on(clock, monkeypatch, capsys, code):
    reset = int(clock.t) + 600
    seen = serve(monkeypatch, limited(reset, code=code), b'{"value": "7"}')
    api = heavy.Api("o/r", "token")
    assert api.variable("HEAVY_FLOOR", 4) == 7
    assert len(seen) == 2  # one refused, one retried after the wait: no tight loop
    assert reset <= clock.t <= reset + 5  # the fake clock stands at the reset time
    assert all(wait <= 60 for wait in clock.waits) and len(clock.waits) <= 11  # slept in minutes, not in a spin
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and "rate limit" in out[0]


def test_the_rate_limit_wait_is_capped_at_an_hour(clock, monkeypatch):
    start = clock.t
    serve(monkeypatch, limited(start + 10 * 3600), b"{}")
    heavy.Api("o/r", "token").call("/x")
    assert start + 3600 <= clock.t <= start + 3600 + 5


def test_a_refusal_without_a_reset_time_waits_a_minute_not_in_a_loop(clock, monkeypatch):
    start = clock.t
    serve(monkeypatch, limited(None), b"{}")
    heavy.Api("o/r", "token").call("/x")
    assert 59 <= clock.t - start <= 65


def test_a_403_that_is_not_the_rate_limit_raises_at_once(clock, monkeypatch):
    seen = serve(monkeypatch, limited(clock.t + 600, remaining="4999"))
    with pytest.raises(RuntimeError, match="HTTP 403"):
        heavy.Api("o/r", "token").call("/x")
    assert len(seen) == 1 and clock.waits == []


def test_a_limit_that_does_not_lift_gives_up_after_three_waits(clock, monkeypatch):
    seen = serve(monkeypatch, *[limited(clock.t + 60)] * 4)
    with pytest.raises(RuntimeError, match="HTTP 403"):
        heavy.Api("o/r", "token").call("/x")
    assert len(seen) == 4


def test_a_rate_limit_wait_inside_the_lock_keeps_the_lock_fresh(clock, monkeypatch):
    serve(monkeypatch, limited(clock.t + 1800), b"{}")
    touched = []
    real = heavy.DispatchLock.keep_fresh.__func__
    monkeypatch.setattr(heavy.DispatchLock, "keep_fresh", classmethod(lambda cls: touched.append(cls.held) or real(cls)))
    with heavy.DispatchLock() as lock:
        heavy.Api("o/r", "token").call("/x")
    assert len(touched) >= 25 and all(held is lock for held in touched)  # every minute of a 30 minute wait


# ---- the secondary rate limit (ticket #567) -------------------------------------------------------------------------


def secondary(retry_after, code=403, remaining=None):
    """The secondary limit: a refusal with Retry-After and (unlike the hourly limit) no X-RateLimit-Remaining: 0."""
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    if remaining is not None:
        headers["X-RateLimit-Remaining"] = remaining
    return urllib.error.HTTPError("https://api.github.test/x", code, "secondary", headers, io.BytesIO(b'{"message":"You have exceeded a secondary rate limit"}'))


def test_a_secondary_limit_waits_retry_after_and_goes_on(clock, monkeypatch, capsys):
    start = clock.t
    seen = serve(monkeypatch, secondary(60), b'{"value": "7"}')
    assert heavy.Api("o/r", "token").variable("HEAVY_FLOOR", 4) == 7
    assert len(seen) == 2  # one refused, one retried after the wait
    assert 60 <= clock.t - start <= 65  # the Retry-After seconds, not POLL_SECONDS
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and "secondary" in out[0] and "60" in out[0]


def test_a_secondary_limit_wait_is_capped(clock, monkeypatch):
    start = clock.t
    serve(monkeypatch, secondary(10 * 3600), b"{}")
    heavy.Api("o/r", "token").call("/x")
    assert heavy.RETRY_AFTER_CAP_SECONDS < 3600
    assert start + heavy.RETRY_AFTER_CAP_SECONDS <= clock.t <= start + heavy.RETRY_AFTER_CAP_SECONDS + 5


def test_a_429_with_retry_after_is_waited_out_too(clock, monkeypatch):
    start = clock.t
    seen = serve(monkeypatch, secondary(30, code=429), b"{}")
    heavy.Api("o/r", "token").call("/x")
    assert len(seen) == 2 and 30 <= clock.t - start <= 35


def test_a_secondary_limit_that_does_not_lift_gives_up_after_three_waits(clock, monkeypatch):
    seen = serve(monkeypatch, *[secondary(5)] * 4)
    with pytest.raises(RuntimeError, match="HTTP 403"):
        heavy.Api("o/r", "token").call("/x")
    assert len(seen) == 4


def test_a_403_with_remaining_requests_and_no_retry_after_is_still_a_plain_refusal(clock, monkeypatch):
    seen = serve(monkeypatch, secondary(None, remaining="4999"))
    with pytest.raises(RuntimeError, match="HTTP 403"):
        heavy.Api("o/r", "token").call("/x")
    assert len(seen) == 1 and clock.waits == []


# ---- the lock stays fresh in a long wait (ticket #567) ---------------------------------------------------------------
# The lock directory's mtime is set from heavy.now(), the script's own clock, never from the file system's: a real
# mtime is months away from the fake clock, so a test could not tell a fresh lock from a stale one.


def test_a_long_rate_limit_wait_keeps_the_lock_younger_than_stale_and_nobody_takes_it_over(clock, monkeypatch):
    serve(monkeypatch, limited(clock.t + 1800), b"{}")  # a 30 minute wait: six times LOCK_STALE_SECONDS
    real_pause = heavy.pause
    ages = []
    lock_path = []

    def watching_pause(seconds):
        real_pause(seconds)
        # the first wait step is the first look: keep_fresh runs after each pause, so the age here is at most one step
        ages.append(clock.t - lock_path[0].stat().st_mtime)
        with pytest.raises(heavy.LockBusy):  # a second session does not find the lock stale, so it cannot take it
            with heavy.DispatchLock(no_wait=True):
                pass

    monkeypatch.setattr(heavy, "pause", watching_pause)
    with heavy.DispatchLock() as lock:
        lock_path.append(lock.path)
        heavy.Api("o/r", "token").call("/x")
        assert (lock.path / "owner").read_text(encoding="utf-8") == lock.token  # still the first session's
    assert ages and max(ages) < heavy.LOCK_STALE_SECONDS
    assert len(ages) >= 25  # it was waited out in minutes, and the check ran at every one


def test_a_lock_nobody_keeps_fresh_is_taken_over_after_the_stale_time(clock):
    abandoned = heavy.DispatchLock()
    abandoned.__enter__()
    heavy.DispatchLock.held = None  # its process is gone
    clock.t += heavy.LOCK_STALE_SECONDS - 1
    with pytest.raises(heavy.LockBusy):
        heavy.DispatchLock(no_wait=True).__enter__()
    clock.t += 2
    with heavy.DispatchLock(no_wait=True) as taker:
        assert (taker.path / "owner").read_text(encoding="utf-8") == taker.token


# ---- a half-made lock, and a slow call inside the lock (ticket #581) -------------------------------------------------


def test_a_failing_touch_after_the_mkdir_removes_the_lock_and_raises_the_error_not_lockbusy(clock, monkeypatch):
    def broken_touch(path):
        raise OSError("disk error")

    monkeypatch.setattr(heavy, "touch", broken_touch)
    with pytest.raises(OSError, match="disk error") as raised:
        heavy.DispatchLock(no_wait=True).__enter__()
    assert not isinstance(raised.value, heavy.LockBusy)
    assert not (heavy.STATE_DIR / "dispatch.lock").exists() and heavy.DispatchLock.held is None
    assert clock.waits == []  # it did not wait on its own half-made lock
    monkeypatch.undo()
    with heavy.DispatchLock(no_wait=True):  # and the next taker finds a free lock
        pass


def test_a_failing_info_write_after_the_mkdir_removes_the_lock_and_raises_the_error_not_lockbusy(clock, monkeypatch):
    real_write = Path.write_text

    def failing_write(self, text, *rest, **keywords):
        if self.name == "info":
            raise OSError("disk full")
        return real_write(self, text, *rest, **keywords)

    monkeypatch.setattr(Path, "write_text", failing_write)
    with pytest.raises(OSError, match="disk full") as raised:
        heavy.DispatchLock().__enter__()
    assert not isinstance(raised.value, heavy.LockBusy)
    assert not (heavy.STATE_DIR / "dispatch.lock").exists() and heavy.DispatchLock.held is None
    assert clock.waits == []


def test_slow_api_calls_inside_the_lock_keep_it_fresh_so_a_second_taker_cannot_take_it_over(clock, monkeypatch):
    slow = 200  # seconds per call: one call is under LOCK_STALE_SECONDS, a decision of several calls is far over it
    assert slow < heavy.LOCK_STALE_SECONDS
    ages = []
    path = []

    def slow_urlopen(request, timeout=None):
        ages.append(clock.t - path[0].stat().st_mtime)  # how old the lock is as this call starts
        with pytest.raises(heavy.LockBusy):  # a second session finds it fresh
            with heavy.DispatchLock(no_wait=True):
                pass
        clock.t += slow
        return Reply(b'{"value": "4", "workflow_runs": []}')

    monkeypatch.setattr(heavy.urllib.request, "urlopen", slow_urlopen)
    api = heavy.Api("o/r", "token")
    start = clock.t
    with heavy.DispatchLock() as lock:
        path.append(lock.path)
        decided = heavy.decide(api, args(runners=2))  # variables and run lists: well over LOCK_STALE_SECONDS in all
        assert clock.t - start > 2 * heavy.LOCK_STALE_SECONDS
        assert (lock.path / "owner").read_text(encoding="utf-8") == lock.token  # still the first session's
    assert decided["count"] == 2
    assert len(ages) > 4 and max(ages) <= slow


# ---- the lock wait honours --max-wait and --no-wait (ticket #567) -----------------------------------------------------


def test_no_wait_does_not_wait_for_a_held_lock_and_names_the_holder(clock, capsys):
    api = FakeApi([])
    with heavy.DispatchLock(what="run on other-branch"):
        before = clock.t
        assert heavy.cmd_run(api, args(runners=2, no_wait=True)) == 3
        assert clock.t == before and clock.waits == []  # no sleeping
    assert api.dispatched == [] and api.reads == 2  # only the two variables, read before the lock
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert "lock held by" in out[0] and f"process {os.getpid()}" in out[0] and "run on other-branch" in out[0] and "since" in out[0]


def test_max_wait_ends_the_wait_for_a_held_lock(clock, capsys):
    api = FakeApi([])
    with heavy.DispatchLock(what="run on other-branch"):
        start = clock.t
        assert heavy.cmd_run(api, args(runners=2, max_wait=2)) == 2
        assert 120 <= clock.t - start < 125  # two minutes, not the LOCK_STALE_SECONDS the holder is allowed
    assert api.dispatched == [] and api.reads == 2  # only the two variables, read before the lock
    out = capsys.readouterr().out.splitlines()
    assert sum("lock held by" in line for line in out) == 1  # said once, not at every look
    assert "gave up after 2 min" in out[-1]


def test_the_lock_wait_goes_on_when_the_holder_lets_go(clock, monkeypatch, capsys):
    api = FakeApi([])
    holder = heavy.DispatchLock(what="run on other-branch")
    holder.__enter__()
    heavy.DispatchLock.held = None  # this test plays two processes
    real_pause = heavy.pause
    pauses = []

    def pause_then_release(seconds):
        real_pause(seconds)
        pauses.append(seconds)
        if len(pauses) == 3:
            holder.__exit__()

    monkeypatch.setattr(heavy, "pause", pause_then_release)
    assert heavy.cmd_run(api, args(runners=2, max_wait=10)) == 0
    assert len(api.dispatched) == 1
    assert sum("lock held by" in line for line in capsys.readouterr().out.splitlines()) == 1


# ---- status reads the variables once (ticket #567) --------------------------------------------------------------------


def test_status_reads_each_variable_once(capsys):
    api = FakeApi(SNAPSHOT["runs"])
    assert heavy.cmd_status(api, type("S", (), {"no_logs": True})()) == 0
    assert sorted(api.variable_reads) == ["CI_RESERVE", "HEAVY_FLOOR"]
    assert "Heavy budget 4 = max(HEAVY_FLOOR=4, 20 - CI_RESERVE=4 - CI jobs 41)" in capsys.readouterr().out
