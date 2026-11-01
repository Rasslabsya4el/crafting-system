"""Risk quantiles of a policy with free actions (ticket #349, `risk._free`).

The planner prices an action that consumes nothing at an epsilon (1e-6 of the cheapest paid offer), so the budget grid stepped by the epsilon and
the 0.9 quantile and the CVaR of a veil plan came back unresolved. `evaluate(free_cost=...)` counts those actions apart from the grid.

The oracles: the exact distribution of a veil loop as `Fraction`s; the same policy with a large "epsilon" on its own exact unit grid (where the
epsilon is a whole bin); and the seeded test-only Monte Carlo of `risk_support`, which shares no code with `risk`.
"""

import math
from fractions import Fraction

import pytest
from risk_support import is_goal, simulate

from crafting_system.risk import _free, _fold, evaluate
from crafting_system.solver import Action

LEVELS = (0.5, 0.9, 0.99)
CVAR_LEVEL = 0.9


def veil_loop(veil=5.0, free=5e-6):
    """The shape of the planner's veil loop: unveil (free), then a pick (free) that ends it 10 times in 13, else a veil (paid) and again."""
    return {
        "placeholder": Action("unveil", free, (("wanted", 10), ("junk", 3))),
        "wanted": Action("pick wanted", free, (("goal", 1),)),
        "junk": Action("pick junk", free, (("veiled", 1),)),
        "veiled": Action("veil", veil, (("placeholder", 1),)),
    }


def veil_loop_exact(veil, free, depth=90):
    """`[(cost, probability)]` of the loop: m failed tries cost m veil + (2 + 2 m) free, with probability (10/13) (3/13)^m."""
    veil, free = Fraction(veil), Fraction(free)
    return [((veil + 2 * free) * m + 2 * free, Fraction(10, 13) * Fraction(3, 13) ** m) for m in range(depth)]


def exact_quantile(points, level):
    level = Fraction(repr(level))
    running = Fraction(0)
    for cost, probability in sorted(points):
        running += probability
        if running >= level:
            return cost
    raise AssertionError("depth too small")


def exact_cvar(points, level):
    """The mean of the worst `1 - level` share (a Fraction, the probability beyond `depth` is below 1e-50 and ignored)."""
    share = 1 - Fraction(repr(level))
    left, total = share, Fraction(0)
    for cost, probability in sorted(points, reverse=True):
        take = min(left, probability)
        total += take * cost
        left -= take
        if left == 0:
            break
    return total / share


def contains(estimate, truth, slack=1e-9):
    truth = float(truth)
    return estimate.low - slack * abs(truth) <= truth <= estimate.high + slack * abs(truth)


# --- the veil loop: resolved, and equal to the exact distribution -----------------------------------------------------------


@pytest.mark.parametrize("veil", [5.0, 500.0, 50_000.0])
def test_the_quantiles_and_the_cvar_of_a_veil_loop_resolve_and_contain_the_exact_values(veil):
    free = veil * 1e-6
    policy = veil_loop(veil, free)
    points = veil_loop_exact(veil, free)

    report = evaluate(policy, "placeholder", is_goal, quantile_levels=LEVELS, cvar_level=CVAR_LEVEL, free_cost=free)

    for level in LEVELS:
        estimate = report.quantiles[level]
        assert math.isfinite(estimate.high), level
        assert contains(estimate, exact_quantile(points, level)), (level, estimate)
        assert estimate.high - estimate.low == pytest.approx(report.grid.free_allowance)  # the paid grid is exact: the width is the epsilon's allowance
    assert math.isfinite(report.cvar.high) and contains(report.cvar, exact_cvar(points, CVAR_LEVEL))
    assert report.cvar.high - report.cvar.low < 1e-3 * report.cvar.value
    assert report.grid.step == veil and not report.grid.exact
    assert 0.0 < report.grid.free_allowance < 1e-3 * veil and report.grid.free_tail > 0.0  # the bound of the epsilon is stated
    assert report.success_probability == (1.0, 1.0, 1.0)


def test_the_mean_and_the_variance_of_a_veil_loop_are_those_of_the_real_costs():
    policy = veil_loop(5.0, 5e-6)
    points = veil_loop_exact(5.0, 5e-6)
    mean = sum(c * p for c, p in points)

    report = evaluate(policy, "placeholder", is_goal, free_cost=5e-6)

    assert contains(report.mean, mean) and report.mean.value == pytest.approx(float(mean), rel=1e-12)
    assert report.variance.value == pytest.approx(float(sum(c * c * p for c, p in points) - mean * mean), rel=1e-9)


def test_without_the_free_cost_the_same_loop_stays_unresolved_as_on_main():
    report = evaluate(veil_loop(5.0, 5e-6), "placeholder", is_goal)

    assert math.isinf(report.p90.high) and math.isinf(report.cvar.high)  # the step is the epsilon: 200,000 bins cover one Chaos


def test_a_median_below_the_first_veil_is_the_epsilon_alone_and_stays_inside_its_allowance():
    report = evaluate(veil_loop(5.0, 5e-6), "placeholder", is_goal, free_cost=5e-6)

    assert report.p50.low == 0.0 and report.p50.high == pytest.approx(report.grid.free_allowance)
    assert report.p50.low <= 2 * 5e-6 <= report.p50.high  # the exact median: two free steps


def test_an_explicit_resolution_is_used_for_the_paying_costs():
    report = evaluate(veil_loop(5.0, 5e-6), "placeholder", is_goal, free_cost=5e-6, resolution=1.25)

    assert report.grid.step == 1.25 and math.isfinite(report.p90.high)
    assert contains(report.p90, exact_quantile(veil_loop_exact(5.0, 5e-6), 0.9))


def test_an_explicit_resolution_above_the_cheapest_paying_cost_is_refused():
    with pytest.raises(ValueError, match="exceeds the smallest cost"):
        evaluate(veil_loop(5.0, 5e-6), "placeholder", is_goal, free_cost=5e-6, resolution=5.5)


# --- the same policy with a big epsilon on its own exact grid ---------------------------------------------------------------


def with_a_free_loop(free):
    """A free state that can loop on itself (a component of its own), reached from a paid state and from the start; the paid costs are 1 and 2."""
    return {
        "start": Action("free start", free, (("a", 1), ("start", 1))),
        "a": Action("paid a", 1.0, (("goal", 1), ("f", 2), ("a", 3))),
        "f": Action("free f", free, (("g", 1), ("f", 1), ("b", 1))),
        "g": Action("free g", free, (("f", 1), ("b", 1), ("goal", 1))),
        "b": Action("paid b", 2.0, (("goal", 1), ("a", 3), ("start", 1))),
    }


FREE_POLICIES = {
    "veil loop": (lambda free: veil_loop(1.0, free), "placeholder"),
    "free cycles": (with_a_free_loop, "start"),
}


@pytest.mark.parametrize("name", FREE_POLICIES)
def test_the_free_grid_brackets_what_the_unit_grid_gives_when_the_epsilon_is_a_whole_bin(name):
    build, start = FREE_POLICIES[name]
    free = 0.01
    levels = (0.1, 0.5, 0.9, 0.99)
    exact = evaluate(build(free), start, is_goal, quantile_levels=levels, resolution=free, max_bins=200_000)
    assert exact.grid.exact

    report = evaluate(build(free), start, is_goal, quantile_levels=levels, free_cost=free, max_bins=200_000)

    assert report.grid.free_allowance > 0.0
    for level in levels:
        assert contains(report.quantiles[level], exact.quantiles[level].value), (level, report.quantiles[level], exact.quantiles[level])
        assert report.quantiles[level].high - report.quantiles[level].low <= 2 * report.grid.free_allowance + report.grid.step
    assert contains(report.cvar, exact.cvar.value)
    assert report.mean.value == pytest.approx(exact.mean.value, rel=1e-9)


def test_a_policy_whose_start_is_paid_and_one_whose_start_is_free_both_resolve():
    free = 1e-6
    start_paid = {"s": Action("paid", 2.0, (("f", 1), ("goal", 1))), "f": Action("free", free, (("s", 1), ("goal", 1)))}
    start_free = {"f": Action("free", free, (("s", 1), ("goal", 1))), "s": Action("paid", 2.0, (("f", 1), ("goal", 1)))}

    for policy, start in ((start_paid, "s"), (start_free, "f")):
        report = evaluate(policy, start, is_goal, free_cost=free)
        assert all(math.isfinite(e.high) for e in (report.p50, report.p90, report.cvar)), start
        assert report.grid.step == 2.0


# --- the independent simulator on an inexact grid ---------------------------------------------------------------------------


def irrational_with_free_steps(free=1e-6):
    return {
        "A": Action("a", math.pi, (("goal", 1), ("F", 1), ("A", 1))),
        "F": Action("free", free, (("B", 1),)),
        "B": Action("b", math.e, (("goal", 2), ("A", 1), ("F", 1))),
    }


def test_the_free_grid_agrees_with_direct_simulation_on_an_inexact_grid():
    runs = 200_000
    free = 1e-6
    report = evaluate(irrational_with_free_steps(free), "A", is_goal, quantile_levels=(0.1, 0.5, 0.9, 0.99), free_cost=free)
    sample = simulate(irrational_with_free_steps(free), "A", is_goal, runs=runs, seed=7)

    assert not report.grid.exact and report.grid.free_allowance > 0.0
    assert abs(sample.mean() - report.mean.value) <= 5 * sample.mean_standard_error()
    for level in (0.1, 0.5, 0.9, 0.99):
        slack = 5 * math.sqrt(level * (1 - level) / runs)
        estimate = report.quantiles[level]
        assert math.isfinite(estimate.high)
        assert sample.cdf_at(estimate.high) >= level - slack
        assert sample.cdf_below(estimate.low) <= level + slack
    slack = 5 * sample.tail_mean_standard_error(CVAR_LEVEL)
    assert report.cvar.low - slack <= sample.tail_mean(CVAR_LEVEL) <= report.cvar.high + slack


def test_the_veil_loop_agrees_with_direct_simulation():
    runs = 200_000
    free = 5e-6
    report = evaluate(veil_loop(5.0, free), "placeholder", is_goal, quantile_levels=(0.5, 0.9, 0.99), free_cost=free)
    sample = simulate(veil_loop(5.0, free), "placeholder", is_goal, runs=runs, seed=11)

    assert abs(sample.mean() - report.mean.value) <= 5 * sample.mean_standard_error()
    for level in (0.5, 0.9, 0.99):
        slack = 5 * math.sqrt(level * (1 - level) / runs)
        assert sample.cdf_at(report.quantiles[level].high) >= level - slack
        assert sample.cdf_below(report.quantiles[level].low) <= level + slack
    slack = 5 * sample.tail_mean_standard_error(CVAR_LEVEL)
    assert report.cvar.low - slack <= sample.tail_mean(CVAR_LEVEL) <= report.cvar.high + slack


# --- when the free grid cannot be built the ordinary one runs as before ---------------------------------------------------------


def same(left, right):
    return repr(left) == repr(right)


def test_a_free_component_too_large_to_fold_falls_back_to_the_ordinary_grid(monkeypatch):
    monkeypatch.setattr(_fold, "FOLD_LIMIT", 1)
    policy = with_a_free_loop(1e-6)

    report = evaluate(policy, "start", is_goal, free_cost=1e-6, max_bins=5_000)

    assert same(report, evaluate(policy, "start", is_goal, max_bins=5_000))
    assert report.grid.free_allowance == 0.0


def test_a_count_of_free_visits_that_does_not_settle_falls_back(monkeypatch):
    monkeypatch.setattr(_free, "COUNT_BINS", 3)
    policy = veil_loop(5.0, 5e-6)

    report = evaluate(policy, "placeholder", is_goal, free_cost=5e-6, max_bins=5_000)

    assert same(report, evaluate(policy, "placeholder", is_goal, max_bins=5_000))


def test_the_fallback_runs_at_the_fallback_bins_the_caller_asked_for(monkeypatch):
    monkeypatch.setattr(_free, "COUNT_BINS", 3)
    policy = veil_loop(5.0, 5e-6)

    report = evaluate(policy, "placeholder", is_goal, free_cost=5e-6, max_bins=150_000, free_fallback_bins=40)

    assert same(report, evaluate(policy, "placeholder", is_goal, max_bins=40))


def test_a_level_the_free_grid_does_not_reach_is_left_to_the_ordinary_grid():
    policy = veil_loop(5.0, 5e-6)

    levels = (0.5, 0.99)

    report = evaluate(policy, "placeholder", is_goal, quantile_levels=levels, free_cost=5e-6, max_bins=1)  # one bin of 5 Chaos: p99 is out of reach

    assert same(report, evaluate(policy, "placeholder", is_goal, quantile_levels=levels, max_bins=1))


def test_a_policy_of_free_actions_alone_has_no_paying_grid_and_falls_back():
    policy = {"s": Action("free", 1e-6, (("goal", 1), ("s", 1)))}

    assert same(evaluate(policy, "s", is_goal, free_cost=1e-6), evaluate(policy, "s", is_goal))


def test_a_free_cost_no_action_has_changes_nothing():
    policy = veil_loop(5.0, 5e-6)

    assert same(evaluate(policy, "placeholder", is_goal, free_cost=1e-9), evaluate(policy, "placeholder", is_goal))


def test_an_improper_policy_and_a_policy_with_inputs_keep_the_ordinary_grid():
    improper = {"s": Action("free", 1e-6, (("s", 1), ("goal", 1), ("dead", 1))), "dead": Action("stay", 1.0, (("dead", 1),))}
    inputs = {
        "s": Action("craft", 2.0, (("s", 1), ("goal", 1)), extra_inputs=("d",)),
        "d": Action("donor", 1e-6, (("d", 1), ("goal", 3))),
    }

    assert same(evaluate(improper, "s", is_goal, free_cost=1e-6), evaluate(improper, "s", is_goal))
    assert same(evaluate(inputs, "s", is_goal, free_cost=1e-6), evaluate(inputs, "s", is_goal))


@pytest.mark.parametrize("bad", [0.0, -1e-6, math.inf, math.nan, True, "1e-6"])
def test_a_bad_free_cost_is_a_value_error(bad):
    with pytest.raises(ValueError, match="free_cost"):
        evaluate(veil_loop(), "placeholder", is_goal, free_cost=bad)


@pytest.mark.parametrize("bad", [0, -3, 2.5, True])
def test_a_bad_fallback_is_a_value_error(bad):
    with pytest.raises(ValueError, match="free_fallback_bins"):
        evaluate(veil_loop(), "placeholder", is_goal, free_cost=5e-6, free_fallback_bins=bad)
