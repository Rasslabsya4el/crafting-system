"""Tier of a mod on a base, counted among the mods of its mod type that can spawn there."""

import dataclasses

import pytest
from items_support import AMULET, DATA
from repoe_support import no_network  # noqa: F401

from crafting_system.items import (
    ItemError,
    TierError,
    UnknownBaseError,
    UnknownModError,
    mod_tier,
    spawn_weight,
    tier_table,
)

NO_BASE = "Metadata/Items/Amulets/NoSuchAmulet"
NO_MOD = "NoSuchModAnywhere"
CANNOT_SPAWN = "SpellDamageOnWeapon1"  # spawn weight 0 for the amulet tags (its only match is default 0)


@pytest.mark.parametrize("number", range(1, 9))
def test_lightning_resistance_tiers_on_an_amulet(number):
    assert mod_tier(DATA, AMULET, f"LightningResist{number}") == 9 - number


@pytest.mark.parametrize("number", range(1, 10))
def test_added_lightning_damage_tiers_on_an_amulet(number):
    assert mod_tier(DATA, AMULET, f"AddedLightningDamage{number}") == 10 - number


@pytest.mark.parametrize(
    "mod_id",
    [
        "ChaosResist6",
        "ItemFoundRarityIncreasePrefix4_",
        "GlobalLightningGemLevel1",
        "GlobalFireGemLevel1_",
        "GlobalColdGemLevel1__",
        "GlobalPhysicalGemLevel1_",
        "GlobalChaosGemLevel1",
        "GlobalSkillGemLevel1",
    ],
)
def test_the_highest_mod_of_its_type_is_tier_one(mod_id):
    assert mod_tier(DATA, AMULET, mod_id) == 1


def test_mods_that_tie_on_required_level_share_a_tier_and_the_next_one_is_three():
    level = DATA.mods["LightningResist8"].required_level
    tied = dataclasses.replace(DATA.mods["LightningResist1"], required_level=level)
    data = dataclasses.replace(DATA, mods={**DATA.mods, "LightningResist1": tied})

    table = tier_table(data, AMULET)

    assert table["LightningResist1"] == table["LightningResist8"] == 1
    assert table["LightningResist7"] == 3


def test_the_table_holds_exactly_the_mods_that_spawn_on_the_base():
    """The pinned 50 is a plain fixture count, not engine output: the mods of `mods.json` whose first
    spawn weight on a tag of Amulet1 (amulet, default) is positive."""
    table = tier_table(DATA, AMULET)
    tags = DATA.base_items[AMULET].tags

    assert len(table) == 50
    assert all(spawn_weight(DATA.mods[mod_id], tags) > 0 for mod_id in table)
    assert CANNOT_SPAWN not in table


def test_the_table_is_read_only():
    with pytest.raises(TypeError):
        tier_table(DATA, AMULET)["LightningResist1"] = 99


def test_a_mod_that_cannot_spawn_on_the_base_has_no_tier():
    with pytest.raises(TierError, match="cannot spawn there") as caught:
        mod_tier(DATA, AMULET, CANNOT_SPAWN)

    assert isinstance(caught.value, ItemError)


def test_an_unknown_base_is_refused():
    with pytest.raises(UnknownBaseError, match="is not in the game data"):
        tier_table(DATA, NO_BASE)
    with pytest.raises(UnknownBaseError, match="is not in the game data"):
        mod_tier(DATA, NO_BASE, "LightningResist1")


def test_an_unknown_mod_is_refused():
    with pytest.raises(UnknownModError, match="is not in the game data"):
        mod_tier(DATA, AMULET, NO_MOD)
