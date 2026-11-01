"""The Eldritch actions on the real 3.29.3.3 dump (ticket #151): the pools of the research (table T1), the pinned Grand Ember,
the closure of Conflict over the 4,086 Eldritch mods, and the three Eldritch orbs on a real boots item.

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`). They
skip cleanly when it is not there; CI fetches it (ticket #165), so they run there. The numbers below are copied by hand from
table T1 of the research note (`docs/research/2026-10-31-eldritch.md` on the branch `research/eldritch`), which counted them from
the same dump with a separate script.
"""

from fractions import Fraction

import pytest

from crafting_system.actions import (
    EldritchAnnulmentOrb,
    EldritchChaosOrb,
    EldritchExaltedOrb,
    EldritchImplicitCurrency,
    NotApplicableError,
    OrbOfConflict,
    implicit_pool,
)
from crafting_system.data import MissingDataError, load_game_data
from crafting_system.items import (
    EldritchSide,
    ExplicitMod,
    ImplicitMod,
    Item,
    Rarity,
    eldritch_grade,
    eldritch_side,
)

BOOTS = "Metadata/Items/Armours/Boots/BootsInt1"
SIDES = {"exarch": EldritchSide.EXARCH, "eater": EldritchSide.EATER}

# (side, item class) -> (mods, total weight) at Lesser (grade 1), Greater (2) and Grand to Perfect (3 to 6)
T1 = {
    ("exarch", "Body Armour"): ((26, 15700), (52, 23550), (78, 26690)),
    ("exarch", "Boots"): ((27, 15400), (54, 23100), (81, 26180)),
    ("exarch", "Gloves"): ((30, 18700), (60, 28050), (90, 31790)),
    ("exarch", "Helmet"): ((26, 16900), (52, 25350), (78, 28730)),
    ("eater", "Body Armour"): ((33, 17100), (66, 25650), (99, 29070)),
    ("eater", "Boots"): ((26, 14600), (52, 21900), (78, 24820)),
    ("eater", "Gloves"): ((31, 18700), (62, 28050), (93, 31810)),
    ("eater", "Helmet"): ((24, 17100), (48, 25650), (72, 29070)),
}


@pytest.fixture(scope="module")
def data():
    try:
        return load_game_data()
    except MissingDataError as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


def bases_of(data, item_class):
    """The released bases of an item class, in id order."""
    return sorted(
        (base for base in data.base_items.values() if base.item_class == item_class and base.release_state == "released"),
        key=lambda base: base.id,
    )


def low(data, mod_id):
    return tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)


def implicit(data, mod_id):
    return ImplicitMod(mod_id, eldritch_grade(data.mods[mod_id]), low(data, mod_id))


def rolled(data, mod_id, **flags):
    return ExplicitMod(mod_id, 1, low(data, mod_id), **flags)


@pytest.mark.parametrize(("side", "item_class"), list(T1))
def test_the_pools_of_the_research_table_by_side_class_and_grade(data, side, item_class):
    shapes = T1[(side, item_class)]
    for base in bases_of(data, item_class):
        for grade in range(1, 7):
            pool = implicit_pool(data, base, SIDES[side], grade)
            expected = shapes[0] if grade == 1 else shapes[1] if grade == 2 else shapes[2]
            assert (len(pool), sum(weight for _, weight in pool)) == expected, (base.id, grade)


def test_a_grand_ember_gives_avoid_shock_on_exarch_boots_with_700_over_26180(data):
    item = Item.build(data, base_id=BOOTS, item_level=84, rarity=Rarity.RARE)
    outcomes = EldritchImplicitCurrency(EldritchSide.EXARCH, 3).outcomes(data, item)
    chances = {result.implicits[0].mod_id: chance for chance, result in outcomes.results}
    assert len(chances) == 81 and sum(chances.values()) == 1
    assert chances["AvoidShockEldritchImplicit3"] == Fraction(700, 26180) == Fraction(5, 187)
    # the roll of the implicit is 39-41 at Grand: the result holds the lowest value
    assert data.mods["AvoidShockEldritchImplicit3"].stats[0].min == 39 and data.mods["AvoidShockEldritchImplicit3"].stats[0].max == 41
    assert next(result for _, result in outcomes.results if result.implicits[0].mod_id == "AvoidShockEldritchImplicit3").implicits[0].values == (39,)


@pytest.mark.parametrize("grade", [1, 2, 3, 4])
def test_every_ember_and_ichor_gives_results_that_sum_to_one_on_each_class(data, grade):
    for item_class in ("Body Armour", "Boots", "Gloves", "Helmet"):
        item = Item.build(data, base_id=bases_of(data, item_class)[0].id, item_level=60, rarity=Rarity.NORMAL)
        for side in EldritchSide:
            outcomes = EldritchImplicitCurrency(side, grade).outcomes(data, item)
            assert sum(chance for chance, _ in outcomes.results) == 1
            assert {eldritch_grade(data.mods[result.implicits[0].mod_id]) for _, result in outcomes.results} == {grade}


def test_every_eldritch_mod_has_the_neighbour_grades_that_conflict_moves_it_to(data):
    count = 0
    for mod in data.mods.values():
        side, grade = eldritch_side(mod), eldritch_grade(mod)
        if side is None:
            continue
        count += 1
        for neighbour in (grade - 1, grade + 1):
            if 1 <= neighbour <= 6:
                other = data.mods[mod.id[:-1] + str(neighbour)]
                assert eldritch_side(other) is side and other.families == mod.families and eldritch_grade(other) == neighbour
    assert count == 4086


def test_a_conflict_on_a_real_pair_moves_each_implicit_one_grade(data):
    item = Item.build(
        data,
        base_id=BOOTS,
        item_level=84,
        rarity=Rarity.RARE,
        implicits=(implicit(data, "AvoidShockEldritchImplicit3"), implicit(data, "ChanceToShockEldritchImplicit2")),
    )
    held = {
        tuple(sorted(entry.mod_id for entry in result.implicits)): chance
        for chance, result in OrbOfConflict().outcomes(data, item).results
    }
    assert held == {
        ("AvoidShockEldritchImplicit4", "ChanceToShockEldritchImplicit1"): Fraction(396517, 10**6),
        ("AvoidShockEldritchImplicit2", "ChanceToShockEldritchImplicit3"): 1 - Fraction(396517, 10**6),
    }


def test_the_three_eldritch_orbs_act_on_the_prefixes_of_a_real_boots_item_when_the_exarch_dominates(data):
    life = next(mod.id for mod in data.mods.values() if mod.generation_type == "prefix" and mod.families == ("IncreasedLife",))
    resist = next(mod.id for mod in data.mods.values() if mod.generation_type == "suffix" and mod.families == ("FireResistance",))
    item = Item.build(
        data,
        base_id=BOOTS,
        item_level=84,
        rarity=Rarity.RARE,
        mods=(rolled(data, life), rolled(data, resist)),
        implicits=(implicit(data, "AvoidShockEldritchImplicit3"), implicit(data, "ChanceToShockEldritchImplicit2")),
    )
    exalted = EldritchExaltedOrb().outcomes(data, item)
    assert sum(exalted.distribution(lambda mod: mod.generation_type).values()) == 1
    assert {side for outcome in exalted.distribution(lambda mod: mod.generation_type) for side, _ in outcome} == {"prefix"}
    chaos = EldritchChaosOrb().outcomes(data, item)
    assert [entry.mod_id for entry in chaos.retained.mods] == [resist]
    sides = chaos.distribution(lambda mod: mod.generation_type)
    assert sum(sides.values()) == 1 and {side for outcome in sides for side, _ in outcome} == {"prefix"}
    assert {dict(outcome)["prefix"] for outcome in sides} == {3}  # one mod stays, so the totals 4, 5 and 6 put back 3, 4 and 5, clamped to 3 slots
    annul = EldritchAnnulmentOrb().outcomes(data, item)
    assert [result.mods for _, result in annul.results] == [(rolled(data, resist),)]


def test_the_eldritch_orbs_need_a_dominant_side_on_a_real_item(data):
    item = Item.build(
        data,
        base_id=BOOTS,
        item_level=84,
        rarity=Rarity.RARE,
        implicits=(implicit(data, "AvoidShockEldritchImplicit3"), implicit(data, "ChanceToShockEldritchImplicit3")),
    )
    for action in (EldritchChaosOrb(), EldritchExaltedOrb(), EldritchAnnulmentOrb()):
        with pytest.raises(NotApplicableError, match="dominant"):
            action.outcomes(data, item)
