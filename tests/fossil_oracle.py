"""A hand oracle for the chances of a Chaotic resonator, independent of `crafting_system.actions` (ticket #61).

It takes the final weight of every mod as a literal table (the test works the fossil factors out by
hand) and walks every draw order exactly with `Fraction`s: a recursion over the set of families drawn
so far. It uses neither the data model nor the item model and knows no fossil.

A pool is `{family: (side, {mod id: final weight})}`; a mod of weight 0 is not in the game's pool, so
it is left out (or given as 0, which the oracle drops).

Rules it plays (the claims of the registry, written again as plain code): the number of mods of the
finished item is 4, 5 or 6 in the ratio 8:3:1 and the mods that stay on the item (fractured, forced)
count inside it, so `total - len(kept)` mods are drawn (none when that is negative); every draw picks
a family in proportion to the weight of its mods, from one pool of both sides; a family leaves the
pool once drawn; a side holds three mods and closes when it is full; the draws stop early when no
open family is left. A drawn family gives one of its mods in proportion to the weights.
"""

from collections import Counter, defaultdict
from collections.abc import Callable, Hashable
from fractions import Fraction
from functools import cache

PREFIX, SUFFIX = "prefix", "suffix"
CAP = 3
TOTALS = {4: Fraction(8, 12), 5: Fraction(3, 12), 6: Fraction(1, 12)}

Pool = dict[str, tuple[str, dict[str, Fraction | int]]]


def drawn_families(
    pool: Pool, kept: tuple[str, ...] = ()
) -> dict[frozenset[str], Fraction]:
    """The exact distribution of the set of families that the draws bring in.

    `kept` are the sides of the mods that stay on the item beside the drawn ones (fractured mods, a
    forced mod): they fill slots and count inside the total. Their own families are not in `pool`.
    """
    side_of = {family: side for family, (side, _) in pool.items()}
    weight = {
        family: sum(map(Fraction, mods.values()), Fraction(0))
        for family, (_, mods) in pool.items()
    }
    families = [family for family in pool if weight[family] > 0]
    used = {PREFIX: kept.count(PREFIX), SUFFIX: kept.count(SUFFIX)}

    @cache
    def walk(
        taken: frozenset[str], left: int
    ) -> tuple[tuple[frozenset[str], Fraction], ...]:
        if left == 0:
            return ((taken, Fraction(1)),)
        room = {
            side: CAP
            - used[side]
            - sum(1 for family in taken if side_of[family] == side)
            for side in used
        }
        open_ = [f for f in families if f not in taken and room[side_of[f]] > 0]
        if not open_:
            return ((taken, Fraction(1)),)
        whole = sum(weight[f] for f in open_)
        result: dict[frozenset[str], Fraction] = defaultdict(Fraction)
        for family in open_:
            for done, chance in walk(taken | {family}, left - 1):
                result[done] += weight[family] / whole * chance
        return tuple(result.items())

    answer: dict[frozenset[str], Fraction] = defaultdict(Fraction)
    for total, chance_of_total in TOTALS.items():
        for done, chance in walk(frozenset(), max(0, total - len(kept))):
            answer[done] += chance_of_total * chance
    return dict(answer)


def chance_all(pool: Pool, targets: list[str], kept: tuple[str, ...] = ()) -> Fraction:
    """The chance that the finished item holds every mod of `targets` that is drawn from `pool`.

    A target that is not in the pool (blocked, or of a family that is kept) has chance 0, and two
    targets of one family cannot be on one item.
    """
    where = {
        mod: family
        for family, (_, mods) in pool.items()
        for mod in mods
        if mods[mod] > 0
    }
    if any(mod not in where for mod in targets):
        return Fraction(0)
    families = [where[mod] for mod in targets]
    if len(set(families)) != len(families):
        return Fraction(0)
    share = Fraction(1)
    for mod, family in zip(targets, families):
        mods = pool[family][1]
        share *= Fraction(mods[mod]) / sum(map(Fraction, mods.values()), Fraction(0))
    reached = sum(
        (
            chance
            for done, chance in drawn_families(pool, kept).items()
            if set(families) <= done
        ),
        Fraction(0),
    )
    return share * reached


def distribution(
    pool: Pool,
    label: Callable[[str], Hashable],
    kept: tuple[tuple[str, Hashable], ...] = (),
    mark: Callable[[Hashable], Hashable] | None = None,
) -> dict[frozenset, Fraction]:
    """The exact distribution of the drawn mods seen through `label` (a function of the family name).

    An outcome is the set of `(label, count)` pairs of the drawn mods; the `kept` mods, given as
    `(side, label)`, are not in it. With `mark`, one mod of the finished item (a kept one included)
    is fractured, uniformly, and the outcome also holds the pair `(mark(label of that mod), 1)`.
    """
    result: dict[frozenset, Fraction] = defaultdict(Fraction)
    for done, chance in drawn_families(pool, tuple(side for side, _ in kept)).items():
        drawn = Counter(label(family) for family in done)
        outcome = frozenset(drawn.items())
        if mark is None:
            result[outcome] += chance
            continue
        everything = drawn + Counter(lab for _, lab in kept)
        number = sum(everything.values())
        for lab, count in everything.items():
            result[outcome | {(mark(lab), 1)}] += chance * Fraction(count, number)
    return dict(result)


def mix(parts: list[tuple[Fraction, dict]]) -> dict:
    """The mixture of distributions: `[(probability, distribution), ...]` into one."""
    result: dict = defaultdict(Fraction)
    for probability, part in parts:
        for outcome, chance in part.items():
            result[outcome] += probability * chance
    return dict(result)
