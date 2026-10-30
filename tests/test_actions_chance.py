"""The chance that the finished item holds +1 Lightning gem level, against the hand oracle (ticket #23).

The oracle (`actions_oracle.py`) walks every draw order by hand with `Fraction`s; the engine must
equal it exactly, with and without a fractured Lightning Resistance.
"""

from fractions import Fraction

import pytest
from actions_oracle import chaos_chance, harvest_chance
from actions_support import DATA, RESIST, TARGET, amulet, fractured_resist

from crafting_system.actions import ChaosOrb, HarvestReforge

LEVELS = (80, 84, 86)


def chance(action, item):
    return action.outcomes(DATA, item).chance_all([TARGET])


@pytest.mark.parametrize("level", LEVELS)
def test_chaos_orb_on_a_rare_amulet_matches_the_oracle(level):
    assert chance(ChaosOrb(), amulet(item_level=level)) == chaos_chance(level)


@pytest.mark.parametrize("level", LEVELS)
def test_chaos_orb_with_a_fractured_lightning_resistance_matches_the_oracle(level):
    item = amulet(fractured_resist(), item_level=level)

    assert chance(ChaosOrb(), item) == chaos_chance(level, ("LightningResistance",))


def test_the_chance_is_an_exact_fraction_not_a_float():
    assert type(chance(ChaosOrb(), amulet())) is Fraction


@pytest.mark.parametrize("level", LEVELS)
def test_harvest_reforge_lightning_on_a_rare_amulet_matches_the_oracle(level):
    assert chance(HarvestReforge("lightning"), amulet(item_level=level)) == harvest_chance(level)


@pytest.mark.parametrize("level", LEVELS)
def test_harvest_reforge_lightning_with_a_fractured_lightning_resistance_matches_the_oracle(level):
    item = amulet(fractured_resist(), item_level=level)

    assert chance(HarvestReforge("lightning"), item) == harvest_chance(level, ("LightningResistance",))


@pytest.mark.parametrize("number", range(1, 9))
def test_any_tier_of_the_fractured_resistance_gives_the_same_chance(number):
    item = amulet(fractured_resist(f"LightningResist{number}"))

    assert chance(ChaosOrb(), item) == chaos_chance(86, ("LightningResistance",))
    assert chance(HarvestReforge("lightning"), item) == harvest_chance(86, ("LightningResistance",))


def test_the_fractured_resistance_raises_the_chance_of_the_gem_mod_under_a_reforge():
    plain = chance(HarvestReforge("lightning"), amulet())
    kept = chance(HarvestReforge("lightning"), amulet(fractured_resist()))

    assert kept > plain
