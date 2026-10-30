"""Family conflicts on an item: two mods that share a family cannot sit together (ADR-0003, ADR-0021)."""

import dataclasses

import pytest
from items_support import BODY, DATA, item, roll
from repoe_support import no_network  # noqa: F401

from crafting_system.items import FamilyConflictError, Item, Rarity


def build_on(data, *mods):
    return Item.build(data, base_id=BODY, item_level=84, rarity=Rarity.RARE, mods=mods)


def with_families(**families):
    """The fixture data where the named mods have the given families."""
    changed = {
        mod_id: dataclasses.replace(DATA.mods[mod_id], families=value)
        for mod_id, value in families.items()
    }
    return dataclasses.replace(DATA, mods={**DATA.mods, **changed})


def test_two_natural_mods_of_one_family_conflict():
    with pytest.raises(FamilyConflictError, match=r"BodyInt1.*LocalIncreasedEnergyShield1.*BaseLocalDefences"):
        item(roll("LocalIncreasedEnergyShield1"), roll("LocalIncreasedPhysicalDamageReductionRating1"))


def test_two_tiers_of_one_family_conflict():
    with pytest.raises(FamilyConflictError, match="LightningResist1.*LightningResist2.*LightningResistance"):
        item(roll("LightningResist1"), roll("LightningResist2", tier=2))


def test_a_natural_and_a_crafted_mod_conflict():
    with pytest.raises(FamilyConflictError, match="IncreasedEnergyShield"):
        item(roll("IncreasedEnergyShield1"), roll("JunMaster2ArmourAndEnergyShield1", crafted=True))


def test_a_fractured_mod_still_conflicts():
    with pytest.raises(FamilyConflictError, match="BaseLocalDefences"):
        item(
            roll("LocalIncreasedEnergyShield1", fractured=True),
            roll("LocalIncreasedPhysicalDamageReductionRating1"),
        )


def test_a_mod_with_several_families_conflicts_through_either_one():
    data = with_families(ColdResist1=("IncreasedPhysicalDamageReductionRating",))
    crafted = roll("JunMaster2ArmourAndEnergyShield1", crafted=True)

    with pytest.raises(FamilyConflictError, match="IncreasedPhysicalDamageReductionRating"):
        build_on(data, crafted, roll("ColdResist1"))
    with pytest.raises(FamilyConflictError, match="IncreasedEnergyShield"):
        build_on(data, crafted, roll("IncreasedEnergyShield1"))


def test_mods_without_a_family_conflict_with_nothing():
    data = with_families(ColdResist1=(), LightningResist1=())

    assert len(build_on(data, roll("ColdResist1"), roll("LightningResist1")).mods) == 2


def test_mods_of_different_families_do_not_conflict():
    assert len(item(roll("LocalIncreasedEnergyShield1"), roll("IncreasedEnergyShield1")).mods) == 2


def test_the_families_of_an_item_are_all_families_of_all_its_mods():
    built = item(roll("JunMaster2ArmourAndEnergyShield1", crafted=True), roll("ColdResist1"))

    assert built.families(DATA) == {
        "IncreasedPhysicalDamageReductionRating",
        "IncreasedEnergyShield",
        "ColdResistance",
    }


def test_blocks_is_true_for_a_mod_sharing_a_family():
    built = item(roll("IncreasedEnergyShield1"))

    assert built.blocks(DATA, DATA.mods["JunMaster2ArmourAndEnergyShield1"]) is True
    assert built.blocks(DATA, DATA.mods["ColdResist1"]) is False


def test_blocks_is_true_for_a_mod_already_on_the_item_even_without_a_family():
    data = with_families(ColdResist1=())
    built = build_on(data, roll("ColdResist1"))

    assert built.blocks(data, data.mods["ColdResist1"]) is True
    assert built.blocks(data, data.mods["LightningResist1"]) is False
