"""The Memory Strands count on the item, in the start item of a target, in the config and on the command line (ticket #274).

"Done when" lines covered here: a pasted item with `Memory Strands: 57` parses and prints back; `Item` equality and hash include the
count; a start item with strands turns the setting on; the report names the setting when off. (That every existing golden report
is unchanged with the setting off is the job of the golden tests that already exist: they run unchanged.)
"""

import dataclasses
import textwrap

import pytest
from cli_support import R12, TODAY, price_file, read_json, run
from items_support import AMULET, DATA, item, roll
from targets_implicits_support import TEXTED, parse, parse_error

from crafting_system.cli import STRANDS_OFF, PlanError, StrandSetting, build_report, main, make_plan, render_text, strand_setting
from crafting_system.cli._route_card import card_of_item
from crafting_system.config import Config, load_config
from crafting_system.items import (
    MAX_MEMORY_STRANDS,
    Item,
    ItemError,
    MemoryStrandsError,
    Rarity,
    memory_strands_line,
    read_memory_strands,
)
from crafting_system.targets import load_target

# A pasted item as the game copies it (the lines that matter here; the others are what any pasted item has).
PASTED = textwrap.dedent(
    """\
    Item Class: Amulets
    Rarity: Rare
    Dread Pendant
    Paua Amulet
    --------
    Quality: +20% (augmented)
    --------
    Requirements:
    Level: 66
    --------
    Item Level: 84
    Memory Strands: 57
    --------
    +13% to Lightning Resistance
    """
)


# --- the count on the item ----------------------------------------------------------------------------------


def test_an_item_has_no_strands_unless_given():
    assert item(roll("IncreasedLife1")).memory_strands == 0


def test_the_count_is_part_of_the_equality_and_the_hash_of_an_item():
    plain, stranded, same = item(roll("IncreasedLife1")), item(roll("IncreasedLife1"), memory_strands=57), item(roll("IncreasedLife1"), memory_strands=57)

    assert plain != stranded and stranded == same
    assert hash(stranded) == hash(same)
    assert len({plain, stranded, same, item(roll("IncreasedLife1"), memory_strands=58)}) == 3
    assert item(roll("IncreasedLife1"), memory_strands=0) == plain


def test_changed_sets_the_count_and_keeps_the_rest():
    start = item(roll("IncreasedLife1"))

    changed = start.changed(DATA, memory_strands=100)

    assert changed.memory_strands == 100
    assert dataclasses.replace(changed, memory_strands=0) == start


@pytest.mark.parametrize("count", [-1, 101, 1000, True, False, 5.0, "5", None])
def test_a_count_that_is_not_a_whole_number_from_0_to_100_is_an_item_error(count):
    with pytest.raises(MemoryStrandsError, match="not a whole number from 0 to 100") as raised:
        item(roll("IncreasedLife1"), memory_strands=count)

    assert isinstance(raised.value, ItemError)


@pytest.mark.parametrize("count", [0, 1, 57, 100])
def test_the_ends_of_the_range_are_accepted(count):
    assert item(roll("IncreasedLife1"), memory_strands=count).memory_strands == count


# --- the pasted line -------------------------------------------------------------------------------------------


def test_a_pasted_item_with_the_line_parses_to_its_count():
    assert read_memory_strands(PASTED) == 57
    assert read_memory_strands("Memory Strands: 57") == 57
    assert read_memory_strands("  Memory Strands: 100 \r\n") == 100


def test_a_pasted_item_without_the_line_has_no_strands():
    assert read_memory_strands(PASTED.replace("Memory Strands: 57\n", "")) == 0
    assert read_memory_strands("") == 0


@pytest.mark.parametrize("count", range(0, MAX_MEMORY_STRANDS + 1))
def test_every_count_prints_back_as_the_line_the_game_shows_and_parses_again(count):
    line = memory_strands_line(count)

    assert line == (f"Memory Strands: {count}" if count else None)
    assert read_memory_strands(line or "") == count


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("Memory Strands: 101", "more than the 100"),
        ("Memory Strands: lots", "not a whole number"),
        ("Memory Strands: 5.5", "not a whole number"),
        ("Memory Strands: -3", "not a whole number"),
        ("Memory Strands:", "not a whole number"),
        ("Memory Strands: 5\nMemory Strands: 6", "2 `Memory Strands:` lines"),
    ],
)
def test_a_badly_written_line_is_refused(text, problem):
    with pytest.raises(MemoryStrandsError, match=problem):
        read_memory_strands(text)


def test_a_line_that_is_not_a_count_is_not_mistaken_for_one():
    assert read_memory_strands("Memory Strands Orb: 5\nSome Memory Strands: 5") == 0


@pytest.mark.parametrize("count", [-1, 101, True, 1.5])
def test_the_line_of_a_bad_count_is_refused(count):
    with pytest.raises(MemoryStrandsError):
        memory_strands_line(count)


# --- the start item of a target ------------------------------------------------------------------------------------


def start(body: str) -> str:
    return "start_item:\n" + "".join(f"  {line}\n" for line in body.strip("\n").splitlines())


def test_the_yaml_key_gives_the_start_item_its_count():
    assert parse(start("memory_strands: 57")).start_item.memory_strands == 57
    assert parse(start("rarity: rare\nmemory_strands: 100")).start_item.memory_strands == 100
    assert parse(start("memory_strands: 0")).start_item.memory_strands == 0


def test_a_start_item_without_the_key_has_no_strands():
    assert parse(start("rarity: normal")).start_item.memory_strands == 0
    assert parse("").start_item.memory_strands == 0


def test_a_pasted_item_text_in_the_key_parses_to_its_count():
    text = "memory_strands: |\n" + textwrap.indent(PASTED, "  ")

    found = parse(start(text)).start_item

    assert found.memory_strands == 57


def test_the_pasted_line_alone_is_enough_in_the_key():
    assert parse(start('memory_strands: "Memory Strands: 57"')).start_item.memory_strands == 57


@pytest.mark.parametrize(
    ("body", "words"),
    [
        ("memory_strands: 101", "must be a whole number from 0 to 100"),
        ("memory_strands: -1", "must be a whole number from 0 to 100"),
        ("memory_strands: 5.5", "must be a whole number from 0 to 100"),
        ("memory_strands: true", "must be a whole number from 0 to 100"),
        ("memory_strands:", "must be a whole number from 0 to 100"),
        ("memory_strands: [57]", "must be a whole number from 0 to 100"),
        ('memory_strands: "lots"', 'must hold the line "Memory Strands: N"'),
        ('memory_strands: "Memory Strands: lots"', "not a whole number"),
        ('memory_strands: "Memory Strands: 101"', "more than the 100"),
    ],
)
def test_a_bad_key_is_blamed_on_its_line_and_key_path(body, words):
    message = parse_error(start(body))

    assert message.startswith("t.yaml:6: start_item.memory_strands: "), message
    assert words in message


def test_a_misspelled_key_gets_a_hint():
    assert "did you mean `memory_strands`?" in parse_error(start("memory_strand: 57"))


def test_a_start_item_with_strands_prints_back_on_its_card():
    found = parse(start("memory_strands: 57")).start_item

    assert "Memory Strands: 57" in card_of_item(TEXTED, found).properties


def test_a_start_item_without_strands_has_the_card_it_always_had():
    plain = item(roll("IncreasedLife1"), base_id=AMULET)

    assert not any("Memory Strands" in line for line in card_of_item(DATA, plain).properties)


def test_a_pasted_item_round_trips_through_the_item_and_its_card():
    count = read_memory_strands(PASTED)
    built = item(roll("IncreasedLife1"), base_id=AMULET, memory_strands=count)

    shown = [line for line in card_of_item(DATA, built).properties if line.startswith("Memory Strands")]

    assert shown == [line for line in PASTED.splitlines() if line.startswith("Memory Strands")]


# --- the setting: config, flag, start item ----------------------------------------------------------------------------


def write_toml(tmp_path, text):
    path = tmp_path / "crafting.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_setting_is_off_by_default(tmp_path):
    assert load_config(env={}, project_root=tmp_path).memory_strands is False
    assert Config(tmp_path, tmp_path, tmp_path).memory_strands is False


def test_the_planner_table_turns_it_on(tmp_path):
    write_toml(tmp_path, "[planner]\nmemory_strands = true\n")

    assert load_config(env={}, project_root=tmp_path).memory_strands is True


def test_the_setting_and_the_paths_are_read_together(tmp_path):
    write_toml(tmp_path, '[paths]\ndata = "d"\n[planner]\nmemory_strands = false\n')

    config = load_config(env={}, project_root=tmp_path)

    assert config.memory_strands is False and config.data_dir == tmp_path / "d"


@pytest.mark.parametrize("value", ['"yes"', "1", "[true]", "{ on = true }"])
def test_a_setting_that_is_not_true_or_false_is_an_error_naming_file_and_key(tmp_path, value):
    write_toml(tmp_path, f"[planner]\nmemory_strands = {value}\n")

    with pytest.raises(ValueError, match=r"crafting\.toml.*memory_strands.*true or false"):
        load_config(env={}, project_root=tmp_path)


def test_an_unknown_planner_key_is_an_error_naming_file_and_key(tmp_path):
    write_toml(tmp_path, "[planner]\nmemory_strand = true\n")

    with pytest.raises(ValueError, match=r"crafting\.toml.*memory_strand.*known: memory_strands"):
        load_config(env={}, project_root=tmp_path)


def test_a_planner_that_is_not_a_table_is_an_error(tmp_path):
    write_toml(tmp_path, "planner = true\n")

    with pytest.raises(ValueError, match=r"crafting\.toml.*'planner' must be a table"):
        load_config(env={}, project_root=tmp_path)


def test_the_committed_config_leaves_strands_off():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]

    assert load_config(env={}, project_root=root).memory_strands is False


def stranded_target(tmp_path, count=57):
    """The R12 target whose start item also carries `count` strands."""
    text = R12.read_text(encoding="utf-8").replace("  rarity: rare\n", f"  rarity: rare\n  memory_strands: {count}\n", 1)
    path = tmp_path / "stranded.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_start_item_with_strands_turns_the_setting_on(tmp_path):
    target = load_target(stranded_target(tmp_path), DATA)

    setting = strand_setting(target.start_item)

    assert setting.on is True
    assert "start item has 57 Memory Strands" in setting.why


def test_the_query_turns_the_setting_on_and_nothing_else_does():
    plain = item(roll("IncreasedLife1"))

    assert strand_setting(plain) is STRANDS_OFF and not STRANDS_OFF.on
    assert strand_setting(plain, asked=True) == StrandSetting(True, "the setting memory_strands is on (`--strands` or crafting.toml)")
    assert strand_setting(item(roll("IncreasedLife1"), memory_strands=1)).on
    assert not strand_setting(item(roll("IncreasedLife1"), memory_strands=0)).on


# --- the report ---------------------------------------------------------------------------------------------------------


def test_the_report_names_the_setting_when_it_is_off(tmp_path, capsys):
    code, _ = run(tmp_path, prices=price_file())

    assert code == 0
    lines = capsys.readouterr().out.splitlines()
    (found,) = [line for line in lines if line.startswith("Memory Strands:")]
    assert found.startswith("Memory Strands: not considered (the setting memory_strands is off")
    assert "--strands" in found and "[planner]" in found
    assert lines[lines.index(found) - 1].startswith("Start item")  # in the header, before the policy


def test_a_plan_made_without_the_setting_says_it_is_off():
    from cli_support import R12 as path

    plan = make_plan(DATA, load_target(path, DATA), price_file())

    assert plan.strands is STRANDS_OFF
    assert "Memory Strands: not considered" in render_text(build_report(plan, DATA))


def test_the_json_policy_is_what_it_was(tmp_path):
    code, out = run(tmp_path, prices=price_file())

    assert code == 0
    assert not any("strand" in key.lower() for key in read_json(out))


def test_asking_for_strands_is_refused_until_the_batch_builds_them(tmp_path, capsys):
    code, _ = run(tmp_path, "--strands", prices=price_file())

    assert code == 1
    err = capsys.readouterr().err
    assert "Memory Strands are on (the setting memory_strands is on" in err and "cannot plan yet" in err


def test_a_start_item_with_strands_is_refused_the_same_way_and_says_why(tmp_path, capsys):
    code, _ = run(tmp_path, target=stranded_target(tmp_path), prices=price_file())

    assert code == 1
    assert "Memory Strands are on (the start item has 57 Memory Strands)" in capsys.readouterr().err


def test_the_config_file_turns_the_command_on(tmp_path, capsys):
    toml = write_toml(tmp_path, "[planner]\nmemory_strands = true\n")

    code = main([str(R12), "--json", str(tmp_path / "p.json")], data=DATA, prices=price_file(), env={"CRAFTING_CONFIG": str(toml)}, today=TODAY)

    assert code == 1
    assert "Memory Strands are on" in capsys.readouterr().err


def test_make_plan_refuses_the_strands_with_a_plan_error():
    target = load_target(R12, DATA)

    with pytest.raises(PlanError, match="Memory Strands are on"):
        make_plan(DATA, target, price_file(), strands=True)
    with pytest.raises(PlanError, match="start item has 3 Memory Strands"):
        make_plan(DATA, dataclasses.replace(target, start_item=target.start_item.changed(DATA, memory_strands=3)), price_file())


def test_a_normal_item_still_has_the_rarity_it_was_given():
    assert item(base_id=AMULET, rarity=Rarity.NORMAL, memory_strands=40).rarity is Rarity.NORMAL
    assert isinstance(item(roll("IncreasedLife1"), memory_strands=40), Item)
