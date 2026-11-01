"""Mean, variance and donor counts of a policy whose actions consume other runs (`extra_inputs`).

The references are exact `Fraction` closed forms built here from geometric attempt counts (a run of
independent attempts, each costing `X`, until the first success) and from hand-solved systems; none
of them calls `crafting_system.risk`.
"""

from fractions import Fraction as F

import pytest
from risk_support import geometric_moments

from crafting_system.risk import _moments
from crafting_system.risk._chain import build_chain
from crafting_system.risk._inputs import (
    NotSubcritical,
    branching,
    expected_uses,
    input_starts_in_order,
    mean_and_variance,
    solve_costs,
)
from crafting_system.risk._moments import real_costs
from crafting_system.solver import Action


def build(policy, start, done):
    return build_chain(policy, start, lambda state: state in done)


def attempts(p, mean, variance):
    """Mean and variance of a sum of `N` independent copies of `X`, `N` geometric with success chance `p`."""
    return mean / p, variance / p + (1 - p) / p**2 * mean**2


def check_moments(chain, mean, variance):
    (m, m_low, m_high), (v, v_low, v_high), _ = mean_and_variance(chain)
    assert m_low <= mean <= m_high
    assert v_low <= variance <= v_high
    assert m == pytest.approx(float(mean), rel=1e-12)
    assert v == pytest.approx(float(variance), rel=1e-12)
    assert (m_high - m_low) <= 1e-9 * float(mean)
    assert (v_high - v_low) <= 1e-9 * float(variance)


def check_uses(chain, expected):
    values, error = solve_costs(chain, real_costs(chain))
    uses = expected_uses(chain, values, error)
    assert {chain.states[y] for y in uses} == expected.keys()
    for y, (value, low, high) in uses.items():
        exact = expected[chain.states[y]]
        assert low <= exact <= high
        assert value == pytest.approx(float(exact), rel=1e-12)


def donor_policy():
    """D: cost 3, finishes with chance 1/3; S: cost 2, needs one run of D per attempt, succeeds with 1/4."""
    return {
        "D": Action("d", 3, (("done", 1), ("D", 2))),
        "S": Action("s", 2, (("goal", 1), ("S", 3)), extra_inputs=("D",)),
    }


def test_one_donor_matches_the_hand_case():
    chain = build(donor_policy(), "S", {"goal", "done"})
    assert chain.proper
    # a donor run costs 9 with variance 54; an attempt costs 2 + A; 4 attempts on average
    donor = geometric_moments(F(1, 3), F(3))
    assert donor == (9, 54)
    mean, variance = attempts(F(1, 4), 2 + donor[0], donor[1])
    assert (mean, variance) == (44, 1668)  # second moment 3604
    check_moments(chain, mean, variance)
    check_uses(chain, {"D": F(4)})
    donor_index = chain.states.index("D")
    assert mean_and_variance(chain)[2][donor_index] == pytest.approx(9.0, rel=1e-12)


def test_the_donor_alone_is_a_geometric_run():
    chain = build(donor_policy(), "D", {"goal", "done"})
    check_moments(chain, F(9), F(54))
    assert expected_uses(chain, *solve_costs(chain, real_costs(chain))) == {}


def test_an_input_shared_by_two_copies():
    policy = {
        "D": Action("d", 3, (("done", 1), ("D", 2))),
        "S": Action("s", 2, (("goal", 1), ("S", 3)), extra_inputs=("D", "D")),
    }
    chain = build(policy, "S", {"goal", "done"})
    donor = geometric_moments(F(1, 3), F(3))
    mean, variance = attempts(F(1, 4), 2 + 2 * donor[0], 2 * donor[1])
    assert (mean, variance) == (80, 5232)
    check_moments(chain, mean, variance)
    check_uses(chain, {"D": F(8)})


def test_two_different_donors():
    policy = {
        "D": Action("d", 3, (("done", 1), ("D", 2))),
        "E": Action("e", 1, (("done", 1), ("E", 1))),
        "S": Action("s", 2, (("goal", 2), ("S", 1)), extra_inputs=("D", "E")),
    }
    chain = build(policy, "S", {"goal", "done"})
    d = geometric_moments(F(1, 3), F(3))
    e = geometric_moments(F(1, 2), F(1))
    assert e == (2, 2)
    mean, variance = attempts(F(2, 3), 2 + d[0] + e[0], d[1] + e[1])
    check_moments(chain, mean, variance)
    check_uses(chain, {"D": F(3, 2), "E": F(3, 2)})


def nested_policy():
    return {
        "D2": Action("d2", 1, (("done", 1), ("D2", 3))),
        "D1": Action("d1", 2, (("done", 1), ("D1", 1)), extra_inputs=("D2",)),
        "S": Action("s", 1, (("goal", 2), ("S", 1)), extra_inputs=("D1",)),
    }


def test_a_donor_that_needs_a_donor():
    chain = build(nested_policy(), "S", {"goal", "done"})
    inner = geometric_moments(F(1, 4), F(1))
    middle = attempts(F(1, 2), 2 + inner[0], inner[1])
    assert middle == (12, 96)
    mean, variance = attempts(F(2, 3), 1 + middle[0], middle[1])
    check_moments(chain, mean, variance)
    # D1 once per attempt (3/2 attempts), D2 twice per D1 run
    check_uses(chain, {"D1": F(3, 2), "D2": F(3)})
    assert not branching(chain)
    assert [chain.states[y] for y in input_starts_in_order(chain)] == ["D2", "D1"]


def test_the_order_of_a_single_shared_input():
    chain = build(donor_policy(), "S", {"goal", "done"})
    assert [chain.states[y] for y in input_starts_in_order(chain)] == ["D"]


def cycle_policy():
    """T pays 1 and returns S half the time, S pays 2 and needs a run of T per attempt (chance 3/4)."""
    return {
        "S": Action("s", 2, (("goal", 3), ("S", 1)), extra_inputs=("T",)),
        "T": Action("t", 1, (("done", 1), ("S", 1))),
    }


def test_inputs_in_a_cycle_with_the_outcomes():
    chain = build(cycle_policy(), "S", {"goal", "done"})
    assert chain.proper
    assert branching(chain)
    with pytest.raises(ValueError):
        input_starts_in_order(chain)
    # V_S = 2 + V_T + V_S / 4 and V_T = 1 + V_S / 2 give V_S = 12, V_T = 7.
    # With B_S = 0 (3/4) or a fresh run of S (1/4), B_T = 0 or a fresh run of S (1/2), independent runs:
    # E[A_S^2] = 86 + E[A_T^2] + E[A_S^2] / 4 and E[A_T^2] = 13 + E[A_S^2] / 2, so E[A_S^2] = 396.
    check_moments(chain, F(12), F(396 - 144))
    assert mean_and_variance(chain)[2][chain.states.index("T")] == pytest.approx(7.0, rel=1e-12)
    # N_T = N_S and N_S = 1 + N_S / 4 + N_T / 2
    check_uses(chain, {"T": F(4)})


def test_a_critical_cycle_is_not_subcritical():
    policy = {
        "S": Action("s", 2, (("goal", 1), ("S", 1)), extra_inputs=("T",)),
        "T": Action("t", 1, (("done", 1), ("S", 1))),
    }
    chain = build(policy, "S", {"goal", "done"})
    assert chain.proper
    with pytest.raises(NotSubcritical):
        mean_and_variance(chain)


def test_two_copies_of_an_input_that_comes_back_half_the_time_is_supercritical():
    policy = {
        "S": Action("s", 1, (("goal", 1), ("S", 1)), extra_inputs=("T", "T")),
        "T": Action("t", 1, (("done", 1), ("S", 1))),
    }
    chain = build(policy, "S", {"goal", "done"})
    assert chain.proper
    assert branching(chain)
    with pytest.raises(NotSubcritical):
        solve_costs(chain, real_costs(chain))
    with pytest.raises(NotSubcritical):
        mean_and_variance(chain)


def test_an_action_that_lists_its_own_state_is_branching_and_never_finishes():
    policy = {"S": Action("s", 1, (("goal", 1), ("S", 1)), extra_inputs=("S",))}
    chain = build(policy, "S", {"goal"})
    assert not chain.proper
    assert branching(chain)
    with pytest.raises(ValueError):
        solve_costs(chain, real_costs(chain))


def test_costs_must_be_positive():
    chain = build(donor_policy(), "S", {"goal", "done"})
    with pytest.raises(ValueError):
        solve_costs(chain, [0.0] * len(chain.states))


def test_an_input_free_chain_agrees_with_the_solver_moments():
    policy = {
        "A": Action("a", 1.5, (("goal", 2), ("B", 1), ("A", 1))),
        "B": Action("b", 0.75, (("goal", 1), ("A", 1))),
    }
    chain = build(policy, "A", {"goal"})
    costs = real_costs(chain)
    values, error = solve_costs(chain, costs)
    reference, _ = _moments.solve_costs(chain, costs)
    assert error < 1e-12
    for got, want in zip(values, reference, strict=True):
        assert got == pytest.approx(want, rel=1e-12)
    ours = mean_and_variance(chain)
    theirs = _moments.mean_and_variance(chain)
    assert ours[0][0] == pytest.approx(theirs[0][0], rel=1e-12)
    assert ours[1][0] == pytest.approx(theirs[1][0], rel=1e-12)
    for got, want in zip(ours[2], theirs[2], strict=True):
        assert got == pytest.approx(want, rel=1e-12)
    assert not branching(chain)
    assert input_starts_in_order(chain) == []
