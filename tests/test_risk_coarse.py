"""The coarse grid (ticket #190): quantiles and CVaR of a policy whose cheapest action is far below its cost scale.

The ordinary grid needs a step at most the cheapest action, so `max_bins` bins cover `max_bins` times that
cost. A policy that pays a cheap orb once per craft, spams a dearer one and restarts has a p90 far beyond
that. The oracles are the same policies on their own exact unit grid, run with a `max_bins` that covers them,
and a closed form.
"""

import math

import pytest
from risk_support import is_goal

from crafting_system.risk import _coarse, evaluate
from crafting_system.solver import Action

LEVELS = (0.5, 0.9)


def craft(orb=0.01, spam=0.1, restart=1.0):
    """A cheap orb, a spam that ends in the goal or a failure in one use of 20 each, and a restart."""
    return {
        "S": Action("orb", orb, (("A", 1),)),
        "A": Action("spam", spam, (("goal", 1), ("A", 18), ("B", 1))),
        "B": Action("restart", restart, (("S", 1),)),
    }


def restart_after_a_cheap_step(cheap=0.001):
    """A restart costing 1 that succeeds one time in four; a failure pays a cheap step first.

    The cost is N + (N - 1) cheap with N geometric (1/4): P(C <= N + (N - 1) cheap) = 1 - 0.75^N.
    """
    return {
        "R": Action("restart", 1.0, (("goal", 1), ("L", 3))),
        "L": Action("cheap", cheap, (("R", 1),)),
    }


def contains(estimate, truth):
    slack = 1e-9 * abs(truth)
    return estimate.low - slack <= truth <= estimate.high + slack


@pytest.mark.parametrize("coarse_bins", [400, 2000])
def test_the_bracket_contains_the_exact_quantiles_and_cvar_of_the_unit_grid(coarse_bins):
    policy = craft()
    exact = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, resolution=0.01, max_bins=20_000)

    report = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, max_bins=20, max_coarse_bins=coarse_bins)

    assert report.grid.step > 0.01 and not report.grid.exact
    assert report.mean.value == pytest.approx(exact.mean.value, rel=1e-9)
    for level in LEVELS:
        assert math.isfinite(report.quantiles[level].high)
        assert contains(report.quantiles[level], exact.quantiles[level].value)
    assert contains(report.cvar, exact.cvar.value)
    assert report.success_probability.value == 1.0


def test_a_finer_coarse_grid_gives_a_narrower_bracket():
    policy = craft()

    wide = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, max_bins=20, max_coarse_bins=400)
    narrow = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, max_bins=20, max_coarse_bins=2000)

    assert narrow.grid.step < wide.grid.step
    for level in LEVELS:
        assert narrow.quantiles[level].high - narrow.quantiles[level].low < 0.05 * narrow.quantiles[level].value
        assert narrow.quantiles[level].high - narrow.quantiles[level].low <= wide.quantiles[level].high - wide.quantiles[level].low


def test_a_very_cheap_step_next_to_an_expensive_restart_matches_the_closed_form():
    policy = restart_after_a_cheap_step()

    report = evaluate(policy, "R", is_goal, quantile_levels=LEVELS, max_bins=1_000, max_coarse_bins=5_000)

    assert report.grid.step > 0.001
    p50 = 3 + 2 * 0.001  # 1 - 0.75^3 = 0.578 >= 0.5 > 1 - 0.75^2
    p90 = 9 + 8 * 0.001  # 1 - 0.75^9 = 0.925 >= 0.9 > 1 - 0.75^8 = 0.8999
    assert contains(report.p50, p50) and contains(report.p90, p90)
    assert report.p90.high - report.p90.low < 0.05 * p90
    assert report.mean.value == pytest.approx(4 + 3 * 0.001, rel=1e-9)  # E[N] = 4 and 3 failures on average
    cvar = report.cvar
    assert math.isfinite(cvar.value) and cvar.low <= cvar.value <= cvar.high


def test_the_ordinary_grid_is_kept_when_it_covers_the_level():
    policy = craft()

    plain = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, max_bins=20_000)

    assert not _coarse.beyond_ordinary_grid(plain.mean.value, plain.variance.value, 0.9, 0.01, 20_000)
    assert plain.grid.step == pytest.approx(0.01)
    assert plain.grid.exact


def test_a_policy_with_one_cost_has_no_step_that_reaches_the_level_and_keeps_the_ordinary_answer():
    policy = {"S": Action("use", 0.001, (("goal", 1), ("S", 999_999)))}

    report = evaluate(policy, "S", is_goal, max_bins=1_000, max_coarse_bins=100_000)

    assert math.isinf(report.p90.value)
    assert report.grid.step == pytest.approx(0.001)


def test_a_chain_beyond_the_dense_limit_keeps_the_ordinary_answer(monkeypatch):
    monkeypatch.setattr(_coarse, "DENSE_STATES", 2)

    report = evaluate(craft(), "S", is_goal, quantile_levels=LEVELS, max_bins=20)

    assert report.grid.step == pytest.approx(0.01) and math.isinf(report.p90.value)


def test_an_explicit_resolution_is_used_as_given():
    report = evaluate(craft(), "S", is_goal, resolution=0.01, max_bins=20)

    assert report.grid.step == 0.01 and math.isinf(report.p90.value)


def test_the_paley_zygmund_bound_is_below_the_exponential_quantile():
    mean = 5.0
    variance = mean * mean  # an exponential cost: the level quantile is mean * ln(1 / (1 - level))

    for level in (0.5, 0.9, 0.99):
        bound = _coarse.quantile_lower_bound(mean, variance, level)
        assert 0.0 <= bound <= mean * math.log(1.0 / (1.0 - level))


def test_a_state_that_leaves_with_probability_rounded_to_zero_keeps_the_ordinary_answer():
    policy = {"S": Action("use", 1.0, (("goal", 1), ("S", 10**17)))}

    report = evaluate(policy, "S", is_goal, max_bins=1_000, max_coarse_bins=100_000)

    assert math.isinf(report.p90.value)


@pytest.mark.parametrize("bins", [0, -3, 2.5, True])
def test_max_coarse_bins_must_be_an_integer_of_at_least_one(bins):
    with pytest.raises(ValueError, match="max_coarse_bins"):
        evaluate(craft(), "S", is_goal, max_coarse_bins=bins)
