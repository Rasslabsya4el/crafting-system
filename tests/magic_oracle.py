"""A hand oracle for the magic-item orbs, independent of `crafting_system.actions` (ticket #64).

It reuses only the typed table of the fixture amulet families of `actions_oracle.py` (the family, its
side and the sum of its weights, typed by hand from the fixture) and walks every draw order exactly
with `Fraction`s. Rules it plays, written again as plain code: a draw picks one family among those
that are not on the item and whose side has a free slot, in proportion to the weight of the family
over the sum of those weights (one pool of both sides); a family is on the item once drawn.
A magic item holds 1 prefix and 1 suffix, a rare item 3 and 3; a Transmutation or an Alteration ends
with 1 or 2 mods (1/2 each, the fractured mods counting inside), a Regal Orb and an Augmentation
Orb add exactly one mod.
"""

from fractions import Fraction

from actions_oracle import FAMILIES, PREFIX, SUFFIX

HALF = Fraction(1, 2)


def next_family(
    families: dict[str, tuple[str, int]], present: dict[str, str], cap: int
) -> dict[str, Fraction]:
    """The chance of each family to be the next one drawn, given the families `present` (name -> side)."""
    room = {side: cap - sum(1 for s in present.values() if s == side) for side in (PREFIX, SUFFIX)}
    open_ = {f: w for f, (side, w) in families.items() if f not in present and room[side] > 0}
    total = sum(open_.values())
    return {f: Fraction(w, total) for f, w in open_.items()}


def draw_sets(
    families: dict[str, tuple[str, int]], present: dict[str, str], cap: int, picks: int
) -> dict[frozenset[str], Fraction]:
    """The chance of each set of families drawn by `picks` draws (fewer when the pool runs dry)."""
    if picks == 0:
        return {frozenset(): Fraction(1)}
    step = next_family(families, present, cap)
    if not step:
        return {frozenset(): Fraction(1)}
    result: dict[frozenset[str], Fraction] = {}
    for family, chance in step.items():
        side = families[family][0]
        for rest, inner in draw_sets(families, {**present, family: side}, cap, picks - 1).items():
            key = rest | {family}
            result[key] = result.get(key, Fraction(0)) + chance * inner
    return result


def magic_roll(
    level: int = 86, kept: tuple[str, ...] = (), cap: int = 1
) -> dict[frozenset[str], Fraction]:
    """A Transmutation or an Alteration: 1 or 2 mods in all, `kept` fractured families counting inside."""
    families = FAMILIES[level]
    present = {family: families[family][0] for family in kept}
    result: dict[frozenset[str], Fraction] = {}
    for total in (1, 2):
        for drawn, chance in draw_sets(families, present, cap, max(0, total - len(kept))).items():
            result[drawn] = result.get(drawn, Fraction(0)) + HALF * chance
    return result


def add_one(
    level: int = 86, present: tuple[str, ...] = (), cap: int = 1
) -> dict[frozenset[str], Fraction]:
    """One more mod on an item that holds the families `present`, with `cap` mods per side."""
    families = FAMILIES[level]
    return draw_sets(families, {family: families[family][0] for family in present}, cap, 1)
