"""A small world for the Locus of Corruption (ticket #262, ADR-0038): the Vaal Orb's world plus a corrupted implicit that shares a mod group.

`DATA` is `corruption_support.DATA` plus `TWIN`, a corrupted implicit of weight 500 in the family of `ALL_RES`, on the same amulet, boots
and belt; the pool of those bases is then ALL_RES 1000, SECOND 500, THIRD 250, LATE 200 (level 75) and TWIN 500, and ALL_RES and TWIN
are one group. `oracle` writes ADR-0038's rules again as plain fractions, never calling `actions.locus` or the pool.
"""

import dataclasses
from fractions import Fraction
from itertools import combinations

from corruption_support import ALL_RES, LATE, LEVEL, POOL, SECOND, THIRD
from corruption_support import DATA as VAAL_DATA

from crafting_system.data import Weight

TWIN = "VaalAllResTwin"
GROUPS = {ALL_RES: "VaalAllResFamily", TWIN: "VaalAllResFamily", SECOND: "VaalTwoStatsFamily", THIRD: "VaalThirdFamily", LATE: "VaalLateFamily"}
WEIGHTS = {**{mod_id: weight for mod_id, (weight, *_) in POOL.items()}, TWIN: 500}
LEVELS = {**{mod_id: level for mod_id, (_, level, *_) in POOL.items()}, TWIN: 1}


def _world():
    template = VAAL_DATA.mods[ALL_RES]
    twin = dataclasses.replace(
        template,
        id=TWIN,
        name=TWIN,
        text=TWIN,
        spawn_weights=tuple(Weight(tag, weight) for tag, weight in (("amulet", 500), ("boots", 500), ("belt", 500), ("default", 0))),
    )
    return dataclasses.replace(VAAL_DATA, mods={**VAAL_DATA.mods, TWIN: twin})


DATA = _world()
QUARTER = Fraction(1, 4)


def pool(level: int = LEVEL) -> dict[str, int]:
    return {mod_id: weight for mod_id, weight in WEIGHTS.items() if LEVELS[mod_id] <= level}


def pair_chance(a: str, b: str, level: int = LEVEL) -> Fraction:
    """ADR-0038's formula: wA/W * wB/(W - gA) + wB/W * wA/(W - gB); 0 for two mods of one group."""
    weights = pool(level)
    if GROUPS[a] == GROUPS[b] or a not in weights or b not in weights:
        return Fraction(0)
    whole = sum(weights.values())

    def group(x: str) -> int:
        return sum(weight for mod_id, weight in weights.items() if GROUPS[mod_id] == GROUPS[x])

    return Fraction(weights[a], whole) * Fraction(weights[b], whole - group(a)) + Fraction(weights[b], whole) * Fraction(weights[a], whole - group(b))


def oracle(held: list[str], level: int = LEVEL) -> dict:
    """Every end of one use of the altar by hand: `("implicits", frozenset of the ids the item holds)`, `"nothing"` or `"dead"`, with its chance.

    Two of three or more held implicits go (each pair alike), all go up to two; the two drawn mods are any pair of different groups.
    """
    if len(held) <= 2:
        kept = [(Fraction(1), [])]
    else:
        gone = list(combinations(range(len(held)), 2))
        kept = [(Fraction(1, len(gone)), [mod_id for index, mod_id in enumerate(held) if index not in pair]) for pair in gone]
    ends: dict = {}
    for stay, left in kept:
        for a, b in combinations(sorted(pool(level)), 2):
            chance = pair_chance(a, b, level)
            if chance:
                key = ("implicits", frozenset([*left, a, b]))
                ends[key] = ends.get(key, Fraction(0)) + QUARTER * stay * chance
    ends["nothing"] = QUARTER  # the sockets
    ends["dead"] = 2 * QUARTER  # the influenced rare and the destruction
    return ends
