"""The interval driver over rule axes on a plan with Hinekora's Lock (ticket #297, ADR-0054; `risk.solve_readings`, ticket #220).

Each reading of a rule axis is a tiny Peek model (`peek_oracles`) with the same states and outcomes and other weights. The driver
solves each with `solve_peek` and evaluates every candidate under every reading with its acceptance set fixed, the chances recomputed
from that reading's kernels. The oracle (Done when): each reading's explicit product expansion (`peek_oracles.product_spec`) played with
the candidate's acceptance set (`lock_support.product_policy`) and evaluated exactly in fractions gives every entry of the table, so
the plan's `[min; max]` is the one of the product expansions.

Also: a reading whose option can throw a result the plan's acceptance set never saw (it is not accepted there); a model with no
axis (the interval is a point, the value `solve_peek`'s); the comparison route without an action, taken out of the Lock's options.
"""

import math
import random
from fractions import Fraction

import pytest
from lock_support import product_policy
from peek_oracles import PeekSpec, peek_model, product_spec, random_peek_spec
from ssp_oracles import evaluate_exactly

from crafting_system.risk import solve_readings
from crafting_system.solver import solve_peek

READINGS = ("plan", "low", "high")


def reweighted(spec, rng):
    """`spec` with every weight scaled by a random factor (the same outcomes, other chances): one more reading of a rule."""

    def outs(outcomes):
        return [(state, weight * rng.randint(1, 6)) for state, weight in outcomes]

    table = {s: [(label, cost, outs(o)) for label, cost, o in actions] for s, actions in spec.table.items()}
    options = [(label, cost, outs(o)) for label, cost, o in spec.options]
    fallback = [(label, cost, outs(o)) for label, cost, o in spec.fallback]
    return spec._replace(table=table, options=options, fallback=fallback)


def reading_specs(seed):
    spec = random_peek_spec(seed)
    rng = random.Random(seed * 7919 + 1)
    return {"plan": spec, "low": reweighted(spec, rng), "high": reweighted(spec, rng)}


def oracle_value(spec, route):
    product = product_spec(spec)
    value = evaluate_exactly(product, product_policy(spec, route))[spec.state]
    return math.inf if value is None else float(value)


def lock_reading_seeds(count):
    found = []
    for seed in range(4000):
        spec = random_peek_spec(seed)
        if spec.state is None:
            continue
        specs = reading_specs(seed)
        solutions = {r: solve_peek(peek_model(s), [spec.state]) for r, s in specs.items()}
        if any(solution.policy.get(spec.state) is not None and solution.policy[spec.state].label == "lock"
               and math.isfinite(solution.values[spec.state]) for solution in solutions.values()):  # fmt: skip
            found.append(seed)
        if len(found) == count:
            return found
    raise AssertionError("too few seeded models take the Lock")


@pytest.mark.parametrize("seed", lock_reading_seeds(30))
def test_the_table_is_the_product_expansion_under_every_reading(seed):
    specs = reading_specs(seed)
    start = specs["plan"].state
    report = solve_readings({r: peek_model(s) for r, s in specs.items()}, start, plan="plan")
    for c in READINGS:
        route = report.routes[c]
        for r2 in READINGS:
            want = oracle_value(specs[r2], route)
            got = report.table[c][r2].value
            if math.isinf(want):
                assert math.isinf(got), (c, r2, got)
            else:
                assert got == pytest.approx(want, rel=1e-9, abs=1e-12), (c, r2)
    plan = [oracle_value(specs[r2], report.plan) for r2 in READINGS]
    assert report.plan.interval == pytest.approx((min(plan), max(plan)), rel=1e-9)
    own = solve_peek(peek_model(specs["plan"]), [start])
    assert report.plan.reactions == own.reactions  # the plan's acceptance set, the one held fixed across readings
    assert report.values["plan"].value == pytest.approx(own.values[start], rel=1e-9)


# goal 3; state 0 offers the Lock with one option (to the goal or a middle state 1) and a burn of 20 back to 0; 1 finishes for 30
def tiny(option_outcomes):
    return PeekSpec(
        3,
        {0: [("restart", Fraction(200), [(3, 1)])], 1: [("finish", Fraction(30), [(3, 1)])], 2: [("finish", Fraction(500), [(3, 1)])]},
        0, Fraction(2), [("option", Fraction(1), option_outcomes)], [("burn", Fraction(20), [(0, 1)])], 0,
    )  # fmt: skip


def test_a_result_the_acceptance_set_never_saw_is_not_accepted():
    plan, other = tiny([(3, 1), (1, 3)]), tiny([(3, 1), (1, 3), (2, 4)])
    report = solve_readings({"plan": peek_model(plan), "other": peek_model(other)}, 0, plan="plan")
    assert report.plan.reactions[0] == ((0, 3), (0, 1))  # 2 + 1/4 + 3/4 * 31 = 25.5 beats burning on the middle state (69)
    # under "other" the plan locks, takes the goal or the middle state, and burns on the new result 2: an exact geometric loop
    accept, total = Fraction(4), Fraction(8)
    locks = total / accept
    middle = Fraction(3, 4)  # of the accepted
    want = locks * 2 + (locks - 1) * 20 + 1 + middle * 30  # 47.5
    assert report.plan.costs["other"].value == pytest.approx(float(want))


def test_no_axis_gives_a_point():
    spec = tiny([(3, 1), (1, 3)])
    report = solve_readings({"only": peek_model(spec)}, 0)
    value = solve_peek(peek_model(spec), [0]).values[0]
    assert report.plan.interval == pytest.approx((value, value))
    assert report.proven_optimal
    assert report.plan.policy[0].label == "lock"


def test_the_comparison_route_drops_an_action_from_the_lock():
    spec = tiny([(3, 1), (1, 3)])
    report = solve_readings({"only": peek_model(spec)}, 0, without=lambda action: action.label == "option")
    assert report.baseline.value.value == pytest.approx(200.0)  # no option left: the Lock goes, the restart remains
    kept = solve_readings({"only": peek_model(spec)}, 0, without=lambda action: action.label == "burn")
    alone = spec._replace(fallback=[])
    assert kept.baseline.value.value == pytest.approx(solve_peek(peek_model(alone), [0]).values[0])
