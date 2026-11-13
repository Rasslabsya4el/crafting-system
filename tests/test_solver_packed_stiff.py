"""The evaluation of a stiff policy above the old dense-fallback count (6,000 states) is solved, not refused (ticket #621, with #584, #600 and #615).

The policy is built to have an answer that does not need a solve to know: `blocks` rings of three states, each ring state going round the ring with
weight `10**power` against 1 out of it into the block's reroll state, and the reroll states taking three shared kernels (every block head with
a weight of its own, and the goal one time in a hundred). A run is in a ring for `10**power` steps, goes out into a reroll, lands in a random ring, and so on; the cycle of
the ring has no self-loop to divide out, and the three kernels of 1,600 outcomes each tie all the 6,400 states into one component. The exact
values are worked out here in `Fraction`s from the floats the graph stores (a ring is a 3-state system, the three rerolls a 3 x 3 one), so that the check
is of the solve and not of the rounding of the chances themselves (a chance `1 - 1e-13` is stored to 1e-16, which is 1e-3 of what the ring leaves).

Before #621 an evaluation of more than `DENSE_FALLBACK` (6,000) states whose BiCGSTAB iterate had a true residual above `ACCEPT_BOUND` was refused
whatever the iterate: at a ring weight of 1e9 the iterate was good to the last digit (a backward error of 1e-15) but its residual `|b - A x| / |b|` was 4e-4 because the answer is 1e9
times the right-hand side, and at 1e13 the iterate was wrong. Now the first is accepted on its backward error and the second is solved by the cycles of the policy's chain.
"""

from fractions import Fraction

import numpy as np
import pytest

from crafting_system.solver import PackedBuilder
from crafting_system.solver import _packed_solve as ps

BLOCKS = 1600  # 6,400 policy states, above the 6,000 of the old `DENSE_FALLBACK`


def ring_policy(blocks: int, ring_weight: int):
    """`(graph, policy)`: the states are ring states `3 j + r`, reroll states `3 blocks + j` and the goal."""
    builder = PackedBuilder()
    goal = 4 * blocks
    kernels = []
    for k in range(3):
        weights = [1 + (i * (k + 2)) % 7 for i in range(blocks)]
        kernels.append(builder.kernel([3 * i for i in range(blocks)] + [goal], weights + [sum(weights) // 99 + 1]))
    tag = 0
    for j in range(blocks):
        for r in range(3):
            builder.action(tag, float(1 + j % 5), builder.kernel([3 * j + (r + 1) % 3, 3 * blocks + j], [ring_weight, 1]))
            builder.close_state(False)
            tag += 1
    for j in range(blocks):
        builder.action(tag, 2.0, kernels[j % 3])
        builder.close_state(False)
        tag += 1
    builder.close_state(True)
    return builder.build(), np.append(np.arange(4 * blocks), -1)


def solve_exactly(rows: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    n = len(rhs)
    table = [[*rows[i], rhs[i]] for i in range(n)]
    for c in range(n):
        pivot = next(r for r in range(c, n) if table[r][c] != 0)
        table[c], table[pivot] = table[pivot], table[c]
        table[c] = [v / table[c][c] for v in table[c]]
        for r in range(n):
            if r != c and table[r][c] != 0:
                table[r] = [a - table[r][c] * b for a, b in zip(table[r], table[c])]
    return [table[i][n] for i in range(n)]


def exact_values(graph, work, leave, blocks: int, ring_weight: int) -> list[Fraction]:
    """The values of the policy by `Fraction` elimination: the rings from their integer weights (`ring_weight` against 1: no rounding), the rerolls from the
    coefficients the evaluation itself forms (`k_prob / leave` and `cost / leave` as floats; they are far from stiff).

    The rings are taken from their weights because their stored chances are not their system: `ring_weight / (ring_weight + 1)` is stored to 1e-16, and
    `1` minus it, the chance to leave a ring state that a solve of `I - P` reads, is then 1e-3 off at 1e13; the leak itself is stored to 1e-16 (#700)."""

    def coefficients(action: int) -> list[Fraction]:
        if action < 3 * blocks:  # a ring state: on round the ring, or out into the reroll
            return [Fraction(ring_weight, ring_weight + 1), Fraction(1, ring_weight + 1)]
        k = int(graph.act_kernel[action])
        span = slice(int(graph.k_ptr[k]), int(graph.k_ptr[k + 1]))
        return [Fraction(float(x)) for x in graph.k_prob[span] / leave[action]]

    def cost(action: int) -> Fraction:
        if action < 3 * blocks:
            return Fraction(float(graph.act_cost[action]))  # (a ring state has no self-loop: its chance to leave is 1)
        return Fraction(float(graph.act_cost[action] / leave[action]))

    alpha, beta = [], []  # head value of block j = alpha + beta * U[j % 3], U the value of the reroll state its ring leaves into
    ring_values = []
    for j in range(blocks):
        rows = [[Fraction(0)] * 3 for _ in range(3)]
        rhs0, rhs1 = [], []
        for r in range(3):
            around, out = coefficients(3 * j + r)
            rows[r][r] += 1
            rows[r][(r + 1) % 3] -= around
            rhs0.append(cost(3 * j + r))
            rhs1.append(cost(3 * j + r) + out)  # with U = 1
        v0, v1 = solve_exactly(rows, rhs0), solve_exactly(rows, rhs1)
        ring_values.append((v0, [b - a for a, b in zip(v0, v1)]))
        alpha.append(v0[0])
        beta.append(v1[0] - v0[0])
    system = [[Fraction(int(i == k)) for i in range(3)] for k in range(3)]
    rhs = []
    for k in range(3):
        action = 3 * blocks + k  # the first reroll state of class k
        *heads, _goal = coefficients(action)
        total = cost(action) + sum((heads[i] * alpha[i] for i in range(blocks)), Fraction(0))
        for i in range(blocks):
            system[k][i % 3] -= heads[i] * beta[i]
        rhs.append(total)
    u = solve_exactly(system, rhs)
    values: list[Fraction] = []
    for j in range(blocks):
        v0, slope = ring_values[j]
        values.extend(a + b * u[j % 3] for a, b in zip(v0, slope))
    values.extend(u[j % 3] for j in range(blocks))
    return values


@pytest.mark.parametrize("power", [9, 13])
def test_a_stiff_policy_above_the_old_dense_fallback_count_is_solved_not_refused(power):
    graph, policy = ring_policy(BLOCKS, 10**power)
    work = ps.Work(graph)
    leave = work.nonself_sums(np.ones(work.n))
    info: dict = {}
    assert int((policy >= 0).sum()) > 6_000  # above the count that used to decide

    values = ps.evaluate_policy(work, leave, policy, np.zeros(work.n), ps.DENSE_LIMIT, 1e-13, info)

    assert info["policy_states"] == 6400 and info["linear_backward_error"] <= 1e-12
    exact = exact_values(graph, work, leave, BLOCKS, 10**power)
    # the 3-state rings are inverted without a subtraction (#700) and the shared rerolls put back by the Woodbury step: the values are good to the
    # rounding of the sums at 1e9 and 1e13 alike (an LU inverse of the rings left 7 digits at 1e9; the iterate of the old code was 4e-4 off at 1e9 and wrong at 1e13)
    assert values[: 4 * BLOCKS] == pytest.approx([float(x) for x in exact], rel=1e-12)
    assert info["linear_cycles"] == 1 and info["linear_cut_rows"] == 3  # the three shared rerolls are cut and put back
    assert info["linear_forward_iterate"] > ps._packed_linear.ACCEPT_ERROR  # the iterate is not good by what bounds its error: the exact solve was made


def test_the_old_count_is_not_read_and_a_memory_that_does_not_hold_the_cycles_is_said_by_what_they_cost(monkeypatch):
    graph, policy = ring_policy(BLOCKS, 10**13)
    work = ps.Work(graph)
    leave = work.nonself_sums(np.ones(work.n))
    info: dict = {}  # (no count of states is read: the old `DENSE_FALLBACK`, 6,000, is gone)
    ps.evaluate_policy(work, leave, policy, np.zeros(work.n), ps.DENSE_LIMIT, 1e-13, info)
    assert info["linear_cycles"] == 1

    from crafting_system.solver import _packed_chain

    monkeypatch.setattr(_packed_chain, "WOODBURY_CELLS", 1_000)  # the memory of a small machine
    with pytest.raises(ps.ConvergenceError) as refused:
        ps.evaluate_policy(work, leave, policy, np.zeros(work.n), ps.DENSE_LIMIT, 1e-13, {})

    words = str(refused.value)
    assert "6,400 states" in words and "backward error" in words and "distinct cut rows" in words and "past the 1,000" in words


def test_what_remains_when_the_cycles_do_not_fit_is_a_limit_that_names_the_memory_they_needed(monkeypatch):
    from crafting_system.planner._packed import evaluation_limits
    from crafting_system.solver import _packed_chain

    graph, policy = ring_policy(BLOCKS, 10**9)
    work = ps.Work(graph)
    leave = work.nonself_sums(np.ones(work.n))
    monkeypatch.setattr(_packed_chain, "WOODBURY_CELLS", 1_000)  # the memory of a small machine
    monkeypatch.setattr(ps, "ACCEPT_BOUND", 1e-3)  # the iterate (a true residual of 4e-4) is accepted as it is
    info: dict = {}

    ps.evaluate_policy(work, leave, policy, np.zeros(work.n), ps.DENSE_LIMIT, 1e-13, info)

    found = info["linear_limit"]
    assert found["states"] == 6400 and found["rows"] == 3 and found["allowed"] == 1_000 and found["cells"] > 1_000 and 1e-10 < found["residual"] <= 1e-3 and found["amplification"] > 1e5
    (limit,) = evaluation_limits(info)
    assert "6,400 states" in limit.why and "GB of memory" in limit.why and limit.what == "How much each state costs was found by approximation"
    assert evaluation_limits({}) == () and evaluation_limits({"policy_states": 6400}) == ()  # an exact solve, or none needed, says nothing


def test_the_shared_rows_of_the_policy_are_given_once_and_never_expanded_state_by_state():
    graph, policy = ring_policy(BLOCKS, 10**13)
    work = ps.Work(graph)
    leave = work.nonself_sums(np.ones(work.n))
    states = np.flatnonzero(policy >= 0)
    position = np.full(work.n, len(states), dtype=np.int64)
    position[states] = np.arange(len(states))

    solver = ps.policy_solver(work, leave, policy[states], position)

    assert solver.q == 3 and sorted(len(g) for g in solver.groups) == [533, 533, 534]  # BLOCKS / 3 rerolls take each kernel
    assert solver.cut.sum() == BLOCKS and not solver.cut[: 3 * BLOCKS].any()  # only the reroll states are cut


# (The iterate with a tiny backward error that is 1e-5 off, #699, is in `tests/test_linear_solve.py`, with the ring of #700 and the 100,000 states of #671.)
