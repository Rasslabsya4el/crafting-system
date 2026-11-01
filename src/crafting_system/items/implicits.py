"""Implicit mods on an item (ADR-0027) and the two Eldritch sides (ADR-0025).

An `ImplicitMod` is a base implicit (grade 0) or an Eldritch implicit (grade 1 to 6) with its rolled
values. The grade of an Eldritch implicit follows from the mod: the repoe id ends in the digit of its
grade, in every one of the 4086 mods of the two Eldritch generation types of 3.29.3.3.
"""

from dataclasses import dataclass
from enum import StrEnum

from crafting_system.data import Mod

from .errors import ImplicitError

SEARING_EXARCH_IMPLICIT = "searing_exarch_implicit"
EATER_OF_WORLDS_IMPLICIT = "eater_of_worlds_implicit"
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
