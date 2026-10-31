"""`--verify`: run the solved policy on concrete items and compare with the computed numbers.

The simulator is the independent check of the kernel (ADR-0019): it draws every click with the
action's own sampler on a concrete item and judges the goal with the target itself, not with the
compressed state. The comparison is the mean total cost (the start price included) against the
computed mean, within `SIGMAS` standard errors of the simulated mean, and the run must have ended
every time in the goal. Every interval is a normal approximation, good for thousands of runs.
"""

import math
from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.simulator import SimulationReport, Step, simulate

from ._plan import Plan

DEFAULT_RUNS = 10_000
DEFAULT_SEED = 1
SIGMAS = 5.0  # a correct policy fails the check about once in 1.7 million runs
STEPS_PER_MEAN = 50  # a run is cut after this many times the clicks the computed mean allows
MIN_STEPS = 100


class Memoized:
    """An action that remembers its `outcomes`, which makes thousands of real runs affordable.

    What a reroll can leave behind depends only on the base, the item level, the rarity, the
    influences, the corruption and the fractured and crafted mods of the item (the `retained` item
    of `Outcomes`), so building it once per such item changes no result. The sampler runs every time.
    """

    def __init__(self, action: object) -> None:
        self.action = action
        self._cache: dict[tuple, object] = {}

    def outcomes(self, data: GameData, item: Item) -> object:
        key = (
            item.base_id, item.item_level, item.rarity, item.influences, item.corrupted,
            item.fractured_mods, item.crafted_mods,
        )  # fmt: skip
        if key not in self._cache:
            self._cache[key] = self.action.outcomes(data, item)
        return self._cache[key]


@dataclass(frozen=True)
class Verification:
    """The simulated numbers next to the computed ones."""

    runs: int
    seed: int
    max_steps: int
    report: SimulationReport
    computed_mean: float  # the total cost with the start price, as the plan reports it
    computed_p90: float
    agrees: bool
    reason: str  # why it does not agree, empty when it does

    @property
    def detectable_error(self) -> float:
        """The smallest relative error of the computed mean this run can reject: SIGMAS standard errors over the mean.

        A cost is about as spread as its mean (a geometric number of clicks), so the standard error is
        about the mean over sqrt(runs): 10,000 runs see an error of 5% or more, not a smaller one.
        """
        return SIGMAS * self.report.cost.standard_error / self.computed_mean if self.computed_mean else math.inf

    @property
    def p90(self):
        return self.report.quantile(0.9)


def max_steps_for(plan: Plan) -> int:
    """A cut-off for one run: far above what the computed mean needs, far below the simulator's default.

    The mean cost over the cheapest click bounds the mean number of clicks, and a run past
    `STEPS_PER_MEAN` times that is far in the tail of any sane policy; a policy whose odds are
    badly wrong then ends as `unfinished` instead of running 100,000 clicks per run.
    """
    cheapest = min(plan.offer_of(action).cost for action in plan.policy.values())
    bound = math.ceil(STEPS_PER_MEAN * max(plan.mean_remaining, cheapest) / cheapest)
    return max(MIN_STEPS, bound)


def verify(data: GameData, plan: Plan, *, runs: int = DEFAULT_RUNS, seed: int = DEFAULT_SEED) -> Verification:
    """Simulate `runs` crafts of the plan's policy from the target's start item."""
    steps = {
        state: Step(Memoized(plan.offer_of(action).offer.action), plan.offer_of(action).cost)
        for state, action in plan.policy.items()
    }
    abstraction, target = plan.abstraction, plan.target

    def policy(item: Item) -> Step | None:
        return steps.get(abstraction.compress(item))

    limit = max_steps_for(plan)
    report = simulate(
        data, policy, target.start_item, target.is_met_by,
        runs=runs, seed=seed, start_cost=plan.start_price.chaos, max_steps=limit,
    )  # fmt: skip
    computed = plan.start_price.chaos + plan.mean_remaining
    reason = ""
    if report.unfinished or report.stopped:
        reason = f"{report.unfinished} runs hit the step limit of {limit} and {report.stopped} stopped early"
    elif not report.cost.agrees_with(computed, sigmas=SIGMAS):
        reason = (
            f"the simulated mean {report.cost.value:.4g} is more than {SIGMAS:g} standard errors "
            f"({report.cost.standard_error:.3g}) from the computed {computed:.4g}"
        )
    return Verification(
        runs, seed, limit, report, computed, plan.start_price.chaos + plan.risk.p90.value, not reason, reason
    )
