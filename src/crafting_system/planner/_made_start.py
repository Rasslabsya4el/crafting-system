"""A bought dual-influenced start item made by its recipe: an Awakener's Orb on two single-influence Rare items (ticket #1523).

A Rare item with two influences whose mods the target does not name (the market's item, ADR-0064) is what an Awakener's Orb gives from two
items of the target's base type, one of each influence (claims `awakener.two_items_same_class`, `awakener.one_influence_each_and_different`,
`awakener.receiver_reforged_rare_both_influences`): the second item is destroyed, the first keeps its base type and item level
(`awakener.keeps_base_level_sockets_quality_enchants`) and becomes Rare with both influences. The orb is refused on a Normal item and on an item
that holds no influenced mod (`awakener.refused_without_influenced_mods`, ADR-0032, `actions.awakener`), so each input is a Rare item of its one
influence that holds at least one influenced mod, any. One influenced mod of each is kept (`awakener.one_influenced_mod_per_input_kept`) and the
rest is rolled anew as a Chaos Orb rolls a rare (`awakener.rest_rerolled_like_chaos`, the kept mods inside the 4 to 6). The plan reads the made
item as the bought Rare listing (`actions.listing`, an Orb of Alchemy's roll), without the two kept mods: the page's step says so.

`made_start` prices that recipe from the price file: the two items at the target's item level under `input_line_name` ("Eternal Burgonet (ilvl 86,
Shaper), Rare with a Shaper mod") and one Awakener's Orb. The second item's level does not matter to the result beyond the orb's 68; it is priced
at the target's level. A good with no price, or with a thin market's marked price, gives no recipe (a recipe good is not priced from a thin market,
as in `_start_options._goods`). `resolve_start_price` takes the recipe when the file has no line for the dual-influenced item, or when the recipe
is cheaper than that line.
"""

import dataclasses

from crafting_system.data import GameData
from crafting_system.items import Influence, Rarity
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
    "awakener.refused_without_influenced_mods",
    "awakener.one_influenced_mod_per_input_kept",
    "awakener.rest_rerolled_like_chaos",
)


def _in_game_order(target: Target) -> tuple[Influence, ...]:
    order = {name.lower(): index for index, name in enumerate(INFLUENCES)}
    return tuple(sorted(target.influences, key=lambda each: order[each.value]))


def input_line_name(data: GameData, target: Target, influence: Influence) -> str:
    """The price name of one input of the recipe: a Rare item of the target's base and item level, of `influence` alone, holding an influenced mod."""
    word = influence.value.capitalize()
    article = "an" if word[0] in "AEIOU" else "a"
    return f"{base_line_name(data, dataclasses.replace(target, influences=frozenset({influence})))}, Rare with {article} {word} mod"


def made_start(data: GameData, target: Target, prices: PriceFile, price_source: str) -> MadeStart | None:
    """The Awakener's Orb recipe of the target's bought start item with its priced goods, or None when it makes no such item or a good has no price.

    It applies to a bought Rare start item with exactly two influences that is the market's item (`unopened_listing`: no mod, nothing corrupted).
    """
    start = target.start_item
    if target.start is not StartKind.BOUGHT or start.rarity is not Rarity.RARE or len(target.influences) != 2:
        return None
    if unopened_listing(data, start) is None:
        return None
    receiver, donor = (input_line_name(data, target, each) for each in _in_game_order(target))
    goods = []
    for name in (receiver, donor, AWAKENERS_ORB):
        planned = planned_price(prices, name, price_source)
        if planned is None or planned.mark is not None:
            return None
        goods.append((name, 1, planned.chaos, planned.source))
    return MadeStart(AWAKENER_RECIPE, AWAKENERS_ORB, tuple(goods), receiver, donor, AWAKENER_CLAIMS)
