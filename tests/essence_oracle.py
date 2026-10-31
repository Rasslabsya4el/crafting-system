"""A hand oracle for the essence chances, independent of `crafting_system.actions` (ticket #55).

It types the pool of the fixture amulet mod by mod (id, level, weight, by family and side, copied by
hand from the fixture) and walks every draw order exactly with `Fraction`s: a recursion over the set
of families drawn so far. It does not group families and uses neither the data model nor the item
model. The two fixture essences put a suffix on an amulet whose family is not in the table, so the
forced mod only takes a suffix slot and counts in the total.

Rules it plays (the claims of the registry, written again as plain code): the number of mods of the
finished item is 4, 5 or 6 in the ratio 8:3:1 and the forced mod and the kept (fractured) mods count
inside it, so `total - kept - 1` mods are drawn (none when that is negative); every draw picks a
family in proportion to the weight of its mods that the level limit lets through, from one pool of
both sides; a family leaves the pool once drawn; a side holds three mods. The level limit is the item
level, or the lower of the item level and the cap of a low essence. The chance of a target mod is
the chance that its family is drawn times its share in the family at that limit.
"""

from fractions import Fraction
from functools import cache

PREFIX, SUFFIX = "prefix", "suffix"
CAP = 3
TOTALS = {4: Fraction(8, 12), 5: Fraction(3, 12), 6: Fraction(1, 12)}

# family: (side, ((mod id, required level, weight), ...))
AMULET = {
    "ChaosResistance": (SUFFIX, (("ChaosResist1", 16, 250), ("ChaosResist2", 30, 250), ("ChaosResist3", 44, 250), ("ChaosResist4", 56, 250), ("ChaosResist5", 65, 250), ("ChaosResist6", 81, 250))),  # fmt: skip
    "ColdResistance": (SUFFIX, (("ColdResist1", 1, 1000),)),
    "FireResistance": (SUFFIX, (("FireResist1", 1, 1000),)),
    "GlobalDamageTypeGemLevel": (PREFIX, (("GlobalChaosGemLevel1", 75, 200), ("GlobalColdGemLevel1__", 75, 200), ("GlobalFireGemLevel1_", 75, 200), ("GlobalLightningGemLevel1", 75, 200), ("GlobalPhysicalGemLevel1_", 75, 200))),  # fmt: skip
    "GlobalSkillGemLevel": (PREFIX, (("GlobalSkillGemLevel1", 75, 50),)),
    "IncreasedEnergyShield": (PREFIX, (("IncreasedEnergyShield1", 3, 1000),)),
    "IncreasedLife": (PREFIX, (("IncreasedLife1", 5, 1000), ("IncreasedLife2", 11, 1000), ("IncreasedLife3", 18, 1000))),  # fmt: skip
    "ItemFoundRarityIncreasePrefix": (PREFIX, (("ItemFoundRarityIncreasePrefix1", 20, 1000), ("ItemFoundRarityIncreasePrefix2", 39, 1000), ("ItemFoundRarityIncreasePrefix3", 62, 1000), ("ItemFoundRarityIncreasePrefix4_", 84, 1000))),  # fmt: skip
    "LifeLeech": (SUFFIX, (("LifeLeechPermyriadSuffix1", 50, 1000), ("LifeLeechPermyriadSuffix2", 60, 500), ("LifeLeechPermyriadSuffix3", 70, 250))),  # fmt: skip
    "LifeRegeneration": (SUFFIX, (("LifeRegeneration1", 1, 1000),)),
    "LightningDamage": (PREFIX, (("AddedLightningDamage1", 3, 500), ("AddedLightningDamage2", 13, 500), ("AddedLightningDamage3", 22, 500), ("AddedLightningDamage4", 28, 500), ("AddedLightningDamage5", 35, 500), ("AddedLightningDamage6", 44, 500), ("AddedLightningDamage7", 52, 500), ("AddedLightningDamage8", 64, 500), ("AddedLightningDamage9", 76, 250))),  # fmt: skip
    "LightningDamagePercentage": (SUFFIX, (("LightningDamagePercent1", 10, 500), ("LightningDamagePercent2", 23, 500), ("LightningDamagePercent3", 36, 500), ("LightningDamagePercent4", 50, 500), ("LightningDamagePercent5", 64, 500))),  # fmt: skip
    "LightningResistance": (SUFFIX, (("LightningResist1", 1, 1000), ("LightningResist2", 13, 1000), ("LightningResist3", 25, 1000), ("LightningResist4", 37, 1000), ("LightningResist5", 49, 1000), ("LightningResist6", 60, 1000), ("LightningResist7", 72, 1000), ("LightningResist8", 84, 1000))),  # fmt: skip
    "ManaLeech": (SUFFIX, (("ManaLeechPermyriadSuffix1", 50, 1000), ("ManaLeechPermyriadSuffix2", 70, 1000))),
}  # fmt: skip


def _pool(limit: int, kept: frozenset[str]) -> dict[str, tuple[str, int]]:
    """family -> (side, weight at `limit`) for every family not kept and with weight at that limit."""
    pool = {}
    for family, (side, mods) in AMULET.items():
        weight = sum(w for _, level, w in mods if level <= limit)
        if weight and family not in kept:
            pool[family] = (side, weight)
    return pool


def _family_of(target: str) -> tuple[str, int, int]:
    for family, (_, mods) in AMULET.items():
        for mod_id, level, weight in mods:
            if mod_id == target:
                return family, level, weight
    raise KeyError(target)


def essence_chance(
    target: str,
    item_level: int,
    cap: int | None = None,
    kept: tuple[str, ...] = (),
    forced_side: str = SUFFIX,
    forced_family: str | None = None,
) -> Fraction:
    """The chance that the finished item holds `target` after an essence whose forced mod is on `forced_side`.

    `kept` are the families of the fractured mods that stay. By default the forced mod's own family
    is not in the table, so it only takes a slot on `forced_side`; with `forced_family` the forced
    mod is a mod of that table family: the family leaves the pool and its side gives the slot.
    """
    limit = item_level if cap is None else min(item_level, cap)
    family, level, weight = _family_of(target)
    if family in kept or level > limit:
        return Fraction(0)
    if forced_family is not None:
        if family == forced_family:
            return Fraction(0)  # another mod of the forced family: blocked (the forced mod itself is no target)
        forced_side = AMULET[forced_family][0]
    pool = _pool(limit, frozenset(kept) | ({forced_family} if forced_family else frozenset()))
    share = Fraction(weight, pool[family][1])
    used = {PREFIX: 0, SUFFIX: 0}
    for name in kept:
        used[AMULET[name][0]] += 1
    used[forced_side] += 1

    @cache
    def drawn_before(taken: frozenset[str], left: int) -> Fraction:
        """The chance that `family` is drawn within `left` more draws, `taken` families being gone."""
        if left == 0:
            return Fraction(0)
        room = {side: CAP - used[side] - sum(1 for f in taken if pool[f][0] == side) for side in used}
        open_ = [f for f, (side, _) in pool.items() if f not in taken and room[side] > 0]
        total = sum(pool[f][1] for f in open_)
        if total == 0:
            return Fraction(0)
        chance = Fraction(0)
        for name in open_:
            step = Fraction(pool[name][1], total)
            chance += step if name == family else step * drawn_before(taken | {name}, left - 1)
        return chance

    return sum(
        (p * drawn_before(frozenset(), max(0, total - len(kept) - 1)) * share for total, p in TOTALS.items()),
        Fraction(0),
    )
