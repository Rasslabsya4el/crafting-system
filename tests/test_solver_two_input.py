"""Actions with inputs (`Action.extra_inputs`, ADR-0022, ticket #178) against an exact oracle.

An input is a state whose value is paid on every attempt of the action, a retry after a self-loop
included; a repeated input is that many copies. The oracle (`ssp_input_oracles`) is exact brute
force over every stationary policy with the positive-solution rule of ADR-0022, independent of the
solver. This file has four parts:

* the oracle checked on its own, by hand (tests with `oracle` in their name run without the solver);
* hand cases with exact numbers, each compared with the oracle and with the number worked out here;
* a seeded fuzz of random instances against the oracle, values and returned policy;
* a coverage test that the fuzz really contains the cases the ticket asks for.

A supercritical component is declared infinite (by the mass-closed pre-check or the value ceiling,
ticket #179). The one case left undecided is a component critical through weights (rho exactly 1,
the mass leaking): `solve` reports it with `ConvergenceError`, never as a value. The fuzz does not
pin those instances, it counts them (as skips); `test_solver_branching.py` pins one by hand.
"""

import functools
import math
from fractions import Fraction

import pytest
from ssp_helpers import GOAL
from ssp_input_oracles import (
    brute_force_inputs,
    evaluate_policy_exactly,
    random_input_spec,
    to_model,
)

from crafting_system.solver import Action, ConvergenceError, solve


def entry(label, cost, outcomes, inputs=()):
    """A table row of a spec: `(label, cost, outcomes, inputs)` with an exact cost."""
    return (label, Fraction(cost), list(outcomes), list(inputs))


def spec_of(table):
    return {GOAL}, table


def agrees(value, optimum, error):
    """`value (1 - error) <= optimum <= value (1 + error)`, compared in exact fractions."""
    value, error = Fraction(value), Fraction(error)
    return value * (1 - error) <= optimum <= value * (1 + error)


def check(table, starts, expected, **options):
    """Solve a hand case; compare every value with the oracle and with the number worked out by hand.

    `expected` maps states to the exact value (None: infinite). Returns the solution.
    """
    spec = spec_of(table)
    best = brute_force_inputs(spec)
    solution = solve(to_model(spec), starts, **options)
    assert solution.error_bound <= 1e-9
    for state, optimum in best.items():
        value = solution.values[state]
        if optimum is None:
            assert value == math.inf, state
        else:
            assert agrees(value, optimum, solution.error_bound), state
    for state, literal in expected.items():
        assert best[state] == literal, f"oracle: {state}"
        if literal is None:
            assert solution.values[state] == math.inf, state
            assert state not in solution.policy, state
        else:
            assert solution.values[state] == pytest.approx(float(literal), rel=1e-9), state
    return solution


# --- the oracle on its own ------------------------------------------------------------------

ONE_DONOR = {
    # A retries with probability 3/4 and pays the donor on every attempt: 2 + 9 = 11 per attempt, 4 attempts
    "A": [entry("combine", 2, [(GOAL, 1), ("A", 3)], ["D"])],
    # D reaches the goal with probability 1/3 per try of cost 3
    "D": [entry("make", 3, [(GOAL, 1), ("D", 2)])],
}


def test_oracle_prices_the_retry_of_a_one_donor_action_again_each_attempt():
    best = brute_force_inputs(spec_of(ONE_DONOR))

    assert best == {"A": 44, "D": 9}


@pytest.mark.parametrize("inputs", [["A"], ["A", "A"]], ids=["one-copy", "two-copies"])
def test_oracle_says_a_state_that_needs_a_copy_of_itself_is_infinite(inputs):
    table = {"A": [entry("self", 1, [(GOAL, 1)], inputs)]}

    assert brute_force_inputs(spec_of(table)) == {"A": None}


TRAP = {
    # each reaches the goal with probability one, but A needs two B and B needs an A: rho = sqrt(2)
    "A": [entry("pair", 1, [(GOAL, 1)], ["B", "B"])],
    "B": [entry("back", 1, [(GOAL, 1)], ["A"])],
}


def test_oracle_says_a_two_state_trap_is_infinite_for_both_states():
    assert brute_force_inputs(spec_of(TRAP)) == {"A": None, "B": None}


@pytest.mark.parametrize(
    "table",
    [
        TRAP,
        {"A": [entry("a", 1, [(GOAL, 1)], ["B"])], "B": [entry("b", 1, [(GOAL, 1)], ["A"])]},
    ],
    ids=["rho-sqrt-2", "rho-1"],
)
def test_oracle_rejects_a_policy_with_rho_at_least_one_even_when_it_reaches_the_goal(table):
    spec = spec_of(table)

    assert evaluate_policy_exactly(spec, {"A": 0, "B": 0}, "A") is None
    assert evaluate_policy_exactly(spec, {"A": 0, "B": 0}, "B") is None


MUTUAL_BUT_SUBCRITICAL = {
    # A needs one B, B can lead back to A by outcome: M = [[0, 1], [1/4, 0]], rho = 1/2
    "A": [entry("need-b", 1, [(GOAL, 1)], ["B"])],
    "B": [entry("maybe-a", 1, [(GOAL, 3), ("A", 1)])],
}


def test_oracle_accepts_a_policy_with_rho_below_one_and_solves_it_exactly():
    # J(A) = 1 + J(B) and J(B) = 1 + J(A) / 4, so J(A) = 8 / 3 and J(B) = 5 / 3
    best = brute_force_inputs(spec_of(MUTUAL_BUT_SUBCRITICAL))

    assert best == {"A": Fraction(8, 3), "B": Fraction(5, 3)}


def test_oracle_takes_the_cheapest_policy_and_its_generator_is_deterministic():
    table = {"A": [entry("dear", 9, [(GOAL, 1)]), entry("cheap", 2, [(GOAL, 1)], ["A"]), entry("mid", 5, [(GOAL, 1)])]}

    assert brute_force_inputs(spec_of(table)) == {"A": 5}
    assert random_input_spec(7) == random_input_spec(7)


# --- hand cases -----------------------------------------------------------------------------


def test_a_donor_is_paid_again_on_every_retry_and_the_policy_keeps_the_inputs():
    solution = check(ONE_DONOR, ["A"], {"D": 9, "A": 44})

    offered = Action("combine", 2, ((GOAL, 1), ("A", 3)), extra_inputs=("D",))
    assert solution.policy["A"] == offered


@pytest.mark.parametrize(
    ("inputs", "value", "grouped"),
    [(["D", "D"], 19, ("D", "D")), (["D", "E", "D"], 21, ("D", "D", "E"))],
    ids=["two-copies", "interleaved"],
)
def test_duplicate_inputs_cost_one_donor_per_copy_and_come_back_grouped(inputs, value, grouped):
    table = {
        "A": [entry("combine", 1, [(GOAL, 1)], inputs)],
        "D": [entry("make", 3, [(GOAL, 1), ("D", 2)])],
        "E": [entry("make", 2, [(GOAL, 1)])],
    }

    solution = check(table, ["A", "D", "E"], {"D": 9, "E": 2, "A": value})

    assert solution.policy["A"].extra_inputs == grouped
    assert solution.policy["A"].outcomes == ((GOAL, 1),)


@pytest.mark.parametrize("inputs", [[], [GOAL], [GOAL, GOAL]], ids=["none", "goal", "two-goals"])
def test_a_goal_as_an_input_costs_nothing(inputs):
    table = {"A": [entry("try", 2, [(GOAL, 1), ("A", 1)], inputs)]}

    check(table, ["A"], {"A": 4})


def test_an_action_whose_input_is_its_own_state_is_never_chosen():
    table = {
        "A": [
            entry("combine", 1, [(GOAL, 1)], ["A"]),
            entry("buy", 10, [(GOAL, 1)]),
        ]
    }

    solution = check(table, ["A"], {"A": 10})

    assert solution.policy["A"].label == "buy"


def test_alone_an_action_whose_input_is_its_own_state_is_infinite():
    table = {"A": [entry("combine", 1, [(GOAL, 1), ("A", 1)], ["A"])]}

    check(table, ["A"], {"A": None})


DEAD_DONORS = {
    "no-actions": ({"X": []}, "X"),
    "own-input-dead": ({"Y": [entry("make", 1, [(GOAL, 1)], ["X"])], "X": []}, "Y"),
    "cannot-reach-the-goal": (
        {"Z": [entry("loop", 1, [("W", 1), ("Z", 1)])], "W": [entry("back", 1, [("Z", 1)])]},
        "Z",
    ),
    "chain-of-inputs": (
        {
            "D1": [entry("make", 1, [(GOAL, 1)], ["D2"])],
            "D2": [entry("make", 1, [(GOAL, 1)], ["D3"])],
            "D3": [],
        },
        "D1",
    ),
}


@pytest.mark.parametrize("dead", DEAD_DONORS.values(), ids=DEAD_DONORS.keys())
def test_an_action_with_a_dead_input_is_dead_and_so_is_its_owner(dead):
    donors, first = dead
    table = {**donors, "A": [entry("combine", 1, [(GOAL, 1)], [first])]}

    check(table, ["A"], dict.fromkeys(table))


@pytest.mark.parametrize("dead", DEAD_DONORS.values(), ids=DEAD_DONORS.keys())
def test_the_owner_of_a_dead_input_falls_back_to_another_action(dead):
    donors, first = dead
    table = {
        **donors,
        "A": [entry("combine", 1, [(GOAL, 1)], [first]), entry("buy", 10, [(GOAL, 1)])],
    }

    solution = check(table, ["A"], {**dict.fromkeys(donors), "A": 10})

    assert solution.policy["A"].label == "buy"


def test_goal_reach_counts_outcomes_only_not_the_inputs():
    # A's only outcome is a dead end; the donor it takes reaches the goal, which does not help A
    table = {
        "A": [entry("combine", 1, [("DEAD", 1)], ["D"])],
        "D": [entry("make", 3, [(GOAL, 1), ("D", 2)])],
        "DEAD": [],
    }

    check(table, ["A"], {"A": None, "DEAD": None, "D": 9})


def test_an_input_that_no_outcome_reaches_is_still_explored_and_has_a_value():
    table = {
        "A": [entry("combine", 1, [(GOAL, 1)], ["D"])],
        "D": [entry("make", 3, [(GOAL, 1), ("D", 2)])],
    }

    solution = check(table, ["A"], {"A": 10, "D": 9})

    assert solution.values["D"] == pytest.approx(9.0, rel=1e-9)


def test_two_donors_that_need_each_other_buy_when_buying_is_cheaper():
    table = {
        "A": [entry("combine", 1, [(GOAL, 1)], ["B"]), entry("buy", 10, [(GOAL, 1)])],
        "B": [entry("combine", 1, [(GOAL, 1)], ["A"]), entry("buy", 10, [(GOAL, 1)])],
    }

    solution = check(table, ["A"], {"A": 10, "B": 10})

    assert solution.policy["A"].label == solution.policy["B"].label == "buy"


def test_two_donors_that_need_each_other_with_one_buy_option_between_them():
    # V(B) = min(10, 1 + V(A)) with V(A) = 1 + V(B): B buys, and A pays for B
    table = {
        "A": [entry("combine", 1, [(GOAL, 1)], ["B"])],
        "B": [entry("combine", 1, [(GOAL, 1)], ["A"]), entry("buy", 10, [(GOAL, 1)])],
    }

    solution = check(table, ["A"], {"A": 11, "B": 10})

    assert solution.policy["B"].label == "buy"
    assert solution.policy["A"].label == "combine"


def test_an_input_that_leads_back_by_outcome_is_priced_through_the_cycle():
    check(MUTUAL_BUT_SUBCRITICAL, ["A"], {"A": Fraction(8, 3), "B": Fraction(5, 3)})


def test_a_cyclic_outcome_component_whose_action_takes_an_outside_input():
    # C costs 9. J(A) = 1 + 9 + J(B) / 2 and J(B) = 2 + 2 J(A) / 3 (A pays C again after each visit)
    table = {
        "A": [entry("go", 1, [("B", 1), (GOAL, 1)], ["C"])],
        "B": [entry("back", 2, [("A", 2), (GOAL, 1)])],
        "C": [entry("make", 3, [(GOAL, 1), ("C", 2)])],
    }

    check(table, ["A"], {"A": Fraction(33, 2), "B": 13, "C": 9})


@pytest.mark.parametrize(
    "table",
    [
        ONE_DONOR,
        {
            "A": [entry("go", 1, [("B", 1), (GOAL, 1)], ["C"])],
            "B": [entry("back", 2, [("A", 2), (GOAL, 1)])],
            "C": [entry("make", 3, [(GOAL, 1), ("C", 2)])],
        },
    ],
    ids=["one-donor", "cycle-with-outside-input"],
)
def test_a_donor_has_the_same_value_alone_as_inside_the_bigger_model(table):
    donor = "D" if "D" in table else "C"

    alone = solve(to_model(spec_of(table)), [donor])
    inside = solve(to_model(spec_of(table)), ["A"])

    assert alone.values[donor] == pytest.approx(9.0, rel=1e-12)
    assert inside.values[donor] == pytest.approx(alone.values[donor], rel=1e-12)


# --- seeded fuzz against the oracle ---------------------------------------------------------

SEEDS = range(300)
SWEEPS = 5000
SLOW_SWEEPS = 200_000


@functools.cache
def fuzz_spec(seed):
    return random_input_spec(seed)


@functools.cache
def fuzz_optimum(seed):
    return brute_force_inputs(fuzz_spec(seed))


def solve_every_state(spec, max_sweeps):
    goals, table = spec
    return solve(to_model(spec), [*table, *goals], max_sweeps=max_sweeps)


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_values_and_policy_equal_exact_brute_force_within_the_certified_bound(seed):
    spec, best = fuzz_spec(seed), fuzz_optimum(seed)
    _, table = spec
    try:
        solution = solve_every_state(spec, SWEEPS)
        undecided = solution.error_bound == math.inf
    except ConvergenceError:
        undecided = True
    if undecided and not every_state_finite(best):
        pytest.skip("a component critical through weights: reported unresolved, never pinned")
    if undecided:  # every state is finite, so this is a slow near-critical instance: it must succeed
        solution = solve_every_state(spec, SLOW_SWEEPS)
    error = solution.error_bound

    finite = set()
    for state, optimum in best.items():
        value = solution.values[state]
        if value == math.inf:
            assert optimum is None, f"state {state}: the solver says infinite, the oracle {optimum}"
        else:
            assert optimum is not None, f"state {state}: the solver says {value}, the oracle infinite"
            assert agrees(value, optimum, error), f"state {state}: {value} against {float(optimum)}"
            finite.add(state)

    # the policy: label back to the index of the action in the spec, then evaluated exactly
    index = {(s, row[0]): i for s, rows in table.items() for i, row in enumerate(rows)}
    choice = {s: index[(s, action.label)] for s, action in solution.policy.items()}
    assert set(choice) == finite
    memo = {}
    for state in finite:
        attained = evaluate_policy_exactly(spec, choice, state, memo)
        assert attained is not None, f"state {state}: the returned policy has an infinite value"
        assert best[state] <= attained <= Fraction(solution.values[state]) * (1 + Fraction(error)), state


# --- the fuzz contains what the ticket asks for ---------------------------------------------


def inputs_of(table):
    """Every `(owner, inputs)` of every action of a spec."""
    return [(s, row[3]) for s, rows in table.items() for row in rows]


def has_a_mutual_input_pair(spec):
    """An input edge `s -> y` inside a strongly connected set: `y != s` and `y` reaches `s` again."""
    goals, table = spec
    out = {s: set() for s in table}
    for s, rows in table.items():
        for _, _, outcomes, inputs in rows:
            out[s] |= {t for t, w in outcomes if w > 0 and t in table}
            out[s] |= {y for y in inputs if y in table}

    def reaches(start, target):
        seen, stack = set(), [start]
        while stack:
            for t in out[stack.pop()]:
                if t == target:
                    return True
                if t not in seen:
                    seen.add(t)
                    stack.append(t)
        return False

    return any(y != s and reaches(y, s) for s, inputs in inputs_of(table) for y in inputs if y in table)


def every_state_finite(best):
    return all(value is not None for value in best.values())


# feature -> (does the instance have it, the fewest instances of the 300 that must)
FEATURES = {
    "goal as an input": (
        lambda spec, best: any(y in spec[0] for _, ys in inputs_of(spec[1]) for y in ys),
        100,
    ),
    "own state as an input": (lambda spec, best: any(s in ys for s, ys in inputs_of(spec[1])), 100),
    "duplicate inputs": (
        lambda spec, best: any(len(set(ys)) < len(ys) for _, ys in inputs_of(spec[1])),
        100,
    ),
    "infinite input": (
        lambda spec, best: any(best.get(y, 1) is None for _, ys in inputs_of(spec[1]) for y in ys),
        100,
    ),
    "retry that pays an input again": (
        lambda spec, best: any(
            s in {t for t, w in outcomes if w > 0} and any(y not in spec[0] for y in ys)
            for s, rows in spec[1].items()
            for _, _, outcomes, ys in rows
        ),
        150,
    ),
    "mutual input pair": (lambda spec, best: has_a_mutual_input_pair(spec), 200),
    "mutual input pair, every state finite": (
        lambda spec, best: has_a_mutual_input_pair(spec) and every_state_finite(best),
        60,
    ),
    "every state finite": (lambda spec, best: every_state_finite(best), 100),
}


def test_the_fuzz_contains_the_cases_the_ticket_asks_for():
    counts = {
        name: sum(1 for seed in SEEDS if has(fuzz_spec(seed), fuzz_optimum(seed)))
        for name, (has, _) in FEATURES.items()
    }
    print(counts)

    for name, count in counts.items():
        assert count >= FEATURES[name][1], f"{name}: {count} of {len(SEEDS)} instances"


def test_a_supercritical_branching_component_is_declared_infinite_not_returned():
    # A needs two B and B needs an A: both reach the goal by outcome, but the policy costs infinity
    # (rho > 1). Both are infinite and neither has a policy.
    table = {
        "A": [entry("two", 1, [(GOAL, 1)], ["B", "B"])],
        "B": [entry("one", 1, [(GOAL, 1)], ["A"])],
    }
    assert brute_force_inputs(spec_of(table)) == {"A": None, "B": None}

    solution = solve(to_model(spec_of(table)), ["A"], max_sweeps=5000)

    assert solution.values["A"] == solution.values["B"] == math.inf
    assert solution.values[GOAL] == 0.0
    assert solution.policy == {}


def test_a_component_critical_through_weights_is_reported_unresolved_not_returned():
    # A pays B once, with a self-loop of weight 4 that makes the retry pay it 5 times over (kappa 5);
    # B leads back to A with probability 1/5: M = [[0, 5], [1/5, 0]], rho = 1 exactly. The mass does
    # not close (B leaks) and the iterate grows linearly, so neither the pre-check nor the ceiling
    # decides it: the oracle says infinite, the solver says it could not decide.
    table = {
        "A": [entry("pay-b", 1, [(GOAL, 1), ("A", 4)], ["B"])],
        "B": [entry("back", 1, [(GOAL, 4), ("A", 1)])],
    }
    assert brute_force_inputs(spec_of(table)) == {"A": None, "B": None}

    with pytest.raises(ConvergenceError) as raised:
        solve(to_model(spec_of(table)), ["A"], max_sweeps=5000)

    assert raised.value.error_bound == math.inf
    assert "a component of 2 states" in str(raised.value)
    assert "'A'" in str(raised.value) and "'B'" in str(raised.value)
