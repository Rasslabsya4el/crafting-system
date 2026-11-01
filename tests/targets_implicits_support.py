"""Shared helpers for the tests of target `implicits:`, `quality:` and the new start-item keys (ticket #141).

`TEXTED` is the extended fixture data of `implicits_support` with real stat texts on the hand-made
implicits (they have the placeholder text `x` there, which no selector can name) and three more records:
an explicit suffix and a family-sharing influence suffix with the same text as the Avoid Shock implicit
(real ones exist: `ChanceToAvoidShockEssence7`, `AvoidShockInfluence1`), and an implicit whose only
mod is a presence variant. `implicits_support` itself is not changed.

`parse` puts four header lines before the text of a test, so the text starts on line 5.
"""

import dataclasses
import textwrap

from implicits_support import EXTENDED

from crafting_system.data import GameData
from crafting_system.targets import Target, TargetError, parse_target

AVOID_SHOCK = "#% chance to Avoid being Shocked"
HEADER = """\
base: Heavy Belt
item_level: 84
requirements:
  - family: IncreasedLife
"""

TEXTS = {
    "StrengthImplicitBelt1": "+(25-35) to Strength",
    "AvoidShockEldritchImplicit1": "(33-35)% chance to Avoid being Shocked",
    "AvoidShockEldritchImplicit2": "(36-38)% chance to Avoid being Shocked",
    "AvoidShockEldritchImplicit3": "(39-41)% chance to Avoid being Shocked",
    "AvoidShockEldritchImplicitUniquePresence4": "(51-53)% chance to Avoid being Shocked",
    "AvoidShockEldritchImplicitPinnaclePresence2": "(54-56)% chance to Avoid being Shocked",
    "ChanceToShockEldritchImplicit2": "10% chance to Shock",
}


def _texted() -> GameData:
    mods = {mod_id: dataclasses.replace(EXTENDED.mods[mod_id], text=text) for mod_id, text in TEXTS.items()}
    suffix = EXTENDED.mods["LightningResist1"]
    mods["ChanceToAvoidShockEssence7"] = dataclasses.replace(
        suffix, id="ChanceToAvoidShockEssence7", families=("ReducedShockChance",), text="(56-60)% chance to Avoid being Shocked"
    )
    mods["AvoidShockInfluence1"] = dataclasses.replace(
        suffix, id="AvoidShockInfluence1", families=("AvoidShock",), text="(31-35)% chance to Avoid being Shocked"
    )
    mods["LoneEldritchImplicitUniquePresence1"] = dataclasses.replace(
        EXTENDED.mods["AvoidShockEldritchImplicitUniquePresence4"],
        id="LoneEldritchImplicitUniquePresence1",
        families=("Lone",),
        text="5% lone",
    )
    return dataclasses.replace(EXTENDED, mods={**EXTENDED.mods, **mods})


TEXTED = _texted()


def parse(text: str, *, header: bool = True) -> Target:
    """Parse `text` on `TEXTED`; unless `header` is false it follows `HEADER` (so it starts on line 5)."""
    body = textwrap.dedent(text).lstrip("\n")
    return parse_target(HEADER + body if header else body, TEXTED, source="t.yaml")


def parse_error(text: str, *, header: bool = True) -> str:
    """The message of the `TargetError` that parsing `text` raises; fails the test if none is raised."""
    try:
        parse(text, header=header)
    except TargetError as error:
        return str(error)
    raise AssertionError("the target parsed without an error")


def assert_error(message: str, line: int, key: str, *causes: str) -> None:
    assert message.startswith(f"t.yaml:{line}: "), message
    assert f": {key}: " in message, message
    for cause in causes:
        assert cause in message, message
