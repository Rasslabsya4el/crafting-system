"""Shared helpers for the `actions` tests: the fixture amulet at item level 86 and a few named mods."""

from fractions import Fraction

from items_support import AMULET, DATA, item, roll
from repoe_support import no_network  # noqa: F401

from crafting_system.items import Item, Rarity

TARGET = "GlobalLightningGemLevel1"
RESIST = "LightningResist1"
LEVEL = 86


def amulet(*mods, item_level: int = LEVEL, rarity: Rarity = Rarity.RARE) -> Item:
    """A rare fixture amulet of the given item level holding `mods`."""
    return item(*mods, base_id=AMULET, rarity=rarity, item_level=item_level)


def fractured_resist(mod_id: str = RESIST):
    return roll(mod_id, fractured=True)


def percent(value: Fraction) -> str:
    return f"{float(value) * 100:.4f}%"


__all__ = ["AMULET", "DATA", "LEVEL", "RESIST", "TARGET", "amulet", "fractured_resist", "percent", "roll"]
