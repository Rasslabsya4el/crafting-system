"""Prefix and suffix capacity by rarity, read from the rules registry, and how the slots fill up."""

import dataclasses

import pytest
from items_support import AMULET, BODY, DATA, item, roll
from repoe_support import no_network  # noqa: F401

from crafting_system.items import Capacity, CapacityError, Item, Rarity, Side, capacity
from crafting_system.items import model
from crafting_system.rules import get_rule
from crafting_system.rules.registry import FrozenMap

PREFIXES = ("IncreasedEnergyShield1", "LocalIncreasedEnergyShield1", "IncreasedLife1")
SUFFIXES = ("ColdResist1", "LightningResist1", "LifeRegeneration1")
FOURTH_PREFIX = "LocalAddedFireDamageTwoHand1"
FOURTH_SUFFIX = "ColdDamagePercentEssence1"


def data_with_base_class(item_class):
    base = dataclasses.replace(DATA.base_items[AMULET], item_class=item_class)
    return dataclasses.replace(DATA, base_items={**DATA.base_items, AMULET: base})


def test_the_three_numbers_come_from_the_registry_rules():
    assert get_rule("affix_count.max_per_side_by_rarity").value["rare"] == 3
    assert model.MAX_PER_SIDE_BY_RARITY is get_rule("affix_count.max_per_side_by_rarity")
    assert model.NORMAL_NO_MODS is get_rule("affix_count.normal_has_no_explicit_mods")
    assert model.RARE_JEWEL is get_rule("affix_count.rare_jewel_max_per_side")


@pytest.mark.parametrize(
    ("rarity", "expected"),
    [(Rarity.NORMAL, (0, 0)), (Rarity.MAGIC, (1, 1)), (Rarity.RARE, (3, 3))],
)
def test_capacity_by_rarity_on_an_ordinary_base(rarity, expected):
    assert capacity(DATA, BODY, rarity) == Capacity(*expected)


def test_capacity_is_read_per_side():
    assert Capacity(2, 3).of(Side.PREFIX) == 2
    assert Capacity(2, 3).of(Side.SUFFIX) == 3


@pytest.mark.parametrize("item_class", ["Jewel", "AbyssJewel"])
def test_a_rare_jewel_holds_two_per_side(item_class):
    assert capacity(data_with_base_class(item_class), AMULET, Rarity.RARE) == Capacity(2, 2)


def test_a_magic_jewel_still_holds_one_per_side():
    assert capacity(data_with_base_class("Jewel"), AMULET, Rarity.MAGIC) == Capacity(1, 1)


def test_an_item_reads_its_own_capacity():
    assert item(base_id=AMULET).capacity(DATA) == Capacity(3, 3)


def test_the_registry_values_are_what_decides(monkeypatch):
    rule = lambda name, **value: dataclasses.replace(get_rule(name), value=FrozenMap(value))  # noqa: E731
    monkeypatch.setattr(
        model, "MAX_PER_SIDE_BY_RARITY", rule("affix_count.max_per_side_by_rarity", magic=2, rare=5)
    )
    monkeypatch.setattr(
        model, "RARE_JEWEL", rule("affix_count.rare_jewel_max_per_side", rare=7, item_classes=("Amulet",))
    )

    assert capacity(DATA, BODY, Rarity.MAGIC) == Capacity(2, 2)
    assert capacity(DATA, BODY, Rarity.RARE) == Capacity(5, 5)
    assert capacity(DATA, AMULET, Rarity.RARE) == Capacity(7, 7)

    monkeypatch.setattr(model, "NORMAL_NO_MODS", rule("affix_count.normal_has_no_explicit_mods", normal=1))

    assert capacity(DATA, BODY, Rarity.NORMAL) == Capacity(1, 1)


def test_a_normal_item_with_a_mod_is_rejected():
    with pytest.raises(CapacityError, match=r"BodyInt1.*normal.*0 prefix"):
        item(roll("IncreasedLife1"), rarity=Rarity.NORMAL)


def test_a_magic_item_holds_one_prefix_and_one_suffix():
    assert len(item(roll("IncreasedLife1"), roll("ColdResist1"), rarity=Rarity.MAGIC).mods) == 2


def test_a_magic_item_with_two_prefixes_is_rejected():
    with pytest.raises(CapacityError, match=r"2 prefixes.*magic.*1"):
        item(roll("IncreasedLife1"), roll("IncreasedEnergyShield1"), rarity=Rarity.MAGIC)


def test_a_rare_holds_three_prefixes_and_three_suffixes():
    built = item(*(roll(mod) for mod in PREFIXES + SUFFIXES))

    assert len(built.mods) == 6


def test_a_fourth_prefix_is_rejected():
    with pytest.raises(CapacityError, match=r"4 prefixes.*rare.*3"):
        item(*(roll(mod) for mod in (*PREFIXES, FOURTH_PREFIX)))


def test_a_fourth_suffix_is_rejected():
    with pytest.raises(CapacityError, match=r"4 suffixes.*rare.*3"):
        item(*(roll(mod) for mod in (*SUFFIXES, FOURTH_SUFFIX)))


def test_fractured_and_crafted_mods_take_prefix_slots():
    slots = (
        roll("LocalIncreasedEnergyShield1"),
        roll("IncreasedLife1", fractured=True),
        roll("JunMaster2ArmourAndEnergyShield1", crafted=True),
    )

    assert len(item(*slots).prefixes(DATA)) == 3
    with pytest.raises(CapacityError, match="4 prefixes"):
        item(*slots, roll(FOURTH_PREFIX))


def test_a_metamod_takes_a_suffix_slot():
    slots = (
        roll("ColdResist1"),
        roll("LightningResist1"),
        roll("IntMasterItemGenerationCannotRollAttackAffixes", crafted=True),
    )

    assert len(item(*slots).suffixes(DATA)) == 3
    with pytest.raises(CapacityError, match="4 suffixes"):
        item(*slots, roll("LifeRegeneration1"))


def test_a_rare_jewel_rejects_a_third_suffix():
    jewel_data = data_with_base_class("Jewel")
    mods = tuple(roll(mod) for mod in SUFFIXES)

    with pytest.raises(CapacityError, match=r"3 suffixes.*rare.*2"):
        Item.build(jewel_data, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=mods)
    assert len(Item.build(jewel_data, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=mods[:2]).mods) == 2
