"""`evaluate` rejects bad arguments with `ValueError` before doing any work."""

import math
from fractions import Fraction

import pytest
from risk_support import geometric_policy, is_goal

from crafting_system.risk import evaluate

POLICY = geometric_policy(1, 3, 0.7)


def run(**kwargs):
    return evaluate(POLICY, "S", is_goal, **kwargs)


@pytest.mark.parametrize("level", [0.0, 1.0, -0.1, 1.5, math.nan, math.inf, True, "0.5", None])
def test_a_quantile_level_must_be_a_number_strictly_between_zero_and_one(level):
    with pytest.raises(ValueError, match="quantile level"):
        run(quantile_levels=(0.5, level))


@pytest.mark.parametrize("level", [0.0, 1.0, 2.0, math.nan, False, "0.9"])
def test_the_cvar_level_must_be_strictly_between_zero_and_one(level):
    with pytest.raises(ValueError, match="cvar_level"):
        run(cvar_level=level)


@pytest.mark.parametrize("tail", [0.0, 1.0, -1e-9, math.nan, True, "1e-9"])
def test_tail_mass_must_be_strictly_between_zero_and_one(tail):
    with pytest.raises(ValueError, match="tail_mass"):
        run(tail_mass=tail)


@pytest.mark.parametrize("bins", [0, -5, 2.5, True, "100"])
def test_max_bins_must_be_an_integer_of_at_least_one(bins):
    with pytest.raises(ValueError, match="max_bins"):
        run(max_bins=bins)


@pytest.mark.parametrize("step", [0.0, -0.1, math.nan, math.inf, True, "0.1"])
def test_a_resolution_must_be_finite_and_above_zero(step):
    with pytest.raises(ValueError, match="resolution"):
        run(resolution=step)


def test_a_resolution_above_the_smallest_cost_is_rejected_with_the_reason():
    with pytest.raises(ValueError, match="smallest cost"):
        run(resolution=0.71)


def test_a_resolution_equal_to_the_smallest_cost_is_allowed():
    assert run(resolution=0.7).grid.exact


@pytest.mark.parametrize("chosen", ["try", None, (0.7, ())])
def test_every_policy_value_must_be_an_action(chosen):
    with pytest.raises(ValueError, match="Action"):
        evaluate({"S": chosen}, "S", is_goal)


def test_a_policy_value_that_is_never_reached_is_still_checked():
    with pytest.raises(ValueError, match="Action"):
        evaluate({**POLICY, "unused": 3}, "S", is_goal)


def test_an_exact_rational_level_is_accepted():
    report = run(quantile_levels=(Fraction(1, 2),))

    assert report.quantiles[0.5].value == pytest.approx(2.1, rel=1e-9)  # 1 - 0.75**3 = 0.578 >= 0.5 > 0.4375
