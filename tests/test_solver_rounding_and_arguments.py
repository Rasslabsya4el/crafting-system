"""Rounded probabilities keep the bound honest; overflow and bad arguments are refused clearly."""

import math
from fractions import Fraction

import pytest
from ssp_helpers import DIRECT_LIMITS, GOAL, act, model
from ssp_oracles import brute_force, random_ssp, to_model

from crafting_system.solver import Action, ConvergenceError, TabularModel, solve

limits = pytest.mark.parametrize("limit", DIRECT_LIMITS.values(), ids=DIRECT_LIMITS.keys())


def true_relative_error(value, optimum):
    return abs(Fraction(value) - optimum) / optimum


@limits
@pytest.mark.parametrize("n", [10**9, 10**12, 10**14])
def test_the_bound_covers_the_rounding_of_a_nearly_certain_cycle(n, limit):
    # state 0 leaves to the goal with chance 1 in n, otherwise goes through state 1 and back
    spec = (2, {0: [("a", Fraction(1), [(1, n - 1), (2, 1)])], 1: [("b", Fraction(1), [(0, 1)])]})
    best = brute_force(spec)
    if limit == 0:
        # sweeps lose a factor 1 / n per sweep here: reported with a bound, never a wrong answer
        with pytest.raises(ConvergenceError) as slow:
            solve(to_model(spec), [0], direct_solve_limit=0, max_sweeps=1000)
        assert not math.isnan(slow.value.error_bound)
        return

    solution = solve(to_model(spec), [0], direct_solve_limit=limit)

    assert solution.error_bound >= 0.0
    for state in (0, 1):
        error = true_relative_error(solution.values[state], best[state])
        assert error <= Fraction(solution.error_bound) + Fraction(1, 10**300)


# Seeds of the wide-weight family whose cycles lose too little per sweep for plain value iteration
# to reach the tolerance in 2000 sweeps (taken from a real run). They must be reported with a
# bound, never answered wrongly; policy iteration (the default and the policy-only limit) answers
# every seed.
SLOW_FOR_SWEEPS = frozenset(
    {1, 37, 43, 44, 47, 52, 75, 77, 82, 89, 90, 99, 105, 107, 111, 117, 126, 130}
)


@limits
@pytest.mark.parametrize("seed", range(150))
def test_the_bound_stays_honest_with_weights_spanning_nine_orders_of_magnitude(seed, limit):
    spec = random_ssp(seed, weight_choices=[1, 2, 5, 10**3, 10**6, 10**9])
    best = brute_force(spec)
    size, _ = spec

    if limit == 0 and seed in SLOW_FOR_SWEEPS:
        with pytest.raises(ConvergenceError) as slow:
            solve(to_model(spec), range(size), direct_solve_limit=0, max_sweeps=2000)
        assert not math.isnan(slow.value.error_bound)
        return

    solution = solve(to_model(spec), range(size), direct_solve_limit=limit, max_sweeps=2000)

    for state, optimum in best.items():
        value = solution.values[state]
        if optimum is None:
            assert value == math.inf
        elif solution.error_bound < math.inf:
            error = true_relative_error(value, optimum)
            assert error <= Fraction(solution.error_bound) + Fraction(1, 10**300)


def test_an_effective_cost_beyond_float64_is_refused_naming_the_state():
    huge_ratio = Action("loop", 1.0, (("A", 2**2000), (GOAL, 1)))

    with pytest.raises(ValueError, match="effective cost overflows float64.*'A'"):
        solve(model({"A": [huge_ratio]}), ["A"])


def test_a_large_cost_times_a_large_ratio_is_refused_naming_the_state():
    costly = Action("loop", 1e308, (("A", 2**70), (GOAL, 1)))

    with pytest.raises(ValueError, match="effective cost overflows float64.*'A'"):
        solve(model({"A": [costly]}), ["A"])


@pytest.mark.parametrize("cost", [10**400, Fraction(10**400), -(10**400)])
def test_a_cost_that_does_not_fit_a_float_is_a_value_error(cost):
    with pytest.raises(ValueError):
        Action("a", cost, ((GOAL, 1),))


@pytest.mark.parametrize("tolerance", [0, 0.0, -1e-3, math.nan, math.inf, True, "1e-3", None])
def test_tolerance_must_be_finite_and_above_zero(tolerance):
    with pytest.raises(ValueError):
        solve(TabularModel([GOAL], {}), [GOAL], tolerance=tolerance)


@pytest.mark.parametrize("max_sweeps", [0, -1, 1.5, True, None, "10"])
def test_max_sweeps_must_be_a_positive_integer(max_sweeps):
    with pytest.raises(ValueError):
        solve(TabularModel([GOAL], {}), [GOAL], max_sweeps=max_sweeps)


@pytest.mark.parametrize("limit", [-1, 2.5, True, None, "3"])
def test_direct_solve_limit_must_be_a_non_negative_integer(limit):
    with pytest.raises(ValueError):
        solve(TabularModel([GOAL], {}), [GOAL], direct_solve_limit=limit)


def test_the_boundary_argument_values_are_accepted():
    solution = solve(model({"A": [act("a", 1, (GOAL, 1))]}), ["A"], tolerance=1e-300, max_sweeps=1, direct_solve_limit=0)

    assert solution.values["A"] == 1.0
