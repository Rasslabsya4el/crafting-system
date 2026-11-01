"""The exact law of the values a mod rolls, as far as the goal can see them (#71).

A requirement leaf with `min_roll` (a roll limit) passes a mod when every wanted value is reached. A mod that
an action draws, or that a Divine Orb rerolls, rolls its values: each stat takes every integer of its range
with the same chance, the stats independently (claim `affix_pool.values_uniform_integers`; whether the stats of
a hybrid mod really roll independently is open question O-04 of ticket #6, so we assume it). With `lucky` (a
Sanctified Fossil) each value is rolled twice and the better one kept, the better being the one nearer the
stat's `max`.

The **roll law** of a mod is the exact distribution, over what the mod gives every leaf (one `Status` per
leaf, as ints), of the values being rolled. It is the law over the whole tuple: two leaves on one mod are
correlated, because the mod rolls once. It is found by cells: the wanted values of the leaves that name the
mod cut the range of each stat into intervals inside which no leaf can tell two values apart; a cell is a
product of one interval per stat, its chance is the product of the chances of its intervals, and `status_of`
at the lowest value of a cell is what the whole cell gives. Cells that give the same tuple are added up.
A mod is **rollable** when its law has more than one outcome; the law of a mod that is not is one outcome of
chance 1, the contribution of its low rolls, which is what a drawn mod was always given.
"""

import itertools
from collections.abc import Sequence
from fractions import Fraction

from crafting_system.data import Mod

from ._goal import Wanted
from ._state import status_of

ONE = Fraction(1)
Cells = tuple[tuple[tuple[int, ...], Fraction], ...]  # (what the mod gives each leaf as ints, its chance), sorted by the ints


class RollLaw:
    """The label of a rollable mod: its law, hashable and ordered after every plain tuple of ints.

    `cells` is the law (`roll_law`); `tail` is room for a second law that must also tell two labels apart (the
    profile of a family type carries the lucky law next to the fair one). Labels sit in family types that are
    sorted, and a pool holds rollable and plain labels together, so a law is ordered after any tuple of ints.
    """

    __slots__ = ("cells", "tail", "_hash")

    def __init__(self, cells: Cells, tail: Cells = ()):
        self.cells = cells
        self.tail = tail
        self._hash = hash((cells, tail))

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RollLaw) and self._hash == other._hash and (self.cells, self.tail) == (other.cells, other.tail)

    def __lt__(self, other: object):
        if isinstance(other, RollLaw):
            return (self.cells, self.tail) < (other.cells, other.tail)
        return False if isinstance(other, tuple) else NotImplemented

    def __gt__(self, other: object):
        if isinstance(other, RollLaw):
            return (self.cells, self.tail) > (other.cells, other.tail)
        return True if isinstance(other, tuple) else NotImplemented

    def __le__(self, other: object):
        return self == other or self.__lt__(other)

    def __ge__(self, other: object):
        return self == other or self.__gt__(other)

    def __repr__(self) -> str:
        shown = ", ".join(f"{ints}: {chance}" for ints, chance in self.cells)
        return f"RollLaw({shown})"


def _bounds(low: int, high: int) -> tuple[int, int]:
    return min(low, high), max(low, high)


def _cumulative(position: int, lo: int, hi: int, ascending: bool, lucky: bool) -> Fraction:
    """The chance that a stat rolls at most `position` (a value of the range, or `lo - 1`), counted from `lo` upwards."""
    count = hi - lo + 1
    if not lucky:
        return Fraction(min(max(position - lo + 1, 0), count), count)
    if ascending:  # the better of two rolls is the higher: at most `position` needs both rolls to be
        return Fraction(min(max(position - lo + 1, 0), count), count) ** 2
    return ONE - Fraction(min(max(hi - position, 0), count), count) ** 2  # the better is the lower: not both above `position`


def _intervals(thresholds: set[int], stat_min: int, stat_max: int, lucky: bool) -> list[tuple[int, Fraction]]:
    """The intervals of one stat that the `thresholds` cut its range into: the lowest value of each and its chance."""
    lo, hi = _bounds(stat_min, stat_max)
    cuts = sorted(threshold for threshold in thresholds if lo < threshold <= hi)
    edges = [lo, *cuts, hi + 1]
    ascending = stat_max >= stat_min
    return [
        (
            start,
            _cumulative(end - 1, lo, hi, ascending, lucky) - _cumulative(start - 1, lo, hi, ascending, lucky),
        )
        for start, end in zip(edges, edges[1:])
    ]


def roll_law(leaves: Sequence[Wanted], mod: Mod, tier: int, crafted: bool = False, lucky: bool = False) -> Cells:
    """The exact law of what `mod`, rolled at `tier`, gives each of `leaves`; sums to 1.

    The leaves that name the mod and limit a stat give the thresholds; a leaf whose `min_roll` has another
    number of entries than the mod has stats is BELOW at every roll and cuts nothing.
    """
    stats = mod.stats
    thresholds: list[set[int]] = [set() for _ in stats]
    for leaf in leaves:
        if mod.id in leaf.mod_ids and leaf.min_roll is not None and len(leaf.min_roll) == len(stats):
            for position, wanted in enumerate(leaf.min_roll):
                if wanted is not None:
                    thresholds[position].add(wanted)
    per_stat = [_intervals(cuts, stat.min, stat.max, lucky) for cuts, stat in zip(thresholds, stats)]
    law: dict[tuple[int, ...], Fraction] = {}
    for cell in itertools.product(*per_stat):
        values = tuple(start for start, _ in cell)
        chance = ONE
        for _, each in cell:
            chance *= each
        ints = tuple(int(status_of(leaf, mod.id, tier, values, crafted)) for leaf in leaves)
        law[ints] = law.get(ints, Fraction(0)) + chance
    return tuple(sorted(law.items()))


def is_rollable(cells: Cells) -> bool:
    """Whether a law has more than one outcome: the values the mod rolls change what it gives the goal."""
    return len(cells) > 1


def compositions(total: int, parts: int):
    """Every way of splitting `total` mods over `parts` outcomes, as tuples of counts (some may be 0)."""
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in compositions(total - first, parts - 1):
            yield (first, *rest)


def multinomial(cells: Cells, count: int) -> list[tuple[tuple[tuple[tuple[int, ...], int], ...], Fraction]]:
    """How `count` mods that each roll the law `cells` are spread over its outcomes, with the exact chance of each spread.

    Each entry is `(((ints, how many mods got them), ...), chance)` for the outcomes that got at least one mod:
    the multinomial `count! / prod(n_i!) * prod(q_i ** n_i)` of the counts `n_i` and the chances `q_i`.
    """
    result = []
    factorials = [1]
    for number in range(1, count + 1):
        factorials.append(factorials[-1] * number)
    for counts in compositions(count, len(cells)):
        chance = Fraction(factorials[count])
        for (_, each), taken in zip(cells, counts):
            chance = chance * each**taken / factorials[taken]
        if chance:
            result.append((tuple((ints, taken) for (ints, _), taken in zip(cells, counts) if taken), chance))
    return result
