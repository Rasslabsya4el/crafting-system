"""Shared data and items for the tests of the burns (ticket #295, B8-3; ADR-0056).

`DATA` is the colour data (a body armour, a sword, a helmet that asks for dexterity and intelligence, the Chromatic Orb named as in the game) with the implicit
fixtures of `implicits_support` (a belt with a ranged implicit, boots, the Eldritch implicits) and three bases of their own: a plain ring, a ring with a ranged
implicit and a jewel.
"""

import dataclasses

from implicits_support import BELT, EXTENDED, _mod
from sockets_colour_support import colour_data
from sockets_support import HELMET, SWORD, socketed, white

from crafting_system.data import BaseItem
from crafting_system.items import ImplicitMod, Item, Rarity

RING, JEWEL, RANGED_RING = (f"Metadata/Items/{kind}/BurnTest" for kind in ("Rings/Ring", "Jewels/Jewel", "Rings/RangedRing"))
TWO_STAT = "TwoStatImplicitRing"
STRENGTH = "StrengthImplicitBelt1"
AVOID_SHOCK_1 = "AvoidShockEldritchImplicit1"


def _base(base_id: str, item_class: str, tags: tuple[str, ...], implicits: tuple[str, ...] = ()) -> BaseItem:
    return BaseItem(base_id, f"Test {item_class}", item_class, "item", 1, tags, implicits, "released")


_BASE = colour_data()
DATA = dataclasses.replace(
    _BASE,
    mods={**_BASE.mods, **EXTENDED.mods, TWO_STAT: _mod(TWO_STAT, "unique", "item", "TwoStat", [("first_stat", 1, 2), ("second_stat", 5, 7)])},
    base_items={
        **_BASE.base_items,
        **EXTENDED.base_items,
        RING: _base(RING, "Ring", ("ring", "default")),
        RANGED_RING: _base(RANGED_RING, "Ring", ("ring", "default"), (TWO_STAT,)),
        JEWEL: _base(JEWEL, "Jewel", ("jewel", "default")),
    },
)


def build(base_id: str, **fields) -> Item:
    fields.setdefault("item_level", 84)
    fields.setdefault("rarity", Rarity.RARE)
    return Item.build(DATA, base_id=base_id, **fields)


def helmet(quality: int = 10, **fields) -> Item:
    return socketed(white(3), base_id=HELMET, quality=quality, **fields)


def sword(quality: int = 10, **fields) -> Item:
    return socketed(white(3), base_id=SWORD, quality=quality, **fields)


def belt(**fields) -> Item:
    return build(BELT, implicits=(ImplicitMod(STRENGTH, 0, (30,)),), **fields)


def ring(**fields) -> Item:
    """A ring with a ranged implicit: a Blessed Orb and a re-anoint are both burns of it."""
    return build(RANGED_RING, **fields)
