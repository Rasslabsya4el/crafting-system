"""Policies that do not always finish, and the edges of the input.

A stuck state (no policy entry) and a trapped class (a cycle with no way to a goal) both lose the
mass that reaches them. Then the success probability is below 1, the mean, variance and CVaR are
infinite, and a quantile is finite only below the success probability.
"""

import math
from fractions import Fraction

import pytest
from risk_support import decimal, geometric_policy, is_goal, path_pmf, pmf_quantile

from crafting_system.risk import evaluate
from crafting_system.solver import Action, TabularModel, solve


def with_dead_end():
    """From S: goal 3, retry 2, dead end 5 (no policy entry) of 10, cost 2 per try. p = 3/8."""
    return {"S": Action("try", 2.0, (("goal", 3), ("S", 2), ("dead", 5)))}


def test_mass_sent_to_a_stuck_state_lowers_the_success_probability():
    report = evaluate(with_dead_end(), "S", is_goal)

    assert report.success_probability.low <= 0.375 <= report.success_probability.high
    assert report.success_probability.high - report.success_probability.low <= 1e-9
    assert report.success_probability.value == report.success_probability.low
    assert report.grid.exact and report.grid.step == 2.0


def test_a_policy_that_can_fail_has_infinite_mean_variance_and_cvar():
    report = evaluate(with_dead_end(), "S", is_goal)

    for estimate in (report.mean, report.variance, report.cvar):
        assert tuple(estimate) == (math.inf, math.inf, math.inf)


def test_quantiles_are_finite_below_the_success_probability_and_infinite_above():
    # P(C <= 2k and success) = 0.375 (1 - 0.2**k): 0.3, 0.36, 0.372, 0.3744, ...
    report = evaluate(with_dead_end(), "S", is_goal, quantile_levels=(0.1, 0.35, 0.37, 0.374, 0.5, 0.9))

    assert report.quantiles[0.1].value == 2.0
    assert report.quantiles[0.35].value == 4.0
    assert report.quantiles[0.37].value == 6.0
    assert report.quantiles[0.374].value == 8.0
    assert tuple(report.quantiles[0.5]) == (math.inf, math.inf, math.inf)
    assert tuple(report.quantiles[0.9]) == (math.inf, math.inf, math.inf)


def test_a_trapped_cycle_that_never_reaches_a_goal_loses_its_mass():
    policy = {
        "S": Action("go", 1.0, (("goal", 1), ("T", 1), ("U", 2))),
        "T": Action("stay", 1.0, (("T", 1),)),
        "U": Action("swap", 1.0, (("V", 1),)),
        "V": Action("swap", 1.0, (("U", 1),)),
    }

    report = evaluate(policy, "S", is_goal)

    assert report.success_probability.low <= 0.25 <= report.success_probability.high
    assert report.success_probability.high - report.success_probability.low <= 1e-9
    assert math.isinf(report.mean.value)
    assert report.quantiles[0.5].value == math.inf
    assert report.quantiles[0.9].value == math.inf


def test_a_start_without_a_policy_entry_has_probability_zero_and_everything_infinite():
    report = evaluate({}, "S", is_goal)

    assert tuple(report.success_probability) == (0.0, 0.0, 0.0)
    for estimate in (report.mean, report.variance, report.cvar, report.p50, report.p90):
        assert tuple(estimate) == (math.inf, math.inf, math.inf)
    assert report.grid.bins == 0


def test_a_start_that_only_loops_to_itself_has_probability_zero():
    report = evaluate({"S": Action("stay", 1.0, (("S", 1),))}, "S", is_goal)

    assert tuple(report.success_probability) == (0.0, 0.0, 0.0)
    assert math.isinf(report.mean.value)


def test_a_start_that_is_a_goal_costs_nothing_even_if_the_policy_lists_it():
    report = evaluate({"goal": Action("never", 1.0, (("goal", 1),))}, "goal", is_goal)

    assert tuple(report.success_probability) == (1.0, 1.0, 1.0)
    for estimate in (report.mean, report.variance, report.cvar, report.p50, report.p90):
        assert tuple(estimate) == (0.0, 0.0, 0.0)
    assert report.grid.exact and report.grid.bins == 0 and report.grid.unresolved_mass == 0.0


def test_a_goal_in_the_middle_absorbs_even_if_the_policy_lists_it():
    policy = {
        "S": Action("go", 1.0, (("goal", 1),)),
        "goal": Action("leave", 1.0, (("elsewhere", 1),)),
    }

    report = evaluate(policy, "S", is_goal)

    assert tuple(report.success_probability) == (1.0, 1.0, 1.0)
    assert report.mean.value == pytest.approx(1.0, rel=1e-12)
    assert report.p90.value == 1.0


def test_a_solver_policy_that_omits_infinite_valued_states_is_proper():
    model = TabularModel(
        ["goal"],
        {
            "S": [
                Action("safe", 5.0, (("goal", 1), ("S", 1))),
                Action("risky", 1.0, (("goal", 1), ("trap", 1))),
            ],
            "trap": [],
        },
    )
    solution = solve(model, ["S"])
    assert math.isinf(solution.values["trap"]) and "trap" not in solution.policy

    report = evaluate(solution.policy, "S", is_goal)

    assert tuple(report.success_probability) == (1.0, 1.0, 1.0)
    assert report.mean.low <= solution.values["S"] <= report.mean.high
    assert report.mean.value == pytest.approx(10.0, rel=1e-12)


def test_a_small_max_bins_reports_what_is_unresolved_instead_of_a_wrong_number():
    # p = 0.01, cost 1: the 90th percentile is 230, far beyond 10 bins
    report = evaluate(geometric_policy(1, 99, 1.0), "S", is_goal, max_bins=10)

    assert report.grid.bins == 10
    assert report.grid.unresolved_mass == pytest.approx(0.99**10, rel=1e-9)
    assert report.p90.high == math.inf and report.p90.value == math.inf
    assert 10.0 <= report.p90.low <= 230.0
    assert report.cvar.high == math.inf
    assert report.mean.value == pytest.approx(100.0, rel=1e-9)  # the solver's moments do not need the DP


def test_truncation_of_a_policy_that_can_fail_still_brackets_the_success_probability():
    report = evaluate(with_dead_end(), "S", is_goal, max_bins=2)

    assert report.success_probability.low < 0.375 < report.success_probability.high
    assert report.grid.unresolved_mass > 0.0


def test_a_policy_that_can_fail_with_generic_float_costs_still_brackets_the_success_probability():
    # costs with no small common unit: a unit of about 2e-12 would leave 200k bins covering nothing
    policy = {
        "S": Action("a", 1.1453657190815998, (("G", 5), ("T", 3), ("X", 2))),
        "T": Action("b", 1.105801955159868, (("G", 3), ("S", 2))),
    }
    truth = Fraction(17, 22)  # p_S = 1/2 + 3/10 p_T and p_T = 3/5 + 2/5 p_S

    report = evaluate(policy, "S", lambda state: state == "G")

    success = report.success_probability
    assert success.low <= truth <= success.high
    assert success.high - success.low < 1e-3
    assert report.grid.step > 1e-3


@pytest.mark.parametrize("cost", [1e200, 1e-200])
def test_costs_outside_the_supported_range_are_rejected_with_the_reason(cost):
    with pytest.raises(ValueError, match="supported range"):
        evaluate(geometric_policy(1, 1, cost), "S", is_goal)


def test_costs_outside_the_supported_range_are_rejected_for_a_policy_that_can_fail_too():
    with pytest.raises(ValueError, match="supported range"):
        evaluate(with_dead_end() | {"S": Action("t", 1e200, (("goal", 1), ("dead", 1)))}, "S", is_goal)


@pytest.mark.parametrize("resolution", [5e-324, 1e-320])
def test_a_resolution_so_small_that_costs_overflow_the_grid_is_a_value_error(resolution):
    with pytest.raises(ValueError, match="resolution"):
        evaluate(geometric_policy(1, 1, 1.0), "S", is_goal, resolution=resolution)


def test_a_policy_that_can_fail_with_irrational_costs_gets_a_fine_default_grid():
    # S pays sqrt 2: goal 2, T 2, dead end 1 (of 5); T pays sqrt 5: goal 1, dead end 1. p = 3/5.
    policy = {
        "S": Action("s", math.sqrt(2), (("goal", 2), ("T", 2), ("dead", 1))),
        "T": Action("t", math.sqrt(5), (("goal", 1), ("dead", 1))),
    }
    pmf = path_pmf(policy, "S")

    report = evaluate(policy, "S", is_goal, quantile_levels=(0.2, 0.5, 0.7))

    assert sum(pmf.values()) == Fraction(3, 5)
    assert report.success_probability.low - 1e-12 <= 0.6 <= report.success_probability.high + 1e-12
    assert report.success_probability.high - report.success_probability.low <= 1e-9
    assert not report.grid.exact
    for level in (0.2, 0.5):
        truth = float(pmf_quantile(pmf, decimal(level)))
        estimate = report.quantiles[level]
        assert estimate.low - 1e-12 <= truth <= estimate.high + 1e-12
        assert estimate.high - estimate.low < 0.03 * truth
    assert tuple(report.quantiles[0.7]) == (math.inf, math.inf, math.inf)
