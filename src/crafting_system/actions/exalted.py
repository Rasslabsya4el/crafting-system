"""The Exalted Orb: adds one random mod to a rare item that has an open slot, through the shared add.

The orbs of the rare item are `ExaltedOrb()` (one more mod through the same shared add, on a rare item with an
open slot), `AnnulmentOrb()` (removes one mod that is not fractured, uniformly, D5; the rarity stays) and
`FracturingOrb()` (a rare item of 4 or more mods that is not influenced, fractured or corrupted: fractures one
mod, uniformly, D6; a crafted mod or a metamod is a candidate, and a fractured one stays). The Exalted and Annulment orbs return an `Outcomes` and a `Finite`; the Fracturing Orb a `FractureOutcomes`,
a `Finite` whose `fractures` is True. None is a planner kind yet. An influenced item draws from the pool of its
base tags plus the influence tags (`item_tags` in `pool.py`), so the mods of an influence join every pool.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .add import add_one_mod
from .catalog import kind
from .contract import Action, Adds, Reads
from .draw import refuse_unmodelled
from .errors import NotApplicableError
from .outcomes import Outcomes
from .strand_use import SPEND_EXALTED, SpendLaw, StrandUse

__all__ = [
    "ExaltedOrb",
]

ACCEPTS_RARE_ONLY = get_rule("exalted_orb.accepts_rare_only")
ADDS_ONE_MOD = get_rule("exalted_orb.adds_one_mod")
REFUSED_ON_CORRUPTED = get_rule("exalted_orb.refused_on_corrupted")
COST = get_rule("exalted_orb.cost")
JEWELS_TAKE_THE_ORBS = get_rule("jewel.ordinary_orbs_work_on_jewels")


@dataclass(frozen=True)
class ExaltedOrb(Action):
    """One Exalted Orb."""

    def label(self, data: GameData | None = None) -> str:
        return "Exalted Orb"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        # ADR-0041 and its amendment: cuts; the ceiling follows the explicit mods on the item before the craft, 16, 22, 26, 32, 34, 38 for 0 to 5
        by_mods = SPEND_EXALTED.value["ceiling_by_mods_before"]
        return StrandUse.cutting(SpendLaw.by_mods(*(by_mods[count] for count in sorted(by_mods))), SPEND_EXALTED)

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def reads(self, data: GameData) -> Reads:
        return Reads.adding(variants=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset())

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, is full, or for which
        no mod is legal, and `OutOfScopeError` for a cluster jewel or an influenced item of a class with no
        influence class key. An open slot of a locked side still fills; the Attack and Caster metamods
        keep the mods with their tag out of the pool.
        """
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(f"an Exalted Orb works on a rare item only, and this item is {item.rarity}")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Exalted Orb")
        refuse_unmodelled(data, item, jewels=True)
        return add_one_mod(data, item, "an Exalted Orb", cut=self.cut_of(data, item))


@kind(
    "exalted-orb",
    order=75,
    opt_in=True,
)
def _exalted_orb(data: GameData, item: Item):
    # a normal or magic item becomes rare on the way (an essence, a Regal Orb), so the kind is listed for it too
    yield ExaltedOrb()
