"""The relaxed draw: a lower bound of a reroll whose pool weights read which junk families the item holds, built without its members (#975).

**The action.** A reroll that multiplies, before it draws, the weight of every mod of a family the item holds by a factor `f`
(`Action.held_weight_factor`: the likelihood Harvest reforges, `f` 10 or 1/10), then draws as `actions/draw.py` says: one mod at a
time over both sides in proportion to weight, its family leaves the pool, a full side closes, a dry pool stops, until the item holds
`total` mods. The members of a key differ in which pure junk families they hold (the module docstring of `_pattern`), and here each
fill `J` is a pool of its own: the boost reads `J`, and the draw is several mods, so neither the corners of `EXTREMES` (one draw) nor
the count of `ONE` holds. `ALL` is exact and makes every fill's multi-draw: about 85 distinct pools a key on the R12 fixture, 20 s a
round (#975). This module makes, for one `ONE` member `m` (its relevant mods, crafted and fractured mods, and how many pure junk
families of each class it holds are the key's or enumerated; which ones is left open), a small model whose value is at most the
action's backup at every member of the key that shares those, whatever its fill: the **choice nodes**.

**The walk.** A node is `x = (room of each side, the relevant mods drawn, d_c the pure junk families of class c drawn)`. Its outcomes
are a relevant mod (each mod of an open relevant family, weight `w * f` when its family is boosted: the families of `m`'s mods that are
not pure junk, which every member shares) or one pure junk family of class `c` (its side open). Of class `c` the walk knows `A_c`
(the weight of all its families in the pool after the reroll), `n_c` (the families of `c` the item held) and `d_c`, not which: the
weight `u_c` the class has left lies in a box,

* `f > 1`: `A_c - Hmax_c(d_c) + (f-1) Hmin_c(max(0, n_c - d_c)) <= u_c <= A_c - Hmin_c(d_c) + (f-1) Hmax_c(n_c)`,
* `f < 1`: `A_c - Hmax_c(d_c) + (f-1) Hmax_c(n_c) <= u_c <= A_c - Hmin_c(d_c) + (f-1) Hmin_c(max(0, n_c - d_c))`,

clipped at 0, with `Hmin_c(k)`, `Hmax_c(k)` the weight of the `k` lightest and heaviest families of `c`. Proof: with `D` the families
drawn and `J` those held, `u_c = sum_{F not in D} w_F + (f-1) sum_{F in J - D} w_F`; the first sum is between `A_c - Hmax(d_c)` and
`A_c - Hmin(d_c)`; `J - D` has between `max(0, n_c - d_c)` and `n_c` families, so the second sum lies between `(f-1)` times the
lightest of the fewest and the heaviest of the most (the sign of `f-1` orders them). A family of the pool that gives the goal nothing
at any roll but that the abstraction tells apart by name (an enabled action names it) joins the class of its side and protected tags in
the walk: the members hold it exactly (its boost is known, its weight `w'` is in `A_c` as boosted), and which one is drawn the key does not
read (it gives no status). It is not one a member may hold unknown, so `Hmin`/`Hmax` of the boost are over the pure junk types alone and
those of the draw over every family of the class: the proof above holds with `w'` for `w` in the first sum. A node offers one kernel for each corner of the
box of its open classes (each class at its least or its greatest `u_c`), each at no cost (`FLOOR_COST` in the packed graph); a node
whose draws are done, or whose candidates weigh nothing, is an end: the item `retained + the relevant mods + d_c families of each class`,
compressed, whose key is the key of every real item that ends there (the key reads the status, which the relevant mods and the
kept mods give, and the counts and the protected tags per side, which the class counts give: `PatternKey`).

**Sound.** Let `V` be any values of the keys and `G(x)` the least value of the choice model at `x` under them. Claim: for every
member `s` of the key with `m`'s relevant mods and class counts (any fill `J`) and every history `h` of its draw that the walk reads
as `x`, `G(x) <= E_s[V(end) | h]`. By induction on the draws left. At an end, both are `V` of the same key. Else the next draw of
`s` after `h` is a relevant mod with chance `w'/(R + sum_c u_c(h))` (the relevant weights `w'` and the room are the walk's: the boosted
set and the relevant mods drawn are exact) or a junk family of class `c` with chance `u_c(h)/(R + sum_c u_c(h))`, with `u(h)` in the
box. So `E_s[V(end) | h] = sum_y p_y(u(h)) E_s[V(end) | h, y] >= sum_y p_y(u(h)) G(y)` by induction (every history `h, y` is read as
`y`). That is a linear-fractional function of `u` with a positive denominator, so quasi-linear: its least over the box is at a corner,
and the node's least corner kernel gives at most it. With `x` the first node, `G` is at most the backup of every member, so the row
`(offer, entry node)` is at most the least backup over those members, and the induction of `_pattern` holds: `V_key <= V*`. The model is
a DAG under the walk (each step draws one mod), so the choice nodes add no cycle.

**What falls back to `ALL`** (the caller's): a key with a lock (the locked side keeps member-dependent junk, which the draw excludes);
a pool with a family on both sides; a junk family boosted by the exact set or whose mods sit in two classes; a relevant mod whose
roll a limit tells apart; an outcome with a guaranteed or forced mod, several totals or a filtered first draw. `relaxed_draw` returns
None for each, and the caller makes every member.
"""

from collections.abc import Hashable
from dataclasses import dataclass
from fractions import Fraction
from itertools import product

from crafting_system.actions import Action
from crafting_system.actions.outcomes import Outcomes
from crafting_system.actions.pool import build_pool
from crafting_system.items import Side
from crafting_system.items.model import ExplicitMod

from ._kernel import _low_values
from ._rolls import is_rollable
from ._state import CompressedState

SIDES = (Side.PREFIX, Side.SUFFIX)


@dataclass(frozen=True)
class ChoiceNode:
    """A node of the bound's model that is no key: one partial draw of a relaxed reroll (`relaxed_draw`). `owner` names the draw, `at` the node."""

    owner: Hashable
    at: int


@dataclass
class RelaxedDraw:
    """The choice nodes of one relaxed reroll: node 0 is the entry. `nodes[i]` is a list of kernels (one per corner), each a dict from a
    target (an int: another node; a `CompressedState`: an end) to its chance."""

    nodes: list[list[dict[object, Fraction]]]


def _class_of(pattern, kinds, universe, family) -> tuple | None:
    """The pure junk class `(side, protected tags)` of a pool family, or None for a relevant one; raises `_Fallback` for a family whose mods
    sit in two classes."""
    from ._pattern import _base, _tagset

    found = set()
    for entry in family.mods:
        kind = kinds.of(entry.mod)
        found.add((family.side, _tagset(kind)) if _base(kind) in universe.pure[family.side] else None)
    if len(found) > 1:
        raise _Fallback
    return found.pop()


def _silent(pattern, kinds, family, influences) -> tuple | None:
    """The class `(side, protected tags)` of a family none of whose mods gives the goal anything at any roll, None for one that gives it
    something; raises `_Fallback` for a silent family whose mods sit in two classes."""
    from ._goal import Status
    from ._pattern import _rolled_contributions, _tagset

    found = set()
    for entry in family.mods:
        if any(value is not Status.ABSENT for status in _rolled_contributions(pattern.ab, entry.mod, influences) for value in status):
            return None
        found.add((family.side, _tagset(kinds.of(entry.mod))))
    if len(found) != 1:
        raise _Fallback
    return found.pop()


class _Fallback(Exception):
    """The relaxed draw does not hold here: the caller makes every member (`ALL`)."""


def relaxed_draw(pattern, member: CompressedState, action: Action, factor: Fraction) -> RelaxedDraw | None:
    """The choice nodes of `action` (weights of held families times `factor`) for the members of `member`'s relevant mods and class counts.

    Raises what the action raises at `member` (`NotApplicableError`, `OutOfScopeError`); None where the relaxation does not hold (the module
    text, "What falls back").
    """
    try:
        return _relaxed(pattern, member, action, factor)
    except _Fallback:
        return None


def _relaxed(pattern, member: CompressedState, action: Action, factor: Fraction) -> RelaxedDraw:
    from ._pattern import _base, _tagset

    ab, data = pattern.ab, pattern.ab.data
    influences = member.flags.influences
    kinds = ab._context(influences).kinds
    universe = pattern.universe(influences)
    item, _ = ab._item_of(member, False)
    result = action.outcomes(data, item)  # the game's refusals, and the shape of the draw
    if (
        not isinstance(result, Outcomes) or result.tag is not None or result.forced is not None or result.guaranteed_blocked
        or result.rolls_lucky or result.rerolled or len(result.totals) != 1
    ):
        raise _Fallback
    retained = result.retained
    total = next(iter(result.totals))
    draws = total - len(retained.mods)
    boosted: set[str] = set()  # the families of the mods every member shares: crafted, fractured and relevant
    held: dict[tuple, int] = {}  # class -> how many pure junk families the item holds
    for entry in item.mods:
        mod = data.mods[entry.mod_id]
        kind = kinds.of(mod)
        side = Side(mod.generation_type) if mod.generation_type in (s.value for s in SIDES) else None
        if not (entry.crafted or entry.fractured) and side is not None and _base(kind) in universe.pure[side]:
            klass = (side, _tagset(kind))
            held[klass] = held.get(klass, 0) + 1
        else:
            boosted |= set(mod.families)
    pool = build_pool(data, retained)
    names = [family.family for family in pool]
    if len(names) != len(set(names)):  # a family on both sides
        raise _Fallback
    relevant: list[tuple[Side, str, tuple[tuple[object, Fraction], ...]]] = []
    junk: dict[tuple, list[tuple[Fraction, object, bool]]] = {}  # class -> (weight, a mod, whether a member may hold it unknown) of its families
    for family in pool:
        klass = _class_of(pattern, kinds, universe, family)
        hit = [bool(boosted & set(entry.mod.families)) for entry in family.mods]
        silent = _silent(pattern, kinds, family, influences) if klass is None else None
        if silent is not None:  # a family that gives the goal nothing and that the members hold exactly: its weight is known, not which is drawn
            weight = sum((entry.weight * (factor if boost else 1) for entry, boost in zip(family.mods, hit)), Fraction(0))
            if weight:
                junk.setdefault(silent, []).append((weight, next(entry.mod for entry in family.mods if entry.weight), False))
            continue
        if klass is None:
            mods = tuple((entry.mod, entry.weight * (factor if boost else 1)) for entry, boost in zip(family.mods, hit) if entry.weight)
            for mod, _w in mods:
                if is_rollable(ab._law(mod, influences)):
                    raise _Fallback
            if mods:
                relevant.append((family.side, family.family, mods))
        else:
            if any(hit) or any(set(entry.mod.families) != {family.family} for entry in family.mods):
                raise _Fallback
            weight = sum((entry.weight for entry in family.mods), Fraction(0))
            if weight:
                representative = next(entry.mod for entry in family.mods if entry.weight)
                junk.setdefault(klass, []).append((weight, representative, True))
    for klass in held:
        junk.setdefault(klass, [])
    classes = sorted(junk, key=lambda k: (SIDES.index(k[0]), k[1]))
    weights = {k: sorted(w for w, _, _ in junk[k]) for k in classes}
    holdable = {k: sorted(w for w, _, may in junk[k] if may) for k in classes}
    counts = {k: held.get(k, 0) for k in classes}

    def box(klass, drawn: int) -> tuple[Fraction, Fraction]:
        return class_box(weights[klass], counts[klass], drawn, factor, holdable[klass])

    room0 = tuple(retained.free_slots(data, side) for side in SIDES)
    index: dict[tuple, int] = {}
    nodes: list[list[dict[object, Fraction]]] = []

    ends: dict[tuple, CompressedState] = {}

    def end(drawn_mods: tuple, drawn_junk: tuple) -> CompressedState:
        found = ends.get((drawn_mods, drawn_junk))
        if found is not None:
            return found
        built = retained
        for mod in drawn_mods:
            built = built.add_mod(data, ExplicitMod(mod.id, _low_values(mod)))
        for klass, d in zip(classes, drawn_junk):
            for _, mod, _ in junk[klass][:d]:
                built = built.add_mod(data, ExplicitMod(mod.id, _low_values(mod)))
        found = ends[(drawn_mods, drawn_junk)] = ab.compress(built)
        return found

    def visit(room: tuple, drawn_mods: tuple, drawn_junk: tuple) -> object:
        state = (room, drawn_mods, drawn_junk)
        found = index.get(state)
        if found is not None:
            return found
        taken = {family for mod in drawn_mods for family in mod.families}
        open_relevant = [
            (side, family, mods) for side, family, mods in relevant if room[SIDES.index(side)] > 0 and family not in taken
        ]
        open_classes = [
            (i, klass) for i, klass in enumerate(classes)
            if room[SIDES.index(klass[0])] > 0 and drawn_junk[i] < len(junk[klass])
        ]
        boxes = {i: box(klass, drawn_junk[i]) for i, klass in open_classes}
        fixed = sum((w for _, _, mods in open_relevant for _, w in mods), Fraction(0))
        done = len(drawn_mods) + sum(drawn_junk) >= draws
        if done or (fixed == 0 and all(hi == 0 for _, hi in boxes.values())):
            return end(drawn_mods, drawn_junk)
        at = index[state] = len(nodes)
        nodes.append([])
        corners = product(*[sorted({lo, hi}) for lo, hi in (boxes[i] for i, _ in open_classes)])
        seen: set = set()
        kernels: list[dict[object, Fraction]] = []
        for corner in corners:
            mass = fixed + sum(corner, Fraction(0))
            if mass == 0:
                continue
            kernel: dict[object, Fraction] = {}
            for side, _family, mods in open_relevant:
                after = _less(room, side)
                for mod, w in mods:
                    target = visit(after, tuple(sorted((*drawn_mods, mod), key=lambda m: m.id)), drawn_junk)
                    kernel[target] = kernel.get(target, Fraction(0)) + w / mass
            for (i, klass), u in zip(open_classes, corner):
                if u:
                    grown = tuple(d + (j == i) for j, d in enumerate(drawn_junk))
                    target = visit(_less(room, klass[0]), drawn_mods, grown)
                    kernel[target] = kernel.get(target, Fraction(0)) + u / mass
            signature = tuple(sorted(((repr(t), c) for t, c in kernel.items())))
            if signature not in seen:
                seen.add(signature)
                kernels.append(kernel)
        nodes[at] = kernels
        return at

    first = visit(room0, (), tuple(0 for _ in classes))
    if not isinstance(first, int):  # nothing is drawn: one certain end
        return RelaxedDraw([[{first: Fraction(1)}]])
    return RelaxedDraw(nodes)


def class_box(
    weights: list[Fraction], held: int, drawn: int, factor: Fraction, holdable: list[Fraction] | None = None
) -> tuple[Fraction, Fraction]:
    """The least and the greatest weight a class has left (the module text): `weights` its families' weights as the pool has them before the
    unknown boost, sorted; `holdable` (sorted; `weights` when None) those of the families a member may hold unknown (the pure junk types),
    `held` how many of those the item held before the reroll, `drawn` how many of the class the reroll has drawn, `factor` the weight factor."""
    holdable = weights if holdable is None else holdable
    lows, highs = _prefix(weights), _prefix(weights[::-1])
    size, total, g = len(weights), lows[-1], factor - 1
    left, rest = total - highs[min(drawn, size)], total - lows[min(drawn, size)]
    lows, highs, size = _prefix(holdable), _prefix(holdable[::-1]), len(holdable)
    fewest, most = min(max(0, held - drawn), size), min(held, size)
    if g >= 0:
        lo, hi = left + g * lows[fewest], rest + g * highs[most]
    else:
        lo, hi = left + g * highs[most], rest + g * lows[fewest]
    return max(lo, Fraction(0)), max(hi, Fraction(0))


def _less(room: tuple, side: Side) -> tuple:
    i = SIDES.index(side)
    return tuple(r - (j == i) for j, r in enumerate(room))


def _prefix(values: list[Fraction]) -> list[Fraction]:
    found = [Fraction(0)]
    for value in values:
        found.append(found[-1] + value)
    return found
