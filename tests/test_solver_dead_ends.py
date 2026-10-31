"""The dead-end search (`proper_states`) against the old round-by-round version, and on long chains (#82).

The old implementation is copied here verbatim as the oracle. Chains are checked on the answers
only; no test asserts on time (ADR-0014).
"""

import math
import random
import sys

import pytest

from crafting_system.solver import Action, TabularModel, solve
from crafting_system.solver._graph import build_graph, proper_states

GOAL = "goal"


def old_proper_states(graph):
    """The previous implementation, kept as the oracle (rescans the whole graph every round)."""
    n_states = len(graph.states)
    pred = [[] for _ in range(n_states)]
    for k, successors in enumerate(graph.succ):
        for j in successors:
            pred[j].append(k)
    alive = [True] * len(graph.owner)
    in_y = [True] * n_states
    while True:
        reached = list(graph.goal)
        stack = [s for s in range(n_states) if graph.goal[s]]
        while stack:
            j = stack.pop()
            for k in pred[j]:
                if alive[k]:
                    owner = graph.owner[k]
                    if not reached[owner]:
                        reached[owner] = True
                        stack.append(owner)
        removed = [s for s in range(n_states) if in_y[s] and not reached[s]]
        if not removed:
            return alive, in_y
        for s in removed:
            in_y[s] = False
            for k in graph.state_actions[s]:
                alive[k] = False
            for k in pred[s]:
                alive[k] = False


def risky(label, cost, *outcomes):
    return Action(label, cost, tuple(outcomes))


def random_model(rng):
    """A small random model: goals, dead states, cycles, self-loops, several actions per state."""
    n = rng.randint(1, 9)
    names = list(range(n))
    goals = {s for s in names if rng.random() < 0.18}
    table = {}
    for s in names:
        if s in goals:
            continue
        actions = []
        for a in range(rng.choice((0, 1, 1, 2, 2, 3))):
            outcomes = [
                (rng.choice(names), rng.randint(1, 3)) for _ in range(rng.randint(1, 3))
            ]
            actions.append(risky(f"a{a}", float(rng.randint(1, 4)), *outcomes))
        table[s] = actions
    return TabularModel(goals, table), names


def test_fuzz_matches_the_old_implementation():
    rng = random.Random(8201)
    with_dead = with_alive_cycle = 0
    for _ in range(4000):
        model, names = random_model(rng)
        graph = build_graph(model, names)
        alive, in_y = proper_states(graph)
        old_alive, old_in_y = old_proper_states(graph)
        assert in_y == old_in_y
        assert alive == old_alive
        with_dead += not all(old_in_y)
        with_alive_cycle += any(old_alive) and not all(graph.goal)
    assert with_dead > 500  # the generator does produce dead ends and survivors
    assert with_alive_cycle > 500


def test_fuzz_larger_graphs_match():
    rng = random.Random(8202)
    for _ in range(300):
        n = rng.randint(10, 40)
        names = list(range(n))
        goals = {s for s in names if rng.random() < 0.06}
        table = {}
        for s in names:
            if s in goals:
                continue
            table[s] = [
                risky(
                    f"a{a}",
                    1.0,
                    *[(rng.choice(names), rng.randint(1, 2)) for _ in range(rng.randint(1, 3))],
                )
                for a in range(rng.choice((0, 1, 2, 2, 3)))
            ]
        graph = build_graph(TabularModel(goals, table), names)
        assert proper_states(graph) == old_proper_states(graph)


def test_alive_is_owner_in_y_and_every_successor_in_y():
    rng = random.Random(8203)
    for _ in range(500):
        model, names = random_model(rng)
        graph = build_graph(model, names)
        alive, in_y = proper_states(graph)
        for k, successors in enumerate(graph.succ):
            expected = in_y[graph.owner[k]] and all(in_y[j] for j in successors)
            assert alive[k] == expected


# Adversarial chains. Each is built so the old code peels one state (or two) per round.


def dag_chain(n, anchor=None):
    """State r (1..n) has one action: half goal, half the state below. State 0 is a dead end.

    With `anchor=k` state k also has a safe action of cost 10 straight to the goal.
    """
    table = {0: []}
    for r in range(1, n + 1):
        actions = [risky("risky", 1.0, (r - 1, 1), (GOAL, 1))]
        if r == anchor:
            actions.append(risky("safe", 10.0, (GOAL, 1)))
        table[r] = actions
    return TabularModel([GOAL], table)


def back_edge_chain(n):
    """The same chain with a back edge at every state: one big cycle for the component search."""
    table = {0: [risky("back", 1.0, (1, 1), ("dead0", 1))]}
    for r in range(1, n + 1):
        actions = [risky("risky", 1.0, (r - 1, 1), (GOAL, 1))]
        if r < n:
            actions.append(risky("back", 1.0, (r + 1, 1), (f"dead{r}", 1)))
        table[r] = actions
    return TabularModel([GOAL], table)


def alternating_chain(n, anchored):
    """Level i has a two-state cycle p_i, q_i and a state y_i, in one big component.

    p_i exits to the goal through E_i = {goal, y_(i-1)}; y_i's only action leads to p_i. Without
    the anchor the bottom level is dead and each level falls in turn, first the cycle (found by
    reachability), then y_i (found by safety), then the next cycle. With it every level lives. A
    back edge from q_1 to the top p_n, through a dead state, closes the component.
    """
    table = {("anchor",): [risky("safe", 3.0, (GOAL, 1))]} if anchored else {}
    for i in range(1, n + 1):
        below = ("anchor",) if (i == 1 and anchored) else (("y", i - 1) if i > 1 else ("dead",))
        table[("p", i)] = [
            risky("exit", 1.0, (GOAL, 1), (below, 1)),
            risky("loop", 1.0, (("q", i), 1)),
        ]
        table[("q", i)] = [risky("loop", 1.0, (("p", i), 1))]
        table[("y", i)] = [risky("climb", 1.0, (("p", i), 1))]
    table[("q", 1)].append(risky("back", 1.0, (("p", n), 1), (("dead",), 1)))
    return TabularModel([GOAL], table)


def solve_all(model):
    names = list(model._table)
    return solve(model, names)


def test_dag_chain_every_state_falls():
    solution = solve_all(dag_chain(40))
    assert solution.values[GOAL] == 0.0
    assert all(solution.values[r] == math.inf for r in range(41))
    assert dict(solution.policy) == {}


def test_dag_chain_with_an_anchor_keeps_what_sits_above_it():
    n, k = 60, 5
    solution = solve_all(dag_chain(n, anchor=k))
    # below the anchor everything falls: r -> r-1 -> ... -> 0, a dead end
    assert all(solution.values[r] == math.inf for r in range(0, k))
    assert solution.values[k] == pytest.approx(10.0, rel=1e-12)
    # above it V(r) = 1 + V(r-1) / 2, so V(k + m) = 2 + 8 / 2**m
    for m in range(1, n - k + 1):
        assert solution.values[k + m] == pytest.approx(2.0 + 8.0 / 2**m, rel=1e-9)
    assert solution.policy[k].label == "safe"
    assert all(solution.policy[r].label == "risky" for r in range(k + 1, n + 1))
    assert set(solution.policy) == set(range(k, n + 1))


def test_back_edge_chain_every_state_falls():
    solution = solve_all(back_edge_chain(40))
    assert solution.values[GOAL] == 0.0
    assert all(solution.values[r] == math.inf for r in range(41))
    assert dict(solution.policy) == {}


def test_alternating_chain_falls_level_by_level():
    solution = solve_all(alternating_chain(30, anchored=False))
    for i in range(1, 31):
        for key in (("p", i), ("q", i), ("y", i)):
            assert solution.values[key] == math.inf
    assert dict(solution.policy) == {}


def test_alternating_chain_with_an_anchor_survives_whole():
    n = 30
    solution = solve_all(alternating_chain(n, anchored=True))
    v_y = 3.0  # the anchor
    for i in range(1, n + 1):
        v_p = 1.0 + 0.5 * v_y  # E_i: cost 1, half goal, half y_(i-1)
        v_y = 1.0 + v_p
        assert solution.values[("p", i)] == pytest.approx(v_p, rel=1e-9)
        assert solution.values[("q", i)] == pytest.approx(1.0 + v_p, rel=1e-9)
        assert solution.values[("y", i)] == pytest.approx(v_y, rel=1e-9)
        assert solution.policy[("p", i)].label == "exit"
        assert solution.policy[("y", i)].label == "climb"


def test_ring_with_an_exit_is_one_cyclic_component():
    """A ring of m states, each stepping to the next at cost 1; state 0 can also exit for 5."""
    m = 25
    table = {i: [risky("next", 1.0, ((i + 1) % m, 1))] for i in range(m)}
    table[0].append(risky("exit", 5.0, (GOAL, 1)))
    solution = solve(TabularModel([GOAL], table), [3])
    assert solution.values[0] == pytest.approx(5.0, rel=1e-9)
    for i in range(1, m):
        assert solution.values[i] == pytest.approx(5.0 + (m - i), rel=1e-9)
    assert solution.policy[0].label == "exit"


def test_long_dag_chain_of_dead_end_peels_finishes():
    n = 20_000
    model = dag_chain(n)
    graph = build_graph(model, [n])
    alive, in_y = proper_states(graph)
    assert [s for s, ok in zip(graph.states, in_y) if ok] == [GOAL]
    assert not any(alive)
    solution = solve(model, [n])
    assert solution.values[GOAL] == 0.0 and solution.values[0] == math.inf
    assert solution.values[n] == math.inf
    assert dict(solution.policy) == {}


def test_long_alternating_chain_finishes():
    n = 7_000
    solution = solve(alternating_chain(n, anchored=False), [("y", n)])
    assert solution.values[("y", n)] == math.inf
    assert dict(solution.policy) == {}


def hub_chain(n, m):
    """The alternating chain plus a hub leaning on every p_i and a path of m states hanging below it."""
    table = dict(alternating_chain(n, anchored=False)._table)
    table["hub"] = [risky(f"H{i}", 1.0, (("p", i), 1)) for i in range(1, n + 1)]
    table[("P", 1)] = [risky("up", 1.0, ("hub", 1))]
    for j in range(2, m + 1):
        table[("P", j)] = [risky("up", 1.0, (("P", j - 1), 1))]
    table[("q", 1)] = [*table[("q", 1)], risky("close", 1.0, (("P", m), 1), (("dead",), 1))]
    return TabularModel([GOAL], table)


def test_hub_over_a_falling_chain_matches_the_old_answer_on_a_small_one():
    graph = build_graph(hub_chain(12, 9), [("P", 9)])
    assert proper_states(graph) == old_proper_states(graph)


def test_hub_over_a_long_falling_chain_finishes():
    n = 3_000
    solution = solve(hub_chain(n, n), [("P", n)])
    assert solution.values[("P", n)] == math.inf and solution.values["hub"] == math.inf
    assert dict(solution.policy) == {}


def test_deep_chains_do_not_hit_the_recursion_limit():
    n = sys.getrecursionlimit() * 4
    graph = build_graph(dag_chain(n, anchor=1), [n])
    alive, in_y = proper_states(graph)
    # anchor at 1: every state above it survives; state 0 has no action and is the only dead one
    assert [s for s, ok in zip(graph.states, in_y) if not ok] == [0]
    solution = solve(dag_chain(n, anchor=1), [n])
    assert solution.values[1] == pytest.approx(10.0, rel=1e-12)
    assert solution.values[n] == pytest.approx(2.0, rel=1e-6)
    cyclic = build_graph(back_edge_chain(n), [n])
    alive, in_y = proper_states(cyclic)
    assert [s for s, ok in zip(cyclic.states, in_y) if ok] == [GOAL]
