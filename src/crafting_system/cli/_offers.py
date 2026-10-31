"""The actions the planner may use, what one use of each takes, and what that costs at today's prices.

An `Offer` pairs an action of `actions` with the resources one use consumes, by their price-file
names. `offers_for` lists what the model offers for one target: a Chaos Orb, the Harvest reforge of
Lightning, every essence the item class takes, Remove Crafted Mods and the bench crafts whose mod
counts toward a requirement. Prices come from the price file (hand overrides on top); an offer with a
missing price is dropped and reported (ADR-0007), never guessed.
"""

import random
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from crafting_system.abstraction import Goal
from crafting_system.actions import (
    ApplyEssence,
    BenchCraft,
    ChaosOrb,
    HarvestReforge,
    RemoveCraftedMods,
    bench_crafts,
)
from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.prices import CHAOS_ORB, PriceFile
from crafting_system.rules import get_rule

TAGGED_RARE_REFORGE_EXISTS = get_rule("harvest_reforge.tagged_rare_reforge_exists")
LIFEFORCE_COST = get_rule("harvest_reforge.lifeforce_cost")
NORMAL_ONLY_UP_TO_LEVEL = get_rule("essence.normal_only_up_to_level")
DAGGER_STAFF_TAKE_CLASS_MODS = get_rule("essence.dagger_staff_take_class_mods")
DESOLATION_IS_NOT_A_B1_ACTION = get_rule("essence.desolation_is_not_a_b1_action")

RESTART = "restart"
REMOVE_CRAFTED_MODS = "Remove Crafted Mods"


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


def default_offers() -> tuple[Offer, ...]:
    """The two rerolls that need no game data: a Chaos Orb and the Harvest reforge of Lightning."""
    return (
        Offer("Chaos Orb", ChaosOrb(), {CHAOS_ORB: 1}),
        Offer(
            "Harvest Reforge Lightning",
            HarvestReforge("lightning"),
            dict(LIFEFORCE_COST.value["lightning"]),
            tag=TAGGED_RARE_REFORGE_EXISTS.value["lightning"],
        ),
    )


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
class BuyStartItem:
    """Buy the start item again: the item comes back as the target's start item, whatever it was.

    It is the restart of ADR-0011's buy action. It is an `actions`-shaped object (`outcomes(data,
    item).sample(rng)`) so that `--verify` can simulate it; the planner gives it the start state.
    """

    item: Item

    def outcomes(self, data: GameData, item: Item) -> "BuyStartItem":
        return self

    def sample(self, rng: random.Random) -> Item:
        return self.item


def without_ranges(text: str) -> str:
    """A mod text with its roll ranges as `#`: "+(6-11) to Strength" -> "+# to Strength"."""
    return re.sub(r"\(-?\d+(?:\.\d+)?--?\d+(?:\.\d+)?\)", "#", text)


def _one_line(text: str) -> str:
    """A mod text on one line: some mods read over two lines, such as a Life craft that also regenerates Mana."""
    return " / ".join(part.strip() for part in text.splitlines() if part.strip())


def offers_for(data: GameData, goal: Goal, base_id: str, start_item: Item) -> OfferSet:
    """The actions the model offers for a target on `base_id`, and the bench crafts it leaves out.

    * A Chaos Orb, the Harvest reforge of Lightning, every essence the item class takes (the ones of
      level 1 to 4 work on a normal item only, so they are listed only when the start item is normal;
      Essence of Desolation and the corruption-only essences are not B1 actions).
    * The bench: Remove Crafted Mods, and a `BenchCraft` ONLY WHEN ITS MOD COUNTS TOWARD ONE OF THE
      GOAL'S REQUIREMENTS. Reason: in this slice every other action (Chaos Orb, Harvest reforge, an
      essence, Remove Crafted Mods) removes the crafted mods, and without the multimod an item holds
      one crafted mod, so a craft that gives the goal nothing only takes a slot and costs currency; it
      can never lower the mean. Leaving it out is exact, and it keeps the state space small: each craft
      that clashes with a family makes that family its own kind, so all 141 ring crafts would grow
      R05 from 76 to 13,172 states (ticket #60, PR #79). REVISIT when an action that adds or removes
      one mod without erasing the crafted mod lands (Exalted Orb and Annulment Orb, #67; metamods and
      the multimod, #68): then a crafted mod can block a family before an Exalted Orb, a craft with no
      goal contribution can pay off, and this rule no longer holds.

    A craft counts when some requirement leaf names its mod and does not refuse a crafted mod
    (`not_crafted`). A craft the bench does not offer for the item class is not listed at all.
    """
    base = data.base_items[base_id]
    offers = [*default_offers()]

    def forced_mod(essence) -> str | None:
        mod_id = essence.mod_for(base.item_class)
        if mod_id is None:
            mod_id = essence.mod_for(DAGGER_STAFF_TAKE_CLASS_MODS.value.get(base.item_class, base.item_class))
        return mod_id

    for essence in data.essences.values():
        if essence.is_corruption_only or essence.name == DESOLATION_IS_NOT_A_B1_ACTION.value:
            continue
        if essence.level <= NORMAL_ONLY_UP_TO_LEVEL.value and start_item.rarity is not Rarity.NORMAL:
            continue
        if forced_mod(essence) is None:
            continue
        offers.append(Offer(essence.name, ApplyEssence(essence.name), {essence.name: 1}, shares=False))

    wanted: dict[str, list[BenchCraft]] = {}
    left_out_crafts: list[str] = []
    counting = {mod_id for leaf in goal.leaves if not leaf.not_crafted for mod_id in leaf.mod_ids}
    for craft in bench_crafts(data):
        option = craft.option(data)
        if base.item_class not in option.item_classes:
            continue
        mod = data.mods[craft.mod_id]
        label = f"Bench craft {_one_line(without_ranges(mod.text or mod.name))}"
        if craft.mod_id in counting:
            wanted.setdefault(label, []).append(craft)
        else:
            left_out_crafts.append(label)
    for label, crafts in wanted.items():
        for craft in crafts:
            name = label if len(crafts) == 1 else f"{label} [{craft.mod_id}]"
            offers.append(Offer(name, craft, {c.currency: c.count for c in craft.cost(data)}, shares=False))
    if wanted or start_item.crafted_mods:
        removal = RemoveCraftedMods()
        offers.append(Offer(REMOVE_CRAFTED_MODS, removal, {c.currency: c.count for c in removal.cost(data)}, shares=False))

    left_out = ()
    if left_out_crafts:
        left_out = (
            LeftOut(
                "its mod counts toward no requirement, so the craft only takes a slot and costs currency "
                "(exact while every other action erases crafted mods; see `offers_for`)",
                tuple(left_out_crafts),
            ),
        )
    return OfferSet(tuple(offers), left_out)
