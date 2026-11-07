"""The time net of a run is one for the whole run, not one for each start option (ticket #626, OR-12): `plan_with_starts` cuts the net each option gets to what the ones before left."""

import time

from test_vendor_starts import TOY, bought_boots, prices, toy_target, vendor_recipe_starts  # the toy world of the start options

from crafting_system.cli import _starts
from crafting_system.cli._envelope import Net
from crafting_system.cli import StartList
from crafting_system.cli._starts import _deadline, _with_time_left, plan_with_starts


def test_the_time_net_is_one_for_the_whole_run_not_one_for_each_start_option(monkeypatch):
    """`plan_with_starts` plans each start option with the net it was given; the time of the net is shared, so the options together stop at the net."""
    seen = []
    real = _starts.make_plan

    def spending(*args, **kwargs):
        net = kwargs.get("net")
        seen.append(None if net is None else net.seconds)
        time.sleep(0.2)
        return real(*args, **{**kwargs, "net": None})

    monkeypatch.setattr(_starts, "make_plan", spending)
    plan_with_starts(TOY, toy_target(), prices(), sources=(vendor_recipe_starts, lambda context: StartList((bought_boots(5.0),))), net=Net(seconds=100.0))
    assert len(seen) == 3 and all(seconds is not None and seconds <= 100.0 for seconds in seen)
    assert all(later < earlier for earlier, later in zip(seen, seen[1:]))  # each option gets what the ones before it left
    assert seen[0] - seen[-1] >= 0.2 * (len(seen) - 1) * 0.9


def test_a_run_without_a_time_net_passes_none_on(monkeypatch):
    assert _deadline({}) is None and _deadline({"net": Net(states=10)}) is None
    kwargs = {"net": Net(states=10)}
    assert _with_time_left(kwargs, None) is kwargs
