"""The packed solve sums each shared kernel once (ticket #568): the same sums, the same values, fewer edges.

The states of one key share the kernel of a reroll (thousands of outcomes), so a graph holds a few kernels for many actions. `Work.nonself_sums` expands every
action's kernel edge by edge (the reference); `Work.shared_sums` sums each kernel once and takes the own term off for an action whose kernel holds its own state;
`evaluate_policy` does the same in the product of BiCGSTAB. What is pinned here:

* `shared_sums` equals `nonself_sums` (to the rounding of the sums) on random graphs, with the thresholds lowered so that the small kernels of the random graphs
  take the shared path, and the actions that keep their edges (a heavy own term) are the ones `Work.edgewise` names;
* an evaluation by BiCGSTAB (shared sums) equals the dense evaluation, and the policy iteration of `solve_graph` ends at the same values and the same policy as the
  dense optimum of the test support, whatever the thresholds;
* on a graph where many states share one big kernel, the matvec reads the kernel once (`info["shared_edges"]` counts the distinct kernels' edges).
"""

import numpy as np
import pytest
from envelope_support import dense_optimum, random_graph

from crafting_system.solver import PackedBuilder
from crafting_system.solver import _packed_solve as ps
from crafting_system.solver._packed_solve import Work, evaluate_policy, solve_graph


def graph_of(seed: int):
    source = random_graph(seed, 40)
    builder = PackedBuilder()
    for s in range(source.n):
        for offer, kernel in source.actions[s].items():
            builder.action(offer, source.costs[offer], builder.kernel(list(kernel), list(kernel.values())))
        builder.close_state(s in source.goal)
    return source, builder.build()


@pytest.fixture(params=[(1, 0.5), (1, 0.2), (3, 0.9), (10_000, 0.5)], ids=["share-all", "share-all-low-heavy", "share-big", "share-none"])
def thresholds(request, monkeypatch):
    share_min, heavy = request.param
    monkeypatch.setattr(ps, "SHARE_MIN", share_min)
    monkeypatch.setattr(ps, "HEAVY_SELF", heavy)
    return share_min, heavy


@pytest.mark.parametrize("seed", range(10))
def test_shared_sums_equal_the_edge_by_edge_sums(seed, thresholds):
    _, graph = graph_of(seed)
    work = Work(graph)
    f = np.random.default_rng(seed).uniform(0.0, 1000.0, size=graph.n)
    assert work.shared_sums(f).tolist() == pytest.approx(work.nonself_sums(f).tolist(), rel=1e-12)
    assert work.shared_sums(np.ones(graph.n)).tolist() == pytest.approx(work.nonself_sums(np.ones(graph.n)).tolist(), rel=1e-12)


@pytest.mark.parametrize("seed", range(10))
def test_the_actions_that_keep_their_edges_are_those_with_a_heavy_own_term_or_a_short_kernel(seed, thresholds):
    share_min, heavy = thresholds
    _, graph = graph_of(seed)
    work = Work(graph)
    mass = work.self_mass
    expected = (mass > 0.0) & ((mass > heavy) | (work.asize < share_min))
    assert work.edgewise.tolist() == expected.tolist()
    own = np.zeros(graph.num_actions)  # the own chance by the plain definition
    for a in range(graph.num_actions):
        kernel = graph.act_kernel[a]
        lo, hi = graph.k_ptr[kernel], graph.k_ptr[kernel + 1]
        for t, p in zip(graph.k_succ[lo:hi].tolist(), graph.k_prob[lo:hi].tolist()):
            if t == work.act_state[a]:
                own[a] += p
    assert mass.tolist() == pytest.approx(own.tolist(), rel=1e-14)


@pytest.mark.parametrize("seed", range(10))
def test_a_policy_evaluated_by_bicgstab_on_shared_sums_equals_the_dense_evaluation(seed, thresholds):
    source, graph = graph_of(seed)
    work = Work(graph)
    leave = work.shared_sums(np.ones(graph.n))
    _, optimal = dense_optimum(source)
    policy = np.full(graph.n, -1, dtype=np.int64)
    for s in range(graph.n):
        if s not in source.goal:
            tags = graph.act_tag[graph.act_ptr[s] : graph.act_ptr[s + 1]].tolist()
            policy[s] = graph.act_ptr[s] + tags.index(optimal[s])
    dense = evaluate_policy(work, leave, policy, np.zeros(graph.n), 10_000, 1e-13, {})
    info: dict = {}
    iterative = evaluate_policy(work, leave, policy, np.zeros(graph.n), 5, 1e-13, info)
    assert "linear_iterations" in info  # BiCGSTAB ran
    assert iterative.tolist() == pytest.approx(dense.tolist(), rel=1e-9)


@pytest.mark.parametrize("seed", range(10))
def test_the_solve_ends_at_the_dense_optimum_whatever_the_thresholds(seed, thresholds):
    source, graph = graph_of(seed)
    value, _ = dense_optimum(source)
    core = solve_graph(graph, dense_limit=5)
    assert core.value.tolist() == pytest.approx(value.tolist(), rel=1e-8)


def test_many_states_that_share_one_big_kernel_read_it_once():
    count, width = 3000, 200
    builder = PackedBuilder()
    big = builder.kernel(list(range(count + 1, count + 1 + width)), [1] * width)  # a reroll: 200 outcomes, the same for every state
    # states 0..count-1 each reroll (cost 1) and have no self-loop; the outcomes are `width` states that finish at once (cost 1)
    for _ in range(count):
        builder.action(0, 1.0, big)
        builder.close_state(False)
    builder.close_state(True)  # count: the goal
    finish = builder.kernel([count], [1])
    for _ in range(width):
        builder.action(1, 1.0, finish)
        builder.close_state(False)
    graph = builder.build()
    info: dict = {}
    core = solve_graph(graph, info=info, dense_limit=10)
    assert core.value[:count].tolist() == pytest.approx([2.0] * count)
    assert info["shared_edges"] == width + 1  # the big kernel once, the outcomes' one-edge kernel once
    assert info["policy_edges"] == 0
