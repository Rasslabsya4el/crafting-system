"""The tagged Harvest reforges: reroll a rare item like a Chaos Orb and guarantee one mod with a tag.

Sixteen crafts exist in 3.29, one per tag of `harvest_reforge.tagged_rare_reforge_exists`; each costs the
lifeforce (and, for five of them, the Crystallised Rancour) of `harvest_reforge.lifeforce_cost`. The influence
reforge (`harvest_influence.py`) and the two likelihood reforges (`harvest_likelihood.py`) are other methods.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .draw import refuse_unmodelled
from .errors import NotApplicableError
from .outcomes import Outcomes

TAGGED_RARE_REFORGE_EXISTS = get_rule("harvest_reforge.tagged_rare_reforge_exists")
REROLLS_LIKE_CHAOS_WITH_GUARANTEED_TAG = get_rule("harvest_reforge.rerolls_like_chaos_with_guaranteed_tag")
REFUSED_ON_CORRUPTED = get_rule("harvest_reforge.refused_on_corrupted")
HARVEST_FILTERS_FIRST_ADDED_MOD = get_rule("metamods.harvest_filters_first_added_mod")
GUARANTEED_MOD_FITS_THE_FREE_SLOTS = get_rule("harvest_reforge.guaranteed_mod_fits_the_free_slots")
REFUSED_WHEN_NO_TAGGED_MOD_FITS = get_rule("harvest_reforge.refused_when_no_tagged_mod_fits_a_free_slot")
LIFEFORCE_COST = get_rule("harvest_reforge.lifeforce_cost")


def check_reforgeable(data: GameData, item: Item) -> None:
    """Raise what every Harvest reforge raises before it draws: `NotApplicableError` for an item that is not rare or is
    corrupted, `OutOfScopeError` for a jewel (`refuse_unmodelled`). The one place for a rule that
    holds for all reforges."""
    if item.rarity is not Rarity.RARE:
        raise NotApplicableError(f"a Harvest reforge works on a rare item only, and this item is {item.rarity}")
    if item.corrupted:
        raise NotApplicableError("the item is corrupted, and a corrupted item takes no Harvest reforge")
    refuse_unmodelled(data, item)


@dataclass(frozen=True)
class HarvestReforge(Action):
    """One tagged Harvest reforge of a rare item; `tag` is the craft's name in lower case ("lightning", "defence")."""

    tag: str = "lightning"

    def __post_init__(self) -> None:
        if not isinstance(self.tag, str) or self.tag not in TAGGED_RARE_REFORGE_EXISTS.value:
            known = ", ".join(sorted(TAGGED_RARE_REFORGE_EXISTS.value))
            raise ValueError(f"there is no Harvest reforge for the tag {self.tag!r}; known: {known}")

    def label(self, data: GameData | None = None) -> str:
        return f"Harvest Reforge {self.tag.title()}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        cost = LIFEFORCE_COST.value.get(self.tag)
        if cost is None:
            raise ValueError(f"the claim harvest_reforge.lifeforce_cost gives no cost for the {self.tag} reforge")
        return dict(cost)

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing(block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.erasing(named=frozenset(), tag=TAGGED_RARE_REFORGE_EXISTS.value[self.tag], single_draw=True)

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the reforge on `item`.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, or whose pool holds
        no mod with the tag that it can still take, and `OutOfScopeError` for a jewel or an influenced item whose
        class has no influence class key. Ordinary crafted mods are removed by the reroll. A locked side stays
        and counts inside the total; an Attack or Caster metamod that stays filters the guaranteed mod only (D8
        of issue #28), not the draws that follow.
        """
        check_reforgeable(data, item)
        return Outcomes.reroll(data, item, tag=TAGGED_RARE_REFORGE_EXISTS.value[self.tag])


@kind("harvest-reforge", order=20)
def _harvest_reforges(data: GameData, item: Item):
    for tag in TAGGED_RARE_REFORGE_EXISTS.value:
        yield HarvestReforge(tag)
