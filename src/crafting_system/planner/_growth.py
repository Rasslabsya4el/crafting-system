"""Plan-led growth: the methods a round holds, grown from the plan in hand (#1414, #1276; OR-12, OR-13, OR-37, OR-39, OR-55).

The rule of the research note `docs/research/2026-11-22-rounds-design-2.md` (section 4), coded: no route, no guide's set and no method kind is
named here. Every choice is read from what the offers declare (`_offer_kinds._kind_of`, `Action.adds`, `Action.reads`, `Action.rarities`,
`Action.imprint_move`) and from the statuses of the states the plan in hand visits.

* **The table** (`OfferTable`). For each offer, at each shape the offers turn the start item into (one item per rarity, `_offers.reached_by`):
  its kind there, the rarities its outcomes have there, and its chance of making each wanted mod not on the start item PASSING in one use,
  the floors' own number (THE NUMBER pbar of `_offer_kinds`, for that one leaf): 1 for a craft, a veiled choice or a veil that names a mod
  passing the leaf (`finishes`), the declared bound or `reach_bound` for an erasing reroll, `add_bound` (or the declared draw's) for an
  addition, none for any other kind. And what it declares at the start item: that it fractures, makes or restores an imprint, needs a veiled
  placeholder or makes one, needs a crafted mod, adds crafted mods, adds no mod at all (a craft that only removes), and which metamods it adds
  (a lock of a side, a tag kept out of the draws, more crafted mods).
* **Round 0, the seed** (`seed`): per wanted mod not passing at the start, the `PER_ROLE` offers of least cost over chance (any kind, any shape).
* **The diagnosis of a plan in hand** (`Grower.next`). Its steps are its actions by their cost share (expected uses times price, read on the
  plan's lumped chain, `step_shares`); the dearest step `D` not diagnosed yet is read at the states where it acts: `W`, the wanted mods not
  passing there that some outcome of `D` makes pass (what `D` waits for), and `K`, the wanted mods passing there that some outcome of `D` loses
  (what `D` can destroy). The roles named for them:
  - **adders** for each mod of `W`: the `PER_ROLE` offers of least cost over chance on it that keep the mods they are given (an addition, a
    craft, a veiled choice or a veil: not a reroll), at any shape, among the offers the round that made the plan did not hold;
  - **moves**: for an adder whose best shape is not one `D` acts at, the cheapest offer of each step of the rarities between them;
  - **protectors** for each mod of `K`, among the offers that draw no mod (they keep the mods they are given; a reroll that also fractures
    keeps none of them): every one that fractures (when the states hold no fractured mod), the cheapest that adds the lock of the mod's side
    (unless every mod of `W` sits on that side: a step that waits for a mod of the other side still gains it under the lock), and the
    cheapest imprint that can be made at `D`'s shape (its outcomes are read there);
  - **cleaners and narrowers** for the adders: the cheapest craft that adds no mod and needs no crafted one (it removes a mod), the crafts that
    add no mod and need a crafted one when the round holds a crafted mod, and, among the offers that draw no mod, the cheapest that keeps each
    tag out of the draws that no wanted mod carries, and the cheapest of more crafted mods when the round holds two crafted mods.
  With no plan in hand the same roles are read at the start: `W` the wanted mods whose providers in the round all reroll, `K` every other
  wanted mod when one mod's only provider rerolls.
* **Dependencies** (`OfferTable.closure`): an offer that needs a veiled placeholder brings every offer that makes one and every other offer that
  needs one (a pick brings the Unveil, the veiled sources and the other picks); an offer that makes a placeholder brings those that need one;
  a restore brings the imprints and an imprint the restores.
* **The next round** holds the support of the plan in hand (the offers its policy uses), the run's named offers, the named roles and their
  dependencies; never the union of the earlier rounds. A set held by an earlier round names nothing new: the step is marked diagnosed and the
  next dearest is read. When no step names anything new the growth ends, and the rounds of `_rounds.widen` follow with the plan's support as
  their base.

The `PER_ROLE` count orders what is searched first; it cuts nothing (OR-12): every offer keeps its group in the widening rounds after the growth.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction

import numpy as np

from crafting_system.abstraction import Abstraction, CompressedState, Status, add_bound, declared_add_bound, declared_bounds, reach_bound
from crafting_system.actions import BLOCKED_TAG, BLOCKING, LOCKED_SIDE, NotApplicableError, OutOfScopeError
from crafting_system.data import GameData
from crafting_system.items import Item, Metamod, Rarity
from crafting_system.solver import linear_solve

from ._offer_kinds import ADD, CRAFT, FINISHING, REFUSED, REROLL, RESTART_KIND, _kind_of, finishes
from ._offers import BuyStartItem, PricedOffer, reached_by

GROWS = True  # every run grows its rounds from the plan in hand; the tests of the widening rounds' own mechanism set it off (`_plan.rounds_grower`)
PER_ROLE = 2  # the offers of least cost over chance a wanted mod brings for one role: an order of what is searched first, never a cut (OR-12)
KEEPS_MODS = (ADD, *FINISHING)  # the kinds that keep the mods they are given and add one: what an adder is (a reroll is not)
_LOCKS = {metamod.value: side for metamod, side in LOCKED_SIDE.items()}
_TAGS = {metamod.value: tag for metamod, tag in BLOCKED_TAG.items()}
_SIDES = frozenset({"prefix", "suffix"})  # the sides a rolled mod sits on (`Mod.generation_type`)


@dataclass
class Entry:
    """One offer as the growth reads it (module text)."""

    position: int
    label: str
    cost: float
    kinds: dict[Rarity, str] = field(default_factory=dict)  # its kind at each shape it was read at (`_kind_of`)
    leads: dict[Rarity, frozenset[Rarity]] = field(default_factory=dict)  # the rarities its outcomes have at each shape where it applies
    chance: dict[tuple[Rarity, int], Fraction] = field(default_factory=dict)  # (shape, leaf) -> its chance of making that leaf PASSING in one use
    fractures: bool = False
    draws: bool = True  # it draws mods (a reroll, an addition): it does not only keep the mods it is given, so it protects none of them
    makes_imprint: bool = False
    restores: bool = False
    needs_veiled: bool = False
    veils: bool = False
    needs_crafted: bool = False
    crafted: bool = False  # it adds mods it names as crafted ones
    removes: bool = False  # a craft that adds no mod: it only takes one off
    locks: frozenset = frozenset()  # the sides whose lock it may add
    keeps_out: frozenset[str] = frozenset()  # the tags it may keep out of the draws
    more_crafted: bool = False  # it may add the metamod of more crafted mods
    need: float = 0.0  # what the cheapest offer it needs to act costs (`OfferTable.priced_needs`): ranked with its price

    def acts_at(self, shapes) -> bool:
        """Whether it is read as acting at one of `shapes` (its kind there is not a refusal)."""
        return any(shape in self.kinds and self.kinds[shape] not in (REFUSED, RESTART_KIND) for shape in shapes)

    def ratio(self, leaf: int, shapes: Sequence[Rarity] | None = None) -> tuple[float, Rarity | None]:
        """Its least cost over chance on `leaf` over `shapes` (all its shapes when None), and the shape it is at; infinity when it has none."""
        best, at = math.inf, None
        for (shape, each), chance in self.chance.items():
            if each == leaf and chance > 0 and (shapes is None or shape in shapes):
                ratio = float(Fraction(self.cost + self.need) / chance) if math.isfinite(self.need) else math.inf
                if ratio < best:
                    best, at = ratio, shape
        return best, at


class OfferTable:
    """The offers of a run as the growth reads them (module text): `entries[i]` is the offer at position `i` of `offers`."""

    def __init__(self, data: GameData, abstraction: Abstraction, start: CompressedState, item: Item, priced: Sequence[PricedOffer],
                 ask: Callable[[], None] | None = None) -> None:  # fmt: skip
        self.data, self.goal = data, abstraction.goal
        shape = abstraction.compress(item) if getattr(start.flags, "unopened", False) else start
        self.start_rarity = item.rarity
        self.open = tuple(index for index in range(len(self.goal.leaves)) if shape.status[index] is not Status.PASSING)
        self.entries = [Entry(position, p.label, p.cost) for position, p in enumerate(priced)]
        actions = [p.offer.action for p in priced if not isinstance(p.offer.action, BuyStartItem) and not getattr(p.offer.action, "opens_listing", False)]
        items = [item, *(each for each in reached_by(data, item, lambda _item: actions)[1:] if not getattr(abstraction.compress(each).flags, "unopened", False))]
        for view in items:
            self._read_shape(abstraction, view, priced, ask)
        for entry, offer in zip(self.entries, priced):
            self._read_declarations(entry, offer, item)
        self.priced_needs()

    def priced_needs(self) -> None:
        """Each offer's cost as the roles rank it: its price plus the cheapest offer of what it needs to act (`closure`): a veiled choice is
        worth what a veiled placeholder costs to make, a restore what an imprint costs, so a free pick is not ranked as a free adder."""
        veil = min((entry.cost for entry in self.entries if entry.veils), default=math.inf)
        imprint = min((entry.cost for entry in self.entries if entry.makes_imprint), default=math.inf)
        for entry in self.entries:
            entry.need = (veil if entry.needs_veiled else 0.0) + (imprint if entry.restores else 0.0)

    def _read_shape(self, abstraction: Abstraction, view: Item, priced: Sequence[PricedOffer], ask) -> None:
        data, goal, rarity = self.data, self.goal, view.rarity
        bare = replace(abstraction.compress(view), slots=())
        rerolls: dict[type, list[int]] = {}
        for position, offer in enumerate(priced):
            if ask is not None and position % 256 == 0:
                ask()
            entry, action = self.entries[position], offer.offer.action
            try:
                kind, named = _kind_of(data, view, offer)
                entry.kinds[rarity] = kind
                if kind in (RESTART_KIND, REFUSED):
                    continue
                try:  # where its outcomes go from this shape's item (a craft refused on an empty item still has its chance, read below)
                    entry.leads[rarity] = frozenset(action.rarities(data, view))
                except (NotApplicableError, OutOfScopeError, ValueError):
                    pass
                if kind in FINISHING:
                    made = bool(action.adds(data, view).crafted)
                    for leaf in self.open:
                        if finishes(goal.leaves[leaf], named, made):
                            entry.chance[(rarity, leaf)] = Fraction(1)
                elif kind == ADD:
                    declared = action.added_draw(data, view) is not None
                    for leaf in self.open:
                        chance = declared_add_bound(abstraction, action, view, (leaf,)) if declared else add_bound(abstraction, bare, action, (leaf,))
                        if chance is not None and chance > 0:
                            entry.chance[(rarity, leaf)] = chance
                elif kind == REROLL:
                    adds = action.adds(data, view)
                    if not (adds.fractures or adds.keeps_crafted or action.reads(data).needs_crafted):
                        rerolls.setdefault(type(action), []).append(position)
            except (NotApplicableError, OutOfScopeError, ValueError):  # refused at this shape, or out of the data's scope: nothing read here
                continue
        for positions in rerolls.values():  # a class answers for its own actions at once (`declared_bounds`, #1073), the rest one by one
            if ask is not None:
                ask()
            for leaf in self.open:
                try:
                    found = declared_bounds(abstraction, bare, [priced[position].offer.action for position in positions], (leaf,))
                except (NotApplicableError, OutOfScopeError, ValueError):
                    found = [None] * len(positions)
                for position, bound in zip(positions, found):
                    if bound is None:
                        try:
                            bound = reach_bound(abstraction, bare, priced[position].offer.action, (leaf,))
                        except (NotApplicableError, OutOfScopeError, ValueError):
                            continue
                    if bound is not None and bound > 0:
                        self.entries[position].chance[(rarity, leaf)] = bound

    def _read_declarations(self, entry: Entry, offer: PricedOffer, item: Item) -> None:
        data, action = self.data, offer.offer.action
        if isinstance(action, BuyStartItem) or getattr(action, "opens_listing", False):
            return
        try:
            adds, reads = action.adds(data, item), action.reads(data)
        except (NotApplicableError, OutOfScopeError, ValueError):
            return
        move = action.imprint_move()
        entry.fractures, entry.draws = bool(adds.fractures), bool(adds.draws)
        entry.makes_imprint = move is not None and not move.restore
        entry.restores = move is not None and move.restore
        entry.needs_veiled, entry.veils, entry.needs_crafted = bool(reads.needs_veiled), bool(adds.veils), bool(reads.needs_crafted)
        entry.crafted = bool(adds.crafted) and bool(adds.named)
        entry.removes = adds.named == frozenset() and not adds.draws and CRAFT in entry.kinds.values()
        families: set[str] = set()
        if adds.named:
            families = {family for mod_id in adds.named if mod_id in data.mods for family in data.mods[mod_id].families}
        elif adds.named is None and adds.crafted:
            families = set(reads.families or ())  # a crafted mod it picks among the families it reads
        entry.locks = frozenset(_LOCKS[family] for family in families if family in _LOCKS)
        entry.keeps_out = frozenset(_TAGS[family] for family in families if family in _TAGS)
        entry.more_crafted = Metamod.MULTIPLE_CRAFTED_MODS.value in families

    def seed(self, per_role: int = PER_ROLE) -> set[int]:
        """Round 0: per wanted mod not passing at the start, the `per_role` offers of least cost over chance on it, any kind, any shape."""
        chosen: set[int] = set()
        for leaf in self.open:
            chosen.update(self._best(leaf, lambda entry: True, per_role))
        return chosen

    def _best(self, leaf: int, allowed: Callable[[Entry], bool], count: int, shapes: Sequence[Rarity] | None = None, held: frozenset[int] = frozenset()) -> list[int]:
        ranked = sorted(
            (ratio, entry.position) for entry in self.entries
            if entry.position not in held and allowed(entry) and math.isfinite(ratio := entry.ratio(leaf, shapes)[0])
        )  # fmt: skip
        return [position for _ratio, position in ranked[:count]]

    def side_of(self, leaf: int) -> str | None:
        """The side of the wanted mod `leaf` when every prefix or suffix that can pass it is on one side, else None (a unique's or another
        source's mod that passes it too is never rolled on the item, so it names no side)."""
        sides = {self.data.mods[mod_id].generation_type for mod_id in self.goal.leaves[leaf].mod_ids if mod_id in self.data.mods} & _SIDES
        return next(iter(sides)) if len(sides) == 1 else None

    def tags_of_wanted(self) -> frozenset[str]:
        return frozenset(tag for leaf in self.goal.leaves for mod_id in leaf.mod_ids if mod_id in self.data.mods for tag in self.data.mods[mod_id].implicit_tags)

    def cheapest(self, allowed: Callable[[Entry], bool], held: frozenset[int] = frozenset()) -> int | None:
        found = [(entry.cost, entry.position) for entry in self.entries if entry.position not in held and allowed(entry)]
        return min(found)[1] if found else None

    def roles(self, waits: set[int], risks: set[int], shapes: frozenset[Rarity], fractured: bool, held: frozenset[int], current: frozenset[int]) -> set[int]:
        """The offers named for a step that waits for `waits` and can lose `risks` at `shapes` (module text). `held` are the offers the round
        that made the plan held (adders are named among the others); `current` the offers the next round already holds."""
        named: set[int] = set()
        adders: list[tuple[int, Rarity | None]] = []
        for leaf in sorted(waits):
            for position in self._best(leaf, lambda entry: any(kind in KEEPS_MODS for kind in entry.kinds.values()) and not entry.removes, PER_ROLE, None, held):
                adders.append((position, self.entries[position].ratio(leaf)[1]))
        for position, at in adders:
            named.add(position)
            if at is not None and at not in shapes:
                named.update(self.moves(shapes, at))
        wait_sides = {self.side_of(leaf) for leaf in waits}
        for leaf in sorted(risks):
            if not fractured:
                named.update(entry.position for entry in self.entries if entry.fractures and not entry.draws and entry.acts_at(shapes))
            side = self.side_of(leaf)
            if side is not None and wait_sides != {side}:
                lock = self.cheapest(lambda entry, side=side: not entry.draws and any(getattr(each, "value", each) == side for each in entry.locks))
                if lock is not None:
                    named.add(lock)
            imprint = self.cheapest(lambda entry: entry.makes_imprint and not entry.draws and any(shape in entry.leads for shape in shapes))
            if imprint is not None:
                named.add(imprint)
        if adders or any(self.entries[position].crafted for position in current):
            holding = current | named
            cleaner = self.cheapest(lambda entry: entry.removes and not entry.needs_crafted)
            if cleaner is not None:
                named.add(cleaner)
            crafted = [position for position in holding if self.entries[position].crafted]
            if crafted:
                named.update(entry.position for entry in self.entries if entry.removes and entry.needs_crafted)
            if len(crafted) >= 2:
                more = self.cheapest(lambda entry: entry.more_crafted and not entry.draws)
                if more is not None:
                    named.add(more)
            wanted_tags = self.tags_of_wanted()
            for tag in sorted({tag for entry in self.entries for tag in entry.keeps_out} - wanted_tags):
                narrower = self.cheapest(lambda entry, tag=tag: tag in entry.keeps_out and not entry.draws)
                if narrower is not None:
                    named.add(narrower)
        return named

    def moves(self, shapes: frozenset[Rarity], to: Rarity) -> set[int]:
        """The cheapest offer of each step on the cheapest way from `shapes` to the shape `to` (the rarities the offers' outcomes have)."""
        best: dict[Rarity, tuple[float, tuple[int, ...]]] = {shape: (0.0, ()) for shape in shapes}
        frontier = list(shapes)
        while frontier:
            shape = frontier.pop(0)
            cost, path = best[shape]
            for entry in self.entries:
                for lead in entry.leads.get(shape, ()):
                    if lead != shape and (lead not in best or cost + entry.cost < best[lead][0]):
                        best[lead] = (cost + entry.cost, (*path, entry.position))
                        frontier.append(lead)
        return set(best.get(to, (0.0, ()))[1])

    def closure(self, positions: set[int]) -> set[int]:
        """`positions` with what each needs to act (module text, dependencies)."""
        found = set(positions)
        while True:
            more = set()
            chosen = [self.entries[position] for position in found]
            if any(entry.needs_veiled or entry.veils for entry in chosen):
                more.update(entry.position for entry in self.entries if entry.needs_veiled or (entry.veils and any(each.needs_veiled for each in chosen)))
            if any(entry.restores or entry.makes_imprint for entry in chosen):
                more.update(entry.position for entry in self.entries if entry.restores or entry.makes_imprint)
            if more <= found:
                return found
            found |= more


def step_shares(plan) -> list[tuple[str, float, list[tuple[CompressedState, object, float]]]]:
    """The steps of `plan` by their cost share, dearest first: each label with its expected uses times its price, and the states where it acts
    with the action there and their expected visits. Read on the plan's lumped chain (`PackedResult.view`, one shown state per block: the
    numbers are those of the policy), whose visits solve `u = e + P^T u` with each state's self-loop taken out exactly (`P[s, t]` its chance to go
    to `t` given that it leaves, `u` the departures, visits = departures over the chance to leave). Empty when it cannot be read."""
    packed = getattr(plan, "packed", None)
    view = getattr(packed, "view", None) if packed is not None else None
    if not view:
        return []
    states = list(view)
    index = {state: i for i, state in enumerate(states)}
    start = plan.start if plan.start in index else None
    if start is None and packed.risk_policy is not None and packed.risk_start in packed.risk_policy:
        start = states[list(packed.risk_policy).index(packed.risk_start)]
    if start is None:
        return []
    n = len(states)
    rows, cols, chances, leave = [], [], [], np.ones(n)
    for i, state in enumerate(states):
        action = view[state]
        total = float(sum(outcome.weight for outcome in action.outcomes))
        self_weight = float(sum(outcome.weight for outcome in action.outcomes if outcome.state == state))
        if total <= 0.0 or self_weight >= total:
            return []
        leave[i] = (total - self_weight) / total
        for outcome in action.outcomes:
            j = index.get(outcome.state)
            if j is not None and j != i:
                rows.append(i)
                cols.append(j)
                chances.append(outcome.weight / (total - self_weight))
    row, col, chance = np.asarray(rows, dtype=np.int64), np.asarray(cols, dtype=np.int64), np.asarray(chances, dtype=float)

    class _Departures(linear_solve.Terms):
        def __init__(self) -> None:
            self.n = n

        def apply(self, v: np.ndarray) -> np.ndarray:
            return np.bincount(col, weights=chance * v[row], minlength=n)

        def dense(self) -> np.ndarray:
            matrix = np.zeros((n, n))
            np.add.at(matrix, (col, row), chance)
            return matrix

    b = np.zeros(n)
    b[index[start]] = 1.0
    with np.errstate(all="ignore"):
        solved = linear_solve.solve(_Departures(), b)
    if solved.x is None or not np.all(np.isfinite(solved.x)):
        return []
    visits = np.maximum(solved.x, 0.0) / leave
    shares: dict[str, float] = {}
    where: dict[str, list] = {}
    for i, state in enumerate(states):
        action = view[state]
        shares[action.label] = shares.get(action.label, 0.0) + visits[i] * action.cost
        where.setdefault(action.label, []).append((state, action, float(visits[i])))
    return sorted(((label, share, where[label]) for label, share in shares.items()), key=lambda each: (-each[1], str(each[0])))


def read_step(acts: Sequence[tuple[CompressedState, object, float]], leaves: int) -> tuple[set[int], set[int], frozenset[Rarity], bool]:
    """`W`, `K`, the shapes and whether a fractured mod is held, at the states where a step acts (module text), from their statuses and their
    outcomes' statuses."""
    waits, risks, shapes, fractured = set(), set(), set(), False
    for state, action, visits in acts:
        if not visits > 0.0:
            continue
        shapes.add(state.flags.rarity)
        fractured = fractured or bool(state.fractured)
        for outcome in action.outcomes:
            after = outcome.state
            status = getattr(after, "status", None)
            if status is None:
                continue
            for leaf in range(leaves):
                before = state.status[leaf] is Status.PASSING
                now = status[leaf] is Status.PASSING
                if not before and now:
                    waits.add(leaf)
                elif before and not now:
                    risks.add(leaf)
    return waits, risks, frozenset(shapes), fractured


class Grower:
    """The growth of the rounds (module text): asked by `_rounds.widen` for the seed, then for the next round's offers after each round.

    `asked` are the positions of the run's named offers (they are in every round); `support(plan)` the positions its policy uses."""

    def __init__(self, table: OfferTable, asked: Sequence[int]) -> None:
        self.table, self.asked = table, frozenset(asked)
        self.tried: list[frozenset[int]] = []
        self.diagnosed: set[str] = set()
        self.plan = None
        self.plan_set: frozenset[int] = frozenset()  # the offers of the round that made the plan in hand
        self.last: frozenset[int] = frozenset()
        self.by_label = {entry.label: entry.position for entry in table.entries}

    def seed(self) -> tuple[tuple[int, ...], str] | None:
        chosen = self.table.closure(self.table.seed() | self.asked)
        if not chosen:
            return None
        return tuple(sorted(chosen)), "the seed: the cheapest methods for each wanted mod, by cost over chance"

    def support(self, plan) -> frozenset[int]:
        if plan is None:
            return frozenset()
        packed = getattr(plan, "packed", None)
        policy = packed.view if packed is not None and packed.view else plan.policy
        labels = {action.label for action in policy.values()}
        return frozenset(self.by_label[label] for label in labels if label in self.by_label)

    def ran(self, positions: Sequence[int], plan_in_hand, improved: bool) -> None:
        """Note a round: its offers, and the plan in hand after it (`improved`: the round made it)."""
        chosen = frozenset(positions)
        self.tried.append(chosen)
        self.last = chosen
        if improved:
            self.plan, self.plan_set, self.diagnosed = plan_in_hand, chosen, set()

    def say(self, text: str) -> None:
        """A line for a measuring script (`_packed.PROGRESS`, never set by the library)."""
        from . import _packed

        if _packed.PROGRESS is not None:
            _packed.PROGRESS(text)

    def _new(self, chosen: set[int]) -> bool:
        return not any(chosen <= tried for tried in self.tried)

    def next(self) -> tuple[tuple[int, ...], str] | None:
        """The next round's offers and the words that say why, or None: nothing new is named for any step (the growth ends)."""
        table, plan = self.table, self.plan
        if plan is None:  # no plan in hand: the roles read at the start
            base = set(self.last)
            waits, risks = self._start_reading(base)
            named = table.roles(waits, risks, frozenset({table.start_rarity}), False, self.last, frozenset(base))
            chosen = table.closure(base | named | self.asked)
            if named and self._new(chosen):
                return tuple(sorted(chosen)), f"no plan yet, so methods named at the start item (it waits for {self._names(waits)}; at risk: {self._names(risks)})"
            return None
        support = self.support(plan)
        for label, share, acts in step_shares(plan):
            if label in self.diagnosed or label not in self.by_label:
                continue
            self.diagnosed.add(label)
            waits, risks, shapes, fractured = read_step(acts, len(table.goal.leaves))
            current = frozenset(support | self.asked)
            named = table.roles(waits, risks, shapes, fractured, self.plan_set, current)
            chosen = table.closure(set(current) | named)
            if named - current and self._new(chosen):
                return tuple(sorted(chosen)), (
                    f"the plan's dearest step not yet read, {label} ({share:,.2f} Chaos of the plan), waits for {self._names(waits)} and can lose {self._names(risks)}"
                )
        return None

    def _start_reading(self, held: set[int]) -> tuple[set[int], set[int]]:
        """`W` and `K` with no plan in hand (module text): the wanted mods whose providers among `held` all reroll, and, when one mod's only
        provider there rerolls, every other wanted mod."""
        table = self.table
        waits, risks = set(), set()
        for leaf in table.open:
            providers = [table.entries[position] for position in held if any(each == leaf for (_shape, each) in table.entries[position].chance)]
            rerolling = [entry for entry in providers if all(kind not in KEEPS_MODS for kind in entry.kinds.values())]
            if not providers or len(rerolling) == len(providers):
                waits.add(leaf)
            if len(providers) == 1 and rerolling:
                risks.update(other for other in table.open if other != leaf)
        return waits, risks

    def _names(self, leaves: set[int]) -> str:
        """The wanted mods `leaves` by a mod each can be (the first of its accepted mods)."""
        if not leaves:
            return "no wanted mod"
        goal, mods = self.table.goal, self.table.data.mods
        names = []
        for leaf in sorted(leaves):
            mod_id = sorted(goal.leaves[leaf].tier_ok or goal.leaves[leaf].mod_ids)[0]
            mod = mods.get(mod_id)
            names.append(" ".join(str(getattr(mod, "text", "") or mod_id).split()))
        return "; ".join(names)


def growth_table(data: GameData, goal, target, priced: Sequence[PricedOffer], listing: Item | None, ask=None) -> OfferTable:
    """The table of `priced` (the rounds' offers, in their order) on the model of every offer (`OfferTable`)."""
    enabled = [p.offer.action for p in priced if (reads := p.offer.action.reads(data)).junk or reads.item_state]
    holds = bool(target.start_item.metamods(data) & BLOCKING)
    abstraction = Abstraction(
        data, goal, target.base_id, target.item_level, enabled, metamods=holds, enchantment=target.start_item.enchantment, allow_inputs=True
    )  # fmt: skip
    start = abstraction.compress(listing or target.start_item)
    return OfferTable(data, abstraction, start, target.start_item, priced, ask)


__all__ = ["Grower", "OfferTable", "PER_ROLE", "growth_table", "read_step", "step_shares"]
