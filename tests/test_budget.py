"""One budget of time and memory for every stage of a plan, and one list of what bound (ticket #825; OR-12, OR-13, OR-32, OR-33).

* the figures are named settings: OR-33's aim of a minute and net of 10 minutes, the memory net a share of the machine's memory;
* the memory reading gives a number on Linux, Windows and macOS (#540): this file runs on the Ubuntu and the Windows jobs of CI;
* the clock's arithmetic by hand, on a clock that only moves when the test says so (no test reads the time, tests/test_no_timing.py);
* on hand-made models, a small budget stops each stage of `make_plan` (the walk, the bound pruning of `solve_pruned` (#702), the search, the
  Lock's check) and the plan says which limit bound, in one limit (#378); a stop before any plan closed says "no plan found yet";
* the settings and the command line set the net (#537).
"""

import os
import re

import pytest
from test_cli_envelope_plan import coarse  # noqa: F401 (the fixture: the coarse world of about 200 states, its start bought for 5 Chaos)
from coarse_support import DATA as COARSE

from test_cli_limit_words import read  # the rule of player words (#481)

from crafting_system import budget
from crafting_system.abstraction import refusal_causes
from crafting_system.budget import MEMORY, STATES, TIME, Binding, Budget, BudgetExceeded
from crafting_system.cli import _main, make_plan
from crafting_system.planner import _plan
from crafting_system.planner._foresight import Status as LockStatus
from crafting_system.planner._limits import BUDGET, budget_limit
from crafting_system.planner._plan import PRUNED_STAGE, SEARCH_STAGE, WALK_STAGE, LOCK_STAGE, PlanError
from crafting_system.config import TIME_LIMIT_SECONDS, Config, load_config


class FakeTime:
    """A clock that only moves when the test says so (it stands in for `budget.time`)."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def perf_counter(self) -> float:
        return self.now


@pytest.fixture
def fake(monkeypatch):
    clock = FakeTime()
    monkeypatch.setattr(budget, "time", clock)
    return clock


# ---- the figures ------------------------------------------------------------------------------------------------------------------


def test_the_figures_are_or33s_and_the_memory_net_is_a_share_of_the_machine(monkeypatch):
    assert budget.AIM_SECONDS == 60.0 and budget.NET_SECONDS == 600.0 and budget.MEMORY_SHARE == 0.8
    monkeypatch.setattr(budget, "physical_mb", lambda: 16_000.0)
    assert Budget.default() == Budget(aim_seconds=60.0, seconds=600.0, memory_mb=12_800.0)  # a runner of 16 GB stops at 12.8 GB, not killed at 16
    monkeypatch.setattr(budget, "physical_mb", lambda: None)
    assert Budget.default().memory_mb is None  # where the machine does not say, no memory net rather than a guessed one
    assert Budget.unlimited() == Budget(None, None, None, None, 0.0)  # no gap either: every proof exact (#826, OR-39)


def test_a_budget_figure_is_a_number_zero_or_more_or_none():
    with pytest.raises(ValueError, match="seconds"):
        Budget(seconds=-1.0)
    with pytest.raises(ValueError, match="memory_mb"):
        Budget(memory_mb=float("inf"))
    assert Budget(seconds=0.0).seconds == 0.0


def test_the_settings_default_is_the_budgets():
    assert TIME_LIMIT_SECONDS == budget.NET_SECONDS  # config.py imports nothing, so it writes the figure again


# ---- the memory reading (#540) ------------------------------------------------------------------------------------------------------


def test_the_memory_of_this_process_and_of_the_machine_is_read_here():
    """CI runs this on Ubuntu and on Windows: before #825 Windows gave no reading, and the memory net never stopped anything there."""
    own = budget.process_mb()
    total = budget.physical_mb()
    assert own is not None and total is not None
    assert 1.0 < own < total
    by_pid = budget.process_mb(os.getpid())
    assert by_pid is not None and by_pid == pytest.approx(own, rel=0.5)  # the same process read by its id (it may have grown a little)


def test_a_process_that_does_not_exist_has_no_reading():
    assert budget.process_mb(2**31 - 7) is None


# ---- the clock, by hand ------------------------------------------------------------------------------------------------------------


def test_the_time_left_is_the_net_less_what_was_spent(fake):
    clock = Budget(seconds=600.0, memory_mb=None).start()
    fake.now = 1250.0
    assert clock.elapsed() == 250.0
    assert clock.left() == 350.0
    fake.now = 1700.0
    assert clock.left() == 0.0  # never below zero
    assert Budget.unlimited().start().left() is None


def test_a_limit_is_met_by_time_or_by_memory_and_said_with_its_figures(fake, monkeypatch):
    monkeypatch.setattr(budget, "process_mb", lambda pid=None: 900.0)
    clock = Budget(seconds=600.0, memory_mb=800.0).start()
    assert clock.over("the walk") == Binding("the walk", MEMORY, 800.0, 900.0)
    clock = Budget(seconds=600.0, memory_mb=1_000.0).start()
    assert clock.over("the walk") is None
    fake.now = 1601.0
    assert clock.over("the walk", "no plan found yet") == Binding("the walk", TIME, 600.0, 601.0, "no plan found yet")
    assert clock.bindings == []  # `over` only looks; `bind` records


def test_the_words_of_a_binding():
    assert Binding("the search", TIME, 600.0, 601.4, "no plan found yet").words() == (
        "the search stopped at the time limit of 600 s (601 s spent): no plan found yet"
    )
    assert Binding("the walk", MEMORY, 12_800.0, 12_850.0).words() == "the walk stopped at the memory limit of 12,800 MB (12,850 MB held)"
    assert Binding("the search", STATES, 96, 97, "kept").words() == "the search stopped at the limit of 96 states (97 reached): kept"


def test_a_checkpoint_past_the_net_stops_the_stage_it_is_in_and_records_it_once(fake):
    clock = Budget(seconds=10.0, memory_mb=None).start()
    with budget.running(clock):
        budget.checkpoint()  # within the net: nothing
        fake.now = 1010.0
        with budget.stage("the walk", "what is left"):
            with pytest.raises(BudgetExceeded) as stop:
                budget.checkpoint()
            assert stop.value.binding == Binding("the walk", TIME, 10.0, 10.0, "what is left")
            with pytest.raises(BudgetExceeded):
                budget.checkpoint()
        assert clock.stage == "the plan" and clock.what == budget.NO_PLAN  # the stage's name is given back
    assert clock.bindings == [Binding("the walk", TIME, 10.0, 10.0, "what is left")]  # met twice, listed once
    budget.checkpoint()  # outside a run: nothing, whatever the time


def test_a_stop_is_not_swallowed_by_a_stages_own_except_exception(fake):
    """A pool that falls back to a serial run, a refused offer: their `except Exception` must not run on past the net."""
    clock = Budget(seconds=0.0, memory_mb=None).start()
    with budget.running(clock), pytest.raises(BudgetExceeded):
        try:
            budget.checkpoint()
        except Exception:  # noqa: BLE001 (the point of the test)
            pytest.fail("the stop was caught as an ordinary error")


def test_a_run_inside_a_run_keeps_the_outer_clock(fake):
    outer = Budget(seconds=100.0).start()
    with budget.running(outer) as first:
        with budget.running(Budget(seconds=5.0).start()) as inner:
            assert first is outer and inner is outer and budget.active() is outer
    assert budget.active() is None


def test_one_limit_lists_every_binding_in_the_order_they_bound():
    assert budget_limit([]) is None
    first = Binding("the search", STATES, 96, 97, "kept")
    second = Binding("the check", TIME, 600.0, 601.0, "the plan without it")
    limit = budget_limit([first, second])
    assert limit.kind == BUDGET and limit.names == (first.words(), second.words())
    assert first.words() in limit.reason() and second.words() in limit.reason()
    for stage, kept in ((_plan.WALK_STAGE, budget.NO_PLAN), (_plan.PRUNED_STAGE, budget.NO_PLAN), (_plan.READINGS_STAGE, budget.NO_PLAN),
                        (_plan.SEARCH_STAGE, _plan.SEARCH_KEPT), (_plan.LOCK_STAGE, _plan.LOCK_KEPT), (_plan.RISK_STAGE, _plan.RISK_KEPT)):
        read(budget_limit([Binding(stage, TIME, 600.0, 601.0, kept), Binding(stage, MEMORY, 9.0, 10.0, kept)]))  # every stage and stop in player words


# ---- every stage of make_plan, on hand-made models ----------------------------------------------------------------------------------


def refusal(coarse_world, **kwargs) -> str:
    target, prices, _ = coarse_world
    with pytest.raises(PlanError) as error:
        make_plan(COARSE, target, prices, start_price=5.0, with_risk=False, **kwargs)
    return str(error.value)


@pytest.mark.parametrize("solver", ["packed", "object"])
def test_the_walk_of_every_item_stops_at_the_net_and_says_where_with_no_plan_yet(coarse, solver):  # noqa: F811
    said = refusal(coarse, solver=solver, budget=Budget(seconds=0.0, memory_mb=None))
    assert re.fullmatch(rf"stopped after \d+ s: {WALK_STAGE} stopped at the time limit of 0 s \(\d+ s spent\): no plan found yet", said), said


def test_the_bound_pruning_stops_at_the_net_instead_of_running_on(coarse, fake, monkeypatch):  # noqa: F811
    """#702: `solve_pruned` had no net, and R08 at the prices of 2026-11-07 ran past a runner's 25 minutes and 16 GB with no word.

    The clock passes the net of 100 s as the bound pruning starts (it took 150 s): its first checkpoint stops it, and the answer says where."""
    monkeypatch.setattr(_plan, "MIN_OFFERS_TO_PRUNE", 2)  # the coarse world's offers go the way of the fossil sets: the bound pruning
    seen = []
    real = _plan.solve_pruned

    def late(*args, **kwargs):
        seen.append(1)
        fake.now += 150.0
        return real(*args, **kwargs)

    monkeypatch.setattr(_plan, "solve_pruned", late)
    # a run with no aim: with an aim `auto` is the envelope search whatever the number of offers (#926), and the bound pruning is not taken
    said = refusal(coarse, budget=Budget(aim_seconds=None, seconds=100.0, memory_mb=None))
    assert seen, "the plan did not take the bound pruning"
    assert said == (
        f"stopped after 150 s: {PRUNED_STAGE} stopped at the time limit of 100 s (150 s spent): no plan found yet; "
        "the faster search, which proves its plan against the cheapest possible cost, was not used: 2 actions or more are offered and the run was given no time to aim at"
    )  # the stop says why `auto` walked instead of searching (OR-13, #926)


def test_a_memory_net_stops_the_run_where_it_is_and_says_so(coarse):  # noqa: F811
    said = refusal(coarse, solver="packed", budget=Budget(seconds=None, memory_mb=0.0))
    assert re.fullmatch(r"stopped after \d+ s: .+ stopped at the memory limit of 0 MB \([\d,]+ MB held\): no plan found yet", said), said


def test_the_bound_pruning_with_room_gives_the_plan_and_lists_nothing(coarse, monkeypatch):  # noqa: F811
    monkeypatch.setattr(_plan, "MIN_OFFERS_TO_PRUNE", 2)
    target, prices, full = coarse
    plan = make_plan(COARSE, target, prices, start_price=5.0, with_risk=False, budget=Budget(aim_seconds=None, seconds=3_600.0, memory_mb=None))
    assert plan.pruned is not None and plan.mean_remaining == pytest.approx(full.mean_remaining, rel=1e-9)
    assert not [limit for limit in plan.limits if limit.kind == BUDGET]


# ---- #926: under a budget `auto` never reaches the forecast of ADR-0023 or its ladder of approximate answers ----------------------------


@pytest.fixture
def no_forecast(monkeypatch):
    """The forecast and the ladder fail the test that reaches them."""

    def reached(*_args, **_kwargs):
        raise AssertionError("a plan under `auto` reached the retired forecast or its ladder")

    monkeypatch.setattr(_plan, "decide", reached)
    monkeypatch.setattr(_plan, "climb", reached)


def test_under_a_budget_many_offers_take_the_envelope_search_not_the_forecast(coarse, monkeypatch, no_forecast):  # noqa: F811
    """The twelve family cases of #926 offered 43 to 140 actions: 40 or more sent `auto` to the bound pruning, and a budget put the forecast and the
    ladder before it, which refused them. With an aim it is the envelope search: its own stop at the proved gap, and the net as the guard."""
    monkeypatch.setattr(_plan, "MIN_OFFERS_TO_PRUNE", 2)
    target, prices, full = coarse
    plan = make_plan(COARSE, target, prices, start_price=5.0, with_risk=False, budget=Budget(seconds=3_600.0, memory_mb=None))
    assert plan.pruned is None and plan.approximation is None and plan.search is not None
    assert plan.search.exact or plan.search.within is not None  # it ended by itself: exact, or at the budget's proved gap (OR-39)
    assert full.mean_remaining * (1 - 1e-9) <= plan.mean_remaining <= full.mean_remaining * (1 + Budget().gap)
    assert not [limit for limit in plan.limits if limit.kind == BUDGET]


def test_under_a_budget_many_offers_stop_at_the_net_in_the_searchs_own_words(coarse, monkeypatch, no_forecast):  # noqa: F811
    monkeypatch.setattr(_plan, "MIN_OFFERS_TO_PRUNE", 2)
    target, prices, full = coarse
    stopped = make_plan(COARSE, target, prices, start_price=5.0, with_risk=False, budget=Budget(seconds=None, memory_mb=None, states=96, gap=0.0))
    info = stopped.search
    assert info is not None and not info.exact and info.within is None  # the net ended it, with the best plan found and the figure below it
    assert info.lower <= full.mean_remaining * (1 + 1e-9) <= info.upper * (1 + 1e-9)
    assert [limit.names for limit in stopped.limits if limit.kind == BUDGET] == [(Binding(SEARCH_STAGE, STATES, 96, info.touched, _plan.SEARCH_KEPT).words(),)]


@pytest.mark.parametrize("why", ["no bound", "a route to judge"])
def test_under_a_budget_a_target_the_search_cannot_take_is_walked_to_the_net_with_no_forecast(coarse, monkeypatch, no_forecast, why):  # noqa: F811
    """Where the envelope search cannot take the target (no lower bound for it yet, or a given route to judge) a budget changes nothing but the
    net: the same exact walk as with no budget, and no approximate answer."""
    if why == "no bound":
        monkeypatch.setattr(_plan, "pattern_refusal", lambda _abstraction: "planted for the test")
    judged = dict(judges_route=why == "a route to judge")
    target, prices, full = coarse
    plan = make_plan(COARSE, target, prices, start_price=5.0, with_risk=False, budget=Budget(aim_seconds=0.0, seconds=3_600.0, memory_mb=None), **judged)
    assert plan.search is None and plan.approximation is None and plan.mean_remaining == pytest.approx(full.mean_remaining, rel=1e-9)
    assert not [limit for limit in plan.limits if limit.what.startswith(("The whole search", "The time of the search"))]  # the forecast's two limits


def test_a_walk_the_net_stops_says_what_the_search_has_no_bound_for(coarse, monkeypatch, no_forecast):  # noqa: F811
    """OR-13, #926: `auto` walked because the search has no lower bound for the target; the stop says which, in the words of `refusal_causes`."""
    monkeypatch.setattr(_plan, "pattern_refusal", lambda _abstraction: "planted")
    monkeypatch.setattr(_plan, "refusal_causes", lambda _abstraction, player: ("an offered action reads the mods an unveil shows to pick from",) if player else ())
    said = refusal(coarse, budget=Budget(seconds=0.0, memory_mb=None))
    assert re.fullmatch(
        rf"stopped after \d+ s: {WALK_STAGE} stopped at the time limit of 0 s \(\d+ s spent\): no plan found yet; the faster search, which proves "
        r"its plan against the cheapest possible cost, was not used: it has no such cost yet where an offered action reads the mods an unveil shows to pick from",
        said,
    ), said
    refused = make_plan(COARSE, coarse[0], coarse[1], start_price=5.0, solve_it=False).abstraction
    refused._has_laws = True
    for name in ("rerolls_values", "tracks_offer", "tracks_imprints"):
        monkeypatch.setattr(type(refused), name, property(lambda self: True), raising=False)
    every = refusal_causes(refused, player=True)
    assert len(every) == len(refusal_causes(refused)) == 4  # every cause the bound has, in the words an answer may show (#481)
    read(budget_limit([Binding(WALK_STAGE, TIME, 0.0, 1.0, _plan.walk_stop(_plan.walk_cause(every, False)))]))
    monkeypatch.setattr(_plan, "pattern_refusal", lambda _abstraction: None)
    judged = refusal(coarse, budget=Budget(seconds=0.0, memory_mb=None), judges_route=True)
    assert judged.endswith("was not used: a given route is judged against the plan, which needs the planner's choice at every item the route can reach")


@pytest.mark.parametrize("solver", ["packed", "object"])
def test_a_walk_asked_for_by_name_says_no_cause(coarse, solver):  # noqa: F811
    assert refusal(coarse, solver=solver, budget=Budget(seconds=0.0, memory_mb=None)).endswith(": no plan found yet")


def test_a_stopped_search_keeps_its_plan_and_the_plan_says_which_limit_bound(coarse):  # noqa: F811
    target, prices, full = coarse
    stopped = make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", budget=Budget(seconds=None, memory_mb=None, states=96), with_risk=False)
    info = stopped.packed.info["envelope"]
    assert not info.exact and info.lower <= full.mean_remaining * (1 + 1e-9) <= info.upper * (1 + 1e-9)
    (bound,) = [limit for limit in stopped.limits if limit.kind == BUDGET]
    (said,) = bound.names
    assert said.startswith(f"{SEARCH_STAGE} stopped at the limit of 96 states (") and said.endswith(_plan.SEARCH_KEPT)
    read(bound)


def test_the_old_net_argument_is_the_same_budget(coarse):  # noqa: F811
    from crafting_system.planner._envelope import Net

    target, prices, _ = coarse
    by_net = make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", net=Net(states=96), with_risk=False)
    (bound,) = [limit for limit in by_net.limits if limit.kind == BUDGET]
    assert "the limit of 96 states" in bound.names[0]


def test_a_stop_met_in_a_worker_is_listed_on_the_runs_own_clock(coarse, monkeypatch):  # noqa: F811
    """A forked worker checks its own copy of the clock: the stop it sends back must still be listed on the run's clock (OR-12, #378)."""
    target, prices, _ = coarse

    def stopped_in_a_worker(*args, **kwargs):  # the binding is made on another clock, as in a worker, and only the stop comes back
        raise BudgetExceeded(Binding(_plan.LOCK_STAGE, TIME, 600.0, 601.0, _plan.LOCK_KEPT))

    monkeypatch.setattr(_plan, "plan_foresight", stopped_in_a_worker)
    plan = make_plan(COARSE, target, prices, start_price=5.0, solver="packed", budget=Budget(seconds=3_600.0, memory_mb=None), with_risk=False)
    (bound,) = [limit for limit in plan.limits if limit.kind == BUDGET]
    assert bound.names == (Binding(_plan.LOCK_STAGE, TIME, 600.0, 601.0, _plan.LOCK_KEPT).words(),)
    assert plan.foresight.status is LockStatus.STOPPED


def test_a_stop_in_the_check_of_the_lock_keeps_the_plan_without_it_and_both_stops_are_listed_once(coarse, monkeypatch):  # noqa: F811
    """A plan has closed when the Lock is checked: the stop keeps it (OR-33), and the one limit lists the search's stop and the Lock's, in order."""
    target, prices, _ = coarse

    def stopped_check(*args, **kwargs):  # the check of the Lock meets the run's net: what a checkpoint inside it does
        clock = budget.active()
        raise BudgetExceeded(clock.bind(Binding(clock.stage, TIME, 600.0, 601.0, clock.what)))

    monkeypatch.setattr(_plan, "plan_foresight", stopped_check)
    plan = make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", budget=Budget(seconds=None, memory_mb=None, states=96), with_risk=False)
    assert plan.foresight.status is LockStatus.STOPPED and plan.solution is not None
    (bound,) = [limit for limit in plan.limits if limit.kind == BUDGET]
    assert [name.split(" stopped at ")[0] for name in bound.names] == [SEARCH_STAGE, LOCK_STAGE]
    assert bound.names[1].endswith(_plan.LOCK_KEPT)
    read(bound)


def test_a_plan_without_a_budget_runs_every_stage_to_its_end(coarse):  # noqa: F811
    target, prices, full = coarse
    plan = make_plan(COARSE, target, prices, start_price=5.0, solver="packed", with_risk=False)
    assert plan.mean_remaining == full.mean_remaining and not [limit for limit in plan.limits if limit.kind == BUDGET]


def test_a_number_as_budget_is_the_aim_alone_as_before():
    assert _plan.as_budget(60.0) == Budget(aim_seconds=60.0, seconds=None, memory_mb=None)
    assert _plan.as_budget(None) is None
    given = Budget(seconds=5.0, memory_mb=None)
    assert _plan.as_budget(given) is given


# ---- the settings and the command line (#537) ------------------------------------------------------------------------------------------


def test_the_settings_set_the_net_and_none_turns_a_limit_off(tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "crafting.toml").write_text('[planner]\ntime_limit_seconds = 90\nmemory_limit_mb = "none"\n')
    config = load_config({}, project_root=tmp_path)
    assert config.time_limit_seconds == 90.0 and config.memory_limit_mb is None
    (tmp_path / "crafting.toml").write_text("[planner]\n")
    default = load_config({}, project_root=tmp_path)
    assert default.time_limit_seconds == 600.0 and default.memory_limit_mb == "share"
    (tmp_path / "crafting.toml").write_text("[planner]\ntime_limit_seconds = -5\n")
    with pytest.raises(ValueError, match="time_limit_seconds"):
        load_config({}, project_root=tmp_path)
    (tmp_path / "crafting.toml").write_text('[planner]\ntime_limit_seconds = "share"\n')
    with pytest.raises(ValueError, match="time_limit_seconds"):
        load_config({}, project_root=tmp_path)


def test_the_command_line_wins_over_the_settings_and_the_share_is_of_the_machine(monkeypatch, tmp_path):
    monkeypatch.setattr(_main, "default_memory_mb", lambda: 12_800.0)
    config = Config(tmp_path, tmp_path, tmp_path)
    assert _main.run_budget(config, 60.0) == Budget(aim_seconds=60.0, seconds=600.0, memory_mb=12_800.0)
    assert _main.run_budget(config, None, None, 2_000.0) == Budget(aim_seconds=None, seconds=None, memory_mb=2_000.0)
    assert _main._limit("none") is None and _main._limit("90") == 90.0
    for wrong in ("0", "-1", "inf", "soon"):
        with pytest.raises(Exception, match="above zero"):
            _main._limit(wrong)


# ---- the stop across processes and threads ------------------------------------------------------------------------------------------


def test_a_stop_met_in_a_pool_worker_reaches_the_parent_whole():
    import pickle

    stop = BudgetExceeded(Binding("the walk", TIME, 600.0, 601.0, "no plan found yet"))
    back = pickle.loads(pickle.dumps(stop))
    assert isinstance(back, BudgetExceeded) and back.binding == stop.binding and str(back) == str(stop)


def test_the_runs_clock_is_let_go_after_a_stop(fake):
    clock = Budget(seconds=0.0, memory_mb=None).start()
    with pytest.raises(BudgetExceeded), budget.running(clock):
        budget.checkpoint()
    assert budget.active() is None


def test_two_runs_in_two_threads_each_have_their_own_clock(fake):
    import threading

    seen = {}
    ready = threading.Barrier(2)

    def run(name: str, seconds: float) -> None:
        with budget.running(Budget(seconds=seconds, memory_mb=None).start()):
            ready.wait()
            seen[name] = budget.active().budget.seconds
            ready.wait()

    threads = [threading.Thread(target=run, args=(name, seconds)) for name, seconds in (("first", 10.0), ("second", 20.0))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert seen == {"first": 10.0, "second": 20.0} and budget.active() is None


def test_a_ladder_the_runs_net_stopped_says_the_run_spent_it(fake):
    from crafting_system.risk import _regen

    clock = Budget(seconds=600.0, memory_mb=None).start()
    fake.now = 1600.0  # the plan took the whole net: the ladder starts with no time left
    with budget.running(clock):
        said = _regen.ladder_stopped(_regen.ladder_net(1800.0), coarser=False)
    assert said == (
        "the run's time limit was reached before the quicker method for the cost figures could work any of them out; the slower method follows"
    )
    assert "30 seconds" in _regen.time_net_words(30.0, coarser=True) and "30 minutes" in _regen.time_net_words(1800.0, coarser=True)


def test_the_command_stops_at_its_time_limit_and_says_so(tmp_path, capsys):
    from cli_support import price_file, run

    code, _ = run(tmp_path, "--time-limit", "0.000001", "--solver", "packed", prices=price_file())
    error = capsys.readouterr().err
    assert code != 0
    assert re.search(rf"Error: stopped after \d+ s: {WALK_STAGE} stopped at the time limit of 0 s \(\d+ s spent\): no plan found yet", error), error


# ---- part 2: the pool's wait and the memory of the workers (#825, #540, #702) -------------------------------------------------------------


def test_the_memory_held_with_the_workers_is_read_on_this_os():
    """#540: before #825 the memory net of the search and the build read nothing on Windows (`parallel.held_mb` read /proc only)."""
    from crafting_system import parallel

    held = parallel.held_mb()
    assert held is not None and held > 1.0


def test_a_pool_watches_the_runs_net_only_in_a_stage_that_stops(fake):
    from crafting_system import parallel

    assert parallel._watched_clock() is None  # outside a run
    with budget.running(Budget(seconds=None, memory_mb=None).start()):
        assert parallel._watched_clock() is None  # a run with no net
    clock = Budget(seconds=60.0, memory_mb=None).start()
    with budget.running(clock):
        assert parallel._watched_clock() is clock
        with budget.stage("the search", stops=False):
            assert parallel._watched_clock() is None  # the search stops at its own net and keeps its plan


def hangs(piece: int) -> int:
    import threading

    threading.Event().wait()
    return piece


@pytest.mark.skipif(not __import__("crafting_system.parallel", fromlist=["can_inherit"]).can_inherit(), reason="a pool of forked workers")
def test_a_pool_past_the_runs_net_is_stopped_with_the_runs_stop_not_a_worker_error():
    """#702: the bound pruning waited on its pool past every limit. A wait past the run's net kills the workers and raises the run's stop."""
    from crafting_system import parallel

    clock = Budget(seconds=0.0, memory_mb=None).start()
    with budget.running(clock), budget.stage("the bound pruning"):
        with pytest.raises(BudgetExceeded) as stop:
            with parallel.WorkerPool(lambda: None, (), workers=2) as pool:
                try:
                    pool.map(hangs, range(4), chunk=1)
                except Exception:  # noqa: BLE001 (what `raise_together` does with a failed pool)
                    pytest.fail("the run's stop was taken for a failed worker")
    assert stop.value.binding.stage == "the bound pruning" and clock.bindings == [stop.value.binding]


def test_a_stage_stopped_early_to_leave_room_says_so():
    assert Binding("the search", TIME, 600.0, 590.0, "kept").words() == (
        "the search stopped 10 s before the time limit of 600 s, to leave room for what follows (590 s spent): kept"
    )
    assert Binding("the walk", TIME, 600.0, 599.99).words() == "the walk stopped at the time limit of 600 s (600 s spent)"  # a clock step short of it


@pytest.mark.skipif(not __import__("crafting_system.parallel", fromlist=["can_inherit"]).can_inherit(), reason="a pool of forked workers")
def test_a_pool_that_watches_the_runs_net_gives_the_same_list_in_the_same_order():
    from crafting_system import parallel

    with budget.running(Budget(seconds=3_600.0, memory_mb=None).start()), budget.stage("the bound pruning"):
        assert parallel._watched_clock() is not None
        with parallel.WorkerPool(lambda: None, (), workers=2) as pool:
            assert pool.map(abs, [-k for k in range(40)], chunk=3) == list(range(40))


def test_the_risk_stage_keeps_its_plan_when_the_run_is_past_its_net(coarse, fake):  # noqa: F811
    """The percentiles refine a plan already in hand (OR-34): past the net their ladder stops itself and says so; the plan is never lost to it."""
    target, prices, full = coarse

    def spent(*args, **kwargs):
        fake.now += 10_000.0  # the plan took past the whole net before the percentiles began
        return real(*args, **kwargs)

    from crafting_system import parallel

    with budget.running(Budget(seconds=600.0, memory_mb=None).start()), budget.stage(_plan.RISK_STAGE, _plan.RISK_KEPT, stops=False):
        assert parallel._watched_clock() is None  # no pool of the risk stage is stopped by the run's net: its ladder stops itself
    real = _plan.plan_foresight
    _plan.plan_foresight = spent
    try:
        plan = make_plan(COARSE, target, prices, start_price=5.0, solver="packed", budget=Budget(seconds=600.0, memory_mb=None))
    finally:
        _plan.plan_foresight = real
    assert plan.mean_remaining == pytest.approx(full.mean_remaining, rel=1e-12) and plan.risk is not None
