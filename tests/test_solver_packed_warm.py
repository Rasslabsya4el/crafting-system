"""The warm start of the packed solve keeps a proper policy and repairs an improper one (ticket #568).

The envelope search solves a lower graph each round, and the graph of one round differs from the last round's in a few states. `solve_graph` takes the last
round's policy and values as a start (`start_policy`, `start_value`). A policy that was proper on the old graph can be improper on the new one (a state that
had only a shortcut to the goal now has actions that lead back), and a policy iteration that starts from an improper policy has no values to improve on.
`warm_policy` decides, by a finite chain's own test (every state reaches the goal with positive chance), whether the start is proper, and if it is not
replaces it at the states that cannot finish by the cheapest path's action. What is pinned here:

* the constructed case: the previous policy is improper on the new graph (a closed class of two states), `warm_policy` says "repaired", the policy it hands
  back is proper by an independent dense check, and the solve ends at the hand-worked optimum;
* a start that is proper is kept (even when it is not optimal) and the solve still ends at the optimum;
* on random graphs and random starts (most of them improper, some naming an action of another state or none), the policy handed back is proper and the
  values equal the cold solve's: the start changes the work, never the answer;
* `reaches_goal` against a plain fixed-point computation.
"""

import numpy as np
import pytest
from envelope_support import random_graph

from crafting_system.solver import PackedBuilder
from crafting_system.solver._packed_solve import Work, reaches_goal, solve_graph, warm_policy


def build(*states):
    """A graph from `(is_goal, [(cost, [(successor, weight), ...]), ...])` per state; the tag of an action is its running number."""
    builder = PackedBuilder()
    tag = 0
    for goal, actions in states:
        for cost, outcomes in actions:
            builder.action(tag, cost, builder.kernel([s for s, _ in outcomes], [w for _, w in outcomes]))
            tag += 1
        builder.close_state(goal)
    return builder.build()


# 0: a0 (cost 1) to 1, or a1 (cost 7) to the goal; 1: b0 (cost 1) back to 0, or b1 (cost 1) to 2; 2: c0 (cost 2) to the goal; 3 is the goal.
# Action numbers: a0 0, a1 1, b0 2, b1 3, c0 4. The optimum is a0, b1, c0 with values 4, 3, 2.
LOOP = build(
    (False, [(1.0, [(1, 1)]), (7.0, [(3, 1)])]),
    (False, [(1.0, [(0, 1)]), (1.0, [(2, 1)])]),
    (False, [(2.0, [(3, 1)])]),
    (True, []),
)
OPTIMUM = [4.0, 3.0, 2.0, 0.0]
A0, A1, B0, B1, C0 = range(5)


def proper(graph, policy) -> bool:
    """Whether `policy` reaches the goal with certainty from every state that has an action: I - P is nonsingular on those states (a dense, independent check)."""
    states = [s for s in range(graph.n) if policy[s] >= 0]
    place = {s: i for i, s in enumerate(states)}
    matrix = np.eye(len(states))
    for s in states:
        kernel = graph.act_kernel[policy[s]]
        lo, hi = graph.k_ptr[kernel], graph.k_ptr[kernel + 1]
        for t, p in zip(graph.k_succ[lo:hi].tolist(), graph.k_prob[lo:hi].tolist()):
            if t in place:
                matrix[place[s], place[t]] -= p
            elif not graph.goal[t]:
                return False  # the policy walks into a state that has no action
    return bool(np.linalg.cond(matrix) < 1e9)


def prepared(graph):
    work = Work(graph)
    leave = work.nonself_sums(np.ones(graph.n))
    alive = leave > 0.0
    return work, alive, np.where(alive, graph.act_cost / np.where(alive, leave, 1.0), np.inf)


def test_a_policy_that_is_proper_on_the_new_graph_is_kept_even_if_it_is_not_the_best():
    work, alive, effective = prepared(LOOP)
    start = np.array([A1, B0, C0, -1])  # 1 goes back to 0, which goes to the goal at once: proper, and dearer than the optimum
    info: dict = {}
    inside, ok, policy = warm_policy(work, alive, effective, start, info)
    assert info["warm"] == "kept"
    assert policy.tolist() == start.tolist()
    assert inside.tolist() == [True, True, True, True]
    core = solve_graph(LOOP, start_policy=start, start_value=np.zeros(4), info=info)
    assert core.value.tolist() == pytest.approx(OPTIMUM)
    assert core.action[:3].tolist() == [A0, B1, C0]


def test_a_policy_that_was_proper_and_is_improper_on_the_new_graph_is_repaired():
    work, alive, effective = prepared(LOOP)
    start = np.array([A0, B0, C0, -1])  # 0 and 1 send each other on forever; 2 finishes
    assert not proper(LOOP, start)
    info: dict = {}
    inside, ok, policy = warm_policy(work, alive, effective, start, info)
    assert info["warm"] == "repaired"
    assert info["warm_replaced"] == 2  # the closed class; the state that finishes keeps its action
    assert policy[2] == C0
    assert proper(LOOP, policy)
    info = {}
    core = solve_graph(LOOP, start_policy=start, start_value=np.zeros(4), info=info)
    assert info["warm"] == "repaired"
    assert core.value.tolist() == pytest.approx(OPTIMUM)
    assert core.action[:3].tolist() == [A0, B1, C0]


def test_a_missing_or_foreign_action_in_the_start_is_replaced_not_followed():
    work, alive, effective = prepared(LOOP)
    start = np.array([C0, -1, A1, -1])  # 0 is given the action of state 2, 1 none, and 2 the action of state 0
    info: dict = {}
    inside, ok, policy = warm_policy(work, alive, effective, start, info)
    assert info["warm"] == "repaired"
    assert proper(LOOP, policy)
    assert policy.tolist() == [A0, B1, C0, -1]  # all three are the cheapest path's


def test_the_goal_and_a_state_without_actions_need_no_policy():
    graph = build((False, [(1.0, [(1, 1), (2, 1)])]), (True, []), (False, []))  # state 2 is a dead end: nothing can be done there
    work, alive, effective = prepared(graph)
    info: dict = {}
    inside, ok, policy = warm_policy(work, alive, effective, np.array([0, -1, -1]), info)
    assert info["warm"] == "repaired"  # 0 may fall into the dead end, so it has no proper policy; nothing to keep
    assert inside.tolist() == [False, True, False]
    core = solve_graph(graph, start_policy=np.array([0, -1, -1]), start_value=np.zeros(3))
    assert core.value[1] == 0.0 and np.isinf(core.value[0]) and np.isinf(core.value[2])


def graph_of(seed: int):
    """A `PackedGraph` of `envelope_support.random_graph(seed)`: the tag of an action is its offer."""
    source = random_graph(seed, 40)
    builder = PackedBuilder()
    for s in range(source.n):
        for offer, kernel in source.actions[s].items():
            builder.action(offer, source.costs[offer], builder.kernel(list(kernel), list(kernel.values())))
        builder.close_state(s in source.goal)
    return builder.build()


@pytest.mark.parametrize("seed", range(25))
def test_a_random_start_never_changes_the_answer_and_the_policy_it_hands_back_is_proper(seed):
    graph = graph_of(seed)
    rng = np.random.default_rng(seed)
    cold = solve_graph(graph)
    work, alive, effective = prepared(graph)
    for _ in range(4):
        start = rng.integers(-1, graph.num_actions, size=graph.n)  # any action index: of another state, or none
        info: dict = {}
        inside, ok, policy = warm_policy(work, alive, effective, start, info)
        assert info["warm"] in ("kept", "repaired")
        assert proper(graph, policy)
        assert reaches_goal(work, policy)[~graph.goal].all()
        warm = solve_graph(graph, start_policy=start, start_value=rng.uniform(0.0, 100.0, size=graph.n))
        assert warm.value.tolist() == pytest.approx(cold.value.tolist(), rel=1e-8)


@pytest.mark.parametrize("seed", range(10))
def test_the_optimal_policy_as_a_start_is_kept_and_needs_no_improvement(seed):
    graph = graph_of(seed)
    cold = solve_graph(graph)
    info: dict = {}
    warm = solve_graph(graph, start_policy=cold.action, start_value=cold.value, info=info)
    assert info["warm"] == "kept"
    assert info["rounds"] == 1  # one evaluation, no state improves
    assert warm.value.tolist() == pytest.approx(cold.value.tolist(), rel=1e-9)


@pytest.mark.parametrize("seed", range(15))
def test_reaches_goal_is_the_fixed_point_of_the_policy_graph(seed):
    graph = graph_of(seed)
    rng = np.random.default_rng(100 + seed)
    policy = np.full(graph.n, -1, dtype=np.int64)
    for s in range(graph.n):
        count = graph.act_ptr[s + 1] - graph.act_ptr[s]
        if count and not graph.goal[s] and rng.random() < 0.8:
            policy[s] = graph.act_ptr[s] + rng.integers(0, count)
    reached = graph.goal.copy()  # the plain computation: grow until nothing changes
    changed = True
    while changed:
        changed = False
        for s in range(graph.n):
            if reached[s] or policy[s] < 0:
                continue
            kernel = graph.act_kernel[policy[s]]
            if any(reached[t] for t in graph.k_succ[graph.k_ptr[kernel] : graph.k_ptr[kernel + 1]].tolist()):
                reached[s] = changed = True
    assert reaches_goal(Work(graph), policy).tolist() == reached.tolist()


def test_a_state_without_a_given_action_takes_the_one_that_is_cheapest_under_the_given_values():
    work, alive, effective = prepared(LOOP)
    leave = work.nonself_sums(np.ones(4))
    info: dict = {}
    inside, ok, policy = warm_policy(work, alive, effective, np.array([-1, -1, -1, -1]), info, np.array(OPTIMUM), leave)
    assert info["warm"] == "kept"
    assert policy[:3].tolist() == [A0, B1, C0]
    wrong = np.array([0.0, 0.0, 2.0, 0.0])  # values that make 0 -> 1 -> 0 look free: the guess is a closed class, and it is repaired
    info = {}
    inside, ok, policy = warm_policy(work, alive, effective, np.array([-1, -1, -1, -1]), info, wrong, leave)
    assert info["warm"] == "repaired"
    assert proper(LOOP, policy)
