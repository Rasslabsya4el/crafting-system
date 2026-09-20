"""Tests for literal, source-preserving PoB modifier family projections.

Source fixtures are authored. Frozen assertions use S1/S24/S25, the local
owner-supplied PoB 2.67.2 (PoE 3.29) snapshot read 2026-09-20.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from craftoracle.pob_mod_families import (
    PROJECTION_FIELDS,
    SOURCE_PATHS,
    build_pob_mod_families_projection,
    parse_mod_source,
    serialize_projection,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "sources/pob/Data"


def _fixture() -> str:
    return """-- generated fixture
return {
    ["TopLevel"] = {
        type = "Prefix",
        affix = "a\\\"ffix",
        "Adds (1-2), {test}",
        statOrder = { 7, 8, },
        level = 12,
        group = "Example",
        weightKey = { "ring", "default", },
        weightVal = { 100, 0, },
        tags = { "has_attack_mod", },
        weightMultiplierKey = { "weapon", "default", },
        weightMultiplierVal = { 50, 100, },
        modTags = { "attack", },
        tradeHashes = { [123] = { "nested stat must not project" }, },
    },
}
"""


def _source_payloads() -> dict[str, bytes]:
    return {
        source_path: _fixture().encode("utf-8")
        for source_path in SOURCE_PATHS
    }


def test_fixture_preserves_top_level_literals_and_ignores_nested_trade_text() -> None:
    rows = parse_mod_source(_fixture(), "fixture.lua")

    assert rows == [
        {
            "source_path": "fixture.lua",
            "source_line": 3,
            "id": "TopLevel",
            "type": "Prefix",
            "affix": 'a"ffix',
            "level": 12,
            "group": "Example",
            "weightKey": ["ring", "default"],
            "weightVal": [100, 0],
            "modTags": ["attack"],
            "stat_text": ["Adds (1-2), {test}"],
            "statOrder": [7, 8],
            "tags": ["has_attack_mod"],
            "weightMultiplierKey": ["weapon", "default"],
            "weightMultiplierVal": [50, 100],
        }
    ]
    assert list(rows[0]) == list(PROJECTION_FIELDS)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (_fixture().replace('type = "Prefix",', 'type = "Prefix", type = "Suffix",'), "duplicate projected key"),
        (_fixture().replace('weightVal = { 100, 0, },', 'weightVal = { 100, },'), "lengths differ"),
        (_fixture().replace('statOrder = { 7, 8, },', 'statOrder = { "bad", },'), "number"),
        (_fixture().replace('level = 12,', 'level = untrusted(),'), "unsupported"),
        (_fixture() + "unexpected", "unexpected content"),
        ("return {\n", "missing closing"),
    ],
)
def test_rejects_malformed_projected_structure(
    source: str, message: str
) -> None:
    with pytest.raises(ValueError, match=rf"fixture\.lua:\d+: .*{message}"):
        parse_mod_source(source, "fixture.lua")


def test_duplicate_ids_are_rejected_with_the_second_row_line() -> None:
    duplicate = _fixture().replace(
        "}\n",
        '    ["TopLevel"] = { type = "Prefix", affix = "x", "x", statOrder = { 1 }, level = 1, group = "x", weightKey = { }, weightVal = { }, modTags = { }, },\n}\n',
        1,
    )

    with pytest.raises(ValueError, match=r"fixture\.lua:18: duplicate id 'TopLevel'"):
        parse_mod_source(duplicate, "fixture.lua")


def test_all_optional_fields_are_null_when_absent() -> None:
    source = _fixture().replace('tags = { "has_attack_mod", },\n        ', "").replace(
        'weightMultiplierKey = { "weapon", "default", },\n        ', ""
    ).replace('weightMultiplierVal = { 50, 100, },\n        ', "")

    parsed = parse_mod_source(source, "fixture.lua")[0]
    assert parsed["tags"] is None
    assert parsed["weightMultiplierKey"] is None
    assert parsed["weightMultiplierVal"] is None


def test_stat_order_preserves_the_known_non_integer_pob_literal() -> None:
    source = """return {
["SpiritMinionEssence1"] = { type = "Suffix", affix = "of the Essence", "Triggers Level 20 Spectral Spirits when Equipped", "+3 to maximum number of Spectral Spirits", statOrder = { 774, 774.1 }, level = 63, group = "GrantsEssenceMinion", weightKey = { "default", }, weightVal = { 0 }, modTags = { "minion" }, },
}
"""

    row = parse_mod_source(source, "sources/pob/Data/ModExplicit.lua")[0]
    assert row["statOrder"] == [774, 774.1]


def test_projection_serializes_deterministically_with_root_snapshot_metadata() -> None:
    payloads = _source_payloads()
    projection = build_pob_mod_families_projection(payloads)

    first = serialize_projection(projection)
    second = serialize_projection(projection)
    loaded = json.loads(first)

    assert first == second
    assert first.endswith(b"\n")
    assert b"\r" not in first
    assert loaded["schema_version"] == 1
    assert loaded["projection_fields"] == list(PROJECTION_FIELDS)
    assert loaded["source_metadata"] == {
        "authority": "owner-supplied snapshot",
        "pob_version": "2.67.2",
        "poe_version": "3.29",
        "upstream_revision": "unverified (Q8)",
    }
    assert [source["path"] for source in loaded["sources"]] == list(SOURCE_PATHS)
    assert [source["record_count"] for source in loaded["sources"]] == [1] * 6
    assert [source["sha256"] for source in loaded["sources"]] == [
        hashlib.sha256(payloads[path]).hexdigest() for path in SOURCE_PATHS
    ]
    assert len(loaded["mods"]) == 6


def _snapshot_payloads_or_skip() -> dict[str, bytes]:
    paths = [ROOT / source_path for source_path in SOURCE_PATHS]
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
    if missing:
        pytest.skip("owner-supplied PoB snapshot missing: " + ", ".join(missing))
    return {
        source_path: (ROOT / source_path).read_bytes()
        for source_path in SOURCE_PATHS
    }


def test_s1_s24_s25_frozen_snapshot_counts_and_required_first_rows() -> None:
    projection = build_pob_mod_families_projection(_snapshot_payloads_or_skip())
    by_source = {source["path"]: source["record_count"] for source in projection["sources"]}
    mods = projection["mods"]

    assert by_source == {
        "sources/pob/Data/ModExplicit.lua": 4310,
        "sources/pob/Data/ModVeiled.lua": 258,
        "sources/pob/Data/ModEldritch.lua": 4086,
        "sources/pob/Data/ModCorrupted.lua": 371,
        "sources/pob/Data/ModDelve.lua": 186,
        "sources/pob/Data/ModSynthesis.lua": 1344,
    }
    assert len(mods) == 10555
    assert [mods[index]["source_line"] for index in (0, 4310, 4568, 8654, 9025, 9211)] == [5] * 6

    veiled = [mod for mod in mods if mod["source_path"].endswith("ModVeiled.lua")]
    assert {mod_type: sum(mod["type"] == mod_type for mod in veiled) for mod_type in ("Prefix", "Suffix")} == {
        "Prefix": 162,
        "Suffix": 96,
    }
    assert veiled[0]["id"] == "JunMasterAvoidStunAndElementalStatusAilments1"
    assert veiled[0]["stat_text"] == [
        "(20-25)% chance to Avoid Elemental Ailments",
        "(20-25)% chance to Avoid being Stunned",
    ]
    assert veiled[0]["statOrder"] == [1869, 1877]
    assert veiled[0]["weightVal"] == [0, 0]

    eldritch = [mod for mod in mods if mod["source_path"].endswith("ModEldritch.lua")]
    assert {mod_type: sum(mod["type"] == mod_type for mod in eldritch) for mod_type in ("Exarch", "Eater")} == {
        "Exarch": 2016,
        "Eater": 2070,
    }
    assert eldritch[0]["id"] == "IncreasedAttackSpeedEldritchImplicit1"
    assert eldritch[0]["level"] == 75
    assert eldritch[0]["stat_text"] == ["8% increased Attack Speed"]
    assert eldritch[0]["weightVal"] == [0, 1000, 0]

    delve = [mod for mod in mods if mod["source_path"].endswith("ModDelve.lua")]
    assert {mod_type: sum(mod["type"] == mod_type for mod in delve) for mod_type in ("DelveImplicit", "Prefix", "Suffix")} == {
        "DelveImplicit": 9,
        "Prefix": 74,
        "Suffix": 103,
    }

    synthesis = [mod for mod in mods if mod["source_path"].endswith("ModSynthesis.lua")]
    assert synthesis[0]["id"] == "SynthesisImplicitLife1"
    assert synthesis[0]["weightKey"] == []
    assert synthesis[0]["weightVal"] == []
    assert synthesis[0]["stat_text"] == ["+(8-10) to maximum Life"]
    optional_counts = {
        source_path: {
            field: sum(
                mod["source_path"] == source_path and mod[field] is not None
                for mod in mods
            )
            for field in ("tags", "weightMultiplierKey", "weightMultiplierVal")
        }
        for source_path in SOURCE_PATHS
    }
    assert optional_counts == {
        "sources/pob/Data/ModExplicit.lua": {
            "tags": 364,
            "weightMultiplierKey": 364,
            "weightMultiplierVal": 364,
        },
        "sources/pob/Data/ModVeiled.lua": {
            "tags": 0,
            "weightMultiplierKey": 0,
            "weightMultiplierVal": 0,
        },
        "sources/pob/Data/ModEldritch.lua": {
            "tags": 0,
            "weightMultiplierKey": 0,
            "weightMultiplierVal": 0,
        },
        "sources/pob/Data/ModCorrupted.lua": {
            "tags": 0,
            "weightMultiplierKey": 0,
            "weightMultiplierVal": 0,
        },
        "sources/pob/Data/ModDelve.lua": {
            "tags": 2,
            "weightMultiplierKey": 2,
            "weightMultiplierVal": 2,
        },
        "sources/pob/Data/ModSynthesis.lua": {
            "tags": 0,
            "weightMultiplierKey": 0,
            "weightMultiplierVal": 0,
        },
    }
    assert sum(
        not isinstance(value, int)
        for mod in mods
        for value in mod["statOrder"]
    ) == 6


def test_full_snapshot_two_builds_are_byte_identical() -> None:
    payloads = _snapshot_payloads_or_skip()
    first = serialize_projection(build_pob_mod_families_projection(payloads))
    second = serialize_projection(build_pob_mod_families_projection(payloads))

    assert first == second
