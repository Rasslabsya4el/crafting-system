"""Published odds that are the chance of an OUTCOME of one action, not a weight share (ticket #70).

R12's guide quotes a single-draw weight share (`_shares`). R04 and R14 quote what one use of an action does to an
item: "a Fracturing Orb fractures the Pierce 25% of the time", "an Orb of Annulment on 3 mods removes the Attack
Speed 1/3 of the time", "two Exalted Orbs force the two prefixes". Each is checked here on a concrete item the
guide describes: the action's own `outcomes` give the chance, which is formatted to the decimals the guide gives and
compared with it. A difference is recorded, not hidden (the planner's rules for the metamods can differ from what a
guide claims, ticket #68); `benchmark` never fails a route over it.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.abstraction import Goal
from crafting_system.actions import Action
from crafting_system.data import GameData
from crafting_system.items import ExplicitMod, Item, Rarity
from crafting_system.targets import Target

from ._offers import offers_for

FRACTURED = "fractured"  # the event: the result holds this mod fractured
REMOVED = "removed"  # the result no longer holds this mod
ADDS = "adds"  # one of these mods is new on the result


@dataclass(frozen=True)
class PublishedOutcome:
    """A chance a guide publishes: `event` of `mod_ids` when `action` is used on the item `on` (rare, the target's base).

    `held` are the mod ids the item holds (rolled at the low end of every range), `fractured` and `crafted` those of
    them that are fractured or crafted. `requirement` says the event in words, `published` is the guide's text with as
    many decimals as it gives ("25%", "33%").
    """

    action: str
    requirement: str
    on: str
    held: tuple[str, ...]
    event: str
    mod_ids: tuple[str, ...]
    published: str
    fractured: tuple[str, ...] = ()
    crafted: tuple[str, ...] = ()
    families: tuple[str, ...] = ()  # every mod of these families counts as well as `mod_ids`


def rolled(data: GameData, mod_id: str, *, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    """The mod `mod_id` with every stat at the low end of its range."""
    mod = data.mods[mod_id]
    return ExplicitMod(mod_id, 1, tuple(min(stat.min, stat.max) for stat in mod.stats), fractured=fractured, crafted=crafted)


def item_of(data: GameData, target: Target, odds: PublishedOutcome) -> Item:
    """The rare item `odds` describes, on the target's base, level and influences."""
    mods = tuple(
        rolled(data, mod_id, fractured=mod_id in odds.fractured, crafted=mod_id in odds.crafted) for mod_id in odds.held
    )
    return Item.build(
        data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.RARE, influences=target.start_item.influences, mods=mods
    )


def chance_of(data: GameData, outcomes, event: str, mod_ids: Iterable[str], families: Iterable[str] = ()) -> Fraction:
    """The exact chance of `event` on the mods `mod_ids` (and every mod of `families`) among the results of `outcomes`."""
    kinds = frozenset(families)
    wanted = frozenset(mod_ids) | {mod.id for mod in data.mods.values() if kinds.intersection(mod.families)}
    if event == ADDS:
        shown = outcomes.distribution(lambda mod: mod.id if mod.id in wanted else None)
        return sum((chance for outcome, chance in shown.items() if any(label is not None for label, _ in outcome)), Fraction(0))
    total = Fraction(0)
    for chance, part in outcomes.components:
        held = part.result.mods
        if event == FRACTURED and any(entry.fractured and entry.mod_id in wanted for entry in held):
            total += chance
        elif event == REMOVED and not wanted & {entry.mod_id for entry in held}:
            total += chance
    return total


def published_outcomes(data: GameData, target: Target, published: Iterable[PublishedOutcome]) -> list[dict]:
    """Each published outcome chance recomputed from the action's outcomes, formatted to the guide's decimals, and compared."""
    published = list(published)
    if not published:
        return []
    offers = {offer.label: offer.action for offer in offers_for(data, Goal.from_target(target), target.base_id, target.start_item, target.actions).offers}
    found = []
    for odds in published:
        action: Action = offers[odds.action]
        share = chance_of(data, action.outcomes(data, item_of(data, target, odds)), odds.event, odds.mod_ids, odds.families)
        decimals = len(odds.published.rstrip("%").partition(".")[2])
        computed = f"{float(share) * 100:.{decimals}f}%"
        found.append(
            {
                "action": odds.action,
                "requirement": odds.requirement,
                "on": odds.on,
                "published": odds.published,
                "computed": computed,
                "matches": computed == odds.published,
                "wanted_weight": None,
                "candidate_weight": None,
                "share": float(share),
            }
        )
    return found
