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
* **The key** is the one place a price name of a start item is made (#471). It carries what tells two start items apart for buying: the base
  (the base id too, where the name is shared), the rarity, the item level window, the influences and the corruption, then the start mods.
  Two targets that differ in any of these read two price entries. `base_line_name` is the other name made here: the poe.ninja-style line
  of a Normal base (`Lion Pelt (ilvl 84)`) that a vendor recipe buys, with the base id in it where the name is shared.
* **A poe.ninja price for a shared name is refused when the bases differ** (`shared_name_refusal`): its line has a name, a level and a variant,
  no base id, so for a name whose bases differ in item class, implicit mods or mod tags it is the price of none of them. Bases that agree in
  all three are one item to a crafter and the line prices any of them (R04's two Penetrating Arrow Quivers). The trade site has no discriminator either (checked on
  2026-11-07 against `GET /api/trade/data/items`: one plain entry per base name, and `disc` only on legacy uniques), so the own implicit above is
  all the query can use.
* **The start mods** are searched by their stat text, with the lowest roll of the mod's own stat range as the minimum (OR-3: the tier the
  price is taken for is the mod the target names; its window starts there), and `fractured` as the target says.
"""

import re

from crafting_system.data import BaseItem, GameData, Mod
from crafting_system.items import Rarity
from crafting_system.items.model import MAX_ITEM_LEVEL
from crafting_system.prices.poe_ninja import SOURCE as NINJA_SOURCE
from crafting_system.prices.poe_watch import SOURCE as WATCH_SOURCE
from crafting_system.prices.price_names import base_price_name, canonical_influences
from crafting_system.prices.trade_query import BuyMod, BuySpec
from crafting_system.prices.trade_stats import normalize_text

from .floor import level_groups
from .model import Target

__all__ = [
    "TRADE_CATEGORY",
    "StartBuyError",
    "base_in_words",
    "base_line_name",
    "buy_spec_of",
    "ninja_line_name",
    "is_name_only_source",
    "plain_base_names",
    "item_level_window",
    "same_name_bases",
    "shared_name_refusal",
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
        name=_key(_base_label(data, base), rarity, low, high, influences, item.corrupted, [(buy.fractured, shown) for buy, shown in mods]),
        base_type=base.name,
        category=category,
        rarity=rarity.value,
        item_level_min=low,
        item_level_max=None if high >= MAX_ITEM_LEVEL else high,
        influences=tuple(name.lower() for name in influences),
        corrupted=item.corrupted,
        mods=(*(buy for buy, _ in mods), *_own_implicits(data, base)),
    )


def _key(
    base: str, rarity: Rarity, low: int, high: int, influences: tuple[str, ...], corrupted: bool, mods: list[tuple[bool, str]]
) -> str:
    """The price key, readable as the item: `Amethyst Ring, item level 75-83, corrupted, fractured +(13-15) to all Attributes`."""
    parts = [base]
    if rarity is not Rarity.RARE:
        parts.append(rarity.value)
    parts.append(f"item level {low}" if low == high else f"item level {low}-{high}")
    if influences:
        parts.append("/".join(influences) + " influence")
    if corrupted:
        parts.append("corrupted")
    parts.extend(f"{'fractured ' if fractured else ''}{shown}" for fractured, shown in mods)
    return ", ".join(parts)


def start_price_key(data: GameData, target: Target) -> str:
    """The name the target's start item has in the price file: the name of its buy spec."""
    return buy_spec_of(data, target).name


def base_line_name(data: GameData, target: Target) -> str:
    """The price name of the target's Normal base at its item level and influences: `Lion Pelt (ilvl 84)`.

    A vendor recipe buys this base and makes the start item from it (`cli/_start_options.py`). The base is named like the start item's base
    in its key: where the name is shared, the base id is in it (`Two-Toned Boots [BootsAtlas1] (ilvl 86)`), so a price of this name is the price of
    this base.
    """
    return base_price_name(_base_label(data, data.base_items[target.base_id]), target.item_level, [each.value for each in target.influences])


def ninja_line_name(data: GameData, target: Target) -> str:
    """The name a poe.ninja stash line of the target's Normal base has (`Two-Toned Boots (ilvl 86)`): the base's name, level and variant, no base id.

    It is the same as `base_line_name` where the name is not shared. Where it is, a price of this name is refused (`shared_name_refusal`).
    """
    return base_price_name(data.base_items[target.base_id].name, target.item_level, [each.value for each in target.influences])


def is_name_only_source(source: str) -> bool:
    """True for a price source whose line has a name, a level and a variant and no base id (poe.ninja, poe.watch)."""
    return source.startswith((NINJA_SOURCE, WATCH_SOURCE))


def _pool_tags(data: GameData) -> frozenset[str]:
    """Every tag some mod's spawn or generation weights read: the tags of a base that can change its mod pool."""
    return frozenset(weight.tag for mod in data.mods.values() for weight in (*mod.spawn_weights, *mod.generation_weights))


def differences_between_same_name_bases(data: GameData, base_id: str) -> tuple[str, ...]:
    """In what the bases that share this base's name differ for a crafter: any of "item class", "implicit mods", "mod tags".

    Read from the export, the same data the planner reads. The implicit mods are compared by what they read and roll (their text and the
    range of each stat), not by id: a base re-released under a new id keeps its implicit. The mod tags are the base's tags that some mod's
    weights read (`_pool_tags`): a tag no mod reads, like `trade_market_legacy_item`, changes no mod pool. Empty when they all agree.
    """
    bases = [data.base_items[each] for each in same_name_bases(data, base_id)]
    pool_tags = _pool_tags(data)

    def implicits(item: BaseItem) -> frozenset[tuple[str, tuple[tuple[str, int, int], ...]]]:
        mods = [data.mods[mod_id] for mod_id in item.implicits]
        return frozenset((normalize_text(mod.text or ""), tuple((stat.id, stat.min, stat.max) for stat in mod.stats)) for mod in mods)

    differing = []
    if len({each.item_class for each in bases}) > 1:
        differing.append("item class")
    if len({implicits(each) for each in bases}) > 1:
        differing.append("implicit mods")
    if len({frozenset(each.tags) & pool_tags for each in bases}) > 1:
        differing.append("mod tags")
    return tuple(differing)


def base_in_words(data: GameData, base_id: str) -> str:
    """What tells this base from the other bases that share its name, in words (#553, #481); empty where the name is not shared.

    The item class where it differs, then the implicit it holds, then a different pool of mods; where the bases agree in all three they
    are one item to a crafter (`shared_name_refusal`) and the words say that. Never the base id: that is for the price key and the JSON.
    """
    ids = same_name_bases(data, base_id)
    if len(ids) < 2:
        return ""
    base = data.base_items[base_id]
    differing = differences_between_same_name_bases(data, base_id)
    parts = []
    if "item class" in differing:
        parts.append(f"{'an' if base.item_class[0] in 'AEIOU' else 'a'} {base.item_class.lower()}")
    if "implicit mods" in differing:
        texts = [_plain(data.mods[mod_id].text or "") for mod_id in base.implicits if data.mods[mod_id].text]
        parts.append(f"the implicit {' and '.join(texts)}" if texts else "no implicit")
    if "mod tags" in differing:
        parts.append("a different pool of mods")
    return ", ".join(parts) if parts else f"one of {len(ids)} bases of this name that play alike"


_BASE_ID_IN_BRACKETS = re.compile(r" \[([A-Za-z][A-Za-z0-9_]*)\]")


def plain_base_names(data: GameData, text: str) -> str:
    """`text` with each base id in brackets (the form of a price key, `Two-Toned Boots [BootsAtlas1] (ilvl 86)`) said in words.

    The page names a base by its game name; where two bases share the name the words of `base_in_words` follow it in parentheses. A
    bracket that is not the tail of a base id is left as it is.
    """

    def said(found: re.Match[str]) -> str:
        ids = [each for each in data.base_items if each.rsplit("/", 1)[-1] == found.group(1)]
        words = base_in_words(data, ids[0]) if len(ids) == 1 else ""
        return f" ({words})" if words else ""

    return _BASE_ID_IN_BRACKETS.sub(said, text)


def shared_name_refusal(data: GameData, base_id: str, source: str, what: str) -> str | None:
    """The words that refuse a price, or None when the price may be used.

    A poe.ninja line has a name, a level and a variant, no base id (poe.watch's base lines are matched by name and level the same way). Where
    the name belongs to several bases that agree in item class, implicit mods and mod tags, they are one item to a crafter and the line
    prices any of them. Where they differ in one of these the line is the price of none of them, and `what` (the start item or the base
    line the price is for) is not priced by it. Prices from every other source are kept.
    """
    if not is_name_only_source(source):
        return None
    ids = same_name_bases(data, base_id)
    if len(ids) < 2:
        return None
    differing = differences_between_same_name_bases(data, base_id)
    if not differing:
        return None
    shown = ", ".join(each.rsplit("/", 1)[-1] for each in ids)
    return (
        f"the price of {what} is refused: it comes from {source}, whose line has a name and no base id, and the name "
        f"'{data.base_items[base_id].name}' belongs to {len(ids)} bases ({shown}) that differ in {' and '.join(differing)}, "
        "so the line is the price of none of them. Price this base on the trade site, or write its price by hand"
    )
