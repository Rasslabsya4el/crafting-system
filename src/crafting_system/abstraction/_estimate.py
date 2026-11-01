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
  the crafted mods it may: one, or three with the multimod; Remove Crafted Mods needs a crafted mod and a mod left over).

That second logic is written apart from `BenchCraft.outcomes` on purpose: `tests/test_abstraction_estimate.py`
compares its count with the real expansion on random crafts and starts. An action of any other shape
(an addition, a fixed result that is not a bench craft) makes
`estimate` raise `EstimateRefused`, so a caller falls back to building the graph without a forecast.

The result also keeps the states it reached, so that a coarse level can be forecast without a second
walk (`Estimate.coarsened`), and a closed prefix of the graph with its true weights, for a calibration
solve (`Estimate.first_layers`). Time enters only through the injected `clock`, to measure the cost of a
repeated kernel call per outcome (`kernel_rate`); a test injects a counter.
"""

import time
from collections import deque
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction

from crafting_system.actions import Action, ActionError
from crafting_system.items import Metamod, Rarity, Side, capacity
from crafting_system.rules import get_rule

from ._kernel import Abstraction, integer_weights
from ._kinds import ALIKE, base_kind, held_families
from ._state import CompressedState, best_of

ONE_CRAFTED_MOD = get_rule("bench_craft.one_crafted_mod_by_default")
MULTIMOD_LIMIT = get_rule("metamods.multimod_raises_crafted_limit")
METAMOD_FAMILIES = frozenset(metamod.value for metamod in Metamod)
DEFAULT_LIMIT = 400_000


class EstimateRefused(ValueError):
    """The pilot cannot count this set of actions: one has a shape it has no rule for."""


@dataclass(frozen=True)
class Estimate:
    """What the pilot found.

    `states` and `transitions` are the reachable states (goals included, not expanded) and the sum of
    the sizes of the kernels of every action there, which is the edge count of the solver's graph.
    `outcomes` is the number of kernel outcomes a build computes (it is `transitions` for the exact graph,
    more for a coarse level, whose kernels are pushed through the block map). `kernel_rate` is the
    seconds one outcome of a repeated, cached kernel call takes; 0.0 when no kernel was run. `solves` is
    how many models are solved (2 for the two bounds). With `complete` false the walk stopped at its
    state limit and every count is a lower bound.
    """

    states: int
    transitions: int
    outcomes: int
    kernel_rate: float
    complete: bool = True
    solves: int = 1
    _pilot: "_Pilot | None" = field(default=None, repr=False, compare=False)

    def seconds(self, r_kernel: float, r_solve: float) -> float:
        """The predicted time of a build and solve: kernel outcomes at `r_kernel`, solved edges at `r_solve`."""
        return self.outcomes * r_kernel + self.solves * self.transitions * r_solve

    def coarsened(self, coarsening) -> "Estimate | None":
        """The forecast of a coarse level: its blocks are the images of the states reached here.

        The lower model may reach more blocks than the images (a member no route reaches), so this is a
        forecast, not a bound. None when the walk was cut short or did not keep its states.
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
        for action in actions:
            self._classify(action)
        self.limit_crafted = ONE_CRAFTED_MOD.value
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
        reads = action.reads(self.data)
        adds = action.adds(self.data, None)
        self.abstraction._check_enabled(action)  # a caller's bug, raised as `Abstraction.kernel` does
        if not reads.junk:
            self.rerolls[action] = adds.keeps_crafted
            return
        named = adds.named
        if reads.families is not None and not reads.pool_weight and adds.crafted and not adds.draws and named is not None and len(named) == 1:
            (mod_id,) = named
            mod = self.data.mods[mod_id]
            self.crafts.append(_Craft(action, Side(mod.generation_type), frozenset(reads.families), self.abstraction.crafted_slot(mod_id)))
            return
        if reads.needs_crafted and not reads.pool_weight and adds.named == frozenset() and not adds.draws:
            self.removals.append(action)
            return
        raise EstimateRefused(f"{self._name(action)} has no rule in the pilot count (it is neither a reroll, a bench craft nor Remove Crafted Mods)")

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
            return (None, state.flags, state.fractured, state.slots)
        if keeps_crafted:
            return (True, state.flags, state.fractured, tuple(slot for slot in state.slots if slot.crafted))
        return (False, state.flags, state.fractured, self._metamods(state))

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
        if found and self._measured is None:
            began = self.clock()
            self.abstraction.kernel(state, action)  # the second call: its caches are warm, as in a build
            self._measured = (self.clock() - began) / len(found)
        return found

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
                kind = base_kind(slot.kind)
                held |= {kind} if kind.startswith("#") else set(kind.split("|"))
        return held, used, crafted

    def expand(
        self, state: CompressedState
    ) -> Iterable[tuple[Action, tuple[CompressedState, ...], Mapping[CompressedState, Fraction] | None]]:
        """Each action that is legal on `state`, its successors and, for a reroll, its kernel (None for a deterministic action)."""
        for action, keeps in self.rerolls.items():
            found = self.kernel_of(action, keeps, state)
            if found:
                yield action, self._successors[id(found)], found
        if not (self.crafts or self.removals):
            return
        flags = state.flags
        if flags.corrupted or flags.rarity is Rarity.NORMAL or not (state.fractured or state.slots):
            return
        held, used, crafted = self._holds(state)
        limit = MULTIMOD_LIMIT.value if Metamod.MULTIPLE_CRAFTED_MODS.value in self._metamods(state) else self.limit_crafted
        if self.crafts and crafted < limit:  # the multimod lifts the limit of crafted mods from one to three (ticket #68)
            room = capacity(self.data, self.abstraction.base_id, flags.rarity)
            for craft in self.crafts:
                if used[craft.side] < room.of(craft.side) and not (craft.families & held):
                    status = tuple(max(a, b) for a, b in zip(state.status, craft.slot.contribution))
                    slots = tuple(sorted((*state.slots, craft.slot), key=lambda slot: slot.key))
                    yield craft.action, (CompressedState(flags, state.fractured, status, slots),), None
        if crafted and self.removals:
            kept = [slot for slot in state.slots if not slot.crafted]
            if state.fractured or kept:
                status = best_of(
                    len(state.status),
                    [entry.contribution for entry in state.fractured] + [slot.contribution for slot in kept],
                )
                after = CompressedState(flags, state.fractured, status, tuple(kept))
                for action in self.removals:
                    yield action, (after,), None

    # --- the walk ---------------------------------------------------------------------------------------

    def run(self, starts: Iterable[CompressedState], limit: int) -> Estimate:
        seen = dict.fromkeys(starts)
        queue = deque(seen)
        transitions = 0
        scanned: set[int] = set()
        while queue:
            state = queue.popleft()
            if self.abstraction.is_goal(state):
                continue
            for _, successors, kernel in self.expand(state):
                transitions += len(successors)
                if kernel is not None:
                    if id(kernel) in scanned:
                        continue  # every state of this kernel is already in `seen`
                    scanned.add(id(kernel))
                for successor in successors:
                    if successor not in seen:
                        seen[successor] = None
                        queue.append(successor)
            if len(seen) > limit:
                self.complete = False
                break
        self.reached = list(seen)
        return Estimate(len(seen), transitions, transitions, self._measured or 0.0, self.complete, 1, self)

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
                key = (action, self._key(self.rerolls[action], state))
                if key not in pushed:
                    pushed[key] = len({coarsening.coarsen(successor) for successor in successors})
                    outcomes += len(successors)
                transitions += pushed[key]
        return Estimate(len(representatives), transitions, outcomes, kernel_rate, True, 2, None)

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
    clock: Callable[[], float] = time.perf_counter,
) -> Estimate:
    """The pilot count of the graph of `actions` from `starts`; see the module docstring.

    `actions` are the actions of the model (every one that reads the junk must be among those the
    abstraction was built with). The walk stops once `limit` states are reached and says so
    (`complete` false). Raises `EstimateRefused` for an action of a shape the pilot has no rule for.
    """
    return _Pilot(abstraction, actions, clock).run(starts, limit)
