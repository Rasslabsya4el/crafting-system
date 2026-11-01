"""The Harvest quality enchants on the real 3.29.3.3 dump (ticket #240): the 14 mods are the 14 priced ones, and each works on its class.

These tests need the cached dump (`CRAFTING_CACHE_DIR`); they skip cleanly when it is not there and run in CI (ticket #165).
"""

from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import HarvestQualityEnchant, NotApplicableError, kinds
from crafting_system.items import EnchantClass, EnchantKind, Item, Rarity, enchant_info
from crafting_system.rules import get_rule

ARMOUR_BASE = "Metadata/Items/Armours/BodyArmours/BodyStr1"
SWORD_BASE = "Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1"
BOOTS_BASE = "Metadata/Items/Armours/Boots/BootsStr1"
COSTS = get_rule("enchantment.harvest_quality_enchant_costs").value


@pytest.fixture(scope="module")
def real():
    return real_game_data()


def build(real, base: str, **fields) -> Item:
    return Item.build(real, base_id=base, item_level=84, rarity=Rarity.RARE, mods=(), **fields)


def test_the_priced_enchants_are_exactly_the_14_quality_mods_of_the_dump(real):
    found = {mod.id: enchant_info(mod) for mod in real.mods.values() if enchant_info(mod) and enchant_info(mod).kind is EnchantKind.QUALITY}

    assert set(COSTS) == set(found) and len(found) == 14
    for mod_id, info in found.items():
        total = sum(COSTS[mod_id].values())
        assert total == (3250 if info.item_class is EnchantClass.BODY_ARMOUR else 5000), mod_id
        assert len(COSTS[mod_id]) == 1 and all("Crystallised Lifeforce" in name for name in COSTS[mod_id])  # no Sacred or Rancour


def test_each_enchant_is_listed_for_its_class_and_sets_the_enchantment(real):
    armour, sword = build(real, ARMOUR_BASE), build(real, SWORD_BASE)
    (entry,) = [kind for kind in kinds() if kind.name == "harvest-quality-enchant"]

    listed_armour, listed_sword = list(entry.members(real, armour)), list(entry.members(real, sword))
    assert len(listed_armour) == 8 and len(listed_sword) == 6
    for action, item in [(action, armour) for action in listed_armour] + [(action, sword) for action in listed_sword]:
        ((chance, result),) = action.outcomes(real, item).results
        assert chance == Fraction(1) and result.enchantment == action.mod_id
        assert result == item.changed(real, enchantment=action.mod_id)  # nothing but the enchantment changes


def test_the_class_and_the_corruption_are_refused_on_the_real_bases(real):
    armour_enchant = next(HarvestQualityEnchant(mod_id) for mod_id in sorted(COSTS) if "Armour" in mod_id)
    weapon_enchant = next(HarvestQualityEnchant(mod_id) for mod_id in sorted(COSTS) if "Weapon" in mod_id)

    for action, item in [(armour_enchant, build(real, SWORD_BASE)), (weapon_enchant, build(real, ARMOUR_BASE)), (armour_enchant, build(real, BOOTS_BASE))]:
        with pytest.raises(NotApplicableError):
            action.outcomes(real, item)
    with pytest.raises(NotApplicableError, match="corrupted"):
        armour_enchant.outcomes(real, build(real, ARMOUR_BASE, corrupted=True))
