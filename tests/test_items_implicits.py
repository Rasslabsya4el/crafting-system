"""Implicits on an item (ADR-0027, ADR-0025): base and Eldritch implicits, grades, sides and values."""

import pytest
from implicits_support import BELT, BOOTS, EXTENDED, implicit, make, on_body
from items_support import BODY, DATA, roll
from repoe_support import no_network  # noqa: F401

from crafting_system.items import (
    EldritchSide,
    ExplicitMod,
    ImplicitError,
    ImplicitMod,
    Item,
    ItemError,
    Rarity,
    UnknownModError,
    ValueRangeError,
    eldritch_grade,
    eldritch_side,
    is_presence_variant,
)

BASE = implicit("StrengthImplicitBelt1")
AVOID1 = implicit("AvoidShockEldritchImplicit1", 1)
AVOID3 = implicit("AvoidShockEldritchImplicit3", 3)
EATER2 = implicit("ChanceToShockEldritchImplicit2", 2)


def test_an_item_built_without_the_new_fields_has_none_of_them():
    built = make()

    assert (built.implicits, built.quality, built.veil_offer) == ((), None, ())


def test_a_base_implicit_with_grade_0_is_accepted():
    assert make(implicits=(BASE,)).implicits == (BASE,)


def test_the_implicit_of_a_fixture_base_is_accepted():
    built = Item.build(
        DATA,
        base_id="Metadata/Items/Belts/Belt3",
        item_level=84,
        rarity=Rarity.RARE,
        implicits=(ImplicitMod("IncreasedLifeImplicitBelt1", 0, (30,)),),
    )

    assert built.implicits[0].values == (30,)


def test_a_base_implicit_with_a_grade_is_rejected():
    with pytest.raises(ImplicitError, match=r"item on .*Belt4: implicit StrengthImplicitBelt1.*implicit of the base.*grade is 0, not 2"):
        make(implicits=(ImplicitMod("StrengthImplicitBelt1", 2, (25,)),))


def test_an_eldritch_implicit_with_its_grade_is_accepted():
    assert on_body(implicits=(AVOID3,)).implicits == (AVOID3,)


def test_a_wrong_eldritch_grade_is_rejected():
    wrong = ImplicitMod("AvoidShockEldritchImplicit3", 2, (39,))

    with pytest.raises(ImplicitError, match=r"item on .*BodyInt1: implicit AvoidShockEldritchImplicit3.*grade 3, not 2"):
        on_body(implicits=(wrong,))


def test_grade_0_on_an_eldritch_implicit_is_rejected():
    with pytest.raises(ImplicitError, match=r"AvoidShockEldritchImplicit3.*grade 3, not 0"):
        on_body(implicits=(ImplicitMod("AvoidShockEldritchImplicit3", 0, (39,)),))


def test_a_presence_variant_takes_the_grade_of_its_trailing_digit():
    unique = implicit("AvoidShockEldritchImplicitUniquePresence4", 4)
    pinnacle = implicit("AvoidShockEldritchImplicitPinnaclePresence2", 2)

    assert on_body(implicits=(unique, EATER2)).eldritch_implicits(EXTENDED)[EldritchSide.EXARCH] == unique
    assert on_body(implicits=(pinnacle,)).implicits == (pinnacle,)


def test_two_eldritch_implicits_of_one_side_are_rejected():
    with pytest.raises(ImplicitError, match=r"item on .*BodyInt1: implicits AvoidShockEldritchImplicit1 and AvoidShockEldritchImplicit3.*exarch side"):
        on_body(implicits=(AVOID3, AVOID1))


def test_two_eldritch_implicits_of_one_side_from_different_families_are_rejected():
    other = implicit("ShockProliferationEldritchImplicit1", 1)

    with pytest.raises(ImplicitError, match="exarch side"):
        on_body(implicits=(AVOID1, other))


def test_one_implicit_on_each_side_is_accepted():
    built = on_body(implicits=(AVOID3, EATER2))

    assert built.eldritch_implicits(EXTENDED) == {EldritchSide.EXARCH: AVOID3, EldritchSide.EATER: EATER2}


def test_a_base_implicit_and_an_eldritch_implicit_can_sit_together():
    built = make(implicits=(AVOID1, BASE))

    assert built.eldritch_implicits(EXTENDED) == {EldritchSide.EXARCH: AVOID1}


def test_an_implicit_that_is_not_in_the_game_data_is_rejected():
    with pytest.raises(UnknownModError, match=r"item on .*Belt4: implicit NoSuchImplicit.*not in the game data"):
        make(implicits=(ImplicitMod("NoSuchImplicit", 0, (1,)),))


def test_an_explicit_mod_as_an_implicit_is_rejected():
    with pytest.raises(ImplicitError, match=r"implicit ColdResist1 is neither an implicit of the base nor an Eldritch"):
        make(implicits=(ImplicitMod("ColdResist1", 0, (6,)),))


def test_an_implicit_of_another_base_is_rejected():
    with pytest.raises(ImplicitError, match=r"implicit IncreasedLifeImplicitBelt1 is neither"):
        make(implicits=(ImplicitMod("IncreasedLifeImplicitBelt1", 0, (30,)),))


def test_the_wrong_number_of_implicit_values_is_rejected():
    with pytest.raises(ValueRangeError, match=r"item on .*Belt4: mod StrengthImplicitBelt1 has 2 rolled value.*1 stat"):
        make(implicits=(ImplicitMod("StrengthImplicitBelt1", 0, (30, 30)),))


def test_a_presence_variant_needs_a_value_for_its_second_stat():
    with pytest.raises(ValueRangeError, match=r"AvoidShockEldritchImplicitUniquePresence4 has 1 rolled value.*2 stat"):
        on_body(implicits=(ImplicitMod("AvoidShockEldritchImplicitUniquePresence4", 4, (52,)),))


@pytest.mark.parametrize("value", [25, 35])
def test_the_edge_values_of_an_implicit_are_accepted(value):
    assert make(implicits=(ImplicitMod("StrengthImplicitBelt1", 0, (value,)),)).implicits[0].values == (value,)


@pytest.mark.parametrize("value", [24, 36])
def test_an_implicit_value_outside_its_range_is_rejected(value):
    with pytest.raises(ValueRangeError, match=rf"mod StrengthImplicitBelt1 has value {value} for additional_strength, outside 25 to 35"):
        make(implicits=(ImplicitMod("StrengthImplicitBelt1", 0, (value,)),))


def test_an_eldritch_value_outside_its_range_is_rejected():
    with pytest.raises(ValueRangeError, match=r"mod AvoidShockEldritchImplicit1 has value 36.*33 to 35"):
        on_body(implicits=(ImplicitMod("AvoidShockEldritchImplicit1", 1, (36,)),))


def test_the_given_order_of_implicits_does_not_matter():
    assert make(implicits=(BASE, AVOID1)) == make(implicits=(AVOID1, BASE))
    assert hash(make(implicits=(BASE, AVOID1))) == hash(make(implicits=(AVOID1, BASE)))
    assert [entry.mod_id for entry in make(implicits=(BASE, AVOID1)).implicits] == [
        "AvoidShockEldritchImplicit1",
        "StrengthImplicitBelt1",
    ]


def test_the_same_implicit_twice_is_rejected():
    with pytest.raises(ImplicitError, match=r"item on .*Belt4: implicit StrengthImplicitBelt1 is on the item twice"):
        make(implicits=(BASE, BASE))


def test_a_mixed_type_list_of_ids_is_an_implicit_error_not_a_type_error():
    with pytest.raises(ImplicitError, match="implicit 5 needs a string id"):
        make(implicits=(ImplicitMod(5, 0, (1,)), ImplicitMod("a", 0, (1,))))


def test_a_mixed_type_list_of_mod_ids_is_an_item_error_not_a_type_error():
    with pytest.raises(ItemError, match="string mod id"):
        make(ExplicitMod(5, 1, (1,)), ExplicitMod("IncreasedLife1", 1, (10,)))


@pytest.mark.parametrize("bad", [[BASE], (BASE, "StrengthImplicitBelt1"), "StrengthImplicitBelt1"])
def test_implicits_must_be_a_tuple_of_implicit_mods(bad):
    with pytest.raises(ImplicitError, match="item on .*Belt4: implicits must be a tuple of ImplicitMod"):
        make(implicits=bad)


@pytest.mark.parametrize(
    ("entry", "reason"),
    [
        (ImplicitMod("StrengthImplicitBelt1", 0, [30]), "tuple of values"),
        (ImplicitMod("StrengthImplicitBelt1", 0.0, (30,)), "integer grade"),
        (ImplicitMod("StrengthImplicitBelt1", True, (30,)), "integer grade"),
        (ImplicitMod("StrengthImplicitBelt1", 0, (30.5,)), "not an integer"),
        (ImplicitMod("StrengthImplicitBelt1", 7, (30,)), "grade 7, outside 0 to 6"),
        (ImplicitMod("StrengthImplicitBelt1", -1, (30,)), "grade -1, outside 0 to 6"),
    ],
)
def test_a_malformed_implicit_is_rejected_without_game_data(entry, reason):
    with pytest.raises(ImplicitError, match=rf"item on {BELT}: implicit StrengthImplicitBelt1.*{reason}"):
        Item(base_id=BELT, item_level=84, rarity=Rarity.RARE, implicits=(entry,))


def test_a_direct_item_with_an_unknown_implicit_fails_validate():
    direct = Item(base_id=BELT, item_level=84, rarity=Rarity.RARE, implicits=(ImplicitMod("Nope", 0, (1,)),))

    with pytest.raises(UnknownModError, match="implicit Nope"):
        direct.validate(EXTENDED)


def test_the_implicit_errors_are_item_errors():
    assert issubclass(ImplicitError, ItemError)


def test_eldritch_grade_reads_the_trailing_digit():
    grades = {mod_id: eldritch_grade(EXTENDED.mods[mod_id]) for mod_id in EXTENDED.mods if "Eldritch" in mod_id and mod_id[-1] != "X"}

    assert grades["AvoidShockEldritchImplicit3"] == 3
    assert grades["AvoidShockEldritchImplicitUniquePresence4"] == 4
    assert grades["AvoidShockEldritchImplicitPinnaclePresence2"] == 2
    assert grades["ChanceToShockEldritchImplicit2"] == 2


def test_eldritch_grade_is_none_for_other_mods():
    assert eldritch_grade(EXTENDED.mods["StrengthImplicitBelt1"]) is None
    assert eldritch_grade(EXTENDED.mods["ColdResist1"]) is None
    assert eldritch_grade(EXTENDED.mods["UnveiledPrefixLife1"]) is None


def test_an_eldritch_mod_without_a_grade_digit_is_refused():
    with pytest.raises(ImplicitError, match="ChanceToShockEldritchImplicitX.*grade 1 to 6"):
        eldritch_grade(EXTENDED.mods["ChanceToShockEldritchImplicitX"])


def test_eldritch_side_maps_the_two_generation_types():
    assert eldritch_side(EXTENDED.mods["AvoidShockEldritchImplicit1"]) is EldritchSide.EXARCH
    assert eldritch_side(EXTENDED.mods["ChanceToShockEldritchImplicit2"]) is EldritchSide.EATER
    assert eldritch_side(EXTENDED.mods["StrengthImplicitBelt1"]) is None


def test_a_presence_variant_is_found_by_its_stat():
    assert is_presence_variant(EXTENDED.mods["AvoidShockEldritchImplicitUniquePresence4"])
    assert is_presence_variant(EXTENDED.mods["AvoidShockEldritchImplicitPinnaclePresence2"])
    assert not is_presence_variant(EXTENDED.mods["AvoidShockEldritchImplicit3"])
    assert not is_presence_variant(EXTENDED.mods["ColdResist1"])


def test_changed_keeps_the_implicits_and_can_replace_them():
    built = make(implicits=(BASE, AVOID1))

    assert built.changed(EXTENDED, corrupted=True).implicits == built.implicits
    assert built.changed(EXTENDED, implicits=(BASE,)).implicits == (BASE,)
    with pytest.raises(ImplicitError):
        built.changed(EXTENDED, implicits=(BASE, AVOID1, AVOID3))


def test_add_mod_and_remove_mod_keep_the_implicits():
    built = make(implicits=(BASE, AVOID1))
    added = built.add_mod(EXTENDED, roll("ColdResist1"))

    assert added.implicits == built.implicits
    assert added.remove_mod(EXTENDED, "ColdResist1").implicits == built.implicits


def test_an_item_without_implicits_equals_and_hashes_like_one_with_the_defaults():
    plain = make()
    explicit = make(implicits=(), quality=None, veil_offer=())

    assert plain == explicit
    assert hash(plain) == hash(explicit)


def test_a_normal_boots_base_takes_no_implicit_of_a_belt():
    with pytest.raises(ImplicitError, match=r"item on .*Boots/BootsStr1: implicit StrengthImplicitBelt1 is neither"):
        make(base_id=BOOTS, rarity=Rarity.NORMAL, implicits=(BASE,))


def test_the_error_names_the_base_of_a_body_armour():
    with pytest.raises(ImplicitError, match=rf"^item on {BODY}:"):
        on_body(implicits=(ImplicitMod("StrengthImplicitBelt1", 0, (30,)),))
