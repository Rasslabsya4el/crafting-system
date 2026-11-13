"""Relations between two runs of the planner that need no reference answer (ticket #887): the cases, the changes and the checks.

The planner is an optimiser with nothing to compare its answer with: nobody can say what the cheapest route "should" cost. What can be
said without a reference is how two answers must stand to each other. Every check here plans through the planner's one entry
(`planner.plan_target`) and returns the violations it found, as sentences; `tests/test_planner_relations.py` asserts there are none
on the planner as it is, and some on a planner broken on purpose.

**The cases** come from the generator of the planning-speed family (`family_bench_support`, ticket #824): its bases, its mod draw, its
prices scaled per currency by a seeded factor. The committed family itself (`tests/fixtures/family_bench/cases-seed824.json`) takes from under a
second to 9 minutes a plan on a runner, and a relation needs up to ten plans of one case, so the cases here are the generator's own draw at one or
two wanted mods (`SIZES`) over the method sets that plan in about a second or less (`METHODS`): the orbs of a Magic item, the same with
the Regal Orb, essences, the Chaos Orb. A case is named by its method set, size and seed (`case`). Nothing here records a number of a route, and no value here is chosen for one case.

**The tolerance** of every comparison of two costs is the one value `GAP`, and a plan that says it stopped at a proved gap (OR-32) is
compared at the figure it proved (`Cost.proved`), so no comparison is loosened for the plans that are exact. The simulator's own test is
`cli._verify.SIGMAS` standard errors of its mean.
"""

from __future__ import annotations

import dataclasses
import math
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import yaml

import crafting_system.cli  # noqa: F401 - names the presenter of plans (`planner.present_with`, issue #882)
import family_bench_support as F
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.actions.pool import tiers_of
from crafting_system.cli._verify import chosen_offers, verify
from crafting_system.data.model import GameData
from crafting_system.items.model import Item, Rarity
from crafting_system.planner import RESTART, Plan, PlanError, PlanSettings, evaluate_risk, free_action_cost, offer_action, plan_target
from crafting_system.prices.price_file import PriceFile
from crafting_system.targets import parse_target

# The room every comparison gives, as a share of the larger side: "a <= b" is read `a <= b * (1 + GAP)`. It is the solver's certified
# tolerance with room to spare. The proved gap of a plan that stopped before it was exact (OR-32, ticket #826) is not in it: such a
# plan says what it proved, and `Cost.proved` reads that.
GAP = 1e-6
PROVED_GAP_LIMIT = 0.01  # OR-32: a plan is exact, or proved at most 1% above the cheapest

PRICE_STEP = 3.0  # an ingredient's price is raised and lowered by this factor
SCALES = (0.25, 3.0)  # every price is scaled by each of these factors
CLICKS = 25_000  # the simulator plays a plan until about this many clicks are made (a few seconds), in no fewer than `PLAYS[0]` and no more than `PLAYS[1]` plays
PLAYS = (50, 500)
PILOT = 20  # plays that measure how many clicks one play takes
GUIDES = 3  # generated guides per case
UNIT = F.UNIT

MAGIC = ("transmutation-orb", "alteration-orb", "augmentation-orb")


@dataclass(frozen=True)
class MethodSet:
    """A method set of the family cut down to what plans in about a second, and the one method `more` a relation may allow on top."""

    method: F.Method
    more: str | None = None


METHODS = {
    entry.method.name: entry
    for entry in (
        MethodSet(F.Method("magic-orbs", "B1", "normal", MAGIC)),
        MethodSet(F.Method("magic-and-regal", "B1", "normal", (*MAGIC, "regal-orb"))),
        MethodSet(F.Method("essences", "B1", "normal", ("essence",), keep=F.keep_some(F.is_essence_for, (2, 3))), more="transmutation-orb"),
        MethodSet(F.Method("chaos-orb", "B1", "rare", ("chaos-orb",)), more="essence"),
    )
}
SIZES = {
    "one": F.Size("one", (1, 1), (3, 3), 0),  # one wanted mod, tier 3 or better: the family's small size at its lower end
    "two": F.Size("two", (2, 2), (2, 3), 1),  # two wanted mods, tier 2 or 3 or better
}


@dataclass(frozen=True)
class Case:
    """One generated case and what a relation changes of it: the target as the YAML document, the prices, the start price."""

    id: str
    generated: F.Case
    more: str | None
    doc: Mapping = field(hash=False, compare=False, default_factory=dict)
    prices: PriceFile | None = field(hash=False, compare=False, default=None)

    @property
    def start_price(self) -> float | None:
        return self.generated.start_price


def case(data: GameData, method: str, size: str, seed: int) -> Case:
    """The generator's case of `method` at `size` for `seed` (`family_bench_support.make_case`: the same draw, the same prices)."""
    entry = METHODS[method]
    classes = list(F.item_classes(data))
    random.Random(f"{seed}:classes").shuffle(classes)
    generated = F.make_case(data, seed, entry.method, SIZES[size], classes, F.merged_snapshots())
    if generated.refused:
        raise ValueError(f"{method}/{size}/{seed} is a case the planner refuses today: {generated.refused}")
    generated = dataclasses.replace(generated, id=f"{method}/{size}/{seed}")
    return Case(generated.id, generated, entry.more, yaml.safe_load(generated.target_yaml), F.prices_for(generated))


# -- the changes a relation makes -----------------------------------------------------------------------------------------------------


def scaled(prices: PriceFile, factor: Callable[[str], float]) -> PriceFile:
    """`prices` with the price of every name but the unit multiplied by `factor(name)`, in every table a price is read from.

    The Chaos Orb is the unit and stays 1 (`price_offers` reads it as 1 whatever the file says); the Divine Orb's rate takes the
    Divine Orb's factor (`family_bench_support.prices_for` scales the same tables).
    """

    def scale(name: str, record):
        if name == UNIT or getattr(record, "chaos", None) is None:
            return record
        return dataclasses.replace(record, chaos=record.chaos * factor(name))

    def table(entries: Mapping) -> dict:
        return {name: scale(name, entry) for name, entry in entries.items()}

    return dataclasses.replace(
        prices, prices=table(prices.prices), ninja=table(prices.ninja), deep=table(prices.deep), markets=table(prices.markets),
        chaos_per_divine=prices.chaos_per_divine * factor("Divine Orb"),
    )  # fmt: skip


def one_price(prices: PriceFile, name: str, factor: float) -> PriceFile:
    return scaled(prices, lambda other: factor if other == name else 1.0)


def with_actions(doc: Mapping, actions) -> dict:
    return {**doc, "actions": list(actions)}


def with_requirements(doc: Mapping, requirements) -> dict:
    return {**doc, "requirements": list(requirements)}


def tier_changes(doc: Mapping) -> list[tuple[str, dict, dict]]:
    """Pairs (what, looser target, tighter target) of the case's target: each wanted mod one tier wider, one tier narrower, and left out.

    The pair is always (the superset, the subset) of the items that meet the target, and one of the two is the case's own target.
    """
    found = []
    wanted = list(doc["requirements"])
    for index, entry in enumerate(wanted):
        if "min_tier" in entry:
            tier = entry["min_tier"]
            wider = with_requirements(doc, [*wanted[:index], {**entry, "min_tier": tier + 1}, *wanted[index + 1 :]])
            found.append((f"{entry['family']} at tier {tier + 1} or better, not {tier}", wider, dict(doc)))
            if tier > 1:
                narrower = with_requirements(doc, [*wanted[:index], {**entry, "min_tier": tier - 1}, *wanted[index + 1 :]])
                found.append((f"{entry['family']} at tier {tier} or better, not {tier - 1}", dict(doc), narrower))
        if len(wanted) > 1:
            found.append((f"without {entry['family']}", with_requirements(doc, wanted[:index] + wanted[index + 1 :]), dict(doc)))
    return found


# -- planning -------------------------------------------------------------------------------------------------------------------------


def _key(value) -> str:
    return yaml.safe_dump(value, sort_keys=True)


NO_PLAN = ("reaches the goal", "no action has a price")  # the planner's two ways to say that the offered actions cannot make the item


@dataclass(frozen=True)
class Cost:
    """The mean cost of a plan, start item included (`stated`), and the cost no plan of the same run is below (`proved`).

    An exact plan proves its own cost. A plan of the envelope search says the two sides it stopped between (`EnvelopeInfo.lower` and
    `upper`, OR-32), and `proved` is the stated cost less that share. Both are infinite where there is no plan.
    """

    stated: float
    proved: float

    def times(self, factor: float) -> "Cost":
        return Cost(self.stated * factor, self.proved * factor)

    @property
    def gap(self) -> float:
        return 0.0 if self.stated == self.proved else self.stated / self.proved - 1.0


NONE = Cost(math.inf, math.inf)


def cost_of(plan: Plan) -> Cost:
    info = plan.packed.info.get("envelope") if plan.packed is not None else None
    share = info.lower / info.upper if info is not None and 0 <= info.lower < info.upper else 1.0
    return Cost(total(plan), plan.start_price.chaos + float(plan.mean_remaining) * share)


class Runs:
    """Plans of the cases through the planner's entry: the same run asked twice (a case's own plan, by every relation) is made once."""

    def __init__(self, data: GameData) -> None:
        self.data = data
        self.made: dict[tuple, tuple] = {}
        self.guides: dict[str, list[tuple[str, float]]] = {}
        self.count = 0

    def plan(self, case: Case, *, doc: Mapping | None = None, prices: PriceFile | None = None, start_factor: float = 1.0) -> Plan | None:
        """The plan of `case` with its target, its prices or its start price changed; None where the planner says there is no plan."""
        doc = case.doc if doc is None else doc
        prices = case.prices if prices is None else prices
        key = (case.id, _key(doc), id(prices), start_factor)
        if key not in self.made:
            self.count += 1
            start = None if case.start_price is None else case.start_price * start_factor
            settings = PlanSettings(recipe_starts=case.generated.vendor_starts, start_price=start)
            try:
                target = parse_target(yaml.safe_dump(dict(doc), sort_keys=False, allow_unicode=True, width=1000), self.data, source=f"<{case.id}>")
                self.made[key] = (prices, plan_target(self.data, target, prices, settings))  # the prices are held so that their `id` stays theirs
            except PlanError as error:
                if not any(words in str(error) for words in NO_PLAN):
                    raise  # any other refusal is the planner failing, not a cost: it must not pass as "infinitely dear"
                self.made[key] = (prices, error)
        made = self.made[key][1]
        return None if isinstance(made, PlanError) else made

    def cost(self, case: Case, **changes) -> Cost:
        """The cost of the plan; `NONE` (infinite) where there is no plan (no offered action reaches the target)."""
        plan = self.plan(case, **changes)
        return NONE if plan is None else cost_of(plan)


def total(plan: Plan) -> float:
    return plan.start_price.chaos + float(plan.mean_remaining)


def not_above(low: Cost, high: Cost) -> bool:
    """Whether "the cheapest of `low`'s run costs no more than the cheapest of `high`'s" can stand, within `GAP`.

    The cheapest of `low`'s run is at least `low.proved` and the cheapest of `high`'s at most `high.stated`. For two exact plans this is
    `low <= high` of their costs. No plan is above every cost and not above no plan.
    """
    return low.proved <= high.stated * (1 + GAP) or (math.isinf(low.proved) and math.isinf(high.stated))


def same(one: Cost, other: Cost) -> bool:
    return not_above(one, other) and not_above(other, one)


def ingredients(plan: Plan) -> list[str]:
    """The names the plan's offers are priced from, the unit and the start item apart: what `one_price` can change."""
    names = set()
    for priced in plan.offers:
        if priced.label != RESTART:
            names.update(name for name, _count, _chaos, source in priced.parts if source != "fixed" and name in plan.prices.prices)
    return sorted(names)


def choices(plan: Plan) -> dict:
    """The plan itself: the offer it takes at every state it decides."""
    return {state: priced.label for state, priced in chosen_offers(plan)}


# -- the relations --------------------------------------------------------------------------------------------------------------------


def price_violations(runs: Runs, case: Case) -> list[str]:
    """Raising the price of one ingredient never lowers the plan's mean cost; lowering it never raises it. The start item is one.

    A price that changes takes no action away, so a run that then finds no plan is a violation too.
    """
    base = runs.plan(case)
    cost = cost_of(base)
    changes = [(name, lambda factor, name=name: {"prices": one_price(case.prices, name, factor)}) for name in ingredients(base)]
    if base.start_price.bought:
        changes.append(("the start item", lambda factor: {"start_factor": factor}))
    found = []
    for name, change in changes:
        dearer, cheaper = runs.cost(case, **change(PRICE_STEP)), runs.cost(case, **change(1 / PRICE_STEP))
        if dearer is NONE or cheaper is NONE:
            found.append(f"{case.id}: {name} at another price leaves no plan")
        if not not_above(cost, dearer):
            found.append(f"{case.id}: {name} at {PRICE_STEP:g} times its price lowers the mean cost from {cost.stated!r} to {dearer.stated!r}")
        if not not_above(cheaper, cost):
            found.append(f"{case.id}: {name} at 1/{PRICE_STEP:g} of its price raises the mean cost from {cost.stated!r} to {cheaper.stated!r}")
    return found


def method_violations(runs: Runs, case: Case) -> list[str]:
    """Allowing one more method never raises the mean cost; forbidding one never lowers it."""
    cost = runs.cost(case)
    actions = list(case.doc["actions"])
    found = []
    for name in actions:
        if len(actions) == 1:
            break  # a target that names no action is refused by the target's parser, not planned
        without = runs.cost(case, doc=with_actions(case.doc, [a for a in actions if a != name]))
        if not not_above(cost, without):
            found.append(f"{case.id}: forbidding {name} lowers the mean cost from {cost.stated!r} to {without.stated!r}")
    if case.more is not None:
        more = runs.cost(case, doc=with_actions(case.doc, [*actions, case.more]))
        if not not_above(more, cost):
            found.append(f"{case.id}: allowing {case.more} raises the mean cost from {cost.stated!r} to {more.stated!r}")
    return found


def target_violations(runs: Runs, case: Case) -> list[str]:
    """Loosening the target (a wider tier range, one mod fewer) never raises the mean cost; tightening never lowers it."""
    found = []
    for what, looser, tighter in tier_changes(case.doc):
        low, high = runs.cost(case, doc=looser), runs.cost(case, doc=tighter)
        if not not_above(low, high):
            found.append(f"{case.id}: the looser target ({what}) costs {low.stated!r}, the tighter one {high.stated!r}")
    return found


def scale_violations(runs: Runs, case: Case) -> list[str]:
    """Scaling every price by one factor scales the cost by that factor and keeps the plan.

    The Chaos Orb is the unit and cannot be scaled. Where an offer of the plan consumes it, the prices scaled by `f` lie between the
    case's prices and `f` times all of them, so the cost lies between the case's cost and `f` times it (the price relation and this
    one together), and the plan may change. The plan is compared only where both runs are exact: a plan that stopped at a proved gap
    is one of several the planner may return.
    """
    base = runs.plan(case)
    cost = cost_of(base)
    unit_used = any(name == UNIT for priced in base.offers for name, *_ in priced.parts)
    found = []
    for factor in SCALES:
        plan = runs.plan(case, prices=scaled(case.prices, lambda name: factor), start_factor=factor)
        if plan is None:
            found.append(f"{case.id}: every price times {factor:g} leaves no plan")
            continue
        other = cost_of(plan)
        if unit_used:
            low, high = sorted((cost, cost.times(factor)), key=lambda entry: entry.stated)
            if not (not_above(low, other) and not_above(other, high)):
                found.append(f"{case.id}: every price but the Chaos Orb's times {factor:g} gives {other.stated!r}, outside {low.stated!r} to {high.stated!r}")
            continue
        if not same(other, cost.times(factor)):
            found.append(f"{case.id}: every price times {factor:g} gives {other.stated!r}, not {factor:g} times {cost.stated!r}")
        if max(cost.gap, other.gap) <= GAP and choices(plan) != choices(base):
            found.append(f"{case.id}: every price times {factor:g} changes the plan")
    return found


def guides(runs: Runs, case: Case) -> list[tuple[str, float]]:
    """Generated guides for the case, each with its mean cost by the planner's own rules, start item included.

    A guide is the case's offers in a seeded order, then `restart`: at every state it takes the first of them the game allows there, as
    a route file of rules with no condition and `skip_refused: true` does (`cli._route`). So it is a valid policy of the allowed methods;
    one that never reaches the target has an infinite mean. The first guide keeps the offers in the planner's order.
    """
    if case.id in runs.guides:
        return runs.guides[case.id]
    plan = runs.plan(case)
    labels = [priced.label for priced in plan.offers if priced.label != RESTART]
    found = {}
    for number in range(GUIDES):
        order = list(labels)
        if number:
            random.Random(f"{case.id}:guide:{number}").shuffle(order)
        found.setdefault(" > ".join(order), plan.start_price.chaos + guide_mean(plan, order))
    runs.guides[case.id] = list(found.items())
    return runs.guides[case.id]


def guide_mean(plan: Plan, order: list[str]) -> float:
    """The mean cost of the fixed policy "the first offer of `order` the game allows, else `restart`" from the plan's start state.

    The way `cli._route.evaluate_route` reads a route, on the plan's own model: each action is the one the solver builds
    (`planner.offer_action`: the same kernel, the same integer weights, the offer's own price) and the mean is the exact one of the
    fixed policy (`planner.evaluate_risk`). A state where the game allows none of them is a gap: the guide never finishes.
    """
    by_label = {priced.label: priced for priced in plan.offers}
    steps = [by_label[label] for label in order] + ([by_label[RESTART]] if RESTART in by_label else [])
    policy: dict = {}
    todo, seen = [plan.start], {plan.start}
    for state in todo:  # the list grows while it is walked
        if plan.is_goal(state):
            continue
        for priced in steps:
            try:
                policy[state] = offer_action(plan.abstraction, priced, state, plan.start)
                break
            except (NotApplicableError, OutOfScopeError):
                continue
        else:
            return math.inf
        for successor, weight in policy[state].outcomes:
            if weight > 0 and successor not in seen:
                seen.add(successor)
                todo.append(successor)
    risk = evaluate_risk(policy, plan.start, plan.is_goal, plan.mean_remaining, free_cost=free_action_cost(plan.offers), resolve_quantiles=False)
    return risk.mean.value if risk.success_probability.value == 1 else math.inf


def guide_violations(runs: Runs, case: Case, given: list[tuple[str, float]]) -> list[str]:
    """A guide's route is a valid policy, so the plan's cost with the guide's methods allowed is never above the guide's cost."""
    cost = runs.cost(case)
    return [f"{case.id}: the plan costs {cost.stated!r}, the guide ({order}) {mean!r}" for order, mean in given if not not_above(cost, Cost(mean, mean))]


def simulation_violations(runs: Runs, case: Case) -> list[str]:
    """The plan played by the simulator reaches the target, and its simulated mean agrees with the stated mean within the simulator's error.

    The plays end at the case's own target, read again from the case and not from the plan. A plan that stopped at a proved gap states
    the exact mean of the plan it returns (OR-32), so this comparison takes no gap.
    """
    plan = runs.plan(case)
    target = parse_target(case.generated.target_yaml, runs.data, source=f"<{case.id}>")
    played = dataclasses.replace(plan, target=target)
    clicks = verify(runs.data, played, runs=PILOT, seed=886).report.mean_steps  # the pilot only sizes the run: its costs are not read
    plays = int(max(PLAYS[0], min(PLAYS[1], CLICKS // max(clicks, 1.0))))
    result = verify(runs.data, played, runs=plays, seed=887)
    return [] if result.agrees else [f"{case.id}: {result.reason}"]


# -- planners broken on purpose -------------------------------------------------------------------------------------------------------


def tiers_upside_down(data: GameData, target):
    """`target` as a planner reads it that takes the tier ladder upside down: a leaf's tier or worse, where the target says or better."""

    def turned(leaf):
        if getattr(leaf, "tier_ok", None) is None:
            return leaf
        tiers = tiers_of(data, Item(target.base_id, target.item_level, Rarity.RARE))
        worst = max(tiers[mod] for mod in leaf.tier_ok if mod in tiers)
        return dataclasses.replace(leaf, tier_ok=frozenset(mod for mod in leaf.mod_ids if tiers.get(mod, 0) >= worst))

    return dataclasses.replace(target, requirements=tuple(turned(leaf) for leaf in target.requirements))


def understated(plan: Plan, share: float) -> Plan:
    """`plan` as a planner returns it that states `share` of the plan's mean cost."""
    values = dict(plan.solution.values)
    values[plan.start] = values[plan.start] * share
    return dataclasses.replace(plan, solution=dataclasses.replace(plan.solution, values=values))
