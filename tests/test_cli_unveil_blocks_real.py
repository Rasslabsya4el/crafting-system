"""Unveil blocks: a bench craft offered because its family is in the unveiled pool of the base (ticket #146, ADR-0026).

A craft whose mod counts toward no requirement is left out (`offers_for`), unless the target is unveiling: then a craft of a family
that the unveiled pool of the base can offer is a block (the family leaves the next offer), and it is offered. These run on the real
3.29.3.3 dump and skip without it (CI has it).
"""

import pytest
from abstraction_support import real_game_data
from limits_support import labels_of

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import unveil_pool_families
from crafting_system.cli import offers_for
from crafting_system.items import Item, Rarity

BOOTS = "Metadata/Items/Armours/Boots/BootsDexInt9"  # Murder Boots, R24's base
WAND = "Metadata/Items/Weapons/OneHandWeapons/Wands/WandAtlas1"  # Convoking Wand, R07's base
MS_ONSLAUGHT = "JunMasterVeiledMovementVelocityAndOnslaughtOnKill"
LIFE_CRAFT = "Bench craft +(15-25) to maximum Life"  # IncreasedLife: the boots' unveiled pool holds it (Life and Regeneration)
FIRE_CRAFT = "Bench craft +(16-20)% to Fire Resistance"  # FireResistance: no unveiled mod of that family spawns on boots
VEILED = ["veiled-chaos-orb", "unveil", "pick", "bench-craft"]


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def boots(data) -> Item:
    return Item.build(data, base_id=BOOTS, item_level=86, rarity=Rarity.RARE, mods=())


def goal() -> Goal:
    return Goal((Wanted(frozenset({MS_ONSLAUGHT})),))


def labels(offer_set) -> set[str]:
    return {offer.label for offer in offer_set.offers}


def test_the_unveiled_pool_families_of_the_boots_are_those_with_weight_on_the_base(data):
    families = unveil_pool_families(data, BOOTS)
    assert {"IncreasedLife", "IncreasedMana", "MovementVelocity", "Dexterity", "Intelligence"} <= families
    assert "FireResistance" not in families
    # the Trigger of R07 has weight 0 on every base (claim unveil.legacy_mods_have_weight_zero): no craft blocks it on the wand
    assert "SupportedByTrigger" not in unveil_pool_families(data, WAND)
    assert "MinionAttackSpeedAndCastSpeed" in unveil_pool_families(data, WAND)


def test_a_craft_of_a_family_in_the_unveiled_pool_is_offered_as_a_block_when_the_target_unveils(data):
    found = offers_for(data, goal(), BOOTS, boots(data), VEILED)
    assert LIFE_CRAFT in labels(found)
    assert FIRE_CRAFT not in labels(found)
    assert FIRE_CRAFT in labels_of(found.limits, "crafts")  # still left out, and said so
    assert LIFE_CRAFT not in labels_of(found.limits, "crafts")


def test_without_the_unveil_no_craft_is_a_block(data):
    found = offers_for(data, goal(), BOOTS, boots(data), ["veiled-chaos-orb", "bench-craft"])
    assert LIFE_CRAFT not in labels(found)
    assert LIFE_CRAFT in labels_of(found.limits, "crafts")
