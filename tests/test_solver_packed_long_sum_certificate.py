"""The certificate of the packed solve where a Bellman sum is long and the value is many steps (ticket #867, cause 1).

The certificate allows `(m + 2) eps` of a computed sum of `m` terms for its rounding, and the bound is that allowance times the value over the
cost of a step. A reroll with thousands of outcomes at a state worth a million steps is refused on the allowance alone, whatever the values
(the family's `start-fractured/large`: 810 keys, a sum of 735 terms at a key worth 7.5e7 steps, bound 1.2e-5 with the residual at 1.4e-15 of
the value). `certify` measures such a plan again with every sum rounded once (`_packed.kernel_sums_rounded_once`): the allowance is then
`4 eps` whatever the length.

WIDE: state 0 pays 1 and goes to the goal with weight 1 and to each of 3,000 states with weight 300; each of those pays 1 and goes back.
With `L = 900,001` the total weight: `V(0) = 1 + (1 - 1/L) (1 + V(0))`, so `V(0) = 2 L - 1 = 1,800,001` and the others `2 L = 1,800,002`.
The allowance of state 0's sum is `3,004 eps * 1,800,001 = 1.2e-6` of its cost of 1: above the 1e-6 accepted.
"""

import sys
from fractions import Fraction

import numpy as np
import pytest

from crafting_system.solver import PackedBuilder
from crafting_system.solver._packed import kernel_sums, kernel_sums_rounded_once, rounded_once_allowance
from crafting_system.solver._packed_solve import ACCEPT_BOUND, _certify, Work, certify, solve_graph

EPS = sys.float_info.epsilon
SIDES = 3000
WEIGHT = 300
TOTAL = 1 + SIDES * WEIGHT


def build(*states):
    """A graph from `(is_goal, [(cost, [(successor, weight), ...]), ...])` per state."""
    builder = PackedBuilder()
    tag = 0
    for goal, actions in states:
        for cost, outcomes in actions:
            builder.action(tag, cost, builder.kernel([s for s, _ in outcomes], [w for _, w in outcomes]))
            tag += 1
        builder.close_state(goal)
    return builder.build()


def wide():
    reroll = (False, [(1.0, [(1, 1)] + [(2 + i, WEIGHT) for i in range(SIDES)])])
    return build(reroll, (True, []), *[(False, [(1.0, [(0, 1)])]) for _ in range(SIDES)])


WIDE_VALUE = np.array([2.0 * TOTAL - 1.0, 0.0] + [2.0 * TOTAL] * SIDES)


def test_a_sum_rounded_once_is_the_exact_sum_rounded_where_adding_term_by_term_can_lose_every_small_term():
    # four outcomes of chance 1/4 with f = 2^54, 1, 1, 1: the exact sum is 2^52 + 0.75, which rounds to 2^52 + 1; added one after the other, each
    # 0.25 is rounded away from 2^52 (the order of `kernel_sums` is numpy's, so its result is not asserted)
    graph = build((False, [(1.0, [(1, 1), (2, 1), (3, 1), (4, 1)])]), (True, []), (True, []), (True, []), (True, []))
    f = np.array([0.0, 2.0**54, 1.0, 1.0, 1.0])

    assert ((2.0**52 + 0.25) + 0.25) + 0.25 == 2.0**52
    assert kernel_sums(graph, f)[0] in (2.0**52, 2.0**52 + 1.0)
    assert kernel_sums_rounded_once(graph, f)[0] == 2.0**52 + 1.0


def test_a_sum_rounded_once_is_within_half_an_epsilon_of_the_exact_sum_of_its_products():
    graph = wide()
    rng = np.random.default_rng(867)
    f = rng.random(graph.n) * 10.0 ** rng.integers(-6, 12, graph.n)
    f[::7] = 0.0
    exact = sum(Fraction(float(p)) * Fraction(float(f[s])) for p, s in zip(graph.k_prob[: SIDES + 1], graph.k_succ[: SIDES + 1]))

    got = kernel_sums_rounded_once(graph, f)

    assert abs(Fraction(float(got[0])) - exact) <= Fraction(EPS) / 2 * exact
    assert float(rounded_once_allowance(SIDES + 2)) == pytest.approx(4 * EPS, rel=1e-3)  # 16 m^3 eps^2 is nothing at 3,000 terms


def test_a_sum_that_cannot_be_taken_exactly_is_not_taken():
    graph = wide()
    for bad in (np.inf, -1.0, 1e200):  # not finite, negative, a factor whose split could overflow
        f = np.ones(graph.n)
        f[5] = bad
        assert kernel_sums_rounded_once(graph, f) is None
    f = np.ones(graph.n)
    f[0] = 1e-300  # the one product of each side state's sum is below 2^-960 (its low part underflows) and nothing larger stands beside it
    assert kernel_sums_rounded_once(graph, f) is None


def test_a_product_too_small_for_its_low_part_is_carried_beside_a_larger_one():
    # the guard is relative to the kernel: a product below 2^-960 (here 1e-300 / 900,001, and one that underflows to 0) costs the sum at most
    # 2^-1013 each, nothing beside the other products of the reroll
    graph = wide()
    f = np.ones(graph.n)
    f[5], f[6] = 1e-300, 5e-324
    exact = sum(Fraction(float(p)) * Fraction(float(f[s])) for p, s in zip(graph.k_prob[: SIDES + 1], graph.k_succ[: SIDES + 1]))

    got = kernel_sums_rounded_once(graph, f)

    assert got is not None and abs(Fraction(float(got[0])) - exact) <= Fraction(EPS) / 2 * exact


# TIP: WIDE with weight 600 a side and one more outcome of weight 1, a tip the search has not looked at whose bound is 0. The planner carries such
# a tip as an action of cost 1e-200 to the goal (`_envelope.FLOOR`, `_pattern_bound.FLOOR_COST`), so its value is 1e-200. With `L = 1,800,002`
# the total weight: `V(0) = 1 + (1e-200 / L) + (1 - 2/L) (1 + V(0))`, so `V(0) = L - 1 + 5e-201 = 1,800,001` and the others `1,800,002`.
# The allowance of state 0's sum term by term is `3,005 eps * 1,800,001 = 1.2e-6` of its cost of 1: above the 1e-6 accepted.
TIP_WEIGHT = 600
TIP_TOTAL = 2 + SIDES * TIP_WEIGHT
FLOOR = 1e-200


def with_a_tip():
    reroll = (False, [(1.0, [(1, 1), (2, 1)] + [(3 + i, TIP_WEIGHT) for i in range(SIDES)])])
    return build(reroll, (True, []), (False, [(FLOOR, [(1, 1)])]), *[(False, [(1.0, [(0, 1)])]) for _ in range(SIDES)])


TIP_VALUE = np.array([TIP_TOTAL - 1.0, 0.0, FLOOR] + [float(TIP_TOTAL)] * SIDES)


def test_a_tip_of_bound_zero_does_not_switch_the_sums_rounded_once_off():
    from crafting_system.planner._envelope import FLOOR as SEARCH_FLOOR
    from crafting_system.planner._pattern_bound import FLOOR_COST

    assert SEARCH_FLOOR == FLOOR_COST == FLOOR  # the cost the planner gives a tip of bound 0: the figure the test is about
    graph = with_a_tip()

    sums = kernel_sums_rounded_once(graph, TIP_VALUE)  # the product of the tip is 1e-200 / 1,800,002: below the planner's floor
    core = solve_graph(graph)  # with a guard at 1e-200: ConvergenceError, "certifies only a relative bound of 1.2e-06"

    assert sums is not None and sums[0] == (TIP_TOTAL - 2.0) * TIP_TOTAL / TIP_TOTAL  # (L - 2) / L of L, and 5e-207 of the tip: nothing in float64
    assert core.value == pytest.approx(TIP_VALUE, rel=1e-9)
    assert core.certificate.bound < 1e-8 and core.certificate.rounded_once
    assert abs(core.value[0] / TIP_VALUE[0] - 1.0) <= core.certificate.bound


def test_the_allowance_of_a_long_sum_alone_refuses_exact_values_and_the_sum_rounded_once_certifies_them():
    graph = wide()
    solved = np.ones(graph.n, dtype=bool)
    work = Work(graph)

    term_by_term = _certify(graph, WIDE_VALUE, solved, work, ACCEPT_BOUND, False)
    certificate = certify(graph, WIDE_VALUE, solved)

    # by hand: rho = (3,002 + 2) eps (3,001 outcomes and the cost), delta = rho / (1 - rho) * V(0), the upper side delta / (1 - delta)
    rho = (SIDES + 4) * EPS
    delta = rho / (1 - rho) * (2.0 * TOTAL - 1.0)
    assert term_by_term.bound == pytest.approx(delta / (1.0 - delta), rel=1e-6) and term_by_term.bound > ACCEPT_BOUND
    assert term_by_term.residual < 1e-9  # the values are the exact ones: what refuses them is the allowance
    # rounded once: the allowance of the side states' sum of one term is 4 eps (2 L), against their cost of 1
    assert certificate.rounded_once and certificate.term_bound == term_by_term.bound
    assert certificate.bound == pytest.approx(4 * EPS * 2 * TOTAL, rel=0.5) and certificate.bound < 1e-8


def test_the_solve_of_a_wide_reroll_worth_a_million_steps_is_certified():
    core = solve_graph(wide())  # before #867: ConvergenceError, "certifies only a relative bound of 1.2e-06"

    assert core.value == pytest.approx(WIDE_VALUE, rel=1e-9)
    assert core.certificate.bound < 1e-8 and core.certificate.rounded_once
    assert abs(core.value[0] / WIDE_VALUE[0] - 1.0) <= core.certificate.bound  # the bound holds of the exact value, worked by hand


def test_a_plan_that_certifies_term_by_term_is_not_measured_again():
    graph = build((False, [(1.0, [(1, 1), (0, 1023)])]), (True, []))

    certificate = certify(graph, np.array([1024.0, 0.0]), np.ones(2, dtype=bool))

    assert certificate.bound <= ACCEPT_BOUND and not certificate.rounded_once
