"""A floor under what an offer can cost, from the pool alone: the offers the bound's model need not build (ticket #626, OR-12, OR-13).

The walk-free bound (`_pattern_bound`) builds, for each offer, the kernel of every member of every key, and the kernel of a fossil set is a Fraction
distribution of seconds (R08: 1.6 s on average, 6.9 s when the set fractures; 3,938 sets). Most offers cannot be the best action anywhere, and
the pruned walk proves it without the kernel (`_bound_prune`: the number `pbar` and the Wald floor `rho`). This module gives the bound the same
two numbers, and the proof that they are a floor of the cost of the offers it leaves out of the model.

For an offer `a` and a state `s` outside `E` (every necessary leaf of the goal that is open at the start is PASSING) that has the flags and the
fractured mods of the start, one use of `a` lands in `E` with chance at most `pbar(a)` and `V*(s') >= rho` for a successor `s'` outside `E`
with the same shape (the claim and its proof are in `_bound_prune`: Wald's identity over the number of uses). So

    Q*(s, a) >= c(a) + (1 - pbar(a)) rho        for s outside E with the start's shape (a "shaped" state),
    Q*(s, a) >= c(a)                            for every state (costs are not negative),
    V*(s)    >= rho                             for a shaped state, V*(s) >= 0 for every state.

An offer that fractures, changes the flags or reads the item's implicits, quality or offer has `pbar = 1`: its floor is its cost. The one thing taken
on the contract of `Reads` and not checked is the assumption of `_bound_prune` (2): an offer the game refuses on the bare item of the start's shape
is refused at every state of that shape; it only moves `rho` (the refused offers are not in the minimum that makes `rho`). The floors of the offers
themselves treat a refused offer as any other, at its cost.

`OfferFloors.lower(position, shaped)` is the floor of an offer in a class of states, and `OfferFloors.needed` says whether an offer outside the model
could lower the value of a key whose model value is `limit` (the test of the certificate of `_bound_prune`, level by level, so that the exact chance of a
reroll, which is an exact distribution, is computed only for an offer whose looser floors did not already rule it out).
"""

import math
from dataclasses import replace

from crafting_system.abstraction import Abstraction, CompressedState, Status

from ._bound_prune import (
    CRAFT,
    REROLL,
    RESTART_KIND,
    SLACK,
    SMALL_START,
    _Entry,
    _kind_of,
    _raised,
    best_first_rho,
    goal_set,
    ONE,
    ZERO,
)
from ._offers import PricedOffer


class OfferFloors:
    """The floors of a list of priced offers, from the start `start` of a plan and its start item `item`."""

    def __init__(self, abstraction: Abstraction, start: CompressedState, priced: list[PricedOffer] | tuple[PricedOffer, ...], item) -> None:
        self.ab = abstraction
        self.start = start
        self.item = item
        data = abstraction.data
        goal = abstraction.goal
        kinds = [_kind_of(data, item, offer) for offer in priced]
        crafts = frozenset().union(*(named for kind, named in kinds if kind == CRAFT)) if kinds else frozenset()
        self.chosen = goal_set(goal, start, crafts)
        u_mods = frozenset().union(*(goal.leaves[index].mod_ids for index in self.chosen)) if self.chosen else frozenset()
        self.entries: list[_Entry] = []
        for index, (offer, (kind, named)) in enumerate(zip(priced, kinds)):
            pbar = ONE
            if kind == RESTART_KIND:
                pbar = ZERO
            elif kind == CRAFT:
                pbar = ONE if named & u_mods else ZERO
            self.entries.append(_Entry(index, offer, kind, 0, pbar))
        self.bare = replace(start, slots=())
        self.shape = (start.flags, start.fractured)
        self.rho = best_first_rho(self.entries, self._raise) if self.chosen else 0.0

    def _raise(self, entry: _Entry, level: int) -> None:
        entry.kind, entry.pbar, entry.level = _raised(
            self.ab, self.bare, self.item, self.chosen, entry.priced.offer.action, entry.kind, entry.level, entry.pbar, level
        )

    # ---- the classes of states ------------------------------------------------------------------------------------------

    def shaped(self, flags, fractured, status: tuple) -> bool:
        """Whether a state with these flags, fractured mods and status is outside `E` and has the start's shape: the class `rho` and `pbar` hold in."""
        if not self.chosen or (flags, fractured) != self.shape:
            return False
        return not all(status[index] is Status.PASSING for index in self.chosen)

    # ---- the floors -----------------------------------------------------------------------------------------------------

    def lower(self, position: int, shaped: bool) -> float:
        """A floor of `Q*(s, a)` for the offer at `position` and a state of the class (never above the exact cost)."""
        entry = self.entries[position]
        if not shaped or entry.pbar == ONE:
            return entry.cost
        return entry.cost + float(1 - entry.pbar) * self.rho

    def floor(self, positions, shaped: bool) -> float:
        """The least floor over `positions` (infinity for none)."""
        return min((self.lower(position, shaped) for position in positions), default=math.inf)

    def initial(self) -> list[int]:
        """The offers the model starts with: the restart, the crafts and the `SMALL_START` rerolls of least cost / pbar (the cheapest offers if none)."""
        inside = {entry.index for entry in self.entries if entry.kind in (RESTART_KIND, CRAFT)}
        rerolls = sorted((entry for entry in self.entries if entry.kind == REROLL), key=lambda entry: (entry.ratio, entry.index))
        inside.update(entry.index for entry in rerolls[:SMALL_START])
        if not inside:
            inside.update(entry.index for entry in sorted(self.entries, key=lambda entry: (entry.cost, entry.index))[:SMALL_START])
        return sorted(inside)

    def needed(self, position: int, limit_shaped: float | None, limit_plain: float | None) -> float | None:
        """The floor that makes the offer at `position` worth building, or None when it cannot lower the value of any key it was asked about.

        `limit_shaped` is the largest model value of a key in the class `shaped` that the model capped (None when none was), `limit_plain` that of the
        other keys. The offer is needed when its floor in a class is not above the limit of the class. A reroll's floor in the class `shaped` is brought
        from `pbar = 1` through the loose bound to the exact chance, a level at a time, and stops at the first level whose floor is above the limit.
        """
        entry = self.entries[position]
        if limit_plain is not None and entry.cost * (1 - SLACK) <= limit_plain:
            return entry.cost
        if limit_shaped is None:
            return None
        for level in (0, 1, 2):
            if level and entry.kind == REROLL and entry.level < level:
                self._raise(entry, level)
            low = self.lower(position, True)
            if low * (1 - SLACK) > limit_shaped:
                return None
            if entry.kind != REROLL or entry.level >= 2:
                return low
        return self.lower(position, True)


__all__ = ["OfferFloors"]
