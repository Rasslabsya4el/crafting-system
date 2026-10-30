"""Closed-form checks of `risk.evaluate` on a loop that ends in the goal with a fixed chance each try.

State `S` has one action of cost c: goal with weight a, back to `S` with weight b, so p = a/(a+b)
and the total cost is c times a geometric count. Every closed form is in `risk_support`. The
tolerance for the solver-backed moments is 1e-9 relative (the solver certifies about 1e-15); the
grid quantities are exact up to 1e-12 relative cost rounding and must match to 1e-9.
"""

import math
from fractions import Fraction

import pytest
from risk_support import (
    decimal,
    geometric_cvar,
    geometric_moments,
    geometric_policy,
    geometric_quantile_steps,
    is_goal,
)

from crafting_system.risk import evaluate

CASES = [
    pytest.param(1, 1, 1.0, id="p=1/2,c=1"),
    pytest.param(1, 3, 0.7, id="p=1/4,c=0.7"),
    pytest.param(1, 99, 2.5, id="p=0.01,c=2.5"),
    pytest.param(9, 1, 0.1, id="p=0.9,c=0.1"),
    pytest.param(3, 7, 4.0, id="p=0.3,c=4"),
    pytest.param(1, 999, 0.25, id="p=0.001,c=0.25"),
]


def close(estimate, truth, rel=1e-9):
    return estimate.low - rel * abs(truth) <= truth <= estimate.high + rel * abs(truth)


@pytest.mark.parametrize(("a", "b", "cost"), CASES)
def test_success_is_exactly_one_when_the_goal_is_always_reachable(a, b, cost):
    report = evaluate(geometric_policy(a, b, cost), "S", is_goal)

    assert tuple(report.success_probability) == (1.0, 1.0, 1.0)


@pytest.mark.parametrize(("a", "b", "cost"), CASES)
def test_mean_and_variance_match_the_closed_form(a, b, cost):
    p = Fraction(a, a + b)
    mean, variance = geometric_moments(p, Fraction(cost))

    report = evaluate(geometric_policy(a, b, cost), "S", is_goal)

    assert close(report.mean, float(mean))
    assert report.mean.value == pytest.approx(float(mean), rel=1e-9)
    assert close(report.variance, float(variance))
    assert report.variance.value == pytest.approx(float(variance), rel=1e-7)


LEVELS = (0.1, 0.5, 0.9, 0.99)


@pytest.mark.parametrize(("a", "b", "cost"), CASES)
def test_quantiles_are_the_closed_form_grid_points(a, b, cost):
    p = Fraction(a, a + b)

    report = evaluate(geometric_policy(a, b, cost), "S", is_goal, quantile_levels=LEVELS)

    assert report.grid.exact
    for level in LEVELS:
        truth = float(Fraction(cost) * geometric_quantile_steps(p, decimal(level)))
        estimate = report.quantiles[level]
        assert estimate.low == pytest.approx(truth, rel=1e-9)
        assert estimate.high == pytest.approx(truth, rel=1e-9)
        assert estimate.value == pytest.approx(truth, rel=1e-9)


def test_the_median_of_a_fair_coin_loop_is_the_tie_and_p50_p90_are_the_default_levels():
    report = evaluate(geometric_policy(1, 1, 1.0), "S", is_goal)

    assert report.p50.value == 1.0  # P(C <= 1) is exactly one half
    assert report.p90 is report.quantiles[0.9]
    assert report.p90.value == 4.0  # 1 - 2**-3 = 0.875 < 0.9 <= 1 - 2**-4 = 0.9375


@pytest.mark.parametrize(("a", "b", "cost"), CASES)
def test_cvar_matches_the_closed_form(a, b, cost):
    p = Fraction(a, a + b)

    report = evaluate(geometric_policy(a, b, cost), "S", is_goal, cvar_level=0.9)

    truth = float(geometric_cvar(p, Fraction(cost), decimal(0.9)))
    assert report.cvar_level == 0.9
    assert close(report.cvar, truth)
    assert report.cvar.value == pytest.approx(truth, rel=1e-8)


def test_a_level_too_close_to_one_to_certify_has_no_upper_bound_even_on_an_exact_grid():
    # the truth at level 1 - 1e-12 is 40 tries; a point answer 33 would be wrong
    report = evaluate(geometric_policy(1, 1, 1.0), "S", is_goal, quantile_levels=(0.999999999999,))

    estimate = report.quantiles[0.999999999999]
    assert report.grid.exact
    assert estimate.high == math.inf and estimate.value == math.inf
    assert 0.0 < estimate.low <= 40.0


def test_a_level_too_close_to_zero_to_certify_has_a_zero_low_end_and_no_point_claim():
    report = evaluate(geometric_policy(1, 1, 1.0), "S", is_goal, quantile_levels=(1e-13,))

    estimate = report.quantiles[1e-13]
    assert estimate.low == 0.0
    assert estimate.high == 1.0  # the truth: the first try already has chance 1/2
    assert estimate.low <= estimate.value <= estimate.high
    assert estimate.value != estimate.high
