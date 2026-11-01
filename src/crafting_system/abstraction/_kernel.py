"""The abstraction of one base at one item level: compression, family types, the cached kernels."""

import math
from collections import Counter, defaultdict, deque
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from operator import attrgetter

from crafting_system.actions import (
    Action,
    ActionError,
    ActionOutcomes,
    Fixed,
    Fractured,
    Outcomes,
    OutOfScopeError,
    build_pool,
)
from crafting_system.data import GameData, Mod
from crafting_system.items import ExplicitMod, Item, ItemError, Rarity, Side, tier_table

from ._goal import Goal, Status
from ._kinds import Kinds, held_families
from ._state import CompressedState, Flags, FracturedMod, Slot, best_of, status_of

Label = Hashable  # the contribution to every leaf as ints; with junk slots kept, also the side and the kind
FamilyType = tuple[Side, tuple[tuple[Label, Fraction, bool], ...]]
ONE = Fraction(1)
_SLOT_KEY = attrgetter("key")
Expanded = tuple[tuple[tuple[Status, ...], tuple[Slot, ...], Fraction], ...]  # (best of the new mods, the slots they add, chance)


class _Signature(tuple):
    """A pool signature that remembers its hash: nested tuples of Fractions are slow to hash, and it keys every cache lookup."""

    def __hash__(self) -> int:
        try:
            return self._hash  # type: ignore[attr-defined]
        except AttributeError:
            self._hash = value = tuple.__hash__(self)
            return value


@dataclass(frozen=True)
class CacheStats:
    """How the kernel cache was used: `kernels` distinct signatures computed, `hits` requests served by one."""

    kernels: int
    hits: int


def integer_weights(kernel: Mapping[CompressedState, Fraction]) -> dict[CompressedState, int]:
    """The kernel as integers proportional to its probabilities, with no common factor."""
    if not kernel:
        return {}
    chances = [(state, chance.numerator, chance.denominator) for state, chance in kernel.items()]
    common = math.lcm(*(denominator for _, _, denominator in chances))
    scaled = {state: numerator * (common // denominator) for state, numerator, denominator in chances}
    divisor = reduce(math.gcd, scaled.values())
    return {state: weight // divisor for state, weight in scaled.items()}


def _low_values(mod: Mod) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in mod.stats)


Origins = dict[tuple[str, bool, bool], "FracturedMod | Slot"]  # (mod id, fractured, crafted) of the item given to an action


@dataclass
class _Prepared:
    """What one action says about one state: its outcomes, where each mod of the item given to it came from, its pool signatures."""

    outcomes: ActionOutcomes
    origins: Origins
    signatures: tuple[Hashable, ...] | None = None
    splits: "tuple[_Split, ...] | None" = None  # the split of every part, read once for `kernel` and `kernel_key`


@dataclass(frozen=True)
class _Split:
    """A part's retained item read back into state terms: the fractured mods and slots it keeps, the new ones, the flags."""

    flags: Flags
    fractured: tuple[FracturedMod, ...]
    kept: tuple[Slot, ...]  # slots of mods the item already had
    new: tuple[Slot, ...]  # slots of mods the action put on it (stored: crafted ones, and every one when junk is kept)
    status: tuple[Status, ...]  # what the mods that stay give each leaf
    new_ids: tuple[str, ...]  # ids of the new mods, in the order of the retained item


class Abstraction:
    """Design D for one base and item level: compress items, and get the exact kernel of an action.

    `actions` are the enabled actions that read the mods besides the fractured ones (`Action.reads`);
    an action that reads none of them is always known. They decide what a state keeps of the mods that
    are not fractured: with none that reads them (the default) only the crafted mods are kept; with
    one, every such mod is a slot of its side and kind (see `Kinds`). `kernel` refuses an action that
    reads them and is not enabled.

    The kernel of a random action is cached by pool signature: two states whose pools have the same
    multiset of family types share one label distribution.
    """

    def __init__(self, data: GameData, goal: Goal, base_id: str, item_level: int, actions: Iterable = ()):
        self.data = data
        self.goal = goal
        self.base_id = base_id
        self.item_level = item_level
        self._tiers = tier_table(data, base_id)
        self._kinds = Kinds(data, base_id, item_level, actions, self._profile)
        self._labels: dict[str, Label] = {}
        self._canonical_group: dict[tuple, list[Mod]] | None = None
        self._canonical: dict[tuple[str, tuple[Status, ...], bool], str] = {}
        self._prepared_by: dict[Hashable, _Prepared] = {}
        self._cache: dict[Hashable, dict[Hashable, Fraction]] = {}
        self._expanded: dict[Hashable, Expanded] = {}
        self._signatures: dict[Hashable, Hashable] = {}  # one object per equal pool signature, so a lookup by it is an identity hit
        self._drawn_slots: dict[tuple, Slot] = {}
        self._drawn_best: dict[tuple, tuple[Status, ...]] = {}
        self._fractures: dict[Hashable, tuple[tuple[Hashable, Fraction], ...]] = {}
        self._kernels = 0
        self._hits = 0

    @property
    def keeps_junk(self) -> bool:
        """Whether a state stores the ordinary mods that are not fractured (an enabled action reads them)."""
        return self._kinds.tracked

    @property
    def stats(self) -> CacheStats:
        """How many label distributions were computed and how many requests reused one."""
        return CacheStats(self._kernels, self._hits)

    @property
    def enabled(self) -> tuple[Action, ...]:
        """The enabled actions that read the ordinary mods (the ones `actions` of the constructor named)."""
        return self._kinds.actions

    def kind_of(self, mod: Mod) -> str:
        """The kind a slot of the ordinary mod `mod` gets: `ALIKE` ("") or its family key."""
        return self._kinds.of(mod)

    def crafted_slot(self, mod_id: str) -> Slot:
        """The slot a crafted mod of this id makes (its canonical id, its contribution, low rolls)."""
        return self._slot_of(ExplicitMod(mod_id, self._tiers.get(mod_id, 1), _low_values(self.data.mods[mod_id]), crafted=True))

    def compress(self, item: Item) -> CompressedState:
        """The compressed state of a concrete item.

        Raises `ValueError` for an item of another base or item level than this abstraction's.
        """
        if item.base_id != self.base_id or item.item_level != self.item_level:
            raise ValueError(
                f"item on {item.base_id} at level {item.item_level} does not fit an abstraction "
                f"of {self.base_id} at level {self.item_level}"
            )
        fractured = sorted(
            (FracturedMod(self._canonical_id(entry), self._contribution(entry)) for entry in item.fractured_mods),
            key=lambda entry: (entry.mod_id, entry.contribution),
        )
        status = best_of(
            len(self.goal.leaves), (self._contribution(entry) for entry in item.mods)
        )
        slots = sorted(
            (
                self._slot_of(entry)
                for entry in item.mods
                if not entry.fractured and (entry.crafted or self._kinds.tracked)
            ),
            key=lambda slot: slot.key,
        )
        flags = Flags(item.rarity, item.corrupted, item.influences)
        return CompressedState(flags, tuple(fractured), status, tuple(slots))

    def is_goal(self, state: CompressedState) -> bool:
        """Whether the status of `state` meets the goal."""
        return self.goal.is_met(state.status)

    def kernel(self, state: CompressedState, action: Action) -> Mapping[CompressedState, Fraction]:
        """The exact distribution of the next compressed state after `action` on `state`.

        Raises what the action raises for the item the state stands for (`NotApplicableError`,
        `OutOfScopeError`), `OutOfScopeError` for a roll limit on a mod the action draws, forces or
        crafts, and `ValueError` for a state of another goal and for an action that reads the mods
        besides the fractured ones and was not enabled.
        """
        if len(state.status) != len(self.goal.leaves):
            raise ValueError(
                f"the state has {len(state.status)} statuses but the goal has {len(self.goal.leaves)} leaves: "
                "it comes from another abstraction"
            )
        self._check_enabled(action)
        return self._mixture_kernel(state, self._prepared(state, action))

    def kernel_key(self, state: CompressedState, action: Action) -> Hashable:
        """A key of the kernel of `action` on `state`, cheaper than the kernel: equal keys, equal kernels.

        `kernel_key(state, a) == kernel_key(state, b)` implies `kernel(state, a) == kernel(state, b)`
        exactly (the converse does not hold: two kernels can be equal under different keys), so of the
        actions that share a key at a state only one needs offering. It builds no state and no integer
        weights, which is where the time of `kernel` goes; it makes the same checks (state width,
        enabled, a fixed result that fractures) and raises what `kernel` raises before the distribution.

        What the kernel reads is, per part of the outcomes, its probability `share`, its pool signature
        (the cached label distribution; `("fixed",)` for a fixed result) and its split (flags, fractured
        mods, kept and new slots, the status of the mods that stay); parts add up in a dict, so their
        order does not matter and equal parts count (a multiset). Not in it: the `state` itself (the
        kernel reads it only through the item given to the action, which the splits already carry),
        and `_Split.new_ids`, which only names the new mods (the forced mods of two essences can differ
        in id and give one kernel). A result that FRACTURES also reads the pool of each part (the
        fractured mod is spread over its families; `_add_fractured`) and the forced mod, so for such a
        part the key adds `part.forced` and the families of the pool with their mod ids and weights.
        """
        if len(state.status) != len(self.goal.leaves):
            raise ValueError(
                f"the state has {len(state.status)} statuses but the goal has {len(self.goal.leaves)} leaves: "
                "it comes from another abstraction"
            )
        self._check_enabled(action)
        prepared = self._prepared(state, action)
        outcomes = prepared.outcomes
        if outcomes.fractures and any(isinstance(part, Fixed) for _, part in outcomes.components):
            raise ValueError("a fixed result cannot fracture a mod: only pool draws do (a Fractured Fossil's)")
        parts: Counter = Counter()
        for (share, part), signature, split in zip(
            outcomes.components, self._signatures_of(prepared), self._splits_of(prepared)
        ):
            key = (share, signature, split.flags, split.fractured, split.kept, split.new, split.status)
            if outcomes.fractures:
                pool = tuple(
                    (family.family, tuple((entry.mod.id, entry.weight) for entry in family.mods))
                    for family in part.pool
                )
                key = (*key, part.forced, pool)
            parts[key] += 1
        return (outcomes.fractures, frozenset(parts.items()))

    def _check_enabled(self, action: Action) -> None:
        if self._kinds.reads_junk(action) and action not in self._kinds.actions:
            raise ValueError(f"{action!r} reads the mods of the item and is not among the enabled actions")

    def signature(self, state: CompressedState, action: Action) -> Hashable:
        """What decides the label distribution: equal signatures share one cached distribution.

        It is `(tag, kept mods, free prefixes, free suffixes, totals, sorted family types of the pool)`
        for a random action. A resonator with one pool and no Fractured Fossil has the signature of that
        pool, so it shares its distribution with any other action of an equal pool (a Chaos Orb, a set
        whose fossils change no weight of this item); a mixture (Tangled, Glyphic) or a Fractured Fossil
        has `("fossils", fractures, the parts)`, each part its probability and the signature of its
        pool, with the label of its forced mod when a mod is fractured. An action with a fixed result
        (a bench craft) draws nothing and has no cache: its signature is `("fixed", action)`, which
        names the action and does not decide its kernel.

        The forced mod of an essence is not in it: it is a kept mod, so the pool already leaves out its
        family, the kept count and the free slots already count it, and it cannot change the draw.
        """
        self._check_enabled(action)
        prepared = self._prepared(state, action)
        outcomes = prepared.outcomes
        if all(isinstance(part, Fixed) for _, part in outcomes.components):
            return ("fixed", action)
        if outcomes.fractures and any(isinstance(part, Fixed) for _, part in outcomes.components):
            raise ValueError("a fixed result cannot fracture a mod: only pool draws do (a Fractured Fossil's)")
        signatures = self._signatures_of(prepared)
        if len(signatures) == 1 and not outcomes.fractures:
            return signatures[0]
        parts = Counter(
            (share, signature, self._forced_label(part) if outcomes.fractures else None)
            for (share, part), signature in zip(outcomes.components, signatures)
        )
        return ("fossils", outcomes.fractures, frozenset(parts.items()))

    def reachable(self, starts: Iterable[CompressedState], actions: Iterable[Action]) -> frozenset[CompressedState]:
        """Every state reachable from `starts` by any of `actions`, the starts included.

        An action that refuses a state (`ActionError`) is skipped there.
        """
        actions = tuple(actions)
        seen = set(starts)
        queue = deque(seen)
        while queue:
            state = queue.popleft()
            for action in actions:
                try:
                    successors = self.kernel(state, action)
                except ActionError:
                    continue
                for successor in successors:
                    if successor not in seen:
                        seen.add(successor)
                        queue.append(successor)
        return frozenset(seen)

    def estimate(self, starts: Iterable[CompressedState], actions: Iterable[Action], **options):
        """How big the graph of `actions` from `starts` is, without building it (`Estimate`, ADR-0023).

        Equal to what `reachable` and the kernels would give (goals not expanded); see `_estimate.py`. Raises
        `EstimateRefused` for an action the count has no rule for.
        """
        from ._estimate import estimate

        return estimate(self, starts, actions, **options)

    def family_types(
        self, tag: str | None = None, fossils: Action | None = None
    ) -> Mapping[FamilyType, tuple[str, ...]]:
        """The families of the full pool of an empty rare item of this base and level, by family type.

        `tag` is the guaranteed tag of a Harvest reforge or None. With `fossils`, an action that
        reweighs the pool (a resonator), the pool is the one it makes: the weights carry the factors and
        blocks of its fossils, so families that no fossil of the set tells apart share a type (a mixture,
        Tangled or Glyphic, has no one pool: `ValueError`). The value is the sorted family ids.
        """
        empty = Item.build(self.data, base_id=self.base_id, item_level=self.item_level, rarity=Rarity.RARE)
        pool = build_pool(self.data, empty)
        if fossils is not None:
            (_, part), *others = fossils.outcomes(self.data, empty).components
            if others:
                raise ValueError(f"{fossils!r} is a mixture of pools: it has no one set of family types")
            pool = part.pool
        grouped: dict[FamilyType, list[str]] = defaultdict(list)
        for family in pool:
            grouped[self._family_type(family, tag)].append(family.family)
        return {kind: tuple(sorted(names)) for kind, names in grouped.items()}

    def _contribution(self, entry: ExplicitMod) -> tuple[Status, ...]:
        return tuple(
            status_of(leaf, entry.mod_id, entry.tier, entry.values, entry.crafted)
            for leaf in self.goal.leaves
        )

    def _drawn_contribution(self, mod: Mod, crafted: bool = False) -> tuple[Status, ...]:
        """What `mod` gives each leaf when an action draws, forces or crafts it: its table tier, low rolls."""
        tier = self._tiers.get(mod.id, 1)
        return tuple(
            status_of(leaf, mod.id, tier, _low_values(mod), crafted) for leaf in self.goal.leaves
        )

    def passes(self, mod: Mod, leaf: int) -> bool:
        """Whether `mod`, drawn by an action (its table tier, low rolls), gives leaf number `leaf` the status PASSING."""
        return self._drawn_contribution(mod)[leaf] is Status.PASSING

    def _profile(self, mod: Mod) -> tuple[int, ...]:
        """What `mod` gives each leaf as ints: the part of a family type that the goal decides."""
        return tuple(int(status) for status in self._drawn_contribution(mod))

    def _guard_roll(self, mod: Mod) -> None:
        """Raise `OutOfScopeError` when a leaf names `mod` and limits its roll: a rolled value is not modelled yet."""
        for leaf in self.goal.leaves:
            if mod.id in leaf.mod_ids and leaf.has_roll_limit:
                raise OutOfScopeError(
                    f"a roll limit on a drawn, forced or crafted mod is not modelled yet (mod {mod.id})"
                )

    def _label(self, mod: Mod) -> Label:
        """The label of a drawn mod: its contribution to every leaf, as ints; with junk slots kept, also its side and kind.

        Raises `OutOfScopeError` when a leaf names the mod and limits its roll.
        """
        label = self._labels.get(mod.id)
        if label is None:
            self._guard_roll(mod)
            ints = tuple(int(status) for status in self._drawn_contribution(mod))
            label = (ints, mod.generation_type, self._kinds.of(mod)) if self._kinds.tracked else ints
            self._labels[mod.id] = label
        return label

    def _slot_of(self, entry: ExplicitMod) -> Slot:
        """The slot of a mod of a concrete item that is not fractured."""
        mod = self.data.mods[entry.mod_id]
        side, contribution = Side(mod.generation_type), self._contribution(entry)
        if entry.crafted:
            return Slot(side, self._canonical_id(entry), contribution, True)
        return Slot(side, self._kinds.of(mod), contribution)

    def _canonical_id(self, entry: ExplicitMod) -> str:
        """The smallest id among the mods of the same families, side and domain that give the same contribution."""
        contribution = self._contribution(entry)
        key = (entry.mod_id, contribution, entry.crafted)
        found = self._canonical.get(key)
        if found is None:
            if self._canonical_group is None:
                groups: dict[tuple, list[Mod]] = defaultdict(list)
                for mod in self.data.mods.values():
                    groups[(mod.families, mod.generation_type, mod.domain)].append(mod)
                self._canonical_group = groups
            own = self.data.mods[entry.mod_id]
            group = self._canonical_group[(own.families, own.generation_type, own.domain)]
            matching = [mod.id for mod in group if self._drawn_contribution(mod, entry.crafted) == contribution]
            found = min(matching) if matching else min(mod.id for mod in group)
            self._canonical[key] = found
        return found

    def _item_of(self, state: CompressedState, erasing: bool) -> tuple[Item, Origins]:
        """A concrete item the state stands for: its fractured mods, its crafted mods, and (unless
        the action erases them) one representative mod for every other slot, of distinct families.
        With it, where each of its mods came from (a fractured mod or a slot of the state).

        Raises `ItemError` when the state is not an item (a normal item with mods) and `ValueError`
        when it holds more mods of a kind than the base has families.
        """
        flags = state.flags
        origins: Origins = {}
        mods = []
        for entry in state.fractured:
            mods.append(
                ExplicitMod(
                    entry.mod_id,
                    self._tiers.get(entry.mod_id, 1),
                    _low_values(self.data.mods[entry.mod_id]),
                    fractured=True,
                )
            )
            origins[(entry.mod_id, True, False)] = entry
        taken = {family for entry in state.fractured for family in held_families(self.data.mods[entry.mod_id])}
        for slot in state.slots:
            if slot.crafted:
                mod = self.data.mods[slot.kind]
                taken |= held_families(mod)
                mods.append(ExplicitMod(mod.id, self._tiers.get(mod.id, 1), _low_values(mod), crafted=True))
                origins[(mod.id, False, True)] = slot
        if not erasing:
            for slot in state.slots:
                if not slot.crafted:
                    mod = self._kinds.representative(slot.side, slot.kind, taken)
                    mods.append(ExplicitMod(mod.id, self._tiers.get(mod.id, 1), _low_values(mod)))
                    origins[(mod.id, False, False)] = slot
        item = Item.build(
            self.data,
            base_id=self.base_id,
            item_level=self.item_level,
            rarity=flags.rarity,
            influences=flags.influences,
            corrupted=flags.corrupted,
            mods=tuple(mods),
        )
        return item, origins

    def _prepared(self, state: CompressedState, action: Action) -> _Prepared:
        """The outcomes of `action` on the item `state` stands for (cached), and where that item's mods came from."""
        erasing = not self._kinds.reads_junk(action)
        slots = tuple(slot for slot in state.slots if slot.crafted) if erasing else state.slots
        key = (action, state.flags, state.fractured, slots)
        prepared = self._prepared_by.get(key)
        if prepared is None:
            try:
                item, origins = self._item_of(state, erasing)
            except ItemError:
                bare = Item.build(
                    self.data,
                    base_id=self.base_id,
                    item_level=self.item_level,
                    rarity=state.flags.rarity,
                    influences=state.flags.influences,
                    corrupted=state.flags.corrupted,
                )
                action.outcomes(self.data, bare)
                raise
            prepared = _Prepared(action.outcomes(self.data, item), origins)
            self._prepared_by[key] = prepared
        return prepared

    def _mixture_kernel(self, state: CompressedState, prepared: _Prepared) -> dict[CompressedState, Fraction]:
        """The kernel of a result that is a mixture of parts: each part gives its states, weighted by its probability.

        A part is a fixed result (the mods that stay, the new ones) or a pool draw (the same, then the
        new draws seen through the label); with a fracture one finished mod also becomes fractured.
        """
        outcomes = prepared.outcomes
        if outcomes.fractures and any(isinstance(part, Fixed) for _, part in outcomes.components):
            raise ValueError("a fixed result cannot fracture a mod: only pool draws do (a Fractured Fossil's)")
        signatures = self._signatures_of(prepared)
        result: dict[CompressedState, Fraction] = defaultdict(Fraction)
        for (share, part), signature, split in zip(outcomes.components, signatures, self._splits_of(prepared)):
            if isinstance(part, Fixed):
                self._add_fixed(result, share, split)
            elif outcomes.fractures:
                self._add_fractured(result, share, state, part, signature, split)
            else:
                self._add_drawn(result, share, part, signature, split)
        return dict(result)

    def _splits_of(self, prepared: _Prepared) -> tuple[_Split, ...]:
        """The split of every part of the outcomes (cached on `prepared`)."""
        if prepared.splits is None:
            prepared.splits = tuple(
                self._split(part.retained, prepared.origins) for _, part in prepared.outcomes.components
            )
        return prepared.splits

    def _split(self, retained: Item, origins: Origins) -> _Split:
        """Read a part's retained item back into state terms.

        A mod the item given to the action held is the fractured mod or slot it came from; any other mod
        is new: its contribution is that of its table tier at low rolls, and it is a slot when it is
        crafted or when junk is kept. Raises `OutOfScopeError` for a new mod a leaf limits the roll of.
        """
        flags = Flags(retained.rarity, retained.corrupted, retained.influences)
        fractured: list[FracturedMod] = []
        kept: list[Slot] = []
        new: list[Slot] = []
        new_ids: list[str] = []
        contributions: list[tuple[Status, ...]] = []
        for entry in retained.mods:
            origin = origins.get((entry.mod_id, entry.fractured, entry.crafted))
            if isinstance(origin, FracturedMod):
                fractured.append(origin)
                contributions.append(origin.contribution)
            elif isinstance(origin, Slot):
                kept.append(origin)
                contributions.append(origin.contribution)
            else:
                mod = self.data.mods[entry.mod_id]
                self._guard_roll(mod)
                contribution = self._drawn_contribution(mod, entry.crafted)
                contributions.append(contribution)
                new_ids.append(mod.id)
                if entry.fractured:
                    fractured.append(FracturedMod(self._canonical_of_mod(mod), contribution))
                elif entry.crafted:
                    new.append(Slot(Side(mod.generation_type), self._canonical_id(entry), contribution, True))
                elif self._kinds.tracked:
                    new.append(Slot(Side(mod.generation_type), self._kinds.of(mod), contribution))
        fractured.sort(key=lambda entry: (entry.mod_id, entry.contribution))
        status = best_of(len(self.goal.leaves), contributions)
        return _Split(flags, tuple(fractured), tuple(kept), tuple(new), status, tuple(new_ids))

    def _add_fixed(self, result: dict[CompressedState, Fraction], share: Fraction, split: _Split) -> None:
        """Add the one state of a fixed result."""
        slots = sorted((*split.kept, *split.new), key=lambda slot: slot.key)
        result[CompressedState(split.flags, split.fractured, split.status, tuple(slots))] += share

    def _add_drawn(
        self, result: dict[CompressedState, Fraction], share: Fraction, part: Outcomes, signature, split: _Split
    ) -> None:
        """Add the states of one pool: what stays, the forced mod and the new draws (slots when junk is kept).

        What the draws add does not depend on the state, only on the signature, so `_expanded_distribution`
        has it ready (the status and the sorted slots of each outcome); per state this merges it with
        the mods that stay.
        """
        stays = sorted((*split.kept, *split.new), key=_SLOT_KEY)
        stays_tuple = tuple(stays)
        flags, fractured, stay_status = split.flags, split.fractured, split.status
        whole = share == 1
        for best, drawn, chance in self._expanded_distribution(signature, part):
            if not drawn:
                slots = stays_tuple
            elif not stays:
                slots = drawn
            else:
                slots = tuple(sorted(stays + list(drawn), key=_SLOT_KEY))
            state = CompressedState(flags, fractured, tuple(map(max, stay_status, best)), slots)
            weight = chance if whole else share * chance
            before = result.get(state)
            result[state] = weight if before is None else before + weight

    def _add_fractured(
        self,
        result: dict[CompressedState, Fraction],
        share: Fraction,
        state: CompressedState,
        part: Outcomes,
        signature,
        split: _Split,
    ) -> None:
        """Add the states of one pool of a result that fractures one finished mod (a Fractured Fossil's).

        One finished mod is fractured, uniformly. The distribution of the pair (the fractured mod, the
        rest) is cached by pool signature at the level of family types (see `_fracture_entries`); here
        each type is spread over the families of this pool that have it, the fractured mod being any of
        them with the same chance.
        """
        families: dict[FamilyType, list] = defaultdict(list)
        for family in part.pool:
            families[self._family_type(family, None)].append(family)
        for (kind, family_type, label, best, rest), chance in self._fracture_entries(part, signature):
            if kind == "none":
                options = [(None, chance)]
            elif kind == "forced":
                options = [(self.data.mods[part.forced], chance)]
            else:
                members = families[family_type]
                options = [(self._mod_with_label(family, label), chance / len(members)) for family in members]
            status = tuple(max(a, b) for a, b in zip(split.status, best))
            slots = [*split.kept] if kind == "forced" else [*split.kept, *split.new]
            if rest is not None:
                slots += [
                    Slot(Side(side), slot_kind, tuple(Status(value) for value in ints))
                    for (ints, side, slot_kind), count in rest
                    for _ in range(count)
                ]
            slots.sort(key=lambda slot: slot.key)
            for mod, each in options:
                fractured = split.fractured
                if mod is not None:
                    entry = FracturedMod(self._canonical_of_mod(mod), self._drawn_contribution(mod))
                    fractured = tuple(sorted((*fractured, entry), key=lambda e: (e.mod_id, e.contribution)))
                result[CompressedState(split.flags, fractured, status, tuple(slots))] += share * each

    def _mod_with_label(self, family, label: Label) -> Mod:
        """A mod of `family` with the label `label`: the mods of one family that share a label share a canonical id."""
        for entry in family.mods:
            if self._label(entry.mod) == label:
                return entry.mod
        raise ValueError(f"the family {family.family} has no mod labelled {label!r}")

    def _canonical_of_mod(self, mod: Mod) -> str:
        """The canonical id of `mod` as a fractured mod, at its table tier and low rolls."""
        return self._canonical_id(
            ExplicitMod(mod.id, self._tiers.get(mod.id, 1), _low_values(mod), fractured=True)
        )

    def _forced_label(self, part: Outcomes) -> Label | None:
        return None if part.forced is None else self._label(self.data.mods[part.forced])

    def _fracture_entries(self, part: Outcomes, signature: Hashable) -> tuple[tuple[Hashable, Fraction], ...]:
        """How a Fractured Fossil splits the finished item of one pool, cached by pool signature.

        Each entry is `((kind, family type, label, best, rest), probability)` where `kind` says what was
        fractured: "none" (the item has no mod), "forced" (the forced mod) or "pool" (a drawn mod of the
        given family type and label); `best` is what the finished mods give each leaf (the fractured one
        included) and `rest`, with junk kept, the other drawn mods as `(label, count)` pairs (None
        otherwise). The probability of a "pool" entry is that of all the families of the type together:
        families of one type are interchangeable in the draw, so each is the fractured one with an equal
        share (`_add_fractured` divides). It takes one run of the exact engine for each family type, with
        that type's mods marked in the label.
        """
        key = (signature, self._forced_label(part))
        found = self._fractures.get(key)
        if found is not None:
            self._hits += 1
            return found
        owner: dict[str, FamilyType] = {}
        for family in part.pool:
            family_type = self._family_type(family, None)
            for entry in family.mods:
                owner[entry.mod.id] = family_type
        types = list(dict.fromkeys(owner.values())) or [None]
        single = part.fracturing()
        merged: dict[Hashable, Fraction] = defaultdict(Fraction)
        for number, marked in enumerate(types):

            def label(mod: Mod, marked=marked) -> Label:
                mark = "forced" if mod.id == part.forced else "type" if owner.get(mod.id) == marked else ""
                return (self._label(mod), mark)

            for outcome, chance in single.distribution(label).items():
                split = self._split_fractured(outcome, first=number == 0)
                if split is not None:
                    kind, fractured_label, best, rest = split
                    merged[(kind, marked if kind == "pool" else None, fractured_label, best, rest)] += chance
        entries = tuple(merged.items())
        self._fractures[key] = entries
        self._kernels += 1
        return entries

    def _split_fractured(self, outcome, *, first: bool):
        """One outcome of the marked run as `(kind, label of the fractured mod, best, rest)`, or None to skip it.

        The run that marks a type reports only the mods of that type as fractured ("pool"); the item
        without a mod and the forced mod are the same in every run, so only the `first` takes them.
        """
        counts: Counter = Counter()
        chosen = None
        for found, count in outcome:
            if isinstance(found, Fractured):
                chosen = found.label
            else:
                counts[found[0]] += count
        if chosen is None:
            kind = "none"
        elif chosen[1] == "forced":
            kind = "forced"
        elif chosen[1] == "type":
            kind = "pool"
        else:
            return None
        if kind != "pool" and not first:
            return None
        ints = (lambda label: label[0]) if self._kinds.tracked else (lambda label: label)
        best = best_of(len(self.goal.leaves), (ints(label) for label in counts))
        fractured_label = None if chosen is None else chosen[0]
        rest = None
        if self._kinds.tracked:
            if kind == "pool":
                counts[fractured_label] -= 1
            rest = frozenset((label, count) for label, count in counts.items() if count > 0)
        return kind, fractured_label, best, rest

    def _family_type(self, family, tag: str | None) -> FamilyType:
        return (
            family.side,
            tuple(
                sorted(
                    (self._label(entry.mod), entry.weight, tag is not None and tag in entry.mod.implicit_tags)
                    for entry in family.mods
                )
            ),
        )

    def _signatures_of(self, prepared: _Prepared) -> tuple[Hashable, ...]:
        """The signature of every part of the outcomes (one, unless the action is a mixture)."""
        if prepared.signatures is None:
            prepared.signatures = tuple(
                ("fixed",) if isinstance(part, Fixed) else self._pool_signature(part)
                for _, part in prepared.outcomes.components
            )
        return prepared.signatures

    def _pool_signature(self, part: Outcomes) -> Hashable:
        free = part.free
        signature = _Signature(
            (
                part.tag,
                len(part.retained.mods),
                free[Side.PREFIX],
                free[Side.SUFFIX],
                tuple(sorted(part.totals.items())),
                tuple(sorted(self._family_type(family, part.tag) for family in part.pool)),
            )
        )
        return self._signatures.setdefault(signature, signature)

    def _expanded_distribution(self, signature: Hashable, part: Outcomes) -> Expanded:
        """`_distribution` read into state terms, cached by signature: `(best, slots, chance)` for each outcome.

        `best` is what the new mods give each leaf (the per-leaf maximum, as `Status`), `slots` the slots
        they add, sorted by `Slot.key` (none when the junk is not kept), `chance` its probability.
        """
        cached = self._expanded.get(signature)
        if cached is not None:
            self._hits += 1
            return cached
        width = len(self.goal.leaves)
        tracked = self._kinds.tracked
        entries = []
        for drawn, chance in self._distribution(signature, part).items():
            if tracked:
                best = best_of(width, (ints for (ints, _, _), _ in drawn))
                slots = sorted(
                    (self._drawn_slot(ints, side, kind) for (ints, side, kind), count in drawn for _ in range(count)),
                    key=_SLOT_KEY,
                )
            else:
                best, slots = tuple(Status(value) for value in drawn), []
            entries.append((self._drawn_best.setdefault(best, best), tuple(slots), chance))
        cached = self._expanded[signature] = tuple(entries)
        return cached

    def _drawn_slot(self, ints: tuple[int, ...], side: str, kind: str) -> Slot:
        """The slot of a new mod with the label `(ints, side, kind)`, one object for all the states."""
        key = (ints, side, kind)
        slot = self._drawn_slots.get(key)
        if slot is None:
            slot = self._drawn_slots[key] = Slot(Side(side), kind, tuple(Status(value) for value in ints))
        return slot

    def _distribution(self, signature: Hashable, part: Outcomes) -> dict[Hashable, Fraction]:
        """The probability of what the new mods give, cached by signature.

        The key is the best label per leaf among the new mods; with junk slots kept it is the whole
        outcome, the set of `(label, how many new mods got it)`.
        """
        cached = self._cache.get(signature)
        if cached is not None:
            self._hits += 1
            return cached
        width = len(self.goal.leaves)
        merged: dict[Hashable, Fraction] = defaultdict(Fraction)
        for outcome, chance in part.distribution(self._label).items():
            if self._kinds.tracked:
                merged[outcome] += chance
            else:
                merged[tuple(best_of(width, (label for label, _ in outcome)))] += chance
        cached = dict(merged)
        self._cache[signature] = cached
        self._kernels += 1
        return cached
