"""Targets that ask for or allow corruption (ticket #257, ADR-0036): `corrupted: true` on an implicit, `allow_corrupted`, the goal check
and the errors of an impossible target. Each error is one test; the message names the cause and the nearest mod.

The data is the small export of `targets_corrupted_support`; the real ring is checked in `test_targets_corrupted_real.py`.
The text of a test starts on line 5; the file is called `t.yaml`.
"""

import pytest
from targets_corrupted_support import (
    ALL_RES,
    COLD_DAMAGE,
    DATA,
    FIRE_DAMAGE,
    FLASK,
    PLAIN_RING,
    RING,
    assert_error,
    parse,
    parse_error,
)

from crafting_system.items import ExplicitMod, ImplicitError, ImplicitMod, Item, Rarity
from crafting_system.targets import ImplicitRequirement, Target

COLD_TIERS = {"ColdCorrupted1", "ColdCorrupted2", "ColdCorrupted3"}
QUIVER_NAME = "Serpent Quiver"


def corrupted_ring(*, implicits=(), mods=()):
    """A corrupted Prismatic Ring with the Cold Resistance suffix the header asks for."""
    return Item.build(
        DATA,
        base_id=RING,
        item_level=84,
        rarity=Rarity.RARE,
        mods=(ExplicitMod("ColdResist1", 1, (10,)), *mods),
        implicits=implicits,
        corrupted=True,
    )


# -- resolving a corrupted entry --------------------------------------------------------------------------


def test_a_corrupted_stat_entry_resolves_to_the_corrupted_mod_of_the_ring():
    target = parse(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\n")

    (wish,) = target.implicits
    assert wish.mod_ids == {"ResistCorrupted"}
    assert wish.corrupted is True and wish.stat == ALL_RES and wish.family is None
    assert target.asks_corrupted and target.takes_corrupted and not target.allow_corrupted


def test_the_same_text_without_the_key_stays_the_base_implicit_and_the_two_are_different_requirements():
    ordinary = parse(f"implicits:\n  - stat: '{ALL_RES}'\n").implicits[0]
    corrupted = parse(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\n").implicits[0]

    assert ordinary.mod_ids == {"RingResistImplicit"} and ordinary.corrupted is False
    assert corrupted.mod_ids == {"ResistCorrupted"}
    on_ring = Item.build(
        DATA, base_id=RING, item_level=84, rarity=Rarity.NORMAL, implicits=(ImplicitMod("RingResistImplicit", 0, (9,)),)
    )
    assert ordinary.is_met_by(on_ring) and not corrupted.is_met_by(on_ring)


def parse_with_level(level: int, text: str, base: str = "Prismatic Ring") -> Target:
    return parse(f"base: {base}\nitem_level: {level}\nrequirements:\n  - family: ColdResistance\n{text}", header=False)


def test_a_corrupted_family_entry_holds_every_tier_the_item_level_allows():
    asked = "implicits:\n  - family: AddedCold\n    corrupted: true\n"

    assert parse(asked).implicits[0].mod_ids == COLD_TIERS  # item level 84
    assert parse(asked).implicits[0].family == "AddedCold"
    assert parse_with_level(40, asked).implicits[0].mod_ids == {"ColdCorrupted1", "ColdCorrupted2"}
    assert parse_with_level(30, asked).implicits[0].mod_ids == {"ColdCorrupted1"}


def test_a_mod_key_names_one_tier_and_the_stat_text_selects_all_of_them():
    target = parse(f"implicits:\n  - stat: '{COLD_DAMAGE}'\n    corrupted: true\n    mod: ColdCorrupted2\n")

    assert target.implicits[0].mod_ids == {"ColdCorrupted2"}
    assert parse(f"implicits:\n  - stat: '{COLD_DAMAGE}'\n    corrupted: true\n").implicits[0].mod_ids == COLD_TIERS


def test_min_roll_on_a_corrupted_entry_is_checked_against_the_corrupted_mods():
    target = parse(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\n    min_roll: 15\n")

    assert target.implicits[0].min_roll == (15,)
    assert_error(
        parse_error(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\n    min_roll: 17\n"),
        8, "implicits[0].min_roll", "17 is above the best roll", "16",
    )  # fmt: skip


def test_corrupted_false_is_the_same_as_leaving_the_key_out():
    text = f"implicits:\n  - stat: '{ALL_RES}'\n"

    assert parse(text) == parse(text.replace("'\n", "'\n    corrupted: false\n"))


def test_a_corrupted_entry_has_no_grade():
    message = parse_error(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\n    min_grade: 2\n")

    assert_error(message, 8, "implicits[0].min_grade", "only an Eldritch implicit has a grade", "ResistCorrupted")


def test_the_key_must_be_true_or_false():
    assert_error(
        parse_error(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: yes please\n"),
        7, "implicits[0].corrupted", "must be true or false", '"yes please"',
    )  # fmt: skip


# -- the errors of a corrupted entry that cannot be had --------------------------------------------------


def test_error_a_text_no_corrupted_implicit_of_the_class_has_names_the_cause_and_the_nearest_mods():
    message = parse_error("implicits:\n  - stat: '+#% to all Elemental Resist'\n    corrupted: true\n")

    assert_error(
        message, 6, "implicits[0].stat", "no corrupted implicit of a Ring (Prismatic Ring) has the text", "to all Elemental Resist",
        "nearest corrupted implicits", '`ResistCorrupted` ("+#% to all Elemental Resistances")',
    )  # fmt: skip


def test_error_a_family_no_corrupted_implicit_has_names_the_cause_and_the_nearest_mod():
    message = parse_error("implicits:\n  - family: AllResistancesCorupted\n    corrupted: true\n")

    assert_error(
        message, 6, "implicits[0].family", "belongs to the family `AllResistancesCorupted`", "`ResistCorrupted`"
    )


def test_error_a_mod_that_needs_a_higher_item_level_names_the_level_and_the_nearest_available_mod():
    low = "implicits:\n  - stat: '%s'\n    corrupted: true\n    mod: ColdCorrupted3\n" % COLD_DAMAGE
    message = parse_error("base: Prismatic Ring\nitem_level: 60\nrequirements:\n  - family: ColdResistance\n" + low, header=False)

    assert_error(
        message, 8, "implicits[0].mod", "`ColdCorrupted3` needs an item level of 81", "the target is item level 60",
        "`ColdCorrupted2`",
    )  # fmt: skip


def test_error_a_text_whose_every_mod_needs_a_higher_item_level_names_that_level_and_the_nearest_available_mod():
    asked = "implicits:\n  - stat: '+#% to Quality of Supported Gems'\n    corrupted: true\n"
    message = parse_error("base: Prismatic Ring\nitem_level: 60\nrequirements:\n  - family: ColdResistance\n" + asked, header=False)

    assert_error(message, 6, "implicits[0].stat", "(`LateCorrupted`) needs an item level of 81", "the target is item level 60", "raise `item_level`")
    assert parse_with_level(81, asked).implicits[0].mod_ids == {"LateCorrupted"}


def test_error_an_item_level_below_every_corrupted_implicit_of_the_class_says_which_level_is_the_lowest():
    asked = "implicits:\n  - stat: '(5-8)% increased Projectile Speed'\n    corrupted: true\n"
    message = parse_error(f"base: Serpent Quiver\nitem_level: 10\nrequirements:\n  - family: ColdResistance\n{asked}", header=False)

    assert_error(message, 6, "implicits[0].stat", "no corrupted implicit of a Quiver (Serpent Quiver) can occur at item level 10", "the lowest needs item level 20")
    assert parse_with_level(20, asked, QUIVER_NAME).implicits[0].mod_ids == {"QuiverCorrupted"}


def test_error_a_text_only_another_item_class_can_get_says_so():
    message = parse_error("implicits:\n  - stat: '(10-15)% increased Stun Duration'\n    corrupted: true\n")

    assert_error(message, 6, "implicits[0].stat", "no corrupted implicit of a Ring", "other item classes only")


def test_error_a_prefix_or_suffix_text_is_pointed_at_the_requirements():
    message = parse_error("implicits:\n  - stat: '+#% to Cold Resistance'\n    corrupted: true\n")

    assert_error(message, 6, "implicits[0].stat", "names a prefix or suffix", "`requirements:`", "nearest corrupted implicits")


def test_error_an_ordinary_implicit_text_is_pointed_at_the_entry_without_the_key():
    message = parse_error(
        "base: Plate Vest\nitem_level: 84\nrequirements:\n  - family: ColdResistance\n"
        "implicits:\n  - stat: '#% chance to Avoid being Shocked'\n    corrupted: true\n",
        header=False,
    )  # fmt: skip

    assert_error(message, 6, "implicits[0].stat", "names an ordinary implicit", "without `corrupted: true`")


def test_error_a_mod_key_that_is_another_mod_of_the_pool_names_the_selector():
    message = parse_error(f"implicits:\n  - stat: '{COLD_DAMAGE}'\n    corrupted: true\n    mod: FireCorrupted1\n")

    assert_error(message, 8, "implicits[0].mod", "`FireCorrupted1` is a corrupted implicit of a Ring", f"not of the stat `{COLD_DAMAGE}`")


def test_error_a_mod_key_that_is_no_corrupted_implicit_of_the_class_names_the_nearest_mod():
    message = parse_error(f"implicits:\n  - stat: '{COLD_DAMAGE}'\n    corrupted: true\n    mod: ColdResist1\n")

    assert_error(message, 8, "implicits[0].mod", "`ColdResist1` is not a corrupted implicit of this item class", "`ColdCorrupted1`")


def test_error_a_base_with_no_corrupted_pool_cannot_be_asked_for_one():
    message = parse_error(
        f"base: {FLASK}\nitem_level: 84\nrequirements:\n  - family: ColdResistance\nimplicits:\n  - family: AddedCold\n    corrupted: true\n",
        header=False,
    )  # fmt: skip

    assert_error(message, 6, "implicits[0].family", "cannot be asked for here", "Small Life Flask", "no corrupted implicit pool")


# -- allow_corrupted and the goal check ------------------------------------------------------------------


def test_allow_corrupted_is_a_top_level_key_that_defaults_to_false():
    assert parse("allow_corrupted: true\n").allow_corrupted is True
    assert parse("allow_corrupted: false\n").allow_corrupted is False
    assert parse("").allow_corrupted is False


def test_allow_corrupted_must_be_true_or_false():
    assert_error(parse_error("allow_corrupted: sometimes\n"), 5, "allow_corrupted", "must be true or false", '"sometimes"')


def test_a_corrupted_ring_meeting_every_mod_requirement_is_not_a_goal_for_a_target_without_either_key():
    target = parse("")
    finished = corrupted_ring()

    assert not target.unmet(finished)  # it holds everything the target names
    assert not target.is_met_by(finished)
    assert target.is_met_by(finished.changed(DATA, corrupted=False))


def test_allow_corrupted_makes_a_corrupted_item_without_a_corrupted_implicit_a_goal():
    target = parse("allow_corrupted: true\n")

    assert target.is_met_by(corrupted_ring())
    assert target.is_met_by(corrupted_ring().changed(DATA, corrupted=False))
    assert not target.is_met_by(corrupted_ring(mods=()).changed(DATA, mods=()))  # the mod requirements still count


def test_a_target_that_asks_for_a_corrupted_implicit_is_met_by_a_corrupted_item_that_holds_it_only():
    target = parse(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\n")
    held = corrupted_ring(implicits=(ImplicitMod("ResistCorrupted", 0, (15,)),))

    assert target.is_met_by(held)
    assert not target.is_met_by(corrupted_ring())
    assert not target.is_met_by(held.changed(DATA, corrupted=False, implicits=()))


def test_a_corrupted_implicit_requirement_is_not_met_by_an_item_that_is_not_corrupted():
    wish = ImplicitRequirement(None, ALL_RES, frozenset({"ResistCorrupted"}), None, None, True)
    held = corrupted_ring(implicits=(ImplicitMod("ResistCorrupted", 0, (15,)),))

    assert wish.is_met_by(held)
    assert not wish.is_met_by(Item(RING, 84, Rarity.RARE, implicits=held.implicits))  # built without the check of `Item.build`


# -- the corrupted start item ----------------------------------------------------------------------------


def test_error_a_corrupted_start_item_under_a_target_that_neither_asks_nor_allows_is_refused():
    message = parse_error("start_item:\n  corrupted: true\n")

    assert_error(message, 6, "start_item.corrupted", "the start item is corrupted", "neither asks for a corrupted implicit", "allow_corrupted")


def test_a_corrupted_start_item_is_taken_by_a_target_that_allows_or_asks():
    allowed = parse("allow_corrupted: true\nstart_item:\n  corrupted: true\n")
    asked = parse(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\nstart_item:\n  corrupted: true\n")

    assert allowed.start_item.corrupted and asked.start_item.corrupted


def test_a_start_item_may_hold_a_corrupted_implicit_when_it_is_corrupted():
    target = parse(
        f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\n"
        "start_item:\n  corrupted: true\n  implicits:\n    - mod: ResistCorrupted\n      values: 15\n"
    )

    assert target.start_item.implicits == (ImplicitMod("ResistCorrupted", 0, (15,)),)
    assert target.implicits[0].is_met_by(target.start_item)


def test_error_a_start_item_that_is_not_corrupted_cannot_hold_a_corrupted_implicit():
    message = parse_error("start_item:\n  implicits:\n    - mod: ResistCorrupted\n      values: 15\n")

    assert_error(message, 7, "start_item.implicits[0]", "ResistCorrupted", "only a corrupted item holds")


def test_a_corrupted_implicit_on_an_item_needs_the_item_to_be_corrupted_the_grade_0_and_a_mod_of_the_class():
    held = ImplicitMod("ResistCorrupted", 0, (15,))
    base = {"base_id": RING, "item_level": 84, "rarity": Rarity.RARE}

    assert Item.build(DATA, corrupted=True, implicits=(held,), **base).implicits == (held,)
    with pytest.raises(ImplicitError, match="only a corrupted item holds"):
        Item.build(DATA, implicits=(held,), **base)
    with pytest.raises(ImplicitError, match="its grade is 0, not 2"):
        Item.build(DATA, corrupted=True, implicits=(ImplicitMod("ResistCorrupted", 2, (15,)),), **base)
    with pytest.raises(ImplicitError, match="not one a Ring can get"):
        Item.build(DATA, corrupted=True, implicits=(ImplicitMod("BeltOnlyCorrupted", 0, (12,)),), **base)
    with pytest.raises(ImplicitError, match="neither an implicit of the base nor an Eldritch implicit nor a corrupted implicit"):
        Item.build(DATA, corrupted=True, implicits=(ImplicitMod("ColdResist1", 0, (8,)),), **base)


# -- how many corrupted implicits the target can get -----------------------------------------------------

TWO = f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\n  - stat: '{COLD_DAMAGE}'\n    corrupted: true\n"


def test_two_corrupted_implicits_of_different_groups_parse_by_default_the_locus_gives_two():
    target = parse(TWO)

    assert [wish.mod_ids for wish in target.implicits] == [{"ResistCorrupted"}, COLD_TIERS]


def test_error_more_corrupted_implicits_than_actions_give_names_the_kinds_and_the_entry_too_many():
    message = parse_error(TWO + "actions: [vaal, chaos-orb]\n")

    assert_error(
        message, 8, "implicits[1]", "asks for 2 corrupted implicits", "the corrupting kinds in `actions:` (`vaal`) give at most 1",
        COLD_DAMAGE, "add `locus` to `actions:`",
    )  # fmt: skip


def test_error_a_target_that_names_no_corrupting_kind_gets_no_corrupted_implicit():
    message = parse_error(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\nactions: [chaos-orb]\n")

    assert_error(message, 6, "implicits[0]", "asks for 1 corrupted implicit,", "`actions:` names no corrupting kind", "`vaal`", "`locus`")


def test_two_corrupted_implicits_parse_when_actions_name_the_locus():
    assert len(parse(TWO + "actions: [locus]\n").implicits) == 2


def test_error_three_corrupted_implicits_are_more_than_any_action_gives():
    message = parse_error(TWO + f"  - stat: '{FIRE_DAMAGE}'\n    corrupted: true\n")

    assert_error(message, 10, "implicits[2]", "asks for 3 corrupted implicits", "the Vaal Orb gives one", "the Locus of Corruption two")


def test_the_corrupting_fossil_set_gives_one():
    assert len(parse(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\nactions: [fossil-set]\n").implicits) == 1
    message = parse_error(TWO + "actions: [fossil-set, vaal]\n")
    assert_error(message, 8, "implicits[1]", "(`fossil-set`, `vaal`) give at most 1")


@pytest.mark.parametrize("suffix", ["start_price: Bought ring\nactions: [vaal]\n", "actions: [vaal]\nstart_item:\n  corrupted: true\n"])
def test_it_is_not_an_error_when_the_target_buys_its_item(suffix):
    target = parse(TWO + suffix)

    assert len(target.implicits) == 2


def test_a_target_that_buys_its_item_may_leave_out_every_corrupting_kind():
    target = parse(f"implicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\nstart_price: Bought ring\nactions: [chaos-orb]\n")

    assert target.start_price == "Bought ring" and target.actions == ("chaos-orb",)


# -- two of one mod group --------------------------------------------------------------------------------

SAME_GROUP = (
    f"implicits:\n  - stat: '{COLD_DAMAGE}'\n    corrupted: true\n    mod: ColdCorrupted1\n"
    f"  - stat: '{COLD_DAMAGE}'\n    corrupted: true\n    mod: ColdCorrupted2\n"
)


def test_error_two_corrupted_implicits_of_one_mod_group_name_the_group_and_the_nearest_mod_of_another():
    message = parse_error(SAME_GROUP)

    assert_error(
        message, 9, "implicits[1]", "implicits[0] and implicits[1] are both of the mod group `AddedCold`",
        "`ColdCorrupted1`", "`ColdCorrupted2`", "Locus of Corruption", "another mod group than the first",
        '`FireCorrupted1` ("Adds # to # Fire Damage to Spells and Attacks")',
    )  # fmt: skip


def test_two_family_entries_of_one_group_are_the_same_error():
    message = parse_error("implicits:\n  - family: AddedCold\n    corrupted: true\n    mod: ColdCorrupted1\n  - family: AddedCold\n    corrupted: true\n    mod: ColdCorrupted3\n")

    assert_error(message, 9, "implicits[1]", "mod group `AddedCold`")


def test_two_entries_one_implicit_could_meet_are_not_two_implicits():
    both = f"implicits:\n  - stat: '{COLD_DAMAGE}'\n    corrupted: true\n  - family: AddedCold\n    corrupted: true\n    mod: ColdCorrupted2\n"

    assert len(parse(both + "actions: [vaal]\n").implicits) == 2


def test_it_is_not_an_error_when_the_target_buys_its_item_and_two_groups_clash():
    assert len(parse(SAME_GROUP + "start_price: Bought ring\n").implicits) == 2


# -- more implicits than the item holds after corruption -------------------------------------------------


def test_error_a_base_implicit_asked_with_a_corrupted_one_on_a_one_implicit_base_cannot_both_stay():
    message = parse_error(f"implicits:\n  - stat: '{ALL_RES}'\n  - stat: '{COLD_DAMAGE}'\n    corrupted: true\n")

    assert_error(
        message, 7, "implicits[1]", "asks for 2 implicits in all", "a corrupting action replaces implicits instead of adding to them",
        "a Prismatic Ring can hold 1 implicit (`RingResistImplicit`)", "at most 0 of them stay",
    )  # fmt: skip


def test_the_same_two_implicits_are_fine_when_the_target_buys_a_corrupted_item_that_cannot_hold_both_the_error_stays():
    message = parse_error(
        f"implicits:\n  - stat: '{ALL_RES}'\n  - stat: '{COLD_DAMAGE}'\n    corrupted: true\nstart_price: Bought ring\n"
    )

    assert_error(message, 7, "implicits[1]", "asks for 2 implicits in all")


def test_a_ring_with_no_implicit_asked_for_a_corrupted_one_alone_is_fine():
    target = parse(f"base: Iron Ring\nitem_level: 84\nrequirements:\n  - family: ColdResistance\nimplicits:\n  - stat: '{ALL_RES}'\n    corrupted: true\n", header=False)

    assert target.base_id == PLAIN_RING and target.implicits[0].mod_ids == {"ResistCorrupted"}


BODY_HEAD = "base: Plate Vest\nitem_level: 84\nrequirements:\n  - family: ColdResistance\n"
AVOID = "  - stat: '#% chance to Avoid being Shocked'\n"
SHOCK = "  - stat: '#% chance to Shock'\n"
RES_BODY = f"  - stat: '{ALL_RES}'\n    corrupted: true\n"


def test_one_eldritch_implicit_and_one_corrupted_one_fit_on_body_armour_where_two_eldritch_implicits_and_a_corrupted_one_do_not():
    one = parse(BODY_HEAD + "implicits:\n" + AVOID + RES_BODY, header=False)
    assert [wish.corrupted for wish in one.implicits] == [False, True]

    message = parse_error(BODY_HEAD + "implicits:\n" + AVOID + SHOCK + RES_BODY, header=False)
    assert_error(message, 8, "implicits[2]", "asks for 3 implicits in all", "a Plate Vest can hold 2 implicits", "at most 1 of them stay")


def test_the_locus_replaces_two_so_one_eldritch_implicit_and_one_corrupted_one_need_the_vaal_orb():
    ok = parse(BODY_HEAD + "implicits:\n" + AVOID + RES_BODY + "actions: [vaal, locus]\n", header=False)
    assert len(ok.implicits) == 2

    message = parse_error(BODY_HEAD + "implicits:\n" + AVOID + RES_BODY + "actions: [locus]\n", header=False)
    assert_error(message, 7, "implicits[1]", "asks for 2 implicits in all", "after `locus` (which adds 2) at most 0 of them stay")


def test_a_target_file_without_the_keys_parses_as_before():
    text = "implicits:\n  - stat: '%s'\nstart_item:\n  rarity: rare\n  mods:\n    - mod: ColdResist1\n      tier: 1\n      values: [8]\n" % ALL_RES
    target = parse(text)

    assert target.allow_corrupted is False and not target.asks_corrupted and not target.takes_corrupted
    assert [wish.corrupted for wish in target.implicits] == [False]
    assert target.start_item.corrupted is False
    assert target.implicits[0].mod_ids == {"RingResistImplicit"}
    assert not target.is_met_by(target.start_item)  # an ordinary target still reads the same
