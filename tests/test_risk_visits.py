"""`expected_total`: how often a fixed policy does something, donor runs included (ticket #221, ADR-0035).

The reference policy is that of `test_risk_inputs`: the main action `make` costs 2, ends with probability 1/4 and otherwise retries, and
every attempt first builds a donor, a run of its own whose action `donor` costs 3 per try and succeeds with probability 1/3. The attempts
number 4 on average, each builds one donor, and a donor run takes 3 tries: `make` is done 4 times, `donor` 12, and the mean cost 44 is
exactly 4 * 2 + 12 * 3.
"""

import math
import random

import pytest

from crafting_system.risk import Estimate, evaluate, expected_total
from crafting_system.solver import Action


def is_goal(state):
    return state == "goal" or state.endswith("done")


POLICY = {
    "S": Action("make", 2.0, (("goal", 1), ("S", 3)), extra_inputs=("D",)),
    "D": Action("donor", 3.0, (("donor_done", 1), ("D", 2))),
}


def count(label):
    return lambda action: 1.0 if action.label == label else 0.0


def test_the_uses_of_the_main_action_and_of_the_donor_run_are_counted_together():
    assert expected_total(POLICY, "S", is_goal, count("make")).value == pytest.approx(4.0, rel=1e-12)
    assert expected_total(POLICY, "S", is_goal, count("donor")).value == pytest.approx(12.0, rel=1e-12)
    assert expected_total(POLICY, "S", is_goal, lambda action: 1.0).value == pytest.approx(16.0, rel=1e-12)


def test_the_cost_as_the_weight_is_the_mean_cost_of_the_evaluation():
    mean = evaluate(POLICY, "S", is_goal).mean.value
    assert expected_total(POLICY, "S", is_goal, lambda action: action.cost).value == pytest.approx(mean, rel=1e-12)
    assert mean == pytest.approx(44.0)


def test_the_donor_runs_the_evaluation_counts_are_the_uses_of_the_action_that_builds_them():
    report = evaluate(POLICY, "S", is_goal)
    assert report.input_runs["D"].value == pytest.approx(expected_total(POLICY, "S", is_goal, count("make")).value, rel=1e-12)


def test_the_interval_holds_the_value_and_is_narrow():
    found = expected_total(POLICY, "S", is_goal, count("donor"))
    assert found.low <= 12.0 <= found.high
    assert found.high - found.low < 1e-8


def test_a_weight_is_a_number_not_below_zero():
    with pytest.raises(ValueError, match="not negative"):
        expected_total(POLICY, "S", is_goal, lambda action: -1.0)
    with pytest.raises(ValueError, match="not negative"):
        expected_total(POLICY, "S", is_goal, lambda action: math.nan)


def test_a_start_that_is_a_goal_does_nothing():
    assert expected_total(POLICY, "goal", is_goal, lambda action: 1.0) == Estimate(0.0, 0.0, 0.0)


def test_a_policy_that_cannot_finish_has_no_finite_count():
    stuck = {"S": Action("make", 2.0, (("S", 1),))}
    found = expected_total(stuck, "S", is_goal, lambda action: 1.0)
    assert math.isinf(found.value)
    missing = expected_total({}, "S", is_goal, lambda action: 1.0)
    assert math.isinf(missing.value)


def test_a_policy_without_inputs_counts_its_own_visits():
    loop = {"S": Action("try", 1.0, (("goal", 1), ("S", 4)))}  # ends with probability 1/5: five tries on average
    assert expected_total(loop, "S", is_goal, count("try")).value == pytest.approx(5.0, rel=1e-12)
    assert expected_total(loop, "S", is_goal, count("other")).value == 0.0


def test_the_counts_agree_with_a_simulation_of_the_nested_process():
    rng = random.Random(221)
    runs = []
    for _ in range(20_000):
        total = 0

        def walk(state):
            nonlocal total
            while not is_goal(state):
                action = POLICY[state]
                total += action.label == "donor"
                for need in action.extra_inputs:
                    walk(need)
                state = rng.choices([t for t, _ in action.outcomes], [w for _, w in action.outcomes])[0]

        walk("S")
        runs.append(total)
    mean = sum(runs) / len(runs)
    error = (sum((n - mean) ** 2 for n in runs) / (len(runs) - 1) / len(runs)) ** 0.5
    assert abs(expected_total(POLICY, "S", is_goal, count("donor")).value - mean) < 5 * error
