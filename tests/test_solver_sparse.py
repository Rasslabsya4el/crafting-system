"""Large stiff components are solved by sparse elimination when sweeps do not converge (ticket #66)."""

import random
from array import array
from fractions import Fraction

import pytest
from ssp_helpers import GOAL, act, model

from crafting_system.solver import ConvergenceError, solve
from crafting_system.solver import _component
from crafting_system.solver._component import Bellman, _evaluate, _evaluate_sparse


class Belt:
    """`size` states in a row; the last reaches the goal rarely and otherwise restarts at state 0.

    Every other state moves on, or restarts with chance 1 in 1000. Gauss-Seidel sweeps lose only
    the chance of one successful attempt (about 7e-5) per sweep, so they need over 3e5 of them.
    """

    def __init__(self, size, finish=1, restart=9999):
        self.size, self.finish, self.restart = size, finish, restart

    def is_goal(self, state):
        return state == GOAL

    def actions(self, state):
        if state == self.size - 1:
            return [act("finish", 1, (GOAL, self.finish), (0, self.restart))]
        return [act("walk", 1, (state + 1, 999), (0, 1))]


def belt_reference(size, finish, restart):
    """Expected cost from state 0 by a renewal argument, in exact fractions.

    An attempt steps state i with chance q^i (q = 999 / 1000), so it costs S = sum q^i steps and
    succeeds with chance q^(size - 1) * finish / (finish + restart): V_0 = S / success.
    """
    q = Fraction(999, 1000)
    steps = sum(q**i for i in range(size))
    return steps / (q ** (size - 1) * Fraction(finish, finish + restart))


class Ring:
    """States in a row that walk on or reset to the first; a resetting chance of 1 in `walk` + 1."""

    def __init__(self, size, reset, walk):
        self.size, self.reset, self.walk = size, reset, walk

    def is_goal(self, state):
        return state == self.size

    def actions(self, state):
        return [act("walk", 1, (state + 1, self.walk), (0, self.reset))]


def test_a_stiff_belt_that_sweeps_cannot_finish_is_solved_exactly():
    solution = solve(Belt(300), [0])

    expected = belt_reference(300, 1, 9999)
    assert solution.values[0] == pytest.approx(float(expected), rel=1e-9)
    assert solution.error_bound <= 1e-8
    assert solution.values[GOAL] == 0.0


def test_the_belt_that_used_to_raise_at_300_sweeps_is_solved():
    with pytest.raises(ConvergenceError):
        solve(Belt(300), [0], max_sweeps=299)  # fewer sweeps than the point where elimination takes over

    solution = solve(Belt(300), [0], max_sweeps=300)

    assert solution.values[0] == pytest.approx(float(belt_reference(300, 1, 9999)), rel=1e-9)
    assert solution.error_bound <= 1e-8


def test_a_direct_solve_limit_of_zero_still_means_sweeps_only():
    with pytest.raises(ConvergenceError):
        solve(Belt(300), [0], direct_solve_limit=0, max_sweeps=1000)


def test_every_state_of_the_belt_is_exact_not_only_the_first():
    solution = solve(Belt(300), [0])

    start = belt_reference(300, 1, 9999)
    for state in (1, 150, 299):
        # V_i = (size - i) + (the chance to restart after i steps) * V_0, written without cancellation
        q = Fraction(999, 1000)
        remaining = sum(q**k for k in range(300 - state))
        reach = q ** (300 - 1 - state) * Fraction(1, 10000)
        expected = remaining + (1 - reach) * start
        assert solution.values[state] == pytest.approx(float(expected), rel=1e-9)


def make_bellman(rows):
    """A Bellman operator from `rows[state] = [(base, [(target, p), ...], leak), ...]`, one entry per action."""
    states = list(range(len(rows)))
    astart, tptr = [0], array("q", [0])
    base, inside, prob, leak = array("d"), array("i"), array("d"), array("d")
    for actions in rows:
        for constant, moves, outside in actions:
            base.append(constant)
            leak.append(outside)
            for target, p in moves:
                inside.append(target)
                prob.append(p)
            tptr.append(len(inside))
        astart.append(len(base))
    ids = array("i", range(len(base)))
    has_exit = bytearray(1 if outside > 0.0 else 0 for actions in rows for _, _, outside in actions)
    return Bellman(states, astart, ids, base, has_exit, tptr, inside, prob, leak, min(base), 3, 1.0, 1.0)


def random_rows(seed, size, actions=2):
    """Substochastic rows with self-loops, repeated targets and rows that only exit.

    A chain down to state 0, which always leaks, makes every policy proper.
    """
    rng = random.Random(seed)
    rows = []
    for state in range(size):
        options = []
        for _ in range(actions):
            weights = {}
            if state > 0:
                weights[state - 1] = rng.uniform(0.1, 1.0)
            for _ in range(rng.randint(0, 4)):
                target = rng.randrange(size)
                weights[target] = weights.get(target, 0.0) + rng.uniform(0.1, 1.0)
            outside = rng.uniform(0.01, 1.0) if state == 0 or rng.random() < 0.4 else 0.0
            if state == size - 1:
                weights, outside = {}, 1.0  # only exit transitions
            total = sum(weights.values()) + outside
            moves = [(target, w / total) for target, w in weights.items()]
            options.append((rng.uniform(0.5, 5.0), moves, outside / total))
        rows.append(options)
    return rows


@pytest.mark.parametrize("seed", range(8))
def test_sparse_evaluation_equals_the_dense_one_on_random_proper_policies(seed):
    rows = random_rows(seed, 12 + seed * 5)
    bellman = make_bellman(rows)
    rng = random.Random(1000 + seed)
    policy = [bellman.astart[s] + rng.randrange(len(rows[s])) for s in range(len(rows))]

    dense = _evaluate(bellman, policy)
    sparse = _evaluate_sparse(bellman, policy)

    assert dense is not None and sparse is not None
    for found, reference in zip(sparse, dense):
        assert found == pytest.approx(reference, rel=1e-12)


def test_sparse_evaluation_handles_self_loops_and_a_state_that_only_exits():
    # state 0 loops on itself and goes to 1 or out; state 1 only exits
    bellman = make_bellman(
        [
            [(2.0, [(0, 0.5), (1, 0.25)], 0.25)],
            [(3.0, [], 1.0)],
        ]
    )

    values = _evaluate_sparse(bellman, [0, 1])

    # V1 = 3; V0 = 2 + 0.5 V0 + 0.25 * 3  ->  V0 = 5.5
    assert values == pytest.approx([5.5, 3.0], rel=1e-14)


def test_sparse_evaluation_refuses_an_improper_policy():
    bellman = make_bellman([[(1.0, [(1, 1.0)], 0.0)], [(1.0, [(0, 1.0)], 0.0)]])

    assert _evaluate_sparse(bellman, [0, 1]) is None


def test_sparse_evaluation_gives_up_when_the_work_budget_is_spent():
    bellman = make_bellman(random_rows(3, 40))
    policy = [bellman.astart[s] for s in range(40)]

    assert _evaluate_sparse(bellman, policy) is not None
    assert _evaluate_sparse(bellman, policy, work_limit=5) is None


def random_table(seed, size):
    """A cyclic SSP with a choice of two actions per state; every state can reach the goal."""
    rng = random.Random(seed)
    table = {}
    for state in range(size):
        options = []
        for label in "ab":
            outcomes = [(rng.randrange(size), rng.randint(1, 20)) for _ in range(rng.randint(1, 3))]
            outcomes.append((GOAL if state == size - 1 else max(state - 1, 0), rng.randint(1, 5)))
            if state == size - 1:
                outcomes.append((rng.randrange(size), 5000))  # a slow exit: sweeps need many rounds
            options.append(act(label, rng.choice([1, 2, 5]), *outcomes))
        table[state] = options
    return table


def test_policy_iteration_with_choices_matches_the_dense_policy_iteration(monkeypatch):
    table = random_table(7, 90)
    dense = solve(model(table), [0], direct_solve_limit=10**9)

    sparse = solve(model(table), [0], direct_solve_limit=64, max_sweeps=300)

    assert sparse.error_bound <= 1e-8
    for state, value in dense.values.items():
        assert sparse.values[state] == pytest.approx(value, rel=1e-9)


def test_a_small_component_gives_the_same_numbers_as_before():
    # pinned from the dense path before the sparse one existed
    solution = solve(Ring(40, 1, 3), [0])

    assert solution.values[0] == 397745.3289933911
    assert solution.values[20] == 396487.98157258425
    assert solution.error_bound == 5.580025330687022e-10


@pytest.mark.parametrize(
    ("args", "start", "middle", "bound"),
    [
        ((100, 1, 99), 173.19990262650037, 107.912303992283, 9.642930898223767e-11),
        ((120, 1, 199), 164.9726376155315, 94.79764335677193, 8.47673042869701e-11),
    ],
)
def test_a_component_that_converges_in_its_first_sweeps_is_unchanged(args, start, middle, bound, monkeypatch):
    # pinned from the sweeps before the sparse path existed; both converge well inside 300 sweeps
    solution = solve(Ring(*args), [0])

    assert solution.values[0] == start
    assert solution.values[args[0] // 2] == middle
    assert solution.error_bound == bound

    monkeypatch.setattr(_component, "SWEEPS_BEFORE_DIRECT", 10**9)  # elimination switched off
    without = solve(Ring(*args), [0])

    assert without.values == solution.values
    assert without.error_bound == solution.error_bound
