"""From a target to a solved policy with its risk: targets -> prices -> abstraction -> solver -> risk.

`make_plan` is the whole pipeline of the R12 slice and does no printing and no file work: the
caller loads the game data, the target and the prices and decides what to do with the `Plan`.
Nothing here reads the clock except `time.perf_counter` around the solve and the risk run, which
are reported (the budget DP of `risk.evaluate` is pure Python and can be slow on large policies).
"""

import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.abstraction import Abstraction, CompressedState, Goal, integer_weights
from crafting_system.actions import ActionError
from crafting_system.data import GameData
from crafting_system.prices import PriceFile
from crafting_system.prices.price_names import canonical_price_name
from crafting_system.risk import RiskReport, evaluate
from crafting_system.solver import Action, Outcome, Solution, solve
from crafting_system.targets import KOfN, Requirement, Target

from ._offers import DroppedOffer, Offer, PricedOffer, default_offers, price_offers


class PlanError(ValueError):
    """The target cannot be planned: a price is missing or no policy reaches the goal."""


@dataclass(frozen=True)
class StartPrice:
    """What the start item costs to get, in Chaos, and where the number came from."""

    name: str | None
    chaos: float
    source: str


@dataclass(frozen=True)
class Plan:
    """Everything the report prints: the solved policy, its risk and the inputs it was built from."""

    target: Target
    abstraction: Abstraction
    leaf_labels: tuple[str, ...]
    prices: PriceFile
    start: CompressedState
    start_price: StartPrice
    offers: tuple[PricedOffer, ...]
    dropped: tuple[DroppedOffer, ...]
    solution: Solution[CompressedState]
    risk: RiskReport
    solve_seconds: float
    risk_seconds: float

    @property
    def policy(self) -> Mapping[CompressedState, Action[CompressedState]]:
        return self.solution.policy

    def is_goal(self, state: CompressedState) -> bool:
        return self.abstraction.is_goal(state)

    def offer_of(self, action: Action[CompressedState]) -> PricedOffer:
        """The priced offer a policy action stands for (the action label is the offer label)."""
        return next(priced for priced in self.offers if priced.label == action.label)

    @property
    def mean_remaining(self) -> float:
        """The solver's expected cost from the start, without the price of the start item."""
        return self.solution.values[self.start]


class _RerollModel:
    """The solver's view of the compressed states under the offered actions."""

    def __init__(self, abstraction: Abstraction, offers: Iterable[PricedOffer]) -> None:
        self.abstraction = abstraction
        self.offers = tuple(offers)

    def is_goal(self, state: CompressedState) -> bool:
        return self.abstraction.is_goal(state)

    def actions(self, state: CompressedState) -> list[Action[CompressedState]]:
        found = []
        for priced in self.offers:
            try:
                kernel = self.abstraction.kernel(state, priced.offer.action)
            except ActionError:  # the game refuses it here, or no admitted rule covers it
                continue
            weights = integer_weights(kernel)
            found.append(
                Action(priced.label, priced.cost, tuple(Outcome(s, w) for s, w in weights.items()))
            )
        return found


def leaf_labels(target: Target) -> tuple[str, ...]:
    """A short English name for each requirement leaf, in the order of `Goal.leaves`."""
    labels: list[str] = []

    def walk(node: Requirement | KOfN) -> None:
        if isinstance(node, KOfN):
            for member in node.of:
                walk(member)
            return
        name = node.stat if node.stat is not None else f"family {node.family}"
        limits = []
        if node.min_tier is not None:
            limits.append(f"tier {node.min_tier} or better")
        if node.min_roll is not None and any(roll is not None for roll in node.min_roll):
            limits.append("roll at least " + "/".join("any" if r is None else str(r) for r in node.min_roll))
        if node.not_crafted:
            limits.append("not crafted")
        labels.append(f"{name} ({', '.join(limits)})" if limits else name)

    for requirement in target.requirements:
        walk(requirement)
    return tuple(labels)


def resolve_start_price(
    target: Target, prices: PriceFile, override: float | None
) -> StartPrice:
    """The cost of the start item: a run's own number, else the price file (hand overrides already in it).

    A target without `start_price` counts its start item as free. A name that is not in the price
    file is an error: the cost of the whole craft would be wrong without it.
    """
    if override is not None:
        if not override >= 0 or override == float("inf"):
            raise PlanError(f"the start price must be a number of Chaos, zero or more, got {override!r}")
        return StartPrice(target.start_price, float(override), "given on the command line")
    if target.start_price is None:
        return StartPrice(None, 0.0, "the target names no start price, so the start item counts as free")
    name = canonical_price_name(target.start_price)
    entry = prices.prices.get(name)
    if entry is None:
        raise PlanError(
            f"no price for the start item {name!r}. Price it with `python -m crafting_system.prices trade "
            "--spec <buy spec>`, write it in price_overrides.toml, or give it with --start-price"
        )
    return StartPrice(name, entry.chaos, entry.source)


def make_plan(
    data: GameData,
    target: Target,
    prices: PriceFile,
    *,
    start_price: float | None = None,
    offers: Iterable[Offer] | None = None,
) -> Plan:
    """Solve the target and measure the risk of the policy.

    `start_price` is the cost of the start item for this run (it wins over the price file);
    `offers` default to `default_offers()`. Raises `PlanError` when no offer has a price or no
    policy reaches the goal, and what the layers below raise for a bad input.
    """
    price_of_start = resolve_start_price(target, prices, start_price)
    priced, dropped = price_offers(default_offers() if offers is None else offers, prices)
    if not priced:
        names = sorted({name for drop in dropped for name in drop.missing})
        raise PlanError(f"no action has a price; missing: {', '.join(names)}")

    goal = Goal.from_target(target)
    abstraction = Abstraction(data, goal, target.base_id, target.item_level)
    start = abstraction.compress(target.start_item)
    model = _RerollModel(abstraction, priced)

    began = time.perf_counter()
    solution = solve(model, [start])
    solve_seconds = time.perf_counter() - began
    if not abstraction.is_goal(start) and not _finite(solution.values[start]):
        raise PlanError("no policy of the offered actions reaches the goal from the start item")

    began = time.perf_counter()
    risk = evaluate(solution.policy, start, abstraction.is_goal)
    risk_seconds = time.perf_counter() - began

    return Plan(
        target, abstraction, leaf_labels(target), prices, start, price_of_start, priced, dropped,
        solution, risk, solve_seconds, risk_seconds,
    )


def _finite(value: float) -> bool:
    return value == value and value != float("inf")


def chance(weight: int, total: int) -> float:
    """`weight / total` as a float, exact in the ratio even for huge integers."""
    return float(Fraction(weight, total))
