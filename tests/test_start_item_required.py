"""The start item is stated by the file, never made up by the parser (#545, OR-6, OR-4; decision of the main chat, 2026-11-07).

* I1: a target with no `start_item:` is refused, naming the key (it used to get a fresh Normal item).
* I2: a `start_item:` with no `rarity:` is refused (it used to be RARE when mods were listed and NORMAL otherwise).
* I6: a target that asks for sockets and whose start item states none is refused, unless the start item says `sockets: any` (it used to
  get one white, unlinked socket; `Target.start_sockets_assumed` is gone).
* Every committed target file parses on the real data and states its start item; the five that had no `start_item:` (R04, R06, R13, R14,
  V01) now state the plain Normal item they always started from, with the guide's words in the file.
"""

import dataclasses
import re

import pytest
from abstraction_support import real_game_data
from start_support import with_start
from targets_support import DATA, EXAMPLES

from crafting_system.items import Rarity
from crafting_system.targets import Target, TargetError, load_target, parse_target

HEAD = "base: Simple Robe\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n"
MODS = "  mods:\n    - mod: LightningResist2\n      values: [14]\n      fractured: true\n"
EXAMPLE_FILES = sorted(EXAMPLES.glob("*.yaml"))
HAD_NO_START_ITEM = {
    "r04-penetrating-quiver.yaml",
    "r06-strength-heavy-belt.yaml",
    "r13-life-resist-belt.yaml",
    "r14-hunter-bow.yaml",
    "v01-minion-helmet.yaml",
}


def refusal(text: str) -> str:
    """The message of the `TargetError` for `text`, closed with `start: given` only (no start item is added); fails if it parses."""
    with pytest.raises(TargetError) as caught:
        parse_target(with_start(text, item=False), DATA, source="t.yaml")
    return str(caught.value)


def test_a_target_with_no_start_item_is_refused_and_the_message_names_the_key():
    message = refusal(HEAD)

    assert message.startswith("t.yaml:1: start_item: this key is required but missing")
    assert "`start_item:`" in message and "`rarity:`" in message


def test_a_start_item_with_no_rarity_is_refused_even_when_it_lists_mods():
    message = refusal(f"{HEAD}start_item:\n{MODS}")

    assert message.startswith("t.yaml:5: start_item.rarity: this key is required but missing")
    assert "not guessed from the mods listed" in message  # no RARE from the mods


def test_a_start_item_with_no_rarity_and_no_mods_is_refused_too():
    message = refusal(f"{HEAD}start_item:\n  corrupted: false\n")

    assert message.startswith("t.yaml:5: start_item.rarity: this key is required but missing")  # no NORMAL by default


def test_a_start_item_that_states_its_rarity_is_read_as_written():
    for written, rarity in (("normal", Rarity.NORMAL), ("magic", Rarity.MAGIC), ("rare", Rarity.RARE)):
        target = parse_target(with_start(f"{HEAD}start_item:\n  rarity: {written}\n", item=False), DATA, source="t.yaml")

        assert target.start_item.rarity is rarity


def test_a_target_that_asks_for_sockets_and_whose_start_item_states_none_is_refused_and_the_message_names_the_key():
    message = refusal(f"{HEAD}sockets: {{count: 3}}\nstart_item:\n  rarity: normal\n")

    assert message.startswith("t.yaml:6: start_item.sockets: the target asks for sockets, so its start item must state its own")
    assert "`sockets: any`" in message and "no socket is assumed" in message


def test_a_target_that_asks_for_sockets_with_a_start_item_of_sockets_any_holds_no_socket():
    text = with_start(f"{HEAD}sockets: {{count: 3}}\nstart_item:\n  rarity: normal\n  sockets: any\n", item=False)
    target = parse_target(text, DATA, source="t.yaml")

    assert target.sockets is not None and target.start_item.sockets is None
    assert "start_sockets_assumed" not in {field.name for field in dataclasses.fields(Target)}


def test_the_committed_targets_are_all_there():
    assert len(EXAMPLE_FILES) == 14


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda path: path.name)
def test_every_committed_target_parses_and_states_its_start_item(real, path):
    target = load_target(path, real)
    text = path.read_text(encoding="utf-8")

    assert re.search(r"(?m)^start_item:", text) and re.search(r"(?m)^  rarity:", text)
    if path.name in HAD_NO_START_ITEM:  # the plain item these files always started from, now written down with the guide's words
        assert target.start_item.rarity is Rarity.NORMAL and not target.start_item.mods
