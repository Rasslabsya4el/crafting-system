"""Every way a target file can be wrong is a `TargetError` that names the file, the line, the key and the cause.

`parse` puts `base` and `item_level` on lines 1 and 2, so the text of a test starts on line 3; the
file is called `t.yaml`.
"""

import dataclasses
from pathlib import Path
from types import MappingProxyType

import pytest
from targets_support import AMULET, DATA, parse, parse_error

from crafting_system.targets import TargetError, load_target, parse_target


def assert_error(message: str, line: int, key: str, *causes: str) -> None:
    assert message.startswith(f"t.yaml:{line}: "), message
    assert f": {key}: " in message, message
    for cause in causes:
        assert cause in message, message


def test_a_target_error_is_a_value_error():
    assert issubclass(TargetError, ValueError)


def test_a_yaml_syntax_error_names_the_line_without_a_traceback():
    message = parse_error("requirements:\n  - family: [LightningResistance\n", header=True)

    assert message.startswith("t.yaml:")
    assert "not valid YAML" in message
    assert "Traceback" not in message and "yaml." not in message


def test_a_tab_in_the_indentation_is_reported_at_its_line():
    message = parse_error("requirements:\n\t- family: IncreasedLife\n")

    assert message.startswith("t.yaml:4: not valid YAML")


def test_an_unknown_key_suggests_the_close_one():
    message = parse_error(
        """
        requirements:
          - family: LightningResistance
            min_tears: 2
        """
    )

    assert_error(message, 5, "requirements[0].min_tears", "unknown key `min_tears`", "did you mean `min_tier`?")


def test_an_unknown_top_level_key_is_reported_at_its_line():
    message = parse_error("requirements:\n  - family: IncreasedLife\nprise_file: p.json\n")

    assert_error(message, 5, "prise_file", "unknown key `prise_file`", "did you mean `price_file`?")


def test_an_unknown_key_with_no_close_match_lists_the_allowed_ones():
    message = parse_error("requirements:\n  - family: IncreasedLife\n    qqqqqqqq: 1\n")

    assert_error(message, 5, "requirements[0].qqqqqqqq", "unknown key `qqqqqqqq`", "`min_tier`", "`not_crafted`")


def test_a_group_entry_rejects_the_keys_of_a_requirement():
    message = parse_error(
        "requirements:\n  - at_least: 1\n    family: IncreasedLife\n    of:\n      - family: IncreasedLife\n"
    )

    assert_error(message, 5, "requirements[0].family", "unknown key `family`", "`at_least`", "`of`")


def test_family_and_stat_together_are_refused():
    message = parse_error(
        """
        requirements:
          - family: IncreasedLife
            stat: "+# to maximum Life"
        """
    )

    assert_error(message, 4, "requirements[0]", "either `family` or `stat`, not both")


def test_a_requirement_with_neither_family_nor_stat_is_refused():
    message = parse_error("requirements:\n  - min_tier: 1\n")

    assert_error(message, 4, "requirements[0]", "`family: <family id>`", "`stat:")


def test_an_unknown_stat_text_shows_the_closest_texts():
    message = parse_error('requirements:\n  - stat: "+# to maximum Lif"\n')

    assert_error(message, 4, "requirements[0].stat", 'no mod has the text "+# to maximum Lif"', '"+# to maximum Life"')


def test_a_stat_text_is_compared_with_case():
    message = parse_error('requirements:\n  - stat: "+# TO MAXIMUM LIFE"\n')

    assert_error(message, 4, "requirements[0].stat", "no mod has the text", '"+# to maximum Life"')


def test_a_two_line_stat_text_is_shown_on_one_line_with_its_line_break_written_out():
    message = parse_error(
        'requirements:\n  - stat: "+(105-150) to Armoux\\n+(11-15) to maximum Energy Shield"\n'
    )

    assert "\n" not in message
    assert '"+# to Armour\\n+# to maximum Energy Shield"' in message


def test_a_stat_text_that_is_nothing_like_any_mod_says_so():
    message = parse_error('requirements:\n  - stat: "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"\n')

    assert_error(message, 4, "requirements[0].stat", "no mod in the game data has the text")


def test_a_stat_that_is_a_family_id_points_to_the_family_key():
    message = parse_error("requirements:\n  - stat: IncreasedLife\n")

    assert_error(message, 4, "requirements[0].stat", "`IncreasedLife` is a family id", "write `family: IncreasedLife`")


def test_an_unknown_family_shows_the_close_ids():
    message = parse_error("requirements:\n  - family: LightningResistanc\n")

    assert_error(message, 4, "requirements[0].family", "`LightningResistanc` is not a family id", "`LightningResistance`")


def test_an_unknown_base_shows_the_close_names():
    message = parse_error("base: Paua Amulte\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n", header=False)

    assert_error(message, 1, "base", "no base is named `Paua Amulte`", "`Paua Amulet`")


def test_a_base_name_is_case_sensitive():
    message = parse_error("base: paua amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n", header=False)

    assert_error(message, 1, "base", "no base is named `paua amulet`", "`Paua Amulet`")


def test_a_mod_that_is_not_text_is_refused():
    message = parse_error("requirements:\n  - family: IncreasedLife\n    mod: 5\n")

    assert_error(message, 5, "requirements[0].mod", "must be non-empty text")


def test_a_mod_that_is_not_of_the_family_is_refused():
    message = parse_error("requirements:\n  - family: IncreasedLife\n    mod: LightningResist2\n")

    assert_error(message, 5, "requirements[0].mod", "`LightningResist2` is not a mod of the family `IncreasedLife`")


@pytest.mark.parametrize("value", ['"high"', "0", "-1", "true", "1.5", "[1]", "null"])
def test_a_bad_minimum_tier_is_refused(value):
    message = parse_error(f"requirements:\n  - family: IncreasedLife\n    min_tier: {value}\n")

    assert_error(message, 5, "requirements[0].min_tier", "must be a whole number of 1 or more")


def test_the_message_shows_the_value_the_owner_wrote():
    message = parse_error('requirements:\n  - family: IncreasedLife\n    min_tier: "high"\n')

    assert message == (
        't.yaml:5: requirements[0].min_tier: must be a whole number of 1 or more, got "high"'
    )


def test_a_bad_not_crafted_is_refused():
    message = parse_error('requirements:\n  - family: IncreasedLife\n    not_crafted: "yes"\n')

    assert_error(message, 5, "requirements[0].not_crafted", "must be true or false")


def best_roll(selector: str) -> int:
    """The highest roll of the one stat of the mods `selector` (a requirement line) selects, from the data."""
    (requirement,) = parse("requirements:\n  - " + selector + "\n").requirements
    return max(
        max(DATA.mods[mod_id].stats[0].min, DATA.mods[mod_id].stats[0].max)
        for mod_id in requirement.mod_ids
    )


def test_a_minimum_roll_above_the_best_roll_says_what_the_best_is():
    best = best_roll("family: LightningResistance")

    message = parse_error(f"requirements:\n  - family: LightningResistance\n    min_roll: {best + 1}\n")

    assert_error(message, 5, "requirements[0].min_roll", f"{best + 1} is above the best roll", f"which is {best}")


def test_a_minimum_roll_in_a_list_above_the_best_roll_names_the_entry():
    best = best_roll('stat: "+# to maximum Life"')

    message = parse_error(f'requirements:\n  - stat: "+# to maximum Life"\n    min_roll: [{best + 1}]\n')

    assert_error(message, 5, "requirements[0].min_roll[0]", f"{best + 1} is above the best roll", f"which is {best}")


def test_a_minimum_roll_exactly_at_the_best_roll_is_accepted():
    best = best_roll("family: LightningResistance")

    target = parse(f"requirements:\n  - family: LightningResistance\n    min_roll: {best}\n")

    assert target.requirements[0].min_roll == (best,)


def test_a_bare_minimum_roll_on_a_two_stat_mod_asks_for_a_list():
    message = parse_error('requirements:\n  - stat: "Adds (1-2) to (3-4) Cold Damage"\n    min_roll: 2\n')

    assert_error(message, 5, "requirements[0].min_roll", "2 stats", "a list", "[null, null]")


@pytest.mark.parametrize("roll_list", ["[1]", "[1, 2, 3]", "[]"])
def test_a_minimum_roll_list_of_the_wrong_length_is_refused(roll_list):
    message = parse_error(f'requirements:\n  - stat: "Adds (1-2) to (3-4) Cold Damage"\n    min_roll: {roll_list}\n')

    assert_error(message, 5, "requirements[0].min_roll", "2 stat(s)", "exactly 2 entries")


def test_a_one_stat_mod_wants_a_list_of_one():
    message = parse_error("requirements:\n  - family: LightningResistance\n    min_roll: [1, 2]\n")

    assert_error(message, 5, "requirements[0].min_roll", "1 stat(s)", "exactly 1 entry")


@pytest.mark.parametrize("entry", ['"a"', "true", "1.5", "[1]"])
def test_a_minimum_roll_entry_must_be_a_whole_number_or_null(entry):
    message = parse_error(f'requirements:\n  - stat: "Adds (1-2) to (3-4) Cold Damage"\n    min_roll: [{entry}, null]\n')

    assert_error(message, 5, "requirements[0].min_roll[0]", "must be a whole number or null")


@pytest.mark.parametrize("value", ['"3"', "true", "2.5", "null"])
def test_a_bare_minimum_roll_must_be_a_whole_number(value):
    message = parse_error(f"requirements:\n  - family: LightningResistance\n    min_roll: {value}\n")

    assert_error(message, 5, "requirements[0].min_roll", "must be a whole number")


def test_a_selector_spanning_mods_with_different_stat_counts_cannot_take_a_minimum_roll():
    message = parse_error("requirements:\n  - family: IncreasedEnergyShield\n    min_roll: 1\n")

    assert_error(message, 5, "requirements[0].min_roll", "different numbers of stats")


def test_a_selector_spanning_mods_with_different_stat_counts_is_fine_without_a_minimum_roll():
    target = parse("requirements:\n  - family: IncreasedEnergyShield\n    min_tier: 1\n")

    assert "JunMaster2ArmourAndEnergyShield1" in target.requirements[0].mod_ids


@pytest.mark.parametrize("count", ["0", "3", "-1", "true", '"2"', "1.5"])
def test_at_least_out_of_range_is_refused(count):
    message = parse_error(
        f"requirements:\n  - at_least: {count}\n    of:\n      - family: IncreasedLife\n      - family: FireResistance\n"
    )

    assert_error(message, 4, "requirements[0].at_least", "from 1 to 2", "the number of entries in `of`")


def test_an_empty_of_is_refused():
    message = parse_error("requirements:\n  - at_least: 1\n    of: []\n")

    assert_error(message, 5, "requirements[0].of", "at least one requirement")


def test_of_must_be_a_list():
    message = parse_error("requirements:\n  - at_least: 1\n    of: IncreasedLife\n")

    assert_error(message, 5, "requirements[0].of", "must be a list")


def test_at_least_without_of_is_refused():
    message = parse_error("requirements:\n  - at_least: 1\n")

    assert_error(message, 4, "requirements[0].of", "needs both `at_least` and `of`")


def test_of_without_at_least_is_refused():
    message = parse_error("requirements:\n  - of:\n      - family: IncreasedLife\n")

    assert_error(message, 4, "requirements[0].at_least", "needs both `at_least` and `of`")


def test_an_error_inside_a_nested_group_has_the_whole_key_path_and_the_real_line():
    message = parse_error(
        """
        requirements:
          - family: FireResistance
          - at_least: 1
            of:
              - family: ColdResistance
              - at_least: 1
                of:
                  - family: IncreasedLife
                    min_tier: 0
        """
    )

    assert_error(message, 11, "requirements[1].of[1].of[0].min_tier", "must be a whole number of 1 or more")


def test_a_list_where_a_mapping_is_expected_is_refused():
    message = parse_error("requirements:\n  - [family, IncreasedLife]\n")

    assert_error(message, 4, "requirements[0]", "must be a mapping", "got a list")


def test_a_mapping_where_a_list_is_expected_is_refused():
    message = parse_error("requirements:\n  family: IncreasedLife\n")

    assert_error(message, 3, "requirements", "must be a list of requirements", "got a mapping")


def test_an_empty_requirements_list_is_refused():
    message = parse_error("requirements: []\n")

    assert_error(message, 3, "requirements", "at least one requirement")


def test_a_key_written_twice_names_both_lines():
    message = parse_error("item_level: 85\nrequirements:\n  - family: IncreasedLife\n")

    assert message.startswith("t.yaml:3: item_level: ")
    assert "written twice" in message and "first on line 2" in message


def test_a_key_written_twice_inside_a_requirement_is_refused():
    message = parse_error("requirements:\n  - family: IncreasedLife\n    min_tier: 1\n    min_tier: 2\n")

    assert message.startswith("t.yaml:6: min_tier: ") and "first on line 5" in message


def test_a_key_that_is_not_text_is_refused():
    message = parse_error("requirements:\n  - family: IncreasedLife\n    1: 2\n")

    assert message.startswith("t.yaml:5: every key must be text")


@pytest.mark.parametrize("text", ["", "   \n", "# only a comment\n"])
def test_an_empty_file_is_refused(text):
    message = parse_error(text, header=False)

    assert message.startswith("t.yaml:1: the file is empty")


@pytest.mark.parametrize("text", ["- base\n- item_level\n", "just text\n", "42\n"])
def test_a_top_level_that_is_not_a_mapping_is_refused(text):
    message = parse_error(text, header=False)

    assert message.startswith("t.yaml:1: the file must be a mapping")


def test_two_documents_in_one_file_are_refused():
    message = parse_error("base: Paua Amulet\n---\nbase: Paua Amulet\n", header=False)

    assert message.startswith("t.yaml:") and "not valid YAML" in message


@pytest.mark.parametrize("missing", ["base", "item_level", "requirements"])
def test_each_required_key_is_checked(missing):
    lines = {
        "base": "base: Paua Amulet\n",
        "item_level": "item_level: 84\n",
        "requirements": "requirements:\n  - family: IncreasedLife\n",
    }
    text = "".join(line for key, line in lines.items() if key != missing)

    message = parse_error(text, header=False)

    assert_error(message, 1, missing, "required but missing")


@pytest.mark.parametrize("level", ["101", "0", "-5", "84.5", '"84"', "true", "null"])
def test_an_item_level_outside_one_to_one_hundred_or_not_whole_is_refused(level):
    message = parse_error(f"base: Paua Amulet\nitem_level: {level}\nrequirements:\n  - family: IncreasedLife\n", header=False)

    assert_error(message, 2, "item_level", "from 1 to 100")


def test_a_base_that_is_not_text_is_refused():
    message = parse_error("base: 5\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n", header=False)

    assert_error(message, 1, "base", "must be non-empty text")


@pytest.mark.parametrize("value", ["shaper", "[crown]", "[1]", "[shaper, null]"])
def test_a_bad_influence_is_refused(value):
    message = parse_error(f"influence: {value}\nrequirements:\n  - family: IncreasedLife\n")

    assert message.startswith("t.yaml:")
    assert "influence" in message
    assert "shaper" in message


def test_a_start_item_mod_with_an_unknown_id_is_refused_with_close_ids():
    message = parse_error(
        """
        requirements:
          - family: IncreasedLife
        start_item:
          mods:
            - mod: LightningResist22
              tier: 1
              values: [14]
        """
    )

    assert_error(message, 7, "start_item.mods[0].mod", "`LightningResist22` is not a mod id", "`LightningResist2`")


def test_a_start_item_that_the_item_model_rejects_keeps_its_words():
    message = parse_error(
        """
        requirements:
          - family: IncreasedLife
        start_item:
          mods:
            - mod: LightningResist2
              tier: 3
              values: [99]
        """
    )

    assert_error(message, 7, "start_item.mods[0]", "mod LightningResist2 has value 99", "outside 12 to 17")


def test_an_item_error_about_the_second_mod_is_reported_at_that_mod():
    message = parse_error(
        """
        requirements:
          - family: IncreasedLife
        start_item:
          mods:
            - mod: IncreasedLife1
              tier: 1
              values: [10]
            - mod: LightningResist2
              tier: 3
              values: [99]
        """
    )

    assert_error(message, 10, "start_item.mods[1]", "mod LightningResist2 has value 99")


def test_an_item_error_naming_two_mods_is_reported_at_the_one_its_words_name_first():
    message = parse_error(
        """
        requirements:
          - family: IncreasedLife
        start_item:
          mods:
            - mod: LightningResist2
              tier: 3
              values: [14]
            - mod: LightningResist1
              tier: 3
              values: [7]
        """
    )

    assert "mods LightningResist1 and LightningResist2 share" in message
    assert_error(message, 10, "start_item.mods[1]", "share the family LightningResistance")


def test_a_normal_start_item_with_mods_is_rejected_by_the_item_model():
    message = parse_error(
        """
        requirements:
          - family: IncreasedLife
        start_item:
          rarity: normal
          mods:
            - mod: LightningResist2
              tier: 3
              values: [14]
        """
    )

    assert_error(message, 5, "start_item", "normal item")


def test_a_start_item_mod_needs_a_mod_a_tier_and_values():
    base = "requirements:\n  - family: IncreasedLife\nstart_item:\n  mods:\n    - mod: LightningResist2\n"
    message = parse_error(base + "      values: [14]\n")

    assert_error(message, 7, "start_item.mods[0].tier", "required but missing")


@pytest.mark.parametrize(
    ("field", "line", "cause"),
    [
        ("tier", "tier: 0", "whole number of 1 or more"),
        ("tier", "tier: true", "whole number of 1 or more"),
        ("values[0]", "values: [1.5]", "must be a whole number"),
        ("values", "values: abc", "whole number or a list"),
        ("values[0]", "values: [true]", "must be a whole number"),
        ("fractured", "fractured: 1", "true or false"),
        ("crafted", "crafted: maybe", "true or false"),
    ],
)
def test_the_fields_of_a_start_item_mod_are_checked(field, line, cause):
    fields = {"mod": "mod: LightningResist2", "tier": "tier: 3", "values": "values: [14]"}
    fields[line.split(":")[0]] = line
    body = "".join(f"    {'- ' if key == 'mod' else '  '}{text}\n" for key, text in fields.items())
    head = "requirements:\n  - family: IncreasedLife\nstart_item:\n  mods:\n"

    message = parse_error(head + body)

    assert message.startswith("t.yaml:")
    assert f"start_item.mods[0].{field}: " in message
    assert cause in message


def test_a_bad_start_item_rarity_is_refused():
    message = parse_error("requirements:\n  - family: IncreasedLife\nstart_item:\n  rarity: unique\n")

    assert_error(message, 6, "start_item.rarity", "normal", "magic", "rare")


def test_a_start_item_must_be_a_mapping():
    message = parse_error("requirements:\n  - family: IncreasedLife\nstart_item: [a]\n")

    assert_error(message, 5, "start_item", "must be a mapping")


def test_a_price_file_must_be_text():
    message = parse_error("requirements:\n  - family: IncreasedLife\nprice_file: 5\n")

    assert_error(message, 5, "price_file", "must be non-empty text")


COPY = "Metadata/Items/Amulets/Copy0"
BASE_TEXT = "base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n"


def two_amulets(original_state: str, copy_state: str):
    """The fixture data with a second base also called `Paua Amulet`; each base has the given release state."""
    original = DATA.base_items[AMULET]
    bases = dict(DATA.base_items)
    bases[AMULET] = dataclasses.replace(original, release_state=original_state)
    bases[COPY] = dataclasses.replace(original, id=COPY, release_state=copy_state)
    return dataclasses.replace(DATA, base_items=MappingProxyType(bases))


def test_a_name_shared_by_one_released_base_and_an_unreleased_one_picks_the_released_one():
    assert parse_target(BASE_TEXT, two_amulets("unreleased", "released")).base_id == COPY
    assert parse_target(BASE_TEXT, two_amulets("released", "legacy")).base_id == AMULET


def test_of_two_released_bases_of_one_name_the_one_not_tagged_not_for_sale_is_picked():
    data = two_amulets("released", "released")
    copy = data.base_items[COPY]
    bases = dict(data.base_items)
    bases[COPY] = dataclasses.replace(copy, tags=(*copy.tags, "not_for_sale"))
    data = dataclasses.replace(data, base_items=MappingProxyType(bases))

    assert parse_target(BASE_TEXT, data).base_id == AMULET


@pytest.mark.parametrize(("first", "second"), [("released", "released"), ("unreleased", "legacy")])
def test_a_name_that_does_not_pick_one_released_base_lists_the_ids(first, second):
    with pytest.raises(TargetError) as caught:
        parse_target(BASE_TEXT, two_amulets(first, second), "t.yaml")

    message = str(caught.value)
    assert_error(message, 1, "base", "several bases are named `Paua Amulet`", "write the base id instead")
    assert AMULET in message and COPY in message


def test_the_default_source_name_is_used_when_none_is_given():
    with pytest.raises(TargetError) as caught:
        parse_target("", DATA)

    assert str(caught.value).startswith("<target>:1: ")


def test_a_valid_target_parses_under_the_same_helper():
    assert parse("requirements:\n  - family: IncreasedLife\n").base_id == AMULET


@pytest.mark.parametrize("bad", ["\x07", "\x00", "\x1b", "\x7f"])
def test_a_character_not_allowed_in_text_is_a_target_error_at_its_line(bad):
    message = parse_error(f"requirements:\n  - family: IncreasedLife\nprice_file: a{bad}b\n")

    assert message.startswith("t.yaml:5: ")
    assert "not allowed in text" in message
    assert "ReaderError" not in message and "special characters" not in message


def test_a_character_not_allowed_at_the_very_start_is_reported_at_line_one():
    message = parse_error("\x07base: Paua Amulet\n", header=False)

    assert message.startswith("t.yaml:1: ") and "not allowed in text" in message


def test_a_nul_in_a_quoted_price_file_is_refused():
    message = parse_error('requirements:\n  - family: IncreasedLife\nprice_file: "a\\0b"\n')

    assert_error(message, 5, "price_file", "not a valid path")


def test_a_control_character_in_a_file_is_a_target_error_that_names_the_path(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_bytes(b"base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n\x00\n")

    with pytest.raises(TargetError) as caught:
        load_target(path, DATA)

    assert str(caught.value).startswith(f"{path}:5: ") and "not allowed in text" in str(caught.value)


def nested_groups(levels: int) -> str:
    """A requirements list of `levels` at_least groups inside each other, around one family entry."""
    lines = ["requirements:"]
    for level in range(levels):
        indent = " " * (2 + 4 * level)
        lines += [f"{indent}- at_least: 1", f"{indent}  of:"]
    lines.append(" " * (2 + 4 * levels) + "- family: IncreasedLife")
    return "\n".join(lines) + "\n"


def test_twenty_levels_of_groups_are_allowed():
    target = parse(nested_groups(20))

    node = target.requirements[0]
    for _ in range(19):
        node = node.of[0]
    assert node.of[0].family == "IncreasedLife"


def test_twenty_one_levels_of_groups_are_refused_with_a_clear_message():
    message = parse_error(nested_groups(21))

    assert message.startswith("t.yaml:")
    assert "nested too deeply" in message and "20" in message
    assert "requirements[0].of[0]" in message


def test_a_chain_of_four_hundred_groups_is_a_target_error():
    assert "nested too deeply" in parse_error(nested_groups(400))


def test_thousands_of_nested_brackets_are_a_target_error_not_a_recursion_error():
    message = parse_error("requirements: " + "[" * 3000 + "]" * 3000 + "\n")

    assert message.startswith("t.yaml:") and "nested too deeply" in message


def test_thousands_of_nested_mappings_are_a_target_error():
    message = parse_error("requirements: " + "{a: " * 3000 + "1" + "}" * 3000 + "\n")

    assert message.startswith("t.yaml:") and "nested too deeply" in message


def test_base_and_price_file_ignore_surrounding_whitespace_and_a_trailing_newline():
    text = (
        "base: >\n  Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n"
        'price_file: "  p.json \\n"\n'
    )

    target = parse(text, header=False)

    assert target.base_id == AMULET and target.price_file == Path("p.json")


def test_a_folded_base_name_with_a_trailing_newline_is_found():
    target = parse("base: |\n  Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n", header=False)

    assert target.base_id == AMULET


@pytest.mark.parametrize("blank", ['""', '"   "', '"\\n"', ">\n  "])
def test_a_blank_base_or_price_file_is_still_refused(blank):
    for key, line in (("base", 1), ("price_file", 5)):
        lines = ["base: Paua Amulet", "item_level: 84", "requirements:", "  - family: IncreasedLife", "price_file: x"]
        lines[line - 1] = f"{key}: {blank}"

        message = parse_error("\n".join(lines) + "\n", header=False)

        assert_error(message, line, key, "must be non-empty text")


def test_a_family_or_stat_with_surrounding_whitespace_is_found():
    target = parse('requirements:\n  - family: " IncreasedLife "\n  - stat: " +# to maximum Life\\n"\n')

    assert target.requirements[0].family == "IncreasedLife"
    assert target.requirements[1].stat == "+# to maximum Life"


def test_a_merge_key_is_refused_even_when_nothing_overrides():
    message = parse_error("requirements:\n  - <<: {family: IncreasedLife}\n    min_tier: 1\n")

    assert message.startswith("t.yaml:4: ")
    assert "merge keys `<<` are not supported; write the keys out" in message


def test_a_merge_key_that_is_overridden_is_refused_the_same_way():
    message = parse_error("requirements:\n  - <<: {family: IncreasedLife, min_tier: 1}\n    min_tier: 2\n")

    assert message.startswith("t.yaml:4: ")
    assert "merge keys `<<` are not supported" in message and "written twice" not in message


def test_an_anchor_is_refused_at_its_line_before_anything_is_read():
    message = parse_error("requirements:\n  - &a {family: IncreasedLife}\n")

    assert message.startswith("t.yaml:4: ")
    assert "anchors `&a` are not supported; write the value out" in message


def test_an_alias_is_refused_at_its_line_even_when_its_anchor_is_missing():
    message = parse_error("requirements:\n  - family: IncreasedLife\nprice_file: *a\n")

    assert message.startswith("t.yaml:5: ")
    assert "aliases `*a` are not supported; write the value out" in message
    assert "undefined alias" not in message


def test_a_repeated_influence_is_refused_whatever_its_case():
    message = parse_error("influence: [shaper, elder, Shaper]\nrequirements:\n  - family: IncreasedLife\n")

    assert message.startswith("t.yaml:")
    assert "influence[2]" in message and "listed twice" in message and "influence[0]" in message


@pytest.mark.parametrize("text", ["[]", "[|]", "[ | ]", " [a|]  [b|] "])
def test_a_stat_text_that_is_empty_once_markup_is_removed_is_refused(text):
    message = parse_error(f'requirements:\n  - stat: "{text}"\n')

    assert_error(message, 4, "requirements[0].stat", "empty", "markup")


def test_a_stat_text_with_only_a_range_is_not_empty():
    message = parse_error('requirements:\n  - stat: "(1-2)"\n')

    assert "empty" not in message and "no mod" in message
