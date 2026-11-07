"""The rule of a completed route, as a check (ticket #599, decision #628).

A guide leaves gaps: states where its rules say nothing. A completed route is the guide's rules plus rules the guide does not have, so that the
route finishes and has a cost to compare with the planner's (`BenchmarkRoute.completed`). The rule for what it may add, written once in the route
language (`_route.py`, "A completed route"): it fills a gap with the guide's own loop and the actions the game forces to make that loop legal; it never
takes the planner's own move; and it never restarts where the guide's loop could keep the progress.

The last clause is the one a program can check, and this module does. A `restart` that a rule the guide does not have fires (a catch-all at the end of the
file, say) throws the item away. It is justified only where every action the guide's own rules name is refused by the game: the guide's loop cannot go on
from there, so nothing the item holds could have been kept by it. A state where such a restart fires while one of the guide's actions is legal is a
`Loss`: it names the legal actions. (The guide's own `restart` rules are not checked: the guide says them.)

Two readings of the same check:

* `losses_at_item`: on a concrete item, which the tests build by hand (R04's gap states are a handful of items).
* `walked_losses`: on every state the completed route reaches in the walked graph of a packed plan (R04 and R14, run by a heavy run:
  `.github/scripts/completion_check.py`).

Pure reading of a route against a plan; nothing is solved here.
"""

from dataclasses import dataclass

from crafting_system.abstraction import CompressedState
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.data import GameData
from crafting_system.items import Item

from ._plan import Plan
from ._route import RESTART, Route
from ._route_packed import _Reading, route_actions


@dataclass(frozen=True)
class Loss:
    """A state where a rule the guide does not have restarts, though the guide's own actions `legal` could go on from it."""

    state: CompressedState | Item
    rule_line: int  # the line of the added rule in the completed route's file
    legal: tuple[str, ...]


def guide_actions(guide: Route) -> tuple[str, ...]:
    """The actions the guide's own rules name, in the order they first appear; `restart` is not one of them (it is what is being checked)."""
    found: list[str] = []
    for rule in guide.rules:
        if rule.do != RESTART and rule.do not in found:
            found.append(rule.do)
    return tuple(found)


def added_restarts(guide: Route, completed: Route) -> frozenset[int]:
    """The indexes in `completed.rules` of the `restart` rules the guide does not have (a rule is the guide's when its conditions and action are the same)."""
    mine = {(rule.when, rule.do) for rule in guide.rules}
    return frozenset(k for k, rule in enumerate(completed.rules) if rule.do == RESTART and (rule.when, rule.do) not in mine)


def losses_at_item(plan: Plan, guide: Route, completed: Route, data: GameData, item: Item) -> tuple[Loss, ...]:
    """The loss at the concrete `item`, if the completed route restarts there by a rule the guide does not have and a guide action is legal on it."""
    added = added_restarts(guide, completed)
    state = plan.abstraction.compress(item)
    offers = {priced.label: priced for priced in plan.offers}

    def refused(label: str) -> bool:
        try:
            offers[label].offer.action.outcomes(data, item)
        except (NotApplicableError, OutOfScopeError):
            return True
        return False

    for k, rule in enumerate(completed.rules):
        if not rule.when.matches(state, data):
            continue
        if refused(rule.do):
            if completed.skip_refused:
                continue
            return ()  # the route has a gap here, not a restart
        if k not in added:
            return ()
        legal = tuple(label for label in guide_actions(guide) if not refused(label))
        return (Loss(item, rule.line, legal),) if legal else ()
    return ()


def walked_losses(plan: Plan, guide: Route, completed: Route, data: GameData) -> tuple[Loss, ...]:
    """Every state of the completed route on the walked graph of a packed plan where an added `restart` fires and a guide action is legal."""
    added = added_restarts(guide, completed)
    if not added:
        return ()
    reading = _Reading(plan, completed, data)
    _, labels, _, _ = route_actions(plan, completed, data)
    names = guide_actions(guide)
    found = []
    for i, label in sorted(labels.items()):
        if label != RESTART:
            continue
        k = _fired(reading, completed, i)
        if k not in added:
            continue
        legal = tuple(name for name in names if reading.action(i, name) is not None)
        if legal:
            found.append(Loss(reading.walked.states[i], completed.rules[k].line, legal))
    return tuple(found)


def _fired(reading: _Reading, completed: Route, i: int) -> int | None:
    """The index of the rule of `completed` that acts at graph state `i`, as `_Reading.choose` finds it."""
    state = reading.walked.states[i]
    for k, rule in enumerate(completed.rules):
        if not rule.when.matches(state, reading.data):
            continue
        if reading.action(i, rule.do) is not None:
            return k
        if not completed.skip_refused:
            return None
    return None
