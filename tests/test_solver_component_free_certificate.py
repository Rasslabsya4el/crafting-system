"""The certificate of the object solver on a cyclic component with free actions (ticket #842, the object solver's side of #769).

An unveil and a pick consume nothing; the planner gives them `FREE_ACTION_SHARE` (1e-6) of the cheapest paid offer (ADR-0026). The object
solver certified each cyclic component against `g`, the smallest constant term of its actions, so a free action inside a cycle (a restart
back to an unveil, picks onto paid states that come back) made `g` that epsilon, and the rounding of the component's sums, `(m + 2) eps V`,
divided by it gave a bound of 1e-3 or worse however good the values were (R24 met the same in the packed solve: 1.5e-3). When that bound is
above `ACCEPT_BOUND`, `_component._ahead` also measures each state's error against the cost ahead (`_certify.widen`, shared with the packed
solve), whose margin at a free state is the paid step after it, and each side takes the better of the two.

FREE: state A has one free action (cost 2^-30) to B; B pays 1 and ends with chance 1/1024, else goes back to A. V_B = 1024 + 1023 * 2^-30,
V_A = 1024 + 1024 * 2^-30, exact in binary, and the policy iteration of the component gives them back exactly.
"""

import math
import sys
from fractions import Fraction

import numpy as np
import pytest

from crafting_system.solver import Action, TabularModel, solve
from crafting_system.solver import _component
from crafting_system.solver._certify import ACCEPT_BOUND, AHEAD_WEIGHT, own_multipliers, relative_error, rounding_allowance
from crafting_system.solver._component import Bellman, build_bellman, solve_cyclic
from crafting_system.solver._graph import build_graph, proper_states

EPS = sys.float_info.epsilon
FREE = 2.0**-30
GOAL = "goal"


def act(label, cost, *outcomes):
    return Action(label, cost, tuple(outcomes))


def free_cycle(free: float = FREE) -> TabularModel:
    return TabularModel([GOAL], {"A": [act("free", free, ("B", 1))], "B": [act("pay", 1.0, (GOAL, 1), ("A", 1023))]})


def whole_component(model, start) -> tuple[Bellman, list]:
    """The Bellman operator of the one cyclic component that holds every non-goal state, with the goal's value 0 outside it."""
    graph = build_graph(model, [start])
    alive, _ = proper_states(graph)
    component = [i for i in range(len(graph.states)) if not graph.goal[i]]
    value = [0.0 if graph.goal[i] else math.inf for i in range(len(graph.states))]
    ones = [1.0] * len(graph.states)
    return build_bellman(graph, alive, component, value, ones, ones), [graph.states[i] for i in component]


def own_spy(monkeypatch) -> list:
    """Records the own multipliers `_ahead` is given (the certificate before #842) and what it returns."""
    seen = []
    real = _component._ahead

    def spy(bellman, values, greedy, lower, upper, wanted):
        found = real(bellman, values, greedy, lower, upper, wanted)
        seen.append(((lower, upper), found))
        return found

    monkeypatch.setattr(_component, "_ahead", spy)
    return seen


def free_cycle_margins(window: int) -> tuple[Fraction, Fraction]:
    """gamma = T h - h of FREE at A and B, by hand: h = (w / L) (C_1 + ... + C_L), C_1 = each state's cheapest constant term, C_(j+1) = T C_j."""
    eps, back = Fraction(FREE), Fraction(1023, 1024)
    c = (eps, Fraction(1))
    total = c
    for _ in range(window - 1):
        c = (eps + c[1], 1 + back * c[0])
        total = (total[0] + c[0], total[1] + c[1])
    weight = Fraction(AHEAD_WEIGHT) / window
    h = (weight * total[0], weight * total[1])
    return eps + h[1] - h[0], 1 + back * h[0] - h[1]


FREE_EXACT = {"A": 1024.0 + 1024 * FREE, "B": 1024.0 + 1023 * FREE}


def test_against_its_cheapest_constant_term_alone_the_free_cycle_fails_at_the_rounding_floor(monkeypatch):
    # the bound of the component on g alone (what it was before #842): terms = 3 (B: its cost and two outcomes), rho = 5 eps, delta = rho * V_A,
    # e = d = 0 (the values are exact), g = 2^-30: lower = g / (g + delta), upper = g / (g - delta), about 5 * 2^-12 = 1.2e-3
    monkeypatch.setattr(_component, "ACCEPT_BOUND", math.inf)  # the cost ahead is never measured
    solved = solve(free_cycle(), ["A"])
    rho = rounding_allowance(3)
    delta = rho * FREE_EXACT["A"]
    lower, upper = FREE / (FREE + delta), FREE / (FREE - delta)

    assert dict(solved.values) == {**FREE_EXACT, GOAL: 0.0}
    assert solved.error_bound == max(1.0 - lower * (1.0 - rho), upper * (1.0 + rho) - 1.0)
    assert solved.error_bound == pytest.approx(5 * 2.0**-12, rel=2e-3) and solved.error_bound > ACCEPT_BOUND  # delta / (g - delta), about 1.2e-3


def test_against_the_cost_ahead_the_free_cycle_is_certified_to_the_rounding_of_its_sums(monkeypatch):
    # One action per state, so kappa = gamma, and e = d = grow * V (the values and their backups are exact): t = max grow V / gamma; the own bound
    # (1.2e-3) is above the accepted 1e-6, so the cost ahead is measured, and its first window, 2, is within it
    seen = own_spy(monkeypatch)
    solved = solve(free_cycle(), ["A"])
    rho = rounding_allowance(3)
    grow = rho / (1.0 - rho)
    gamma = free_cycle_margins(2)
    t = max(grow * FREE_EXACT["A"] / float(gamma[0]), grow * FREE_EXACT["B"] / float(gamma[1]))
    lower, upper = 1.0 / (1.0 + t), 1.0 / (1.0 - t)

    assert float(gamma[0]) == pytest.approx(0.25, rel=1e-3) and float(gamma[1]) == pytest.approx(0.7498, rel=1e-3)  # the paid step, not 2^-30
    assert t == pytest.approx(grow * FREE_EXACT["A"] / float(gamma[0]), rel=1e-15)  # A sets it: its margin is the quarter of the paid step
    assert dict(solved.values) == {**FREE_EXACT, GOAL: 0.0}  # the values are those of before: only the certificate changed
    assert len(seen) == 1 and seen[0][1] == (pytest.approx(lower, rel=1e-15), pytest.approx(upper, rel=1e-15), 2)
    assert solved.error_bound == pytest.approx(max(1.0 - lower * (1.0 - rho), upper * (1.0 + rho) - 1.0), rel=1e-9)
    assert solved.error_bound == pytest.approx(4.5e-12, rel=2e-2)  # 9 orders of magnitude under the bound on g alone


def test_a_wrong_value_at_the_free_state_is_still_caught():
    bellman, order = whole_component(free_cycle(), "A")
    exact = [FREE_EXACT[s] for s in order]
    a = order.index("A")
    rho = rounding_allowance(bellman.terms)
    for factor in (1.01, 0.99):
        values = list(exact)
        values[a] *= factor
        greedy = [bellman.astart[i] for i in range(len(order))]
        lower, upper, _ = _component._ahead(bellman, values, greedy, 0.0, math.inf, 0.0)
        # the multipliers must hold the exact values, whatever the window: lower V <= V* <= upper V
        assert all(lower * v <= x * (1 + rho) for v, x in zip(values, exact))
        assert all(x <= upper * v * (1 + rho) for v, x in zip(values, exact))
        assert relative_error(lower, upper) >= 0.0099 * (1 - 1e-9) or upper == math.inf


# --- an unveil and its picks in a cycle, against exact elimination --------------------------------------------------------


PAID = 3  # paid states; choice node j picks between paid states j % 3 and (j + 1) % 3


def unveil_cycle(terms: int, scale: float, free: float):
    """U unveils (cost `free`) into `terms` choice nodes with weights 1 + j % 7; choice node j picks (cost `free`) one of two paid states; paid
    state k costs `scale * (1 + k / 2) / 2` and ends with chance 1/2, else goes back to U (a restart): one cyclic component.
    Returns `(model, exact values of the true model as Fractions)`: the weights' own chances, not their rounded floats."""
    weights = [1 + j % 7 for j in range(terms)]
    costs = [scale * (1 + k / 2) / 2 for k in range(PAID)]
    table = {"U": [act("unveil", free, *[(("c", j), w) for j, w in enumerate(weights)])]}
    for j in range(terms):
        table[("c", j)] = [act("pick", free, (("p", j % PAID), 1)), act("pick", free, (("p", (j + 1) % PAID), 1))]
    for k in range(PAID):
        table[("p", k)] = [act("pay", costs[k], (GOAL, 1), ("U", 1))]
    return TabularModel([GOAL], table), unveil_exact(terms, scale, Fraction(free))


def unveil_exact(terms: int, scale: float, eps: Fraction) -> dict:
    """The exact values of `unveil_cycle` for a free cost `eps` (0 included), by elimination: V_U = eps + sum p_j (eps + min c + V_U / 2), the
    chances summing to 1 exactly, so V_U = 4 eps + 2 S with S = sum p_j min c."""
    weights = [1 + j % 7 for j in range(terms)]
    costs = [Fraction(scale * (1 + k / 2) / 2) for k in range(PAID)]
    total = sum(weights)
    cheaper = [min(costs[j % PAID], costs[(j + 1) % PAID]) for j in range(terms)]
    unveil = 4 * eps + 2 * sum(Fraction(w, total) * c for w, c in zip(weights, cheaper))
    exact = {"U": unveil, GOAL: Fraction(0)}
    exact.update({("c", j): eps + cheaper[j] + unveil / 2 for j in range(terms)})
    exact.update({("p", k): costs[k] + unveil / 2 for k in range(PAID)})
    return exact


@pytest.mark.parametrize("terms", [1_000, 10_000])
@pytest.mark.parametrize("scale", [1e2, 1e6])
def test_an_unveil_and_its_picks_in_a_cycle_are_certified_and_hold_the_exact_values(monkeypatch, scale, terms):
    free = 1e-6 * scale / 2  # FREE_ACTION_SHARE of the cheapest paid action
    model, exact = unveil_cycle(terms, scale, free)
    seen = own_spy(monkeypatch)
    solved = solve(model, ["U"])

    bound = solved.error_bound
    for state, value in solved.values.items():
        if state != GOAL:  # the certificate holds the exact value of the true model
            assert Fraction(value) * (1 - Fraction(bound)) <= exact[state] <= Fraction(value) * (1 + Fraction(bound)), state
    rho = rounding_allowance(terms + 1)
    assert bound <= ACCEPT_BOUND and bound <= 16 * rho  # a few roundings of the unveil's sum
    # on g alone, about (m + 2) eps V_U / g: 1.2e-6 at 1,000 terms, 1.2e-5 at 10,000, above the accepted bound; the cost ahead is 1000 times tighter
    assert len(seen) == 1
    own = seen[0][0]
    assert relative_error(*own) > ACCEPT_BOUND and relative_error(*own) > 1e3 * bound


# --- a free action of cost exactly 0 (the object model refuses a cost of 0, so it is set in the component's operator) -------


def zero_free(bellman: Bellman, free: float) -> Bellman:
    """The same component with every constant term equal to `free` (the free actions: all their outcomes are inside) set to exactly 0."""
    for a, base in enumerate(bellman.base):
        if base == free:
            bellman.base[a] = 0.0
    bellman.g = min(bellman.base)
    return bellman


@pytest.mark.parametrize("which", ["free cycle", "unveil"])
def test_a_free_action_of_cost_zero_is_certified_against_the_cost_ahead(which):
    if which == "free cycle":
        model, start = free_cycle(), "A"
        exact = {"A": Fraction(1024), "B": Fraction(1024)}
    else:
        model, _ = unveil_cycle(2_000, 1e4, 1e-6 * 1e4 / 2)
        exact = unveil_exact(2_000, 1e4, Fraction(0))
        start = "U"
    bellman, order = whole_component(model, start)
    zero_free(bellman, 1e-6 * 1e4 / 2 if which == "unveil" else FREE)
    result = solve_cyclic(bellman, 1e-10, 64, 100_000)

    assert bellman.g == 0.0
    assert own_multipliers(bellman.g, EPS, EPS) == (0.0, math.inf)  # on g alone nothing can be said, however small the residuals
    assert result.converged and result.upper < math.inf
    assert relative_error(result.lower, result.upper) < 1e-10
    for state, value in zip(order, result.values):
        assert Fraction(value) * Fraction(result.lower) <= exact[state] <= Fraction(value) * Fraction(result.upper), state


def test_values_of_zero_on_a_free_cycle_are_not_certified():
    # A and B send each other on for nothing; B can also pay 5 to finish. The true value is 5 at both, but 0 is a fixed point of the free cycle:
    # e = kappa = 0 there proves nothing about the greedy (free, improper) policy, so nothing can be said above
    model = TabularModel([GOAL], {"A": [act("free", FREE, ("B", 1))], "B": [act("free", FREE, ("A", 1)), act("pay", 5.0, (GOAL, 1))]})
    bellman, order = whole_component(model, "A")
    zero_free(bellman, FREE)
    b = order.index("B")
    greedy = [bellman.astart[i] for i in range(len(order))]  # the first action of each: A's free one, B's free one
    assert bellman.base[greedy[b]] == 0.0
    lower, upper, _ = _component._ahead(bellman, [0.0, 0.0], greedy, 0.0, math.inf, 0.0)

    assert upper == math.inf


def test_a_free_action_into_the_goal_is_certified_though_its_margin_and_error_are_both_zero():
    # A pays 3 and reaches B or stays, half and half; B ends for nothing (or pays 1 to go back to A): V = (6, 0). At B, e = kappa = 0 for every h
    # (its value and its step are 0), but its action leaves the component, so the policy is proper there and the upper side holds
    model = TabularModel([GOAL], {"A": [act("pay", 3.0, ("B", 1), ("A", 1))], "B": [act("free", FREE, (GOAL, 1)), act("back", 1.0, ("A", 1))]})
    bellman, order = whole_component(model, "A")
    for a in range(len(bellman.base)):
        if bellman.base[a] == FREE:
            bellman.base[a] = 0.0
    a, b = order.index("A"), order.index("B")
    values = [0.0, 0.0]
    values[a], values[b] = 6.0, 0.0
    greedy = [0, 0]
    greedy[a], greedy[b] = bellman.astart[a], bellman.astart[b]  # A's paid loop, B's free exit
    lower, upper, _ = _component._ahead(bellman, values, greedy, 0.0, math.inf, 0.0)

    assert relative_error(lower, upper) < 1e-14  # B's e = kappa = 0, but its action leaves the component: carried


def test_a_run_of_free_steps_longer_than_the_first_window_doubles_it_until_a_paid_step_is_in_it():
    # five free steps in a row, then the paid step that goes back to the first: a window of L steps sees the paid step from the first state only
    # once L + 1 > 5, so the window 8 is the first that carries it
    run = 5
    table = {i: [act("free", FREE, (i + 1, 1))] for i in range(run)}
    table[run] = [act("pay", 1.0, (GOAL, 1), (0, 1023))]
    seen = []
    real = _component._ahead
    solved = None
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_component, "_ahead", lambda *args: seen.append(real(*args)) or seen[-1])
        solved = solve(TabularModel([GOAL], table), [0])

    assert len(seen) == 1 and seen[0][2] == 8
    # the first state's margin in the window 8 is (w / 8) of the paid step, 1/16: t = 5 eps 1024 / (1/16) = 1.8e-11 (on g alone: 1.2e-3)
    assert solved.error_bound == pytest.approx(5 * EPS * 1024 * 16, rel=2e-2)


# --- what the cost ahead must not change, and random plans against an independent solve ------------------------------------


@pytest.mark.parametrize("seed", range(8))
def test_a_component_that_certifies_on_g_keeps_the_numbers_of_before_to_the_bit(monkeypatch, seed):
    # paid states only: the bound on g is within the accepted one, so the cost ahead is never measured: the values and the bound are those of before
    rng = np.random.default_rng(seed)
    table = {}
    for s in range(6):
        table[s] = [act("a", float(rng.uniform(0.5, 2.0)), *[(int(t), int(rng.integers(1, 50))) for t in rng.choice(6, size=3, replace=False)], (GOAL, 1)) for _ in range(2)]
    model = TabularModel([GOAL], table)

    def never(*args):
        raise AssertionError("the cost ahead was measured")

    monkeypatch.setattr(_component, "_ahead", never)
    solved = solve(model, [0], direct_solve_limit=[0, 64][seed % 2])
    assert solved.error_bound < ACCEPT_BOUND


def reference(bellman: Bellman) -> tuple[np.ndarray, list[int]]:
    """The least values of the component by plain policy iteration with dense solves (no code under test), and the policy (action indices)."""
    n = len(bellman.states)
    acts = [list(range(bellman.astart[s], bellman.astart[s + 1])) for s in range(n)]

    def q(a, v):
        lo, hi = bellman.tptr[a], bellman.tptr[a + 1]
        return bellman.base[a] + sum(p * v[j] for j, p in zip(bellman.inside[lo:hi], bellman.prob[lo:hi]))

    policy = [max(acts[s], key=lambda a: bellman.has_exit[a]) for s in range(n)]
    while True:
        m, b = np.eye(n), np.zeros(n)
        for s, a in enumerate(policy):
            b[s] = bellman.base[a]
            for j, p in zip(bellman.inside[bellman.tptr[a] : bellman.tptr[a + 1]], bellman.prob[bellman.tptr[a] : bellman.tptr[a + 1]]):
                m[s, j] -= p
        v = np.linalg.solve(m, b)
        changed = False
        for s in range(n):
            best = min(acts[s], key=lambda a: q(a, v))
            if q(best, v) < q(policy[s], v) * (1 - 1e-12):
                policy[s], changed = best, True
        if not changed:
            return v, policy


@pytest.mark.parametrize("free", [1e-9, 0.0])
@pytest.mark.parametrize("seed", range(10))
def test_the_certificate_holds_the_true_values_of_random_cycles_with_free_steps(seed, free):
    # paid states 0..5 (two actions each, every one with a chance to end) and free states 6..9 (one free action each, onto paid states or the
    # next free state); the paid states come back to the free ones, so it is one component
    rng = np.random.default_rng(seed)
    table = {}
    for s in range(6):
        table[s] = [act("a", float(rng.uniform(0.5, 2.0)), *[(int(t), int(rng.integers(1, 50))) for t in rng.choice(10, size=3, replace=False)], (GOAL, 1)) for _ in range(2)]
        table[s].append(act("back", float(rng.uniform(0.5, 2.0)), (6, 1)))
    for s in range(6, 10):
        succ = [int(t) for t in rng.choice(6, size=2, replace=False)] + list(range(s + 1, 10))[:1]
        table[s] = [act("free", FREE, *[(t, int(rng.integers(1, 20))) for t in succ])]
    bellman, order = whole_component(TabularModel([GOAL], table), 6)
    if free == 0.0:
        zero_free(bellman, FREE)
    else:
        for a, base in enumerate(bellman.base):
            if base == FREE:
                bellman.base[a] = free
    truth, policy = reference(bellman)
    for scale in (0.0, 1e-9, 1e-6, 1e-3):
        values = list(truth * (1.0 + scale * rng.uniform(-1.0, 1.0, len(truth))))
        greedy = [min(range(bellman.astart[s], bellman.astart[s + 1]), key=lambda a: _q(bellman, values, a)) for s in range(len(values))]
        lower, upper, _ = _component._ahead(bellman, values, greedy, 0.0, math.inf, 0.0)  # wanted 0: measured whatever the own bound
        assert all(lower * v <= x * (1 + 1e-13) for v, x in zip(values, truth)), (seed, scale)
        if math.isfinite(upper):
            assert all(x <= upper * v * (1 + 1e-13) for v, x in zip(values, truth)), (seed, scale)
        if scale == 0.0:
            assert relative_error(lower, upper) < 1e-10  # the free states are certified by the cost ahead


def _q(bellman, values, a):
    lo, hi = bellman.tptr[a], bellman.tptr[a + 1]
    return bellman.base[a] + sum(p * values[j] for j, p in zip(bellman.inside[lo:hi], bellman.prob[lo:hi]))


def test_a_branching_component_with_a_free_step_is_certified_against_the_cost_ahead(monkeypatch):
    # FREE's A and B, where B pays 1 to end or go back to A half and half, or pays 1 to end with A as an input (an input inside its own
    # component: branching). V_B = 1 + V_A / 2, V_A = 2^-30 + V_B: V = (2 + 2^-29, 2 + 2^-30), exact. On g = 2^-30 alone: about 2.4e-6
    model = TabularModel([GOAL], {
        "A": [act("free", FREE, ("B", 1))],
        "B": [act("pay", 1.0, (GOAL, 1), ("A", 1)), Action("combine", 1.0, ((GOAL, 1),), extra_inputs=("A",))],
    })
    assert whole_component(model, "A")[0].branching
    seen = own_spy(monkeypatch)
    solved = solve(model, ["A"])

    assert dict(solved.values) == {"A": 2.0 + 2 * FREE, "B": 2.0 + FREE, GOAL: 0.0}
    assert len(seen) == 1 and relative_error(*seen[0][0]) > ACCEPT_BOUND
    assert solved.error_bound < 1e-13
