"""The exact lumping of a policy's chain (`lump_policy`, ticket #70): blocks that pay alike and move into every block alike are one state.

Generic models only (no game data). The lumped chain must give the very numbers of the whole chain (odds, mean, variance, the
quantiles), merge rows that are the same distribution under different integer weights, and keep apart rows that differ by one
weight. A kernel with weights beyond 62 bits is lumped by its exact chances.
"""

import math
import random

import pytest

from crafting_system.risk import evaluate
from crafting_system.solver import Action, Outcome, TabularModel, lump_policy, pack_model, policy_reach, solve_packed
from crafting_system.solver import _packed_lump as lump_module

from test_solver_packed import random_model


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
    blocks = {}
    for b in range(lumped.count):
        if lumped.goal[b] or lumped.action[b] < 0:
            continue
        blocks[b] = Action("a", float(lumped.cost[b]), tuple(Outcome(int(s), int(w)) for s, w in zip(lumped.succ[b].tolist(), lumped.weight[b])))
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
    assert lumped.count <= len(policy) + 1
    whole = evaluate(policy, 0, lambda s: bool(graph.goal[s]))
    same_risk(evaluate(blocks, int(lumped.start), lambda b: bool(lumped.goal[b])), whole)


@pytest.mark.parametrize("seed", range(30))
def test_reading_the_kernels_in_small_chunks_gives_the_same_blocks(seed, monkeypatch):
    model = random_model(seed)
    _, graph, _, whole = whole_and_lumped(model)
    monkeypatch.setattr(lump_module, "CHUNK_EDGES", 3)

    _, _, _, chunked = whole_and_lumped(model)

    assert chunked.count == whole.count and chunked.transitions == whole.transitions
    assert chunked.deviation <= 1e-12 and (chunked.block == whole.block).all()


def test_kernels_with_weights_beyond_62_bits_lump_by_their_exact_chances():
    """Look-alike twins whose weights are huge, in different multiples, are one block; a twin that differs by one weight in 10**21 is not."""
    goal = 5
    huge = 10**21
    table = {
        0: [Action("roll", 1.0, tuple(Outcome(i, huge * i) for i in (1, 2, 3, 4)))],
        1: [Action("try", 3.0, (Outcome(goal, huge), Outcome(0, huge)))],
        2: [Action("try", 3.0, (Outcome(goal, 2 * huge), Outcome(0, 2 * huge)))],  # the same chances at twice the weights
        3: [Action("try", 3.0, (Outcome(goal, 3 * huge), Outcome(0, 3 * huge)))],
        4: [Action("try", 3.0, (Outcome(goal, huge + 1), Outcome(0, huge)))],  # one part in 10**21 apart: another row
    }
    policy, graph, blocks, lumped = whole_and_lumped(TabularModel([goal], table))

    assert lumped.count == 4  # the start, the three twins, the odd one, the goal
    assert any(int(k) in graph.k_big for k in range(graph.num_kernels))
    same_risk(evaluate(blocks, int(lumped.start), lambda b: bool(lumped.goal[b])), evaluate(policy, 0, lambda s: bool(graph.goal[s])))


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


def kernel_table(rows):
    """A `PackedGraph` holding only kernels (no states, no actions): the table `lump_states` reads."""
    import numpy as np

    from crafting_system.solver._packed import PackedGraph, probabilities

    k_ptr = np.concatenate(([0], np.cumsum([len(row) for row in rows]))).astype(np.int64)
    k_succ = np.array([s for row in rows for s, _ in row], dtype=np.int32)
    k_wt = np.array([w for row in rows for _, w in row], dtype=np.int64)
    empty = np.zeros(0, dtype=np.int64)
    return PackedGraph(np.zeros(0, dtype=bool), np.zeros(1, dtype=np.int64), empty.astype(np.int32), np.zeros(0), empty.astype(np.int32), k_ptr, k_succ, k_wt, probabilities(k_ptr, k_wt, {}))


@pytest.mark.parametrize(("label_of_4", "blocks"), [(3, [[0], [1, 2], [3, 4], [5]]), (4, [[0], [1], [2], [3], [4], [5]])])
def test_lump_states_keeps_labels_apart_and_merges_rows_with_the_same_chances_into_every_block(label_of_4, blocks):
    """#689: 0 -> 1, 2 (1:1); 1 -> 3, goal (1:1); 2 -> 4, goal (2:2); 3 and 4 share a kernel -> goal. State 5 is the goal.

    With 3 and 4 under one label they are one block, so 1 and 2 have the same chances into every block (1/2, 1/2, under different weights) and merge.
    With 4 under its own label, 3 and 4 are apart, and that splits 1 from 2 in a second round.
    """
    import numpy as np

    table = kernel_table([[(1, 1), (2, 1)], [(3, 1), (5, 1)], [(4, 2), (5, 2)], [(5, 1)]])
    slot = np.array([0, 1, 2, 3, 3, -1])
    label = np.array([1, 2, 2, 3, label_of_4, 9])

    block = lump_module.lump_states(table, slot, label)

    found = sorted(sorted(np.flatnonzero(block == b).tolist()) for b in np.unique(block).tolist())
    assert found == blocks
