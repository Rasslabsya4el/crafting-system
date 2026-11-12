"""The Orb of Unravelling: uses every Memory Strand of the item to try to raise its explicit mods in place (ADR-0044, ticket #281).

**Inputs.** An item that holds at least one strand and at least one eligible mod, not corrupted and not an unopened listing (the one
item of the model whose mods are not looked at yet, `Item.unopened`: the game refuses an unidentified item,
`memory_strands.unravelling_needs_identified_item`). A mirrored item is not in the item model. The kind is `needs_strands` (ADR-0040).

**Eligible mods.** An explicit mod of the item's own domain that is itself a mod of the item's pool (the whole pool of its base, item
level and influences, as if the item held no explicit mod) and has a higher tier there. Left as they are: a crafted mod
(`memory_strands.unravelling_limits`), a fractured mod and a veiled one (`memory_strands.unravelling_skips_fractured_and_veiled`,
approximate), a mod at the top of its tier table at this item level, and a mod the pool does not hold (an essence-only or a delve mod:
the emulator gives those another form of the chance that no source tests, `memory_strands.unravelling_side_weight_is_whole_pool`). The
`Prefixes` and `Suffixes Cannot Be Changed` metamods do not protect a mod (`memory_strands.unravelling_ignores_metamods`). An influence
mod rises among the regular tiers of its own table; an Elevated mod has no weight in the pool, so it is never a destination
(`memory_strands.unravelling_limits`).

**The chance of one mod** is `min(1, s * W_up / (2 * W_side))` (`memory_strands.unravelling_chance_model`): `s` the strands before the
craft, `W_up` the summed pool weight of the tiers above the mod in its table (its mod type and side), `W_side` the total weight of the
whole pool of its side (`memory_strands.unravelling_side_weight_is_whole_pool`). Each mod is tried on its own, so several may rise in one
use and none may (`memory_strands.unravelling_effect`).

**The destination** of a mod that rises is one of those higher tiers, by a weight (`Destination`): the plan reads the cumulative weight,
the tier's own weight plus the weights of the tiers above it (reading B, `memory_strands.unravelling_destination_tier`, approximate); the
rank reading (A: the tier's weight times 1 for the top tier, 2 for the second, ...) is kept for the published wand test only. The sheet
fit rejected A (ADR-0044, amendment of #274), so the two readings are no rule axis: an action is built with one, and the catalog gives the
plan's. The destination is not cut by the strands (`memory_strands.unravelling_destination_not_cut`).

**The count** becomes 0 (`StrandUse.spending_all`): the spend is applied around `outcomes` like every spend (`strand_use.py`), and the
declaration says that the odds read the count. The result is a finite list of items, the product over the eligible mods of "stays" or
"rises to this tier", each raised mod at the lowest values of its new tier (`sample` rolls them). The compressed state must name each mod of
the item by id to know its tier, so `reads` names every family by mod (`Reads.by_mod`), as the Harvest swaps do for theirs (#149).
"""

import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from fractions import Fraction
from itertools import product

from crafting_system.data import GameData, Mod
from crafting_system.items import ExplicitMod, Item, Side
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError
from .finite import Finite
from .pool import pool_candidates
from .strand_use import StrandUse

__all__ = [
    "Destination",
    "OrbOfUnravelling",
    "PLAN_DESTINATION",
    "destination_shares",
    "unravel_chance",
]

EFFECT = get_rule("memory_strands.unravelling_effect")
LIMITS = get_rule("memory_strands.unravelling_limits")
IGNORES_METAMODS = get_rule("memory_strands.unravelling_ignores_metamods")
NEEDS_IDENTIFIED = get_rule("memory_strands.unravelling_needs_identified_item")
SKIPS_FRACTURED_AND_VEILED = get_rule("memory_strands.unravelling_skips_fractured_and_veiled")
CHANCE_MODEL = get_rule("memory_strands.unravelling_chance_model")
SIDE_WEIGHT = get_rule("memory_strands.unravelling_side_weight_is_whole_pool")
DESTINATION_TIER = get_rule("memory_strands.unravelling_destination_tier")
DESTINATION_NOT_CUT = get_rule("memory_strands.unravelling_destination_not_cut")
COST = get_rule("orb_of_unravelling.cost")

ONE = Fraction(1)
ZERO = Fraction(0)


class Destination(StrEnum):
    """How a raised mod's new tier is drawn among the tiers above it (ADR-0044, "The destination")."""

    RANK = "rank"  # reading A: the tier's weight times its rank from the top (1, 2, 3, ...); rejected by the sheet fit
    CUMULATIVE = "cumulative"  # reading B: the tier's own weight plus the weights of the tiers above it; the plan


PLAN_DESTINATION = Destination(DESTINATION_TIER.value["reading"])


def unravel_chance(strands: int, w_up: Fraction, w_side: Fraction) -> Fraction:
    """The chance that one mod rises: `min(1, strands * w_up / (divisor * w_side))`, exact (`memory_strands.unravelling_chance_model`).

    0 when `w_up` is 0 (the mod is at the top of its table). Raises `ValueError` for a count below 0, a negative `w_up` or a side weight
    that is not positive.
    """
    if type(strands) is not int or strands < 0:
        raise ValueError(f"a strand count is a whole number from 0, got {strands!r}")
    if w_up < 0 or w_side <= 0:
        raise ValueError(f"the weights of an Unravelling chance are W_up >= 0 and W_side > 0, got {w_up!r} and {w_side!r}")
    divisor = Fraction(CHANCE_MODEL.value["divisor"])
    return min(ONE, Fraction(strands) * Fraction(w_up) / (divisor * Fraction(w_side)))


def destination_shares(weights: Sequence[Fraction], reading: Destination = PLAN_DESTINATION) -> tuple[Fraction, ...]:
    """The chance of each higher tier, given their pool weights from the top tier down; they sum to exactly 1.

    `CUMULATIVE`: a tier weighs its own weight plus the weights of the tiers above it. `RANK`: a tier weighs its own weight times its rank
    from the top (1 for the top tier). Raises `ValueError` for no tier or a weight that is not positive.
    """
    if not weights or any(weight <= 0 for weight in weights):
        raise ValueError(f"a destination needs at least one higher tier, each of positive weight: {weights!r}")
    reading = Destination(reading)
    if reading is Destination.CUMULATIVE:
        scores, running = [], ZERO
        for weight in weights:
            running += Fraction(weight)
            scores.append(running)
    else:
        scores = [Fraction(weight) * rank for rank, weight in enumerate(weights, start=1)]
    total = sum(scores, ZERO)
    return tuple(score / total for score in scores)


@dataclass(frozen=True)
class _Table:
    """The whole pool of an item's base, level and influences, as an Unravelling reads it: side totals and the tiers of each mod type."""

    side_weight: Mapping[str, Fraction]
    tiers: Mapping[tuple[str, str], tuple[tuple[Mod, Fraction], ...]]  # (mod type, side) -> its pool mods, highest required level first
    held: frozenset[str]  # the ids of the mods of the pool

    def upper(self, mod: Mod) -> tuple[tuple[Mod, Fraction], ...]:
        """The tiers above `mod` in its table, top first: the pool mods of its type and side with a higher required level."""
        return tuple(entry for entry in self.tiers.get((mod.type, mod.generation_type), ()) if entry[0].required_level > mod.required_level)


def _table(data: GameData, item: Item) -> _Table:
    bare = item.changed(data, mods=(), veil_offer=())  # the whole pool, as if the item held no explicit mod
    totals: dict[str, Fraction] = defaultdict(Fraction)
    groups: dict[tuple[str, str], list[tuple[Mod, Fraction]]] = defaultdict(list)
    for candidate in pool_candidates(data, bare):
        totals[candidate.side.value] += candidate.weight
        groups[(candidate.mod.type, candidate.side.value)].append((candidate.mod, candidate.weight))
    tiers = {key: tuple(sorted(found, key=lambda entry: (-entry[0].required_level, entry[0].id))) for key, found in groups.items()}
    held = frozenset(mod.id for found in groups.values() for mod, _ in found)
    return _Table(dict(totals), tiers, held)


def _lowest(mod: Mod) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in mod.stats)


@dataclass(frozen=True, eq=False)
class Unravelled(Finite):
    """The items an Unravelling can leave: a `Finite` whose `sample` rolls the values of each raised mod inside its new tier's range."""

    def sample(self, rng: random.Random) -> Item:
        result = super().sample(rng)
        held = {entry.mod_id for entry in self.given.mods}
        mods = tuple(
            entry
            if entry.mod_id in held
            else replace(
                entry,
                values=tuple(rng.randint(min(stat.min, stat.max), max(stat.min, stat.max)) for stat in self.data.mods[entry.mod_id].stats),
            )
            for entry in result.mods
        )
        return result.changed(self.data, mods=mods)


@dataclass(frozen=True)
class OrbOfUnravelling(Action):
    """One Orb of Unravelling; `destination` is the reading of the new tier (the plan's by default, see the module docstring)."""

    destination: Destination = PLAN_DESTINATION

    def __post_init__(self) -> None:
        object.__setattr__(self, "destination", Destination(self.destination))

    @property
    def variant(self) -> str:
        return "" if self.destination is PLAN_DESTINATION else str(self.destination)

    def label(self, data: GameData | None = None) -> str:
        return "Orb of Unravelling"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.spending_all(EFFECT)  # every strand is used; the odds read the count; no draw is cut (unravelling_destination_not_cut)

    def reads(self, data: GameData) -> Reads:
        # The chance and the destination of a mod depend on its tier, so every family the item can hold is told apart by mod; the
        # implicits, the quality, the offer, the enchantment and the sockets are not read.
        return Reads(junk=True, families=None, by_mod=_rollable_families(data))

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds()  # it changes mods for other tiers of themselves and leaves the implicits, the quality and the offer alone

    def eligible(self, data: GameData, item: Item) -> tuple[tuple[ExplicitMod, Fraction, tuple[tuple[Mod, Fraction], ...]], ...]:
        """Each eligible mod of `item` with its chance to rise at the item's count and its destinations (mod, chance) top first."""
        table = _table(data, item)
        domain = data.base_items[item.base_id].domain
        found = []
        for entry in item.mods:
            mod = data.mods[entry.mod_id]
            if entry.fractured or entry.crafted or mod.domain != domain or entry.mod_id not in table.held:
                continue  # fractured, crafted, veiled (domain `veiled`), essence-only or delve: never raised
            upper = table.upper(mod)
            if not upper:
                continue  # the top of its table at this item level (an Elevated tier has no weight in the pool)
            w_up = sum((weight for _, weight in upper), ZERO)
            chance = unravel_chance(item.memory_strands, w_up, table.side_weight[mod.generation_type])
            shares = destination_shares([weight for _, weight in upper], self.destination)
            found.append((entry, chance, tuple((target, share) for (target, _), share in zip(upper, shares))))
        return tuple(found)

    def outcomes(self, data: GameData, item: Item) -> Unravelled:
        """Every item one use can leave on `item`, with its chance: each eligible mod stays or rises to one of its higher tiers.

        Raises `NotApplicableError` for an unopened listing (unidentified), a corrupted item, an item with no strand and an item with no
        eligible mod.
        """
        if item.unopened:
            raise NotApplicableError("the item is not identified yet (a bought listing not opened), and an Orb of Unravelling needs an identified item")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Orb of Unravelling")
        if item.memory_strands < 1:
            raise NotApplicableError("the item holds no Memory Strand, and an Orb of Unravelling needs at least one")
        eligible = self.eligible(data, item)
        if not eligible:
            raise NotApplicableError(
                "an Orb of Unravelling cannot be used here: no mod of the item that is not crafted, fractured or veiled has a higher tier"
            )
        choices = []
        for entry, chance, targets in eligible:
            options: list[tuple[Fraction, ExplicitMod | None]] = [(ONE - chance, None)] if chance < 1 else []
            options += [(chance * share, ExplicitMod(target.id, _lowest(target))) for target, share in targets]
            choices.append([(entry, option) for option in options])
        results = []
        for picks in product(*choices):
            probability, raised = ONE, {}
            for entry, (share, new) in picks:
                probability *= share
                if new is not None:
                    raised[entry.mod_id] = new
            mods = tuple(raised.get(entry.mod_id, entry) for entry in item.mods)
            results.append((probability, item.changed(data, mods=mods)))
        return Unravelled(data, item, tuple(results))


_FAMILIES: dict[int, tuple[GameData, frozenset[str]]] = {}


def _rollable_families(data: GameData) -> frozenset[str]:
    """The family of every prefix or suffix that spawns somewhere and has one family (what a pool can hold); cached per game data object."""
    hit = _FAMILIES.get(id(data))
    if hit is not None and hit[0] is data:
        return hit[1]
    found = frozenset(
        mod.families[0]
        for mod in data.mods.values()
        if len(mod.families) == 1
        and mod.generation_type in (Side.PREFIX.value, Side.SUFFIX.value)
        and any(weight.weight > 0 for weight in mod.spawn_weights)
    )
    _FAMILIES[id(data)] = (data, found)
    return found


@kind("orb-of-unravelling", order=110, needs_strands=True)
def _orb_of_unravelling(data: GameData, item: Item):
    if item.mods:
        yield OrbOfUnravelling()
