"""Reading an item against the data, and the updates that return a new validated item."""

import dataclasses

import pytest
from items_support import AMULET, DATA, item, roll
from repoe_support import no_network  # noqa: F401

from crafting_system.items import (
    CapacityError,
    ExplicitMod,
    FamilyConflictError,
    Influence,
    ItemError,
    Metamod,
    Rarity,
    Side,
    UnknownModError,
)

ATTACK_BLOCK = "IntMasterItemGenerationCannotRollAttackAffixes"
SUFFIX_LOCK = "DexMasterItemGenerationCannotChangeSuffixes"


def full_prefixes():
    return item(roll("IncreasedLife1"), roll("LocalIncreasedEnergyShield1"), roll("IncreasedEnergyShield1"))


def test_mods_are_split_by_side():
    built = item(roll("IncreasedLife1"), roll("ColdResist1"), roll("LightningResist1"))

    assert [mod.mod_id for mod in built.prefixes(DATA)] == ["IncreasedLife1"]
    assert [mod.mod_id for mod in built.suffixes(DATA)] == ["ColdResist1", "LightningResist1"]
    assert built.mods_on(DATA, Side.PREFIX) == built.prefixes(DATA)


def test_free_slots_count_what_is_left():
    built = item(roll("IncreasedLife1"), roll("ColdResist1"), roll("LightningResist1"))

    assert built.free_slots(DATA, Side.PREFIX) == 2
    assert built.free_slots(DATA, Side.SUFFIX) == 1
    assert item(rarity=Rarity.NORMAL).free_slots(DATA, Side.PREFIX) == 0


def test_metamods_are_found_by_family():
    built = item(roll(ATTACK_BLOCK, crafted=True), roll(SUFFIX_LOCK, crafted=True), roll("ColdResist1"))

    assert built.metamods(DATA) == {Metamod.NO_ATTACK_MODS, Metamod.SUFFIXES_CANNOT_CHANGE}
    assert item(roll("ColdResist1")).metamods(DATA) == frozenset()


@pytest.mark.parametrize(
    ("mod_id", "metamod"),
    [
        ("StrMasterItemGenerationCannotChangePrefixes", Metamod.PREFIXES_CANNOT_CHANGE),
        ("DexMasterItemGenerationCannotChangeSuffixes", Metamod.SUFFIXES_CANNOT_CHANGE),
        ("IntMasterItemGenerationCannotRollAttackAffixes", Metamod.NO_ATTACK_MODS),
        ("StrDexMasterItemGenerationCannotRollCasterAffixes", Metamod.NO_CASTER_MODS),
        ("StrIntMasterItemGenerationCanHaveMultipleCraftedMods", Metamod.MULTIPLE_CRAFTED_MODS),
    ],
)
def test_every_metamod_in_the_fixture_is_recognised(mod_id, metamod):
    assert item(roll(mod_id, crafted=True)).metamods(DATA) == {metamod}


def test_can_add_needs_a_free_slot_and_no_family_conflict():
    assert full_prefixes().can_add(DATA, DATA.mods["LocalAddedFireDamageTwoHand1"]) is False
    assert full_prefixes().can_add(DATA, DATA.mods["ColdResist1"]) is True
    assert item(roll("ColdResist1")).can_add(DATA, DATA.mods["ColdResist1"]) is False
    assert item(roll("LightningResist1")).can_add(DATA, DATA.mods["LightningResist2"]) is False


def test_can_add_accepts_a_crafted_mod_and_refuses_a_foreign_one():
    built = item(roll("ColdResist1"))
    foreign = dataclasses.replace(DATA.mods["IncreasedLife1"], domain="monster")

    assert built.can_add(DATA, DATA.mods["JunMaster2ArmourAndEnergyShield1"]) is True
    assert built.can_add(DATA, DATA.mods["AccuracyPercentImplicitSword1"]) is False
    assert built.can_add(DATA, foreign) is False


def test_can_add_is_false_on_a_normal_item():
    assert item(rarity=Rarity.NORMAL).can_add(DATA, DATA.mods["IncreasedLife1"]) is False


def test_add_mod_returns_a_new_item():
    before = item(roll("ColdResist1"))
    after = before.add_mod(DATA, roll("IncreasedLife1"))

    assert [mod.mod_id for mod in before.mods] == ["ColdResist1"]
    assert [mod.mod_id for mod in after.mods] == ["ColdResist1", "IncreasedLife1"]


def test_add_mod_validates_the_result():
    with pytest.raises(CapacityError):
        full_prefixes().add_mod(DATA, roll("LocalAddedFireDamageTwoHand1"))
    with pytest.raises(FamilyConflictError):
        item(roll("LightningResist1")).add_mod(DATA, roll("LightningResist2"))
    with pytest.raises(UnknownModError):
        item().add_mod(DATA, ExplicitMod("NoSuchMod", 1, (1,)))


def test_remove_mod_returns_a_new_item_and_allows_a_fractured_mod():
    before = item(roll("ColdResist1", fractured=True), roll("IncreasedLife1"))

    after = before.remove_mod(DATA, "ColdResist1")

    assert [mod.mod_id for mod in after.mods] == ["IncreasedLife1"]
    assert len(before.mods) == 2


def test_removing_a_mod_that_is_not_there_is_an_error():
    with pytest.raises(ItemError, match="BodyInt1.*ColdResist1.*not on the item"):
        item().remove_mod(DATA, "ColdResist1")


def test_changed_replaces_fields_and_validates():
    before = item(roll("ColdResist1"))

    assert before.changed(DATA, item_level=60).item_level == 60
    assert before.changed(DATA, influences=frozenset({Influence.SHAPER})).influences == {Influence.SHAPER}
    assert before.changed(DATA, rarity=Rarity.MAGIC).rarity is Rarity.MAGIC
    assert before.changed(DATA, corrupted=True).corrupted is True
    assert before.item_level == 84
    with pytest.raises(CapacityError):
        before.changed(DATA, rarity=Rarity.NORMAL)
    with pytest.raises(ItemError, match="item level"):
        before.changed(DATA, item_level=0)


def test_changed_can_switch_the_base():
    assert item(roll("ColdResist1")).changed(DATA, base_id=AMULET).base_id == AMULET
