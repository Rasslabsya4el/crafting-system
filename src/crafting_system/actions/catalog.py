"""The catalog: every action kind that can apply to an item, each module registering its own.

A *kind* is a family of actions a module defines (Chaos Orb, every essence, every bench craft, every
fossil set, ...). A module registers its kinds once, at import, with the `kind` decorator on a
function `members(data, item)` that yields the actions of the kind for `item`; the order number
fixes where the kind stands in a catalog (a planner offers in that order, so numbers stay the same
when a module is added). `catalog(data, item)` lists the members of every kind, or of the kinds that
are `planner` kinds, and `kinds()` lists the kinds themselves.

`members` decides what can apply to the item or to what a policy makes of it: an essence of level 1 to
4 works on a normal item only, so it is listed only for a normal item; the refusal that needs the
item's mods (a full side, a family already on it) is `outcomes`'s, because the planner asks the catalog
once per rarity the item can reach (`planner/_offers.py` `reached_items`, #973) and the policy then visits
many states.

A kind is `planner=False` when the planner cannot use it yet (a reason in `why_not`): it stays in the
catalog and under the contract tests, and a planner that asks for `planner_only` leaves it out. `why_not` is the developer's
text; `player_why`, when a kind has one, is the same reason in a player's words, and the answer states it beside the kind
instead of the general "methods the planner cannot use yet" (`planner/_offers.py`, OR-13; #943).

A kind is `opt_in` when the planner can use it but offers it only when it is named (`catalog(..., names=None)` leaves an opt-in kind
out; `names` that include it list it). Since #886 (OR-41) no kind of the beta's scope is opt-in: every one is offered by default, and
the flag is left only to a kind outside it (the recombinator, the Foulborn Exalted Orb, and since #1125 the corrupting Vaal Orb and Locus of
Corruption of B4; `prices/spends.py`, `DEFERRED_KINDS`) and as the mechanism behind a user's switch that turns a method off (#323). `tests/test_actions_opt_in.py` fails on an in-scope opt-in kind.

A kind is `needs_strands` when its actions exist only in a plan that considers Memory Strands (the Foulborn orbs, the Orb of Remembrance,
the Orb of Unravelling; ADR-0040, "Strands are off unless the query has them"). `catalog(..., strands=False)` leaves such a kind out;
`strands=True` (the setting `memory_strands` of the query) lists it, and so does an item that holds strands, which turns the setting on by
itself. `kinds()` and the contract suites still see it, so a kind of this sort is checked like every other.

A kind is `burns` when some of its actions declare `burn` (ticket #295, ADR-0056): a currency that changes no mod and may give a Hinekora's Lock up.
`burn.py` asks the kinds with this flag, and only them, for the burns of a state (the other kinds are never searched for one).
The flag does not offer the kind: a burn is never a plain action, and the kind stays a `planner=False` kind or is offered by its own rules.

A kind is `corrupting` when every action it lists corrupts (`Adds.corrupts`: the Vaal Orb, the Locus of Corruption). A planner
leaves such a kind unmentioned in its report when the target takes no corrupted item (ADR-0036).

A kind is `only_quality` when every action it lists only sets the quality (`Adds.only_quality`: the catalysts, the quality currency). Quality
changes no odds of the mods (ADR-0029), so such a kind can never make a plan of the mods cheaper: a planner leaves it unmentioned in its
report when the target asks for no quality, or when the kind lists nothing for the start item (a catalyst on boots), as it does the
corrupting kinds (#159).

A kind is `only_implicit_rolls` when every action it lists only rerolls the values of the item's implicits (`Adds.implicits` with
`Adds.needs_roll_limit`: the Blessed Orb). Such a kind can change no odds of the mods either, so a planner leaves it unmentioned in its report
when the target asks for no roll of an implicit the start item holds with a range (#1231).

Two declarations are read by the shared tests, which therefore name no kind (ticket #334). `applies_only_to` names the item class
that is the only one the kind works on (`"armour"`: body armours, boots, gloves and helmets; the fixture items of the contract suite
are amulets, so the suite does not require that the kind applies to one, and fails when it does). `reads_item_state_while_not_planner`
names the one part of the item state (`"implicits"`, `"quality"` or `"offer"`) that a kind outside the planner reads, so the item-state
suite expects that part to be declared by its actions and the others not; `"any"` says that the kind declares whatever part it needs
(the veiled orbs, which declare the offer and are planner kinds since ticket #145: the compressed model keeps the offer). Both are empty
for an ordinary kind.

**A model gap met while a kind lists its actions** (ticket #511) is not a game refusal. A `members` function that leaves an action, a part of
the kind or the whole kind out because the model has no rule for this item (`OutOfScopeError`) says so with `listing_gap(error, subject)`;
one that leaves it out because the game refuses it (`NotApplicableError`) stays silent. `catalog_kinds(..., gaps=found)` collects what the
kinds it lists said into `found`, one `ListingGap` per kind, subject and cause, and the planner makes them a limit of the answer
(`planner/_offers.py`). A listing asked without `gaps` collects nothing: a `listing_gap` there is a no-op.
"""

from collections.abc import Callable, Collection, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from crafting_system.data import GameData
from crafting_system.items import Item

from .contract import Action
from .errors import OutOfScopeError

__all__ = [
    "Kind",
    "ListingGap",
    "catalog",
    "catalog_kinds",
    "kind",
    "kinds",
    "listing_gap",
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
    needs_strands: bool = False
    burns: bool = False
    player_why: str = field(default="", compare=False)
    only_quality: bool = False
    only_implicit_rolls: bool = False


_KINDS: dict[str, Kind] = {}


@dataclass(frozen=True)
class ListingGap:
    """A model gap met while the kind `kind` listed its actions for an item (ticket #511).

    `subject` is what the kind left out, in player words ("Hollow Fossil"), or "" when it left the whole kind out; `cause` is the player's
    sentence of the `OutOfScopeError` and `detail` the developer's text behind it.
    """

    kind: str
    subject: str
    cause: str
    detail: str = field(default="", compare=False)


_LISTING: ContextVar[tuple[str, list[ListingGap]] | None] = ContextVar("catalog_listing", default=None)


def listing_gap(error: OutOfScopeError, subject: str = "") -> None:
    """Say that the kind being listed leaves `subject` ("" for all of it) out because the model has no rule for the item (`error`).

    It goes to the `gaps` of the `catalog_kinds` that lists the kind, once per subject and cause; outside such a listing it is dropped.
    """
    current = _LISTING.get()
    if current is None:
        return
    name, found = current
    gap = ListingGap(name, subject, error.player, error.detail)
    if gap not in found:
        found.append(gap)


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
    needs_strands: bool = False,
    burns: bool = False,
    player_why: str = "",
    only_quality: bool = False,
    only_implicit_rolls: bool = False,
) -> Callable[[Callable[[GameData, Item], Iterable[Action]]], Callable[[GameData, Item], Iterable[Action]]]:
    """Decorator that registers a function `members(data, item)` as the kind `name`."""

    def decorate(members):
        register(Kind(name, members, order, planner, why_not, opt_in, corrupting, applies_only_to, reads_item_state_while_not_planner, needs_strands, burns, player_why, only_quality, only_implicit_rolls))
        return members

    return decorate


def kinds(*, planner_only: bool = False) -> tuple[Kind, ...]:
    """The registered kinds in catalog order."""
    chosen = (entry for entry in _KINDS.values() if entry.planner or not planner_only)
    return tuple(sorted(chosen, key=lambda entry: (entry.order, entry.name)))


def catalog(
    data: GameData,
    item: Item,
    *,
    planner_only: bool = False,
    names: Collection[str] | None = None,
    strands: bool = False,
) -> tuple[Action, ...]:
    """Every action of every kind that can apply to `item`, in catalog order.

    With `planner_only` only the kinds the planner can use; with `names` only the kinds of those names (an `opt_in`
    kind is listed only when named). A `needs_strands` kind is listed only with `strands` or for an item that holds
    strands. The same action never appears twice.
    """
    return tuple(catalog_kinds(data, item, planner_only=planner_only, names=names, strands=strands))


def catalog_kinds(
    data: GameData,
    item: Item,
    *,
    planner_only: bool = False,
    names: Collection[str] | None = None,
    strands: bool = False,
    gaps: list[ListingGap] | None = None,
) -> dict[Action, str]:
    """`catalog`, each action with the name of the kind that lists it (the first, when two kinds list the same action).

    With `gaps`, the model gaps the kinds meet while they list (`listing_gap`) are added to it.
    """
    found: dict[Action, str] = {}
    for entry in kinds(planner_only=planner_only):
        if names is not None and entry.name not in names:
            continue
        if entry.needs_strands and not (strands or getattr(item, "memory_strands", 0) >= 1):
            continue
        if names is None and entry.opt_in and planner_only:
            continue
        token = _LISTING.set((entry.name, gaps) if gaps is not None else None)  # a listing inside a listing writes to its own caller's list
        try:
            for action in entry.members(data, item):
                try:
                    hash(action)
                except TypeError:
                    raise TypeError(f"{action!r} of the kind {entry.name!r} is not hashable: make an action a frozen dataclass") from None
                found.setdefault(action, entry.name)
        finally:
            _LISTING.reset(token)
    return found


@contextmanager
def registered(entry: Kind) -> Iterator[Kind]:
    """Register `entry` for the length of a `with` block (a test's toy action) and take it out again."""
    register(entry)
    try:
        yield entry
    finally:
        _KINDS.pop(entry.name, None)
