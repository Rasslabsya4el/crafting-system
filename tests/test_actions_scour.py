"""The Orb of Scouring: every mod goes but the fractured ones, and the rarity follows what is left (ticket #64)."""

import dataclasses
import random
from fractions import Fraction

import pytest
from actions_support import DATA, RESIST, amulet, fractured_resist, roll

from crafting_system.actions import ScouringOrb
from crafting_system.items import Influence, Rarity

LIFE, FIRE = "IncreasedLife1", "FireResist1"
FRACTURED_LIFE = roll(LIFE, fractured=True)
FRACTURED_REGEN = roll("LifeRegeneration1", fractured=True)


def scour(item):
    return ScouringOrb().outcomes(DATA, item).retained


def test_a_rare_item_goes_back_to_normal():
    scoured = scour(amulet(roll(LIFE), roll(FIRE), roll("IncreasedEnergyShield1"), roll("LifeRegeneration1")))

    assert scoured.rarity is Rarity.NORMAL
    assert scoured.mods == ()


def test_a_magic_item_goes_back_to_normal():
    assert scour(amulet(roll(LIFE), rarity=Rarity.MAGIC)).rarity is Rarity.NORMAL


def test_a_magic_item_without_mods_becomes_normal():
    assert scour(amulet(rarity=Rarity.MAGIC)).rarity is Rarity.NORMAL


@pytest.mark.parametrize("rarity", [Rarity.MAGIC, Rarity.RARE])
def test_one_fractured_mod_stays_and_the_item_is_magic(rarity):
    item = amulet(fractured_resist(), roll(LIFE), roll(FIRE) if rarity is Rarity.RARE else roll("IncreasedEnergyShield1"))
    if rarity is Rarity.MAGIC:
        item = amulet(fractured_resist(), roll(LIFE), rarity=rarity)

    scoured = scour(item)

    assert [entry.mod_id for entry in scoured.mods] == [RESIST]
    assert scoured.rarity is Rarity.MAGIC


def test_a_fractured_prefix_and_suffix_leave_a_rare_item():
    scoured = scour(amulet(FRACTURED_LIFE, fractured_resist(), roll("LifeRegeneration1"), roll("IncreasedEnergyShield1")))

    assert {entry.mod_id for entry in scoured.mods} == {LIFE, RESIST}
    assert scoured.rarity is Rarity.RARE


def test_two_fractured_mods_leave_a_rare_item_and_the_orb_changes_nothing_more():
    item = amulet(FRACTURED_LIFE, fractured_resist(), FRACTURED_REGEN, roll("IncreasedEnergyShield1"))

    scoured = scour(item)

    assert scoured.rarity is Rarity.RARE
    assert len(scoured.mods) == 3
    assert all(entry.fractured for entry in scoured.mods)


def test_an_ordinary_crafted_mod_is_removed():
    scoured = scour(amulet(fractured_resist(), roll("JunMaster2AllDamage2_", crafted=True)))

    assert [entry.mod_id for entry in scoured.mods] == [RESIST]


def test_the_item_keeps_its_influences_and_its_level():
    item = dataclasses.replace(amulet(roll(LIFE)), influences=frozenset({Influence.SHAPER, Influence.ELDER}))

    scoured = scour(item)

    assert scoured.influences == item.influences
    assert (scoured.base_id, scoured.item_level) == (item.base_id, item.item_level)


def test_the_result_has_one_outcome_of_probability_one():
    outcomes = ScouringOrb().outcomes(DATA, amulet(fractured_resist(), roll(LIFE)))

    assert outcomes.distribution(lambda mod: mod.id) == {frozenset(): Fraction(1)}
    assert outcomes.chance_all([RESIST]) == 1
    assert outcomes.chance_all([LIFE]) == 0
    assert outcomes.chance_all([RESIST, "LightningResist2"]) == 0
    assert outcomes.sample(random.Random(1)) is outcomes.retained


def test_chance_all_rejects_an_unknown_mod():
    with pytest.raises(ValueError, match="not in the game data"):
        ScouringOrb().outcomes(DATA, amulet()).chance_all(["NoSuchMod"])
