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

import contextvars
import random
from collections import OrderedDict, defaultdict
from collections.abc import Callable, Hashable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from fractions import Fraction
from math import comb, gcd

from crafting_system import budget
from crafting_system.data import GameData, Mod
from crafting_system.items import Item, Side
from crafting_system.rules import get_rule

from .errors import UnmodelledBase
from .metamods import allowed_by_tags
from .pool import PoolFamily, PoolMod
from .scope import BasePassed, probing

__all__ = [
    "DrawStore",
    "Outcome",
    "floating",
    "sharing",
    "shared_draws",
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


DRAWS_SHARE = 0.15  # the share of the run's memory net (or of the machine's default net) the draws kept for a plan may fill (`sharing`)
OUTCOME_BYTES = 1200  # what one kept outcome takes, about: its set of (label, count) pairs, its chance and its place in the table (measured on
# a draw of 15,380 outcomes of the real boots pool, #1194: 1,212 bytes each)
DRAWS_KEPT = 1_000_000  # the outcomes kept where neither the run nor the machine says how much memory there is
GIVE_WAY = 0.6  # the draws are dropped, and no new one is kept, once the process holds this share of the run's memory net


class DrawStore:
    """The walks of `exact_distributions` made for one plan, kept so that no part of the plan makes one of them twice (#1194).

    A plan searches its offers in rounds, each round with a model of its own (`abstraction.Abstraction`), whose caches start empty: the round
    then made again every draw the round before it had made (R20: about 6 s for each of the large ones, in every round). What a walk reads
    is not the model, though. It reads the pool through the caller's label only as a partition: which mods share a label, never what the label
    is. So the key of a walk is what the engine works from once the labels are numbered in the order the pool shows them: the number type,
    the classes of families with their sides, their weights per label number and their counts, the free slots, the totals and their chances,
    the mods kept, the guaranteed draw's candidates (per part, label number and weight, in the order met) and, for each view, how it merges
    the parts and the labels. Two calls with equal keys make the same walk step for step, so they give the same chances in the same order,
    with the labels of one where the other has its own. The store keeps the result with its labels; a later call with the same labels gets a
    copy, one with other labels gets it renamed (label number by label number; the store then keeps it under the new names), and both are
    what the walk would have returned, to the last digit and in the same order. A model of more offers that tells the mods apart as an earlier one did (or names the same kinds otherwise:
    a family type is "~3" in one model and "~5" in the next) therefore makes no walk the earlier one made; where it tells them apart more
    finely the key differs and the walk is made, as it must be.

    Nothing a plan says can depend on the store: a call gets the same result with or without it. Under a search counted in states
    (`budget.Allowance` with a `given`) a kept walk adds to each stage's count what its making added, when the store holds those counts
    and they fit the allowance; otherwise the walk is made again, counted, and cut where it would have been cut. So a run counted in states
    stops where it stopped before.

    **Memory.** `limit` is the number of outcomes kept: the walks least recently used leave once it is passed, and a walk larger than the
    limit is not kept. The process's memory holds the store, so the run's memory net sees it; once the process holds `GIVE_WAY` of that net
    the store is emptied and keeps nothing more (`sharing` gives it the net), so that the store is never what stops a run.
    """

    def __init__(self, limit: int, memory_mb: float | None = None) -> None:
        self.limit = max(int(limit), 0)
        self.memory_mb = memory_mb  # the run's memory net, or None
        self.held = 0  # the outcomes kept now
        self.walks = 0  # the walks made while the store was open
        self.hits = 0  # the calls answered from a kept walk
        self.renamed = 0  # those of them whose labels had other names than the kept ones (`find`)
        self.dropped = 0  # the kept walks that left for room or for the memory net
        self.keys: list[Hashable] | None = None  # a test's record: the key of every walk made, in order (None: not recorded)
        self.fresh: list[tuple] | None = None  # a pool worker's record of what it kept, for its parent (`adopt`, `abstraction._prime`)
        self._kept: OrderedDict[Hashable, tuple[list[tuple[tuple, dict]], dict[str, int] | None, int]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._kept)

    def holds(self, key: Hashable) -> bool:
        return key in self._kept

    def find(self, key: Hashable, names: Sequence[Sequence[Hashable]], allowance: "budget.Allowance | None") -> list[dict[Outcome, Fraction]] | None:
        """The kept result of the walk `key` under the labels `names` (one list for each ordering), or None when the walk must be made."""
        entry = self._kept.get(key)
        if entry is None:
            return None
        shown, counts, _ = entry
        if allowance is not None and allowance.given is not None:  # a count: the walk's pieces are counted as if it had been made
            if counts is None or any(allowance.made.get(stage, 0) + made > allowance.given for stage, made in counts.items()):
                return None  # no counts kept (it was made outside a count), or it would be cut: the walk is made, and cut where it is cut
            for stage, made in counts.items():
                allowance.add(stage, made)
        self._kept.move_to_end(key)
        self.hits += 1
        renamed = False
        for at, ((kept_names, outcomes), given) in enumerate(zip(shown, names)):
            given = tuple(given)
            if given != kept_names:  # other names for the same labels: kept from now on under these, the ones the next call most likely has
                new = dict(zip(kept_names, given))
                shown[at] = (given, {frozenset((new[name], n) for name, n in outcome): chance for outcome, chance in outcomes.items()})
                renamed = True
        self.renamed += renamed
        return [dict(outcomes) for _, outcomes in shown]

    def keep(self, key: Hashable, names: Sequence[Sequence[Hashable]], result: list[dict[Outcome, Fraction]], counts: dict[str, int] | None) -> None:
        """Keep the result of the walk `key`, made under the labels `names`; `counts` is what each stage of a counted making added, or None."""
        self.walks += 1
        if self.keys is not None:
            self.keys.append(key)
        size = sum(len(outcomes) for outcomes in result) + 1  # an empty result still takes an entry
        if self._gives_way():
            return
        self._add(key, ([(tuple(listed), dict(outcomes)) for listed, outcomes in zip(names, result)], counts, size))

    def _gives_way(self) -> bool:
        """Whether the process holds `GIVE_WAY` of the run's memory net: the store is then emptied, and keeps nothing."""
        if self.memory_mb is None:
            return False
        clock = budget.active()
        held = None if clock is None else clock.memory()
        if held is None or held < GIVE_WAY * self.memory_mb:
            return False
        self.dropped += len(self._kept)
        self._kept.clear()
        self.held = 0
        return True

    def _add(self, key: Hashable, entry: tuple) -> None:
        size = entry[2]
        before = self._kept.pop(key, None)
        if before is not None:
            self.held -= before[2]
        if size > self.limit:
            return
        while self._kept and self.held + size > self.limit:
            _, (_, _, gone) = self._kept.popitem(last=False)
            self.held -= gone
            self.dropped += 1
        self._kept[key] = entry
        self.held += size
        if self.fresh is not None:
            self.fresh.append((key, entry))

    def adopt(self, fresh: Iterable[tuple]) -> None:
        """Keep what a pool worker kept (its `fresh`): the walks it made are this plan's too."""
        for key, entry in fresh:
            self.walks += 1
            if self.keys is not None:
                self.keys.append(key)
            if not self._gives_way():
                self._add(key, entry)


_store: contextvars.ContextVar[DrawStore | None] = contextvars.ContextVar("crafting_system_draw_store", default=None)


def shared_draws() -> DrawStore | None:
    """The store of the plan being made (`sharing`), or None."""
    return _store.get()


@contextmanager
def sharing(limit: int | None = None) -> Iterator[DrawStore]:
    """Within the block every walk of `exact_distributions` is kept and no walk is made twice (`DrawStore`): one plan, with all its rounds,
    start options and second items. A block inside another shares the outer store. `limit` is the number of outcomes kept; by default
    `DRAWS_SHARE` of the run's memory net (`budget.active`), or of the machine's default net where the run has none, at `OUTCOME_BYTES` an
    outcome: a setting of the machine the run is on (OR-40)."""
    outer = _store.get()
    if outer is not None:
        yield outer
        return
    clock = budget.active()
    net = None if clock is None else clock.budget.memory_mb
    if limit is None:
        room = net if net is not None else budget.default_memory_mb()
        limit = DRAWS_KEPT if room is None else int(room * DRAWS_SHARE * 1024 * 1024 / OUTCOME_BYTES)
    token = _store.set(DrawStore(limit, net))
    try:
        yield _store.get()
    finally:
        _store.reset(token)

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

    **The order of the outcomes.** The dict is in the order the earlier engine gave (a draw-by-draw walk, backward, that went through
    the parts in their order and each part's labels in theirs, and kept the outcomes in the order it first met them). Whoever reads
    the dict in floats adds its chances in that order, so the order is part of the numbers a plan prints (#934: the recorded routes
    keep every digit). That walk met an outcome first along its least sequence of draws `(part, label)`, and the limits of a draw (the
    families of a class, the free slots of a side) read only how many draws of each part were made, never their order, so every order
    of one set of draws is a sequence of the walk: the least is that set sorted. An outcome is therefore placed by the least, over the
    end states and spreads that make it, of (the first total whose draws end there, the guaranteed group, the sorted draws); the
    least of a group of end states is kept as the group is added, since adding the same draws to two sorted sets keeps their order.

    The earlier engine walked the same states backward and kept with each the whole distribution of the labels still to come; for a
    pool of many classes and labels (a fossil set, an essence on a base of many family types) that held millions of distributions
    and was most of the time of a fossil plan. A forward state holds one number, and the states of one draw are dropped once the
    next draw is made.
    """
    return exact_distributions(pool, free, tag, totals, kept, label, (), blocked)[0]


def exact_distributions(
    pool: tuple[PoolFamily, ...],
    free: Mapping[Side, int],
    tag: str | None,
    totals: Mapping[int, Fraction],
    kept: int,
    label: Callable[[Mod], Hashable],
    views: Sequence[tuple[Callable[[Mod], Hashable], Callable[[Hashable], bool] | None]],
    blocked: frozenset[str] = frozenset(),
    *,
    own: bool = True,
    peek: bool = False,
) -> list[dict[Outcome, Fraction]]:
    """The distribution of `exact_distribution` seen through `label` (unless not `own`), then through each of `views`, from one walk of `label`'s parts.

    A view is `(its label, needed)`. Its label must be coarser than `label` (two mods that `label` gives one value get one value from the
    view), and its distribution is what `exact_distribution` gives with the view's label: the same chances (the sums of those of `label`'s
    outcomes it merges) in the same order (the order is that of the view's own parts and labels, see `exact_distribution`). With `needed`
    (a test on the values of `label`) it holds only the outcomes made from outcomes of `label` with a value that passes it, which a view
    whose label tells those values apart from the rest gets whole. A Fractured Fossil reads one view per family type out of one walk
    (`Abstraction._fracture_entries`, #934).

    Under a search counted in states (`budget.counting`, #1105) the walk counts what it makes as it makes it, each stage on its own count:
    each state of the walk met for the first time at a step of the draws (the "end state" count, intermediate steps included), each group of
    end states, each entry of a part's spread over its labels as the spread is built (the "spread" count, #1137) and each way of spreading a
    group's labels; past the allowance it raises `budget.OutcomesCut`. Every structure the walk holds is counted as it grows, so a cut walk
    has made at most one piece past the allowance at each stage.

    Inside `sharing` (a plan) a walk made before in the block is not made again (`DrawStore`): the result is the same. With `peek` nothing is
    made: the answer is whether the block's store holds this walk (False outside a block), for a caller that would otherwise send it to a
    pool worker (`abstraction._prime`).
    """
    number = NUMBER
    allowance = budget.allowed()  # None outside a counted search: nothing is counted
    zero = number(0)

    def classify(label: Callable[[Mod], Hashable]):
        """The labels, classes and parts of the pool seen through `label`, numbered as the engine numbers them."""
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
        part_of: dict[tuple[int, bool], int] = {}
        flat = 0
        for index, parts in enumerate(class_parts):
            for on_prefix, _, _ in parts:
                part_of.setdefault((index, on_prefix), flat)
                flat += 1
        return labels, class_parts, class_count, class_of, mod_label, part_of

    labels, class_parts, class_count, class_of, mod_label, part_of = classify(label)
    width = len(labels)

    # the parts: their class, side, the weight of one family's mods on that side and its (label, weight) pairs
    part_class: list[int] = []
    part_prefix: list[bool] = []
    part_weight: list = []
    part_labels: list[tuple[tuple[int, Fraction], ...]] = []
    for index, parts in enumerate(class_parts):
        for on_prefix, weights, total in parts:
            part_class.append(index)
            part_prefix.append(on_prefix)
            part_weight.append(int(total) if isinstance(total, Fraction) and total.denominator == 1 else total)  # an int when it is one: cheaper to multiply
            part_labels.append(weights)
    count = len(part_class)
    room = (free[Side.PREFIX], free[Side.SUFFIX])

    # the orderings: `label`'s own, then each view's, as (its part of each part, its label of each label, its labels, the labels one of
    # which an outcome needs or None, whether its labels are `label`'s)
    orderings: list[tuple[list[int], list[int], list[Hashable], list[int] | None, bool]] = []
    if own:
        orderings.append((list(range(count)), list(range(width)), labels, None, True))
    a_mod: dict[int, str] = {}
    for mod_id, index in mod_label.items():
        a_mod.setdefault(index, mod_id)
    a_family: dict[int, str] = {}
    for name, index in class_of.items():
        a_family.setdefault(index, name)
    for view, needed in views:
        view_labels, _, _, view_class_of, view_mod_label, view_part_of = classify(view)
        orderings.append(
            (
                [view_part_of[(view_class_of[a_family[part_class[part]]], part_prefix[part])] for part in range(count)],
                [view_mod_label[a_mod[index]] for index in range(width)],
                view_labels,
                None if needed is None else [index for index, value in enumerate(labels) if needed(value)],
                False,
            )
        )
    if not totals:
        return False if peek else [{} for _ in orderings]

    # the guaranteed draw's candidates: how many mods of each (part, label, weight), in the order the pool shows them
    tagged: dict[tuple[int, int, Fraction], int] = defaultdict(int)
    if tag is not None:
        for family, entry in guaranteed_candidates(pool, free, tag, blocked):
            tagged[(part_of[(class_of[family.family], family.side is Side.PREFIX)], mod_label[entry.mod.id], entry.weight)] += 1

    store = _store.get()
    key: Hashable = None
    counted_from: dict[str, int] | None = None
    if store is not None:
        # all the walk reads (`DrawStore`): equal keys, the same walk
        key = (
            number is Fraction,
            tuple(class_parts),
            tuple(class_count),
            room,
            kept,
            tuple(totals.items()),
            None if tag is None else tuple(tagged.items()),
            tuple((tuple(parts), tuple(labs), len(names), None if needed is None else tuple(needed), same) for parts, labs, names, needed, same in orderings),
        )
        if peek:
            return store.holds(key)
        found = store.find(key, [names for _, _, names, _, _ in orderings], allowance)
        if found is not None:
            return found
        if allowance is not None and allowance.given is not None:
            counted_from = dict(allowance.made)
    elif peek:
        return False

    whole = number is Fraction and all(type(weight) is int for weight in part_weight)  # every weight an integer: the walk keeps (numerator, denominator) pairs

    # which total each end state serves first: the order of the outcomes reads it (see `exact_distribution`)
    picks_list = [max(0, total - kept - (tag is not None)) for total in totals]
    first_at: dict[int, int] = {}
    for index, picks in enumerate(picks_list):
        first_at.setdefault(picks, index)

    def first_above(made: int) -> int | None:
        return min((index for index, picks in enumerate(picks_list) if picks > made), default=None)

    def ends(start: tuple[int, ...], picks_by_chance: Mapping[int, Fraction]) -> tuple[dict[tuple[int, ...], Fraction], dict[tuple[int, ...], int]]:
        """The chance of each end state of the draws from `start`, mixed over the numbers of draws to make, and the first total it serves.

        It walks forward one draw at a time and keeps only the states of the current draw: a state where `made` draws were
        made ends there when `made` is the number to make, or when nothing can be drawn from it and more were to be made.
        With integer weights a chance is kept as a reduced pair of integers and added with one `gcd`, which is the same exact
        number as a `Fraction` at a third of the time (the walk is where a large draw spends it); it is a `Fraction` again on the way out.
        """
        result: dict[tuple[int, ...], Fraction] = defaultdict(number)
        first: dict[tuple[int, ...], int] = {}
        picks = max(picks_by_chance)
        more = {made: sum((weight for drawn, weight in picks_by_chance.items() if drawn > made), zero) for made in range(picks)}

        def add(found: dict, weight, at: int | None) -> None:
            if not weight:
                return
            for state, chance in found.items():
                result[state] += weight * (Fraction(*chance) if whole else chance)
                if at is not None and (state not in first or at < first[state]):
                    first[state] = at

        level: dict[tuple[int, ...], object] = {start: (1, 1) if whole else number(1)}
        for made in range(picks + 1):
            add(level, picks_by_chance.get(made, zero), first_at.get(made))
            if made == picks:
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
                        if before is None and allowance is not None:
                            allowance.add("end state")
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
                    if before is None and allowance is not None:
                        allowance.add("end state")
                    if before is not None:
                        other, under = before
                        if under == bottom:
                            top += other
                        else:
                            top, bottom = top * under + other * bottom, bottom * under
                        common = gcd(top, bottom)
                        top, bottom = top // common, bottom // common
                    following[child] = (top, bottom)
            add(stuck, more[made], first_above(made))
            level = following
        return result, first

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
                        if allowance is not None:
                            allowance.add("spread")  # counted as it is built, its intermediate labels included (#1137)
                        grown.append(((*counts, (lab, k)) if k else counts, chance * share**k * comb(left, k), left - k))
                ways = grown
            found = spreads[(part, n)] = [(counts, chance) for counts, chance, _ in ways if chance]
        return found

    # each ordering's number of each pair `part x width + label`: its own part and label, so that numbers sort as its (part, label) pairs do
    codes = [[parts[pair // width] * len(names) + labs[pair % width] for pair in range(count * width)] for parts, labs, names, *_ in orderings]
    sums: list[dict[tuple[int, ...], Fraction]] = [defaultdict(number) for _ in orderings]  # per ordering: its label counts -> chance
    least: list[dict[tuple[int, ...], tuple]] = [{} for _ in orderings]  # per ordering: its label counts -> the key that places it

    def spread_ends(found: Mapping[tuple[int, ...], Fraction], first: Mapping[tuple[int, ...], int], fixed: tuple[int, int] | None, scale, groups: tuple[int, ...]) -> None:
        """Add the outcomes of the end states `found`, times `scale`; `fixed` is the (part, label) of the guaranteed mod, whose label is known.

        `first` is the first total each end state serves and `groups` the guaranteed group in each ordering (0 without a tag): with the
        sorted draws they make the key that places an outcome (see `exact_distribution`).
        """
        grouped: dict[tuple, list] = {}
        for state, chance in found.items():
            base = [0] * width
            mixed = []
            singles: list[int] = []  # the draws of the parts of one label, as pairs `part x width + label`
            for part, n in enumerate(state):
                if fixed is not None and part == fixed[0]:
                    n -= 1
                if not n:
                    continue
                if len(part_labels[part]) == 1:
                    lab = part_labels[part][0][0]
                    base[lab] += n
                    singles.extend([part * width + lab] * n)
                else:
                    mixed.append((part, n))
            if fixed is not None:
                base[fixed[1]] += 1
            group = (tuple(base), tuple(mixed))
            known = grouped.get(group)
            if known is None:
                if allowance is not None:
                    allowance.add("group")
                # the orderings an outcome of the group can reach: a view that needs a label is skipped where none can be drawn
                drawable = {index for index, n in enumerate(base) if n} | {lab for part, _ in mixed for lab, _ in part_labels[part]}
                known = grouped[group] = [zero, [None if needed is not None and drawable.isdisjoint(needed) else () for *_, needed, _ in orderings]]
            known[0] += chance
            at = first[state]
            least_of = known[1]
            for o, code in enumerate(codes):
                if least_of[o] is not None:
                    key = (at, tuple(sorted(map(code.__getitem__, singles))))
                    if not least_of[o] or key < least_of[o]:
                        least_of[o] = key
        for (base, mixed), (chance, keys) in grouped.items():
            ways: list[tuple[tuple[int, ...], Fraction, tuple[int, ...]]] = [(base, chance * scale, ())]
            for part, n in mixed:
                grown = []
                for tally, before, drawn in ways:
                    for counts, each in spread(part, n):
                        if allowance is not None:
                            allowance.add("way")
                        after = list(tally)
                        pairs = list(drawn)
                        for lab, k in counts:
                            after[lab] += k
                            pairs.extend([part * width + lab] * k)
                        grown.append((tuple(after), before * each, tuple(pairs)))
                ways = grown
            for tally, each, drawn in ways:
                for o, (parts, labs, names, needed, same) in enumerate(orderings):
                    if keys[o] is None or (needed is not None and not any(tally[index] for index in needed)):
                        continue
                    at, seq = keys[o]
                    key = (at, groups[o], tuple(sorted(seq + tuple(map(codes[o].__getitem__, drawn)))))
                    if not same:
                        seen = [0] * len(names)
                        for index, n in enumerate(tally):
                            if n:
                                seen[labs[index]] += n
                        shown = tuple(seen)
                    else:
                        shown = tally
                    sums[o][shown] += each
                    before = least[o].get(shown)
                    if before is None or key < before:
                        least[o][shown] = key

    start = (0,) * count
    picks_of: dict[int, Fraction] = {}
    for picks, chance in zip(picks_list, totals.values()):
        picks_of[picks] = picks_of.get(picks, zero) + number(chance)
    if tag is None:
        found, first = ends(start, picks_of)
        spread_ends(found, first, None, number(1), (0,) * len(orderings))
    else:
        groups = tagged
        group_numbers: list[dict[tuple, int]] = [{} for _ in orderings]  # the guaranteed groups each ordering makes, in the order it met them
        for part, lab, weight in groups:  # in the order the candidates were met: a group is numbered when its first candidate is
            for numbers, (parts, labs, *_) in zip(group_numbers, orderings):
                numbers.setdefault((parts[part], labs[lab], weight), len(numbers))
        tagged_total = sum((n * number(weight) for (_, _, weight), n in groups.items()), number(0))
        by_part: dict[int, list[tuple[int, Fraction, tuple[int, ...]]]] = defaultdict(list)
        for (part, lab, weight), n in groups.items():
            numbered = tuple(numbers[(parts[part], labs[lab], weight)] for numbers, (parts, labs, *_) in zip(group_numbers, orderings))
            by_part[part].append((lab, n * number(weight) / tagged_total, numbered))
        for part, chosen in by_part.items():
            found, first = ends(start[:part] + (1,) + start[part + 1 :], picks_of)
            for lab, step, numbered in chosen:
                spread_ends(found, first, (part, lab), step, numbered)
    result = [
        {
            frozenset((names[i], n) for i, n in enumerate(shown) if n): sums[o][shown]
            for shown in sorted(least[o], key=least[o].__getitem__)
            if sums[o][shown]
        }
        for o, (_, _, names, _, _) in enumerate(orderings)
    ]
    if store is not None:
        counts = None
        if counted_from is not None:  # what each stage of this making added, in the order the stages were first counted
            counts = {stage: made - counted_from.get(stage, 0) for stage, made in allowance.made.items() if made > counted_from.get(stage, 0)}
        store.keep(key, [names for _, _, names, _, _ in orderings], result, counts)
    return result


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
