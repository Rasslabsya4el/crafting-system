"""Float costs that are not whole multiples of one step: the quantile and CVaR intervals must bracket the truth.

The oracle is an acyclic policy whose every path is enumerated with exact `Fraction` costs, so the
true quantile (the smallest cost with P(C <= x) >= level) and the true CVaR are known exactly.
"""

import math
import random

import pytest
from risk_support import decimal, is_goal, path_pmf, pmf_cvar, pmf_moments, pmf_quantile

from crafting_system.risk import evaluate
from crafting_system.solver import Action

LEVELS = (0.1, 0.5, 0.75, 0.9)


def branching(c1, c2, c3):
    """S has three exits; the paths cost c1, c1+c3, c1+c2 and c1+c2+c3."""
    return {
        "S": Action("s", c1, (("X", 2), ("Y", 1), ("goal", 1))),
        "X": Action("x", c2, (("goal", 1), ("Y", 1))),
        "Y": Action("y", c3, (("goal", 1),)),
    }


def width(estimate):
    return estimate.high - estimate.low


def contains(estimate, truth):
    """A grid cost within 1e-12 relative of a multiple of the step counts as that multiple (documented)."""
    slack = 1e-12 * abs(truth)
    return estimate.low - slack <= truth <= estimate.high + slack


def brackets_truth(report, pmf):
    for level in LEVELS:
        truth = float(pmf_quantile(pmf, decimal(level)))
        estimate = report.quantiles[level]
        assert contains(estimate, truth)
        assert estimate.low <= estimate.value <= estimate.high
    assert contains(report.cvar, float(pmf_cvar(pmf, decimal(report.cvar_level))))
    mean, variance = pmf_moments(pmf)
    assert report.mean.low <= mean <= report.mean.high
    assert report.variance.low <= variance <= report.variance.high


@pytest.mark.parametrize(
    "costs",
    [(math.pi, math.e, 1.5 * math.pi), (1.3, 2.1, 1.7)],
    ids=["no-common-unit", "tenths"],
)
@pytest.mark.parametrize("resolution", [None, 0.3, 0.5, 1.0])
def test_intervals_bracket_the_exact_distribution(costs, resolution):
    policy = branching(*costs)
    pmf = path_pmf(policy, "S")

    report = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, cvar_level=0.9, resolution=resolution)

    brackets_truth(report, pmf)


def test_costs_without_a_common_unit_give_an_inexact_grid_with_a_wide_but_finite_interval():
    report = evaluate(branching(math.pi, math.e, 1.5 * math.pi), "S", is_goal)

    assert not report.grid.exact
    assert report.grid.step <= math.e
    assert all(math.isfinite(width(e)) and width(e) > 0 for e in report.quantiles.values())


def test_the_default_grid_for_costs_without_a_unit_gives_a_narrow_interval_that_contains_the_truth():
    policy = branching(math.pi, math.e, 1.5 * math.pi)
    pmf = path_pmf(policy, "S")

    # the four paths have chance 1/4 each, so levels away from 1/4, 1/2, 3/4 avoid ties between paths
    report = evaluate(policy, "S", is_goal, quantile_levels=(0.4, 0.6, 0.9))

    assert not report.grid.exact
    for level in (0.4, 0.6, 0.9):
        truth = float(pmf_quantile(pmf, decimal(level)))
        assert contains(report.quantiles[level], truth)
        assert width(report.quantiles[level]) < 0.02 * truth


def test_a_finer_resolution_narrows_the_intervals_and_still_contains_the_truth():
    policy = branching(1.3, 2.1, 1.7)
    pmf = path_pmf(policy, "S")

    coarse = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, resolution=0.9)
    fine = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, resolution=0.07)

    assert coarse.grid.step == 0.9 and fine.grid.step == 0.07
    assert width(fine.cvar) < width(coarse.cvar)
    for level in LEVELS:
        truth = float(pmf_quantile(pmf, decimal(level)))
        assert width(fine.quantiles[level]) < width(coarse.quantiles[level])
        assert contains(fine.quantiles[level], truth)


@pytest.mark.parametrize(
    ("costs", "exact"),
    [
        ((0.1, 0.25, 0.5), True),
        ((0.5, 1.5, 2.5), True),
        ((1.3, 2.1, 1.7), True),
        ((1 / 3, 1.0001, 1.0), True),
        ((math.pi, math.e, 1.0), False),
        ((1.0, 2.0 * math.pi, 3.0), False),
    ],
)
def test_the_unit_finder_decides_exactness_when_the_horizon_fits(costs, exact):
    report = evaluate(branching(*costs), "S", is_goal)

    assert report.grid.exact is exact


def test_the_unit_is_the_greatest_common_divisor_of_the_costs():
    report = evaluate(branching(0.1, 0.25, 0.5), "S", is_goal)

    assert report.grid.step == pytest.approx(0.05, rel=1e-12)


def test_an_exact_unit_too_fine_for_the_horizon_falls_back_to_an_inexact_grid():
    # 1/3 and 1.0001 share only the unit 1/30000, far more bins than the cap allows here
    report = evaluate(branching(1 / 3, 1.0001, 1.0), "S", is_goal, max_bins=1000)

    assert not report.grid.exact
    assert report.grid.unresolved_mass == 0.0


def test_an_explicit_resolution_is_exact_only_when_every_cost_is_a_multiple_of_it():
    policy = branching(1.5, 2.5, 4.0)

    assert evaluate(policy, "S", is_goal, resolution=0.5).grid.exact
    assert not evaluate(policy, "S", is_goal, resolution=0.4).grid.exact


def random_acyclic(seed):
    """Five layered states with random float costs and weights; every path ends in the goal."""
    rng = random.Random(seed)
    table = {}
    for i in range(5):
        later = [f"s{j}" for j in range(i + 1, 5)] + ["goal"]
        picks = rng.sample(later, k=min(len(later), rng.randint(1, 3)))
        table[f"s{i}"] = Action(f"a{i}", rng.uniform(0.2, 3.0), tuple((t, rng.randint(1, 4)) for t in picks))
    return table


@pytest.mark.parametrize("seed", range(40))
def test_intervals_bracket_the_exact_distribution_of_random_acyclic_policies(seed):
    rng = random.Random(1000 + seed)
    policy = random_acyclic(seed)
    pmf = path_pmf(policy, "s0")
    smallest = min(a.cost for a in policy.values())
    resolution = rng.choice([None, smallest, smallest / 2, smallest / 3.7])

    report = evaluate(policy, "s0", is_goal, quantile_levels=LEVELS, resolution=resolution)

    brackets_truth(report, pmf)
