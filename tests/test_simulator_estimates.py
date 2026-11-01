"""The estimators behind `SimulationReport`, against numbers worked out by hand, and `Step` / argument checks."""

import math
import random
from fractions import Fraction

import pytest
from simulator_support import DATA, ITEMS, FakeAction, chain_policy, holds_target

from crafting_system.simulator import SampledEstimate, Step, simulate
from crafting_system.simulator._estimate import cvar, mean, proportion, quantile

Z95 = 1.959963984540054  # the 97.5% point of the standard normal, from a table


def test_the_wilson_interval_of_half_the_runs():
    estimate = proportion(50, 100, 0.95)

    assert estimate.value == 0.5
    assert (estimate.low, estimate.high) == pytest.approx((0.4038, 0.5962), abs=1e-4)
    assert estimate.standard_error == pytest.approx(math.sqrt(0.25 / (100 + Z95**2)), rel=1e-3)


def test_the_wilson_interval_of_no_success_is_zero_to_z_squared_over_n_plus_z_squared():
    estimate = proportion(0, 10, 0.95)

    assert estimate.value == 0.0 and estimate.low == 0.0
    assert estimate.high == pytest.approx(Z95**2 / (10 + Z95**2))


def test_the_wilson_interval_of_all_successes_is_n_over_n_plus_z_squared_to_one():
    estimate = proportion(10, 10, 0.95)

    assert estimate.value == 1.0 and estimate.high == 1.0
    assert estimate.low == pytest.approx(10 / (10 + Z95**2))
    assert estimate.standard_error > 0.0


def test_the_mean_of_four_numbers():
    estimate = mean([1.0, 2.0, 3.0, 4.0], 0.95)

    sd = math.sqrt(5 / 3)  # sum of squares 5, n - 1 = 3
    assert estimate.value == 2.5
    assert estimate.standard_error == pytest.approx(sd / 2)
    assert estimate.low == pytest.approx(2.5 - Z95 * sd / 2)
    assert estimate.high == pytest.approx(2.5 + Z95 * sd / 2)


@pytest.mark.parametrize("value, count", [(0.1, 3), (0.7, 3), (0.2, 6)])
def test_a_repeated_cost_that_floats_cannot_sum_back_to_has_no_spread(value, count):
    estimate = mean([value] * count, 0.95)

    assert estimate.value == value
    assert estimate.standard_error == 0.0
    assert estimate.agrees_with(value)


def test_equal_values_have_no_spread():
    estimate = mean([3.0, 3.0, 3.0], 0.95)

    assert (estimate.value, estimate.standard_error, estimate.low, estimate.high) == (3.0, 0.0, 3.0, 3.0)


def test_the_quantile_of_the_numbers_one_to_one_hundred():
    shuffled = [((7 * i) % 101) for i in range(1, 101)]  # a permutation of 1..100
    assert sorted(shuffled) == list(range(1, 101))

    estimate = quantile(shuffled, 0.9, 0.95)

    # rank 90; the binomial rank has sd 3, so the bracket is ranks 90 -+ 1.96 * 3 = 84.12 and 95.88,
    # rounded outwards to 84 and 96
    assert (estimate.value, estimate.low, estimate.high) == (90, 84, 96)
    assert estimate.standard_error == pytest.approx(12 / (2 * Z95))


def test_the_rank_of_a_quantile_has_no_float_noise():
    """0.7 * 10 is 7.000000000000001 in floating point, but the 70% quantile of ten values is the 7th."""
    assert quantile(list(range(1, 11)), 0.7, 0.95).value == 7


def test_a_quantile_bracket_is_held_inside_the_sample():
    estimate = quantile([4.0, 8.0, 15.0], 0.99, 0.95)

    assert estimate.value == 15.0 and estimate.high == 15.0 and 4.0 <= estimate.low <= 15.0


def test_a_quantile_of_equal_values_has_no_standard_error():
    estimate = quantile([5.0] * 50, 0.5, 0.95)

    assert (estimate.value, estimate.standard_error, estimate.low, estimate.high) == (5.0, 0.0, 5.0, 5.0)


@pytest.mark.parametrize("level", [0.0, 1.0, -0.1, 1.5, math.nan, math.inf, True, "0.5", None])
def test_a_quantile_level_must_be_strictly_between_zero_and_one(level):
    report = simulate(DATA, lambda item: None, ITEMS["goal"], holds_target, runs=2, seed=1)

    with pytest.raises(ValueError, match="quantile level"):
        report.quantile(level)


def worst_share_mean(values, level):
    """The mean of the worst 1 - level share of `values`, straight from the definition with exact Fractions:
    take the largest values one run at a time, the last one only in part."""
    tail = 1 - Fraction(repr(level))
    left = tail * len(values)
    total = Fraction(0)
    for x in sorted(values, reverse=True):
        take = min(Fraction(1), left)
        total += take * Fraction(x)
        left -= take
        if left == 0:
            break
    return float(total / (tail * len(values)))


def test_the_cvar_of_one_to_ten_at_ninety_percent_is_the_worst_run():
    assert cvar(list(range(1, 11)), 0.9, 0.95).value == pytest.approx(10.0, rel=1e-12)


def test_the_cvar_of_one_to_ten_at_85_percent_has_a_fractional_boundary_run():
    # the worst 15% of ten runs is 1.5 runs: the run worth 10 and half of the run worth 9
    # (10 + 0.5 * 9) / 1.5 = 29/3
    assert cvar(list(range(1, 11)), 0.85, 0.95).value == pytest.approx(29 / 3, rel=1e-12)


@pytest.mark.parametrize("level", [0.5, 0.73, 0.85, 0.9, 0.99])
def test_the_cvar_is_the_mean_of_the_worst_share_by_definition(level):
    values = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0, 5.0, 3.0]

    assert cvar(values, level, 0.95).value == pytest.approx(worst_share_mean(values, level), rel=1e-12)


def test_the_cvar_is_at_least_the_quantile_at_the_same_level():
    shuffled = [((7 * i) % 101) for i in range(1, 101)]  # a permutation of 1..100

    for level in (0.5, 0.9, 0.99):
        assert cvar(shuffled, level, 0.95).value >= quantile(shuffled, level, 0.95).value
    assert cvar(shuffled, 0.9, 0.95).value == pytest.approx(95.5, rel=1e-12)  # the mean of 91..100


def test_the_cvar_at_a_level_near_zero_is_the_mean():
    values = [((7 * i) % 101) for i in range(1, 101)]

    assert cvar(values, 1e-6, 0.95).value == pytest.approx(mean(values, 0.95).value, rel=1e-5)


def test_a_cvar_of_equal_values_is_that_value_with_no_standard_error():
    estimate = cvar([3.0, 3.0, 3.0], 0.9, 0.95)

    assert (estimate.value, estimate.standard_error, estimate.low, estimate.high) == (3.0, 0.0, 3.0, 3.0)


@pytest.mark.parametrize("value, count", [(0.1, 3), (0.7, 3), (0.2, 6)])
def test_a_cvar_of_a_repeated_cost_that_floats_cannot_sum_back_to_has_no_spread(value, count):
    estimate = cvar([value] * count, 0.9, 0.95)

    assert estimate.value == value
    assert estimate.standard_error == 0.0
    assert (estimate.low, estimate.high) == (value, value)


def test_the_cvar_interval_covers_the_true_cvar_of_an_exponential_sample():
    # exponential with mean 1: VaR at 0.9 is -ln(0.1), and the mean excess above it is 1, so CVaR = 1 - ln(0.1)
    rng = random.Random(1)
    sample = [rng.expovariate(1.0) for _ in range(20_000)]
    true_cvar = 1.0 - math.log(1.0 - 0.9)

    estimate = cvar(sample, 0.9, 0.999)

    assert estimate.standard_error > 0.0
    assert estimate.contains(true_cvar)


@pytest.mark.parametrize("level", [0.0, 1.0, -0.1, 1.5, math.nan, math.inf, True, "0.5", "x", None])
def test_a_cvar_level_must_be_strictly_between_zero_and_one(level):
    report = simulate(DATA, lambda item: None, ITEMS["goal"], holds_target, runs=2, seed=1)

    with pytest.raises(ValueError, match="cvar level"):
        report.cvar(level)


def test_the_report_cvar_is_the_cvar_of_its_costs():
    chain = chain_policy({"S": (1.0, (("goal", 1), ("S", 2)))})
    report = simulate(DATA, chain, ITEMS["S"], holds_target, runs=200, seed=4)

    assert len(set(report.costs)) > 1
    assert report.cvar(0.9) == cvar(report.costs, 0.9, report.confidence)


def test_contains_is_inclusive_at_both_ends():
    estimate = SampledEstimate(10.0, 1.0, 8.0, 12.0)

    assert estimate.contains(8.0) and estimate.contains(12.0) and estimate.contains(10.0)
    assert not estimate.contains(7.99) and not estimate.contains(12.01)


def test_agrees_with_counts_standard_errors():
    estimate = SampledEstimate(10.0, 2.0, 6.0, 14.0)

    assert estimate.agrees_with(20.0)  # exactly 5 standard errors
    assert not estimate.agrees_with(20.01)
    assert estimate.agrees_with(14.0, sigmas=2.0) and not estimate.agrees_with(14.1, sigmas=2.0)


def test_agrees_with_asks_for_equality_when_there_is_no_spread():
    estimate = SampledEstimate(7.5, 0.0, 7.5, 7.5)

    assert estimate.agrees_with(7.5) and estimate.agrees_with(7.5 * (1 + 1e-13))
    assert not estimate.agrees_with(7.5 * (1 + 1e-9))


# ------------------------------------------------------------------------------ Step


def test_a_step_keeps_its_action_and_cost_and_is_immutable():
    action = FakeAction((("goal", 1),))
    step = Step(action, 2)

    assert step.action is action and step.cost == 2.0 and isinstance(step.cost, float)
    with pytest.raises(AttributeError):
        step.cost = 3.0
    assert Step(action, 0).cost == 0.0


@pytest.mark.parametrize("cost", [-0.1, math.nan, math.inf, -math.inf, True, "1.0", None])
def test_a_step_cost_must_be_finite_and_not_negative(cost):
    with pytest.raises(ValueError, match="cost"):
        Step(FakeAction((("goal", 1),)), cost)


@pytest.mark.parametrize("action", [None, "chaos", 3, object()])
def test_a_step_needs_an_action_with_outcomes(action):
    with pytest.raises(ValueError, match="outcomes"):
        Step(action, 1.0)
