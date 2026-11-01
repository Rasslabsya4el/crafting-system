"""The HiGHS LP oracle for actions with inputs (`lp_values_inputs`, ADR-0022, ticket #179).

The Bellman LP (maximal subsolution) is checked against the exact brute-force oracle; no solver
is run. The LP equals the optimal values only when every value is finite, so the fuzz compares
the two on the all-finite instances only. On an instance with an infinite state the oracle's
answer is not V* (its docstring says so), so the fuzz asserts nothing there; the hand cases at the
end pin that it is None (unbounded) for the typical infinite shapes.
"""

import functools
from fractions import Fraction

import pytest
from ssp_helpers import GOAL
from ssp_input_oracles import brute_force_inputs, lp_values_inputs, random_input_spec


def entry(label, cost, outcomes, inputs=()):
    return (label, Fraction(cost), list(outcomes), list(inputs))


def spec_of(table):
    return {GOAL}, table


SEEDS = range(300)
MIN_ALL_FINITE = 60


@functools.cache
def fuzz_spec(seed):
    return random_input_spec(seed)


@functools.cache
def fuzz_optimum(seed):
    return brute_force_inputs(fuzz_spec(seed))


def all_finite(best):
    return all(value is not None for value in best.values())


FINITE_SEEDS = [seed for seed in SEEDS if all_finite(fuzz_optimum(seed))]


def test_the_fuzz_has_enough_all_finite_instances():
    assert len(FINITE_SEEDS) >= MIN_ALL_FINITE, f"{len(FINITE_SEEDS)} of {len(SEEDS)}"


@pytest.mark.parametrize("seed", FINITE_SEEDS)
def test_lp_matches_brute_force_on_every_all_finite_instance(seed):
    best = fuzz_optimum(seed)

    values = lp_values_inputs(fuzz_spec(seed))

    assert values is not None
    for state, optimum in best.items():
        assert values[state] == pytest.approx(float(optimum), rel=1e-8), state


def check(table, expected):
    spec = spec_of(table)
    assert brute_force_inputs(spec) == expected
    values = lp_values_inputs(spec)
    for state, literal in expected.items():
        assert values[state] == pytest.approx(float(literal), rel=1e-8), state


def test_one_donor_pays_the_donor_on_every_attempt():
    # A: 4 attempts of 2 + 9; D: 3 per try, 3 tries
    table = {
        "A": [entry("combine", 2, [(GOAL, 1), ("A", 3)], ["D"])],
        "D": [entry("make", 3, [(GOAL, 1), ("D", 2)])],
    }

    check(table, {"A": 44, "D": 9})


def test_a_retry_pays_its_donor_again():
    # A succeeds with probability 1/2 and pays donor D (cost 5, sure) on each of its 2 attempts
    table = {
        "A": [entry("go", 1, [(GOAL, 1), ("A", 1)], ["D"])],
        "D": [entry("make", 5, [(GOAL, 1)])],
    }

    check(table, {"A": 12, "D": 5})


def test_two_donors_that_need_each_other_with_buy_options():
    # A needs a B and B needs an A (rho = 1, infinite) unless a buy breaks the cycle
    table = {
        "A": [
            entry("a", 1, [(GOAL, 1)], ["B"]),
            entry("buy", 30, [(GOAL, 1)]),
        ],
        "B": [
            entry("b", 1, [(GOAL, 1)], ["A"]),
            entry("buy", 10, [(GOAL, 1)]),
        ],
    }

    check(table, {"A": 11, "B": 10})


@pytest.mark.parametrize(
    "table",
    [
        {"A": [entry("self2", 1, [(GOAL, 1)], ["A", "A"])]},
        {
            "A": [entry("pair", 1, [(GOAL, 1)], ["B", "B"])],
            "B": [entry("back", 1, [(GOAL, 1)], ["A"])],
        },
        {"A": []},
    ],
    ids=["needs-two-copies-of-itself", "trap", "dead-end"],
)
def test_an_infinite_state_leaves_the_lp_unbounded(table):
    spec = spec_of(table)
    assert None in brute_force_inputs(spec).values()

    assert lp_values_inputs(spec) is None
