"""How a run ends and what it pays: goal, stop, step limit, start cost, seeds (ADR-0019, ticket 25).

Fake actions on fixture amulets, so the runs are cheap. Exact claims are asserted exactly. The
statistical ones state their tolerance at five standard errors so a correct result fails about once
in 1.7 million runs (the seeds are fixed, so a run is repeatable):

* a policy that stops at the second state of a coin chain: the success rate lies in the Wilson interval
  made at five sigma around 1/2, and the mean cost (all runs, and the successful ones) is within 5
  standard errors of its closed form, 2 steps of cost 2.
"""

import dataclasses
import math

import pytest
from simulator_support import DATA, FIVE_SIGMA, ITEMS, chain_policy, holds_target

from crafting_system.simulator import SimulationReport, Step, simulate

LADDER = {  # S -> T -> dead -> goal, one certain step each, cost 1.0 per step ("dead" is only a name here)
    "S": (1.0, (("T", 1),)),
    "T": (1.0, (("dead", 1),)),
    "dead": (1.0, (("goal", 1),)),
}
COIN = {"S": (2.0, (("goal", 1), ("T", 1), ("S", 2)))}  # no policy for T: the policy stops there
STUCK = {"S": (2.0, (("S", 1),))}  # an action that never changes the item
REPEAT = {"S": (2.5, (("goal", 1), ("S", 4)))}


def run(chain, *, start="S", runs=200, seed=7, **extra):
    return simulate(DATA, chain_policy(chain), ITEMS[start], holds_target, runs=runs, seed=seed, **extra)


def test_a_start_item_that_is_a_goal_takes_no_step_and_costs_the_start_cost():
    def never(item):
        raise AssertionError("the policy was asked about a goal item")

    report = simulate(DATA, never, ITEMS["goal"], holds_target, runs=10, seed=1, start_cost=7.5)

    assert (report.runs, report.successes, report.stopped, report.unfinished) == (10, 10, 0, 0)
    assert report.costs == (7.5,) * 10
    assert report.mean_steps == 0.0
    assert report.cost.value == 7.5 and report.cost.standard_error == 0.0
    assert report.cost_of_successes == report.cost


def test_the_policy_is_never_asked_about_a_goal_item():
    asked = []
    inner = chain_policy(REPEAT)

    def policy(item):
        asked.append(item)
        return inner(item)

    run_report = simulate(DATA, policy, ITEMS["S"], holds_target, runs=200, seed=3)

    assert run_report.successes == 200
    assert asked and not any(holds_target(item) for item in asked)
    assert len(asked) == sum(round(total / 2.5) for total in run_report.costs)


def test_a_run_that_needs_exactly_max_steps_steps_succeeds():
    report = run(LADDER, runs=5, max_steps=3)

    assert report.successes == 5 and report.unfinished == 0
    assert report.costs == (3.0,) * 5 and report.mean_steps == 3.0


def test_a_run_one_step_short_of_the_goal_is_unfinished_and_pays_for_its_steps():
    report = run(LADDER, runs=5, max_steps=2, start_cost=10.0)

    assert (report.successes, report.stopped, report.unfinished) == (0, 0, 5)
    assert report.costs == (12.0,) * 5 and report.mean_steps == 2.0
    assert report.cost_of_successes is None
    assert report.success_rate.value == 0.0 and report.success_rate.low == 0.0


def test_a_step_that_changes_nothing_is_still_paid_every_time():
    report = run(STUCK, runs=20, max_steps=7)

    assert report.unfinished == 20 and report.mean_steps == 7.0
    assert report.costs == (14.0,) * 20
    assert report.cost.value == 14.0 and report.cost.standard_error == 0.0


def test_the_default_step_limit_is_one_hundred_thousand():
    report = run(STUCK, runs=2)

    assert report.unfinished == 2 and report.mean_steps == 100_000


def test_a_policy_that_stops_counts_the_stopped_runs_and_pays_for_them():
    report = run(COIN, runs=20_000, seed=11, confidence=FIVE_SIGMA)

    assert report.successes + report.stopped == 20_000 and report.unfinished == 0
    assert 0 < report.stopped < 20_000
    assert report.success_rate.contains(0.5)
    assert report.cost.agrees_with(4.0)
    assert report.cost_of_successes.agrees_with(4.0)
    assert math.isclose(report.mean_steps, report.cost.value / 2.0, rel_tol=1e-12)


def test_the_start_cost_is_added_to_every_run_and_nothing_else_changes():
    plain = run(REPEAT, runs=100, seed=5)
    shifted = run(REPEAT, runs=100, seed=5, start_cost=100.0)

    assert shifted.mean_steps == plain.mean_steps
    assert shifted.successes == plain.successes
    assert shifted.costs == pytest.approx(tuple(total + 100.0 for total in plain.costs), rel=1e-12)
    assert shifted.cost.value == pytest.approx(plain.cost.value + 100.0)
    assert shifted.cost.standard_error == pytest.approx(plain.cost.standard_error)


def test_the_same_seed_gives_the_same_report():
    assert run(REPEAT, runs=300, seed=9) == run(REPEAT, runs=300, seed=9)


def test_another_seed_gives_another_report():
    assert run(REPEAT, runs=300, seed=9).costs != run(REPEAT, runs=300, seed=10).costs


def test_one_generator_serves_all_runs_in_order():
    """The first runs of a longer experiment are the runs of a shorter one with the same seed."""
    short, long = run(REPEAT, runs=40, seed=12), run(REPEAT, runs=400, seed=12)

    assert long.costs[:40] == short.costs


def test_the_quantile_of_a_report_is_read_from_its_run_costs():
    report = run(REPEAT, runs=1_000, seed=13)

    assert report.quantile(0.5).value == sorted(report.costs)[499]


def test_a_wider_confidence_widens_every_interval_and_moves_no_value():
    narrow, wide = run(REPEAT, runs=2_000, seed=14, confidence=0.8), run(REPEAT, runs=2_000, seed=14, confidence=0.99)

    assert narrow.costs == wide.costs and narrow.cost.value == wide.cost.value
    assert wide.cost.low < narrow.cost.low and wide.cost.high > narrow.cost.high
    assert wide.success_rate.low < narrow.success_rate.low
    assert wide.quantile(0.9).low <= narrow.quantile(0.9).low
    assert wide.quantile(0.9).high >= narrow.quantile(0.9).high
    assert narrow.confidence == 0.8 and wide.confidence == 0.99


def test_a_report_is_immutable():
    report = run(REPEAT, runs=10)

    assert isinstance(report, SimulationReport)
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.runs = 3


def test_a_free_step_is_allowed():
    report = run({"S": (0.0, (("goal", 1),))}, runs=5)

    assert report.costs == (0.0,) * 5 and report.mean_steps == 1.0


def test_an_error_of_the_policy_propagates():
    def broken(item):
        raise KeyError("no step for this item")

    with pytest.raises(KeyError):
        simulate(DATA, broken, ITEMS["S"], holds_target, runs=2, seed=1)


def test_the_action_of_each_step_is_used_with_the_cost_of_that_step():
    """Two different actions priced differently: the total is the sum of what each step costs."""
    first = chain_policy({"S": (1.0, (("T", 1),))})(ITEMS["S"])
    second = chain_policy({"T": (4.0, (("goal", 1),))})(ITEMS["T"])
    steps = {ITEMS["S"]: first, ITEMS["T"]: second}

    report = simulate(DATA, steps.get, ITEMS["S"], holds_target, runs=3, seed=1)

    assert report.costs == (5.0,) * 3 and isinstance(first, Step)
