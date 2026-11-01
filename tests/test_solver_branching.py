"""Branching components (an input inside the component), ADR-0022, ticket #179.

Policy iteration, the value ceiling and the local re-solve.

Every case with an exact answer is checked against the number worked out here; the instances small
enough for it also against the brute-force oracle of `ssp_input_oracles`, which shares no code with
the solver.
"""

import math
from fractions import Fraction
from types import SimpleNamespace

import pytest
from ssp_helpers import GOAL
from ssp_input_oracles import brute_force_inputs, to_model

from crafting_system.solver import ConvergenceError, solve
from crafting_system.solver import _component, _solve
from crafting_system.solver._component import build_bellman
from crafting_system.solver._graph import build_graph, proper_states


def entry(label, cost, outcomes, inputs=()):
    """A table row of a spec: `(label, cost, outcomes, inputs)` with an exact cost."""
    return (label, Fraction(cost), list(outcomes), list(inputs))


def spec_of(table):
    return {GOAL}, table


def solve_table(table, starts, **options):
    return solve(to_model(spec_of(table)), starts, **options)


# --- hand cases -----------------------------------------------------------------------------


def test_two_donors_that_need_each_other_buy_where_buying_is_cheaper():
    # X = min(10, 1 + Y) and Y = min(8, 1 + X): Y buys at 8, and X pays for Y: 9
    table = {
        "X": [entry("combine", 1, [(GOAL, 1)], ["Y"]), entry("buy", 10, [(GOAL, 1)])],
        "Y": [entry("combine", 1, [(GOAL, 1)], ["X"]), entry("buy", 8, [(GOAL, 1)])],
    }

    solution = solve_table(table, ["X"])

    assert brute_force_inputs(spec_of(table)) == {"X": 9, "Y": 8}
    assert solution.values["X"] == pytest.approx(9.0, rel=1e-12)
    assert solution.values["Y"] == pytest.approx(8.0, rel=1e-12)
    assert solution.policy["X"].label == "combine"
    assert solution.policy["Y"].label == "buy"


TRAP = {
    # each reaches the goal with probability one, but A needs two B and B needs an A: rho = sqrt(2)
    "A": [entry("pair", 1, [(GOAL, 1)], ["B", "B"])],
    "B": [entry("back", 1, [(GOAL, 1)], ["A"])],
}


def test_a_state_that_needs_two_copies_of_itself_through_a_pair_is_infinite():
    solution = solve_table(TRAP, ["A"])

    assert solution.values["A"] == solution.values["B"] == math.inf
    assert solution.values[GOAL] == 0.0
    assert "A" not in solution.policy and "B" not in solution.policy


def test_a_state_that_can_still_buy_is_finite_beside_the_pair():
    table = {
        **TRAP,
        "Z": [entry("use-a", 1, [(GOAL, 1)], ["A"]), entry("buy", 5, [(GOAL, 1)])],
    }
    assert brute_force_inputs(spec_of(table)) == {"A": None, "B": None, "Z": 5}

    solution = solve_table(table, ["Z"])

    assert solution.values["Z"] == pytest.approx(5.0, rel=1e-12)
    assert solution.values["A"] == solution.values["B"] == math.inf
    assert set(solution.policy) == {"Z"}
    assert solution.policy["Z"].label == "buy"


def test_a_pair_with_a_buy_option_in_one_state_is_finite_in_both():
    # A = min(1 + 2 B, 7) and B = 1 + A: A buys at 7 and B pays 8; the pair policy is supercritical
    table = {
        "A": [entry("pair", 1, [(GOAL, 1)], ["B", "B"]), entry("buy", 7, [(GOAL, 1)])],
        "B": [entry("back", 1, [(GOAL, 1)], ["A"])],
    }
    assert brute_force_inputs(spec_of(table)) == {"A": 7, "B": 8}

    solution = solve_table(table, ["A"])

    assert solution.values["A"] == pytest.approx(7.0, rel=1e-12)
    assert solution.values["B"] == pytest.approx(8.0, rel=1e-12)
    assert solution.policy["A"].label == "buy"


def near_critical(p_num, p_den):
    """X = 1 + Y and Y = 1 + p X with p = p_num / p_den: one input edge inside, rho = sqrt(p)."""
    return {
        "X": [entry("need-y", 1, [(GOAL, 1)], ["Y"])],
        "Y": [entry("maybe-x", 1, [("X", p_num), (GOAL, p_den - p_num)])],
    }


@pytest.fixture
def sweeps_counted(monkeypatch):
    """The number of certificate checks (one per sweep, one per policy-iteration result)."""
    calls = []
    real = _component._certify

    def counting(bellman, values):
        calls.append(len(values))
        return real(bellman, values)

    monkeypatch.setattr(_component, "_certify", counting)
    return calls


def test_a_near_critical_component_finishes_in_a_few_thousand_sweeps(sweeps_counted):
    # rho = sqrt(0.9998) = 0.9999: V_Y = (1 + p) / (1 - p) = 9999 and V_X = 10000, exactly
    table = near_critical(9998, 10000)

    solution = solve_table(table, ["X"], max_sweeps=5000)

    assert solution.values["X"] == pytest.approx(10000.0, rel=1e-9)
    assert solution.values["Y"] == pytest.approx(9999.0, rel=1e-9)
    assert solution.error_bound <= 1e-9
    assert len(sweeps_counted) <= 5000


def test_the_same_component_by_value_iteration_alone_does_not_finish_in_that_many_sweeps():
    with pytest.raises(ConvergenceError):
        solve_table(near_critical(9998, 10000), ["X"], max_sweeps=5000, direct_solve_limit=0)


def test_the_error_text_names_the_first_three_states_cut_to_sixty_characters_and_counts_the_rest():
    long = "x" * 100
    graph = SimpleNamespace(states=[long + str(i) for i in range(5)])

    message = _solve._describe(graph, [0, 1, 2, 3, 4])

    assert message.startswith("a component of 5 states (")
    assert message.endswith(" and 2 more)")
    assert message.count("...") == 3
    assert repr(long + "0")[:57] + "..." in message
    cut = [repr(long + str(i))[:57] + "..." for i in range(2)]
    assert _solve._describe(graph, [0, 1]) == f"a component of 2 states ({cut[0]}, {cut[1]})"
    short = SimpleNamespace(states=["a", "b"])
    assert _solve._describe(short, [0, 1]) == "a component of 2 states ('a', 'b')"


# --- solving a component alone is solving it inside the whole -------------------------------

RING = {
    "X": [entry("a", 1, [(GOAL, 1)], ["Y"]), entry("buy", 10, [(GOAL, 1)])],
    "Y": [entry("a", 1, [(GOAL, 1), ("X", 1)], ["Z"]), entry("buy", 12, [(GOAL, 1)])],
    "Z": [entry("a", 1, [(GOAL, 2), ("Y", 1)], ["X"]), entry("buy", 7, [(GOAL, 1)])],
    "T": [entry("use", 2, [(GOAL, 1), ("T", 1)], ["X"])],
}


@pytest.fixture
def eliminate_early(monkeypatch):
    """Sparse policy iteration at the first certificate instead of after 300 sweeps."""
    monkeypatch.setattr(_component, "SWEEPS_BEFORE_DIRECT", 1)


@pytest.mark.parametrize("limit", [0, 64, 1], ids=["sweeps-only", "default", "sparse"])
def test_a_donor_ring_has_the_same_values_alone_and_inside_the_whole(limit, eliminate_early):
    best = brute_force_inputs(spec_of(RING))
    alone = solve_table(RING, ["X"], direct_solve_limit=limit)
    inside = solve_table(RING, ["T"], direct_solve_limit=limit)

    for state in "XYZ":
        assert alone.values[state] == pytest.approx(float(best[state]), rel=1e-9)
        assert inside.values[state] == pytest.approx(alone.values[state], rel=1e-12)
        assert inside.policy[state] == alone.policy[state]
    assert inside.values["T"] == pytest.approx(float(best["T"]), rel=1e-9)
    assert alone.error_bound <= 1e-9 and inside.error_bound <= 1e-9


def test_the_ways_of_solving_a_branching_component_agree(eliminate_early):
    sweeps = solve_table(RING, ["T"], direct_solve_limit=0)
    dense = solve_table(RING, ["T"])
    sparse = solve_table(RING, ["T"], direct_solve_limit=1)

    for state in RING:
        assert dense.values[state] == pytest.approx(sweeps.values[state], rel=1e-9)
        assert sparse.values[state] == pytest.approx(sweeps.values[state], rel=1e-9)


# --- sparse policy iteration on a large branching component --------------------------------


def stiff_belt(length):
    """A belt of `length` states that restarts at the first with chance 1 in 20 per step (1 in 10 at the
    end), each state taking a helper as an input; the helpers are in the same component because a
    helper falls back to the first state of the belt half of the time: 2 * `length` states, one
    branching component, and the walk back to the start makes it stiff."""
    table = {}
    for i in range(length):
        last = i == length - 1
        move = (GOAL, 1) if last else (i + 1, 19)
        table[i] = [entry("walk", 1, [move, (0, 9 if last else 1)], [("help", i)])]
        table[("help", i)] = [entry("help", 1, [(GOAL, 10**7), (0, 1)])]
    return table


def test_sparse_policy_iteration_on_a_branching_belt_of_120_states_agrees_with_the_other_ways(
    monkeypatch, eliminate_early
):
    table = stiff_belt(60)
    sparse_calls, dense_calls = [], []
    sparse_real, dense_real = _component._evaluate_sparse, _component._evaluate

    def sparse_counting(bellman, policy, work_limit=_component.WORK_LIMIT):
        sparse_calls.append(len(policy))
        return sparse_real(bellman, policy, work_limit)

    def dense_counting(bellman, policy):
        dense_calls.append(len(policy))
        return dense_real(bellman, policy)

    monkeypatch.setattr(_component, "_evaluate_sparse", sparse_counting)
    monkeypatch.setattr(_component, "_evaluate", dense_counting)

    swept = solve_table(table, [0], direct_solve_limit=0)
    assert sparse_calls == [] and dense_calls == []
    dense = solve_table(table, [0], direct_solve_limit=10**9)
    assert dense_calls and sparse_calls == []
    sparse = solve_table(table, [0], direct_solve_limit=64)

    assert sparse_calls and set(sparse_calls) == {120}
    for solution in (swept, dense, sparse):
        assert solution.error_bound <= 1e-8
    for state in table:
        assert sparse.values[state] == pytest.approx(swept.values[state], rel=1e-9)
        assert dense.values[state] == pytest.approx(swept.values[state], rel=1e-9)


def test_the_elimination_not_the_sweeps_finishes_a_branching_belt(eliminate_early):
    # the sweeps alone need about 5000 sweeps; with 3000 only an exact evaluation can finish it
    table = stiff_belt(60)
    with pytest.raises(ConvergenceError):
        solve_table(table, [0], direct_solve_limit=0, max_sweeps=3000)

    solution = solve_table(table, [0], direct_solve_limit=64, max_sweeps=3000)

    assert solution.error_bound <= 1e-8
    assert solution.values[0] == pytest.approx(7871.450534126549, rel=1e-9)


def test_the_sparse_evaluation_of_a_branching_policy_equals_the_dense_one():
    # the leak of a branching row is negative (outside probability minus the kappa of its input)
    graph = build_graph(to_model(spec_of(stiff_belt(5))), [0])
    alive, _ = proper_states(graph)
    component = [s for s in range(len(graph.states)) if not graph.goal[s]]
    ones, zeros = [1.0] * len(graph.states), [0.0] * len(graph.states)  # the goal is the only outside state
    bellman = build_bellman(graph, alive, component, zeros, ones, ones)
    policy = [bellman.astart[local] for local in range(len(component))]
    assert bellman.branching and min(bellman.leak) < 0.0

    dense, sparse = _component._evaluate(bellman, policy), _component._evaluate_sparse(bellman, policy)

    assert dense is not None and sparse is not None
    assert sparse == pytest.approx(dense, rel=1e-12)


# --- the ceiling ----------------------------------------------------------------------------

# X costs 1e13 once Y is paid; Y has a cheap action of its own: X and Y are one branching component
DEAR = {
    "X": [entry("dear", 10**13, [(GOAL, 1)], ["Y"])],
    "Y": [entry("lean-on-x", 1, [(GOAL, 1)], ["X"]), entry("cheap", 1, [(GOAL, 1)])],
    # U can use X, or buy at 1e14: the ceiling kills X, so U buys
    "U": [entry("use-x", 1, [(GOAL, 1)], ["X"]), entry("buy", 10**14, [(GOAL, 1)])],
}


def test_a_state_over_the_ceiling_is_dead_and_its_user_falls_back():
    solution = solve_table(DEAR, ["U"])

    assert solution.values["X"] == math.inf
    assert "X" not in solution.policy
    assert solution.values["Y"] == pytest.approx(1.0, rel=1e-12)
    assert solution.policy["Y"].label == "cheap"
    assert solution.values["U"] == pytest.approx(1e14, rel=1e-12)
    assert solution.policy["U"].label == "buy"


def test_without_a_ceiling_the_dear_state_is_finite():
    solution = solve_table(DEAR, ["U"], value_ceiling=math.inf)

    assert solution.values["X"] == pytest.approx(1e13 + 1, rel=1e-12)
    assert solution.values["U"] == pytest.approx(1e13 + 2, rel=1e-12)
    assert solution.policy["U"].label == "use-x"


def test_a_higher_ceiling_keeps_what_it_lets_through():
    solution = solve_table(DEAR, ["U"], value_ceiling=1e13 + 1.5)

    assert solution.values["X"] == pytest.approx(1e13 + 1, rel=1e-12)
    assert solution.values["U"] == pytest.approx(1e13 + 2, rel=1e-12)


def test_a_supercritical_component_is_declared_dead_by_the_ceiling_alone():
    # A needs two B, B comes back to A with probability 3/4: rho = sqrt(1.5); the mass is not closed
    table = {
        "A": [entry("pair", 1, [(GOAL, 1)], ["B", "B"])],
        "B": [entry("back", 1, [("A", 3), (GOAL, 1)])],
    }
    assert brute_force_inputs(spec_of(table)) == {"A": None, "B": None}

    solution = solve_table(table, ["A"])

    assert solution.values["A"] == solution.values["B"] == math.inf
    assert solution.policy == {}


def test_a_supercritical_component_without_a_ceiling_is_unresolved_not_returned():
    table = {
        "A": [entry("pair", 1, [(GOAL, 1)], ["B", "B"])],
        "B": [entry("back", 1, [("A", 3), (GOAL, 1)])],
    }

    with pytest.raises(ConvergenceError) as raised:
        solve_table(table, ["A"], value_ceiling=math.inf, max_sweeps=500)

    assert raised.value.error_bound == math.inf


@pytest.mark.parametrize("bad", [0, -1, 0.0, -math.inf, math.nan, True, False, None, "1e12", [1.0]])
def test_a_ceiling_that_is_not_a_real_above_zero_is_refused(bad):
    with pytest.raises(ValueError, match="value_ceiling"):
        solve_table(DEAR, ["U"], value_ceiling=bad)


@pytest.mark.parametrize("good", [1e12, 5, math.inf, Fraction(10**20)])
def test_a_ceiling_that_is_a_real_above_zero_is_accepted(good):
    assert solve_table(DEAR, ["Y"], value_ceiling=good).values["Y"] == pytest.approx(1.0)


# --- the local re-solve ----------------------------------------------------------------------


def test_a_ceiling_restart_does_not_solve_a_finished_component_again(monkeypatch):
    # H1 and H2 are a heavy cyclic component downstream of {X, Y, W}; X is dear, so that component
    # is solved, X dies, and {Y, W} is solved again. Starts fix the state numbers: X0 Y1 W2 H1 3 H2 4.
    table = {
        "X": [entry("dear", 10**13, [(GOAL, 1)], ["Y"])],
        "Y": [
            entry("lean-on-x", 1, [(GOAL, 1), ("W", 1)], ["X"]),
            entry("direct", 1, [(GOAL, 1), ("W", 1)]),
        ],
        "W": [entry("go", 1, [(GOAL, 1), ("Y", 1)], ["H1"])],
        "H1": [entry("a", 1, [(GOAL, 1), ("H2", 1)])],
        "H2": [entry("a", 1, [(GOAL, 1), ("H1", 1)])],
    }
    calls = []
    real = _solve.solve_cyclic

    def recording(bellman, *args, **options):
        calls.append(tuple(sorted(bellman.states)))
        return real(bellman, *args, **options)

    monkeypatch.setattr(_solve, "solve_cyclic", recording)

    solution = solve_table(table, ["X", "Y", "W", "H1", "H2"])

    assert calls.count((3, 4)) == 1  # the finished component, once
    assert calls.count((0, 1, 2)) == 1  # the diverged one, once
    assert calls.count((1, 2)) == 1  # what is left of it
    assert len(calls) == 3
    # H = 2; Y = 1 + W / 2 and W = 1 + 2 + Y / 2 give Y = 10 / 3 and W = 14 / 3
    assert solution.values["H1"] == pytest.approx(2.0, rel=1e-9)
    assert solution.values["Y"] == pytest.approx(10 / 3, rel=1e-9)
    assert solution.values["W"] == pytest.approx(14 / 3, rel=1e-9)
    assert solution.values["X"] == math.inf
    assert "X" not in solution.policy
    assert solution.policy["Y"].label == "direct"
