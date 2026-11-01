"""Socket targets, plain quality and the start item's sockets (ticket #227, ADR-0046, ADR-0049, ADR-0008 amendment).

The text of a test starts on line 5 (`targets_sockets_support.parse`: `base`, `item_level`, `requirements` with one Life entry before it);
the file is called `t.yaml`. Each refusal is one test and asserts the line, the key path and the words of the message that tell the
owner what is wrong. The data is the extended fixture data: Simple Robe (Body Armour, 6), Iron Greaves (Boots, 4), Rusted Sword
(One Hand Sword, 3), Paua Amulet and Heavy Belt (jewellery).
"""

import dataclasses

import pytest
from cli_support import R12, price_file
from items_support import AMULET, roll
from items_support import item as fixture_item
from targets_sockets_support import (
    ABYSS_BASE_DATA,
    ABYSS_DATA,
    ABYSS_MOD,
    DATA,
    ROBE,
    assert_error,
    assert_golden_json,
    dump_target,
    parse,
    parse_error,
    robe_with,
)
from targets_support import DATA as FIXTURE_DATA

from crafting_system.cli import PlanError, make_plan
from crafting_system.cli._route_card import card_of_item, card_of_target
from crafting_system.cli._route_html import _item
from crafting_system.items import CatalystType, Item, PlainQuality, Quality, Rarity, SocketColour, Sockets
from crafting_system.targets import (
    EnchantmentRequirement,
    ImplicitRequirement,
    PlainQualityRequirement,
    QualityRequirement,
    Requirement,
    SocketRequirement,
    Target,
    load_target,
)

WHITE = SocketColour.WHITE
RED, GREEN, BLUE = SocketColour.RED, SocketColour.GREEN, SocketColour.BLUE
SIX_LINK = "sockets: {count: 6, links: 6, colours: {R: 2, G: 2, B: 2}}\n"
ABYSS_START_MOD = f"start_item:\n  mods:\n    - mod: {ABYSS_MOD}\n      tier: 1\n      values: 1\n"


def start_sockets(body: str) -> str:
    """A `start_item:` block whose only key is `sockets:` with `body` (line 5 is `start_item:`, line 6 `sockets:`)."""
    return f"start_item:\n  sockets: {body}\n"


# -- A. a socket target, accepted -------------------------------------------------------------------


def test_a_six_link_target_with_colours_is_one_socket_requirement():
    target = parse(SIX_LINK)

    assert target.sockets == SocketRequirement(6, 6, 2, 2, 2)


def test_each_socket_key_stands_alone():
    assert parse("sockets: {count: 5}\n").sockets == SocketRequirement(count=5)
    assert parse("sockets: {links: 4}\n").sockets == SocketRequirement(links=4)
    assert parse("sockets: {colours: {R: 1, B: 2}}\n").sockets == SocketRequirement(red=1, blue=2)


def test_colours_alone_name_only_the_colours_given():
    wanted = parse("sockets: {colours: {G: 3}}\n").sockets

    assert (wanted.count, wanted.links) == (None, None)
    assert (wanted.red, wanted.green, wanted.blue, wanted.coloured) == (0, 3, 0, 3)


def test_a_block_style_target_reads_as_the_flow_style_one():
    target = parse("sockets:\n  count: 6\n  links: 5\n  colours:\n    R: 1\n    G: 1\n    B: 1\n")

    assert target.sockets == SocketRequirement(6, 5, 1, 1, 1)


def test_the_colours_may_fill_the_whole_group_and_the_group_the_whole_count():
    assert parse("sockets: {count: 3, links: 3, colours: {R: 1, G: 1, B: 1}}\n", base="Rusted Sword").sockets.coloured == 3


def test_a_target_with_sockets_and_a_start_item_that_states_none_assumes_one_white_unlinked_socket():
    target = parse(SIX_LINK)

    assert target.start_item.sockets == Sockets((WHITE,), (1,))
    assert target.start_sockets_assumed is True


def test_a_start_item_that_states_other_things_but_no_sockets_still_gets_the_assumed_socket():
    target = parse("sockets: {count: 3}\nstart_item:\n  quality: {percent: 10}\n")

    assert target.start_item.sockets == Sockets((WHITE,), (1,))
    assert target.start_item.quality == PlainQuality(10)
    assert target.start_sockets_assumed is True


def test_a_start_item_that_states_sockets_keeps_them_and_nothing_is_assumed():
    target = parse(SIX_LINK + start_sockets("{colours: [R, G, B, W], links: [3, 1]}"))

    assert target.start_item.sockets == Sockets((RED, GREEN, BLUE, WHITE), (3, 1))
    assert target.start_sockets_assumed is False


def test_a_target_without_sockets_creates_none_and_assumes_none():
    target = parse("start_item:\n  rarity: normal\n")

    assert target.sockets is None
    assert target.start_item.sockets is None
    assert target.start_sockets_assumed is False


def test_a_target_with_no_start_item_and_no_sockets_creates_none():
    target = parse("")

    assert (target.sockets, target.start_item.sockets, target.start_sockets_assumed) == (None, None, False)


def test_a_start_item_with_sockets_under_a_target_without_sockets_keeps_them_and_assumes_none():
    target = parse(start_sockets("{count: 2}"))

    assert target.sockets is None
    assert target.start_item.sockets == Sockets((WHITE, WHITE), (1, 1))
    assert target.start_sockets_assumed is False


def test_the_socket_requirement_adds_nothing_to_the_mod_requirements():
    with_sockets, without = parse(SIX_LINK), parse("")

    assert with_sockets.requirements == without.requirements
    assert len(with_sockets.requirements) == 1 and isinstance(with_sockets.requirements[0], Requirement)
    assert with_sockets.implicits == () and with_sockets.quality is None


# -- B. a socket target, refused --------------------------------------------------------------------


def test_links_above_count_are_refused_on_links():
    message = parse_error("sockets: {count: 4, links: 5}\n")

    assert_error(message, 5, "sockets.links", "a linked group of 5", "does not fit", "`count` 4")


def test_colours_above_links_are_refused_on_colours():
    message = parse_error("sockets: {links: 3, colours: {R: 2, G: 2}}\n")

    assert_error(message, 5, "sockets.colours", "4 coloured sockets", "R 2, G 2, B 0", "one linked group of 3", "`links`")


def test_colours_above_count_without_links_are_refused_on_colours():
    message = parse_error("sockets: {count: 3, colours: {R: 2, G: 2}}\n")

    assert_error(message, 5, "sockets.colours", "4 coloured sockets", "more than the 3 sockets of `count`")


def test_colours_that_fit_the_count_are_accepted_without_links():
    assert parse("sockets: {count: 4, colours: {R: 2, G: 2}}\n").sockets == SocketRequirement(4, None, 2, 2, 0)


def test_count_above_six_is_refused_on_count():
    message = parse_error("sockets: {count: 7}\n")

    assert_error(message, 5, "sockets.count", "must be a whole number from 1 to 6", "got 7")


def test_count_zero_is_refused_on_count():
    message = parse_error("sockets: {count: 0}\n")

    assert_error(message, 5, "sockets.count", "must be a whole number from 1 to 6", "got 0")


def test_a_count_that_is_not_a_number_is_refused_on_count():
    message = parse_error("sockets: {count: x}\n")

    assert_error(message, 5, "sockets.count", "must be a whole number from 1 to 6", 'got "x"')


def test_a_fractional_count_is_refused_on_count():
    message = parse_error("sockets: {count: 2.5}\n")

    assert_error(message, 5, "sockets.count", "must be a whole number")


def test_a_true_count_is_not_a_whole_number():
    message = parse_error("sockets: {count: true}\n")

    assert_error(message, 5, "sockets.count", "must be a whole number")


def test_links_of_one_are_refused_because_one_socket_is_no_link():
    message = parse_error("sockets: {links: 1}\n")

    assert_error(message, 5, "sockets.links", "must be a whole number from 2 to 6", "a group of one socket is no link", "got 1")


def test_links_above_six_are_refused_on_links():
    message = parse_error("sockets: {links: 7}\n")

    assert_error(message, 5, "sockets.links", "from 2 to 6", "got 7")


def test_the_line_of_the_wrong_key_is_the_line_it_is_written_on():
    message = parse_error("sockets:\n  count: 3\n  links: 9\n")

    assert_error(message, 7, "sockets.links", "from 2 to 6", "got 9")


def test_count_above_the_class_maximum_of_boots_names_the_maximum_and_the_class():
    message = parse_error("sockets: {count: 5}\n", base="Iron Greaves")

    assert_error(message, 5, "sockets.count", "5 sockets", "class maximum of 4", "Iron Greaves", "Boots")


def test_a_link_size_above_the_class_maximum_of_a_one_hand_sword_names_three():
    message = parse_error("sockets: {links: 4}\n", base="Rusted Sword")

    assert_error(message, 5, "sockets.links", "a linked group of 4", "class maximum of 3", "Rusted Sword", "One Hand Sword")


def test_a_count_above_the_class_maximum_of_a_one_hand_sword_names_three():
    message = parse_error("sockets: {count: 4}\n", base="Rusted Sword")

    assert_error(message, 5, "sockets.count", "4 sockets", "class maximum of 3")


def test_the_class_maximum_of_a_body_armour_is_six_so_six_is_accepted_and_boots_take_four():
    assert parse("sockets: {count: 6, links: 6}\n").sockets == SocketRequirement(6, 6)
    assert parse("sockets: {count: 4, links: 4}\n", base="Iron Greaves").sockets == SocketRequirement(4, 4)
    assert parse("sockets: {count: 3, links: 3}\n", base="Rusted Sword").sockets == SocketRequirement(3, 3)


def test_a_colour_total_above_the_maximum_is_refused_on_colours_when_no_count_is_given():
    message = parse_error("sockets: {colours: {R: 3, G: 2}}\n", base="Iron Greaves")

    assert_error(message, 5, "sockets.colours", "5 coloured sockets", "class maximum of 4", "Iron Greaves")


def test_a_colour_total_above_six_is_refused_on_a_body_armour_too():
    message = parse_error("sockets: {colours: {R: 3, G: 3, B: 1}}\n")

    assert_error(message, 5, "sockets.colours", "7 coloured sockets", "class maximum of 6")


def test_an_empty_sockets_mapping_is_refused_on_sockets():
    message = parse_error("sockets: {}\n")

    assert_error(message, 5, "sockets", "name at least one of `count`, `links` and `colours`", "empty mapping")


def test_sockets_that_are_not_a_mapping_are_refused_on_sockets():
    message = parse_error("sockets: 5\n")

    assert_error(message, 5, "sockets", "must be a mapping with `count`, `links` and `colours`", "got 5")


def test_sockets_that_are_a_list_are_refused_on_sockets():
    message = parse_error("sockets: [3, 4]\n")

    assert_error(message, 5, "sockets", "must be a mapping")


def test_an_unknown_socket_key_is_refused_with_the_hint_count():
    message = parse_error("sockets: {cnt: 5}\n")

    assert_error(message, 5, "sockets.cnt", "unknown key `cnt`", "did you mean `count`?")


def test_colours_that_are_not_a_mapping_are_refused_on_colours():
    message = parse_error("sockets: {colours: 3}\n")

    assert_error(message, 5, "sockets.colours", "must be a mapping with `R`, `G` and `B` counts", "got 3")


def test_empty_colours_are_refused_on_colours():
    message = parse_error("sockets: {colours: {}}\n")

    assert_error(message, 5, "sockets.colours", "name at least one of `R`, `G` and `B`")


def test_an_unknown_colour_key_is_refused_naming_the_allowed_ones():
    message = parse_error("sockets: {colours: {X: 1}}\n")

    assert_error(message, 5, "sockets.colours.X", "unknown key `X`", "`R`, `G`, `B`")


def test_a_lower_case_colour_key_is_not_accepted():
    message = parse_error("sockets: {colours: {r: 1}}\n")

    assert_error(message, 5, "sockets.colours.r", "unknown key `r`")


def test_a_colour_count_of_zero_is_refused_and_says_to_leave_the_colour_out():
    message = parse_error("sockets: {colours: {R: 0}}\n")

    assert_error(message, 5, "sockets.colours.R", "from 1 to 6", "leave the colour out", "got 0")


def test_a_colour_count_of_seven_is_refused_on_that_colour():
    message = parse_error("sockets: {colours: {G: 1, B: 7}}\n")

    assert_error(message, 5, "sockets.colours.B", "from 1 to 6", "got 7")


@pytest.mark.parametrize("base", ["Paua Amulet", "Heavy Belt"])
def test_a_socket_target_on_jewellery_is_refused_and_the_message_says_jewellery(base):
    message = parse_error("sockets: {count: 3}\n", base=base)

    assert_error(message, 5, "sockets", base, "jewellery", "out of scope", "ADR-0046")


def test_a_corrupted_start_item_is_refused_on_the_sockets_key_when_the_target_allows_corruption():
    message = parse_error("allow_corrupted: true\nstart_item:\n  corrupted: true\nsockets: {count: 3}\n")

    assert_error(message, 8, "sockets", "corrupted item takes no socket orb", "`start_item.corrupted`")


def test_the_line_of_a_corrupted_refusal_is_the_sockets_key_wherever_it_stands():
    message = parse_error("sockets: {count: 3}\nallow_corrupted: true\nstart_item:\n  corrupted: true\n")

    assert_error(message, 5, "sockets", "corrupted item takes no socket orb")


def test_a_corrupted_start_item_without_allow_corrupted_is_already_refused_by_the_corruption_check():
    message = parse_error("start_item:\n  corrupted: true\nsockets: {count: 3}\n")

    assert_error(message, 6, "start_item.corrupted", "could never become the goal")


def test_a_corrupted_start_item_is_fine_for_a_target_without_sockets():
    assert parse("allow_corrupted: true\nstart_item:\n  corrupted: true\n").start_item.corrupted is True


def test_an_abyssal_socket_mod_on_the_start_item_is_refused_on_the_sockets_key():
    message = parse_error("sockets: {count: 3}\n" + ABYSS_START_MOD, data=ABYSS_DATA)

    assert_error(message, 5, "sockets", "start item has an Abyssal Socket", "out of scope", "ADR-0046")


def test_an_abyssal_socket_as_an_implicit_of_the_base_is_refused_on_the_sockets_key():
    message = parse_error("sockets: {count: 3}\n", data=ABYSS_BASE_DATA)

    assert_error(message, 5, "sockets", "start item has an Abyssal Socket", "implicit of the base")


def test_a_requirement_that_can_give_an_abyssal_socket_is_blamed_on_its_own_entry():
    message = parse_error("  - family: AbyssSocket\nsockets: {count: 3}\n", data=ABYSS_DATA)

    assert_error(message, 5, "requirements[1]", "can put an Abyssal Socket on the item", "out of scope")


def test_a_requirement_inside_an_at_least_group_that_can_give_an_abyssal_socket_is_blamed_on_the_group():
    message = parse_error(
        "  - at_least: 1\n    of:\n      - family: AbyssSocket\n      - family: IncreasedMana\nsockets: {count: 3}\n", data=ABYSS_DATA
    )

    assert_error(message, 5, "requirements[1]", "can put an Abyssal Socket on the item")


def test_an_abyssal_socket_is_no_problem_for_a_target_without_sockets():
    wants_abyss = parse("  - family: AbyssSocket\nallow_corrupted: false\n", data=ABYSS_DATA)
    holds_abyss = parse(ABYSS_START_MOD, data=ABYSS_DATA)
    base_has_it = parse("", data=ABYSS_BASE_DATA)

    assert wants_abyss.sockets is None and holds_abyss.sockets is None and base_has_it.sockets is None


# -- C. the start item's sockets --------------------------------------------------------------------


def test_start_colours_and_links_give_the_sockets_as_written():
    item = parse(start_sockets("{colours: [R, G, B, W], links: [3, 1]}")).start_item

    assert item.sockets == Sockets((RED, GREEN, BLUE, WHITE), (3, 1))


def test_a_start_count_alone_gives_white_unlinked_sockets():
    item = parse(start_sockets("{count: 3}")).start_item

    assert item.sockets == Sockets((WHITE, WHITE, WHITE), (1, 1, 1))


def test_start_links_alone_give_white_sockets_and_the_count_is_their_sum():
    item = parse(start_sockets("{links: [2, 2, 1]}")).start_item

    assert item.sockets == Sockets((WHITE,) * 5, (2, 2, 1))


def test_start_colours_alone_are_unlinked():
    item = parse(start_sockets("{colours: [R, R]}")).start_item

    assert item.sockets == Sockets((RED, RED), (1, 1))


def test_start_colour_words_are_accepted_in_any_case():
    item = parse(start_sockets("{colours: [red, Green, BLUE, White]}")).start_item

    assert item.sockets.colours == (RED, GREEN, BLUE, WHITE)


def test_start_colour_letters_are_accepted_in_lower_case():
    item = parse(start_sockets("{colours: [r, g, b, w]}")).start_item

    assert item.sockets.colours == (RED, GREEN, BLUE, WHITE)


def test_start_count_and_colours_that_agree_are_accepted():
    item = parse(start_sockets("{count: 2, colours: [B, G]}")).start_item

    assert item.sockets == Sockets((BLUE, GREEN), (1, 1))


def test_start_count_and_colours_that_disagree_are_refused_on_count():
    message = parse_error(start_sockets("{count: 3, colours: [R, G]}"))

    assert_error(message, 6, "start_item.sockets.count", "is 3", "`colours` lists 2 sockets", "must agree")


def test_start_links_that_do_not_add_up_are_refused_on_links():
    message = parse_error(start_sockets("{count: 3, links: [2, 2]}"))

    assert_error(message, 6, "start_item.sockets.links", "[2, 2]", "add up to 4", "the item has 3")


def test_start_links_that_do_not_add_up_to_the_colours_are_refused_on_links():
    message = parse_error(start_sockets("{colours: [R, G, B], links: [2]}"))

    assert_error(message, 6, "start_item.sockets.links", "add up to 2", "the item has 3")


def test_a_start_count_above_six_is_refused_on_count():
    message = parse_error(start_sockets("{count: 7}"))

    assert_error(message, 6, "start_item.sockets.count", "from 1 to 6", "got 7")


def test_seven_start_colours_are_refused_on_sockets():
    message = parse_error(start_sockets("{colours: [R, R, R, R, R, R, R]}"))

    assert_error(message, 6, "start_item.sockets", "7 sockets", "more than the 6 any item can have")


def test_start_links_adding_up_to_seven_are_refused_on_sockets():
    message = parse_error(start_sockets("{links: [3, 3, 1]}"))

    assert_error(message, 6, "start_item.sockets", "7 sockets", "more than the 6")


def test_a_bad_start_colour_name_lists_the_allowed_ones():
    message = parse_error(start_sockets("{colours: [R, purple]}"))

    assert_error(message, 6, "start_item.sockets.colours[1]", "`W`, `R`, `G`, `B`", "red, green, blue, white", 'got "purple"')


def test_a_start_colour_that_is_not_a_word_is_refused_on_its_entry():
    message = parse_error(start_sockets("{colours: [R, 3]}"))

    assert_error(message, 6, "start_item.sockets.colours[1]", "`W`, `R`, `G`, `B`", "got 3")


def test_start_colours_that_are_not_a_list_are_refused_on_colours():
    message = parse_error(start_sockets("{colours: RGB}"))

    assert_error(message, 6, "start_item.sockets.colours", "non-empty list of socket colours")


def test_start_links_that_are_not_a_list_are_refused_on_links():
    message = parse_error(start_sockets("{links: 3}"))

    assert_error(message, 6, "start_item.sockets.links", "non-empty list of link group sizes", "got 3")


def test_a_start_link_group_of_zero_is_refused_on_its_entry():
    message = parse_error(start_sockets("{links: [3, 0]}"))

    assert_error(message, 6, "start_item.sockets.links[1]", "from 1 to 6", "got 0")


def test_an_unknown_start_socket_key_is_refused_with_the_hint_count():
    message = parse_error(start_sockets("{cnt: 3}"))

    assert_error(message, 6, "start_item.sockets.cnt", "unknown key `cnt`", "did you mean `count`?")


def test_an_empty_start_sockets_mapping_is_refused():
    message = parse_error(start_sockets("{}"))

    assert_error(message, 6, "start_item.sockets", "name at least one of `count`, `colours` and `links`", "states no sockets")


def test_start_sockets_that_are_not_a_mapping_are_refused():
    message = parse_error(start_sockets("3"))

    assert_error(message, 6, "start_item.sockets", "must be a mapping with `colours`, `count` and `links`", "got 3")


def test_more_start_sockets_than_the_class_maximum_are_blamed_on_the_sockets_key():
    message = parse_error(start_sockets("{count: 5}"), base="Iron Greaves")

    assert_error(message, 6, "start_item.sockets", "5 sockets", "Iron Greaves", "Boots", "at most 4")


def test_start_sockets_on_a_start_item_of_jewellery_are_blamed_on_the_sockets_key():
    message = parse_error(start_sockets("{count: 2}"), base="Paua Amulet")

    assert_error(message, 6, "start_item.sockets", "sockets need a weapon or armour base", "this one is Amulet")


def test_the_line_of_a_start_socket_refusal_is_the_sockets_key_not_the_start_item_key():
    message = parse_error("start_item:\n  rarity: rare\n  sockets: {count: 5}\n", base="Iron Greaves")

    assert_error(message, 7, "start_item.sockets", "at most 4")


# -- D. plain quality -------------------------------------------------------------------------------


def test_a_plain_quality_target_on_a_body_armour_is_a_plain_quality_requirement():
    target = parse("quality: {min_percent: 20}\n")

    assert target.quality == PlainQualityRequirement(20)
    assert target.quality.type is None


def test_a_plain_quality_target_works_on_a_weapon_too():
    assert parse("quality: {min_percent: 12}\n", base="Rusted Sword").quality == PlainQualityRequirement(12)


def test_the_catalyst_form_still_works_on_an_amulet():
    target = parse("quality: {type: Prismatic, min_percent: 12}\n", base="Paua Amulet")

    assert target.quality == QualityRequirement(CatalystType.PRISMATIC, 12)


def test_a_missing_type_on_an_amulet_still_errors():
    message = parse_error("quality: {min_percent: 12}\n", base="Paua Amulet")

    assert_error(message, 5, "quality.type", "this key is required but missing")


def test_a_type_on_a_body_armour_errors_with_the_catalyst_message_and_the_hint_to_leave_it_out():
    message = parse_error("quality: {type: prismatic, min_percent: 20}\n")

    assert_error(message, 5, "quality", "Simple Robe is a Body Armour", "catalyst quality can only be put on", "leave `type` out")


@pytest.mark.parametrize("percent", ["0", "31", "-1"])
def test_a_plain_min_percent_outside_one_to_thirty_is_refused(percent):
    message = parse_error(f"quality: {{min_percent: {percent}}}\n")

    assert_error(message, 5, "quality.min_percent", "must be a whole number from 1 to 30", f"got {percent}")


def test_a_plain_min_percent_that_is_not_a_number_is_refused():
    message = parse_error("quality: {min_percent: x}\n")

    assert_error(message, 5, "quality.min_percent", "from 1 to 30", 'got "x"')


def test_a_fractional_plain_min_percent_is_refused():
    message = parse_error("quality: {min_percent: 12.5}\n")

    assert_error(message, 5, "quality.min_percent", "must be a whole number")


def test_a_plain_quality_without_min_percent_is_refused():
    message = parse_error("quality: {}\n")

    assert_error(message, 5, "quality.min_percent", "this key is required but missing")


def test_an_unknown_plain_quality_key_is_refused():
    message = parse_error("quality: {min_percent: 20, percent: 20}\n")

    assert_error(message, 5, "quality.percent", "unknown key `percent`")


def test_a_plain_quality_above_twenty_with_no_start_quality_is_refused_naming_twenty_percent():
    message = parse_error("quality: {min_percent: 25}\n")

    assert_error(message, 5, "quality.min_percent", "25%", "20%", "Whetstones", "Scraps", "start_item.quality.percent")


def test_a_plain_quality_above_twenty_is_accepted_when_the_start_item_holds_it():
    target = parse("quality: {min_percent: 25}\nstart_item:\n  quality: {percent: 28}\n")

    assert target.quality == PlainQualityRequirement(25)
    assert target.start_item.quality == PlainQuality(28)


def test_a_plain_quality_above_what_the_start_item_holds_is_refused():
    message = parse_error("quality: {min_percent: 30}\nstart_item:\n  quality: {percent: 28}\n")

    assert_error(message, 5, "quality.min_percent", "30%", "20%", "30 or more")


def test_twenty_percent_is_buyable_so_no_start_quality_is_needed():
    assert parse("quality: {min_percent: 20}\n").quality == PlainQualityRequirement(20)


def test_quality_that_is_not_a_mapping_on_a_body_armour_names_min_percent():
    message = parse_error("quality: 20\n")

    assert_error(message, 5, "quality", "must be a mapping with `min_percent`", "plain quality", "got 20")


def test_quality_that_is_not_a_mapping_on_an_amulet_names_type_and_min_percent():
    message = parse_error("quality: 20\n", base="Paua Amulet")

    assert_error(message, 5, "quality", "`type` and `min_percent`", "got 20")


def test_a_plain_start_quality_on_a_body_armour_is_a_plain_quality():
    assert parse("start_item:\n  quality: {percent: 20}\n").start_item.quality == PlainQuality(20)


def test_a_start_quality_of_zero_is_no_quality():
    assert parse("start_item:\n  quality: {percent: 0}\n").start_item.quality is None


def test_a_start_quality_of_thirty_is_allowed_because_a_random_drop_reaches_it():
    assert parse("start_item:\n  quality: {percent: 30}\n").start_item.quality == PlainQuality(30)


def test_a_start_quality_above_thirty_is_refused():
    message = parse_error("start_item:\n  quality: {percent: 31}\n")

    assert_error(message, 6, "start_item.quality.percent", "from 0 to 30", "got 31")


def test_a_start_quality_with_a_catalyst_type_on_a_body_armour_is_the_item_error():
    message = parse_error("start_item:\n  quality: {type: prismatic, percent: 10}\n")

    assert_error(message, 6, "start_item.quality", "needs a base of item class", "this one is Body Armour")


def test_a_plain_start_percent_alone_on_an_amulet_misses_the_type():
    message = parse_error("start_item:\n  quality: {percent: 10}\n", base="Paua Amulet")

    assert_error(message, 6, "start_item.quality.type", "this key is required but missing")


def test_a_start_quality_without_percent_on_a_body_armour_is_refused():
    message = parse_error("start_item:\n  quality: {}\n")

    assert_error(message, 6, "start_item.quality.percent", "this key is required but missing")


def test_a_start_quality_that_is_not_a_mapping_on_a_body_armour_names_percent():
    message = parse_error("start_item:\n  quality: 20\n")

    assert_error(message, 6, "start_item.quality", "must be a mapping with `percent`", "plain quality", "got 20")


def test_a_start_quality_that_is_not_a_mapping_on_an_amulet_names_type_and_percent():
    message = parse_error("start_item:\n  quality: 20\n", base="Paua Amulet")

    assert_error(message, 6, "start_item.quality", "`type` and `percent`")


def test_a_catalyst_start_quality_on_an_amulet_still_works():
    target = parse("start_item:\n  quality: {type: prismatic, percent: 10}\n", base="Paua Amulet")

    assert target.start_item.quality == Quality(CatalystType.PRISMATIC, 10)


def test_a_plain_quality_target_and_a_socket_target_can_stand_together():
    target = parse(SIX_LINK + "quality: {min_percent: 20}\n")

    assert target.sockets == SocketRequirement(6, 6, 2, 2, 2)
    assert target.quality == PlainQualityRequirement(20)


# -- E. matching ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wanted", "colours", "links", "met"),
    [
        # count only
        (SocketRequirement(count=4), "WWWW", None, True),
        (SocketRequirement(count=4), "WWWWW", None, True),
        (SocketRequirement(count=4), "WWW", None, False),
        # links only: a group of at least N
        (SocketRequirement(links=3), "RGBW", (3, 1), True),
        (SocketRequirement(links=3), "RGBWW", (2, 3), True),
        (SocketRequirement(links=3), "RGBWWW", (4, 2), True),
        (SocketRequirement(links=3), "RGBWWW", (2, 2, 2), False),
        (SocketRequirement(links=3), "RGBW", None, False),
        (SocketRequirement(links=2), "WWW", (1, 2), True),
        (SocketRequirement(links=6), "WWWWWW", (6,), True),
        (SocketRequirement(links=6), "WWWWWW", (5, 1), False),
        # count and links together are both needed
        (SocketRequirement(count=6, links=5), "WWWWW", (5,), False),
        (SocketRequirement(count=6, links=5), "WWWWWW", (5, 1), True),
        (SocketRequirement(count=6, links=5), "WWWWWW", (3, 3), False),
        # colours counted in one group of at least `links`
        (SocketRequirement(links=3, red=1, green=1, blue=1), "RGBRGB", (3, 3), True),
        (SocketRequirement(links=3, red=1, green=1, blue=1), "RRGBBG", (3, 3), False),
        (SocketRequirement(links=2, red=1, green=1), "WWWWRG", (4, 2), True),
        (SocketRequirement(links=3, red=1, green=1, blue=1), "RGBWWW", (1, 1, 1, 3), False),
        (SocketRequirement(links=3, red=2), "RRWRRW", (3, 3), True),
        (SocketRequirement(links=3, red=3), "RRWRRW", (3, 3), False),
        (SocketRequirement(links=2, red=1, blue=1), "RBGG", (2, 2), True),
        (SocketRequirement(links=2, red=1, blue=1), "RGBG", (2, 2), False),
        (SocketRequirement(links=2, red=1, blue=1), "RGBG", (1, 1, 2), False),
        # colours without links are counted over the whole item
        (SocketRequirement(red=1, green=1, blue=1), "RGB", None, True),
        (SocketRequirement(red=1, green=1, blue=1), "RGB", (1, 2), True),
        (SocketRequirement(red=1, green=1, blue=1), "RRGG", None, False),
        (SocketRequirement(red=2, green=1), "RGWR", (2, 2), True),
        (SocketRequirement(count=4, red=2, blue=1), "RWBR", None, True),
        (SocketRequirement(count=4, red=2, blue=1), "RBR", None, False),
        # white sockets count for count and links, never for a colour
        (SocketRequirement(count=3), "WWW", None, True),
        (SocketRequirement(links=3), "WWW", (3,), True),
        (SocketRequirement(red=1), "WWW", None, False),
        (SocketRequirement(red=1), "WWR", None, True),
        (SocketRequirement(links=3, red=1), "WWW", (3,), False),
        (SocketRequirement(blue=2), "BWB", (3,), True),
        (SocketRequirement(blue=3), "BWB", (3,), False),
    ],
)
def test_the_socket_requirement_table_on_a_simple_robe(wanted, colours, links, met):
    assert wanted.is_met_by(robe_with(colours, links)) is met


def test_a_six_link_target_is_met_by_a_six_link_and_not_by_a_five_link_with_a_sixth_socket():
    wanted = parse(SIX_LINK).sockets

    assert wanted.is_met_by(robe_with("RGBRGB", (6,)))
    assert not wanted.is_met_by(robe_with("RGBRGB", (5, 1)))
    assert not wanted.is_met_by(robe_with("RRRRGB", (6,)))


@pytest.mark.parametrize(
    "wanted",
    [
        SocketRequirement(count=1),
        SocketRequirement(links=2),
        SocketRequirement(red=1),
        SocketRequirement(count=1, links=2, red=1),
    ],
)
def test_an_item_with_no_sockets_meets_no_socket_requirement(wanted):
    assert not wanted.is_met_by(fixture_item(roll("IncreasedLife1")))


def test_an_item_with_no_sockets_is_not_met_even_by_a_requirement_of_one_socket():
    assert fixture_item().sockets is None
    assert not SocketRequirement(count=1).is_met_by(fixture_item())


def test_a_requirement_is_hashable_and_compares_by_its_fields():
    assert SocketRequirement(6, 5, 1, 1, 1) == SocketRequirement(count=6, links=5, red=1, green=1, blue=1)
    assert len({SocketRequirement(count=3), SocketRequirement(count=3)}) == 1


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"red": 0, "green": 0, "blue": 0},
        {"count": 0},
        {"count": -1},
        {"links": 0},
        {"links": -2},
        {"red": -1},
        {"green": -1, "count": 3},
        {"blue": -1, "links": 2},
        {"count": 2.0},
        {"count": True},
        {"links": "3"},
        {"red": 1.5},
    ],
)
def test_a_malformed_socket_requirement_raises_value_error(fields):
    with pytest.raises(ValueError, match="socket requirement"):
        SocketRequirement(**fields)


def test_a_socket_requirement_with_one_colour_alone_is_allowed():
    assert SocketRequirement(blue=1).coloured == 1


def test_coloured_is_the_sum_of_the_three_colours():
    assert SocketRequirement(red=1, green=2, blue=3).coloured == 6


@pytest.mark.parametrize(("have", "met"), [(20, True), (21, True), (30, True), (19, False), (1, False)])
def test_a_plain_quality_requirement_is_met_at_and_above_its_percent(have, met):
    item = Item.build(DATA, base_id=ROBE, item_level=84, rarity=Rarity.NORMAL, quality=PlainQuality(have))

    assert PlainQualityRequirement(20).is_met_by(item) is met


def test_a_plain_quality_requirement_is_not_met_by_an_item_with_no_quality():
    assert not PlainQualityRequirement(1).is_met_by(fixture_item())
    assert not PlainQualityRequirement(1).is_met_by(Item.build(DATA, base_id=ROBE, item_level=84, rarity=Rarity.NORMAL, quality=PlainQuality(0)))


def test_a_plain_quality_requirement_is_not_met_by_a_catalyst_quality():
    amulet = fixture_item(base_id=AMULET, quality=Quality(CatalystType.PRISMATIC, 20))

    assert not PlainQualityRequirement(10).is_met_by(amulet)


def test_a_catalyst_quality_requirement_is_not_met_by_a_plain_quality():
    robe = Item.build(DATA, base_id=ROBE, item_level=84, rarity=Rarity.NORMAL, quality=PlainQuality(20))

    assert not QualityRequirement(CatalystType.PRISMATIC, 5).is_met_by(robe)


@pytest.mark.parametrize("percent", [0, -1, 1.5, True])
def test_a_plain_quality_requirement_below_one_percent_or_not_whole_raises_value_error(percent):
    with pytest.raises(ValueError, match="plain quality requirement"):
        PlainQualityRequirement(percent)


def full_target(**fields) -> Target:
    """A Simple Robe target holding every kind of condition, none of which a bare item meets."""
    base = parse("quality: {min_percent: 20}\n" + SIX_LINK)
    implicit = ImplicitRequirement(None, "x", frozenset({"StrengthImplicitBelt1"}))
    enchantment = EnchantmentRequirement(("x",), frozenset({"x"}))
    return dataclasses.replace(base, implicits=(implicit,), enchantment=enchantment, **fields)


def test_unmet_lists_the_socket_requirement_last_after_requirements_implicits_quality_and_enchantment():
    target = full_target()

    unmet = target.unmet(fixture_item())

    assert [type(condition) for condition in unmet] == [
        Requirement,
        ImplicitRequirement,
        PlainQualityRequirement,
        EnchantmentRequirement,
        SocketRequirement,
    ]
    assert unmet[-1] == SocketRequirement(6, 6, 2, 2, 2)


def test_unmet_leaves_out_the_socket_requirement_when_the_sockets_are_met():
    target = parse(SIX_LINK)
    met = fixture_item(roll("IncreasedLife1"), sockets=Sockets((RED, GREEN, BLUE, RED, GREEN, BLUE), (6,)))

    assert target.unmet(met) == ()


def test_unmet_names_only_the_socket_requirement_when_everything_else_is_met():
    target = parse(SIX_LINK + "quality: {min_percent: 20}\n")
    item = fixture_item(roll("IncreasedLife1"), quality=PlainQuality(20), sockets=Sockets((RED, GREEN, BLUE, RED, GREEN, BLUE), (5, 1)))

    assert target.unmet(item) == (target.sockets,)


def test_a_target_without_sockets_has_no_socket_condition_in_unmet():
    target = parse("quality: {min_percent: 20}\n")

    assert [type(condition) for condition in target.unmet(fixture_item())] == [Requirement, PlainQualityRequirement]


def test_the_target_is_met_by_an_item_that_holds_the_mods_the_quality_and_the_sockets():
    target = parse(SIX_LINK + "quality: {min_percent: 20}\n")
    item = fixture_item(roll("IncreasedLife1"), quality=PlainQuality(20), sockets=Sockets((RED, GREEN, BLUE, RED, GREEN, BLUE), (6,)))

    assert target.is_met_by(item) is True


def test_the_target_is_not_met_when_only_the_sockets_are_not():
    target = parse(SIX_LINK)
    item = fixture_item(roll("IncreasedLife1"), sockets=Sockets((RED, GREEN, BLUE, RED, GREEN, BLUE), (3, 3)))

    assert target.requirements[0].is_met_by(item)
    assert target.is_met_by(item) is False


def test_the_target_is_not_met_by_an_item_with_no_sockets_at_all():
    target = parse("sockets: {count: 1}\n")

    assert target.is_met_by(fixture_item(roll("IncreasedLife1"))) is False


def test_the_assumed_start_item_does_not_meet_a_socket_target_of_two_sockets():
    target = parse("sockets: {count: 2}\n")

    assert target.start_item.sockets.count == 1
    assert not target.sockets.is_met_by(target.start_item)


def test_a_start_item_that_already_meets_the_sockets_meets_that_condition():
    target = parse(SIX_LINK + start_sockets("{colours: [R, G, B, R, G, B], links: [6]}"))

    assert target.sockets.is_met_by(target.start_item)


# -- F. golden parses -------------------------------------------------------------------------------


SIX_LINK_TARGET = """\
base: Simple Robe
item_level: 84
requirements:
  - family: IncreasedLife
    min_tier: 3
sockets:
  count: 6
  links: 6
  colours: {R: 2, G: 2, B: 2}
quality:
  min_percent: 20
start_item:
  rarity: rare
  mods:
    - mod: IncreasedLife1
      tier: 3
      values: [12]
  quality:
    percent: 12
  sockets:
    colours: [R, G, B, W, W, W]
    links: [3, 2, 1]
"""

PLAIN_QUALITY_TARGET = """\
base: Rusted Sword
item_level: 80
requirements:
  - family: IncreasedLife
quality:
  min_percent: 20
start_item:
  rarity: normal
  quality:
    percent: 8
"""


def test_the_six_link_target_with_colours_parses_to_its_golden_json():
    target = parse(SIX_LINK_TARGET, data=FIXTURE_DATA, header=False)

    assert_golden_json("target_sockets_six_link_colours", dump_target(target))


def test_the_plain_quality_target_parses_to_its_golden_json():
    target = parse(PLAIN_QUALITY_TARGET, data=FIXTURE_DATA, header=False)

    assert_golden_json("target_quality_plain", dump_target(target))


def test_the_dump_is_deterministic_and_reads_no_game_data():
    first, second = dump_target(parse(SIX_LINK_TARGET, header=False)), dump_target(parse(SIX_LINK_TARGET, header=False))

    assert first == second
    assert "spawn_weights" not in first and "stats" not in first


# -- G. the neighbours: the plan and the route card -------------------------------------------------


@pytest.fixture(scope="module")
def r12_target():
    return load_target(R12, FIXTURE_DATA)


def test_the_plan_of_a_socket_target_is_refused_because_the_planner_would_ignore_the_sockets(r12_target):
    asked = dataclasses.replace(r12_target, sockets=SocketRequirement(count=3))

    with pytest.raises(PlanError, match="asks for sockets"):
        make_plan(FIXTURE_DATA, asked, price_file())


def test_the_refusal_of_a_socket_target_says_the_planner_cannot_plan_it_yet(r12_target):
    asked = dataclasses.replace(r12_target, sockets=SocketRequirement(6, 6, 2, 2, 2))

    with pytest.raises(PlanError, match=r"cannot plan yet.*#228"):
        make_plan(FIXTURE_DATA, asked, price_file())


def test_the_plan_of_a_plain_quality_target_is_refused_too(r12_target):
    asked = dataclasses.replace(r12_target, quality=PlainQualityRequirement(20))

    with pytest.raises(PlanError, match="cannot plan yet"):
        make_plan(FIXTURE_DATA, asked, price_file())


def test_the_card_of_a_plain_quality_target_says_quality_twenty_percent_or_more():
    target = Target(ROBE, 84, frozenset(), (), robe_with("W"), quality=PlainQualityRequirement(20))

    card = card_of_target(DATA, target)

    assert card.properties == ("Rare", "item level 84", "Quality 20% or more")


def test_the_card_of_a_socket_target_does_not_crash_and_shows_no_socket_line():
    target = parse(SIX_LINK + "quality: {min_percent: 20}\n")

    card = card_of_target(DATA, target)

    assert "Quality 20% or more" in card.properties
    assert not any("ocket" in line for line in card.properties)


def test_the_card_of_an_item_with_plain_quality_says_quality_twenty_percent():
    card = card_of_item(DATA, robe_with("RGB", (3,), quality=PlainQuality(20)))

    assert "Quality 20%" in card.properties
    assert not any("catalyst" in line for line in card.properties)


def test_the_card_of_an_item_with_sockets_but_no_quality_has_no_quality_pill():
    card = card_of_item(DATA, robe_with("RGB", (3,)))

    assert not any("uality" in line for line in card.properties)


def test_the_html_of_a_plain_quality_target_and_item_do_not_crash():
    target = Target(ROBE, 84, frozenset(), (), robe_with("W"), quality=PlainQualityRequirement(20))

    assert "Quality 20% or more" in _item(card_of_target(DATA, target), target=True)
    assert "Quality 20%" in _item(card_of_item(DATA, robe_with("RGB", (3,), quality=PlainQuality(20))))
