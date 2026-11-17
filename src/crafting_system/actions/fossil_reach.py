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
passes no leaf here; it took one slot of its own side and took out of the pool every family it conflicts with, on either side (`_offset`: a
Glyphic suffix whose family is a prefix family of a shield's pool takes a prefix family). Draw j of the ordinary draws comes after j earlier
ordinary draws, split as `a` on the prefix side and `j - a` on the suffix side in every way the slots left beside the forced mod allow; a side
is open when its draws and the forced mod's slot are below its free slots, and the families gone from a side are its draws plus the forced
mod's families there. A set that may force one of several mods (Glyphic) is bounded for each and takes the largest; in a Tangled set,
whose forced mod's law follows the outcome record, the largest is taken per record before the mean over records (the mean of the maxima
bounds the mixture, the maximum of the means need not). For a family f of the pool, x_f is the weight of its mods in X and j_f the
weight of the rest. After the earlier draws and the forced mod took a set R of families (|R| of each side as above), the chance of a hit is
(X - X_R) / (W - W_R) over the open sides, and

    (X - X_R) / (W - W_R) <= X / (X + J - J_R)          (cross-multiply: it is X - X_R <= W - W_R, the X weight left is part of the weight left)

where J is the junk weight of the open sides. J - J_R is at least the sum of the smallest (count - |R|) junk weights of the side, so c_j is the
largest, over the splits, of X / (X + that sum) over the open sides (0 when X is 0). A family the set's weights drop has weight 0 on both counts
and changes neither sum. This is the c_j of `_bound.py` without Dinkelbach's choice of the drawn families: never below it.

Weights. A mod's weight in the pool of a set is its spawn weight on the item times the set's factor (`FossilWeights.factor`: the tag factor of
its tag set, times the Sanctified level factor). A Tangled Fossil makes the use a mixture over its 420 outcome records, each with the same
chance: the chance of the mixture is the mean of the members' chances, so the mean of their bounds is a bound. The factor of a tag set reads
only the records' entries for the tags of the set, so the records are grouped into classes by their entries for every tag of the pool (each
class weighted by its count) and each factor is worked out once per class of entries for its own tags. The added mods of a set (a Faceted
Fossil's) are candidates of its pool like any other.

Every leaf at once. Its chance is at most the least of the leaves' chances and, when some leaves have pairwise disjoint X's and no forced mod
passes any leaf, at most the joint bound of `abstraction/_bound.py` (`_joint_hits`: each of them needs a draw of its own), per total. When a
forced mod may pass a leaf, no bound on every leaf at once is declared (`together` None: the least of the leaves' bounds holds).

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
BATCH = 64  # sets whose rows of factors are worked at once (a Tangled set has one row per class of outcome records, up to 420)


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
        for (index, _records, _forced_mods), (chances, together) in zip(members, _group_bounds(data, candidates, members, pairs, leaf_flags, free, kept, totals)):
            found[index] = ReachDeclared(True, chances, together)
    return tuple(found)


NO_FORCED = (0, 0, 0, 0)


def _offset(candidates, mod: Mod) -> tuple[int, int, int, int]:
    """What a forced mod does to the draws after it: the slots it takes on (prefix, suffix) and the families of the pool it takes out of each.

    Its families are read from the candidates it conflicts with, on either side: a Glyphic suffix whose family is a prefix family of the pool
    (`SpellBlockOnLowLifeEssence1` on a shield) takes a prefix family and a suffix slot (#1073, checker round 1).
    """
    taken = {(candidate.family, candidate.side) for candidate in candidates if conflicts(mod, candidate.mod)}
    side = Side(mod.generation_type)
    return (int(side is Side.PREFIX), int(side is Side.SUFFIX), sum(s is Side.PREFIX for _f, s in taken), sum(s is Side.SUFFIX for _f, s in taken))

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


def _group_bounds(data, candidates, members, pairs, leaf_flags, free, kept, totals) -> list[tuple[tuple[float, ...], float | None]]:
    """The bound of each member set per leaf and on every leaf at once, for sets that share one list of candidates (see the module text)."""
    from . import fossil as F

    mods = [candidate.mod for candidate in candidates]
    leaves = len(leaf_flags(mods[0] if mods else next(iter(data.mods.values()))))  # an empty pool still answers once per leaf (checker round 2)
    if not mods:
        return [_nothing_drawn(forced, leaves, leaf_flags) for _i, _r, forced in members]
    passing = np.array([leaf_flags(mod) for mod in mods], dtype=bool).T  # leaves x mods
    spawn = np.array([float(candidate.weight) for candidate in candidates])
    any_x = (passing & (spawn > 0)).any(axis=1)  # per leaf: some candidate of X has a spawn weight
    results: list[tuple[float, ...] | None] = [None] * len(members)
    todo: list[int] = []
    for position, (_index, _records, forced) in enumerate(members):
        forced_hits = [any(leaf_flags(mod)[leaf] for mod in forced) for leaf in range(leaves)]
        zero = [leaf for leaf in range(leaves) if not any_x[leaf] and not forced_hits[leaf]]
        if zero:  # a leaf no use can reach: 0 there is exact, and 1 is an upper bound for the others
            results[position] = (tuple(0.0 if leaf in zero else 1.0 for leaf in range(leaves)), 0.0)
        else:
            todo.append(position)
    if not todo:
        return results  # type: ignore[return-value]

    pool = _Pool(candidates, passing, spawn, free, kept, totals)
    factors = _Factors(pool.tag_sets, pairs)
    joint = _disjoint(passing, leaves)
    # a unit is a set with one mod it may force (or none). Which one it forces is not read, so each row of the set's mixture (one outcome
    # record class of a Tangled set, whose forced mod's law follows the record) takes the largest bound over the units, and the set the mean
    # of those maxima over its rows: a mean of maxima, never the maximum of the means, which may be below the exact chance
    per_set = np.zeros((len(members), leaves))
    per_set_all = np.zeros(len(members))
    for start in range(0, len(todo), BATCH):  # a batch of sets at a time: a Tangled set is up to 420 rows of factors per unit
        rows: list[np.ndarray] = []  # each: rows x tag sets, the factor of each tag set for one member of a set's mixture
        lucky: list[np.ndarray] = []
        offsets: list[tuple[int, int, int, int]] = []
        spans: list[tuple[int, int, int, np.ndarray]] = []  # per set: its position, first row, units, shares of its rows
        for position in todo[start : start + BATCH]:
            records = members[position][1]
            opulent = any(F._special(record, "opulent") for record in records)
            table, shares = factors.table(records, opulent, any(F._special(record, "tangled") for record in records))
            units = sorted({_offset(candidates, mod) for mod in members[position][2]} or {NO_FORCED})
            spans.append((position, sum(len(row) for row in rows), len(units), shares))
            for offset in units:
                rows.append(table)
                lucky.append(np.full(len(table), any(record.rolls_lucky for record in records)))
                offsets.extend([offset] * len(table))
        singles, together = pool.bounds(np.concatenate(rows), np.concatenate(lucky), offsets, leaves, joint)
        for position, first, count, shares in spans:
            width = len(shares)
            block = singles[first : first + count * width].reshape(count, width, leaves).max(axis=0)
            per_set[position] = shares @ block
            per_set_all[position] = shares @ together[first : first + count * width].reshape(count, width).max(axis=0)
    for position in todo:
        forced = members[position][2]
        hits = [any(leaf_flags(mod)[leaf] for mod in forced) for leaf in range(leaves)]
        values = tuple(1.0 if hits[leaf] else _raised(per_set[position, leaf]) for leaf in range(leaves))
        # the bound on every leaf at once counts hits by draws only: none when a forced mod may pass a leaf (the least of `values` then holds)
        both = None if any(hits) else _raised(per_set_all[position])
        results[position] = (values, both)
    return results  # type: ignore[return-value]


def _nothing_drawn(forced, leaves: int, leaf_flags) -> tuple[tuple[float, ...], float]:
    """The bounds of a set with no candidate to draw: a leaf is reached only by a forced mod that passes it."""
    values = tuple(1.0 if any(leaf_flags(mod)[leaf] for mod in forced) else 0.0 for leaf in range(leaves))
    return values, min(values, default=1.0)


def _raised(value: float) -> float:
    """A bound worked in floats, raised by `MARGIN` of itself (see the module text, Floats); 0 stays 0, and no bound is above 1."""
    return 0.0 if value <= 0.0 else min(1.0, float(value) * (1 + MARGIN))


def _disjoint(passing: np.ndarray, leaves: int) -> list[int]:
    """Leaves whose X share no candidate, chosen greedily in order: each needs a draw of its own (`_bound._joint_hits`)."""
    chosen: list[int] = []
    for leaf in range(leaves):
        if all(not (passing[leaf] & passing[other]).any() for other in chosen):
            chosen.append(leaf)
    return chosen if len(chosen) > 1 else []


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


    def bounds(self, table, lucky, offsets, leaves, joint) -> tuple[np.ndarray, np.ndarray]:
        """The bound per row and leaf, and per row the bound on every leaf at once. Row r is a pool whose mods weigh their spawn weight times
        `table[r]` of their tag set (times the Sanctified level factor where `lucky[r]`), drawn after the forced mod `offsets[r]` describes
        (`_offset`; one that passes no leaf).

        For each total: one leaf's bound is 1 - prod(1 - c_j) over its draws; every leaf at once is at most the least of them and, when the
        leaves of `joint` have pairwise disjoint X's, at most the sum over the ways to give each of them a draw of its own of the product of
        their c's (`_bound._joint_hits`, its argument). Each is averaged over the totals.
        """
        singles = np.zeros((len(table), leaves))
        together = np.zeros(len(table))
        offsets = np.array(offsets, dtype=int).reshape(len(table), 4)
        for start in range(0, len(table), self.CHUNK):
            part = slice(start, start + self.CHUNK)
            weights = self.spawn[None, :] * table[part][:, self.tag_of]
            weights = np.where(lucky[part][:, None], weights * self.level[None, :], weights)
            for offset in {tuple(row) for row in offsets[part].tolist()}:
                chosen = (offsets[part] == offset).all(axis=1)
                chances = [self._chance(weights[chosen], self.passing[leaf], offset) for leaf in range(leaves)]
                with np.errstate(divide="ignore"):
                    logs = [np.log1p(-np.minimum(chance, 1.0)) for chance in chances]  # -inf where c is 1: that total's bound is 1
                for total, share in self.totals:
                    draws = max(0, total - self.kept - offset[0] - offset[1])
                    alone = [-np.expm1(log[:, :draws].sum(axis=1)) for log in logs]
                    for leaf in range(leaves):
                        singles[part][chosen, leaf] += share * alone[leaf]
                    least = np.minimum.reduce(alone)
                    if joint:
                        least = np.minimum(least, _joint([chances[leaf][:, :draws] for leaf in joint]))
                    together[part][chosen] += share * least
        return singles, together

    def _chance(self, weights, passing, offset) -> np.ndarray:
        """Per row and number j of earlier ordinary draws without a hit, c: at least the chance that the next draw hits X (module text).

        `offset` is the forced mod's (`_offset`): the slots it takes on each side and the families of the pool it takes out of each side.
        """
        slots, taken = offset[:2], offset[2:]
        rows = len(weights)
        hit = (weights * passing) @ self.one_hot  # rows x families: x_f
        junk = (weights * ~passing) @ self.one_hot  # j_f
        sides = []
        for mask in (self.prefix, ~self.prefix):
            ascending = np.sort(junk[:, mask], axis=1)
            smallest = np.concatenate([np.zeros((rows, 1)), np.cumsum(ascending, axis=1)], axis=1)  # [:, i]: the sum of the i smallest
            sides.append((hit[:, mask].sum(axis=1), smallest, int(mask.sum())))
        most = max(0, max(total for total, _ in self.totals) - self.kept)
        chance = np.zeros((rows, most + 1))
        for prior in range(most + 1):
            for a in range(prior + 1):
                drawn = (a, prior - a)
                if any(drawn[side] + slots[side] > self.room[side] for side in (0, 1)):
                    continue  # that split of the earlier draws cannot have happened
                x = np.zeros(rows)
                j = np.zeros(rows)
                for side in (0, 1):
                    x_side, smallest, width = sides[side]
                    if drawn[side] + slots[side] < self.room[side]:  # the side is open
                        x = x + x_side
                        j = j + smallest[:, max(width - drawn[side] - taken[side], 0)]
                ratio = np.divide(x, x + j, out=np.zeros(rows), where=x > 0)
                chance[:, prior] = np.maximum(chance[:, prior], ratio)
        return chance

def _joint(chances: list[np.ndarray]) -> np.ndarray:
    """Per row, the sum over the ways to give each X its own draw of the product of their c's (`_bound._joint_hits`, per row)."""
    count = len(chances)
    rows, draws = chances[0].shape
    ways = [np.zeros(rows) for _ in range(1 << count)]
    ways[0] = np.ones(rows)
    for draw in range(draws):
        for mask in range(len(ways) - 1, -1, -1):  # descending: a mask grows only into larger ones
            for k in range(count):
                if not mask >> k & 1:
                    ways[mask | 1 << k] = ways[mask | 1 << k] + ways[mask] * chances[k][:, draw]
    return ways[-1]

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
