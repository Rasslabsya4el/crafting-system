"""The chance that a policy ever visits each state, against closed forms."""

import pytest

from crafting_system.cli._reach import MAX_TRANSIENT, policy_states, reach_probabilities
from crafting_system.solver import Action, Outcome


def action(*outcomes):
    return Action("a", 1.0, tuple(Outcome(state, weight) for state, weight in outcomes))


def is_goal(state):
    return state == "goal"


def test_a_state_behind_a_self_loop_is_reached_with_the_chance_of_leaving_that_way():
    # S: stay 1/2, to T 1/4, goal 1/4. Leaving S goes to T or goal with equal chance. T: back to S 1/2, goal 1/2.
    policy = {"S": action(("S", 2), ("T", 1), ("goal", 1)), "T": action(("S", 1), ("goal", 1))}

    reach = reach_probabilities("S", policy, is_goal)

    assert reach["S"] == pytest.approx(1.0)
    assert reach["T"] == pytest.approx(0.5)
    assert reach["goal"] == pytest.approx(1.0)


def test_a_state_that_is_only_sometimes_visited_and_a_dead_end_have_their_chances():
    policy = {"S": action(("A", 1), ("B", 3)), "A": action(("goal", 1)), "B": action(("goal", 1), ("dead", 1))}

    reach = reach_probabilities("S", policy, is_goal)

    assert reach == {
        "S": pytest.approx(1.0),
        "A": pytest.approx(0.25),
        "B": pytest.approx(0.75),
        "goal": pytest.approx(0.25 + 0.75 / 2),
        "dead": pytest.approx(0.75 / 2),
    }
    assert policy_states("S", policy, is_goal) == ["S", "A", "B", "goal", "dead"]


def test_a_start_that_is_a_goal_reaches_only_itself():
    assert reach_probabilities("goal", {}, is_goal) == {"goal": 1.0}


def test_too_many_states_give_no_chances():
    policy = {i: action((i + 1, 1)) for i in range(MAX_TRANSIENT + 1)}
    policy[MAX_TRANSIENT + 1] = action(("goal", 1))

    assert reach_probabilities(0, policy, is_goal) is None
