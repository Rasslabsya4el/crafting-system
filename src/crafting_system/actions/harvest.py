"""The tagged Harvest reforge: rerolls a rare item like a Chaos Orb and guarantees one mod with a tag."""

from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .draw import refuse_unmodelled
from .errors import NotApplicableError
from .outcomes import Outcomes

TAGGED_RARE_REFORGE_EXISTS = get_rule("harvest_reforge.tagged_rare_reforge_exists")
REROLLS_LIKE_CHAOS_WITH_GUARANTEED_TAG = get_rule("harvest_reforge.rerolls_like_chaos_with_guaranteed_tag")
REFUSED_ON_CORRUPTED = get_rule("harvest_reforge.refused_on_corrupted")


@dataclass(frozen=True)
class HarvestReforge:
    """One tagged Harvest reforge of a rare item; `tag` is the craft's name in lower case ("lightning")."""

    tag: str = "lightning"

    def __post_init__(self) -> None:
        if not isinstance(self.tag, str) or self.tag not in TAGGED_RARE_REFORGE_EXISTS.value:
            known = ", ".join(sorted(TAGGED_RARE_REFORGE_EXISTS.value))
            raise ValueError(f"there is no Harvest reforge for the tag {self.tag!r}; known: {known}")

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the reforge on `item`.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, or whose pool holds
        no mod with the tag that it can still take, and `OutOfScopeError` for a jewel, an influenced
        item or one with a crafted metamod. Ordinary crafted mods are removed by the reroll.
        """
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(
                f"a Harvest reforge works on a rare item only, and this item is {item.rarity}"
            )
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Harvest reforge")
        refuse_unmodelled(data, item)
        return Outcomes.reroll(data, item, tag=TAGGED_RARE_REFORGE_EXISTS.value[self.tag])
