"""The pool of candidates for one more draw: which mods, grouped by family, with which weight."""

import dataclasses
from fractions import Fraction

import pytest
from actions_oracle import FAMILIES, TAGGED
from actions_support import AMULET, DATA, amulet, roll

from crafting_system.actions import OutOfScopeError, PoolFamily, build_pool
from crafting_system.data import Weight
from crafting_system.items import Side

LIGHTNING = "lightning"


def pool_mods(pool):
    return [entry for family in pool for entry in family.mods]


def test_the_guides_weight_shares_come_out_of_the_pool_builder():
    # ADR-0020: the guide's numbers are single-draw weight shares of the lightning-tagged mods.
    pool = build_pool(DATA, amulet())

    tagged = [e for e in pool_mods(pool) if LIGHTNING in e.mod.implicit_tags]
    tagged_total = sum(e.weight for e in tagged)
    without_resistance = sum(
        e.weight for f in pool if f.family != "LightningResistance" for e in f.mods if e in tagged
    )

    assert tagged_total == 14_950
    assert Fraction(200, tagged_total) == Fraction(200, 14_950)  # 1.338%
    assert round(float(Fraction(200, 14_950)) * 100, 3) == 1.338
    assert without_resistance == 6_950
    assert round(float(Fraction(200, 6_950)) * 100, 2) == 2.88


def families_of(pool):
    return {f.family: (f.side, f.weight, len(f.mods)) for f in pool}


def test_the_fixture_amulet_pool_at_item_level_86_has_these_fourteen_families():
    pool = build_pool(DATA, amulet())

    assert families_of(pool) == {
        "GlobalDamageTypeGemLevel": (Side.PREFIX, 1000, 5),
        "GlobalSkillGemLevel": (Side.PREFIX, 50, 1),
        "IncreasedEnergyShield": (Side.PREFIX, 1000, 1),
        "IncreasedLife": (Side.PREFIX, 3000, 3),  # three mods of 1000, at levels 5, 11 and 18
        "ItemFoundRarityIncreasePrefix": (Side.PREFIX, 4000, 4),
        "LightningDamage": (Side.PREFIX, 4250, 9),
        "ChaosResistance": (Side.SUFFIX, 1500, 6),
        "ColdResistance": (Side.SUFFIX, 1000, 1),
        "FireResistance": (Side.SUFFIX, 1000, 1),
        "LifeLeech": (Side.SUFFIX, 1750, 3),
        "LifeRegeneration": (Side.SUFFIX, 1000, 1),
        "LightningDamagePercentage": (Side.SUFFIX, 2500, 5),
        "LightningResistance": (Side.SUFFIX, 8000, 8),
        "ManaLeech": (Side.SUFFIX, 2000, 2),
    }
    assert all(isinstance(f, PoolFamily) for f in pool)
    assert all(type(entry.weight) is Fraction for entry in pool_mods(pool))


def test_item_level_74_has_no_gem_level_mod():
    pool = build_pool(DATA, amulet(item_level=74))

    assert not {"GlobalDamageTypeGemLevel", "GlobalSkillGemLevel"} & {f.family for f in pool}


def test_a_mod_whose_required_level_equals_the_item_level_is_in_the_pool():
    ids = lambda level: {e.mod.id for e in pool_mods(build_pool(DATA, amulet(item_level=level)))}  # noqa: E731

    assert "LightningResist8" not in ids(83)
    assert "LightningResist8" in ids(84)


def test_a_family_on_the_item_leaves_the_pool_with_all_its_mods():
    pool = build_pool(DATA, amulet(roll("LightningResist1"), roll("AddedLightningDamage1")))

    names = {f.family for f in pool}
    assert "LightningResistance" not in names and "LightningDamage" not in names
    assert len(pool) == 12  # fourteen families less the two on the item


def test_an_implicit_of_the_base_does_not_block_its_family():
    base = DATA.base_items[AMULET]
    blocking = dataclasses.replace(
        DATA,
        base_items={**DATA.base_items, AMULET: dataclasses.replace(base, implicits=("LifeRegeneration1",))},
    )

    pool = build_pool(blocking, amulet())

    assert "LifeRegeneration" in {f.family for f in pool}


def test_a_generation_weight_scales_the_weight_exactly():
    mod = DATA.mods["IncreasedLife1"]
    scaled = dataclasses.replace(mod, generation_weights=(Weight("amulet", 33),))
    data = dataclasses.replace(DATA, mods={**DATA.mods, mod.id: scaled})

    family = next(f for f in build_pool(data, amulet()) if f.family == "IncreasedLife")

    # IncreasedLife1 is scaled to 33/100 of 1000; IncreasedLife2 and IncreasedLife3 keep their 1000.
    assert family.weight == Fraction(1000 * 33, 100) + 1000 + 1000


def test_a_candidate_with_two_families_is_out_of_scope():
    mod = DATA.mods["IncreasedLife1"]
    two = dataclasses.replace(mod, families=("IncreasedLife", "SomethingElse"))
    data = dataclasses.replace(DATA, mods={**DATA.mods, mod.id: two})

    with pytest.raises(OutOfScopeError, match="IncreasedLife1.*2 families"):
        build_pool(data, amulet())


def test_a_candidate_without_a_family_is_out_of_scope():
    mod = DATA.mods["IncreasedLife1"]
    none = dataclasses.replace(mod, families=())
    data = dataclasses.replace(DATA, mods={**DATA.mods, mod.id: none})

    with pytest.raises(OutOfScopeError, match="0 families"):
        build_pool(data, amulet())


def test_a_family_spread_over_both_sides_is_out_of_scope():
    mod = DATA.mods["IncreasedLife1"]
    flipped = dataclasses.replace(mod, id="IncreasedLifeOtherSide", generation_type="suffix")
    data = dataclasses.replace(DATA, mods={**DATA.mods, flipped.id: flipped})

    with pytest.raises(OutOfScopeError, match="both sides"):
        build_pool(data, amulet())


@pytest.mark.parametrize("level", [80, 84, 86])
def test_the_hand_typed_oracle_table_is_the_pool_of_the_fixture_amulet(level):
    pool = build_pool(DATA, amulet(item_level=level))

    assert {f.family: (f.side.value, f.weight) for f in pool} == FAMILIES[level]
    tagged = {
        f.family: sum(e.weight for e in f.mods if LIGHTNING in e.mod.implicit_tags)
        for f in pool
        if any(LIGHTNING in e.mod.implicit_tags for e in f.mods)
    }
    assert tagged == TAGGED[level]


def test_at_item_level_80_the_lightning_tagged_weight_is_13_950():
    pool = build_pool(DATA, amulet(item_level=80))

    assert sum(e.weight for f in pool for e in f.mods if LIGHTNING in e.mod.implicit_tags) == 13_950
