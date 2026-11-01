"""Shared helpers for the tests of socket and plain-quality targets (ticket #227, ADR-0046 and ADR-0049).

`DATA` is the extended fixture data of `targets_implicits_support` (a Simple Robe, Iron Greaves, a Rusted Sword, a Paua Amulet, a Heavy
Belt). `parse` puts four header lines before the text of a test (`base`, `item_level`, `requirements` with one Life entry), so the
text starts on line 5; the file is called `t.yaml`. `ABYSS_DATA` adds a suffix with the Abyssal Socket stat, and `ABYSS_BASE_DATA` a
Simple Robe whose base implicit has it. `dump_target` and `assert_golden_json` write and compare a parsed target as JSON.
"""

import dataclasses
import enum
import json
import os
import textwrap
from pathlib import Path

from targets_implicits_support import TEXTED, assert_error

from crafting_system.data import GameData, StatRange
from crafting_system.items import Item, Rarity, SocketColour, Sockets
from crafting_system.targets import Target, TargetError, parse_target

__all__ = [
    "ABYSS_BASE_DATA",
    "ABYSS_DATA",
    "ABYSS_IMPLICIT",
    "ABYSS_MOD",
    "DATA",
    "GOLDEN",
    "ROBE",
    "assert_error",
    "assert_golden_json",
    "dump_target",
    "parse",
    "parse_error",
    "robe_with",
]

DATA = TEXTED
GOLDEN = Path(__file__).resolve().parent / "golden"
ROBE = "Metadata/Items/Armours/BodyArmours/BodyInt1"
ABYSS_STAT = "local_has_X_abyss_sockets"
ABYSS_MOD = "AbyssSocketSuffix1"
ABYSS_IMPLICIT = "AbyssSocketImplicit1"
HEADER = """\
base: {base}
item_level: 84
requirements:
  - family: IncreasedLife
"""


def _abyss(data: GameData) -> GameData:
    """`data` plus an ordinary suffix of domain item that carries the Abyssal Socket stat, and the same stat as a base implicit."""
    stats = (StatRange(ABYSS_STAT, 1, 1),)
    suffix = dataclasses.replace(
        data.mods["LightningResist1"], id=ABYSS_MOD, families=("AbyssSocket",), type="AbyssSocket", text="Has 1 Abyssal Socket", stats=stats
    )
    implicit = dataclasses.replace(suffix, id=ABYSS_IMPLICIT, generation_type="unique", spawn_weights=())
    return dataclasses.replace(data, mods={**data.mods, ABYSS_MOD: suffix, ABYSS_IMPLICIT: implicit})


def _robe_with_abyss_implicit(data: GameData) -> GameData:
    robe = dataclasses.replace(data.base_items[ROBE], implicits=(ABYSS_IMPLICIT,))
    return dataclasses.replace(data, base_items={**data.base_items, ROBE: robe})


ABYSS_DATA = _abyss(DATA)
ABYSS_BASE_DATA = _robe_with_abyss_implicit(ABYSS_DATA)


def parse(text: str, *, base: str = "Simple Robe", data: GameData = DATA, header: bool = True) -> Target:
    """Parse `text` after the four header lines of `base` (so it starts on line 5); unless `header` is false it stands alone."""
    body = textwrap.dedent(text).lstrip("\n")
    return parse_target((HEADER.format(base=base) if header else "") + body, data, source="t.yaml")


def parse_error(text: str, *, base: str = "Simple Robe", data: GameData = DATA, header: bool = True) -> str:
    """The message of the `TargetError` that parsing `text` raises; fails the test if none is raised."""
    try:
        parse(text, base=base, data=data, header=header)
    except TargetError as error:
        return str(error)
    raise AssertionError("the target parsed without an error")


def robe_with(colours: str, links: tuple[int, ...] | None = None, *, quality=None) -> Item:
    """A validated Simple Robe at item level 84 with the sockets `colours` (letters W, R, G, B, one per socket), in groups `links` (default: none linked)."""
    shades = tuple(SocketColour(letter) for letter in colours)
    sockets = Sockets(shades, links if links is not None else (1,) * len(shades))
    return Item.build(DATA, base_id=ROBE, item_level=84, rarity=Rarity.NORMAL, sockets=sockets, **({} if quality is None else {"quality": quality}))


def dump_target(target: Target) -> str:
    """A parsed target as deterministic, indented JSON: dataclasses as dicts (with their class name under `_type`), enums as their
    values, sets sorted, paths as text. It reads no game data, so the text says only what the target holds."""
    return json.dumps(_plain(target), indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _plain(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        found: dict[str, object] = {"_type": type(value).__name__}
        found.update({field.name: _plain(getattr(value, field.name)) for field in dataclasses.fields(value)})
        return found
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, frozenset | set):
        return sorted((_plain(entry) for entry in value), key=str)
    if isinstance(value, tuple | list):
        return [_plain(entry) for entry in value]
    if isinstance(value, dict):
        return {str(key): _plain(entry) for key, entry in value.items()}
    if isinstance(value, Path):
        return str(value)
    return value


def assert_golden_json(name: str, text: str) -> None:
    """`text` equals `tests/golden/<name>.json`; `UPDATE_GOLDEN=1` writes it first, a missing file fails."""
    path = GOLDEN / f"{name}.json"
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    assert path.exists(), f"no golden file {path}; run with UPDATE_GOLDEN=1 to write it"
    assert text == path.read_text(encoding="utf-8"), f"{name} differs from its golden file {path}"
