"""Sockets, the class maximum, plain quality of weapons and armour and Abyssal Sockets on an item (ADR-0046, ADR-0049)."""

import dataclasses
import pickle

import pytest
from abstraction_support import real_game_data
from implicits_support import BELT, BOOTS, EXTENDED, SOME_BOOTS, make
from items_support import AMULET, BODY
from repoe_support import no_network  # noqa: F401

from crafting_system.data import StatRange
from crafting_system.items import (
    MAX_PLAIN_QUALITY,
    MAX_QUALITY,
    PLAIN_QUALITY_ITEM_CLASSES,
    SOCKET_ITEM_CLASSES,
    CatalystType,
    Item,
    PlainQuality,
    Quality,
    QualityError,
    Rarity,
    SocketColour,
    SocketError,
    Sockets,
    class_maximum,
    has_abyssal_socket,
    is_abyssal_socket_mod,
)
from crafting_system.rules import get_rule

R, G, B, W = SocketColour.RED, SocketColour.GREEN, SocketColour.BLUE, SocketColour.WHITE
SWORD = "Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1"
STAFF = "Metadata/Items/Weapons/TwoHandWeapons/Staves/Staff2"
GNARLED_BRANCH = "Metadata/Items/Weapons/TwoHandWeapons/Staves/Staff1"
SIX = Sockets((R, G, B, B, W, R), (3, 2, 1))

# written from ADR-0046 and the wiki table it quotes, not read from the claim
EXPECTED_MAXIMUM = {
    "Body Armour": 6,
    "Bow": 6,
    "Staff": 6,
    "Warstaff": 6,
    "Two Hand Axe": 6,
    "Two Hand Mace": 6,
    "Two Hand Sword": 6,
    "Boots": 4,
    "Gloves": 4,
    "Helmet": 4,
    "Shield": 3,
    "Claw": 3,
    "Dagger": 3,
    "Rune Dagger": 3,
    "One Hand Axe": 3,
    "One Hand Mace": 3,
    "One Hand Sword": 3,
    "Thrusting One Hand Sword": 3,
    "Sceptre": 3,
    "Wand": 3,
}


def of_class(item_class: str, base_id: str = "Metadata/Items/Test/Base1"):
    """A base of `item_class` with the given id, copied from the fixture boots."""
    return dataclasses.replace(SOME_BOOTS, id=base_id, item_class=item_class)


def build_on(item_class: str, base_id: str = "Metadata/Items/Test/Base1", **fields) -> Item:
    """A validated item at item level 84 on a base of `item_class`."""
    base = of_class(item_class, base_id)
    data = dataclasses.replace(EXTENDED, base_items={**EXTENDED.base_items, base.id: base})
    return Item.build(data, base_id=base.id, item_level=84, rarity=Rarity.RARE, **fields)


def abyssal(mod_id: str = "AbyssalSocketMod"):
    """A fixture mod that carries the Abyssal Socket stat."""
    return dataclasses.replace(
        EXTENDED.mods["ColdResist1"], id=mod_id, stats=(StatRange("local_has_X_abyss_sockets", 1, 1),)
    )


# Sockets


def test_sockets_of_a_valid_value():
    sockets = Sockets((R, G), (2,))

    assert sockets.colours == (R, G)
    assert sockets.links == (2,)


def test_unlinked_puts_every_socket_in_a_group_of_its_own():
    assert Sockets.unlinked((R, G, B)) == Sockets((R, G, B), (1, 1, 1))


def test_count_is_the_number_of_sockets():
    assert SIX.count == 6
    assert Sockets.unlinked((W,)).count == 1


def test_groups_are_the_colours_of_each_link_group_in_socket_order():
    assert SIX.groups() == ((R, G, B), (B, W), (R,))


def test_no_sockets_is_refused():
    with pytest.raises(SocketError, match=r"0 sockets is outside 1 to 6"):
        Sockets((), ())


def test_seven_sockets_are_refused():
    with pytest.raises(SocketError, match=r"7 sockets is outside 1 to 6"):
        Sockets.unlinked((R,) * 7)


def test_links_that_do_not_add_up_to_the_sockets_are_refused():
    with pytest.raises(SocketError, match=r"link groups \(2, 2\) add up to 4 sockets, but there are 3 sockets"):
        Sockets((R, G, B), (2, 2))
    with pytest.raises(SocketError, match=r"link groups \(1,\) add up to 1 sockets, but there are 2 sockets"):
        Sockets((R, G), (1,))


def test_a_link_group_of_size_zero_is_refused():
    with pytest.raises(SocketError, match=r"link group sizes \(2, 0, 1\) must all be 1 or more"):
        Sockets((R, G, B), (2, 0, 1))


@pytest.mark.parametrize("colours", [["R", "G"], ("R", "G"), (R, "G"), (1, 2)])
def test_colours_that_are_not_socket_colours_are_refused(colours):
    with pytest.raises(SocketError, match="socket colours must be a tuple of SocketColour"):
        Sockets(colours, (2,))


@pytest.mark.parametrize("links", [[2], (2.0,), ("2",), (True,), None, 2])
def test_links_that_are_not_a_tuple_of_int_are_refused(links):
    with pytest.raises(SocketError, match="socket links must be a tuple of whole group sizes"):
        Sockets((R, G), links)


def test_two_equal_sockets_are_equal_and_hash_the_same():
    first = Sockets((R, G, B), (2, 1))
    second = Sockets((R, G, B), (2, 1))

    assert first == second
    assert hash(first) == hash(second)
    assert first != Sockets((R, G, B), (1, 2))
    assert first != Sockets((R, G, G), (2, 1))


# Item with sockets


def test_a_body_armour_takes_six_linked_sockets():
    built = make(base_id=BODY, sockets=SIX)

    assert built.sockets == SIX
    assert built.sockets.groups() == ((R, G, B), (B, W), (R,))


def test_boots_refuse_five_sockets_and_name_the_base_and_the_maximum():
    with pytest.raises(SocketError, match=rf"item on {BOOTS}: it has 5 sockets, but Iron Greaves \(Boots\) holds at most 4"):
        make(base_id=BOOTS, sockets=Sockets.unlinked((R,) * 5))


def test_boots_take_four_sockets():
    assert make(base_id=BOOTS, sockets=Sockets.unlinked((R,) * 4)).sockets.count == 4


def test_a_one_hand_sword_refuses_four_sockets_and_takes_three():
    with pytest.raises(SocketError, match=r"Rusted Sword \(One Hand Sword\) holds at most 3"):
        make(base_id=SWORD, sockets=Sockets.unlinked((R,) * 4))
    assert make(base_id=SWORD, sockets=Sockets.unlinked((R,) * 3)).sockets.count == 3


@pytest.mark.parametrize("item_class", ["Ring", "Amulet", "Belt"])
def test_sockets_on_jewellery_need_a_weapon_or_armour_base(item_class):
    with pytest.raises(SocketError, match=rf"sockets need a weapon or armour base.*this one is {item_class}$"):
        build_on(item_class, sockets=Sockets.unlinked((R,)))


def test_sockets_on_the_fixture_belt_and_amulet_are_refused():
    for base_id, item_class in ((BELT, "Belt"), (AMULET, "Amulet")):
        with pytest.raises(SocketError, match=rf"this one is {item_class}$"):
            make(base_id=base_id, sockets=Sockets.unlinked((R,)))


def test_changed_sets_keeps_and_clears_sockets():
    sockets = Sockets((R, G), (2,))

    with_sockets = make(base_id=BODY).changed(EXTENDED, sockets=sockets)

    assert with_sockets.sockets == sockets
    assert with_sockets.changed(EXTENDED, corrupted=True).sockets == sockets
    assert with_sockets.changed(EXTENDED, sockets=None).sockets is None


def test_changed_refuses_sockets_above_the_class_maximum():
    with pytest.raises(SocketError, match="holds at most 4"):
        make(base_id=BOOTS).changed(EXTENDED, sockets=Sockets.unlinked((R,) * 5))


@pytest.mark.parametrize("bad", ["RGB", (R, G), [R], 3, SIX.colours])
def test_an_item_sockets_value_must_be_sockets_or_none(bad):
    with pytest.raises(SocketError, match=rf"item on {BODY}: sockets .* is not a Sockets or None"):
        make(base_id=BODY, sockets=bad)


# an item made before B6


def test_an_item_built_without_sockets_has_none_and_equals_one_built_with_none():
    without = make(base_id=BODY)
    explicit = make(base_id=BODY, sockets=None)

    assert without.sockets is None
    assert without == explicit
    assert hash(without) == hash(explicit)


def test_an_item_with_sockets_differs_from_one_without():
    assert make(base_id=BODY, sockets=SIX) != make(base_id=BODY)
    assert make(base_id=BODY, sockets=SIX) != make(base_id=BODY, sockets=Sockets.unlinked((R,) * 6))


def test_the_pre_b6_fields_keep_their_order_and_sockets_comes_last():
    names = [field.name for field in dataclasses.fields(Item)]

    assert names[:11] == [
        "base_id",
        "item_level",
        "rarity",
        "mods",
        "influences",
        "corrupted",
        "implicits",
        "quality",
        "veil_offer",
        "enchantment",
        "memory_strands",
    ]
    assert names[-1] == "sockets"


def test_a_pickle_round_trip_keeps_an_item_equal():
    for built in (make(base_id=BODY), make(base_id=BODY, sockets=SIX, quality=PlainQuality(20))):
        copy = pickle.loads(pickle.dumps(built))
        assert copy == built
        assert hash(copy) == hash(built)


# the class table


@pytest.mark.parametrize(("item_class", "most"), sorted(EXPECTED_MAXIMUM.items()))
def test_the_class_maximum_of_each_socket_class(item_class, most):
    assert class_maximum(of_class(item_class)) == most


def test_the_socket_classes_are_the_twenty_of_the_table():
    assert len(EXPECTED_MAXIMUM) == 20
    assert SOCKET_ITEM_CLASSES == frozenset(EXPECTED_MAXIMUM)
    assert SOCKET_ITEM_CLASSES == PLAIN_QUALITY_ITEM_CLASSES


@pytest.mark.parametrize("item_class", ["Ring", "Amulet", "Belt", "Quiver"])
def test_a_class_outside_the_table_has_no_maximum(item_class):
    assert class_maximum(of_class(item_class)) is None


def test_the_gnarled_branch_holds_three_but_another_staff_six():
    assert class_maximum(of_class("Staff", GNARLED_BRANCH)) == 3
    assert class_maximum(of_class("Staff", STAFF)) == 6


def test_the_gnarled_branch_refuses_four_sockets_and_another_staff_takes_six():
    with pytest.raises(SocketError, match=r"\(Staff\) holds at most 3"):
        build_on("Staff", GNARLED_BRANCH, sockets=Sockets.unlinked((R,) * 4))
    assert build_on("Staff", STAFF, sockets=Sockets.unlinked((R,) * 6)).sockets.count == 6


def test_the_class_maximum_claim_is_approximate_and_lists_the_twenty_classes():
    rule = get_rule("sockets.class_maximum_sockets")

    assert rule.approximate is True
    assert set(rule.value["by_class"]) == set(EXPECTED_MAXIMUM)
    assert rule.value["by_base"] == {GNARLED_BRANCH: 3}


# quality of a weapon or armour


def test_the_quality_limits_are_20_catalyst_and_30_plain():
    assert MAX_QUALITY == 20
    assert MAX_PLAIN_QUALITY == 30


@pytest.mark.parametrize("percent", [0, 1, 20, 30])
def test_a_plain_percent_from_0_to_30_is_accepted(percent):
    assert PlainQuality(percent).percent == percent


@pytest.mark.parametrize("percent", [31, -1])
def test_a_plain_percent_outside_0_to_30_is_rejected(percent):
    with pytest.raises(QualityError, match=rf"plain quality has percent {percent}, outside 0 to 30"):
        PlainQuality(percent)


@pytest.mark.parametrize("percent", [10.0, "10", None, True])
def test_a_plain_percent_that_is_not_an_integer_is_rejected(percent):
    with pytest.raises(QualityError, match="not an integer"):
        PlainQuality(percent)


def test_a_plain_quality_has_no_catalyst_type_and_is_not_a_catalyst_quality():
    assert PlainQuality(10).type is None
    assert PlainQuality(5) != Quality(CatalystType.INTRINSIC, 5)


@pytest.mark.parametrize("item_class", ["Body Armour", "Shield", "One Hand Sword"])
def test_a_plain_quality_is_accepted_on_armour_shield_and_weapon(item_class):
    assert build_on(item_class, quality=PlainQuality(20)).quality == PlainQuality(20)


def test_a_plain_quality_of_30_is_accepted_on_a_body_armour():
    assert make(base_id=BODY, quality=PlainQuality(30)).quality.percent == 30


def test_a_plain_quality_of_zero_is_no_quality():
    zero = make(base_id=BODY, quality=PlainQuality(0))

    assert zero.quality is None
    assert zero == make(base_id=BODY)
    assert hash(zero) == hash(make(base_id=BODY))


@pytest.mark.parametrize("item_class", ["Ring", "Amulet", "Belt"])
def test_a_plain_quality_on_jewellery_is_rejected(item_class):
    with pytest.raises(QualityError, match=rf"plain quality 20% needs a weapon or armour base.*this one is {item_class}$"):
        build_on(item_class, quality=PlainQuality(20))


@pytest.mark.parametrize("base_id", [BODY, SWORD])
def test_a_catalyst_quality_on_armour_or_a_weapon_is_rejected(base_id):
    with pytest.raises(QualityError, match=r"needs a base of item class Amulet, Belt, Ring"):
        make(base_id=base_id, quality=Quality(CatalystType.INTRINSIC, 20))


def test_a_catalyst_quality_on_an_amulet_is_still_accepted():
    assert make(base_id=AMULET, quality=Quality(CatalystType.INTRINSIC, 20)).quality.percent == 20


def test_changed_keeps_a_plain_quality():
    built = make(base_id=BODY, quality=PlainQuality(20))

    assert built.changed(EXTENDED, corrupted=True).quality == PlainQuality(20)
    assert built.changed(EXTENDED, sockets=SIX).quality == PlainQuality(20)
    assert built.changed(EXTENDED, quality=None).quality is None


# Abyssal Sockets


def test_a_mod_with_the_abyssal_socket_stat_is_recognised():
    assert is_abyssal_socket_mod(abyssal())


def test_an_ordinary_mod_is_not_an_abyssal_socket_mod():
    assert not is_abyssal_socket_mod(EXTENDED.mods["ColdResist1"])


def test_an_abyssal_mod_in_the_list_is_found():
    mod = abyssal()
    data = dataclasses.replace(EXTENDED, mods={**EXTENDED.mods, mod.id: mod})

    assert has_abyssal_socket(data, BODY, (mod.id,))
    assert has_abyssal_socket(data, BODY, ("ColdResist1", mod.id))


def test_an_abyssal_implicit_of_the_base_is_found():
    mod = abyssal()
    base = dataclasses.replace(EXTENDED.base_items[BODY], implicits=(mod.id,))
    data = dataclasses.replace(
        EXTENDED, mods={**EXTENDED.mods, mod.id: mod}, base_items={**EXTENDED.base_items, BODY: base}
    )

    assert has_abyssal_socket(data, BODY, ())


def test_no_abyssal_socket_on_ordinary_mods_or_an_unknown_mod_id():
    assert not has_abyssal_socket(EXTENDED, BODY, ())
    assert not has_abyssal_socket(EXTENDED, BODY, ("ColdResist1",))
    assert not has_abyssal_socket(EXTENDED, BODY, ("NoSuchMod",))


# the real bench


def test_the_real_socket_bench_options_cover_exactly_the_twenty_classes():
    data = real_game_data()
    found = {
        item_class
        for option in data.bench_options
        if option.actions.change_socket_count is not None
        or option.actions.link_sockets is not None
        or option.actions.color_sockets is not None
        for item_class in option.item_classes
    }

    assert found == set(EXPECTED_MAXIMUM)
    assert len(found) == 20
