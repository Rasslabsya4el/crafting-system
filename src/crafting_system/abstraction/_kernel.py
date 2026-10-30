"""The abstraction of one base at one item level: compression, family types, the cached kernel."""

import math
from collections import defaultdict, deque
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import reduce

from crafting_system.actions import ActionError, Outcomes, OutOfScopeError, build_pool
from crafting_system.data import GameData, Mod
from crafting_system.items import ExplicitMod, Item, ItemError, Rarity, Side, tier_table

from ._goal import Goal, Status
from ._state import CompressedState, Flags, FracturedMod, best_of, status_of

Label = tuple[int, ...]
FamilyType = tuple[Side, tuple[tuple[Label, Fraction, bool], ...]]


@dataclass(frozen=True)
class CacheStats:
    """How the kernel cache was used: `kernels` distinct signatures computed, `hits` requests served by one."""

    kernels: int
    hits: int


def integer_weights(kernel: Mapping[CompressedState, Fraction]) -> dict[CompressedState, int]:
    """The kernel as integers proportional to its probabilities, with no common factor."""
    if not kernel:
        return {}
    common = reduce(math.lcm, (chance.denominator for chance in kernel.values()))
    scaled = {state: int(chance * common) for state, chance in kernel.items()}
    divisor = reduce(math.gcd, scaled.values())
    return {state: weight // divisor for state, weight in scaled.items()}


def _low_values(mod: Mod) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in mod.stats)


class Abstraction:
    """Design D for one base and item level: compress items, and get the exact kernel of a rerolling action.

    The kernel of a state under an action is cached by pool signature: two states whose pools have
    the same multiset of family types share one label distribution.
    """

    def __init__(self, data: GameData, goal: Goal, base_id: str, item_level: int):
        self.data = data
        self.goal = goal
        self.base_id = base_id
        self.item_level = item_level
        self._tiers = tier_table(data, base_id)
        self._labels: dict[str, Label] = {}
        self._canonical_group: dict[tuple, list[Mod]] | None = None
        self._canonical: dict[tuple[str, tuple[Status, ...]], str] = {}
        self._outcomes: dict[Hashable, Outcomes] = {}
        self._signatures: dict[Hashable, Hashable] = {}
        self._cache: dict[Hashable, dict[Label, Fraction]] = {}
        self._kernels = 0
        self._hits = 0

    @property
    def stats(self) -> CacheStats:
        """How many label distributions were computed and how many requests reused one."""
        return CacheStats(self._kernels, self._hits)

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
        flags = Flags(item.rarity, item.corrupted, item.influences, bool(item.crafted_mods))
        return CompressedState(flags, tuple(fractured), status)

    def is_goal(self, state: CompressedState) -> bool:
        """Whether the status of `state` meets the goal."""
        return self.goal.is_met(state.status)

    def kernel(self, state: CompressedState, action) -> Mapping[CompressedState, Fraction]:
        """The exact distribution of the next compressed state after `action` on `state`.

        Raises what the action raises for the retained item (`NotApplicableError`,
        `OutOfScopeError`), `OutOfScopeError` for a crafted mod and for a roll limit on a drawn
        mod, and `ValueError` for a state of another goal.
        """
        if len(state.status) != len(self.goal.leaves):
            raise ValueError(
                f"the state has {len(state.status)} statuses but the goal has {len(self.goal.leaves)} leaves: "
                "it comes from another abstraction"
            )
        outcomes = self._outcomes_of(state, action)
        if state.flags.crafted:
            raise OutOfScopeError(
                "the item has a crafted mod or metamod; bench mods and metamods are not modelled yet"
            )
        distribution = self._distribution(state, action, outcomes)
        fixed = best_of(len(self.goal.leaves), (entry.contribution for entry in state.fractured))
        result: dict[CompressedState, Fraction] = defaultdict(Fraction)
        for drawn, chance in distribution.items():
            status = tuple(max(a, b) for a, b in zip(fixed, map(Status, drawn)))
            result[CompressedState(state.flags, state.fractured, status)] += chance
        return dict(result)

    def signature(self, state: CompressedState, action) -> Hashable:
        """What decides the label distribution: equal signatures share one cached distribution.

        It is `(tag, kept mods, free prefixes, free suffixes, totals, sorted family types of the pool)`.
        """
        return self._signature_of(state, action, self._outcomes_of(state, action))

    def reachable(self, starts: Iterable[CompressedState], actions) -> frozenset[CompressedState]:
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

    def family_types(self, tag: str | None = None) -> Mapping[FamilyType, tuple[str, ...]]:
        """The families of the full pool of an empty rare item of this base and level, by family type.

        `tag` is the guaranteed tag of a Harvest reforge or None. The value is the sorted family ids.
        """
        empty = Item.build(self.data, base_id=self.base_id, item_level=self.item_level, rarity=Rarity.RARE)
        grouped: dict[FamilyType, list[str]] = defaultdict(list)
        for family in build_pool(self.data, empty):
            grouped[self._family_type(family, tag)].append(family.family)
        return {kind: tuple(sorted(names)) for kind, names in grouped.items()}

    def _contribution(self, entry: ExplicitMod) -> tuple[Status, ...]:
        return tuple(
            status_of(leaf, entry.mod_id, entry.tier, entry.values, entry.crafted)
            for leaf in self.goal.leaves
        )

    def _drawn_contribution(self, mod: Mod) -> tuple[Status, ...]:
        """What `mod` gives each leaf when an action draws it: its table tier, low rolls, not crafted."""
        tier = self._tiers.get(mod.id, 1)
        return tuple(
            status_of(leaf, mod.id, tier, _low_values(mod), False) for leaf in self.goal.leaves
        )

    def _label(self, mod: Mod) -> Label:
        """The label of a drawn mod: its contribution to every leaf, as ints.

        Raises `OutOfScopeError` when a leaf names the mod and limits its roll: the roll of a drawn
        mod is not modelled yet.
        """
        label = self._labels.get(mod.id)
        if label is None:
            for leaf in self.goal.leaves:
                if mod.id in leaf.mod_ids and leaf.has_roll_limit:
                    raise OutOfScopeError(
                        f"a roll limit on a drawn mod is not modelled yet (mod {mod.id})"
                    )
            label = tuple(int(status) for status in self._drawn_contribution(mod))
            self._labels[mod.id] = label
        return label

    def _canonical_id(self, entry: ExplicitMod) -> str:
        """The smallest id among the mods of the same families, side and domain that give the same contribution."""
        contribution = self._contribution(entry)
        key = (entry.mod_id, contribution)
        found = self._canonical.get(key)
        if found is None:
            if self._canonical_group is None:
                groups: dict[tuple, list[Mod]] = defaultdict(list)
                for mod in self.data.mods.values():
                    groups[(mod.families, mod.generation_type, mod.domain)].append(mod)
                self._canonical_group = groups
            own = self.data.mods[entry.mod_id]
            group = self._canonical_group[(own.families, own.generation_type, own.domain)]
            matching = [mod.id for mod in group if self._drawn_contribution(mod) == contribution]
            found = min(matching) if matching else min(mod.id for mod in group)
            self._canonical[key] = found
        return found

    def _retained(self, state: CompressedState) -> Item:
        flags = state.flags
        mods = tuple(
            ExplicitMod(
                entry.mod_id,
                self._tiers.get(entry.mod_id, 1),
                _low_values(self.data.mods[entry.mod_id]),
                fractured=True,
            )
            for entry in state.fractured
        )
        fields = dict(
            base_id=self.base_id,
            item_level=self.item_level,
            rarity=flags.rarity,
            influences=flags.influences,
            corrupted=flags.corrupted,
        )
        return Item.build(self.data, mods=mods, **fields)

    def _outcomes_of(self, state: CompressedState, action) -> Outcomes:
        key = (action, state.flags, state.fractured)
        outcomes = self._outcomes.get(key)
        if outcomes is None:
            try:
                retained = self._retained(state)
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
            outcomes = action.outcomes(self.data, retained)
            self._outcomes[key] = outcomes
        return outcomes

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

    def _signature_of(self, state: CompressedState, action, outcomes: Outcomes) -> Hashable:
        key = (action, state.flags, state.fractured)
        signature = self._signatures.get(key)
        if signature is None:
            free = outcomes.free
            signature = (
                outcomes.tag,
                len(outcomes.retained.mods),
                free[Side.PREFIX],
                free[Side.SUFFIX],
                tuple(sorted(outcomes.totals.items())),
                tuple(sorted(self._family_type(family, outcomes.tag) for family in outcomes.pool)),
            )
            self._signatures[key] = signature
        return signature

    def _distribution(self, state: CompressedState, action, outcomes: Outcomes) -> dict[Label, Fraction]:
        """The probability of the best label per leaf among the new mods, cached by signature."""
        signature = self._signature_of(state, action, outcomes)
        cached = self._cache.get(signature)
        if cached is not None:
            self._hits += 1
            return cached
        width = len(self.goal.leaves)
        merged: dict[Label, Fraction] = defaultdict(Fraction)
        for outcome, chance in outcomes.distribution(self._label).items():
            merged[tuple(best_of(width, (label for label, _ in outcome)))] += chance
        cached = dict(merged)
        self._cache[signature] = cached
        self._kernels += 1
        return cached
