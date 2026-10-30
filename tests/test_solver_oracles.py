"""The solver against two independent oracles: exact brute force and the HiGHS Bellman LP.

Brute force tries every deterministic stationary policy on tiny SSPs and evaluates each in exact
fractions. The LP solves the same Bellman optimality conditions with a numerical solver. Both are
run against the solver under value iteration only, policy iteration only, and the default.
"""

import functools
import math
from fractions import Fraction

import pytest
from ssp_helpers import DIRECT_LIMITS
from ssp_oracles import (
    brute_force,
    cost_spread_ssp,
    evaluate_exactly,
    exact_optimal_values,
    lp_values,
    random_ssp,
    sparse_ssp,
    to_model,
)

from crafting_system.solver import solve

limits = pytest.mark.parametrize("limit", DIRECT_LIMITS.values(), ids=DIRECT_LIMITS.keys())
SEEDS = range(200)
PROPER_SEEDS = range(60)

# The LP is solved by a floating point simplex with feasibility tolerances of 1e-10; its answer is
# only trusted to about 1e-7 relative, so this slack belongs to the LP, not to the solver. The
# solver's own agreement is bounded by its certified `error_bound`.
LP_TOLERANCE = 1e-7


@functools.cache
def exact_optimum(seed, ensure_proper=False):
    return brute_force(random_ssp(seed, ensure_proper=ensure_proper))


def solve_all_states(spec, limit):
    size, _ = spec
    return solve(to_model(spec), range(size), direct_solve_limit=limit)


@limits
@pytest.mark.parametrize("seed", SEEDS)
def test_values_equal_exact_brute_force_within_the_certified_bound(seed, limit):
    spec = random_ssp(seed)
    best = exact_optimum(seed)

    solution = solve_all_states(spec, limit)

    for state, optimum in best.items():
        value = solution.values[state]
        if optimum is None:
            assert value == math.inf
        else:
            optimum = float(optimum)
            assert abs(value - optimum) <= solution.error_bound * optimum + 1e-12 * optimum


@limits
@pytest.mark.parametrize("seed", SEEDS)
def test_the_returned_policy_is_proper_and_attains_the_optimum_within_the_bound(seed, limit):
    spec = random_ssp(seed)
    best = exact_optimum(seed)

    solution = solve_all_states(spec, limit)

    choice = {
        state: int(action.label.split(".")[1]) for state, action in solution.policy.items()
    }
    exact = evaluate_exactly(spec, choice)
    finite = {state for state, optimum in best.items() if optimum is not None}
    assert set(solution.policy) == finite
    for state in finite:
        assert exact[state] is not None, "the policy must be proper"
        assert exact[state] >= best[state], "no policy beats the optimum"
        slack = 2 * solution.error_bound + 1e-12  # lower and upper multipliers both apply
        assert float(exact[state]) <= float(best[state]) * (1 + slack)


@limits
@pytest.mark.parametrize("seed", PROPER_SEEDS)
def test_values_match_the_highs_lp_on_small_random_ssps(seed, limit):
    spec = random_ssp(seed, ensure_proper=True)

    solution = solve_all_states(spec, limit)

    for state, reference in enumerate(lp_values(spec)):
        value = solution.values[state]
        assert abs(value - reference) <= solution.error_bound * reference + LP_TOLERANCE * reference


@pytest.mark.parametrize("seed", range(25))
def test_the_lp_oracle_agrees_with_exact_brute_force(seed):
    spec = random_ssp(seed, ensure_proper=True)

    best = exact_optimum(seed, ensure_proper=True)

    for state, reference in enumerate(lp_values(spec)):
        assert abs(reference - float(best[state])) <= LP_TOLERANCE * float(best[state])


@limits
@pytest.mark.parametrize("seed", range(12))
def test_values_match_the_highs_lp_on_larger_sparse_ssps(seed, limit):
    states = 20 + (seed * 7) % 41
    spec = sparse_ssp(seed, states)

    solution = solve_all_states(spec, limit)

    for state, reference in enumerate(lp_values(spec)):
        value = solution.values[state]
        assert abs(value - reference) <= solution.error_bound * reference + LP_TOLERANCE * reference


@pytest.mark.parametrize("tolerance", [1e-1, 1e-3])
@pytest.mark.parametrize("seed", SEEDS)
def test_a_loose_tolerance_still_gives_an_honest_error_bound(seed, tolerance):
    spec = random_ssp(seed)
    best = exact_optimum(seed)
    size, _ = spec

    solution = solve(to_model(spec), range(size), tolerance=tolerance, direct_solve_limit=0)

    assert solution.error_bound >= 0.0
    for state, optimum in best.items():
        if optimum is not None:
            optimum = float(optimum)
            assert abs(solution.values[state] - optimum) <= solution.error_bound * optimum + 1e-12 * optimum


CHEAP_CYCLE_UPSTREAM = (
    3,
    {
        # States 0 and 1 form a genuine cycle of cost 0.01 each and leave to state 2 half the time.
        # State 2 repeats until success and is worth about 1e7, a billion times the cheap costs.
        0: [("0.0", Fraction(1, 100), [(1, 1), (2, 1)])],
        1: [("1.0", Fraction(1, 100), [(0, 1), (2, 1)])],
        2: [("2.0", Fraction(1), [(2, 9_999_999), (3, 1)])],
    },
)


@limits
def test_a_cheap_cycle_upstream_of_a_huge_value_matches_brute_force_at_the_default_tolerance(limit):
    best = brute_force(CHEAP_CYCLE_UPSTREAM)

    solution = solve(to_model(CHEAP_CYCLE_UPSTREAM), [0], direct_solve_limit=limit)

    assert solution.error_bound <= 1e-9
    for state, optimum in best.items():
        optimum = float(optimum)
        assert abs(solution.values[state] - optimum) <= solution.error_bound * optimum + 1e-12 * optimum


def test_the_cheap_cycle_is_certified_within_a_small_sweep_budget_because_the_downstream_cost_counts():
    # The component's own costs are 0.01, but every action also pays for the huge downstream value,
    # so the certificate may measure its residual against that, not against 0.01: the cycle is
    # certified to the default tolerance in 22 sweeps (it needs 27 if only the 0.01 counts).
    best = brute_force(CHEAP_CYCLE_UPSTREAM)

    solution = solve(to_model(CHEAP_CYCLE_UPSTREAM), [0], direct_solve_limit=0, max_sweeps=22)

    assert solution.error_bound <= 1e-9
    for state, optimum in best.items():
        optimum = float(optimum)
        assert abs(solution.values[state] - optimum) <= solution.error_bound * optimum + 1e-12 * optimum


@limits
@pytest.mark.parametrize("seed", [701582, 701779, 701945])
def test_cost_spread_cycles_with_large_values_are_answered_at_the_default_tolerance(seed, limit):
    # Costs from 0.001 to 1000 and values near 1e4: the exact solve leaves residuals at the
    # rounding floor, far above tolerance * 0.001, yet the answer is exact to about 1e-16.
    spec = cost_spread_ssp(seed)
    size, _ = spec
    exact = exact_optimal_values(spec)

    # one of the three is a genuinely slow cycle for plain sweeps (about 30 000 of them)
    sweeps = 60_000 if (seed, limit) == (701582, 0) else 3000
    solution = solve(to_model(spec), range(size), direct_solve_limit=limit, max_sweeps=sweeps)

    assert solution.error_bound <= 1e-6
    for state, optimum in exact.items():
        error = abs(Fraction(solution.values[state]) - optimum) / optimum
        assert error <= Fraction(solution.error_bound)
