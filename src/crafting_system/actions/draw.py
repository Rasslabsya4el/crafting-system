"""The reroll process that a Chaos Orb and a tagged Harvest reforge share, exactly and by sampling.

A reroll keeps the fractured mods, then draws the rest of a total of 4, 5 or 6 mods (8:3:1) from
the pool one mod at a time. The kept mods count inside the total, so only `total - kept` mods are
drawn, and none when the kept mods reach it (`KEPT_MODS_COUNT_IN_TOTAL`). A tagged reforge first
draws one guaranteed mod with its tag, which counts inside the total as well and is drawn whatever
the total is (`GUARANTEED_MOD_COUNTS_IN_TOTAL`). Every ordinary draw picks one mod from the prefixes
and suffixes together in proportion to weight; its whole family leaves the pool and its side uses a
slot; a side that is full closes (`DRAW_PROPORTIONAL_TO_WEIGHT`, `ONE_POOL_FOR_BOTH_SIDES`,
`FULL_SIDE_CLOSES`). When nothing can be drawn before the total is reached the reroll stops with
fewer mods (`DRY_POOL_LEAVES_FEWER_MODS`).

The exact engine does not track which family was drawn. Two families that the caller's label cannot
tell apart (same side, same weight per label) are interchangeable, so they are grouped into a class
and the state is only how many families of each class have been drawn plus the free slots; states
are memoised. This is exact. The number of states grows with the number of distinct
(side, weight per label) classes, not with the number of families, so a pool whose families all
have different weights, or a label that tells many mods apart, gives many states.
"""

import random
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping
from fractions import Fraction
from functools import cache

from crafting_system.data import GameData, Mod
from crafting_system.items import Item, Side
from crafting_system.rules import get_rule

from .errors import OutOfScopeError
from .pool import PoolFamily, PoolMod

Outcome = frozenset[tuple[Hashable, int]]

RARE_REROLL_RATIO = get_rule("affix_count.rare_reroll_ratio")
KEPT_MODS_COUNT_IN_TOTAL = get_rule("chaos_orb.kept_mods_count_in_total")
DRY_POOL_LEAVES_FEWER_MODS = get_rule("chaos_orb.dry_pool_leaves_fewer_mods")
RARE_JEWEL_MAX_PER_SIDE = get_rule("affix_count.rare_jewel_max_per_side")
TAG_IS_IMPLICIT_TAG = get_rule("harvest_reforge.tag_is_implicit_tag")
GUARANTEED_DRAW_FIRST_BY_WEIGHT = get_rule("harvest_reforge.guaranteed_draw_first_by_weight")
GUARANTEED_MOD_COUNTS_IN_TOTAL = get_rule("harvest_reforge.guaranteed_mod_counts_in_total")
DRAW_PROPORTIONAL_TO_WEIGHT = get_rule("affix_pool.draw_proportional_to_weight")
ONE_POOL_FOR_BOTH_SIDES = get_rule("affix_pool.one_pool_for_both_sides")
FULL_SIDE_CLOSES = get_rule("affix_pool.full_side_closes")

ONE = Fraction(1)


def refuse_unmodelled(data: GameData, item: Item) -> None:
    """Raise `OutOfScopeError` for an item in a state no admitted rule covers yet.

    Called after each action's own checks of rarity and corruption, each of which cites its own claim.
    A rare jewel is out of scope: the 8:3:1 ratio is the claim for regular items, not for jewels.
    """
    base = data.base_items.get(item.base_id)
    if base is not None and base.item_class in RARE_JEWEL_MAX_PER_SIDE.value["item_classes"]:
        raise OutOfScopeError(
            f"the item is a jewel ({base.item_class}); the 4, 5 or 6 mod ratio is admitted for "
            "regular items only, so rerolling a jewel is not modelled yet"
        )
    if item.influences:
        raise OutOfScopeError(
            "the item has an influence, and the influence tags of the pool are not modelled yet"
        )
    if item.crafted_mods:
        raise OutOfScopeError(
            "the item has a crafted mod or metamod; bench mods and metamods are not modelled yet"
        )


def total_distribution() -> Mapping[int, Fraction]:
    """The probability of each total number of mods of a rerolled rare item, from the 8:3:1 ratio."""
    ratio = RARE_REROLL_RATIO.value
    whole = sum(ratio.values())
    return {total: Fraction(share, whole) for total, share in ratio.items()}


def guaranteed_candidates(
    pool: Iterable[PoolFamily], free: Mapping[Side, int], tag: str
) -> list[tuple[PoolFamily, PoolMod]]:
    """The mods that carry `tag` and whose side still has a free slot: what the guaranteed draw picks from."""
    return [
        (family, entry)
        for family in pool
        if free[family.side] > 0
        for entry in family.mods
        if tag in entry.mod.implicit_tags
    ]


def exact_distribution(
    pool: tuple[PoolFamily, ...],
    free: Mapping[Side, int],
    tag: str | None,
    totals: Mapping[int, Fraction],
    kept: int,
    label: Callable[[Mod], Hashable],
) -> dict[Outcome, Fraction]:
    """The exact distribution of the new mods, seen through `label`, as `{outcome: probability}`.

    An outcome is the set of `(label, how many new mods got it)` pairs, labels with a count of at
    least one only. `free` is the number of free slots per side on the retained item, `tag` the
    guaranteed tag or None, `kept` how many mods the retained item holds. `label` is called once
    per candidate mod and must be pure.
    """
    labels: list[Hashable] = []
    label_index: dict[Hashable, int] = {}
    classes: dict[tuple, int] = {}
    class_weights: list[tuple[tuple[int, Fraction], ...]] = []
    class_count: list[int] = []
    on_prefix: list[bool] = []
    class_of: dict[str, int] = {}
    mod_label: dict[str, int] = {}
    for family in pool:
        by_label: dict[int, Fraction] = defaultdict(Fraction)
        for entry in family.mods:
            value = label(entry.mod)
            index = label_index.setdefault(value, len(label_index))
            if index == len(labels):
                labels.append(value)
            mod_label[entry.mod.id] = index
            by_label[index] += entry.weight
        weights = tuple(sorted(by_label.items()))
        key = (family.side, weights)
        if key not in classes:
            classes[key] = len(class_weights)
            class_weights.append(weights)
            class_count.append(0)
            on_prefix.append(family.side is Side.PREFIX)
        class_count[classes[key]] += 1
        class_of[family.family] = classes[key]
    width = len(labels)
    class_total = [sum((w for _, w in weights), Fraction(0)) for weights in class_weights]

    @cache
    def walk(
        drawn: tuple[int, ...], room_prefix: int, room_suffix: int, picks: int
    ) -> dict[tuple[int, ...], Fraction]:
        """The distribution of the label counts of the draws still to come from this state."""
        nothing = {(0,) * width: ONE}
        if picks == 0:
            return nothing
        eligible = [
            index
            for index, taken in enumerate(drawn)
            if class_count[index] > taken and (room_prefix if on_prefix[index] else room_suffix) > 0
        ]
        if not eligible:
            return nothing
        total = sum((class_count[i] - drawn[i]) * class_total[i] for i in eligible)
        result: dict[tuple[int, ...], Fraction] = defaultdict(Fraction)
        for index in eligible:
            remaining = class_count[index] - drawn[index]
            child = walk(
                drawn[:index] + (drawn[index] + 1,) + drawn[index + 1 :],
                room_prefix - on_prefix[index],
                room_suffix - (not on_prefix[index]),
                picks - 1,
            )
            for lab, weight in class_weights[index]:
                step = remaining * weight / total
                for tally, chance in child.items():
                    result[tally[:lab] + (tally[lab] + 1,) + tally[lab + 1 :]] += step * chance
        return dict(result)

    start = (0,) * len(class_count)
    guaranteed: list[tuple[int, int, Fraction]] = []
    if tag is not None:
        groups: dict[tuple[int, int, Fraction], int] = defaultdict(int)
        for family, entry in guaranteed_candidates(pool, free, tag):
            groups[(class_of[family.family], mod_label[entry.mod.id], entry.weight)] += 1
        tagged_total = sum((n * weight for (_, _, weight), n in groups.items()), Fraction(0))
        guaranteed = [(cls, lab, n * weight / tagged_total) for (cls, lab, weight), n in groups.items()]
    tallies: dict[tuple[int, ...], Fraction] = defaultdict(Fraction)
    for total, chance in totals.items():
        picks = max(0, total - kept - (tag is not None))
        if tag is None:
            for tally, inner in walk(start, free[Side.PREFIX], free[Side.SUFFIX], picks).items():
                tallies[tally] += chance * inner
            continue
        for cls, lab, step in guaranteed:
            inner_all = walk(
                start[:cls] + (1,) + start[cls + 1 :],
                free[Side.PREFIX] - on_prefix[cls],
                free[Side.SUFFIX] - (not on_prefix[cls]),
                picks,
            )
            for tally, inner in inner_all.items():
                tallies[tally[:lab] + (tally[lab] + 1,) + tally[lab + 1 :]] += chance * step * inner
    return {
        frozenset((labels[i], count) for i, count in enumerate(tally) if count): chance
        for tally, chance in tallies.items()
    }


def sample_new_mods(
    pool: tuple[PoolFamily, ...],
    free: Mapping[Side, int],
    tag: str | None,
    total: int,
    kept: int,
    rng: random.Random,
    floats: Mapping[str, float],
) -> list[PoolMod]:
    """The new mods of one reroll in the order they were drawn: the same process, drawn at random.

    `floats` maps a mod id to its weight as a float, converted once by the caller: the exact
    fractions stay in the pool, and a float is good enough for a random pick.
    """
    room = dict(free)
    open_families = list(pool)
    drawn: list[PoolMod] = []

    def take(candidates: list[tuple[PoolFamily, PoolMod]]) -> None:
        family, entry = rng.choices(candidates, weights=[floats[c[1].mod.id] for c in candidates])[0]
        open_families.remove(family)
        room[family.side] -= 1
        drawn.append(entry)

    if tag is not None:
        take(guaranteed_candidates(open_families, room, tag))
    for _ in range(max(0, total - kept - (tag is not None))):
        candidates = [
            (family, entry)
            for family in open_families
            if room[family.side] > 0
            for entry in family.mods
        ]
        if not candidates:
            break
        take(candidates)
    return drawn
