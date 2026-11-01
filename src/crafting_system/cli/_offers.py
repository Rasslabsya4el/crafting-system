"""The actions the planner may use, what one use of each takes, and what that costs at today's prices.

An `Offer` pairs an action of `actions` with the resources one use consumes, by their price-file
names. `offers_for` lists what the model offers for one target: a Chaos Orb, the Harvest reforge of
Lightning, every essence the item class takes, Remove Crafted Mods and the bench crafts whose mod
counts toward a requirement. Prices come from the price file (hand overrides on top); an offer with a
missing price is dropped and reported (ADR-0007), never guessed.
"""

import random
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from crafting_system.abstraction import Goal
from crafting_system.actions import Action, Reads, catalog, default_actions
from crafting_system.actions import without_ranges  # noqa: F401  (the report reads it from here)
from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.prices import CHAOS_ORB, PriceFile

RESTART = "restart"


@dataclass(frozen=True)
class Offer:
    """One action and what a use of it consumes.

    `resources` maps a price-file name to how many of it one use takes. `tag` is the guaranteed mod
    tag of a Harvest reforge and None for any other action.
    """

    label: str
    action: object
    resources: Mapping[str, int]
    tag: str | None = None
    shares: bool = True  # whether the report quotes a single-draw weight share (a Chaos Orb, a Harvest reforge)


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
    return Offer(label, action, dict(action.resources(data)), tag=adds.tag, shares=adds.single_draw)


def default_offers() -> tuple[Offer, ...]:
    """The two rerolls that need no game data: a Chaos Orb and the Harvest reforge of Lightning."""
    return tuple(offer_of(action, action.label()) for action in default_actions())


def price_offers(
    offers: Iterable[Offer], prices: PriceFile
) -> tuple[tuple[PricedOffer, ...], tuple[DroppedOffer, ...]]:
    """The offers whose resources all have a price, and those that do not (with the names missing).

    A Chaos Orb is worth 1 Chaos whether or not the file lists it.
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
            else:
                missing.append(name)
        if missing:
            dropped.append(DroppedOffer(offer.label, tuple(sorted(missing))))
        else:
            priced.append(PricedOffer(offer, sum(part[2] for part in parts), tuple(parts)))
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


def offers_for(data: GameData, goal: Goal, base_id: str, start_item: Item) -> OfferSet:
    """The actions the model offers for a target on `base_id`: the planner kinds of the catalog, then the filters below.

    Every action of the `planner` kinds of `actions.catalog` that can apply to the start item is offered
    (a Chaos Orb, the Harvest reforge of Lightning, every essence the item class takes, the bench), under
    its `label`; two with one label are told apart by their `variant`. A new method registered in the
    catalog is offered with no edit here. The filters, each over what an action declares (`Action.adds`,
    `Action.reads`):

    * An action that only adds named crafted mods (a bench craft) is offered ONLY WHEN A MOD IT ADDS
      COUNTS TOWARD ONE OF THE GOAL'S REQUIREMENTS (a leaf names it and does not refuse a crafted mod,
      `not_crafted`), AND ONLY WHILE EVERY OTHER OFFERED ACTION ERASES THE CRAFTED MODS (declares
      `Adds.keeps_crafted` False; the default True keeps every craft in play, so an action that keeps
      them needs no edit here). Reason: in this slice every other action (Chaos Orb, Harvest reforge, an
      essence, Remove Crafted Mods) removes the crafted mods, and without the multimod an item holds one crafted
      mod, so a craft that gives the goal nothing only takes a slot and costs currency; it can never
      lower the mean. Leaving it out is exact, and it keeps the state space small: each craft that
      clashes with a family makes that family its own kind, so all 141 ring crafts would grow R05 from
      76 to 13,172 states (ticket #60, PR #79). REVISIT when an action that adds or removes one mod
      without erasing the crafted mod lands (Exalted Orb and Annulment Orb, #67; metamods and the
      multimod, #68): then a crafted mod can block a family before an Exalted Orb, a craft with no goal
      contribution can pay off, and this rule no longer holds. The crafts left out are reported.
    * An action that adds named mods only for a target that wants them (`Adds.wanted_only`, an aspect beast, #147) is
      offered only when a mod it adds is named by a requirement of the goal, whatever the other actions do to crafted mods.
      It is left out and reported like a craft that counts for nothing.
    * An action that needs a crafted mod to be used on (`Reads.needs_crafted`, Remove Crafted Mods) is
      offered only when the start item holds one or another offered action adds one.
    """
    counting = {mod_id for leaf in goal.leaves if not leaf.not_crafted for mod_id in leaf.mod_ids}
    named = {mod_id for leaf in goal.leaves for mod_id in leaf.mod_ids}  # a `wanted_only` mod is no crafted one, so `not_crafted` does not hide it
    candidates = []
    left_out_unwanted: list[str] = []
    for action in catalog(data, start_item, planner_only=True):
        adds = action.adds(data, start_item)
        if adds.wanted_only and not (adds.named or frozenset()) & named:
            left_out_unwanted.append(action.label(data))
        else:
            candidates.append(action)
    # a craft that gives the goal nothing is useless while every other action erases the crafted mod
    erased_by_all = not any(
        action.adds(data, start_item).keeps_crafted for action in candidates if not _only_crafts(data, start_item, action)
    )
    chosen: list[Action] = []
    left_out_crafts: list[str] = []
    for action in candidates:
        if erased_by_all and _only_crafts(data, start_item, action):
            if not action.adds(data, start_item).named & counting:
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
    if left_out_crafts:
        left_out = (
            LeftOut(
                "its mod counts toward no requirement, so the craft only takes a slot and costs currency "
                "(exact while every other action erases crafted mods; see `offers_for`)",
                tuple(left_out_crafts),
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
