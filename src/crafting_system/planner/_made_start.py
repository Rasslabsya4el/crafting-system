"""A bought dual-influenced start item made by its recipe: an Awakener's Orb on two single-influence Normal bases (ticket #1523).

A Rare item with two influences whose mods the target does not name (the market's item, ADR-0064) is what an Awakener's Orb gives from two
Normal bases of the target's base type, one of each influence (claims `awakener.two_items_same_class`,
`awakener.one_influence_each_and_different`, `awakener.receiver_reforged_rare_both_influences`): the second item is destroyed, the first keeps its
base type and item level (`awakener.keeps_base_level_sockets_quality_enchants`) and becomes Rare with both influences. A Normal base holds no
influenced mod, so none is kept (`awakener.one_influenced_mod_per_input_kept`) and every mod is rolled anew as a Chaos Orb rolls a rare, 4, 5 or 6
mods at 8:3:1 (`awakener.rest_rerolled_like_chaos`): the same law as the draw that opens a bought Rare listing (`actions.listing`, an Orb of
Alchemy's), so the plan from the made item is the plan from the bought one and only the price and the first step's words differ.

`made_start_price` prices that recipe from the price file: the two bases at the target's item level under their base lines
(`targets.base_line_name`: "Eternal Burgonet (ilvl 86, Shaper)") and one Awakener's Orb. The second item's level does not matter to the result;
it is priced at the target's level, which is never cheaper than a lower one would be. A good with no price, or with a thin market's marked price,
gives no recipe (a recipe good is not priced from a thin market, as in `_start_options._goods`). `resolve_start_price` takes the recipe when the
file has no line for the dual-influenced item, or when the recipe is cheaper than that line.
"""

import dataclasses

from crafting_system.data import GameData
from crafting_system.items import Rarity
from crafting_system.actions import unopened_listing
from crafting_system.prices import PriceFile, planned_price
from crafting_system.prices.price_names import INFLUENCES
from crafting_system.targets import StartKind, Target, base_line_name

from ._start_types import MadeStart

AWAKENERS_ORB = "Awakener's Orb"
AWAKENER_RECIPE = "awakeners_orb"
AWAKENER_CLAIMS = (
    "awakener.two_items_same_class",
    "awakener.one_influence_each_and_different",
    "awakener.receiver_reforged_rare_both_influences",
    "awakener.keeps_base_level_sockets_quality_enchants",
    "awakener.one_influenced_mod_per_input_kept",
    "awakener.rest_rerolled_like_chaos",
)


def _in_game_order(target: Target) -> tuple:
    order = {name.lower(): index for index, name in enumerate(INFLUENCES)}
    return tuple(sorted(target.influences, key=lambda each: order[each.value]))


def made_start(data: GameData, target: Target, prices: PriceFile, price_source: str) -> MadeStart | None:
    """The Awakener's Orb recipe of the target's bought start item with its priced goods, or None when it makes no such item or a good has no price.

    It applies to a bought Rare start item with exactly two influences that is the market's item (`unopened_listing`: no mod, nothing corrupted).
    """
    start = target.start_item
    if target.start is not StartKind.BOUGHT or start.rarity is not Rarity.RARE or len(target.influences) != 2:
        return None
    if unopened_listing(data, start) is None:
        return None
    receiver, donor = (base_line_name(data, dataclasses.replace(target, influences=frozenset({each}))) for each in _in_game_order(target))
    goods = []
    for name in (receiver, donor, AWAKENERS_ORB):
        planned = planned_price(prices, name, price_source)
        if planned is None or planned.mark is not None:
            return None
        goods.append((name, 1, planned.chaos, planned.source))
    return MadeStart(AWAKENER_RECIPE, AWAKENERS_ORB, tuple(goods), receiver, donor, AWAKENER_CLAIMS)
