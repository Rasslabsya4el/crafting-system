"""Parser for one generated, single-line PoB modifier row.

This deliberately recognizes only the flat fields projected by ``parse_mod_row``.
It does not parse a Lua file, execute Lua, or resolve modifier eligibility.
Source values exercised by the smoke test: PoB data ``ModExplicit.lua``, key
``Strength1``, line 5, read 2026-09-20.
"""

from __future__ import annotations

import re


_ROW = re.compile(r'^\s*\["(?P<id>[^"]+)"\]\s*=\s*\{(?P<body>.*)\},\s*$')


def _one_string_field(body: str, name: str) -> str:
    matches = re.findall(rf'\b{re.escape(name)}\s*=\s*"([^"]*)"', body)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one quoted {name} field")
    return matches[0]


def _one_integer_field(body: str, name: str) -> int:
    matches = re.findall(
        rf'\b{re.escape(name)}\s*=\s*([0-9]+)(?=\s*(?:,|\}}))', body
    )
    if len(matches) != 1:
        raise ValueError(f"expected exactly one non-negative integer {name} field")
    return int(matches[0])


def _one_array_field(body: str, name: str) -> str:
    matches = re.findall(
        rf'\b{re.escape(name)}\s*=\s*\{{([^{{}}]*)\}}', body
    )
    if len(matches) != 1:
        raise ValueError(f"expected exactly one flat {name} array")
    return matches[0]


def _array_members(content: str) -> list[str]:
    stripped = content.strip()
    if not stripped:
        return []
    members = [member.strip() for member in content.split(",")]
    if members[-1] == "":
        members.pop()
    if not members or any(not member for member in members):
        raise ValueError("array members must be flat and comma-separated")
    return members


def _string_array(content: str) -> list[str]:
    values: list[str] = []
    for member in _array_members(content):
        match = re.fullmatch(r'"([^"]*)"', member)
        if match is None:
            raise ValueError("array must contain quoted strings")
        values.append(match.group(1))
    return values


def _integer_array(content: str) -> list[int]:
    values: list[int] = []
    for member in _array_members(content):
        if re.fullmatch(r"[0-9]+", member) is None:
            raise ValueError("array must contain non-negative integers")
        values.append(int(member))
    return values


def parse_mod_row(row: str) -> dict:
    """Project one generated PoB modifier row without evaluating any Lua.

    The accepted input is one line in the form ``[\"id\"] = { ... },``.  Requested
    arrays must be flat.  A malformed row, a missing projected field, or unequal
    ``weightKey`` and ``weightVal`` lengths raises ``ValueError``.
    """
    if not isinstance(row, str):
        raise ValueError("row must be a string")

    match = _ROW.fullmatch(row)
    if match is None:
        raise ValueError("input is not a single generated modifier row")

    body = match.group("body")
    weight_keys = _string_array(_one_array_field(body, "weightKey"))
    weight_values = _integer_array(_one_array_field(body, "weightVal"))
    if len(weight_keys) != len(weight_values):
        raise ValueError("weightKey and weightVal lengths differ")

    return {
        "id": match.group("id"),
        "type": _one_string_field(body, "type"),
        "affix": _one_string_field(body, "affix"),
        "level": _one_integer_field(body, "level"),
        "group": _one_string_field(body, "group"),
        "weightKey": weight_keys,
        "weightVal": weight_values,
        "modTags": _string_array(_one_array_field(body, "modTags")),
    }
