"""Validating an item against the game data: base, mod ids, slots, domains and rolled values."""

import dataclasses

import pytest
from items_support import AMULET, BODY, DATA, item, roll
from repoe_support import no_network  # noqa: F401

from crafting_system.items import (
    ExplicitMod,
    Item,
    ModSlotError,
    Rarity,
    UnknownBaseError,
    UnknownModError,
    ValueRangeError,
)


def test_a_valid_item_builds():
    built = item(roll("IncreasedEnergyShield1"), roll("ColdResist1"))

    assert [mod.mod_id for mod in built.mods] == ["ColdResist1", "IncreasedEnergyShield1"]


def test_an_unknown_base_is_rejected():
    with pytest.raises(UnknownBaseError, match="Metadata/Nope.*not in the game data"):
        item(base_id="Metadata/Nope")


def test_an_unknown_mod_id_is_rejected():
    with pytest.raises(UnknownModError, match=r"BodyInt1.*NoSuchMod.*not in the game data"):
        item(ExplicitMod("NoSuchMod", 1, (1,)))


def test_a_mod_that_is_neither_prefix_nor_suffix_is_rejected():
    with pytest.raises(ModSlotError, match=r"AccuracyPercentImplicitSword1.*unique.*prefix or suffix"):
        item(roll("AccuracyPercentImplicitSword1"))


def test_a_flask_enchantment_is_rejected():
    with pytest.raises(ModSlotError, match="FlaskEnchantmentInjectorAdjacentFlasks___.*prefix or suffix"):
        item(roll("FlaskEnchantmentInjectorAdjacentFlasks___"))


def test_a_mod_of_another_domain_is_rejected():
    monster = dataclasses.replace(DATA.mods["ColdResist1"], domain="monster")
    data = dataclasses.replace(DATA, mods={**DATA.mods, "ColdResist1": monster})

    with pytest.raises(ModSlotError, match=r"ColdResist1.*domain monster.*domain item"):
        Item.build(data, base_id=BODY, item_level=84, rarity=Rarity.RARE, mods=(roll("ColdResist1"),))


@pytest.mark.parametrize(
    ("mod_id", "crafted"),
    [("JunMaster2ArmourAndEnergyShield1", True), ("DelveStrengthGemLevel1", False)],
)
def test_crafted_and_delve_domains_are_allowed_on_an_item_base(mod_id, crafted):
    assert item(roll(mod_id, crafted=crafted)).mods[0].mod_id == mod_id


def test_a_crafted_mod_without_the_crafted_flag_is_rejected():
    with pytest.raises(ModSlotError, match=r"JunMaster2ArmourAndEnergyShield1.*crafted domain.*not flagged"):
        item(roll("JunMaster2ArmourAndEnergyShield1"))


def test_the_crafted_flag_on_a_natural_mod_is_rejected():
    with pytest.raises(ModSlotError, match=r"ColdResist1.*flagged crafted.*domain item"):
        item(roll("ColdResist1", crafted=True))


def test_the_wrong_number_of_values_is_rejected():
    two_stats = ExplicitMod("LocalAddedFireDamageTwoHand1", 1, (3,))

    with pytest.raises(ValueRangeError, match=r"LocalAddedFireDamageTwoHand1.*1 rolled value.*2 stat"):
        item(two_stats)


@pytest.mark.parametrize("value", [6, 11])
def test_the_edge_values_of_a_range_are_accepted(value):
    assert item(ExplicitMod("ColdResist1", 1, (value,))).mods[0].values == (value,)


@pytest.mark.parametrize("value", [5, 12])
def test_a_value_outside_its_range_is_rejected(value):
    with pytest.raises(ValueRangeError, match=rf"ColdResist1.*value {value}.*6 to 11"):
        item(ExplicitMod("ColdResist1", 1, (value,)))


def test_a_range_given_high_to_low_still_works():
    flipped = dataclasses.replace(
        DATA.mods["ColdResist1"], stats=(dataclasses.replace(DATA.mods["ColdResist1"].stats[0], min=11, max=6),)
    )
    data = dataclasses.replace(DATA, mods={**DATA.mods, "ColdResist1": flipped})

    built = Item.build(
        data, base_id=BODY, item_level=84, rarity=Rarity.RARE, mods=(ExplicitMod("ColdResist1", 1, (8,)),)
    )

    assert built.mods[0].values == (8,)


def test_the_first_failing_check_is_the_one_raised():
    bad = (ExplicitMod("NoSuchMod", 1, (1,)), ExplicitMod("ColdResist1", 1, (99,)))

    with pytest.raises(UnknownModError):
        item(*bad)


def test_an_amulet_takes_item_domain_mods():
    assert item(roll("GlobalLightningGemLevel1"), base_id=AMULET).mods[0].values == (1,)
