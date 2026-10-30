"""`evaluate` against direct Monte Carlo simulation of the same policy (ADR-0006, ticket 20).

Every chain is walked N = 200_000 times by the seeded test-only simulator in `risk_support`, which
shares no code with `risk`. Stated tolerances, each at five standard errors so a correct result
fails about once in two million runs (the seeds are fixed, so a run is repeatable):

* mean: |empirical mean - report mean| <= 5 standard errors of the empirical mean;
* success probability: the empirical rate is within 5 standard errors of the reported bracket;
* quantile of level L: P(C <= high) >= L - 5 sqrt(L (1-L) / N) and P(C < low) <= L + 5 sqrt(L (1-L) / N);
* CVaR: the empirical tail mean is within 5 standard errors of the reported interval
  (`Sample.tail_mean_standard_error`);
* variance: within 5% relative (the kurtosis of these chains keeps its standard error near 1%).
"""

import functools
import math

import pytest
from risk_support import simulate

from crafting_system.risk import evaluate
from crafting_system.solver import Action, TabularModel, solve

N = 200_000
LEVELS = (0.1, 0.5, 0.9, 0.99)
CVAR_LEVEL = 0.9


def reaches_goal(state):
    return state.startswith("goal")


def branching_with_loops():
    """Two exits (goal_a, goal_b), a self-loop on B and a back edge from C to B."""
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


def solved_with_competing_actions():
    """The solver picks between a quick risky action and a slow safe one in two states."""
    model = TabularModel(
        ["goal"],
        {
            "S": [
                Action("fast", 1.0, (("goal", 1), ("S", 4), ("T", 1))),
                Action("slow", 3.5, (("goal", 3), ("T", 1))),
            ],
            "T": [
                Action("cheap", 0.5, (("goal", 1), ("T", 6))),
                Action("dear", 4.0, (("goal", 1),)),
            ],
        },
    )
    solution = solve(model, ["S"])
    return solution.policy, solution


def irrational_costs():
    """No common unit: the grid is inexact and the intervals have width."""
    return {
        "A": Action("a", math.pi, (("goal", 1), ("B", 1), ("A", 1))),
        "B": Action("b", math.e, (("goal", 2), ("A", 1))),
    }


def with_a_dead_end():
    return {"A": Action("a", 1.5, (("goal", 3), ("B", 3), ("dead", 4))), "B": Action("b", 0.5, (("goal", 1), ("A", 1)))}


CHAINS = {
    "branching": branching_with_loops,
    "self-loop-and-pair": self_loop_and_two_state_loop,
    "solver-policy": lambda: solved_with_competing_actions()[0],
    "irrational-costs": irrational_costs,
}
START = {"branching": "A", "self-loop-and-pair": "A", "solver-policy": "S", "irrational-costs": "A"}


def goal_test(state):
    return state == "goal" or reaches_goal(state)


@functools.cache
def sample_of(name, seed):
    return simulate(CHAINS[name](), START[name], goal_test, runs=N, seed=seed)


@functools.cache
def report_of(name):
    return evaluate(CHAINS[name](), START[name], goal_test, quantile_levels=LEVELS, cvar_level=CVAR_LEVEL)


names = pytest.mark.parametrize("name", CHAINS)


@names
def test_the_mean_agrees_with_simulation(name):
    sample, report = sample_of(name, 11), report_of(name)

    assert abs(sample.mean() - report.mean.value) <= 5 * sample.mean_standard_error()


@names
def test_the_variance_agrees_with_simulation(name):
    sample, report = sample_of(name, 12), report_of(name)

    assert report.variance.value == pytest.approx(sample.variance(), rel=0.05)


@names
def test_the_quantiles_agree_with_simulation(name):
    sample, report = sample_of(name, 13), report_of(name)

    for level in LEVELS:
        slack = 5 * math.sqrt(level * (1 - level) / N)
        estimate = report.quantiles[level]
        assert sample.cdf_at(estimate.high) >= level - slack
        assert sample.cdf_below(estimate.low) <= level + slack


@names
def test_the_cvar_agrees_with_simulation(name):
    sample, report = sample_of(name, 14), report_of(name)
    slack = 5 * sample.tail_mean_standard_error(CVAR_LEVEL)

    assert report.cvar.low - slack <= sample.tail_mean(CVAR_LEVEL) <= report.cvar.high + slack


def test_the_exact_grid_cases_report_a_point_and_the_irrational_case_an_interval():
    assert report_of("branching").grid.exact
    assert report_of("self-loop-and-pair").grid.exact
    assert not report_of("irrational-costs").grid.exact


def test_the_reported_mean_of_a_solver_policy_is_the_solver_value():
    _, solution = solved_with_competing_actions()
    report = report_of("solver-policy")

    assert report.mean.low <= solution.values["S"] <= report.mean.high
    assert report.mean.value == pytest.approx(solution.values["S"], rel=1e-12)


def test_the_solver_policy_picks_among_competing_actions():
    policy, solution = solved_with_competing_actions()

    assert {state: action.label for state, action in policy.items()} == {"S": "slow", "T": "cheap"}
    assert solution.values["S"] == pytest.approx(4.375)  # "fast" would cost 4.75 from S


def test_a_policy_that_can_fail_agrees_with_simulation_on_success_and_finite_quantiles():
    policy = with_a_dead_end()
    sample = simulate(policy, "A", goal_test, runs=N, seed=15)
    report = evaluate(policy, "A", goal_test, quantile_levels=(0.1, 0.3, 0.5, 0.9))
    slack = 5 * sample.success_standard_error()

    assert report.success_probability.low - slack <= sample.success() <= report.success_probability.high + slack
    assert sample.success() < 0.9
    for level in (0.1, 0.3, 0.5, 0.9):
        estimate = report.quantiles[level]
        band = 5 * math.sqrt(level * (1 - level) / N)
        if math.isinf(estimate.high):
            assert level >= sample.success() - slack
        else:
            assert sample.cdf_at(estimate.high) >= level - band
            assert sample.cdf_below(estimate.low) <= level + band
