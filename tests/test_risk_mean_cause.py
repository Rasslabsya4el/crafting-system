"""Ticket #512 (M7, rebuild step 5): a policy with no finite mean says why, in every reader of the infinite value.

`evaluate` puts the cause in `GridInfo.cause` (#506); `policy_mean` and `expected_total`, the readers of the interval driver, carry it with
the infinite `Estimate` they return, and the text report and the route page say the same sentence for it.
"""

import math

import pytest

from crafting_system.risk import SUBCRITICAL, Estimate, expected_total, expected_totals
from crafting_system.risk._mean import policy_mean
from crafting_system.risk._report import STUCK, UNDECIDED
from crafting_system.solver import Action


def is_goal(state):
    return state == "goal" or state.endswith("done")


def supercritical():
    """Every state can finish, but an attempt at A needs two runs of B and half of them come back to A: more runs start than finish."""
    return {
        "A": Action("a", 1.0, (("goal", 1), ("A", 1)), extra_inputs=("B", "B")),
        "B": Action("b", 1.0, (("donor_done", 1), ("A", 1))),
    }


def one_donor():
    return {
        "S": Action("make", 2.0, (("goal", 1), ("S", 3)), extra_inputs=("D",)),
        "D": Action("donor", 3.0, (("donor_done", 1), ("D", 2))),
    }


STUCK_POLICY = {"S": Action("make", 2.0, (("S", 1),))}


def test_policy_mean_of_a_policy_that_starts_more_runs_than_it_finishes_says_subcritical():
    found = policy_mean(supercritical(), "A", is_goal)

    assert math.isinf(found.value) and math.isinf(found.low) and math.isinf(found.high)
    assert found.cause == SUBCRITICAL


def test_policy_mean_of_a_policy_that_cannot_finish_says_stuck():
    assert policy_mean(STUCK_POLICY, "S", is_goal).cause == STUCK
    assert policy_mean({}, "S", is_goal).cause == STUCK


def test_policy_mean_of_an_ordinary_policy_is_finite_and_has_no_cause():
    found = policy_mean(one_donor(), "S", is_goal)

    assert found.value == pytest.approx(4 * (2 + 9), rel=1e-12)  # 4 attempts, each 2 Chaos and one donor of 3 runs at 3 Chaos
    assert found.cause == ""
    assert found.estimate == Estimate(found.value, found.low, found.high)


def test_expected_total_of_a_policy_that_starts_more_runs_than_it_finishes_says_subcritical():
    found = expected_total(supercritical(), "A", is_goal, lambda action: 1.0)

    assert math.isinf(found.value)
    assert found.cause == SUBCRITICAL


def test_expected_total_of_a_policy_that_cannot_finish_says_stuck_and_an_ordinary_one_has_no_cause():
    assert expected_total(STUCK_POLICY, "S", is_goal, lambda action: 1.0).cause == STUCK
    ordinary = expected_total(one_donor(), "S", is_goal, lambda action: 1.0)
    assert ordinary.value == pytest.approx(16.0, rel=1e-12) and ordinary.cause == ""


def test_expected_totals_carry_the_cause_for_every_weight():
    found = expected_totals(supercritical(), "A", is_goal, [lambda action: 1.0, lambda action: action.cost])

    assert [each.cause for each in found] == [SUBCRITICAL, SUBCRITICAL]


def test_an_undecided_solve_is_said_apart_from_a_subcritical_policy(monkeypatch):
    from crafting_system.risk import _inputs

    def undecided(chain, costs):
        raise _inputs.Undecided("the residual is as large as the costs")

    monkeypatch.setattr(_inputs, "solve_costs", undecided)

    assert policy_mean(one_donor(), "S", is_goal).cause == UNDECIDED
    assert expected_total(one_donor(), "S", is_goal, lambda action: 1.0).cause == UNDECIDED
