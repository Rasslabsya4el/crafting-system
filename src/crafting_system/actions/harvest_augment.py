"""The Harvest add and remove crafts and the Harvest swaps: exact actions on a rare (or magic) item (ticket #148, ADR-0030).

Add and remove (`harvest_augment`): eleven crafts, one per tag of `harvest_augment.add_remove_crafts_exist`. A craft adds
one new mod with its tag first, then removes another one (`harvest_augment.add_first_then_remove`). The new mod is drawn
in proportion to its weight among the mods of the item's pool that carry the tag and fit an open side; the removed mod
is uniform among the mods that are not fractured and not on a locked side, crafted mods and metamods included. An
influenced item refuses the craft; a fractured mod and an Eldritch implicit do not (the implicits stay on the item, and
they are no explicit mod, so the removal never takes them). A magic item takes the craft as a rare one does: the wiki names no
rarity and Craft of Exile checks none.

Swaps (`harvest_swap`): six resistance swaps and six damage swaps change one mod of the item into the mod of another
element with the same tier number and roll its value again. Which mods qualify as sources is a list of stat ids in the
claims; the target is the mod whose stat ids are the source's with the element word replaced. The sources that can
be swapped are equally likely.

An answer is a `RolledFinite`: a `Finite` whose results keep a new mod at its lowest values, like every `Finite`, and
whose `sample` rolls the values of the new mod inside its range.
"""

import random
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction

from crafting_system.data import GameData, Mod
from crafting_system.items import ExplicitMod, Item, Rarity
from crafting_system.rules import Rule, get_rule

from .catalog import kind
from .contract import Action, Adds
from .draw import refuse_unmodelled
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .metamods import locked_sides, on_locked_side
from .pool import build_pool, tiers_of

TAGGED_RARE_REFORGE_EXISTS = get_rule("harvest_reforge.tagged_rare_reforge_exists")
ADD_REMOVE_CRAFTS_EXIST = get_rule("harvest_augment.add_remove_crafts_exist")
ADD_REMOVE_REFUSED_ON_INFLUENCED_ITEM = get_rule("harvest_augment.refused_on_influenced_item")
WORKS_ON_FRACTURED_AND_ELDRITCH_IMPLICIT = get_rule("harvest_augment.works_on_fractured_and_eldritch_implicit")
ADD_REMOVE_REFUSED_ON_CORRUPTED = get_rule("harvest_augment.refused_on_corrupted")
REMOVES_ANOTHER_MODIFIER = get_rule("harvest_augment.removes_another_modifier")
ADD_FIRST_THEN_REMOVE = get_rule("harvest_augment.add_first_then_remove")
REFUSED_WHEN_NO_ROOM_TO_ADD = get_rule("harvest_augment.refused_when_no_room_to_add")
REFUSED_WHEN_NOTHING_TO_REMOVE = get_rule("harvest_augment.refused_when_nothing_to_remove")
ADD_OBEYS_SIDE_LOCKS_AND_CANNOT_ROLL = get_rule("harvest_augment.add_obeys_side_locks_and_cannot_roll")
REMOVAL_OBEYS_SIDE_LOCKS_IGNORES_CANNOT_ROLL = get_rule("harvest_augment.removal_obeys_side_locks_ignores_cannot_roll")
REMOVAL_NEVER_TAKES_FRACTURED = get_rule("harvest_augment.removal_never_takes_fractured")
REMOVAL_UNIFORM_AMONG_REMOVABLE = get_rule("harvest_augment.removal_uniform_among_removable")
ADDITION_WEIGHTED_BY_TIER_WEIGHT = get_rule("harvest_augment.addition_weighted_by_tier_weight")

RESISTANCE_SWAPS_EXIST = get_rule("harvest_swap.resistance_swaps_exist")
DAMAGE_SWAPS_EXIST = get_rule("harvest_swap.damage_swaps_exist")
KEEPS_TIER_REROLLS_VALUE = get_rule("harvest_swap.keeps_tier_rerolls_value")
RESISTANCE_SOURCE_STATS = get_rule("harvest_swap.resistance_source_stats")
DAMAGE_SOURCE_STATS = get_rule("harvest_swap.damage_source_stats")
DAMAGE_SWAP_EXCLUDES_CRIT_MULTIPLIER = get_rule("harvest_swap.damage_swap_excludes_crit_multiplier")
TARGET_ABOVE_ITEM_LEVEL_REFUSED = get_rule("harvest_swap.target_above_item_level_refused")
UNIFORM_AMONG_SOURCES = get_rule("harvest_swap.uniform_among_sources")
REFUSED_WITHOUT_SOURCE = get_rule("harvest_swap.refused_without_source")
RESPECTS_SIDE_LOCKS = get_rule("harvest_swap.respects_side_locks")
FRACTURED_AND_CRAFTED_MODS_NOT_SWAPPED = get_rule("harvest_swap.fractured_and_crafted_mods_not_swapped")
SWAP_REFUSED_ON_CORRUPTED = get_rule("harvest_swap.refused_on_corrupted")

NO_COMPRESSED_KERNEL = "no compressed-state kernel for the Harvest add, remove and swap crafts yet (#149)"


@dataclass(frozen=True, eq=False)
class RolledFinite(Finite):
    """A `Finite` whose `sample` rolls the values of the new mods inside their ranges, uniformly over the integers.

    The new mods of a result are those `given` does not hold (by mod id); the exact results keep them at their lowest values.
    """

    def sample(self, rng: random.Random) -> Item:
        result = super().sample(rng)
        held = {entry.mod_id for entry in self.given.mods}
        mods = tuple(
            entry
            if entry.mod_id in held
            else replace(
                entry,
                values=tuple(
                    rng.randint(min(stat.min, stat.max), max(stat.min, stat.max))
                    for stat in self.data.mods[entry.mod_id].stats
                ),
            )
            for entry in result.mods
        )
        return result.changed(self.data, mods=mods)


def _lowest(mod: Mod) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in mod.stats)


@dataclass(frozen=True)
class HarvestAddRemove(Action):
    """One Harvest craft that adds a new mod of a tag and removes another; `craft` is its name in lower case ("fire", "defence")."""

    craft: str = "fire"

    def __post_init__(self) -> None:
        if not isinstance(self.craft, str) or self.craft not in ADD_REMOVE_CRAFTS_EXIST.value:
            known = ", ".join(sorted(ADD_REMOVE_CRAFTS_EXIST.value))
            raise ValueError(f"there is no Harvest add and remove craft for {self.craft!r}; known: {known}")

    def label(self, data: GameData | None = None) -> str:
        return f"Harvest Add Remove {self.craft.title()}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(ADD_REMOVE_CRAFTS_EXIST.value[self.craft])

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(tag=TAGGED_RARE_REFORGE_EXISTS.value[self.craft])

    def outcomes(self, data: GameData, item: Item) -> RolledFinite:
        """The outcomes of using the craft on `item`: one result per (new mod, removed mod) pair.

        The new mod is one of the pool's mods with the craft's tag on a side with an open slot, with chance its weight
        over the sum of those weights; it is rolled at the tier of the pool. The removed mod is uniform among the mods
        that are not fractured and not on a locked side (a crafted mod and a metamod can go); it is never the new one.
        The rarity stays.

        Raises `NotApplicableError` for a normal or a corrupted item, an influenced item, an item with no
        open slot on the side of any mod with the tag (or whose Attack/Caster metamod keeps them out) and an item with
        no mod to remove, and `OutOfScopeError` for a jewel.
        """
        if item.rarity is Rarity.NORMAL:
            raise NotApplicableError("a Harvest add and remove craft works on a magic or rare item only, and this item is normal")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Harvest add and remove craft")
        if item.influences:
            raise NotApplicableError("the item is influenced, and an influenced item takes no Harvest add and remove craft")
        refuse_unmodelled(
            data, item, "the add and remove crafts are admitted for regular items only, so this craft on a jewel is not modelled yet"
        )
        tag = TAGGED_RARE_REFORGE_EXISTS.value[self.craft]
        candidates = [
            entry
            for family in build_pool(data, item)
            if item.free_slots(data, family.side) > 0
            for entry in family.mods
            if tag in entry.mod.implicit_tags
        ]
        if not candidates:
            raise NotApplicableError(
                f"the {self.craft} craft cannot add a mod: no {tag} mod of the pool fits an open slot of this item "
                "(a side is full, the family is on the item, the mod is above the item level or an Attack/Caster metamod keeps it out)"
            )
        locked = locked_sides(data, item)
        removable = [entry for entry in item.mods if not entry.fractured and not on_locked_side(data, entry, locked)]
        if not removable:
            raise NotApplicableError(
                f"the {self.craft} craft cannot remove a mod: every mod of the item is fractured or on a locked side, or there is none"
            )
        total = sum((entry.weight for entry in candidates), Fraction(0))
        tiers = tiers_of(data, item)
        results = []
        for entry in candidates:
            mod = entry.mod
            added = item.add_mod(data, ExplicitMod(mod.id, tiers.get(mod.id, 1), _lowest(mod)))
            for gone in removable:
                results.append((entry.weight / total / len(removable), added.remove_mod(data, gone.mod_id)))
        return RolledFinite(data, item, tuple(results))


@kind("harvest-add-remove", order=23, planner=False, why_not=NO_COMPRESSED_KERNEL)
def _harvest_add_remove(data: GameData, item: Item):
    if not item.influences:
        for craft in ADD_REMOVE_CRAFTS_EXIST.value:
            yield HarvestAddRemove(craft)


def _element_word(stat_id: str, source: str, target: str) -> str:
    """`stat_id` with the element word `source` replaced by `target` (a whole word between underscores)."""
    return re.sub(rf"(?<![a-z]){source}(?![a-z])", target, stat_id)


def _check_swap_pair(swaps: Rule, source: str, target: str) -> None:
    if not isinstance(source, str) or not isinstance(target, str) or target not in swaps.value.get(source, {}):
        known = ", ".join(f"{a} to {b}" for a, targets in swaps.value.items() for b in targets)
        raise ValueError(f"there is no Harvest swap from {source!r} to {target!r}; known: {known}")


def _swap_outcomes(data: GameData, item: Item, source: str, target: str, source_stats: Rule, what: str) -> RolledFinite:
    """The shared swap: one result per source mod that can be swapped, each with chance 1/n. See `HarvestResistanceSwap.outcomes`."""
    if item.rarity is Rarity.NORMAL:
        raise NotApplicableError("a Harvest swap works on a magic or rare item only, and this item is normal")
    if item.corrupted:
        raise NotApplicableError("the item is corrupted, and a corrupted item takes no Harvest swap")
    refuse_unmodelled(data, item, "the swap crafts are admitted for regular items only, so this craft on a jewel is not modelled yet")
    tiers = tiers_of(data, item)
    locked = locked_sides(data, item)
    wanted = {template.replace("X", source) for template in source_stats.value}
    with_target = 0
    swaps: list[tuple[ExplicitMod, ExplicitMod]] = []
    for entry in item.mods:
        mod = data.mods[entry.mod_id]
        if entry.fractured or entry.crafted or on_locked_side(data, entry, locked):
            continue
        if entry.mod_id not in tiers or wanted.isdisjoint(stat.id for stat in mod.stats):
            continue
        tier = tiers[entry.mod_id]
        stat_ids = tuple(_element_word(stat.id, source, target) for stat in mod.stats)
        found = [
            other
            for other_id, other_tier in tiers.items()
            if other_tier == tier
            and (other := data.mods[other_id]).generation_type == mod.generation_type
            and other.domain == mod.domain
            and tuple(stat.id for stat in other.stats) == stat_ids
        ]
        if len(found) > 1:
            names = ", ".join(sorted(other.id for other in found))
            raise OutOfScopeError(f"the swap of {entry.mod_id} to {target} is ambiguous: tier {tier} has several {target} mods ({names})")
        if not found:
            continue
        with_target += 1
        new = found[0]
        if new.required_level > item.item_level or item.remove_mod(data, entry.mod_id).blocks(data, new):
            continue
        swaps.append((entry, ExplicitMod(new.id, tier, _lowest(new))))
    if not swaps:
        if with_target == 0:
            raise NotApplicableError(
                f"a {what} cannot be used here: no mod of the item that is not fractured, not crafted and not on a locked side "
                f"grants {source} and has a {target} mod of the same tier"
            )
        raise NotApplicableError(
            f"a {what} cannot be used here: the {target} mod of the same tier of every {source} mod of the item is above "
            "the item level or shares a family with another mod of the item"
        )
    share = Fraction(1, len(swaps))
    return RolledFinite(
        data, item, tuple((share, item.remove_mod(data, old.mod_id).add_mod(data, new)) for old, new in swaps)
    )


@dataclass(frozen=True)
class HarvestResistanceSwap(Action):
    """One Harvest craft that changes a `source` resistance mod into the `target` one ("fire", "cold", "lightning")."""

    source: str = "fire"
    target: str = "cold"

    def __post_init__(self) -> None:
        _check_swap_pair(RESISTANCE_SWAPS_EXIST, self.source, self.target)

    def label(self, data: GameData | None = None) -> str:
        return f"Harvest Swap Resistance {self.source.title()} to {self.target.title()}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(RESISTANCE_SWAPS_EXIST.value[self.source][self.target])

    def outcomes(self, data: GameData, item: Item) -> RolledFinite:
        """The outcomes of using the swap on `item`: one result per source mod that can be swapped, each with chance 1/n.

        A source mod is not fractured, not crafted, not on a locked side and has a stat of the claim; its target is the
        mod of the other element with the same stats, side, domain and tier number, which replaces it at its lowest
        values. A source whose target is above the item level or shares a family with another mod of the item
        is left out. The rarity and the other mods stay; an influenced item is allowed.

        Raises `NotApplicableError` for a normal or a corrupted item and for an item with no source that can be swapped,
        and `OutOfScopeError` for a jewel, for an influenced item whose class has no influence class key
        and for a source with several targets.
        """
        return _swap_outcomes(data, item, self.source, self.target, RESISTANCE_SOURCE_STATS, "Harvest resistance swap")


@dataclass(frozen=True)
class HarvestDamageSwap(Action):
    """One Harvest craft that changes a `source` damage mod into the `target` one ("fire", "cold", "lightning")."""

    source: str = "fire"
    target: str = "cold"

    def __post_init__(self) -> None:
        _check_swap_pair(DAMAGE_SWAPS_EXIST, self.source, self.target)

    def label(self, data: GameData | None = None) -> str:
        return f"Harvest Swap Damage {self.source.title()} to {self.target.title()}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(DAMAGE_SWAPS_EXIST.value[self.source][self.target])

    def outcomes(self, data: GameData, item: Item) -> RolledFinite:
        """The outcomes of using the swap on `item`, as `HarvestResistanceSwap.outcomes` but for the damage stats of the claim.

        Raises `NotApplicableError` for a normal or a corrupted item and for an item with no source that can be swapped,
        and `OutOfScopeError` for a jewel, for an influenced item whose class has no influence class key
        and for a source with several targets.
        """
        return _swap_outcomes(data, item, self.source, self.target, DAMAGE_SOURCE_STATS, "Harvest damage swap")


@kind("harvest-resistance-swap", order=24, planner=False, why_not=NO_COMPRESSED_KERNEL)
def _harvest_resistance_swaps(data: GameData, item: Item):
    for source, targets in RESISTANCE_SWAPS_EXIST.value.items():
        for target in targets:
            yield HarvestResistanceSwap(source, target)


@kind("harvest-damage-swap", order=25, planner=False, why_not=NO_COMPRESSED_KERNEL)
def _harvest_damage_swaps(data: GameData, item: Item):
    for source, targets in DAMAGE_SWAPS_EXIST.value.items():
        for target in targets:
            yield HarvestDamageSwap(source, target)
