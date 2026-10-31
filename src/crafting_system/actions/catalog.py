"""The catalog: every action kind that can apply to an item, each module registering its own.

A *kind* is a family of actions a module defines (Chaos Orb, every essence, every bench craft, every
fossil set, ...). A module registers its kinds once, at import, with the `kind` decorator on a
function `members(data, item)` that yields the actions of the kind for `item`; the order number
fixes where the kind stands in a catalog (a planner offers in that order, so numbers stay the same
when a module is added). `catalog(data, item)` lists the members of every kind, or of the kinds that
are `planner` kinds, and `kinds()` lists the kinds themselves.

`members` decides what can apply to the item or to what a policy makes of it: an essence of level 1 to
4 works on a normal item only, so it is listed only for a normal item; the refusal that needs the
item's mods (a full side, a family already on it) is `outcomes`'s, because the catalog is asked once
for the start item and the policy then visits many states.

A kind is `planner=False` when the planner cannot use it yet (a reason in `why_not`): it stays in the
catalog and under the contract tests, and a planner that asks for `planner_only` leaves it out.
"""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from crafting_system.data import GameData
from crafting_system.items import Item

from .contract import Action


@dataclass(frozen=True)
class Kind:
    """One registered family of actions."""

    name: str
    members: Callable[[GameData, Item], Iterable[Action]]
    order: int
    planner: bool = True
    why_not: str = field(default="", compare=False)


_KINDS: dict[str, Kind] = {}


def register(entry: Kind) -> Kind:
    """Add `entry` to the catalog; a second kind with the same name is a mistake (`ValueError`)."""
    if entry.name in _KINDS:
        raise ValueError(f"the action kind {entry.name!r} is registered twice")
    _KINDS[entry.name] = entry
    return entry


def kind(
    name: str, *, order: int, planner: bool = True, why_not: str = ""
) -> Callable[[Callable[[GameData, Item], Iterable[Action]]], Callable[[GameData, Item], Iterable[Action]]]:
    """Decorator that registers a function `members(data, item)` as the kind `name`."""

    def decorate(members):
        register(Kind(name, members, order, planner, why_not))
        return members

    return decorate


def kinds(*, planner_only: bool = False) -> tuple[Kind, ...]:
    """The registered kinds in catalog order."""
    chosen = (entry for entry in _KINDS.values() if entry.planner or not planner_only)
    return tuple(sorted(chosen, key=lambda entry: (entry.order, entry.name)))


def catalog(data: GameData, item: Item, *, planner_only: bool = False) -> tuple[Action, ...]:
    """Every action of every kind that can apply to `item`, in catalog order.

    With `planner_only` only the kinds the planner can use. The same action never appears twice.
    """
    found: dict[Action, None] = {}
    for entry in kinds(planner_only=planner_only):
        for action in entry.members(data, item):
            try:
                hash(action)
            except TypeError:
                raise TypeError(f"{action!r} of the kind {entry.name!r} is not hashable: make an action a frozen dataclass") from None
            found.setdefault(action)
    return tuple(found)


@contextmanager
def registered(entry: Kind) -> Iterator[Kind]:
    """Register `entry` for the length of a `with` block (a test's toy action) and take it out again."""
    register(entry)
    try:
        yield entry
    finally:
        _KINDS.pop(entry.name, None)
