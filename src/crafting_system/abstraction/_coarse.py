"""The coarse state: pools of junk kinds, with variant kernels for additions (ADR-0023, tickets #125 and #172).

A `Coarsening` of an `Abstraction` pools junk families that no requirement cares about. The exact state
tells a junk family apart by its **kind**: its own name when an enabled action would clash with it, the
family type `~n` (side, and the weights and goal profile of its mods) when an adding action is enabled,
and "" when every enabled action treats it like any other of its side. A coarse state renames the kind of
every pooled family to its pool, so the exact states that differ only in which pooled family a slot holds
become one **block** (a `CompressedState` whose pooled slots have the kind of their pool). `coarsen(state)`
is that map.

A group lists families by name; a block pools them per side, so the pool of a side is the families of the
group that sit on that side (`k` of them). A pool is made of kinds: a told-apart family is a kind of its
own, and a family type `~n` is one kind with all its families, so a group that lists one family of a type
must list every family of that type on that side (`ValueError` otherwise). A crafted mod with no requirement
and one family that is pooled is pooled with it (its slot keeps `crafted=True`). Never pooled, and so held
exactly by every member of a block: a family a requirement names, a mod with several families (a hybrid junk
mod keeps its family key as kind, a hybrid crafted mod its canonical id), a fractured mod, a crafted mod
that is not pooled, and a family whose kind is "". With `H` the families of a pool that these hold, the
members of a block with `n` pooled slots in the pool are the ways to put the slots on `n` distinct families
of the pool outside `H` (a pooled crafted slot on a family that has a crafted mod).

The kernels. `kernel(block, action, bound)` is the exact kernel of the action on a member, pushed through
`coarsen`. It is defined per member and for two kinds of action:

* an action that declares `Reads.block_invariant` (an erasing reroll, a bench craft, Remove Crafted Mods,
  Annulment): its pushed kernel is the same on every member where it is legal. What differs between members
  is legality: the `"lower"` (optimistic) model offers the action when some member can take it, the
  `"upper"` (pessimistic) model only when every member can. Legality is read from the action itself, by
  running it on one representative member of each way the families it reads (`Reads.families`) can be
  held: for a craft of family `phi` in a pool of `k` with `n` pooled slots and `H` held, that is legal in the
  lower model if `n <= k - |H| - 1`, in the upper only if `n = 0`, and in neither if `phi` is in `H`.
* an action that declares `Reads.variants` (an addition that keeps the mods: Augmentation, Regal, Exalted):
  its kernel depends on the member through the pool weight its pooled families hold, as a linear-fractional
  function, so the best and the worst backup over the members are reached at the members that put the slots
  of each pool on its lightest or on its heaviest free families. `variants(block, action, bound)` is the
  tuple of the distinct pushed kernels of those up to `2^p` members (`p` the pools that hold slots) that can
  take the action: the optimistic model takes the cheapest of them, the pessimistic the dearest. The legality
  is that of the extreme members (the lower model offers the action if one can take it, the upper only if all
  can). `kernel` of such an action is the single kernel when the variants are one, and raises `ValueError`
  otherwise.

Any other action raises `OutOfScopeError`. The crafted mods that a block can pool are those the data lists
with the domain `crafted` and one family (a method that adds a crafted mod of another domain is not pooled:
its slot stays exact). One `Coarsening` keeps a one-entry cache and is not for two threads.

Soundness needs the members to contain every exact state that maps to the block, which they do (a
member that no route can reach only makes the lower model offer more and the upper offer less).
`tests/test_abstraction_coarse.py`, `tests/test_abstraction_variants.py` and the contract suite compare
every member of every block of the fixtures with the brute force; `tests/test_abstraction_variants_real.py`
does it for the extremes claim on the real Hunter Thicket Bow pools.
"""

from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from itertools import combinations, product
from typing import Literal

from crafting_system.actions import BLOCKING, Action, ActionError, OutOfScopeError, build_pool
from crafting_system.items import Influence, Item, Rarity, Side

from ._kernel import Abstraction
from ._kinds import ALIKE, TYPE_PREFIX, base_kind, held_families
from ._goal import Status
from ._state import CompressedState, Slot

Block = CompressedState
Bound = Literal["lower", "upper"]
POOLED = "="  # a slot kind that starts with this names a pool of families (no family key, mod id or family type "~n" does)


def _slot_key(slot: Slot):
    return slot.key


@dataclass(frozen=True)
class _Pool:
    """The families of one group that sit on one side; the kind of their slots in a block is `kind`."""

    side: Side
    kind: str
    families: tuple[str, ...]


@dataclass(frozen=True)
class _Evaluation:
    """What the members of a block say about an action: the distinct pushed kernels of the legal ones, the first refusal."""

    kernels: tuple[Mapping[Block, Fraction], ...]
    error: ActionError | None


class Coarsening:
    """Pools of an `Abstraction`: the map from states to blocks and the kernels of the two models.

    `groups` lists the families of each group by name (a family name is a `PoolFamily.family`). Raises
    `OutOfScopeError` when an enabled action declares neither block invariance nor variants, reads every
    family, or is declared in a way that cannot be pooled, and `ValueError` for a family that is not told
    apart by the enabled actions (it is already merged by the state, or is not in the pool), that a
    requirement names, that two groups list, or whose family type is only partly in its group.

    `influences` are those of the items the blocks stand for: the families of their influence mods join the
    pool (and, being told apart by name in the state, can be pooled like the rest). The `pooling_*` builders take
    them from the `start` state.
    """

    def __init__(
        self, abstraction: Abstraction, groups: Iterable[Collection[str]] = (), influences: frozenset[Influence] = frozenset()
    ):
        self.abstraction = abstraction
        self.influences = influences
        self._data = abstraction.data
        for action in abstraction.enabled:
            self.require_invariant(action)
        pool = build_pool(
            self._data,
            Item.build(
                self._data, base_id=abstraction.base_id, item_level=abstraction.item_level, rarity=Rarity.RARE, influences=influences
            ),
        )
        self._side_of = {family.family: family.side for family in pool}
        self._weight = {family.family: family.weight for family in pool}  # the pool weight a family takes out when held
        self._kind_of = {family.family: abstraction.kind_of(family.mods[0].mod) for family in pool}
        of_kind: dict[tuple[Side, str], list[str]] = defaultdict(list)
        for name in sorted(self._kind_of):
            of_kind[(self._side_of[name], self._kind_of[name])].append(name)
        self._of_kind = {key: tuple(names) for key, names in of_kind.items()}  # (side, kind) -> its families, by name
        self.told_apart = frozenset(  # a family whose kind is its own name (not "" and not a family type "~n")
            name for name, kind in self._kind_of.items() if kind == name
        )
        self.relevant_families = self._relevant_families()
        self.groups: tuple[frozenset[str], ...] = tuple(frozenset(group) for group in groups)
        self._pools: dict[tuple[Side, str], _Pool] = {}  # (side, kind of a pooled family) -> its pool
        self._pool_of_kind: dict[tuple[Side, str], _Pool] = {}
        self._build_pools()
        self._crafted: dict[tuple[Side, str], Slot] = {}
        self._zero = tuple(Status.ABSENT for _ in abstraction.goal.leaves)
        self._find_crafted_mods()
        self._last: tuple[Block, Action, _Evaluation] | None = None
        self._slots: dict[Slot, Slot] = {}  # the pooled form of every slot seen
        self._rerolls: dict[tuple, _Evaluation] = {}  # an erasing action sees the flags, the fractured and crafted mods only

    @classmethod
    def pooling_irrelevant(
        cls, abstraction: Abstraction, size: int | None = None, start: CompressedState | None = None
    ) -> "Coarsening":
        """Pool every told-apart family that no requirement and no goal-relevant craft cares about.

        The families, sorted by name, are cut into groups of `size` (all in one group when `size` is
        None). A group may list families of both sides; its blocks pool them per side. With the `start`
        state, the families its fractured mods hold are left out: they stay held in every state of a
        route, so no slot is ever pooled on them and they would only take a place in a group.
        """
        if size is not None and size < 1:
            raise ValueError(f"a group needs at least one family, got size {size}")
        influences = start.flags.influences if start is not None else frozenset()
        probe = cls(abstraction, (), influences)
        always_held = probe._held_by_fractured(start) if start is not None else set()
        candidates = sorted(probe.told_apart - probe.relevant_families - always_held)
        if not candidates:
            return probe
        step = len(candidates) if size is None else size
        return cls(abstraction, [candidates[at : at + step] for at in range(0, len(candidates), step)], influences)

    @classmethod
    def pooling_by_spread(
        cls, abstraction: Abstraction, spread: Fraction | float, start: CompressedState | None = None
    ) -> "Coarsening":
        """Pool the junk kinds that no requirement cares about by the weight a family of each takes out of the pool.

        The candidates are the kinds no requirement and no goal-relevant craft cares about (a family type
        with a goal profile holds goal families, so it is not one; the families held by the fractured mods
        of `start` are left out when their kind is the family's own name, and a kind "" is already merged).
        On each side the units are the kinds, a family type being one unit with all its families, sorted by
        the weight of one of its families and then by kind. A pool starts at the lightest unit not yet used
        and takes the following units while their weight differs from the lightest's by at most `spread`;
        a pool of a single unit is not made. One group is a pool, so a group lists families of one side.
        """
        if spread < 0:
            raise ValueError(f"the spread is a weight difference and cannot be negative, got {spread}")
        influences = start.flags.influences if start is not None else frozenset()
        probe = cls(abstraction, (), influences)
        always_held = probe._held_by_fractured(start) if start is not None else set()
        groups: list[set[str]] = []
        for side in Side:
            units = sorted(
                (probe._weight[families[0]], kind, families)
                for (kind_side, kind), families in probe._of_kind.items()
                if kind_side is side
                and kind != ALIKE
                and not probe.relevant_families.intersection(families)
                and (kind.startswith(TYPE_PREFIX) or not always_held.intersection(families))
            )
            first = 0
            while first < len(units):
                last = first + 1
                while last < len(units) and units[last][0] - units[first][0] <= spread:
                    last += 1
                if last - first > 1:
                    groups.append({name for _, _, families in units[first:last] for name in families})
                first = last
        return cls(abstraction, groups, influences)

    # --- which families may be pooled ---------------------------------------------------------------

    def weight_of(self, family: str) -> Fraction:
        """The pool weight of a family: the sum of the weights of its mods in the pool of an empty rare item of the base."""
        return self._weight[family]

    def side_of(self, family: str) -> Side:
        """The side of a family of the pool."""
        return self._side_of[family]

    def _goal_families(self) -> frozenset[str]:
        """The families of the ordinary mods a requirement names: a slot of one gives the goal something, so they are never pooled."""
        mods = self._data.mods
        return frozenset(
            family
            for leaf in self.abstraction.goal.leaves
            for mod_id in leaf.mod_ids
            if mod_id in mods and mods[mod_id].domain != "crafted"
            for family in mods[mod_id].families
        )

    def _relevant_families(self) -> frozenset[str]:
        """The families a requirement names, and those an enabled craft that gives a requirement clashes with."""
        data = self._data
        named = frozenset().union(*(leaf.mod_ids for leaf in self.abstraction.goal.leaves))
        families = set(self._goal_families())
        for action in self.abstraction.enabled:
            reads = action.reads(data)
            if not reads.junk:
                continue
            adds = action.adds(data, None).named
            if adds is None or adds & named:
                families |= reads.families or set()
        return frozenset(families)

    def require_invariant(self, action: Action) -> None:
        """Raise `OutOfScopeError` unless `action` declares `Reads.block_invariant` or `Reads.variants` and names the families it reads.

        A block-invariant action must not read the pool weight (its kernel would follow the families
        held); an action with variants must read it, and name the families it tells apart (none for an addition).
        """
        reads = action.reads(self._data)
        if reads.variants:
            if not (reads.junk and reads.pool_weight and reads.families is not None):
                raise OutOfScopeError(
                    f"{self._name(action)} declares variants but does not read the pool weight of the junk with named families, "
                    "so the extremes of its pools are not defined (ADR-0023)"
                )
            return
        if not reads.block_invariant:
            raise OutOfScopeError(
                f"{self._name(action)} is not declared block-invariant and declares no variants, so it has no family-group level "
                "(ADR-0023: every other action refuses the coarse state until its invariance or its variants are proved)"
            )
        if reads.junk and reads.families is None:
            raise OutOfScopeError(f"{self._name(action)} reads every family of the item, so no family can be pooled for it")
        if reads.pool_weight:
            raise OutOfScopeError(
                f"{self._name(action)} adds mods, so its kernel depends on the pool weight of the families held; "
                "claiming block invariance for it is wrong, and it declares no variants (ADR-0023)"
            )

    def _name(self, action: Action) -> str:
        try:
            return action.label(self._data)
        except ValueError:
            return repr(action)

    def _build_pools(self) -> None:
        goal_families = self._goal_families()
        seen: set[str] = set()
        for index, group in enumerate(self.groups):
            for family in sorted(group):
                if family not in self._side_of:
                    raise ValueError(f"{family!r} is not a family of the pool of {self.abstraction.base_id}")
                kind = self._kind_of[family]
                if kind == ALIKE:
                    raise ValueError(f"{family!r} is not told apart by an enabled action: the state already merges it")
                if family in goal_families:
                    raise ValueError(f"{family!r} holds a mod that a requirement names: a goal-relevant family is never pooled")
                if family in seen:
                    raise ValueError(f"{family!r} is in two groups")
                seen.add(family)
                missing = set(self._of_kind[(self._side_of[family], kind)]) - group
                if missing:
                    raise ValueError(
                        f"{family!r} has the family type {kind}, so every family of that type on the "
                        f"{self._side_of[family].value} side must be in its group: {sorted(missing)} are not"
                    )
            for side in Side:
                families = tuple(sorted(f for f in group if self._side_of[f] is side))
                if families:
                    pool = _Pool(side, f"{POOLED}g{index}", families)
                    self._pool_of_kind[(side, pool.kind)] = pool
                    for family in families:
                        self._pools[(side, self._kind_of[family])] = pool

    def _find_crafted_mods(self) -> None:
        """The slot a crafted mod of each pooled family makes: crafted mods with one family on the family's side."""
        found: dict[tuple[Side, str], set[Slot]] = defaultdict(set)
        for mod in self._data.mods.values():
            if mod.domain != "crafted" or len(mod.families) != 1 or mod.generation_type not in Side:
                continue
            side, family = Side(mod.generation_type), mod.families[0]
            if (side, self._kind_of.get(family)) in self._pools:
                slot = self.abstraction.crafted_slot(mod.id)
                if all(value is Status.ABSENT for value in slot.contribution):  # a crafted goal mod is held exactly
                    found[(side, family)].add(slot)
        for key, slots in found.items():
            self._crafted[key] = min(slots, key=lambda slot: slot.key)

    # --- the map to blocks ---------------------------------------------------------------------------

    def coarsen(self, state: CompressedState) -> Block:
        """The block of an exact state: the slots of pooled families get the kind of their pool."""
        slots = [self._coarse_slot(slot) for slot in state.slots]
        if all(new is old for new, old in zip(slots, state.slots)):
            return state
        return replace(state, slots=tuple(sorted(slots, key=_slot_key)))

    def _coarse_slot(self, slot: Slot) -> Slot:
        found = self._slots.get(slot)
        if found is None:
            found = self._slots[slot] = self._pooled_slot(slot)
        return found

    def _pooled_slot(self, slot: Slot) -> Slot:
        if any(value is not Status.ABSENT for value in slot.contribution):
            return slot
        kind: str | None = slot.kind
        if slot.crafted:
            mod = self._data.mods.get(slot.kind)
            kind = self._kind_of.get(mod.families[0]) if mod is not None and len(mod.families) == 1 else None
        else:
            kind = base_kind(slot.kind) if slot.kind != ALIKE else None
        pool = self._pools.get((slot.side, kind)) if kind is not None else None
        return slot if pool is None else Slot(slot.side, pool.kind, slot.contribution, slot.crafted)

    def is_goal(self, block: Block) -> bool:
        """Whether the status of `block` meets the goal."""
        return self.abstraction.is_goal(block)

    # --- the members of a block ------------------------------------------------------------------------

    def members(self, block: Block) -> Iterator[CompressedState]:
        """Every exact state that `coarsen` maps to `block` (and, for a pooled crafted mod, has a crafted mod of that family)."""
        yield from self._members(block, None)

    def _held_by_fractured(self, state: CompressedState) -> set[str]:
        held: set[str] = set()
        for entry in state.fractured:
            mod = self._data.mods.get(entry.mod_id)
            if mod is None:
                raise OutOfScopeError(
                    f"the state holds a fractured mod as the family type {entry.mod_id}: "
                    "the family-group level has no rule for a fracture made mid-route"
                )
            held |= held_families(mod)
        return held

    def _held(self, block: Block) -> set[str]:
        """The families that the fractured mods and the slots that are not pooled hold, in every member."""
        held = self._held_by_fractured(block)
        for slot in block.slots:
            if slot.kind.startswith(POOLED):
                continue
            if slot.crafted:
                held |= held_families(self._data.mods[slot.kind])
            else:
                kind = base_kind(slot.kind)
                if kind != ALIKE and not kind.startswith(TYPE_PREFIX):  # a family type that is not pooled holds no family of a pool
                    held |= {kind} if kind.startswith("#") else set(kind.split("|"))
        return held

    def _pooled_counts(self, block: Block) -> tuple[dict[tuple[Side, str], list[int]], list[Slot]]:
        """The pooled slots of a block per (side, pool kind) as [plain, crafted], and the slots that are not pooled."""
        counts: dict[tuple[Side, str], list[int]] = defaultdict(lambda: [0, 0])
        rest = []
        for slot in block.slots:
            if slot.kind.startswith(POOLED):
                if (slot.side, slot.kind) not in self._pool_of_kind:
                    raise ValueError(f"{block!r} is not a block of this coarsening: no pool {slot.kind!r} on the {slot.side.value} side")
                counts[(slot.side, slot.kind)][slot.crafted] += 1
            else:
                rest.append(slot)
        return counts, rest

    def _assemble(self, block: Block, rest: list[Slot], choices: Iterable[Iterable[tuple[Slot, ...]]]) -> Iterator[CompressedState]:
        """The block with its pooled slots replaced by one choice of slots for each pool."""
        for choice in choices:
            slots = list(rest)
            for part in choice:
                slots += part
            yield replace(block, slots=tuple(sorted(slots, key=_slot_key)))

    def _members(self, block: Block, marked: frozenset[str] | None) -> Iterator[CompressedState]:
        """Representative members: one for each way the families in `marked` can be held (all of them when None).

        Families of a pool outside `marked` are interchangeable here, so the first free ones stand for the rest.
        """
        counts, rest = self._pooled_counts(block)
        if not counts:
            yield block
            return
        held = self._held(block)
        pools = [self._pool_of_kind[key] for key in counts]
        options = [self._options(pool, *counts[(pool.side, pool.kind)], held, marked) for pool in pools]
        yield from self._assemble(block, rest, product(*options))

    def _slots_on(self, pool: _Pool, junk: Iterable[str], crafted: Iterable[str]) -> tuple[Slot, ...]:
        """The slots of plain mods on the families `junk` (each of its kind) and of crafted mods on `crafted`, sorted."""
        slots = [Slot(pool.side, self._kind_of[family], self._zero) for family in junk]
        slots += [self._crafted[(pool.side, family)] for family in crafted]
        return tuple(sorted(slots, key=_slot_key))

    def _options(
        self, pool: _Pool, junk: int, crafted: int, held: set[str], marked: frozenset[str] | None
    ) -> list[tuple[Slot, ...]]:
        """The ways `junk` plain and `crafted` crafted slots can sit on distinct free families of `pool`, as slots (each way once)."""
        free = [family for family in pool.families if family not in held]
        chosen = [family for family in free if marked is None or family in marked]
        others = [family for family in free if family not in chosen]
        can_craft = {family for family in free if (pool.side, family) in self._crafted}
        options: dict[tuple[Slot, ...], None] = {}  # families of one type give the same slots: keep the first
        for with_marked in range(crafted + 1):
            for crafted_marked in combinations([f for f in chosen if f in can_craft], with_marked):
                crafted_others = [f for f in others if f in can_craft][: crafted - with_marked]
                if len(crafted_others) < crafted - with_marked:
                    continue
                used = {*crafted_marked, *crafted_others}
                marked_left = [f for f in chosen if f not in used]
                others_left = [f for f in others if f not in used]
                for count in range(max(0, junk - len(others_left)), min(junk, len(marked_left)) + 1):
                    for picked in combinations(marked_left, count):
                        options[self._slots_on(pool, (*picked, *others_left[: junk - count]), (*crafted_marked, *crafted_others))] = None
        if not options:
            raise self._too_few(pool, len(free), junk + crafted)
        return list(options)

    def _too_few(self, pool: _Pool, free: int, slots: int) -> ValueError:
        return ValueError(
            f"the pool {pool.kind} on the {pool.side.value} side has {free} free families of {len(pool.families)} "
            f"but the block puts {slots} slots in it"
        )

    def _extreme(self, pool: _Pool, junk: int, crafted: int, held: set[str], heavy: bool) -> tuple[Slot, ...]:
        """The slots when the pool's `junk` plain and `crafted` crafted slots sit on its lightest (or heaviest) free families.

        The crafted slots take the families that have a crafted mod first (the lightest of them, or the
        heaviest), then the plain slots the lightest (heaviest) of all the families left; ties are broken
        by name. This holds the least (most) pool weight of any member, which is what the extremes of an
        addition's kernel need.
        """
        free = [family for family in pool.families if family not in held]
        able = sorted((f for f in free if (pool.side, f) in self._crafted), key=lambda f: (self._weight[f], f), reverse=heavy)
        if len(free) < junk + crafted or len(able) < crafted:
            raise self._too_few(pool, len(free), junk + crafted)
        crafted_on = able[:crafted]
        left = sorted((f for f in free if f not in crafted_on), key=lambda f: (self._weight[f], f), reverse=heavy)
        return self._slots_on(pool, left[:junk], crafted_on)

    def _extremes(self, block: Block) -> Iterator[CompressedState]:
        """The members that hold the lightest or the heaviest families in each pool (every combination, each state once)."""
        counts, rest = self._pooled_counts(block)
        if not counts:
            yield block
            return
        held = self._held(block)
        pools = [self._pool_of_kind[key] for key in counts]
        options = []
        for pool in pools:
            junk, crafted = counts[(pool.side, pool.kind)]
            lightest = self._extreme(pool, junk, crafted, held, False)
            heaviest = self._extreme(pool, junk, crafted, held, True)
            options.append([lightest] if lightest == heaviest else [lightest, heaviest])
        yield from self._assemble(block, rest, product(*options))

    # --- the kernels -----------------------------------------------------------------------------------

    def kernel(self, block: Block, action: Action, bound: Bound) -> Mapping[Block, Fraction]:
        """The kernel of `action` on `block` in the optimistic (`"lower"`) or pessimistic (`"upper"`) model.

        The lower model offers the action when some member can take it, the upper only when every
        member can; both charge the same pushed kernel. Raises `OutOfScopeError` for an action that
        declares neither block invariance nor variants, and what the action raises (`NotApplicableError`,
        `OutOfScopeError`) when it is not offered: in the lower model when no member can take it, in
        the upper when one cannot. An action with variants has one kernel only when its variants are one;
        otherwise `ValueError` (use `variants`).
        """
        kernels = self.variants(block, action, bound)
        if len(kernels) > 1:
            raise ValueError(f"{self._name(action)} has several variants ({len(kernels)}) on this block: use variants()")
        return kernels[0]

    def variants(self, block: Block, action: Action, bound: Bound) -> tuple[Mapping[Block, Fraction], ...]:
        """The distinct pushed kernels of `action` on `block` that its model charges, one for a block-invariant action.

        An action with `Reads.variants` has the kernels of the members that hold the lightest or the
        heaviest pool weight in each pool, those that can take the action; the optimistic model takes the
        cheapest backup over them, the pessimistic the dearest (ADR-0023). The offer follows the lower
        model (some such member can take the action) or the upper (all can), and what the action raises
        when it is not offered comes back as for `kernel`.
        """
        if bound not in ("lower", "upper"):
            raise ValueError(f"bound must be 'lower' or 'upper', got {bound!r}")
        found = self._evaluate(block, action)
        if found.kernels if bound == "lower" else found.error is None:
            return found.kernels
        assert found.error is not None
        raise found.error.with_traceback(None)  # a cached refusal is raised many times: do not stack tracebacks on it

    def _evaluate(self, block: Block, action: Action) -> _Evaluation:
        if self._last is not None and self._last[0] == block and self._last[1] == action:
            return self._last[2]
        self.require_invariant(action)
        if self._holds_blocking_metamod(block):
            raise OutOfScopeError(
                "the block holds a lock or an Attack/Caster metamod: a lock keeps the junk of its side through a reroll, "
                "which the family-group level does not pool yet (#69)"
            )
        reads = action.reads(self._data)
        if reads.variants:
            found = self._run_members(self._extremes(block), action, False)
        elif reads.junk:
            found = self._run_members(self._members(block, frozenset(reads.families)), action, True)
        else:  # an erasing action looks at the flags, the fractured mods and the crafted mods: blocks that agree on them share it
            key = (action, block.flags, block.fractured, tuple(slot for slot in block.slots if slot.crafted))
            found = self._rerolls.get(key)
            if found is None:
                found = self._rerolls[key] = self._run_members(self._members(block, frozenset()), action, True)
        self._last = (block, action, found)
        return found

    def _holds_blocking_metamod(self, block: Block) -> bool:
        families, mods = {metamod.value for metamod in BLOCKING}, self._data.mods
        ids = [slot.kind for slot in block.slots if slot.crafted] + [entry.mod_id for entry in block.fractured]
        return any(mod_id in mods and families & set(mods[mod_id].families) for mod_id in ids)

    def _run_members(self, members: Iterable[CompressedState], action: Action, invariant: bool) -> _Evaluation:
        """Run the exact kernel on each member: the distinct pushed kernels, the first refusal.

        A block-invariant action has the same pushed kernel on every member that can take it, so only the first is pushed.
        """
        kernels: list[Mapping[Block, Fraction]] = []
        error: ActionError | None = None
        for member in members:
            try:
                exact = self.abstraction.kernel(member, action)
            except ActionError as refusal:
                error = error or refusal
                continue
            if invariant and kernels:
                continue
            pushed: dict[Block, Fraction] = defaultdict(Fraction)
            for state, chance in exact.items():
                pushed[self.coarsen(state)] += chance
            if dict(pushed) not in kernels:
                kernels.append(dict(pushed))
        return _Evaluation(tuple(kernels), error)

    def reachable(
        self, starts: Iterable[Block], actions: Iterable[Action], bound: Bound = "lower", *, stop_at_goal: bool = False
    ) -> frozenset[Block]:
        """Every block reachable from `starts` by any of `actions` in the model of `bound`, the starts included.

        The successors of every variant of an action count. With `stop_at_goal` a block that meets the
        goal is not expanded (a solver does not expand goals).
        """
        actions = tuple(actions)
        for action in actions:
            self.require_invariant(action)  # a refusal of the action itself is not a refusal in one state
        seen = set(starts)
        queue = list(seen)
        while queue:
            block = queue.pop()
            if stop_at_goal and self.is_goal(block):
                continue
            for action in actions:
                try:
                    kernels = self.variants(block, action, bound)
                except ActionError:
                    continue
                for successors in kernels:
                    for successor in successors:
                        if successor not in seen:
                            seen.add(successor)
                            queue.append(successor)
        return frozenset(seen)
