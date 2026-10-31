"""A hand oracle for what the five metamods do to the B1 actions, independent of `crafting_system.actions` (ticket #68).

It plays the rules as plain code over the typed table of the fixture amulet families of
`actions_oracle.py` (family, side, summed weight; at item level 86 or 84 and up) and the draw walk of
`magic_oracle.py`, with `Fraction`s. Nothing here reads the data model, the item model or the engine.

The rules, written again:

* a side locked by `Prefixes` / `Suffixes Cannot Be Changed` keeps all its mods through a reroll; every
  other mod goes, the metamod included; the kept mods count inside the total of 4, 5 or 6 mods (8:3:1)
  and fill their slots; a side holds three mods (a magic item one);
* a draw picks a family among those not on the item whose side has room, in proportion to its weight;
* `Cannot roll Attack Modifiers` takes the families whose mods all carry the attack tag out of the pool
  (in the fixture amulet: LightningDamage, LifeLeech, ManaLeech); a Harvest reforge filters its guaranteed
  mod only, so the fill that follows still sees them;
* a metamod that stays on the item is a pseudo family `META` of its side: it fills a slot and blocks nothing.
"""

from fractions import Fraction

from actions_oracle import FAMILIES, PREFIX, SUFFIX, TAGGED, TOTALS
from magic_oracle import draw_sets

META = "META"
ATTACK_FAMILIES = frozenset({"LightningDamage", "LifeLeech", "ManaLeech"})
CAP = 3


def pool(level: int, blocked: frozenset[str] = frozenset()) -> dict[str, tuple[str, int]]:
    """The fixture amulet's families without the `blocked` ones."""
    return {family: entry for family, entry in FAMILIES[level].items() if family not in blocked}


def merge(into: dict[frozenset[str], Fraction], key: frozenset[str], chance: Fraction) -> None:
    into[key] = into.get(key, Fraction(0)) + chance


def reroll(
    level: int, kept: dict[str, str], blocked: frozenset[str] = frozenset(), cap: int = CAP
) -> dict[frozenset[str], Fraction]:
    """A Chaos Orb that keeps the families `kept`: the chance of each set of new families."""
    families = pool(level, blocked)
    result: dict[frozenset[str], Fraction] = {}
    for total, chance in TOTALS.items():
        for drawn, inner in draw_sets(families, kept, cap, max(0, total - len(kept))).items():
            merge(result, drawn, chance * inner)
    return result


def harvest(
    level: int, kept: dict[str, str], first_blocked: frozenset[str] = frozenset()
) -> dict[frozenset[str], Fraction]:
    """A Harvest Reforge Lightning that keeps `kept`: the guaranteed family minus `first_blocked`, then the whole pool."""
    families = FAMILIES[level]
    room = {side: CAP - sum(1 for s in kept.values() if s == side) for side in (PREFIX, SUFFIX)}
    tagged = {
        f: w
        for f, w in TAGGED[level].items()
        if f not in kept and f not in first_blocked and room[families[f][0]] > 0
    }
    whole = sum(tagged.values())
    result: dict[frozenset[str], Fraction] = {}
    for total, chance in TOTALS.items():
        for first, weight in tagged.items():
            present = {**kept, first: families[first][0]}
            for rest, inner in draw_sets(families, present, CAP, max(0, total - len(kept) - 1)).items():
                merge(result, rest | {first}, chance * Fraction(weight, whole) * inner)
    return result


def add_one(
    level: int, present: dict[str, str], blocked: frozenset[str] = frozenset(), cap: int = CAP
) -> dict[frozenset[str], Fraction]:
    """One more mod on an item holding `present` (an Exalted Orb, an Augmentation, a Regal Orb)."""
    return draw_sets(pool(level, blocked), present, cap, 1)


def alteration(
    level: int, kept: dict[str, str], blocked: frozenset[str] = frozenset()
) -> dict[frozenset[str], Fraction]:
    """An Orb of Alteration on a magic item that keeps `kept`: 1 or 2 mods in all, 1/2 each."""
    families = pool(level, blocked)
    result: dict[frozenset[str], Fraction] = {}
    for total in (1, 2):
        for drawn, inner in draw_sets(families, kept, 1, max(0, total - len(kept))).items():
            merge(result, drawn, Fraction(1, 2) * inner)
    return result


__all__ = ["ATTACK_FAMILIES", "META", "PREFIX", "SUFFIX", "add_one", "alteration", "harvest", "reroll"]
