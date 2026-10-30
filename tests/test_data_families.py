"""Family exclusion: two mods conflict when they share any family (ADR-0003, ADR-0021)."""

import dataclasses

import pytest
from repoe_support import fixture_game_data, no_network  # noqa: F401

from crafting_system.data.model import Mod, conflicts

DATA = fixture_game_data()


def mod(mod_id):
    return DATA.mods[mod_id]


@pytest.mark.parametrize(
    ("first", "second", "shared"),
    [
        ("FireDamagePrefixOnWeapon1", "SpellDamageOnWeapon1", "WeaponCasterDamagePrefix"),
        (
            "LocalIncreasedEnergyShield1",
            "LocalIncreasedPhysicalDamageReductionRating1",
            "BaseLocalDefences",
        ),
        ("JunMaster2ArmourAndEnergyShield1", "IncreasedEnergyShield1", "IncreasedEnergyShield"),
    ],
)
def test_mods_sharing_a_family_conflict_in_both_directions(first, second, shared):
    a, b = mod(first), mod(second)

    assert shared in a.families and shared in b.families
    assert conflicts(a, b) is True
    assert conflicts(b, a) is True


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("LocalAddedFireDamageTwoHand1", "LocalIncreasedEnergyShield1"),
        ("JunMaster2ArmourAndEnergyShield1", "LocalIncreasedPhysicalDamageReductionRating1"),
        ("FireDamagePrefixOnWeapon1", "LocalAddedFireDamageTwoHand1"),
    ],
)
def test_mods_sharing_no_family_do_not_conflict(first, second):
    a, b = mod(first), mod(second)

    assert conflicts(a, b) is False
    assert conflicts(b, a) is False


def test_the_two_family_mod_conflicts_through_either_of_its_families_only():
    bench = mod("JunMaster2ArmourAndEnergyShield1")

    assert conflicts(bench, mod("IncreasedEnergyShield1"))  # its second family
    assert not conflicts(bench, mod("LocalIncreasedEnergyShield1"))  # same stat words, other family


def test_a_mod_conflicts_with_itself():
    heated = mod("LocalAddedFireDamageTwoHand1")

    assert conflicts(heated, heated) is True


def test_a_mod_with_no_family_conflicts_with_nothing_not_even_itself():
    heated = mod("LocalAddedFireDamageTwoHand1")
    orphan = dataclasses.replace(heated, id="Orphan1", families=())
    twin = dataclasses.replace(orphan, id="Orphan2")

    assert conflicts(orphan, heated) is False
    assert conflicts(heated, orphan) is False
    assert conflicts(orphan, twin) is False
    assert conflicts(orphan, orphan) is False


def test_the_same_mod_type_alone_never_conflicts():
    heated = mod("LocalAddedFireDamageTwoHand1")
    other = dataclasses.replace(heated, id="Other1", families=("SomethingElse",))

    assert heated.type == other.type
    assert conflicts(heated, other) is False


def test_conflicts_takes_mods():
    assert isinstance(mod("IncreasedEnergyShield1"), Mod)
