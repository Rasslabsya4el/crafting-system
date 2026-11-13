"""The dense solves of the risk report on stiff chains, against exact `Fraction` elimination (tickets #642, #615, #584).

A state that stays with chance `1 - 1e-13` has `1 - p = 1e-13 +- 1e-16` in the matrix `I - M` as the chain gives it. A dense solve of that is good to three
digits and the residual formed from it has none left, so the mean cost of such a chain was shown with a bound that was merely under 1 or refused. The
risk code now divides each state's own chance of staying out of its row (the sum of its other chances is the pivot: no `1 - p`), refines the dense solves
and measures their componentwise backward error, and the error it returns is the certificate of the answer: a number that is small when the answer is good.

The references here are `Fraction` eliminations on the chain's own weights; none of them calls `crafting_system.risk`.
"""

import math
import random
from fractions import Fraction

import pytest

from crafting_system.risk import _coarse, _inputs, _linear, evaluate
from crafting_system.risk._chain import build_chain
from crafting_system.risk._report import UNDECIDED
from crafting_system.solver import Action

EPS = _linear.EPS
DONE = {"goal", "done"}


def is_done(state):
    return state in DONE


def exact_solve(matrix: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    """Gauss-Jordan elimination of `matrix x = rhs` in exact arithmetic."""
    n = len(rhs)
    rows = [[*matrix[i], rhs[i]] for i in range(n)]
    for c in range(n):
        pivot = next(r for r in range(c, n) if rows[r][c] != 0)
        rows[c], rows[pivot] = rows[pivot], rows[c]
        rows[c] = [v / rows[c][c] for v in rows[c]]
        for r in range(n):
            if r != c and rows[r][c] != 0:
                rows[r] = [a - rows[r][c] * b for a, b in zip(rows[r], rows[c])]
    return [rows[i][n] for i in range(n)]


def system_of(policy):
    """`(states, M)` with `M[s][t]` the chance `s` goes to `t` plus one for each copy of `t` among its inputs; goals are not states."""
    states = [s for s in policy]
    index = {s: i for i, s in enumerate(states)}
    m = [[Fraction(0)] * len(states) for _ in states]
    for s, action in policy.items():
        total = sum(o[1] for o in action.outcomes)
        for target, weight in action.outcomes:
            if target in index:
                m[index[s]][index[target]] += Fraction(weight, total)
        for y in action.extra_inputs:
            m[index[s]][index[y]] += 1
    return states, m


def exact_means(policy):
    states, m = system_of(policy)
    n = len(states)
    matrix = [[(1 if i == j else 0) - m[i][j] for j in range(n)] for i in range(n)]
    return states, exact_solve(matrix, [Fraction(policy[s].cost) for s in states])


def exact_moments(policy, start):
    """`(mean, variance)` of the total cost from `start`: the first moment by elimination, the second from it by the formula of `_inputs`."""
    states, m1 = exact_means(policy)
    index = {s: i for i, s in enumerate(states)}
    second = []
    for s in states:
        action = policy[s]
        total_weight = sum(o[1] for o in action.outcomes)
        c = Fraction(action.cost)
        feeds = [m1[index[y]] for y in action.extra_inputs]
        ahead = sum((Fraction(w, total_weight) * m1[index[t]] for t, w in action.outcomes if t in index), Fraction(0))
        total = sum(feeds, Fraction(0))
        pairs = sum((feeds[a] * feeds[b] for a in range(len(feeds)) for b in range(a + 1, len(feeds))), Fraction(0))
        second.append(c * c + 2 * c * (total + ahead) + 2 * pairs + 2 * ahead * total)
    _, m = system_of(policy)
    n = len(states)
    m2 = exact_solve([[(1 if i == j else 0) - m[i][j] for j in range(n)] for i in range(n)], second)
    s0 = index[start]
    return m1[s0], m2[s0] - m1[s0] ** 2


def exact_visits(policy, start):
    """The expected visits of every state from `start`, row `start` of `(I - M)^-1`, by elimination of the transposed system."""
    states, m = system_of(policy)
    n = len(states)
    transposed = [[(1 if i == j else 0) - m[j][i] for j in range(n)] for i in range(n)]
    unit = [Fraction(1 if s == start else 0) for s in states]
    return dict(zip(states, exact_solve(transposed, unit), strict=True))


def stiff_policy(rng: random.Random, size: int, power: int, donors: int = 0, donor_power: int | None = 0):
    """Every state stays with weight `10**power` against 1 to 3 weights of 1 to 3 to others and the goal; the first states use one run of a donor each.

    The donors (states `D0`...) lead to each other and to `done`, never back: the runs they make are independent of the states that use them, so the policy
    is subcritical, and the mean cost of the start is of the order `10**power` (the self-loop is the stiffness, as in the route-flow tests of #615). A donor
    stays with weight `10**donor_power`; with `donor_power = power` a stiff state consumes a stiff donor and its cost is the product of the two.
    """
    names = [f"s{i}" for i in range(size)]
    donor_names = [f"D{i}" for i in range(donors)]
    policy = {}
    for name in names:
        others = [*rng.sample(names, rng.randint(1, 3)), "goal"]
        uses = (rng.choice(donor_names),) if donor_names and rng.random() < 0.5 else ()
        policy[name] = Action(
            rng.choice("abc"), rng.choice([1, 2, 3]), ((name, 10**power), *((t, rng.choice([1, 2, 3])) for t in others if t != name)), extra_inputs=uses
        )
    for k, name in enumerate(donor_names):
        later = donor_names[k + 1 :]
        outcomes = ((name, 10 ** (power if donor_power is None else donor_power)), ("done", rng.choice([1, 2])), *((t, rng.choice([1, 2])) for t in rng.sample(later, min(len(later), 1))))
        policy[name] = Action("donor", rng.choice([1, 2, 3]), outcomes)
    return names[0], policy


def chain_of(start, policy):
    return build_chain(policy, start, is_done)


def skeel(chain) -> float:
    """The Skeel condition of the system the risk solves, `max (|A^-1| |A| |x|) / |x|` with `A = I - P'` (the self-loops divided out), in floats."""
    import numpy as np

    system = _inputs._system(chain)
    nodes = list(system.nodes)
    at = {s: k for k, s in enumerate(nodes)}
    a = np.eye(len(nodes))
    for s in nodes:
        for t, coef in system.scaled_rows[s]:
            a[at[s], at[t]] -= coef
    costs = _inputs.real_costs(chain)
    x = np.linalg.solve(a, np.array([costs[s] / system.pivot[s] for s in nodes]))
    return float(np.max(np.abs(np.linalg.inv(a)) @ np.abs(a) @ np.abs(x) / np.abs(x)))


@pytest.mark.parametrize(("power", "donor_power"), [(6, 0), (10, 0), (13, 0), (4, None), (6, None), (8, None), (10, None), (12, None)])
def test_the_mean_and_variance_of_a_stiff_policy_with_inputs_are_good_and_the_bound_is_its_condition_times_the_rounding(power, donor_power):
    """A stiff state stays with weight `10**power`; a donor is mild (`donor_power` 0) or as stiff (None), and then a stiff state consumes a stiff donor.

    The cost of a stiff state that consumes a stiff donor is the product of two stiffnesses, 1e24 at 1e12. The certificate against the costs of the actions
    is worse by the ratio of the cost to the cost of one action (3e-4 at 1e10, refused above 1e11: #670); the one against the scale of the terms, certified
    by one more sweep, is the rounding times the Skeel condition of the system, about 1e-13 at every weight, and both hold the exact value.
    """
    width = 1e-12
    for seed in range(20):
        rng = random.Random(seed)
        start, policy = stiff_policy(rng, rng.randint(3, 6), power, donors=rng.randint(1, 3), donor_power=donor_power)
        chain = chain_of(start, policy)
        mean, variance = exact_moments(policy, start)

        (m, m_low, m_high), (v, v_low, v_high), _ = _inputs.mean_and_variance(chain)

        assert m_low <= mean <= m_high and v_low <= variance <= v_high, (power, seed)
        assert m == pytest.approx(float(mean), rel=1e-12) and v == pytest.approx(float(variance), rel=1e-12), (power, seed)
        assert (m_high - m_low) <= width * float(mean), (power, seed)  # the bound is a residual that is small, not one that is merely under 1
        assert (m_high - m_low) <= 64 * len(chain.states) * EPS * skeel(chain) * float(mean), (power, seed)  # a few units of the rounding times the condition
        assert (v_high - v_low) <= 10 * width * float(variance), (power, seed)


@pytest.mark.parametrize(("power", "donor_power"), [(6, 0), (10, 0), (13, 0), (4, None), (8, None), (12, None)])
def test_the_donor_counts_and_the_weighted_visits_of_a_stiff_policy_are_good_and_their_range_is_narrow(power, donor_power):
    """The range of a donor count was a 1-norm of the visits' residual times `max V / c_min`, `[0, huge]` on a stiff chain (#670); it is now each state's
    backward error times a bound certified by one more sweep, and the width is the floor of the summing (`MIN_COUNT_ROUNDING`, 1e-12 of the count)."""
    for seed in range(12):
        rng = random.Random(100 + seed)
        start, policy = stiff_policy(rng, rng.randint(3, 6), power, donors=rng.randint(1, 3), donor_power=donor_power)
        chain = chain_of(start, policy)
        visits = exact_visits(policy, start)
        values, error = _inputs.solve_costs(chain, _inputs.real_costs(chain))

        uses = _inputs.expected_uses(chain, values, error)
        weighted = _inputs.weighted_visits(chain, values, error, [1.0 if chain.action[i] else 0.0 for i in range(len(chain.states))])

        for y, (value, low, high) in uses.items():
            name = chain.states[y]
            exact = sum(
                visits[s] * policy[s].extra_inputs.count(name) for s in policy
            )  # the runs started at `name`: the visits of every state that lists it
            assert low <= exact <= high and value == pytest.approx(float(exact), rel=1e-9), (power, seed, name)
            assert high - low <= 3 * _inputs.MIN_COUNT_ROUNDING * value, (power, seed, name)
        total = sum(visits.values())
        assert weighted[1] <= total <= weighted[2] and weighted[0] == pytest.approx(float(total), rel=1e-9), (power, seed)
        assert weighted[2] - weighted[1] <= 3 * _inputs.MIN_COUNT_ROUNDING * weighted[0], (power, seed)


@pytest.mark.parametrize("power", [6, 10, 13])
def test_the_visits_of_the_coarse_grid_of_a_stiff_chain_are_good_with_a_bound_that_holds(power):
    checked = 0
    for seed in range(20):
        rng = random.Random(200 + seed)
        start, policy = stiff_policy(rng, rng.randint(3, 8), power)
        chain = chain_of(start, policy)
        exact = exact_visits(policy, start)

        found = _coarse.expected_visits_checked(chain)

        assert found is not None
        states, visits, bound = found
        for s, v in zip(states, visits, strict=True):
            assert abs(v - float(exact[chain.states[s]])) <= bound * v + 1e-300, (power, seed, s)
            assert v == pytest.approx(float(exact[chain.states[s]]), rel=1e-9)
        assert bound < 1e-9  # a stiff self-loop costs no digits once it is divided out
        checked += 1
    assert checked == 20


# --- stiffness the self-loop division cannot remove: a cycle of states, each leaving with chance 1e-p ----------------------------------------------------


def ring(weight, donor=True):
    """A and B send each other with weight `weight` against 1 to the goal; A also uses a donor run (mean 18): the cost of A is about `weight / 2`, with no self-loop to divide out."""
    policy = {
        "A": Action("a", 1, (("B", weight), ("goal", 1)), extra_inputs=("D",) if donor else ()),
        "B": Action("b", 2, (("A", weight), ("goal", 1))),
        "D": Action("d", 3, (("done", 1), ("D", 5))),
    }
    return "A", policy


def ring_mean(weight):
    p = Fraction(weight, weight + 1)
    return (1 + 18 + 2 * p) / (1 - p * p)


@pytest.mark.parametrize("power", [4, 8, 10])
def test_a_cycle_that_is_stiff_is_certified_to_the_digits_its_conditioning_leaves_and_the_exact_mean_is_inside(power):
    start, policy = ring(10**power)
    chain = chain_of(start, policy)

    values, error = _inputs.solve_costs(chain, _inputs.real_costs(chain))

    low, high = _inputs.bracket(values[0], error)
    assert low <= ring_mean(10**power) <= high
    assert error < 1e-12 * 10**power  # about the machine epsilon times the expected steps of a run, not 1
    assert values[0] == pytest.approx(float(ring_mean(10**power)), rel=1e-6)


def test_a_cycle_whose_mean_is_known_to_less_than_four_digits_is_said_in_a_limit():
    from crafting_system.planner._limits import loose_figures, risk_limits

    start, policy = ring(10**11)
    risk = evaluate(policy, start, is_done, resolve_quantiles=False)

    assert _linear.SAID_ABOVE < (risk.mean.high - risk.mean.value) / risk.mean.value <= _linear.REFUSED_ABOVE
    assert risk.mean.low <= float(ring_mean(10**11)) <= risk.mean.high
    limit = loose_figures(risk)
    assert limit is not None and limit.what == "The cost figures are good to fewer digits than printed"
    assert "significant digits" in limit.why and limit in risk_limits(risk)
    start, policy = ring(10**4)
    assert loose_figures(evaluate(policy, start, is_done, resolve_quantiles=False)) is None  # a plan that is not stiff says nothing


@pytest.mark.parametrize("power", [13, 16])
def test_a_cycle_so_stiff_that_the_mean_is_known_to_less_than_one_in_a_hundred_is_refused_not_shown_with_a_bound_under_one(power):
    start, policy = ring(10**power)
    chain = chain_of(start, policy)

    with pytest.raises(_inputs.NotSubcritical):  # (`Undecided` at 1e13; at 1e16 the check fails altogether, as it did before)
        _inputs.solve_costs(chain, _inputs.real_costs(chain))
    with pytest.raises(_inputs.NotSubcritical):
        _inputs.mean_and_variance(chain)


def test_the_refusal_at_one_in_a_hundred_is_an_undecided_not_a_policy_that_needs_more_than_it_makes():
    start, policy = ring(10**13)  # (at 1e12 the bound against the scale of the terms, #670, is 2e-3: shown, with a limit)
    chain = chain_of(start, policy)

    with pytest.raises(_inputs.Undecided, match="relative error"):
        _inputs.solve_costs(chain, _inputs.real_costs(chain))
    risk = evaluate(policy, start, is_done, resolve_quantiles=False)

    assert risk.grid.cause == UNDECIDED and math.isinf(risk.mean.value)
    from crafting_system.planner._limits import risk_limits
    from crafting_system.cli._report import NOT_COMPUTED

    (limit,) = risk_limits(risk)  # the reader is told it is the arithmetic, not the plan, that could not decide
    assert "close to 1" in limit.why and "more runs of its inputs" not in limit.why and limit.what.startswith("Not computed")
    assert "arithmetic" in NOT_COMPUTED[UNDECIDED] and "more runs" not in NOT_COMPUTED[UNDECIDED]


def test_the_visits_of_the_coarse_grid_are_refused_with_none_when_their_bound_is_above_one_in_a_hundred():
    start, policy = ring(10**13, donor=False)

    assert _coarse.expected_visits(chain_of(start, policy)) is None
    assert _coarse.expected_visits_checked(chain_of(*ring(10**8, donor=False))) is not None


# --- the dense solve itself ------------------------------------------------------------------------------------------------------------------------


def test_the_backward_error_of_the_dense_solve_is_the_rounding_of_the_product_for_a_good_answer_and_about_one_for_a_wrong_one():
    import numpy as np

    off = np.array([[0.0, 0.5], [0.25, 0.0]])
    rhs = np.array([1.0, 2.0])

    x, error = _linear.solve(off, rhs)

    assert error <= 8 * _linear.EPS
    first = 2.0 / 0.875  # x0 = 1 + x1 / 2 and x1 = 2 + x0 / 4
    assert x == pytest.approx([first, 2.0 + first / 4.0], rel=1e-14)
    assert _linear.backward_error(off, rhs, x + 1.0) > 0.1
    assert _linear.backward_error(off, rhs, np.array([math.nan, 1.0])) == math.inf


def test_a_matrix_that_is_singular_in_floats_has_no_solve_and_the_refinement_is_taken_only_while_it_helps():
    import numpy as np

    assert _linear.solve(np.array([[0.0, 1.0], [1.0, 0.0]]), np.array([1.0, 1.0])) is None  # I - off is singular: x = 1 + x
    assert _linear.solve(np.zeros((0, 0)), np.zeros(0)) == (pytest.approx(np.zeros(0)), 0.0)


def test_the_forward_estimate_holds_the_true_error_of_an_answer_and_is_tiny_for_a_good_one():
    import numpy as np

    off = np.array([[0.0, 0.5], [0.25, 0.0]])
    rhs = np.array([1.0, 2.0])
    exact = np.array([2.0 / 0.875, 2.0 + 2.0 / 0.875 / 4.0])
    x, error = _linear.solve(off, rhs)

    assert _linear.forward_estimate(off, rhs, x, error) < 1e-13
    for wrong in (1e-9, 1e-6, 1e-3):  # an answer that is off by a known relative amount: the bound must cover it
        perturbed = exact * np.array([1.0 + wrong, 1.0 - wrong])
        measured = _linear.backward_error(off, rhs, perturbed)
        assert _linear.forward_estimate(off, rhs, perturbed, measured) >= float(np.max(np.abs(perturbed - exact) / exact))
    assert _linear.forward_estimate(np.array([[0.0, 1.0], [1.0, 0.0]]), rhs, rhs, 0.5) == math.inf  # a singular system has no bound
