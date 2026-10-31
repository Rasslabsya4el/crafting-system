"""The two likelihood Harvest reforges: reroll a rare item like a Chaos Orb, with the mods it holds more or less likely to return.

Before the draw the weight of every mod of a family the item holds a mod of is multiplied by 90 (the more
likely craft) or divided by 90 (the less likely one), `harvest_reforge.likelihood_weight_factor`, and the
reroll draws as many mods as the item held, at least 4 (`harvest_reforge.likelihood_never_fewer_mods`); there
is no guaranteed mod. Unlike the other rerolls this one reads the mods it removes: which families the item
holds decides the pool. The result depends on a family only through the weights of its mods and what they give
the goal, so the declaration is `Reads.adding()` and the compressed state keeps the junk by family type.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData, Mod
from crafting_system.items import Item
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .harvest import check_reforgeable
from .outcomes import Outcomes, retained_item
from .pool import build_pool

LIKELIHOOD_REFORGES_EXIST = get_rule("harvest_reforge.likelihood_reforges_exist")
LIKELIHOOD_WEIGHT_FACTOR = get_rule("harvest_reforge.likelihood_weight_factor")
NEVER_FEWER_MODS = get_rule("harvest_reforge.likelihood_never_fewer_mods")
LIFEFORCE_COST = get_rule("harvest_reforge.likelihood_lifeforce_cost")
REFUSED_ON_CORRUPTED = get_rule("harvest_reforge.refused_on_corrupted")


@dataclass(frozen=True)
class HarvestReforgeLikelihood(Action):
    """One likelihood Harvest reforge: `more` is True for the one that makes the held mods more likely, False for less likely."""

    more: bool = True

    @property
    def _key(self) -> str:
        return "more" if self.more else "less"

    def label(self, data: GameData | None = None) -> str:
        return f"Harvest Reforge {self._key.title()} Likely"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(LIFEFORCE_COST.value)

    def reads(self, data: GameData) -> Reads:
        return Reads.adding()

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.erasing(named=frozenset())

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the reforge on `item`.

        Raises `NotApplicableError` for an item that is not rare or is corrupted, and `OutOfScopeError` for a jewel,
        an influenced item whose class has no influence class key, or one with a crafted metamod. Ordinary
        crafted mods are removed by the reroll (their families still weigh the pool).
        """
        check_reforgeable(data, item)
        held = {family for entry in item.mods for family in data.mods[entry.mod_id].families}
        weight = Fraction(LIKELIHOOD_WEIGHT_FACTOR.value[self._key])
        factor = weight if self.more else 1 / weight

        def reweigh(mod: Mod) -> Fraction:
            return factor if held.intersection(mod.families) else Fraction(1)

        retained = retained_item(data, item)
        total = max(len(item.mods), NEVER_FEWER_MODS.value["floor"])
        return Outcomes(data, retained, build_pool(data, retained, factor=reweigh), {total: Fraction(1)}, None)


@kind(
    "harvest-reforge-likelihood",
    order=22,
    planner=False,
    why_not="reads every junk family, so a state is a set of family types and every kernel has all-distinct weights; not in the B1 offer set until pruning (#118) decides",
)
def _harvest_reforge_likelihood(data: GameData, item: Item):
    for key in LIKELIHOOD_REFORGES_EXIST.value:
        yield HarvestReforgeLikelihood(more=key == "more")
