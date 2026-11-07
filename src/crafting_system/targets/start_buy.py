"""The bought start item, described once: the buy spec, the trade query and the price key are computed from the target (#474, OR-3).

A target that buys its start item (`start: bought`) is the only description of it. `buy_spec_of(data, target)` turns the target's base,
item level, influences, start rarity and start mods into a `BuySpec`; `start_price_key(data, target)` is that spec's name, the key the
price is stored under; the trade query is `build_query` of the spec. Nothing is typed twice, so the three cannot disagree.

* **The base.** The trade `type` is the base's English name. The trade site's item list has one entry per name, and its `disc` field only
  tells legacy uniques apart (checked on 2026-11-06 against `GET /api/trade/data/items`), so `type` cannot tell bases of one name apart.
  Where the bases of a name have implicits that read differently (the three Two-Toned Boots: Cold and Lightning, Fire and Cold, Fire and
  Lightning Resistances), the query also asks for the target's base's own implicit, an `own` implicit buy mod: the base's implicit is part
  of the base, not a bought mod. Where they read alike (the two Penetrating Arrow Quivers share an implicit and a mod pool) nothing can tell
  them apart. Either way the price key says which base is meant (`Two-Toned Boots [BootsAtlas1]`), so the key is the target's base and
  never a neighbour's.
* **The category** is `TRADE_CATEGORY`, from the base's item class.
* **The item level window** runs from the target's level up to the highest level whose mod pool is the same (`floor.level_groups`): any mod
  gained anywhere in the pool changes the odds of the craft, so the whole-pool window is the exact one. A window that runs to the highest
  item level has no maximum in the query.
* **The rarity** is the start item's, as the target states it. (R08 and R09 start rare with no mods; their committed prices are of a Normal
  base plus an Alchemy typed into the sum, which the keys and the tests mark as a price for another item, #494 point 2.)
* **The start mods** are searched by their stat text, with the lowest roll of the mod's own stat range as the minimum (OR-3: the tier the
  price is taken for is the mod the target names; its window starts there), and `fractured` as the target says.
"""

import re

from crafting_system.data import BaseItem, GameData, Mod
from crafting_system.items import Rarity
from crafting_system.items.model import MAX_ITEM_LEVEL
from crafting_system.prices.price_names import canonical_influences
from crafting_system.prices.trade_query import BuyMod, BuySpec
from crafting_system.prices.trade_stats import normalize_text

from .floor import level_groups
from .model import Target

__all__ = [
    "TRADE_CATEGORY",
    "StartBuyError",
    "buy_spec_of",
    "item_level_window",
    "same_name_bases",
    "start_price_key",
]

# raw item class -> the trade site's `category` option: a fact about the trade site.
TRADE_CATEGORY = {
    "Amulet": "accessory.amulet",
    "Ring": "accessory.ring",
    "Belt": "accessory.belt",
    "Boots": "armour.boots",
    "Gloves": "armour.gloves",
    "Helmet": "armour.helmet",
    "Body Armour": "armour.chest",
    "Shield": "armour.shield",
    "Quiver": "armour.quiver",
    "Bow": "weapon.bow",
}

NOT_FOR_SALE_TAG = "not_for_sale"
ROYALE_MARKER = "Royale"
_MARKUP_LABEL = re.compile(r"\[[^\]|]*\|([^\]]*)\]")
_MARKUP = re.compile(r"\[([^\]|]*)\]")


class StartBuyError(ValueError):
    """The start item of a target cannot be turned into a buy spec; the message says why."""


def same_name_bases(data: GameData, base_id: str) -> tuple[str, ...]:
    """The ids of every base a player can hold under this base's English name, sorted, itself included.

    Released bases only, Battle Royale copies never; where a name is shared and some of its bases are on sale, the ones tagged
    `not_for_sale` are dropped (the second Leather Belt is `BeltRoyale1`); where all are tagged so, all stay.
    """
    name = data.base_items[base_id].name
    found = [
        base for base in data.base_items.values() if base.name == name and base.release_state == "released" and ROYALE_MARKER not in base.id
    ]
    on_sale = [base for base in found if NOT_FOR_SALE_TAG not in base.tags]
    ids = sorted(base.id for base in on_sale or found)
    return tuple(ids) if base_id in ids else tuple(sorted({*ids, base_id}))


def item_level_window(data: GameData, target: Target) -> tuple[int, int]:
    """(the target's item level, the highest item level whose mod pool is the same): the levels one bought base can have."""
    group = level_groups(data, target, target.item_level)[0]
    return group.lowest, group.highest


def _plain(text: str) -> str:
    return " ".join(_MARKUP.sub(r"\1", _MARKUP_LABEL.sub(r"\1", text)).split())


def _minimum(mod: Mod) -> int | float:
    """The lowest roll of the mod's one stat (the low end of its range in the data): the tier the price is taken for starts there."""
    if len(mod.stats) != 1 or mod.text is None or "\n" in mod.text:
        raise StartBuyError(f"the start mod {mod.id} has {len(mod.stats)} stat(s) or no single-line text: only a one-line, one-stat mod is searched")
    stat = mod.stats[0]
    return min(stat.min, stat.max)


def _own_implicits(data: GameData, base: BaseItem) -> list[BuyMod]:
    """The base's own implicits as buy mods when its name is shared by bases whose implicits read differently, else none.

    The trade site cannot tell bases of one name apart by `type`; an implicit it can filter on does (the three Two-Toned Boots).
    """
    others = [data.base_items[other] for other in same_name_bases(data, base.id) if other != base.id]
    if not others:
        return []

    def reads(item: BaseItem) -> frozenset[str]:
        return frozenset(normalize_text(data.mods[mod_id].text or "") for mod_id in item.implicits)

    if all(reads(other) == reads(base) for other in others):
        return []
    return [BuyMod(_plain(data.mods[mod_id].text or ""), implicit=True, own=True) for mod_id in base.implicits if data.mods[mod_id].text]


def _base_label(data: GameData, base: BaseItem) -> str:
    if len(same_name_bases(data, base.id)) == 1:
        return base.name
    return f"{base.name} [{base.id.rsplit('/', 1)[-1]}]"


def buy_spec_of(data: GameData, target: Target) -> BuySpec:
    """The buy spec of the target's start item: what to search the trade site for, named by its price key.

    Raises `StartBuyError` when a part of the item cannot be searched: an item class with no trade category, a crafted start mod, a mod
    of several stats.
    """
    item = target.start_item
    base = data.base_items[target.base_id]
    category = TRADE_CATEGORY.get(base.item_class)
    if category is None:
        raise StartBuyError(f"no trade category is known for the item class {base.item_class!r} (base {base.name}): add it to TRADE_CATEGORY")
    low, high = item_level_window(data, target)
    rarity = item.rarity
    influences = canonical_influences(influence.value for influence in item.influences)
    mods = []
    for entry in item.mods:
        if entry.crafted:
            raise StartBuyError(f"the start mod {entry.mod_id} is crafted: a crafted mod is not bought on the trade site")
        mod = data.mods[entry.mod_id]
        mods.append((BuyMod(_plain(mod.text or ""), _minimum(mod), entry.fractured), _plain(mod.text or "")))
    return BuySpec(
        name=_key(_base_label(data, base), rarity, low, high, influences, [(buy.fractured, shown) for buy, shown in mods]),
        base_type=base.name,
        category=category,
        rarity=rarity.value,
        item_level_min=low,
        item_level_max=None if high >= MAX_ITEM_LEVEL else high,
        influences=tuple(name.lower() for name in influences),
        corrupted=item.corrupted,
        mods=(*(buy for buy, _ in mods), *_own_implicits(data, base)),
    )


def _key(base: str, rarity: Rarity, low: int, high: int, influences: tuple[str, ...], mods: list[tuple[bool, str]]) -> str:
    """The price key, readable as the item: `Amethyst Ring, item level 75-83, fractured +(13-15) to all Attributes`."""
    parts = [base]
    if rarity is not Rarity.RARE:
        parts.append(rarity.value)
    parts.append(f"item level {low}" if low == high else f"item level {low}-{high}")
    if influences:
        parts.append("/".join(influences) + " influence")
    parts.extend(f"{'fractured ' if fractured else ''}{shown}" for fractured, shown in mods)
    return ", ".join(parts)


def start_price_key(data: GameData, target: Target) -> str:
    """The name the target's start item has in the price file: the name of its buy spec."""
    return buy_spec_of(data, target).name
