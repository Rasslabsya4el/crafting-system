"""`evaluate(coarse_first=True)`: the coarse grid is tried when the ordinary one is not certain to reach the level (ticket #70).

R04 policy chain pays 0.37 Chaos in one state and 50 to 370 in the rest, with a p90 of 157,000: the ordinary grid (a step at most
the cheapest cost, 200,000 bins) covers 73,000 and reports the quantile unresolved, though no bound says it must. The default is
unchanged (a policy whose ordinary grid resolves keeps its results); `coarse_first` only widens when the coarse grid is tried.
"""

import math

import pytest

from crafting_system.risk import evaluate
from crafting_system.solver import Action, Outcome

GOAL = "goal"


def policy():
    """Start pays 50 and finishes with chance 0.002; with chance 0.001 it first passes a state that pays 0.1; else it starts again."""
    return {
        "start": Action("try", 50.0, (Outcome(GOAL, 2), Outcome("cheap", 1), Outcome("start", 997))),
        "cheap": Action("tick", 0.1, (Outcome("start", 1),)),
    }


def levels(**extra):
    return evaluate(policy(), "start", lambda s: s == GOAL, max_bins=200_000, max_coarse_bins=1_000_000, **extra)


def test_the_ordinary_grid_leaves_the_p90_unresolved():
    risk = levels()

    assert math.isinf(risk.p90.high) and risk.success_probability.value == 1.0


def test_coarse_first_resolves_it_within_a_bracket_that_holds_the_true_quantile():
    risk = levels(coarse_first=True)

    # 50 x a geometric number of tries with chance 0.002 (the cheap state adds at most 0.1 per try): the 90th percentile is try 1,151
    assert math.isfinite(risk.p90.high) and risk.p90.low <= 1151 * 50.0 <= risk.p90.high + 1.0
    assert (risk.p90.high - risk.p90.low) / risk.p90.value < 0.05
    assert risk.mean.value == pytest.approx(levels().mean.value, rel=1e-12)


def test_coarse_first_changes_nothing_when_the_ordinary_grid_certainly_reaches():
    easy = {"start": Action("try", 5.0, (Outcome(GOAL, 1), Outcome("start", 1)))}

    plain = evaluate(easy, "start", lambda s: s == GOAL)
    again = evaluate(easy, "start", lambda s: s == GOAL, coarse_first=True)

    assert again == plain
