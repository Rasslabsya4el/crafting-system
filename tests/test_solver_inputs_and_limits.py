"""Invalid actions are refused; slow cycles report a bound; big graphs need no recursion."""

import math

import pytest
from ssp_helpers import GOAL, act, model

from crafting_system.solver import Action, ConvergenceError, Outcome, solve


@pytest.mark.parametrize("cost", [0, 0.0, -1, -0.5, math.nan, math.inf, -math.inf, True, "3"])
def test_an_action_needs_a_finite_cost_above_zero(cost):
    with pytest.raises(ValueError):
        Action("a", cost, ((GOAL, 1),))


@pytest.mark.parametrize("weight", [-1, 1.5, 2.0, True, math.nan, "1", None])
def test_an_outcome_weight_must_be_a_non_negative_integer(weight):
    with pytest.raises(ValueError):
        Action("a", 1, ((GOAL, weight),))


@pytest.mark.parametrize("outcomes", [(), ((GOAL, 0),), ((GOAL, 0), ("A", 0))])
def test_an_action_needs_a_total_weight_above_zero(outcomes):
    with pytest.raises(ValueError):
        Action("a", 1, outcomes)


def test_plain_tuples_and_outcome_tuples_are_the_same_outcomes():
    plain = Action("a", 1, ((GOAL, 2), ("A", 1)))
    named = Action("a", 1, (Outcome(GOAL, 2), Outcome("A", 1)))

    assert plain == named
    assert plain.outcomes[0].weight == 2


def test_a_cycle_too_slow_for_the_sweep_budget_raises_with_its_best_bound():
    # leaves with chance 1 in 1000 per step: a sweep gains almost nothing
    table = {
        "A": [act("a", 1, ("B", 999), (GOAL, 1))],
        "B": [act("b", 1, ("A", 999), (GOAL, 1))],
    }

    with pytest.raises(ConvergenceError) as caught:
        solve(model(table), ["A"], direct_solve_limit=0, max_sweeps=5)

    assert caught.value.error_bound > 1e-10
    assert not math.isnan(caught.value.error_bound)


def test_the_same_slow_cycle_is_solved_exactly_by_policy_iteration():
    table = {
        "A": [act("a", 1, ("B", 999), (GOAL, 1))],
        "B": [act("b", 1, ("A", 999), (GOAL, 1))],
    }

    solution = solve(model(table), ["A"], direct_solve_limit=64, max_sweeps=1)

    # V = 1 + 0.999 V  ->  1000, by symmetry for both states
    assert solution.values["A"] == pytest.approx(1000.0, rel=1e-9)
    assert solution.values["B"] == pytest.approx(1000.0, rel=1e-9)


def test_the_same_slow_cycle_converges_given_enough_sweeps():
    table = {
        "A": [act("a", 1, ("B", 999), (GOAL, 1))],
        "B": [act("b", 1, ("A", 999), (GOAL, 1))],
    }

    solution = solve(model(table), ["A"], direct_solve_limit=0, tolerance=1e-8)

    assert solution.values["A"] == pytest.approx(1000.0, rel=1e-7)
    assert solution.error_bound <= 1e-7


class Ladder:
    """`size` states in a row; each repeats itself half the time, else moves one step on."""

    def __init__(self, size):
        self.size = size

    def is_goal(self, state):
        return state == self.size

    def actions(self, state):
        return [act("climb", 1, (state, 1), (state + 1, 1))]


def test_a_long_acyclic_ladder_is_solved_without_recursion():
    size = 20_000

    solution = solve(Ladder(size), [0])

    assert len(solution.values) == size + 1
    assert solution.values[0] == pytest.approx(2.0 * size, rel=1e-12)
    assert solution.values[size - 1] == 2.0
    assert solution.error_bound < 1e-9


class Ring:
    """A ring of states that walk to the goal but reset to the start with a small chance."""

    def __init__(self, size, reset=1, walk=999):
        self.size, self.reset, self.walk = size, reset, walk

    def is_goal(self, state):
        return state == self.size

    def actions(self, state):
        return [act("walk", 1, (state + 1, self.walk), (0, self.reset))]


def ring_reference(size, reset, walk):
    """Expected cost from state 0, by the closed form of a renewal argument.

    Each attempt walks until it resets or reaches the end. With q = walk / (walk + reset) the
    chance to survive one step, an attempt costs sum_{i<size} q^i expected steps (state 0 is
    stepped from first) and succeeds with chance q^size, so V_0 = cost_per_attempt / q^size.
    """
    q = walk / (walk + reset)
    per_attempt = sum(q**i for i in range(size))
    return per_attempt / q**size


def test_a_large_single_component_with_resets_is_solved_by_sweeps():
    size = 300

    solution = solve(Ring(size), [0], tolerance=1e-10)

    expected = ring_reference(size, 1, 999)
    assert solution.values[0] == pytest.approx(expected, rel=1e-8)
    assert solution.error_bound <= 1e-9


def test_a_ring_is_the_same_whether_sweeps_or_policy_iteration_solve_it():
    by_sweeps = solve(Ring(40), [0], direct_solve_limit=0)
    by_policy = solve(Ring(40), [0], direct_solve_limit=10**9)

    assert by_sweeps.values[0] == pytest.approx(by_policy.values[0], rel=1e-8)
