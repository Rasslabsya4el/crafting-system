"""R03 and R06 on the real 3.29.3.3 dump: implicits resolve to their grade ids, R06 is written as base rolls plus quality (ticket #141).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the folder with `CRAFTING_CACHE_DIR`).
They skip cleanly when it is not there; CI fetches it (ticket #165), so they run there.
"""

import pytest
from abstraction_support import real_game_data
from targets_support import EXAMPLES

from crafting_system.items import (
    CatalystType,
    ImplicitMod,
    Item,
    Quality,
    Rarity,
    VeilOfferError,
    spawn_weight,
    veiled_placeholder,
)
from crafting_system.targets import load_target

GRADES = {f"AvoidShockEldritchImplicit{grade}" for grade in range(1, 7)}
BELT = "Metadata/Items/Belts/Belt4"


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.fixture(scope="module")
def r03(real):
    return load_target(EXAMPLES / "r03-avoid-shock-boots.yaml", real)


@pytest.fixture(scope="module")
def r06(real):
    return load_target(EXAMPLES / "r06-strength-heavy-belt.yaml", real)


def with_implicits(real, target, *entries: ImplicitMod, quality: Quality | None = None) -> Item:
    return Item.build(
        real,
        base_id=target.base_id,
        item_level=target.item_level,
        rarity=Rarity.RARE,
        influences=target.influences,
        implicits=entries,
        quality=quality,
    )


def test_r03_loads_and_its_implicit_is_exactly_the_six_exarch_grades(r03):
    (wanted,) = r03.implicits

    assert wanted.stat == "#% chance to Avoid being Shocked" and wanted.family is None
    assert wanted.mod_ids == GRADES  # no presence variant, no explicit suffix of the same text
    assert wanted.min_roll == (40,) and wanted.min_grade is None
    assert r03.quality is None
    assert r03.start_item.mods[0].mod_id == "ChanceToSuppressSpells5__" and r03.start_item.mods[0].fractured


def test_r03_is_met_by_an_implicit_of_40_or_more_on_any_grade(r03, real):
    def implicit_of(grade: int, value: int) -> Item:
        return with_implicits(real, r03, ImplicitMod(f"AvoidShockEldritchImplicit{grade}", grade, (value,)))

    wanted = r03.implicits[0]

    assert wanted.is_met_by(implicit_of(3, 40))
    assert not wanted.is_met_by(implicit_of(3, 39))
    assert wanted.is_met_by(implicit_of(3, 41))
    assert not wanted.is_met_by(implicit_of(2, 38))
    assert wanted.is_met_by(implicit_of(4, 42))
    assert not wanted.is_met_by(with_implicits(real, r03))


def test_r06_loads_as_base_rolls_plus_intrinsic_quality(r06):
    (wanted,) = r06.implicits

    assert wanted.family == "Strength" and wanted.mod_ids == {"StrengthImplicitBelt1"}
    assert wanted.min_roll == (35,)
    assert r06.quality.type is CatalystType.INTRINSIC and r06.quality.min_percent == 20
    assert r06.base_id == BELT and r06.item_level == 75


def test_r06_implicit_and_quality_are_met_only_at_35_and_20_percent_intrinsic(r06, real):
    strength = "StrengthImplicitBelt1"

    def belt(value: int, quality: Quality | None) -> Item:
        return with_implicits(real, r06, ImplicitMod(strength, 0, (value,)), quality=quality)

    best = Quality(CatalystType.INTRINSIC, 20)
    done = belt(35, best)

    assert r06.implicits[0].is_met_by(done) and r06.quality.is_met_by(done)
    assert not r06.implicits[0].is_met_by(belt(34, best))
    assert not r06.quality.is_met_by(belt(35, Quality(CatalystType.INTRINSIC, 19)))
    assert not r06.quality.is_met_by(belt(35, Quality(CatalystType.ABRASIVE, 20)))
    assert not r06.quality.is_met_by(belt(35, None))
    assert r06.unmet(done) == r06.requirements  # the explicit mods are still wanted


def test_real_unveiled_mods_valid_for_velour_boots_validate_and_others_are_refused(real, r03):
    boots = r03.base_id
    tags = real.base_items[boots].tags
    wanted = "JunMasterVeiledMovementVelocityAndMovementVelocityIfNotHitRecently"
    blocked = next(
        mod.id for mod in real.mods.values() if mod.domain == "unveiled" and mod.generation_type == "prefix" and spawn_weight(mod, tags) == 0
    )
    held = (veiled_placeholder(real, "VeiledPrefix"),)
    build = {"base_id": boots, "item_level": 100, "rarity": Rarity.RARE, "mods": held}

    assert Item.build(real, veil_offer=(wanted,), **build).veil_offer == (wanted,)
    with pytest.raises(VeilOfferError, match=f"{blocked} has spawn weight 0"):
        Item.build(real, veil_offer=(blocked,), **build)
