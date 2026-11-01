"""Which mods are enchantments and what each one is (ADR-0050 to ADR-0053).

An item holds one enchantment besides its implicits and explicit mods. Three families of mod can sit in
that slot: an enchant of the Tempering Orb pool (weapons), one of the Tailoring Orb pool (body armour), and
a Harvest quality enchant (the 14, 8 for body armour and 6 for weapons). The repoe dump holds them as mods of
generation type `unique` with no spawn weights, told apart only by their family. The 3.29.0 notes removed the
pool enchants that set white sockets or set every socket to one colour; the dump still lists them, so they
are recognised here by their stat and are not enchantments any more.

`enchant_info` classifies one mod; it reads only the mod, so it needs no game data. The words follow the
GLOSSARY: a **clean** enchant has a positive magnitude on a tag, no socket rider and no downside (a hybrid of
two positive tags and an attribute requirement reduction stay clean); the **extra crafted slot** is the one
pool enchant "Can have 1 additional Crafted Modifier".
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from crafting_system.data import BaseItem, Mod

WEAPON_POOL_FAMILY = "EnchantmentHeistWeapon"
BODY_ARMOUR_POOL_FAMILY = "EnchantmentHeistArmour"
WEAPON_QUALITY_FAMILY = "AlternateWeaponQuality"
BODY_ARMOUR_QUALITY_FAMILY = "AlternateArmourQuality"
REMOVED_STATS = frozenset(
    {
        "local_has_X_white_sockets",
        "local_all_sockets_are_red",
        "local_all_sockets_are_green",
        "local_all_sockets_are_blue",
    }
)
SOCKET_STATS = frozenset(
    {
        "local_all_sockets_linked",
        "local_cannot_have_red_sockets",
        "local_cannot_have_green_sockets",
        "local_cannot_have_blue_sockets",
        "local_maximum_sockets_+",
    }
)
EXTRA_CRAFTED_SLOT_STAT = "local_can_have_additional_crafted_mods"
REQUIREMENTS_STAT = "local_attribute_requirements_+%"
EFFECT_STAT_PREFIX = "heist_enchantment_"
WEAPON_TAG = "weapon"
BODY_ARMOUR_TAG = "body_armour"
MAGNITUDE_LINE = re.compile(r"^\d+% (increased|reduced) Explicit (.+) Modifier magnitudes$")


class EnchantClass(StrEnum):
    """The kind of item an enchantment sits on: a weapon (any base tagged `weapon`) or a body armour."""

    WEAPON = "weapon"
    BODY_ARMOUR = "body armour"


class EnchantKind(StrEnum):
    """Where an enchantment comes from: a Tempering or Tailoring Orb pool, or a Harvest quality enchant."""

    POOL = "pool"
    QUALITY = "quality"


POOL_FAMILIES = {WEAPON_POOL_FAMILY: EnchantClass.WEAPON, BODY_ARMOUR_POOL_FAMILY: EnchantClass.BODY_ARMOUR}
QUALITY_FAMILIES = {WEAPON_QUALITY_FAMILY: EnchantClass.WEAPON, BODY_ARMOUR_QUALITY_FAMILY: EnchantClass.BODY_ARMOUR}


@dataclass(frozen=True, slots=True)
class EnchantInfo:
    """One enchantment mod. `tags` are the tags it raises by a positive magnitude, as the mod's text names them
    ("Life", "Critical"); `socket_rider` is set when it also touches the sockets, `downside` when it lowers a
    magnitude of another tag or raises the attribute requirements."""

    mod_id: str
    kind: EnchantKind
    item_class: EnchantClass
    tags: tuple[str, ...]
    socket_rider: bool
    downside: bool
    extra_slot: bool

    @property
    def clean(self) -> bool:
        """A pool enchant with a positive magnitude on a tag, no socket rider and no downside."""
        return self.kind is EnchantKind.POOL and bool(self.tags) and not self.socket_rider and not self.downside


def enchant_class(base: BaseItem) -> EnchantClass | None:
    """The enchantments `base` can hold: weapons by the `weapon` tag, body armour by the `body_armour` tag, else none."""
    if WEAPON_TAG in base.tags:
        return EnchantClass.WEAPON
    if BODY_ARMOUR_TAG in base.tags:
        return EnchantClass.BODY_ARMOUR
    return None


def is_removed_enchant(mod: Mod) -> bool:
    """Whether `mod` is a pool enchant the 3.29.0 notes removed (white sockets, every socket one colour)."""
    stats = {stat.id for stat in mod.stats}
    return any(family in POOL_FAMILIES for family in mod.families) and bool(stats & REMOVED_STATS)


def enchant_info(mod: Mod) -> EnchantInfo | None:
    """What `mod` is as an enchantment, or None when it is not one (or was removed from the pool in 3.29.0)."""
    for family in mod.families:
        if family in POOL_FAMILIES and not is_removed_enchant(mod):
            return _info(mod, EnchantKind.POOL, POOL_FAMILIES[family])
        if family in QUALITY_FAMILIES:
            return _info(mod, EnchantKind.QUALITY, QUALITY_FAMILIES[family])
    return None


def _info(mod: Mod, kind: EnchantKind, item_class: EnchantClass) -> EnchantInfo:
    tags: list[str] = []
    for line in (mod.text or "").splitlines():
        match = MAGNITUDE_LINE.match(line.strip())
        if match and match.group(1) == "increased":
            tags.append(match.group(2))
    return EnchantInfo(
        mod_id=mod.id,
        kind=kind,
        item_class=item_class,
        tags=tuple(tags),
        socket_rider=any(stat.id in SOCKET_STATS for stat in mod.stats),
        downside=any(_is_downside(stat.id, stat.max) for stat in mod.stats),
        extra_slot=any(stat.id == EXTRA_CRAFTED_SLOT_STAT for stat in mod.stats),
    )


def _is_downside(stat_id: str, high: int) -> bool:
    if stat_id == REQUIREMENTS_STAT:
        return high > 0
    return stat_id.startswith(EFFECT_STAT_PREFIX) and high < 0
