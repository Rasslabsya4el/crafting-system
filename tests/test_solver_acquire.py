"""The acquisition adapter (`Need`, `MAIN`, `Acquisition`; ADR-0022, ticket #180) against an exact oracle.

A base model whose actions list `Need(start, want)` in `extra_inputs` becomes a product model over
states `('in', want, s)`: one copy of the base graph for the main target (`MAIN`) and one for each
wanted item. The expected numbers come from `ssp_input_oracles.brute_force_inputs`, exact brute
force over every stationary policy, run on a product table that THIS file builds itself
(`product_spec`: a plain expansion of the base table into every `('in', want, s)`, no adapter code),
so the adapter is not used to check itself. This file has five parts:

* the tiny two-prefix recombinator case of the prototype (4 item states, 3 wanted items, 3 selection
  rules, 2 price sets, 12 product states), values and policy against the oracle, a few exact numbers
  and the ones worked out by hand;
* a model with only the main target gives the same solution with and without the wrapper;
* hand cases: a Need nested in another acquisition, a Need already satisfied by its start, the
  `reaches` dominance predicate, a repeated Need, one copy shared by two actions, the `TypeError`
  for a plain input, `MAIN` under `copy` and `pickle`;
* a seeded fuzz of random base tables with Needs against the oracle, values and returned policy;
* a coverage test that the fuzz really contains the cases the ticket asks for.

Instances the solver cannot decide are not pinned: a supercritical component the solver cannot
declare infinite raises `ConvergenceError` today and ticket #179 changes that, so the fuzz only
counts them (as skips).
"""

import copy
import dataclasses
import functools
import math
import operator
import pickle
import random
from collections import Counter
from fractions import Fraction

import pytest
import ssp_oracles
from ssp_helpers import GOAL, CountingModel
from ssp_input_oracles import brute_force_inputs, evaluate_policy_exactly

from crafting_system.solver import (
    MAIN,
    Acquisition,
    Action,
    ConvergenceError,
    Need,
    TabularModel,
    solve,
)

# --- a base table, its model, and its product table (built here, with no adapter code) ---------
#
# A base spec is `(goals, table)`; `table[s]` is a list of `(label, cost, outcomes, needs)` with an
# exact cost, `outcomes` a list of `(state, weight)` and `needs` a list of `(start, want)` pairs.


def row(label, cost, outcomes, needs=()):
    return (label, Fraction(cost), list(outcomes), list(needs))


def base_model(spec):
    """The base model of a spec, with `Need` objects in the extra inputs."""
    goals, table = spec
    return TabularModel(
        goals,
        {
            state: [
                Action(
                    label,
                    float(cost),
                    tuple((t, w) for t, w in outcomes),
                    tuple(Need(start, want) for start, want in needs),
                )
                for label, cost, outcomes, needs in rows
            ]
            for state, rows in table.items()
        },
    )


def wants_of(spec):
    """The wanted items of a spec, in a fixed order."""
    _, table = spec
    found = {want for rows in table.values() for _, _, _, needs in rows for _, want in needs}
    return sorted(found, key=repr)


def product_spec(spec, reaches=operator.eq):
    """The oracle spec of the product: every base state `s` in every copy `want` in (MAIN, *wants).

    A state is a goal of the copy MAIN when it is a base goal, of another copy when `reaches(s,
    want)`. Every other state keeps the base actions of `s`: outcomes stay in their copy and a
    need `(start, want2)` becomes the input `('in', want2, start)`.
    """
    goals, table = spec
    items = set(goals) | set(table)
    for rows in table.values():
        for _, _, outcomes, needs in rows:
            items |= {t for t, _ in outcomes}
            items |= {start for start, _ in needs}
    items |= set(wants_of(spec))
    product_goals, product_table = set(), {}
    for want in [MAIN, *wants_of(spec)]:
        for s in items:
            state = ("in", want, s)
            if (s in goals) if want is MAIN else reaches(s, want):
                product_goals.add(state)
                continue
            product_table[state] = [
                (
                    label,
                    cost,
                    [(("in", want, t), w) for t, w in outcomes],
                    [("in", want2, start) for start, want2 in needs],
                )
                for label, cost, outcomes, needs in table.get(s, [])
            ]
    return product_goals, product_table


def all_states(product):
    goals, table = product
    return sorted([*goals, *table], key=repr)


def agrees(value, optimum, error):
    """`value (1 - error) <= optimum <= value (1 + error)`, compared in exact fractions."""
    value, error = Fraction(value), Fraction(error)
    return value * (1 - error) <= optimum <= value * (1 + error)


def merged(outcomes):
    result = {}
    for state, weight in outcomes:
        if weight > 0:
            result[state] = result.get(state, 0) + weight
    return result


def assert_matches_oracle(product, best, solution, *, max_error=1e-9):
    """Every value the solver returns equals the exact optimum within its bound; so does the policy.

    Only the states the solver reached are compared. The policy must cover exactly the finite
    non-goal states, each action must be the product table's row of that label, and the policy
    evaluated exactly must be within the bound of the optimum.
    """
    goals, table = product
    error = solution.error_bound
    assert error <= max_error, f"error bound {error}"
    finite = set()
    for state, value in solution.values.items():
        assert state in goals or state in best, f"{state!r} is not a state of the product"
        if state in goals:
            assert value == 0.0, state
        elif value == math.inf:
            assert best[state] is None, f"state {state}: the solver says infinite, the oracle {best[state]}"
        else:
            assert best[state] is not None, f"state {state}: the solver says {value}, the oracle infinite"
            assert agrees(value, best[state], error), f"state {state}: {value} against {float(best[state])}"
            finite.add(state)

    index = {(s, r[0]): (i, r) for s, rows in table.items() for i, r in enumerate(rows)}
    choice = {}
    for state, action in solution.policy.items():
        i, r = index[(state, action.label)]
        assert action.cost == float(r[1]), state
        assert merged(action.outcomes) == merged(r[2]), state
        assert sorted(action.extra_inputs, key=repr) == sorted(r[3], key=repr), state
        choice[state] = i
    assert set(choice) == finite
    memo = {}
    for state in finite:
        attained = evaluate_policy_exactly(product, choice, state, memo)
        assert attained is not None, f"state {state}: the returned policy has an infinite value"
        assert best[state] <= attained <= Fraction(solution.values[state]) * (1 + Fraction(error)), state


def check(spec, starts, expected=None, *, reaches=None, **options):
    """Solve a hand case through `Acquisition`; compare with the oracle and with the hand numbers.

    `starts` are base states for the main target or full product states; `expected` maps product
    states to the exact value (None: infinite). Returns `(solution, acquisition)`.
    """
    acquisition = Acquisition(base_model(spec), reaches=reaches)
    product = product_spec(spec, reaches or operator.eq)
    best = brute_force_inputs(product)
    solution = solve(acquisition, starts, **options)
    assert_matches_oracle(product, best, solution)
    for state, literal in (expected or {}).items():
        if state in product[0]:
            assert literal == 0, state
            assert solution.values[state] == 0.0, state
        elif literal is None:
            assert best[state] is None, f"oracle: {state}"
            assert solution.values[state] == math.inf, state
            assert state not in solution.policy, state
        else:
            assert best[state] == literal, f"oracle: {state}"
            assert solution.values[state] == pytest.approx(float(literal), rel=1e-9), state
    return solution, acquisition


def main_of(s):
    return ("in", MAIN, s)


# --- the tiny two-prefix recombinator case ------------------------------------------------------
#
# Item states E (empty), P (common prefix), Q (rare prefix), PQ (both, the main target). The
# wanted items are PQ (the main target), P and Q. `recombine` from P needs a Q that begins as E,
# and from Q needs a P that begins as E. Costs are in chaos.

RULES = {"equal": (1, 1), "rare-x2": (2, 1), "rare-x5": (5, 1)}
PRICES = {"cc": 1, "bP": 3, "bQ": 8, "cr": 1, "cs": 2}
PRICES_B = {"cc": 2, "bP": 2, "bQ": 8, "cr": 1, "cs": 2}
PRICE_SETS = {"prices-a": PRICES, "prices-b": PRICES_B}
TINY_CASES = {f"{rule}-{prices}": (RULES[rule], PRICE_SETS[prices]) for rule in RULES for prices in PRICE_SETS}


def tiny_spec(rule, prices, *, recombine=True, scour=True):
    """The base table of the tiny case.

    The recombinator pool holds two mods, one kept with chance 2/3 or both with 1/3; when one is
    kept, the rare mod Q is kept with weight kQ against kP for the common P. In integers: PQ gets
    kQ + kP, Q gets 2 kQ and P gets 2 kP out of 3 (kQ + kP).
    """
    kq, kp = rule
    p = prices
    table = {
        "E": [
            row("craft P", p["cc"], [("P", 1), ("E", 9)]),
            row("craft Q", p["cc"], [("Q", 1), ("E", 9)]),
            row("buy P", p["bP"], [("P", 1)]),
            row("buy Q", p["bQ"], [("Q", 1)]),
        ]
    }
    for s, other in (("P", "Q"), ("Q", "P")):
        rows = [row("craft " + other, p["cc"], [("PQ", 1), (s, 19)])]
        if recombine:
            rows.append(
                row("recombine", p["cr"], [("PQ", kq + kp), ("Q", 2 * kq), ("P", 2 * kp)], [("E", other)])
            )
        if scour:
            rows.append(row("scour", p["cs"], [("E", 1)]))
        table[s] = rows
    return {"PQ"}, table


@functools.cache
def tiny(case):
    """`(product, best, solution)` of one rule x price set, every product state a start."""
    rule, prices = TINY_CASES[case]
    spec = tiny_spec(rule, prices)
    product = product_spec(spec)
    best = brute_force_inputs(product)
    acquisition = Acquisition(base_model(spec))
    return product, best, solve(acquisition, all_states(product))


def test_the_tiny_case_has_twelve_product_states_and_all_are_reached_from_one_start():
    spec = tiny_spec(RULES["equal"], PRICES)
    product = product_spec(spec)
    acquisition = Acquisition(base_model(spec))

    assert wants_of(spec) == ["P", "Q"]
    assert len(product[0]) + len(product[1]) == 12

    solution = solve(acquisition, [acquisition.start("E")])
    assert set(solution.values) == set(all_states(product))


@pytest.mark.parametrize("case", TINY_CASES)
def test_the_tiny_case_values_and_policy_equal_exact_brute_force(case):
    product, best, solution = tiny(case)

    assert set(solution.values) == set(all_states(product))
    assert_matches_oracle(product, best, solution)


# the exact optimum of the main target and of the two donor copies, from the oracle, once
TINY_PINS = {
    "equal-prices-a": {
        ("P", "E"): 3,
        ("Q", "E"): 8,
        (MAIN, "E"): 23,
        (MAIN, "P"): 20,
        (MAIN, "Q"): 16,
    },
    "equal-prices-b": {
        ("P", "E"): 2,
        ("Q", "E"): 8,
        (MAIN, "E"): 23,
        (MAIN, "P"): 21,
        (MAIN, "Q"): 15,
    },
    "rare-x2-prices-a": {
        ("P", "E"): 3,
        ("Q", "E"): 8,
        (MAIN, "E"): 23,
        (MAIN, "P"): 20,
        (MAIN, "Q"): Fraction("76/5"),
    },
    "rare-x2-prices-b": {
        ("P", "E"): 2,
        ("Q", "E"): 8,
        (MAIN, "E"): 21,
        (MAIN, "P"): 19,
        (MAIN, "Q"): 13,
    },
    "rare-x5-prices-a": {
        ("P", "E"): 3,
        ("Q", "E"): 8,
        (MAIN, "E"): Fraction("65/3"),
        (MAIN, "P"): Fraction("56/3"),
        (MAIN, "Q"): Fraction("41/3"),
    },
    "rare-x5-prices-b": {
        ("P", "E"): 2,
        ("Q", "E"): 8,
        (MAIN, "E"): 19,
        (MAIN, "P"): 17,
        (MAIN, "Q"): 11,
    },
}


@pytest.mark.parametrize("case", TINY_CASES)
def test_the_tiny_case_pinned_exact_numbers(case):
    product, best, solution = tiny(case)

    for (want, s), literal in TINY_PINS[case].items():
        state = ("in", want, s)
        assert best[state] == literal, f"oracle: {state}"
        assert solution.values[state] == pytest.approx(float(literal), rel=1e-9), state


def test_the_tiny_case_by_hand_with_equal_weights():
    # Q from E: buy 8 (crafting costs 1 for a 1/10 chance: 10). P from E: buy 3.
    # In the main copy, state P: craft Q, 1 for a 1/20 chance: 20; recombine pays 1 + 8 = 9 per attempt
    # for PQ 1/3, Q 1/3, P 1/3, so with b = V(Q): 2 V(P) = 27 + b. State Q: craft P is 20, recombine
    # pays 1 + 3 = 4 per attempt, 2 b = 12 + V(P); with V(P) = 20 that gives b = 16 and V(P) = 21.5 > 20.
    # State E: buy P then be in P: 3 + 20 = 23 (buy Q: 8 + 16 = 24; crafting P: 30).
    product, best, solution = tiny("equal-prices-a")

    expected = {
        ("in", "Q", "E"): 8,
        ("in", "P", "E"): 3,
        main_of("P"): 20,
        main_of("Q"): 16,
        main_of("E"): 23,
        main_of("PQ"): 0,
    }
    for state, literal in expected.items():
        assert solution.values[state] == pytest.approx(float(literal), rel=1e-9), state
    labels = {state: solution.policy[state].label for state in solution.policy}
    assert labels[("in", "Q", "E")] == "buy Q"
    assert labels[("in", "P", "E")] == "buy P"
    assert labels[main_of("P")] == "craft Q"
    assert labels[main_of("Q")] == "recombine"
    assert labels[main_of("E")] == "buy P"
    assert solution.policy[main_of("Q")].extra_inputs == (("in", "P", "E"),)
    assert best[main_of("E")] == 23


@pytest.mark.parametrize("prices", PRICE_SETS)
@pytest.mark.parametrize("rule", RULES)
def test_the_cheapest_way_to_get_a_q_from_empty_is_to_buy_it(rule, prices):
    # crafting a Q costs cc per try with a 1/10 chance: 10 cc >= 10 > 8 = bQ, and every route through P is dearer
    _, _, solution = tiny(f"{rule}-{prices}")

    assert solution.values[("in", "Q", "E")] == pytest.approx(8.0, rel=1e-9)
    assert solution.policy[("in", "Q", "E")].label == "buy Q"


# --- a model with only the main target: the same with and without the wrapper -------------------


def unwrapped(action):
    """A wrapped action back in the base states; it must be in the MAIN copy and have no inputs."""
    outcomes = []
    for state, weight in action.outcomes:
        tag, want, s = state
        assert tag == "in"
        assert want is MAIN
        outcomes.append((s, weight))
    assert action.extra_inputs == ()
    return Action(action.label, action.cost, tuple(outcomes))


def assert_same_with_and_without_the_wrapper(model, states):
    acquisition = Acquisition(model)
    wrapped_starts = [acquisition.start(s) for s in states]
    try:
        plain = solve(model, states)
    except ConvergenceError:
        with pytest.raises(ConvergenceError):
            solve(acquisition, wrapped_starts)
        return
    wrapped = solve(acquisition, wrapped_starts)

    assert wrapped.error_bound == plain.error_bound
    assert set(wrapped.values) == {main_of(s) for s in plain.values}
    for s, value in plain.values.items():
        assert wrapped.values[main_of(s)] == value, s
    assert set(wrapped.policy) == {main_of(s) for s in plain.policy}
    for s, action in plain.policy.items():
        assert unwrapped(wrapped.policy[main_of(s)]) == action, s


@pytest.mark.parametrize("scour", [True, False], ids=["with-scour", "no-scour"])
@pytest.mark.parametrize("case", ["equal-prices-a", "rare-x5-prices-b"])
def test_the_tiny_case_without_recombining_is_the_same_with_and_without_the_wrapper(case, scour):
    rule, prices = TINY_CASES[case]
    model = base_model(tiny_spec(rule, prices, recombine=False, scour=scour))

    assert_same_with_and_without_the_wrapper(model, ["E", "P", "Q", "PQ"])
    # sanity: this is a real problem, not an all-infinite one
    assert solve(model, ["E"]).values["E"] < math.inf


@pytest.mark.parametrize("seed", range(100))
def test_a_random_model_without_inputs_is_the_same_with_and_without_the_wrapper(seed):
    size, table = ssp_oracles.random_ssp(seed, ensure_proper=seed % 2 == 1)
    model = ssp_oracles.to_model((size, table))

    assert_same_with_and_without_the_wrapper(model, list(range(size + 1)))


def test_the_wrapper_asks_the_base_model_once_per_state_and_never_about_a_goal():
    counting = CountingModel(base_model(tiny_spec(RULES["equal"], PRICES, recombine=False)))
    acquisition = Acquisition(counting)

    solve(acquisition, [acquisition.start("E")])

    calls = Counter(counting.action_calls)
    assert set(calls) == {"E", "P", "Q"}
    assert max(calls.values()) == 1
    assert "PQ" not in counting.action_calls


# --- hand cases -----------------------------------------------------------------------------------

NESTED = (
    {GOAL},
    {
        # M needs an A made from A0; making an A needs a B made from B0; a B is made in one step
        "M": [row("use", 1, [(GOAL, 1)], [("A0", "A")])],
        "A0": [row("make A", 2, [("A", 1)], [("B0", "B")])],
        "B0": [row("make B", 3, [("B", 1)])],
    },
)


def test_a_need_nested_inside_the_acquisition_of_another_need():
    solution, acquisition = check(
        NESTED,
        [Acquisition(base_model(NESTED)).start("M")],
        {main_of("M"): 6, ("in", "A", "A0"): 5, ("in", "B", "B0"): 3},
    )

    assert set(solution.values) == {
        main_of("M"),
        main_of(GOAL),
        ("in", "A", "A0"),
        ("in", "A", "A"),
        ("in", "B", "B0"),
        ("in", "B", "B"),
    }
    assert solution.policy[main_of("M")] == Action("use", 1.0, ((main_of(GOAL), 1),), (("in", "A", "A0"),))
    assert solution.policy[("in", "A", "A0")].extra_inputs == (("in", "B", "B0"),)
    assert solution.policy[("in", "B", "B0")].extra_inputs == ()


def test_the_base_model_is_left_as_it_was():
    model = base_model(NESTED)
    acquisition = Acquisition(model)

    solve(acquisition, [acquisition.start("M")])

    assert model.actions("M")[0].extra_inputs == (Need("A0", "A"),)
    assert model.actions("M")[0].outcomes == ((GOAL, 1),)


def test_a_need_whose_start_already_satisfies_the_want_is_free():
    spec = ({GOAL}, {"M": [row("use", 2, [(GOAL, 1)], [("A", "A")])]})

    solution, acquisition = check(
        spec, [Acquisition(base_model(spec)).start("M")], {main_of("M"): 2, ("in", "A", "A"): 0}
    )

    assert solution.values[("in", "A", "A")] == 0.0
    assert solution.policy[main_of("M")].extra_inputs == (("in", "A", "A"),)


# a ladder: from rung 0 either jump to rung 2 at cost 1 or step to rung 1 at cost 5; M needs a rung 1
LADDER = (
    {GOAL},
    {
        "M": [row("use", 1, [(GOAL, 1)], [(0, 1)])],
        0: [row("jump", 1, [(2, 1)]), row("step", 5, [(1, 1)])],
        1: [row("up", 1, [(2, 1)])],
        2: [],
    },
)


def at_least(s, want):
    return isinstance(s, int) and s >= want


@pytest.mark.parametrize(
    ("reaches", "total", "rung", "label"),
    [(None, 6, 5, "step"), (at_least, 2, 1, "jump")],
    ids=["equality", "dominance"],
)
def test_the_want_predicate_ends_an_acquisition_early_when_a_state_dominates_the_want(
    reaches, total, rung, label
):
    solution, _ = check(
        LADDER,
        [main_of("M")],
        {main_of("M"): total, ("in", 1, 0): rung},
        reaches=reaches,
    )

    assert solution.policy[("in", 1, 0)].label == label
    assert solution.values[("in", 1, 2)] == (0.0 if reaches else math.inf)


def test_the_want_predicate_is_never_asked_about_the_main_target():
    asked = []

    def reaches(s, want):
        asked.append(want)
        return s == want

    solve_acquisition = Acquisition(base_model(NESTED), reaches=reaches)
    solve(solve_acquisition, [solve_acquisition.start("M")])

    assert asked
    assert not any(want is MAIN for want in asked)


@pytest.mark.parametrize("copies", [1, 2, 3])
def test_a_repeated_need_is_that_many_copies(copies):
    spec = (
        {GOAL},
        {
            "M": [row("use", 1, [(GOAL, 1)], [("S", "T")] * copies)],
            "S": [row("make", 3, [("T", 1)])],
        },
    )

    solution, acquisition = check(spec, [main_of("M")], {main_of("M"): 1 + 3 * copies, ("in", "T", "S"): 3})

    assert solution.policy[main_of("M")].extra_inputs == (("in", "T", "S"),) * copies
    assert acquisition.actions(main_of("M"))[0].extra_inputs == (("in", "T", "S"),) * copies


def test_a_repeated_need_is_paid_again_on_every_retry():
    # use fails 1 time in 2 and each try pays two T of 3 each: (1 + 6) per try, two tries: 14
    spec = (
        {GOAL},
        {
            "M": [row("use", 1, [(GOAL, 1), ("M", 1)], [("S", "T"), ("S", "T")])],
            "S": [row("make", 3, [("T", 1)])],
        },
    )

    check(spec, [main_of("M")], {main_of("M"): 14, ("in", "T", "S"): 3})


SHARED = {
    "two-starts": (
        {GOAL},
        {
            "M": [
                row("x", 1, [(GOAL, 1)], [("S", "T")]),
                row("y", 2, [(GOAL, 1)], [("S2", "T")]),
            ],
            "S": [row("make", 4, [("T", 1), ("S", 1)])],  # a T half the time: 8
            "S2": [row("make2", 1, [("T", 1)])],
        },
        {main_of("M"): 3, ("in", "T", "S"): 8, ("in", "T", "S2"): 1},
        "y",
        {main_of("M"), main_of(GOAL), ("in", "T", "S"), ("in", "T", "S2"), ("in", "T", "T")},
    ),
    "one-start": (
        {GOAL},
        {
            "M": [
                row("x", 1, [(GOAL, 1)], [("S", "T")]),
                row("y", 2, [(GOAL, 1)], [("S", "T")]),
            ],
            "S": [row("make", 4, [("T", 1), ("S", 1)])],
        },
        {main_of("M"): 9, ("in", "T", "S"): 8},
        "x",
        {main_of("M"), main_of(GOAL), ("in", "T", "S"), ("in", "T", "T")},
    ),
}


@pytest.mark.parametrize("name", SHARED)
def test_the_same_want_asked_by_two_actions_shares_one_product_copy(name):
    goals, table, expected, label, reachable = SHARED[name]
    spec = (goals, table)

    solution, acquisition = check(spec, [main_of("M")], expected)

    assert set(solution.values) == reachable
    assert {want for _, want, _ in solution.values} == {MAIN, "T"}
    assert solution.policy[main_of("M")].label == label
    assert acquisition.actions(main_of("M"))[0].extra_inputs[0][:2] == ("in", "T")


def test_a_want_that_is_a_string_called_main_is_not_the_main_target():
    spec = (
        {GOAL},
        {
            "M": [row("use", 1, [(GOAL, 1)], [("S", "MAIN")])],
            "S": [row("make", 3, [("MAIN", 1)])],
        },
    )

    solution, _ = check(spec, [main_of("M")], {main_of("M"): 4, ("in", "MAIN", "S"): 3})

    assert ("in", "MAIN", "MAIN") in solution.values
    assert ("in", MAIN, "MAIN") not in solution.values


@pytest.mark.parametrize(
    "inputs",
    [("D",), (Need("D", "D"), "D"), ("D", Need("D", "D")), (("in", "D", "D"),), (None,)],
    ids=["plain-state", "need-then-plain", "plain-then-need", "product-state", "none"],
)
def test_a_plain_state_among_the_extra_inputs_raises_type_error(inputs):
    action = Action("combine", 1.0, ((GOAL, 1),), inputs)
    model = TabularModel({GOAL}, {"A": [action]})
    acquisition = Acquisition(model)

    with pytest.raises(TypeError, match="Need"):
        list(acquisition.actions(main_of("A")))
    with pytest.raises(TypeError):
        solve(acquisition, [acquisition.start("A")])


def test_a_model_with_a_need_keeps_labels_and_costs_in_the_product_actions():
    acquisition = Acquisition(base_model(NESTED))

    (action,) = acquisition.actions(("in", "A", "A0"))

    assert action == Action("make A", 2.0, ((("in", "A", "A"), 1),), (("in", "B", "B0"),))


def test_the_start_and_the_goal_test_of_the_product():
    model = base_model(NESTED)
    acquisition = Acquisition(model)

    assert acquisition.start("M") == ("in", MAIN, "M")
    assert acquisition.is_goal(main_of(GOAL))
    assert not acquisition.is_goal(main_of("M"))
    assert not acquisition.is_goal(main_of("A"))  # a wanted state is not a goal of the main target
    assert acquisition.is_goal(("in", "A", "A"))
    assert not acquisition.is_goal(("in", "A", "A0"))
    assert not acquisition.is_goal(("in", "A", GOAL))  # the base goal is not a goal of another copy


def test_the_want_predicate_is_a_keyword_only_option():
    with pytest.raises(TypeError):
        Acquisition(base_model(NESTED), at_least)


def test_main_is_one_object_that_copy_and_pickle_give_back():
    state = main_of("A")

    assert repr(MAIN) == "MAIN"
    assert MAIN != "MAIN"
    assert hash(MAIN) == hash(MAIN)
    assert copy.copy(MAIN) is MAIN
    assert copy.deepcopy(MAIN) is MAIN
    assert copy.deepcopy(state)[1] is MAIN
    assert copy.deepcopy(state) == state
    for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
        assert pickle.loads(pickle.dumps(MAIN, protocol)) is MAIN
        assert pickle.loads(pickle.dumps(state, protocol))[1] is MAIN


def test_need_is_a_frozen_value_with_start_then_want():
    need = Need("S", "T")

    assert (need.start, need.want) == ("S", "T")
    assert need == Need("S", "T")
    assert need != Need("T", "S")
    assert hash(need) == hash(Need("S", "T"))
    assert {need: 1}[Need("S", "T")] == 1
    assert pickle.loads(pickle.dumps(need)) == need
    assert copy.deepcopy(need) == need
    with pytest.raises(dataclasses.FrozenInstanceError):
        need.want = "U"


# --- seeded fuzz against the oracle ---------------------------------------------------------------

SEEDS = range(60)
SWEEPS = 5000
SLOW_SWEEPS = 200_000


def random_acquisition_spec(seed):
    """A seeded random base spec with Needs: 2-4 non-goal states `0..size-1`, the one goal is `size`.

    One or two wanted items (any state, the goal included), so the product has 2-3 copies. Each
    state is a dead end (6%) or has one or two actions of 1-3 weighted outcomes (any state) with
    0-2 needs `(start, want)`; a state with one action may also get a `buy` straight to the goal.
    """
    rng = random.Random(seed)
    size = rng.choice([2, 3, 3, 4])
    wants = rng.sample(range(size + 1), 1 if rng.random() < 0.7 else 2)
    p_need = rng.choice([0.3, 0.6, 0.9])
    p_buy = rng.choice([0.0, 0.3, 0.6])
    table = {}
    for s in range(size):
        if rng.random() < 0.06:
            table[s] = []
            continue
        rows = []
        for index in range(rng.randint(1, 2)):
            outcomes = [
                (rng.choice([*wants, size]) if rng.random() < 0.4 else rng.randint(0, size), rng.randint(1, 6))
                for _ in range(rng.randint(1, 3))
            ]
            needs = []
            while len(needs) < 2 and rng.random() < p_need:
                needs.append((rng.randint(0, size - 1), rng.choice(wants)))
            rows.append(row(f"{s}.{index}", Fraction(rng.randint(1, 12), 4), outcomes, needs))
        if len(rows) == 1 and rng.random() < p_buy:
            rows.append(row(f"{s}.buy", Fraction(rng.randint(20, 80), 4), [(size, 1)]))
        table[s] = rows
    return {size}, table


@functools.cache
def fuzz_spec(seed):
    return random_acquisition_spec(seed)


@functools.cache
def fuzz_product(seed):
    return product_spec(fuzz_spec(seed))


@functools.cache
def fuzz_optimum(seed):
    return brute_force_inputs(fuzz_product(seed))


def every_state_finite(best):
    return all(value is not None for value in best.values())


@functools.cache
def fuzz_solution(seed):
    """The solution with every product state a start; None when the solver cannot decide the instance."""
    model = Acquisition(base_model(fuzz_spec(seed)))
    starts = all_states(fuzz_product(seed))
    for sweeps in (SWEEPS, SLOW_SWEEPS):
        try:
            solution = solve(model, starts, max_sweeps=sweeps)
        except ConvergenceError:
            solution = None
        if solution is not None and solution.error_bound < math.inf:
            return solution
        if not every_state_finite(fuzz_optimum(seed)):
            return None  # an infinite state: the ceiling and pre-check of ticket #179 decide it
    pytest.fail(f"seed {seed}: every state is finite, yet the solver did not converge in {SLOW_SWEEPS} sweeps")


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_values_and_policy_equal_exact_brute_force_within_the_certified_bound(seed):
    solution = fuzz_solution(seed)
    if solution is None:
        pytest.skip("some state is infinite and the solver cannot decide it yet (ticket #179)")

    product = fuzz_product(seed)
    assert set(solution.values) == set(all_states(product))
    assert_matches_oracle(product, fuzz_optimum(seed), solution, max_error=1e-6)


# --- the fuzz contains what the ticket asks for ---------------------------------------------------


def needs_of(spec):
    """Every `(owner, (start, want))` of every action of a spec."""
    _, table = spec
    return [(s, need) for s, rows in table.items() for _, _, _, needs in rows for need in needs]


def reachable_from(table, start, stop):
    """The base states reached from `start` by outcomes, not going on from the state `stop`."""
    seen, stack = {start}, [start]
    while stack:
        s = stack.pop()
        if s == stop:
            continue
        for _, _, outcomes, _ in table.get(s, []):
            for t, w in outcomes:
                if w > 0 and t not in seen:
                    seen.add(t)
                    stack.append(t)
    return seen


def has_a_nested_need(spec, *, other_item=False):
    """A need whose acquisition process can run an action that itself has a need.

    With `other_item` the inner need must want something other than the outer one.
    """
    _, table = spec
    for _, (start, want) in needs_of(spec):
        for state in reachable_from(table, start, want) - {want}:
            for _, _, _, needs in table.get(state, []):
                if any(w != want or not other_item for _, w in needs):
                    return True
    return False


def policy_pays_for_a_need(spec, solution):
    """The returned policy takes an action with an input that is not a goal of its copy."""
    product_goals = fuzz_product_goals(spec)
    return solution is not None and any(
        any(y not in product_goals for y in action.extra_inputs) for action in solution.policy.values()
    )


def fuzz_product_goals(spec):
    return product_spec(spec)[0]


# feature -> (does the instance have it, the fewest instances of the 60 that must)
FEATURES = {
    "a need": (lambda spec, best, solution: bool(needs_of(spec)), 45),
    "a need whose start is its want": (
        lambda spec, best, solution: any(start == want for _, (start, want) in needs_of(spec)),
        10,
    ),
    "two wanted items": (lambda spec, best, solution: len(wants_of(spec)) == 2, 8),
    "a nested need": (lambda spec, best, solution: has_a_nested_need(spec), 20),
    "a nested need of another item": (
        lambda spec, best, solution: has_a_nested_need(spec, other_item=True),
        5,
    ),
    "a repeated need": (
        lambda spec, best, solution: any(
            len(needs) != len(set(needs)) for rows in spec[1].values() for _, _, _, needs in rows
        ),
        8,
    ),
    "the solver decides it": (lambda spec, best, solution: solution is not None, 45),
    "the solver decides it, with a need": (
        lambda spec, best, solution: solution is not None and bool(needs_of(spec)),
        35,
    ),
    "the solver decides it, with a nested need": (
        lambda spec, best, solution: solution is not None and has_a_nested_need(spec),
        20,
    ),
    "the solver decides it, and its policy pays for a need": (
        lambda spec, best, solution: policy_pays_for_a_need(spec, solution),
        1,
    ),
    "every product state finite": (lambda spec, best, solution: every_state_finite(best), 5),
    "an infinite product state": (lambda spec, best, solution: not every_state_finite(best), 20),
}


def test_the_fuzz_contains_the_cases_the_ticket_asks_for():
    counts = {
        name: sum(1 for seed in SEEDS if has(fuzz_spec(seed), fuzz_optimum(seed), fuzz_solution(seed)))
        for name, (has, _) in FEATURES.items()
    }
    print(counts)

    for name, count in counts.items():
        assert count >= FEATURES[name][1], f"{name}: {count} of {len(SEEDS)} instances"
