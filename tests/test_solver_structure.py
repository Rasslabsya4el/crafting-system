"""The solver on hand-solved structures: DAGs, resets, traps, dead ends, invariances."""

import math

import pytest
from ssp_helpers import DIRECT_LIMITS, GOAL, CountingModel, act, model

from crafting_system.solver import Action, TabularModel, solve

limits = pytest.mark.parametrize("limit", DIRECT_LIMITS.values(), ids=DIRECT_LIMITS.keys())


def test_a_chain_of_two_loops_adds_their_costs():
    table = {
        "A": [act("a", 3, ("A", 6), ("B", 1))],  # 3 / (1/7) = 21 to reach B
        "B": [act("b", 5, ("B", 4), (GOAL, 2))],  # 5 / (2/6) = 15 to reach the goal
    }

    solution = solve(model(table), ["A"])

    assert solution.values["B"] == 15.0
    assert solution.values["A"] == 36.0
    assert solution.error_bound <= 1e-12


def test_two_competing_loops_give_the_cheaper_one():
    table = {"A": [act("slow", 5, ("A", 8), (GOAL, 2)), act("fast", 3, ("A", 3), (GOAL, 1))]}
    # slow: 5 / (2/10) = 25 ; fast: 3 / (1/4) = 12

    solution = solve(model(table), ["A"])

    assert solution.values["A"] == 12.0
    assert solution.policy["A"].label == "fast"
    assert solution.error_bound <= 1e-12


def test_the_cheaper_loop_wins_even_when_it_is_listed_second_and_looks_dearer_per_try():
    table = {"A": [act("cheap-try", 1, ("A", 99), (GOAL, 1)), act("dear-try", 10, (GOAL, 1))]}
    # cheap-try: 1 / (1/100) = 100 ; dear-try: 10

    solution = solve(model(table), ["A"])

    assert solution.values["A"] == 10.0
    assert solution.policy["A"].label == "dear-try"


def test_a_stochastic_dag_is_solved_in_one_pass():
    table = {
        "S": [act("go", 1, ("A", 1), ("B", 1))],
        "A": [act("a", 2, (GOAL, 1))],
        "B": [act("b", 4, (GOAL, 1))],
    }

    solution = solve(model(table), ["S"])

    assert solution.values == {"S": 4.0, "A": 2.0, "B": 4.0, GOAL: 0.0}
    assert solution.error_bound <= 1e-12


@limits
def test_a_two_stage_reset_matches_the_hand_solved_two_by_two(limit):
    # V_A = 1 + V_B ; V_B = 2 + V_A / 2  ->  V_B = 5, V_A = 6
    table = {"A": [act("a", 1, ("B", 1))], "B": [act("b", 2, (GOAL, 1), ("A", 1))]}

    solution = solve(model(table), ["A"], direct_solve_limit=limit)

    assert solution.values["A"] == pytest.approx(6.0, rel=1e-9)
    assert solution.values["B"] == pytest.approx(5.0, rel=1e-9)
    assert abs(solution.values["A"] - 6.0) <= solution.error_bound * 6.0 + 1e-12


@limits
def test_a_cheap_looking_action_that_loops_forever_is_never_chosen(limit):
    table = {
        "S": [act("loop-out", 0.1, ("T", 1)), act("escape", 10, (GOAL, 1))],
        "T": [act("loop-back", 0.1, ("S", 1))],
    }

    solution = solve(model(table), ["S"], direct_solve_limit=limit)

    assert solution.values["S"] == pytest.approx(10.0, rel=1e-9)
    assert solution.policy["S"].label == "escape"
    assert solution.values["T"] == pytest.approx(10.1, rel=1e-9)


def test_a_state_with_no_route_to_a_goal_costs_infinity_and_has_no_policy():
    table = {"A": [act("a", 1, ("B", 1))], "B": [act("b", 1, ("A", 1))]}

    solution = solve(model(table), ["A"])

    assert solution.values == {"A": math.inf, "B": math.inf}
    assert solution.policy == {}


def test_a_state_with_only_a_self_repeating_action_costs_infinity():
    solution = solve(model({"A": [act("stuck", 1, ("A", 5))]}), ["A"])

    assert solution.values["A"] == math.inf
    assert "A" not in solution.policy


def test_an_action_that_can_fall_into_a_dead_end_is_never_chosen_and_taints_nothing():
    table = {
        "S": [act("risky", 1, (GOAL, 9), ("dead", 1)), act("safe", 5, (GOAL, 1))],
    }

    solution = solve(model(table), ["S"])

    assert solution.values["S"] == 5.0
    assert solution.values["dead"] == math.inf
    assert solution.policy["S"].label == "safe"
    assert not any(math.isnan(v) for v in solution.values.values())
    assert not math.isnan(solution.error_bound)


def test_a_dead_end_inside_a_cycle_does_not_make_the_cycle_infinite():
    table = {
        "A": [act("to-b", 1, ("B", 1)), act("finish", 20, (GOAL, 1))],
        "B": [act("back", 1, ("A", 3), ("dead", 1)), act("safe-back", 2, ("A", 1))],
    }

    solution = solve(model(table), ["A"])

    assert solution.values["A"] == 20.0
    assert solution.policy["A"].label == "finish"
    assert solution.values["B"] == 22.0
    assert solution.policy["B"].label == "safe-back"
    assert not any(math.isnan(v) for v in solution.values.values())


def test_a_start_that_is_a_goal_costs_zero():
    solution = solve(model({}), [GOAL])

    assert solution.values == {GOAL: 0.0}
    assert solution.policy == {}


def test_no_starts_give_an_empty_solution():
    solution = solve(model({}), [])

    assert solution.values == {}
    assert solution.policy == {}
    assert solution.error_bound == 0.0


@limits
def test_a_chain_of_nearly_certain_self_loops_agrees_between_ways_of_solving_components(limit):
    # each state repeats with chance 0.999999, moves on with 1 in a million, or resets to the start
    size = 5
    table = {
        i: [act("step", 1, (i, 999_998), (i + 1 if i + 1 < size else GOAL, 1), (0, 1))]
        for i in range(size)
    }

    solution = solve(model(table), [0], direct_solve_limit=limit)
    reference = solve(model(table), [0], direct_solve_limit=64)

    assert solution.values[0] == pytest.approx(reference.values[0], rel=1e-8)
    assert solution.values[0] > 1e6
    assert solution.error_bound <= 1e-8


def test_adding_an_action_never_raises_a_value_and_removing_one_never_lowers_it():
    base = {"A": [act("slow", 5, ("A", 8), (GOAL, 2))]}
    richer = {"A": [*base["A"], act("fast", 3, ("A", 3), (GOAL, 1))]}

    before = solve(model(base), ["A"]).values["A"]
    after = solve(model(richer), ["A"]).values["A"]

    assert after <= before
    assert after < before


def test_multiplying_every_cost_scales_every_value_and_keeps_the_policy():
    table = {
        "S": [act("a", 1, ("S", 1), ("T", 2)), act("b", 7, (GOAL, 1))],
        "T": [act("c", 2, ("S", 1), (GOAL, 3)), act("d", 1.5, ("T", 1), (GOAL, 1))],
    }
    scaled = {
        state: [Action(a.label, a.cost * 4, a.outcomes) for a in actions]
        for state, actions in table.items()
    }

    plain = solve(model(table), ["S"])
    larger = solve(model(scaled), ["S"])

    for state, value in plain.values.items():
        assert larger.values[state] == pytest.approx(4 * value, rel=1e-9)
    assert {s: a.label for s, a in plain.policy.items()} == {
        s: a.label for s, a in larger.policy.items()
    }


def test_raising_the_price_of_one_action_never_lowers_a_value():
    def build(price):
        return model(
            {
                "S": [act("a", price, ("S", 1), ("T", 2)), act("b", 7, (GOAL, 1))],
                "T": [act("c", 2, ("S", 1), (GOAL, 3))],
            }
        )

    values = [solve(build(price), ["S"]).values["S"] for price in (1, 2, 3, 6, 9)]

    assert values == sorted(values)


def test_splitting_an_outcome_into_two_identical_successors_changes_nothing():
    whole = {"S": [act("a", 2, ("S", 1), ("T", 6), (GOAL, 1))], "T": [act("b", 1, (GOAL, 2), ("S", 1))]}
    split = {
        "S": [act("a", 2, ("S", 1), ("T", 2), ("T", 4), (GOAL, 1))],
        "T": [act("b", 1, (GOAL, 1), (GOAL, 1), ("S", 1))],
    }

    one = solve(model(whole), ["S"])
    other = solve(model(split), ["S"])

    assert other.values["S"] == pytest.approx(one.values["S"], rel=1e-12)
    assert other.values["T"] == pytest.approx(one.values["T"], rel=1e-12)


def test_zero_weight_outcomes_are_ignored_and_their_states_not_explored():
    counting = CountingModel(model({"A": [act("a", 2, (GOAL, 1), ("never", 0))]}))

    solution = solve(counting, ["A"])

    assert solution.values == {"A": 2.0, GOAL: 0.0}
    assert "never" not in counting.action_calls
    assert "never" not in counting.goal_calls


def test_actions_are_asked_at_most_once_per_non_goal_state_and_never_for_a_goal():
    table = {
        "A": [act("a", 1, ("B", 1), ("A", 1)), act("a2", 1, ("C", 1))],
        "B": [act("b", 1, ("A", 1), (GOAL, 1))],
        "C": [act("c", 1, ("B", 1), (GOAL, 1))],
    }
    counting = CountingModel(model(table))

    solve(counting, ["A", "B", "A"])

    assert sorted(counting.action_calls) == ["A", "B", "C"]
    assert GOAL not in counting.action_calls


def test_states_may_be_tuples_frozensets_and_strings():
    start = (frozenset({"x", "y"}), "item")
    middle = frozenset({1, 2})
    table = {
        start: [act("go", 1, (middle, 1), (start, 1))],
        middle: [act("finish", 2, ("done", 1))],
    }

    solution = solve(TabularModel(["done"], table), [start])

    assert solution.values[start] == 2 * 1 + 2
    assert solution.values[middle] == 2.0
    assert solution.values["done"] == 0.0


def test_tabular_model_treats_a_state_missing_from_the_table_as_having_no_actions():
    tabular = TabularModel(["g"], {"a": [act("x", 1, ("g", 1))]})

    assert tabular.is_goal("g")
    assert not tabular.is_goal("a")
    assert len(tabular.actions("a")) == 1
    assert list(tabular.actions("unlisted")) == []
