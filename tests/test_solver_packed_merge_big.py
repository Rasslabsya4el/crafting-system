"""The exact merge of kernels whose weights have thousands of digits (ticket #868).

A kernel's integer weights are its chances on their common denominator, which grows with every distinct denominator: a Chaos Orb
kernel of 148,436 successors whose chances have at most 490 bits each has a common denominator of 22,965 bits. The merge keyed such
a kernel by the decimal text of its weights, which Python refuses past 4,300 digits (`ValueError`) and which costs time quadratic
in the digits. The weights below have 4,342 digits; the merge keys them as integers and gives the answer of the unmerged graph.
"""

import sys

import numpy as np
import pytest

from crafting_system.solver import PackedBuilder, solve_packed
from crafting_system.solver._packed_merge import exact_classes

X = 3**9100  # 4,342 decimal digits
Y = X + 1  # coprime to X: the weights (X, Y) do not reduce


def hand_worked_graph():
    """Start 3 rolls one of 0, 1, 2 (a third each, cost 1); each of those tries at cost 1 and reaches the goal 4 with chance X / (X + Y), else stays.

    0 and 1 have the same chances (1 on twice the weights), so they are one class; 2 keeps one more part in 10^4342 and is a class
    of its own. Hand-worked: a try costs (X + Y) / X = 2 + 1 / X tries on average, 2 + 2 / X at state 2, so 2.0 in floats at all
    three, and the start costs 1 + 2 = 3.0.
    """
    builder = PackedBuilder()
    k0 = builder.kernel([4, 0], [X, Y])
    k1 = builder.kernel([4, 1], [2 * X, 2 * Y])
    k2 = builder.kernel([4, 2], [X, Y + 1])
    roll = builder.kernel([0, 1, 2], [1, 1, 1])
    for state, kernel in ((0, k0), (1, k1), (2, k2)):
        builder.action(state, 1.0, kernel)
        builder.close_state(False)
    builder.action(3, 1.0, roll)
    builder.close_state(False)
    builder.close_state(True)
    return builder.build()


def test_weights_of_thousands_of_digits_could_not_be_written_as_text():
    """The old key: the decimal text of the weights, which Python refuses at this size (unless the process lifts its own limit)."""
    if sys.get_int_max_str_digits() == 0 or sys.get_int_max_str_digits() > 4342:
        pytest.skip("this interpreter writes integers of any length as text")
    with pytest.raises(ValueError, match="4300 digits"):
        repr((X, Y))


def test_the_merge_keys_huge_weights_as_integers_and_keeps_exact_classes():
    graph = hand_worked_graph()
    assert set(graph.k_big) == {0, 1, 2}

    classes = exact_classes(graph)

    cls = classes.cls.tolist()
    assert classes.count == 4  # {0, 1}, {2}, {3}, the goal
    assert cls[0] == cls[1] and len({cls[1], cls[2], cls[3], cls[4]}) == 4


def test_the_merged_solve_gives_the_answer_of_the_unmerged_one():
    graph = hand_worked_graph()

    merged = solve_packed(graph)
    whole = solve_packed(graph, merge=False)

    assert merged.classes == 4 and whole.classes == graph.n  # the number of classes
    assert np.array_equal(merged.value, whole.value)
    assert merged.value.tolist() == pytest.approx([2.0, 2.0, 2.0, 3.0, 0.0], rel=1e-15)  # the start's sum of thirds rounds in its last bit
