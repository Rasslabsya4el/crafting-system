"""The influence Harvest reforge: rerolls an influenced rare item like a Chaos Orb and guarantees one influence mod.

The guaranteed mod is drawn first, in proportion to weight, from the influence mods that the item can still
roll: the mods of its pool whose spawn weight comes from one of its influence tags
(`harvest_reforge.influence_mod_is_influence_spawn`; the `influence_mod` tag of the data is not the test, the
Hunter mods lack it). An item without influence has none and the craft is refused. The pool of an influenced
item is the one of ticket #67 (`affix_pool.influence_tags`). Randomise Influence is another craft and is not
modelled (out of v1).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.data import GameData, Mod
from crafting_system.items import Item
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError
from .harvest import check_reforgeable
from .outcomes import Outcomes
from .pool import item_tags

__all__ = [
    "HarvestReforgeInfluence",
]

INFLUENCE_REFORGE_EXISTS = get_rule("harvest_reforge.influence_reforge_exists")
INFLUENCE_MOD_IS_INFLUENCE_SPAWN = get_rule("harvest_reforge.influence_mod_is_influence_spawn")
REFUSED_WHEN_NOT_INFLUENCED = get_rule("harvest_reforge.influence_reforge_refused_when_not_influenced")
LIFEFORCE_COST = get_rule("harvest_reforge.influence_reforge_lifeforce_cost")

GUARANTEE = "influence"  # the name of the guarantee inside the pool, not a tag of the data


def influence_spawn_test(data: GameData, item: Item):
    """The test of whether a mod is an influence mod of `item`: its first spawn weight that the item has is an influence tag."""
    tags = frozenset(item_tags(data, item))
    influence_tags = tags - frozenset(data.base_items[item.base_id].tags)

    def is_influence_mod(mod: Mod) -> bool:
        deciding = next((entry.tag for entry in mod.spawn_weights if entry.tag in tags), None)
        return deciding in influence_tags

    return is_influence_mod


@dataclass(frozen=True)
class HarvestReforgeInfluence(Action):
    """One influence Harvest reforge."""

    def label(self, data: GameData | None = None) -> str:
        return "Harvest Reforge Influence"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(LIFEFORCE_COST.value)

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing(block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.erasing(named=frozenset())

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the reforge on `item`.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, has no influence, or whose pool
        holds no influence mod that it can still take (an Attack/Caster metamod that stays keeps the influence mods with
        its tag out of the guaranteed draw), and `OutOfScopeError` for a jewel or an influenced item whose
        class has no influence class key. Ordinary crafted mods are removed by the reroll; a locked side stays.
        """
        check_reforgeable(data, item)
        if not item.influences:
            raise NotApplicableError("the item has no influence, and the influence reforge works on an influenced item only")
        return Outcomes.reroll(data, item, tag=GUARANTEE, guaranteed=influence_spawn_test(data, item))


@kind("harvest-reforge-influence", order=21)
def _harvest_reforge_influence(data: GameData, item: Item):
    if item.influences:
        yield HarvestReforgeInfluence()
