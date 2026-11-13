"""The certificate of the packed solve on a plan with free actions (ticket #769).

An unveil and a pick consume nothing; the planner gives them `FREE_ACTION_SHARE` (1e-6) of the cheapest paid offer (ADR-0026). The certificate
of `certify` measured each state's error against the state's own cheapest action, so at a state whose actions are all free the rounding of its
sum alone, `(m + 2) eps V`, divided by the epsilon, made the bound fail however good the values were (R24: 1.5e-3). It now also measures the
error against the cost ahead (`h`, the cheapest costs of the next `L` steps), whose margin `T h - h` at a free state is the paid step after it,
and takes the better of the two on each side; the window `L` doubles while that helps. A free action may then cost its epsilon or exactly 0.

FREE: state 0 has one free action (cost 2^-30) to state 1; state 1 pays 1 and ends with chance 1/1024, else stays; state 2 is the goal.
Every number of FREE is exact in binary: V = (1024 + 2^-30, 1024, 0), and the Bellman operator gives them back exactly.
"""

import math
import sys
from fractions import Fraction

import numpy as np
import pytest

from crafting_system.solver import PackedBuilder, solve_packed
from crafting_system.solver._packed import kernel_sums
from crafting_system.solver._packed_solve import AHEAD_FIRST, AHEAD_WEIGHT, certify

EPS = sys.float_info.epsilon
FREE = 2.0**-30


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


FREE_GRAPH = build((False, [(FREE, [(1, 1)])]), (False, [(1.0, [(2, 1), (1, 1023)])]), (True, []))
FREE_VALUE = np.array([1024.0 + FREE, 1024.0, 0.0])


def allowance(terms: int, value: float) -> float:
    """The rounding allowance of a sum of `terms - 1` outcomes: rho / (1 - rho) * value, rho = (terms + 2) eps."""
    rho = (terms + 2) * EPS
    return rho / (1.0 - rho) * value


def free_margins(window: int) -> tuple[Fraction, Fraction]:
    """gamma = T h - h of FREE at states 0 and 1, by hand: h = (w / L) (C_1 + ... + C_L), C_1 = the cheapest cost, C_(j+1) = T C_j."""
    eps, stay = Fraction(FREE), Fraction(1023, 1024)
    c = (eps, Fraction(1))
    total = c
    for _ in range(window - 1):
        c = (eps + c[1], 1 + stay * c[1])
        total = (total[0] + c[0], total[1] + c[1])
    weight = Fraction(AHEAD_WEIGHT) / window
    h = (weight * total[0], weight * total[1])
    return eps + h[1] - h[0], 1 + stay * h[1] - h[1]


def test_against_the_own_cost_alone_the_free_state_fails_at_the_rounding_floor():
    # state 0: one outcome, terms = 2, delta = 4 eps / (1 - 4 eps) * (1024 + 2^-30); g = k = 2^-30: the upper side is delta / (k - delta) ~ 2^-10
    delta = allowance(2, 1024.0 + FREE)
    certificate = certify(FREE_GRAPH, FREE_VALUE, np.ones(3, dtype=bool))

    assert certificate.own_bound == pytest.approx(delta / (FREE - delta), rel=1e-9)
    assert certificate.own_bound == pytest.approx(2.0**-10, rel=1e-2) and certificate.own_bound > 1e-6  # what refused R24 (1.5e-3)
    assert certificate.own_cost == FREE  # the state that sets it is the free one
    assert certificate.residual == 0.0 and certificate.at_floor is True


def test_against_the_cost_ahead_the_free_state_is_certified_to_the_rounding_of_its_sums():
    # One action per state, so kappa = gamma, and e = d = delta (the values are exact): t = max delta / gamma, lower = 1 / (1 + t), upper =
    # 1 / (1 - t). The own bound (2^-10) is above the accepted 1e-6, so the cost ahead is measured; the first window, 2, is within it, so it is the last.
    assert AHEAD_FIRST == 2 and AHEAD_WEIGHT == 0.5
    delta = (allowance(2, 1024.0 + FREE), allowance(3, 1024.0))
    gamma = free_margins(2)
    t = max(delta[i] / float(gamma[i]) for i in (0, 1))
    certificate = certify(FREE_GRAPH, FREE_VALUE, np.ones(3, dtype=bool))

    assert float(gamma[0]) == pytest.approx(0.49976, rel=1e-4) and float(gamma[1]) == pytest.approx(0.99927, rel=1e-4)  # the paid step, not 2^-30
    assert t == pytest.approx(delta[1] / float(gamma[1]), rel=1e-15)  # state 1 sets it: a larger sum, a larger allowance
    assert certificate.lower == pytest.approx(1.0 / (1.0 + t), rel=1e-15) and certificate.upper == pytest.approx(1.0 / (1.0 - t), rel=1e-15)
    assert certificate.bound == pytest.approx(t, rel=1e-9)
    assert certificate.bound == pytest.approx(1.82e-12, rel=2e-2)  # 9 orders of magnitude under the own bound of the test above
    assert certificate.window == 2


def test_a_run_of_free_steps_longer_than_the_first_window_doubles_it_until_a_paid_step_is_in_it():
    # five free steps in a row, then the paid loop of FREE: a window of L steps sees the paid step from the first state only once L + 1 > 5. The
    # margin there is (1 - w) eps + (w / L) (C_(L+1) - eps) = eps for L = 2 and L = 4 alike (the bound stays about 1e-3), and the window 8 is the first
    # that carries it
    run = 5
    states = [(False, [(FREE, [(i + 1, 1)])]) for i in range(run)] + [(False, [(1.0, [(run + 1, 1), (run, 1023)])]), (True, [])]
    graph = build(*states)
    value = np.array([1024.0 + (run - i) * FREE for i in range(run)] + [1024.0, 0.0])
    certificate = certify(graph, value, np.ones(run + 2, dtype=bool))

    assert certificate.own_bound > 1e-4 and certificate.own_cost == FREE
    assert certificate.window == 8
    assert certificate.bound < 1e-11


def test_the_solve_of_a_plan_with_a_free_step_is_accepted():
    # before #769: ConvergenceError "certifies only a relative bound of 0.000978"
    solved = solve_packed(FREE_GRAPH)

    assert solved.value.tolist() == FREE_VALUE.tolist()
    assert solved.error_bound < 1e-11
    assert solved.info["quotient_own_bound"] > 1e-6  # the progress line says what the own cost alone would have given


def test_where_the_own_cost_is_the_tighter_measure_it_is_the_one_given():
    # GEO of test_solver_packed_light: one action of cost 2, the goal or stay half and half, value 4; the bound stays 10 eps, the own cost's
    geo = build((False, [(2.0, [(1, 1), (0, 1)])]), (True, []))
    certificate = certify(geo, np.array([4.0, 0.0]), np.array([True, True]))

    assert certificate.bound == pytest.approx(10 * EPS, rel=1e-6)
    assert certificate.own_bound == certificate.bound and certificate.own_cost == 2.0 and certificate.window == 0


def test_a_wrong_value_at_a_free_state_is_still_caught():
    # V(0) 1% too high: d = 10.24 against a margin of about 0.5, so the lower side is at most 0.5 / 10.74: the true error (1%) is inside
    high = FREE_VALUE.copy()
    high[0] *= 1.01
    certificate = certify(FREE_GRAPH, high, np.ones(3, dtype=bool))

    assert certificate.lower <= 1024.0 / high[0]
    assert certificate.bound >= 0.0099
    # V(0) 1% too low: e = 10.24 is more than the paid step ahead, nothing can be said above
    low = FREE_VALUE.copy()
    low[0] *= 0.99
    assert certify(FREE_GRAPH, low, np.ones(3, dtype=bool)).upper == math.inf


# --- an unveil and its picks, against exact elimination ------------------------------------------------------------------


PAID = 3  # paid states; choice node j picks between paid states j % 3 and (j + 1) % 3
STAY = Fraction(1, 2)  # a paid state ends with chance 1/2, else stays


def unveil_graph(terms: int, scale: float, free: float):
    """State 0 unveils (cost `free`) into `terms` choice nodes 1..terms with weights 1 + j % 7; choice node j picks (cost `free`) one of two paid
    states; paid state k costs `scale * (1 + k / 2) / 2`, so its value is `scale * (1 + k / 2)`; the last state is the goal.
    Returns `(graph, exact values as Fractions, the Skeel condition of the greedy policy at each state)`."""
    first_paid, goal = terms + 1, terms + 1 + PAID
    builder = PackedBuilder()
    weights = [1 + j % 7 for j in range(terms)]
    builder.action(0, free, builder.kernel(list(range(1, terms + 1)), weights))
    builder.close_state(False)
    pick = [builder.kernel([first_paid + k], [1]) for k in range(PAID)]
    for j in range(terms):
        builder.action(1, free, pick[j % PAID])
        builder.action(2, free, pick[(j + 1) % PAID])
        builder.close_state(False)
    costs = [scale * (1 + k / 2) / 2 for k in range(PAID)]
    for k in range(PAID):
        builder.action(3, costs[k], builder.kernel([goal, first_paid + k], [1, 1]))
        builder.close_state(False)
    builder.close_state(True)
    graph = builder.build()

    # exact elimination of the stored chances: a paid state solves V = c + V / 2; a choice node takes the cheaper pick; the unveil the mean
    lo, hi = graph.k_ptr[graph.act_kernel[0]], graph.k_ptr[graph.act_kernel[0] + 1]
    chance = [Fraction(float(p)) for p in graph.k_prob[lo:hi]]
    eps = Fraction(free)
    paid = [Fraction(c) / (1 - STAY) for c in costs]
    choice = [eps + min(paid[j % PAID], paid[(j + 1) % PAID]) for j in range(terms)]
    exact = [eps + sum(p * v for p, v in zip(chance, choice))] + choice + paid + [Fraction(0)]
    # Skeel's condition of (I - P) x = c at each state, |(I - P)^-1| |I - P| |x| / |x| = (2 N x - x) / x since P x = x - c, N = (I - P)^-1:
    # N x is the sum of the values met on the way (a paid state is met 1 / (1 - STAY) = 2 times)
    met_paid = [2 * v for v in paid]
    met_choice = [v + min(met_paid[j % PAID], met_paid[(j + 1) % PAID]) for j, v in enumerate(choice)]
    met = [exact[0] + sum(p * m for p, m in zip(chance, met_choice))] + met_choice + met_paid
    condition = [float((2 * m - v) / v) for m, v in zip(met, exact)]
    return graph, exact, condition


@pytest.mark.parametrize("free", ["epsilon", "zero"])
@pytest.mark.parametrize("terms", [1_000, 10_000, 100_000])
@pytest.mark.parametrize("scale", [1e2, 1e4, 1e6])
def test_an_unveil_and_its_picks_are_certified_within_a_few_roundings_times_the_condition(scale, terms, free):
    cost = 1e-6 * scale / 2 if free == "epsilon" else 0.0  # FREE_ACTION_SHARE of the cheapest paid action, or nothing at all
    graph, exact, condition = unveil_graph(terms, scale, cost)
    solved = solve_packed(graph)

    truth = np.array([float(v) for v in exact])
    assert np.all(np.abs(solved.value - truth) <= 1e-13 * truth), np.max(np.abs(solved.value - truth) / np.maximum(truth, 1e-300))
    assert solved.error_bound <= 1e-6  # accepted (before #769 the 100,000 terms were refused: 4e-5 at every scale)
    # asked for the tightest it gives, the certificate is within a few roundings of the longest sum times the condition, and holds the exact values
    rho = (terms + 3) * EPS
    found = certify(graph, solved.value, np.ones(graph.n, dtype=bool), wanted=0.0)
    assert found.bound <= 4 * rho * max(condition), (found.bound, rho, max(condition))
    inner = truth[:-1]
    assert np.all(found.lower * solved.value[:-1] <= inner) and np.all(inner <= found.upper * solved.value[:-1])
    # against each state's own cheapest cost the unveil's rounding fails: a 1e-6 epsilon (or 0) is no measure of it
    assert found.own_bound > 1e3 * found.bound


# --- random plans with free steps, against an independent solve ----------------------------------------------------------


def reference_values(graph, n: int) -> np.ndarray:
    """The optimal values of a small graph by plain policy iteration with dense solves (no code under test)."""
    rows = []
    for s in range(n):
        acts = []
        for a in range(graph.act_ptr[s], graph.act_ptr[s + 1]):
            k = graph.act_kernel[a]
            lo, hi = graph.k_ptr[k], graph.k_ptr[k + 1]
            acts.append((graph.act_cost[a], graph.k_succ[lo:hi], graph.k_prob[lo:hi]))
        rows.append(acts)
    goal = graph.goal
    policy = [0] * n
    while True:
        a_mat, b = np.eye(n), np.zeros(n)
        for s in range(n):
            if goal[s]:
                continue
            cost, succ, prob = rows[s][policy[s]]
            b[s] = cost
            for t, p in zip(succ, prob):
                a_mat[s, t] -= p
        value = np.linalg.solve(a_mat, b)
        changed = False
        for s in range(n):
            if goal[s]:
                continue
            q = [cost + float(np.dot(prob, value[succ])) for cost, succ, prob in rows[s]]
            best = int(np.argmin(q))
            if q[best] < q[policy[s]] * (1 - 1e-12):
                policy[s], changed = best, True
        if not changed:
            return value


def random_free_graph(seed: int, free: float):
    """Paid states 0..5 (two actions each, every kernel ends with positive chance) and free states 6..9 (one free action each, onto the
    paid states or another free state of a higher number); state 10 is the goal."""
    rng = np.random.default_rng(seed)
    states = []
    for _ in range(6):
        actions = []
        for _ in range(2):
            succ = rng.choice(10, size=3, replace=False).tolist() + [10]
            actions.append((float(rng.uniform(0.5, 2.0)), [(int(t), int(rng.integers(1, 50))) for t in succ]))
        states.append((False, actions))
    for s in range(6, 10):
        succ = rng.choice(6, size=2, replace=False).tolist() + list(range(s + 1, 10))[:1]
        states.append((False, [(free, [(int(t), int(rng.integers(1, 20))) for t in succ])]))
    states.append((True, []))
    return build(*states)


@pytest.mark.parametrize("free", [1e-9, 0.0])
@pytest.mark.parametrize("seed", range(12))
def test_the_certificate_holds_the_true_values_of_random_plans_with_free_steps(seed, free):
    graph = random_free_graph(seed, free)
    truth = reference_values(graph, graph.n)
    rng = np.random.default_rng(1000 + seed)
    for scale in (0.0, 1e-9, 1e-6, 1e-3):
        value = truth * (1.0 + scale * rng.uniform(-1.0, 1.0, graph.n))
        certificate = certify(graph, value, np.ones(graph.n, dtype=bool), wanted=0.0)  # the cost ahead is measured whatever the own bound
        inner = slice(0, graph.n - 1)
        assert np.all(certificate.lower * value[inner] <= truth[inner] * (1 + 1e-13)), (seed, scale)
        if math.isfinite(certificate.upper):
            assert np.all(truth[inner] <= certificate.upper * value[inner] * (1 + 1e-13)), (seed, scale)
        if scale == 0.0:
            assert certificate.bound < 1e-10 < certificate.own_bound  # the free states are certified only by the cost ahead


# --- what the cost ahead must not do ---------------------------------------------------------------------------------------


def test_values_of_zero_on_a_free_cycle_are_not_certified():
    # states 0 and 1 send each other on for nothing; 1 can also pay 5 to finish. The true value is 5 at both, but 0 is a fixed point of the free
    # cycle: e = kappa = 0 there proves nothing about the greedy (free, improper) policy, so nothing can be said above
    graph = build((False, [(0.0, [(1, 1)])]), (False, [(0.0, [(0, 1)]), (5.0, [(2, 1)])]), (True, []))
    certificate = certify(graph, np.zeros(3), np.ones(3, dtype=bool), wanted=0.0)

    assert certificate.upper == math.inf and certificate.bound == math.inf


@pytest.mark.parametrize("seed", range(8))
def test_a_plan_that_certifies_on_its_own_costs_keeps_the_numbers_of_374_to_the_bit(seed):
    # paid states only: the bound on each state's own cost is within the accepted one, so the cost ahead is not measured, and the numbers are
    # those of the expressions of #374: lower = min g / (g + d), upper = max k / (k - e), the allowance (m + 2) eps of the sum
    rng = np.random.default_rng(seed)
    states = []
    for s in range(6):
        actions = []
        for _ in range(2):
            succ = sorted(set(rng.choice(6, size=3).tolist())) + [6]
            actions.append((float(rng.uniform(0.5, 2.0)), [(int(t), int(rng.integers(1, 50))) for t in succ]))
        states.append((False, actions))
    states.append((True, []))
    graph = build(*states)
    value = reference_values(graph, graph.n) * (1.0 + 1e-12 * rng.uniform(-1.0, 1.0, graph.n))
    found = certify(graph, value, np.ones(graph.n, dtype=bool))

    q = graph.act_cost + kernel_sums(graph, value)[graph.act_kernel]  # the sums as the solver adds them (a primitive this PR does not change)
    lowers, uppers = [], []
    for s in range(6):
        acts = range(graph.act_ptr[s], graph.act_ptr[s + 1])
        tv = min(q[a] for a in acts)
        greedy = min(a for a in acts if q[a] == tv)
        terms = max(graph.k_ptr[graph.act_kernel[a] + 1] - graph.k_ptr[graph.act_kernel[a]] + 1 for a in acts)
        rho = (terms + 2.0) * EPS
        delta = rho / (1.0 - rho) * tv
        g, k = min(graph.act_cost[a] for a in acts), graph.act_cost[greedy]
        lowers.append(g / (g + max(value[s] - tv, 0.0) + delta))
        uppers.append(k / (k - (max(tv - value[s], 0.0) + delta)))
    assert found.window == 0
    assert found.lower == min(lowers) and found.upper == max(uppers)  # exact equality: the same floats in the same order


def test_a_free_cycle_stops_the_window_after_two_tries(monkeypatch):
    # FREE with state 0's free action sent back to itself as well: no window gives state 0 a margin (its cheapest costs ahead are 0 by the loop),
    # so the second window, no better, ends the doubling instead of running to the rail of AHEAD_LIMIT steps
    from crafting_system.solver import _packed_solve as ps

    graph = build((False, [(0.0, [(0, 1)]), (0.0, [(1, 1)])]), (False, [(1.0, [(2, 1), (1, 1023)])]), (True, []))
    sweeps = []
    real = ps.kernel_sums
    monkeypatch.setattr(ps, "kernel_sums", lambda g, f: sweeps.append(1) or real(g, f))
    certificate = certify(graph, np.array([1024.0, 1024.0, 0.0]), np.ones(3, dtype=bool), wanted=0.0)

    assert len(sweeps) <= 1 + 3 + 2  # the Bellman sum, the steps of the windows 2 and 4, and their margins
    assert certificate.lower == 0.0  # the free loop costs nothing forever: nothing below


def test_a_free_action_into_the_goal_is_certified_though_its_margin_and_error_are_both_zero():
    # state 0 pays 3 to reach state 1, which ends for nothing: V = (3, 0). At state 1, e = kappa = 0 for every h (its value and its step are 0),
    # but the greedy action reaches the goal, so the policy is proper there and the upper side holds; the free cycle above is what it refuses
    graph = build((False, [(3.0, [(1, 1)])]), (False, [(0.0, [(2, 1)])]), (True, []))
    certificate = certify(graph, np.array([3.0, 0.0, 0.0]), np.ones(3, dtype=bool), wanted=0.0)

    assert certificate.bound < 1e-14 and certificate.own_bound == math.inf  # the rounding of state 0's sum; its own cost 0 at state 1 says nothing
