"""Whether an action can be used on any item of a base at all, asked before the walk (ticket #848).

`draw.refuse_unmodelled` is the one place that refuses an item for its base alone (a jewel for an action not modelled on jewels, a cluster
jewel, a base that exists as a unique only), and it raises `UnmodelledBase` for it. Its verdict reads nothing but the base, so an action that
raises it on one item of a base refuses every item of that base: the planner can leave such an action out before the walk instead of asking it
at every state (on the Cobalt Jewel J01 the Harvest crafts and the veiled orbs; their reads also split the states the walk keeps).

`base_refusal` asks the action on a few items of the base and stops each use as soon as it reaches `refuse_unmodelled` and passes it (`probing`):
past that point the action's own work (a pool, a draw) is not needed for the answer, so the question costs a check per offer, not a kernel. An
action that never reaches the call, or is refused by the game before it on every item asked, is kept: nothing is proved about it.
"""

from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from crafting_system.data import GameData
from crafting_system.items import Item

from .errors import NotApplicableError, OutOfScopeError, UnmodelledBase

if TYPE_CHECKING:
    from .contract import Action

__all__ = ["base_refusal"]

_PROBING: ContextVar[bool] = ContextVar("base_probe", default=False)


class BasePassed(Exception):  # noqa: N818  (a signal, not an error: it subclasses neither family, so no action's own clause catches it)
    """Raised by `refuse_unmodelled` inside `probing` when the base passes: the action works on this base, and the rest of its use is skipped."""


def probing() -> bool:
    """Whether a use runs inside `base_refusal` (then `refuse_unmodelled` stops it at its verdict)."""
    return _PROBING.get()


@contextmanager
def _probe():
    token = _PROBING.set(True)
    try:
        yield
    finally:
        _PROBING.reset(token)


def base_refusal(data: GameData, action: "Action", items: Iterable[Item]) -> UnmodelledBase | None:
    """The refusal of `action` for the base of `items` (one base), or None when it is not shown to refuse every item of it.

    Each item is asked in turn: `UnmodelledBase` proves the refusal; a pass of `refuse_unmodelled`, or a result, proves the action is modelled
    on the base; a game refusal or another model gap before the call says nothing, and the next item is asked.
    """
    with _probe():
        for item in items:
            try:
                action.outcomes_under(data, item)
            except UnmodelledBase as refusal:
                return refusal
            except BasePassed:
                return None
            except (NotApplicableError, OutOfScopeError):  # either family, refused before the base was asked: this item says nothing
                continue
            return None  # it gave a result: modelled here
    return None
