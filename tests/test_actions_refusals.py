"""What an action refuses, with which error, and in which order."""

import dataclasses

import pytest
from actions_support import AMULET, DATA, amulet, fractured_resist, roll

from crafting_system.actions import (
    ActionError,
    ChaosOrb,
    HarvestReforge,
    NotApplicableError,
    OutOfScopeError,
    Outcomes,
)
from crafting_system.items import Influence, Rarity

ACTIONS = (ChaosOrb(), HarvestReforge("lightning"))
CRAFTED = "DexMasterItemGenerationCannotChangeSuffixes"


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("rarity", [Rarity.NORMAL, Rarity.MAGIC])
def test_an_item_that_is_not_rare_is_refused_by_the_game(action, rarity):
    mods = (roll("IncreasedLife1"),) if rarity is Rarity.MAGIC else ()
    item = amulet(*mods, rarity=rarity)

    with pytest.raises(NotApplicableError, match="rare item only"):
        action.outcomes(DATA, item)


@pytest.mark.parametrize(
    ("action", "fragment"),
    [(ChaosOrb(), "takes no Chaos Orb"), (HarvestReforge("lightning"), "takes no Harvest reforge")],
)
def test_a_corrupted_item_is_refused_by_the_game_and_the_message_names_the_action(action, fragment):
    with pytest.raises(NotApplicableError, match=f"corrupted.*{fragment}"):
        action.outcomes(DATA, dataclasses.replace(amulet(), corrupted=True))


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("item_class", ["Jewel", "AbyssJewel"])
def test_a_jewel_base_is_out_of_scope(action, item_class):
    base = DATA.base_items[AMULET]
    jewel = dataclasses.replace(base, item_class=item_class)
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, AMULET: jewel})

    with pytest.raises(OutOfScopeError, match=rf"jewel \({item_class}\).*regular items only"):
        action.outcomes(data, amulet())


@pytest.mark.parametrize("action", ACTIONS)
def test_an_influenced_item_of_a_class_with_no_influence_class_key_is_out_of_scope(action):
    sword = dataclasses.replace(DATA.base_items[AMULET], item_class="Thrusting One Hand Sword")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, AMULET: sword})
    item = dataclasses.replace(amulet(), influences=frozenset({Influence.SHAPER}))

    with pytest.raises(OutOfScopeError, match="influence class key"):
        action.outcomes(data, item)


@pytest.mark.parametrize("action", ACTIONS)
def test_an_influenced_amulet_is_in_scope(action):
    item = dataclasses.replace(amulet(), influences=frozenset({Influence.SHAPER}))

    assert action.outcomes(DATA, item).retained.influences == item.influences


@pytest.mark.parametrize("action", ACTIONS)
def test_a_crafted_metamod_makes_the_item_out_of_scope(action):
    item = amulet(roll(CRAFTED, crafted=True))

    with pytest.raises(OutOfScopeError, match="crafted metamod"):
        action.outcomes(DATA, item)


@pytest.mark.parametrize("action", ACTIONS)
def test_an_ordinary_crafted_mod_does_not_make_the_item_out_of_scope(action):
    item = amulet(roll("JunMaster2AllDamage2_", crafted=True))

    assert action.outcomes(DATA, item).retained.mods == ()


@pytest.mark.parametrize("action", ACTIONS)
def test_a_not_applicable_error_comes_before_an_out_of_scope_one(action):
    item = dataclasses.replace(
        amulet(), corrupted=True, influences=frozenset({Influence.HUNTER})
    )

    with pytest.raises(NotApplicableError):
        action.outcomes(DATA, item)


def test_both_refusals_are_action_errors_and_value_errors():
    assert issubclass(NotApplicableError, ActionError) and issubclass(OutOfScopeError, ActionError)
    assert issubclass(ActionError, ValueError)


def test_a_reforge_is_refused_when_every_tagged_family_is_blocked():
    blocked = amulet(
        roll("AddedLightningDamage1", fractured=True),
        roll("GlobalLightningGemLevel1", fractured=True),
        roll("LightningResist1", fractured=True),
        roll("LightningDamagePercent1", fractured=True),
    )

    with pytest.raises(NotApplicableError, match="no lightning mod"):
        HarvestReforge("lightning").outcomes(DATA, blocked)
    # The Chaos Orb has no such need and works on the same item.
    assert ChaosOrb().outcomes(DATA, blocked).retained == blocked


def test_a_reforge_is_refused_when_the_side_of_every_tagged_mod_is_full():
    # Three fractured suffixes fill that side; the only tagged prefixes are blocked by a fractured one each.
    item = amulet(
        roll("LifeRegeneration1", fractured=True),
        roll("ColdResist1", fractured=True),
        roll("ChaosResist1", fractured=True),
        roll("AddedLightningDamage1", fractured=True),
        roll("GlobalLightningGemLevel1", fractured=True),
    )

    with pytest.raises(NotApplicableError, match="no lightning mod"):
        HarvestReforge("lightning").outcomes(DATA, item)


def test_building_outcomes_with_a_tag_nothing_can_carry_is_refused_by_the_game():
    blocked = amulet(
        roll("AddedLightningDamage1", fractured=True),
        roll("GlobalLightningGemLevel1", fractured=True),
        roll("LightningResist1", fractured=True),
        roll("LightningDamagePercent1", fractured=True),
    )

    with pytest.raises(NotApplicableError, match="no lightning mod"):
        Outcomes.reroll(DATA, blocked, "lightning")
    assert Outcomes.reroll(DATA, blocked, None).tag is None


@pytest.mark.parametrize("tag", [["lightning"], None, 5, ("lightning",)])
def test_a_reforge_with_a_tag_that_is_not_a_string_cannot_be_built(tag):
    with pytest.raises(ValueError, match="no Harvest reforge for the tag"):
        HarvestReforge(tag)


def test_a_reforge_with_an_unknown_tag_cannot_be_built():
    with pytest.raises(ValueError, match="no Harvest reforge for the tag 'fire'"):
        HarvestReforge("fire")


def test_the_default_reforge_is_lightning():
    assert HarvestReforge() == HarvestReforge("lightning")


def test_an_action_is_a_value():
    assert ChaosOrb() == ChaosOrb()
    assert hash(HarvestReforge("lightning")) == hash(HarvestReforge("lightning"))


def test_an_item_on_an_unknown_base_is_not_modelled():
    item = amulet(fractured_resist())
    data = dataclasses.replace(DATA, base_items={k: v for k, v in DATA.base_items.items() if k != AMULET})

    with pytest.raises(ValueError):
        ChaosOrb().outcomes(data, item)
