"""`simulate`: run a policy on concrete items and measure what it costs and how often it succeeds.

One run starts from `start` with `start_cost` paid. While the item is not a goal, the policy names
a step; the step's cost is added, the action is applied with its sampler and the new item replaces
the old one. A run ends when the item is a goal (success; the goal is checked before the policy is
asked, so a goal item is never acted on, the start included), when the policy returns None
(stopped) or when `max_steps` steps have been taken and the item is still not a goal (unfinished).
The policy is asked about the item after the last step first, so it can still stop the run, which
then counts as stopped. The cost of a run is the total paid until it ends, whatever the ending.

All runs draw from one `random.Random(seed)`, in order, so the same arguments give the same report.

A refusal of the action (`NotApplicableError`, `OutOfScopeError`) is not caught: a policy that
applies an action the game would refuse is a bug in the policy.

This module is the independent check of the abstraction kernel (ADR-0019). It is written from the
documented behaviour of `actions` (`action.outcomes(data, item).sample(rng)`) and shares nothing with
`abstraction`, `solver` or `risk`; the goal check and the costs come in from the caller.
"""

import math
import random
import statistics
from collections.abc import Callable
from numbers import Integral, Real

from crafting_system.data import GameData
from crafting_system.items import Item

from ._estimate import critical_value, mean, proportion
from ._report import SimulationReport
from ._step import Policy

DEFAULT_MAX_STEPS = 100_000


def simulate(
    data: GameData,
    policy: Policy,
    start: Item,
    is_goal: Callable[[Item], bool],
    *,
    runs: int,
    seed: int,
    start_cost: float = 0.0,
    max_steps: int = DEFAULT_MAX_STEPS,
    confidence: float = 0.95,
) -> SimulationReport:
    """Run `policy` from `start` `runs` times and report the success rate and the cost.

    `policy(item)` is asked only for items that are not a goal and returns a `Step` or None to
    stop. `start_cost` (what `start` cost to get) is part of every run's total. Raises
    `ValueError` for a bad argument: `runs` an integer of at least 2, `seed` an integer,
    `start_cost` finite and not negative, `max_steps` an integer of at least 1, `confidence`
    strictly between 0 and 1. Errors raised by the actions or the policy propagate.
    """
    _check_arguments(runs, seed, start_cost, max_steps, confidence)
    rng = random.Random(seed)
    costs: list[float] = []
    paid_by_successes: list[float] = []
    stopped = unfinished = steps_taken = 0
    for _ in range(runs):
        item, total, steps = start, float(start_cost), 0
        while True:
            if is_goal(item):
                paid_by_successes.append(total)
                break
            step = policy(item)
            if step is None:
                stopped += 1
                break
            if steps == max_steps:
                unfinished += 1
                break
            total += step.cost
            item = step.action.outcomes(data, item).sample(rng)
            steps += 1
        costs.append(total)
        steps_taken += steps
    successes = len(paid_by_successes)
    return SimulationReport(
        runs=runs,
        successes=successes,
        stopped=stopped,
        unfinished=unfinished,
        success_rate=proportion(successes, runs, confidence),
        cost=mean(costs, confidence),
        cost_of_successes=mean(paid_by_successes, confidence) if successes >= 2 else None,
        mean_steps=steps_taken / runs,
        confidence=confidence,
        costs=tuple(costs),
    )


def _check_arguments(runs: object, seed: object, start_cost: object, max_steps: object, confidence: object) -> None:
    if isinstance(runs, bool) or not isinstance(runs, Integral) or runs < 2:
        raise ValueError(f"runs must be an integer of at least 2, got {runs!r}")
    if isinstance(seed, bool) or not isinstance(seed, Integral):
        raise ValueError(f"seed must be an integer, got {seed!r}")
    if isinstance(start_cost, bool) or not isinstance(start_cost, Real) or not (
        _is_finite(start_cost) and start_cost >= 0.0
    ):
        raise ValueError(f"start_cost must be finite and not negative, got {start_cost!r}")
    if isinstance(max_steps, bool) or not isinstance(max_steps, Integral) or max_steps < 1:
        raise ValueError(f"max_steps must be an integer of at least 1, got {max_steps!r}")
    if isinstance(confidence, bool) or not isinstance(confidence, Real) or not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be strictly between 0 and 1, got {confidence!r}")
    try:
        usable = critical_value(confidence) > 0.0
    except statistics.StatisticsError:
        usable = False
    if not usable:
        raise ValueError(f"confidence {confidence!r} is too close to 0 or 1 to give an interval")


def _is_finite(value: Real) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:  # an integer too large for a float
        return False
