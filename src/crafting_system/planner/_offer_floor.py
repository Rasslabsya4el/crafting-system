"""A floor under what an offer can cost, from the pool alone: the offers the bound's model need not build (ticket #626, OR-12, OR-13).

The walk-free bound (`_pattern_bound`) builds, for each offer, the kernel of every member of every key, and the kernel of a fossil set is a Fraction
distribution of seconds (R08: 1.6 s on average, 6.9 s when the set fractures; 3,938 sets). Most offers cannot be the best action anywhere, and
the number `pbar` and the Wald floor `rho` of `_offer_kinds` prove it without the kernel. This module gives the bound the same
two numbers, and the proof that they are a floor of the cost of the offers it leaves out of the model.

For an offer `a` and a state `s` outside `E` (every necessary leaf of the goal that is open at the start is PASSING) that has the flags and the
fractured mods of the start (of the item it opens into when the start is an unopened listing, ADR-0064), one use of `a` lands in `E` with chance at most `pbar(a)` and `V*(s') >= rho` for a successor `s'` outside `E`
with the same shape (the claim and its proof are in `_offer_kinds`: Wald's identity over the number of uses). So, with three classes of states,

    class OUTSIDE (outside E, the start's shape):   Q*(s, a) >= max(c(a) + (1 - pbar(a)) rho, rho),  V*(s) >= rho  (Q* >= V* for any offer, #829),
    class INSIDE  (in E, the start's shape):        Q*(s, a) >= c(a) + (1 - pbar(a)) rho  for an *erasing reroll* `a` (its result does not depend on the state
                                                    but through the flags and the fractured mods, so it lands in E with the same chance as from outside),
                                                    Q*(s, a) >= c(a) for any other offer (a craft from a state in E may stay in E),
    class OTHER   (any other shape; a state that holds an imprint when the start holds none and the restores are set aside, #1074):
                                                    Q*(s, a) >= c(a),
    (a move, an offer that leaves the start's shape for a shape the floors know, a Scouring of R05's Rare: `_offer_kinds`, THE SHAPES, #973:
     in OUTSIDE and, as an erasing one, INSIDE, Q*(s, a) >= c(a) + (1 - pbar(a)) R, R the least floor of the shapes it lands in, not rho),
    class SHAPED + S (outside E, of another shape S the floors know, holding no dead leaf of S PASSING: the claim C_S of THE SHAPES):
                                                    Q*(s, a) >= max(c(a), rho_S),  V*(s) >= rho_S  (C_S gives V*(s) >= rho_S, and Q* >= V*),
    class UNOPENED (an unopened listing, ADR-0064): Q*(s, a) >= c(a) for the draw that opens it and the restart, and infinity for any other offer
                                                    (the kernel refuses every other action on an unopened item: `Abstraction._prepare`),

and `V*(s) >= 0` everywhere (costs are not negative).

Why SHAPED is a class of its own (#973). With moves offered, the cheapest way from the start in a bound's model is often a move and then a state of
the shape it lands in; a state of another shape in class OTHER had the price of one offer as its floor, so a model whose growth had not reached
those keys valued the start at a move and that price (R11's Exalted round: a Scouring and an Alteration, 0.52 Chaos, where the start's rho is
9.64 and main's model started at 160.26). Its build then grew the model many times to lift that value (R05: 15 growths, its build run past its
share and its search given 0 s; R11: 21) and its search was led by a bound near 0. The floors of every known shape are already worked out
(`rho_of`), and the claim C_S is what they are proved for, so a state of C_S outside E reads rho_S, as a state of the start's shape outside E
reads rho. A state in E, holding a dead leaf PASSING, holding an imprint the floors set aside, or of a shape the floors do not know stays OTHER.

An offer that fractures, changes the flags or reads the item's implicits, quality, offer or imprints has `pbar = 1`: its floor is its cost; but a
veiled choice (an Unveil, a Pick: it reads the offer) and a veil (a Veiled Exalted Orb) have the pbar of the mods they may add, as a bench craft,
an implicit change (an Ember, an Ichor) has pbar 0, an addition whose class declares its draw (a Beastcraft side swap, an Eldritch Exalted Orb)
the bound of one added mod (`_offer_kinds`, #1074), and a restore of an imprint offered to a start with none is set aside as refused. The
things taken on the contracts of `Reads` and `Adds` and not checked are the assumptions of `_offer_kinds`: (1) an offer the game refuses on the bare item of the start's shape is refused at every state of that shape; (2) an
action that needs the veiled placeholder changes no flag but by what `Adds` declares; (3) only an offer that reads the imprints makes one (a
reroll that declares `Adds.imprints` is made TERMINAL). They only move `rho` (the refused offers are not in the minimum that makes `rho`). The floors
of the offers themselves treat a refused offer as any other, at its cost (its floor outside E is `rho`, as every offer's).

`OfferFloors.lower(position, klass)` is the floor of an offer in a class of states, and `OfferFloors.tighten` raises it, level by level, only for an
offer the envelope search would otherwise build at a state (#829), so that the exact chance of a reroll, which is an exact distribution, is computed
only for an offer whose looser floors did not already rule it out, and once for all the states of its class. `OfferFloors.needed` asks the same of
the bound's model: whether an offer outside it, its floor raised as far as it goes, could lower a key where the floor action is the cheapest, so that
the offer joins the model (`_pattern_bound`, #988).
"""

import contextlib
import math
from collections.abc import Callable, Iterator
from dataclasses import replace

from crafting_system import budget
from crafting_system.abstraction import Abstraction, CompressedState, Status, add_bound, declared_add_bound, reach_bound
from crafting_system.abstraction._pattern import Tally

from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.items import ItemError

from ._offer_kinds import (
    ADD,
    FINISHING,
    MOVE,
    MOVE_ADD,
    NAMING,
    REROLL,
    REFUSED,
    RESTART_KIND,
    SLACK,
    SMALL_START,
    ShapeView,
    _Entry,
    _kind_of,
    _raised,
    beyond,
    declared_pbars,
    raisable,
    finishes,
    goal_set,
    shape_rhos,
    through_listing,
    ONE,
    ZERO,
)
from ._offers import BuyStartItem, PricedOffer, reached_by


OTHER, INSIDE, OUTSIDE, UNOPENED = 0, 1, 2, 3  # the classes of states a floor is stated for (see the module text)
CLASSES = (OTHER, INSIDE, OUTSIDE, UNOPENED)
SHAPED = 4  # class SHAPED + S: outside E, of the known shape S > 0, no dead leaf of S PASSING (THE SHAPES, #973); `OfferFloors.classes` lists them


def shape_of(klass: int) -> int | None:
    """The shape a class of another known shape is stated for (`SHAPED`), or None for the four classes of `CLASSES`."""
    return klass - SHAPED if klass >= SHAPED else None


class FloorsStopped(Exception):
    """Raised inside the offers' floors when the net of the run is reached (OR-12): the floors are not finished."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class OfferFloors:
    """The floors of a list of priced offers, from the start `start` of a plan and its start item `item` (the item an unopened `start` opens into)."""

    def __init__(
        self,
        abstraction: Abstraction,
        start: CompressedState,
        priced: list[PricedOffer] | tuple[PricedOffer, ...],
        item,
        stop: Callable[[], str | None] | None = None,
        tally: Tally | None = None,
    ) -> None:
        self.tally = tally  # a build counted in pieces of work (`abstraction._pattern.Tally`): each floor raised for the build adds one
        self.ab = abstraction
        self.start = start
        self.item = item
        self.stop = stop  # the net: asked between two offers of the kinds and before every raise of a floor, and inside the making of a kernel (`inside`); raises `FloorsStopped`
        data = abstraction.data
        goal = abstraction.goal
        kinds = []
        for index, offer in enumerate(priced):
            if index % 256 == 0:
                self.ask()
            kinds.append(_kind_of(data, item, offer))
        crafted = [bool(kind in NAMING and offer.offer.action.adds(data, item).crafted) for offer, (kind, _named) in zip(priced, kinds)]
        crafts = {(named, made) for (kind, named), made in zip(kinds, crafted) if kind in NAMING}  # the mods each craft or veiled choice may add, and whether crafted
        # A bought start the market sells unopened (ADR-0064) is a listing no reroll applies to: the floors are stated for the item it opens into,
        # as the retired bound pruning's were (`shape`). Stated for the listing, every reroll is refused there, `rho` is infinite, and the
        # listing itself (outside E, of "the start's shape") got an infinite floor above its finite cost (#731). The listing is then of another shape.
        shape = abstraction.compress(item) if start.flags.unopened else start
        self.chosen = goal_set(goal, shape, sorted(crafts, key=lambda craft: (sorted(craft[0]), craft[1])))
        chosen_leaves = [goal.leaves[index] for index in self.chosen]
        self.entries: list[_Entry] = []
        self.lifted: dict[int, int] = {}  # the offers `tighten` lifted during the search, with their levels (`version`)
        for index, (offer, (kind, named), made) in enumerate(zip(priced, kinds, crafted)):
            if index % 256 == 0:
                self.ask()
            pbar = ONE
            if kind == RESTART_KIND:
                pbar = ZERO
            elif kind in FINISHING:
                pbar = ONE if any(finishes(leaf, named, made) for leaf in chosen_leaves) else ZERO  # a craft or a veiled choice lands in E only by passing a leaf of U
            self.entries.append(_Entry(index, offer, kind, 0, pbar))
        with self.inside():
            through_listing(abstraction, start, shape, self.chosen, self.entries)  # a restart into an unopened listing is counted with its draw
        self.bare = replace(shape, slots=())
        self.shape = (shape.flags, shape.fractured)
        self.unimprinted = any(kind == REFUSED for kind, _named in kinds)  # restores set aside: a state that holds an imprint is of another shape (#1074)
        self.views = [ShapeView(abstraction, self.bare, item, self.chosen, (), {self.shape: 0})]  # the shapes the floors are stated for (THE SHAPES, #973)
        self.shape_entries = [self.entries]
        self.settled: list[float | None] = [None]
        self.rest = 0.0  # no shape left unsettled has a floor below this
        if self.chosen:
            self._other_shapes(priced, item)
            with self.inside():
                for view, entries in zip(self.views, self.shape_entries):
                    declared_pbars(abstraction, view.bare, view.item, self.chosen, entries, self.ask)  # every set's level 0 from its class at once (#1073)
            self.settled, self.rest = shape_rhos(self.shape_entries, self._raise_in, until=0)
        self.rho = self.settled[0] if self.chosen else 0.0
        self.rhos = [self.rho_of(index) for index in range(len(self.views))] if self.chosen else [0.0]
        self.classes = CLASSES + tuple(SHAPED + index for index in range(1, len(self.views)))  # every class a state can be in here

    # ---- the shapes (THE SHAPES in `_offer_kinds`) --------------------------------------------------------------------------

    def _other_shapes(self, priced, item) -> None:
        """The shapes of the other rarities the priced offers turn the start item into (`_offers.reached_by`), each with its offers' kinds, its
        dead leaves (`_dead`) and their pbars; a restart from one of them is a move into the start's shape."""
        ab, data = self.ab, self.ab.data
        actions = [offer.offer.action for offer in priced if not isinstance(offer.offer.action, BuyStartItem) and not getattr(offer.offer.action, "opens_listing", False)]
        if not actions:
            return
        known = self.views[0].known
        self.ask()
        for reached in reached_by(data, item, lambda _item: actions)[1:]:
            state = ab.compress(reached)
            key = (state.flags, state.fractured)
            if key in known or getattr(state.flags, "unopened", False):
                continue
            known[key] = len(self.views)
            self.views.append(ShapeView(ab, replace(state, slots=()), reached, self.chosen, (), known))
        if len(self.views) == 1:
            return
        kinds = [[self._asked(position, _kind_of, data, view.item, offer) if index else None for position, offer in enumerate(priced)] for index, view in enumerate(self.views)]
        kinds[0] = [(entry.kind, None) for entry in self.entries]
        reach = [[self._asked(position, self._rarities, view, offer.offer.action) for position, offer in enumerate(priced)] for view in self.views]
        restart = next((entry for entry in self.entries if isinstance(entry.priced.offer.action, BuyStartItem)), None)
        goal = ab.goal
        for index in range(1, len(self.views)):
            view = self.views[index]
            view.dead = self._dead(index, priced, kinds, reach)
            entries: list[_Entry] = []
            for position, (offer, (kind, named)) in enumerate(zip(priced, kinds[index])):
                if position % 256 == 0:
                    self.ask()
                entry = _Entry(position, offer, kind, 0, ONE)
                if kind == RESTART_KIND:
                    if restart is not None and offer is restart.priced:  # back to the start: a move into its shape (or its listing and the draw)
                        entry.pbar, entry.extra, entry.dests = restart.pbar, restart.extra, frozenset({0})
                    else:  # the draw that opens a listing: no listing is of this shape
                        entry.kind = REFUSED
                elif kind in FINISHING:
                    made = bool(offer.offer.action.adds(data, view.item).crafted)
                    leaves = [goal.leaves[leaf] for leaf in (view.dead or self.chosen)]
                    test = all if view.dead else any  # one mod added must pass every dead leaf, or some leaf of U where none is dead
                    entry.pbar = ONE if test(finishes(leaf, named, made) for leaf in leaves) else ZERO
                entries.append(entry)
            self.shape_entries.append(entries)

    def _asked(self, position: int, function, *args):
        """`function(*args)`, the net asked first at every 256th offer (OR-40)."""
        if position % 256 == 0:
            self.ask()
        return function(*args)

    def _rarities(self, view: ShapeView, action):
        """The rarities one use of `action` leaves an item of the shape in: asked of the shape's item, then of its bare item; None when neither
        answers (THE SHAPES, assumption (7): an action that applies nowhere there leaves no item of another rarity)."""
        if isinstance(action, BuyStartItem):
            return None
        data = self.ab.data
        for asked in (view.item, view.item.changed(data, mods=tuple(entry for entry in view.item.mods if entry.fractured))):
            try:
                return action.rarities(data, asked)
            except (NotApplicableError, OutOfScopeError, ItemError, ValueError):  # refused there, or the data cannot build it: ask the next item
                continue
        return None

    def _dead(self, index: int, priced, kinds, reach) -> tuple[int, ...]:
        """The leaves of U that no state of the claim of shape `index` holds PASSING (THE SHAPES): U less every leaf a use that lands in the shape
        may leave PASSING (from any shape, an erasing reroll's outcome at the bare item; any other use that can land there leaves every leaf open to
        it) and every leaf an offer of the shape may make PASSING."""
        view = self.views[index]
        rarity = view.item.rarity
        open_leaves = set(self.chosen)
        for source, other in enumerate(self.views):
            if source == index:
                continue
            for position, offer in enumerate(priced):
                if not open_leaves:
                    return ()
                if position % 256 == 0:
                    self.ask()
                rarities = reach[source][position]
                kind = kinds[source][position][0]
                if kind in (REFUSED, RESTART_KIND) or rarities is None or rarity not in rarities:
                    continue
                action = offer.offer.action
                adds = action.adds(self.ab.data, other.item)
                if kind != REROLL or adds.fractures or adds.keeps_crafted or action.reads(self.ab.data).needs_crafted:
                    return ()  # it keeps mods of the state it was used at, which may pass any leaf
                open_leaves -= self._passed(other, offer.offer.action, REROLL, (), open_leaves)
        for position, offer in enumerate(priced):
            if not open_leaves:
                return ()
            kind, named = kinds[index][position]
            rarities = reach[index][position]
            if kind in FINISHING:
                made = bool(offer.offer.action.adds(self.ab.data, view.item).crafted)
                open_leaves -= {leaf for leaf in open_leaves if finishes(self.ab.goal.leaves[leaf], named, made)}
            elif kind in (REROLL, ADD) and (rarities is None or rarity in rarities):
                open_leaves -= self._passed(view, offer.offer.action, kind, named, open_leaves)
        return tuple(sorted(open_leaves))

    def _passed(self, view: ShapeView, action, kind: str, _named, leaves) -> set[int]:
        """The leaves of `leaves` one use of the erasing reroll (`kind` REROLL) or the addition (ADD) `action` at a state of the shape `view` may
        make PASSING: those its bound for the leaf alone does not prove 0 (`reach_bound` at the bare item; `add_bound` over the states of the
        shape). A reroll the bare item refuses passes none (assumption (1)); any other answer that proves nothing passes them all."""
        ab = self.ab
        found: set[int] = set()
        for leaf in sorted(leaves):
            self.ask()
            if self.tally is not None:
                self.tally.done += 1
            try:
                with self.inside():  # a bound builds kernels: the net is asked inside them too (#1238)
                    if kind == REROLL:
                        bound = reach_bound(ab, view.bare, action, (leaf,))
                    elif action.added_draw(ab.data, view.item) is not None:
                        bound = declared_add_bound(ab, action, view.item, (leaf,))
                    else:
                        bound = add_bound(ab, view.bare, action, (leaf,))
            except NotApplicableError:
                if kind == REROLL:
                    return set()
                bound = None
            except OutOfScopeError:
                bound = None
            if bound is None or bound > 0:
                found.add(leaf)
        return found

    def rho_of(self, shape: int) -> float:
        """The floor of the shape `shape`: settled, or the least an unsettled one can have (`rest`)."""
        value = self.settled[shape] if shape < len(self.settled) else None
        return self.rest if value is None else value

    def ask(self) -> None:
        """Ask the net; raise `FloorsStopped` with its reason once it is reached."""
        if self.stop is not None and (reason := self.stop()) is not None:
            raise FloorsStopped(reason)

    @contextlib.contextmanager
    def inside(self) -> Iterator[None]:
        """Ask the net inside the making of the kernels of the block too (`budget.asking`, #1238): one kernel can be the whole run. The listing draw
        of R20 under `Reads.influenced` grew past 12 GB in `through_listing` with the net of 3,000 MB never asked. Only on the clock and on memory:
        a build counted in pieces of work (`tally`) asks at its pieces alone, so that it stops at the same point on every machine."""
        try:
            with budget.asking(self.stop if self.tally is None else None):
                yield
        except budget.NetReached as reached:
            raise FloorsStopped(reached.reason) from None

    def _raise(self, entry: _Entry, level: int) -> None:
        """Bring an offer of the start's shape to `level`, asking the net and counting a piece of work."""
        self._raise_in(0, entry, level)

    def _raise_in(self, shape: int, entry: _Entry, level: int) -> None:
        self.ask()
        if self.tally is not None:
            self.tally.done += 1
        with self.inside():
            self._lift(shape, entry, level)

    def _lift(self, shape: int, entry: _Entry, level: int) -> None:
        """Bring an offer of the shape `shape` to `level`, the net not asked: `tighten` calls it from the search, which keeps its own net and
        does not catch `FloorsStopped` (#829); the floors' own raises ask it through `_raise_in`."""
        entry.kind, entry.pbar, entry.level, entry.dests = _raised(
            self.views[shape], entry.priced.offer.action, entry.kind, entry.level, entry.pbar, level, entry.dests
        )

    # ---- the classes of states ------------------------------------------------------------------------------------------

    def klass(self, flags, fractured, status: tuple, imprints: tuple) -> int:
        """The class of a state with these flags, fractured mods, status and imprints: `UNOPENED` (a listing), `OUTSIDE` (outside `E`, the start's
        shape), `INSIDE` (in `E`, the start's shape), `SHAPED + S` (outside `E`, of another known shape S, no dead leaf of S PASSING: THE SHAPES) or `OTHER`. When the restores are set aside (`_offer_kinds`, #1074), a state that holds an
        imprint is not of the start's shape."""
        if getattr(flags, "unopened", False):
            return UNOPENED
        if not self.chosen or (imprints and self.unimprinted):
            return OTHER
        if (flags, fractured) != self.shape:
            # another shape the floors know (THE SHAPES): its claim C_S holds outside E where no leaf of its dead leaves D_S is PASSING
            index = self.views[0].known.get((flags, fractured))
            if not index or all(status[leaf] is Status.PASSING for leaf in self.chosen) or any(status[leaf] is Status.PASSING for leaf in self.views[index].dead):
                return OTHER
            return SHAPED + index
        return INSIDE if all(status[index] is Status.PASSING for index in self.chosen) else OUTSIDE

    def at(self, klass: int) -> float:
        """The floor of `V*` at every state of the class `klass`: rho for `OUTSIDE`, rho_S for a class of another known shape S (THE SHAPES), 0
        for any other (costs are not negative)."""
        if klass == OUTSIDE:
            return self.rho
        shape = shape_of(klass)
        return 0.0 if shape is None else self.rho_of(shape)

    # ---- the floors -----------------------------------------------------------------------------------------------------

    def lower(self, position: int, klass: int) -> float:
        """A floor of `Q*(s, a)` for the offer at `position` and a state of the class `klass` (never above the exact cost)."""
        entry = self.entries[position]
        if klass >= SHAPED:
            # a state of the claim C_S of another known shape S, outside E: Q*(s, a) >= V*(s) >= rho_S for every offer (THE SHAPES). Without it every
            # state a move lands in had the price of one offer as its floor, and the model of R11's Exalted round valued the start at a Scouring and an
            # Alteration (0.52 Chaos, where its rho is 9.64), its build grew 21 times to lift it and its search had no bound to go by (#973)
            return max(entry.cost, self.rho_of(klass - SHAPED))
        if klass == UNOPENED:  # only the draw works on a listing; the restart buys it again
            action = entry.priced.offer.action
            return entry.cost if getattr(action, "opens_listing", False) or isinstance(action, BuyStartItem) else math.inf
        if klass == OUTSIDE:
            # Q*(s, a) >= V*(s) >= rho for every offer at a state of this class, whatever the offer is: one the bare item refuses (the assumption `rho`
            # rests on) or one that leaves the shape has a floor of `rho` too, not its bare cost. Without that the state's bound (`rho`) stood above the
            # least floor of its offers (R12 with the floors on: 8.98 against a refused reforge's 0.75) and the search refused it as inconsistent (#829)
            return max(entry.cost + self.after_leaving(entry), self.rho)
        if entry.pbar == ONE or klass == OTHER or (klass == INSIDE and entry.kind not in (REROLL, MOVE)):
            return entry.cost
        return entry.cost + self.after_leaving(entry)

    def after_leaving(self, entry: _Entry) -> float:
        """`(1 - pbar) R`: the least the offer costs after its use beyond its price, R being `rho` for an offer that keeps the start's shape and the
        least floor of the shapes a move lands in (`_offer_kinds.beyond`, THE SHAPES). 0 for an offer that lands in E for sure, also when R is
        infinite (nothing else enters E: `_offer_kinds`, UNREACHABLE), where float arithmetic would make it 0 * inf, not a number."""
        return beyond(entry, self.rho, self.rho_of)

    def floor(self, positions, klass: int) -> float:
        """The least floor over `positions` (infinity for none)."""
        return min((self.lower(position, klass) for position in positions), default=math.inf)

    def initial(self) -> list[int]:
        """The offers the model starts with: the restart, the crafts, the veiled choices and the `SMALL_START` rerolls and moves of least floor (a
        reroll's cost / pbar; a move's key in `shape_rhos`, the least of its c / p and c + (1 - p) R) (the cheapest offers if none).

        The moves are ranked with the rerolls (#973): from a Normal start every essence, Alchemy and Transmutation is a move into the shape it
        makes, and a model started without them took no action at the start, its value there infinite, so every offer was found needed at
        once (R17: 7,062 offers joining in one growth, 656 s past a net of 19 s; R04: 6,100, killed at 4 GB). Which offers the model starts
        with only decides how it grows; any start set is sound."""
        inside = {entry.index for entry in self.entries if entry.kind in (RESTART_KIND, *NAMING)}
        rerolls = sorted((entry for entry in self.entries if entry.kind in (REROLL, MOVE, MOVE_ADD)), key=lambda entry: (self._start_key(entry), entry.index))
        inside.update(entry.index for entry in rerolls[:SMALL_START])
        if not inside:
            inside.update(entry.index for entry in sorted(self.entries, key=lambda entry: (entry.cost, entry.index))[:SMALL_START])
        return sorted(inside)

    def _start_key(self, entry: _Entry) -> float:
        """The floor `initial` ranks an offer by: cost / pbar, and for a move the least of that and its price plus the floor it lands in."""
        return min(entry.ratio, entry.cost + self.after_leaving(entry)) if entry.dests else entry.ratio

    def needed(self, position: int, limits: dict[int, float | None]) -> float | None:
        """The floor that makes the offer at `position` worth building into the bound's model, or None when it cannot lower the value of any key it was
        asked about (`_pattern_bound._binding`, #988).

        `limits[klass]` is the largest model value of a key of that class where the floor action was the cheapest (None when there is none). The offer is
        needed when its floor in a class is not above the limit of the class. A reroll's floor is brought from `pbar = 1` through the loose bound to the
        exact chance, a level at a time, and stops at the first level whose floor is above the limits; a floor with nothing to raise (any offer in a
        class of another shape, a terminal offer) is its price.
        """
        entry = self.entries[position]
        for klass in (OTHER, UNOPENED, *self.classes[len(CLASSES):]):
            if limits.get(klass) is not None and (low := self.lower(position, klass)) * (1 - SLACK) <= limits[klass]:
                return low
        found: list[tuple[float, int]] = []
        for level in (0, 1, 2):
            if level and raisable(entry.kind, entry.level) and entry.level < level:
                self._raise(entry, level)
            found = [
                (low, klass)
                for klass in (INSIDE, OUTSIDE)
                if limits.get(klass) is not None and (low := self.lower(position, klass)) * (1 - SLACK) <= limits[klass]
            ]
            if not found:
                return None
            if not raisable(entry.kind, entry.level):
                break
        return min(low for low, _ in found)

    def tighten(self, position: int, klass: int, above: float) -> float:
        """The floor of the offer at `position` in the class `klass`, its reroll's chance brought up a level at a time (the loose bound of the pool,
        then the exact chance on the bare item) until the floor is above `above` or the chance is exact.

        The chance is the offer's own, the same at every state of the start's shape (see the module text), so it is worked out once and every later
        floor of the offer reads it. The net is not asked: the search that calls this keeps its own net, and one raise is one exact distribution,
        of the size of the kernel it may spare (#829).
        """
        entry = self.entries[position]
        while raisable(entry.kind, entry.level) and klass in (INSIDE, OUTSIDE) and self.lower(position, klass) * (1 - SLACK) <= above:
            self._lift(0, entry, entry.level + 1)
            self.lifted[position] = entry.level
        return self.lower(position, klass)

    def version(self) -> tuple[tuple[int, int], ...]:
        """What the search has changed of the floors (`tighten`): the offers it lifted, with their levels. Two processes whose versions are equal
        give every offer the same floor (a pool worker's listing of a state is taken only so, `planner._ahead`, #1340)."""
        return tuple(sorted(self.lifted.items()))


__all__ = ["CLASSES", "FloorsStopped", "OfferFloors", "SHAPED", "shape_of"]
