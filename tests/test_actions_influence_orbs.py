"""The six influenced Exalted Orbs and the beast influence recipes against a hand oracle (ticket #154).

The fixture is the Contract Helmet of `influence_support.py`, whose pools are typed by hand there (the table in its docstring).
At item level 84 and with the Plain prefix on the item, the Shaper pool is the prefix family P (weights 300 + 300 + 200 = 800) and
the suffix family S (500 + 500 = 1000); the Shaper mod of level 90 is above the item level and the legacy one has weight 0. So one
Shaper's Exalted Orb draws a prefix with chance 800/1800 = 4/9, the top prefix with 200/1800 = 1/9 and the top suffix with 500/1800 = 5/18.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from influence_support import (
    ELDER_P,
    ELDER_S,
    HIGH,
    HUNTER_S,
    INFLUENCE_DATA,
    OLD,
    P1,
    P2,
    P3,
    PLAIN,
    S1,
    S2,
    helmet,
    influence_data,
    roll,
)
from item_state_support import ITEM_DATA, implicit
from item_state_support import AVOID_SHOCK

from crafting_system.actions import (
    BeastInfluenceRecipe,
    InfluencedExaltedOrb,
    NotApplicableError,
    OutOfScopeError,
    catalog,
    influence_pool,
)
from crafting_system.data import BaseItem
from crafting_system.items import Influence, Item, Rarity

DATA = INFLUENCE_DATA
LOCK_PREFIXES = "StrMasterItemGenerationCannotChangePrefixes"  # a crafted metamod on the suffix side
LOCK_SUFFIXES = "DexMasterItemGenerationCannotChangeSuffixes"  # a crafted metamod on the prefix side
NO_ATTACK = "IntMasterItemGenerationCannotRollAttackAffixes"
SHAPER, ELDER, HUNTER, WARLORD = (Influence.SHAPER, Influence.ELDER, Influence.HUNTER, Influence.WARLORD)


def shaper_orb():
    return InfluencedExaltedOrb(SHAPER)


def plain(**fields):
    return helmet(roll(PLAIN, 1), **fields)


def chance(outcomes, *mod_ids) -> Fraction:
    return outcomes.chance_all(mod_ids)


def metamod(mod_id):
    return roll(mod_id, 1, crafted=True)


# --- the draw ---------------------------------------------------------------------------------------------------------


def test_a_shapers_exalted_orb_draws_only_shaper_mods_in_proportion_to_their_weights():
    result = shaper_orb().outcomes(DATA, plain())

    assert chance(result, P3) == Fraction(200, 1800)
    assert chance(result, P1) == chance(result, P2) == Fraction(300, 1800)
    assert chance(result, S1) == chance(result, S2) == Fraction(500, 1800)
    assert chance(result, HIGH) == chance(result, OLD) == 0  # above the item level, and weight 0
    assert chance(result, ELDER_S) == chance(result, HUNTER_S) == chance(result, ELDER_P) == 0  # another influence
    assert chance(result, PLAIN) == 1  # the mod it had stays
    sides = result.distribution(lambda mod: mod.generation_type)
    assert sides == {frozenset({("prefix", 1)}): Fraction(4, 9), frozenset({("suffix", 1)}): Fraction(5, 9)}


def test_the_item_gets_the_influence_and_exactly_one_more_mod():
    result = shaper_orb().outcomes(DATA, plain())

    assert result.retained.influences == {SHAPER}
    for seed in range(20):
        item = result.sample(random.Random(seed))
        assert item.influences == {SHAPER} and len(item.mods) == 2 and any(entry.mod_id == PLAIN for entry in item.mods)
        item.validate(DATA)


def test_the_item_level_gate_cuts_the_pool_and_below_68_the_orb_is_refused():
    with pytest.raises(NotApplicableError, match="68"):
        shaper_orb().outcomes(DATA, plain(level=67))
    low = shaper_orb().outcomes(DATA, plain(level=68))
    assert chance(low, P1) == Fraction(300, 800) and chance(low, S1) == Fraction(500, 800)  # level 68: P1 and S1 only
    assert chance(shaper_orb().outcomes(DATA, plain(level=74)), P2) == 0
    assert chance(shaper_orb().outcomes(DATA, plain(level=75)), P2) == Fraction(300, 1600)  # level 75: P1 + P2 and S1 + S2


def test_a_family_on_the_item_leaves_the_pool():
    result = shaper_orb().outcomes(DATA, helmet(roll(PLAIN, 1), roll(S1, 2)))

    assert chance(result, S2) == 0
    assert chance(result, P3) == Fraction(200, 800)  # the prefix family alone is left
    assert result.distribution(lambda mod: mod.generation_type) == {frozenset({("prefix", 1)}): 1}


def test_a_full_side_closes_and_an_item_with_six_mods_is_refused():
    prefixes_full = helmet(roll(PLAIN, 1), roll(ELDER_P, 1), roll(OLD, 1))
    result = shaper_orb().outcomes(DATA, prefixes_full)
    assert chance(result, S2) == Fraction(1, 2) and chance(result, P1) == 0

    six = helmet(roll(PLAIN, 1), roll(ELDER_P, 1), roll(OLD, 1), roll(ELDER_S, 1), roll(HUNTER_S, 1), roll(HIGH, 1))
    with pytest.raises(NotApplicableError, match="open"):
        shaper_orb().outcomes(DATA, six)


def test_the_open_slot_of_a_locked_side_still_fills():
    # Suffixes Cannot Be Changed sits on the prefix side; the suffix side holds nothing but is locked: it may still be filled
    result = shaper_orb().outcomes(DATA, helmet(roll(PLAIN, 1), metamod(LOCK_SUFFIXES)))
    assert chance(result, S2) == Fraction(500, 1800) and chance(result, P3) == Fraction(200, 1800)


def test_cannot_roll_attack_modifiers_keeps_the_attack_tagged_mods_out():
    # the fixture's Shaper prefixes carry the attack tag, the suffixes do not
    result = shaper_orb().outcomes(DATA, helmet(roll(PLAIN, 1), metamod(NO_ATTACK)))
    assert chance(result, P3) == 0 and chance(result, S2) == Fraction(1, 2)


def test_each_orb_draws_from_its_own_influence_and_an_empty_pool_is_refused():
    elder = InfluencedExaltedOrb(ELDER).outcomes(DATA, plain())
    assert chance(elder, ELDER_S) == Fraction(400, 500) and chance(elder, ELDER_P) == Fraction(100, 500)
    assert elder.retained.influences == {ELDER}
    hunter = InfluencedExaltedOrb(HUNTER).outcomes(DATA, plain())
    assert chance(hunter, HUNTER_S) == 1
    with pytest.raises(NotApplicableError, match="no mod of the pool"):
        InfluencedExaltedOrb(WARLORD).outcomes(DATA, plain())


def test_the_pool_of_an_influence_is_the_hand_table():
    item = shaper_orb().outcomes(DATA, plain()).retained
    table = {family.family: (family.side.value, sum(entry.weight for entry in family.mods)) for family in influence_pool(DATA, item, SHAPER)}
    assert table == {"ContractHelmetShaperP": ("prefix", 800), "ContractHelmetShaperS": ("suffix", 1000)}


# --- the refusals -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("rarity", [Rarity.NORMAL, Rarity.MAGIC])
def test_the_orb_works_on_a_rare_item_only(rarity):
    mods = () if rarity is Rarity.NORMAL else (roll(PLAIN, 1),)
    with pytest.raises(NotApplicableError, match="rare"):
        shaper_orb().outcomes(DATA, helmet(*mods, rarity=rarity))


def test_a_corrupted_item_takes_no_orb():
    with pytest.raises(NotApplicableError, match="corrupted"):
        shaper_orb().outcomes(DATA, plain(corrupted=True))


@pytest.mark.parametrize("held", [SHAPER, ELDER])
@pytest.mark.parametrize("orb", [SHAPER, ELDER])
def test_every_influenced_item_is_refused_the_orbs_own_influence_included(orb, held):
    with pytest.raises(NotApplicableError, match="already has an influence"):
        InfluencedExaltedOrb(orb).outcomes(DATA, plain(influences=frozenset({held})))


def test_a_fractured_item_is_refused():
    with pytest.raises(NotApplicableError, match="fractured"):
        shaper_orb().outcomes(DATA, helmet(roll(PLAIN, 1, fractured=True)))


def test_an_item_with_an_eldritch_implicit_is_refused():
    data = influence_data(ITEM_DATA)
    item = helmet(roll(PLAIN, 1, data), implicits=(implicit(AVOID_SHOCK[0], data),), data=data)
    with pytest.raises(NotApplicableError, match="Eldritch"):
        shaper_orb().outcomes(data, item)


def test_an_item_class_without_an_influence_key_is_out_of_scope():
    jewel = BaseItem("Metadata/Items/Jewels/ContractJewel", "Contract Jewel", "Jewel", "item", 1, (), (), "released")
    data = dataclasses.replace(INFLUENCE_DATA, base_items={**INFLUENCE_DATA.base_items, jewel.id: jewel})
    item = Item.build(data, base_id=jewel.id, item_level=84, rarity=Rarity.RARE, mods=())
    with pytest.raises(OutOfScopeError, match="class key"):
        shaper_orb().outcomes(data, item)


# --- the beast recipes --------------------------------------------------------------------------------------------------


def test_a_beast_recipe_draws_from_the_pool_of_its_influence_on_an_item_that_has_it():
    item = plain(influences=frozenset({SHAPER}))
    result = BeastInfluenceRecipe(SHAPER).outcomes(DATA, item)

    assert chance(result, P3) == Fraction(200, 1800) and chance(result, S2) == Fraction(500, 1800)
    assert result.retained.influences == {SHAPER}  # only the pool is borrowed: the influences are not added to
    # it uses the item's own level, like its orb
    low = BeastInfluenceRecipe(SHAPER).outcomes(DATA, plain(level=68, influences=frozenset({SHAPER})))
    assert chance(low, P1) == Fraction(300, 800)


def test_a_beast_recipe_borrows_the_pool_of_its_influence_alone_on_a_dual_influenced_item():
    item = plain(influences=frozenset({SHAPER, ELDER}))
    shaper = BeastInfluenceRecipe(SHAPER).outcomes(DATA, item)
    assert chance(shaper, ELDER_S) == 0 and chance(shaper, ELDER_P) == 0 and chance(shaper, S2) == Fraction(500, 1800)
    elder = BeastInfluenceRecipe(ELDER).outcomes(DATA, item)
    assert chance(elder, ELDER_S) == Fraction(400, 500) and chance(elder, S2) == 0


def test_a_beast_recipe_needs_a_rare_uncorrupted_item_with_the_influence_and_a_legal_mod():
    recipe = BeastInfluenceRecipe(SHAPER)
    with pytest.raises(NotApplicableError, match="Shaper influence"):
        recipe.outcomes(DATA, plain())
    with pytest.raises(NotApplicableError, match="Shaper influence"):
        recipe.outcomes(DATA, plain(influences=frozenset({ELDER})))
    with pytest.raises(NotApplicableError, match="rare"):
        recipe.outcomes(DATA, helmet(roll(PLAIN, 1), rarity=Rarity.MAGIC, influences=frozenset({SHAPER})))
    with pytest.raises(NotApplicableError, match="corrupted"):
        recipe.outcomes(DATA, plain(corrupted=True, influences=frozenset({SHAPER})))
    with pytest.raises(NotApplicableError, match="no mod of the pool"):
        BeastInfluenceRecipe(WARLORD).outcomes(DATA, plain(influences=frozenset({WARLORD})))


# --- names, prices, claims and the catalog ---------------------------------------------------------------------------------


def test_the_six_orbs_and_recipes_have_their_names_and_prices():
    labels = [InfluencedExaltedOrb(influence).label() for influence in Influence]
    assert labels == [f"{word}'s Exalted Orb" for word in ("Shaper", "Elder", "Crusader", "Hunter", "Redeemer", "Warlord")]
    assert [dict(InfluencedExaltedOrb(influence).resources()) for influence in Influence] == [{label: 1} for label in labels]
    assert BeastInfluenceRecipe(HUNTER).label() == "Beastcraft Add a Mod to a Hunter Item"
    assert dict(BeastInfluenceRecipe(SHAPER).resources()) == {"Fenumal Devourer": 1, "Craicic Maw": 1, "Chaos Orb": 2}
    assert dict(BeastInfluenceRecipe(SHAPER, rare_creature_price=3).resources()) == {"Fenumal Devourer": 1, "Craicic Maw": 1, "Chaos Orb": 6}
    assert dict(BeastInfluenceRecipe(ELDER).resources())["Saqawine Blood Viper"] == 1


def test_the_answers_name_the_approximate_claims_they_read():
    orb = InfluencedExaltedOrb(SHAPER).claims()
    assert {"influence.exalt_refused_on_eldritch_implicit", "influence.exalt_refused_without_legal_mod", "influence.cost"} <= orb
    assert "influence_beast.adds_a_mod_of_that_influence" not in orb and "dominance.picks_uniform_remove_first" not in orb
    recipe = BeastInfluenceRecipe(SHAPER).claims()
    assert {"influence_beast.adds_a_mod_of_that_influence", "influence_beast.recipes"} <= recipe
    assert "influence.exalt_refused_on_eldritch_implicit" not in recipe


def test_the_catalog_offers_the_six_orbs_on_an_uninfluenced_rare_item_and_the_recipes_on_the_influences_it_has():
    plain_item = plain()
    assert [a for a in catalog(DATA, plain_item) if isinstance(a, InfluencedExaltedOrb)] == [InfluencedExaltedOrb(i) for i in Influence]
    assert not [a for a in catalog(DATA, plain_item) if isinstance(a, BeastInfluenceRecipe)]
    shaper_item = plain(influences=frozenset({SHAPER}))
    offered = catalog(DATA, shaper_item)
    assert not [a for a in offered if isinstance(a, InfluencedExaltedOrb)]
    assert [a for a in offered if isinstance(a, BeastInfluenceRecipe)] == [BeastInfluenceRecipe(SHAPER)]
    assert not [a for a in catalog(DATA, helmet(roll(PLAIN, 1), rarity=Rarity.MAGIC)) if isinstance(a, InfluencedExaltedOrb)]


def test_an_orb_and_a_recipe_must_be_given_an_influence():
    with pytest.raises(ValueError):
        InfluencedExaltedOrb("shaper")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        BeastInfluenceRecipe("shaper")  # type: ignore[arg-type]
