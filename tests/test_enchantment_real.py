"""The enchantment rules on the real 3.29.3.3 dump (ticket #236): the pool sizes, the 14 quality enchants and the clean set of a tag.

These tests need the cached dump (`CRAFTING_CACHE_DIR`); they skip cleanly when it is not there and run in CI (ticket #165).
The counts are the research of ticket #100 (`docs/research/2026-10-31-enchantments-pools.py`) and ADR-0051.
"""

import collections

import pytest
from abstraction_support import real_game_data

from crafting_system.items import EnchantClass, EnchantKind, Item, Rarity, enchant_info
from crafting_system.targets import parse_target

ARMOUR_BASE = "Metadata/Items/Armours/BodyArmours/BodyStr1"
SWORD_BASE = "Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1"
EXTRA_SLOT_TEXT = "Can have 1 additional Crafted Modifier"
REQUIREMENT = '  - stat: "+# to maximum Life"\n'


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.fixture(scope="module")
def counts(real):
    found = collections.Counter()
    for mod in real.mods.values():
        info = enchant_info(mod)
        if info is not None:
            found[(info.kind, info.item_class)] += 1
    return found


def target(real, base: str, text: str):
    return parse_target(f"base: {base}\nitem_level: 84\nrequirements:\n{REQUIREMENT}{text}", real, source="t.yaml")


def test_the_pools_have_136_weapon_and_54_body_armour_enchants_and_14_quality_enchants(counts):
    assert counts[(EnchantKind.POOL, EnchantClass.WEAPON)] == 136
    assert counts[(EnchantKind.POOL, EnchantClass.BODY_ARMOUR)] == 54
    assert counts[(EnchantKind.QUALITY, EnchantClass.BODY_ARMOUR)] == 8
    assert counts[(EnchantKind.QUALITY, EnchantClass.WEAPON)] == 6


def test_a_bare_life_resolves_to_the_4_clean_body_armour_enchants(real):
    wanted = target(real, ARMOUR_BASE, "enchantment:\n  any_of: [Life]\n").enchantment
    assert len(wanted.mod_ids) == 4
    infos = [enchant_info(real.mods[mod_id]) for mod_id in wanted.mod_ids]
    assert all(info.clean and "Life" in info.tags and info.item_class is EnchantClass.BODY_ARMOUR for info in infos)


def test_a_listed_hybrid_resolves_to_itself_and_a_dirty_enchant_only_by_its_own_name(real):
    hybrid = "6% increased Explicit Life Modifier magnitudes\\n6% increased Explicit Attribute Modifier magnitudes"
    wanted = target(real, ARMOUR_BASE, f'enchantment:\n  any_of: ["{hybrid}"]\n').enchantment
    assert [real.mods[mod_id].text for mod_id in wanted.mod_ids] == [hybrid.replace("\\n", "\n")]
    penalty = "ArmourEnchantmentHeistLifeEffectSocketPenalty1"
    assert target(real, ARMOUR_BASE, f"enchantment:\n  any_of: [{penalty}]\n").enchantment.mod_ids == {penalty}
    assert penalty not in target(real, ARMOUR_BASE, "enchantment:\n  any_of: [Life]\n").enchantment.mod_ids


def test_every_clean_enchant_of_every_tag_is_a_pool_enchant_without_rider_or_downside(real):
    for base, tag in ((ARMOUR_BASE, "Defence"), (ARMOUR_BASE, "Resistance"), (SWORD_BASE, "Critical"), (SWORD_BASE, "Speed")):
        wanted = target(real, base, f"enchantment:\n  any_of: [{tag}]\n").enchantment
        assert wanted.mod_ids
        for mod_id in wanted.mod_ids:
            info = enchant_info(real.mods[mod_id])
            assert info.kind is EnchantKind.POOL and info.clean
            assert not info.socket_rider and not info.downside and not info.extra_slot


def test_the_extra_crafted_slot_text_names_one_mod_per_class_and_needs_a_start_item(real):
    ids = {}
    for base in (ARMOUR_BASE, SWORD_BASE):
        start = f'start_item:\n  enchantment: "{EXTRA_SLOT_TEXT}"\n'
        wanted = target(real, base, f'enchantment:\n  any_of: ["{EXTRA_SLOT_TEXT}"]\n{start}')
        (mod_id,) = wanted.enchantment.mod_ids
        assert wanted.start_item.enchantment == mod_id
        ids[base] = mod_id
        with pytest.raises(ValueError, match="cannot be reached by clicking orbs"):
            target(real, base, f'enchantment:\n  any_of: ["{EXTRA_SLOT_TEXT}"]\n')
    assert ids[ARMOUR_BASE] != ids[SWORD_BASE]


def test_a_removed_white_socket_enchant_is_not_an_enchantment_any_more(real):
    removed = [
        mod_id
        for mod_id, mod in real.mods.items()
        if mod.families == ("EnchantmentHeistArmour",) and any(s.id == "local_has_X_white_sockets" for s in mod.stats)
    ]
    assert removed
    with pytest.raises(ValueError, match="was removed from the enchant pool in 3.29.0"):
        Item.build(real, base_id=ARMOUR_BASE, item_level=84, rarity=Rarity.RARE, enchantment=removed[0])


def test_a_quality_enchant_is_named_by_its_full_text_and_sits_on_a_body_armour(real):
    text = "Quality does not increase Defences\\nGrants +1 to Maximum Life per 2% Quality"
    wanted = target(real, ARMOUR_BASE, f'enchantment:\n  any_of: ["{text}"]\n').enchantment
    (mod_id,) = wanted.mod_ids
    assert enchant_info(real.mods[mod_id]).kind is EnchantKind.QUALITY
    assert Item.build(real, base_id=ARMOUR_BASE, item_level=84, rarity=Rarity.RARE, enchantment=mod_id).enchantment == mod_id
