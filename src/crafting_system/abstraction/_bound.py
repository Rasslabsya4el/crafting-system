"""A rigorous upper bound, from the pool alone, on the chance that one use of a reroll makes a set of leaves PASSING (#118).

`reach_bound(abstraction, state, action, leaves)` is a number that is never below the exact chance that,
after one use of `action`, every leaf of `leaves` is PASSING. It is for bound-based pruning of actions:
the expected cost of making the leaves PASSING is at least `cost / bound` for the best action, so an
action whose best case cannot beat the best exact one per Chaos can be dropped. With `exact=True` it
returns the exact chance itself, through `Outcomes.distribution` (one run of the exact engine).

The argument, for one part of the outcomes (a pool draw) and one leaf L. X is the set of pool mods that
are PASSING for L. The leaf is made PASSING if a kept mod (fractured, forced) is, or if some drawn mod
is in X; a leaf a kept mod makes PASSING costs nothing (bound 1). The process (`actions/draw.py`): a
total T is drawn from `totals`; with a tag one guaranteed draw comes first, from the tagged mods of the
sides with room; then `max(0, T - kept - guaranteed)` ordinary draws, each picking one mod of an
undrawn family on a side with room in proportion to weight, the whole family leaving the pool and its
side losing a slot.

One draw. Let c_j be a number such that, for every history of the draws before draw j in which no drawn
mod is in X, the chance that draw j picks a mod of X is at most c_j. By the chain rule
P(no hit in the first n draws) = prod_j P(no hit at j | no hit before), and each factor is an average
of 1 - (hit chance at j) over histories without a hit, hence at least 1 - c_j. So
P(hit) <= 1 - prod_j (1 - c_j), for each total T over its own number of draws, then averaged over
`totals`. (A draw that cannot happen has hit chance 0, which c_j covers.) The guaranteed draw is the
first one and c_0 is its exact chance, tagged X weight over tagged weight on the sides with room.

Finding c_j for an ordinary draw with `prior` draws before it (the guaranteed one counted). Of the
earlier draws, a were made on the prefix side and b = prior - a on the suffix side; each used a slot of
a side with room and a distinct family of its side, so a <= free prefix slots, a <= prefix families,
and the same for b. Enumerate every such (a, b). A side is open for draw j when a < its free slots and
fewer than all its families were drawn. The weight that can be picked is the weight of the undrawn
families of the open sides, and the weight that hits is the X weight of the same families; in a
history with no hit the drawn families are known to have taken their X mods out of the pool as well.
So the chance is at most max over the sets of a prefix families and b suffix families that were
drawn of (X weight of the rest) / (weight of the rest) on the open sides, found exactly by
Dinkelbach's iteration (`_scenario_chance`: for a guess `price` of the ratio, the drawn families that
make `hit - price * whole` largest are those with the largest `price * weight - X weight`). c_j is the
maximum over the scenarios (0 when none is feasible or none can hit). This is larger than any real
history's chance, because the real drawn families are one of the sets maximised over, and the real
history is one of the (a, b) enumerated.

Several leaves. P(all) <= P(any one) for each member, so the bound is at most the smallest single bound.
Besides, when the X's of some leaves are pairwise disjoint (no mod is PASSING for two of them), each
needs a draw of its own. P(X_k first hit at draw i and X_l first hit at draw j) <= c_k(i) c_l(j)
(the later one's chance given any history without a hit of its own X is at most its c, and the
earlier one's chance of being the first hit is at most its c; a history that holds hits of the other
X's is a history of the scenario enumeration too, since a mod of another X is not in this X). The
union bound over the ways to give every X its own draw is `_joint_hits`. The bound for the leaves
is the smallest of the single bounds and the joint bound of a greedily chosen disjoint subset,
taken per total T, and averaged over `totals`.

The bound of an action is the mean over its parts (`components`) by their shares. Where a step could
be loose it is loose upwards: a drawn family is assumed to be the worst one, a hit is assumed to end
nothing. None of it is below the exact value; the tests compare it with the brute force and with the
exact engine on random pools.
"""

from collections.abc import Hashable, Mapping, Sequence
from fractions import Fraction

from crafting_system.actions import Action, Fixed, OutOfScopeError, PoolFamily
from crafting_system.actions.draw import guaranteed_candidates
from crafting_system.data import Mod
from crafting_system.items import Side

from ._goal import Status
from ._kernel import Abstraction
from ._state import CompressedState

ZERO, ONE = Fraction(0), Fraction(1)


class _Side:
    """One side of a pool: the weight and the X weight of each family (X: the mods that are PASSING)."""

    def __init__(self, families: Sequence[tuple[Fraction, Fraction]]):
        self.families = tuple(families)  # (weight of the family, weight of its X mods)
        self.count = len(self.families)
        self.weight = sum((weight for weight, _ in self.families), ZERO)
        self.wanted = sum((wanted for _, wanted in self.families), ZERO)

    def after(self, drawn: int, price: Fraction) -> tuple[Fraction, Fraction]:
        """The `(X weight, weight)` left on this side after the `drawn` families that maximise `wanted - price * weight` of the rest.

        Drawn families leave with their whole weight, X mods included; the families that hurt the most
        (the most X weight, the least weight) are the ones assumed drawn, which is the largest ratio.
        """
        by_value = sorted(self.families, key=lambda family: price * family[0] - family[1], reverse=True)
        gone = by_value[:drawn]
        return (
            self.wanted - sum((wanted for _, wanted in gone), ZERO),
            self.weight - sum((weight for weight, _ in gone), ZERO),
        )


def _sides(pool: Sequence[PoolFamily], passing: Mapping[str, bool]) -> dict[Side, _Side]:
    """The `_Side` of each side of `pool`; `passing` says which mod ids are in X."""
    families: dict[Side, list[tuple[Fraction, Fraction]]] = {side: [] for side in Side}
    for family in pool:
        wanted = sum((entry.weight for entry in family.mods if passing[entry.mod.id]), ZERO)
        families[family.side].append((family.weight, wanted))
    return {side: _Side(families[side]) for side in Side}


def _scenario_chance(live: Sequence[tuple[_Side, int]]) -> Fraction:
    """The largest chance that a draw hits X when the `live` sides (side, families drawn on it) are the open ones.

    The hit weight is the X weight of the undrawn families and the whole weight the weight of the
    undrawn families; the ratio is largest over the choices of which `drawn` families of each side
    were drawn. Dinkelbach's iteration finds that largest ratio exactly: with `price` the best ratio
    found so far, the choice that maximises `hit - price * whole` is the `drawn` families of each side
    with the largest `price * weight - wanted`; if that is not positive, `price` is the largest ratio.
    """
    price = ZERO
    while True:
        hit = whole = ZERO
        for side, drawn in live:
            side_hit, side_whole = side.after(drawn, price)
            hit += side_hit
            whole += side_whole
        if whole <= 0:  # cannot happen for a live side (an undrawn family has weight); stay on the safe side
            return ONE
        better = hit / whole
        if better <= price:
            return price
        price = better


def _draw_chance(prior: int, free: Mapping[Side, int], sides: Mapping[Side, _Side]) -> Fraction:
    """The most that ordinary draw number `prior + 1` can hit X with, over every history of `prior` earlier draws.

    The history is one with no hit so far (the draws made were not X mods): `a` of them on the prefix
    side and `prior - a` on the suffix side, for every `a` that fits the free slots and the families of
    each side. A side is open for the draw when it has a free slot left and an undrawn family.
    """
    prefix, suffix = sides[Side.PREFIX], sides[Side.SUFFIX]
    room_prefix, room_suffix = max(0, free[Side.PREFIX]), max(0, free[Side.SUFFIX])
    best = ZERO
    for a in range(min(prior, room_prefix, prefix.count) + 1):
        b = prior - a
        if b > room_suffix or b > suffix.count:
            continue  # this split of the earlier draws between the sides cannot have happened
        live = []
        if a < room_prefix and a < prefix.count:
            live.append((prefix, a))
        if b < room_suffix and b < suffix.count:
            live.append((suffix, b))
        if not live or sum(side.wanted for side, _ in live) == 0:
            continue  # nothing can be drawn, or nothing drawn can hit
        best = max(best, _scenario_chance(live))
    return best


def _guaranteed_chance(pool: Sequence[PoolFamily], free: Mapping[Side, int], tag: str, passing: Mapping[str, bool]) -> Fraction:
    """The exact chance that the guaranteed draw picks a mod of X: tagged X weight over tagged weight, sides with room."""
    candidates = guaranteed_candidates(pool, free, tag)
    whole = sum((entry.weight for _, entry in candidates), ZERO)
    if whole == 0:
        return ZERO
    return sum((entry.weight for _, entry in candidates if passing[entry.mod.id]), ZERO) / whole


def _draw_chances(
    pool: Sequence[PoolFamily],
    free: Mapping[Side, int],
    totals: Mapping[int, Fraction],
    kept: int,
    tag: str | None,
    passing: Mapping[str, bool],
) -> list[Fraction]:
    """For each draw in order (the guaranteed one first), the most it can hit X with, given no hit before.

    The guaranteed draw's entry is its exact chance. The list is as long as the longest draw count
    of any total in `totals` (see `_draw_counts`).
    """
    sides = _sides(pool, passing)
    chances = [] if tag is None else [_guaranteed_chance(pool, free, tag, passing)]
    for prior in range(len(chances), max(_draw_counts(totals, kept, tag).values(), default=0)):
        chances.append(_draw_chance(prior, free, sides))
    return chances


def _draw_counts(totals: Mapping[int, Fraction], kept: int, tag: str | None) -> dict[int, int]:
    """How many draws are made for each total: the guaranteed one, then `total - kept - guaranteed` ordinary ones."""
    guaranteed = 0 if tag is None else 1
    return {total: guaranteed + max(0, total - kept - guaranteed) for total in totals}


def _single_miss(chances: Sequence[Fraction], draws: int) -> Fraction:
    """A lower bound on the chance that none of the first `draws` draws hits X.

    By the chain rule, P(no hit) is the product over draws of P(no hit now | no hit before), and each
    factor is at least 1 - c_j because c_j bounds the hit chance over every history without a hit.
    """
    miss = ONE
    for chance in chances[:draws]:
        miss *= 1 - chance
    return miss


def _joint_hits(chances: Sequence[Sequence[Fraction]], draws: int) -> Fraction:
    """An upper bound on the chance that each X in a family of pairwise disjoint X's is hit by some of the first `draws` draws.

    A mod is in at most one X, so each X is first hit by a different draw. The chance that X number k
    is first hit at draw i, and X number l at draw j, say i before j, is at most c_k[i] * c_l[j]:
    first the draw j conditioned on any history with no hit of X number l before it, then P(first hit of
    k at i) <= c_k[i]. By the union bound over the ways to give each X its own draw, the chance is at most
    the sum over injective assignments of the product of c_k[draw of k]: a sum computed by walking the
    draws and the subsets of the X's already given a draw.
    """
    count = len(chances)
    ways = [ZERO] * (1 << count)
    ways[0] = ONE
    for draw in range(draws):
        for mask in range(len(ways) - 1, -1, -1):  # descending: a mask grows only into larger ones
            if ways[mask] == 0:
                continue
            for k in range(count):
                if not mask >> k & 1:
                    ways[mask | 1 << k] += ways[mask] * chances[k][draw]
    return ways[-1]


def _part_bound(
    pool: Sequence[PoolFamily],
    free: Mapping[Side, int],
    totals: Mapping[int, Fraction],
    kept: int,
    tag: str | None,
    passings: Sequence[Mapping[str, bool]],
) -> Fraction:
    """An upper bound on the chance that a draw from `pool` puts a mod of every X of `passings` (by mod id) on the item.

    For each total the bound is the smallest of: the bound of each X alone (one minus `_single_miss`),
    and, over a greedily chosen subset of pairwise disjoint X's, their `_joint_hits`.
    """
    chances = [_draw_chances(pool, free, totals, kept, tag, passing) for passing in passings]
    counts = _draw_counts(totals, kept, tag)
    alone = [[1 - _single_miss(row, counts[total]) for total in totals] for row in chances]
    members = [{mod_id for mod_id, flag in passing.items() if flag} for passing in passings]
    chosen: list[int] = []
    for k in sorted(range(len(passings)), key=lambda k: sum(alone[k], ZERO)):
        if all(not members[k] & members[l] for l in chosen):
            chosen.append(k)
    result = ZERO
    for position, (total, chance) in enumerate(totals.items()):
        bound = min(row[position] for row in alone)
        if len(chosen) > 1:
            bound = min(bound, _joint_hits([chances[k] for k in chosen], counts[total]))
        result += chance * min(ONE, bound)
    return result


def _leaf_bound(
    pool: Sequence[PoolFamily],
    free: Mapping[Side, int],
    totals: Mapping[int, Fraction],
    kept: int,
    tag: str | None,
    passing: Mapping[str, bool],
) -> Fraction:
    """An upper bound on the chance that a draw from `pool` puts a mod of X (`passing` by mod id) on the item."""
    return _part_bound(pool, free, totals, kept, tag, [passing])


def _passing_ids(abstraction: Abstraction, pool: Sequence[PoolFamily], leaf: int, memo: dict) -> dict[str, bool]:
    """For every mod of `pool`: whether it is PASSING for leaf number `leaf` when drawn."""
    found: dict[str, bool] = {}
    for family in pool:
        for entry in family.mods:
            key = (entry.mod.id, leaf)
            if key not in memo:
                memo[key] = abstraction.passes(entry.mod, leaf)
            found[entry.mod.id] = memo[key]
    return found


def _guard(abstraction: Abstraction, pool: Sequence[PoolFamily], leaves: Sequence[int]) -> None:
    """Raise `OutOfScopeError` when a leaf asks for a roll of a mod that the pool can draw."""
    ids = {entry.mod.id for family in pool for entry in family.mods}
    for index in leaves:
        leaf = abstraction.goal.leaves[index]
        if leaf.has_roll_limit and ids & leaf.mod_ids:
            raise OutOfScopeError("a roll limit on a drawn mod is not modelled yet, so no bound is given")


def reach_bound(
    abstraction: Abstraction,
    state: CompressedState,
    action: Action,
    leaves: Sequence[int],
    *,
    exact: bool = False,
) -> Fraction | None:
    """An upper bound on the chance that one use of `action` on `state` makes every leaf of `leaves` PASSING.

    `leaves` are indexes into `abstraction.goal.leaves`. The bound uses the pool alone and costs
    milliseconds; with `exact=True` the result is the exact chance. Returns None when the action
    cannot be bounded: it reads the junk (it does not erase it), a part of its result is a `Fixed`
    one, it fractures a mod, or a leaf of `leaves` limits the roll of a mod in its pool.
    """
    leaves = tuple(leaves)
    if not leaves:
        raise ValueError("leaves must not be empty")
    if any(not 0 <= index < len(abstraction.goal.leaves) for index in leaves):
        raise ValueError(f"leaves {leaves} are not all leaf indexes of a goal of {len(abstraction.goal.leaves)} leaves")
    if len(state.status) != len(abstraction.goal.leaves):
        raise ValueError("the state comes from another abstraction")
    if action.reads(abstraction.data).junk:
        return None
    try:
        prepared = abstraction._prepared(state, action)
        outcomes = prepared.outcomes
        if outcomes.fractures or any(isinstance(part, Fixed) for _, part in outcomes.components):
            return None
        memo: dict = {}
        total = ZERO
        for share, part in outcomes.components:
            _guard(abstraction, part.pool, leaves)
            retained = abstraction._split(part.retained, prepared.origins).status
            todo = [index for index in leaves if retained[index] is not Status.PASSING]
            if not todo:
                total += share
            elif exact:
                total += share * _exact_part(abstraction, part, leaves, retained)
            else:
                total += share * _part_bound(
                    part.pool,
                    part.free,
                    part.totals,
                    len(part.retained.mods),
                    part.tag,
                    [_passing_ids(abstraction, part.pool, index, memo) for index in todo],
                )
        return min(ONE, total)
    except OutOfScopeError:
        return None


def _exact_part(abstraction: Abstraction, part, leaves: Sequence[int], retained: Sequence[Status]) -> Fraction:
    """The exact chance that the retained mods and the draws of `part` make every leaf PASSING."""

    def label(mod: Mod) -> Hashable:
        return tuple(abstraction.passes(mod, index) for index in leaves)

    total = ZERO
    for outcome, chance in part.distribution(label).items():
        if all(
            retained[index] is Status.PASSING or any(flags[position] for flags, _ in outcome)
            for position, index in enumerate(leaves)
        ):
            total += chance
    return total
