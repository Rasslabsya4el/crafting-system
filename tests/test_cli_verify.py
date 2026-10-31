"""`--verify`: the policy run on concrete fixture amulets, against the computed mean (ticket #26).

The fixture pool is small, so a sampled click is fast; 2,000 runs keep the test at a few seconds.
The verdict is the mean within five standard errors of the simulated mean (a correct policy fails it
about once in 1.7 million runs, and the seed is fixed), so a per-click error of a few tens of percent
shows; the real-data version of this check is in `test_cli_real.py`.
"""

import dataclasses

import pytest
from cli_support import R12, price_file, read_json
from cli_support import run as run_command
from targets_support import DATA

from crafting_system.cli import make_plan, verify
from crafting_system.cli._verify import MIN_STEPS, Memoized, max_steps_for
from crafting_system.solver import Solution
from crafting_system.targets import load_target

RUNS = 2_000


@pytest.fixture(scope="module")
def plan():
    return make_plan(DATA, load_target(R12, DATA), price_file())


def test_verify_agrees_with_the_computed_mean(plan):
    check = verify(DATA, plan, runs=RUNS, seed=7)

    assert check.agrees and check.reason == ""
    assert check.report.successes == RUNS and check.report.unfinished == 0
    assert check.report.cost.agrees_with(plan.start_price.chaos + plan.mean_remaining)
    assert check.computed_mean == pytest.approx(plan.start_price.chaos + plan.mean_remaining)


def test_verify_says_the_interval_is_a_normal_approximation(tmp_path, capsys):
    code, out = run_command(tmp_path, "--verify", "--runs", str(RUNS), prices=price_file())

    text = capsys.readouterr().out
    assert code == 0
    assert f"Verification by simulation ({RUNS:,} runs" in text
    assert "(normal approximation)" in text and "AGREES with the computed mean" in text
    simulated = read_json(out)["verification"]
    assert simulated["agrees"] is True and simulated["runs"] == RUNS
    assert simulated["interval"] == "95%, normal approximation"
    mean = simulated["simulated_mean_cost"]
    assert mean["low"] < mean["value"] < mean["high"]
    assert abs(mean["value"] - simulated["computed_mean_cost"]) <= 5 * mean["standard_error"]


def test_a_wrong_computed_mean_does_not_agree(plan):
    wrong = Solution(
        values={state: value * 1.3 for state, value in plan.solution.values.items()},
        policy=plan.solution.policy,
        error_bound=0.0,
    )

    check = verify(DATA, dataclasses.replace(plan, solution=wrong), runs=RUNS, seed=7)

    assert not check.agrees
    assert "standard errors" in check.reason


def test_the_command_exits_with_2_when_the_simulation_does_not_agree(tmp_path, monkeypatch, capsys):
    from crafting_system.cli import _main

    real_verify = _main.verify

    def lying(data, plan, **fields):
        wrong = Solution({s: v * 1.3 for s, v in plan.solution.values.items()}, plan.solution.policy, 0.0)
        return real_verify(data, dataclasses.replace(plan, solution=wrong), **fields)

    monkeypatch.setattr(_main, "verify", lying)

    code, out = run_command(tmp_path, "--verify", "--runs", str(RUNS), prices=price_file())

    assert code == 2
    assert "DOES NOT AGREE" in capsys.readouterr().out
    assert read_json(out)["verification"]["agrees"] is False


def test_the_step_limit_is_low_but_far_above_the_computed_clicks(plan):
    limit = max_steps_for(plan)
    clicks = plan.mean_remaining / min(plan.offer_of(a).cost for a in plan.policy.values())

    assert MIN_STEPS <= limit < 100_000
    assert limit >= 20 * clicks


def test_a_step_limit_that_cuts_runs_is_not_an_agreement(plan, monkeypatch):
    from crafting_system.cli import _verify

    monkeypatch.setattr(_verify, "max_steps_for", lambda _: 3)

    check = verify(DATA, plan, runs=200, seed=7)

    assert not check.agrees and "hit the step limit of 3" in check.reason


def test_the_memoized_action_builds_its_outcomes_once_per_kind_of_item(plan):
    class Counting:
        def __init__(self):
            self.calls = 0

        def outcomes(self, data, item):
            self.calls += 1
            return object()

    action = Counting()
    memo = Memoized(action)
    start = plan.target.start_item

    first = memo.outcomes(DATA, start)
    again = memo.outcomes(DATA, start)

    assert first is again and action.calls == 1


BIG_RUNS = 20_000


def test_a_mean_six_percent_off_is_rejected_when_the_run_can_see_it():
    # No start price, so the whole mean is the cost of the clicks and a 6% error in it is a 6% error per click.
    # A craft's cost is as spread as its mean, so the standard error is about mean / sqrt(runs) and five of
    # them are 3.5% at 20,000 runs. The default 10,000 runs see errors above about 5%, not smaller ones:
    # the output says so (`detectable_error`).
    exact = make_plan(DATA, load_target(R12, DATA), price_file(), start_price=0.0)
    off = Solution({s: v * 1.06 for s, v in exact.solution.values.items()}, exact.solution.policy, 0.0)

    wrong = verify(DATA, dataclasses.replace(exact, solution=off), runs=BIG_RUNS, seed=3)

    assert wrong.report.cost.agrees_with(exact.mean_remaining)  # the simulation itself is right
    assert not wrong.agrees and "standard errors" in wrong.reason
    assert 0.03 < wrong.detectable_error < 0.05  # it saw 6% and says it could not see much less


def test_the_verify_output_names_the_smallest_error_the_run_can_detect(plan, tmp_path, capsys):
    code, out = run_command(tmp_path, "--verify", "--runs", str(RUNS), prices=price_file())

    assert code == 0
    assert "a mean off by more than" in capsys.readouterr().out
    assert 0.0 < read_json(out)["verification"]["detectable_relative_error"] < 1.0
