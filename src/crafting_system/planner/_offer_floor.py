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
    class OTHER   (any other shape):                Q*(s, a) >= c(a),
    class UNOPENED (an unopened listing, ADR-0064): Q*(s, a) >= c(a) for the draw that opens it and the restart, and infinity for any other offer
                                                    (the kernel refuses every other action on an unopened item: `Abstraction._prepare`),

and `V*(s) >= 0` everywhere (costs are not negative).

An offer that fractures, changes the flags or reads the item's implicits, quality or offer has `pbar = 1`: its floor is its cost. The one thing taken
on the contract of `Reads` and not checked is the assumption of `_offer_kinds` (1): an offer the game refuses on the bare item of the start's shape
is refused at every state of that shape; it only moves `rho` (the refused offers are not in the minimum that makes `rho`). The floors of the offers
themselves treat a refused offer as any other, at its cost.

`OfferFloors.lower(position, klass)` is the floor of an offer in a class of states, and `OfferFloors.tighten` raises it, level by level, only for an
offer the envelope search would otherwise build at a state (#829), so that the exact chance of a reroll, which is an exact distribution, is computed
only for an offer whose looser floors did not already rule it out, and once for all the states of its class. `OfferFloors.needed` asks the same of
the bound's model: whether an offer outside it, its floor raised as far as it goes, could lower a key where the floor action is the cheapest, so that
the offer joins the model (`_pattern_bound`, #988).
"""

import math
from collections.abc import Callable
from dataclasses import replace

from crafting_system.abstraction import Abstraction, CompressedState, Status

from ._offer_kinds import (
    CRAFT,
    REROLL,
    RESTART_KIND,
    SLACK,
    SMALL_START,
    _Entry,
    _kind_of,
    _raised,
    best_first_rho,
    declared_pbars,
    raisable,
    goal_set,
    through_listing,
    ONE,
    ZERO,
)
from ._offers import BuyStartItem, PricedOffer


OTHER, INSIDE, OUTSIDE, UNOPENED = 0, 1, 2, 3  # the classes of states a floor is stated for (see the module text)
CLASSES = (OTHER, INSIDE, OUTSIDE, UNOPENED)


class FloorsStopped(Exception):
    """Raised inside the offers' floors when the net of the run is reached (OR-12): the floors are not finished."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class OfferFloors:
    """The floors of a list of priced offers, from the start `start` of a plan and its start item `item` (the item an unopened `start` opens into)."""

    def __init__(
        self, abstraction: Abstraction, start: CompressedState, priced: list[PricedOffer] | tuple[PricedOffer, ...], item, stop: Callable[[], str | None] | None = None
    ) -> None:
        self.ab = abstraction
        self.start = start
        self.item = item
        self.stop = stop  # the net: asked between two offers of the kinds and before every raise of a floor (an exact chance, milliseconds); raises `FloorsStopped`
        data = abstraction.data
        goal = abstraction.goal
        kinds = []
        for index, offer in enumerate(priced):
            if index % 256 == 0:
                self.ask()
            kinds.append(_kind_of(data, item, offer))
        crafts = frozenset().union(*(named for kind, named in kinds if kind == CRAFT)) if kinds else frozenset()
        # A bought start the market sells unopened (ADR-0064) is a listing no reroll applies to: the floors are stated for the item it opens into,
        # as the retired bound pruning's were (`shape`). Stated for the listing, every reroll is refused there, `rho` is infinite, and the
        # listing itself (outside E, of "the start's shape") got a floor of 1e300 above its finite cost (#731). The listing is then of another shape.
        shape = abstraction.compress(item) if start.flags.unopened else start
        self.chosen = goal_set(goal, shape, crafts)
        u_mods = frozenset().union(*(goal.leaves[index].mod_ids for index in self.chosen)) if self.chosen else frozenset()
        self.entries: list[_Entry] = []
        for index, (offer, (kind, named)) in enumerate(zip(priced, kinds)):
            if index % 256 == 0:
                self.ask()
            pbar = ONE
            if kind == RESTART_KIND:
                pbar = ZERO
            elif kind == CRAFT:
                pbar = ONE if named & u_mods else ZERO
            self.entries.append(_Entry(index, offer, kind, 0, pbar))
        through_listing(abstraction, start, shape, self.chosen, self.entries)  # a restart into an unopened listing is counted with its draw
        self.bare = replace(shape, slots=())
        self.shape = (shape.flags, shape.fractured)
        if self.chosen:
            declared_pbars(abstraction, self.bare, item, self.chosen, self.entries, self.ask)  # every set's level 0 from its class at once (#1073)
        self.rho = best_first_rho(self.entries, self._raise) if self.chosen else 0.0

    def ask(self) -> None:
        """Ask the net; raise `FloorsStopped` with its reason once it is reached."""
        if self.stop is not None and (reason := self.stop()) is not None:
            raise FloorsStopped(reason)

    def _raise(self, entry: _Entry, level: int) -> None:
        self.ask()
        entry.kind, entry.pbar, entry.level = _raised(
            self.ab, self.bare, self.item, self.chosen, entry.priced.offer.action, entry.kind, entry.level, entry.pbar, level
        )

    # ---- the classes of states ------------------------------------------------------------------------------------------

    def klass(self, flags, fractured, status: tuple) -> int:
        """The class of a state with these flags, fractured mods and status: `UNOPENED` (a listing), `OUTSIDE` (outside `E`, the start's shape), `INSIDE` (in `E`, the start's shape) or `OTHER`."""
        if getattr(flags, "unopened", False):
            return UNOPENED
        if not self.chosen or (flags, fractured) != self.shape:
            return OTHER
        return INSIDE if all(status[index] is Status.PASSING for index in self.chosen) else OUTSIDE

    # ---- the floors -----------------------------------------------------------------------------------------------------

    def lower(self, position: int, klass: int) -> float:
        """A floor of `Q*(s, a)` for the offer at `position` and a state of the class `klass` (never above the exact cost)."""
        entry = self.entries[position]
        if klass == UNOPENED:  # only the draw works on a listing; the restart buys it again
            action = entry.priced.offer.action
            return entry.cost if getattr(action, "opens_listing", False) or isinstance(action, BuyStartItem) else math.inf
        if klass == OUTSIDE:
            # Q*(s, a) >= V*(s) >= rho for every offer at a state of this class, whatever the offer is: one the bare item refuses (the assumption `rho`
            # rests on) or one that leaves the shape has a floor of `rho` too, not its bare cost. Without that the state's bound (`rho`) stood above the
            # least floor of its offers (R12 with the floors on: 8.98 against a refused reforge's 0.75) and the search refused it as inconsistent (#829)
            return max(entry.cost + float(1 - entry.pbar) * self.rho, self.rho)
        if entry.pbar == ONE or klass == OTHER or (klass == INSIDE and entry.kind != REROLL):
            return entry.cost
        return entry.cost + float(1 - entry.pbar) * self.rho

    def floor(self, positions, klass: int) -> float:
        """The least floor over `positions` (infinity for none)."""
        return min((self.lower(position, klass) for position in positions), default=math.inf)

    def initial(self) -> list[int]:
        """The offers the model starts with: the restart, the crafts and the `SMALL_START` rerolls of least cost / pbar (the cheapest offers if none)."""
        inside = {entry.index for entry in self.entries if entry.kind in (RESTART_KIND, CRAFT)}
        rerolls = sorted((entry for entry in self.entries if entry.kind == REROLL), key=lambda entry: (entry.ratio, entry.index))
        inside.update(entry.index for entry in rerolls[:SMALL_START])
        if not inside:
            inside.update(entry.index for entry in sorted(self.entries, key=lambda entry: (entry.cost, entry.index))[:SMALL_START])
        return sorted(inside)

    def needed(self, position: int, limits: dict[int, float | None]) -> float | None:
        """The floor that makes the offer at `position` worth building into the bound's model, or None when it cannot lower the value of any key it was
        asked about (`_pattern_bound._binding`, #988).

        `limits[klass]` is the largest model value of a key of that class where the floor action was the cheapest (None when there is none). The offer is
        needed when its floor in a class is not above the limit of the class. A reroll's floor is brought from `pbar = 1` through the loose bound to the
        exact chance, a level at a time, and stops at the first level whose floor is above the limits; a floor with nothing to raise (any offer in a
        class of another shape, a terminal offer) is its price.
        """
        entry = self.entries[position]
        for klass in (OTHER, UNOPENED):
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
            entry.kind, entry.pbar, entry.level = _raised(
                self.ab, self.bare, self.item, self.chosen, entry.priced.offer.action, entry.kind, entry.level, entry.pbar, entry.level + 1
            )
        return self.lower(position, klass)


__all__ = ["CLASSES", "FloorsStopped", "OfferFloors"]
