"""`evaluate` on policies that build second items (ADR-0022, ticket #181).

The reference policy has one donor: the main action costs 2, ends with probability 1/4 and otherwise
retries, and every attempt (the retries included) first builds a donor, a run of its own that costs
3 per try and succeeds with probability 1/3. The donor run is geometric: mean 9, variance 54. The
number of attempts N is geometric with mean 4 and variance 12, an attempt costs X = 2 + donor run
(mean 11, second moment 175, variance 54), so the total cost has mean 44 and second moment
3604: Var = E[N] Var(X) + Var(N) E[X]^2 = 216 + 1452 = 1668.

Quantiles and CVaR are checked against a Monte Carlo of the nested process written here (a recursive
walk that builds the donor afresh before every attempt). Stated tolerances, as in
`test_risk_simulation`: five standard errors on the mean, the quantile and the CVaR.
"""

import math
import random
from fractions import Fraction

import pytest
from risk_oracle_evaluate import evaluate as old_evaluate
from risk_support import Sample

from crafting_system.risk import evaluate
from crafting_system.solver import Action

N = 100_000
LEVELS = (0.1, 0.5, 0.9, 0.99)


def is_goal(state):
    return state == "goal" or state.endswith("done")


def one_donor():
    return {
        "S": Action("make", 2.0, (("goal", 1), ("S", 3)), extra_inputs=("D",)),
        "D": Action("donor", 3.0, (("donor_done", 1), ("D", 2))),
    }


def two_donors():
    """Every attempt builds two copies of the same donor and one of a second kind, itself built from the first."""
    return {
        "S": Action("make", 1.5, (("goal", 1), ("S", 2)), extra_inputs=("D", "D", "E")),
        "D": Action("donor", 3.0, (("donor_done", 1), ("D", 2))),
        "E": Action("other", 1.0, (("E_done", 2), ("E", 1)), extra_inputs=("D",)),
    }


def failing_donor():
    """The donor can run out of tries (a dead end): the policy succeeds with probability below 1."""
    return {
        "S": Action("make", 2.0, (("goal", 1), ("S", 1)), extra_inputs=("D",)),
        "D": Action("donor", 3.0, (("donor_done", 3), ("D", 1), ("dead", 1))),
    }


def cyclic_but_finite():
    """A needs B as input; B ends or goes back to A: an input edge inside a cycle. V_A = 8, V_B = 3."""
    return {
        "A": Action("a", 1.0, (("goal", 1), ("A", 1)), extra_inputs=("B",)),
        "B": Action("b", 1.0, (("donor_done", 3), ("A", 1))),
    }


def supercritical():
    """Every state can finish, but an attempt at A needs two runs of B and half of them come back to A."""
    return {
        "A": Action("a", 1.0, (("goal", 1), ("A", 1)), extra_inputs=("B", "B")),
        "B": Action("b", 1.0, (("donor_done", 1), ("A", 1))),
    }


class Walker:
    """Seeded recursive Monte Carlo of the nested process: shares no code with `risk`."""

    def __init__(self, policy, goal_test, seed):
        self.policy = policy
        self.goal_test = goal_test
        self.rng = random.Random(seed)
        self.cumulative = {}
        for state, action in policy.items():
            total, acc = 0, []
            for target, weight in action.outcomes:
                total += weight
                acc.append((total, target))
            self.cumulative[state] = (acc, total)

    def run(self, state, depth=0):
        total = 0.0
        while not self.goal_test(state):
            action = self.policy.get(state)
            if action is None or depth > 40:
                return math.inf
            total += action.cost
            for y in action.extra_inputs:
                total += self.run(y, depth + 1)
            acc, whole = self.cumulative[state]
            draw = self.rng.random() * whole
            state = next(target for bound, target in acc if draw < bound)
        return total

    def sample(self, start, runs):
        return Sample(sorted(self.run(start) for _ in range(runs)))


def inside(value, estimate, slack=0.0):
    return estimate.low - slack <= value <= estimate.high + slack


def test_hand_policy_has_the_exact_mean_second_moment_and_donor_count():
    report = evaluate(one_donor(), "S", is_goal)

    assert report.success_probability == (1.0, 1.0, 1.0)
    assert report.mean.value == pytest.approx(44.0, rel=1e-12)
    assert inside(44.0, report.mean)
    second = report.variance.value + report.mean.value**2
    assert second == pytest.approx(3604.0, rel=1e-12)
    assert inside(1668.0, report.variance)
    assert report.variance.high - report.variance.low < 1e-9 * 1668.0
    uses = report.input_runs["D"]
    assert uses.value == pytest.approx(4.0, rel=1e-12)
    assert inside(4.0, uses)


def test_the_donor_alone_is_geometric_with_mean_9_and_variance_54():
    report = evaluate(one_donor(), "D", is_goal)

    assert report.mean.value == pytest.approx(9.0, rel=1e-12)
    assert report.variance.value == pytest.approx(54.0, rel=1e-12)
    assert report.input_runs == {}


def test_two_donors_mean_and_variance_match_the_closed_form():
    report = evaluate(two_donors(), "S", is_goal)

    # donor D: cost 3, ends 1/3: mean 9, variance 54; E: attempts geometric(2/3), each 1 + D
    # E-run cost = sum over N_E ~ Geom(2/3) of (1 + D_i): mean 1.5 * 10 = 15
    d_mean, d_var = Fraction(9), Fraction(54)
    x_e_mean, x_e_var = 1 + d_mean, d_var
    n_mean, n_var = Fraction(3, 2), Fraction(1, 3) / Fraction(4, 9)
    e_mean = n_mean * x_e_mean
    e_var = n_mean * x_e_var + n_var * x_e_mean**2
    # attempt at S: 1.5 + D + D + E, independent
    x_mean = Fraction(3, 2) + 2 * d_mean + e_mean
    x_var = 2 * d_var + e_var
    attempts_mean, attempts_var = Fraction(3), Fraction(6)  # geometric, success 1/3
    mean = attempts_mean * x_mean
    variance = attempts_mean * x_var + attempts_var * x_mean**2

    assert report.mean.value == pytest.approx(float(mean), rel=1e-12)
    assert report.variance.value == pytest.approx(float(variance), rel=1e-11)
    assert report.input_runs["D"].value == pytest.approx(float(attempts_mean * (2 + n_mean)), rel=1e-12)
    assert report.input_runs["E"].value == pytest.approx(float(attempts_mean), rel=1e-12)


@pytest.mark.parametrize("name", ["one_donor", "two_donors"])
def test_quantiles_cvar_and_mean_match_the_nested_monte_carlo(name):
    policy = {"one_donor": one_donor, "two_donors": two_donors}[name]()
    report = evaluate(policy, "S", is_goal, quantile_levels=LEVELS, cvar_level=0.9)
    sample = Walker(policy, is_goal, seed=181).sample("S", N)

    assert abs(sample.mean() - report.mean.value) <= 5 * sample.mean_standard_error()
    for level in LEVELS:
        estimate = report.quantiles[level]
        slack = 5 * math.sqrt(level * (1 - level) / N)
        assert sample.cdf_at(estimate.high) >= level - slack
        assert sample.cdf_below(estimate.low) <= level + slack
    cvar_slack = 5 * sample.tail_mean_standard_error(0.9)
    assert report.cvar.low - cvar_slack <= sample.tail_mean(0.9) <= report.cvar.high + cvar_slack


def test_a_donor_that_can_fail_gives_a_success_bracket_and_infinite_moments():
    policy = failing_donor()
    report = evaluate(policy, "S", is_goal)
    sample = Walker(policy, is_goal, seed=7).sample("S", N)

    # a donor try ends with 3/5, retries with 1/5, dies with 1/5: it succeeds with 3/4;
    # s = 3/4 (1/2 + s/2) gives s = 3/5
    assert math.isinf(report.mean.value)
    assert math.isinf(report.cvar.value)
    success = report.success_probability
    assert success.low <= 0.6 <= success.high
    assert success.high - success.low < 1e-6
    slack = 5 * sample.success_standard_error()
    assert success.low - slack <= sample.success() <= success.high + slack
    assert report.input_runs == {}


def test_inputs_in_a_cycle_keep_exact_moments_and_report_the_quantiles_unresolved():
    report = evaluate(cyclic_but_finite(), "A", is_goal)

    assert report.mean.value == pytest.approx(8.0, rel=1e-12)
    assert inside(8.0, report.mean)
    assert report.input_runs["B"].value == pytest.approx(4.0, rel=1e-12)
    assert report.success_probability == (1.0, 1.0, 1.0)
    for estimate in report.quantiles.values():
        assert math.isinf(estimate.high) and estimate.low >= 1.0
    assert math.isinf(report.cvar.high)
    assert report.cvar.low <= 8.0 * (1 + 1e-12)


def test_a_supercritical_policy_has_no_finite_mean():
    report = evaluate(supercritical(), "A", is_goal)

    assert math.isinf(report.mean.value) and math.isinf(report.variance.value)
    assert math.isinf(report.cvar.value)
    assert report.success_probability.low == 0.0 and report.success_probability.high == 1.0


def test_a_start_whose_input_cannot_be_built_cannot_finish():
    policy = {"S": Action("make", 1.0, (("goal", 1),), extra_inputs=("nowhere",))}

    report = evaluate(policy, "S", is_goal)

    assert report.success_probability == (0.0, 0.0, 0.0)
    assert math.isinf(report.mean.value)
    assert all(math.isinf(q.value) for q in report.quantiles.values())


def test_an_input_that_is_already_a_goal_costs_nothing():
    policy = {"S": Action("make", 2.0, (("goal", 1), ("S", 3)), extra_inputs=("goal",))}

    report = evaluate(policy, "S", is_goal)

    assert report.mean.value == pytest.approx(8.0, rel=1e-12)
    assert report.variance.value == pytest.approx(2.0**2 * 12.0, rel=1e-12)
    assert report.input_runs["goal"].value == pytest.approx(4.0, rel=1e-12)


@pytest.mark.parametrize("seed", range(6))
def test_policies_without_inputs_are_unchanged(seed):
    rng = random.Random(seed)
    n = rng.randint(2, 6)
    policy = {}
    for i in range(n):
        outcomes = [("goal", rng.randint(1, 3))]
        outcomes += [(rng.randrange(n), rng.randint(1, 3)) for _ in range(rng.randint(1, 3))]
        policy[i] = Action("a", rng.choice([1.0, 1.5, 2.0, 2.5]), tuple(outcomes))
    goal_test = lambda state: state == "goal"  # noqa: E731

    new = evaluate(policy, 0, goal_test)
    old = old_evaluate(policy, 0, goal_test)

    assert new == old
    assert new.input_runs == {}


def test_many_copies_of_one_donor_stay_cheap():
    policy = {
        "S": Action("make", 2.0, (("goal", 1), ("S", 3)), extra_inputs=("D",) * 12),
        "D": Action("donor", 3.0, (("donor_done", 1), ("D", 2))),
    }

    report = evaluate(policy, "S", is_goal)

    assert report.mean.value == pytest.approx(4 * (2 + 12 * 9), rel=1e-12)
    assert report.p50.low <= report.mean.value <= report.p90.high
    assert report.input_runs["D"].value == pytest.approx(4 * 12, rel=1e-12)


# --- ticket #506: the cause of a quantile that is not computed is its own (M7), and two limits that change no answer (C26, C27) -------------


def improper_in_a_cycle():
    """A needs B and B goes back to A (inputs in a cycle), and A can also step to C, which only loops on itself: C can never finish."""
    return {
        "A": Action("a", 1.0, (("goal", 1), ("C", 1)), extra_inputs=("B",)),
        "B": Action("b", 1.0, (("donor_done", 1), ("A", 1))),
        "C": Action("c", 1.0, (("C", 1),)),
    }


def test_m7_a_policy_that_starts_more_runs_than_it_finishes_says_so_and_a_cycle_of_inputs_says_that():
    from crafting_system.cli._limits import limit_text, risk_limits, unresolved
    from crafting_system.cli._report import NOT_COMPUTED, _quantile_text

    for policy, start, cause in ((supercritical(), "A", "subcritical"), (cyclic_but_finite(), "A", "unordered"), (improper_in_a_cycle(), "A", "improper")):
        report = evaluate(policy, start, is_goal)
        (limit,) = risk_limits(report)

        assert report.grid.cause == cause
        assert not unresolved(report, report.p90)  # not "the grid could not reach it": the grid is not the cause
        assert _quantile_text(report, report.p90, 0.0, 1.0) == NOT_COMPUTED[cause]
        assert "#190" not in NOT_COMPUTED[cause] and "#190" not in limit_text(limit)
    assert risk_limits(evaluate(one_donor(), "S", is_goal)) == ()  # an ordinary policy with inputs says nothing


def test_m7_the_guarantee_of_each_cause_is_true_of_the_report_it_is_attached_to():
    """`unordered` means a proper policy: its mean and variance are exact. An improper policy has an infinite mean and a success chance between 0 and 1."""
    from crafting_system.cli._limits import risk_limits

    unordered = evaluate(cyclic_but_finite(), "A", is_goal)
    improper = evaluate(improper_in_a_cycle(), "A", is_goal)

    (said,) = risk_limits(unordered)
    assert said.guarantee == "The success chance, the mean cost and the variance are exact."
    assert unordered.success_probability.value == 1.0 and math.isfinite(unordered.mean.value) and math.isfinite(unordered.variance.value)
    (denied,) = risk_limits(improper)
    assert "cannot finish" in denied.why and "exact" not in denied.guarantee and denied.guarantee.startswith("Only the bracket")
    assert improper.success_probability.low == 0.0 and improper.success_probability.high == 1.0 and math.isinf(improper.mean.value)
    assert denied.what == "Not computed: the mean cost, the variance, the median cost, the cost 9 runs in 10 stay under, and the average of the worst tenth"


def test_m7_a_quantile_the_grid_did_compute_is_shown_and_only_an_infinite_one_gets_the_cause():
    import dataclasses

    from crafting_system.cli._limits import risk_limits
    from crafting_system.cli._report import NOT_COMPUTED, _quantile_text
    from crafting_system.risk import Estimate

    report = evaluate(one_donor(), "S", is_goal)
    graded = dataclasses.replace(
        report, quantiles={0.5: Estimate(40.0, 39.0, 41.0), 0.9: Estimate(math.inf, 1.0, math.inf)}, mean=Estimate(math.inf, math.inf, math.inf),
        grid=dataclasses.replace(report.grid, cause="subcritical"),
    )

    assert _quantile_text(graded, graded.p50, 0.0, 1.0).startswith("40.00 Chaos")
    assert _quantile_text(graded, graded.p90, 0.0, 1.0) == NOT_COMPUTED["subcritical"]
    (limit,) = risk_limits(graded)
    assert limit.what == "Not computed: the mean cost and the cost 9 runs in 10 stay under"  # p50 was computed and is not claimed lost


def test_c26_the_mass_the_nested_run_drops_is_counted_and_is_far_below_the_rounding_allowance():
    import numpy as np

    from crafting_system.risk import _nested

    values = np.array([1e-200, 0.5, 1e-160, 1e-10])
    dropped = _nested._clean(values)

    assert dropped == pytest.approx(1e-160, rel=1e-9, abs=0.0) and list(values) == [0.0, 0.5, 0.0, 1e-10]  # what it zeroes it returns, to be counted as unresolved
    assert _nested.TINY * 200_000 * 1_000 < 1e-100  # even every cell of a grid of 200,000 bins over 1,000 states cannot reach what a float rounds away
    assert evaluate(one_donor(), "S", is_goal).grid.rounding > 1e-100


def test_c27_the_packed_moments_are_the_same_numbers_as_the_object_ones(monkeypatch):
    from crafting_system.risk import _moments

    policy = {"s": Action("try", 2.0, (("goal", 1), ("t", 2))), "t": Action("again", 3.0, (("goal", 1), ("s", 3)))}  # no inputs: the moments come from `_moments`
    plain = evaluate(policy, "s", is_goal)
    packed_calls = []
    real = _moments.solve_packed_model
    monkeypatch.setattr(_moments, "solve_packed_model", lambda *args, **options: packed_calls.append(1) or real(*args, **options))
    assert not packed_calls and evaluate(policy, "s", is_goal) == plain
    monkeypatch.setattr(_moments, "PACKED_FROM_EDGES", 0)
    packed = evaluate(policy, "s", is_goal)

    assert packed_calls  # the packed arrays were used
    assert packed.mean.value == pytest.approx(plain.mean.value, rel=1e-9) and packed.variance.value == pytest.approx(plain.variance.value, rel=1e-9)
    assert packed.mean.low <= plain.mean.value <= packed.mean.high  # certified either way
