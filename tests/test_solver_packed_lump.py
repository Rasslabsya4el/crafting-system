"""The exact lumping of a policy's chain (`lump_policy`, ticket #70): blocks that pay alike and move into every block alike are one state.

Generic models only (no game data). The lumped chain must give the very numbers of the whole chain (odds, mean, variance, the
quantiles), merge rows that are the same distribution under different integer weights, and keep apart rows that differ by one
weight. A kernel with weights beyond 62 bits is not lumped (None).
"""

import math
import random

import pytest

from crafting_system.risk import evaluate
from crafting_system.solver import Action, Outcome, TabularModel, lump_policy, pack_model, policy_reach, solve_packed

from test_solver_packed import BIG, random_model


def whole_and_lumped(model: TabularModel, start=0):
    """(policy of the concrete states, its goal test, policy of the lumped blocks, goal test, lumped chain) for the optimal policy."""
    packed = pack_model(model, [start])
    solved = solve_packed(packed.graph)
    action = solved.action
    graph = packed.graph
    policy = {}
    for i in policy_reach(graph, action, 0).tolist():
        a = int(action[i])
        if a < 0:
            continue
        kernel = int(graph.act_kernel[a])
        lo, hi = int(graph.k_ptr[kernel]), int(graph.k_ptr[kernel + 1])
        outcomes = tuple(Outcome(int(s), int(w)) for s, w in zip(graph.k_succ[lo:hi].tolist(), graph.kernel_weights(kernel)))
        policy[i] = Action("a", float(graph.act_cost[a]), outcomes)
    lumped = lump_policy(graph, action, 0)
    if lumped is None:
        return policy, graph, None, None
    blocks = {}
    for b in range(lumped.count):
        if lumped.goal[b] or lumped.action[b] < 0:
            continue
        blocks[b] = Action("a", float(lumped.cost[b]), tuple(Outcome(int(s), int(w)) for s, w in zip(lumped.succ[b].tolist(), lumped.weight[b].tolist())))
    return policy, graph, blocks, lumped


def same_risk(a, b):
    assert a.success_probability.value == pytest.approx(b.success_probability.value, abs=1e-12)
    assert a.mean.value == pytest.approx(b.mean.value, rel=1e-9)
    assert a.variance.value == pytest.approx(b.variance.value, rel=1e-8)
    for level in (0.5, 0.9):
        assert a.quantiles[level].low == pytest.approx(b.quantiles[level].low, rel=1e-9)
        assert a.quantiles[level].high == pytest.approx(b.quantiles[level].high, rel=1e-9)


def twin_model(copies: int, scale=lambda i: 1) -> TabularModel:
    """State 0 rerolls into `copies` look-alike states (weights `scale(i)` times a constant); each is finished or sent back alike."""
    goal = copies + 1
    table = {0: [Action("roll", 2.0, tuple(Outcome(i, 3 * scale(i)) for i in range(1, copies + 1)))]}
    for i in range(1, copies + 1):
        table[i] = [Action("try", 3.0, (Outcome(goal, scale(i)), Outcome(0, scale(i))))]
    return TabularModel([goal], table)


def test_look_alike_states_are_one_block_and_the_numbers_are_the_whole_chains():
    policy, graph, blocks, lumped = whole_and_lumped(twin_model(40))

    assert lumped.count == 3 and lumped.transitions == 3  # start, the twins, the goal
    same_risk(evaluate(blocks, int(lumped.start), lambda b: bool(lumped.goal[b])), evaluate(policy, 0, lambda s: bool(graph.goal[s])))


def test_the_same_chances_under_different_weights_are_one_row():
    policy, graph, blocks, lumped = whole_and_lumped(twin_model(6, scale=lambda i: i))

    assert lumped.count == 3  # the twins' rows are (1/2 goal, 1/2 start) at weights 1:1, 2:2, ... and the start's row weights them 1:2:3...


def test_states_that_differ_by_one_weight_stay_apart():
    goal = 3
    table = {
        0: [Action("roll", 2.0, (Outcome(1, 1), Outcome(2, 1)))],
        1: [Action("try", 3.0, (Outcome(goal, 1), Outcome(0, 1)))],
        2: [Action("try", 3.0, (Outcome(goal, 1), Outcome(0, 2)))],  # a third, not a half
    }
    policy, graph, blocks, lumped = whole_and_lumped(TabularModel([goal], table))

    assert lumped.count == 4
    same_risk(evaluate(blocks, int(lumped.start), lambda b: bool(lumped.goal[b])), evaluate(policy, 0, lambda s: bool(graph.goal[s])))


def test_states_that_pay_differently_stay_apart():
    goal = 3
    table = {
        0: [Action("roll", 2.0, (Outcome(1, 1), Outcome(2, 1)))],
        1: [Action("try", 3.0, (Outcome(goal, 1), Outcome(0, 1)))],
        2: [Action("try", 4.0, (Outcome(goal, 1), Outcome(0, 1)))],
    }
    _, _, _, lumped = whole_and_lumped(TabularModel([goal], table))

    assert lumped.count == 4


@pytest.mark.parametrize("seed", range(60))
def test_the_lumped_chain_of_a_random_optimal_policy_has_the_numbers_of_the_whole_chain(seed):
    model = random_model(seed)
    policy, graph, blocks, lumped = whole_and_lumped(model)
    if lumped is None:  # a big-weight kernel on the policy: not lumped
        assert any(int(k) in graph.k_big for k in range(graph.num_kernels))
        return

    assert lumped.count <= len(policy) + 1
    whole = evaluate(policy, 0, lambda s: bool(graph.goal[s]))
    same_risk(evaluate(blocks, int(lumped.start), lambda b: bool(lumped.goal[b])), whole)


def test_a_policy_with_a_big_weight_kernel_is_not_lumped():
    goal = 2
    table = {0: [Action("roll", 1.0, (Outcome(1, BIG), Outcome(goal, BIG)))], 1: [Action("back", 1.0, (Outcome(0, 1),))]}
    packed = pack_model(TabularModel([goal], table), [0])
    solved = solve_packed(packed.graph)

    assert lump_policy(packed.graph, solved.action, 0) is None


def test_a_dead_end_is_its_own_block_and_not_a_goal():
    goal = 3
    table = {
        0: [Action("roll", 1.0, (Outcome(1, 1), Outcome(goal, 1)))],
        1: [Action("finish", 5.0, (Outcome(goal, 1),))],
    }
    packed = pack_model(TabularModel([goal], table), [0])
    solved = solve_packed(packed.graph)

    lumped = lump_policy(packed.graph, solved.action, 0)

    assert lumped.count == 3 and int(lumped.goal.sum()) == 1
    assert math.isfinite(float(lumped.cost.sum()))


def test_many_random_states_with_shuffled_successor_order_lump_alike():
    rng = random.Random(7)
    copies = 25
    goal = copies + 1
    order = list(range(1, copies + 1))
    rng.shuffle(order)
    table = {0: [Action("roll", 2.0, tuple(Outcome(i, 5) for i in order))]}
    for i in range(1, copies + 1):
        pairs = [Outcome(goal, 2), Outcome(0, 1), Outcome(0, 1)]
        rng.shuffle(pairs)
        table[i] = [Action("try", 3.0, tuple(pairs))]
    _, _, _, lumped = whole_and_lumped(TabularModel([goal], table))

    assert lumped.count == 3
