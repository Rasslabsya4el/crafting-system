"""What a fossil set declares of one use without building its outcomes: whether it keeps the shape, and a bound on its chance per leaf (#1073).

`ApplyFossils.reach_batch` answers it for thousands of sets at once (`Action.reach_batch`, `ReachDeclared`). A planner needs a number never below
the chance that one use of a set puts on the item a mod of X (the mods `passes` says can make a leaf PASSING), and needs it for every set of a
listing before it builds any set's pool: building one (`fossil._build`, a Tangled set is a mixture of 420 pools) takes a tenth of a second and
more, and a fossil round offers 5,000 to 10,000 sets.

THE SHAPE. A set keeps the rarity, the corruption, the influences and the fractured mods of the item unless it holds a Bloodstained Fossil (it
corrupts) or a Fractured Fossil (it fractures a mod): every other fossil rerolls the item as a Chaos Orb does, with other weights, and may force
one mod (Hollow, Glyphic) that is an ordinary explicit mod. So `keeps_shape` is read from the names of the fossils.

THE BOUND, for one set and one leaf L. The use is a reroll (`actions/draw.py`): a total T is drawn from `totals`; a forced mod, if any, is put on
first; then `n_T = T - kept - forced` draws, each picking one mod of an undrawn family on a side with room, in proportion to weight, the whole
family leaving the pool and its side losing a slot. When the set can force a mod of X (any of its possible forced mods passes L), the bound is
1. Otherwise L becomes PASSING only if a draw picks a mod of X, and the argument of `abstraction/_bound.py` ("One draw") applies: with c_j a
number at least the chance that draw j hits X given any history of earlier draws without a hit, P(hit) <= 1 - prod_j (1 - c_j). The forced mod
is counted as an earlier draw without a hit (it took one slot of its side and, if its family is in the pool, that family): so draw j of the
ordinary draws has `prior = j + forced` earlier draws, split as `a` on the prefix side and `prior - a` on the suffix side in every way the free
slots allow. A side is open when its count is below its free slots. For a family f of the pool, x_f is the weight of its mods in X and j_f the
weight of the rest. After the earlier draws took a set R of families (|R| of each side as the split says), the chance of a hit is
(X - X_R) / (W - W_R) over the open sides, and

    (X - X_R) / (W - W_R) <= X / (X + J - J_R)          (cross-multiply: it is X - X_R <= W - W_R, the X weight left is part of the weight left)

where J is the junk weight of the open sides. J - J_R is at least the sum of the smallest (count - |R|) junk weights of the side, so c_j is the
largest, over the splits, of X / (X + that sum) over the open sides (0 when X is 0). A family the set's weights drop has weight 0 on both counts
and changes neither sum. This is the c_j of `_bound.py` without Dinkelbach's choice of the drawn families: never below it.

Weights. A mod's weight in the pool of a set is its spawn weight on the item times the set's factor (`FossilWeights.factor`: the tag factor of
its tag set, times the Sanctified level factor). A Tangled Fossil makes the pool a mixture over its 420 outcome records; the chance of the
mixture is at most the largest chance of a member, and the bound above grows with every x_f and falls with every j_f (X / (X + sum of the
smallest junk weights)), so taking each mod in X at its largest weight over the records and each other mod at its smallest gives a number
above every member's bound. The factor of a tag set reads only the records' entries for the tags of the set, so the records are grouped by
those entries and each group is worked out once. The added mods of a set (a Faceted Fossil's) are candidates of its pool like any other.

Floats. Every x_f, j_f and sum is a sum of nonnegative products of a few factors, each rounded once (relative error under 1e-13 for a few
hundred terms); no step subtracts two sums (the junk left is summed from the smallest up); 1 - prod(1 - c_j) is `-expm1(sum log1p(-c_j))`,
whose relative error is of the same order. Every positive bound is raised by `MARGIN` of itself, far above that error, so it stays above the
exact value; a bound is 0 only when no mod of X has weight (a sum of exact zeros) and no forced mod passes. `tests/test_actions_fossil_reach.py`
compares the bound with the exact chance of every set of the fixture listing, and the declared shape with `keeps_shape`.

No declaration (None) for a set the item refuses or the model has no rule for (the refusals of `fossil.outcomes`), and for a pool with a family
on both sides (a jewel: the argument has no side split for it).
"""

from collections.abc import Callable, Sequence
from types import SimpleNamespace

import numpy as np

from crafting_system.data import GameData, Mod, conflicts
from crafting_system.items import Item, Side

from .contract import ReachDeclared
from .draw import refuse_unmodelled, total_distribution
from .errors import NotApplicableError, OutOfScopeError
from .fossil_weights import SANCTIFIED_LEVEL_FACTOR, fossil_weights
from .outcomes import retained_item
from .pool import group_pool, partners, pool_candidates

MARGIN = 1e-9  # the relative raise of every positive bound: above the float error of the module text
PERCENT = 100


def declared(data: GameData, item: Item, actions: Sequence, passes: Callable[[Mod], tuple[bool, ...]]) -> tuple[ReachDeclared | None, ...]:
    """`ReachDeclared` of each fossil set of `actions` on the bare item `item` (see the module text); None where the set gives none."""
    from . import fossil as F  # the set's own helpers; imported here, since `fossil` imports this module's caller

    found: list[ReachDeclared | None] = [None] * len(actions)
    try:
        F._check_item(data, item)
        refuse_unmodelled(data, item, jewels=True)
    except (NotApplicableError, OutOfScopeError):
        return tuple(found)
    base = data.base_items.get(item.base_id)
    if base is None:
        return tuple(found)
    retained = retained_item(data, item)
    kept = len(retained.mods)
    free = {side: max(0, retained.free_slots(data, side)) for side in Side}
    totals = [(total, float(chance)) for total, chance in total_distribution(data, retained).items()]
    memo: dict[str, tuple[bool, ...]] = {}

    def leaf_flags(mod: Mod) -> tuple[bool, ...]:
        if mod.id not in memo:
            memo[mod.id] = tuple(passes(mod))
        return memo[mod.id]

    groups: dict[tuple[str, ...], list[tuple[int, list, list[Mod]]]] = {}
    pairs = None
    for index, action in enumerate(actions):
        try:
            records = [F._record(data, name) for name in action.fossils]
            if len({record.id for record in records}) != len(records):
                continue
            for record in records:
                F._check_fossil(record, base.tags, item)
            F._check_set(records)
            if any(F._special(record, "bloodstained") or F._special(record, "fractured") for record in records):
                found[index] = ReachDeclared(False)
                continue
            tangled = any(F._special(record, "tangled") for record in records)
            if tangled and pairs is None:
                pairs = F._tangled_pairs(data)
            forced = _forced(data, item, base.item_class, records, tangled)
        except (NotApplicableError, OutOfScopeError, ValueError):
            continue
        extra = tuple(mod.id for mod in F._added_mods(data, records))
        groups.setdefault(extra, []).append((index, records, forced))
    for extra, members in groups.items():
        try:
            candidates = pool_candidates(data, retained, None, [data.mods[mod_id] for mod_id in extra])
            if partners(group_pool(candidates)):
                continue
        except OutOfScopeError:
            continue
        for (index, _records, _forced_mods), chances in zip(members, _group_bounds(data, candidates, members, pairs, leaf_flags, free, kept, totals)):
            found[index] = ReachDeclared(True, chances)
    return tuple(found)


def _forced(data: GameData, item: Item, item_class: str, records: list, tangled: bool) -> list[Mod]:
    """Every mod the set may force (empty when it forces none), with the refusals of `fossil._forced_choices`.

    A Glyphic set in a Tangled resonator draws its forced mod with weights that follow the outcome record, so every corrupted-essence mod of
    the class that fits beside the fractured mods is listed: more than it may force, which only raises the bound.
    """
    from . import fossil as F

    if not tangled:
        weights = fossil_weights(records, None, opulent=any(F._special(r, "opulent") for r in records), sanctified=any(r.rolls_lucky for r in records))
        return [mod for _chance, mod in F._forced_choices(data, item, records, weights) if mod is not None]
    for record in records:
        if record.forced_mods:
            return [mod for _chance, mod in F._forced_choices(data, item, [record], fossil_weights([record]))]
    if not any(record.corrupted_essence_chance >= 100 and not F._special(record, "tangled") for record in records):
        return []
    listed = []
    for essence in data.essences.values():
        if not essence.is_corruption_only:
            continue
        mod_id = essence.mod_for(item_class)
        if mod_id is None:
            mod_id = essence.mod_for(F.DAGGER_STAFF_TAKE_CLASS_MODS.value.get(item_class, item_class))
        if mod_id is None:
            continue
        mod = data.mods[mod_id]
        if any(conflicts(mod, data.mods[entry.mod_id]) for entry in item.fractured_mods):
            continue
        F._check_forced(data, item, mod, "Glyphic Fossil")
        listed.append(mod)
    if not listed:
        raise OutOfScopeError("the Glyphic Fossil has no corrupted-essence mod to force on this item")
    return listed


def _group_bounds(data, candidates, members, pairs, leaf_flags, free, kept, totals) -> list[tuple[float, ...]]:
    """The bound of each member set per leaf, for sets that share one list of candidates (see the module text)."""
    from . import fossil as F

    mods = [candidate.mod for candidate in candidates]
    leaves = len(leaf_flags(mods[0])) if mods else 0
    if not mods:
        return [tuple(1.0 if any(leaf_flags(mod)[leaf] for mod in forced) else 0.0 for leaf in range(leaves)) for _i, _r, forced in members]
    passing = np.array([leaf_flags(mod) for mod in mods], dtype=bool).T  # leaves x mods
    spawn = np.array([float(candidate.weight) for candidate in candidates])
    any_x = (passing & (spawn > 0)).any(axis=1)  # per leaf: some candidate of X has a spawn weight
    results: list[tuple[float, ...] | None] = [None] * len(members)
    todo: list[int] = []
    for position, (_index, _records, forced) in enumerate(members):
        forced_hits = [any(leaf_flags(mod)[leaf] for mod in forced) for leaf in range(leaves)]
        zero = [leaf for leaf in range(leaves) if not any_x[leaf] and not forced_hits[leaf]]
        if zero:  # a leaf no use can reach: 0 there is exact, and 1 is an upper bound for the others
            results[position] = tuple(0.0 if leaf in zero else 1.0 for leaf in range(leaves))
        else:
            todo.append(position)
    if not todo:
        return results  # type: ignore[return-value]

    pool = _Pool(candidates, passing, spawn, free, kept, totals)
    factors = _Factors(pool.tag_sets, pairs)
    rows: list[np.ndarray] = []  # each: rows x tag sets, the factor of each tag set for one member of a set's mixture
    owner: list[np.ndarray] = []
    share: list[np.ndarray] = []
    lucky: list[np.ndarray] = []
    forced_rows: list[np.ndarray] = []
    for position in todo:
        records, forced = members[position][1], members[position][2]
        opulent = any(F._special(record, "opulent") for record in records)
        table, shares = factors.table(records, opulent, any(F._special(record, "tangled") for record in records))
        rows.append(table)
        owner.append(np.full(len(table), position))
        share.append(shares)
        lucky.append(np.full(len(table), any(record.rolls_lucky for record in records)))
        forced_rows.append(np.full(len(table), 1 if forced else 0))
    bounds = pool.bounds(np.concatenate(rows), np.concatenate(lucky), np.concatenate(forced_rows), leaves) * np.concatenate(share)[:, None]
    per_set = np.zeros((len(members), leaves))
    np.add.at(per_set, np.concatenate(owner), bounds)  # a Tangled set: the mean over its outcome records, by their shares
    for position in todo:
        forced = members[position][2]
        values = []
        for leaf in range(leaves):
            if any(leaf_flags(mod)[leaf] for mod in forced):
                values.append(1.0)
            elif per_set[position, leaf] <= 0.0:
                values.append(0.0)
            else:
                values.append(min(1.0, float(per_set[position, leaf]) * (1 + MARGIN)))
        results[position] = tuple(values)
    return results  # type: ignore[return-value]


class _Pool:
    """The candidates of a group of sets as arrays: what the bound reads of each mod, family and side."""

    CHUNK = 4096  # rows worked at once

    def __init__(self, candidates, passing, spawn, free, kept, totals):
        mods = [candidate.mod for candidate in candidates]
        self.passing, self.spawn, self.kept, self.totals = passing, spawn, kept, totals
        self.room = (free[Side.PREFIX], free[Side.SUFFIX])
        family_of: dict[tuple[str, Side], int] = {}
        column = np.array([family_of.setdefault((candidate.family, candidate.side), len(family_of)) for candidate in candidates])
        self.one_hot = np.zeros((len(mods), len(family_of)))
        self.one_hot[np.arange(len(mods)), column] = 1.0
        self.prefix = np.array([side is Side.PREFIX for _family, side in family_of])
        tag_sets: dict[frozenset[str], int] = {}
        self.tag_of = np.array([tag_sets.setdefault(frozenset(mod.implicit_tags), len(tag_sets)) for mod in mods])
        self.tag_sets = list(tag_sets)
        # the Sanctified factor of each mod; a mod it would give a weight below 0 leaves the pool (`group_pool` drops a weight <= 0)
        self.level = np.maximum(np.array([1.0 + (mod.required_level - SANCTIFIED_LEVEL_FACTOR.value) / PERCENT for mod in mods]), 0.0)

    def bounds(self, table, lucky, forced, leaves) -> np.ndarray:
        """The bound per row and leaf. Row r is a pool whose mods weigh their spawn weight times `table[r]` of their tag set (times the
        Sanctified level factor where `lucky[r]`), drawn after `forced[r]` forced mods."""
        out = np.zeros((len(table), leaves))
        for start in range(0, len(table), self.CHUNK):
            part = slice(start, start + self.CHUNK)
            weights = self.spawn[None, :] * table[part][:, self.tag_of]
            weights = np.where(lucky[part][:, None], weights * self.level[None, :], weights)
            for leaf in range(leaves):
                out[part, leaf] = self._leaf(weights, forced[part], self.passing[leaf])
        return out

    def _leaf(self, weights, forced, passing) -> np.ndarray:
        rows = len(weights)
        hit = (weights * passing) @ self.one_hot  # rows x families: x_f
        junk = (weights * ~passing) @ self.one_hot  # j_f
        sides = []
        for mask in (self.prefix, ~self.prefix):
            ascending = np.sort(junk[:, mask], axis=1)
            smallest = np.concatenate([np.zeros((rows, 1)), np.cumsum(ascending, axis=1)], axis=1)  # [:, i]: the sum of the i smallest
            sides.append((hit[:, mask].sum(axis=1), smallest, int(mask.sum())))
        most = max(total for total, _ in self.totals) - self.kept
        chance = np.zeros((rows, max(most, 0) + 1))  # [:, prior]: c of a draw after `prior` earlier draws without a hit
        for prior in range(max(most, 0) + 1):
            for a in range(min(prior, self.room[0]) + 1):
                b = prior - a
                if b > self.room[1]:
                    continue  # that split of the earlier draws cannot have happened
                x = np.zeros(rows)
                j = np.zeros(rows)
                for (x_side, smallest, width), drawn, room in ((sides[0], a, self.room[0]), (sides[1], b, self.room[1])):
                    if drawn < room:  # the side is open
                        x = x + x_side
                        j = j + smallest[:, max(width - drawn, 0)]
                ratio = np.divide(x, x + j, out=np.zeros(rows), where=x > 0)
                chance[:, prior] = np.maximum(chance[:, prior], ratio)
        with np.errstate(divide="ignore"):
            logs = np.log1p(-np.minimum(chance, 1.0))  # -inf where c is 1: that total's bound is 1
        bound = np.zeros(rows)
        for total, share in self.totals:
            for count in (0, 1):
                chosen = forced == count
                if chosen.any():
                    draws = max(0, total - self.kept - count)
                    bound[chosen] += share * -np.expm1(logs[chosen][:, count : count + draws].sum(axis=1))
        return bound


class _Factors:
    """The fossil factor of each tag set of a pool for a set, read per tag set from the records' entries for its tags (see the module text)."""

    def __init__(self, tag_sets, pairs):
        self.tag_sets = tag_sets
        self.restricted: dict[tuple[str, int], tuple] = {}  # (record id, tag set): the record's entries for those tags
        self.columns: dict[tuple, np.ndarray] = {}  # (tag set, the set's own entries for it, opulent): the factor per class of outcome records
        self.shares = np.ones(1)
        self.class_of: list[np.ndarray] = []  # per tag set: the class of each class of the whole pool, by its entries for the tag set
        self.pair_keys: list[list[tuple]] = []  # per tag set: the entries of each of its classes
        if pairs is None:
            return
        every = frozenset().union(*tag_sets)
        found: dict[tuple, int] = {}
        for _chance, record in pairs:
            key = _entries(record, every)
            found[key] = found.get(key, 0) + 1
        whole = list(found)  # the classes of outcome records that weigh every tag of the pool alike
        self.shares = np.array([found[key] / len(pairs) for key in whole])
        for tags in tag_sets:
            keys: dict[tuple, int] = {}
            self.class_of.append(np.array([keys.setdefault(tuple(entry for entry in key if entry[0] in tags), len(keys)) for key in whole]))
            self.pair_keys.append(list(keys))

    def table(self, records, opulent: bool, tangled: bool) -> tuple[np.ndarray, np.ndarray]:
        """The factors of one set: one row, or one row per class of Tangled outcome records, with the share of each row."""
        if not tangled:
            return np.array([[self._column(column, records, opulent, False)[0] for column in range(len(self.tag_sets))]]), np.ones(1)
        return np.stack([self._column(column, records, opulent, True)[self.class_of[column]] for column in range(len(self.tag_sets))], axis=1), self.shares

    def _column(self, column: int, records, opulent: bool, tangled: bool) -> np.ndarray:
        """The factor of tag set `column`: one value, or one per class of outcome records for its tags."""
        tags = self.tag_sets[column]
        own = []
        for record in records:
            key = (record.id, column)
            if key not in self.restricted:
                self.restricted[key] = _entries(record, tags)
            own.extend(self.restricted[key])
        memo_key = (column, tuple(sorted(own)), opulent and not tags, tangled)
        found = self.columns.get(memo_key)
        if found is None:
            pairs = self.pair_keys[column] if tangled else [()]
            found = self.columns[memo_key] = np.array([_factor(tags, (*own, *pair), opulent) for pair in pairs])
        return found


def _factor(tags: frozenset[str], entries, opulent: bool) -> float:
    """`FossilWeights.tag_factor` of `tags` for fossils whose entries for those tags are `entries` (the factor reads no other)."""
    stand_in = SimpleNamespace(positive_mod_weights=tuple(SimpleNamespace(tag=tag, weight=weight) for tag, weight in entries), negative_mod_weights=())
    return float(fossil_weights([stand_in], None, opulent=opulent).tag_factor(tags))


def _entries(record, tags: frozenset[str]) -> tuple[tuple[str, int], ...]:
    """The tag weights of a fossil record (or a class of them) for `tags`, sorted: all that `FossilWeights.tag_factor` of a tag set within `tags` reads of it."""
    return tuple(sorted((entry.tag, entry.weight) for entry in (*record.positive_mod_weights, *record.negative_mod_weights) if entry.tag in tags))
