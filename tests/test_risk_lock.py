"""`risk` on a plan with Hinekora's Lock (ticket #297, ADR-0054, ADR-0057): the expanded policy against the explicit product expansion.

`solve_peek` hands `risk` its policy with the Lock replaced by ordinary actions under the acceptance set (the "apply a" and "give up"
pseudo-states). The oracle is the explicit product expansion of the same tiny model (`peek_oracles.product_spec`: a react state for
every combination of one result per option), played with the same acceptance set (`lock_support.product_policy`) and evaluated in
exact fractions. By the ticket's "Done when":

* on tiny models `risk.evaluate`'s mean and second moment equal the product expansion's (seeded models that take the Lock, every
  family of `peek_oracles` among them, and the burn loop);
* with a Lock costing 100,000 Chaos next to a 1-Chaos burn (the case of #190: a cost far below the quantile asked, so the ordinary
  grid cannot reach it) the p90 and the CVaR of `risk.evaluate` hold the closed form, and agree with `risk.evaluate` on the explicit
  product expansion.
"""

import math
from fractions import Fraction

import pytest
from lock_support import burn_spec, product_policy
from peek_oracles import peek_model, product_spec, random_peek_spec
from risk_support import geometric_cvar, geometric_moments, geometric_quantile_steps
from ssp_oracles import _solve_fractions, to_model

from crafting_system.risk import evaluate
from crafting_system.solver import PeekNode, solve_peek

_SOLVED = {}


def solved(spec):
    key = repr(spec)
    if key not in _SOLVED:
        _SOLVED[key] = solve_peek(peek_model(spec), [spec.state, *range(spec.size)])
    return _SOLVED[key]


def goal_of(spec):
    return lambda state: not isinstance(state, PeekNode) and state == spec.size


def exact_moments(product, choice, start):
    """Mean and second moment of the total cost of `choice` on the product spec, in fractions (the policy must be proper).

    X(s) = c + X(next): E[X] = c + sum P E[X'], E[X^2] = c^2 + 2 c sum P E[X'] + sum P E[X'^2].
    """
    size, table = product
    states = sorted(choice)
    index = {s: i for i, s in enumerate(states)}

    def solve(rhs_of):
        matrix = [[Fraction(int(i == j)) for j in range(len(states))] for i in range(len(states))]
        rhs = []
        for s in states:
            _, cost, outcomes = table[s][choice[s]]
            total = sum(w for _, w in outcomes)
            for t, w in outcomes:
                if t != size:
                    matrix[index[s]][index[t]] -= Fraction(w, total)
            rhs.append(rhs_of(Fraction(cost), outcomes, total))
        return dict(zip(states, _solve_fractions(matrix, rhs)))

    mean = solve(lambda c, outs, total: c)
    second = solve(lambda c, outs, total: c * c + 2 * c * sum(Fraction(w, total) * mean.get(t, 0) for t, w in outs if t != size))
    return mean[start], second[start]


def reachable(product, choice, start):
    size, table = product
    seen, stack = {start}, [start]
    while stack:
        s = stack.pop()
        if s == size:
            continue
        for t, w in table[s][choice[s]][2]:
            if w and t not in seen:
                seen.add(t)
                stack.append(t)
    return {s: choice[s] for s in seen if s != size}


def lock_seeds(count, *, start=0):
    found = []
    for seed in range(start, 6000):
        spec = random_peek_spec(seed)
        if spec.state is None:
            continue
        solution = solved(spec)
        action = solution.policy.get(spec.state)
        if action is not None and action.label == "lock" and math.isfinite(solution.values[spec.state]):
            found.append(seed)
        if len(found) == count:
            return found
    raise AssertionError("too few seeded models take the Lock")


def check_moments(spec):
    solution = solved(spec)
    report = evaluate(solution.policy, spec.state, goal_of(spec))
    product = product_spec(spec)
    choice = reachable(product, product_policy(spec, solution), spec.state)
    mean, second = exact_moments(product, choice, spec.state)
    assert report.success_probability.value == 1.0
    assert report.mean.value == pytest.approx(float(mean), rel=1e-9)
    assert report.variance.value + report.mean.value**2 == pytest.approx(float(second), rel=1e-8)
    assert report.mean.value == pytest.approx(solution.values[spec.state], rel=1e-9)  # the expanded policy is the plan
    return report, product, choice


@pytest.mark.parametrize("seed", lock_seeds(40))
def test_mean_and_second_moment_equal_the_product_expansion(seed):
    check_moments(random_peek_spec(seed))


def test_the_burn_loop_has_the_product_moments():
    spec = burn_spec(lock=Fraction(3), success=1, failure=4, option_cost=Fraction(1), burn=Fraction(1, 2))
    report, _, _ = check_moments(spec)
    # C = 3.5 N - 0.5 + 1 with N ~ Geometric(1/5)
    mean, variance = geometric_moments(Fraction(1, 5), Fraction(7, 2))
    assert report.mean.value == pytest.approx(float(mean + Fraction(1, 2)))
    assert report.variance.value == pytest.approx(float(variance))


def test_quantiles_agree_with_the_product_expansion():
    for seed in lock_seeds(10):
        spec = random_peek_spec(seed)
        report, product, choice = check_moments(spec)
        model = to_model(product)
        policy = {s: model.actions(s)[i] for s, i in choice.items()}
        oracle = evaluate(policy, spec.state, lambda s: s == product[0])
        for level in (0.5, 0.9):
            mine, theirs = report.quantiles[level], oracle.quantiles[level]
            assert mine.low <= theirs.high and theirs.low <= mine.high
        assert report.cvar.low <= oracle.cvar.high and oracle.cvar.low <= report.cvar.high


def test_a_lock_of_100000_next_to_a_burn_of_1():
    """The case of #190: C = 100,001 N, N geometric with chance 1/5 (a Lock, then a 1-Chaos option on a hit or a 1-Chaos burn on a miss)."""
    spec = burn_spec(lock=Fraction(100_000), success=1, failure=4, option_cost=Fraction(1), burn=Fraction(1))
    solution = solved(spec)
    assert solution.policy[0].label == "lock"
    report = evaluate(solution.policy, 0, goal_of(spec))
    p, unit = Fraction(1, 5), 100_001
    p90 = unit * geometric_quantile_steps(p, Fraction(9, 10))
    cvar = geometric_cvar(p, unit, Fraction(9, 10))
    assert p90 == 1_100_011
    assert report.p90.low <= p90 <= report.p90.high
    assert report.cvar.low <= cvar <= report.cvar.high
    assert report.p90.high - report.p90.low <= 0.05 * p90  # the coarse grid of #190 (a step of 2,000 here): a bracket of 2%, not a shrug
    assert report.cvar.high - report.cvar.low <= 0.05 * cvar

    product = product_spec(spec)
    model = to_model(product)
    choice = reachable(product, product_policy(spec, solution), 0)
    oracle = evaluate({s: model.actions(s)[i] for s, i in choice.items()}, 0, lambda s: s == product[0])
    assert oracle.p90.low <= p90 <= oracle.p90.high
    assert report.p90.low <= oracle.p90.high and oracle.p90.low <= report.p90.high
    assert report.cvar.low <= oracle.cvar.high and oracle.cvar.low <= report.cvar.high
    mean, second = exact_moments(product, choice, 0)
    assert report.mean.value == pytest.approx(float(mean))
