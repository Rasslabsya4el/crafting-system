"""Shared helpers for the `items` tests: a mod rolled at its lowest values, and a body armour builder."""

import dataclasses

from repoe_support import fixture_game_data

from crafting_system.data.model import BaseItem, GameData
from crafting_system.items import ExplicitMod, Item, Rarity

# the names of the currencies the fixture's bench costs name: the excerpt holds no currency base item
CURRENCY_NAMES = {
    "CurrencyRerollRare": "Chaos Orb",
    "CurrencyAddModToRare": "Exalted Orb",
    "CurrencyRerollMagic": "Orb of Alteration",
    "CurrencyModValues": "Divine Orb",
    "CurrencyConvertToNormal": "Orb of Scouring",
    "CurrencyUpgradeToRare": "Regal Orb",
    "CurrencyUpgradeRandomly": "Orb of Chance",
    "CurrencyInstillingOrb": "Instilling Orb",
    "CurrencyFlaskQuality": "Glassblower's Bauble",
    "CurrencyRerollSocketColours": "Chromatic Orb",
    "CurrencyRerollSocketLinks": "Orb of Fusing",
    "CurrencyRerollSocketNumbers": "Jeweller's Orb",
}


def with_bench_currencies(data: GameData) -> GameData:
    """`data` with a currency base item for every currency its bench costs name, so every bench craft can be priced (#886: the planner
    offers blocking and filler crafts by default, so a toy world's crafts are priced whether or not its goal names them)."""
    bases = dict(data.base_items)
    for option in data.bench_options:
        for entry in option.cost:
            key = entry.item_id.rsplit("/", 1)[-1]
            bases.setdefault(entry.item_id, BaseItem(entry.item_id, CURRENCY_NAMES.get(key, key), "StackableCurrency", "currency", 1, (), (), "released"))
    return dataclasses.replace(data, base_items=bases)


DATA = with_bench_currencies(fixture_game_data())

BODY = "Metadata/Items/Armours/BodyArmours/BodyInt1"
AMULET = "Metadata/Items/Amulets/Amulet1"


def roll(mod_id: str, *, tier: int = 1, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    """The mod `mod_id` with every stat rolled at the low end of its range."""
    mod = DATA.mods[mod_id]
    values = tuple(min(stat.min, stat.max) for stat in mod.stats)
    return ExplicitMod(mod_id, values, fractured=fractured, crafted=crafted)


def item(*mods: ExplicitMod, base_id: str = BODY, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    """A validated item on `base_id` (default: a body armour) at item level 84."""
    fields.setdefault("item_level", 84)
    return Item.build(DATA, base_id=base_id, rarity=rarity, mods=mods, **fields)
