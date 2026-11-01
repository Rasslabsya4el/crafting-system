"""The lower and the upper run of the risk DP side by side (ticket #250): the report is the same for any number of workers."""

import pytest
from risk_support import is_goal

from crafting_system.risk import evaluate
from crafting_system.solver import Action

LEVELS = (0.5, 0.9)


def craft():
    """A cheap orb, a spam that ends in the goal or a failure in one use of 20 each, and a restart (R13's shape)."""
    return {
        "S": Action("orb", 0.01, (("A", 1),)),
        "A": Action("spam", 0.1, (("goal", 1), ("A", 18), ("B", 1))),
        "B": Action("restart", 1.0, (("S", 1),)),
    }


def uneven():
    """Costs that are not multiples of one unit, so the ordinary grid is inexact and runs a lower and an upper chain."""
    return {
        "S": Action("a", 0.37, (("T", 1), ("S", 1))),
        "T": Action("b", 1.13, (("goal", 1), ("S", 2))),
    }


@pytest.mark.parametrize("name,options", [("coarse", dict(max_bins=20, max_coarse_bins=2000)), ("ordinary", dict(max_bins=3000))])
def test_the_report_is_equal_for_one_and_two_workers(monkeypatch, name, options):
    policy = craft() if name == "coarse" else uneven()
    monkeypatch.setenv("CRAFTING_WORKERS", "1")
    serial = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, **options)
    monkeypatch.setenv("CRAFTING_WORKERS", "2")
    pooled = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, **options)

    assert pooled == serial
    assert not serial.grid.exact  # both runs happened
