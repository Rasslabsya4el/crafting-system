"""The preconditioned solve of a policy's system (ticket #1484, H20 of board #1434): when the plain BiCGSTAB stalls and the exact solve by the cycles
of the chain cannot be made, the same BiCGSTAB preconditioned by an incomplete LU of the system with one unknown per kernel (`_packed_ilu`).

R17's first plan (1,024,996 states, one cycle of 943,748 states with a single exit, 712,952 states on a free action) is the case: flat at a backward
error of 0.0957 and 25,133 cut rows past the memory for the cycles. The fixture here is that shape made small: one long cycle of free steps
(1e-8 c each) with a single exit at its last state, above `INVERT_LIMIT` so the cycles are cut, and a memory for the Woodbury step that holds none of
its cut rows (`WOODBURY_CELLS`, "a small machine", as `test_solver_packed_stiff.py` does). Its values are known without a solve: a run goes round
the ring until it leaves, so `V(0) = ((n - 1) free + paid) / q`.
"""

import numpy as np
import pytest
import scipy.sparse as sp
import scipy.sparse.linalg as sla
from envelope_support import dense_optimum, random_graph

from crafting_system.solver import PackedBuilder
from crafting_system.solver import _packed_chain, _packed_linear
from crafting_system.solver import _packed_solve as ps

STATES = 5_000  # above `_packed_chain.INVERT_LIMIT` (4,000): the ring is cut and its rows put back by the Woodbury step
FREE = 1e-8  # the cost of a free step (R17's tag 12: 1.05e-8 c)
PAID = 1.0
EXIT = 1e-4  # the chance the paid step leaves for the goal (else back to the ring's first state)


def ring(states: int = STATES, exit_weight: int = 100, free: float = FREE):
    """`(graph, policy)`: states `0 .. states - 1` each step to the next for `free`; the last pays `PAID` and reaches the goal (`states`) with
    chance `exit_weight / 10**6`, else goes back to 0."""
    builder = PackedBuilder()
    for s in range(states - 1):
        builder.action(0, free, builder.kernel([s + 1], [1]))
        builder.close_state(False)
    builder.action(1, PAID, builder.kernel([states, 0], [exit_weight, 10**6 - exit_weight]))
    builder.close_state(False)
    builder.close_state(True)
    return builder.build(), np.append(np.arange(states), -1)


def ring_values(states: int = STATES, exit_weight: int = 100, free: float = FREE) -> np.ndarray:
    q = exit_weight / 10**6
    start = ((states - 1) * free + PAID) / q
    ahead = free * np.arange(states - 1, 0, -1, dtype=float)  # the free steps from s to the last state
    return np.append(ahead, 0.0) + PAID + (1.0 - q) * start


@pytest.fixture
def small_machine(monkeypatch):
    monkeypatch.setattr(_packed_chain, "WOODBURY_CELLS", 1_000)  # no room to put back a cut row: the exact solve cannot be made


def evaluate(graph, policy, info):
    work = ps.Work(graph)
    leave = work.nonself_sums(np.ones(work.n))
    return ps.evaluate_policy(work, leave, policy, np.zeros(work.n), ps.DENSE_LIMIT, 1e-13, info)


def test_without_it_the_stalled_ring_is_refused(small_machine, monkeypatch):
    graph, policy = ring()
    monkeypatch.setattr(ps._PolicyTerms, "sparse", lambda self: None)  # main before #1484: no sparse form, no preconditioned solve

    with pytest.raises(ps.ConvergenceError) as refused:
        evaluate(graph, policy, {})

    words = str(refused.value)
    assert "5,000 states" in words and "distinct cut rows" in words and "past the 1,000" in words  # flat near 1 and no room for the cycles


def test_the_stalled_ring_is_solved_by_the_preconditioned_iteration_and_judged_as_an_iterate(small_machine):
    graph, policy = ring()
    info: dict = {}

    values = evaluate(graph, policy, info)

    assert info["linear_forward_iterate"] > _packed_linear.ACCEPT_ERROR  # the plain iteration stalled short of the limit
    assert info["linear_preconditioned"] == 1 and info["linear_preconditioned_taken"] == 1 and "linear_cycles" not in info
    assert info["linear_backward_error"] <= 1e-12 and info["linear_forward"] <= 1e-6  # taken by its forward estimate, as an iterate is
    tried = info["preconditioned"]
    assert tried["entries"] > 0 and tried["iterations"] >= 1 and "seconds" in tried and "why" not in tried
    assert values[:STATES] == pytest.approx(ring_values(), rel=1e-9)


def test_through_the_solvers_entry_the_ring_is_solved_and_certified(small_machine):
    """Through `solve_graph` the answer is certified as any other (`certify`). The steps cost 1e-4 here, not 1e-8: a ring of 5,000 steps of 1e-8 c
    is refused by the float64 certificate whatever solved it (0.000889, the exact solve by the cycles too: its margin is the rounding of values
    1e12 times a step), which is #1484's open risk for R17, measured on the dumped system and not this test's subject."""
    graph, _ = ring(free=1e-4)
    info: dict = {}

    core = ps.solve_graph(graph, info=info)

    assert core.value[0] == pytest.approx(ring_values(free=1e-4)[0], rel=1e-9)
    assert info["linear_preconditioned_taken"] >= 1 and "linear_cycles" not in info


def test_where_the_cycles_fit_they_are_solved_exactly_and_nothing_is_preconditioned():
    graph, policy = ring()
    info: dict = {}

    values = evaluate(graph, policy, info)

    assert info["linear_cycles"] == 1 and "linear_preconditioned" not in info and "preconditioned" not in info
    assert values[:STATES] == pytest.approx(ring_values(), rel=1e-12)


def test_a_factorisation_past_the_memory_net_is_not_begun_and_the_refusal_says_so(small_machine, monkeypatch):
    from crafting_system import parallel

    graph, policy = ring()
    monkeypatch.setattr(parallel, "held_mb", lambda under=None, paced=True: 1_000.0)
    with parallel.memory_net(1_000.5), pytest.raises(ps.ConvergenceError) as refused:
        evaluate(graph, policy, {})

    words = str(refused.value)
    assert "the incomplete factors were not made" in words and "past the limit of 1,000 MB" in words


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize(("share_min", "heavy"), [(1, 0.5), (1, 0.2), (3, 0.9), (10_000, 0.5)], ids=["share-all", "share-all-low-heavy", "share-big", "share-none"])
def test_the_system_with_an_unknown_per_kernel_has_the_policys_values(seed, share_min, heavy, monkeypatch):
    """`policy_system` solved directly (a sparse LU) gives the dense evaluation's values, whatever states keep their edges (`Work.edgewise`)."""
    monkeypatch.setattr(ps, "SHARE_MIN", share_min)
    monkeypatch.setattr(ps, "HEAVY_SELF", heavy)
    source = random_graph(seed, 40)
    builder = PackedBuilder()
    for s in range(source.n):
        for offer, kernel in source.actions[s].items():
            builder.action(offer, source.costs[offer], builder.kernel(list(kernel), list(kernel.values())))
        builder.close_state(s in source.goal)
    graph = builder.build()
    work = ps.Work(graph)
    leave = work.shared_sums(np.ones(graph.n))
    _, optimal = dense_optimum(source)
    policy = np.full(graph.n, -1, dtype=np.int64)
    for s in range(graph.n):
        if s not in source.goal:
            tags = graph.act_tag[graph.act_ptr[s] : graph.act_ptr[s + 1]].tolist()
            policy[s] = graph.act_ptr[s] + tags.index(optimal[s])
    dense = ps.evaluate_policy(work, leave, policy, np.zeros(graph.n), 10_000, 1e-13, {})
    states = np.flatnonzero(policy >= 0)
    position = np.full(graph.n, len(states), dtype=np.int64)
    position[states] = np.arange(len(states))
    chosen = policy[states]

    system = ps.policy_system(work, leave, chosen, states, position)

    matrix = sp.csc_matrix((system.value, (system.row, system.col)), shape=(system.size, system.size))
    rhs = np.zeros(system.size)
    rhs[: len(states)] = system.scale * (graph.act_cost[chosen] / leave[chosen])
    assert sla.spsolve(matrix, rhs)[: len(states)].tolist() == pytest.approx(dense[states].tolist(), rel=1e-9)


def test_a_run_that_never_stalls_takes_the_same_path_bit_for_bit(monkeypatch):
    """An evaluation whose plain iteration converges never builds the sparse form: its values are those of the code without it, to the bit."""
    from test_solver_packed_stiff import BLOCKS, ring_policy

    graph, policy = ring_policy(BLOCKS, 10**3)  # rings of 1,000 steps: BiCGSTAB converges
    asked = []
    info: dict = {}
    original = ps._PolicyTerms.sparse
    monkeypatch.setattr(ps._PolicyTerms, "sparse", lambda self: asked.append(1) or original(self))
    with_it = evaluate(graph, policy, info)
    monkeypatch.setattr(ps._PolicyTerms, "sparse", lambda self: None)
    without = evaluate(graph, policy, {})

    assert asked == [] and "preconditioned" not in info and "linear_cycles" not in info and info["linear_iterations"] > 0
    assert with_it.tobytes() == without.tobytes()
