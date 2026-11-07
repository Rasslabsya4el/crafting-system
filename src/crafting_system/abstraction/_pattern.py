"""The crafted pattern: the key of a state and the optimistic model of the key, built from the abstraction alone (ticket #497, research #376).

A **pattern** is a function of the state. The **key** of this module is `(flags, fractured mods, status of the wanted mods, the item state beyond
the mods, the crafted slots, the ordinary mods per side)`, and with the metamods modelled also the **protected tags** of the ordinary mods per
side (`PatternKey`). The **optimistic model** of the key has one abstract state per key and, in it, the actions of the concrete states that have
it, seen through the key. A concrete policy is a policy of that model (it takes the action of the member it is in), so its optimal value never
exceeds the exact value of a member: `V_key(key(s)) <= V*(s)`. Research #376 measured this bound on the walked graphs (99.48% of the exact cost
on R04, 98.10% on R14, 99.99% with the tags, 100% on S02). This module builds the same model **without the walk**: `members(key, mode)`
makes the concrete states of a key from the key alone, `Pattern.expand` offers the kernels of those members, and `build_pattern_model` explores
the keys from the start key.

Admissible by construction (an action offered in a key is at least as good as the action of every concrete state of the key, for any values of
the successor keys; costs are the offers' own, the same for every member; no outcome is dropped, because the kernel of a member is the exact
kernel of `Abstraction`, pushed through the key, and chances that fall in one key add). What has to be argued is that the members offered
stand for all the members. The members of a key are the states with that key, and their ordinary mods differ in two ways.

* **Which goal-relevant mods they hold.** An ordinary slot is *relevant* unless its kind is a family type `~n` none of whose mods gives the
  goal anything ("pure junk"); relevant slots (those that give a leaf something, those of a family type that has such a mod, and the families an
  enabled action names) are enumerated exactly: every multiset consistent with the status, the counts and the tags. Nothing is assumed of them.
* **Which pure junk they hold.** A pure junk slot of side `s` and tag set `T` (its *class*) stands for one family of a family type of that class.
  The classes' counts are in the key (with the tags in it) or enumerated (without). Within a class the members differ in which types they hold,
  and so in the pool weight `H_c` the held families take out of the pool.

The member policy of an action (`Pattern.mode_of`) says which pure junk assignments are offered, and is the soundness argument of the action
class. In the notation `V` is any value of the successor keys and `backup_m(V)` is the chance-weighted sum for the member `m`:

* `ANY` (one member): an erasing reroll that reads no junk (Chaos, Alteration, Transmutation, an essence, a Harvest reforge), when the key holds
  no lock. Its outcome is a function of the flags, the fractured mods, the crafted slots and the item state (the pool excludes the fractured
  families only; the other mods are erased), all in the key (ADR-0023, "block-invariant", checked on the fixtures by the contract suite).
  **Proved** by the same argument as ADR-0023; with a lock it is not (the locked side keeps its junk through a reroll, the draw excludes
  those families, and several mods are drawn: the chance is a product of ratios, not a linear-fractional function), so a key that holds a lock
  uses `ALL`.
* `ONE` (one member for each relevant multiset and class composition): an action that reads the junk but is declared block-invariant and reads
  no pool weight (a bench craft, Remove Crafted Mods, the Annulment). Bench crafts read the families they name (relevant kinds, enumerated);
  Remove Crafted Mods reads nothing of the junk; the Annulment removes one removable slot uniformly, and the removable slots are counted by
  class (the tags are in the key, or the compositions are enumerated), so its pushed kernel is the same for every assignment of the pure junk
  of a class: the chance of a successor key is `(removable slots that lead to it) / (removable slots)`. **Proved** for the Annulment under
  protected tags when the tags are in the key or enumerated (an Attack/Caster metamod keeps the protected-tag slots out of the candidates, and
  that is a function of the class); the locked side is kept (a lock in the key makes the mode `ALL`).
* `EXTREMES` (the lightest and the heaviest assignment in each class that holds pure junk): an addition that keeps the mods (`Reads.variants`:
  Augmentation, Regal, Exalted; one mod drawn). The chance of a successor key is `(a + sum_c b_c H_c) / (W - H_rel - sum_c H_c)` with `H_c` the
  pool weight (under the protected tags the key's metamods impose) the held pure junk of class `c` takes out, `H_rel` that of the relevant slots
  (the same for every assignment) and `W` the pool total: a drawn pure junk mod of class `c'` lands in the same successor key whichever of its
  types it is, and the chance of that is `(W_c' - H_c') / (W - H)`. A linear-fractional function with a positive denominator is quasi-linear,
  so the least and the greatest backup over a box of `H_c` are reached at its corners; the achievable `H` vector is a subset of the box whose
  corners are achievable (the lightest and the heaviest fill of each class, independently), so the least backup over all members is reached at
  an offered one. **Proved for a single draw** (ADR-0023); **extended here to the protected tags** (the draw excludes the mods of the blocked
  tags and the held families take out their eligible weight) and checked against all members on the fixtures. A corner that two classes make
  impossible together (one family type shared by two tag kinds) is not offered: the key then falls back to `ALL`.
  An action that draws by tag or by item level (`Reads.draw_tags`, `Reads.draw_levels`) makes the family types differ by more than weight: `ALL`.
* `ALL` (every pure junk assignment): the Fracturing Orb (the successor key holds the type of the mod fractured, a function of which types the
  member holds: not of the weights), any action that is not declared one of the above, and an erasing reroll under a lock. **Unproved to be
  cheaper, and exact by construction.**

Every member offered is checked to be an item (`Abstraction._item_of`), so a member that no item has is never offered.

**Refusals.** An action that the game forbids at a member (`NotApplicableError`) is not an action of that member and is left out
of it. An action that raises a model gap at a member (`OutOfScopeError`: no admitted rule covers the item) is left out only when
no member of the key can take it (each is a game refusal or a gap: the exact model has no action at any state of the key, as the walk and the
planner treat a gap as unavailable). If another member can take it, the build refuses and names the offer and the key: the exact model drops
the action only at the states where the gap is, so leaving it out of the key could put the bound above the exact cost (`_gap_everywhere`). A
model gap in `_item_of` always refuses.

**The universe.** The members of a key are made of the ordinary slots an item can hold. They come from three places: the pool of an empty rare
item (every mod a draw can give; the pure junk types are made of these), what an offered action adds by name (`Adds.named`: an essence's forced
mod, which the pool does not list; `Universe._seed_named`), and every slot a kernel the build evaluates produces (`note`; a slot found this way
that the two others missed starts the build again, `stats.universe_growth`). A slot that a non-offered member's kernel would produce, and no
offered member's, cannot be one of the first two: a draw gives a mod of the pool, and a forced mod is the same at every member. What is left is
a draw from a pool wider than the empty rare item's (a fossil's added mods) at a member that is not offered, which `Adds` does not name: the
universe may miss that slot, and the members that hold it are not made (issue #520). No route of the benchmark has such an action.
"""

import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from fractions import Fraction
from functools import reduce
from itertools import product
from math import gcd, lcm
from typing import NamedTuple

from crafting_system.actions import BLOCKED_TAG, Action, NotApplicableError, OutOfScopeError, allowed_by_tags
from crafting_system.data import Mod
from crafting_system.items import Item, ItemError, Metamod, Rarity, Side

from ._goal import Status
from ._kernel import Abstraction
from ._kinds import TYPE_PREFIX, kind_tags
from ._state import CompressedState, Slot, best_of

# The two families of refusal an action raises (`actions/errors.py`, #506). A game refusal (`NotApplicableError`: the game forbids the action on that
# item) may drop the action at a member: it is not an action there. A model gap (`OutOfScopeError`: no admitted rule covers the item) may not: at a
# member that is not a state of the route it says nothing about the states that are, and dropping the action from the key could put the bound
# above the exact cost. The build refuses and says why. The clauses name the families themselves (`tests/test_cli_model_gaps.py` scans for them).

PRIME_FROM = 8  # a key that is given at least this many offers at once primes their distributions in a process pool, in chunks of ...
PRIME_CHUNK = 32  # ... this many offers (the net is asked between two chunks)
POLL_SECONDS = 0.5  # how often a build asks its net (a clock and a memory read, cheap beside one offer)
SIDES = (Side.PREFIX, Side.SUFFIX)
LOCKS = frozenset({Metamod.PREFIXES_CANNOT_CHANGE.value, Metamod.SUFFIXES_CANNOT_CHANGE.value})
TAG_OF_METAMOD = {metamod.value: tag for metamod, tag in BLOCKED_TAG.items()}


class Mode(StrEnum):
    """Which members of a key an action is offered at (see the module docstring)."""

    ANY = "any"
    ONE = "one"
    EXTREMES = "extremes"
    ALL = "all"


class PatternKey(NamedTuple):
    """The pattern of a state: what the optimistic model tells states apart by."""

    flags: object
    fractured: tuple
    status: tuple
    held: tuple
    crafted: tuple
    counts: tuple  # the ordinary (not crafted) slots per side: (prefix, suffix)
    tags: tuple | None  # ((side index, protected tags), count) of the ordinary slots, or None when the key carries no tags


@dataclass(frozen=True)
class _PureType:
    """A family type none of whose mods gives the goal anything: `capacity` families of one `weight`, on a side."""

    side: Side
    base: str
    capacity: int
    mods: tuple[Mod, ...]  # the mods of one family of the type, with the weight they have in the pool
    weights: tuple[Fraction, ...]

    def weight(self, blocked: frozenset[str]) -> Fraction:
        """The pool weight a family of this type takes out of a draw under the metamods that block `blocked` tags."""
        return sum((w for mod, w in zip(self.mods, self.weights) if allowed_by_tags(mod, blocked)), Fraction(0))


@dataclass(frozen=True)
class _PureKind:
    kind: str
    slot: Slot
    type: _PureType


class _Universe:
    """The ordinary slots an item with given influences can hold, split into relevant slots and pure junk kinds."""

    def __init__(self, pattern: "Pattern", influences: frozenset):
        ab = pattern.ab
        context = ab._context(influences)
        kinds = context.kinds
        zero = pattern.zero
        self.relevant: dict[Side, dict[Slot, None]] = {side: {} for side in SIDES}
        self.pure: dict[Side, dict[str, _PureType]] = {side: {} for side in SIDES}
        self.classes: dict[Side, dict[tuple, list[_PureKind]]] = {side: defaultdict(list) for side in SIDES}
        by_type: dict[tuple[Side, str], list] = defaultdict(list)  # (side, type kind) -> [(family, mod, slot)]
        for family in kinds._pool() if kinds.tracked else ():  # a state that keeps no junk holds no ordinary slot
            for entry in family.mods:
                kind = kinds.of(entry.mod)
                contribution = ab._drawn_contribution(entry.mod, False, influences)
                slot = Slot(family.side, kind, contribution)
                by_type[(family.side, _base(kind))].append((family, entry.mod, slot))
        for (side, base), rows in by_type.items():
            pure = base.startswith(TYPE_PREFIX) and all(all(value is Status.ABSENT for value in slot.contribution) for _, _, slot in rows)
            if not pure:
                for _, _, slot in rows:
                    self.relevant[side][slot] = None
                continue
            families = {family.family: family for family, _, _ in rows}
            first = next(iter(families.values()))  # the families of one type have the same mods and weights (the type is made of them)
            kind_type = _PureType(side, base, len(families), tuple(entry.mod for entry in first.mods), tuple(entry.weight for entry in first.mods))
            self.pure[side][base] = kind_type
            for kind in sorted({slot.kind for _, _, slot in rows}):
                self.classes[side][_tagset(kind)].append(_PureKind(kind, Slot(side, kind, zero), kind_type))
        self.zero = zero
        self.influences = influences
        self.kinds = kinds
        self._seed_named(pattern, pattern.actions)

    def _seed_named(self, pattern: "Pattern", actions: Sequence[Action]) -> int:
        """Add the ordinary mods an offered action puts on the item by name and that the pool does not list (an essence's forced mod).

        `Adds.named` is the same on every use, so the slot is known before any kernel is run; this is what keeps a slot that only a member that
        is not offered would have produced from missing (see the module docstring, "The universe"). Returns how many slots the universe gained.
        """
        ab = pattern.ab
        influences, kinds = self.influences, self.kinds
        gained = 0
        probe = Item.build(ab.data, base_id=ab.base_id, item_level=ab.item_level, rarity=Rarity.RARE, influences=influences)
        for action in actions:
            try:
                adds = action.adds(ab.data, probe)
            except NotApplicableError:
                continue
            if adds.crafted:
                continue
            for mod_id in adds.named or ():
                mod = ab.data.mods.get(mod_id)
                if mod is None or mod.domain == "crafted" or mod.generation_type not in (side.value for side in SIDES):
                    continue
                gained += self.note(Slot(Side(mod.generation_type), kinds.of(mod), ab._drawn_contribution(mod, False, influences)))
        return gained

    def note(self, slot: Slot) -> bool:
        """Add a slot a kernel produced that the pool did not list; True when the universe grew."""
        if slot.crafted or slot.side not in self.relevant:
            return False
        base = _base(slot.kind)
        known_pure = self.pure[slot.side].get(base)
        if known_pure is not None and all(value is Status.ABSENT for value in slot.contribution):
            if any(item.kind == slot.kind for item in self.classes[slot.side][_tagset(slot.kind)]):
                return False
            self.classes[slot.side][_tagset(slot.kind)].append(_PureKind(slot.kind, Slot(slot.side, slot.kind, self.zero), known_pure))
            return True
        if slot in self.relevant[slot.side]:
            return False
        self.relevant[slot.side][slot] = None
        return True


def _base(kind: str) -> str:
    from ._kinds import base_kind

    return base_kind(kind)


def _tagset(kind: str) -> tuple:
    return tuple(sorted(kind_tags(kind)))


def _slot_key(slot: Slot):
    return slot.key


@dataclass
class PatternStats:
    """What a build did, for the report (ticket #497: kernels evaluated against the walk's, time, memory)."""

    keys: int = 0
    goal_keys: int = 0
    members: int = 0  # concrete states offered an action, over all keys and modes (a member counted once per mode)
    pairs: int = 0  # (member, action) pairs whose kernel key was asked for
    kernels: int = 0  # distinct kernels computed (the walk's count is its distinct `kernel_key`s)
    abstract_actions: int = 0
    abstract_edges: int = 0
    refused_pairs: int = 0
    gap_pairs: int = 0  # pairs left out because the action is a model gap at every member of the key that is not a game refusal
    universe_growth: int = 0
    modes: Counter = field(default_factory=Counter)  # (member mode, label of the offer) -> keys it was expanded at
    seconds: float = 0.0
    fallbacks: int = 0  # keys whose extremes were impossible and used every member


@dataclass
class PatternModel:
    """The optimistic model of the key: state 0 is the start key; `actions[k]` are `(offer index, kernel id)` of key `k`."""

    keys: list[PatternKey]
    goal: list[bool]
    actions: list[list[tuple[int, int]]]
    kernels: list[tuple[tuple[int, ...], tuple[int, ...]]]  # (successor keys, integer weights)
    stats: PatternStats
    index: dict[PatternKey, int]
    expanded: list[bool] = field(default_factory=list)  # key -> whether its actions were built; a key the build did not reach is a tip (no actions, not a dead end)
    stopped: str | None = None  # why the build ended before every key was expanded (a net), None for a complete model


class Pattern:
    """The key of a state and the members of a key, for one `Abstraction`.

    `tags` says whether the key carries the protected tags of the ordinary mods; it defaults to whether the abstraction models the metamods.
    Raises `OutOfScopeError` for an abstraction whose slots the key cannot yet enumerate: roll limits on the goal, an enabled action that
    rerolls values, or one that reads the unveil offer or the imprints.
    """

    def __init__(self, abstraction: Abstraction, tags: bool | None = None, actions: Sequence[Action] = ()):
        if abstraction._has_laws or abstraction.rerolls_values or abstraction.tracks_offer or abstraction.tracks_imprints:
            raise OutOfScopeError(
                "the crafted-pattern bound has no members for a goal with a roll limit, an action that rerolls values, an unveil offer or imprints (#497)"
            )
        self.ab = abstraction
        self.data = abstraction.data
        self.actions = tuple(actions)  # the offered actions: what they add by name joins the universe of slots
        self.tags = abstraction.models_metamods if tags is None else tags
        self.width = len(abstraction.goal.leaves)
        self.zero = (Status.ABSENT,) * self.width
        self._universes: dict[frozenset, _Universe] = {}
        self._reads: dict[Action, object] = {}
        self._feasible: dict[CompressedState, bool] = {}
        self._tag_kind: dict[str, tuple] = {}
        self.grew = 0
        self.fallbacks = 0

    def add_actions(self, actions: Sequence[Action]) -> None:
        """Offer more actions: what they add by name joins the universe, and a universe that gains a slot counts as growth (`grew`), as a kernel's slot does."""
        self.actions = (*self.actions, *actions)
        for universe in self._universes.values():
            self.grew += universe._seed_named(self, actions)

    # ---- the key ----------------------------------------------------------------------------------------------

    def key(self, state: CompressedState) -> PatternKey:
        counts = [0, 0]
        crafted = []
        tags: Counter | None = Counter() if self.tags else None
        for slot in state.slots:
            if slot.crafted:
                crafted.append(slot)
                continue
            side = 0 if slot.side is Side.PREFIX else 1
            counts[side] += 1
            if tags is not None:
                tagset = self._tag_kind.get(slot.kind)
                if tagset is None:
                    tagset = self._tag_kind[slot.kind] = _tagset(slot.kind)
                tags[(side, tagset)] += 1
        return PatternKey(
            state.flags, state.fractured, state.status, state.held, tuple(crafted), (counts[0], counts[1]),
            tuple(sorted(tags.items())) if tags is not None else None,
        )

    def universe(self, influences: frozenset) -> _Universe:
        found = self._universes.get(influences)
        if found is None:
            found = self._universes[influences] = _Universe(self, influences)
        return found

    def note(self, state: CompressedState) -> None:
        """Learn the ordinary slots of a state a kernel produced (the pool may not list them)."""
        universe = self.universe(state.flags.influences)
        for slot in state.slots:
            if not slot.crafted and universe.note(slot):
                self.grew += 1

    # ---- the member policy of an action -----------------------------------------------------------------------

    def reads(self, action: Action):
        found = self._reads.get(action)
        if found is None:
            found = self._reads[action] = action.reads(self.data)
        return found

    def holds_lock(self, key: PatternKey) -> bool:
        """Whether the key holds a lock (`Prefixes` / `Suffixes Cannot Be Changed`), crafted or fractured: a reroll then keeps the locked side."""
        mods = self.data.mods
        ids = [slot.kind for slot in key.crafted] + [entry.mod_id for entry in key.fractured]
        return any(mod_id in mods and LOCKS & set(mods[mod_id].families) for mod_id in ids)

    def blocked_tags(self, key: PatternKey) -> frozenset[str]:
        """The tags the key's Attack and Caster metamods keep out of a draw and out of an Annulment."""
        mods = self.data.mods
        ids = [slot.kind for slot in key.crafted] + [entry.mod_id for entry in key.fractured]
        return frozenset(TAG_OF_METAMOD[family] for mod_id in ids if mod_id in mods for family in mods[mod_id].families if family in TAG_OF_METAMOD)

    def mode_of(self, action: Action, key: PatternKey) -> Mode:
        reads = self.reads(action)
        kinds = self.ab._context(key.flags.influences).kinds
        if reads.variants and reads.junk and reads.pool_weight and not reads.fractures:
            return Mode.ALL if kinds._tagged or kinds._levels else Mode.EXTREMES
        if reads.block_invariant and not (reads.variants or reads.pool_weight or reads.fractures or reads.rerolls_values or reads.input_classes):
            if self.holds_lock(key):
                return Mode.ALL
            return Mode.ONE if reads.junk else Mode.ANY
        return Mode.ALL

    # ---- the members of a key ---------------------------------------------------------------------------------

    def members(self, key: PatternKey, mode: Mode) -> list[CompressedState]:
        """The concrete states of `key` that stand for all of its members for an action of the policy `mode`; each is an item."""
        if not self.ab._context(key.flags.influences).kinds.tracked:
            # no enabled action reads the junk, so a state keeps none of it: its status is a fact about mods that are not stored, and the one
            # state the key stands for is the key itself (no ordinary slot to choose, nothing to check the status against)
            only = CompressedState(key.flags, key.fractured, key.status, key.crafted, *key.held)
            return [only] if self._ok(only) else []
        universe = self.universe(key.flags.influences)
        blocked = self.blocked_tags(key)
        base = best_of(self.width, [slot.contribution for slot in key.crafted] + [entry.contribution for entry in key.fractured])
        found: dict[CompressedState, None] = {}
        for rel_p, rel_s in product(
            self._relevant(universe, Side.PREFIX, key.counts[0], key.status), self._relevant(universe, Side.SUFFIX, key.counts[1], key.status)
        ):
            relevant = rel_p + rel_s
            if best_of(self.width, [slot.contribution for slot in relevant] + [base]) != key.status:
                continue
            for compositions in self._compositions(universe, key, rel_p, rel_s):
                for state in self._assemble(universe, key, relevant, compositions, blocked, mode):
                    found[state] = None
                if mode is Mode.ANY and found:
                    return list(found)
        return list(found)

    def _relevant(self, universe: _Universe, side: Side, count: int, status: tuple) -> list[tuple[Slot, ...]]:
        """Every multiset of at most `count` relevant slots of `side` that none of its slots exceeds `status` in."""
        pool = sorted(
            (slot for slot in universe.relevant[side] if all(c <= s for c, s in zip(slot.contribution, status))), key=_slot_key
        )
        out: list[tuple[Slot, ...]] = []

        def grow(start: int, chosen: tuple[Slot, ...]) -> None:
            out.append(chosen)
            if len(chosen) == count:
                return
            for at in range(start, len(pool)):
                grow(at, (*chosen, pool[at]))

        grow(0, ())
        return out

    def _compositions(self, universe: _Universe, key: PatternKey, rel_p, rel_s) -> Iterator[dict[tuple, int]]:
        """The ways the pure junk slots split into classes (side index, tag set): fixed by the key's tags, enumerated without them."""
        have = Counter()
        for slot in (*rel_p, *rel_s):
            have[(0 if slot.side is Side.PREFIX else 1, _tagset(slot.kind))] += 1
        left = (key.counts[0] - len(rel_p), key.counts[1] - len(rel_s))
        if left[0] < 0 or left[1] < 0:
            return
        if key.tags is not None:
            need = {cls: count - have[cls] for cls, count in key.tags}
            for cls, count in have.items():
                if cls not in need:
                    return
            if any(count < 0 for count in need.values()):
                return
            need = {cls: count for cls, count in need.items() if count}
            if any(sum(c for (s, _), c in need.items() if s == side) != left[side] for side in (0, 1)):
                return
            yield need
            return
        per_side = []
        for index, side in enumerate(SIDES):
            classes = sorted(tagset for tagset, items in universe.classes[side].items() if items)
            per_side.append([{(index, tagset): n for tagset, n in zip(classes, split) if n} for split in _splits(left[index], len(classes))] if classes or not left[index] else [])
        for first, second in product(*per_side):
            yield {**first, **second}

    def _assemble(self, universe: _Universe, key: PatternKey, relevant, need: dict[tuple, int], blocked, mode: Mode) -> Iterator[CompressedState]:
        options = []
        for (side_index, tagset), count in sorted(need.items()):
            side = SIDES[side_index]
            fills = _fills(universe.classes[side].get(tagset, []), count, blocked, mode)
            if not fills:
                return
            options.append(fills)
        corners = self._states(key, relevant, options)
        if mode is Mode.ALL or all(self._ok(state) for state in corners):
            yield from (state for state in corners if self._ok(state))
            return
        # a corner that two classes make impossible together (or no state at all): every assignment of this composition instead
        every = [_fills(universe.classes[SIDES[side_index]].get(tagset, []), count, blocked, Mode.ALL) for (side_index, tagset), count in sorted(need.items())]
        found = [state for state in self._states(key, relevant, every) if self._ok(state)]
        if found:
            self.fallbacks += 1
        yield from found

    def _states(self, key: PatternKey, relevant, options) -> list[CompressedState]:
        out = []
        for pick in product(*options) if options else [()]:
            slots = [*key.crafted, *relevant]
            for part in pick:
                slots.extend(part)
            slots.sort(key=_slot_key)
            out.append(CompressedState(key.flags, key.fractured, key.status, tuple(slots), *key.held))
        return out

    def _ok(self, state: CompressedState) -> bool:
        """Whether the state is an item the abstraction can give to an action (every slot has a family of its own)."""
        found = self._feasible.get(state)
        if found is None:
            try:
                self.ab._item_of(state, False)
                found = True
            except OutOfScopeError:
                raise
            except (ValueError, ItemError):
                found = False
            self._feasible[state] = found
        return found


def _splits(total: int, parts: int) -> Iterator[tuple[int, ...]]:
    """Every way to write `total` as `parts` non-negative integers."""
    if parts == 0:
        if total == 0:
            yield ()
        return
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in _splits(total - first, parts - 1):
            yield (first, *rest)


def _fills(items: Sequence[_PureKind], count: int, blocked: frozenset[str], mode: Mode) -> list[tuple[Slot, ...]]:
    """The ways `count` pure junk slots of one class sit on its kinds: the lightest, the heaviest, or every one, by the pool weight they take out."""
    if count == 0:
        return [()]
    order = sorted(items, key=lambda item: (item.type.weight(blocked), item.kind))
    if mode is Mode.ALL:
        return _all_fills(order, count)
    lightest = _greedy(order, count)
    if mode is not Mode.EXTREMES:
        return [lightest] if lightest is not None else []
    heaviest = _greedy(order[::-1], count)
    out = [fill for fill in (lightest, heaviest) if fill is not None]
    return [out[0]] if len(out) == 2 and out[0] == out[1] else out


def _greedy(order: Sequence[_PureKind], count: int) -> tuple[Slot, ...] | None:
    used: Counter = Counter()
    chosen: list[Slot] = []
    for item in order:
        while len(chosen) < count and used[item.type.base] < item.type.capacity:
            used[item.type.base] += 1
            chosen.append(item.slot)
    return tuple(sorted(chosen, key=_slot_key)) if len(chosen) == count else None


def _all_fills(order: Sequence[_PureKind], count: int) -> list[tuple[Slot, ...]]:
    out: list[tuple[Slot, ...]] = []
    used: Counter = Counter()

    def grow(at: int, chosen: tuple[Slot, ...]) -> None:
        if len(chosen) == count:
            out.append(tuple(sorted(chosen, key=_slot_key)))
            return
        for index in range(at, len(order)):
            item = order[index]
            if used[item.type.base] < item.type.capacity:
                used[item.type.base] += 1
                grow(index, (*chosen, item.slot))
                used[item.type.base] -= 1

    grow(0, ())
    return out


# ---- the optimistic model -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PatternOffer:
    """An action of the plan: `action` is None for the restart (buy the start item again), which leads to the start key."""

    label: str
    action: Action | None
    cost: float


def build_pattern_model(
    abstraction: Abstraction,
    start: CompressedState,
    offers: Sequence[PatternOffer],
    *,
    tags: bool | None = None,
    progress=None,
    max_keys: int | None = None,
    stop: Callable[[], str | None] | None = None,
) -> PatternModel:
    """The optimistic model of the key from the start key, with no walk of the concrete graph.

    For each key, not a goal, and each offer it is offered at the pushed kernel of every member of the policy of the action
    (`Pattern.mode_of`); members that the action refuses do not offer it, and a restart leads to the start key from every key but the start's.
    Two members with the same pushed kernel give one abstract action. If a kernel produces an ordinary slot the pool did not list, the
    universe grows and the build runs again (`stats.universe_growth` counts the restarts). Raises `OutOfScopeError` as `Pattern` does and
    `RuntimeError` when more than `max_keys` keys were found (a safety net the caller asks for, never a default).

    `stop` is the stop-and-say-so net of the build (OR-12, OR-13): it is asked between two offers of a key (so a key that holds thousands of
    offers is no longer one step) and returns the reason once a net is reached. The build then ends with `PatternModel.stopped` set. The key it was
    expanding is left a tip like the keys it had not reached: a tip has no actions in the model, which is not "the key has none", so the caller
    gives it a bound of its own (`_pattern_bound`, a floor action to the goal). If the universe had grown in that pass, the keys expanded before
    the growth lack the members that hold the new slot, so none of them is kept: every key is a tip.
    """
    return PatternBuilder(abstraction, start, tags=tags, progress=progress, max_keys=max_keys, stop=stop).extend(offers)


class PatternBuilder:
    """The model of the key, built on a list of offers that can grow: `extend` adds offers and builds only what they add (ticket #626).

    A model built on a part of the offers and grown by the ones that turn out to matter would cost a whole build for each round if each round began
    again; here a key that is expanded keeps its actions, and an offer added later is offered at the keys already expanded (its members, its kernels,
    each distinct kernel once) and at the keys it finds. `extend` returns a snapshot of the model, so a model returned stays what it was when the builder
    goes on. A build that stops (`stop`) leaves the builder unusable: the keys it had expanded do not all hold the offers being added, so the caller keeps
    the model of the round before. A universe that grows (a slot no member held) begins the whole build again, as `build_pattern_model` always has.
    """

    def __init__(
        self, abstraction: Abstraction, start: CompressedState, *, tags: bool | None = None, progress=None, max_keys: int | None = None, stop=None
    ) -> None:
        self.ab = abstraction
        self.start = start
        self.tags = tags
        self.progress = progress
        self.max_keys = max_keys
        self.stop = stop
        self.offers: list[PatternOffer] = []
        self.restarts = 0
        self.began = time.perf_counter()
        self.dead = False
        self._reset()

    def _reset(self) -> None:
        self.pattern = Pattern(self.ab, self.tags, [offer.action for offer in self.offers if offer.action is not None])
        self.stats = PatternStats()
        self.index: dict[PatternKey, int] = {}
        self.keys: list[PatternKey] = []
        self.goal: list[bool] = []
        self.rows: list[list[tuple[int, int]]] = []
        self.expanded: list[bool] = []
        self.kernel_ids: dict[tuple, int] = {}
        self.kernels: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
        self.computed: dict = {}  # kernel key of the abstraction -> kernel id of the model
        self.gaps: dict = {}  # (key, offer index) -> whether no member of the key can take the action (see `_gap_everywhere`)
        self.done = 0  # the number of offers every expanded key holds
        self.pattern.note(self.start)
        self.start_id = self._intern(self.start)

    def _intern(self, state: CompressedState) -> int:
        key = self.pattern.key(state)
        found = self.index.get(key)
        if found is None:
            found = self.index[key] = len(self.keys)
            self.keys.append(key)
            self.goal.append(self.ab.is_goal(state))
            self.rows.append([])
            self.expanded.append(False)
            if self.max_keys is not None and len(self.keys) > self.max_keys:
                raise RuntimeError(f"more than {self.max_keys} keys")
        return found

    def extend(self, offers: Sequence[PatternOffer]) -> PatternModel:
        """Add `offers` to the model and build what they add; the snapshot of the model, with `stopped` set if a net ended the build."""
        if self.dead:
            raise RuntimeError("the build was stopped; use the model of the round before")
        self.offers.extend(offers)
        self.pattern.grew = 0
        self.pattern.add_actions([offer.action for offer in offers if offer.action is not None])
        while True:  # each pass that grows the universe adds slots to a finite set, so this ends; a pass that adds none is the answer
            stopped = self._pass()
            if stopped is not None:
                self.dead = True
                if self.pattern.grew:
                    self.expanded = [False] * len(self.keys)
                    self.rows = [[] for _ in self.keys]
                return self._snapshot(stopped)
            if not self.pattern.grew:
                return self._snapshot(None)
            self.restarts += 1
            self._reset()
            self.pattern.grew = 0

    def _snapshot(self, stopped: str | None) -> PatternModel:
        stats = replace(self.stats)
        stats.keys = len(self.keys)
        stats.goal_keys = sum(self.goal)
        stats.fallbacks = self.pattern.fallbacks
        stats.universe_growth = self.restarts
        stats.abstract_actions = sum(len(row) for row in self.rows)
        stats.abstract_edges = sum(len(self.kernels[kid][0]) for row in self.rows for _, kid in row)
        stats.seconds = time.perf_counter() - self.began
        stats.modes = Counter(self.stats.modes)
        return PatternModel(
            list(self.keys), list(self.goal), [list(row) for row in self.rows], list(self.kernels), stats, dict(self.index), list(self.expanded), stopped
        )

    def _pass(self) -> str | None:
        """Expand every key for the offers it lacks; the reason a net ended it, or None when it ran to the end."""
        pattern, offers, stats, progress = self.pattern, self.offers, self.stats, self.progress
        last = polled = time.perf_counter()
        i = 0

        def tick(oi: int) -> None:
            """Between two offers: ask the net, and say where the build is every 30 seconds (a key can take minutes: no longer one silent step)."""
            nonlocal last, polled
            now = time.perf_counter()
            if now - polled < POLL_SECONDS:
                return
            polled = now
            if self.stop is not None:
                reason = self.stop()
                if reason is not None:
                    raise _Stopped(reason)
            if progress is not None and now - last >= 30:
                last = now
                progress(
                    f"keys found {len(self.keys):,} expanded {i:,} (now offer {oi + 1:,} of {len(offers):,} of key {i:,}) kernels {stats.kernels:,} members {stats.members:,}"
                )

        while i < len(self.keys):
            if self.stop is not None and (reason := self.stop()) is not None:
                return reason
            if not self.goal[i]:
                first = self.done if self.expanded[i] else 0
                if first < len(offers):
                    if not pattern.members(self.keys[i], Mode.ANY):
                        raise _no_member(self.keys[i])
                    try:
                        self._offers_of_key(i, first, tick)
                    except _Stopped as reached:
                        self.ab.release_prepared(keep_erased=True)
                        return reached.reason
                    self.ab.release_prepared(keep_erased=True)
            self.expanded[i] = True
            i += 1
            now = time.perf_counter()
            if progress is not None and now - last >= 30:
                last = now
                progress(f"keys found {len(self.keys):,} expanded {i:,} kernels {stats.kernels:,} members {stats.members:,}")
        self.done = len(offers)
        return None

    def _prime(self, key: PatternKey, lo: int, hi: int, by_mode: dict) -> None:
        """Make, side by side in a process pool, the exact distributions that the offers `lo` to `hi` need at the members of `key` (ticket #250, #626).

        The kernel of a fossil set is a distribution of seconds, computed once per pool and cached; a model built on hundreds of offers asked for them
        one after the other. Nothing is built here and nothing changes in the answer; with one worker, or no `fork`, this does nothing. A chunk is
        at most `PRIME_CHUNK` offers so that the net is asked between chunks.
        """
        requests = []
        for offer in self.offers[lo:hi]:
            if offer.action is None:
                continue
            mode = self.pattern.mode_of(offer.action, key)
            members = by_mode.get(mode)
            if members is None:
                members = by_mode[mode] = self.pattern.members(key, mode)
                self.stats.members += len(members)
            requests.extend((member, offer.action) for member in members)
        self.ab.prime(requests)

    def _offers_of_key(self, i: int, first: int, tick) -> None:
        """Add to the row of key number `i` the abstract actions of the offers from number `first` on (one `(offer index, kernel id)` for each distinct pushed kernel)."""
        pattern, ab, stats, offers = self.pattern, self.ab, self.stats, self.offers
        key = self.keys[i]
        by_mode: dict[Mode, list[CompressedState]] = {}
        added: list[tuple[int, int]] = []
        for oi in range(first, len(offers)):
            offer = offers[oi]
            tick(oi)
            if (oi - first) % PRIME_CHUNK == 0 and len(offers) - first >= PRIME_FROM:
                self._prime(key, oi, min(oi + PRIME_CHUNK, len(offers)), by_mode)
            if offer.action is None:
                if i != self.start_id:
                    added.append((oi, _kernel_id(self.kernel_ids, self.kernels, {self.start_id: Fraction(1)})))
                continue
            mode = pattern.mode_of(offer.action, key)
            members = by_mode.get(mode)
            if members is None:
                members = by_mode[mode] = pattern.members(key, mode)
                stats.members += len(members)
            stats.modes[(mode.value, offer.label)] += 1
            seen: set[int] = set()
            for member in members:
                stats.pairs += 1
                try:
                    ck = ab.kernel_key(member, offer.action)
                except NotApplicableError:
                    stats.refused_pairs += 1
                    continue
                except OutOfScopeError as gap:
                    if _gap_everywhere(pattern, self.gaps, key, offer):
                        stats.gap_pairs += 1
                        continue
                    raise _gap(offer, key, gap) from gap
                kid = self.computed.get(ck)
                if kid is None:
                    try:
                        exact = ab.kernel(member, offer.action)
                    except NotApplicableError:
                        stats.refused_pairs += 1
                        continue
                    except OutOfScopeError as gap:
                        if _gap_everywhere(pattern, self.gaps, key, offer):
                            stats.gap_pairs += 1
                            continue
                        raise _gap(offer, key, gap) from gap
                    stats.kernels += 1
                    pushed: dict[int, Fraction] = defaultdict(Fraction)
                    for successor, chance in exact.items():
                        pattern.note(successor)
                        pushed[self._intern(successor)] += chance
                    kid = self.computed[ck] = _kernel_id(self.kernel_ids, self.kernels, pushed)
                if kid not in seen:
                    seen.add(kid)
                    added.append((oi, kid))
        self.rows[i].extend(added)  # the row of a key is whole or untouched: a stop in the middle leaves it as it was


class _Stopped(Exception):
    """Raised by the tick of a build when a net is reached, inside the expansion of one key."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _no_member(key: PatternKey) -> OutOfScopeError:
    """The refusal of a build that reached a non-goal key it can make no member of: a defect of the member builder, never a fact about the game.

    The concrete state that reached the key is itself an item of the key, so the key has a member. With none, the key would keep only the
    restart, and its value, and every value that leans on it, would sit above the exact cost: a bound that a cut would trust (OR-12, OR-13).
    """
    return OutOfScopeError(
        f"the crafted-pattern bound reached a key it can make no member of (status {[int(v) for v in key.status]}, {len(key.crafted)} crafted, "
        f"counts {key.counts}, tags {key.tags}, rarity {key.flags.rarity.value}, {len(key.fractured)} fractured). That is a defect of the member "
        "builder, since the state that reached the key is a member of it; its value would sit above the exact cost, so the build refuses."
    )


def _gap_everywhere(pattern: Pattern, memo: dict, key: PatternKey, offer: PatternOffer) -> bool:
    """Whether no member of the key can take the action: each is refused by the game or is a model gap.

    Then the exact model has no action at any state of the key either (a gap makes it unavailable, as the walk and the planner do), so leaving
    it out of the key is what the exact model does. If one member can take it, a gap at the member that was asked may not be left out.
    """
    found = memo.get((key, id(offer)))
    if found is None:
        found = True
        for member in pattern.members(key, Mode.ALL):
            try:
                pattern.ab.kernel_key(member, offer.action)
            except (NotApplicableError, OutOfScopeError):
                continue
            found = False
            break
        memo[(key, id(offer))] = found
    return found


def _gap(offer: PatternOffer, key: PatternKey, gap: Exception) -> OutOfScopeError:
    """The refusal of a build that met a model gap at a member: the action cannot be dropped from the key without risking a bound above the exact cost."""
    return OutOfScopeError(
        f"{offer.label} raised a model gap at a member of a key (status {[int(v) for v in key.status]}, {len(key.crafted)} crafted, "
        f"counts {key.counts}) while another member of the key can take it: {gap}. The crafted-pattern bound cannot drop the action from the "
        "key (the exact model drops it only where the gap is), so it refuses the route instead of returning a bound that may be above the "
        "exact cost (OR-12, OR-13)."
    )


def _kernel_id(ids: dict[tuple, int], kernels: list, pushed: dict[int, Fraction]) -> int:
    """The id of a pushed kernel (successor keys with integer weights, gcd-reduced), interned."""
    items = sorted(pushed.items())
    common = lcm(*(chance.denominator for _, chance in items))
    weights = [chance.numerator * (common // chance.denominator) for _, chance in items]
    divisor = reduce(gcd, weights)
    entry = (tuple(k for k, _ in items), tuple(w // divisor for w in weights))
    found = ids.get(entry)
    if found is None:
        found = ids[entry] = len(kernels)
        kernels.append(entry)
    return found


__all__ = ["Mode", "Pattern", "PatternBuilder", "PatternKey", "PatternModel", "PatternOffer", "PatternStats", "build_pattern_model"]
