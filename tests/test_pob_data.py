"""Tests for the limited, source-linked ModExplicit projection (S1/S10)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from craftoracle.pob_data import (
    PROJECTION_FIELDS,
    build_pob_explicit_projection,
    parse_mod_explicit_source,
    serialize_projection,
)


SOURCE = Path(__file__).resolve().parents[1] / "sources/pob/Data/ModExplicit.lua"


def _fixture() -> str:
    return "\n".join(
        [
            "-- an authored fixture comment",
            "return {",
            '\t["First"] = { type = "Prefix", affix = "first", level = 1, group = "FirstGroup", weightKey = { "ring", "default", }, weightVal = { 100, 0 }, modTags = { "tag" }, },',
            '\t["Second"] = { type = "Suffix", affix = "second", level = 2, group = "SecondGroup", weightKey = { "amulet", }, weightVal = { 200 }, modTags = {  }, },',
            "}",
        ]
    )


def test_authored_wrapper_preserves_order_and_source_lines() -> None:
    rows = parse_mod_explicit_source(_fixture())

    assert [row["id"] for row in rows] == ["First", "Second"]
    assert [row["source_line"] for row in rows] == [3, 4]
    assert all(set(row) == set(PROJECTION_FIELDS) for row in rows)
    assert all(len(row) == 9 for row in rows)


@pytest.mark.parametrize(
    ("source", "line"),
    [
        (_fixture().replace('["Second"]', '["First"]'), 4),
        (_fixture().replace("return {", "return {\nunexpected", 1), 3),
        (_fixture().replace("return {", "return"), 2),
        (_fixture().replace('affix = "first", ', ""), 3),
        ("", 1),
        ("return {\n", 1),
        (_fixture() + '\n["After"] = { type = "Prefix", affix = "after", level = 1, group = "AfterGroup", weightKey = { "ring", }, weightVal = { 1 }, modTags = { }, },', 6),
    ],
)
def test_rejects_invalid_source_shapes(
    source: str, line: int
) -> None:
    with pytest.raises(ValueError, match=rf"line {line}:"):
        parse_mod_explicit_source(source)


def test_serialization_is_deterministic_utf8_lf_and_trailing_newline() -> None:
    source = _fixture()
    projection = build_pob_explicit_projection(
        source, hashlib.sha256(source.encode("utf-8")).hexdigest()
    )

    first = serialize_projection(projection)
    second = serialize_projection(projection)

    assert first == second
    assert first.endswith(b"\n")
    assert b"\r" not in first
    loaded = json.loads(first)
    assert loaded["schema_version"] == 1
    assert loaded["projection_fields"] == list(PROJECTION_FIELDS)
    assert loaded["source"]["path"] == "sources/pob/Data/ModExplicit.lua"
    assert loaded["source"]["sha256"] == hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()
    assert loaded["source"]["pob_version"] == "2.67.2"
    assert loaded["source"]["poe_version"] == "3.29"
    assert loaded["source"]["version_authority"] == (
        "AGENTS.md section 1 (owner supplied; upstream revision unverified)"
    )
    assert loaded["source"]["record_count"] == 2
    assert "pob_version" not in loaded
    assert "poe_version" not in loaded
    assert "version_authority" not in loaded
    assert "record_count" not in loaded


def test_full_s1_snapshot_has_all_expected_literal_projection_values() -> None:
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "6d400101f60ec48f854daad9a5ca2479b43e9e405f92724e80631b276eaf4568"
    )

    rows = parse_mod_explicit_source(raw.decode("utf-8"))
    by_id = {row["id"]: row for row in rows}

    assert len(rows) == len(by_id) == 4310
    assert len(PROJECTION_FIELDS) == 9
    assert rows[0]["id"] == "Strength1"
    assert rows[0]["source_line"] == 5
    assert by_id["Strength1"]["level"] == 1
    assert len(by_id["Strength1"]["weightKey"]) == 13
    assert len(by_id["Strength1"]["weightVal"]) == 13
    assert sum(by_id["Strength1"]["weightVal"]) == 8333
    assert by_id["Strength1"]["weightVal"][-1] == 0
    assert by_id["Strength8"]["level"] == 74
    assert by_id["Strength8"]["group"] == "Strength"
    assert by_id["Strength8"]["type"] == "Suffix"
    assert rows[-1] == {
        "id": "DeepwaterSwordGrantedSkillGhostCannons",
        "type": "Prefix",
        "affix": "Ghostly Arms",
        "level": 60,
        "group": "DeepwaterSwordGrantedSkillGhostCannons",
        "weightKey": ["deepwater_sword", "default"],
        "weightVal": [2500, 0],
        "modTags": [],
        "source_line": 4314,
    }
