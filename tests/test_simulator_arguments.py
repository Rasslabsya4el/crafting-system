"""`simulate` rejects bad arguments with `ValueError` before doing any work."""

import math

import pytest
from simulator_support import DATA, ITEMS, holds_target

from crafting_system.simulator import simulate


def call(**kwargs):
    arguments = {"runs": 10, "seed": 1}
    arguments.update(kwargs)

    def never(item):
        raise AssertionError("no run should have started")

    return simulate(DATA, never, ITEMS["S"], holds_target, **arguments)


@pytest.mark.parametrize("runs", [0, 1, -5, 2.5, 10.0, True, "10", None])
def test_runs_must_be_an_integer_of_at_least_two(runs):
    with pytest.raises(ValueError, match="runs"):
        call(runs=runs)


@pytest.mark.parametrize("seed", [1.5, True, "7", None])
def test_seed_must_be_an_integer(seed):
    with pytest.raises(ValueError, match="seed"):
        call(seed=seed)


@pytest.mark.parametrize("start_cost", [-1.0, math.nan, math.inf, 10**400, True, "0", None])
def test_start_cost_must_be_finite_and_not_negative(start_cost):
    with pytest.raises(ValueError, match="start_cost"):
        call(start_cost=start_cost)


@pytest.mark.parametrize("max_steps", [0, -1, 2.5, 10.0, True, "5", None])
def test_max_steps_must_be_an_integer_of_at_least_one(max_steps):
    with pytest.raises(ValueError, match="max_steps"):
        call(max_steps=max_steps)


@pytest.mark.parametrize("confidence", [0.0, 1.0, -0.1, 1.5, math.nan, math.inf, True, "0.95", None, 1 - 1e-16, 1e-20])
def test_confidence_must_be_strictly_between_zero_and_one(confidence):
    with pytest.raises(ValueError, match="confidence"):
        call(confidence=confidence)


def test_a_negative_seed_and_zero_start_cost_are_fine():
    report = simulate(DATA, lambda item: None, ITEMS["goal"], holds_target, runs=2, seed=-4, start_cost=0)

    assert report.runs == 2
