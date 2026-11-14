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
and the state is only how many families of each class have been drawn (on which side); the states
are walked forward, one draw at a time, and the labels of the drawn families are spread at the end
(`exact_distribution` says why that is exact, ticket #934). This is exact. The number of states grows with the number of distinct
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
from contextlib import contextmanager
from fractions import Fraction
from math import comb, gcd

from crafting_system.data import GameData, Mod
from crafting_system.items import Item, Side
from crafting_system.rules import get_rule

from .errors import UnmodelledBase
from .metamods import allowed_by_tags
from .pool import PoolFamily, PoolMod
from .scope import BasePassed, probing

__all__ = [
    "Outcome",
    "floating",
    "guaranteed_candidates",
]

Outcome = frozenset[tuple[Hashable, int]]

NUMBER: type = Fraction  # the number type of `exact_distribution`: Fraction, or float inside `floating()`


@contextmanager
def floating():
    """Within the block `exact_distribution` works in floats (ticket #626).

    The engine adds and multiplies positive numbers only (a chance is a product of weight ratios, and chances are summed), so no cancellation happens and each
    chance it returns is the exact one to a relative error of about (operations on a path) x 2^-53, a few 1e-14 at most for the draws of the game (six draws, as
    many classes). Whoever reads these chances as those of a lower bound must take that error off (`abstraction._pattern`: every chance is shrunk by 2^-30 and the
    mass that is missing goes to a state that costs nothing), and must not mix them with the exact ones (`Abstraction.approximate` keeps its own caches).
    """
    global NUMBER
    saved, NUMBER = NUMBER, float
    try:
        yield
    finally:
        NUMBER = saved

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

    Every refusal here reads the base alone, so it is an `UnmodelledBase`: the action refuses every item of the base (#848). Inside
    `scope.base_refusal` a base that passes stops the use here (`BasePassed`): the planner only asked whether the base is modelled.
    """
    item_class = jewel_class(data, item)
    if item_class is None:
        if probing():
            raise BasePassed
        return
    base = data.base_items[item.base_id]
    if base.release_state == "unique_only" or base.domain == NO_MOD_DOMAIN:  # the Assembled Eye Jewel has the domain "undefined" and no mod
        raise UnmodelledBase(
            f"the item is a {base.name}, a base that exists as a unique item only (the wiki: it is found as a unique "
            "and then converted to a non-unique rarity), so crafting it is not modelled"
        )
    if base.domain in CLUSTER_JEWEL_DOMAINS.value:
        raise UnmodelledBase(
            f"the item is a cluster jewel ({base.name}); its enchantments decide which mods it can roll "
            "and the item state holds no enchantment, so crafting it is not modelled"
        )
    if not jewels:
        reason = jewel_reason or (
            "the 4, 5 or 6 mod ratio is modelled for regular items only, so rerolling a jewel is not modelled yet"
        )
        raise UnmodelledBase(
            f"the item is a jewel; {reason}",
            detail=f"the item is a jewel ({item_class}); {reason}",
        )
    if probing():
        raise BasePassed


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

    **How, and why it is exact (ticket #934).** A *part* is one side of a class of families (see the module docstring). A draw
    picks the part `p` of class `c` with chance `(families of c not drawn yet) x W_p / (open weight)`, `W_p` the weight of one
    family's mods on that side, and then the label `l` of the mod with chance `w_pl / W_p`, `w_pl` the weight of that family's mods
    of that side with label `l`. Only the first factor reads what was drawn before, and only how many families of each part were
    taken (a family leaves the pool whichever of its mods was drawn); the second reads nothing of it (the families of a class have
    the same weights per label). So the labels of the drawn families are independent of each other and of the order of the
    draws, each with the chances `w_pl / W_p` of its part. The engine walks the parts alone, forward one draw at a time, a state
    holding one number (the chance of having drawn these many families of each part), and spreads each end state over the labels at
    the end: the `n` families drawn from part `p` take their labels as `n` independent draws from `w_pl / W_p` (a multinomial). The
    chance of an outcome is the sum, over the ways of reaching it, of the same products of ratios a draw-by-draw walk multiplies,
    grouped differently, so it is the same exact number. End states with the same counts give the same spread, so they are added
    before it is made.

    The earlier engine walked the same states backward and kept with each the whole distribution of the labels still to come; for a
    pool of many classes and labels (a fossil set, an essence on a base of many family types) that held millions of distributions
    and was most of the time of a fossil plan. A forward state holds one number, and the states of one draw are dropped once the
    next draw is made.
    """
    number = NUMBER
    zero = number(0)
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
            by_label: dict[int, Fraction] = defaultdict(number)
            for entry in family.mods:
                value = label(entry.mod)
                index = label_index.setdefault(value, len(label_index))
                if index == len(labels):
                    labels.append(value)
                mod_label[entry.mod.id] = index
                by_label[index] += number(entry.weight)
            weights = tuple(sorted(by_label.items()))
            parts.append((family.side is Side.PREFIX, weights, sum((w for _, w in weights), number(0))))
        key = tuple(sorted(parts))
        if key not in classes:
            classes[key] = len(class_parts)
            class_parts.append(key)
            class_count.append(0)
        class_count[classes[key]] += 1
        class_of[name] = classes[key]
    width = len(labels)

    # the parts: their class, side, the weight of one family's mods on that side and its (label, weight) pairs
    part_class: list[int] = []
    part_prefix: list[bool] = []
    part_weight: list = []
    part_labels: list[tuple[tuple[int, Fraction], ...]] = []
    part_of: dict[tuple[int, bool], int] = {}
    for index, parts in enumerate(class_parts):
        for on_prefix, weights, total in parts:
            part_of.setdefault((index, on_prefix), len(part_class))
            part_class.append(index)
            part_prefix.append(on_prefix)
            part_weight.append(int(total) if isinstance(total, Fraction) and total.denominator == 1 else total)  # an int when it is one: cheaper to multiply
            part_labels.append(weights)
    count = len(part_class)
    room = (free[Side.PREFIX], free[Side.SUFFIX])

    whole = number is Fraction and all(type(weight) is int for weight in part_weight)  # every weight an integer: the walk keeps (numerator, denominator) pairs

    def forward(start: tuple[int, ...], picks: int) -> list[tuple[dict, dict]]:
        """For 0 to `picks` draws made: the chance of each state reached, and of those of them where nothing can be drawn.

        With integer weights a chance is kept as a reduced pair of integers and added with one `gcd`, which is the same exact
        number as a `Fraction` at a third of the time (the walk is where a large draw spends it); it is a `Fraction` again on the way out.
        """
        out = []
        level: dict[tuple[int, ...], object] = {start: (1, 1) if whole else number(1)}
        for made in range(picks + 1):
            if made == picks:
                out.append((level, {}))
                break
            stuck: dict[tuple[int, ...], object] = {}
            following: dict[tuple[int, ...], object] = {}
            for state, chance in level.items():
                taken = [0] * len(class_count)
                room_prefix, room_suffix = room
                for part, n in enumerate(state):
                    if n:
                        taken[part_class[part]] += n
                        if part_prefix[part]:
                            room_prefix -= n
                        else:
                            room_suffix -= n
                steps = []
                total = 0
                for part in range(count):
                    if (room_prefix if part_prefix[part] else room_suffix) <= 0 or not part_weight[part]:
                        continue
                    remaining = class_count[part_class[part]] - taken[part_class[part]]
                    if remaining > 0:
                        weight = remaining * part_weight[part]
                        steps.append((part, weight))
                        total += weight
                if not steps:
                    stuck[state] = chance
                    continue
                if not whole:
                    each = chance / total
                    for part, weight in steps:
                        child = state[:part] + (state[part] + 1,) + state[part + 1 :]
                        step = each * weight
                        before = following.get(child)
                        following[child] = step if before is None else before + step
                    continue
                numerator, denominator = chance
                common = gcd(numerator, total)
                numerator, denominator = numerator // common, denominator * (total // common)  # chance / total, reduced
                for part, weight in steps:
                    child = state[:part] + (state[part] + 1,) + state[part + 1 :]
                    common = gcd(weight, denominator)
                    top, bottom = numerator * (weight // common), denominator // common  # chance x weight / total, reduced
                    before = following.get(child)
                    if before is not None:
                        other, under = before
                        if under == bottom:
                            top += other
                        else:
                            top, bottom = top * under + other * bottom, bottom * under
                        common = gcd(top, bottom)
                        top, bottom = top // common, bottom // common
                    following[child] = (top, bottom)
            out.append((level, stuck))
            level = following
        if whole:
            out = [tuple({state: Fraction(*pair) for state, pair in found.items()} for found in entry) for entry in out]
        return out

    def ends(start: tuple[int, ...], picks_by_chance: Mapping[int, Fraction]) -> dict[tuple[int, ...], Fraction]:
        """The chance of each end state of the draws from `start`, mixed over the numbers of draws to make."""
        levels = forward(start, max(picks_by_chance))
        result: dict[tuple[int, ...], Fraction] = defaultdict(number)
        for picks, weight in picks_by_chance.items():
            for made in range(picks + 1):
                level, stuck = levels[made]
                for state, chance in (level if made == picks else stuck).items():
                    result[state] += weight * chance
        return result

    spreads: dict[tuple[int, int], list[tuple[tuple[tuple[int, int], ...], Fraction]]] = {}

    def spread(part: int, n: int) -> list[tuple[tuple[tuple[int, int], ...], Fraction]]:
        """The labels `n` families drawn from `part` take, `((label, count), ...)`, each with its multinomial chance."""
        found = spreads.get((part, n))
        if found is None:
            options = part_labels[part]
            ways: list[tuple[tuple[tuple[int, int], ...], Fraction, int]] = [((), number(1), n)]
            for at, (lab, weight) in enumerate(options):
                share = weight / part_weight[part]
                grown = []
                for counts, chance, left in ways:
                    for k in [left] if at == len(options) - 1 else range(left + 1):
                        grown.append(((*counts, (lab, k)) if k else counts, chance * share**k * comb(left, k), left - k))
                ways = grown
            found = spreads[(part, n)] = [(counts, chance) for counts, chance, _ in ways if chance]
        return found

    tallies: dict[tuple[int, ...], Fraction] = defaultdict(number)

    def spread_ends(found: Mapping[tuple[int, ...], Fraction], fixed: tuple[int, int] | None, scale) -> None:
        """Add the outcomes of the end states `found`, times `scale`; `fixed` is the (part, label) of the guaranteed mod, whose label is known."""
        grouped: dict[tuple, Fraction] = defaultdict(number)
        for state, chance in found.items():
            base = [0] * width
            mixed = []
            for part, n in enumerate(state):
                if fixed is not None and part == fixed[0]:
                    n -= 1
                if not n:
                    continue
                if len(part_labels[part]) == 1:
                    base[part_labels[part][0][0]] += n
                else:
                    mixed.append((part, n))
            if fixed is not None:
                base[fixed[1]] += 1
            grouped[(tuple(base), tuple(mixed))] += chance
        for (base, mixed), chance in grouped.items():
            ways: list[tuple[tuple[int, ...], Fraction]] = [(base, chance * scale)]
            for part, n in mixed:
                grown = []
                for tally, before in ways:
                    for counts, each in spread(part, n):
                        after = list(tally)
                        for lab, k in counts:
                            after[lab] += k
                        grown.append((tuple(after), before * each))
                ways = grown
            for tally, each in ways:
                tallies[tally] += each

    start = (0,) * count
    picks_of: dict[int, Fraction] = {}
    for total, chance in totals.items():
        picks = max(0, total - kept - (tag is not None))
        picks_of[picks] = picks_of.get(picks, zero) + number(chance)
    if tag is None:
        spread_ends(ends(start, picks_of), None, number(1))
    else:
        groups: dict[tuple[int, int, Fraction], int] = defaultdict(int)
        for family, entry in guaranteed_candidates(pool, free, tag, blocked):
            groups[(part_of[(class_of[family.family], family.side is Side.PREFIX)], mod_label[entry.mod.id], entry.weight)] += 1
        tagged_total = sum((n * number(weight) for (_, _, weight), n in groups.items()), number(0))
        by_part: dict[int, list[tuple[int, Fraction]]] = defaultdict(list)
        for (part, lab, weight), n in groups.items():
            by_part[part].append((lab, n * number(weight) / tagged_total))
        for part, chosen in by_part.items():
            found = ends(start[:part] + (1,) + start[part + 1 :], picks_of)
            for lab, step in chosen:
                spread_ends(found, (part, lab), step)
    return {
        frozenset((labels[i], count) for i, count in enumerate(tally) if count): chance
        for tally, chance in tallies.items()
        if chance
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
