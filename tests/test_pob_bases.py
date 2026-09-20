"""Tests for the literal, deliberately limited PoB item-base projection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from craftoracle.pob_bases import (
    PROJECTION_FIELDS,
    build_pob_bases_projection,
    parse_base_source,
    parse_base_sources,
    serialize_projection,
)
from tools.build_pob_bases import build


ROOT = Path(__file__).resolve().parents[1]
BASES_DIRECTORY = ROOT / "sources/pob/Data/Bases"


def _fixture() -> str:
    return "\n".join(
        [
            "-- authored fixture comment",
            "local itemBases = ...",
            "",
            'itemBases["First"] = {',
            '\ttype = "Helmet",',
            '\tsubType = "Armour",',
            "\tsocketLimit = 4,",
            "\ttags = { armour = true, -- line comment with } and {",
            "\t\tdefault = true, },",
            '\tinfluenceTags = { shaper = "helmet_shaper", },',
            "\t-- record comment with } and {",
            '\tignored = { nested = { text = "a } brace { stays quoted", }, },',
            "}",
            "",
            'itemBases["Second"] = {',
            '\ttype = "Bow",',
            "\ttags = { bow = true, },",
            '\tinfluenceTags = { shaper = "bow_shaper", },',
            "}",
        ]
    )


def test_authored_fixture_preserves_order_provenance_and_optional_fields() -> None:
    bases = parse_base_source(_fixture(), "sources/pob/Data/Bases/example.lua")

    assert [base["name"] for base in bases] == ["First", "Second"]
    assert [base["source"] for base in bases] == [
        {"path": "sources/pob/Data/Bases/example.lua", "line": 4},
        {"path": "sources/pob/Data/Bases/example.lua", "line": 15},
    ]
    assert bases[0] == {
        "name": "First",
        "type": "Helmet",
        "subType": "Armour",
        "socketLimit": 4,
        "tags": {"armour": True, "default": True},
        "influenceTags": {"shaper": "helmet_shaper"},
        "source": {"path": "sources/pob/Data/Bases/example.lua", "line": 4},
    }
    assert bases[1]["subType"] is None
    assert bases[1]["socketLimit"] is None
    assert all(set(base) == set(PROJECTION_FIELDS) for base in bases)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (_fixture().replace("armour = true", 'armour = "true"'), "tags"),
        (_fixture().replace("armour = true,", ",", 1), "empty projected map entry"),
        (_fixture().replace("armour = true, --", "armour = true,, --"), "empty projected map entry"),
        (_fixture().replace('"helmet_shaper"', "true"), "influenceTags"),
        (_fixture().replace('"Helmet"', '"Hel\\qmet"'), "unknown string escape"),
        (_fixture().replace('"Helmet"', '"Hel\nmet"'), "literal newline"),
        (_fixture().replace("\ttags = { armour = true, -- line comment with } and {\n\t\tdefault = true, },\n", ""), "missing required"),
        (_fixture().replace("\ttags = { armour = true, -- line comment with } and {\n\t\tdefault = true, },\n", "\ttags = { armour = true, },\n\ttags = { default = true, },\n"), "duplicate projected field"),
        (_fixture().replace("\n}\n\nitemBases[\"Second\"]", "\n\nitemBases[\"Second\"]", 1), "unclosed record"),
        (_fixture().replace("\n\nitemBases[\"Second\"]", "\nunexpected\nitemBases[\"Second\"]"), "unexpected outside content"),
    ],
)
def test_rejects_required_invalid_source_shapes(source: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_base_source(source, "sources/pob/Data/Bases/example.lua")


def test_repeated_display_names_are_retained_with_distinct_source_lines() -> None:
    source = _fixture().replace('itemBases["Second"]', 'itemBases["First"]')
    bases = parse_base_source(source, "sources/pob/Data/Bases/example.lua")
    assert [base["name"] for base in bases] == ["First", "First"]
    assert [base["source"]["line"] for base in bases] == [4, 15]


def test_rejects_duplicate_source_identity_across_inputs() -> None:
    with pytest.raises(ValueError, match="duplicate source identity"):
        parse_base_sources(
            [
                ("sources/pob/Data/Bases/one.lua", _fixture()),
                ("sources/pob/Data/Bases/one.lua", _fixture()),
            ]
        )


def test_serialization_is_deterministic_utf8_lf_and_trailing_newline() -> None:
    source = _fixture()
    projection = build_pob_bases_projection(
        [
            (
                "sources/pob/Data/Bases/example.lua",
                source.encode("utf-8"),
            )
        ]
    )

    first = serialize_projection(projection)
    second = serialize_projection(projection)

    assert first == second
    assert first.endswith(b"\n")
    assert b"\r" not in first
    loaded = json.loads(first)
    assert loaded["schema_version"] == 1
    assert loaded["projection_fields"] == list(PROJECTION_FIELDS)
    assert loaded["sources"] == [
        {
            "path": "sources/pob/Data/Bases/example.lua",
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "record_count": 2,
        }
    ]
    assert loaded["pob_version"] == "2.67.2"
    assert loaded["poe_version"] == "3.29"
    assert loaded["version_authority"] == (
        "AGENTS.md section 1 (owner supplied; upstream revision unverified)"
    )


def test_full_s1_projection_and_real_build_are_deterministic() -> None:
    expected = [
        ("helmet.lua", 95, "Iron Hat", "Golden Wreath", "bb5f8a66c491ae5073350d9c5b0c45edafc137712d5a555435a9421d0419db8e"),
        ("bow.lua", 29, "Crude Bow", "Ethereal Bow", "ad420096d028a4aadaef230e880f7b9d5feb57fbe8613d8e3722b3b4238e38f0"),
        ("ring.lua", 48, "Iron Ring", "Jet Ring", "6db93137a173e81f2e16374ba96e845536004903bc01f12443bd754785bca86d"),
        ("body.lua", 123, "Plate Vest", "Golden Mantle", "b764b6065a41af36d8433dd26838a6290ce0abd17431c3b7090ab935534f9557"),
        ("gloves.lua", 80, "Iron Gauntlets", "Golden Bracers", "6c251c4582062109de151ad9c7b5bf9583c4b51fb6fa27e7f9d1648d6ead2217"),
    ]
    raw_sources = []
    for filename, count, first_name, last_name, sha256 in expected:
        raw = (BASES_DIRECTORY / filename).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == sha256
        raw_sources.append((f"sources/pob/Data/Bases/{filename}", raw))

    projection = build_pob_bases_projection(raw_sources)
    bases = projection["bases"]
    sources = projection["sources"]
    assert [source["record_count"] for source in sources] == [95, 29, 48, 123, 80]
    offset = 0
    for (_, count, first_name, last_name, _), source in zip(expected, sources, strict=True):
        assert bases[offset]["name"] == first_name
        assert bases[offset + count - 1]["name"] == last_name
        offset += count

    assert len(bases) == 375
    assert len({base["name"] for base in bases}) == 371
    assert [base["source"]["line"] for base in bases if base["name"] == "Two-Stone Ring"] == [105, 114, 123]
    assert [base["source"]["line"] for base in bases if base["name"] == "Shadowed Ring"] == [312, 321, 330]
    assert [
        sum(base["subType"] is None for base in bases[offset:offset + count])
        for offset, (_, count, _, _, _) in zip((0, 95, 124, 172, 295), expected, strict=True)
    ] == [1, 29, 48, 0, 1]
    assert [
        sum(base["socketLimit"] is None for base in bases[offset:offset + count])
        for offset, (_, count, _, _, _) in zip((0, 95, 124, 172, 295), expected, strict=True)
    ] == [0, 0, 48, 0, 0]

    by_name = {base["name"]: base for base in bases}
    assert by_name["Iron Hat"]["type"] == "Helmet"
    assert by_name["Iron Hat"]["subType"] == "Armour"
    assert by_name["Iron Hat"]["socketLimit"] == 4
    assert by_name["Iron Hat"]["tags"] == {
        "armour": True, "default": True, "helmet": True, "str_armour": True,
    }
    assert len(by_name["Iron Hat"]["influenceTags"]) == 8
    assert by_name["Iron Hat"]["influenceTags"]["shaper"] == "helmet_shaper"
    assert by_name["Crude Bow"]["type"] == "Bow"
    assert by_name["Crude Bow"]["subType"] is None
    assert by_name["Crude Bow"]["socketLimit"] == 6
    assert by_name["Crude Bow"]["tags"] == {
        "bow": True, "default": True, "ranged": True,
        "two_hand_weapon": True, "twohand": True, "weapon": True,
    }
    assert len(by_name["Crude Bow"]["influenceTags"]) == 8
    assert by_name["Iron Ring"]["type"] == "Ring"
    assert by_name["Iron Ring"]["subType"] is None
    assert by_name["Iron Ring"]["socketLimit"] is None
    assert by_name["Iron Ring"]["tags"] == {"default": True, "ring": True}

    first_output = build().read_bytes()
    second_output = build().read_bytes()
    assert first_output == second_output == serialize_projection(projection)
