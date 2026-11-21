"""The exact solve of a graph whose float64 certificate cannot reach its values (#1380): policy iteration in rational numbers on the quotient.

The failing shape is R17's round 1 on its whole Talisman (#1289): a bought start item, one Alchemy Orb that reaches the target with a chance of
2.4e-14, and a restart of 533 c from every miss back to the start. The plan costs 2.26e16 c, about 10^14 Orbs; float64 holds such a value to
`eps V`, about 5 c, larger than the margin of the restart, so no float64 certificate is within 0.18 of it, and every one of R17's rounds 1 to
12 was refused ("the policy iteration on 326 states certifies only a relative bound of 0.177"). Its 326 states merge into 3 classes.

ALCHEMY (hand-worked): state 0 pays `a = 1/8` and reaches the goal (1) with weight 1 of `W = 2^47`, else one of three misses (2, 3, 4) with
weights `2^45`, `2^46` and `2^45 - 1`; each miss pays `R = 533` and goes back to 0. With `p = 1 / W`, `V0 = a + (1 - p)(R + V0)`, so
`V0 = a W + (W - 1) R` and every miss is worth `R + V0`.
REROLL: the same, with a second action at each miss, a reroll of cost 2 with the distribution of the Alchemy Orb (R17's Chaos Orb round).
A miss rerolls (`2 W` against `R + a + 2 (W - 1)`): `Vm = 2 + (1 - p) Vm`, `Vm = 2 W`, and `V0 = a + (1 - p) Vm = a + 2 (W - 1)`.
"""

import sys
from fractions import Fraction

import numpy as np
import pytest
from test_solver_packed_long_sum_certificate import build

from crafting_system.solver import ConvergenceError
from crafting_system.solver import _exact_solve
from crafting_system.solver._packed_solve import solve_graph, solve_packed

EPS = sys.float_info.epsilon
W = 2**47
A = Fraction(1, 8)
R = 533
MISSES = ((2, 2**45), (3, 2**46), (4, 2**45 - 1))
ALCHEMY_V0 = A * W + (W - 1) * R
REROLL_V0 = A + 2 * (W - 1)


def alchemy(reroll: bool = False):
    draw = [(1, 1), *MISSES]
    miss = [(float(R), [(0, 1)])] + ([(2.0, draw)] if reroll else [])
    return build((False, [(float(A), draw)]), (True, []), *[(False, miss) for _ in MISSES])


@pytest.fixture
def float_only(monkeypatch):
    monkeypatch.setattr(_exact_solve, "EXACT_CLASSES", 0)


def test_float64_alone_cannot_certify_the_alchemy_round(float_only):
    # the failing shape: the refusal R17's rounds ended in, whatever the evaluation
    with pytest.raises(ConvergenceError) as refused:
        solve_graph(alchemy())
    assert refused.value.error_bound > 1e-3  # above even the share of a 1% gap a search takes its figures at
    with pytest.raises(ConvergenceError):
        solve_graph(alchemy(), refuse_above=1e-3)


def test_the_alchemy_round_is_solved_exactly_on_its_quotient():
    core = solve_graph(alchemy())

    assert sum(w for _, w in MISSES) == W - 1 and ALCHEMY_V0 > 7e16  # (the numbers above: about 10^17 steps of 1/8)
    assert core.certificate.exact and core.certificate.bound <= EPS
    assert core.value[0] == float(ALCHEMY_V0)  # the exact rational, rounded once
    assert list(core.value[2:]) == [float(R + ALCHEMY_V0)] * 3 and core.value[1] == 0.0
    assert list(core.action) == [0, -1, 1, 2, 3]  # the Alchemy Orb at the start, the restart at each miss


def test_the_reroll_round_picks_the_reroll_at_every_miss_and_its_exact_values():
    graph = alchemy(reroll=True)
    core = solve_graph(graph)

    assert REROLL_V0 < A + R + 2 * W  # a miss that restarts pays R and the start again: the reroll is cheaper
    assert core.certificate.exact
    assert core.value[0] == float(REROLL_V0) and list(core.value[2:]) == [float(2 * W)] * 3
    rerolls = [graph.act_ptr[s] + 1 for s in (2, 3, 4)]  # each miss: its restart first, its reroll second
    assert list(core.action[2:]) == rerolls


def test_the_merged_solve_keeps_the_exact_certificate_on_the_whole_graph():
    solved = solve_packed(alchemy())

    assert solved.error_bound <= EPS and solved.value[0] == float(ALCHEMY_V0)


def test_a_quotient_above_the_exact_size_is_still_refused():
    # a chain of more classes than `EXACT_CLASSES` (each state pays its own cost, so none merges) before the long draw: float64 refuses it as
    # before, and the rational solve is not tried
    k = _exact_solve.EXACT_CLASSES + 1
    chain = [(False, [(float(i + 1), [(i + 1, 1)])]) for i in range(k - 1)]
    last = (False, [(1.0, [(k, 1), (0, W - 1)])])
    with pytest.raises(ConvergenceError):
        solve_graph(build(*chain, last, (True, [])))


def test_a_graph_no_policy_of_which_reaches_the_goal_gives_no_exact_solve():
    # the rational solve answers only where a proper policy exists over the states it is given
    graph = build((False, [(1.0, [(1, 1)])]), (False, [(1.0, [(0, 1)])]), (True, []))
    assert _exact_solve.exact_quotient(graph, np.array([True, True, False])) is None
