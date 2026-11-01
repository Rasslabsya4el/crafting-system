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

A kind is `opt_in` when the planner can use it but offers it only when a target names it in `actions:` (the fossil
sets: 12,696 of them on boots, which a target that is not about fossils must not pay for). `catalog(..., names=None)`
leaves an opt-in kind out; `names` that include it list it.

A kind is `corrupting` when every action it lists corrupts (`Adds.corrupts`: the Vaal Orb, the Locus of Corruption). A planner
leaves such a kind unmentioned in its report when the target takes no corrupted item (ADR-0036).

Two declarations are read by the shared tests, which therefore name no kind (ticket #334). `applies_only_to` names the item class
that is the only one the kind works on (`"armour"`: body armours, boots, gloves and helmets; the fixture items of the contract suite
are amulets, so the suite does not require that the kind applies to one, and fails when it does). `reads_item_state_while_not_planner`
names the one part of the item state (`"implicits"`, `"quality"` or `"offer"`) that a kind outside the planner reads, so the item-state
suite expects that part to be declared by its actions and the others not. Both are empty for an ordinary kind.
"""

from collections.abc import Callable, Collection, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from crafting_system.data import GameData
from crafting_system.items import Item

from .contract import Action

__all__ = [
    "Kind",
    "catalog",
    "kind",
    "kinds",
    "register",
    "registered",
]


@dataclass(frozen=True)
class Kind:
    """One registered family of actions."""

    name: str
    members: Callable[[GameData, Item], Iterable[Action]]
    order: int
    planner: bool = True
    why_not: str = field(default="", compare=False)
    opt_in: bool = False
    corrupting: bool = False
    applies_only_to: str = ""
    reads_item_state_while_not_planner: str = ""


_KINDS: dict[str, Kind] = {}


def register(entry: Kind) -> Kind:
    """Add `entry` to the catalog; a second kind with the same name is a mistake (`ValueError`)."""
    if entry.name in _KINDS:
        raise ValueError(f"the action kind {entry.name!r} is registered twice")
    _KINDS[entry.name] = entry
    return entry


def kind(
    name: str,
    *,
    order: int,
    planner: bool = True,
    why_not: str = "",
    opt_in: bool = False,
    corrupting: bool = False,
    applies_only_to: str = "",
    reads_item_state_while_not_planner: str = "",
) -> Callable[[Callable[[GameData, Item], Iterable[Action]]], Callable[[GameData, Item], Iterable[Action]]]:
    """Decorator that registers a function `members(data, item)` as the kind `name`."""

    def decorate(members):
        register(Kind(name, members, order, planner, why_not, opt_in, corrupting, applies_only_to, reads_item_state_while_not_planner))
        return members

    return decorate


def kinds(*, planner_only: bool = False) -> tuple[Kind, ...]:
    """The registered kinds in catalog order."""
    chosen = (entry for entry in _KINDS.values() if entry.planner or not planner_only)
    return tuple(sorted(chosen, key=lambda entry: (entry.order, entry.name)))


def catalog(
    data: GameData, item: Item, *, planner_only: bool = False, names: Collection[str] | None = None
) -> tuple[Action, ...]:
    """Every action of every kind that can apply to `item`, in catalog order.

    With `planner_only` only the kinds the planner can use; with `names` only the kinds of those names (an `opt_in`
    kind is listed only when named). The same action never appears twice.
    """
    found: dict[Action, None] = {}
    for entry in kinds(planner_only=planner_only):
        if names is not None and entry.name not in names:
            continue
        if names is None and entry.opt_in and planner_only:
            continue
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
