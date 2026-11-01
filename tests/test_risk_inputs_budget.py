"""The nested budget DP (`risk._nested`, ADR-0022, ticket 181) against independent oracles.

The oracle here is an exact `Fraction` dynamic program over bins written in this file: the pmf of
the total cost from a state is built by increasing bin, an attempt at s costing k_s bins plus the
convolution of the pmfs of its input copies, then an outcome drawn with its probability. It shares
no code with `risk`. A seeded Monte Carlo of the nested process (each attempt runs fresh runs of its
inputs) checks the DP at five standard errors. Input-free chains must match `run_budget`.
"""

import math
import random
from fractions import Fraction

import pytest
from risk_support import GOAL, geometric_policy

from crafting_system.risk._budget import run_budget
from crafting_system.risk._chain import build_chain
from crafting_system.risk._nested import BranchingError, nested_work, run_nested
from crafting_system.solver import Action

HAND_GOALS = {"goal", "donor_done"}


def hand_policy(copies=1):
    """Donor D: 3 bins, 1/3 done, else again. Main S: 2 bins, `copies` runs of D, 1/4 goal, else again."""
    return {
        "D": Action("d", 3, (("donor_done", 1), ("D", 2))),
        "S": Action("s", 2, (("goal", 1), ("S", 3)), extra_inputs=("D",) * copies),
    }


HAND_BINS = {"S": 2, "D": 3}


def two_level_policy():
    """S needs D2, and D2 needs D1: three nested levels of runs."""
    return {
        "D1": Action("d1", 2, (("d1_done", 2), ("D1", 1))),
        "D2": Action("d2", 1, (("d2_done", 1), ("D2", 1)), extra_inputs=("D1",)),
        "S": Action("s", 2, (("goal", 1), ("S", 2)), extra_inputs=("D2",)),
    }


TWO_LEVEL_BINS = {"S": 2, "D2": 1, "D1": 2}
TWO_LEVEL_GOALS = {"goal", "d1_done", "d2_done"}


def chain_of(policy, start, goals):
    return build_chain(policy, start, goals.__contains__)


def bins_of(chain, table):
    return [table.get(state, 1) for state in chain.states]


# ---------------------------------------------------------------- the exact oracle (TEST ONLY)


def convolution_at(arrays, b):
    """Entry b of the convolution of the arrays (the delta at 0 for none)."""
    if not arrays:
        return Fraction(int(b == 0))
    if len(arrays) == 1:
        return arrays[0][b]
    return sum((arrays[0][i] * convolution_at(arrays[1:], b - i) for i in range(b + 1)), Fraction(0))


def exact_pmf(policy, start, goals, bins, horizon):
    """`P(total cost == b bins)` for b = 0..horizon, from `start`, by increasing b with exact fractions.

    A state without an action that is not a goal is dead: it has no mass.
    """
    names = set(policy) | set(goals) | {start}
    for action in policy.values():
        names.update(target for target, _ in action.outcomes)
        names.update(action.extra_inputs)
    pmf = {s: [Fraction(0)] * (horizon + 1) for s in names}
    for s in names & goals:
        pmf[s][0] = Fraction(1)
    increment = {s: [] for s in policy}
    for b in range(horizon + 1):
        for s, action in policy.items():
            if s in goals:
                continue
            total = sum(w for _, w in action.outcomes)
            value = Fraction(0)
            for target, w in action.outcomes:
                for t in range(bins[s], b + 1):
                    value += Fraction(w, total) * increment[s][t - bins[s]] * pmf[target][b - t]
            pmf[s][b] = value
        for s, action in policy.items():
            increment[s].append(convolution_at([pmf[y] for y in action.extra_inputs], b))
    return pmf[start]


def exact_cdf(pmf):
    out, running = [], Fraction(0)
    for mass in pmf:
        running += mass
        out.append(running)
    return out


def check_against_the_oracle(policy, goals, table, *, start="S", horizon=120):
    chain = chain_of(policy, start, goals)
    run = run_nested(chain, bins_of(chain, table), target=None, tail_mass=0.0, max_bins=horizon)
    exact = exact_cdf(exact_pmf(policy, start, goals, table, horizon))
    assert run.bins == horizon
    assert max(abs(run.cdf[b] - float(exact[b])) for b in range(horizon + 1)) <= 1e-12
    assert abs(run.unresolved - (1.0 - run.cdf[-1])) <= 1e-12
    return run


# ---------------------------------------------------------------- input-free chains equal run_budget


def branching_with_loops():
    return {
        "A": Action("a", 1.5, (("goal_a", 1), ("B", 2), ("A", 1))),
        "B": Action("b", 0.5, (("goal_b", 2), ("A", 1), ("B", 1), ("C", 1))),
        "C": Action("c", 3.0, (("goal_a", 1), ("B", 1))),
    }


def self_loop_and_two_state_loop():
    return {
        "A": Action("a", 1.1, (("goal", 1), ("A", 2), ("B", 2))),
        "B": Action("b", 0.9, (("A", 2), ("goal", 1))),
    }


INPUT_FREE = {
    "geometric": (geometric_policy(1, 3, 1.0), "S", {"S": 3}),
    "branching": (branching_with_loops(), "A", {"A": 3, "B": 1, "C": 5}),
    "pair": (self_loop_and_two_state_loop(), "A", {"A": 2, "B": 1}),
}


@pytest.mark.parametrize("name", INPUT_FREE)
@pytest.mark.parametrize(("target", "tail_mass"), [(0.5, 1e-6), (0.99, 1e-6), (None, 1e-9), (None, 1e-3)])
def test_a_chain_without_inputs_equals_the_plain_budget_dp(name, target, tail_mass):
    policy, start, table = INPUT_FREE[name]
    chain = build_chain(policy, start, lambda state: state.startswith("goal"))
    bins = bins_of(chain, table)

    nested = run_nested(chain, bins, target=target, tail_mass=tail_mass, max_bins=4000)
    plain = run_budget(chain, bins, target=target, tail_mass=tail_mass, max_bins=4000)

    assert nested.bins == plain.bins
    assert max(abs(a - b) for a, b in zip(nested.cdf, plain.cdf, strict=True)) <= 1e-12
    assert abs(nested.unresolved - plain.unresolved) <= 1e-12


# ---------------------------------------------------------------- inputs against the exact oracle


def test_the_hand_case_matches_the_exact_distribution():
    check_against_the_oracle(hand_policy(), HAND_GOALS, HAND_BINS)


def test_the_hand_case_pmf_starts_with_the_value_worked_by_hand():
    chain = chain_of(hand_policy(), "S", HAND_GOALS)
    run = run_nested(chain, bins_of(chain, HAND_BINS), target=None, tail_mass=0.0, max_bins=40)

    # the cheapest total: S pays 2, its donor pays 3 and finishes first try (1/3), S finishes (1/4)
    assert run.cdf[4] == 0.0
    assert run.cdf[5] == pytest.approx(1 / 12, abs=1e-15)


def test_two_copies_of_the_same_donor_match_the_exact_distribution():
    check_against_the_oracle(hand_policy(copies=2), HAND_GOALS, HAND_BINS)


def test_a_two_level_donor_chain_matches_the_exact_distribution():
    check_against_the_oracle(two_level_policy(), TWO_LEVEL_GOALS, TWO_LEVEL_BINS)


def test_a_horizon_that_has_to_double_gives_the_exact_prefix():
    policy = hand_policy()
    chain = chain_of(policy, "S", HAND_GOALS)

    run = run_nested(chain, bins_of(chain, HAND_BINS), target=None, tail_mass=1e-3, max_bins=400)

    exact = exact_cdf(exact_pmf(policy, "S", HAND_GOALS, HAND_BINS, run.bins))
    assert run.bins > 128
    assert max(abs(run.cdf[b] - float(exact[b])) for b in range(run.bins + 1)) <= 1e-12
    assert run.unresolved <= 1e-3
    assert abs(run.unresolved - (1.0 - run.cdf[-1])) <= 1e-12


def test_a_target_stops_at_the_first_bin_that_reaches_it():
    policy = hand_policy()
    chain = chain_of(policy, "S", HAND_GOALS)

    run = run_nested(chain, bins_of(chain, HAND_BINS), target=0.9, tail_mass=1e-9, max_bins=400, horizon=20)

    exact = [float(x) for x in exact_cdf(exact_pmf(policy, "S", HAND_GOALS, HAND_BINS, run.bins))]
    assert run.cdf[-1] >= 0.9
    assert run.cdf[-2] < 0.9
    assert max(abs(a - b) for a, b in zip(run.cdf, exact, strict=True)) <= 1e-12


def test_the_work_estimate_counts_starts_states_and_the_square_of_the_horizon():
    chain = chain_of(hand_policy(), "S", HAND_GOALS)

    assert nested_work(chain, 10) == 2 * 2 * 100


# ---------------------------------------------------------------- Monte Carlo of the nested process


def nested_sample(policy, start, goals, table, runs, seed):
    """Total bins of `runs` walks; every attempt runs fresh walks of its inputs (TEST ONLY)."""
    rng = random.Random(seed)

    def walk(state):
        total = 0
        while state not in goals:
            action = policy[state]
            total += table[state]
            for donor in action.extra_inputs:
                total += walk(donor)
            draw = rng.random() * sum(w for _, w in action.outcomes)
            for target, w in action.outcomes:
                draw -= w
                if draw < 0:
                    state = target
                    break
        return total

    return sorted(walk(start) for _ in range(runs))


def test_the_nested_dp_agrees_with_a_monte_carlo_of_the_nested_process():
    runs = 100_000
    sample = nested_sample(hand_policy(), "S", HAND_GOALS, HAND_BINS, runs, seed=181)
    chain = chain_of(hand_policy(), "S", HAND_GOALS)
    run = run_nested(chain, bins_of(chain, HAND_BINS), target=None, tail_mass=1e-9, max_bins=2000)

    for level in (0.1, 0.5, 0.9, 0.99):
        bins = next(b for b, c in enumerate(run.cdf) if c >= level)
        empirical = sum(1 for cost in sample if cost <= bins) / runs
        assert abs(empirical - run.cdf[bins]) <= 5 * math.sqrt(run.cdf[bins] * (1 - run.cdf[bins]) / runs)


# ---------------------------------------------------------------- branching


def test_an_action_that_consumes_its_own_state_is_branching():
    policy = {"S": Action("s", 1, ((GOAL, 1), ("S", 1)), extra_inputs=("S",))}
    chain = build_chain(policy, "S", lambda state: state == GOAL)

    with pytest.raises(BranchingError):
        run_nested(chain, [1, 1], target=0.5, tail_mass=1e-9, max_bins=100)


def test_an_input_whose_outcomes_lead_back_to_the_consumer_is_branching():
    policy = {
        "S": Action("s", 1, (("goal", 1), ("S", 1)), extra_inputs=("T",)),
        "T": Action("t", 1, (("t_done", 1), ("S", 1))),
    }
    chain = chain_of(policy, "S", {"goal", "t_done"})

    assert all(chain.can_finish[:2])
    with pytest.raises(BranchingError):
        run_nested(chain, bins_of(chain, {}), target=0.5, tail_mass=1e-9, max_bins=100)


def test_a_donor_shared_by_two_consumers_is_not_branching():
    policy = {
        "S": Action("s", 1, (("goal", 1), ("U", 1)), extra_inputs=("D",)),
        "U": Action("u", 1, (("goal", 1), ("S", 1)), extra_inputs=("D",)),
        "D": Action("d", 1, (("donor_done", 1), ("D", 1))),
    }
    chain = chain_of(policy, "S", HAND_GOALS)

    run = run_nested(chain, bins_of(chain, {}), target=0.5, tail_mass=1e-9, max_bins=100)

    assert run.cdf[-1] >= 0.5


# ---------------------------------------------------------------- a donor that can fail


def test_a_donor_with_a_dead_end_loses_mass_and_the_parts_add_up():
    policy = {
        "D": Action("d", 3, (("donor_done", 1), ("D", 1), ("dead", 1))),
        "S": Action("s", 2, (("goal", 1), ("S", 2)), extra_inputs=("D",)),
    }
    horizon = 200
    chain = chain_of(policy, "S", HAND_GOALS)

    run = run_nested(chain, bins_of(chain, HAND_BINS), target=None, tail_mass=0.0, max_bins=horizon)

    # a donor run ends done with probability 1/2 (per try: done 1/3, again 1/3, dead 1/3); S then needs
    # a try with a finished donor (1/2) and its own 1/3: absorbed (1/6) / (1 - 1/2 * 2/3) = 1/4 in total
    lost = 3 / 4
    exact = exact_cdf(exact_pmf(policy, "S", HAND_GOALS, HAND_BINS, horizon))
    assert max(abs(run.cdf[b] - float(exact[b])) for b in range(horizon + 1)) <= 1e-12
    assert 0.0 < run.cdf[-1] < 0.25
    assert run.unresolved > 0.0
    assert abs(run.cdf[-1] + run.unresolved + lost - 1.0) <= 1e-12


def test_a_donor_cut_by_a_short_horizon_keeps_its_missing_mass_in_flight():
    policy = {
        "D": Action("d", 3, (("donor_done", 1), ("D", 1), ("dead", 1))),
        "S": Action("s", 2, (("goal", 1), ("S", 2)), extra_inputs=("D",)),
    }
    horizon = 30
    chain = chain_of(policy, "S", HAND_GOALS)

    run = run_nested(chain, bins_of(chain, HAND_BINS), target=0.249, tail_mass=0.0, max_bins=horizon)

    # In flight at the horizon: the donor mass above it is in flight (not lost, not finished), only the
    # dead ends reached at or below it are lost. Every arrival of S at bin b <= horizon starts an attempt
    # that ends above the horizon unless its donor finishes in time; S never leaves for a dead end.
    donor = exact_pmf(policy, "D", HAND_GOALS, HAND_BINS, horizon)
    donor_lost = sum(Fraction(1, 3) ** (m + 1) for m in range(horizon // 3 + 1))
    arrivals = [Fraction(1)]
    for b in range(1, horizon + 1):
        arrivals.append(sum(arrivals[b - 2 - t] * Fraction(2, 3) * donor[t] for t in range(b - 1)))
    in_flight = sum(
        arrivals[b] * ((1 - donor_lost) - sum(donor[: max(horizon - b - 1, 0)])) for b in range(horizon + 1)
    )
    exact = exact_cdf(exact_pmf(policy, "S", HAND_GOALS, HAND_BINS, horizon))
    assert run.bins == horizon
    assert max(abs(run.cdf[b] - float(exact[b])) for b in range(horizon + 1)) <= 1e-12
    assert run.unresolved > 0.0
    assert abs(run.unresolved - float(in_flight)) <= 1e-12


def test_a_chain_that_ends_at_once_reports_nothing_in_flight():
    policy = {
        "D": Action("d", 3, (("donor_done", 1), ("dead", 1))),
        "S": Action("s", 2, (("goal", 1), ("dead", 1)), extra_inputs=("D",)),
    }
    chain = chain_of(policy, "S", HAND_GOALS)

    run = run_nested(chain, bins_of(chain, HAND_BINS), target=0.99, tail_mass=1e-9, max_bins=500)

    assert run.cdf == [0.0] * 5 + [0.25]
    assert run.unresolved == 0.0
