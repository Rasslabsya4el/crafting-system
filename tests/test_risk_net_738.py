"""The cost figures stop at their net, every method of them (ticket #738, OR-40, OR-13).

R17's site plan (`benchmark_routes.py R17 --net`, 2026-11-18, `.claude/scratch/t1224/f1-R17-8-t1224-main.log`): when its Exalted round found the
plan of about 24,500 Chaos, the run's net was spent by the plan, and the percentiles of its merged chain (12,399 classes) were killed for memory at
12 and 16 GB. Two faults of one mechanism, the net that only the attempt-by-attempt ladder honoured:

* each step of the ladder had one attempt run stopped by the net and the other refused by its fold (a loop of nearly free states longer than
  `FOLD_LIMIT` on the lower chain); the refusal was read first, so the step counted as "no answer", not "stopped", and every finer step ran;
* after the ladder the ordinary grid ran with no net at all ("the slower method follows"), on a chain whose grid fills memory.

Now one net (`_regen.ladder_net`: `REGEN_SECONDS`, or what the run has left, and the run's memory net) bounds every method of the figures: past
the deadline each run may expand `_budget.ALLOWANCE` entries more (a cheap run, R10's or R11's site plan of a few classes, still ends exact; a dear
one stops), and at the memory net it stops at once (`_budget.Watch`; a pool's parent watches its workers' sum and stops them). A run it stops keeps
what it reached; the figures it did not reach are not computed and say so (`GridInfo.stopped`, the risk limit), while the plan, its odds and its
exact mean stand. Counted in steps, bins and entries on a clock that moves only when the test says so (no test reads the time).
"""

import math

import numpy as np
import pytest
from test_cli_envelope_plan import coarse  # noqa: F401 (the fixture: the coarse world of about 200 states, its start bought for 5 Chaos)
from coarse_support import DATA as COARSE

from crafting_system import budget, parallel
from crafting_system.budget import Budget
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.planner import _limits, _plan
from crafting_system.planner._limits import RISK, STOPPED_FIGURE, STOPPED_FIGURE_MEMORY, not_shown, risk_limits
from crafting_system.risk import _budget, _dense, _evaluate, _regen, evaluate
from crafting_system.risk._chain import Chain
from crafting_system.solver import Action, Outcome


class Ticking:
    """A clock that moves `tick` seconds each time it is read (it stands in for `time` in `_regen` and `_budget`)."""

    def __init__(self, tick: float = 0.0, now: float = 1000.0) -> None:
        self.now, self.tick = now, tick

    def monotonic(self) -> float:
        self.now += self.tick
        return self.now

    perf_counter = monotonic


CHAIN = Chain((0, 1, None), (False, True, False), (Action("a", 1.0, ((1, 1),)), None, None), (((1, 1.0),), (), ()), (True, True, False), ((),) * 3)


@pytest.mark.parametrize("reason,marker", [(budget.TIME, _regen.TIMED_OUT), (budget.MEMORY, _regen.OUT_OF_MEMORY)])
def test_a_ladder_step_stopped_by_the_net_is_refused_though_its_other_attempt_was_refused_by_its_fold(monkeypatch, reason, marker):
    # R17: the lower chain's attempt folds gave up (None), the upper chain's attempt runs were stopped at bin 1 by the net
    stopped_run = (np.zeros(1), 1.0, reason)
    monkeypatch.setattr(_regen, "run_jobs", lambda jobs, deadline=None: [None, None, stopped_run, stopped_run])

    found = _regen.regenerative_runs(CHAIN, [0, 0, 0], [1, 0, 0], 0.9, 10, lambda b: 0.0, 10, deadline=0.0, step=1.0)

    assert found == marker  # before #738: None, and the ladder went on to every finer step past its net


def test_a_ladder_step_whose_pool_passed_the_memory_net_is_refused_and_not_run_again_here(monkeypatch):
    def watched(jobs, deadline=None):
        raise parallel.MemoryNetReached("this process and its workers held 13,000 MB, the limit is 12,000 MB; the workers were stopped")

    monkeypatch.setattr(_regen, "run_jobs", watched)
    assert _regen.regenerative_runs(CHAIN, [1, 0, 0], [1, 0, 0], 0.9, 10, lambda b: 0.0, 10, deadline=None) == _regen.OUT_OF_MEMORY


def restarting(**extra):
    """`test_risk_regen.narrow`: a craft that starts over (a restart pays 6), whose figures only the ladder reaches on 10 bins."""
    from test_risk_regen import narrow

    return narrow(regenerative=True, **extra)


def test_a_ladder_the_net_stops_runs_no_finer_step_and_the_ordinary_grid_after_it_is_held_to_the_same_net(monkeypatch):
    clock = Ticking()
    monkeypatch.setattr(_regen, "time", clock)
    monkeypatch.setattr(_budget, "time", clock)
    monkeypatch.setattr(_budget, "ALLOWANCE", 0)
    tried = []

    def stopped_by_the_net(jobs, deadline=None):  # each upper attempt is stopped at the net, each lower one is refused by its fold (R17)
        tried.append(deadline)
        clock.now = deadline + 1.0
        return [None if k < len(jobs) // 2 else (np.zeros(1), 1.0, budget.TIME) for k in range(len(jobs))]

    monkeypatch.setattr(_regen, "run_jobs", stopped_by_the_net)

    report = restarting()

    assert len(tried) == 1  # one step, stopped; before #738: all five steps, then the ordinary grid with no net
    assert _regen.time_net_words(_evaluate.REGEN_SECONDS, coarser=False) in report.grid.gave_up  # the ladder's stop, said
    assert report.grid.stopped == _regen.figures_words(budget.TIME, _evaluate.REGEN_SECONDS, None, False)  # and the ordinary grid's
    assert report.grid.bins == 0 and all(math.isinf(e.high) for e in (report.p50, report.p90, report.cvar))  # stopped at its first bin
    # the exact mean stands, by hand: E[s] = 3 + 2/6 E[t] + 3/6 E[bad], E[bad] = 6 + E[s], E[t] = 4.5 + 1/3 E[bad] + 1/3 E[s] = 6.5 + 2/3 E[s];
    # so E[s] (1 - 2/9 - 1/2) = 3 + 6.5/3 + 3, E[s] = (49/6) / (5/18) = 29.4
    assert report.mean.value == pytest.approx(29.4, rel=1e-9)


def geometric(p_goal: float):
    """One state that pays 1 and ends with chance `p_goal`, else tries again: no restart, so only the ordinary grid computes its figures."""
    weight = round(p_goal * 10_000)
    return {"s": Action("try", 1.0, (Outcome("goal", weight), Outcome("s", 10_000 - weight)))}


@pytest.fixture
def spent(monkeypatch):
    """The figures' net is passed before they begin (`REGEN_SECONDS` 0): R17's site plan, whose run had 0 s left."""
    clock = Ticking(1.0)
    monkeypatch.setattr(_regen, "time", clock)
    monkeypatch.setattr(_budget, "time", clock)
    monkeypatch.setattr(_evaluate, "REGEN_SECONDS", 0.0)


def figures():
    return evaluate(geometric(1e-4), "s", lambda state: state == "goal")


def test_past_the_net_the_ordinary_grid_expands_its_allowance_and_stops_there(spent, monkeypatch):  # noqa: F811
    whole = evaluate(geometric(1e-4), "s", lambda state: state == "goal", max_bins=200_000)
    # by hand: the first n with 1 - (1 - 1e-4)^n >= level; p50 n = ceil(ln 0.5 / ln(1 - 1e-4)) = 6,932, p90 n = ceil(ln 0.1 / ln(1 - 1e-4)) = 23,025
    assert (whole.p50.value, whole.p90.value) == (6_932, 23_025) and not whole.grid.stopped

    monkeypatch.setattr(_budget, "ALLOWANCE", 10_000)  # one state, one entry a bin: the run stops 10,000 bins past the net, seen passed at bin 0
    cut = figures()

    assert cut.grid.bins == 10_000
    assert cut.p50.value == 6_932  # reached within the allowance: exact
    assert math.isinf(cut.p90.high) and cut.p90.low == 10_000  # not reached: not computed, with the bins it did reach as its low end
    assert cut.grid.stopped == _regen.figures_words(budget.TIME, 0.0, None, False) and cut.mean == whole.mean

    monkeypatch.setattr(_budget, "ALLOWANCE", 2 * 23_025)
    assert figures() == whole  # a run that ends within its allowance is the run with no net at all


def test_at_the_memory_net_a_run_of_the_figures_stops_at_once_and_says_so(monkeypatch):
    with parallel.memory_net(1.0):  # 1 MB: any process holds more
        report = figures()

    assert report.grid.bins == 0 and math.isinf(report.p50.high) and math.isinf(report.p90.high)
    assert report.grid.stopped == _regen.figures_words(budget.MEMORY, _evaluate.REGEN_SECONDS, None, False)
    assert "memory limit" in report.grid.stopped and not_shown(report, report.p90) == STOPPED_FIGURE_MEMORY  # the cell names the memory net


def test_a_pool_of_the_figures_past_the_memory_net_is_not_run_again_here(monkeypatch):
    calls = []

    def watched(low, high):
        calls.append(low)
        raise parallel.MemoryNetReached("held 13,000 MB, the limit is 12,000 MB; the workers were stopped")

    monkeypatch.setattr(_evaluate, "_both", watched)
    report = evaluate({"s": Action("try", 1.5, (Outcome("goal", 1), Outcome("s", 9)))}, "s", lambda state: state == "goal", resolution=1.0)

    assert len(calls) == 1 and math.isinf(report.p90.high) and "memory limit" in report.grid.stopped
    assert report.mean.value == pytest.approx(15.0)  # 1.5 Chaos a try, 10 tries on average


def test_the_dense_grid_stops_at_a_passed_net(monkeypatch):
    chain = Chain((0, 1), (False, True), (Action("a", 1.0, ((1, 1),)), None), (((0, 0.999), (1, 0.001)), ()), (True, True), ((),) * 2)
    run = dict(initial=((0, 1.0),), target=0.9, tail_mass=1e-9, max_bins=100_000)

    whole = _dense.run_dense(chain, [1, 0], **run)
    past = _dense.run_dense(chain, [1, 0], **run, deadline=-math.inf)
    monkeypatch.setattr(_budget, "ALLOWANCE", 0)
    cut = _dense.run_dense(chain, [1, 0], **run, deadline=-math.inf)

    assert len(whole.cdf) == 2_303 and past == whole  # ceil(ln 0.1 / ln 0.999) = 2,302 bins reach 0.9; a cheap run past the net ends exact
    assert len(cut.cdf) == 1 and cut.unresolved == pytest.approx(1.0) and cut.stopped == budget.TIME  # no allowance: stopped at once


def through_the_entry(coarse, monkeypatch, past: float = 600.0):  # noqa: F811
    target, prices, full = coarse
    clock = Ticking()
    monkeypatch.setattr(budget, "time", clock)
    real = _plan.plan_foresight

    def spent_by_the_plan(*args, **kwargs):
        # the plan took the whole net before the percentiles began (R17's site plan: 0 s left); the figures' moments still have the share of the
        # net past it that `budget.AFTER_NET` gives (#1553), and `past` beyond it leaves them none
        clock.now += past
        return real(*args, **kwargs)

    monkeypatch.setattr(_plan, "plan_foresight", spent_by_the_plan)
    settings = PlanSettings(recipe_starts=False, start_price=5.0, solver="packed", budget=Budget(seconds=600.0, memory_mb=None))
    plan = plan_target(COARSE, target, prices, settings)
    assert plan.mean_remaining == pytest.approx(full.mean_remaining, rel=1e-12)  # the plan stands (OR-34: the figures come after it)
    return plan, full


def test_through_the_entry_a_cheap_plan_whose_run_spent_its_net_still_gets_its_figures(coarse, monkeypatch):  # noqa: F811
    plan, full = through_the_entry(coarse, monkeypatch)
    alone = _plan.add_risk(full).risk  # the same plan's figures with no net

    assert (plan.risk.p50, plan.risk.p90, plan.risk.cvar) == (alone.p50, alone.p90, alone.cvar) and not plan.risk.grid.stopped


def test_through_the_entry_a_dear_plan_whose_run_spent_its_net_keeps_its_plan_and_says_its_figures_were_stopped(coarse, monkeypatch):  # noqa: F811
    monkeypatch.setattr(_budget, "ALLOWANCE", 0)  # as dear as R17's: nothing past the net
    plan, _ = through_the_entry(coarse, monkeypatch)

    risk = plan.risk
    said = _regen.figures_words(budget.TIME, 0.0, None, True)
    assert risk.grid.stopped == said and "the run's time limit" in said
    assert math.isinf(risk.p90.high) and not_shown(risk, risk.p90) == STOPPED_FIGURE
    (limit,) = [limit for limit in plan.limits if limit.kind == RISK and said in limit.why]
    assert "cheapest step" not in limit.why  # not the words of a grid too small to reach them


def test_through_the_entry_a_plan_whose_run_spent_its_net_and_its_share_past_it_gets_no_figures_and_says_so(coarse, monkeypatch):  # noqa: F811
    """#1553: the moments' solves keep the run's net plus `budget.AFTER_NET` of it (R17's took 850 s past a 1 h net). Past both, the figures are
    not computed, the mean given is the plan's own, and the run's stop is listed with the stages a limit stopped."""
    plan, full = through_the_entry(coarse, monkeypatch, past=10_000.0)
    risk = plan.risk
    assert risk.grid.stopped is not None and "5% of that limit past it" in risk.grid.stopped
    assert risk.mean.value == pytest.approx(full.mean_remaining, rel=1e-9) and math.isinf(risk.p50.value) and math.isinf(risk.p90.high)
    (stop,) = [limit for limit in plan.limits if limit.kind == _limits.BUDGET]
    assert any("cost figures were not worked out" in name for name in stop.names)


def test_a_stopped_plan_that_may_not_finish_says_its_stop_too(spent, monkeypatch):
    monkeypatch.setattr(_budget, "ALLOWANCE", 0)
    stuck = {"s": Action("try", 1.0, (Outcome("goal", 1), Outcome("s", 8), Outcome("dead", 1)))}  # "dead" has no action: the plan may not finish

    report = evaluate(stuck, "s", lambda state: state == "goal")

    assert report.success_probability.value < 1.0 and report.grid.stopped
    (said,) = [limit for limit in risk_limits(report) if limit.why == report.grid.stopped]
    assert said.what == "The work on the cost figures was stopped"
