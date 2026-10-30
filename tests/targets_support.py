"""Shared helpers for the `targets` tests: the fixture game data, a small target text, items to check."""

import textwrap
from pathlib import Path

from items_support import AMULET, BODY, DATA, item, roll

from crafting_system.items import ExplicitMod, Item
from crafting_system.targets import Target, TargetError, parse_target

__all__ = [
    "AMULET",
    "BELT",
    "BODY",
    "DATA",
    "EXAMPLES",
    "belt",
    "item",
    "parse",
    "parse_error",
    "roll",
]

BELT = "Metadata/Items/Belts/Belt3"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "targets"

HEADER = """\
base: Paua Amulet
item_level: 84
"""


def parse(text: str, *, header: bool = True, **kwargs) -> Target:
    """Parse `text` against the fixture data. Unless `header` is false, `base` and `item_level` are lines 1 and 2, so the text starts on line 3."""
    body = textwrap.dedent(text).lstrip("\n")
    return parse_target(HEADER + body if header else body, DATA, source="t.yaml", **kwargs)


def parse_error(text: str, *, header: bool = True, **kwargs) -> str:
    """The message of the `TargetError` that parsing `text` raises; fails the test if none is raised."""
    try:
        parse(text, header=header, **kwargs)
    except TargetError as error:
        return str(error)
    raise AssertionError("the target parsed without an error")


def belt(*mods: ExplicitMod, **fields) -> Item:
    """A validated rare Leather Belt at item level 86."""
    fields.setdefault("item_level", 86)
    return item(*mods, base_id=BELT, **fields)
