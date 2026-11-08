"""`.github/scripts/wait_runs.py` (ticket #711): wait for GitHub runs with one API call per poll.

No network: `gh` is a fake that answers from a script of what each poll sees, and the clock is a fake that a wait moves on.
The tests run in well under a second."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "wait_runs.py"
spec = importlib.util.spec_from_file_location("wait_runs", SCRIPT)
wait_runs = importlib.util.module_from_spec(spec)
sys.modules["wait_runs"] = wait_runs
spec.loader.exec_module(wait_runs)

REPO_ID = 1439947914


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0
        self.waits = []

    def now(self):
        return self.t

    def pause(self, seconds):
        self.waits.append(seconds)
        self.t += seconds


class FakeGh:
    """`gh api repos/o/r --jq .id` and `gh api graphql ...`; `polls[n]` is what poll n+1 sees: a dict run id -> (status,
    conclusion, [job conclusions]), or a tuple (exit code, stderr) for a refused call. The last entry repeats."""

    def __init__(self, clock, polls, branches=None):
        self.clock = clock
        self.polls = polls
        self.calls = []  # (clock time, kind, arguments)
        self.poll_times = []
        self.branches = branches or {}

    def __call__(self, arguments):
        if arguments[:2] == ["api", "graphql"]:
            return self.graphql(arguments)
        self.calls.append((self.clock.t, "repo", arguments))
        assert arguments == ["api", "repos/o/r", "--jq", ".id"]
        return 0, f"{REPO_ID}\n", ""

    def graphql(self, arguments):
        self.calls.append((self.clock.t, "poll", arguments))
        self.poll_times.append(self.clock.t)
        asked = [a[len("ids[]="):] for a in arguments if a.startswith("ids[]=")]
        seen = self.polls[min(len(self.poll_times), len(self.polls)) - 1]
        if isinstance(seen, tuple):
            return seen[0], "", seen[1]
        by_node = {wait_runs.run_node_id(REPO_ID, run_id): run_id for run_id in seen}
        nodes = []
        for node_id in asked:
            run_id = by_node.get(node_id)
            if run_id is None:
                nodes.append(None)
                continue
            status, conclusion, jobs = seen[run_id]
            nodes.append({
                "databaseId": run_id,
                "workflow": {"name": "Run a command"},
                "checkSuite": {
                    "status": status,
                    "conclusion": conclusion,
                    "branch": {"name": self.branches.get(run_id, "claude/711-wait")},
                    "checkRuns": {"totalCount": len(jobs), "nodes": [{"conclusion": job} for job in jobs]},
                },
            })
        return 0, json.dumps({"data": {"nodes": nodes}}), ""


DONE_OK = ("COMPLETED", "SUCCESS", ["SUCCESS"] * 3)
DONE_BAD = ("COMPLETED", "FAILURE", ["SUCCESS", "FAILURE", "SKIPPED"])
RUNNING = ("IN_PROGRESS", None, ["SUCCESS", None])


@pytest.fixture
def clock(monkeypatch):
    fake = Clock()
    monkeypatch.setattr(wait_runs, "now", fake.now)
    monkeypatch.setattr(wait_runs, "pause", fake.pause)
    return fake


def install(monkeypatch, clock, polls, **keywords):
    gh = FakeGh(clock, polls, **keywords)
    monkeypatch.setattr(wait_runs, "run_gh", gh)
    return gh


def run(*arguments):
    return wait_runs.main([*arguments, "--repo", "o/r"])


def test_the_node_id_of_a_run_is_the_one_github_gives():
    # read from the REST answer for run 42462213458 of Rasslabsya4el/crafting-system
    assert wait_runs.run_node_id(1439947914, 42462213458) == "WFR_kwLOVdPcis8AAAAJ4vH1Ug"


def test_all_runs_succeed_exit_0_and_one_line_for_each(clock, monkeypatch, capsys):
    gh = install(monkeypatch, clock, [{11: DONE_OK, 22: DONE_OK}], branches={22: "integ/x"})
    assert run("11", "22") == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("run 11  claude/711-wait  Run a command  success  jobs: success 3")
    assert lines[1].startswith("run 22  integ/x  Run a command  success")
    assert [kind for _, kind, _ in gh.calls] == ["repo", "poll"]  # one call for the whole wait
    assert clock.waits == []


def test_one_failing_run_exits_1_and_its_jobs_are_counted(clock, monkeypatch, capsys):
    install(monkeypatch, clock, [{11: DONE_OK, 22: DONE_BAD}])
    assert run("11", "22") == 1
    out = capsys.readouterr().out
    assert "run 22  claude/711-wait  Run a command  failure  jobs: failure 1, skipped 1, success 1" in out


def test_a_run_in_progress_keeps_being_polled_and_is_printed_once_when_it_completes(clock, monkeypatch, capsys):
    gh = install(monkeypatch, clock, [{11: DONE_OK, 22: RUNNING}, {11: DONE_OK, 22: RUNNING}, {11: DONE_OK, 22: RUNNING}, {11: DONE_OK, 22: DONE_OK}])
    assert run("11", "22") == 0
    assert len(gh.poll_times) == 4
    lines = capsys.readouterr().out.strip().splitlines()
    assert [line.split()[1] for line in lines] == ["11", "22"]  # the finished run is not printed again at every poll
    asked = [[a for a in arguments if a.startswith("ids[]=")] for _, kind, arguments in gh.calls if kind == "poll"]
    assert [len(item) for item in asked] == [2, 1, 1, 1]  # and not asked about again


def test_never_more_than_one_call_per_poll_and_polls_are_at_least_240_seconds_apart(clock, monkeypatch):
    gh = install(monkeypatch, clock, [{11: RUNNING, 22: RUNNING, 33: RUNNING}] * 5 + [{11: DONE_OK, 22: DONE_OK, 33: DONE_OK}])
    assert run("11", "22", "33") == 0
    assert [kind for _, kind, _ in gh.calls] == ["repo"] + ["poll"] * 6  # one resolve at the start, then one call per poll
    gaps = [b - a for a, b in zip(gh.poll_times, gh.poll_times[1:])]
    assert len(gaps) == 5 and min(gaps) >= 240
    assert wait_runs.MIN_POLL_SECONDS == 240


def test_a_poll_interval_under_240_seconds_is_refused(clock, monkeypatch, capsys):
    gh = install(monkeypatch, clock, [{11: DONE_OK}])
    assert run("11", "--poll-seconds", "60") == 2
    assert gh.calls == [] and "240" in capsys.readouterr().err


def test_a_refusal_waits_for_the_next_poll(clock, monkeypatch, capsys):
    gh = install(monkeypatch, clock, [(1, "gh: API rate limit exceeded for user ID 1 (HTTP 403)"), {11: DONE_OK}])
    assert run("11") == 0
    assert len(gh.poll_times) == 2 and gh.poll_times[1] - gh.poll_times[0] >= 240
    captured = capsys.readouterr()
    assert "rate limit" in captured.err and "next poll" in captured.err
    assert len(captured.out.strip().splitlines()) == 1


def test_a_graphql_rate_limit_answer_is_a_refusal_too(clock, monkeypatch, capsys):
    limited = json.dumps({"errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]})
    gh = install(monkeypatch, clock, [{11: DONE_OK}])
    answers = [(1, limited, ""), None]
    real = gh.graphql

    def graphql(arguments):
        first = answers.pop(0)
        return first if first else real(arguments)

    gh.graphql = graphql
    assert run("11") == 0
    assert "rate limit" in capsys.readouterr().err
    assert clock.waits and min(clock.waits) >= 240


def test_other_failures_in_a_row_end_the_wait_with_exit_1(clock, monkeypatch, capsys):
    gh = install(monkeypatch, clock, [(1, "gh: could not resolve host")])
    assert run("11") == 1
    assert len(gh.poll_times) == wait_runs.FAILURES_IN_A_ROW
    assert "giving up" in capsys.readouterr().err


def test_the_timeout_gives_exit_3(clock, monkeypatch, capsys):
    gh = install(monkeypatch, clock, [{11: RUNNING}])
    assert run("11", "--timeout-minutes", "10") == 3
    assert len(gh.poll_times) == 4  # at 0, 4, 8 and 12 minutes: the last one finds the 10 minutes up
    assert "timeout" in capsys.readouterr().err
    assert clock.t - 1_800_000_000.0 >= 600


@pytest.mark.parametrize("bad", ["abc", "12x", "-5", "1.5", ""])
def test_a_bad_id_gives_exit_2_and_calls_nothing(clock, monkeypatch, bad):
    gh = install(monkeypatch, clock, [{11: DONE_OK}])
    assert run("11", bad) == 2
    assert gh.calls == []


def test_no_id_at_all_gives_exit_2(clock, monkeypatch):
    gh = install(monkeypatch, clock, [{11: DONE_OK}])
    assert wait_runs.main(["--repo", "o/r"]) == 2
    assert gh.calls == []


def test_an_id_that_is_not_a_run_of_the_repository_gives_exit_2(clock, monkeypatch, capsys):
    install(monkeypatch, clock, [{11: DONE_OK}])
    assert run("11", "99") == 2
    assert "99" in capsys.readouterr().err


def test_a_token_in_the_environment_is_never_printed(clock, monkeypatch, capsys):
    monkeypatch.setenv("GH_TOKEN", "ghp_secret_value")
    install(monkeypatch, clock, [(1, "rate limit"), {11: DONE_OK}])
    assert run("11") == 0
    captured = capsys.readouterr()
    assert "ghp_secret_value" not in captured.out + captured.err


def test_duplicate_ids_are_asked_once(clock, monkeypatch, capsys):
    install(monkeypatch, clock, [{11: DONE_OK}])
    assert run("11", "11") == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 1
