"""Ids and mods of the Awakener's Orb tests (ticket #213): influence mods that the contract suite's fixture pool lacks.

The mods are copies of two fixture mods with their own ids, families and spawn weights on the amulet's influence tags. None
is drawn on an item of one influence only, so they join the fixture data (`contract_fixtures_awakener.py`) without changing a pool
of any other test. The Shaper prefix `ContractShaperPrefix1` is the contract suite's own (`contract_support.SHAPER_PREFIX`).
"""

import dataclasses

from abstraction_pool import DAMAGE_1, MANA_1
from items_support import DATA

from crafting_system.data import Weight

SHAPER_PREFIX = "ContractShaperPrefix1"
SHAPER_SUFFIX = "ContractShaperSuffix1"
CRUSADER_SUFFIX = "ContractCrusaderSuffix1"
CRUSADER_CLASH = "ContractCrusaderClash1"  # a Crusader prefix of the family of SHAPER_PREFIX: the two meet in a group conflict


def awakener_mods() -> dict:
    """A second Shaper mod (a suffix of a family of its own), a Crusader suffix of a family of its own, and the clashing Crusader prefix."""
    mana, damage = DATA.mods[MANA_1], DATA.mods[DAMAGE_1]
    return {
        SHAPER_SUFFIX: dataclasses.replace(
            mana, id=SHAPER_SUFFIX, type=SHAPER_SUFFIX, families=(SHAPER_SUFFIX,), spawn_weights=(Weight("amulet_shaper", 500), Weight("default", 0))
        ),
        CRUSADER_SUFFIX: dataclasses.replace(
            mana, id=CRUSADER_SUFFIX, type=CRUSADER_SUFFIX, families=(CRUSADER_SUFFIX,), spawn_weights=(Weight("amulet_crusader", 400), Weight("default", 0))
        ),
        CRUSADER_CLASH: dataclasses.replace(
            damage, id=CRUSADER_CLASH, type=CRUSADER_CLASH, families=(SHAPER_PREFIX,), spawn_weights=(Weight("amulet_crusader", 300), Weight("default", 0))
        ),
    }
