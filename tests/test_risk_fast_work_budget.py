"""A large policy gets a coarser grid instead of a day-long DP; the intervals stay certified (#82)."""

import random

import pytest
from risk_oracle_evaluate import evaluate as old_evaluate
from risk_support import is_goal

from crafting_system.risk import evaluate
from crafting_system.solver import Action

GOAL = "goal"


def layered(rng: random.Random, size: int) -> dict:
    policy = {}
    for i in range(size):
        outcomes = [(i, rng.randint(5, 30)), (i + 1 if i + 1 < size else GOAL, rng.randint(10, 40))]
        if i > 3 and rng.random() < 0.2:
            outcomes.append((rng.randrange(max(0, i - 6), i), rng.randint(1, 12)))
        policy[i] = Action(f"a{i}", rng.uniform(0.9, 3.5), tuple(outcomes))
    return policy


def test_a_small_budget_raises_the_step_and_a_large_one_leaves_it():
    policy = layered(random.Random(1), 40)

    fine = evaluate(policy, 0, is_goal)
    capped = evaluate(policy, 0, is_goal, work_budget=1e5)
    roomy = evaluate(policy, 0, is_goal, work_budget=1e15)

    assert capped.grid.step > fine.grid.step
    assert roomy.grid.step == fine.grid.step
    assert roomy == fine


def test_the_coarse_intervals_bracket_the_fine_answer():
    policy = layered(random.Random(2), 60)
    fine = old_evaluate(policy, 0, is_goal)

    capped = evaluate(policy, 0, is_goal, work_budget=1e5)

    assert capped.grid.step > fine.grid.step
    for level in (0.5, 0.9):
        assert capped.quantiles[level].low <= fine.quantiles[level].value <= capped.quantiles[level].high
    assert capped.cvar.low <= fine.cvar.value <= capped.cvar.high
    assert capped.mean == fine.mean


def test_an_explicit_resolution_ignores_the_budget():
    policy = layered(random.Random(3), 40)

    report = evaluate(policy, 0, is_goal, resolution=0.05, work_budget=1.0)

    assert report.grid.step == 0.05


def test_the_step_never_exceeds_the_smallest_cost():
    policy = layered(random.Random(4), 40)

    report = evaluate(policy, 0, is_goal, work_budget=1e-3)

    assert report.grid.step <= min(a.cost for a in policy.values())


@pytest.mark.parametrize("bad", [0, -1.0, float("nan"), True, "x", None])
def test_a_bad_work_budget_is_rejected(bad):
    with pytest.raises(ValueError, match="work_budget"):
        evaluate(layered(random.Random(5), 5), 0, is_goal, work_budget=bad)
