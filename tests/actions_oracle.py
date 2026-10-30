"""A hand oracle for the R12 chances, independent of `crafting_system.actions`.

It knows the thirteen families of the fixture amulet at item level 84 to 86 as a typed table and
walks every draw order exactly: a recursion over the set of families drawn so far, with
`Fraction`s. It does not group families and does not use the engine's lumping, the data model or
the item model; the only shared thing is the table, typed here by hand from the fixture.

Rules it plays (the claims of the registry, written again as plain code): the number of mods of
the finished item is 4, 5 or 6 in the ratio 8:3:1 and the kept (fractured) mods count inside it;
every draw picks a family in proportion to its weight from one pool of both sides; a family leaves
the pool once drawn; a side holds three mods; a Harvest reforge first draws one family among the
tagged ones in proportion to the weight of their tagged mods, and that draw counts inside the total
as well. The chance of the target mod is the chance of its family times the share of the target in
the family.
"""

from fractions import Fraction
from functools import cache

PREFIX, SUFFIX = "prefix", "suffix"
CAP = 3

FAMILIES = {
    "GlobalDamageTypeGemLevel": (PREFIX, 1000),
    "GlobalSkillGemLevel": (PREFIX, 50),
    "IncreasedEnergyShield": (PREFIX, 1000),
    "IncreasedLife": (PREFIX, 1000),
    "ItemFoundRarityIncreasePrefix": (PREFIX, 4000),
    "LightningDamage": (PREFIX, 4250),
    "ChaosResistance": (SUFFIX, 1500),
    "ColdResistance": (SUFFIX, 1000),
    "LifeLeech": (SUFFIX, 1750),
    "LifeRegeneration": (SUFFIX, 1000),
    "LightningDamagePercentage": (SUFFIX, 2500),
    "LightningResistance": (SUFFIX, 8000),
    "ManaLeech": (SUFFIX, 2000),
}
# The lightning-tagged weight of each family; the gem-level family counts only its Lightning member.
TAGGED = {
    "LightningDamage": 4250,
    "GlobalDamageTypeGemLevel": 200,
    "LightningResistance": 8000,
    "LightningDamagePercentage": 2500,
}
GEM_FAMILY = "GlobalDamageTypeGemLevel"
TARGET_WEIGHT = 200
TOTALS = {4: Fraction(8, 12), 5: Fraction(3, 12), 6: Fraction(1, 12)}


def _family_drawn(kept: frozenset[str], picks: int, first: frozenset[str] = frozenset()) -> Fraction:
    """The chance that the gem-level family is drawn within `picks` ordinary draws.

    `kept` families are on the item and fill their side; `first` families were drawn before
    (a Harvest guaranteed draw) and fill their side too.
    """

    @cache
    def walk(drawn: frozenset[str], left: int) -> Fraction:
        if left == 0:
            return Fraction(0)
        room = {
            side: CAP - sum(1 for f in drawn if FAMILIES[f][0] == side) for side in (PREFIX, SUFFIX)
        }
        open_ = [f for f, (side, _) in FAMILIES.items() if f not in drawn and room[side] > 0]
        total = sum(FAMILIES[f][1] for f in open_)
        if total == 0:
            return Fraction(0)
        chance = Fraction(0)
        for family in open_:
            share = Fraction(FAMILIES[family][1], total)
            if family == GEM_FAMILY:
                chance += share
            else:
                chance += share * walk(drawn | {family}, left - 1)
        return chance

    return walk(kept | first, picks)


def chaos_chance(kept: tuple[str, ...] = ()) -> Fraction:
    """The chance that a Chaos Orb leaves the +1 Lightning gem level mod on the amulet."""
    blocked = frozenset(kept)
    share = Fraction(TARGET_WEIGHT, FAMILIES[GEM_FAMILY][1])
    return sum(
        p * _family_drawn(blocked, max(0, total - len(kept))) * share for total, p in TOTALS.items()
    )


def harvest_chance(kept: tuple[str, ...] = ()) -> Fraction:
    """The chance that a Harvest Reforge Lightning leaves the +1 Lightning gem level mod on the amulet."""
    blocked = frozenset(kept)
    room = {
        side: CAP - sum(1 for f in blocked if FAMILIES[f][0] == side) for side in (PREFIX, SUFFIX)
    }
    candidates = {f: w for f, w in TAGGED.items() if f not in blocked and room[FAMILIES[f][0]] > 0}
    tagged_total = sum(candidates.values())
    share = Fraction(TARGET_WEIGHT, FAMILIES[GEM_FAMILY][1])
    result = Fraction(0)
    for total, p in TOTALS.items():
        picks = max(0, total - len(kept) - 1)
        for family, weight in candidates.items():
            pick = Fraction(weight, tagged_total)
            if family == GEM_FAMILY:
                result += p * Fraction(TARGET_WEIGHT, tagged_total)
            else:
                result += p * pick * _family_drawn(blocked, picks, frozenset({family})) * share
    return result
