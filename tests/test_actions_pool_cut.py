"""The tier cut in the pool (ticket #275, ADR-0040 and ADR-0042), on the fixture amulet and on toy tier tables.

"Done when": at 0 strands without a Foulborn orb every pool equals today's; the pool keeps the `K` highest tiers of each tier table by
the integer formula (the numbers the sources publish are `test_strands_cut.py`); a property test shows reading 1 keeps each family's total
weight. Also here: the cut counts what the draw can roll (the level gate and an essence's cap), is made before the item's own mods
block their families, and is made only when the caller gives the pool a `Cut`; the declaration `strand_use` that gives it (`Action.cut_of`); and no action that does not
use strands names a strand claim.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from actions_support import DATA, amulet, roll

from crafting_system.actions import Adds, AlterationOrb, ChaosOrb, ExaltedOrb, RegalOrb, build_pool
from crafting_system.actions.cut import PLAN_READING, Cut, WeightReading, cut_weights, rollable_tiers
from crafting_system.actions.pool import pool_candidates
from crafting_system.data import Weight
from crafting_system.items import Rarity
from crafting_system.rules import get_rule

READINGS = tuple(WeightReading)
FAMILY = "LightningResistance"  # eight tiers at levels 1, 13, 25, 37, 49, 60, 72, 84; every tier weighs 1000
DAMAGE = "LightningDamage"  # nine tiers (levels 3 to 76); the highest weighs 250, the others 500: 4250 in all


def pool_mods(pool):
    return [entry for family in pool for entry in family.mods]


def family(pool, name):
    return next(entry for entry in pool if entry.family == name)


def ids_of(pool, name):
    return [entry.mod.id for entry in family(pool, name).mods]


def weights_of(pool, name):
    return {entry.mod.id: entry.weight for entry in family(pool, name).mods}


def totals(pool):
    return {entry.family: entry.weight for entry in pool}


# --- 0 strands, no Foulborn orb: today's pool ---------------------------------------------------------------------------------


@pytest.mark.parametrize("level", [74, 78, 83, 84, 86])
def test_at_0_strands_without_a_foulborn_orb_every_pool_equals_todays(level):
    item = amulet(item_level=level)

    todays = build_pool(DATA, item)

    assert build_pool(DATA, item, cut=Cut(0)) == todays
    assert build_pool(DATA, item, cut=Cut.of(item)) == todays
    assert pool_candidates(DATA, item, cut=Cut(0)) is pool_candidates(DATA, item)  # the same cached pool, not a copy


@pytest.mark.parametrize("reading", READINGS)
def test_the_reading_does_not_matter_when_the_cut_cannot_remove_a_tier(reading):
    assert build_pool(DATA, amulet(), cut=Cut(0, reading=reading)) == build_pool(DATA, amulet())


def test_todays_fixture_pool_is_the_one_the_pool_tests_pin():
    pool = build_pool(DATA, amulet(), cut=Cut(0))

    assert {entry.family: (entry.weight, len(entry.mods)) for entry in pool} == {
        "GlobalDamageTypeGemLevel": (1000, 5),
        "GlobalSkillGemLevel": (50, 1),
        "IncreasedEnergyShield": (1000, 1),
        "IncreasedLife": (3000, 3),
        "ItemFoundRarityIncreasePrefix": (4000, 4),
        "LightningDamage": (4250, 9),
        "ChaosResistance": (1500, 6),
        "ColdResistance": (1000, 1),
        "FireResistance": (1000, 1),
        "LifeLeech": (1750, 3),
        "LifeRegeneration": (1000, 1),
        "LightningDamagePercentage": (2500, 5),
        "LightningResistance": (8000, 8),
        "ManaLeech": (2000, 2),
    }


def test_the_count_on_the_item_alone_does_not_cut_the_pool_so_a_fossil_on_a_stranded_item_draws_from_the_ordinary_pool():
    stranded = amulet(item_level=86)
    stranded = dataclasses.replace(stranded, memory_strands=60)

    assert build_pool(DATA, stranded) == build_pool(DATA, amulet())
    assert build_pool(DATA, stranded, cut=Cut.of(stranded)) != build_pool(DATA, amulet())


# --- which tiers stay ---------------------------------------------------------------------------------------------------------


def test_82_strands_keep_the_two_highest_tiers_of_the_eight_tier_table_and_81_keep_three():
    item = amulet(item_level=86)

    assert ids_of(build_pool(DATA, item, cut=Cut(82)), FAMILY) == ["LightningResist7", "LightningResist8"]
    assert ids_of(build_pool(DATA, item, cut=Cut(81)), FAMILY) == ["LightningResist6", "LightningResist7", "LightningResist8"]


def test_the_kept_tiers_are_the_k_best_of_the_tiers_the_draw_can_roll_not_tiers_one_to_k_of_the_whole_table():
    # At item level 83 LightningResist8 (level 84) cannot roll, so the table has 7 tiers and 82 strands keep two: 7 and 6.
    low = amulet(item_level=83)

    pool = build_pool(DATA, low, cut=Cut(82))

    assert ids_of(pool, FAMILY) == ["LightningResist6", "LightningResist7"]
    assert rollable_tiers(7, 82) == 2


def test_an_essences_level_cap_shrinks_the_table_the_cut_counts():
    # A cap of 70 leaves tiers at levels 1, 13, 25, 37, 49, 60: six tiers, so 82 strands keep two.
    pool = build_pool(DATA, amulet(item_level=86), max_level=70, cut=Cut(82))

    assert ids_of(pool, FAMILY) == ["LightningResist5", "LightningResist6"]
    assert rollable_tiers(6, 82) == 2
    assert ids_of(build_pool(DATA, amulet(item_level=86), max_level=70, cut=Cut(0)), FAMILY) == [f"LightningResist{n}" for n in range(1, 7)]


def test_a_foulborn_orb_on_an_item_with_no_strands_keeps_five_of_eight_tiers_the_cut_of_eleven_strands():
    item = amulet(item_level=86)

    foulborn = build_pool(DATA, item, cut=Cut(0, foulborn=True))

    assert ids_of(foulborn, FAMILY) == [f"LightningResist{n}" for n in range(4, 9)]
    assert foulborn == build_pool(DATA, item, cut=Cut(11))


def test_a_foulborn_orb_on_a_stranded_item_cuts_like_thirty_strands_more():
    item = amulet(item_level=86)

    for strands in (1, 10, 40, 70):
        assert build_pool(DATA, item, cut=Cut(strands, foulborn=True)) == build_pool(DATA, item, cut=Cut(strands + 30))


def test_a_table_with_a_single_tier_is_never_cut():
    one = {entry.family: entry.mods for entry in build_pool(DATA, amulet(), cut=Cut(100, foulborn=True))}

    assert len(one["ColdResistance"]) == 1 and len(one["FireResistance"]) == 1
    assert len(one["GlobalSkillGemLevel"]) == 1


def test_the_cut_leaves_the_order_of_the_families_and_of_the_mods_as_in_the_data():
    ordinary = [entry.family for entry in build_pool(DATA, amulet())]
    cut = build_pool(DATA, amulet(), cut=Cut(60))

    assert [entry.family for entry in cut] == ordinary
    for entry in cut:
        order = [mod.mod.id for mod in entry.mods]
        assert order == sorted(order, key=lambda mod_id: list(DATA.mods).index(mod_id))


def test_the_cut_is_made_before_the_mods_on_the_item_block_their_families():
    # A family on the item leaves the pool whole; the tables of the other families are cut as they were.
    bare = build_pool(DATA, amulet(), cut=Cut(82))
    holding = build_pool(DATA, amulet(roll("LightningResist1"), roll("AddedLightningDamage1")), cut=Cut(82))

    assert [entry for entry in bare if entry.family not in {FAMILY, DAMAGE}] == list(holding)


def test_a_cut_pool_is_cached_apart_from_the_ordinary_one_and_from_other_cuts():
    item = amulet(item_level=86)

    one = pool_candidates(DATA, item, cut=Cut(82))
    two = pool_candidates(DATA, item, cut=Cut(82))
    other = pool_candidates(DATA, item, cut=Cut(81))

    assert one is two
    assert one != other
    assert one != pool_candidates(DATA, item)
    assert pool_candidates(DATA, item) == pool_candidates(DATA, item, cut=Cut(0))


# --- what the kept tiers weigh ------------------------------------------------------------------------------------------------


def test_the_plan_reads_the_claim_that_the_sheet_fit_settled_and_the_three_readings_are_named_for_the_adr():
    assert get_rule("memory_strands.weights_of_kept_tiers").value["reading"] == "refactored"
    assert PLAN_READING is WeightReading.REFACTORED
    assert Cut(5).reading is PLAN_READING
    assert [reading.value for reading in READINGS] == ["redistribution", "refactored", "delete_only"]  # readings 1, 2 and 3 of ADR-0042


def test_the_example_of_the_adr_gives_500_and_1000_then_200_and_400_then_100_and_200():
    # Four tiers T1 to T4 of weights 100, 200, 400, 800; 2 strands (D = 305) keep the two highest.
    data = tier_table_data([(40, 100), (30, 200), (20, 400), (10, 800)])
    item = amulet(item_level=86)
    assert rollable_tiers(4, 2) == 2

    kept = {
        reading: sorted(weights_of(build_pool(data, item, cut=Cut(2, reading=reading)), "IncreasedLife").values())
        for reading in READINGS
    }

    assert kept[WeightReading.REDISTRIBUTION] == [500, 1000]
    assert kept[WeightReading.REFACTORED] == [200, 400]
    assert kept[WeightReading.DELETE_ONLY] == [100, 200]
    assert sum(kept[WeightReading.REDISTRIBUTION]) == 1500  # 100 + 200 + 400 + 800: the type keeps its whole weight


def test_the_fixture_damage_type_under_the_three_readings_at_50_strands():
    # 9 tiers at 50 strands: D = 545, floor(1600 / 545) + 1 = 3 tiers stay: levels 76 (250), 64 and 52 (500 each); the type weighs 4250.
    item = amulet(item_level=86)
    names = ["AddedLightningDamage9", "AddedLightningDamage8", "AddedLightningDamage7"]
    expected = {
        WeightReading.REDISTRIBUTION: {"AddedLightningDamage7": 1700, "AddedLightningDamage8": 1700, "AddedLightningDamage9": 850},
        WeightReading.REFACTORED: {"AddedLightningDamage7": 1500, "AddedLightningDamage8": 1500, "AddedLightningDamage9": 750},
        WeightReading.DELETE_ONLY: {"AddedLightningDamage7": 500, "AddedLightningDamage8": 500, "AddedLightningDamage9": 250},
    }
    assert rollable_tiers(9, 50) == 3

    for reading, weights in expected.items():
        pool = build_pool(DATA, item, cut=Cut(50, reading=reading))
        assert weights_of(pool, DAMAGE) == weights, reading
        assert sorted(weights_of(pool, DAMAGE)) == sorted(names)


def test_with_equal_tier_weights_redistribution_and_the_refactored_weight_are_the_same_pool():
    item = amulet(item_level=86)  # the eight resistance tiers all weigh 1000: 82 strands keep 2, each kept weighs 4000 under both

    redistribution = build_pool(DATA, item, cut=Cut(82, reading=WeightReading.REDISTRIBUTION))
    refactored = build_pool(DATA, item, cut=Cut(82, reading=WeightReading.REFACTORED))
    delete_only = build_pool(DATA, item, cut=Cut(82, reading=WeightReading.DELETE_ONLY))

    assert weights_of(redistribution, FAMILY) == weights_of(refactored, FAMILY) == {"LightningResist7": 4000, "LightningResist8": 4000}
    assert weights_of(delete_only, FAMILY) == {"LightningResist7": 1000, "LightningResist8": 1000}


def test_weights_stay_exact_fractions():
    pool = build_pool(DATA, amulet(), cut=Cut(50, reading=WeightReading.REDISTRIBUTION))

    assert all(type(entry.weight) is Fraction for entry in pool_mods(pool))
    assert Fraction(850) in {entry.weight for entry in pool_mods(pool)}  # 250 * 4250 / 1250, not a rounded 849.99


# --- the property: reading 1 keeps each family's total weight -----------------------------------------------------------------


@pytest.mark.parametrize("level", [74, 78, 83, 86])
def test_reading_1_keeps_the_total_weight_of_every_family_at_every_count_with_and_without_a_foulborn_orb(level):
    item = amulet(item_level=level)
    ordinary = totals(build_pool(DATA, item))

    for foulborn in (False, True):
        for strands in range(0, 101):
            cut = build_pool(DATA, item, cut=Cut(strands, foulborn, WeightReading.REDISTRIBUTION))
            assert totals(cut) == ordinary, (strands, foulborn)


def random_tier_data(rng: random.Random):
    """The fixture amulet's life, resistance and damage types with random levels and random weights (ties in level included)."""
    mods = dict(DATA.mods)
    for name in ("IncreasedLife", FAMILY, DAMAGE):
        for mod in [mod for mod in DATA.mods.values() if mod.families == (name,)]:
            mods[mod.id] = dataclasses.replace(
                mod,
                spawn_weights=(Weight("amulet", rng.choice([1, 2, 3, 5, 100, 250, 1000, 7777])), Weight("default", 0)),
                required_level=rng.choice(range(1, 86)),
            )
    return dataclasses.replace(DATA, mods=mods)


def test_reading_1_keeps_each_familys_total_weight_on_random_tier_weights_and_levels():
    rng = random.Random(275)
    for _ in range(40):
        data = random_tier_data(rng)
        item = amulet(item_level=rng.choice([76, 80, 86]))
        ordinary = totals(build_pool(data, item))
        for strands in (0, 1, 2, 5, 11, 30, 50, 81, 82, 100):
            for foulborn in (False, True):
                cut = build_pool(data, item, cut=Cut(strands, foulborn, WeightReading.REDISTRIBUTION))
                assert totals(cut) == ordinary, (strands, foulborn)


def test_the_other_readings_do_not_keep_the_total_of_a_type_that_lost_tiers_of_unequal_weight():
    item = amulet(item_level=86)
    ordinary = totals(build_pool(DATA, item))

    refactored = totals(build_pool(DATA, item, cut=Cut(50, reading=WeightReading.REFACTORED)))
    delete_only = totals(build_pool(DATA, item, cut=Cut(50, reading=WeightReading.DELETE_ONLY)))

    assert refactored[DAMAGE] == 3750 and delete_only[DAMAGE] == 1250  # 4250 before
    assert refactored[DAMAGE] != ordinary[DAMAGE] != delete_only[DAMAGE]
    assert all(delete_only[name] <= ordinary[name] for name in ordinary)


@pytest.mark.parametrize("reading", READINGS)
def test_the_chosen_tier_inside_a_type_has_the_same_odds_under_every_reading(reading):
    item = amulet(item_level=86)

    pool = build_pool(DATA, item, cut=Cut(50, reading=reading))
    kept = weights_of(pool, DAMAGE)

    assert kept["AddedLightningDamage7"] == kept["AddedLightningDamage8"] == 2 * kept["AddedLightningDamage9"]  # 500 : 500 : 250


# --- how a toy table is cut ---------------------------------------------------------------------------------------------------


def tier_table_data(levels_and_weights):
    """The fixture data with the type IncreasedLife replaced by tiers at these (required level, weight) pairs, highest level first."""
    template = DATA.mods["IncreasedLife1"]
    mods = {mod_id: mod for mod_id, mod in DATA.mods.items() if mod.families != ("IncreasedLife",)}
    for number, (level, weight) in enumerate(levels_and_weights, start=1):
        mod_id = f"IncreasedLifeToy{number}"
        mods[mod_id] = dataclasses.replace(
            template, id=mod_id, required_level=level, spawn_weights=(Weight("amulet", weight), Weight("default", 0))
        )
    return dataclasses.replace(DATA, mods=mods)


def test_mods_that_tie_on_the_required_level_share_a_tier_and_stay_or_go_together():
    # Levels 40, 30, 30, 20 are three tiers, not four. At 22 strands (D = 405) three tiers keep one and four would keep two:
    # only the level 40 mod stays. At 2 strands three tiers keep two, so both mods of the shared tier stay and the level 20 mod goes.
    data = tier_table_data([(40, 100), (30, 200), (30, 300), (20, 400)])
    assert (rollable_tiers(3, 22), rollable_tiers(4, 22)) == (1, 2)
    assert rollable_tiers(3, 2) == 2

    one = build_pool(data, amulet(item_level=86), cut=Cut(22, reading=WeightReading.DELETE_ONLY))
    two = build_pool(data, amulet(item_level=86), cut=Cut(2, reading=WeightReading.DELETE_ONLY))

    assert ids_of(one, "IncreasedLife") == ["IncreasedLifeToy1"]
    assert ids_of(two, "IncreasedLife") == ["IncreasedLifeToy1", "IncreasedLifeToy2", "IncreasedLifeToy3"]


def test_a_mod_type_that_has_mods_on_both_sides_is_cut_as_two_tier_tables():
    # A table is a mod type of one generation type: the prefix tiers (levels 5, 11, 18) and the toy suffix tiers (50, 40) of one
    # mod type are two tables. At 82 strands each keeps one tier; counted as one table of five tiers they would keep two.
    template = DATA.mods["IncreasedLife1"]
    mods = dict(DATA.mods)
    for number, level in enumerate((50, 40), start=1):
        mod_id = f"IncreasedLifeSuffixToy{number}"
        mods[mod_id] = dataclasses.replace(
            template,
            id=mod_id,
            generation_type="suffix",
            families=("IncreasedLifeSuffixToy",),
            required_level=level,
            spawn_weights=(Weight("amulet", 1000), Weight("default", 0)),
        )
    data = dataclasses.replace(DATA, mods=mods)
    assert (rollable_tiers(3, 82), rollable_tiers(2, 82), rollable_tiers(5, 82)) == (1, 1, 2)

    pool = build_pool(data, amulet(item_level=86), cut=Cut(82))

    assert ids_of(pool, "IncreasedLife") == ["IncreasedLife3"]
    assert ids_of(pool, "IncreasedLifeSuffixToy") == ["IncreasedLifeSuffixToy1"]


def test_cut_weights_returns_the_pairs_unchanged_when_the_cut_cannot_remove_a_tier():
    pairs = [(mod, Fraction(index + 1)) for index, mod in enumerate(list(DATA.mods.values())[:12])]

    assert cut_weights(pairs, Cut(0)) == tuple(pairs)


# --- the contract flag --------------------------------------------------------------------------------------------------------


def test_the_cut_is_declared_by_strand_use_and_adds_has_no_second_flag():
    # ticket #276 moved the flag of #275 (`Adds.cuts`) into `Action.strand_use`: one declaration, not two
    assert not hasattr(Adds(), "cuts")
    item = amulet(rarity=Rarity.RARE)
    for action in (ChaosOrb(), AlterationOrb(), RegalOrb(), ExaltedOrb()):
        assert action.strand_use(DATA).cuts is True, action
        assert action.cut_of(DATA, item) == Cut(0) and not action.cut_of(DATA, item).active, action  # 0 strands: a cut that keeps every tier
        assert action.cut_of(DATA, dataclasses.replace(item, memory_strands=40)) == Cut(40), action


def test_an_action_that_does_not_use_strands_names_no_strand_claim():
    # The claims of the cut sit in `cut.py`; an action that only builds a pool does not import them, so no answer of B1 to B4 lists
    # the (approximate) strand claims it does not use.
    for action in (ChaosOrb(), AlterationOrb(), RegalOrb(), ExaltedOrb()):
        claims = action.claims(DATA)
        assert not {claim for claim in claims if claim.startswith(("memory_strands.", "foulborn."))}, action
        assert "affix_pool.no_memory_strands" not in claims


def test_the_module_that_holds_the_cut_names_the_claims_it_reads():
    import crafting_system.actions.cut as cut_module
    from crafting_system.rules import Rule

    held = {value.id for value in vars(cut_module).values() if isinstance(value, Rule)}

    assert {
        "affix_pool.no_memory_strands",
        "memory_strands.rollable_tiers",
        "memory_strands.weights_of_kept_tiers",
        "memory_strands.cull_counts_eligible_tiers",
        "memory_strands.zero_is_no_cull",
        "memory_strands.cut_uses_strands_before_spend",
        "foulborn.on_stranded_item",
        "foulborn.bonus_is_added_to_the_strand_denominator",
        "foulborn.zero_strand_cut_matches_eleven_strands",
    } <= held
