"""The 5,000-instance fuzz of the two-input solver (ticket #179) against exact brute force and HiGHS.

Seeds 0..4999 of `ssp_input_oracles.random_input_spec` (3 to 6 states, up to 2 inputs per action, goal,
self and duplicate inputs, traps that need two copies of what they make), solved from every state. For
each instance:

* every value equals the exact optimum of `brute_force_inputs` within the solver's own certificate,
  `V (1 - err) <= V* <= V (1 + err)`, compared in exact fractions; an infinite value is infinite on
  both sides, and the returned policy, evaluated exactly, attains the value;
* when every optimum is finite, the Bellman LP of HiGHS (`lp_values_inputs`, the maximal subsolution)
  agrees with the solver;
* the one thing the solver may refuse to decide is an infinite value that is critical through weights
  (ADR-0022, guard 3): it then raises `ConvergenceError` with `error_bound == inf`. That is allowed only
  on an instance where brute force says some value is infinite, and only for the five seeds of `CRITICAL_THROUGH_WEIGHTS`
  (0.1% of the instances); an instance with every value finite must be solved.

The seeds run in chunks of 100 so a failure names a range; `test_few_instances_are_left_undecided`
runs last in the module and counts them.
"""

import functools
import math
from fractions import Fraction

import pytest
from ssp_input_oracles import (
    brute_force_inputs,
    evaluate_policy_exactly,
    lp_values_inputs,
    random_input_spec,
    to_model,
)

from crafting_system.solver import ConvergenceError, solve

INSTANCES = 5000
CHUNK = 100
SWEEPS = 5000
SLOW_SWEEPS = 200_000
# the instances (of 5,000) that are infinite but critical through weights, which neither the ceiling nor the
# mass-closed pre-check decides; they are the same five the prototype of #91 left
CRITICAL_THROUGH_WEIGHTS = {1074, 1255, 2065, 2594, 3640}

undecided_seeds: list[int] = []


def agrees(value, optimum, error):
    """`value (1 - error) <= optimum <= value (1 + error)`, in exact fractions."""
    value, error = Fraction(value), Fraction(error)
    return value * (1 - error) <= optimum <= value * (1 + error)


@functools.cache
def optimum_of(seed):
    return brute_force_inputs(random_input_spec(seed))


def solve_every_state(spec, max_sweeps):
    goals, table = spec
    return solve(to_model(spec), [*table, *goals], max_sweeps=max_sweeps)


def check(seed):
    """Check one instance; return False when the solver declined to decide it."""
    spec = random_input_spec(seed)
    _, table = spec
    best = optimum_of(seed)
    every_state_finite = all(value is not None for value in best.values())
    try:
        solution = solve_every_state(spec, SWEEPS)
    except ConvergenceError as raised:
        assert not every_state_finite, f"seed {seed}: gave up on an instance with every value finite"
        assert raised.error_bound == math.inf, f"seed {seed}: gave up with a finite bound"
        return False
    error = solution.error_bound
    assert error < math.inf, f"seed {seed}: returned a solution with no upper certificate"

    finite = set()
    for state, optimum in best.items():
        value = solution.values[state]
        if optimum is None:
            assert value == math.inf, f"seed {seed}, state {state}: the solver says {value}, the oracle infinite"
        else:
            assert value < math.inf, f"seed {seed}, state {state}: the solver says infinite, the oracle {optimum}"
            assert agrees(value, optimum, error), f"seed {seed}, state {state}: {value} against {float(optimum)}"
            finite.add(state)

    index = {(s, row[0]): i for s, rows in table.items() for i, row in enumerate(rows)}
    choice = {s: index[(s, action.label)] for s, action in solution.policy.items()}
    assert set(choice) == finite, f"seed {seed}: the policy covers {sorted(choice, key=repr)}"
    memo = {}
    for state in finite:
        attained = evaluate_policy_exactly(spec, choice, state, memo)
        assert attained is not None, f"seed {seed}, state {state}: the returned policy is infinite"
        assert best[state] <= attained <= Fraction(solution.values[state]) * (1 + Fraction(error))

    if every_state_finite:
        lp = lp_values_inputs(spec)
        assert lp is not None, f"seed {seed}: HiGHS found no optimum"
        for state, optimum in best.items():
            assert lp[state] == pytest.approx(float(optimum), rel=1e-8), f"seed {seed}, state {state}"
            assert solution.values[state] == pytest.approx(lp[state], rel=1e-8), f"seed {seed}, state {state}"
    return True


@pytest.mark.parametrize("first", range(0, INSTANCES, CHUNK))
def test_fuzz_chunk_matches_brute_force_and_the_certificate_holds(first):
    for seed in range(first, first + CHUNK):
        if not check(seed):
            undecided_seeds.append(seed)


def test_few_instances_are_left_undecided():
    # runs after the chunks above (pytest keeps the file order); alone it has nothing to count
    assert set(undecided_seeds) <= CRITICAL_THROUGH_WEIGHTS, undecided_seeds
