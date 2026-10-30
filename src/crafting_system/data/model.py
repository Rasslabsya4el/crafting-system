"""The typed model of the repoe-fork data (ADR-0003).

Plain frozen records with tuples, no behaviour beyond lookups, and no knowledge of crafting.
Wherever the raw data is a list or an object, the order of the raw file is kept: spawn and
generation weights are order-dependent in the game, and tags are never sorted. Words follow
ADR-0021: a "family" is the exclusion set (the raw key `groups`), a "mod type" is the raw `type`.
"""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Weight:
    """A tag and the weight it gives; in spawn weights the first tag the item has decides."""

    tag: str
    weight: int


@dataclass(frozen=True, slots=True)
class StatRange:
    """One stat of a mod and the range its value rolls in."""

    id: str
    min: int
    max: int


@dataclass(frozen=True, slots=True)
class Mod:
    """One mod (one tier of one family on one kind of item).

    `id` is the key of the raw object. `families` is the raw `groups` (7 real mods have none,
    224 have several). `type` is the mod type, which is not the family.
    """

    id: str
    name: str
    text: str | None
    type: str
    families: tuple[str, ...]
    domain: str
    generation_type: str
    required_level: int
    spawn_weights: tuple[Weight, ...]
    generation_weights: tuple[Weight, ...]
    adds_tags: tuple[str, ...]
    implicit_tags: tuple[str, ...]
    stats: tuple[StatRange, ...]
    is_essence_only: bool


@dataclass(frozen=True, slots=True)
class BaseItem:
    """A base item type. `tags` keep their order and duplicates (28 real bases repeat a tag); `implicits` are mod ids."""

    id: str
    name: str
    item_class: str
    domain: str
    drop_level: int
    tags: tuple[str, ...]
    implicits: tuple[str, ...]
    release_state: str


@dataclass(frozen=True, slots=True)
class Fossil:
    """A delve fossil (the description texts of the raw file are dropped; real names can be empty)."""

    id: str
    name: str
    added_mods: tuple[str, ...]
    forced_mods: tuple[str, ...]
    allowed_tags: tuple[str, ...]
    forbidden_tags: tuple[str, ...]
    positive_mod_weights: tuple[Weight, ...]
    negative_mod_weights: tuple[Weight, ...]
    changes_quality: bool
    rolls_lucky: bool
    rolls_white_sockets: bool
    mirrors: bool
    corrupted_essence_chance: int


@dataclass(frozen=True, slots=True)
class EssenceMod:
    """The mod an essence adds to one item class; `mod_id` is None where the raw file has null."""

    item_class: str
    mod_id: str | None


@dataclass(frozen=True, slots=True)
class Essence:
    """An essence. `tier` and `is_corruption_only` come from the raw `type` object."""

    id: str
    name: str
    tier: int
    is_corruption_only: bool
    level: int
    item_level_restriction: int | None
    spawn_level_min: int
    mods: tuple[EssenceMod, ...]

    def mod_for(self, item_class: str) -> str | None:
        """The id of the mod this essence adds to `item_class`, or None if it adds none there."""
        for entry in self.mods:
            if entry.item_class == item_class:
                return entry.mod_id
        return None


@dataclass(frozen=True, slots=True)
class CostEntry:
    """One currency item of a bench option's price, by item id."""

    item_id: str
    count: int


@dataclass(frozen=True, slots=True)
class BenchActions:
    """What a bench option does: the nine raw action keys, each None when the option does not use it."""

    add_explicit_mod: str | None
    add_enchant_mod: str | None
    change_socket_count: int | None
    link_sockets: int | None
    color_sockets: str | None
    remove_crafted_mods: bool | None
    remove_enchantments: bool | None
    reroll_rarity: bool | None
    reroll_rare_mods: int | None


@dataclass(frozen=True, slots=True)
class BenchOption:
    """One crafting bench option (the raw list has no ids, so none is made up)."""

    master: str
    bench_tier: int
    item_classes: tuple[str, ...]
    cost: tuple[CostEntry, ...]
    actions: BenchActions


@dataclass(frozen=True, slots=True)
class GameData:
    """Everything normalized for one pinned version; the mappings are read-only and keep file order."""

    version: str
    mods: Mapping[str, Mod]
    base_items: Mapping[str, BaseItem]
    fossils: Mapping[str, Fossil]
    essences: Mapping[str, Essence]
    bench_options: tuple[BenchOption, ...]


def conflicts(a: Mod, b: Mod) -> bool:
    """Whether two mods exclude each other: they share any family.

    Symmetric. A mod with no family conflicts with nothing, not even itself, and a shared mod
    type alone never conflicts (mods of several types can share a family, and the reverse).
    """
    return not set(a.families).isdisjoint(b.families)
