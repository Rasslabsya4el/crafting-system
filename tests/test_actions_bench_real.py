"""The bench on the real 3.29.3.3 dump: all 732 crafts, and the crafts the B1 routes finish with (ticket #56).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there; CI fetches it (ticket #165), so they run there.
"""

import random
import re

import pytest
from targets_support import EXAMPLES

from crafting_system.actions import (
    BenchCraft,
    CurrencyCost,
    NotApplicableError,
    RemoveCraftedMods,
    bench_crafts,
)
from crafting_system.data import MissingDataError, load_game_data
from crafting_system.items import ExplicitMod, Item, Rarity

BOOTS = "Metadata/Items/Armours/Boots/BootsInt1"
SHRIEKING_SPITE = "Metadata/Items/Currency/CurrencyEssenceSpite3"
SIDES = {"prefix", "suffix"}


@pytest.fixture(scope="module")
def data():
    try:
        return load_game_data()
    except MissingDataError as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


def listed(data, item_class, wanted):
    """The crafts offered for `item_class` whose mod satisfies `wanted`, as (mod id, side, level, cost, tier) rows."""
    return [
        (
            craft.mod_id,
            data.mods[craft.mod_id].generation_type,
            data.mods[craft.mod_id].required_level,
            tuple((entry.currency, entry.count) for entry in craft.cost(data)),
            craft.option(data).bench_tier,
        )
        for craft in bench_crafts(data)
        if item_class in craft.option(data).item_classes and wanted(data.mods[craft.mod_id])
    ]


def has_family(*families):
    return lambda mod: bool(set(mod.families) & set(families))


def rolled(data, mod_id, **flags):
    mod = data.mods[mod_id]
    return ExplicitMod(
        mod_id, 1, tuple(min(stat.min, stat.max) for stat in mod.stats), crafted=mod.domain == "crafted", **flags
    )


# --- every option --------------------------------------------------------------------------------


def test_the_bench_has_732_crafts_each_with_a_crafted_mod_a_side_and_a_priced_option(data):
    crafts = bench_crafts(data)

    assert len(crafts) == 732 and len({craft.mod_id for craft in crafts}) == 732
    sides = {data.mods[craft.mod_id].generation_type for craft in crafts}
    assert sides == SIDES
    assert {data.mods[craft.mod_id].domain for craft in crafts} == {"crafted"}
    assert sum(data.mods[craft.mod_id].generation_type == "prefix" for craft in crafts) == 408
    for craft in crafts:
        cost = craft.cost(data)
        assert cost and all(entry.count > 0 and entry.currency for entry in cost)


def test_the_five_metamods_are_crafts_with_their_costs_on_all_24_equipment_classes(data):
    expected = {
        "StrMasterItemGenerationCannotChangePrefixes": ("suffix", "Divine Orb", 2),
        "DexMasterItemGenerationCannotChangeSuffixes": ("prefix", "Divine Orb", 2),
        "StrIntMasterItemGenerationCanHaveMultipleCraftedMods": ("suffix", "Divine Orb", 2),
        "IntMasterItemGenerationCannotRollAttackAffixes": ("suffix", "Divine Orb", 1),
        "StrDexMasterItemGenerationCannotRollCasterAffixes": ("suffix", "Divine Orb", 1),
    }
    for mod_id, (side, currency, count) in expected.items():
        craft = BenchCraft(mod_id)
        assert data.mods[mod_id].generation_type == side
        assert craft.cost(data) == (CurrencyCost(currency, count),)
        assert len(craft.option(data).item_classes) == 24 and craft.option(data).bench_tier == 0


def test_remove_crafted_mods_costs_one_orb_of_scouring_on_24_classes(data):
    assert RemoveCraftedMods().cost(data) == (CurrencyCost("Orb of Scouring", 1),)
    assert len(RemoveCraftedMods().option(data).item_classes) == 24


@pytest.mark.parametrize(
    ("mod_id", "currency", "count"),
    [
        ("JunMaster2AllDamage2_", "Chaos Orb", 4),
        ("JunMaster2AllDamage3", "Exalted Orb", 4),
        ("EinharMasterAvoidElementalAilments2_", "Chaos Orb", 2),
        ("EinharMasterAllAttributes1", "Orb of Chance", 3),
        ("JunMaster2LocalIncreaseSocketedSupportGemLevel2", "Exalted Orb", 4),
    ],
)
def test_a_sample_of_costs_equals_the_excerpts_of_the_data(data, mod_id, currency, count):
    assert BenchCraft(mod_id).cost(data) == (CurrencyCost(currency, count),)


# --- the crafts the B1 routes finish with ------------------------------------------------------------


def test_r10_the_avoid_elemental_ailments_craft_on_boots_has_two_tiers(data):
    rows = listed(data, "Boots", has_family("AvoidElementalStatusAilments"))

    assert rows == [
        ("EinharMasterAvoidElementalAilments1", "suffix", 30, (("Chaos Orb", 1),), 1),
        ("EinharMasterAvoidElementalAilments2_", "suffix", 60, (("Chaos Orb", 2),), 2),
    ]


def test_r10_the_craft_lands_in_the_open_suffix_of_the_boots_the_route_waits_for(data):
    boots = Item.build(
        data,
        base_id=BOOTS,
        item_level=86,
        rarity=Rarity.RARE,
        mods=(
            rolled(data, "MovementVelocity5", fractured=True),
            rolled(data, "IncreasedLife9"),
            rolled(data, data.essences[SHRIEKING_SPITE].mod_for("Boots")),
        ),
    )

    outcomes = BenchCraft("EinharMasterAvoidElementalAilments2_").outcomes(data, boots)

    assert outcomes.chance_all(["MovementVelocity5", "IncreasedLife9", "EinharMasterAvoidElementalAilments2_"]) == 1
    finished = outcomes.sample(random.Random(1))
    assert len(finished.mods) == 4 and len(finished.crafted_mods) == 1
    full = boots.add_mod(data, rolled(data, "ColdResist1")).add_mod(data, rolled(data, "FireResist1"))
    with pytest.raises(NotApplicableError, match="no free suffix slot"):
        BenchCraft("EinharMasterAvoidElementalAilments2_").outcomes(data, full)


def test_r11_the_resistance_and_attribute_crafts_on_a_helmet_are_47_suffixes(data):
    wanted = lambda mod: mod.generation_type == "suffix" and re.search(  # noqa: E731
        r"Resistance|Strength|Dexterity|Intelligence|Attributes", mod.text or ""
    )

    rows = listed(data, "Helmet", wanted)

    assert len(rows) == 47
    by_id = {row[0]: row for row in rows}
    assert by_id["HelenaMasterFireResist1"][2:4] == (15, (("Orb of Transmutation", 1),))
    assert by_id["EinharMasterFireResist3_"][2:4] == (50, (("Chaos Orb", 3),))
    assert by_id["EinharMasterStrength3"][2:4] == (40, (("Chaos Orb", 2),))
    assert by_id["EinharMasterAllAttributes2"][2:4] == (50, (("Orb of Chance", 6),))
    assert by_id["JunMaster2StrengthAndDexterity3_"][2:4] == (81, (("Chaos Orb", 4),))
    assert by_id["JunMaster2FireAndChaosDamageResistance3"][2:4] == (81, (("Chaos Orb", 3),))


def test_r05_the_strength_and_all_attributes_crafts_on_a_ring(data):
    rows = listed(data, "Ring", has_family("AllAttributes", "Strength"))

    assert [(row[0], row[2], row[3]) for row in rows if len(data.mods[row[0]].families) == 1] == [
        ("HelenaMasterStrength1", 15, (("Orb of Augmentation", 1),)),
        ("EinharMasterStrength2", 20, (("Orb of Alchemy", 2),)),
        ("EinharMasterStrength3", 40, (("Chaos Orb", 2),)),
        ("EinharMasterAllAttributes1", 30, (("Orb of Chance", 3),)),
        ("EinharMasterAllAttributes2", 50, (("Orb of Chance", 6),)),
    ]
    assert {row[1] for row in rows} == {"suffix"}


def test_r13_the_damage_prefixes_on_a_belt_are_the_two_families_of_the_target_file(data):
    rows = listed(data, "Belt", lambda mod: mod.generation_type == "prefix" and "damage" in (mod.text or "").lower())

    assert [(row[0], row[2], row[3]) for row in rows] == [
        ("EinharMasterWeaponElementalDamage1_", 30, (("Orb of Alteration", 6),)),
        ("EinharMasterWeaponElementalDamage2", 50, (("Orb of Alchemy", 4),)),
        ("JunMaster2AllDamage2_", 72, (("Chaos Orb", 4),)),
        ("JunMaster2AllDamage3", 81, (("Exalted Orb", 4),)),
    ]
    text = (EXAMPLES / "r13-life-resist-belt.yaml").read_text(encoding="utf-8")
    assert {family for row in rows for family in data.mods[row[0]].families} == {
        "AllDamage",
        "IncreasedWeaponElementalDamagePercent",
    }
    assert all(family in text for family in ("AllDamage", "IncreasedWeaponElementalDamagePercent"))


def test_r14_the_finishing_crafts_on_a_bow(data):
    support = listed(data, "Bow", has_family("IncreaseSpecificSocketedGemLevel"))
    chaos_dot = listed(data, "Bow", lambda mod: "Chaos Damage over Time Multiplier" in (mod.text or ""))

    assert support == [
        ("JunMaster2LocalIncreaseSocketedSupportGemLevel1", "prefix", 60, (("Chaos Orb", 8),), 1),
        ("JunMaster2LocalIncreaseSocketedSupportGemLevel2", "prefix", 80, (("Exalted Orb", 4),), 2),
    ]
    assert [(row[0], row[1], row[2], row[3]) for row in chaos_dot] == [
        ("JunMaster2ChaosDamageOverTimeMultiplier1_", "suffix", 60, (("Orb of Alteration", 8),)),
        ("JunMaster2ChaosDamageOverTimeMultiplier2", "suffix", 72, (("Orb of Alchemy", 2),)),
        ("JunMaster2ChaosDamageOverTimeMultiplier3", "suffix", 81, (("Chaos Orb", 4),)),
    ]


def test_r14_a_bow_of_item_level_78_takes_the_finishing_crafts_of_the_route(data):
    bow = next(base for base in data.base_items.values() if base.item_class == "Bow" and "Thicket" in base.name)
    item = Item.build(data, base_id=bow.id, item_level=78, rarity=Rarity.RARE, mods=(rolled(data, "IncreasedLife1"),))

    for mod_id in (
        "JunMaster2LocalIncreaseSocketedSupportGemLevel2",
        "JunMaster2ChaosDamageOverTimeMultiplier3",
    ):
        assert BenchCraft(mod_id).outcomes(data, item).chance_all([mod_id]) == 1
