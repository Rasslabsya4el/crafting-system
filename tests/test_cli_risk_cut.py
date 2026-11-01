"""The risk run of a policy whose cost scale is far above its cheapest action (ticket #66, follow-up #190).

The budget grid cannot step over the cheapest action, so it covers `RISK_BINS` times that cost. A policy whose mean is
beyond that gets its mean and odds at once and its quantiles and CVaR unresolved, not after minutes of grid.
"""

import math

import pytest

from crafting_system.cli import _plan
from crafting_system.cli._report import UNRESOLVED, _quantile_text, unresolved
from crafting_system.cli._plan import evaluate_risk
from crafting_system.solver import Action, Outcome

GOAL = "goal"


def repeat_until_success(cost: float, odds: int) -> dict:
    """One state, one action of `cost` that ends in the goal once in `odds` uses."""
    return {"start": Action("use", cost, (Outcome("start", odds - 1), Outcome(GOAL, 1)))}


def test_a_policy_within_the_grid_gets_its_quantiles():
    policy = repeat_until_success(1.0, 4)

    risk = evaluate_risk(policy, "start", lambda s: s == GOAL, mean=4.0)

    assert risk.mean.value == pytest.approx(4.0)
    assert math.isfinite(risk.p90.value)
    assert not unresolved(risk, risk.p90)


def test_a_policy_far_above_its_cheapest_action_gets_exact_odds_and_mean_and_unresolved_quantiles(monkeypatch):
    monkeypatch.setattr(_plan, "RISK_BINS", 2_000)  # the real figure is 200,000: 0.001 x 2,000 x 2 = 4 < 1,000
    used = []
    real = _plan.evaluate
    monkeypatch.setattr(_plan, "evaluate", lambda *args, **kwargs: used.append(kwargs["max_bins"]) or real(*args, **kwargs))
    policy = repeat_until_success(0.001, 1_000_000)

    risk = evaluate_risk(policy, "start", lambda s: s == GOAL, mean=1_000.0)

    assert used == [_plan.UNRESOLVED_BINS]  # the grid was cut
    assert risk.success_probability.value == 1.0
    assert risk.mean.value == pytest.approx(1_000.0, rel=1e-9)
    assert math.isinf(risk.p90.value) and math.isinf(risk.cvar.value)
    assert unresolved(risk, risk.p90)
    assert _quantile_text(risk, risk.p90, 10.0, 300.0) == UNRESOLVED


def test_an_infinite_quantile_of_a_policy_that_can_fail_is_not_called_unresolved():
    policy = {"start": Action("use", 1.0, (Outcome("start", 1), Outcome("dead", 1))), "dead": Action("stay", 1.0, (Outcome("dead", 1),))}

    risk = evaluate_risk(policy, "start", lambda s: s == GOAL, mean=math.inf)

    assert risk.success_probability.value < 1.0
    assert not unresolved(risk, risk.p90)


def test_a_mean_just_above_the_grid_is_not_cut_while_the_median_can_still_be_found():
    policy = repeat_until_success(1.0, 240_000)  # the grid covers 200,000; the median is 166,355, the mean 240,000

    risk = evaluate_risk(policy, "start", lambda s: s == GOAL, mean=240_000.0)

    assert math.isfinite(risk.p50.value) and math.isinf(risk.p90.value)
