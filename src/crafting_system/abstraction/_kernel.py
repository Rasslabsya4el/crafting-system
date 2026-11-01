"""The abstraction of one base at one item level: compression, family types, the cached kernels."""

import math
from collections import Counter, defaultdict, deque
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from operator import attrgetter

from crafting_system.actions import (
    BLOCKING,
    Action,
    ActionError,
    ActionOutcomes,
    Fixed,
    Fractured,
    Need,
    NotApplicableError,
    Outcomes,
    OutOfScopeError,
    Reading,
    Rerolled,
    allowed_by_tags,
    build_pool,
    partners,
    tiers_of,
)
from crafting_system.data import GameData, Mod
from crafting_system.items import (
    EldritchSide,
    ExplicitMod,
    ImplicitError,
    ImplicitMod,
    Influence,
    Item,
    ItemError,
    Quality,
    Rarity,
    Side,
    eldritch_grade,
    eldritch_side,
    spawn_weight,
    tier_table,
)

from ._goal import Goal, Status
from ._kinds import MOD_PREFIX, TYPE_PREFIX, Kinds, TypeNumbers, base_kind, held_families, protected_tags
from ._rolls import Cells, RollLaw, is_rollable, multinomial, roll_law
from ._state import (
    CompressedState,
    Flags,
    FracturedMod,
    ImplicitSide,
    OfferedMod,
    Slot,
    best_of,
    implicit_status_of,
    status_of,
)

Label = Hashable  # the contribution to every leaf as ints (a `RollLaw` for a mod whose roll changes it); with junk slots kept, also the side and the kind
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
    item: Item | None = None  # the item the state stands for, as the action was given it


@dataclass(frozen=True)
class _Split:
    """A part's retained item read back into state terms: the fractured mods and slots it keeps, the new ones, the flags."""

    flags: Flags
    fractured: tuple[FracturedMod, ...]
    kept: tuple[Slot, ...]  # slots of mods the item already had
    new: tuple[Slot, ...]  # slots of mods the action put on it (stored: crafted ones, and every one when junk is kept)
    status: tuple[Status, ...]  # what the mods that stay give each leaf
    new_ids: tuple[str, ...]  # ids of the new mods, in the order of the retained item
    implicits: tuple[ImplicitSide, ...] = ()  # the Eldritch pair of the retained item (ADR-0027); () when not kept
    quality: Quality | None = None
    offer: tuple[OfferedMod, ...] = ()


class _Context:
    """What depends on the influences of an item: the tier of every mod, the kinds, the labels of drawn mods."""

    def __init__(self, influences: frozenset[Influence], tiers: Mapping[str, int], kinds: Kinds):
        self.influences = influences
        self.tiers = tiers
        self.kinds = kinds
        self.labels: dict[str, Label] = {}
        self.lucky_labels: dict[str, Label] = {}  # the labels of a draw that rolls every value twice and keeps the better
        self.laws: dict[tuple[str, bool, bool], Cells] = {}  # (mod id, lucky, crafted) -> the roll law


class Abstraction:
    """Design D for one base and item level: compress items, and get the exact kernel of an action.

    `actions` are the enabled actions that read the mods besides the fractured ones (`Action.reads`);
    an action that reads none of them is always known. They decide what a state keeps of the mods that
    are not fractured: with none that reads them (the default) only the crafted mods are kept; with
    one, every such mod is a slot of its side and kind (see `Kinds`). `kernel` refuses an action that
    reads them and is not enabled.

    `metamods` says that items may hold a lock (`Prefixes` / `Suffixes Cannot Be Changed`) or an Attack or
    Caster metamod; it is True whenever an enabled action adds one by name. The state then keeps every mod
    as a slot (a lock makes a reroll keep the locked side), told apart by family type and by the tags a
    metamod looks at, and `compress` refuses an item that holds one when it is False.

    `reading` (ticket #210) is the value of each rule axis the enabled actions read (`actions.model_readings`): the
    abstraction is then the ordinary model of that reading, and every kernel is taken at it. None is the plan's reading,
    and an input-free action has no axis, so for it nothing changes. With `allow_inputs` False (the planner, until
    the solver is given the donors, ticket #212) an action that consumes other items (`Action.inputs`) on the item of
    a state is refused with `OutOfScopeError`, so that it is never priced as if its inputs were free.

    The tiers of the mods come from the pool of the item's influences (`tiers_of`), so an influence mod has
    its own tier. The kernel of a random action is cached by pool signature: two states whose pools have
    the same multiset of family types share one label distribution.

    `enchantment` is the mod id of the enchantment of the start item, or None. No action adds or removes one, so it is a constant of
    the problem and not part of the state; the items the kernel rebuilds from a state hold it, so that an action sees what the
    concrete item shows (the enchantment that lets an item hold two crafted mods, ADR-0053), and `compress` refuses an item whose
    enchantment is another.
    """

    def __init__(
        self,
        data: GameData,
        goal: Goal,
        base_id: str,
        item_level: int,
        actions: Iterable = (),
        *,
        metamods: bool = False,
        enchantment: str | None = None,
        reading: Reading | None = None,
        allow_inputs: bool = True,
    ):
        self.data = data
        self._reading = reading
        self._allow_inputs = allow_inputs
        self.goal = goal
        self.base_id = base_id
        self.item_level = item_level
        self.enchantment = enchantment
        if enchantment is not None:  # a mod id that does not fit the base is the caller's error, raised here and not at the first kernel
            Item.build(data, base_id=base_id, item_level=item_level, rarity=Rarity.RARE, enchantment=enchantment)
        actions = tuple(actions)
        self._metamods = metamods or any(self._adds_metamod(action) for action in actions)
        self._roll_leaves = tuple(leaf for leaf in goal.leaves if leaf.has_roll_limit)  # a roll limit: a drawn mod rolls its values
        self._has_laws = bool(self._roll_leaves)
        self._roll_ids = frozenset().union(*(leaf.mod_ids for leaf in self._roll_leaves))
        if any(leaf.has_roll_limit for leaf in goal.implicits):
            raise OutOfScopeError("a roll limit on an implicit is not modelled yet (ticket #158)")
        self._numbers = TypeNumbers()
        self._actions = actions
        reads, adds = [action.reads(data) for action in actions], [action.adds(data) for action in actions]
        self._tracks_implicits = bool(goal.implicits) or any(r.implicits for r in reads) or any(a.implicits for a in adds)
        self._tracks_quality = any(r.quality for r in reads) or any(a.quality for a in adds)
        self._tracks_offer = any(r.offer for r in reads) or any(a.offer for a in adds)
        self._sets_enchantment = any(a.enchantment for a in adds)  # the state never holds the enchantment (ADR-0050); this only lets `compress` see a result
        self._no_implicit = ImplicitSide(0, (Status.ABSENT,) * len(goal.implicits))
        self._eldritch: dict[tuple[EldritchSide, int], list[Mod]] | None = None
        self._implicit_mods: dict[tuple[EldritchSide, int, tuple[Status, ...]], Mod] = {}
        self._offered_ids: dict[tuple[frozenset[Influence], str, tuple[Status, ...]], str] = {}
        self._contexts: dict[frozenset[Influence], _Context] = {}
        self._kinds = self._new_context(frozenset(), tier_table(data, base_id)).kinds
        if self._tracks_offer and not self._kinds.tracked:
            raise ValueError(
                "an action that reads or draws the unveil offer must read the junk: the veiled placeholder is a mod of the item"
            )
        self._canonical_group: dict[tuple, list[Mod]] | None = None
        self._canonical: dict[tuple[frozenset[Influence], str, tuple[Status, ...], bool], str] = {}
        self._prepared_by: dict[Hashable, _Prepared] = {}
        self._has_partners: bool | None = None  # whether the pool of an empty rare item has a family with mods on both sides
        self._cache: dict[Hashable, dict[Hashable, Fraction]] = {}
        self._expanded: dict[Hashable, Expanded] = {}
        self._signatures: dict[Hashable, Hashable] = {}  # one object per equal pool signature, so a lookup by it is an identity hit
        self._drawn_slots: dict[tuple, Slot] = {}
        self._drawn_best: dict[tuple, tuple[Status, ...]] = {}
        self._fractures: dict[Hashable, tuple[tuple[Hashable, Fraction], ...]] = {}
        self._spread: dict[tuple[RollLaw, int], list] = {}
        self._unrolled: set[Hashable] = set()  # signatures of fracturing pools that hold no rollable mod
        self._kernels = 0
        self._hits = 0

    @property
    def reading(self) -> Reading | None:
        """The reading of the rule axes this abstraction's kernels are taken at (None: the plan's; each reading is one ordinary model, ADR-0033)."""
        return self._reading

    def inputs(self, state: CompressedState, action: Action) -> tuple[Need, ...]:
        """The `Need`s of `action` used on the item `state` stands for (`Action.inputs`); empty for an input-free action.

        The kernel of an action with inputs is the result of using it with them (the action finds its donor itself);
        what the donor is worth is the solver's, and which wanted states the planner builds for it is ticket #211.
        Raises what `kernel` raises when the action refuses the state's item.
        """
        self._check_enabled(action)
        return action.inputs(self.data, self._prepare(state, action).item)

    @property
    def keeps_junk(self) -> bool:
        """Whether a state stores the ordinary mods that are not fractured (an enabled action reads them)."""
        return self._kinds.tracked

    @property
    def rerolls_values(self) -> bool:
        """Whether an enabled action rerolls the values of the mods an item holds (a Divine Orb): rollable mods are then slots by mod id."""
        return self._kinds.rerolls

    @property
    def tracks_implicits(self) -> bool:
        """Whether a state holds the Eldritch pair: an enabled action reads or changes the implicits, or the goal asks for one."""
        return self._tracks_implicits

    @property
    def tracks_quality(self) -> bool:
        """Whether a state holds the catalyst quality: an enabled action reads or changes it."""
        return self._tracks_quality

    @property
    def sets_enchantment(self) -> bool:
        """Whether an enabled action declares that it sets the enchantment (`Adds.enchantment`, ADR-0050, ticket #238).

        It never makes the state hold the enchantment: the state is the same size with such an action or without it, and
        what the actions read of the enchantment is the start item's (the constant `enchantment`). It only means `compress`
        accepts a finished item whose enchantment is not the start item's, so a result of that action can be compared.
        """
        return self._sets_enchantment

    @property
    def tracks_offer(self) -> bool:
        """Whether a state holds the unveil offer: an enabled action reads, draws or uses it."""
        return self._tracks_offer

    @property
    def models_metamods(self) -> bool:
        """Whether the state models the lock and Attack/Caster metamods (`metamods`, or an enabled action adds one)."""
        return self._metamods

    @property
    def stats(self) -> CacheStats:
        """How many label distributions were computed and how many requests reused one."""
        return CacheStats(self._kernels, self._hits)

    @property
    def enabled(self) -> tuple[Action, ...]:
        """The enabled actions that read the ordinary mods (the ones `actions` of the constructor named)."""
        return self._kinds.actions

    def kind_of(self, mod: Mod, influences: frozenset[Influence] = frozenset()) -> str:
        """The kind a slot of the ordinary mod `mod` gets on an item with these influences: `ALIKE` ("") or its family key or type."""
        return self._kinds.of(mod) if not influences else self._context(influences).kinds.of(mod)

    def crafted_slot(self, mod_id: str) -> Slot:
        """The slot a crafted mod of this id makes (its canonical id, its contribution, low rolls)."""
        return self._slot_of(ExplicitMod(mod_id, 1, _low_values(self.data.mods[mod_id]), crafted=True), frozenset())

    # --- what depends on the influences ----------------------------------------------------------------

    def _adds_metamod(self, action: Action) -> bool:
        """Whether `action` adds a lock or an Attack/Caster metamod: by name (a bench craft of one), or as a crafted mod it picks among the families it reads (the Wild Bristle Matron)."""
        blocking = {metamod.value for metamod in BLOCKING}
        adds = action.adds(self.data)
        if adds.named is None:
            families = action.reads(self.data).families
            return bool(adds.crafted and families and blocking & set(families))
        return any(blocking & set(self.data.mods[mod_id].families) for mod_id in adds.named if mod_id in self.data.mods)

    def _new_context(self, influences: frozenset[Influence], tiers: Mapping[str, int]) -> _Context:
        kinds = Kinds(
            self.data,
            self.base_id,
            self.item_level,
            self._actions,
            lambda mod: self._profile(mod, influences),
            metamods=self._metamods,
            influences=influences,
            numbers=self._numbers,
            rollable=lambda: self._rollable_mods(influences),
        )
        context = self._contexts[influences] = _Context(influences, tiers, kinds)
        return context

    def _context(self, influences: frozenset[Influence]) -> _Context:
        """The tiers, kinds and labels for items with these influences, built when first asked for.

        The tiers are those of the pool of an item with the influences (`tiers_of`), so an influence mod
        has its own tier; the kinds are built on that pool, so an influence family is a family type. An
        item class with no influence class key has no such pool: its tiers are the base's (every action
        that draws raises `OutOfScopeError` on it, one that draws nothing does not look at them).
        """
        found = self._contexts.get(influences)
        if found is None:
            self._kinds.number_types()  # the types of the plain pool keep the numbers they would have without influences
            probe = Item.build(
                self.data, base_id=self.base_id, item_level=self.item_level, rarity=Rarity.RARE, influences=influences
            )
            try:
                tiers = tiers_of(self.data, probe)
            except OutOfScopeError:
                tiers = tier_table(self.data, self.base_id)
            found = self._new_context(influences, tiers)
        return found

    def compress(self, item: Item) -> CompressedState:
        """The compressed state of a concrete item.

        Raises `ValueError` for an item of another base or item level than this abstraction's and
        `OutOfScopeError` for an item that holds a lock or an Attack/Caster metamod when `metamods` is False.
        """
        if item.base_id != self.base_id or item.item_level != self.item_level:
            raise ValueError(
                f"item on {item.base_id} at level {item.item_level} does not fit an abstraction "
                f"of {self.base_id} at level {self.item_level}"
            )
        if item.enchantment != self.enchantment and not self._sets_enchantment:
            raise ValueError(
                f"item with enchantment {item.enchantment!r} does not fit an abstraction built with enchantment {self.enchantment!r}: "
                "the enchantment is a constant of the problem, pass it as `enchantment`"
            )
        if not self._metamods:
            held = item.metamods(self.data) & BLOCKING
            if held:
                names = ", ".join(sorted(metamod.value for metamod in held))
                raise OutOfScopeError(
                    f"the item holds a metamod ({names}) and this abstraction was built with metamods=False: "
                    "pass metamods=True to model what a lock or an Attack/Caster metamod changes"
                )
        influences = item.influences
        fractured = sorted(
            (FracturedMod(self._fractured_id(entry, influences), self._contribution(entry)) for entry in item.fractured_mods),
            key=lambda entry: (entry.mod_id, entry.contribution),
        )
        status = best_of(
            len(self.goal.leaves), (self._contribution(entry) for entry in item.mods)
        )
        slots = sorted(
            (
                self._slot_of(entry, influences)
                for entry in item.mods
                if not entry.fractured and (entry.crafted or self._kinds.tracked)
            ),
            key=lambda slot: slot.key,
        )
        flags = Flags(item.rarity, item.corrupted, item.influences)
        return CompressedState(
            flags,
            tuple(fractured),
            status,
            tuple(slots),
            *self._held_by(item.implicits, item.quality, item.veil_offer, influences),
        )

    def _held_by(
        self,
        implicits: tuple[ImplicitMod, ...],
        quality: Quality | None,
        offer: tuple[str, ...],
        influences: frozenset[Influence],
    ) -> tuple[tuple[ImplicitSide, ...], Quality | None, tuple[OfferedMod, ...]]:
        """The implicits, the quality and the offer of an item as a state keeps them: each is empty unless an enabled action reads or changes it."""
        return (
            self._implicit_pair(implicits) if self._tracks_implicits else (),
            quality if self._tracks_quality else None,
            self._offer_of(offer, influences) if self._tracks_offer else (),
        )

    def is_goal(self, state: CompressedState) -> bool:
        """Whether `state` meets the goal: the status of the leaves, and for each Eldritch implicit wanted one side that passes it."""
        if not self.goal.is_met(state.status):
            return False
        wanted = len(self.goal.implicits)
        if not wanted:
            return True
        return all(any(side.contribution[index] is Status.PASSING for side in state.implicits) for index in range(wanted))

    def kernel(self, state: CompressedState, action: Action) -> Mapping[CompressedState, Fraction]:
        """The exact distribution of the next compressed state after `action` on `state`.

        Raises what the action raises for the item the state stands for (`NotApplicableError`,
        `OutOfScopeError`), `OutOfScopeError` for a roll limit on a forced, crafted or fixed-result new mod
        and for a Fractured Fossil whose pool holds a mod a roll limit tells apart (a mod the action draws
        is fine: its roll is spread over its law), and `ValueError` for a state of another goal and for an
        action that reads the mods besides the fractured ones and was not enabled.
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
        part the key adds `part.forced` and the families of the pool with their mod ids and weights. A
        `Rerolled` part also reads which of the kept slots are rerolled (`changed`), so the key adds them.
        """
        if len(state.status) != len(self.goal.leaves):
            raise ValueError(
                f"the state has {len(state.status)} statuses but the goal has {len(self.goal.leaves)} leaves: "
                "it comes from another abstraction"
            )
        self._check_enabled(action)
        prepared = self._prepared(state, action)
        outcomes = prepared.outcomes
        self._check_parts(outcomes)
        parts: Counter = Counter()
        for (share, part), signature, split in zip(
            outcomes.components, self._signatures_of(prepared), self._splits_of(prepared)
        ):
            key = (share, signature, split.flags, split.fractured, split.kept, split.new, split.status, split.implicits, split.quality, split.offer)
            if isinstance(part, Rerolled):  # which of the kept slots are rerolled decides the kernel
                key = (*key, tuple(sorted(self._rerolled_slots(part, prepared.origins)[1], key=_SLOT_KEY)))
            if outcomes.fractures and not isinstance(part, Fixed):
                self._refuse_rollable_fracture(part, signature)
                pool = tuple(
                    (family.family, tuple((entry.mod.id, entry.weight) for entry in family.mods))
                    for family in part.pool
                )
                key = (*key, part.forced, pool)
            parts[key] += 1
        return (outcomes.fractures, frozenset(parts.items()))

    def _check_parts(self, outcomes: ActionOutcomes) -> None:
        """Refuse the mixtures of parts that no kernel is defined for (a fracture needs all pool draws or all fixed results)."""
        parts = [part for _, part in outcomes.components]
        fixed = [isinstance(part, Fixed) for part in parts]
        if outcomes.fractures and any(fixed) and not all(fixed):
            raise ValueError("a mixture of fixed results and pool draws cannot fracture a mod: only pool draws (a Fractured Fossil) or fixed results (a Fracturing Orb) do")
        if outcomes.fractures and any(isinstance(part, Rerolled) for part in parts):
            raise ValueError("a rerolled result cannot fracture a mod")

    def _check_enabled(self, action: Action) -> None:
        reads = action.reads(self.data)
        if not (reads.junk or reads.item_state) or action in self._kinds.actions:
            return
        if reads.junk:
            raise ValueError(f"{action!r} reads the mods of the item and is not among the enabled actions")
        raise ValueError(f"{action!r} reads the implicits, the quality or the offer of the item and is not among the enabled actions")

    def signature(self, state: CompressedState, action: Action) -> Hashable:
        """What decides the label distribution: equal signatures share one cached distribution.

        It is `(tag, blocked tags, kept mods, free prefixes, free suffixes, totals, sorted family types of the
        pool)` for a random action. A resonator with one pool and no Fractured Fossil has the signature of that
        pool, so it shares its distribution with any other action of an equal pool (a Chaos Orb, a set
        whose fossils change no weight of this item); a mixture (Tangled, Glyphic) or a Fractured Fossil
        has `("fossils", fractures, the parts)`, each part its probability and the signature of its
        pool, with the label of its forced mod when a mod is fractured. An action with a fixed result
        (a bench craft) draws nothing and has no cache: its signature is `("fixed", action)`, which
        names the action and does not decide its kernel. A `Rerolled` part (a Divine Orb) is the same:
        its signature `("rerolled", lucky)` names the kind only, and the kernel also reads which kept slots
        are rerolled (`kernel_key` carries them).

        The forced mod of an essence is not in it: it is a kept mod, so the pool already leaves out its
        family, the kept count and the free slots already count it, and it cannot change the draw.
        """
        self._check_enabled(action)
        prepared = self._prepared(state, action)
        outcomes = prepared.outcomes
        if all(isinstance(part, Fixed) for _, part in outcomes.components):
            return ("fixed", action)
        self._check_parts(outcomes)
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
        if partners(pool):
            raise OutOfScopeError("the family types of a pool with a family that has mods on both sides are not modelled")
        grouped: dict[FamilyType, list[str]] = defaultdict(list)
        for family in pool:
            grouped[self._family_type(family, tag, frozenset())].append(family.family)
        return {kind: tuple(sorted(names)) for kind, names in grouped.items()}

    def _contribution(self, entry: ExplicitMod) -> tuple[Status, ...]:
        return tuple(
            status_of(leaf, entry.mod_id, entry.tier, entry.values, entry.crafted)
            for leaf in self.goal.leaves
        )

    # --- the implicits, the quality and the offer (ADR-0027) ---------------------------------------------

    def _implicit_pair(self, implicits: tuple[ImplicitMod, ...]) -> tuple[ImplicitSide, ...]:
        """The Eldritch pair of an item's implicits: the Searing Exarch side and the Eater of Worlds side.

        Raises `OutOfScopeError` for an implicit that is not Eldritch: the state holds no base implicit until ticket #158.
        """
        sides = {side: self._no_implicit for side in EldritchSide}
        for entry in implicits:
            side = eldritch_side(self.data.mods[entry.mod_id])
            if side is None:
                raise OutOfScopeError(
                    f"the item holds the base implicit {entry.mod_id}: the state holds the two Eldritch sides only"
                    " (rolls of base implicits: ticket #158)"
                )
            contribution = tuple(
                implicit_status_of(leaf, entry.mod_id, entry.grade, entry.values) for leaf in self.goal.implicits
            )
            sides[side] = ImplicitSide(entry.grade, contribution)
        return (sides[EldritchSide.EXARCH], sides[EldritchSide.EATER])

    def _implicit_mod(self, side: EldritchSide, grade: int, contribution: tuple[Status, ...]) -> Mod:
        """The Eldritch mod that stands for a side of the pair: the smallest id of the side and grade that gives `contribution`."""
        key = (side, grade, contribution)
        found = self._implicit_mods.get(key)
        if found is None:
            if self._eldritch is None:
                grouped: dict[tuple[EldritchSide, int], list[Mod]] = defaultdict(list)
                for mod in self.data.mods.values():
                    mod_side = eldritch_side(mod)
                    if mod_side is None:
                        continue
                    try:
                        grouped[(mod_side, eldritch_grade(mod))].append(mod)
                    except ImplicitError:
                        continue  # an id without a grade: not a mod an action can put on an item
                self._eldritch = grouped
            for mod in sorted(self._eldritch.get((side, grade), ()), key=lambda mod: mod.id):
                given = tuple(implicit_status_of(leaf, mod.id, grade, _low_values(mod)) for leaf in self.goal.implicits)
                if given == contribution:
                    found = mod
                    break
            else:
                raise OutOfScopeError(
                    f"no Eldritch mod of the {side.value} side and grade {grade} gives {[int(v) for v in contribution]}"
                    " to the implicits wanted"
                )
            self._implicit_mods[key] = found
        return found

    def _offer_of(self, offer: tuple[str, ...], influences: frozenset[Influence]) -> tuple[OfferedMod, ...]:
        """The mods of an unveil offer as the state keeps them, sorted: each by the canonical id of its kind and what it gives each leaf."""
        entries = []
        for mod_id in offer:
            mod = self.data.mods[mod_id]
            contribution = self._drawn_contribution(mod, False, influences)
            entries.append(OfferedMod(self._offered_id(mod, contribution, influences), contribution))
        return tuple(sorted(entries, key=lambda entry: (entry.mod_id, entry.contribution)))

    def _offered_id(self, mod: Mod, contribution: tuple[Status, ...], influences: frozenset[Influence]) -> str:
        """The smallest id among the unveiled mods of the families and side of `mod` that give `contribution` and can spawn on this base."""
        key = (influences, mod.id, contribution)
        found = self._offered_ids.get(key)
        if found is None:
            tags = self.data.base_items[self.base_id].tags
            group = self._canonical_groups()[(mod.families, mod.generation_type, mod.domain)]
            matching = [
                other.id
                for other in group
                if spawn_weight(other, tags) > 0 and self._drawn_contribution(other, False, influences) == contribution
            ]
            found = self._offered_ids[key] = min(matching) if matching else mod.id
        return found

    def _drawn_contribution(
        self, mod: Mod, crafted: bool = False, influences: frozenset[Influence] = frozenset()
    ) -> tuple[Status, ...]:
        """What `mod` gives each leaf when an action draws, forces or crafts it: its table tier (that of the pool of an item with these influences), low rolls."""
        tier = self._context(influences).tiers.get(mod.id, 1)
        return tuple(
            status_of(leaf, mod.id, tier, _low_values(mod), crafted) for leaf in self.goal.leaves
        )

    def passes(self, mod: Mod, leaf: int) -> bool:
        """Whether `mod`, drawn by an action (its table tier, low rolls), gives leaf number `leaf` the status PASSING."""
        return self._drawn_contribution(mod)[leaf] is Status.PASSING

    def _law(self, mod: Mod, influences: frozenset[Influence], lucky: bool = False, crafted: bool = False) -> Cells:
        """The roll law of `mod` at its table tier (that of the pool of an item with these influences); see `_rolls.py`."""
        context = self._context(influences)
        key = (mod.id, lucky, crafted)
        law = context.laws.get(key)
        if law is None:
            law = context.laws[key] = roll_law(self.goal.leaves, mod, context.tiers.get(mod.id, 1), crafted, lucky)
        return law

    def _rollable_mods(self, influences: frozenset[Influence]):
        """The ordinary mods a roll limit can tell apart by their values: those named by a leaf whose law has more than one outcome."""
        seen: set[str] = set()
        for mod_id in self._roll_ids:
            mod = self.data.mods.get(mod_id)
            if mod is not None and mod.domain != "crafted" and mod_id not in seen:
                seen.add(mod_id)
                if is_rollable(self._law(mod, influences)):
                    yield mod

    def _profile(self, mod: Mod, influences: frozenset[Influence] = frozenset()) -> Hashable:
        """What `mod` gives each leaf as ints (the part of a family type that the goal decides); a `RollLaw` for a rollable mod.

        The law holds the fair and the lucky outcomes, so that two families that roll alike when fair but not
        when lucky are never one family type.
        """
        if not self._has_laws:
            return tuple(int(status) for status in self._drawn_contribution(mod, False, influences))
        cells = self._law(mod, influences)
        return RollLaw(cells, self._law(mod, influences, True)) if is_rollable(cells) else cells[0][0]

    def _guard_roll(self, mod: Mod) -> None:
        """Raise `OutOfScopeError` when a leaf names `mod` and limits its roll: a forced, crafted or fixed-result mod rolls a value no law is built for."""
        for leaf in self.goal.leaves:
            if mod.id in leaf.mod_ids and leaf.has_roll_limit:
                raise OutOfScopeError(
                    f"a roll limit on a forced, crafted or fixed-result new mod is not modelled yet (mod {mod.id})"
                )

    def _label(self, mod: Mod, influences: frozenset[Influence] = frozenset(), lucky: bool = False) -> Label:
        """The label of a drawn mod: its contribution to every leaf, as ints; with junk slots kept, also its side and kind.

        A mod whose roll changes what it gives the goal (a rollable mod) is labelled by its roll law (a `RollLaw`,
        with `lucky` the law of values rolled twice, the better kept); `_distribution` spreads it over the rolls.
        """
        context = self._context(influences)
        labels = context.lucky_labels if lucky else context.labels
        label = labels.get(mod.id)
        if label is None:
            if self._has_laws:
                cells = self._law(mod, influences, lucky)
                ints = RollLaw(cells) if is_rollable(cells) else cells[0][0]
            else:
                ints = tuple(int(status) for status in self._drawn_contribution(mod, False, influences))
            label = (ints, mod.generation_type, context.kinds.of(mod)) if context.kinds.tracked else ints
            labels[mod.id] = label
        return label

    def _labeller(self, influences: frozenset[Influence], lucky: bool = False):
        """`_label` as a function of the mod alone, for the influences of one item."""
        return lambda mod: self._label(mod, influences, lucky)

    def _slot_of(self, entry: ExplicitMod, influences: frozenset[Influence]) -> Slot:
        """The slot of a mod of a concrete item that is not fractured."""
        mod = self.data.mods[entry.mod_id]
        side, contribution = Side(mod.generation_type), self._contribution(entry)
        if entry.crafted:
            return Slot(side, self._canonical_id(entry, influences), contribution, True)
        return Slot(side, self._context(influences).kinds.of(mod), contribution)

    def _canonical_id(self, entry: ExplicitMod, influences: frozenset[Influence]) -> str:
        """The canonical id of a mod of a concrete item (see `_canonical_for`)."""
        return self._canonical_for(self.data.mods[entry.mod_id], self._contribution(entry), entry.crafted, influences)

    def _canonical_groups(self) -> dict[tuple, list[Mod]]:
        """Every mod of the data by (families, side, domain): the mods a canonical id stands for."""
        if self._canonical_group is None:
            groups: dict[tuple, list[Mod]] = defaultdict(list)
            for mod in self.data.mods.values():
                groups[(mod.families, mod.generation_type, mod.domain)].append(mod)
            self._canonical_group = groups
        return self._canonical_group

    def _canonical_for(
        self, own: Mod, contribution: tuple[Status, ...], crafted: bool, influences: frozenset[Influence]
    ) -> str:
        """The smallest id among the mods of the same families, side and domain that give `contribution`.

        With `metamods`, the mods must also carry the same tags an Attack or Caster metamod looks at.
        """
        key = (influences, own.id, contribution, crafted)
        found = self._canonical.get(key)
        if found is None:
            group = self._canonical_groups()[(own.families, own.generation_type, own.domain)]
            tags = protected_tags(own)
            matching = [
                mod.id
                for mod in group
                if self._drawn_contribution(mod, crafted, influences) == contribution
                and (not self._metamods or protected_tags(mod) == tags)
            ]
            found = min(matching) if matching else min(mod.id for mod in group)
            self._canonical[key] = found
        return found

    def _fractured_id(self, entry: ExplicitMod, influences: frozenset[Influence]) -> str:
        """The id a fractured mod of a concrete item has in the state.

        Its canonical id, except when an enabled action may fracture a mod the item holds
        (`Reads.fractures`) and the mod's family is told apart only by its family type: the state then holds
        the kind of that type ("~3", with the mod's tags), the same as the slot the mod was before it was fractured.
        """
        if self._kinds.fractures and not entry.crafted:
            kind = self._context(influences).kinds.of(self.data.mods[entry.mod_id])
            if kind.startswith(TYPE_PREFIX):
                return kind
        return self._canonical_id(entry, influences)

    def _item_of(
        self, state: CompressedState, erasing: bool, avoid: frozenset[str] = frozenset()
    ) -> tuple[Item, Origins]:
        """A concrete item the state stands for: its fractured mods, its crafted mods, and (unless
        the action erases them) one representative mod for every other slot, of distinct families.
        With it, where each of its mods came from (a fractured mod or a slot of the state).
        `avoid` are families the representative of a fractured family type must not be (to try its siblings).

        Raises `ItemError` when the state is not an item (a normal item with mods) and `ValueError`
        when it holds more mods of a kind than the base has families.
        """
        flags = state.flags
        influences = flags.influences
        origins: Origins = {}
        mods = []
        types = []  # fractured mods that the state holds as a family type: a concrete mod is found for each below
        for entry in state.fractured:
            if entry.mod_id.startswith(TYPE_PREFIX):
                types.append(entry)
                continue
            crafted = self.data.mods[entry.mod_id].domain == "crafted"  # a Fracturing Orb may fracture a crafted mod
            mods.append(
                ExplicitMod(
                    entry.mod_id,
                    self._context(influences).tiers.get(entry.mod_id, 1),
                    _low_values(self.data.mods[entry.mod_id]),
                    fractured=True,
                    crafted=crafted,
                )
            )
            origins[(entry.mod_id, True, crafted)] = entry
        taken = {
            family
            for entry in state.fractured
            if not entry.mod_id.startswith(TYPE_PREFIX)
            for family in held_families(self.data.mods[entry.mod_id])
        }
        for slot in state.slots:
            if slot.crafted:
                mod = self.data.mods[slot.kind]
                taken |= held_families(mod)
                mods.append(ExplicitMod(mod.id, self._context(influences).tiers.get(mod.id, 1), _low_values(mod), crafted=True))
                origins[(mod.id, False, True)] = slot
        if types or not erasing:
            kinds = self._context(influences).kinds
            for entry in types:
                blocked = taken | avoid
                mod = kinds.representative(kinds.side_of(entry.mod_id), entry.mod_id, blocked)
                taken |= blocked - avoid
                mods.append(
                    ExplicitMod(mod.id, self._context(influences).tiers.get(mod.id, 1), _low_values(mod), fractured=True)
                )
                origins[(mod.id, True, False)] = entry
            if not erasing:
                for slot in state.slots:
                    if not slot.crafted:
                        mod = kinds.representative(slot.side, slot.kind, taken)
                        mods.append(ExplicitMod(mod.id, self._context(influences).tiers.get(mod.id, 1), _low_values(mod)))
                        origins[(mod.id, False, False)] = slot
        item = Item.build(
            self.data,
            base_id=self.base_id,
            item_level=self.item_level,
            rarity=flags.rarity,
            influences=flags.influences,
            corrupted=flags.corrupted,
            mods=tuple(mods),
            implicits=self._implicits_of(state),
            quality=state.quality,
            veil_offer=() if erasing else tuple(entry.mod_id for entry in state.offer),  # an action that erases the junk erases the placeholder
            enchantment=self.enchantment,
        )
        return item, origins

    def _implicits_of(self, state: CompressedState) -> tuple[ImplicitMod, ...]:
        """The implicits of the item a state stands for: for each Eldritch side that holds one, the mod that stands for it at its lowest values."""
        implicits = []
        for side, held in zip(EldritchSide, state.implicits):  # the pair is in the order of EldritchSide: Searing Exarch, then Eater of Worlds
            if held.grade:
                mod = self._implicit_mod(side, held.grade, held.contribution)
                implicits.append(ImplicitMod(mod.id, held.grade, _low_values(mod)))
        return tuple(implicits)

    def _prepared(self, state: CompressedState, action: Action) -> _Prepared:
        """`_prepare`, refusing an action that consumes other items when `allow_inputs` is False (every kernel goes through here)."""
        prepared = self._prepare(state, action)
        if not self._allow_inputs and action.inputs(self.data, prepared.item):
            raise OutOfScopeError(
                "the action consumes other items, and the planner does not price them yet (ticket #212): "
                "its kernel would count them as free"
            )
        return prepared

    def _prepare(self, state: CompressedState, action: Action) -> _Prepared:
        """The outcomes of `action` on the item `state` stands for (cached), and where that item's mods came from.

        An action that reads no junk erases it, so the item holds only the crafted slots; with `metamods`
        no action is taken to erase, because a lock keeps the mods of its side: the item holds every slot,
        and what the action keeps is read back from `origins`, the rest is dropped.
        """
        erasing = not self._kinds.reads_junk(action) and not self._metamods
        slots = tuple(slot for slot in state.slots if slot.crafted) if erasing else state.slots
        key = (action, state.flags, state.fractured, slots, state.implicits, state.quality, () if erasing else state.offer)
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
                    enchantment=self.enchantment,
                )
                action.outcomes_under(self.data, bare, self._reading)
                raise
            try:
                outcomes = action.outcomes_under(self.data, item, self._reading)  # a refusal of the action comes first
            except NotApplicableError:
                self._refusal_depends_on_the_family(state, erasing, action, origins)
                raise
            self._check_type_blind(state, outcomes)
            self._check_fracture_without_partners(state, outcomes)
            prepared = _Prepared(outcomes, origins, item=item)
            self._prepared_by[key] = prepared
        return prepared

    def _refusal_depends_on_the_family(
        self, state: CompressedState, erasing: bool, action: Action, origins: Origins
    ) -> None:
        """Raise `OutOfScopeError` when the game's refusal of the representative item is not the game's answer for the state.

        A fractured mod held as a family type stands for any family of the type, and a refusal that comes
        from its family (an essence forcing a mod of it, a reforge whose tag it lacks) may not hold for the
        others. Each other family of the type is tried as the fractured mod; if one is accepted the refusal
        depends on the family. If all of them are refused too, the caller re-raises the refusal.
        """
        held = [entry for entry in state.fractured if entry.mod_id.startswith(TYPE_PREFIX)]
        kinds = self._context(state.flags.influences).kinds
        if not held or not any(kinds.shared_families(entry.mod_id) for entry in held):
            return
        avoid: set[str] = set()
        while True:
            before = len(avoid)
            for (mod_id, fractured, crafted), origin in origins.items():
                if fractured and not crafted and isinstance(origin, FracturedMod) and origin.mod_id.startswith(TYPE_PREFIX):
                    avoid |= held_families(self.data.mods[mod_id])
            if len(avoid) == before:
                return  # the representative did not change: every family of the type has been tried
            try:
                other, origins = self._item_of(state, erasing, frozenset(avoid))
            except (ItemError, ValueError):
                return  # no other family of the type is left to try
            try:
                action.outcomes_under(self.data, other, self._reading)
            except NotApplicableError:
                continue
            raise OutOfScopeError(
                "the item holds a fractured mod known only as a family type, and whether the game refuses this action "
                "depends on which family of the type was fractured"
            )

    def _check_fracture_without_partners(self, state: CompressedState, outcomes: ActionOutcomes) -> None:
        """Refuse a fracture, or a fractured mod known only as a family type, on a pool with a family that has mods on both sides.

        The family types of such a pool carry the other side of the family (`Kinds._type_kinds`), but the spread of a fractured
        type over the families that have it (`_add_fractured`) has no test with them, so a Cobalt or Viridian Jewel does not
        get a planned fracture. Raises `OutOfScopeError`.
        """
        if not (outcomes.fractures or any(entry.mod_id.startswith(TYPE_PREFIX) for entry in state.fractured)):
            return
        if self._has_partners is None:
            empty = Item.build(self.data, base_id=self.base_id, item_level=self.item_level, rarity=Rarity.RARE)
            self._has_partners = bool(partners(build_pool(self.data, empty)))
        if self._has_partners:
            raise OutOfScopeError(
                "a fracture on an item whose pool has a family with mods on both sides (a Cobalt or Viridian Jewel) "
                "is not modelled in the compressed state"
            )

    def _check_type_blind(self, state: CompressedState, outcomes: ActionOutcomes) -> None:
        """Refuse a draw that could tell apart the families behind a fractured mod held as a family type.

        A fractured mod of such a state stands for any family of its type (`_fractured_id`), which is exact
        only while the action draws from the plain pool: a guaranteed tag (a Harvest reforge), another weight
        (a fossil) or a forced mod of one of those families (an essence) can tell them apart, and the kernel
        of the one representative would then be wrong for the others. A fixed result (Annulment, Scouring, a
        bench craft, the Fracturing Orb) never draws, and a type of one family has nobody to be mistaken for.
        Raises `OutOfScopeError`.
        """
        held = [entry for entry in state.fractured if entry.mod_id.startswith(TYPE_PREFIX)]
        if not held:
            return
        influences = state.flags.influences
        kinds = self._context(influences).kinds
        members = set().union(*(kinds.shared_families(entry.mod_id) for entry in held))
        if not members:
            return
        for _, part in outcomes.components:
            if isinstance(part, (Fixed, Rerolled)):
                continue  # neither draws: a fractured mod keeps its value whatever its family is
            forced = set() if part.forced is None else held_families(self.data.mods[part.forced])
            plain = part.tag is None and part.pool == build_pool(self.data, part.retained)
            if forced & members or not plain:
                raise OutOfScopeError(
                    "the item holds a fractured mod known only as a family type, and this action draws from a pool "
                    "that can tell the families of that type apart (a guaranteed tag, other weights, or a forced mod "
                    "of one of them), so the result would depend on which family was fractured"
                )

    def _mixture_kernel(self, state: CompressedState, prepared: _Prepared) -> dict[CompressedState, Fraction]:
        """The kernel of a result that is a mixture of parts: each part gives its states, weighted by its probability.

        A part is a fixed result (the mods that stay, the new ones), a rerolled result (the same mods, the
        values of some rolled afresh) or a pool draw (the same, then the new draws seen through the label);
        with a fracture one finished mod also becomes fractured.
        """
        outcomes = prepared.outcomes
        self._check_parts(outcomes)
        signatures = self._signatures_of(prepared)
        result: dict[CompressedState, Fraction] = defaultdict(Fraction)
        for (share, part), signature, split in zip(outcomes.components, signatures, self._splits_of(prepared)):
            if isinstance(part, Fixed):
                self._add_fixed(result, share, split)  # a fixed result that fractures a mod holds it fractured already
            elif isinstance(part, Rerolled):
                self._add_rerolled(result, share, part, prepared.origins, split)
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

        A mod the item given to the action held is the fractured mod or slot it came from; a fractured
        mod whose unfractured form was a slot is that slot turned into a fractured mod (a Fracturing
        Orb); any other mod is new: its contribution is that of its table tier at low rolls, and it is a
        slot when it is crafted or when junk is kept. Raises `OutOfScopeError` for a new mod a leaf limits
        the roll of.
        """
        influences = retained.influences
        flags = Flags(retained.rarity, retained.corrupted, influences)
        fractured: list[FracturedMod] = []
        kept: list[Slot] = []
        new: list[Slot] = []
        new_ids: list[str] = []
        contributions: list[tuple[Status, ...]] = []
        for entry in retained.mods:
            origin = origins.get((entry.mod_id, entry.fractured, entry.crafted))
            if origin is None and entry.fractured:
                origin = self._fractured_slot(origins.get((entry.mod_id, False, entry.crafted)), entry, influences)
            if isinstance(origin, FracturedMod):
                fractured.append(origin)
                contributions.append(origin.contribution)
            elif isinstance(origin, Slot):
                kept.append(origin)
                contributions.append(origin.contribution)
            else:
                mod = self.data.mods[entry.mod_id]
                self._guard_roll(mod)
                contribution = self._drawn_contribution(mod, entry.crafted, influences)
                contributions.append(contribution)
                new_ids.append(mod.id)
                if entry.fractured:
                    fractured.append(FracturedMod(self._canonical_of_mod(mod, influences), contribution))
                elif entry.crafted:
                    new.append(Slot(Side(mod.generation_type), self._canonical_id(entry, influences), contribution, True))
                elif self._kinds.tracked:
                    new.append(Slot(Side(mod.generation_type), self._context(influences).kinds.of(mod), contribution))
        fractured.sort(key=lambda entry: (entry.mod_id, entry.contribution))
        status = best_of(len(self.goal.leaves), contributions)
        held = self._held_by(retained.implicits, retained.quality, retained.veil_offer, influences)
        return _Split(flags, tuple(fractured), tuple(kept), tuple(new), status, tuple(new_ids), *held)

    def _fractured_slot(self, slot, entry: ExplicitMod, influences: frozenset[Influence]) -> FracturedMod | None:
        """The fractured mod that the slot `slot` becomes when the action fractures its mod `entry`; None when it is no slot.

        The identity is the one `compress` gives the concrete fractured mod: a crafted mod keeps its canonical
        id (the slot's kind), a family told apart only by its family type keeps that kind (when an enabled
        action may fracture the mods the item holds), any other family the canonical id at the slot's contribution.
        """
        if not isinstance(slot, Slot):
            return None
        if slot.crafted or (self._kinds.fractures and base_kind(slot.kind).startswith(TYPE_PREFIX)):
            return FracturedMod(slot.kind, slot.contribution)
        own = self.data.mods[entry.mod_id]
        return FracturedMod(self._canonical_for(own, slot.contribution, False, influences), slot.contribution)

    def _add_fixed(self, result: dict[CompressedState, Fraction], share: Fraction, split: _Split) -> None:
        """Add the one state of a fixed result."""
        slots = sorted((*split.kept, *split.new), key=lambda slot: slot.key)
        result[CompressedState(split.flags, split.fractured, split.status, tuple(slots), split.implicits, split.quality, split.offer)] += share

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
        held = (split.implicits, split.quality, split.offer)
        whole = share == 1
        for best, drawn, chance in self._expanded_distribution(signature, part):
            if not drawn:
                slots = stays_tuple
            elif not stays:
                slots = drawn
            else:
                slots = tuple(sorted(stays + list(drawn), key=_SLOT_KEY))
            state = CompressedState(flags, fractured, tuple(map(max, stay_status, best)), slots, *held)
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
        influences = split.flags.influences
        self._refuse_rollable_fracture(part, signature)
        families: dict[FamilyType, list] = defaultdict(list)
        for family in part.pool:
            families[self._family_type(family, None, influences)].append(family)
        for (kind, family_type, label, best, rest), chance in self._fracture_entries(part, signature):
            if kind == "none":
                options = [(None, chance)]
            elif kind == "forced":
                options = [(self.data.mods[part.forced], chance)]
            else:
                members = families[family_type]
                options = [(self._mod_with_label(family, label, influences), chance / len(members)) for family in members]
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
                    entry = FracturedMod(
                        self._canonical_of_mod(mod, influences), self._drawn_contribution(mod, False, influences)
                    )
                    fractured = tuple(sorted((*fractured, entry), key=lambda e: (e.mod_id, e.contribution)))
                result[CompressedState(split.flags, fractured, status, tuple(slots), split.implicits, split.quality, split.offer)] += share * each

    def _mod_with_label(self, family, label: Label, influences: frozenset[Influence]) -> Mod:
        """A mod of `family` with the label `label`: the mods of one family that share a label share a canonical id."""
        for entry in family.mods:
            if self._label(entry.mod, influences) == label:
                return entry.mod
        raise ValueError(f"the family {family.family} has no mod labelled {label!r}")

    def _canonical_of_mod(self, mod: Mod, influences: frozenset[Influence]) -> str:
        """The id of `mod` as a fractured mod, at its table tier and low rolls (see `_fractured_id`)."""
        tier = self._context(influences).tiers.get(mod.id, 1)
        return self._fractured_id(ExplicitMod(mod.id, tier, _low_values(mod), fractured=True), influences)

    def _forced_label(self, part: Outcomes) -> Label | None:
        if part.forced is None:
            return None
        mod = self.data.mods[part.forced]
        self._guard_roll(mod)  # the forced mod is a kept mod rolled at its low values: a roll limit on it has no law
        return self._label(mod, part.retained.influences)

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
        influences = part.retained.influences
        if partners(part.pool):
            raise OutOfScopeError("a fracture on an item whose pool has a family with mods on both sides is not modelled")
        label_of = self._labeller(influences)
        owner: dict[str, FamilyType] = {}
        for family in part.pool:
            family_type = self._family_type(family, None, influences)
            for entry in family.mods:
                owner[entry.mod.id] = family_type
        types = list(dict.fromkeys(owner.values())) or [None]
        single = part.fracturing()
        merged: dict[Hashable, Fraction] = defaultdict(Fraction)
        for number, marked in enumerate(types):

            def label(mod: Mod, marked=marked) -> Label:
                mark = "forced" if mod.id == part.forced else "type" if owner.get(mod.id) == marked else ""
                return (label_of(mod), mark)

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

    def _family_type(
        self,
        family,
        tag: str | None,
        influences: frozenset[Influence],
        blocked: frozenset[str] = frozenset(),
        lucky: bool = False,
    ) -> FamilyType:
        """The side and the sorted (label, weight, whether the guaranteed draw may pick it) of the mods of a family.

        A guaranteed draw (`tag`) picks only a mod with the tag and none of the `blocked` tags
        (an Attack or Caster metamod the item keeps).
        """
        return (
            family.side,
            tuple(
                sorted(
                    (
                        self._label(entry.mod, influences, lucky),
                        entry.weight,
                        tag is not None and tag in entry.mod.implicit_tags and allowed_by_tags(entry.mod, blocked),
                    )
                    for entry in family.mods
                )
            ),
        )

    def _signatures_of(self, prepared: _Prepared) -> tuple[Hashable, ...]:
        """The signature of every part of the outcomes (one, unless the action is a mixture)."""
        if prepared.signatures is None:
            prepared.signatures = tuple(
                ("fixed",)
                if isinstance(part, Fixed)
                else ("rerolled", part.lucky)
                if isinstance(part, Rerolled)
                else self._pool_signature(part)
                for _, part in prepared.outcomes.components
            )
        return prepared.signatures

    def _pool_signature(self, part: Outcomes) -> Hashable:
        free = part.free
        influences = part.retained.influences
        signature = _Signature(
            (
                part.tag,
                part.guaranteed_blocked,
                len(part.retained.mods),
                free[Side.PREFIX],
                free[Side.SUFFIX],
                tuple(sorted(part.totals.items())),
                tuple(
                    sorted(
                        self._family_type(family, part.tag, influences, part.guaranteed_blocked, part.rolls_lucky)
                        for family in part.pool
                    )
                ),
                tuple(  # the families with mods on both sides: which one-sided types are two sides of one family
                    sorted(
                        tuple(sorted(self._family_type(side, part.tag, influences, part.guaranteed_blocked) for side in sides))
                        for sides in partners(part.pool).values()
                    )
                ),
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
        tracked = self._kinds.tracked
        merged: dict[Hashable, Fraction] = defaultdict(Fraction)
        for outcome, chance in part.distribution(self._labeller(part.retained.influences, part.rolls_lucky)).items():
            for concrete, each in self._concrete(outcome) if self._has_laws else ((outcome, ONE),):
                weight = chance if each == 1 else chance * each
                if tracked:
                    merged[concrete] += weight
                else:
                    merged[tuple(best_of(width, (label for label, _ in concrete)))] += weight
        cached = dict(merged)
        self._cache[signature] = cached
        self._kernels += 1
        return cached

    def _concrete(self, outcome) -> tuple[tuple[Hashable, Fraction], ...]:
        """One outcome of the engine, whose labels may be roll laws, as the outcomes of concrete rolls with their chances.

        n mods that share a law (and, with junk kept, a side and a kind) spread over the outcomes of the law with
        the multinomial chance; the counts are merged onto the labels of the concrete rolls. An outcome with no
        law is itself, with chance 1.
        """
        tracked = self._kinds.tracked
        plain: dict[Hashable, int] = {}
        laws = []
        for label, count in outcome:
            core = label[0] if tracked else label
            if isinstance(core, RollLaw):
                laws.append((core, label[1:] if tracked else (), count))
            else:
                plain[label] = count
        if not laws:
            return ((outcome, ONE),)
        states: list[tuple[dict[Hashable, int], Fraction]] = [(plain, ONE)]
        for law, rest, count in laws:
            key = (law, count)
            spreads = self._spread.get(key)
            if spreads is None:
                spreads = self._spread[key] = multinomial(law.cells, count)
            following = []
            for counts, chance in states:
                for spread, each in spreads:
                    merged = dict(counts)
                    for ints, taken in spread:
                        label = (ints, *rest) if tracked else ints
                        merged[label] = merged.get(label, 0) + taken
                    following.append((merged, chance * each))
            states = following
        return tuple((frozenset(counts.items()), chance) for counts, chance in states)

    def _refuse_rollable_fracture(self, part: Outcomes, signature: Hashable) -> None:
        """Raise `OutOfScopeError` when the pool of a draw that fractures one of its mods holds a rollable mod.

        The fractured mod is found by marking its family type in the label, and the fracture entries are not
        spread over the rolls of a law: that is not built, so such a pool is refused (a Fractured Fossil whose
        pool holds a mod a roll limit tells apart).
        """
        if not self._has_laws or signature in self._unrolled:
            return
        influences = part.retained.influences
        for family in part.pool:
            for entry in family.mods:
                if is_rollable(self._law(entry.mod, influences)):
                    raise OutOfScopeError(
                        f"a roll limit on a mod of the pool of a draw that fractures one of its mods is not modelled yet (mod {entry.mod.id})"
                    )
        self._unrolled.add(signature)

    # --- a Divine Orb: the same mods, some values rolled afresh -----------------------------------------

    def _rerolled_slots(self, part: Rerolled, origins: Origins) -> tuple[list[Slot], list[Slot]]:
        """The slots of the item given to the action that stay as they are, and those whose values it rerolls."""
        if any(fractured for _, fractured, _ in part.changed):
            raise ValueError("a rerolled result does not change a fractured mod")
        unchanged: list[Slot] = []
        rerolled: list[Slot] = []
        for entry in part.given.mods:
            key = (entry.mod_id, entry.fractured, entry.crafted)
            origin = origins[key]
            if isinstance(origin, Slot):
                (rerolled if key in part.changed else unchanged).append(origin)
        return unchanged, rerolled

    def _slot_law(self, slot: Slot, influences: frozenset[Influence], lucky: bool) -> Cells | None:
        """The roll law of the mod a slot stands for when a reroll of values changes it; None for a slot a reroll cannot change.

        Only a slot of kind `"$<mod id>"` (a mod of a family whose roll the goal looks at) can change. A crafted
        slot knows only the canonical id of its mod: it is refused (`OutOfScopeError`) when any mod it may stand for
        is rollable, because the range of the real mod is not known.
        """
        if not self._has_laws:
            return None
        if slot.crafted:
            own = self.data.mods[slot.kind]
            group = self._canonical_groups()[(own.families, own.generation_type, own.domain)]
            if any(mod.id in self._roll_ids and is_rollable(self._law(mod, influences, lucky, True)) for mod in group):
                raise OutOfScopeError(
                    f"a Divine Orb rerolls a crafted mod ({own.id}) that a roll limit looks at: the range of the real mod "
                    "is not known from its canonical id, so its new roll cannot be modelled"
                )
            return None
        base = base_kind(slot.kind)
        if not base.startswith(MOD_PREFIX):
            return None
        cells = self._law(self.data.mods[base[len(MOD_PREFIX) :]], influences, lucky)
        return cells if is_rollable(cells) else None

    def _add_rerolled(
        self, result: dict[CompressedState, Fraction], share: Fraction, part: Rerolled, origins: Origins, split: _Split
    ) -> None:
        """Add the states of a result that rolls the values of some mods afresh.

        The fractured mods and the slots that are not changed stay as they are. Each changed slot of a rollable
        mod gets a new contribution drawn from the law of its mod, independently of the others, and the status
        of every leaf is the best over all the mods again. Equal states add up.
        """
        if not self._kinds.tracked:
            raise ValueError("a rerolled result needs the mods of the item as slots: the action must read the junk")
        influences = split.flags.influences
        unchanged, rerolled = self._rerolled_slots(part, origins)
        fixed = list(unchanged)
        laws: list[tuple[Slot, Cells]] = []
        for slot in rerolled:
            cells = self._slot_law(slot, influences, part.lucky)
            if cells is None:
                fixed.append(slot)
            else:
                laws.append((slot, cells))
        outcomes: list[tuple[tuple[Slot, ...], Fraction]] = [((), ONE)]
        for slot, cells in laws:
            outcomes = [
                (chosen + (Slot(slot.side, slot.kind, tuple(Status(value) for value in ints)),), before * each)
                for chosen, before in outcomes
                for ints, each in cells
            ]
        width = len(self.goal.leaves)
        held = [entry.contribution for entry in split.fractured]
        for chosen, chance in outcomes:
            slots = sorted((*fixed, *chosen), key=_SLOT_KEY)
            status = best_of(width, (*held, *(slot.contribution for slot in slots)))
            result[CompressedState(split.flags, split.fractured, status, tuple(slots), split.implicits, split.quality, split.offer)] += share * chance
