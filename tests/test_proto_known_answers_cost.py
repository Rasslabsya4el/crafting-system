"""Ticket #73: the prototype's hand-checked solver cases H1-H3 and cost known answers KA30-KA41, on today's code.

Every expected number is the hand value of the prototype (`docs/specs/2026-09-21-bounded-policy-solver.md`,
`docs/research/known-answers.md`, `docs/specs/2026-09-21-loop-costs.md` on `archive/prototype`), typed as a
constant with its derivation beside it. KA27-KA29 (utility masses) are not here: ADR-0006 minimises the mean
cost and nothing is optimised on a utility, so they no longer hold as such.

Each loop of KA30-KA41 is a policy `{state: Action}` read by `risk.evaluate`. A cost distribution lives on
the integer cost lattice, so those grids are exact and the value must equal the hand value to 1e-9 relative.
"""

import math

import pytest
from risk_support import is_goal
from ssp_helpers import DIRECT_LIMITS, GOAL, act, model

from crafting_system.risk import evaluate
from crafting_system.solver import Action, solve

limits = pytest.mark.parametrize("limit", DIRECT_LIMITS.values(), ids=DIRECT_LIMITS.keys())

# ---------------------------------------------------------------- H1-H3: the hand-checked solver cases

# value of each state and the label chosen in each state
SOLVER_CASES = [
    pytest.param(
        # V(S) = 2 + 3/4 V(S)  =>  V(S) = 8
        {"S": [act("retry", 2, (GOAL, 1), ("S", 3))]},
        {"S": 8.0},
        {"S": "retry"},
        id="H1",
    ),
    pytest.param(
        # V(T) = 2; cheap at S: V = 1 + 1/2 V(T) + 1/2 V  =>  V(S) = 2 + V(T) = 4 (direct costs 6)
        {
            "S": [act("cheap", 1, ("T", 1), ("S", 1)), act("direct", 6, (GOAL, 1))],
            "T": [act("finish", 2, (GOAL, 1))],
        },
        {"S": 4.0, "T": 2.0},
        {"S": "cheap", "T": "finish"},
        id="H2",
    ),
    pytest.param(
        # V(B) = min(recover 2 + V(A), finish 5) = 5; gamble at A: V = 1 + 3/4 * 5 = 4.75 (direct costs 7)
        # always recovering would give V(A) = 1 + 3/4 (2 + V(A)) = 10, worse than direct 7
        {
            "A": [act("gamble", 1, (GOAL, 1), ("B", 3)), act("direct", 7, (GOAL, 1))],
            "B": [act("recover", 2, ("A", 1)), act("finish", 5, (GOAL, 1))],
        },
        {"A": 4.75, "B": 5.0},
        {"A": "gamble", "B": "finish"},
        id="H3",
    ),
]


@limits
@pytest.mark.parametrize(("table", "values", "labels"), SOLVER_CASES)
def test_hand_values_and_chosen_actions(table, values, labels, limit):
    start = next(iter(table))

    solution = solve(model(table), [start], direct_solve_limit=limit)

    bound = solution.error_bound
    for state, hand in values.items():
        assert solution.values[state] * (1 - bound) <= hand <= solution.values[state] * (1 + bound)
        assert solution.values[state] == pytest.approx(hand, rel=1e-9)
    assert {state: solution.policy[state].label for state in labels} == labels


# ---------------------------------------------------------------- robustness cases of the same spec


@limits
def test_an_unreachable_self_loop_state_is_infinite_and_corrupts_nothing(limit):
    # L only repeats itself: no policy reaches a goal from it. S has the H1 retry, plus a risky
    # action into L that is never chosen (retry is proper, risky is not).
    table = {
        "S": [act("retry", 2, (GOAL, 1), ("S", 3)), act("risky", 1, (GOAL, 1), ("L", 1))],
        "L": [act("stuck", 1, ("L", 1))],
    }

    solution = solve(model(table), ["S", "L"], direct_solve_limit=limit)

    assert solution.values["S"] == pytest.approx(8.0, rel=1e-9)  # H1
    assert solution.values["L"] == math.inf
    assert solution.policy["S"].label == "retry"
    assert "L" not in solution.policy
    assert not any(math.isnan(v) for v in solution.values.values())


def test_a_successor_without_actions_is_infinite_instead_of_rejected():
    # The prototype rejected an unknown successor id; today a state absent from the table is a state
    # with no action, so its value is infinity and the action leading only there is never chosen.
    table = {"S": [act("go", 1, ("ghost", 1)), act("safe", 5, (GOAL, 1))]}

    solution = solve(model(table), ["S"])

    assert solution.values["ghost"] == math.inf
    assert solution.values["S"] == 5.0
    assert solution.policy["S"].label == "safe"


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: Action("bad", 1, ((GOAL, -1), ("S", 2))), id="negative-weight"),
        pytest.param(lambda: Action("bad", 1, ((GOAL, 0), ("S", 0))), id="zero-total-weight"),
        pytest.param(lambda: Action("bad", 0, ((GOAL, 1),)), id="zero-cost"),
        pytest.param(lambda: Action("bad", -2, ((GOAL, 1),)), id="negative-cost"),
        pytest.param(lambda: Action("bad", 1, ((GOAL, 0.5), ("S", 0.5))), id="fractional-weight"),
    ],
)
def test_a_malformed_action_is_rejected_with_value_error(build):
    # integer weights make "probabilities not summing to 1" impossible; what is left to reject is this
    with pytest.raises(ValueError):
        build()


# ---------------------------------------------------------------- KA30-KA41: cost loops read by risk.evaluate


def hits(result, truth, rel=1e-9):
    """The value (an `Estimate`, or a float derived from one) equals the hand value; an interval contains it."""
    value = getattr(result, "value", result)
    assert value == pytest.approx(truth, rel=rel)
    if hasattr(result, "low"):
        assert result.low - rel * abs(truth) <= truth <= result.high + rel * abs(truth)


def loop(price, success, failure, *, name="S"):
    """One state whose action costs `price`: goal with weight `success`, else back to itself."""
    return {name: Action("try", price, ((GOAL, success), (name, failure)))}


HALF_PRICE_TWO = loop(2, 1, 1)
SIXTH_PRICE_TWO = loop(2, 1, 5)
# S1 -> S2 -> goal, each stage a p = 1/2 price-1 loop
TWO_STAGES = {
    "S1": Action("first", 1, (("S2", 1), ("S1", 1))),
    "S2": Action("second", 1, ((GOAL, 1), ("S2", 1))),
}
# one attempt: price 1 or 2 with equal chance, independent of success (p = 1/2). S pays the first unit and
# goes to goal / S (price-1 success / failure) or to G / F (price-2 success / failure); G and F pay the second.
COMPOUND = {
    "S": Action("attempt", 1, ((GOAL, 1), ("S", 1), ("G", 1), ("F", 1))),
    "G": Action("second-unit", 1, ((GOAL, 1),)),
    "F": Action("second-unit", 1, (("S", 1),)),
}
# setup 7, then p = 1/2 tries of price 2, each failure paying a reset of 3 before the next try
RESET_SETUP = {
    "U": Action("setup", 7, (("S", 1),)),
    "S": Action("try", 2, ((GOAL, 1), ("R", 1))),
    "R": Action("reset", 3, (("S", 1),)),
}

KA_CASES = [
    # E[attempts] = 1/p = 2: the mean cost 4 over the price 2
    pytest.param(HALF_PRICE_TWO, "S", lambda r: r.mean.value / 2, 2.0, id="KA30"),
    # E[C] = price * E[N] = 2 * 2
    pytest.param(HALF_PRICE_TWO, "S", lambda r: r.mean, 4.0, id="KA31"),
    # smallest N with 1 - (1/2)^N >= .9 is 4 (CDF(3) = 7/8 < .9, CDF(4) = 15/16): the p90 cost 8 over the price 2
    pytest.param(HALF_PRICE_TWO, "S", lambda r: r.p90.value / 2, 4.0, id="KA32"),
    # p90 cost = price * 4
    pytest.param(HALF_PRICE_TWO, "S", lambda r: r.p90, 8.0, id="KA33"),
    # E[C] = 2 / (1/6)
    pytest.param(SIXTH_PRICE_TWO, "S", lambda r: r.mean, 12.0, id="KA34"),
    # (5/6)^12 = .1122 > .1 >= (5/6)^13 = .0935: N = 13, cost 2 * 13
    pytest.param(SIXTH_PRICE_TWO, "S", lambda r: r.p90, 26.0, id="KA35"),
    # E[C] = 2 + 2
    pytest.param(TWO_STAGES, "S1", lambda r: r.mean, 4.0, id="KA36"),
    # CDF(6) = 57/64 = .8906 < .9 <= CDF(7) = 15/16; not the sum of the marginal p90s, 4 + 4 = 8
    pytest.param(TWO_STAGES, "S1", lambda r: r.p90, 7.0, id="KA37"),
    # E[C] = E[attempts] * E[price] = 2 * (1 + 2) / 2
    pytest.param(COMPOUND, "S", lambda r: r.mean, 3.0, id="KA38"),
    # CDF(5) = .8798828125 < .9 <= CDF(6) = .924072265625
    pytest.param(COMPOUND, "S", lambda r: r.p90, 6.0, id="KA39"),
    # E[C] = 7 + 2 * E[N] + 3 * (E[N] - 1) = 7 + 4 + 3
    pytest.param(RESET_SETUP, "U", lambda r: r.mean, 14.0, id="KA40"),
    # N = 4: 7 + 2 * 4 + 3 * (4 - 1)
    pytest.param(RESET_SETUP, "U", lambda r: r.p90, 24.0, id="KA41"),
]


@pytest.mark.parametrize(("policy", "start", "read", "hand"), KA_CASES)
def test_known_answers_of_the_cost_loops(policy, start, read, hand):
    report = evaluate(policy, start, is_goal)

    assert report.grid.exact
    hits(read(report), hand)


def test_the_compound_loop_cdf_crosses_09_between_five_and_six():
    # CDF(4) = .81640625 (h1..h4 = .25 + .3125 + .140625 + .11328125), CDF(5) = .8798828125, CDF(6) = .924072265625
    report = evaluate(
        COMPOUND, "S", is_goal, quantile_levels=(0.8164, 0.87988, 0.88, 0.924, 0.925), cvar_level=0.5
    )

    assert [report.quantiles[x].value for x in (0.8164, 0.87988, 0.88, 0.924, 0.925)] == [4.0, 5.0, 6.0, 6.0, 7.0]


# ---------------------------------------------------------------- the loop-costs spec's other hand numbers

LOOP_COSTS_CASES = [
    # p = 1/10 price 1: E[N] = 10; (9/10)^21 = .1094 > .1 >= (9/10)^22 = .0985: p90 = 22 attempts
    pytest.param(loop(1, 1, 9), "S", 10.0, 22.0, id="loop-p-tenth-price-1"),
    # p = 1 with setup 7 and a reset 3 never paid: one try of 2, so mean = p90 = 7 + 2
    pytest.param(
        {"U": Action("setup", 7, (("S", 1),)), "S": Action("try", 2, ((GOAL, 1),))},
        "U",
        9.0,
        9.0,
        id="loop-p-one-setup",
    ),
    # two p = 1/2 stages of price 2: the KA36/KA37 chain doubled: mean 2 * 4, p90 2 * 7
    pytest.param(
        {
            "S1": Action("first", 2, (("S2", 1), ("S1", 1))),
            "S2": Action("second", 2, ((GOAL, 1), ("S2", 1))),
        },
        "S1",
        8.0,
        14.0,
        id="loop-two-stages-price-2",
    ),
    # a deterministic stage of cost 3 before the KA36/KA37 chain: mean 3 + 4, p90 3 + 7
    pytest.param(
        {"D": Action("fixed", 3, (("S1", 1),)), **TWO_STAGES}, "D", 7.0, 10.0, id="loop-fixed-stage-plus-chain"
    ),
    # price 0.25 is a binary fraction, so the grid is exact: the KA36/KA37 chain scaled by 1/4
    pytest.param(
        {
            "S1": Action("first", 0.25, (("S2", 1), ("S1", 1))),
            "S2": Action("second", 0.25, ((GOAL, 1), ("S2", 1))),
        },
        "S1",
        1.0,
        1.75,
        id="loop-two-stages-price-quarter",
    ),
]


@pytest.mark.parametrize(("policy", "start", "mean", "p90"), LOOP_COSTS_CASES)
def test_loop_costs_spec_numbers(policy, start, mean, p90):
    report = evaluate(policy, start, is_goal)

    assert report.grid.exact
    hits(report.mean, mean)
    hits(report.p90, p90)
