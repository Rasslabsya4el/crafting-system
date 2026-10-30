"""Shared helpers for the `items` tests: a mod rolled at its lowest values, and a body armour builder."""

from repoe_support import fixture_game_data

from crafting_system.items import ExplicitMod, Item, Rarity

DATA = fixture_game_data()

BODY = "Metadata/Items/Armours/BodyArmours/BodyInt1"
AMULET = "Metadata/Items/Amulets/Amulet1"


def roll(mod_id: str, *, tier: int = 1, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    """The mod `mod_id` with every stat rolled at the low end of its range."""
    mod = DATA.mods[mod_id]
    values = tuple(min(stat.min, stat.max) for stat in mod.stats)
    return ExplicitMod(mod_id, tier, values, fractured=fractured, crafted=crafted)


def item(*mods: ExplicitMod, base_id: str = BODY, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    """A validated item on `base_id` (default: a body armour) at item level 84."""
    fields.setdefault("item_level", 84)
    return Item.build(DATA, base_id=base_id, rarity=rarity, mods=mods, **fields)
