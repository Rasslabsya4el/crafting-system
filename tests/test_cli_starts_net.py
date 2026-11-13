"""The time net of a run is one for the whole run, not one for each start option (tickets #626, #825; OR-12): the start options share the run's clock.

The clock is a fake one, set by hand: a test of the real planner does not read the time (tests/test_no_timing.py).
"""

from test_vendor_starts import TOY, bought_boots, prices, toy_target, vendor_recipe_starts  # the toy world of the start options

from crafting_system import budget
from crafting_system.cli import StartList, plan_with_starts
from crafting_system.planner import _starts
from crafting_system.planner._envelope import Net


class Clock:
    """A clock that only moves when the test says so (`budget.time` is replaced by it)."""

    def __init__(self) -> None:
        self.now = 1000.0

    def perf_counter(self) -> float:
        return self.now


def spending(monkeypatch, clock: Clock, seen: list) -> None:
    """Planning an option takes 20 seconds; `seen` gets the time the run's clock had left when the option began."""
    real = _starts.make_plan

    def plan(*args, **kwargs):
        seen.append(budget.active().left() if budget.active() is not None else None)
        clock.now += 20.0
        return real(*args, **kwargs)

    monkeypatch.setattr(_starts, "make_plan", plan)


def test_the_time_net_is_one_for_the_whole_run_not_one_for_each_start_option(monkeypatch):
    """`plan_with_starts` plans each start option on the run's one clock, so the options together stop at the net."""
    clock = Clock()
    monkeypatch.setattr(budget, "time", clock)
    seen: list = []
    spending(monkeypatch, clock, seen)
    plan_with_starts(
        TOY, toy_target(), prices(), sources=(vendor_recipe_starts, lambda context: StartList((bought_boots(5.0),))),
        budget=budget.Budget(seconds=100.0, memory_mb=None),
    )  # fmt: skip
    assert seen == [100.0, 80.0, 60.0]  # the plain option, the bought boots, the recipe: each gets what the ones before it left


def test_the_older_net_argument_is_the_same_one_clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(budget, "time", clock)
    seen: list = []
    spending(monkeypatch, clock, seen)
    plan_with_starts(TOY, toy_target(), prices(), sources=(vendor_recipe_starts, lambda context: StartList((bought_boots(5.0),))), net=Net(seconds=100.0))
    assert seen == [100.0, 80.0, 60.0]


def test_a_run_without_a_net_has_no_clock(monkeypatch):
    seen: list = []
    spending(monkeypatch, Clock(), seen)
    plan_with_starts(TOY, toy_target(), prices(), sources=(vendor_recipe_starts, lambda context: StartList((bought_boots(5.0),))))
    assert seen and all(left is None for left in seen)
