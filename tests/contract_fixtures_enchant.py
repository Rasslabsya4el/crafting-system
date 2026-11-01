"""The Tempering and Tailoring Orbs' part of the contract suite's fixture (ticket #239): a body armour and a sword of the enchant data.

The amulet of the fixture holds no enchantment, so the two kinds have nothing to do on it (they declare `applies_only_to`). Their items are
on a base of their own, in the contract data plus the real-shaped slice of the enchant pools (`enchant_support.SLICE`): a rare body armour
that holds an enchantment already (a click replaces it), a normal one, a rare sword and a magic one. Each is asked about its own kind only.
"""

import dataclasses
import functools

from contract_registry import register_extra_item
from enchant_support import BODY, LIFE, SLICE, SWORD, WEAPON_CRITICAL

from crafting_system.items import Rarity


@functools.cache
def enchant_contract_data():
    from contract_support import CONTRACT_DATA  # late: contract_support loads this module while it builds CONTRACT_DATA

    return dataclasses.replace(CONTRACT_DATA, mods={**CONTRACT_DATA.mods, **{mod.id: mod for mod in SLICE}})


def _item(base_id: str, rarity: Rarity, mods: tuple[str, ...], enchantment: str | None = None):
    from contract_support import _roll  # late, as above
    from crafting_system.items import Item

    return Item.build(
        enchant_contract_data(), base_id=base_id, item_level=84, rarity=rarity, mods=tuple(_roll(mod) for mod in mods), enchantment=enchantment
    )


register_extra_item(
    "body_armour_enchanted", ("tailoring",), enchant_contract_data, lambda: _item(BODY, Rarity.RARE, ("LightningResist2", "IncreasedLife1"), LIFE)
)
register_extra_item("body_armour_normal", ("tailoring",), enchant_contract_data, lambda: _item(BODY, Rarity.NORMAL, ()))
register_extra_item("sword_rare", ("tempering",), enchant_contract_data, lambda: _item(SWORD, Rarity.RARE, ("IncreasedLife1",)))
register_extra_item(
    "sword_magic_enchanted", ("tempering",), enchant_contract_data, lambda: _item(SWORD, Rarity.MAGIC, ("IncreasedLife1",), WEAPON_CRITICAL)
)
