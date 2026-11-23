"""A lower bound that counts every missing mod (C2, H21 of board #1434, #1496, OR-39, OR-40, OR-55).

The offers' floors (`_offer_floor`) give every state outside E one figure, rho: the cheapest way into E from the start's shape. A plan that
needs three mods pays for three, and rho counts one. This module solves, once per round and from that round's own `OfferFloors`, a small
abstract problem whose states remember which wanted mods are on the item and how much room is left, and whose value at each state is a lower
bound of the least expected cost to the goal (V*) of every item it stands for. On R10 its value at the start was the plan's own cost to 4.5e-8
(the hand test of #1471, comment 7105336504), where rho and the pattern bound's growth stopped at 3.23 c.

**Entry.** `missing_mods_table(floors, stop, say)` gives a `MissingModsTable`: its `lower(state)` is the bound at one concrete state (0 for a
state it does not model), `start` its value at the floors' start, and `off` the reason the table is not used (then `lower` is 0 everywhere and
today's floors stand). It is read per state only (`CraftingProblem._at`, `candidates`, `tighten`); a class of states is never given the max of
its members' values, which would be no bound (a class holds states the table calls OFF, whose bound is 0).

THE STATE
---------
phi(s) = (sigma, A, fp, fs, kp, ks) for an item s whose flags and fractured mods are a shape sigma the floors know (`OfferFloors.views`), that
holds no imprint, no Memory Strands and no lock (Prefixes / Suffixes Cannot Be Changed: `Abstraction._holds_lock`); A is the set of the leaves
of U' that are PASSING at s (U' = every necessary leaf of the goal open at the start, `_offer_kinds.necessary_leaves`); fp and fs the free prefix
and suffix slots (the shape's capacity less every explicit mod held: fractured, crafted, ordinary, the veiled placeholder); kp and ks the crafted
mods held on each side. Every other item is OFF: phi(s) = OFF, h(OFF) = 0. A goal state has A = U', where h = 0. The table is refused (`off`)
when the abstraction keeps no junk slots (the room is then not in the state), when the start is OFF or an unopened listing, and when U' has more
than `MAX_OPEN` leaves (the states are 2^|U'| per room).

THE THEOREM
-----------
Let h be bounded, h(OFF) = 0, h = 0 when A = U', and suppose that for every item s with phi(s) != OFF and every offer a of the round that
applies to s,

    (*)   h(phi(s)) <= c(a) + E[ h(phi(s')) ]        (s' the item after one use of a).

Then h(phi(s)) <= V*(s) for every item s (V* over every offer of the round). Proof: fix a policy reaching the goal a.s.; stop at the first goal
or OFF item, tau; M_t = h(phi(s_{t ^ tau})) + the costs paid before t ^ tau is a submartingale by (*), so h(phi(s)) <= E M_t <= E h(phi(s_{t ^ tau}))
+ V^pi(s), and the first term goes to E h(phi(s_tau)) = 0 (bounded convergence). Q*(s, a) >= V*(s) for any offer, so h(phi(s)) is a lower
bound of every offer's figure at s too.

How (*) is met: for each offer a and each abstract state x, a number L_a(x, h) <= E[h(phi(s'))] for EVERY item s with phi(s) = x at which a
applies (the laws below), and (T h)(x) = min_a [c(a) + L_a(x, h)]. The table is iterated from h = 0 as h <- closure(T h), the closure being the
least over the subsets of A at the same room (so h never grows when A grows: h is antitone in A, which "a lost leaf is ignored" needs below:
A(s') within A u G gives h(phi(s')) >= h(.., A u G, ..)). Since some laws (the best-first levels of the rerolls) are not monotone in h, the
iteration proves nothing by itself: **the check** does. After it ends, h is scaled down by `SHRINK` and the check h <= T h is made over every
state and every offer of the catalogue with no tolerance; when it fails the table is OFF. That check, with the laws, is (*).

THE LAWS (one row per kind of offer; `_Build`)
----------------------------------------------
* **Erasing reroll** (REROLL / MOVE that fractures nothing, keeps no crafted mod and needs none: Chaos, Alteration, essences, fossil sets,
  Harvest reforges of a type, Scouring). Its result depends on the shape alone (it keeps the fractured mods, and a locked side's mods, and no
  in-model state holds a lock), so its exact law is the kernel at the shape's bare item: L = sum P(x') h(x'), an OFF outcome at 0. It is
  computed lazily, best first: level 0 is L >= 0; level 1 (a reroll that keeps the shape) is G(empty) - min(chain, Moebius) with
  G(B) = the least h over the shape's rooms at B, u_l >= P(leaf l PASSING after) (`reach_bound`, `declared_bounds`): every outcome's A' lies within
  the support W of u, red(A') = G(empty) - G(A') = sum over B within A' of mu(B) (its Moebius transform), so E red <= sum mu+(B) min_{l in B} u_l,
  and E red <= sum u_l Delta_l along a chain; an outcome holds no crafted mod, so it is in the model at a room of its shape. Level 2 is the exact
  law. The least of the rerolls is popped from a heap and raised until the least is exact, so the least over all of them is exact.
* **One drawn mod** (ADD, MOVE_ADD: Exalted, Augmentation, Regal, Eldritch Exalted, Harvest add, the Beastcraft side swap). It keeps every mod
  (or removes one, below) and adds one drawn mod; A(s') within A u G, G the leaves the one mod passes. The chances that the mod passes leaf l
  (Q_l), some open leaf (P1), two open leaves (P2) are bounded by their largest value over every item with phi = x: the pool of the bare item less
  the families of A's leaves (one family and one side each, disjoint from the other leaves of A), the state's own free slots by side, the families
  the held mods take out (a held mod takes every family it has out of the pool, `Item.blocks`; so on side T at most sum over sides S of
  m(S, T) x (mods held on S), m(S, T) the most families of side T one mod the item model admits on side S holds, #1489), over which families
  those are (`_scenario_chance`, exact over every family set of each count) and every set of tags a metamod blocks. A class that declares its draw
  (`AddedDraw` without `together`) draws on one open side: each side alone. Then E h >= h(A, r') - [P2' d_all + the greedy fill of P1 - P2' over
  the d_l, largest first], d_l = h(A, r') - h(A u l, r'), d_all = h(A, r') - min_G h(A u G, r'), P2' = min(P2, P1): a linear bound whose
  maximum over the chances is at those corners since d_all >= every d_l. The room after the use is not known exactly (which side the mod
  lands on, whether a mod was removed and whether it was crafted): every landing it may have is listed and the least h over them is taken.
* **Side swap's removal** (BeastSideSwap): one held mod of its remove side is removed, each with chance 1/n (n the mods held there). A wanted mod
  of a sure leaf (below) removed loses its leaf; the junk keeps A. The swap is refused without room on its add side or a mod on its remove side.
* **Bench craft** (CRAFT naming its mods): puts the named mod on in one free slot of its side, keeps every mod: A u (the leaves it finishes,
  `finishes`), the side's free slot less one, one more crafted mod when the mod is crafted (refused past `KMAX` crafted mods or with no slot).
  A lock craft leads OFF: its law is L = 0 (a CUT).
* **Remove Crafted Mods**: removes every crafted mod: (fp + kp, fs + ks, 0, 0), A kept (a lost leaf ignored); refused with none held.
* **Orb of Annulment**: removes one removable mod (not fractured, not protected by a held tag metamod), each with chance 1/n (`annul.py`). Without
  a crafted mod held, and no tag metamod fractured in the shape, every held mod is removable; otherwise a metamod may protect some junk: the
  least over every number of protected junk per side. A wanted mod of a sure leaf removed loses its leaf. When a leaf of A is not sure, only the landings are used
  (one slot of either side back, A kept).
* **Any other craft that names no mod** (ReAnoint, an enchant): it adds no explicit mod and may only remove some: the least h over every room
  with at least as many free slots and at most as many crafted mods on each side, A kept.
* **Veiled choice** (VEILED: Unveil, Pick): the placeholder becomes a mod, not crafted (`veiled.mod_is_a_plain_affix_not_crafted`): A u gain at
  the same room; without a gain no constraint (L = h(x) >= h(x) - c).
* **Veil** (Veiled Exalted Orb): removes one held mod (crafted or not) and puts the placeholder on either side with room: the least h over those
  landings and the ones with nothing removed, A kept.
* **Implicit change** (Ember, Ichor, Orb of Conflict, Blessed): no explicit mod changes: phi(s') = phi(s), no constraint.
* **Harvest resistance / damage swap** when no leaf of U' has such a stat: one mod changes its element, the count and the crafted flag kept,
  no leaf of U' can pass by it: A(s') within A at the same room, no constraint. Otherwise a CUT.
* **Restart** (buy the start again): c + h(phi(start)).
* **Harvest likelihood reforge** (TERMINAL to the floors): it removes every mod but the fractured ones (no in-model state holds a lock) and
  draws the item full again, the held families' weights times 10 or 1/10. Every outcome holds no crafted mod and keeps the shape (checked:
  `keeps_shape`, `Adds.keeps_crafted`, `Adds.fractures`; otherwise a CUT; a shape that is not rare refuses it), so it is in the model at a room
  of its shape, and P(leaf l PASSING after) <= u_l = `likelihood_bound` (#1471 part 1 per leaf; checker of 2026-11-23: sound as used on R10,
  hardened here by counting up to m(S, T) families per drawn mod, `Holdable.most`): level 1 of the erasing rerolls, L = G(empty) - min(chain,
  Moebius).
* **Refused by its shape**: an offer whose `outcomes` raise NotApplicableError at the shape's bare item while reading none of the item's
  fields that differ between the in-model states of the shape (`refused_by_shape`: the mods, implicits, quality, veiled offer, enchantment and
  sockets are handed in as poisons that raise `_Read` at any read) has read only what every in-model state of the shape shares: the base and
  the item level (the craft's, held by no state), the rarity, corruption, influences and the unopened flag (the shape's `Flags`), no imprint
  and no Memory Strand (phi is OFF on either). The game's answer is a function of those alone, so it refuses the offer at every in-model state
  of the shape: the offer is not available there and puts no term in the min of T (the floors' premise (1), as for a REFUSED entry; the
  imprint law of H25 is the same argument). A refusal that reads a mod (a side swap with no mod to remove, an Exalted Orb on a full side, the
  dominance of an Eldritch implicit) proves nothing for the states that hold others: the offer keeps its law or its CUT. So on R10 the
  Eldritch Exalted Orb (3.31 c) and the Beastcraft side swaps (5 c) leave the Magic shape the Orb of Scouring leads to (#1496: they held the
  787-offer round's table at 0.3463 + 3.31 = 3.6563 c).
* **Every other offer** (Fracturing Orb, an imprint, corruptions, the Eldritch Chaos Orb and Annulment, value rerolls, any other TERMINAL, a
  reroll that fractures or keeps crafted mods): a CUT, L = 0 (h >= 0). So the table can never exceed the price of the cheapest offer it holds
  no law for (its ceiling: 41.82 c on R10, the Eldritch Chaos Orb; comment 7106498087 on #1434).

A **sure leaf** is one whose passing mods are of one family tuple on one side, disjoint from every other leaf's, none with an Attack or Caster
tag (a tag metamod could protect it from an Annulment), all in the data: the item holds at most one mod of that family, so removing it loses
the leaf. Its mod's crafted flag is known (True or False) or not (a leaf with crafted and natural mods: both landings are taken).

What is taken on contract and not checked: the floors' premises (1) to (7) of `_offer_kinds`, `metamods.kept_by_reroll` (a reroll that reads
no junk keeps only the fractured mods and a locked side's), that a bench craft fills one slot, the Annulment and the veil remove one mod, that
only a lock craft makes a lock and only an imprint an imprint, and that no offer adds Memory Strands.
"""

import copy
import heapq
import itertools
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction

from crafting_system.abstraction import Abstraction, CompressedState, Status, declared_bounds, keeps_shape, reach_bound
from crafting_system.abstraction._bound import Holdable, _blocked_sets, _guard, _may_pass, _scenario_chance, _Side, holdable
from crafting_system.actions import NotApplicableError, OutOfScopeError, allowed_by_tags, unveil_pool_mods
from crafting_system.actions.beast_mods import BeastSideSwap
from crafting_system.actions.harvest_likelihood import HarvestReforgeLikelihood
from crafting_system.actions.pool import build_pool
from crafting_system.items.model import Metamod, Rarity, Side, capacity

from . import _offer_kinds as kinds
from crafting_system import budget

from ._offer_floor import FloorsStopped, OfferFloors
from ._offers import BuyStartItem

ZERO, ONE = Fraction(0), Fraction(1)
KMAX = 3  # the crafted mods an item can hold (with the multimod)
MAX_OPEN = 6  # the most open leaves the table is built for: 2^|U'| sets per room
LOCKS = frozenset({Metamod.PREFIXES_CANNOT_CHANGE.value, Metamod.SUFFIXES_CANNOT_CHANGE.value})
TAG_METAMODS = frozenset({Metamod.NO_ATTACK_MODS.value, Metamod.NO_CASTER_MODS.value})  # an Annulment does not remove the mods they protect
SWAPS = {"HarvestResistanceSwap": "resist", "HarvestDamageSwap": "damage"}  # one mod's element changes, the count kept (see THE LAWS)
SHRINK = (1e-9, 1e-6)  # h is scaled down by 1 - this before the check (the float sums of T carry rounding); the second when the first fails
ITERATIONS = 3000  # the iteration's cap (R10 needed 653); the check decides either way: a stopped iteration is a weaker table, never an unsound one
ASK_STATES = 256  # the net is asked once every this many states of a pass of T
TABLE_SHARE = 0.5  # the table's own time share: this part of the round's seconds (`_pattern_bound`, OR-40); the build's net stands above it
CONVERGED = 1e-10  # relative change of the start's value under which the iteration ends
P_, S_ = Side.PREFIX, Side.SUFFIX


class _Read(BaseException):
    """A field of the probe item that differs between the states of a shape was read (`refused_by_shape`); a BaseException, so that no
    `except Exception` of an action turns the read into a refusal."""


def _poisoned(*_args, **_kwargs):
    raise _Read


class _PoisonTuple(tuple):
    """A tuple field of the probe item: any read of it raises `_Read`."""

    __iter__ = __len__ = __getitem__ = __contains__ = __bool__ = __hash__ = __eq__ = __ne__ = __add__ = __radd__ = __reversed__ = _poisoned
    __lt__ = __le__ = __gt__ = __ge__ = __mul__ = __rmul__ = count = index = __reduce__ = __reduce_ex__ = __repr__ = _poisoned


class _PoisonValue:
    """An optional field of the probe item (a quality, an enchantment, sockets): any read of it raises `_Read`."""

    __getattr__ = __bool__ = __hash__ = __eq__ = __ne__ = __iter__ = __len__ = __lt__ = __le__ = __gt__ = __ge__ = _poisoned
    __getitem__ = __contains__ = __str__ = __repr__ = __int__ = __index__ = __reduce__ = __reduce_ex__ = _poisoned


VARYING = ("mods", "implicits", "quality", "veil_offer", "enchantment", "sockets")  # the item's fields two in-model states of a shape may differ in


def refused_by_shape(data, item, action) -> bool:
    """Whether `action` is refused at every in-model state of the shape of `item` (THE LAWS, "Refused by its shape"): its `outcomes` raise
    NotApplicableError at the shape's bare item (no imprint, no Memory Strand) with every field of `VARYING` poisoned, in two probes: the
    optional fields as poisons and as the bare item's own values (so a test `is None` read by identity, which no poison sees, gives the
    refusal both ways or the probe fails). False on any read of a poisoned field, on any other error, and when the outcomes are given."""
    bare = item.changed(data, mods=tuple(entry for entry in item.mods if entry.fractured), imprints=(), memory_strands=0)
    for optional in (True, False):
        probe = copy.copy(bare)
        for name in VARYING:
            value = getattr(bare, name)
            if isinstance(value, tuple):
                object.__setattr__(probe, name, _PoisonTuple(value))
            elif optional or value is not None:
                object.__setattr__(probe, name, _PoisonValue())
        try:
            action.outcomes(data, probe)
        except NotApplicableError:
            continue
        except _Read:
            return False
        except Exception:  # noqa: BLE001  (any other answer proves nothing)
            return False
        return False
    return True


class _Off(Exception):
    """The table is not used: the reason."""


@dataclass(frozen=True, eq=False)
class MissingModsTable:
    """The solved table of one round (see the module text). `off` is None when it is used."""

    off: str | None
    start: float = 0.0  # h at the floors' start (0 when off)
    seconds: float = 0.0  # what the build took
    states: int = 0  # the abstract states
    reader: "_Reader | None" = field(default=None, repr=False)

    def lower(self, state: CompressedState) -> float:
        """A lower bound of V*(state) over the round's offers: h(phi(state)), 0 when the table is off or the state is OFF."""
        if self.reader is None:
            return 0.0
        return self.reader.value(state)

    def serves(self, offers) -> bool:
        """Whether `offers` are the very offers the table was built from (the search's and the floors' priced list)."""
        return self.reader is not None and len(offers) == len(self.reader.offers) and all(a is b for a, b in zip(offers, self.reader.offers))


@dataclass(eq=False)
class _Reader:
    """What `lower` needs: phi and the values."""

    ab: Abstraction
    known: Mapping[tuple, int]
    bits: tuple[tuple[int, int], ...]  # (leaf, bit) of U'
    full: int
    side_free: tuple[dict, ...]
    lockmods: frozenset[str]
    h: dict
    offers: tuple

    def phi(self, state: CompressedState) -> tuple | None:
        """(shape, A, fp, fs, kp, ks), or None for an OFF state (unknown shape, an imprint, Memory Strands, a lock, a room out of range)."""
        shape = self.known.get((state.flags, state.fractured))
        if shape is None or state.imprints or state.strands or any(slot.crafted and slot.kind in self.lockmods for slot in state.slots) or self.ab._holds_lock(state):
            return None
        held = 0
        for leaf, bit in self.bits:
            if state.status[leaf] is Status.PASSING:
                held |= bit
        free = self.side_free[shape]
        fp = free[P_] - sum(1 for slot in state.slots if slot.side is P_)
        fs = free[S_] - sum(1 for slot in state.slots if slot.side is S_)
        kp = sum(1 for slot in state.slots if slot.crafted and slot.side is P_)
        ks = sum(1 for slot in state.slots if slot.crafted and slot.side is S_)
        if not (0 <= fp <= free[P_] and 0 <= fs <= free[S_]) or kp + ks > KMAX:
            return None
        return (shape, held, fp, fs, kp, ks)

    def value(self, state: CompressedState) -> float:
        try:
            x = self.phi(state)
        except Exception:  # noqa: BLE001  (a state phi cannot read is OFF: 0 is a bound of anything)
            return 0.0
        if x is None or x[1] == self.full:
            return 0.0
        v = self.h.get(x, 0.0)
        return v if math.isfinite(v) else 0.0


def missing_mods_table(
    floors: OfferFloors, stop: Callable[[], str | None] | None = None, say: Callable[[str], None] | None = None, seconds: float | None = None
) -> MissingModsTable:
    """The table of the round whose floors are `floors`, built under the net `stop` (the build's clock and memory) and a time share of its own,
    `seconds` (OR-39, OR-40: `TABLE_SHARE` of the round's seconds, `_pattern_bound`); both are asked at every iteration, every `ASK_STATES`
    states of a pass and inside the making of every kernel (`budget.asking`, also in a run counted in pieces: the table is no piece of the
    count, so the floors' rule of asking no clock there does not apply to it). A run counted in states has no round seconds (`seconds` None): its
    table's work is then capped by count alone, the same on every machine: at most `ITERATIONS` passes of T and the check's, each over the
    states (at most 2^`MAX_OPEN` sets per room) and the round's offers, and one exact kernel per erasing offer; memory stays asked. It is `off`, with its reason, whenever it cannot be built, a net
    is reached, the check h <= T h fails, or anything in it raises: a table that is off is today's floors, never a crash of the round."""
    said = say or (lambda _text: None)
    began = time.perf_counter()

    def net() -> str | None:
        if stop is not None and (reason := stop()) is not None:
            return reason
        if seconds is not None and time.perf_counter() - began >= seconds:
            return f"the table's own share of {seconds:.0f} seconds was used"
        return None

    def off(reason: str) -> MissingModsTable:
        said(f"missing mods' table: off ({reason})")
        return MissingModsTable(reason, seconds=time.perf_counter() - began)

    try:
        build = _Build(floors, net)
        with budget.asking(net):
            build.prepare()
            build.solve()
            shrink = build.check()
    except _Off as why:
        return off(str(why))
    except FloorsStopped as reached:
        return off(f"the net was reached: {reached.reason}")
    except budget.NetReached as reached:
        return off(f"the net was reached: {reached.reason}")
    except Exception as error:  # noqa: BLE001  (a fault in the table turns it off; the round goes on with its floors)
        return off(f"{type(error).__name__}: {error}")
    seconds = time.perf_counter() - began
    reader = _Reader(
        floors.ab, build.known, tuple((leaf, build.bit[leaf]) for leaf in build.U), build.full, tuple(build.side_free), build.lockmods, build.h,
        tuple(entry.priced for entry in floors.entries),
    )  # fmt: skip
    start = build.H(*build.xstart)
    said(
        f"missing mods' table: h(start) {start!r} at {build.xstart}, {len(build.states):,} states, {build.iterations} iterations, "
        f"{build.raised:,} rerolls raised, {build.by_shape:,} offers refused by their shape, checked at a shrink of {shrink:g} ({seconds:.1f} s)"
    )
    return MissingModsTable(None, start, seconds, len(build.states), reader)


def likelihood_bound(ab: Abstraction, action: HarvestReforgeLikelihood, item, leaves, held: Mapping[Side, Holdable]) -> dict[int, Fraction]:
    """u_l >= P(leaf l PASSING after one use of the likelihood reforge `action`) at every item of the shape of `item` (#1471 part 1, the
    lemma's P1, per leaf; checker of 2026-11-23 on th21c: SOUND as used on R10, with the hardening below).

    The reforge removes every mod but the fractured ones (no in-model state holds a lock, so no side is kept) and draws the item full again
    from the pool of the bare item, the weight of every mod of a family the item held multiplied by f (10 or 1/10). For a family g with a mod
    passing the leaf: the share of the passing mods inside g is at most `share` (its passing weight over its kept weight, times f against 1/f
    when g's mods are not all of g alone, over every set of blocked tags), and the chance that g is drawn in some slot of its side is at most
    1 - (1 - s1)(1 - s2)^(k - 1): s = F / (F + O), F the whole weight of g at its most (times f when held), O the weight of the other
    families of its side less the most that the other drawn mods can take out (each removes every family it holds: on side T the k_T - 1
    others and the k_other mods of the other side take at most (k_T - 1) m(T, T) + k_other m(other, T) families, `Holdable.most` (#1489),
    the heaviest ones), at its least (times 1/f when f < 1); s1 for the first draw (a kept Attack/Caster metamod filters it: the filtered
    weight), s2 for the others. A union bound over g gives u_l, at most 1."""
    data = ab.data
    f = action.held_weight_factor()
    hi, lo = (f, ONE) if f > 1 else (ONE, f)
    bare = item.changed(data, mods=tuple(entry for entry in item.mods if entry.fractured))
    cap = capacity(data, bare.base_id, bare.rarity)
    fractured = {P_: len(bare.prefixes(data)), S_: len(bare.suffixes(data))}
    k = {side: cap.of(side) - fractured[side] for side in (P_, S_)}
    pool = build_pool(data, bare, tag_filter=False)
    out = {}
    for leaf in leaves:
        wanted = ab.goal.leaves[leaf]
        ok = wanted.tier_ok if wanted.tier_ok is not None else wanted.mod_ids
        total = ZERO
        for g in pool:
            if not any(m.mod.id in ok for m in g.mods) or k[g.side] <= 0:
                continue
            uniform = all(set(m.mod.families) == {g.family} for m in g.mods)
            share = ZERO
            for blocked in ((), ("attack",), ("caster",), ("attack", "caster")):
                keep = [m for m in g.mods if not (set(m.mod.implicit_tags or ()) & set(blocked))]
                wl = sum((m.weight for m in keep if m.mod.id in ok), ZERO)
                wg = sum((m.weight for m in keep), ZERO)
                if wl == 0:
                    continue
                share = max(share, wl / wg if uniform else (wl * hi) / (wl * hi + (wg - wl) * min(lo, ONE)))
            F = sum((m.weight for m in g.mods), ZERO) * (hi if uniform else max(hi, ONE))
            other = S_ if g.side is P_ else P_
            others = [m for h in pool if h.side == g.side for m in h.mods if g.family not in m.mod.families]
            names = frozenset(name for m in others for name in m.mod.families)
            removable = (k[g.side] - 1) * held[g.side].most(names) + k[other] * held[other].most(names)

            def rest(mods):
                weights: dict = {}
                for m in mods:
                    for name in m.mod.families:
                        weights[name] = weights.get(name, ZERO) + m.weight
                top = sum(sorted(weights.values(), reverse=True)[:removable], ZERO)
                return max(sum((m.weight for m in mods), ZERO) - top, ZERO) * lo

            O2 = rest(others)
            O1 = rest([m for m in others if not (set(m.mod.implicit_tags or ()) & {"attack", "caster"})]) if ab.models_metamods else O2
            s1, s2 = F / (F + O1), F / (F + O2)
            total += share * (1 - (1 - s1) * (1 - s2) ** (k[g.side] - 1))
        out[leaf] = min(total, ONE)
    return out


class _Build:
    """The table's catalogue, laws and iteration (see the module text, THE LAWS)."""

    def __init__(self, floors: OfferFloors, stop: Callable[[], str | None] | None) -> None:
        self.floors, self.stop = floors, stop
        ab = self.ab = floors.ab
        data = self.data = ab.data
        goal = ab.goal
        start = floors.start
        if not floors.chosen:
            raise _Off("no open leaf: the floors have no set U")
        if start.flags.unopened:
            raise _Off("the start is an unopened listing")
        if not ab.keeps_junk:
            raise _Off("the abstraction keeps no junk slots: the room is not in the state")
        self.U = [leaf for leaf in kinds.necessary_leaves(goal) if start.status[leaf] is not Status.PASSING]
        if not self.U:
            raise _Off("no necessary leaf is open at the start")
        if len(self.U) > MAX_OPEN:
            raise _Off(f"{len(self.U)} open leaves, more than {MAX_OPEN}")
        self.full = (1 << len(self.U)) - 1
        self.bit = {leaf: 1 << j for j, leaf in enumerate(self.U)}
        self.views = floors.views
        self.S = len(self.views)
        self.known = self.views[0].known
        self.side_free = []
        for view in self.views:
            cap = capacity(data, view.item.base_id, view.item.rarity)
            bare = view.item.changed(data, mods=tuple(entry for entry in view.item.mods if entry.fractured))
            self.side_free.append({P_: cap.prefix - len(bare.prefixes(data)), S_: cap.suffix - len(bare.suffixes(data))})
        self.lockmods = frozenset(mid for mid, mod in data.mods.items() if set(mod.families) & LOCKS)
        self.tagged_fracture = [
            any(entry.fractured and set(data.mods[entry.mod_id].families) & TAG_METAMODS for entry in view.item.mods if entry.mod_id in data.mods)
            for view in self.views
        ]  # fmt: skip
        self.admitted = holdable(data, floors.item.base_id)  # m(S, T) of the draws (#1489, `abstraction._bound.holdable`)
        self.info = {}
        for leaf in self.U:
            wanted = goal.leaves[leaf]
            ok = frozenset(wanted.tier_ok if wanted.tier_ok is not None else wanted.mod_ids)
            mods = [data.mods[m] for m in ok if m in data.mods]
            self.info[leaf] = dict(
                ok=ok, sides={mod.generation_type for mod in mods}, fams={tuple(sorted(mod.families)) for mod in mods},
                domains={mod.domain for mod in mods}, all_known=len(mods) == len(ok),
            )  # fmt: skip
        self.sure = {leaf: self._sure(leaf) for leaf in self.U}
        self.reader = _Reader(ab, self.known, tuple((leaf, self.bit[leaf]) for leaf in self.U), self.full, tuple(self.side_free), self.lockmods, {}, ())
        self.xstart = self.reader.phi(start)
        if self.xstart is None:
            raise _Off("the start is OFF (an unknown shape, an imprint, Memory Strands or a lock)")
        self.rk = [
            [(fp, fs, kp, ks) for fp in range(self.side_free[s][P_] + 1) for fs in range(self.side_free[s][S_] + 1)
             for kp in range(self.side_free[s][P_] - fp + 1) for ks in range(self.side_free[s][S_] - fs + 1) if kp + ks <= KMAX]
            for s in range(self.S)
        ]  # fmt: skip
        self.states = [(s, A, *room) for s in range(self.S) for A in range(self.full + 1) for room in self.rk[s]]
        self.h = {x: 0.0 for x in self.states}
        self.raised = 0
        self.iterations = 0
        self._likely: dict = {}

    def ask(self) -> None:
        if self.stop is not None and (reason := self.stop()) is not None:
            raise FloorsStopped(reason)

    def _sure(self, leaf: int):
        """(side, crafted True / False / None for both) of a sure leaf (see the module text), else None."""
        info = self.info[leaf]
        disjoint = all(not (info["ok"] & self.info[other]["ok"]) for other in self.U if other != leaf)
        tagged = any(set(self.data.mods[m].implicit_tags or ()) & {"attack", "caster"} for m in info["ok"] if m in self.data.mods)
        if len(info["sides"]) != 1 or len(info["fams"]) != 1 or not disjoint or tagged or not info["all_known"]:
            return None
        if next(iter(info["sides"])) not in (P_.value, S_.value):
            return None
        side = Side(next(iter(info["sides"])))
        domains = info["domains"]
        return side, (True if domains == {"crafted"} else False if "crafted" not in domains else None)

    def H(self, s, A, fp, fs, kp=0, ks=0) -> float:
        if A == self.full:
            return 0.0
        return self.h.get((s, A, fp, fs, kp, ks), math.inf)

    def held(self, s, fp, fs) -> dict:
        return {P_: self.side_free[s][P_] - fp, S_: self.side_free[s][S_] - fs}

    def Hmin(self, s, A, opts) -> float:
        """The least h over the rooms a use may land in (which one is not known)."""
        return min((self.H(s, A, *o) for o in opts), default=math.inf)

    def valid(self, t, room) -> bool:
        free = self.side_free[t]
        fp, fs, kp, ks = room
        return 0 <= fp <= free[P_] and 0 <= fs <= free[S_] and 0 <= kp <= free[P_] - fp and 0 <= ks <= free[S_] - fs and kp + ks <= KMAX

    # ---- the catalogue -------------------------------------------------------------------------------------------------------

    def prepare(self) -> None:
        data = self.data
        self.erasing, self.draws, self.crafts, self.cuts, self.bounded = [], [], [], [], []
        self.restart = None
        self.by_shape = 0
        for s, entries in enumerate(self.floors.shape_entries):
            view = self.views[s]
            for entry in entries:
                action = entry.priced.offer.action
                name = type(action).__name__
                cost = float(entry.cost)
                if entry.kind == kinds.REFUSED:
                    continue  # refused at every state of the shape (the floors' premise (1); a restore with no imprint)
                if entry.kind != kinds.RESTART_KIND and refused_by_shape(data, view.item, action):
                    self.by_shape += 1
                    continue  # refused at every in-model state of the shape (THE LAWS, "Refused by its shape")
                if entry.kind == kinds.RESTART_KIND:
                    if isinstance(action, BuyStartItem):
                        self.restart = cost if self.restart is None else min(self.restart, cost)
                    else:
                        self.cuts.append((s, cost))
                    continue
                if name in SWAPS and not self._swap_hits(SWAPS[name]):
                    continue  # no constraint (THE LAWS)
                if entry.kind in (kinds.REROLL, kinds.MOVE):
                    adds = action.adds(data, view.item)
                    if adds.fractures or adds.keeps_crafted or action.reads(data).needs_crafted:
                        self.cuts.append((s, cost))
                    else:
                        self.erasing.append(dict(e=entry, s=s, cost=cost, level=0, u=None, law=None))
                elif entry.kind in (kinds.ADD, kinds.MOVE_ADD):
                    self.draws.append(dict(e=entry, s=s, cost=cost))
                elif entry.kind in (kinds.CRAFT, kinds.VEILED, kinds.VEIL):
                    self.crafts.append(dict(e=entry, s=s, cost=cost))
                elif entry.kind == kinds.IMPLICIT:
                    continue  # no constraint
                elif entry.kind == kinds.TERMINAL and isinstance(action, HarvestReforgeLikelihood):
                    self._likelihood(entry, s, cost)
                else:
                    self.cuts.append((s, cost))
            self.ask()
        self._prepare_crafts()
        self._prepare_draws()
        self.ask()
        self._declared_level1()

    def _likelihood(self, entry, s: int, cost: float) -> None:
        """A Harvest likelihood reforge (THE LAWS): bounded like an erasing reroll at level 1, u from `likelihood_bound`; a CUT when its use may
        keep a crafted mod, fracture one or change the shape; nothing on a shape that is not rare (the reforge refuses it)."""
        view = self.views[s]
        if view.item.rarity is not Rarity.RARE:
            return  # refused at every state of the shape
        action = entry.priced.offer.action
        adds = action.adds(self.data, view.item)
        try:
            same = keeps_shape(self.ab, view.bare, action)
        except NotApplicableError:
            return
        except OutOfScopeError:
            same = False
        if adds.fractures or adds.keeps_crafted or not same:
            self.cuts.append((s, cost))
            return
        key = (s, action.held_weight_factor())
        if key not in self._likely:
            self.ask()
            self._likely[key] = likelihood_bound(self.ab, action, view.item, self.U, self.admitted)
        self.bounded.append(dict(s=s, cost=cost, u=self._likely[key]))

    def _swap_hits(self, word: str) -> bool:
        return any(word in stat.id for leaf in self.U for m in self.info[leaf]["ok"] if m in self.data.mods for stat in self.data.mods[m].stats)

    def _prepare_crafts(self) -> None:
        data, goal = self.data, self.ab.goal
        kept = []
        for d in self.crafts:
            entry, s = d["e"], d["s"]
            action = entry.priced.offer.action
            item = self.views[s].item
            adds = action.adds(data, item)
            named = frozenset(adds.named) if adds.named is not None else None
            if entry.kind == kinds.VEIL:
                kept.append({**d, "kind": "veil", "gain": 0})  # it adds the placeholder only (`_kind_of`): no leaf
                continue
            if entry.kind == kinds.VEILED and not named:
                named = unveil_pool_mods(data, item.base_id)
            if named is None:
                self.cuts.append((s, d["cost"]))
                continue
            families = set()
            for m in named:
                if m in data.mods:
                    families |= set(data.mods[m].families)
            if families & LOCKS:
                self.cuts.append((s, d["cost"]))  # a lock craft leads OFF
                continue
            d["sides"] = sorted({Side(data.mods[m].generation_type) for m in named if m in data.mods and data.mods[m].generation_type in (P_.value, S_.value)}, key=lambda x: x.value)
            gain = 0
            for leaf in self.U:
                if kinds.finishes(goal.leaves[leaf], named, bool(adds.crafted)):
                    gain |= self.bit[leaf]
            name = type(action).__name__
            if entry.kind == kinds.VEILED:
                if not gain:
                    continue  # no constraint
                d.update(kind="veiled", gain=gain)
            elif named:
                if not d["sides"]:
                    self.cuts.append((s, d["cost"]))
                    continue
                d.update(kind="craft", gain=gain, crafted=bool(adds.crafted))
            elif name == "RemoveCraftedMods":
                d.update(kind="remove-crafted", gain=0)
            elif name == "AnnulmentOrb":
                d.update(kind="annul", gain=0)
            else:
                d.update(kind="removes", gain=0)
            kept.append(d)
        self.crafts = kept

    # ---- one drawn mod -------------------------------------------------------------------------------------------------------

    def _forced(self, A):
        """The families and the slots the leaves of A hold for sure: a leaf of one side and one family tuple, whose mods are disjoint from the
        other leaves of A, holds a slot there and its families are out of the pool. A leaf of several families (Cold OR Fire resistance) reserves
        nothing: its mod stays among the held mods of the room, which `_sup` counts as taking up to m(S, T) families out (#1496 checker round 1:
        reserving its slot without removing its family left that family in the pool and the mod out of the held count, an unsound sup)."""
        families, slots = set(), {P_: 0, S_: 0}
        leaves = [leaf for leaf in self.U if A & self.bit[leaf]]
        for leaf in leaves:
            info = self.info[leaf]
            if any(info["ok"] & self.info[other]["ok"] for other in leaves if other != leaf):
                continue
            if len(info["sides"]) == 1 and len(info["fams"]) == 1 and next(iter(info["sides"])) in (P_.value, S_.value):
                slots[Side(next(iter(info["sides"])))] += 1
                families |= set(next(iter(info["fams"])))
        return families, slots

    def _sup(self, pool, free, tag, passing, A, fp, fs, single=False) -> Fraction:
        """The largest chance that the one drawn mod is in X (`passing`) over the items of the shape with the leaves of A held, fp and fs free."""
        families, slots = self._forced(A)
        room = {side: max(0, free[side]) - slots[side] for side in Side}
        if room[P_] < 0 or room[S_] < 0 or not (0 <= fp <= room[P_] and 0 <= fs <= room[S_]):
            return ZERO  # no such item
        held = {P_: room[P_] - fp, S_: room[S_] - fs}
        f = {P_: fp, S_: fs}
        opens = [side for side in (P_, S_) if f[side] > 0]
        tag_sets = _blocked_sets() if self.ab.models_metamods else (frozenset(),)
        best = ZERO
        for blocked in tag_sets:
            kept = {side: [] for side in Side}
            names = {side: set() for side in Side}
            for family in pool:
                if family.family in families:
                    continue
                mods = [m for m in family.mods if allowed_by_tags(m.mod, blocked) and (tag is None or tag in m.mod.implicit_tags)]
                weight = sum((m.weight for m in mods), ZERO)
                if weight > 0:
                    kept[family.side].append((weight, sum((m.weight for m in mods if passing.get(m.mod.id)), ZERO)))
                    names[family.side].add(family.family)
            sides = {side: _Side(kept[side]) for side in Side}
            spread = {(src, dst): self.admitted[src].most(frozenset(names[dst])) for src in (P_, S_) for dst in (P_, S_)}
            caps = [min(sum(spread[src, side] * held[src] for src in (P_, S_)), sides[side].count) for side in opens]
            for ks in itertools.product(*(range(cap + 1) for cap in caps)):
                live = [(sides[side], k) for side, k in zip(opens, ks) if k < sides[side].count]
                for one in ([[x] for x in live] if single else [live]):
                    if not one or sum(x.wanted for x, _ in one) == 0:
                        continue
                    best = max(best, _scenario_chance(one))
        return best

    def _sups(self, pool, free, tag, pas, A, fp, fs, single=False):
        opened = [leaf for leaf in self.U if not A & self.bit[leaf]]
        Q = {leaf: self._sup(pool, free, tag, pas[leaf], A, fp, fs, single) for leaf in opened}
        mods = set().union(*(pas[leaf].keys() for leaf in self.U))
        union = {m: any(pas[leaf].get(m) for leaf in opened) for m in mods}
        two = {m: sum(1 for leaf in opened if pas[leaf].get(m)) >= 2 for m in mods}
        P1 = self._sup(pool, free, tag, union, A, fp, fs, single) if any(Q.values()) else ZERO
        P2 = self._sup(pool, free, tag, two, A, fp, fs, single) if any(two.values()) else ZERO
        return Q, P1, P2

    def _prepare_draws(self) -> None:
        ab, data = self.ab, self.data
        kept = []
        for d in self.draws:
            self.ask()
            entry, s = d["e"], d["s"]
            view = self.views[s]
            action = entry.priced.offer.action
            kind, _pbar, _level, dests = kinds._raised(view, action, entry.kind, 0, ONE, 1, frozenset())
            if kind == kinds.REFUSED:
                continue
            if kind not in (kinds.ADD, kinds.MOVE_ADD) or (kind == kinds.MOVE_ADD and len(dests) != 1):
                self.cuts.append((s, d["cost"]))
                continue
            dest = s if kind == kinds.ADD else next(iter(dests))
            declared = action.added_draw(data, view.item)
            single = False
            if declared is not None:
                if kind == kinds.MOVE_ADD:
                    self.cuts.append((s, d["cost"]))
                    continue
                pool, free, tag, influences = declared.pool, dict(self.side_free[s]), declared.tag, view.item.influences
                single = not getattr(declared, "together", False)
            else:
                parts = ab._prepared(view.bare, action).outcomes.components
                if len(parts) != 1:
                    self.cuts.append((s, d["cost"]))
                    continue
                part = parts[0][1]
                pool, free, tag, influences = part.pool, part.free, part.tag, part.retained.influences
            try:
                _guard(pool)
            except OutOfScopeError:
                self.cuts.append((s, d["cost"]))
                continue
            if isinstance(action, BeastSideSwap):
                law = ("swap", action.add_side, action.remove_side)
            elif action.reads(data).variants or declared is not None:
                law = "add"
            else:
                law = "add-maybe-remove"
            memo: dict = {}
            pas = {leaf: _may_pass(ab, pool, leaf, influences, memo) for leaf in self.U}
            sups = {}
            if kind == kinds.MOVE_ADD:  # a Regal Orb: drawn in the room of the shape it lands in, the Magic item's mods held
                there = dict(self.side_free[dest])
                law = "move-add"
                for A in range(self.full):
                    self.ask()
                    for fp, fs, kp, ks in self.rk[s]:
                        if kp or ks:
                            continue
                        moved = (fp + there[P_] - self.side_free[s][P_], fs + there[S_] - self.side_free[s][S_])
                        sups[(A, fp, fs)] = self._sups(pool, there, tag, pas, A, *moved)
            else:
                for A in range(self.full):
                    self.ask()
                    for fp, fs, kp, ks in self.rk[s]:
                        if kp or ks or fp + fs < 1:
                            continue
                        sups[(A, fp, fs)] = self._sups(pool, free, tag, pas, A, fp, fs, single)
            d.update(dest=dest, law=law, sups=sups)
            kept.append(d)
        self.draws = kept

    # ---- erasing rerolls: levels ---------------------------------------------------------------------------------------------

    def _declared_level1(self) -> None:
        """Level 1 of every erasing reroll whose class declares its bound (fossil sets), for a class of 20 offers or more."""
        groups: dict = {}
        for d in self.erasing:
            groups.setdefault((d["s"], type(d["e"].priced.offer.action)), []).append(d)
        for (s, _klass), group in groups.items():
            if len(group) < 20:
                continue
            self.ask()
            actions = [d["e"].priced.offer.action for d in group]
            per = {leaf: declared_bounds(self.ab, self.views[s].bare, actions, (leaf,)) for leaf in self.U}
            for j, d in enumerate(group):
                if all(per[leaf][j] is not None for leaf in self.U):
                    d.update(u={leaf: per[leaf][j] for leaf in self.U}, same=True, level=1)  # a declaration is given only for a class that keeps the shape

    def _raise(self, d) -> None:
        self.ask()
        ab = self.ab
        s, action = d["s"], d["e"].priced.offer.action
        bare = self.views[s].bare
        try:
            if d["level"] == 0:
                d["level"] = 1
                d["same"] = keeps_shape(ab, bare, action)
                d["u"] = {leaf: (ONE if (b := reach_bound(ab, bare, action, (leaf,))) is None else b) for leaf in self.U}
                return
            d["level"] = 2
            law: dict = {}
            for state, p in ab.kernel(bare, action).items():
                x = self.reader.phi(state)
                if x is not None:
                    law[x] = law.get(x, ZERO) + p  # an OFF outcome counts 0
            d["law"] = {x: float(p) for x, p in law.items()}
        except NotApplicableError:
            d["refused"] = True  # refused at the bare item: at every state of the shape (premise (1))
        except OutOfScopeError:
            d["cut"] = True

    def _G(self, s, supp):
        g = [min(self.H(s, A, *room) for room in self.rk[s]) for A in range(self.full + 1)]
        delta = {}
        for leaf in self.U:
            b = self.bit[leaf]
            delta[leaf] = max((g[A] - g[A | b] for A in range(self.full + 1) if not A & b and A & supp == A), default=0.0) if b & supp else 0.0
        mu = {}
        for B in range(1, self.full + 1):
            if B & supp != B:
                continue
            total, C = 0.0, B
            while True:
                total += (-1) ** (bin(B).count("1") - bin(C).count("1")) * (g[0] - g[C])
                if C == 0:
                    break
                C = (C - 1) & B
            if total > 1e-15:
                mu[B] = total
        return g, delta, mu

    def _q_erasing(self, d, cache) -> float:
        if d.get("refused"):
            return math.inf
        if d.get("cut") or d["level"] == 0:
            return d["cost"]
        if d["level"] == 1:
            if not d["same"]:
                return d["cost"]
            return self._q_bounded(d["s"], d["cost"], d["u"], cache)
        return d["cost"] + sum(p * self.H(*x) for x, p in d["law"].items())

    def _q_bounded(self, s, cost, u, cache) -> float:
        """c + G(empty) - min(chain, Moebius) for a use whose every outcome is in the model at a room of shape s, holds no crafted mod and passes
        leaf l with chance at most u_l (level 1 of the erasing rerolls; the likelihood reforges)."""
        supp = 0
        for leaf in self.U:
            if u[leaf] > 0:
                supp |= self.bit[leaf]
        key = (s, supp)
        if key not in cache:
            cache[key] = self._G(*key)
        g, delta, mu = cache[key]
        if not all(math.isfinite(v) for v in g):
            return cost  # L = 0 (no inf - inf)
        chain = sum(float(u[leaf]) * delta[leaf] for leaf in self.U)
        moebius = sum(v * float(min(u[leaf] for leaf in self.U if B & self.bit[leaf])) for B, v in mu.items())
        return cost + max(0.0, g[0] - min(chain, moebius))

    def _best_erasing(self, s) -> float:
        """The least Q over the erasing rerolls of shape s (state-free), the least one raised until exact."""
        cache: dict = {}
        heap = [(self._q_erasing(d, cache), i) for i, d in enumerate(self.erasing) if d["s"] == s and not d.get("refused")]
        heapq.heapify(heap)
        while heap:
            q, i = heapq.heappop(heap)
            d = self.erasing[i]
            if d.get("refused"):
                continue
            if d["level"] < 2 and not d.get("cut"):
                self._raise(d)
                self.raised += 1
                if not d.get("refused"):
                    heapq.heappush(heap, (self._q_erasing(d, cache), i))
                continue
            return q
        return math.inf

    # ---- the other laws ------------------------------------------------------------------------------------------------------

    def _landings(self, d, x):
        """The rooms of the destination shape one draw may land in, or [] when the use is refused at x."""
        s, A, fp, fs, kp, ks = x
        t = d["dest"]
        out = []
        K = {P_: kp, S_: ks}

        def keep(f, k):
            room = (f[P_], f[S_], k[P_], k[S_])
            if self.valid(t, room):
                out.append(room)

        law = d["law"]
        if law == "move-add":
            moved = {P_: fp + self.side_free[t][P_] - self.side_free[s][P_], S_: fs + self.side_free[t][S_] - self.side_free[s][S_]}
            for side in (P_, S_):
                if moved[side] >= 1:
                    f = dict(moved)
                    f[side] -= 1
                    keep(f, K)
        elif law == "add":
            for side in (P_, S_):
                f = {P_: fp, S_: fs}
                if f[side] >= 1:
                    f[side] -= 1
                    keep(f, K)
        elif law[0] == "swap":
            _, add, remove = law
            f = {P_: fp, S_: fs}
            if f[add] < 1 or self.held(s, fp, fs)[remove] < 1:
                return []
            f[add] -= 1
            f[remove] += 1
            keep(f, K)
            if K[remove]:
                keep(f, {**K, remove: K[remove] - 1})
        else:  # added on an open side; maybe one held mod removed on either side, crafted or not
            held = self.held(s, fp, fs)
            for side in (P_, S_):
                f = {P_: fp, S_: fs}
                if f[side] < 1:
                    continue
                f[side] -= 1
                keep(f, K)
                for remove in (P_, S_):
                    if held[remove] + (1 if remove is side else 0) < 1:
                        continue
                    g = dict(f)
                    g[remove] += 1
                    keep(g, K)
                    if K[remove]:
                        keep(g, {**K, remove: K[remove] - 1})
        return out

    def _wanted_on(self, A):
        """The leaves of A on each side (one mod each), or None when a leaf of A is not sure."""
        out = {P_: [], S_: []}
        for leaf in self.U:
            if A & self.bit[leaf]:
                if self.sure[leaf] is None:
                    return None
                out[self.sure[leaf][0]].append(leaf)
        return out

    def _drawval(self, Q, P1, P2, t, A, opts) -> float:
        """A lower bound of E h after the one drawn mod, A kept, the landing among `opts`."""
        if not opts:
            return math.inf  # no such item
        base = self.Hmin(t, A, opts)
        if not Q or not math.isfinite(base):
            return base  # no leaf can pass, or no landing in the model holds a finite h (inf - inf is not taken)
        drop = {leaf: base - self.Hmin(t, A | self.bit[leaf], opts) for leaf in Q}
        d_all = base - min(self.Hmin(t, A | G, opts) for G in range(self.full + 1) if not G & A)
        p2 = min(float(P2), float(P1))
        budget = float(P1) - p2
        cut = p2 * d_all
        for leaf in sorted(drop, key=lambda leaf: -drop[leaf]):
            take = min(float(Q[leaf]), budget)
            cut += take * max(drop[leaf], 0.0)
            budget -= take
            if budget <= 0:
                break
        return base - cut

    def _lost_rooms(self, leaf, f, K, side, t):
        """The rooms after the mod of the sure leaf `leaf` on `side` is removed (its crafted flag known or not)."""
        crafted = self.sure[leaf][1]
        ks_ = [K] if crafted is False else ([{**K, side: K[side] - 1}] if crafted else [K, {**K, side: K[side] - 1}])
        return [room for k in ks_ if self.valid(t, room := (f[P_], f[S_], k[P_], k[S_]))]

    def _junk_rooms(self, W, f, K, side, junk, t):
        """The rooms after a junk mod of `side` is removed: crafted junk only when some crafted mod there is not a wanted one."""
        crafted_wanted = sum(1 for leaf in W[side] if self.sure[leaf][1])
        mixed = sum(1 for leaf in W[side] if self.sure[leaf][1] is None)
        crafted_junk = K[side] - crafted_wanted
        ks_ = ([K] if junk > max(0, crafted_junk - mixed) else []) + ([{**K, side: K[side] - 1}] if crafted_junk > 0 else [])
        return [room for k in ks_ if self.valid(t, room := (f[P_], f[S_], k[P_], k[S_]))]

    def _q_swap(self, d, x, Q, P1, P2):
        s, A, fp, fs, kp, ks = x
        _, add, remove = d["law"]
        W = self._wanted_on(A)
        F, K = {P_: fp, S_: fs}, {P_: kp, S_: ks}
        n = self.held(s, fp, fs)[remove]
        if W is None or F[add] < 1 or n < 1:
            return None
        f = dict(F)
        f[add] -= 1
        f[remove] += 1
        t = d["dest"]
        lost = W[remove]
        junk = n - len(lost)
        if junk < 0 or K[remove] < sum(1 for leaf in lost if self.sure[leaf][1]):
            return math.inf  # no such item
        total = sum(self._drawval(Q, P1, P2, t, A & ~self.bit[leaf], self._lost_rooms(leaf, f, K, remove, t)) / n for leaf in lost)
        if junk:
            total += self._drawval(Q, P1, P2, t, A, self._junk_rooms(W, f, K, remove, junk, t)) * junk / n
        return d["cost"] + total

    def _q_draw(self, d, x) -> float:
        s, A, fp, fs, kp, ks = x
        sup = d["sups"].get((A, fp, fs))
        if sup is None:
            return math.inf
        opts = self._landings(d, x)
        if not opts:
            return math.inf  # refused at x
        Q, P1, P2 = sup
        if d["law"][0] == "swap":
            v = self._q_swap(d, x, Q, P1, P2)
            if v is not None:
                return v
        return d["cost"] + self._drawval(Q, P1, P2, d["dest"], A, opts)

    def _q_annul(self, d, x) -> float:
        s, A, fp, fs, kp, ks = x
        W = self._wanted_on(A)
        F, K = {P_: fp, S_: fs}, {P_: kp, S_: ks}
        held = self.held(s, fp, fs)
        junk = {side: held[side] - len(W[side]) for side in (P_, S_)}
        if any(v < 0 for v in junk.values()) or any(K[side] < sum(1 for leaf in W[side] if self.sure[leaf][1]) for side in (P_, S_)):
            return math.inf  # no such item
        lost, value = [], {}
        for side in (P_, S_):
            f = dict(F)
            f[side] += 1
            for leaf in W[side]:
                lost.append(self.Hmin(s, A & ~self.bit[leaf], self._lost_rooms(leaf, f, K, side, s)))
            if junk[side]:
                value[side] = self.Hmin(s, A, self._junk_rooms(W, f, K, side, junk[side], s))
        protect = kp + ks > 0 or self.tagged_fracture[s]  # a tag metamod held crafted, or fractured in the shape, may protect junk
        best = math.inf
        for jp in range(junk[P_] + 1) if protect else (junk[P_],):
            for js in range(junk[S_] + 1) if protect else (junk[S_],):
                n = len(lost) + jp + js
                if n == 0 or (jp and value[P_] == math.inf) or (js and value[S_] == math.inf):
                    continue
                best = min(best, (sum(lost) + (jp * value[P_] if jp else 0.0) + (js * value[S_] if js else 0.0)) / n)
        return d["cost"] + best if best < math.inf else math.inf

    def _q_craft(self, d, x) -> float:
        s, A, fp, fs, kp, ks = x
        kind = d["kind"]
        held = self.held(s, fp, fs)
        F, K = {P_: fp, S_: fs}, {P_: kp, S_: ks}

        def room(f, k):
            return (f[P_], f[S_], k[P_], k[S_])

        if kind == "craft":
            crafted = d["crafted"]
            if crafted and kp + ks + 1 > KMAX:
                return math.inf
            opts = []
            for side in d["sides"]:
                if F[side] < 1:
                    continue
                f = {**F, side: F[side] - 1}
                k = {**K, side: K[side] + 1} if crafted else K
                if self.valid(s, room(f, k)):
                    opts.append(room(f, k))
            return d["cost"] + self.Hmin(s, A | d["gain"], opts) if opts else math.inf
        if kind == "veiled":
            return d["cost"] + self.H(s, A | d["gain"], fp, fs, kp, ks)
        if kind == "veil":
            opts = []
            for remove in (None, P_, S_):  # None: nothing removed (taken too, so the law does not rest on the orb's refusal)
                if remove is not None and held[remove] < 1:
                    continue
                f = F if remove is None else {**F, remove: F[remove] + 1}
                for k in [K] + ([{**K, remove: K[remove] - 1}] if remove is not None and K[remove] else []):
                    for place in (P_, S_):
                        if f[place] >= 1:
                            r = room({**f, place: f[place] - 1}, k)
                            if self.valid(s, r):
                                opts.append(r)
            return d["cost"] + self.Hmin(s, A, opts) if opts else math.inf
        if kind == "annul" and self._wanted_on(A) is not None:
            return self._q_annul(d, x)
        if kind == "annul":
            opts = []
            for side in (P_, S_):
                if held[side] < 1:
                    continue
                f = {**F, side: F[side] + 1}
                for k in [K] + ([{**K, side: K[side] - 1}] if K[side] else []):
                    if self.valid(s, room(f, k)):
                        opts.append(room(f, k))
            return d["cost"] + self.Hmin(s, A, opts) if opts else math.inf
        if kind == "remove-crafted":
            if kp + ks == 0:
                return math.inf
            return d["cost"] + self.H(s, A, fp + kp, fs + ks, 0, 0)
        # "removes": no mod added, any number removed
        opts = [r for r in self.rk[s] if r[0] >= fp and r[1] >= fs and r[2] <= kp and r[3] <= ks and r[0] - fp >= kp - r[2] and r[1] - fs >= ks - r[3]]
        return d["cost"] + self.Hmin(s, A, opts)

    # ---- the iteration and the check -----------------------------------------------------------------------------------------

    def _T(self) -> dict:
        """T h at every state (without the closure)."""
        out = {}
        cut = [min((c for s2, c in self.cuts if s2 == s), default=math.inf) for s in range(self.S)]
        erasing = [self._best_erasing(s) for s in range(self.S)]
        cache: dict = {}
        bounded = [min((self._q_bounded(s, d["cost"], d["u"], cache) for d in self.bounded if d["s"] == s), default=math.inf) for s in range(self.S)]
        again = math.inf if self.restart is None else self.restart + self.H(*self.xstart)
        for n, x in enumerate(self.states):
            if n % ASK_STATES == 0:
                self.ask()
            s, A = x[0], x[1]
            if A == self.full:
                out[x] = 0.0
                continue
            v = min(cut[s], erasing[s], bounded[s], again)
            for d in self.draws:
                if d["s"] == s:
                    v = min(v, self._q_draw(d, x))
            for d in self.crafts:
                if d["s"] == s:
                    v = min(v, self._q_craft(d, x))
            out[x] = v
        return out

    def _closure(self, t: dict) -> dict:
        return {x: min(t[(x[0], B, *x[2:])] for B in range(self.full + 1) if B & x[1] == B) for x in self.states}

    def solve(self) -> None:
        for self.iterations in range(1, ITERATIONS + 1):
            self.ask()
            new = self._closure(self._T())
            change = 0.0
            for x in self.states:
                a, b = new[x], self.h[x]
                if a != b:
                    change = max(change, math.inf if math.isinf(a) or math.isinf(b) else abs(a - b))
            self.h = new
            if change <= CONVERGED * max(1.0, self.H(*self.xstart)):
                break

    def check(self) -> float:
        """Scale h down and check h <= T h at every state with every offer, no tolerance; raise `_Off` when it fails. Returns the shrink used."""
        raw = self.h
        for shrink in SHRINK:
            self.h = {x: v * (1.0 - shrink) for x, v in raw.items()}
            t = self._T()
            if all(self.h[x] <= t[x] for x in self.states):
                self.reader.h = self.h
                return shrink
        worst = max(raw[x] - t[x] for x in self.states)
        raise _Off(f"the check h <= T h fails (by {worst!r})")
