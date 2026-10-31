"""The solver's compact storage (#126): the policy's actions are rebuilt from flat arrays.

`solve` no longer keeps the caller's `Action` objects (about 100 bytes per transition), so the policy
action is rebuilt from the stored weights. These tests check it is the offered action, down to the
position of the self-loop and weights that do not fit 64 bits. No test asserts on memory or time
(ADR-0014); the table of both is in the pull request.
"""

import pytest
from ssp_helpers import GOAL, act, model

from crafting_system.solver import Action, Outcome, solve
from crafting_system.solver._graph import build_graph

HUGE = 10**40  # does not fit an unsigned 64-bit integer


@pytest.mark.parametrize(
    "outcomes",
    [
        (("A", 3), ("B", 2), (GOAL, 1)),  # self-loop first
        (("B", 2), ("A", 3), (GOAL, 1)),  # in the middle
        (("B", 2), (GOAL, 1), ("A", 3)),  # last
        (("B", 2), (GOAL, 1)),  # none
        (("A", HUGE), ("B", 2 * HUGE), (GOAL, 1)),  # weights beyond 64 bits
        (("B", 2**64 - 1), (GOAL, 2**64), ("A", 5)),  # on both sides of the limit
    ],
)
def test_the_policy_action_is_the_offered_action(outcomes):
    offered = act("go", 2.5, *outcomes)
    table = {"A": [offered], "B": [act("end", 1, (GOAL, 1))]}

    solution = solve(model(table), ["A"])

    assert solution.policy["A"] == offered
    assert all(type(o.weight) is int for o in solution.policy["A"].outcomes)


def test_repeated_successors_are_merged_and_zero_weights_dropped():
    offered = Action("go", 1.0, (Outcome("B", 1), Outcome("A", 2), Outcome("B", 4), Outcome(GOAL, 0), Outcome(GOAL, 3)))
    table = {"A": [offered], "B": [act("end", 1, (GOAL, 1))]}

    solution = solve(model(table), ["A"])

    assert solution.policy["A"].outcomes == (Outcome("B", 5), Outcome("A", 2), Outcome(GOAL, 3))
    assert solution.policy["A"].cost == 1.0 and solution.policy["A"].label == "go"


def test_the_policy_keeps_the_original_cost_not_the_effective_one():
    table = {"A": [act("go", 3, ("A", 6), (GOAL, 1))]}  # effective cost 21

    solution = solve(model(table), ["A"])

    assert solution.values["A"] == 21.0
    assert solution.policy["A"].cost == 3.0


def test_each_state_gets_its_own_action_when_labels_repeat():
    table = {
        "A": [act("go", 1, ("B", 1), (GOAL, 1)), act("alt", 9, (GOAL, 1))],
        "B": [act("go", 1, (GOAL, 3), ("A", 1))],
    }

    solution = solve(model(table), ["A"])

    assert solution.policy["A"] == table["A"][0]
    assert solution.policy["B"] == table["B"][0]


def test_the_flat_graph_lists_each_action_and_its_successors_in_order():
    table = {
        "A": [act("a1", 1, ("A", 1), ("B", 2), ("C", 3)), act("a2", 1, ("C", 1))],
        "B": [act("b1", 1, ("A", 1), (GOAL, 1))],
        "C": [],
    }

    graph = build_graph(model(table), ["A"])

    assert graph.states == ["A", "B", "C", GOAL]
    assert [list(graph.state_actions[s]) for s in range(4)] == [[0, 1], [2], [], []]
    assert [list(graph.succ[k]) for k in range(len(graph.owner))] == [[1, 2], [2], [0, 3]]
    assert list(graph.owner) == [0, 0, 1]
    assert len(graph.succ) == len(graph.owner) == 3
    assert graph.original_action(0) == table["A"][0]
