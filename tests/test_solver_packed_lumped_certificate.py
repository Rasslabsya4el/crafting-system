"""The whole graph's check of a merged solve, where float64 cannot measure on the graph what it measured on the quotient (#1412).

The failing shape is R17's growth seed round (#1414's comment on #1412): a plan of about 10^12 attempts at 1.7e12 c whose 468,783 states merge into
4 classes (`.claude/scratch/t1412/analyze_float.out` on the server). On the quotient a class is one state that stays with chance `1 - p`; the certificate divides that stay out (`_divided`) and certified
the values to 0.00092. On the whole graph the members of a class pass the run to each other, a cycle of many states with no self-loop, whose
margin is one step: its rounding allowance alone, `eps V` over the cost of a step, was 0.0737, and `solve_packed` refused a right plan ("the
merge or the solve is wrong"). The merge is exact in integers, so the check is made there (`lumps_exactly`), and the quotient's certificate is
carried to the members.

SWAP (hand-worked): states 0 and 1 each pay `c = 1` and hand the run to the other with weight `W - 1` of `W = 2^45`, or reach the goal (2) with
weight 1. They are one class; the quotient is one state that stays with chance `1 - 1/W`, so `V = c + (1 - 1/W) V`, `V = c W = 2^45` (3.5e13
steps), and float64 holds it exactly. On the whole graph `eps V / c` is 0.0078: no measure there is within 1e-3 of it.
UNEVEN: the same, but state 1 reaches the goal with weight 2 of `W + 1`; then `V0 = 1 + (1 - 1/W) V1`, `V1 = 1 + ((W - 1) / (W + 1)) V0`. Forced
into one class by a wrong merge, the quotient (state 0's actions) gives `W` to both, which is wrong for state 1 by a factor of about 2.
"""

import sys

import numpy as np
import pytest
from test_solver_packed_long_sum_certificate import build

from crafting_system.solver import ConvergenceError
from crafting_system.solver import _packed_solve
from crafting_system.solver._packed import PackedBuilder
from crafting_system.solver._packed_merge import Classes, exact_classes, lumps_exactly, quotient
from crafting_system.solver._packed_solve import certify, solve_graph, solve_packed

EPS = sys.float_info.epsilon
W = 2**45


def swap():
    return build((False, [(1.0, [(1, W - 1), (2, 1)])]), (False, [(1.0, [(0, W - 1), (2, 1)])]), (True, []))


def uneven():
    return build((False, [(1.0, [(1, W - 1), (2, 1)])]), (False, [(1.0, [(0, W - 1), (2, 2)])]), (True, []))


def merged(graph):
    classes = exact_classes(graph)
    reduced, kernel_map = quotient(graph, classes)
    return classes, reduced, kernel_map


def test_the_whole_graph_alone_cannot_measure_the_swap_to_a_gap():
    graph = swap()
    value = np.array([float(W), float(W), 0.0])  # the exact values (2^45 is a float64)

    assert certify(graph, value, np.ones(3, dtype=bool), wanted=1e-3).bound > 1e-3  # the refusal R17's seed round met, on exact values


@pytest.mark.parametrize("refuse_above", [None, 1e-3])
def test_a_merge_checked_exact_carries_the_quotients_certificate(refuse_above):
    solved = solve_packed(swap(), refuse_above=refuse_above)

    assert solved.classes == 2
    assert solved.value.tolist() == [float(W), float(W), 0.0]
    assert solved.error_bound <= 1e-6  # the quotient's, not the whole graph's
    assert solved.info["graph_bound"] > 1e-3  # what the whole graph's own measure gave, kept for the report


def test_a_wrong_merge_is_refused_still(monkeypatch):
    graph = uneven()
    assert exact_classes(graph).count == 3  # the right merge keeps 0 and 1 apart
    forced = Classes(np.array([1, 1, 0]), 2, 1)
    monkeypatch.setattr(_packed_solve, "exact_classes", lambda _graph, _say: forced)

    reduced, _ = quotient(graph, forced)
    assert solve_graph(reduced, refuse_above=1e-3).certificate.bound <= 1e-6  # the wrong quotient certifies itself: only the check can refuse
    assert not lumps_exactly(graph, forced.cls, *quotient(graph, forced))
    with pytest.raises(ConvergenceError, match="the merge or the solve is wrong"):
        solve_packed(graph, refuse_above=1e-3)


def test_the_exact_merge_of_each_shape_lumps():
    for graph in (swap(), uneven()):
        classes, reduced, kernel_map = merged(graph)
        assert lumps_exactly(graph, classes.cls, reduced, kernel_map)


def test_a_kernel_of_python_integers_is_checked_in_python_integers():
    # weights adding up to 2^62 or more are kept apart as Python integers (`BIG_TOTAL`); two states reach the same two classes with the same
    # chances written on different totals (one doubled), and a third with a chance one part in 2^63 apart
    big = 2**63

    def graph(last: int):
        return build(
            (False, [(1.0, [(3, big), (4, big)])]),
            (False, [(1.0, [(3, 2 * big), (4, 2 * big)])]),
            (False, [(1.0, [(3, big), (4, last)])]),
            (True, []),
            (False, [(1.0, [(3, 1)])]),
        )

    same = graph(big)
    classes, reduced, kernel_map = merged(same)
    assert classes.count == 3 and same.k_big
    assert lumps_exactly(same, classes.cls, reduced, kernel_map)
    apart = graph(big + 1)
    assert not lumps_exactly(apart, classes.cls, *quotient(apart, classes))


def test_each_part_of_the_check_refuses_its_own_fault():
    graph = swap()
    classes, reduced, kernel_map = merged(graph)
    cls = classes.cls

    def changed(cost=1.0, weight=W - 1, goal=True):
        builder = PackedBuilder()
        builder.action(0, 1.0, builder.kernel([1, 2], [W - 1, 1]))
        builder.close_state(False)
        builder.action(1, cost, builder.kernel([0, 2], [weight, 1]))
        builder.close_state(False)
        builder.close_state(goal)
        return builder.build()

    assert lumps_exactly(changed(), cls, reduced, kernel_map)  # (the same graph, built again)
    assert not lumps_exactly(changed(cost=1.0 + 2 * EPS), cls, reduced, kernel_map)  # a cost one bit apart
    assert not lumps_exactly(changed(weight=W - 2), cls, reduced, kernel_map)  # a chance one part in 2^45 apart
    assert not lumps_exactly(graph, cls, reduced, np.zeros_like(kernel_map) + reduced.num_kernels)  # a kernel map out of the quotient
    wrong_goal = Classes(np.array([1, 1, 1]), 2, 1)
    assert not lumps_exactly(graph, wrong_goal.cls, reduced, kernel_map)  # a goal in a class that is not one
