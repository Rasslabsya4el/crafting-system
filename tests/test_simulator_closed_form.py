"""`simulate` against closed forms and against `risk.evaluate`, with fake actions (ADR-0019, ticket 25).

The actions here are fakes that return a fixed state with a stated probability, so N = 50_000 runs
are cheap. Stated tolerances, each at five standard errors so a correct result fails about once in
1.7 million runs (the seeds are fixed, so a run is repeatable):

* mean cost: |report mean - exact value| <= 5 * the report's own standard error of the mean;
* mean steps: within 5 sd(steps) / sqrt(N) of the exact value (sd(steps) solved exactly in Fractions too, `steps_mean_and_sd`);
* sd of the cost: within 5% relative (the kurtosis of these distributions keeps its standard error below 1%);
* success rate: the exact value lies in the Wilson interval made at five sigma (`FIVE_SIGMA`);
* quantile of level L: the exact quantile lies in the order-statistic bracket made at five sigma, and
  against `risk`: P(C <= high) >= L - 5 sqrt(L (1-L) / N) and P(C < low) <= L + 5 sqrt(L (1-L) / N).
"""

import math
from bisect import bisect_left, bisect_right
from fractions import Fraction

import pytest
from risk_support import geometric_quantile_steps
from simulator_support import (
    DATA,
    FIVE_SIGMA,
    ITEMS,
    chain_policy,
    holds_target,
    paid,
    reaches_goal,
    solve_chain,
    steps_mean_and_sd,
)

from crafting_system.risk import evaluate
from crafting_system.simulator import simulate
from crafting_system.solver import Action

N = 50_000

# state -> (cost, ((next state, weight), ...)); "goal" and "dead" are absorbing
REPEAT = {"S": (2.5, (("goal", 1), ("S", 4)))}  # p = 1/5
TWO_STATES = {
    "S": (1.5, (("goal", 1), ("T", 2), ("S", 3))),
    "T": (0.5, (("goal", 2), ("S", 1), ("T", 1))),
}
WITH_A_DEAD_END = {
    "S": (1.5, (("goal", 3), ("T", 3), ("dead", 4))),
    "T": (0.5, (("goal", 1), ("S", 1))),
}
REPEAT_PROBABILITIES = {"fifth": Fraction(1, 5), "half": Fraction(1, 2), "tenth": Fraction(1, 10)}


def run(chain, seed, **extra):
    return simulate(DATA, chain_policy(chain), ITEMS["S"], holds_target, runs=N, seed=seed, **extra)


@pytest.mark.parametrize("name", REPEAT_PROBABILITIES)
def test_repeat_until_the_goal_matches_the_geometric_closed_form(name):
    p, cost = REPEAT_PROBABILITIES[name], 2.5
    chain = {"S": (cost, (("goal", p.numerator), ("S", p.denominator - p.numerator)))}

    report = run(chain, seed=101)

    mean, sd = cost / float(p), cost * math.sqrt(1 - p) / float(p)
    assert report.successes == N and report.stopped == 0 and report.unfinished == 0
    assert report.success_rate.value == 1.0 and report.success_rate.high == 1.0
    assert report.cost.agrees_with(mean)
    assert report.cost.standard_error * math.sqrt(N) == pytest.approx(sd, rel=0.05)
    assert report.cost_of_successes == report.cost
    steps_sd = math.sqrt(1 - p) / float(p)
    assert abs(report.mean_steps - 1 / float(p)) <= 5 * steps_sd / math.sqrt(N)


def test_the_cost_of_a_run_is_the_number_of_steps_times_the_cost():
    report = run(REPEAT, seed=102)

    assert all(total / 2.5 == round(total / 2.5) >= 1 for total in report.costs)
    assert sum(report.costs) / 2.5 / N == pytest.approx(report.mean_steps, rel=1e-12)


@pytest.mark.parametrize("level", [0.5, 0.9, 0.99])
def test_the_quantiles_match_the_geometric_quantile(level):
    report = run(REPEAT, seed=103, confidence=FIVE_SIGMA)

    exact = 2.5 * geometric_quantile_steps(Fraction(1, 5), Fraction(repr(level)))
    estimate = report.quantile(level)
    assert estimate.contains(exact)
    assert estimate.low <= estimate.value <= estimate.high


def test_the_success_interval_contains_the_exact_rate_when_runs_can_fail():
    report = run(WITH_A_DEAD_END, seed=104, confidence=FIVE_SIGMA)

    exact = solve_chain(WITH_A_DEAD_END, reaches_goal)["S"]
    assert 0 < exact < 1
    assert report.success_rate.contains(float(exact))
    assert report.successes + report.stopped == N and report.unfinished == 0


def test_the_mean_cost_paid_with_a_dead_end_matches_the_closed_form():
    """Without success rate 1 the mean over all runs is the mean paid, failed runs included."""
    report = run(WITH_A_DEAD_END, seed=105)

    assert report.cost.agrees_with(float(solve_chain(WITH_A_DEAD_END, paid)["S"]))
    steps, steps_sd = steps_mean_and_sd(WITH_A_DEAD_END, "S")
    assert abs(report.mean_steps - steps) <= 5 * steps_sd / math.sqrt(N)


def test_the_two_state_chain_matches_the_closed_form():
    report = run(TWO_STATES, seed=106, confidence=FIVE_SIGMA)

    assert report.success_rate.value == 1.0
    assert report.cost.agrees_with(float(solve_chain(TWO_STATES, paid)["S"]))
    steps, steps_sd = steps_mean_and_sd(TWO_STATES, "S")
    assert abs(report.mean_steps - steps) <= 5 * steps_sd / math.sqrt(N)


def hand_built(chain):
    """The same chain as a solver policy: a dict state -> Action with the same costs and weights."""
    return {state: Action(state, cost, row) for state, (cost, row) in chain.items()}


def is_goal_state(state):
    return state == "goal"


@pytest.mark.parametrize("chain", [TWO_STATES, REPEAT], ids=["two-states", "repeat"])
def test_the_simulator_agrees_with_the_risk_report_on_a_proper_chain(chain):
    report = run(chain, seed=107)
    risk = evaluate(hand_built(chain), "S", is_goal_state, quantile_levels=(0.5, 0.9))

    assert risk.success_probability.value == 1.0
    assert report.success_rate.value == 1.0
    assert risk.mean.low - 5 * report.cost.standard_error <= report.cost.value
    assert report.cost.value <= risk.mean.high + 5 * report.cost.standard_error
    ordered = sorted(report.costs)
    for level, interval in ((0.5, risk.p50), (0.9, risk.p90)):
        slack = 5 * math.sqrt(level * (1 - level) / N)
        assert bisect_right(ordered, interval.high) / N >= level - slack
        assert bisect_left(ordered, interval.low) / N <= level + slack


def test_the_simulator_agrees_with_the_risk_success_probability_on_a_failing_chain():
    report = run(WITH_A_DEAD_END, seed=108, confidence=FIVE_SIGMA)
    risk = evaluate(hand_built({"S": WITH_A_DEAD_END["S"], "T": WITH_A_DEAD_END["T"]}), "S", is_goal_state)

    assert risk.success_probability.low < 1
    slack = 5 * report.success_rate.standard_error
    assert risk.success_probability.low - slack <= report.success_rate.value
    assert report.success_rate.value <= risk.success_probability.high + slack

