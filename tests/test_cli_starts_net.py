"""The time net of a run is one for the whole run, not one for each start option (ticket #626, OR-12): `plan_with_starts` cuts the net each option gets to what the ones before left.

The clock is a fake one, set by hand: a test of the real planner does not read the time (tests/test_no_timing.py).
"""

from test_vendor_starts import TOY, bought_boots, prices, toy_target, vendor_recipe_starts  # the toy world of the start options

from crafting_system.cli import StartList, _starts, plan_with_starts
from crafting_system.cli._envelope import Net
from crafting_system.cli._starts import _deadline, _net_left


class Clock:
    """A clock that only moves when the test says so (`_starts.time` is replaced by it)."""

    def __init__(self) -> None:
        self.now = 1000.0

    def perf_counter(self) -> float:
        return self.now


def test_the_time_net_is_one_for_the_whole_run_not_one_for_each_start_option(monkeypatch):
    """`plan_with_starts` plans each start option with the net it was given; the time of the net is shared, so the options together stop at the net."""
    clock = Clock()
    monkeypatch.setattr(_starts, "time", clock)
    seen = []
    real = _starts.make_plan

    def spending(*args, **kwargs):
        net = kwargs.get("net")
        seen.append(None if net is None else net.seconds)
        clock.now += 20.0  # planning an option takes 20 seconds
        return real(*args, **{**kwargs, "net": None})

    monkeypatch.setattr(_starts, "make_plan", spending)
    plan_with_starts(TOY, toy_target(), prices(), sources=(vendor_recipe_starts, lambda context: StartList((bought_boots(5.0),))), net=Net(seconds=100.0))
    assert seen == [100.0, 80.0, 60.0]  # the plain option, the bought boots, the recipe: each gets what the ones before it left


def test_an_option_planned_after_the_time_is_spent_gets_a_net_of_zero_seconds(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(_starts, "time", clock)
    net = Net(seconds=10.0, states=5)
    deadline = _deadline(net)
    assert deadline == 1010.0
    assert _net_left(net, deadline)["net"] == Net(seconds=10.0, states=5)
    clock.now = 1004.0
    assert _net_left(net, deadline)["net"] == Net(seconds=6.0, states=5)  # the other limits go on unchanged
    clock.now = 1100.0
    assert _net_left(net, deadline)["net"].seconds == 0.0


def test_a_run_without_a_time_net_passes_it_on_as_it_is():
    assert _deadline(None) is None and _deadline(Net(states=10)) is None
    assert _net_left(None, None) == {}
    net = Net(states=10, memory_mb=1.0)
    assert _net_left(net, None) == {"net": net}
