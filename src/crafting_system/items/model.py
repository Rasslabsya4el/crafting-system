"""The concrete item (ADR-0018): a base, an item level, a rarity and a set of explicit mods.

An `Item` is a value: frozen, hashable, and equal to any other item with the same fields, whatever
order its mods were given in (mods are stored sorted by id). Building one checks the rules that
need no game data; `Item.validate` checks the rest against a `GameData`, and `Item.build`,
`changed`, `add_mod` and `remove_mod` always return an item that passed it. Implicits are not stored:
they come from the base. Words follow ADR-0021: a "family" is the exclusion set of a mod.

Not enforced here, because they are rules of `actions` or open questions: a mod's required level
against the item level, whether a mod can spawn on the base's tags, the limit of one crafted mod
(and the metamod that lifts it), a magic item needing at least one mod and a rare at least four,
the limit of two influences, fractured mods only on rares, and what corruption forbids. The `tier`
of a mod is stored as given; `tiers.py` derives the tier of a mod on a base from the data.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Self

from crafting_system.data import GameData, Mod, conflicts
from crafting_system.rules import get_rule

from .errors import (
    CapacityError,
    FamilyConflictError,
    ItemError,
    ModSlotError,
    UnknownBaseError,
    UnknownModError,
    ValueRangeError,
)


class Rarity(StrEnum):
    """The rarity of an item; unique items are not modelled."""

    NORMAL = "normal"
    MAGIC = "magic"
    RARE = "rare"


class Side(StrEnum):
    """Prefix or suffix; the values equal the repoe `generation_type` of a mod."""

    PREFIX = "prefix"
    SUFFIX = "suffix"


class Influence(StrEnum):
    """An item influence. Eldritch implicits are not influences."""

    SHAPER = "shaper"
    ELDER = "elder"
    CRUSADER = "crusader"
    HUNTER = "hunter"
    REDEEMER = "redeemer"
    WARLORD = "warlord"


class Metamod(StrEnum):
    """A crafted metamod, valued by the repoe family id of its mod."""

    PREFIXES_CANNOT_CHANGE = "ItemGenerationCannotChangePrefixes"
    SUFFIXES_CANNOT_CHANGE = "ItemGenerationCannotChangeSuffixes"
    NO_ATTACK_MODS = "ItemGenerationCannotRollAttackAffixes"
    NO_CASTER_MODS = "ItemGenerationCannotRollCasterAffixes"
    MULTIPLE_CRAFTED_MODS = "ItemGenerationCanHaveMultipleCraftedMods"


@dataclass(frozen=True, slots=True)
class ExplicitMod:
    """One explicit mod on an item.

    `tier` is 1 for the best and is stored as given. `values` holds one rolled integer per stat of
    the mod, in the order of `Mod.stats`.
    """

    mod_id: str
    tier: int
    values: tuple[int, ...]
    fractured: bool = False
    crafted: bool = False


@dataclass(frozen=True, slots=True)
class Capacity:
    """How many prefixes and how many suffixes an item can hold."""

    prefix: int
    suffix: int

    def of(self, side: Side) -> int:
        """The capacity of one side."""
        return self.prefix if side is Side.PREFIX else self.suffix


def capacity(data: GameData, base_id: str, rarity: Rarity) -> Capacity:
    """The capacity of an item of `rarity` on `base_id`, from the rules registry.

    Normal items hold none; magic and rare items hold the same number on each side, except that
    rare items of the jewel item classes hold fewer.
    """
    base = data.base_items.get(base_id)
    if base is None:
        raise UnknownBaseError(f"item on {base_id}: the base is not in the game data")
    if rarity is Rarity.NORMAL:
        per_side = NORMAL_NO_MODS.value["normal"]
    elif rarity is Rarity.RARE and base.item_class in RARE_JEWEL.value["item_classes"]:
        per_side = RARE_JEWEL.value["rare"]
    else:
        per_side = MAX_PER_SIDE_BY_RARITY.value[rarity.value]
    return Capacity(per_side, per_side)


MIN_ITEM_LEVEL = 1
MAX_ITEM_LEVEL = 100
MAX_PER_SIDE_BY_RARITY = get_rule("affix_count.max_per_side_by_rarity")
NORMAL_NO_MODS = get_rule("affix_count.normal_has_no_explicit_mods")
RARE_JEWEL = get_rule("affix_count.rare_jewel_max_per_side")
EXPLICIT_EXTRA_DOMAINS = frozenset({"crafted", "delve", "veiled", "unveiled"})
CRAFTED_DOMAIN = "crafted"
SIDE_VALUES = frozenset(side.value for side in Side)


@dataclass(frozen=True, slots=True)
class Item:
    """A concrete item. Construction checks only what needs no game data; see the module docstring."""

    base_id: str
    item_level: int
    rarity: Rarity
    mods: tuple[ExplicitMod, ...] = ()
    influences: frozenset[Influence] = frozenset()
    corrupted: bool = False

    def __post_init__(self) -> None:
        if type(self.item_level) is not int:
            raise self._error(f"item level {self.item_level!r} is not an integer")
        if not MIN_ITEM_LEVEL <= self.item_level <= MAX_ITEM_LEVEL:
            raise self._error(
                f"item level {self.item_level} is outside {MIN_ITEM_LEVEL} to {MAX_ITEM_LEVEL}"
            )
        if not isinstance(self.rarity, Rarity):
            raise self._error(f"rarity {self.rarity!r} is not a Rarity")
        if not isinstance(self.influences, frozenset) or not all(
            isinstance(entry, Influence) for entry in self.influences
        ):
            raise self._error("influences must be a frozenset of Influence")
        if not all(isinstance(mod, ExplicitMod) for mod in self.mods):
            raise self._error("mods must all be ExplicitMod")
        ordered = tuple(sorted(self.mods, key=lambda mod: mod.mod_id))
        for mod in ordered:
            if type(mod.tier) is not int or not isinstance(mod.values, tuple):
                raise self._error(f"mod {mod.mod_id} needs an integer tier and a tuple of values")
            if any(type(value) is not int for value in mod.values):
                raise self._error(f"mod {mod.mod_id} has a rolled value that is not an integer")
            if mod.tier < 1:
                raise self._error(f"mod {mod.mod_id} has tier {mod.tier}, tiers start at 1")
            if mod.fractured and mod.crafted:
                raise self._error(f"mod {mod.mod_id} is flagged both fractured and crafted")
        for first, second in zip(ordered, ordered[1:]):
            if first.mod_id == second.mod_id:
                raise self._error(f"mod {first.mod_id} is on the item twice")
        object.__setattr__(self, "mods", ordered)

    def _error(self, reason: str, kind: type[ItemError] = ItemError) -> ItemError:
        return kind(f"item on {self.base_id}: {reason}")

    @property
    def fractured_mods(self) -> tuple[ExplicitMod, ...]:
        """The fractured explicit mods."""
        return tuple(mod for mod in self.mods if mod.fractured)

    @property
    def crafted_mods(self) -> tuple[ExplicitMod, ...]:
        """The explicit mods added from the crafting bench."""
        return tuple(mod for mod in self.mods if mod.crafted)

    @classmethod
    def build(cls, data: GameData, **fields) -> Self:
        """Construct an item from `fields` and validate it against `data`."""
        built = cls(**fields)
        built.validate(data)
        return built

    def validate(self, data: GameData) -> None:
        """Raise an `ItemError` subclass for the first problem found, checking in this order: unknown
        base, unknown mod, wrong slot or domain, wrong values, capacity, family conflict."""
        base = data.base_items.get(self.base_id)
        if base is None:
            raise self._error("the base is not in the game data", UnknownBaseError)
        for entry in self.mods:
            if entry.mod_id not in data.mods:
                raise self._error(f"mod {entry.mod_id} is not in the game data", UnknownModError)
        for entry in self.mods:
            self._check_slot(entry, data.mods[entry.mod_id], base.domain)
        for entry in self.mods:
            self._check_values(entry, data.mods[entry.mod_id])
        self._check_capacity(data)
        self._check_families(data)

    def _check_slot(self, entry: ExplicitMod, mod: Mod, base_domain: str) -> None:
        if mod.generation_type not in SIDE_VALUES:
            raise self._error(
                f"mod {entry.mod_id} is of generation type {mod.generation_type}, not prefix or suffix",
                ModSlotError,
            )
        if mod.domain not in {base_domain} | EXPLICIT_EXTRA_DOMAINS:
            raise self._error(
                f"mod {entry.mod_id} is of domain {mod.domain}, which does not fit a base of domain {base_domain}",
                ModSlotError,
            )
        if entry.crafted != (mod.domain == CRAFTED_DOMAIN):
            reason = (
                "is flagged crafted but is of domain " + mod.domain
                if entry.crafted
                else "is of the crafted domain but is not flagged crafted"
            )
            raise self._error(f"mod {entry.mod_id} {reason}", ModSlotError)

    def _check_values(self, entry: ExplicitMod, mod: Mod) -> None:
        if len(entry.values) != len(mod.stats):
            raise self._error(
                f"mod {entry.mod_id} has {len(entry.values)} rolled value(s) but the mod has {len(mod.stats)} stat(s)",
                ValueRangeError,
            )
        for value, stat in zip(entry.values, mod.stats, strict=True):
            low, high = min(stat.min, stat.max), max(stat.min, stat.max)
            if not low <= value <= high:
                raise self._error(
                    f"mod {entry.mod_id} has value {value} for {stat.id}, outside {low} to {high}",
                    ValueRangeError,
                )

    def _check_capacity(self, data: GameData) -> None:
        room = self.capacity(data)
        for side in Side:
            used = len(self.mods_on(data, side))
            if used > room.of(side):
                raise self._error(
                    f"it has {_count(used, side)}, but a {self.rarity} item on this base holds at most"
                    f" {_count(room.of(side), side)}",
                    CapacityError,
                )

    def _check_families(self, data: GameData) -> None:
        for index, first in enumerate(self.mods):
            for second in self.mods[index + 1 :]:
                a, b = self._mod(data, first), self._mod(data, second)
                if conflicts(a, b):
                    shared = next(family for family in a.families if family in b.families)
                    raise self._error(
                        f"mods {first.mod_id} and {second.mod_id} share the family {shared}",
                        FamilyConflictError,
                    )

    def capacity(self, data: GameData) -> Capacity:
        """The prefix and suffix capacity of this item."""
        return capacity(data, self.base_id, self.rarity)

    def mods_on(self, data: GameData, side: Side) -> tuple[ExplicitMod, ...]:
        """The explicit mods on one side, in mod id order."""
        return tuple(
            entry for entry in self.mods if self._mod(data, entry).generation_type == side.value
        )

    def prefixes(self, data: GameData) -> tuple[ExplicitMod, ...]:
        """The explicit prefixes."""
        return self.mods_on(data, Side.PREFIX)

    def suffixes(self, data: GameData) -> tuple[ExplicitMod, ...]:
        """The explicit suffixes."""
        return self.mods_on(data, Side.SUFFIX)

    def free_slots(self, data: GameData, side: Side) -> int:
        """How many more mods fit on one side."""
        return self.capacity(data).of(side) - len(self.mods_on(data, side))

    def families(self, data: GameData) -> frozenset[str]:
        """Every family of every explicit mod."""
        return frozenset(
            family for entry in self.mods for family in self._mod(data, entry).families
        )

    def metamods(self, data: GameData) -> frozenset[Metamod]:
        """The metamods among the explicit mods, found by their family."""
        known = {metamod.value: metamod for metamod in Metamod}
        return frozenset(known[family] for family in self.families(data) if family in known)

    def blocks(self, data: GameData, mod: Mod) -> bool:
        """Whether adding `mod` would clash: it is on the item already, or shares a family with a mod there."""
        return any(
            entry.mod_id == mod.id or conflicts(self._mod(data, entry), mod) for entry in self.mods
        )

    def can_add(self, data: GameData, mod: Mod) -> bool:
        """Whether `mod` could be added: it fits this base as a prefix or suffix, a slot is free and nothing blocks it."""
        if mod.generation_type not in SIDE_VALUES:
            return False
        if mod.domain not in {data.base_items[self.base_id].domain} | EXPLICIT_EXTRA_DOMAINS:
            return False
        return self.free_slots(data, Side(mod.generation_type)) > 0 and not self.blocks(data, mod)

    def changed(self, data: GameData, **fields) -> Self:
        """A new validated item with the given fields replaced."""
        updated = replace(self, **fields)
        updated.validate(data)
        return updated

    def add_mod(self, data: GameData, mod: ExplicitMod) -> Self:
        """A new validated item with `mod` added."""
        return self.changed(data, mods=(*self.mods, mod))

    def remove_mod(self, data: GameData, mod_id: str) -> Self:
        """A new validated item without the mod `mod_id`; fractured mods can be removed here, when they
        may be is a rule of `actions`."""
        if all(entry.mod_id != mod_id for entry in self.mods):
            raise self._error(f"mod {mod_id} is not on the item")
        return self.changed(data, mods=tuple(entry for entry in self.mods if entry.mod_id != mod_id))

    def _mod(self, data: GameData, entry: ExplicitMod) -> Mod:
        mod = data.mods.get(entry.mod_id)
        if mod is None:
            raise self._error(f"mod {entry.mod_id} is not in the game data", UnknownModError)
        return mod


def _count(number: int, side: Side) -> str:
    return f"{number} {side.value}" + ("" if number == 1 else "es")
