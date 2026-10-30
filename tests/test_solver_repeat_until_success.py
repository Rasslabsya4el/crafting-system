"""A pure repeat-until-success loop costs exactly cost / p (ticket #17, research checklist)."""

import pytest

from crafting_system.solver import Action, TabularModel, solve

GOAL = "goal"


def loop(cost, goal_weight, self_weight, label="try"):
    """One state `A` whose single action reaches the goal or repeats itself."""
    return Action(label, cost, (("A", self_weight), (GOAL, goal_weight)))


def value_of_loop(cost, goal_weight, self_weight):
    model = TabularModel([GOAL], {"A": [loop(cost, goal_weight, self_weight)]})
    return solve(model, ["A"])


@pytest.mark.parametrize(
    ("cost", "goal_weight", "self_weight", "expected"),
    [
        (3, 1, 6, 21.0),
        (5, 2, 4, 15.0),
        (1, 1, 999_999, 1_000_000.0),
        (2.5, 1, 0, 2.5),
    ],
)
def test_a_repeat_until_success_loop_costs_exactly_cost_over_p(
    cost, goal_weight, self_weight, expected
):
    solution = value_of_loop(cost, goal_weight, self_weight)

    assert solution.values["A"] == expected
    assert solution.values[GOAL] == 0.0
    assert solution.error_bound <= 1e-12


def test_a_non_dyadic_cost_is_what_cost_over_p_rounds_to():
    solution = value_of_loop(0.1, 1, 2)

    assert solution.values["A"] == pytest.approx(0.1 * 3 / 1, rel=1e-15)
