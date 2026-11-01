"""The Exalted Orb against the hand oracle, and what it refuses (ticket #67).

The oracle (`magic_oracle.py`) walks every draw order by hand: one draw from the pool of both sides
without the families on the item, a side of three closed once it holds three.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from actions_support import DATA, amulet, fractured_resist, roll
from magic_oracle import add_one

from crafting_system.actions import (
    ExaltedOrb,
    NotApplicableError,
    OutOfScopeError,
    catalog,
    kinds,
)
from crafting_system.items import Rarity

LEVELS = (80, 86)
LIFE, FIRE, COLD = "IncreasedLife1", "FireResist1", "ColdResist1"
FAMILY = {LIFE: "IncreasedLife", FIRE: "FireResistance", COLD: "ColdResistance"}
CRAFTED = "DexMasterItemGenerationCannotChangeSuffixes"
BY_FAMILY = lambda mod: mod.families[0]  # noqa: E731


def seen(outcomes) -> dict[frozenset[str], Fraction]:
    result: dict[frozenset[str], Fraction] = {}
    for outcome, chance in outcomes.distribution(BY_FAMILY).items():
        assert all(count == 1 for _, count in outcome)
        key = frozenset(family for family, _ in outcome)
        result[key] = result.get(key, Fraction(0)) + chance
    return result


@pytest.mark.parametrize("level", LEVELS)
def test_an_exalted_orb_on_a_rare_item_with_two_mods_matches_the_oracle(level):
    item = amulet(roll(LIFE), roll(FIRE), item_level=level)

    assert seen(ExaltedOrb().outcomes(DATA, item)) == add_one(level, ("IncreasedLife", "FireResistance"), cap=3)


def test_an_exalted_orb_adds_exactly_one_mod_and_the_chances_sum_to_one():
    item = amulet(roll(LIFE), roll(FIRE), roll(COLD), roll("ManaLeechPermyriadSuffix1"))
    shown = ExaltedOrb().outcomes(DATA, item).distribution(BY_FAMILY)

    assert sum(shown.values()) == 1
    assert all(sum(count for _, count in outcome) == 1 for outcome in shown)


def test_a_family_on_the_item_is_out_of_the_pool():
    item = amulet(roll(LIFE), roll(FIRE), roll(COLD), roll("ManaLeechPermyriadSuffix1"))
    shown = seen(ExaltedOrb().outcomes(DATA, item))

    assert not any(family in key for key in shown for family in ("IncreasedLife", "FireResistance", "ColdResistance", "ManaLeech"))


def test_a_full_side_closes_and_the_other_side_is_the_whole_pool():
    prefixes = ("IncreasedLife1", "IncreasedEnergyShield1", "AddedLightningDamage1")
    item = amulet(*(roll(mod_id) for mod_id in prefixes), roll(FIRE))
    shown = seen(ExaltedOrb().outcomes(DATA, item))

    expected = add_one(86, ("IncreasedLife", "IncreasedEnergyShield", "LightningDamage", "FireResistance"), cap=3)
    assert shown == expected
    assert all(next(iter(key)) in {"ColdResistance", "ChaosResistance", "LifeLeech", "LifeRegeneration", "LightningDamagePercentage", "LightningResistance", "ManaLeech"} for key in shown)


def test_a_fractured_mod_stays_blocks_its_family_and_fills_its_slot():
    item = amulet(fractured_resist(), roll(LIFE), roll(FIRE))
    outcomes = ExaltedOrb().outcomes(DATA, item)

    assert seen(outcomes) == add_one(86, ("LightningResistance", "IncreasedLife", "FireResistance"), cap=3)
    assert any(entry.fractured for entry in outcomes.retained.mods)


def test_an_exalted_orb_keeps_every_mod_and_the_rarity():
    item = amulet(roll(LIFE), roll(FIRE), roll("JunMaster2AllDamage2_", crafted=True))
    outcomes = ExaltedOrb().outcomes(DATA, item)

    assert outcomes.retained == item
    assert outcomes.retained.rarity is Rarity.RARE
    result = outcomes.sample(random.Random(5))
    assert {entry.mod_id for entry in item.mods} <= {entry.mod_id for entry in result.mods}
    assert len(result.mods) == len(item.mods) + 1


def test_chance_all_of_a_drawn_mod_and_two_mods_of_one_family():
    item = amulet(roll(LIFE), roll(FIRE))
    outcomes = ExaltedOrb().outcomes(DATA, item)

    assert outcomes.chance_all([COLD]) == add_one(86, ("IncreasedLife", "FireResistance"), cap=3)[frozenset({"ColdResistance"})]
    assert outcomes.chance_all(["LightningResist1", "LightningResist2"]) == 0
    assert outcomes.chance_all([LIFE, FIRE]) == 1


def test_a_normal_or_a_magic_item_is_refused_by_the_game():
    for rarity, mods in ((Rarity.NORMAL, ()), (Rarity.MAGIC, (roll(LIFE),))):
        with pytest.raises(NotApplicableError, match="rare item only"):
            ExaltedOrb().outcomes(DATA, amulet(*mods, rarity=rarity))


def test_a_corrupted_item_is_refused_by_the_game():
    with pytest.raises(NotApplicableError, match="corrupted.*Exalted Orb"):
        ExaltedOrb().outcomes(DATA, dataclasses.replace(amulet(roll(LIFE)), corrupted=True))


def test_a_full_item_is_refused_and_nothing_is_consumed():
    full = amulet(
        roll(LIFE), roll("IncreasedEnergyShield1"), roll("AddedLightningDamage1"),
        roll(FIRE), roll(COLD), roll("ManaLeechPermyriadSuffix1"),
    )  # fmt: skip

    with pytest.raises(NotApplicableError, match="no open prefix or suffix slot"):
        ExaltedOrb().outcomes(DATA, full)


def test_an_item_with_no_legal_mod_is_refused():
    # a game data that holds only the two mods on the item: every family of the pool is on the item
    data = dataclasses.replace(DATA, mods={mod_id: DATA.mods[mod_id] for mod_id in (LIFE, FIRE)})

    with pytest.raises(NotApplicableError, match="no mod of the pool is legal"):
        ExaltedOrb().outcomes(data, amulet(roll(LIFE), roll(FIRE)))


def test_a_crafted_metamod_is_in_scope_and_a_cluster_jewel_is_out_of_scope():
    assert ExaltedOrb().outcomes(DATA, amulet(roll(CRAFTED, crafted=True))).retained.metamods(DATA)
    cluster = dataclasses.replace(DATA.base_items[amulet().base_id], item_class="Jewel", domain="affliction_jewel")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, amulet().base_id: cluster})
    with pytest.raises(OutOfScopeError, match="cluster jewel"):
        ExaltedOrb().outcomes(data, amulet(roll(LIFE)))


def test_an_influenced_item_of_a_class_with_a_key_is_in_scope():
    from crafting_system.items import Influence

    item = dataclasses.replace(amulet(roll(LIFE)), influences=frozenset({Influence.SHAPER}))

    assert ExaltedOrb().outcomes(DATA, item).retained.influences == item.influences


def test_the_orb_is_named_priced_and_declared():
    action = ExaltedOrb()

    assert action.label(DATA) == "Exalted Orb"
    assert action.resources(DATA) == {"Exalted Orb": 1}
    assert action.reads(DATA).block_invariant is False
    adds = action.adds(DATA, amulet())
    assert adds.draws and adds.keeps_crafted and adds.named == frozenset()


def test_the_kind_is_in_the_catalog_for_a_rare_item_only_and_not_a_planner_kind():
    assert catalog(DATA, amulet(roll(LIFE))).count(ExaltedOrb()) == 1
    assert ExaltedOrb() not in catalog(DATA, amulet(rarity=Rarity.NORMAL))
    assert ExaltedOrb() not in catalog(DATA, amulet(roll(LIFE)), planner_only=True)
    assert {entry.name: entry.planner for entry in kinds()}["exalted-orb"] is False
