"""Two shapes of the imprint state, as throwaway layers over any solver model (ADR-0060, ticket #218). Not collected as tests.

An imprint stores the compressed state of the item and restores it later; it is used up when it restores
(ADR-0034). Both shapes wrap a `base` model (anything with `is_goal` and `actions`, the planner's own model
included) and give the solver a model of its own.

* `WithImprints` is **shape A, snapshots in the item state**. A state is `(s, held)`: the base state and the
  frozenset of base states an imprint was made at. `imprint` adds the current state to `held`, `restore(h)`
  moves the item to `h` and removes it from `held`. The solver sees plain actions; nothing in it knows what an
  imprint is.
* `ImprintAndTry` is **shape B, "imprint then try" as one macro-action**. A state is the base state alone. At an
  imprintable `s`, for every `body` (a fixed run of base action labels) there is one action: make the imprint,
  run the body, and where the end state is not accepted return to `s` (the restore). Its cost is the imprint
  price plus the expected cost of the body, so it is positive and no restore needs a cost of its own.

Neither charges the restore with the cost of building the snapshot state again: the snapshot is the item itself
in an earlier state, so its price is the beast that made it, paid once, when it was made. (ADR-0013's first
reading, "imprint as acquiring a copy", would pay a `Need` for a second item in the snapshot state on every
restore; the tests build that reading by hand to show what the charge does.)
"""

from collections.abc import Callable, Hashable, Iterable
from fractions import Fraction
from itertools import product
from math import lcm

from crafting_system.solver import Action, Need, Outcome

RESTORE_COST = 1e-6  # a restore is free in the game; the solver wants a positive cost, as for the unveil pick (ADR-0026)


class WithImprints:
    """Shape A: the base model with up to `limit` imprints held in the state.

    `imprintable(s)`: an imprint may be made of an item in base state `s` (Croaker: magic; Arachnid: rare
    Talisman, ADR-0034). `restorable(s)`: an imprint may be restored onto an item in `s`, and an item that is
    not (fractured, corrupted) has lost every imprint it held, so the outcome of an action into such a state
    carries an empty set. `clears(label)`: the action makes a new item (a recombination, a split) and its
    outcomes carry an empty set too. `limit` bounds the state, not the game: at `limit` held, an imprint replaces
    one of them (the policy picks which). A snapshot equal to the current state is never made twice and a restore
    onto the current state is not offered (a second imprint of the same state never helps: the item is back in
    that state after the restore and can make it again at the same price).
    """

    def __init__(
        self,
        base,
        *,
        price: float,
        limit: int,
        imprintable: Callable[[Hashable], bool],
        restorable: Callable[[Hashable], bool] = lambda s: True,
        clears: Callable[[Hashable], bool] = lambda label: False,
        restore_cost: float = RESTORE_COST,
    ) -> None:
        self._base = base
        self._price = price
        self._limit = limit
        self._imprintable = imprintable
        self._restorable = restorable
        self._clears = clears
        self._restore_cost = restore_cost

    def start(self, state):
        return (state, frozenset())

    def is_goal(self, state) -> bool:
        return self._base.is_goal(state[0])

    def actions(self, state) -> list[Action]:
        s, held = state
        result = []
        for action in self._base.actions(s):
            outcomes = tuple(
                Outcome((t, held if not self._clears(action.label) and self._restorable(t) else frozenset()), w)
                for t, w in action.outcomes
            )
            inputs = tuple(
                Need((need.start, frozenset()), (need.want, frozenset())) if isinstance(need, Need) else need
                for need in action.extra_inputs
            )  # a donor is an item of its own: it starts and ends with no imprint, and keeps none when it is consumed
            result.append(Action(action.label, action.cost, outcomes, inputs))
        if self._limit and self._imprintable(s) and s not in held:
            if len(held) < self._limit:
                result.append(Action(("imprint",), self._price, (Outcome((s, held | {s}), 1),)))
            else:  # full: the new imprint replaces one held (the old one is thrown away; holding it costs nothing in the game)
                for h in sorted(held, key=repr):
                    result.append(Action(("imprint", h), self._price, (Outcome((s, (held - {h}) | {s}), 1),)))
        if self._restorable(s):
            for h in sorted(held, key=repr):
                if h != s:
                    result.append(Action(("restore", h), self._restore_cost, (Outcome((h, held - {h}), 1),)))
        return result


class ImprintAndTry:
    """Shape B: one macro-action per imprintable state and body; a failed try returns to the snapshot.

    `bodies(s)` lists the bodies, each a tuple of base action labels run in order from `s` (a step whose label
    the state does not offer, or a goal, stops there). `accept(s, t)` says whether an end state `t` is kept;
    where it is not, the item is restored to `s`. The imprint left over after an accepted end state is lost
    (nothing in the state holds it).
    """

    def __init__(
        self,
        base,
        *,
        price: float,
        imprintable: Callable[[Hashable], bool],
        bodies: Callable[[Hashable], Iterable[tuple[Hashable, ...]]],
        accept: Callable[[Hashable, Hashable], bool],
    ) -> None:
        self._base = base
        self._price = price
        self._imprintable = imprintable
        self._bodies = bodies
        self._accept = accept

    def is_goal(self, state) -> bool:
        return self._base.is_goal(state)

    def actions(self, state) -> list[Action]:
        result = list(self._base.actions(state))
        if self._imprintable(state):
            for body in self._bodies(state):
                macro = self._macro(state, body)
                if macro is not None:
                    result.append(macro)
        return result

    def _macro(self, s, body) -> Action | None:
        dist = {s: Fraction(1)}
        cost = Fraction(self._price).limit_denominator(10**9)
        for label in body:
            step: dict = {}
            for state, p in dist.items():
                found = None if self._base.is_goal(state) else next(
                    (a for a in self._base.actions(state) if a.label == label), None
                )
                if found is None:
                    step[state] = step.get(state, 0) + p
                    continue
                cost += p * Fraction(found.cost).limit_denominator(10**9)
                total = sum(w for _, w in found.outcomes)
                for t, w in found.outcomes:
                    step[t] = step.get(t, 0) + p * Fraction(w, total)
            dist = step
        if dist == {s: Fraction(1)}:
            return None  # the body did nothing: not an action
        merged: dict = {}
        for t, p in dist.items():
            kept = t if (self._base.is_goal(t) or self._accept(s, t)) else s
            merged[kept] = merged.get(kept, 0) + p
        scale = lcm(*(p.denominator for p in merged.values()))
        return Action(("imprint", body), float(cost), tuple(Outcome(t, int(p * scale)) for t, p in merged.items()))


def all_bodies(labels: Iterable[Hashable], longest: int) -> list[tuple[Hashable, ...]]:
    """Every run of one to `longest` labels: the catalogue of bodies shape B must list."""
    labels = list(labels)
    return [run for n in range(1, longest + 1) for run in product(labels, repeat=n)]


def explore(model, starts: Iterable) -> dict:
    """Every state reachable from `starts` (goals included) with its actions: `{state: list of actions}`."""
    seen: dict = {}
    stack = list(starts)
    while stack:
        state = stack.pop()
        if state in seen:
            continue
        seen[state] = [] if model.is_goal(state) else list(model.actions(state))
        for action in seen[state]:
            stack.extend(t for t, w in action.outcomes if w)
    return seen


def count_states(model, starts: Iterable) -> int:
    """The number of non-goal states reachable from `starts` (what the solver would hold)."""
    return sum(1 for state in explore(model, starts) if not model.is_goal(state))


def spec_of(model, starts: Iterable):
    """The explicit `(goals, table)` of a model for the oracles of `ssp_input_oracles` (costs as exact fractions)."""
    seen = explore(model, starts)
    goals = {state for state in seen if model.is_goal(state)}
    table = {
        state: [
            (a.label, Fraction(a.cost), [(t, w) for t, w in a.outcomes], list(a.extra_inputs)) for a in actions
        ]
        for state, actions in seen.items()
        if state not in goals
    }
    return goals, table
