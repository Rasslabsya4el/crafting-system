"""`simulate`: run a policy on concrete items and measure what it costs and how often it succeeds.

One run starts from `start` with `start_cost` paid. While the item is not a goal, the policy names
a step; the step's cost is added, the action is applied with its sampler and the new item replaces
the old one. A run ends when the item is a goal (success; the goal is checked before the policy is
asked, so a goal item is never acted on, the start included), when the policy returns None
(stopped) or when `max_steps` steps have been taken and the item is still not a goal (unfinished).
The policy is asked about the item after the last step first, so it can still stop the run, which
then counts as stopped. The cost of a run is the total paid until it ends, whatever the ending.

All runs draw from one `random.Random(seed)`, in order, so the same arguments give the same report. With `block` the
runs are cut in blocks of that many: block 0 draws from `random.Random(seed)` and block b from `random.Random(f"{seed}/{b}")`,
and the blocks may run in a process pool (ticket #250, `crafting_system.parallel`); the report is the same for any number of
workers, because a block's draws depend on its number only and the blocks are joined in order. Without `block`, or with
`block >= runs`, there is the one stream and nothing is parallel.

Nested runs (ticket #222, ADR-0022). A `Step` may list `inputs`: second items the action consumes. Before the action is applied
the simulator makes each input by a run of its own (`Input.policy` from `Input.start` until `Input.is_goal`), in order, adds what
those runs cost to the run that asked, then applies the action to the item in hand (bound to the donors the runs made when the
step has `bind`) and checks each donor with `Input.matches` when it has one. Every attempt makes its inputs afresh, a retry
included, and a nested run draws from the same stream as the run that asked, so the draws of a run stay in one fixed order. All
the steps of the tree of runs count against `max_steps`, and the clicks of nested runs count in `mean_steps`. A nested run that
is stopped or cut ends the run that asked for it the same way (stopped or unfinished), the cost paid until then counted. A block
still draws from its own seeded stream only, so nested runs keep the report the same for any number of workers.

With `reading` the simulator samples the actions under that reading of the rule axes (`action.outcomes_under(data, item, reading)`,
for an action that has it) in every run and every nested run, instead of the plan's value: a reading is one global fact of the
game (ADR-0033), so a nested run reads the same one as the run that asked for it.

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

from crafting_system import parallel
from crafting_system.data import GameData
from crafting_system.items import Item

from ._estimate import critical_value, mean, proportion
from ._report import SimulationReport
from ._step import DonorMismatchError, Policy

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
    block: int | None = None,
    workers: int | None = None,
    reading: object | None = None,
) -> SimulationReport:
    """Run `policy` from `start` `runs` times and report the success rate and the cost.

    `policy(item)` is asked only for items that are not a goal and returns a `Step` or None to
    stop. `start_cost` (what `start` cost to get) is part of every run's total. Raises
    `ValueError` for a bad argument: `runs` an integer of at least 2, `seed` an integer,
    `start_cost` finite and not negative, `max_steps` an integer of at least 1, `confidence`
    strictly between 0 and 1. Errors raised by the actions or the policy propagate, and so does
    `DonorMismatchError` from a nested run whose donor its `Input.matches` refuses.
    """
    _check_arguments(runs, seed, start_cost, max_steps, confidence)
    if block is not None and (isinstance(block, bool) or not isinstance(block, Integral) or block < 1):
        raise ValueError(f"block must be a whole number of 1 or more, got {block!r}")
    size = runs if block is None else min(block, runs)
    tasks = [(seed if number == 0 else f"{seed}/{number}", min(size, runs - first)) for number, first in enumerate(range(0, runs, size))]
    shared = (data, policy, start, is_goal, float(start_cost), max_steps, reading)
    # the policy is a closure: it is inherited by forked workers, not pickled, so where there is no fork the blocks run here
    if len(tasks) > 1 and parallel.can_inherit() and (workers is None or workers > 1):
        with parallel.WorkerPool(_shared, (shared,), workers=workers) as pool:
            parts = pool.map(_run_block, tasks, chunk=1)
    else:
        parts = [_block(*shared, *task) for task in tasks]
    costs: list[float] = []
    paid_by_successes: list[float] = []
    stopped = unfinished = steps_taken = nested = 0
    for block_costs, block_paid, block_stopped, block_unfinished, block_steps, block_nested in parts:
        costs.extend(block_costs)
        paid_by_successes.extend(block_paid)
        stopped += block_stopped
        unfinished += block_unfinished
        steps_taken += block_steps
        nested += block_nested
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
        nested_runs=nested,
    )


def _shared(shared: tuple) -> tuple:
    return shared


def _run_block(task: tuple) -> tuple:
    return _block(*parallel.context(), *task)


def _sampler(action, data, item, reading):
    """The action's outcomes on `item`: under `reading` when one is given and the action takes readings, else the plan's."""
    if reading is not None:
        under = getattr(action, "outcomes_under", None)
        if under is not None:
            return under(data, item, reading)
    return action.outcomes(data, item)


class _Tree:
    """One run and the nested runs it makes: the stream, the step budget shared by the tree, the counts."""

    __slots__ = ("data", "rng", "max_steps", "reading", "steps", "nested")

    def __init__(self, data, rng, max_steps, reading):
        self.data, self.rng, self.max_steps, self.reading = data, rng, max_steps, reading
        self.steps = self.nested = 0

    def walk(self, item, policy, is_goal):
        """Run `policy` from `item` until a goal, a stop or the step budget: `(ending, last item, paid)`.

        `ending` is "goal", "stopped" or "unfinished". `paid` is what the steps cost, nested runs included, the start not.
        """
        paid = 0.0
        while True:
            if is_goal(item):
                return "goal", item, paid
            step = policy(item)
            if step is None:
                return "stopped", item, paid
            if self.steps == self.max_steps:
                return "unfinished", item, paid
            paid += step.cost
            action = step.action
            if step.inputs:
                donors = []
                for need in step.inputs:
                    self.nested += 1
                    ending, donor, spent = self.walk(need.start, need.policy, need.is_goal)
                    paid += need.start_cost + spent
                    if ending != "goal":
                        return ending, item, paid
                    if need.matches is not None and not need.matches(donor):
                        raise DonorMismatchError(f"a nested run made a donor that its step refuses: {donor!r}")
                    donors.append(donor)
                if self.steps == self.max_steps:  # the nested runs used the last click: this step cannot be taken
                    return "unfinished", item, paid
                if step.bind is not None:
                    action = step.bind(tuple(donors))
            item = _sampler(action, self.data, item, self.reading).sample(self.rng)
            self.steps += 1


def _block(data, policy, start, is_goal, start_cost, max_steps, reading, seed, runs):
    """`runs` crafts drawn from `random.Random(seed)`: their costs, the costs of the successes and the counts."""
    rng = random.Random(seed)
    costs: list[float] = []
    paid_by_successes: list[float] = []
    stopped = unfinished = steps_taken = nested = 0
    for _ in range(runs):
        tree = _Tree(data, rng, max_steps, reading)
        ending, _, paid = tree.walk(start, policy, is_goal)
        total = start_cost + paid
        if ending == "goal":
            paid_by_successes.append(total)
        elif ending == "stopped":
            stopped += 1
        else:
            unfinished += 1
        costs.append(total)
        steps_taken += tree.steps
        nested += tree.nested
    return costs, paid_by_successes, stopped, unfinished, steps_taken, nested


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
