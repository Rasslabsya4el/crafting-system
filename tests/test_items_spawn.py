"""Spawn weight and generation weight of a mod on an item's tags, and the effective weight of a draw."""

import dataclasses
from fractions import Fraction

from items_support import AMULET, DATA
from repoe_support import no_network  # noqa: F401

from crafting_system.data import Weight
from crafting_system.items import effective_weight, generation_factor, spawn_weight

SPELL_ON_WEAPON = DATA.mods["SpellDamageOnWeapon1"]
LIFE_LEECH = DATA.mods["LifeLeechPermyriadSuffix1"]
AMULET_TAGS = DATA.base_items[AMULET].tags


def with_generation_weights(mod, *weights: Weight):
    return dataclasses.replace(mod, generation_weights=weights)


def test_the_first_matching_generation_entry_gives_the_factor():
    mod = with_generation_weights(LIFE_LEECH, Weight("dagger", 50), Weight("default", 100))

    assert generation_factor(mod, ["dagger", "default"]) == Fraction(1, 2)
    assert generation_factor(mod, ["bow", "default"]) == Fraction(1)


def test_no_generation_weights_or_no_matching_one_gives_factor_one():
    assert generation_factor(with_generation_weights(LIFE_LEECH), ["dagger"]) == Fraction(1)
    mod = with_generation_weights(LIFE_LEECH, Weight("dagger", 50))
    assert generation_factor(mod, ["bow", "default"]) == Fraction(1)


def test_effective_weight_is_the_spawn_weight_times_the_factor():
    assert effective_weight(LIFE_LEECH, AMULET_TAGS) == Fraction(1000)
    mod = with_generation_weights(LIFE_LEECH, Weight("amulet", 50))
    assert effective_weight(mod, AMULET_TAGS) == Fraction(500)


def test_the_first_matching_spawn_entry_of_the_mod_decides():
    assert spawn_weight(SPELL_ON_WEAPON, ["dagger", "attack_dagger", "default"]) == 0
    assert spawn_weight(SPELL_ON_WEAPON, ["dagger", "default"]) == 1500
    assert spawn_weight(SPELL_ON_WEAPON, ["wand", "default"]) == 1500


def test_no_matching_tag_gives_spawn_weight_zero():
    assert spawn_weight(SPELL_ON_WEAPON, []) == 0


def test_the_order_of_the_item_tags_does_not_matter():
    assert spawn_weight(SPELL_ON_WEAPON, ["default", "dagger"]) == spawn_weight(
        SPELL_ON_WEAPON, ["dagger", "default"]
    )
