"""Implicit mods on an item (ADR-0027) and the two Eldritch sides (ADR-0025).

An `ImplicitMod` is a base implicit (grade 0), an Eldritch implicit (grade 1 to 6) or a corrupted implicit (grade
0, held only by a corrupted item, ADR-0036) with its rolled values. The grade of an Eldritch implicit follows from
the mod: the repoe id ends in the digit of its grade, in every one of the 4086 mods of the two Eldritch generation
types of 3.29.3.3.
"""

from dataclasses import dataclass
from enum import StrEnum

from crafting_system.data import BaseItem, Mod

from .errors import ImplicitError
from .spawn import spawn_weight

SEARING_EXARCH_IMPLICIT = "searing_exarch_implicit"
EATER_OF_WORLDS_IMPLICIT = "eater_of_worlds_implicit"
CORRUPTED_IMPLICIT = "corrupted"
ABYSS_JEWEL_TAG = "abyss_jewel"
ABYSS_JEWEL_DOMAIN = "abyss_jewel"
CLUSTER_JEWEL_DOMAIN = "affliction_jewel"
TIMELESS_JEWEL_NAME = "Timeless Jewel"
# the domains whose items a corrupting action gives an implicit: equipment, jewellery and quivers, jewels, abyss jewels. Other domains
# also hold corrupted mods (maps, relics, grafts) that no corrupting action draws for an item of this project.
CORRUPTED_POOL_DOMAINS = frozenset({"item", "misc", ABYSS_JEWEL_DOMAIN})
BASE_GRADE = 0
MIN_ELDRITCH_GRADE = 1
MAX_ELDRITCH_GRADE = 6
PRESENCE_STATS = frozenset(
    {
        "local_influence_mod_requires_unique_monster_presence",
        "local_influence_mod_requires_celestial_boss_presence",
    }
)


class EldritchSide(StrEnum):
    """The two Eldritch implicit sides: Searing Exarch (prefixes) and Eater of Worlds (suffixes)."""

    EXARCH = "exarch"
    EATER = "eater"


SIDE_BY_GENERATION_TYPE = {
    SEARING_EXARCH_IMPLICIT: EldritchSide.EXARCH,
    EATER_OF_WORLDS_IMPLICIT: EldritchSide.EATER,
}


@dataclass(frozen=True, slots=True)
class ImplicitMod:
    """One implicit mod on an item.

    `grade` is 0 for a base implicit and 1 (Lesser) to 6 (Perfect) for an Eldritch one. `values` holds one
    rolled integer per stat of the mod, in the order of `Mod.stats`.
    """

    mod_id: str
    grade: int
    values: tuple[int, ...]


def eldritch_side(mod: Mod) -> EldritchSide | None:
    """The Eldritch side of `mod`, or None when it is not an Eldritch implicit."""
    return SIDE_BY_GENERATION_TYPE.get(mod.generation_type)


def eldritch_grade(mod: Mod) -> int | None:
    """The Eldritch grade 1 to 6 of `mod`, read from the digit its id ends in; None for any other mod."""
    if eldritch_side(mod) is None:
        return None
    last = mod.id[-1:]
    if not last.isdigit() or not MIN_ELDRITCH_GRADE <= int(last) <= MAX_ELDRITCH_GRADE:
        raise ImplicitError(f"mod {mod.id} is an Eldritch implicit but its id does not end in a grade 1 to 6")
    return int(last)


def is_presence_variant(mod: Mod) -> bool:
    """Whether `mod` is a "While a Unique Enemy / Pinnacle Atlas Boss is in your Presence" variant; its
    text is the same as the base mod's."""
    return any(stat.id in PRESENCE_STATS for stat in mod.stats)


def is_corrupted_implicit(mod: Mod) -> bool:
    """Whether `mod` is of the generation type corrupted: the implicit a corrupting action draws (ADR-0037)."""
    return mod.generation_type == CORRUPTED_IMPLICIT


def corrupted_pool_domain(base: BaseItem) -> str:
    """The domain of the corrupted mods `base` draws from: its own, except that an abyss jewel counts as its own domain (its mods list
    only the `default` tag, which every base has)."""
    return ABYSS_JEWEL_DOMAIN if ABYSS_JEWEL_TAG in base.tags else base.domain


def fits_corrupted_implicit(mod: Mod, base: BaseItem) -> bool:
    """Whether `mod` is a corrupted implicit that `base` can get: of the base's pool domain, with a spawn weight above 0 on the base's
    tags, and the base is not a Cluster or a Timeless jewel (their pools are not checked, ADR-0037). The item level is not checked here
    (the pool of `actions` gates it)."""
    if base.domain == CLUSTER_JEWEL_DOMAIN or base.name == TIMELESS_JEWEL_NAME:
        return False
    domain = corrupted_pool_domain(base)
    return (
        is_corrupted_implicit(mod)
        and domain in CORRUPTED_POOL_DOMAINS
        and mod.domain == domain
        and spawn_weight(mod, base.tags) > 0
    )
