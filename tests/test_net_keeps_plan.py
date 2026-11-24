"""A run its net stops keeps the plan it priced inside the net (#1566, OR-13, OR-33, OR-40), through the planner's entry, on the clock.

The fixture belt of `test_planner_blocking_crafts` with the plan-led growth on (`_growth`, #1414): its seed round prices a plan of
`16e/3 + 2S` (153.33 c: Exalted Orbs until the Life prefix) at once. The clock is the run's own (`time.perf_counter`, which the budget, the
search and the rounds all read), moved forward by hand: what took R17 an hour takes the belt a millisecond, so the hour is added where R17
spent it.

* **A plan, then the net.** The search tells its watcher of its first plan (`Standing`), and the clock then jumps past the 1,000 s net, as
  R17's round went on for 17 minutes past its net after pricing its plan at minute 51. The growth's reading of its next round asks the net
  (R17's met it in the bounds of its lock group, `abstraction._bound`); here every reading asks it first. Before #1566 that stop went up
  through the rounds and the answer was "no plan found yet". Now the answer is the plan, and its limits list the run's stop.
* **No plan, then the net.** The clock jumps past the net before the first round's search: no plan was priced, and the answer still says
  "no plan found yet" (OR-33).
"""

import pytest
from test_planner_blocking_crafts import E, S, _prices, data, target  # noqa: F401  (the belt world and its fixtures)

from crafting_system import budget
from crafting_system.budget import NO_PLAN, Budget
from crafting_system.planner import PlanError, PlanSettings, _growth, _offers, plan_target
from crafting_system.planner import _plan as planner_plan
from crafting_system.planner._limits import BUDGET

NET = 1000.0  # the run's time net, in seconds
PAST = 2 * NET  # how far the clock jumps: well past the net and past the share the pricing at a stop may take beyond it (`LAST_PRICING`)


@pytest.fixture
def clock(monkeypatch):
    """The run's clock, which a test moves forward by setting `clock[0]`; the growth's reading of its next round asks the run's net first."""
    clock_module = budget.time  # the module every reader of the run's clock reads (no `import time` here: test_no_timing)
    real = clock_module.perf_counter
    shift = [0.0]
    monkeypatch.setattr(clock_module, "perf_counter", lambda: real() + shift[0])
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    for name in ("next", "stop"):
        inner = getattr(_growth.Grower, name)
        monkeypatch.setattr(_growth.Grower, name, lambda self, inner=inner: (budget.checkpoint(), inner(self))[1])
    return shift


def _settings(watch=None) -> PlanSettings:
    return PlanSettings(recipe_starts=False, start_price=S, solver="envelope", budget=Budget(seconds=NET), watch=watch)


def test_a_plan_priced_before_the_net_is_the_answer_and_the_answer_says_the_net_stopped_the_run(data, target, clock):  # noqa: F811
    priced = []

    def watch(standing):
        priced.append(standing.upper)
        clock[0] = PAST  # the round goes on past the net after its first plan

    plan = plan_target(data, target, _prices(), _settings(watch))
    assert priced and plan.mean_remaining == pytest.approx(16 * E / 3 + 2 * S, rel=1e-9) == pytest.approx(priced[0], rel=1e-9)
    stops = [limit for limit in plan.limits if limit.kind == BUDGET]
    assert len(stops) == 1 and any(f"time limit of {NET:,.0f} s" in name and "kept" in name for name in stops[0].names)
    assert not any(NO_PLAN in name for name in stops[0].names)


def test_a_run_its_net_stops_before_any_plan_still_says_no_plan_found_yet(data, target, clock, monkeypatch):  # noqa: F811
    inner = planner_plan._make_plan

    def make(*args, **kwargs):
        if kwargs.get("round_call") is not None:
            clock[0] = PAST  # the net is spent before the round's search prices anything
        return inner(*args, **kwargs)

    monkeypatch.setattr(planner_plan, "_make_plan", make)
    with pytest.raises(PlanError, match=NO_PLAN):
        plan_target(data, target, _prices(), _settings())
