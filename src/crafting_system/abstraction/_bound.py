"""A rigorous upper bound, from the pool alone, on the chance that one use of a reroll makes a set of leaves PASSING (#118).

`reach_bound(abstraction, state, action, leaves)` is a number that is never below the exact chance that,
after one use of `action`, every leaf of `leaves` is PASSING. It is for bound-based pruning of actions:
the expected cost of making the leaves PASSING is at least `cost / bound` for the best action, so an
action whose best case cannot beat the best exact one per Chaos can be dropped. With `exact=True` it
returns the exact chance itself, through `Outcomes.distribution` (one run of the exact engine).

The argument, for one part of the outcomes (a pool draw) and one leaf L. X is the set of pool mods that
are PASSING for L (under a roll limit, at some roll: a mod outside X never passes L,
#830). The leaf is made PASSING if a kept mod (fractured, forced) is, or if some drawn mod
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

One added mod (`add_bound`, #1072). An action that keeps the mods and adds one drawn mod (an Exalted Orb; `Reads.pool_weight`: the families on
the item leave the pool, so the draw depends on them only through the weight they take out) cannot be read at one state for all: its chance
depends on which families the item holds. What the floors of the planner need (`planner/_offer_kinds`, pbar) is a number that is never below
its chance, from ANY state of one shape (the flags and the fractured mods of the bare item `s0`) at which a leaf L is not PASSING, of putting
on the item a mod of X (the mods that pass L at some roll). At such a state `s`, the mod is drawn from the mods of the pool of `s0` (less
the mods of the tags an Attack or Caster metamod of `s` keeps out, and only those of the tag the action names, `Adds.tag`) whose family `s`
does not hold, on the sides where `s` has room, in proportion to weight; so its chance of X is `(X weight left) / (weight left)` over the open
sides. `s` holds on each side at most its free slots of `s0`, and at most that many families of the pool; a side is open when what it holds is
below its room. So that chance is at most the largest, over the numbers `a` and `b` of families taken out of each side (below the room of an
open side) and over which families they are, of that ratio: Dinkelbach's iteration (`_scenario_chance`) finds it exactly over every set of
families of each count, the families of X included. The pool of `s0`, its free slots and the draw's tag are read from the action's own result
at `s0` (one part, one draw); the blocked tags are every set the two metamods make when the abstraction models them. Nothing here tracks
which families a state holds: it is the most favourable weight share of the free families, the same at every state of the shape. What is
taken on the contract of `Reads.pool_weight` and not checked: that the action draws the same way at every state of the shape (from the pool
of `s0` less the held families and the blocked tags, one mod, on a side with room) as it does at `s0`. Where it is known not to hold, no
bound is given (None): a draw cut by Memory Strands on an item that holds some (each use spends a number that follows the mods held, so the
states of the shape hold other counts and draw from other cuts). The tests compare the bound with the
exact chance at every member state of hand-worked pools (`tests/test_add_bound.py`), including the members whose chance is above the
chance at `s0`, the one a bound read at `s0` alone would give.

The bound of an action is the mean over its parts (`components`) by their shares. Where a step could
be loose it is loose upwards: a drawn family is assumed to be the worst one, a hit is assumed to end
nothing. None of it is below the exact value; the tests compare it with the brute force and with the
exact engine on random pools.
"""

from collections.abc import Hashable, Mapping, Sequence
from fractions import Fraction

from crafting_system.actions import BLOCKED_TAG, Action, Fixed, OutOfScopeError, PoolFamily, Rerolled, allowed_by_tags, guaranteed_candidates, partners
from crafting_system.budget import checkpoint
from crafting_system.data import Mod
from crafting_system.items import ItemError, Side

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


def _guard(pool: Sequence[PoolFamily]) -> None:
    """Raise `OutOfScopeError` for a pool the bound has no argument for: a family with mods on both sides."""
    if partners(pool):
        raise OutOfScopeError(
            "a family with mods on both sides of the item (a jewel) is not modelled yet",
            detail="a family with mods on both sides is not modelled in the bound, so no bound is given",
        )


def _roll_cells(abstraction: Abstraction, mod: Mod, leaves: Sequence[int], influences, lucky: bool) -> tuple[tuple[tuple[bool, ...], Fraction], ...]:
    """What a drawn `mod` does for `leaves` over its rolls: (which leaves it makes PASSING, chance), one entry per pattern (#830).

    Under a roll limit a drawn mod of a leaf passes it only at some rolls: its roll law (`_rolls.roll_law`, lucky for a draw that rolls twice
    and keeps the better). Without one the mod does the same at every roll, its low roll's judgement (`Abstraction.passes`).
    """
    if not abstraction._has_laws:
        return ((tuple(abstraction.passes(mod, index) for index in leaves), ONE),)
    found: dict[tuple[bool, ...], Fraction] = {}
    for ints, chance in abstraction._law(mod, influences, lucky):
        flags = tuple(ints[index] == Status.PASSING for index in leaves)
        found[flags] = found.get(flags, ZERO) + chance
    return tuple(sorted(found.items()))


def _may_pass(abstraction: Abstraction, pool: Sequence[PoolFamily], leaf: int, influences, memo: dict) -> dict[str, bool]:
    """For every mod of `pool`: whether some roll of it, drawn, makes leaf number `leaf` PASSING (the X of the loose bound, #830).

    A mod that passes at some rolls only is counted in X: the leaf is PASSING only if a mod of X is drawn, so the chance of drawing one stays
    above the chance of the leaf, and the argument of the module text holds as it is.
    """
    found: dict[str, bool] = {}
    for family in pool:
        for entry in family.mods:
            key = (entry.mod.id, leaf)
            if key not in memo:
                memo[key] = any(flags[0] for flags, _ in _roll_cells(abstraction, entry.mod, (leaf,), influences, False))
            found[entry.mod.id] = memo[key]
    return found


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
    or a `Rerolled` one, or it fractures a mod. A roll limit on a mod of its pool is bounded since
    #830: the bound counts a mod that passes at some roll, and the exact chance follows the mod's roll law.
    """
    checkpoint()  # the run's net (#825, #702): the bound pruning raises thousands of these, in pool workers too (they inherit the run's clock by fork)
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
        if outcomes.fractures or any(isinstance(part, (Fixed, Rerolled)) for _, part in outcomes.components):
            return None
        memo: dict = {}
        total = ZERO
        for share, part in outcomes.components:
            _guard(part.pool)
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
                    [_may_pass(abstraction, part.pool, index, part.retained.influences, memo) for index in todo],
                )
        return min(ONE, total)
    except OutOfScopeError:
        return None


def declared_bounds(abstraction: Abstraction, state: CompressedState, actions: Sequence[Action], leaves: Sequence[int]) -> list[Fraction | None]:
    """For each action of `actions` (all of one class), an upper bound on the chance that one use on `state` makes every leaf of `leaves`
    PASSING, from what the class declares without building an outcome (`Action.reach_batch`, #1073); None where it declares no bound or that the
    action may leave the shape (`ReachDeclared.keeps_shape`).

    `state` is the bare item of a shape (its fractured mods and nothing else). X of a leaf is what `reach_bound` reads (`_may_pass`: some roll of
    the mod makes the leaf PASSING), and P(every leaf) <= P(each one), so the bound is the least of the declared chances. The declared bound is the
    class's argument (`actions/fossil_reach.py` for the fossil sets), checked by its tests against the exact chance.
    """
    checkpoint()
    leaves = tuple(leaves)
    if not leaves or not actions:
        return [None] * len(actions)
    if len(state.status) != len(abstraction.goal.leaves):
        raise ValueError("the state comes from another abstraction")
    try:
        item = abstraction._item_of(state, True)[0]
    except (ItemError, ValueError):
        return [None] * len(actions)
    influences = state.flags.influences

    def passes(mod: Mod) -> tuple[bool, ...]:
        return tuple(any(flags[0] for flags, _ in _roll_cells(abstraction, mod, (leaf,), influences, False)) for leaf in leaves)

    answers = type(actions[0]).reach_batch(abstraction.data, item, tuple(actions), passes)
    if answers is None:
        return [None] * len(actions)
    found: list[Fraction | None] = []
    for answer in answers:
        if answer is None or not answer.keeps_shape or answer.chances is None:
            found.append(None)
        else:
            least = min(answer.chances) if answer.together is None else min(*answer.chances, answer.together)
            found.append(min(ONE, Fraction(least)))
    return found


def add_bound(abstraction: Abstraction, state: CompressedState, action: Action, leaves: Sequence[int]) -> Fraction | None:
    """An upper bound, over EVERY state with the flags and the fractured mods of `state` (whatever else it holds) at which one leaf of `leaves`
    is not PASSING, on the chance that one use of the adding action `action` puts on the item a mod that makes that leaf PASSING (#1072).

    `state` is the bare item of the shape (its fractured mods and nothing else). The action is one that keeps the junk and draws ONE mod from the
    pool of the item less the families it holds, on a side with room (`Reads.pool_weight`; an Exalted Orb, an Orb of Augmentation; not a Harvest
    add/remove craft, which also removes a mod, so its result is not one drawn mod: None; see "One added mod" in the module text for the argument and what it takes on the contract). Returns None when the
    action at `state` is not one such draw: a part that is not a pool draw, a draw count other than one, or a fracture; and when the item holds
    Memory Strands and the action's draw is cut by them (the count, and so the cut, differs between the states of the shape). Raises what the action
    raises at `state` (`NotApplicableError`, `OutOfScopeError`): a refusal at the bare item says nothing of the states that hold more mods.
    """
    checkpoint()
    leaves = tuple(leaves)
    if not leaves:
        raise ValueError("leaves must not be empty")
    if len(state.status) != len(abstraction.goal.leaves):
        raise ValueError("the state comes from another abstraction")
    use = action.strand_use(abstraction.data)
    if state.strands and use is not None and use.cuts:
        return None  # the cut follows the Memory Strand count, which the uses before it spend: not the same draw at every state of the shape
    prepared = abstraction._prepared(state, action)
    outcomes = prepared.outcomes
    if outcomes.fractures:  # `components` and `fractures` are on the `ActionOutcomes` contract
        return None
    components = outcomes.components
    tag_sets = _blocked_sets() if abstraction.models_metamods else (frozenset(),)
    memo: dict = {}
    best = ZERO
    for _share, part in components:
        if isinstance(part, (Fixed, Rerolled)) or not hasattr(part, "pool"):
            return None
        if set(_draw_counts(part.totals, len(part.retained.mods), part.tag).values()) != {1}:
            return None
        _guard(part.pool)
        for leaf in leaves:
            passing = _may_pass(abstraction, part.pool, leaf, part.retained.influences, memo)
            for blocked in tag_sets:
                best = max(best, _added_chance(part.pool, part.free, part.tag, blocked, passing))
    return min(ONE, best)


def _blocked_sets() -> tuple[frozenset[str], ...]:
    """Every set of tags the Attack and Caster metamods can keep out of a draw (none, either, both)."""
    tags = sorted(set(BLOCKED_TAG.values()))
    return tuple(frozenset(tag for bit, tag in enumerate(tags) if mask >> bit & 1) for mask in range(1 << len(tags)))


def _added_chance(pool: Sequence[PoolFamily], free: Mapping[Side, int], tag: str | None, blocked: frozenset[str], passing: Mapping[str, bool]) -> Fraction:
    """The largest chance that the one added mod is in X, over every set of families held besides the bare item's and every room left.

    The draw picks from the mods of `pool` that carry `tag` (all when None) and none of `blocked`, on the sides with room. A state holds `a` more
    mods on the prefix side and `b` on the suffix side (`0 <= a <= free prefix`, and the same for `b`), whose families (at most `a` and `b` of them:
    a crafted mod of no family takes a slot and no weight) left the pool. A side is open when its `a` is below its free slots. For each `(a, b)` and
    each number `k` of families taken out of an open side (`k <= a`), the largest ratio over which families is `_scenario_chance`'s, which ranges
    over every set of `k` families, X families included. A closed side takes nothing out of the draw, and every way a side closes is a `k` of the
    loop: `k` at its room (whatever filled the slots: families, a crafted mod of none) or at its number of families (nothing left to draw there).
    """
    kept: dict[Side, list[tuple[Fraction, Fraction]]] = {side: [] for side in Side}
    for family in pool:
        mods = [entry for entry in family.mods if allowed_by_tags(entry.mod, blocked) and (tag is None or tag in entry.mod.implicit_tags)]
        weight = sum((entry.weight for entry in mods), ZERO)
        if weight > 0:
            kept[family.side].append((weight, sum((entry.weight for entry in mods if passing[entry.mod.id]), ZERO)))
    # a family with no mod left in the draw still leaves the pool when held, but takes no weight from it: dropping it from the sides changes no ratio
    sides = {side: _Side(kept[side]) for side in Side}
    room = {side: max(0, free[side]) for side in Side}
    best = ZERO
    taken = {side: range(0, min(room[side], sides[side].count) + 1) for side in Side}
    for a in taken[Side.PREFIX]:
        for b in taken[Side.SUFFIX]:
            live = [(sides[side], k) for side, k in ((Side.PREFIX, a), (Side.SUFFIX, b)) if k < room[side] and k < sides[side].count]
            if not live or sum(side.wanted for side, _ in live) == 0:
                continue
            best = max(best, _scenario_chance(live))
    return best


def _exact_part(abstraction: Abstraction, part, leaves: Sequence[int], retained: Sequence[Status]) -> Fraction:
    """The exact chance that the retained mods and the draws of `part` make every leaf PASSING.

    A drawn mod is labelled by what it does for the leaves over its rolls (`_roll_cells`): one pattern without a roll limit, the law's patterns
    with one. The rolls of the drawn mods are independent (`actions.rolls`), so the chance that every leaf ends PASSING, given the mods drawn, is
    found by joining their patterns one mod at a time (a leaf passes when any mod passes it).
    """
    influences, lucky = part.retained.influences, bool(getattr(part, "rolls_lucky", False))

    def label(mod: Mod) -> Hashable:
        return _roll_cells(abstraction, mod, leaves, influences, lucky)

    start = tuple(retained[index] is Status.PASSING for index in leaves)
    total = ZERO
    for outcome, chance in part.distribution(label).items():
        checkpoint()
        held: dict[tuple[bool, ...], Fraction] = {start: ONE}
        for cells, count in outcome:
            for _ in range(count):
                joined: dict[tuple[bool, ...], Fraction] = {}
                for passed, before in held.items():
                    for flags, each in cells:
                        key = tuple(a or b for a, b in zip(passed, flags))
                        joined[key] = joined.get(key, ZERO) + before * each
                held = joined
        total += chance * sum((each for passed, each in held.items() if all(passed)), ZERO)
    return total


def keeps_shape(abstraction: Abstraction, state: CompressedState, action: Action) -> bool:
    """Whether every outcome of `action` on `state` has the flags and the fractured mods that `state` has.

    A pruning that holds the start's flags and fractured mods fixed for an action it bounds needs this
    (#118): `reach_bound` is read at one state, and it holds at another only when the result of the
    action does not move the item to another shape. False when the action fractures a mod or changes
    the rarity, the corruption or the influences. Raises what the action raises (`NotApplicableError` or `OutOfScopeError`) when
    it is refused on the item `state` stands for.
    """
    prepared = abstraction._prepared(state, action)
    if prepared.outcomes.fractures:
        return False
    return all(
        split.flags == state.flags and split.fractured == state.fractured for split in abstraction._splits_of(prepared)
    )
