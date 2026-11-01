"""The reroll process that a Chaos Orb, a tagged Harvest reforge and an essence share, exactly and by sampling.

A reroll keeps the fractured mods (an essence also puts its forced mod on the item, which is kept
too) and removes every other mod, an ordinary crafted one included. It then draws the rest of a
total of 4, 5 or 6 mods (8:3:1) from the pool one mod at a time. The kept mods count inside the
total, so only `total - kept` mods are drawn, and none when the kept mods reach it (`KEPT_MODS_COUNT_IN_TOTAL`). A tagged reforge first
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

A family can have mods on both sides (five families of the base jewels do, `FAMILY_MAY_SPAN_BOTH_SIDES`). Its
two `PoolFamily` are one unit: a draw picks one mod of the unit in proportion to weight among the sides
that have room, and the unit leaves the pool whichever side it was drawn on. Units are interchangeable
when their parts have the same sides and the same weights per label, as one-sided families are.
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
from .metamods import allowed_by_tags
from .pool import PoolFamily, PoolMod

__all__ = [
    "Outcome",
    "guaranteed_candidates",
]

Outcome = frozenset[tuple[Hashable, int]]

RARE_REROLL_RATIO = get_rule("affix_count.rare_reroll_ratio")
KEPT_MODS_COUNT_IN_TOTAL = get_rule("chaos_orb.kept_mods_count_in_total")
DRY_POOL_LEAVES_FEWER_MODS = get_rule("chaos_orb.dry_pool_leaves_fewer_mods")
RARE_JEWEL_MAX_PER_SIDE = get_rule("affix_count.rare_jewel_max_per_side")
CHAOS_REMOVES_CRAFTED_MODS = get_rule("chaos_orb.removes_crafted_mods")
HARVEST_REMOVES_CRAFTED_MODS = get_rule("harvest_reforge.removes_crafted_mods")
TAG_IS_IMPLICIT_TAG = get_rule("harvest_reforge.tag_is_implicit_tag")
GUARANTEED_DRAW_FIRST_BY_WEIGHT = get_rule("harvest_reforge.guaranteed_draw_first_by_weight")
GUARANTEED_MOD_COUNTS_IN_TOTAL = get_rule("harvest_reforge.guaranteed_mod_counts_in_total")
DRAW_PROPORTIONAL_TO_WEIGHT = get_rule("affix_pool.draw_proportional_to_weight")
ONE_POOL_FOR_BOTH_SIDES = get_rule("affix_pool.one_pool_for_both_sides")
FULL_SIDE_CLOSES = get_rule("affix_pool.full_side_closes")
FAMILY_MAY_SPAN_BOTH_SIDES = get_rule("affix_pool.family_may_span_both_sides")
NO_MOD_DOMAIN = "undefined"
CLUSTER_JEWEL_DOMAINS = get_rule("jewel.cluster_pool_depends_on_enchantments")
JEWEL_REROLL_COUNT = get_rule("jewel.reroll_mod_count")

ONE = Fraction(1)


def jewel_class(data: GameData, item: Item) -> str | None:
    """The item class of `item` when it is a jewel (`affix_count.rare_jewel_max_per_side` lists the classes), else None."""
    base = data.base_items.get(item.base_id)
    if base is not None and base.item_class in RARE_JEWEL_MAX_PER_SIDE.value["item_classes"]:
        return base.item_class
    return None


def refuse_unmodelled(data: GameData, item: Item, jewel_reason: str | None = None, *, jewels: bool = False) -> None:
    """Raise `OutOfScopeError` for an item in a state no admitted rule covers yet.

    Called after each action's own checks of rarity and corruption, each of which cites its own claim.
    An action that works on jewels passes `jewels=True` (the claim `jewel.ordinary_orbs_work_on_jewels` holds
    for the ordinary orbs, `jewel.fossils_work_on_jewels` for fossils); a jewel is still refused when it is a
    cluster jewel, whose pool depends on its enchantments (`jewel.cluster_pool_depends_on_enchantments`).
    Any other action refuses every jewel (`jewel_reason` says what else is admitted for regular items only).
    Ordinary crafted mods are not out of scope: a reforge removes them (`chaos_orb.removes_crafted_mods`,
    `harvest_reforge.removes_crafted_mods`, `essence.reforge_removes_crafted_mods`), and neither is a
    metamod (`metamods.py` says what it changes).
    """
    item_class = jewel_class(data, item)
    if item_class is None:
        return
    base = data.base_items[item.base_id]
    if base.release_state == "unique_only" or base.domain == NO_MOD_DOMAIN:  # the Assembled Eye Jewel has the domain "undefined" and no mod
        raise OutOfScopeError(
            f"the item is a {base.name}, a base that exists as a unique item only (the wiki: it is found as a unique "
            "and then converted to a non-unique rarity), so crafting it is not modelled"
        )
    if base.domain in CLUSTER_JEWEL_DOMAINS.value:
        raise OutOfScopeError(
            f"the item is a cluster jewel ({base.name}); its enchantments decide which mods it can roll "
            "and the item state holds no enchantment, so crafting it is not modelled"
        )
    if not jewels:
        reason = jewel_reason or (
            "the 4, 5 or 6 mod ratio is admitted for regular items only, so rerolling a jewel is not modelled yet"
        )
        raise OutOfScopeError(f"the item is a jewel ({item_class}); {reason}")


def total_distribution(data: GameData | None = None, item: Item | None = None) -> Mapping[int, Fraction]:
    """The probability of each total number of mods of a rerolled rare item, from the 8:3:1 ratio.

    A jewel (`item` on a jewel base of `data`) takes the 3 or 4 mods of `jewel.reroll_mod_count` (65:35).
    """
    jewel = data is not None and item is not None and jewel_class(data, item) is not None
    ratio = JEWEL_REROLL_COUNT.value if jewel else RARE_REROLL_RATIO.value
    whole = sum(ratio.values())
    return {total: Fraction(share, whole) for total, share in ratio.items()}


def guaranteed_candidates(
    pool: Iterable[PoolFamily], free: Mapping[Side, int], tag: str, blocked: frozenset[str] = frozenset()
) -> list[tuple[PoolFamily, PoolMod]]:
    """The mods that carry `tag` and none of the `blocked` tags, and whose side still has a free slot: what the guaranteed draw picks from."""
    return [
        (family, entry)
        for family in pool
        if free[family.side] > 0
        for entry in family.mods
        if tag in entry.mod.implicit_tags and allowed_by_tags(entry.mod, blocked)
    ]


def exact_distribution(
    pool: tuple[PoolFamily, ...],
    free: Mapping[Side, int],
    tag: str | None,
    totals: Mapping[int, Fraction],
    kept: int,
    label: Callable[[Mod], Hashable],
    blocked: frozenset[str] = frozenset(),
) -> dict[Outcome, Fraction]:
    """The exact distribution of the new mods, seen through `label`, as `{outcome: probability}`.

    An outcome is the set of `(label, how many new mods got it)` pairs, labels with a count of at
    least one only. `free` is the number of free slots per side on the retained item, `tag` the
    guaranteed tag or None, `kept` how many mods the retained item holds. `label` is called once
    per candidate mod and must be pure. `blocked` are the tags the guaranteed draw may not pick (a
    Harvest reforge under an Attack or Caster metamod: it filters that first mod only).
    """
    labels: list[Hashable] = []
    label_index: dict[Hashable, int] = {}
    classes: dict[tuple, int] = {}
    class_parts: list[tuple[tuple[bool, tuple[tuple[int, Fraction], ...], Fraction], ...]] = []
    class_count: list[int] = []
    class_of: dict[str, int] = {}
    mod_label: dict[str, int] = {}
    units: dict[str, list[PoolFamily]] = defaultdict(list)
    for family in pool:
        units[family.family].append(family)
    for name, sides in units.items():
        parts = []
        for family in sides:
            by_label: dict[int, Fraction] = defaultdict(Fraction)
            for entry in family.mods:
                value = label(entry.mod)
                index = label_index.setdefault(value, len(label_index))
                if index == len(labels):
                    labels.append(value)
                mod_label[entry.mod.id] = index
                by_label[index] += entry.weight
            weights = tuple(sorted(by_label.items()))
            parts.append((family.side is Side.PREFIX, weights, sum((w for _, w in weights), Fraction(0))))
        key = tuple(sorted(parts))
        if key not in classes:
            classes[key] = len(class_parts)
            class_parts.append(key)
            class_count.append(0)
        class_count[classes[key]] += 1
        class_of[name] = classes[key]
    width = len(labels)

    @cache
    def walk(
        drawn: tuple[int, ...], room_prefix: int, room_suffix: int, picks: int
    ) -> dict[tuple[int, ...], Fraction]:
        """The distribution of the label counts of the draws still to come from this state.

        A unit is a family: one part per side it has mods on, and drawing a mod of either part takes the unit out.
        """
        nothing = {(0,) * width: ONE}
        if picks == 0:
            return nothing
        open_weight = {}
        for index, taken in enumerate(drawn):
            if class_count[index] > taken:
                weight = sum(
                    (total for on_prefix, _, total in class_parts[index] if (room_prefix if on_prefix else room_suffix) > 0),
                    Fraction(0),
                )
                if weight:
                    open_weight[index] = weight
        if not open_weight:
            return nothing
        total = sum(((class_count[i] - drawn[i]) * weight for i, weight in open_weight.items()), Fraction(0))
        result: dict[tuple[int, ...], Fraction] = defaultdict(Fraction)
        for index in open_weight:
            remaining = class_count[index] - drawn[index]
            for on_prefix, weights, _ in class_parts[index]:
                if (room_prefix if on_prefix else room_suffix) <= 0:
                    continue
                child = walk(
                    drawn[:index] + (drawn[index] + 1,) + drawn[index + 1 :],
                    room_prefix - on_prefix,
                    room_suffix - (not on_prefix),
                    picks - 1,
                )
                for lab, weight in weights:
                    step = remaining * weight / total
                    for tally, chance in child.items():
                        result[tally[:lab] + (tally[lab] + 1,) + tally[lab + 1 :]] += step * chance
        return dict(result)

    start = (0,) * len(class_count)
    guaranteed: list[tuple[int, bool, int, Fraction]] = []
    if tag is not None:
        groups: dict[tuple[int, bool, int, Fraction], int] = defaultdict(int)
        for family, entry in guaranteed_candidates(pool, free, tag, blocked):
            groups[(class_of[family.family], family.side is Side.PREFIX, mod_label[entry.mod.id], entry.weight)] += 1
        tagged_total = sum((n * weight for (_, _, _, weight), n in groups.items()), Fraction(0))
        guaranteed = [(cls, on_prefix, lab, n * weight / tagged_total) for (cls, on_prefix, lab, weight), n in groups.items()]
    tallies: dict[tuple[int, ...], Fraction] = defaultdict(Fraction)
    for total, chance in totals.items():
        picks = max(0, total - kept - (tag is not None))
        if tag is None:
            for tally, inner in walk(start, free[Side.PREFIX], free[Side.SUFFIX], picks).items():
                tallies[tally] += chance * inner
            continue
        for cls, on_prefix, lab, step in guaranteed:
            inner_all = walk(
                start[:cls] + (1,) + start[cls + 1 :],
                free[Side.PREFIX] - on_prefix,
                free[Side.SUFFIX] - (not on_prefix),
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
    blocked: frozenset[str] = frozenset(),
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
        open_families[:] = [other for other in open_families if other.family != family.family]  # both sides of a family leave
        room[family.side] -= 1
        drawn.append(entry)

    if tag is not None:
        take(guaranteed_candidates(open_families, room, tag, blocked))
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
