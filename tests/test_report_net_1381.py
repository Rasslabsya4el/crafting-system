"""The report and the route page of a finished plan ask the run's memory net, and the plan's record is written first (ticket #1381).

R20's plan of 2026-11-21 was made in 3 h 50 min under a memory net of 12 GB; the kernel then killed the run at 16.7 GB while its report was
built, and the plan was lost with nothing said. The growth was the expected uses of the prices, solved by `risk.expected_totals` dense on each
cycle of the lumped view (28,773 blocks: a matrix of 6.6 GB, copied twice). Done when (the ticket): a plan whose report passes a small memory
net ends with its record written and a stated stop, not a crash.

The memory a test process holds is not the test's to set, so the figure the report's net reads (`budget.process_mb`) is the process's own
until the planner's entry has returned, and a figure past every net after it: the planner plans under the same net, unstopped, and the
report meets it. Nothing here reads the clock.
"""

import json

import pytest
from cli_support import R12, TODAY, price_file, read_json
from cli_support import run as run_command
from targets_support import DATA

import crafting_system.cli._benchmark as benchmark_module
from crafting_system import budget
from crafting_system.cli import _main, main
from crafting_system.cli._price_marks import expected_uses
from crafting_system.cli._report import RECORD
from crafting_system.cli._report_net import STAGE, ask, report_net
from crafting_system.cli._route_chain import chain_of_plan
from crafting_system.risk import expected_totals
from crafting_system.solver import Action, Outcome

from test_cli_benchmark import COMMAND, entry_of
from test_planner_entry import settings_of_the_command

NET_MB = 1_000_000  # the run's memory net: the planner never meets it in a test
HELD_MB = 2 * NET_MB  # what the process is said to hold once the plan is made


def held_past_the_net_after(monkeypatch, module, name: str, *, before: bool = False) -> None:
    """From the moment `module.name` returns (or, with `before`, is called) on, this process is said to hold `HELD_MB`."""
    real_mb, real_call = budget.process_mb, getattr(module, name)
    past = {"on": False}

    def process_mb(pid=None):
        return HELD_MB if past["on"] and pid is None else real_mb(pid)

    def call(*args, **kwargs):
        if before:
            past["on"] = True
        found = real_call(*args, **kwargs)
        past["on"] = True
        return found

    monkeypatch.setattr(budget, "process_mb", process_mb)
    monkeypatch.setattr(module, name, call)


def words(stop_kept: str = "the plan's record is written; what was not built is not shown") -> str:
    return f"{STAGE} stopped at the memory limit of {NET_MB:,.0f} MB ({HELD_MB:,.0f} MB held): {stop_kept}"


def test_a_report_past_the_memory_net_leaves_the_plan_s_record_and_says_where_it_stopped(tmp_path, capsys, monkeypatch):
    (tmp_path / "free").mkdir()
    code, out = run_command(tmp_path / "free", "--memory-limit", "none", prices=price_file())  # the same plan with no net: its JSON policy
    assert code == 0
    whole = read_json(out)
    capsys.readouterr()
    held_past_the_net_after(monkeypatch, _main, "plan_target")

    code, out = run_command(tmp_path, "--memory-limit", str(NET_MB), prices=price_file())

    printed = capsys.readouterr().out
    assert code == 0  # a stop said, not a crash: the plan was made
    assert printed.splitlines() == [
        f"Report not built: {words()}.",
        f"The plan's record (its cost, odds, start and limits) is written to {out}",
    ]
    record = read_json(out)
    assert record[RECORD] == {"report_built": False, "stopped": words()}
    assert record["totals"] == whole["totals"]  # the plan's cost and odds, as the JSON policy of the same plan gives them
    assert record["requirements"] == whole["requirements"] and record["offered_actions"] == whole["offered_actions"]
    assert record["states_solved"] == whole["states_solved"]
    assert "states" not in record  # what needs the report is not there
    assert not (out.parent / f"{R12.stem}.route.html").exists()


def test_a_page_past_the_memory_net_keeps_the_json_policy_and_says_the_page_is_not_written(tmp_path, capsys, monkeypatch):
    held_past_the_net_after(monkeypatch, _main, "write_route_page", before=True)

    code, out = run_command(tmp_path, "--memory-limit", str(NET_MB), prices=price_file())

    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    assert lines[-2:] == [f"JSON policy written to {out}", f"Route view not written: {words()}."]
    document = read_json(out)
    assert RECORD not in document and document["states"]  # the JSON policy replaced the record
    assert not (out.parent / f"{R12.stem}.route.html").exists()


def test_under_the_net_the_outputs_are_those_of_a_run_with_no_net(tmp_path, capsys):
    runs = []
    for folder, limit in (("free", "none"), ("netted", str(NET_MB))):
        (tmp_path / folder).mkdir()
        code, out = run_command(tmp_path / folder, "--memory-limit", limit, prices=price_file())
        assert code == 0
        page = (out.parent / f"{R12.stem}.route.html").read_text(encoding="utf-8")
        runs.append((capsys.readouterr().out.replace(str(tmp_path / folder), "DIR"), read_json(out), page))
    free, netted = runs

    def strip(text: str) -> list[str]:
        return [line for line in text.splitlines() if not line.startswith("Run time: ")]

    assert strip(free[0]) == strip(netted[0])
    assert {k: v for k, v in free[1].items() if k != "timings_seconds"} == {k: v for k, v in netted[1].items() if k != "timings_seconds"}
    assert RECORD not in netted[1]
    assert free[2] == netted[2]  # the route page


def test_the_net_is_asked_only_inside_the_report_s_block(monkeypatch):
    monkeypatch.setattr(budget, "process_mb", lambda pid=None: HELD_MB)
    ask()  # outside the block: nothing (the planner's own call of the page's maths, every other caller)
    with report_net(None):
        ask()  # no net: nothing
    with report_net(NET_MB), pytest.raises(budget.BudgetExceeded) as stop:
        ask()
    assert stop.value.binding.words() == words()


def run_benchmark(out_dir, *arguments):
    code = main([COMMAND, "--out", str(out_dir), *arguments], data=DATA, prices=price_file(), env={}, today=TODAY)
    return code, out_dir / "benchmark.json"


def test_the_benchmark_writes_a_route_s_record_before_anything_after_its_plan(tmp_path, monkeypatch):
    # the run is killed in what follows the plan (here: the published odds raise what no handler takes); benchmark.json holds the record
    monkeypatch.setattr(benchmark_module, "BENCHMARKS", benchmark_module.BENCHMARKS[:1])

    class Killed(BaseException):
        pass

    def killed(*args, **kwargs):
        raise Killed

    monkeypatch.setattr(benchmark_module, "published_odds", killed)
    with pytest.raises(Killed):
        run_benchmark(tmp_path, "--net")

    entry = entry_of(read_json(tmp_path / "benchmark.json"))
    assert entry["record"]["mean"] == entry["solver"]["mean"] and entry["record"]["stop"]


def test_the_benchmark_says_a_stop_after_the_plan_and_keeps_the_record(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_module, "BENCHMARKS", benchmark_module.BENCHMARKS[:1])
    held_past_the_net_after(monkeypatch, benchmark_module, "published_odds", before=True)
    config_net = {"CRAFTING_CONFIG": str(tmp_path / "net.toml")}
    (tmp_path / "net.toml").write_text(f"[planner]\nmemory_limit_mb = {NET_MB}\n", encoding="utf-8")

    code = main([COMMAND, "--out", str(tmp_path), "--net"], data=DATA, prices=price_file(), env=config_net, today=TODAY)

    assert code == 0
    entry = entry_of(read_json(tmp_path / "benchmark.json"))
    assert entry["error"] == words()
    assert entry["record"]["mean"] == entry["solver"]["mean"]
    assert entry["given_route"] is None  # stopped before the guide's route was read


def test_the_expected_uses_are_the_visits_of_the_risk_s_own_solve_on_r12():
    from crafting_system.planner import plan_target
    from crafting_system.targets import load_target

    plan = plan_target(DATA, load_target(R12, DATA), price_file(), settings_of_the_command())
    labels = sorted({action.label for action in plan.policy.values()})
    found = expected_uses(chain_of_plan(plan), labels)
    solved = expected_totals(plan.policy, plan.start, plan.is_goal, [lambda action, label=label: float(action.label == label) for label in labels])
    assert [found[label] for label in labels] == pytest.approx([each.value for each in solved], rel=1e-9, abs=1e-12)


def ring(size: int) -> dict:
    """A policy whose `size` states are one cycle (the shape of R20's lumped view: one strongly connected component), each with a 1% way out."""
    policy = {}
    for i in range(size):
        outcomes = (Outcome((i + 1) % size, 98), Outcome(0, 1), Outcome("goal", 1))
        policy[i] = Action("odd" if i % 2 else "even", 1.0, outcomes)
    return policy


def test_the_expected_uses_of_one_big_cycle_are_solved_without_a_dense_matrix(monkeypatch):
    # the dense solve of a cycle of n states holds n x n floats: 28,773 states are 6.6 GB. The visits are solved a block of edges at a time.
    from crafting_system.cli._route_flow import chain_of_policy
    from crafting_system.risk import _inputs

    small = ring(300)
    solved = expected_totals(small, 0, lambda s: s == "goal", [lambda a, n=name: float(a.label == n) for name in ("even", "odd")])
    found = expected_uses(chain_of_policy(0, small, lambda s: s == "goal"), ["even", "odd"])
    assert [found["even"], found["odd"]] == pytest.approx([each.value for each in solved], rel=1e-9)

    def dense(*args, **kwargs):
        raise AssertionError("a dense solve of a cycle")

    monkeypatch.setattr(_inputs._linear, "solve", dense)
    big = expected_uses(chain_of_policy(0, ring(20_000), lambda s: s == "goal"), ["even", "odd"])
    assert big["even"] + big["odd"] == pytest.approx(100.0, rel=1e-9)  # each use ends the run with chance 1 in 100


def test_the_record_is_plain_json():
    from crafting_system.cli._report import plan_record
    from crafting_system.planner import plan_target
    from crafting_system.targets import load_target

    plan = plan_target(DATA, load_target(R12, DATA), price_file(), settings_of_the_command())
    text = json.dumps(plan_record(plan, target_name=R12.name, stopped="why"), allow_nan=False)
    assert json.loads(text)[RECORD] == {"report_built": False, "stopped": "why"}


def test_a_stop_removes_the_page_an_earlier_run_left_beside_the_record(tmp_path, capsys, monkeypatch):
    stale = tmp_path / f"{R12.stem}.route.html"
    stale.write_text("the page of an earlier plan", encoding="utf-8")
    held_past_the_net_after(monkeypatch, _main, "plan_target")

    code, out = run_command(tmp_path, "--memory-limit", str(NET_MB), prices=price_file())

    assert code == 0 and read_json(out)[RECORD]["stopped"] == words()
    assert not stale.exists()
    assert not out.with_name(out.name + ".partial").exists()  # the JSON is written whole, then put in place


def test_the_site_s_work_past_the_net_after_the_plan_gives_the_record_and_no_page(monkeypatch):
    from web_support import FixtureWorld, r12_target

    from crafting_system.budget import Budget
    from crafting_system.config import load_config
    from crafting_system.web import _work

    class NettedWorld(FixtureWorld):
        @property
        def budget(self) -> Budget:  # type: ignore[override]
            return Budget(seconds=None, memory_mb=NET_MB)

    held_past_the_net_after(monkeypatch, _work, "plan_target")
    route = _work.plan_request(NettedWorld(DATA, price_file(), load_config({})), {"target": r12_target()}, "poe1", lambda standing: None)

    assert route["page"] is None
    assert route["policy"][RECORD] == {"report_built": False, "stopped": words()}
    assert route["summary"]["totals"] == route["policy"]["totals"] and route["summary"]["totals"]["mean_cost"]["value"] > 0
