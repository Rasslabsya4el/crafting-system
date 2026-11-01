"""`--verify`: run the solved policy on concrete items and compare with the computed numbers.

The simulator is the independent check of the kernel (ADR-0019): it draws every click with the
action's own sampler on a concrete item and judges the goal with the target itself, not with the
compressed state. The comparison is the mean total cost (the start price included) against the
computed mean, within `SIGMAS` standard errors of the simulated mean, and the run must have ended
every time in the goal. Every interval is a normal approximation, good for thousands of runs.

An approximate plan is verified the same way through the lift (`_lift`, ADR-0023): the policy of blocks is run on
concrete items. There is no computed mean to compare with, only the certified interval `[lower, upper]`, so the
run agrees when no run was cut or stopped and the simulated mean, within `SIGMAS` standard errors, touches that
interval. Its p90 and CVaR are simulated numbers and are never certified.
"""

import math
from dataclasses import dataclass

from crafting_system.actions import Action
from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.simulator import SampledEstimate, SimulationReport, Step, simulate

from ._lift import lift
from ._plan import Plan

DEFAULT_RUNS = 10_000
DEFAULT_SEED = 1
SIGMAS = 5.0  # a correct policy fails the check about once in 1.7 million runs
STEPS_PER_MEAN = 50  # a run is cut after this many times the clicks the computed mean allows
MIN_STEPS = 100
ROUNDING = 1e-12  # relative: the rounding that a run with no spread may show against a bound (the simulator's own exact tolerance)
CVAR_LEVEL = 0.9  # the level of `risk.evaluate`'s default, so the two CVaRs are the same quantity


class Memoized:
    """An action that remembers its `outcomes`, which makes thousands of real runs affordable.

    What a reroll can leave behind depends only on the base, the item level, the rarity, the
    influences, the corruption and the fractured and crafted mods of the item (the `retained` item
    of `Outcomes`) for an action that reads nothing of the other mods (`Action.reads`), so building it
    once per such item changes no result. The sampler runs every time.
    """

    def __init__(self, action: object) -> None:
        self.action = action
        self._cache: dict[tuple, object] = {}

    def outcomes(self, data: GameData, item: Item) -> object:
        if isinstance(self.action, Action) and self.action.reads(data).junk:
            return self.action.outcomes(data, item)  # it reads the other mods of the item, so the key above is not enough
        key = (
            item.base_id, item.item_level, item.rarity, item.influences, item.corrupted,
            item.fractured_mods, item.crafted_mods,
        )  # fmt: skip
        if key not in self._cache:
            self._cache[key] = self.action.outcomes(data, item)
        return self._cache[key]


def _memoized(action: object) -> object:
    """Every action is wrapped; `Memoized` remembers only those that read nothing of the junk (a bench action reads every mod of the item and is not)."""
    return Memoized(action)


@dataclass(frozen=True)
class Verification:
    """The simulated numbers next to the computed ones."""

    runs: int
    seed: int
    max_steps: int
    report: SimulationReport
    computed_mean: float  # the total cost with the start price, as the plan reports it (the upper bound of an approximate plan)
    computed_p90: float | None  # None for an approximate plan: it has no certified p90
    agrees: bool
    reason: str  # why it does not agree, empty when it does
    bounds: tuple[float, float] | None = None  # an approximate plan's certified interval of the total cost, the start price included

    @property
    def detectable_error(self) -> float:
        """The smallest relative error of the computed mean this run can reject: SIGMAS standard errors over the mean.

        A cost is about as spread as its mean (a geometric number of clicks), so the standard error is
        about the mean over sqrt(runs): 10,000 runs see an error of 5% or more, not a smaller one.
        """
        centre = self.computed_mean if self.bounds is None else sum(self.bounds) / 2  # the middle of an interval
        return SIGMAS * self.report.cost.standard_error / centre if centre else math.inf

    @property
    def p90(self) -> SampledEstimate:
        return self.report.quantile(0.9)

    @property
    def cvar(self) -> SampledEstimate:
        """The mean of the worst `1 - CVAR_LEVEL` share of the simulated costs."""
        return self.report.cvar(CVAR_LEVEL)

    @property
    def approximate(self) -> bool:
        return self.bounds is not None


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
        state: Step(_memoized(plan.offer_of(action).offer.action), plan.offer_of(action).cost)
        for state, action in plan.policy.items()
    }
    target = plan.target
    policy = lift(plan, steps)

    limit = max_steps_for(plan)
    report = simulate(
        data, policy, target.start_item, target.is_met_by,
        runs=runs, seed=seed, start_cost=plan.start_price.chaos, max_steps=limit,
    )  # fmt: skip
    shift = plan.start_price.chaos
    computed = shift + plan.mean_remaining
    if plan.approximation is not None:
        bounds = (shift + plan.approximation.lower, shift + plan.approximation.upper)
        reason = _approximate_reason(report, bounds, limit)
        return Verification(runs, seed, limit, report, computed, None, not reason, reason, bounds)
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


def _approximate_reason(report: SimulationReport, bounds: tuple[float, float], limit: int) -> str:
    """Why a simulation does not agree with a certified interval, empty when it does.

    The simulated mean's interval is `SIGMAS` standard errors wide on each side, not the 95% one that is shown:
    a policy whose gap is close to 0 would be rejected in one seed of twenty by a 95% interval.
    """
    if report.unfinished or report.stopped:
        return f"{report.unfinished} runs hit the step limit of {limit} and {report.stopped} stopped early"
    lower, upper = bounds
    cost = report.cost
    low, high = cost.value - SIGMAS * cost.standard_error, cost.value + SIGMAS * cost.standard_error
    if cost.standard_error == 0.0:  # no spread: equality within the rounding of the exact check counts as meeting
        low, high = cost.value * (1 - ROUNDING), cost.value * (1 + ROUNDING)
    if high < lower:
        side = "below"
    elif low > upper:
        side = "above"
    else:
        return ""
    return (
        f"the simulated mean {cost.value:.4g} (interval {low:.4g} to {high:.4g} at {SIGMAS:g} standard errors) "
        f"lies {side} the certified interval {lower:.4g} to {upper:.4g}"
    )
