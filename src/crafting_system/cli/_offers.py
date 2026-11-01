"""The actions the planner may use, what one use of each takes, and what that costs at today's prices.

An `Offer` pairs an action of `actions` with the resources one use consumes, by their price-file
names. `offers_for` lists what the model offers for one target: a Chaos Orb, the Harvest reforge of
Lightning, every essence the item class takes, Remove Crafted Mods and the bench crafts whose mod
counts toward a requirement. Prices come from the price file (hand overrides on top); an offer with a
missing price is dropped and reported (ADR-0007), never guessed.
"""

import random
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, replace

from crafting_system.abstraction import Goal
from crafting_system.actions import Action, ActionError, Axis, Need, Reads, catalog, default_actions, drawable_mod_ids, kinds
from crafting_system.actions import without_ranges  # noqa: F401  (the report reads it from here)
from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.prices import CHAOS_ORB, DIVINE_ORB, PriceFile

RESTART = "restart"
FREE_ACTION_SHARE = 1e-6  # what an action that consumes nothing costs, as a share of the cheapest offer that costs something (ADR-0026)


@dataclass(frozen=True)
class Offer:
    """One action and what a use of it consumes.

    `resources` maps a price-file name to how many of it one use takes. `tag` is the guaranteed mod
    tag of a Harvest reforge and None for any other action. `inputs` are the other items one use consumes on the
    start item (`Action.inputs`, ADR-0022) and `axes` the rule axes the action reads (`Action.rule_axes`, ADR-0033);
    both are empty for an action that has neither, which is every action of batches B1 and B2. The inputs of other
    states are asked of the action there (`Abstraction.inputs`).
    """

    label: str
    action: object
    resources: Mapping[str, int]
    tag: str | None = None
    shares: bool = True  # whether the report quotes a single-draw weight share (a Chaos Orb, a Harvest reforge)
    inputs: tuple[Need, ...] = ()
    axes: tuple[Axis, ...] = ()


@dataclass(frozen=True)
class PricedOffer:
    """An offer with the price of one use, in Chaos Orbs, and where each resource price came from."""

    offer: Offer
    cost: float
    parts: tuple[tuple[str, int, float, str], ...]  # (resource, count, chaos for all of them, source)

    @property
    def label(self) -> str:
        return self.offer.label


@dataclass(frozen=True)
class DroppedOffer:
    """An offer left out because some resource has no price."""

    label: str
    missing: tuple[str, ...]


def offer_of(action: Action, label: str, data: GameData | None = None, item: Item | None = None) -> Offer:
    """The offer of `action` under `label`: its resources, and whether the report quotes a single-draw share (with its tag).

    `data` and `item` only matter to an action whose resources or additions depend on them (an essence, a bench craft).
    """
    adds = action.adds(data, item)
    inputs = action.inputs(data, item) if data is not None else ()
    axes = action.rule_axes(data) if data is not None else ()
    return Offer(label, action, dict(action.resources(data)), tag=adds.tag, shares=adds.single_draw, inputs=inputs, axes=axes)


def default_offers() -> tuple[Offer, ...]:
    """The two rerolls that need no game data: a Chaos Orb and the Harvest reforge of Lightning."""
    return tuple(offer_of(action, action.label()) for action in default_actions())


def price_offers(
    offers: Iterable[Offer], prices: PriceFile
) -> tuple[tuple[PricedOffer, ...], tuple[DroppedOffer, ...]]:
    """The offers whose resources all have a price, and those that do not (with the names missing).

    A Chaos Orb is worth 1 Chaos whether or not the file lists it, and a Divine Orb the file's `chaos_per_divine` when
    it lists no price for it (a Divine Orb is the unit of that rate, ticket #71).

    An action that consumes nothing (an unveil, a pick: `unveil.is_free_and_in_place`) costs `FREE_ACTION_SHARE` of the cheapest
    offer that costs something, because the solver needs a positive cost on every action (ADR-0026, ticket #145). The share is a
    compromise: a use must stay negligible next to the value of a route (a route of a million Chaos is moved by a Chaos at most),
    yet a cycle of free steps and paid steps (veil, unveil, pick, veil again) lies in one component of the solver, whose certified
    error is about `epsilon * value / g` for the smallest constant term `g` of the component, here the free step's cost. With a
    share of 1e-6 a route of a few thousand Chaos is certified to about 1e-9 (`tests/test_cli_free_actions.py`).
    """
    priced: list[PricedOffer] = []
    dropped: list[DroppedOffer] = []
    for offer in offers:
        parts = []
        missing = []
        for name, count in offer.resources.items():
            if name == CHAOS_ORB:
                parts.append((name, count, float(count), "fixed"))
            elif name in prices.prices:
                entry = prices.prices[name]
                parts.append((name, count, count * entry.chaos, entry.source))
            elif name == DIVINE_ORB:
                parts.append((name, count, count * prices.chaos_per_divine, "rate"))
            else:
                missing.append(name)
        if missing:
            dropped.append(DroppedOffer(offer.label, tuple(sorted(missing))))
        else:
            priced.append(PricedOffer(offer, sum(part[2] for part in parts), tuple(parts)))
    if any(not entry.offer.resources for entry in priced):
        paid = [entry.cost for entry in priced if entry.cost > 0]
        free_cost = FREE_ACTION_SHARE * min(paid) if paid else FREE_ACTION_SHARE
        priced = [replace(entry, cost=free_cost) if not entry.offer.resources else entry for entry in priced]
    return tuple(priced), tuple(dropped)


# --- what the model offers for one target ------------------------------------------------------------


@dataclass(frozen=True)
class LeftOut:
    """Offers the model leaves out on purpose, with the reason; unlike a dropped offer, nothing is missing."""

    reason: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class OfferSet:
    """The offers for one target and the ones left out because they cannot matter."""

    offers: tuple[Offer, ...]
    left_out: tuple[LeftOut, ...]


@dataclass(frozen=True)
class BuyStartItem(Action):
    """Buy the start item again: the item comes back as the target's start item, whatever it was.

    It is the restart of ADR-0011's buy action. It meets the contract only as far as the simulator and
    the planner need (`outcomes(data, item).sample(rng)`, the label, and that it reads nothing of the
    item, which it replaces); the planner gives it the start state and prices it with the start item.
    """

    item: Item

    def label(self, data: GameData | None = None) -> str:
        return RESTART

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {}

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing()

    def outcomes(self, data: GameData, item: Item) -> "BuyStartItem":  # type: ignore[override]
        return self

    def sample(self, rng: random.Random) -> Item:
        return self.item


def offers_for(
    data: GameData, goal: Goal, base_id: str, start_item: Item, kinds_named: Collection[str] | None = None
) -> OfferSet:
    """The actions the model offers for a target on `base_id`: the planner kinds of the catalog, then the filters below.

    Every action of the `planner` kinds of `actions.catalog` that can apply to the start item is offered
    (a Chaos Orb, the Harvest reforge of Lightning, every essence the item class takes, the bench), under
    its `label`; two with one label are told apart by their `variant`. A new method registered in the
    catalog is offered with no edit here. The filters, each over what an action declares (`Action.adds`,
    `Action.reads`):

    * An action that only adds named crafted mods (a bench craft) is offered ONLY WHEN A MOD IT ADDS
      COUNTS TOWARD ONE OF THE GOAL'S REQUIREMENTS (a leaf names it and does not refuse a crafted mod,
      `not_crafted`). While EVERY OTHER OFFERED ACTION ERASES THE CRAFTED MODS (declares
      `Adds.keeps_crafted` False; the default True keeps every craft in play, so an action that keeps
      them needs no edit here) this is exact: every other action (Chaos Orb, Harvest reforge, an
      essence, Remove Crafted Mods) removes the crafted mods, and without the multimod an item holds one crafted
      mod, so a craft that gives the goal nothing only takes a slot and costs currency; it can never
      lower the mean. Leaving it out keeps the state space small: each craft that
      clashes with a family makes that family its own kind, so all 141 ring crafts would grow R05 from
      76 to 13,172 states (ticket #60, PR #79). When an offered action keeps the crafted mod (Augmentation
      and Regal Orb, #66) a craft that counts for nothing could still pay off: it takes a slot or clears a
      family out of the pool before the next orb. It is left out all the same, because every belt craft in
      the model is 100 offers and the states grow past what a plan can hold; the plan is then the cheapest
      among the offered crafts, not a proof against the rest (the report says so). REVISIT with the
      Exalted Orb and Annulment Orb (#67) and the metamods and the multimod (#68). The crafts left out are reported.
    * With `kinds_named` (the target's `actions:` key) only the kinds of those names are listed at all and the filters
      below see only them. That is the target's choice, not a proof: the plan is the cheapest among the named kinds,
      and the kinds not named are listed in `left_out`. A name may also be the label of ONE action (`Essence of
      Insanity`, `Bench craft Cannot roll Attack Modifiers`): that action is offered whatever the filters below say
      (a metamod craft counts toward no requirement and would be left out), and only the actions named that way are
      listed of a kind that is not named as a whole. An `opt_in` kind (Exalted Orb, Annulment, Fracturing
      Orb) is offered only when named, as a kind or by its label (ticket #70).
    * An action that adds named mods only for a target that wants them (`Adds.wanted_only`, an aspect beast, #147) is
      offered only when a mod it adds is named by a requirement of the goal, whatever the other actions do to crafted mods.
      It is left out and reported like a craft that counts for nothing.
    * An action that needs a crafted mod to be used on (`Reads.needs_crafted`, Remove Crafted Mods) is
      offered only when the start item holds one or another offered action adds one.
    * An action that only changes rolled values (`Adds.needs_roll_limit`, a Divine Orb, #71) is offered only when the goal has a
      roll limit (a leaf with a `min_roll` that asks for some value) on a mod that can occur on the item: the start item
      holds it, a draw of its pool can give it, or another candidate adds it by name. Without such a limit no value
      matters to the goal, so the orb would only cost currency. It is left out; the report names it only when the goal has a
      roll limit and every one is on a mod that cannot occur (a target without a roll limit needs no word about it).
    * An action that corrupts the item (`Adds.corrupts`, a Vaal Orb, the Locus) is offered only when the goal asks for a corrupted
      implicit or allows a corrupted item (`Goal.takes_corrupted`): an item never arrives corrupted unasked (ADR-0036). For any
      other target it is absent from the offers and the report says nothing about it. Which states offer it, for a target that
      asks, is `solver_actions`' business (`_prune.py`). One that also declares `Adds.asked_only` (a fossil set with the Bloodstained
      Fossil: its reroll exists without the corruption) is offered only when the goal asks for a corrupted implicit, not when it
      merely allows a corrupted item (ADR-0038).
    """
    counting = {mod_id for leaf in goal.leaves if not leaf.not_crafted for mod_id in leaf.mod_ids}
    kind_names, label_names = _split_names(data, start_item, kinds_named)
    named = {mod_id for leaf in goal.leaves for mod_id in leaf.mod_ids}  # a `wanted_only` mod is no crafted one, so `not_crafted` does not hide it
    candidates = []
    left_out_unwanted: list[str] = []
    listed = _listed(data, start_item, kind_names, label_names)
    roll_matters = _roll_limit_can_matter(data, goal, start_item, listed)
    left_out_rolls: list[str] = []
    for action in listed:
        adds = action.adds(data, start_item)
        if adds.corrupts and (not goal.takes_corrupted or (adds.asked_only and not goal.asks_corrupted)):
            continue  # an item never arrives corrupted unasked, and the report does not mention what the target could never use
        if adds.wanted_only and not (adds.named or frozenset()) & named and action.label(data) not in label_names:
            left_out_unwanted.append(action.label(data))
        elif adds.needs_roll_limit and not roll_matters:
            left_out_rolls.append(action.label(data))
        else:
            candidates.append(action)
    # a craft that gives the goal nothing is useless while every other action erases the crafted mod
    erased_by_all = not any(
        action.adds(data, start_item).keeps_crafted for action in candidates if not _only_crafts(data, start_item, action)
    )
    chosen: list[Action] = []
    left_out_crafts: list[str] = []
    for action in candidates:
        if (
            _only_crafts(data, start_item, action)
            and not action.adds(data, start_item).named & counting
            and action.label(data) not in label_names
        ):
            left_out_crafts.append(action.label(data))
            continue
        chosen.append(action)
    chosen = usable_actions(data, start_item, chosen)

    groups: dict[str, list[Action]] = defaultdict(list)
    for action in chosen:
        groups[action.label(data)].append(action)
    offers = []
    for label, actions in groups.items():
        variants = [action.variant for action in actions]
        if len(set(variants)) != len(variants) or "" in variants:
            variants = [str(number) for number in range(1, len(actions) + 1)]
        for action, variant in zip(actions, variants):
            offers.append(offer_of(action, label if len(actions) == 1 else f"{label} [{variant}]", data, start_item))

    left_out = ()
    if kinds_named is not None:
        # a kind that only corrupts is not mentioned for a target that takes no corrupted item: nothing of it could ever be used
        skipped = tuple(
            entry.name
            for entry in kinds(planner_only=True)
            if entry.name not in kind_names and not (entry.corrupting and not goal.takes_corrupted)
        )
        if skipped:
            left_out += (
                LeftOut("the target's `actions:` does not name these kinds, so the plan is the cheapest among the named ones", skipped),
            )
    if left_out_crafts:
        reason = (
            "its mod counts toward no requirement, so the craft only takes a slot and costs currency "
            "(exact while every other action erases crafted mods; see `offers_for`)"
            if erased_by_all
            else "its mod counts toward no requirement; an offered action keeps crafted mods, so a craft could still "
            "pay off by clearing a family from the pool, and the plan is the cheapest among the offered crafts only"
        )
        left_out += (LeftOut(reason, tuple(left_out_crafts)),)
    if left_out_rolls and any(leaf.has_roll_limit for leaf in goal.leaves):  # a target without a roll limit needs no word about it
        left_out = (
            *left_out,
            LeftOut(
                "it only changes rolled values and the roll limit of the target is on a mod that cannot occur on the item, "
                "so it would only cost currency",
                tuple(left_out_rolls),
            ),
        )
    if left_out_unwanted:
        left_out = (
            *left_out,
            LeftOut(
                "it adds one fixed mod and the target wants none of those, so it only takes a slot and costs currency",
                tuple(left_out_unwanted),
            ),
        )
    return OfferSet(tuple(offers), left_out)


def _split_names(data: GameData, start_item: Item, names: Collection[str] | None) -> tuple[frozenset[str] | None, frozenset[str]]:
    """The names of a target's `actions:` as (kinds, labels): a name is a kind of the catalog, else the label of one action.

    No names (`None`) is every kind offered by default and no label. A name that is neither is an error, as is a
    kind the planner cannot use yet.
    """
    if names is None:
        return None, frozenset()
    usable = {entry.name for entry in kinds(planner_only=True)}
    exist = {entry.name for entry in kinds()}
    kind_names = {name for name in names if name in exist}
    unready = sorted(kind_names - usable)
    labels = {action.label(data) for action in catalog(data, start_item, planner_only=True, names=usable)}
    unknown = sorted(name for name in names if name not in exist and name not in labels)
    problems = []
    if unknown:
        problems.append(f"unknown action kind(s) or action label(s) {', '.join(unknown)}")
    if unready:
        problems.append(f"action kind(s) {', '.join(unready)} cannot be used by the planner yet")
    if problems:
        raise ValueError("; ".join(problems) + f"; the kinds the planner can use are {', '.join(sorted(usable))}")
    return frozenset(kind_names), frozenset(name for name in names if name not in exist)


def _listed(data: GameData, start_item: Item, kind_names: frozenset[str] | None, label_names: frozenset[str]) -> list[Action]:
    """The planner actions of the kinds named, plus those named by label (any planner kind, default or not)."""
    found = list(catalog(data, start_item, planner_only=True, names=kind_names))
    if label_names:
        usable = {entry.name for entry in kinds(planner_only=True)}
        extra = [a for a in catalog(data, start_item, planner_only=True, names=usable) if a.label(data) in label_names]
        found.extend(action for action in extra if action not in found)
    return found


def _roll_limit_can_matter(data: GameData, goal: Goal, start_item: Item, listed: Iterable[Action]) -> bool:
    """Whether a roll limit of the goal is on a mod that can occur: held by the start item, drawable on it, or added by name."""
    limited = {mod_id for leaf in goal.leaves if leaf.has_roll_limit for mod_id in leaf.mod_ids}
    if not limited:
        return False
    if limited & {entry.mod_id for entry in start_item.mods}:
        return True
    if any(limited & (action.adds(data, start_item).named or frozenset()) for action in listed):
        return True
    try:
        return bool(limited & drawable_mod_ids(data, start_item))
    except ActionError:  # a pool the model cannot build: no proof the mod is out of reach, so keep the orb
        return True


def _only_crafts(data: GameData, item: Item, action: Action) -> bool:
    """Whether the action only adds mods it names, as crafted mods (a bench craft)."""
    adds = action.adds(data, item)
    return adds.crafted and not adds.draws and adds.named is not None


def usable_actions(data: GameData, start_item: Item, actions: Iterable[Action]) -> list[Action]:
    """`actions` without those that need a crafted mod when neither the start item nor another of them gives one."""
    actions = list(actions)
    if start_item.crafted_mods or any(action.adds(data, start_item).crafted for action in actions):
        return actions
    return [action for action in actions if not action.reads(data).needs_crafted]
