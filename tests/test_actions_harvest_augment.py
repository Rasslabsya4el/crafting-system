"""The Harvest add and remove crafts (ticket #148, ADR-0030): 11 crafts that add a new mod of a tag and remove another.

Every expected number is written here by hand, not read from the registry or the code:

* the cost of the 11 crafts, the lifeforce prices of 2026-10-31 and the cost in chaos come from the wiki table and the
  research (`harvest_augment_support.CRAFTS`, `PRICES`);
* the chances come from the weights of the small amulet pool (`abstraction_pool.SMALL`, hand-tagged by
  `harvest_reforge_support.TAGGED`): a mod's chance to be added is its weight over the weights of the mods of the tag that
  fit an open side and whose family the item does not hold, and the mod removed is uniform among the others, so each
  (added, removed) result has the chance weight / total * 1/n.

The weights of the pool (amulet, item level 84), by hand from the fixture: Life 1 and 2: 1000 each (prefixes); Added
Lightning Damage 1 and 2: 500 each (prefixes); the three gem-level mods (Lightning, Fire, Cold): 200 each (prefixes);
Mana Leech 1 and 2: 1000 each (suffixes); Fire and Cold Resistance: 1000 each; Lightning Resistance 1 to 3: 1000 each
(suffixes). The crafted mod of the pool, `DexMasterItemGenerationCannotChangeSuffixes`, is a prefix that locks the suffixes.
"""

import datetime
import random
from fractions import Fraction
from math import sqrt

import pytest
from abstraction_pool import (
    COLD_GEM,
    COLD_RESIST,
    CRAFTED,
    DAMAGE_1,
    DAMAGE_2,
    FIRE_GEM,
    FIRE_RESIST,
    GEM,
    LIFE_1,
    LIFE_2,
    MANA_1,
    MANA_2,
    RESIST_1,
    RESIST_2,
    RESIST_3,
    roll,
)
from harvest_augment_support import (
    CRAFTS,
    META_DATA,
    NO_ATTACK,
    NO_CASTER,
    PCBC,
    PRICES,
    SACRED,
    amulet,
    lowest,
    pairs,
)

from crafting_system.actions import HarvestAddRemove, NotApplicableError, catalog, kinds
from crafting_system.cli._offers import offer_of, price_offers
from crafting_system.items import ExplicitMod, Influence, Rarity
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.rules import SourceKind, get_rule

ONE = Fraction(1)
HALF = Fraction(1, 2)

# --- the 11 crafts ----------------------------------------------------------------------------------


def test_the_eleven_crafts_are_the_wiki_table():
    assert set(get_rule("harvest_augment.add_remove_crafts_exist").value) == set(CRAFTS)
    assert len(CRAFTS) == 11
    for craft, (tag, lifeforce, count, _) in CRAFTS.items():
        action = HarvestAddRemove(craft)
        assert action.label() == f"Harvest Add Remove {craft.title()}", craft
        assert action.resources() == {lifeforce: count, SACRED: 1}, craft
        assert action.adds().tag == tag, craft


def test_the_cost_of_each_craft_is_typed_from_the_wiki_table():
    """A guard on the table itself: fire, cold and lightning 15000, the six of 17500 and the two of 20000."""
    assert {craft for craft, row in CRAFTS.items() if row[2] == 15000} == {"fire", "cold", "lightning", "physical"}
    assert {craft for craft, row in CRAFTS.items() if row[2] == 17500} == {"life", "defence", "chaos", "attack", "caster"}
    assert {craft for craft, row in CRAFTS.items() if row[2] == 20000} == {"speed", "critical"}
    assert HarvestAddRemove("fire").resources() == {"Wild Crystallised Lifeforce": 15000, "Sacred Crystallised Lifeforce": 1}
    assert HarvestAddRemove("critical").resources() == {"Primal Crystallised Lifeforce": 20000, "Sacred Crystallised Lifeforce": 1}


def test_the_default_craft_is_fire():
    assert HarvestAddRemove().craft == "fire"


@pytest.mark.parametrize("name", ["", "Fire", "defences", "influence", "randomise", "minion", "elemental", None, 3])
def test_a_craft_that_does_not_exist_is_refused_at_construction(name):
    with pytest.raises(ValueError, match="no Harvest add and remove craft"):
        HarvestAddRemove(name)


# --- the price in chaos -----------------------------------------------------------------------------


def price_file() -> PriceFile:
    prices = {name: PriceEntry(chaos, "test") for name, chaos in PRICES.items()}
    return PriceFile("Test", datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), 300.0, prices)


def test_each_craft_costs_what_the_research_says_to_one_decimal():
    offers = [offer_of(HarvestAddRemove(craft), HarvestAddRemove(craft).label()) for craft in CRAFTS]
    priced, dropped = price_offers(offers, price_file())
    assert not dropped
    costs = {offer.offer.label: offer.cost for offer in priced}
    for craft, (_, lifeforce, count, chaos) in CRAFTS.items():
        cost = costs[f"Harvest Add Remove {craft.title()}"]
        assert cost == pytest.approx(chaos, abs=0.06), craft
        assert cost == pytest.approx(count * PRICES[lifeforce] + 49.75), craft  # one Sacred is 49.75 chaos


def test_without_a_sacred_price_every_craft_is_dropped_for_it():
    prices = price_file()
    del prices.prices[SACRED]
    offers = [offer_of(HarvestAddRemove(craft), HarvestAddRemove(craft).label()) for craft in CRAFTS]
    priced, dropped = price_offers(offers, prices)
    assert not priced
    assert {drop.missing for drop in dropped} == {(SACRED,)}
    assert len(dropped) == 11


# --- the exact distribution on hand-built cases -----------------------------------------------------


def test_fire_on_a_life_and_cold_resistance_amulet():
    """Life 1 (prefix) and Cold Resistance (suffix) are held; the Fire mods are Fire Gem Level (200) and Fire Resistance (1000).

    P(Fire Gem Level) = 200/1200 = 1/6, P(Fire Resistance) = 1000/1200 = 5/6, and the mod removed is Life 1 or Cold
    Resistance with 1/2 each: four results of 1/12, 1/12, 5/12, 5/12.
    """
    start = amulet(roll(LIFE_1), roll(COLD_RESIST))
    outcomes = HarvestAddRemove("fire").outcomes(META_DATA, start)

    assert pairs(outcomes) == {
        (FIRE_GEM, LIFE_1): Fraction(1, 12),
        (FIRE_GEM, COLD_RESIST): Fraction(1, 12),
        (FIRE_RESIST, LIFE_1): Fraction(5, 12),
        (FIRE_RESIST, COLD_RESIST): Fraction(5, 12),
    }
    assert len(outcomes.results) == 4
    assert sum(chance for chance, _ in outcomes.results) == 1
    assert outcomes.chance_all([FIRE_GEM]) == Fraction(1, 6)
    assert outcomes.chance_all([FIRE_RESIST]) == Fraction(5, 6)
    assert outcomes.chance_all([LIFE_1]) == HALF  # stays when Cold Resistance goes
    assert outcomes.chance_all([COLD_RESIST]) == HALF
    assert outcomes.chance_all([FIRE_GEM, LIFE_1]) == Fraction(1, 12)
    assert outcomes.chance_all([FIRE_GEM, COLD_RESIST]) == Fraction(1, 12)
    assert outcomes.chance_all([FIRE_RESIST, LIFE_1]) == Fraction(5, 12)
    assert outcomes.chance_all([FIRE_RESIST, COLD_RESIST]) == Fraction(5, 12)
    assert outcomes.chance_all([LIFE_1, COLD_RESIST]) == 0  # exactly one of the two old mods goes
    assert outcomes.chance_all([FIRE_GEM, FIRE_RESIST]) == 0  # one mod is added
    assert outcomes.chance_all([COLD_GEM]) == 0  # not a Fire mod


def test_the_rarity_stays_and_the_other_fields_are_kept():
    start = amulet(roll(LIFE_1), roll(COLD_RESIST))
    for _, result in HarvestAddRemove("fire").outcomes(META_DATA, start).results:
        assert result.rarity is Rarity.RARE
        assert result.item_level == start.item_level and result.base_id == start.base_id
        assert not result.corrupted and not result.influences
        assert len(result.mods) == 2  # one added, one removed


def test_lightning_has_six_candidates_of_four_hundred_and_two_hundred_over_a_total_of_4200():
    """Life 1 and Fire Resistance are held (neither blocks a Lightning mod): Lightning Gem Level 200, Added Lightning
    Damage 1 and 2: 500 each, Lightning Resistance 1 to 3: 1000 each; the total is 200 + 500 + 500 + 3000 = 4200.
    """
    start = amulet(roll(LIFE_1), roll(FIRE_RESIST))
    outcomes = HarvestAddRemove("lightning").outcomes(META_DATA, start)

    added = {
        GEM: Fraction(1, 21),  # 200/4200
        DAMAGE_1: Fraction(5, 42),  # 500/4200
        DAMAGE_2: Fraction(5, 42),
        RESIST_1: Fraction(5, 21),  # 1000/4200
        RESIST_2: Fraction(5, 21),
        RESIST_3: Fraction(5, 21),
    }
    assert sum(added.values()) == 1
    assert len(outcomes.results) == 12
    assert pairs(outcomes) == {(mod_id, gone): chance / 2 for mod_id, chance in added.items() for gone in (LIFE_1, FIRE_RESIST)}
    for mod_id, chance in added.items():
        assert outcomes.chance_all([mod_id]) == chance, mod_id
        assert outcomes.chance_all([mod_id, LIFE_1]) == chance / 2, mod_id
    assert outcomes.chance_all([RESIST_1, RESIST_2]) == 0  # one family, one mod
    assert outcomes.chance_all([DAMAGE_1, DAMAGE_2]) == 0


def test_with_three_mods_each_is_removed_with_a_third():
    """Life 1, Cold Resistance and Mana Leech 1 are held; Fire: 1/6 gem, 5/6 resistance; one of the three goes with 1/3."""
    start = amulet(roll(LIFE_1), roll(COLD_RESIST), roll(MANA_1))
    outcomes = HarvestAddRemove("fire").outcomes(META_DATA, start)

    assert len(outcomes.results) == 6
    assert pairs(outcomes) == {
        (FIRE_GEM, LIFE_1): Fraction(1, 18),
        (FIRE_GEM, COLD_RESIST): Fraction(1, 18),
        (FIRE_GEM, MANA_1): Fraction(1, 18),
        (FIRE_RESIST, LIFE_1): Fraction(5, 18),
        (FIRE_RESIST, COLD_RESIST): Fraction(5, 18),
        (FIRE_RESIST, MANA_1): Fraction(5, 18),
    }
    assert outcomes.chance_all([LIFE_1, COLD_RESIST]) == Fraction(1, 3)  # Mana Leech goes
    assert outcomes.chance_all([FIRE_RESIST, LIFE_1, COLD_RESIST]) == Fraction(5, 18)
    assert outcomes.chance_all([LIFE_1]) == Fraction(2, 3)


# For the item below (Lightning Resistance 2, a suffix, and Added Lightning Damage 1, a prefix, held), the mods of
# the two Lightning families are out of every draw. What is left of each tag, by hand from the tag table and weights:
BASE_HELD = (RESIST_2, DAMAGE_1)
ADDED_ON_BASE = {
    "fire": {FIRE_GEM: Fraction(1, 6), FIRE_RESIST: Fraction(5, 6)},  # 200, 1000
    "cold": {COLD_GEM: Fraction(1, 6), COLD_RESIST: Fraction(5, 6)},  # 200, 1000
    "lightning": {GEM: ONE},  # only the gem-level mod is outside the two held families
    "physical": {LIFE_2: ONE},  # Added Lightning Damage 2 is blocked by Damage 1
    "life": {LIFE_1: Fraction(1, 3), LIFE_2: Fraction(1, 3), MANA_1: Fraction(1, 3)},
    "defence": {LIFE_1: Fraction(1, 3), COLD_RESIST: Fraction(1, 3), FIRE_RESIST: Fraction(1, 3)},
    "chaos": {MANA_2: ONE},  # Damage 1 is held
    "attack": {MANA_1: ONE},  # both damage mods are blocked
    "caster": {GEM: Fraction(1, 3), FIRE_GEM: Fraction(1, 3), COLD_GEM: Fraction(1, 3)},
    "speed": {MANA_1: HALF, MANA_2: HALF},
    "critical": {GEM: Fraction(1, 6), LIFE_1: Fraction(5, 6)},  # 200, 1000
}


@pytest.mark.parametrize("craft", ADDED_ON_BASE)
def test_every_craft_adds_in_proportion_to_weight_and_removes_one_of_the_two_held_mods(craft):
    start = amulet(roll(RESIST_2), roll(DAMAGE_1))
    outcomes = HarvestAddRemove(craft).outcomes(META_DATA, start)

    expected = ADDED_ON_BASE[craft]
    assert sum(expected.values()) == 1
    assert pairs(outcomes) == {(mod_id, gone): chance / 2 for mod_id, chance in expected.items() for gone in BASE_HELD}
    assert len(outcomes.results) == 2 * len(expected)
    for mod_id, chance in expected.items():
        assert outcomes.chance_all([mod_id]) == chance, mod_id
    assert outcomes.chance_all([RESIST_2]) == HALF
    assert outcomes.chance_all([DAMAGE_1]) == HALF


def test_the_added_mod_sits_at_its_tier_and_lowest_values():
    """Tiers of the small pool, by hand: Life 2, Damage 2, Mana Leech 2, Resistance 3, Fire/Cold Resistance and the gem
    mods are tier 1; Life 1, Damage 1, Mana Leech 1 and Lightning Resistance 2 are tier 2; Lightning Resistance 1 is tier 3.
    """
    tiers = {
        LIFE_1: ExplicitMod(LIFE_1, 2, (10,)),
        LIFE_2: ExplicitMod(LIFE_2, 1, (25,)),
        DAMAGE_1: ExplicitMod(DAMAGE_1, 2, (1, 5)),
        DAMAGE_2: ExplicitMod(DAMAGE_2, 1, (1, 14)),
        MANA_1: ExplicitMod(MANA_1, 2, (20,)),
        MANA_2: ExplicitMod(MANA_2, 1, (60,)),
        RESIST_1: ExplicitMod(RESIST_1, 3, (6,)),
        RESIST_2: ExplicitMod(RESIST_2, 2, (12,)),
        RESIST_3: ExplicitMod(RESIST_3, 1, (18,)),
        FIRE_RESIST: ExplicitMod(FIRE_RESIST, 1, (6,)),
        COLD_RESIST: ExplicitMod(COLD_RESIST, 1, (6,)),
        GEM: ExplicitMod(GEM, 1, (1,)),
        FIRE_GEM: ExplicitMod(FIRE_GEM, 1, (1,)),
        COLD_GEM: ExplicitMod(COLD_GEM, 1, (1,)),
    }
    for craft, added in ADDED_ON_BASE.items():
        outcomes = HarvestAddRemove(craft).outcomes(META_DATA, amulet(roll(RESIST_2), roll(DAMAGE_1)))
        for _, result in outcomes.results:
            (new,) = (entry for entry in result.mods if entry.mod_id in added)
            assert new == tiers[new.mod_id], (craft, new.mod_id)
            assert not new.fractured and not new.crafted


def test_a_held_mod_keeps_its_tier_and_values():
    start = amulet(ExplicitMod(LIFE_1, 2, (17,)), roll(COLD_RESIST))
    for _, result in HarvestAddRemove("fire").outcomes(META_DATA, start).results:
        kept = [entry for entry in result.mods if entry.mod_id == LIFE_1]
        assert kept in ([], [ExplicitMod(LIFE_1, 2, (17,))])


# --- the refusals -----------------------------------------------------------------------------------


def test_a_normal_item_is_refused():
    with pytest.raises(NotApplicableError, match="normal"):
        HarvestAddRemove("fire").outcomes(META_DATA, amulet(rarity=Rarity.NORMAL))


def test_a_corrupted_item_is_refused():
    with pytest.raises(NotApplicableError, match="corrupted"):
        HarvestAddRemove("fire").outcomes(META_DATA, amulet(roll(LIFE_1), corrupted=True))


@pytest.mark.parametrize("influence", [Influence.SHAPER, Influence.HUNTER, Influence.WARLORD])
def test_an_influenced_item_is_refused(influence):
    start = amulet(roll(LIFE_1), roll(COLD_RESIST), influences=frozenset({influence}))
    with pytest.raises(NotApplicableError, match="influenced"):
        HarvestAddRemove("fire").outcomes(META_DATA, start)


@pytest.mark.parametrize("craft", CRAFTS)
def test_a_full_item_is_refused_by_every_craft(craft):
    full = amulet(*(roll(mod_id) for mod_id in (GEM, LIFE_1, DAMAGE_1, RESIST_1, COLD_RESIST, FIRE_RESIST)))
    with pytest.raises(NotApplicableError, match="cannot add a mod"):
        HarvestAddRemove(craft).outcomes(META_DATA, full)


def test_a_tag_whose_mods_are_all_suffixes_is_refused_when_the_suffixes_are_full():
    """Speed is on the two Mana Leech suffixes only; three suffixes held leave no open one, though a prefix is free."""
    start = amulet(roll(LIFE_1), roll(RESIST_1), roll(COLD_RESIST), roll(FIRE_RESIST))
    with pytest.raises(NotApplicableError, match="speed"):
        HarvestAddRemove("speed").outcomes(META_DATA, start)
    # Caster is on the three gem-level prefixes (200 each, 1/3 each); one of the four old mods goes with 1/4: 1/12 a pair
    caster = HarvestAddRemove("caster").outcomes(META_DATA, start)
    assert {(added, chance) for (added, _), chance in pairs(caster).items()} == {
        (GEM, Fraction(1, 12)),
        (FIRE_GEM, Fraction(1, 12)),
        (COLD_GEM, Fraction(1, 12)),
    }


def test_a_tag_whose_mods_are_all_in_a_held_family_is_refused():
    """Speed is on Mana Leech 1 and 2, one family: holding Mana Leech 1 blocks both."""
    with pytest.raises(NotApplicableError, match="speed"):
        HarvestAddRemove("speed").outcomes(META_DATA, amulet(roll(MANA_1)))


def test_a_tag_whose_mods_are_above_the_item_level_is_refused():
    """Mana Leech 1 needs level 50 and Mana Leech 2 level 70; an item of level 40 rolls neither."""
    with pytest.raises(NotApplicableError, match="speed"):
        HarvestAddRemove("speed").outcomes(META_DATA, amulet(roll(LIFE_1), level=40))


def test_nothing_to_remove_when_every_mod_is_fractured():
    start = amulet(roll(LIFE_1, fractured=True), roll(COLD_RESIST, fractured=True))
    with pytest.raises(NotApplicableError, match="cannot remove a mod"):
        HarvestAddRemove("fire").outcomes(META_DATA, start)


def test_nothing_to_remove_when_the_item_has_no_mod_at_all():
    with pytest.raises(NotApplicableError, match="cannot remove a mod"):
        HarvestAddRemove("fire").outcomes(META_DATA, amulet())


def test_nothing_to_remove_when_both_sides_are_locked():
    """The suffix lock is a prefix and the prefix lock is a suffix: each sits on the side the other locks."""
    start = amulet(roll(CRAFTED, crafted=True), lowest(PCBC, crafted=True))
    with pytest.raises(NotApplicableError, match="cannot remove a mod"):
        HarvestAddRemove("cold").outcomes(META_DATA, start)


def test_nothing_to_remove_when_the_only_free_mod_is_a_fractured_metamod():
    """A fractured Suffixes Cannot Be Changed (on the prefix side) and a Cold Resistance on the locked suffix side."""
    start = amulet(roll(CRAFTED, crafted=True, fractured=True), roll(COLD_RESIST))
    with pytest.raises(NotApplicableError, match="cannot remove a mod"):
        HarvestAddRemove("fire").outcomes(META_DATA, start)


# --- items the craft does work on ------------------------------------------------------------------


def test_a_fractured_mod_is_never_removed():
    """Life 1 fractured, Cold Resistance not: only Cold Resistance can go."""
    start = amulet(roll(LIFE_1, fractured=True), roll(COLD_RESIST))
    outcomes = HarvestAddRemove("fire").outcomes(META_DATA, start)

    assert pairs(outcomes) == {(FIRE_GEM, COLD_RESIST): Fraction(1, 6), (FIRE_RESIST, COLD_RESIST): Fraction(5, 6)}
    assert outcomes.chance_all([LIFE_1]) == 1
    assert outcomes.chance_all([COLD_RESIST]) == 0
    for _, result in outcomes.results:
        (kept,) = (entry for entry in result.mods if entry.mod_id == LIFE_1)
        assert kept.fractured


def test_a_fractured_mod_holding_a_family_still_blocks_it():
    """Fractured Fire Resistance stays on the item, so the Fire craft can only add the Fire gem-level mod."""
    start = amulet(roll(FIRE_RESIST, fractured=True), roll(LIFE_1))
    outcomes = HarvestAddRemove("fire").outcomes(META_DATA, start)
    assert pairs(outcomes) == {(FIRE_GEM, LIFE_1): ONE}


def test_a_magic_item_works():
    """A magic amulet holds one prefix and one suffix: with Life 1 held the only open side is the suffix, so Fire adds
    Fire Resistance (1000/1000) and Life 1 goes."""
    start = amulet(roll(LIFE_1), rarity=Rarity.MAGIC)
    outcomes = HarvestAddRemove("fire").outcomes(META_DATA, start)

    assert pairs(outcomes) == {(FIRE_RESIST, LIFE_1): ONE}
    (_, result), = outcomes.results
    assert result.rarity is Rarity.MAGIC
    assert [entry.mod_id for entry in result.mods] == [FIRE_RESIST]


def test_a_magic_item_with_both_sides_full_is_refused():
    start = amulet(roll(LIFE_1), roll(COLD_RESIST), rarity=Rarity.MAGIC)
    with pytest.raises(NotApplicableError, match="cannot add a mod"):
        HarvestAddRemove("fire").outcomes(META_DATA, start)


# --- the metamods ----------------------------------------------------------------------------------


def test_suffixes_locked_keep_the_suffixes_but_an_open_suffix_slot_is_still_filled():
    """Life 1 (prefix), Fire Resistance (suffix) and the crafted Suffixes Cannot Be Changed (a prefix) are held.

    Fire Resistance, on the locked side, is never removed; the metamod and Life 1 are removable with 1/2 each. The Cold
    craft adds Cold Resistance (suffix, an open slot on the locked side, 5/6) or the Cold gem-level mod (1/6).
    """
    start = amulet(roll(LIFE_1), roll(FIRE_RESIST), roll(CRAFTED, crafted=True))
    outcomes = HarvestAddRemove("cold").outcomes(META_DATA, start)

    assert pairs(outcomes) == {
        (COLD_GEM, LIFE_1): Fraction(1, 12),
        (COLD_GEM, CRAFTED): Fraction(1, 12),
        (COLD_RESIST, LIFE_1): Fraction(5, 12),
        (COLD_RESIST, CRAFTED): Fraction(5, 12),
    }
    assert outcomes.chance_all([FIRE_RESIST]) == 1
    assert outcomes.chance_all([COLD_RESIST]) == Fraction(5, 6)  # added on the locked side
    assert outcomes.chance_all([CRAFTED]) == HALF  # the metamod itself can go: it is on the unlocked side
    assert outcomes.chance_all([LIFE_1]) == HALF


def test_prefixes_locked_keep_the_prefixes_but_an_open_prefix_slot_is_still_filled():
    """Life 1 (prefix, locked), Fire Resistance (suffix) and the crafted Prefixes Cannot Be Changed (a suffix) are held."""
    start = amulet(roll(LIFE_1), roll(FIRE_RESIST), lowest(PCBC, crafted=True))
    outcomes = HarvestAddRemove("cold").outcomes(META_DATA, start)

    assert pairs(outcomes) == {
        (COLD_GEM, FIRE_RESIST): Fraction(1, 12),
        (COLD_GEM, PCBC): Fraction(1, 12),
        (COLD_RESIST, FIRE_RESIST): Fraction(5, 12),
        (COLD_RESIST, PCBC): Fraction(5, 12),
    }
    assert outcomes.chance_all([LIFE_1]) == 1
    assert outcomes.chance_all([COLD_GEM]) == Fraction(1, 6)  # a prefix added on the locked side


def test_a_full_locked_side_gives_no_room_to_add():
    """The suffix side is locked and full (three suffixes): the Speed craft (suffixes only) has nowhere to add."""
    start = amulet(roll(COLD_RESIST), roll(FIRE_RESIST), roll(RESIST_1), roll(CRAFTED, crafted=True))
    with pytest.raises(NotApplicableError, match="speed"):
        HarvestAddRemove("speed").outcomes(META_DATA, start)


def test_without_the_attack_metamod_chaos_adds_damage_or_mana_leech():
    """The control: Chaos is on Added Lightning Damage 1 (500) and Mana Leech 2 (1000) in the test tags."""
    outcomes = HarvestAddRemove("chaos").outcomes(META_DATA, amulet(roll(LIFE_1)))
    assert pairs(outcomes) == {(DAMAGE_1, LIFE_1): Fraction(1, 3), (MANA_2, LIFE_1): Fraction(2, 3)}


def test_cannot_roll_attack_keeps_an_attack_mod_out_of_the_addition():
    """Added Lightning Damage 1 carries the attack tag in the test data, so the Chaos craft adds Mana Leech 2 only."""
    start = amulet(roll(LIFE_1), lowest(NO_ATTACK, crafted=True))
    outcomes = HarvestAddRemove("chaos").outcomes(META_DATA, start)
    assert pairs(outcomes) == {(MANA_2, LIFE_1): HALF, (MANA_2, NO_ATTACK): HALF}
    assert outcomes.chance_all([DAMAGE_1]) == 0


def test_cannot_roll_attack_refuses_a_craft_whose_every_mod_is_an_attack_mod():
    """The attack tag is on Added Lightning Damage 1 and 2 and Mana Leech 1: all out of the draw."""
    start = amulet(roll(LIFE_1), lowest(NO_ATTACK, crafted=True))
    with pytest.raises(NotApplicableError, match="attack"):
        HarvestAddRemove("attack").outcomes(META_DATA, start)


def test_cannot_roll_attack_protects_no_attack_mod_from_the_removal():
    """Added Lightning Damage 1 (an attack mod) and the metamod are held; Cold is no attack mod. Both go with 1/2."""
    start = amulet(roll(DAMAGE_1), lowest(NO_ATTACK, crafted=True))
    outcomes = HarvestAddRemove("cold").outcomes(META_DATA, start)
    assert pairs(outcomes) == {
        (COLD_GEM, DAMAGE_1): Fraction(1, 12),
        (COLD_GEM, NO_ATTACK): Fraction(1, 12),
        (COLD_RESIST, DAMAGE_1): Fraction(5, 12),
        (COLD_RESIST, NO_ATTACK): Fraction(5, 12),
    }
    assert outcomes.chance_all([DAMAGE_1]) == HALF


def test_without_the_caster_metamod_critical_adds_the_gem_or_life():
    outcomes = HarvestAddRemove("critical").outcomes(META_DATA, amulet(roll(MANA_1)))
    assert pairs(outcomes) == {(GEM, MANA_1): Fraction(1, 6), (LIFE_1, MANA_1): Fraction(5, 6)}


def test_cannot_roll_caster_keeps_a_caster_mod_out_of_the_addition():
    """The Lightning gem-level mod carries the caster tag in the test data, so Critical adds Life 1 only (1000/1000)."""
    start = amulet(roll(MANA_1), lowest(NO_CASTER, crafted=True))
    outcomes = HarvestAddRemove("critical").outcomes(META_DATA, start)
    assert pairs(outcomes) == {(LIFE_1, MANA_1): HALF, (LIFE_1, NO_CASTER): HALF}
    assert outcomes.chance_all([GEM]) == 0


def test_cannot_roll_caster_refuses_a_craft_whose_every_mod_is_a_caster_mod():
    start = amulet(roll(MANA_1), lowest(NO_CASTER, crafted=True))
    with pytest.raises(NotApplicableError, match="caster"):
        HarvestAddRemove("caster").outcomes(META_DATA, start)


def test_cannot_roll_caster_protects_no_caster_mod_from_the_removal():
    """The Fire gem-level mod (a caster mod) and the metamod are held; Life is no caster mod. Six results of 1/6."""
    start = amulet(roll(FIRE_GEM), lowest(NO_CASTER, crafted=True))
    outcomes = HarvestAddRemove("life").outcomes(META_DATA, start)
    assert pairs(outcomes) == {
        (added, gone): Fraction(1, 6) for added in (LIFE_1, LIFE_2, MANA_1) for gone in (FIRE_GEM, NO_CASTER)
    }
    assert outcomes.chance_all([FIRE_GEM]) == HALF


# --- sampling ---------------------------------------------------------------------------------------


def test_a_sample_is_a_valid_item_with_the_new_mod_rolled_in_its_range():
    """Fire on Life 1 and Cold Resistance: Fire Resistance is added with 5/6, its value 6 to 11; Life 1 stays with 1/2."""
    start = amulet(roll(LIFE_1), roll(COLD_RESIST))
    outcomes = HarvestAddRemove("fire").outcomes(META_DATA, start)
    rng = random.Random(148)

    added = 0
    values = set()
    stays = 0
    count = 1000
    for _ in range(count):
        item = outcomes.sample(rng)
        item.validate(META_DATA)
        ids = [entry.mod_id for entry in item.mods]
        assert len(ids) == 2
        assert item.rarity is Rarity.RARE
        if FIRE_RESIST in ids:
            added += 1
            (entry,) = (entry for entry in item.mods if entry.mod_id == FIRE_RESIST)
            assert 6 <= entry.values[0] <= 11
            assert entry.tier == 1
            values.add(entry.values[0])
        else:
            (entry,) = (entry for entry in item.mods if entry.mod_id == FIRE_GEM)
            assert entry.values == (1,)  # a range of one integer
        if LIFE_1 in ids:
            stays += 1
            assert next(entry for entry in item.mods if entry.mod_id == LIFE_1) == roll(LIFE_1)  # kept as it was
    assert len(values) > 1
    assert values <= {6, 7, 8, 9, 10, 11}

    p = 5 / 6
    assert abs(added / count - p) <= 5 * sqrt(p * (1 - p) / count)
    assert abs(stays / count - 0.5) <= 5 * sqrt(0.25 / count)


def test_a_sampled_mod_with_two_stats_takes_each_value_inside_its_ranges():
    """Physical on two resistances: Added Lightning Damage 2 (500) or Life 2 (1000), 1/3 and 2/3; the damage rolls 1 to 1 and 14 to 15."""
    start = amulet(roll(COLD_RESIST), roll(FIRE_RESIST))
    outcomes = HarvestAddRemove("physical").outcomes(META_DATA, start)
    rng = random.Random(2026)

    damage = 0
    highs = set()
    count = 1000
    for _ in range(count):
        item = outcomes.sample(rng)
        item.validate(META_DATA)
        for entry in item.mods:
            if entry.mod_id == DAMAGE_2:
                damage += 1
                assert entry.values[0] == 1
                assert 14 <= entry.values[1] <= 15
                highs.add(entry.values[1])
            if entry.mod_id == LIFE_2:
                assert 25 <= entry.values[0] <= 39
    assert highs == {14, 15}
    p = 1 / 3
    assert abs(damage / count - p) <= 5 * sqrt(p * (1 - p) / count)


def test_the_exact_results_keep_the_new_mod_at_its_lowest_values_and_a_sample_is_seeded():
    start = amulet(roll(LIFE_1), roll(COLD_RESIST))
    outcomes = HarvestAddRemove("fire").outcomes(META_DATA, start)
    for _, result in outcomes.results:
        assert all(entry.values in {(6,), (1,), roll(LIFE_1).values, roll(COLD_RESIST).values} for entry in result.mods)
    first = [outcomes.sample(random.Random(5)) for _ in range(3)]
    assert first[0] == first[1] == first[2]


# --- the catalog -------------------------------------------------------------------------------------


def kind_members(item):
    return [action for entry in kinds() if entry.name == "harvest-add-remove" for action in entry.members(META_DATA, item)]


def test_the_catalog_lists_the_eleven_crafts_for_a_rare_item_without_influence():
    members = kind_members(amulet(roll(LIFE_1), roll(COLD_RESIST)))
    assert sorted(action.craft for action in members) == sorted(CRAFTS)
    assert len(members) == 11
    assert set(members) <= set(catalog(META_DATA, amulet(roll(LIFE_1), roll(COLD_RESIST))))


def test_the_catalog_lists_none_for_an_influenced_item():
    assert kind_members(amulet(roll(LIFE_1), influences=frozenset({Influence.SHAPER}))) == []


def test_the_kind_is_not_a_planner_kind_and_says_why():
    (entry,) = (entry for entry in kinds() if entry.name == "harvest-add-remove")
    assert entry.planner is False
    assert entry.why_not
    assert entry in kinds() and entry not in kinds(planner_only=True)


# --- the Eldritch implicit ---------------------------------------------------------------------------


def test_the_claim_that_the_craft_works_on_an_eldritch_implicit_and_a_fractured_mod_is_the_owner_s():
    """`Item` stores no implicits yet, so there is no refusal to test; the claim is what answers it."""
    rule = get_rule("harvest_augment.works_on_fractured_and_eldritch_implicit")
    assert rule.source_kind is SourceKind.OWNER
    assert "Eldritch" in rule.statement and "fractured" in rule.statement
