"""The packed solve (`solve_packed_model`, `solve_packed`, `certify`, `policy_reach`) against the object solver `solve`.

Generic models only (no game data): random tabular models with restarts, self loops and huge-weight kernels give the same
values and state sets as `solve`; the packed policy is greedy; interchangeable states merge into one class; dead states
get infinity; what the packed solve cannot take is refused; the certificate tells a wrong value from a right one;
`policy_reach` agrees with a plain walk; the BiCGSTAB path matches on a chain of 3000 states.
"""

import math
import random
from fractions import Fraction

import numpy as np
import pytest

from crafting_system.solver import (
    Action,
    Outcome,
    Peek,
    TabularModel,
    VariantAction,
    certify,
    pack_model,
    policy_reach,
    solve,
    solve_packed,
    solve_packed_model,
)

INF = math.inf
BIG = (1 << 70) // 3
SEEDS = range(100)


def random_model(seed: int) -> TabularModel:
    """3 to 40 states, state n-1 the goal; every state can `finish` to the goal; most can `restart` to state 0."""
    rng = random.Random(seed)
    n = rng.randint(3, 40)
    goal = n - 1
    table = {}
    for s in range(goal):
        actions = []
        for a in range(rng.randint(1, 4)):
            targets = rng.sample(range(n), min(rng.randint(1, 4), n))
            if rng.random() < 0.5:
                targets.append(s)  # a self loop (repeated successors are merged by the model)
            weights = [rng.randint(1, 50) for _ in targets]
            if rng.random() < 0.2:
                weights = [w * BIG for w in weights]  # the big-kernel path
            cost = round(rng.uniform(0.1, 20), 2)
            actions.append(Action(f"a{a}", cost, tuple(Outcome(t, w) for t, w in zip(targets, weights))))
        if s != 0 and rng.random() < 0.8:
            actions.append(Action("restart", 5.0, (Outcome(0, 1),)))
        actions.append(Action("finish", 30.0 + s, (Outcome(goal, 1), Outcome(s, 3))))
        table[s] = actions
    return TabularModel([goal], table)


def close(a: float, b: float, rel: float) -> bool:
    if math.isinf(a) or math.isinf(b):
        return a == b
    return abs(a - b) <= rel * max(1.0, abs(a), abs(b))


def action_value(action: Action, state: int, values) -> float:
    """(cost + sum of weight * value over the other successors) / (weight leaving / total): the self loop compiled out."""
    merged: dict[int, int] = {}
    for o in action.outcomes:
        merged[o.state] = merged.get(o.state, 0) + o.weight
    total = sum(merged.values())
    leaving = total - merged.get(state, 0)
    if leaving == 0:
        return INF
    ahead = sum(float(Fraction(w, total)) * values[t] for t, w in merged.items() if t != state)
    return (action.cost + ahead) / float(Fraction(leaving, total))


@pytest.mark.parametrize("seed", SEEDS)
def test_packed_values_equal_the_object_solver_on_random_models(seed):
    model = random_model(seed)
    expected = solve(model, [0])
    for merge in (True, False):
        for dense_limit in (1500, 0):
            got = solve_packed_model(model, [0], merge=merge, dense_limit=dense_limit)
            assert set(got.values) == set(expected.values)
            for state, value in expected.values.items():
                assert close(got.values[state], value, 1e-9), (merge, dense_limit, state)
            assert got.error_bound < 1e-6


@pytest.mark.parametrize("seed", range(40))
def test_the_packed_policy_is_greedy_on_its_own_values(seed):
    model = random_model(seed)
    got = solve_packed_model(model, [0])
    for state, chosen in got.policy.items():
        assert close(action_value(chosen, state, got.values), got.values[state], 1e-8)
        for other in model.actions(state):
            assert action_value(other, state, got.values) >= got.values[state] * (1 - 1e-8)


@pytest.mark.parametrize("k", [1, 2, 5, 30])
def test_interchangeable_states_merge_into_three_classes(k):
    goal = k + 1
    table = {0: [Action("pick", 1.0, tuple(Outcome(i, 1) for i in range(1, k + 1)))]}
    for i in range(1, k + 1):
        table[i] = [Action("try", 2.0, (Outcome(i, 5), Outcome(goal, 1))), Action("back", 7.0, (Outcome(0, 1),))]
    model = TabularModel([goal], table)
    packed = pack_model(model, [0])
    merged = solve_packed(packed.graph)
    assert merged.classes == 3
    assert solve_packed(packed.graph, merge=False).classes == goal + 1
    expected = solve(model, [0])
    for state, value in expected.values.items():
        assert close(float(merged.value[packed.index[state]]), value, 1e-10)


def dead_state_model() -> TabularModel:
    """0 can finish or gamble on a dead state; 1 and 2 only loop among themselves; 3 must risk 1; 4 has no actions."""
    return TabularModel(
        [9],
        {
            0: [
                Action("finish", 3.0, (Outcome(9, 1),)),
                Action("gamble", 1.0, (Outcome(9, 1), Outcome(1, 1))),
                Action("risk", 1.0, (Outcome(3, 1), Outcome(9, 1))),
                Action("stuck", 1.0, (Outcome(4, 1), Outcome(9, 1))),
            ],
            1: [Action("on", 1.0, (Outcome(2, 1),))],
            2: [Action("back", 1.0, (Outcome(1, 1),)), Action("wait", 1.0, (Outcome(2, 1), Outcome(1, 2)))],
            3: [Action("only", 1.0, (Outcome(9, 1), Outcome(1, 1)))],
        },
    )


def test_dead_states_are_infinite_in_both_solvers_and_have_no_policy_entry():
    model = dead_state_model()
    expected = solve(model, [0])
    for merge in (True, False):
        got = solve_packed_model(model, [0], merge=merge)
        assert set(got.values) == set(expected.values) == {0, 1, 2, 3, 4, 9}
        for dead in (1, 2, 3, 4):
            assert got.values[dead] == expected.values[dead] == INF
        for state in (0, 9):
            assert close(got.values[state], expected.values[state], 1e-12)
        assert got.values[0] == pytest.approx(3.0)
        assert set(got.policy) == set(expected.policy) == {0}


@pytest.mark.parametrize(
    "bad",
    [
        Action("two", 1.0, (Outcome(1, 1),), extra_inputs=(1,)),
        VariantAction("var", 1.0, (((1, 1),), ((0, 1), (1, 1)))),
        Peek("look", 1.0, (Action("opt", 1.0, (Outcome(1, 1),)),)),
    ],
    ids=["extra_inputs", "variant", "peek"],
)
def test_pack_model_refuses_what_the_object_solvers_keep(bad):
    model = TabularModel([1], {0: [bad]})
    with pytest.raises(ValueError):
        pack_model(model, [0])


def solved_graph(seed: int):
    packed = pack_model(random_model(seed), [0])
    return packed, solve_packed(packed.graph, merge=False)


@pytest.mark.parametrize("seed", range(10))
def test_certify_accepts_the_exact_solution(seed):
    packed, solved = solved_graph(seed)
    found = certify(packed.graph, solved.value, np.isfinite(solved.value))
    assert found.bound < 1e-9
    assert found.at_floor or found.residual < 1e-10


@pytest.mark.parametrize("seed", range(10))
def test_certify_sees_values_that_are_one_percent_too_high(seed):
    packed, solved = solved_graph(seed)
    found = certify(packed.graph, solved.value * 1.01, np.ones(packed.graph.n, dtype=bool))
    assert found.bound > 1e-3
    assert found.bound >= 0.0099  # the true relative error is 1 - 1/1.01
    assert 1.0 - found.lower >= 0.0099 - 1e-9


@pytest.mark.parametrize("seed", range(10))
def test_certify_sees_values_that_are_half_the_truth(seed):
    packed, solved = solved_graph(seed)
    found = certify(packed.graph, solved.value * 0.5, np.ones(packed.graph.n, dtype=bool))
    assert found.bound >= 0.4
    assert found.upper >= 2.0 * (1 - 1e-9)  # may be infinite


@pytest.mark.parametrize("seed", range(30))
def test_policy_reach_is_the_plain_walk_of_the_policy(seed):
    packed, solved = solved_graph(seed)
    graph = packed.graph
    seen, todo = {0}, [0]
    while todo:
        s = todo.pop()
        if solved.action[s] < 0:
            continue
        kernel = graph.act_kernel[solved.action[s]]
        for t in graph.k_succ[graph.k_ptr[kernel] : graph.k_ptr[kernel + 1]]:
            if int(t) not in seen:
                seen.add(int(t))
                todo.append(int(t))
    assert policy_reach(graph, solved.action, 0).tolist() == sorted(seen)


@pytest.mark.parametrize("seed", range(30))
def test_merged_states_share_a_value_and_policy_actions_stay_in_their_state(seed):
    graph = pack_model(random_model(seed), [0]).graph
    solved = solve_packed(graph)
    for c in range(solved.classes):
        assert len(set(solved.value[solved.cls == c].tolist())) == 1
    for s in range(graph.n):
        if not graph.goal[s] and np.isfinite(solved.value[s]):
            assert graph.act_ptr[s] <= solved.action[s] < graph.act_ptr[s + 1]


def test_bicgstab_matches_the_object_solver_on_a_chain_of_3000_states():
    rng = random.Random(7)
    n = 3000
    table = {}
    for s in range(n - 1):
        step = (Outcome(s + 1, rng.randint(1000, 2000)), Outcome(s, rng.randint(1, 5)), Outcome(0, 1))
        actions = [
            Action("step", round(rng.uniform(0.5, 3), 3), step),
            Action("finish", 1e6 + s, (Outcome(n - 1, 1), Outcome(s, 20))),
        ]
        if s > 10:
            actions.append(Action("back", round(rng.uniform(1, 6), 3), (Outcome(rng.randrange(s), 1), Outcome(s + 1, 1000))))
        table[s] = actions
    model = TabularModel([n - 1], table)
    expected = solve(model, [0])
    got = solve_packed_model(model, [0], dense_limit=0)
    assert set(got.values) == set(expected.values)
    for state, value in expected.values.items():
        assert close(got.values[state], value, 1e-8)
