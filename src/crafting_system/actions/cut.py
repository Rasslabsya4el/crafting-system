"""The tier cut of an item with Memory Strands, and what the kept tiers weigh (ADR-0040, ADR-0042; ticket #275).

An item with one strand or more, or a draw by a Foulborn orb, sees only the highest tiers of each tier table. A tier table is the mods
of one mod type (with its generation type and domain) that the pool admits: they pass the level gate of the draw, so a tier the item
level forbids is not counted. `T` is the number of tiers of the table, and the draw keeps its `K` best, in exact integers:

    K = floor(200 (T - 1) / D) + 1,   D = 200 + [s >= 1] (5 s + 95) + [Foulborn] 150

which is the wiki's `floor(100 (T - 1) / (2.5 s + 147.5 + 75 [Foulborn])) + 1` multiplied by 2 above and below, with no float
(8 tiers at 81 strands is exactly 2.0 before the floor: K is 3, and 82 strands gives 2). 0 strands without a Foulborn orb has
`D = 200` and so `K = T`: no cut. A Foulborn orb on an item with no strands has `D = 350`; that case rests on the wiki alone
(`foulborn.zero_strand_cut_matches_eleven_strands`, `approximate`). The count is the one the item has before the craft: the craft's
own spend comes after the cut (`memory_strands.cut_uses_strands_before_spend`), so the caller gives the pool the item as it stands.

`Cut(strands, foulborn, reading)` is what a pool takes; `Cut.of(item)` reads the count off the item. What the kept tiers weigh is
`WeightReading` (ADR-0042): the plan reads the claim `memory_strands.weights_of_kept_tiers` (the sheet fit chose the refactored
weight); the other two readings stay available as a parameter. `cut_weights` applies a cut to the weighted mods of a pool.

A pool is cut only when the action asks for it: an action's contract says whether its draws cut (`Adds.cuts`, ADR-0041), and a fossil,
a Harvest craft or a beast never does. Fixed mods (an essence's guaranteed mod, a crafted mod) are not drawn from a tier table by
chance and are not cut either; the caller adds them outside the pool.

The claims this module holds are named by an action that imports from it (`Action.claims`); a pool built without a cut names none of
them, so no answer that does not use strands lists the (approximate) strand claims.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from crafting_system.data import Mod
from crafting_system.items import MAX_MEMORY_STRANDS, Item, MemoryStrandsError
from crafting_system.rules import get_rule

ROLLABLE_TIERS = get_rule("memory_strands.rollable_tiers")
CULL_COUNTS_ELIGIBLE_TIERS = get_rule("memory_strands.cull_counts_eligible_tiers")
ZERO_IS_NO_CULL = get_rule("memory_strands.zero_is_no_cull")
CUT_USES_STRANDS_BEFORE_SPEND = get_rule("memory_strands.cut_uses_strands_before_spend")
WEIGHTS_OF_KEPT_TIERS = get_rule("memory_strands.weights_of_kept_tiers")
FOULBORN_ON_STRANDED_ITEM = get_rule("foulborn.on_stranded_item")
FOULBORN_BONUS_IS_ADDED = get_rule("foulborn.bonus_is_added_to_the_strand_denominator")
FOULBORN_ZERO_STRAND_CUT = get_rule("foulborn.zero_strand_cut_matches_eleven_strands")
FOULBORN_EFFECT = get_rule("foulborn.effect_tier_cull")

_NUMERATOR: int = ROLLABLE_TIERS.value["numerator"]
_BASE_RATING: int = ROLLABLE_TIERS.value["base_rating"]
_PER_STRAND: int = ROLLABLE_TIERS.value["strand_rating_per_strand"]
_OFFSET: int = ROLLABLE_TIERS.value["strand_rating_offset"]
_FOULBORN_RATING: int = ROLLABLE_TIERS.value["foulborn_rating"]


class WeightReading(StrEnum):
    """What the kept tiers of a mod type weigh after a cut (ADR-0042); the readings 1, 2 and 3 of its table.

    With tiers of weights 100, 200, 400, 800 and a cut that keeps the first two, the kept weights are 500 and 1000, 200 and 400,
    100 and 200. The chosen tier inside the type has the same odds in all three; they differ in the chance of the type against
    the other types of its side.
    """

    REDISTRIBUTION = "redistribution"  # 1: the removed weight goes to the kept tiers of the same type, by their weights; the type keeps its total
    REFACTORED = "refactored"  # 2: each kept weight times (tiers before) / (tiers kept)
    DELETE_ONLY = "delete_only"  # 3: the kept tiers keep their weights


PLAN_READING = WeightReading(WEIGHTS_OF_KEPT_TIERS.value["reading"])


def strand_rating(strands: int, foulborn: bool = False) -> int:
    """The denominator `D` of the cut, doubled so that it is a whole number: 200 + [s >= 1] (5 s + 95) + [Foulborn] 150.

    `strands` is any whole number from 0 up: the wiki's table runs to 122, past the 100 an item can hold, and the formula is defined there.
    """
    if type(strands) is not int or strands < 0:
        raise MemoryStrandsError(f"memory strands {strands!r} is not a whole number from 0")
    return _BASE_RATING + (_PER_STRAND * strands + _OFFSET if strands >= 1 else 0) + (_FOULBORN_RATING if foulborn else 0)


def rollable_tiers(total_tiers: int, strands: int, foulborn: bool = False) -> int:
    """The number of highest tiers a draw sees in a tier table of `total_tiers` eligible tiers, by integer arithmetic only.

    `total_tiers` is at least 1 and the result runs from 1 to `total_tiers`. With no strand and no Foulborn orb it is `total_tiers`.
    See `strand_rating` for `strands`.
    """
    if type(total_tiers) is not int or total_tiers < 1:
        raise ValueError(f"a tier table has at least one tier, got {total_tiers!r}")
    return _NUMERATOR * (total_tiers - 1) // strand_rating(strands, foulborn) + 1


@dataclass(frozen=True, slots=True)
class Cut:
    """The cut a draw makes: the strand count the item has before the craft, whether a Foulborn orb draws, and the weight reading.

    `active` is false for 0 strands without a Foulborn orb: that cut keeps every tier, and a pool built with it equals the pool built
    with no cut at all (and `reading` does not matter).
    """

    strands: int = 0
    foulborn: bool = False
    reading: WeightReading = PLAN_READING

    def __post_init__(self) -> None:
        if type(self.strands) is not int or not 0 <= self.strands <= MAX_MEMORY_STRANDS:
            raise MemoryStrandsError(f"memory strands {self.strands!r} is not a whole number from 0 to {MAX_MEMORY_STRANDS}")
        if type(self.foulborn) is not bool:
            raise ValueError(f"the Foulborn flag of a cut is a bool, got {self.foulborn!r}")
        if not isinstance(self.reading, WeightReading):
            raise ValueError(f"the reading of a cut is a WeightReading, got {self.reading!r}")

    @classmethod
    def of(cls, item: Item, *, foulborn: bool = False, reading: WeightReading = PLAN_READING) -> "Cut":
        """The cut of a draw on `item` as it stands (its count is the one before the craft)."""
        return cls(item.memory_strands, foulborn, reading)

    @property
    def active(self) -> bool:
        """Whether the cut can remove a tier: one strand or more, or a Foulborn orb."""
        return self.strands >= 1 or self.foulborn

    def kept(self, total_tiers: int) -> int:
        """The number of tiers kept of a table of `total_tiers` (`rollable_tiers` at this cut)."""
        return rollable_tiers(total_tiers, self.strands, self.foulborn)


def cut_weights(weighted: Sequence[tuple[Mod, Fraction]], cut: Cut) -> tuple[tuple[Mod, Fraction], ...]:
    """The `(mod, weight)` pairs of a pool after `cut`, in the order given: the low tiers of each tier table dropped, the rest reweighed.

    Each tier table is the mods of one `(type, generation type, domain)` among `weighted`, whose tiers are the distinct required levels
    from the highest down (mods that tie on the level share a tier). A table of `T` tiers keeps its `cut.kept(T)` highest. Under
    `WeightReading.REDISTRIBUTION` the kept weights are scaled to the table's whole weight, under `REFACTORED` multiplied by `T / K`,
    under `DELETE_ONLY` left alone. Weights stay exact fractions. An inactive cut returns the pairs unchanged.
    """
    if not cut.active:
        return tuple(weighted)
    tables: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for position, (mod, _) in enumerate(weighted):
        tables[(mod.type, mod.generation_type, mod.domain)].append(position)
    result: list[tuple[Mod, Fraction] | None] = list(weighted)
    for positions in tables.values():
        levels = sorted({weighted[position][0].required_level for position in positions}, reverse=True)
        total, kept = len(levels), cut.kept(len(levels))
        if kept >= total:
            continue
        lowest_kept = levels[kept - 1]
        whole = sum((weighted[position][1] for position in positions), Fraction(0))
        remaining = sum((weighted[position][1] for position in positions if weighted[position][0].required_level >= lowest_kept), Fraction(0))
        scale = _scale(cut.reading, whole, remaining, total, kept)
        for position in positions:
            mod, weight = weighted[position]
            result[position] = (mod, weight * scale) if mod.required_level >= lowest_kept else None
    return tuple(entry for entry in result if entry is not None)


def _scale(reading: WeightReading, whole: Fraction, remaining: Fraction, total: int, kept: int) -> Fraction:
    """The factor on the weight of a kept mod of a table that lost tiers."""
    if reading is WeightReading.REDISTRIBUTION:
        return whole / remaining
    if reading is WeightReading.REFACTORED:
        return Fraction(total, kept)
    return Fraction(1)


__all__ = [
    "Cut",
    "PLAN_READING",
    "WeightReading",
    "cut_weights",
    "rollable_tiers",
    "strand_rating",
]
