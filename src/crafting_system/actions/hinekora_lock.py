"""Hinekora's Lock as an item the plan buys and puts on a finished item: its label, what it refuses and what it costs (ticket #294, B8, ADR-0054, ADR-0055).

The Lock is **not an `Action`** and is not in the catalog. An `Action` answers `outcomes`, the exact result of one use, and the Lock has
none of its own: it puts the item into a foreseeing state that is never stored (ADR-0054), and the planner builds the Peek (the solver's
look-then-choose action) from the previewable actions of a state. `HinekoraLock` sits beside `Action` and answers only what that build
needs: `label`, `refused_on` (the legality test), `resources` (what it consumes, by price-file name), `strand_use` and `claims`. It
subclasses nothing, so the contract suite, which runs on the kinds of the catalog, does not ask it for `outcomes`.

**What it refuses** (`hinekora_lock.refused_on`, wiki): a corrupted item, a mirrored item and an unmodifiable item (and gems, which are out of v1,
#81, and which the planner never holds). The item model holds a corrupted flag only; an `Item` has no mirrored or unmodifiable flag, so those two
are keyword arguments of the test that a caller who knows them passes (a start item that arrives mirrored, say). `refused_on` answers the
reason, or None for an item the Lock may be put on; `check` raises `NotApplicableError` with it.

**What it costs.** One Hinekora's Lock, by its price-file name (`hinekora_lock.cost`); the Lock is used up when it is applied
(`hinekora_lock.lock_is_used_up`, owner), so a relock pays the price again (ADR-0056). The price entry and the fetchers are B8-3's.

**Strands.** Putting the Lock on changes neither the mods nor the strand count of the item and cuts no tier: it declares
`StrandUse.untouched` as the Blessed Orb does (ADR-0041, `memory_strands.cut_follows_spend_table`: the emulator cuts exactly the methods
that have a spend row, and the Lock has none). The spend of a previewed craft is that craft's own.

**The foresight declarations of the other actions** (`previewable`, `currency_item`, `burn`, `preview_claims`) are on `Action`
(`contract.py`); `claims` here lists the Lock's own claims, which a plan that takes a Lock step lists among its inputs (ADR-0057).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.rules import get_rule

from .errors import NotApplicableError
from .strand_use import CUT_FOLLOWS_SPEND_TABLE, StrandUse

__all__ = [
    "HinekoraLock",
]

FORESEES = get_rule("hinekora_lock.foresees_next_currency")
REFUSED_ON = get_rule("hinekora_lock.refused_on")
USED_UP = get_rule("hinekora_lock.lock_is_used_up")
NO_SECOND_LOCK = get_rule("hinekora_lock.no_second_lock_on_a_foreseeing_item")
COST = get_rule("hinekora_lock.cost")


@dataclass(frozen=True)
class HinekoraLock:
    """One Hinekora's Lock, put on an item that is not corrupted, mirrored or unmodifiable."""

    def label(self, data: GameData | None = None) -> str:
        return "Hinekora's Lock"

    def refused_on(self, item: Item, *, mirrored: bool = False, unmodifiable: bool = False) -> str | None:
        """Why the game refuses the Lock on `item`, or None when it may be put on.

        `mirrored` and `unmodifiable` are the two facts the item model does not hold (see the module docstring); a caller that knows
        either passes it. Whether the item is already under a Lock is no question of the item: no state is foreseeing, so the planner
        offers the Lock only where the flag is off (`hinekora_lock.no_second_lock_on_a_foreseeing_item`, ADR-0054).
        """
        if item.corrupted:
            return "the item is corrupted, and a corrupted item takes no Hinekora's Lock"
        if mirrored:
            return "the item is mirrored, and a mirrored item takes no Hinekora's Lock"
        if unmodifiable:
            return "the item is unmodifiable, and an unmodifiable item takes no Hinekora's Lock"
        return None

    def check(self, item: Item, *, mirrored: bool = False, unmodifiable: bool = False) -> None:
        """Raise `NotApplicableError` when the game refuses the Lock on `item` (`refused_on`)."""
        reason = self.refused_on(item, mirrored=mirrored, unmodifiable=unmodifiable)
        if reason is not None:
            raise NotApplicableError(reason)

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: putting the Lock on neither cuts nor spends; the item is unchanged

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        """The claims behind the Lock itself: what it does, what it refuses, that it is used up and that it cannot be put on twice."""
        return frozenset(rule.id for rule in (FORESEES, REFUSED_ON, USED_UP, NO_SECOND_LOCK, COST))
