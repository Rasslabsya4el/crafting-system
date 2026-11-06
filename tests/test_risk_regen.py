"""`evaluate(regenerative=True)`: the cost of a craft that starts over, found one attempt at a time (`risk._regen`, ticket #70).

A craft that returns to its first state is a sum of independent attempts, so the budget DP runs on one attempt and the renewal equation
adds them up. On a grid where every cost is a whole multiple of the step the result is the exact distribution, the very numbers of the
ordinary DP; where some are not, the lower and the upper chain bracket it.
"""

import math

import pytest

from crafting_system.risk import evaluate
from crafting_system.solver import Action, Outcome

GOAL = "goal"


def policy(middle: float = 4.5):
    """Start pays 3 and ends, goes on to `t`, or fails to `bad` (a restart that pays 6); `t` pays `middle`, ends, fails, or starts over."""
    return {
        "s": Action("try", 3.0, (Outcome(GOAL, 1), Outcome("t", 2), Outcome("bad", 3))),
        "t": Action("next", middle, (Outcome(GOAL, 1), Outcome("bad", 1), Outcome("s", 1))),
        "bad": Action("restart", 6.0, (Outcome("s", 1),)),
    }


def risk(chain, **extra):
    return evaluate(chain, "s", lambda state: state == GOAL, **extra)


def narrow(**extra):
    """The ordinary grid is cut at 10 bins, far below the 90th percentile, so only the attempt-wise run can resolve it."""
    return risk(policy(extra.pop("middle", 4.5)), max_bins=10, max_coarse_bins=200_000, **extra)


def test_the_ordinary_grid_cut_short_leaves_the_levels_unresolved():
    assert math.isinf(narrow().p90.high)


def test_on_a_grid_where_every_cost_is_whole_the_attempt_wise_run_gives_the_ordinary_numbers():
    exact = risk(policy(), max_bins=200_000)
    found = narrow(regenerative=True)

    assert found.mean.value == pytest.approx(exact.mean.value, rel=1e-12)
    for level in (0.5, 0.9):
        assert found.quantiles[level].low == pytest.approx(exact.quantiles[level].low, rel=1e-9)
        assert found.quantiles[level].high == pytest.approx(exact.quantiles[level].high, rel=1e-9)
    assert found.cvar.low == pytest.approx(exact.cvar.low, rel=1e-6) and found.cvar.high == pytest.approx(exact.cvar.high, rel=1e-6)


def test_where_a_cost_is_not_whole_the_lower_and_the_upper_chain_bracket_the_ordinary_numbers():
    exact = risk(policy(middle=4.6), max_bins=2_000_000)
    found = narrow(regenerative=True, middle=4.6)

    for level in (0.5, 0.9):
        assert found.quantiles[level].low <= exact.quantiles[level].value <= found.quantiles[level].high
        assert math.isfinite(found.quantiles[level].high)
    assert found.cvar.low <= exact.cvar.value <= found.cvar.high


def test_a_chain_that_never_starts_over_is_left_to_the_other_grids():
    easy = {"a": Action("go", 3.0, (Outcome(GOAL, 1), Outcome("b", 1))), "b": Action("go", 4.5, (Outcome(GOAL, 1), Outcome("b", 1)))}

    found = evaluate(easy, "a", lambda state: state == GOAL, max_bins=2, max_coarse_bins=3, regenerative=True)

    assert math.isinf(found.p90.high)  # not attempt-wise (no edge into the start), and the 2-bin cap leaves it unresolved


def test_c25_an_attempt_wise_run_refused_for_the_mass_it_cuts_is_written_and_a_resolved_one_is_not(monkeypatch):
    from crafting_system.cli._limits import risk_limits, limit_text
    from crafting_system.risk import _regen

    assert not narrow(regenerative=True).grid.gave_up
    monkeypatch.setattr(_regen, "MAX_MISSING", -1.0)  # any cut attempt mass is now too much
    refused = narrow(regenerative=True)

    (said,) = refused.grid.gave_up
    assert said.startswith("the attempts cut short hold ") and "more than the -1e+00 the quicker method allows" in said
    assert math.isinf(refused.p90.high)  # the ordinary grid ran instead and could not reach it
    (limit,) = risk_limits(refused)
    assert limit.what == "Not computed: p90, CVaR" and said in limit.reason() and "the faster methods gave up first" in limit_text(limit)
