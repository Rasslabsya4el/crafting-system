"""The pilot count: how big the exact state graph is, found without building it (ADR-0023, ticket #127).

`Abstraction.estimate(starts, actions)` walks the states the way the solver's graph does (a goal is not
expanded) but pays a kernel only where one is needed:

* an action that erases the junk (`Reads.junk` false: a Chaos Orb, an essence, a resonator) has a
  kernel that depends on the flags, the fractured mods and, when the action keeps crafted mods, the
  crafted slots; when it erases them, only on which metamods they are (a crafted metamod makes a reroll
  refuse). Each such key is run once, through the real `Abstraction.kernel`; every other state with that
  key reuses its successors, so the whole walk pays one kernel per (action, key);
* a bench craft (an action that adds one named crafted mod and names the families it clashes with) and
  Remove Crafted Mods (it removes the crafted mods and nothing else) are deterministic, so the pilot
  does not call their kernel at all. It decides their legality itself, from the sets of families and the
  free slots (the rules of the bench: not on a corrupted or normal item, not on an empty one, not when a
  mod of the item shares a family with the craft, not on a full side, not when the item already holds
  the crafted mods it may: one, two with the enchantment of the extra crafted slot, three with the multimod; Remove Crafted Mods needs a crafted mod and a mod left over).

That second logic is written apart from `BenchCraft.outcomes` on purpose: `tests/test_abstraction_estimate.py`
compares its count with the real expansion on random crafts and starts;
* any other action that reads the junk (an addition: Augmentation, Regal, Exalted; Annulment) is **walked**.
  Its kernel depends on the whole set of held families and kinds, so there is no cheap closed form: the walk
  calls the real `Abstraction.kernel` for it on every state it expands (an `ActionError` means the action is
  not legal there) and the transitions are the kernel's size. A walk of these actions pays one real kernel per
  state and action, so a caller passes the smaller `ADDING_LIMIT` for them (`needs_walk` tells whether to);
  `Estimate.walked` says that some were among the actions. A walked action whose kernel cannot be computed at
  all (a `ValueError` that is not an `ActionError`, which a build would meet too) makes `estimate` raise
  `EstimateRefused`, so a caller falls back to building the graph without a forecast.

The result also keeps the states it reached, so that a coarse level can be forecast without a second
walk (`Estimate.coarsened`), and a closed prefix of the graph with its true weights, for a calibration
solve (`Estimate.first_layers`; the prefix kernel of a walked action is its real kernel). Time enters only through the injected `clock`, to measure the cost of a
repeated kernel call per outcome (`kernel_rate`; the first walked kernel is measured the same way when no reroll was); a test injects a counter.
"""

import time
from collections import deque
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from fractions import Fraction

from crafting_system.actions import Action, ActionError, crafted_limit_of
from crafting_system.items import Metamod, Rarity, Side, capacity

from ._kernel import Abstraction, integer_weights
from ._kinds import ALIKE, base_kind, held_families, kind_families
from ._state import CompressedState, best_of

METAMOD_FAMILIES = frozenset(metamod.value for metamod in Metamod)
DEFAULT_LIMIT = 400_000
ADDING_LIMIT = 20_000  # the state limit for a query with walked actions: each state there pays a real kernel call
VARIANT_FACTOR = 2  # a coarse level with variants has two kernels (the lightest and the heaviest member) per action that declares `Reads.variants`


class EstimateRefused(ValueError):
    """The pilot cannot count this set of actions: the kernel of one of them cannot be computed."""


@dataclass(frozen=True)
class Estimate:
    """What the pilot found.

    `states` and `transitions` are the reachable states (goals included, not expanded) and the sum of
    the sizes of the kernels of every action there, which is the edge count of the solver's graph.
    `outcomes` is the number of kernel outcomes a build computes (it is `transitions` for the exact graph,
    more for a coarse level, whose kernels are pushed through the block map). `kernel_rate` is the
    seconds one outcome of a repeated, cached kernel call takes; 0.0 when no kernel was run. `solves` is
    how many models are solved (2 for the two bounds). With `complete` false the walk stopped at its
    state limit and every count is a lower bound. `walked` tells that an action was walked (its kernel run
    for real on every state), which is what makes a walk expensive.
    """

    states: int
    transitions: int
    outcomes: int
    kernel_rate: float
    complete: bool = True
    solves: int = 1
    walked: bool = False
    _pilot: "_Pilot | None" = field(default=None, repr=False, compare=False)

    def seconds(self, r_kernel: float, r_solve: float) -> float:
        """The predicted time of a build and solve: kernel outcomes at `r_kernel`, solved edges at `r_solve`."""
        return self.outcomes * r_kernel + self.solves * self.transitions * r_solve

    def coarsened(self, coarsening) -> "Estimate | None":
        """The forecast of a coarse level: its blocks are the images of the states reached here.

        The lower model may reach more blocks than the images (a member no route reaches), so this is a
        forecast, not a bound. None when the walk was cut short or did not keep its states. For a walked
        action the block is read through its first reached state; the transitions are the distinct blocks of
        the successors times the number of variants, `VARIANT_FACTOR` for an action that declares
        `Reads.variants` (a forecast, since the real count of variants is not known before the build) and 1
        for any other.
        """
        if self._pilot is None or not self.complete:
            return None
        return self._pilot.coarse_estimate(coarsening, self.kernel_rate)

    def first_layers(self, max_edges: int) -> Mapping[CompressedState, tuple[tuple[Action, tuple[tuple[CompressedState, int], ...]], ...]]:
        """The first states in breadth-first order and, for each non-goal one, its actions with integer weights.

        A closed prefix: the walk stops once about `max_edges` edges are taken, and an outcome that leaves the
        prefix is dropped, so a model made of it can be solved on its own. Empty without a pilot.
        """
        return {} if self._pilot is None else self._pilot.prefix(max_edges)


@dataclass(frozen=True)
class _Craft:
    """A bench-like action: the crafted slot it adds, the side it needs a place on, the families it clashes with."""

    action: Action
    side: Side
    families: frozenset[str]
    slot: object  # the Slot its mod makes


def _shape(data, action: Action) -> str:
    """How the pilot treats `action`: "reroll" (erases the junk), "craft" (a bench craft), "removal" (Remove Crafted Mods) or "walked"."""
    reads = action.reads(data)
    if not reads.junk:
        return "reroll"  # its real kernel is run once per key, which carries the implicits, the quality and the offer (`state.held`)
    adds = action.adds(data, None)
    named = adds.named
    if action.inputs(data, None):
        return "walked"  # the closed forms leave the inputs out: an action that consumes other items runs its real kernel
    if reads.item_state or adds.item_state:
        return "walked"  # the closed forms of a craft and of a removal change the slots only: an action that touches the implicits, the quality or the offer runs its real kernel
    if reads.families is not None and not reads.pool_weight and adds.crafted and not adds.draws and named is not None and len(named) == 1:
        return "craft"
    if reads.needs_crafted and not reads.pool_weight and named == frozenset() and not adds.draws:
        return "removal"
    return "walked"


def needs_walk(abstraction: Abstraction, actions: Iterable[Action]) -> bool:
    """Whether the pilot walks one of `actions` with real kernels (an addition, Annulment, any other action it has no closed form for).

    A caller asks before the walk, to pick the smaller `ADDING_LIMIT` for such a query.
    """
    return any(_shape(abstraction.data, action) == "walked" for action in actions)


class _Pilot:
    """The walk itself (see the module docstring)."""

    def __init__(self, abstraction: Abstraction, actions: Iterable[Action], clock: Callable[[], float]):
        if abstraction.rerolls_values:
            raise EstimateRefused(
                "an enabled action rerolls values: its rollable mods are slots by mod id, which the pilot count has no rule for"
            )
        self.abstraction = abstraction
        self.data = abstraction.data
        self.clock = clock
        self.rerolls: dict[Action, bool] = {}  # action -> whether it keeps crafted mods
        self.crafts: list[_Craft] = []
        self.removals: list[Action] = []
        self.walked: dict[Action, int] = {}  # action -> the number of kernels a coarse level needs for it (its variants)
        for action in actions:
            self._classify(action)
        # the limit of crafted mods by what the item holds: the enchantment is a constant of the problem, the multimod is read from the state
        self.limit_crafted = {
            multimod: crafted_limit_of(self.data, multimod=multimod, enchantment=abstraction.enchantment) for multimod in (False, True)
        }
        self._kernels: dict[Hashable, Mapping[CompressedState, Fraction] | None] = {}
        self._successors: dict[int, tuple[CompressedState, ...]] = {}  # id of a memoised kernel -> its states, listed once
        self._slot_metamods: dict[object, frozenset[str]] = {}
        self._measured: float | None = None
        self.reached: list[CompressedState] = []
        self.complete = True

    # --- what each action is --------------------------------------------------------------------------

    def _name(self, action: Action) -> str:
        try:
            return action.label(self.data)
        except ValueError:
            return repr(action)

    def _classify(self, action: Action) -> None:
        self.abstraction._check_enabled(action)  # a caller's bug, raised as `Abstraction.kernel` does
        shape = _shape(self.data, action)
        reads = action.reads(self.data)
        adds = action.adds(self.data, None)
        if shape == "reroll":
            self.rerolls[action] = adds.keeps_crafted
        elif shape == "craft":
            (mod_id,) = adds.named
            mod = self.data.mods[mod_id]
            self.crafts.append(_Craft(action, Side(mod.generation_type), frozenset(reads.families), self.abstraction.crafted_slot(mod_id)))
        elif shape == "removal":
            self.removals.append(action)
        else:
            self.walked[action] = VARIANT_FACTOR if reads.variants else 1

    # --- the keys and kernels of rerolls ---------------------------------------------------------------

    def _metamods(self, state: CompressedState) -> frozenset[str]:
        found: set[str] = set()
        for slot in state.slots:
            if slot.crafted:
                held = self._slot_metamods.get(slot)
                if held is None:
                    held = self._slot_metamods[slot] = METAMOD_FAMILIES & set(self.data.mods[slot.kind].families)
                found |= held
        return frozenset(found)

    def _key(self, keeps_crafted: bool, state: CompressedState) -> Hashable:
        if self.abstraction.models_metamods:  # a lock keeps the junk of its side, so every slot decides the kernel
            return (None, state.flags, state.fractured, state.slots, state.held)
        if keeps_crafted:
            return (True, state.flags, state.fractured, tuple(slot for slot in state.slots if slot.crafted), state.held)
        return (False, state.flags, state.fractured, self._metamods(state), state.held)

    def kernel_of(self, action: Action, keeps_crafted: bool, state: CompressedState) -> Mapping[CompressedState, Fraction] | None:
        """The real kernel of a reroll on `state`, once per key; None when the action refuses there."""
        key = (action, self._key(keeps_crafted, state))
        if key in self._kernels:
            return self._kernels[key]
        try:
            found = self.abstraction.kernel(state, action)
        except ActionError:
            found = None
        self._kernels[key] = found
        if found:
            self._successors[id(found)] = tuple(found)
        if found:
            self._measure(state, action, found)
        return found

    def _measure(self, state: CompressedState, action: Action, found: Mapping[CompressedState, Fraction]) -> None:
        """The seconds per outcome of a repeated kernel call, taken once on the first kernel that has outcomes."""
        if self._measured is None:
            began = self.clock()
            self.abstraction.kernel(state, action)  # the second call: its caches are warm, as in a build
            self._measured = (self.clock() - began) / len(found)

    def walked_kernel(self, action: Action, state: CompressedState) -> Mapping[CompressedState, Fraction] | None:
        """The real kernel of a walked action on `state`, run for every state; None when the action refuses there.

        It is not memoised: nothing is known to decide it besides the whole state, and each call returns a new dict.
        """
        try:
            found = self.abstraction.kernel(state, action)
        except ActionError:
            return None
        except ValueError as error:  # a build would meet the same error, so there is nothing to forecast
            raise EstimateRefused(f"the kernel of {self._name(action)} cannot be computed: {error}") from error
        if found:
            self._measure(state, action, found)
        return found or None

    # --- legality of the deterministic actions ----------------------------------------------------------

    def _holds(self, state: CompressedState) -> tuple[set[str], dict[Side, int], int]:
        """The families the mods of the state occupy, the mods per side, and the crafted mods."""
        mods = self.data.mods
        held: set[str] = set()
        used = {Side.PREFIX: 0, Side.SUFFIX: 0}
        crafted = 0
        for entry in state.fractured:
            mod = mods.get(entry.mod_id)
            if mod is None:
                raise EstimateRefused(
                    f"the state holds a fractured mod as the family type {entry.mod_id}: the pilot count has no rule for a fracture made mid-route"
                )
            held |= held_families(mod)
            used[Side(mod.generation_type)] += 1
        for slot in state.slots:
            used[slot.side] += 1
            if slot.crafted:
                crafted += 1
                held |= held_families(mods[slot.kind])
            elif base_kind(slot.kind) != ALIKE and not slot.kind.startswith("~"):
                held |= kind_families(slot.kind)
        return held, used, crafted

    def expand(
        self, state: CompressedState
    ) -> Iterable[tuple[Action, tuple[CompressedState, ...], Mapping[CompressedState, Fraction] | None]]:
        """Each action that is legal on `state`, its successors and, for a reroll or a walked action, its kernel (None for a deterministic action)."""
        self.abstraction.prime(  # the kernels below are cheap once their pools' distributions exist; those are made side by side (#250)
            [(state, action) for action, keeps in self.rerolls.items() if (action, self._key(keeps, state)) not in self._kernels]
            + [(state, action) for action in self.walked]
        )
        for action, keeps in self.rerolls.items():
            found = self.kernel_of(action, keeps, state)
            if found:
                yield action, self._successors[id(found)], found
        for action in self.walked:
            found = self.walked_kernel(action, state)
            if found:
                yield action, tuple(found), found
        if not (self.crafts or self.removals):
            return
        flags = state.flags
        if flags.corrupted or flags.rarity is Rarity.NORMAL or not (state.fractured or state.slots):
            return
        held, used, crafted = self._holds(state)
        limit = self.limit_crafted[Metamod.MULTIPLE_CRAFTED_MODS.value in self._metamods(state)]
        if self.crafts and crafted < limit:  # the multimod and the extra crafted slot lift the limit of crafted mods (ticket #68, ADR-0053)
            room = capacity(self.data, self.abstraction.base_id, flags.rarity)
            for craft in self.crafts:
                if used[craft.side] < room.of(craft.side) and not (craft.families & held):
                    status = tuple(max(a, b) for a, b in zip(state.status, craft.slot.contribution))
                    slots = tuple(sorted((*state.slots, craft.slot), key=lambda slot: slot.key))
                    yield craft.action, (replace(state, status=status, slots=slots),), None
        if crafted and self.removals:
            kept = [slot for slot in state.slots if not slot.crafted]
            if state.fractured or kept:
                status = best_of(
                    len(state.status),
                    [entry.contribution for entry in state.fractured] + [slot.contribution for slot in kept],
                )
                after = replace(state, status=status, slots=tuple(kept))
                for action in self.removals:
                    yield action, (after,), None

    # --- the walk ---------------------------------------------------------------------------------------

    def run(self, starts: Iterable[CompressedState], limit: int, seconds: float | None = None) -> Estimate:
        seen = dict.fromkeys(starts)
        deadline = None if seconds is None else self.clock() + seconds
        queue = deque(seen)
        transitions = 0
        scanned: set[int] = set()
        while queue:
            state = queue.popleft()
            if self.abstraction.is_goal(state):
                continue
            for action, successors, kernel in self.expand(state):
                transitions += len(successors)
                if action in self.rerolls:  # only a memoised kernel is the same dict twice; a walked kernel is scanned every time
                    if id(kernel) in scanned:
                        continue  # every state of this kernel is already in `seen`
                    scanned.add(id(kernel))
                for successor in successors:
                    if successor not in seen:
                        seen[successor] = None
                        queue.append(successor)
            if len(seen) > limit or (deadline is not None and self.clock() > deadline):
                self.complete = False
                break
        self.reached = list(seen)
        return Estimate(len(seen), transitions, transitions, self._measured or 0.0, self.complete, 1, bool(self.walked), self)

    # --- levels and calibration ---------------------------------------------------------------------------

    def coarse_estimate(self, coarsening, kernel_rate: float) -> Estimate:
        """The counts of the lower model, each block read through the first state that maps to it."""
        representatives: dict[CompressedState, CompressedState] = {}
        for state in self.reached:
            representatives.setdefault(coarsening.coarsen(state), state)
        transitions = outcomes = 0
        pushed: dict[Hashable, int] = {}
        for block, state in representatives.items():
            if self.abstraction.is_goal(block):
                continue
            for action, successors, kernel in self.expand(state):
                if kernel is None:
                    transitions += 1  # a deterministic action: one pushed edge
                    outcomes += 1
                    continue
                if action in self.walked:  # no key to share: the block's representative is expanded as it is
                    factor = self.walked[action]
                    transitions += len({coarsening.coarsen(successor) for successor in successors}) * factor
                    outcomes += len(successors) * factor
                    continue
                key = (action, self._key(self.rerolls[action], state))
                if key not in pushed:
                    pushed[key] = len({coarsening.coarsen(successor) for successor in successors})
                    outcomes += len(successors)
                transitions += pushed[key]
        return Estimate(len(representatives), transitions, outcomes, kernel_rate, True, 2, bool(self.walked), None)

    def prefix(self, max_edges: int) -> dict[CompressedState, tuple[tuple[Action, tuple[tuple[CompressedState, int], ...]], ...]]:
        taken: dict[CompressedState, list[tuple[Action, Mapping[CompressedState, Fraction]]]] = {}
        edges = 0
        for state in self.reached:
            if edges >= max_edges:
                break
            if self.abstraction.is_goal(state):
                continue
            actions = []
            for action, successors, kernel in self.expand(state):
                actions.append((action, kernel if kernel is not None else {successors[0]: Fraction(1)}))
                edges += len(successors)
            taken[state] = actions
        inside = set(taken) | {state for state in self.reached if self.abstraction.is_goal(state)}
        closed = {}
        for state, actions in taken.items():
            kept = []
            for action, kernel in actions:
                weights = integer_weights({s: c for s, c in kernel.items() if s in inside})
                if weights:
                    kept.append((action, tuple(weights.items())))
            closed[state] = tuple(kept)
        return closed


def estimate(
    abstraction: Abstraction,
    starts: Iterable[CompressedState],
    actions: Iterable[Action],
    *,
    limit: int = DEFAULT_LIMIT,
    seconds: float | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Estimate:
    """The pilot count of the graph of `actions` from `starts`; see the module docstring.

    `actions` are the actions of the model (every one that reads the junk must be among those the
    abstraction was built with). The walk stops once `limit` states are reached, or `seconds` have passed on
    `clock` (a walked action pays a real kernel call per state, so a caller bounds the pilot's own time), and says so
    (`complete` false); pass `ADDING_LIMIT` when `needs_walk(abstraction, actions)`. Raises `EstimateRefused`
    for a walked action whose kernel cannot be computed.
    """
    return _Pilot(abstraction, actions, clock).run(starts, limit, seconds)
