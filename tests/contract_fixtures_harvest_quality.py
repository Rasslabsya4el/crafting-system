"""The Harvest quality enchants' part of the contract suite's fixture (ticket #240): a body armour and a sword.

The amulet of the fixture holds no enchantment, so the quality enchants have nothing to do on it. Each item is for the kind named with it
and no other: the body armour and the sword live in the contract data with the 14 quality mods added. The sword already holds a quality
enchant, so the suite also meets the replacement.
"""

import functools

from contract_registry import register_extra_item
from harvest_quality_support import ACCURACY, body_armour, quality_data, sword


@functools.cache
def contract_quality_data():
    from contract_support import CONTRACT_DATA  # late: contract_support loads this module while it builds CONTRACT_DATA

    return quality_data(CONTRACT_DATA)


KIND = ("harvest-quality-enchant",)
register_extra_item("body_armour_quality", KIND, contract_quality_data, lambda: body_armour(contract_quality_data()))
register_extra_item("sword_quality", KIND, contract_quality_data, lambda: sword(contract_quality_data(), enchantment=ACCURACY))
