"""Tests for literal, source-linked PoB bench and essence projections."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest

from craftoracle.pob_recipes import (
    BENCH_PROJECTION_FIELDS,
    ESSENCE_PROJECTION_FIELDS,
    build_pob_bench_projection,
    build_pob_essences_projection,
    parse_bench_source,
    parse_essence_source,
    serialize_projection,
)
from tools.build_pob_recipes import build


ROOT = Path(__file__).resolve().parents[1]
BENCH_SOURCE = ROOT / "sources/pob/Data/ModMaster.lua"
ESSENCE_SOURCE = ROOT / "sources/pob/Data/Essence.lua"


def _bench_fixture() -> str:
    return "\n".join(
        [
            "-- authored fixture comment",
            "return {",
            "\t{ type = \"Prefix\", affix = \"Upgraded\", modTags = { \"resource\", \"life\", }, \"+(15, 25) to {maximum} Life\", statOrder = { 1594, 7, }, level = 15, group = \"IncreasedLife\", types = { [\"Helmet\"] = true, [\"Ring\"] = false, }, ignored = { nested = \"must not enter stat_text\", }, },",
            "\t{ type = \"Suffix\", affix = \"of Craft\", modTags = { }, \"One stat\", statOrder = { 24, }, level = 1, group = \"NoCaster\", types = { [\"Wand\"] = true, }, },",
            "}",
        ]
    )


def _essence_fixture() -> str:
    return "\n".join(
        [
            "-- authored fixture comment",
            "return {",
            '\t["Metadata/Items/Currency/First"] = { name = "Whispering Essence of First", type = 0, tier = 1, mods = { ["Helmet"] = "Strength1", ["Ring"] = "Life1", }, },',
            '\t["Metadata/Items/Currency/Second"] = { name = "Essence of Second", type = 24, tier = 8, mods = { ["Helmet"] = "Strength8", }, },',
            "}",
        ]
    )


def test_authored_bench_fixture_preserves_row_order_and_only_top_level_stats() -> None:
    rows = parse_bench_source(_bench_fixture(), "sources/pob/Data/ModMaster.lua")

    assert [row["source_index"] for row in rows] == [1, 2]
    assert [row["source_line"] for row in rows] == [3, 4]
    assert all(row["source_path"] == "sources/pob/Data/ModMaster.lua" for row in rows)
    assert rows[0] == {
        "source_index": 1,
        "source_path": "sources/pob/Data/ModMaster.lua",
        "source_line": 3,
        "type": "Prefix",
        "affix": "Upgraded",
        "level": 15,
        "group": "IncreasedLife",
        "modTags": ["resource", "life"],
        "statOrder": [1594, 7],
        "stat_text": ["+(15, 25) to {maximum} Life"],
        "types": {"Helmet": True, "Ring": False},
    }
    assert all(set(row) == set(BENCH_PROJECTION_FIELDS) for row in rows)


def test_authored_essence_fixture_preserves_ids_maps_and_source_order() -> None:
    rows = parse_essence_source(_essence_fixture(), "sources/pob/Data/Essence.lua")

    assert [row["id"] for row in rows] == [
        "Metadata/Items/Currency/First",
        "Metadata/Items/Currency/Second",
    ]
    assert [row["source_line"] for row in rows] == [3, 4]
    assert rows[0] == {
        "id": "Metadata/Items/Currency/First",
        "name": "Whispering Essence of First",
        "type": 0,
        "tier": 1,
        "mods": {"Helmet": "Strength1", "Ring": "Life1"},
        "source_path": "sources/pob/Data/Essence.lua",
        "source_line": 3,
    }
    assert all(set(row) == set(ESSENCE_PROJECTION_FIELDS) for row in rows)


@pytest.mark.parametrize(
    ("source", "line", "message"),
    [
        (_bench_fixture().replace('affix = "Upgraded", ', "", 1), 3, "missing required"),
        (_bench_fixture().replace('type = "Prefix", ', 'type = "Prefix", type = "Again", ', 1), 3, "duplicate field"),
        (_bench_fixture().replace('["Helmet"] = true, ["Ring"] = false', '["Helmet"] = true, ["Helmet"] = false', 1), 3, "duplicate map key"),
        (_bench_fixture().replace('\t{ type = "Prefix"', "\tunsupported = 1,\n\t{ type = \"Prefix\"", 1), 3, "non-row content"),
        (_bench_fixture().removesuffix("\n}"), 4, "missing closing return table"),
        (_bench_fixture().replace('level = 15', 'level = 1 + 14', 1), 3, "level must be an integer"),
    ],
)
def test_bench_rejects_malformed_required_projected_or_wrapper_content(
    source: str, line: int, message: str
) -> None:
    with pytest.raises(ValueError, match=rf"ModMaster\.lua: line {line}: .*{message}"):
        parse_bench_source(source, "sources/pob/Data/ModMaster.lua")


@pytest.mark.parametrize(
    ("source", "line", "message"),
    [
        (_essence_fixture().replace('name = "Whispering Essence of First", ', "", 1), 3, "missing required"),
        (_essence_fixture().replace('type = 0, ', 'type = 0, type = 1, ', 1), 3, "duplicate field"),
        (_essence_fixture().replace('["Helmet"] = "Strength1", ["Ring"] = "Life1"', '["Helmet"] = "Strength1", ["Helmet"] = "Life1"', 1), 3, "duplicate map key"),
        (_essence_fixture().replace('Metadata/Items/Currency/Second', 'Metadata/Items/Currency/First', 1), 4, "duplicate essence ID"),
        (_essence_fixture().replace('tier = 1', 'tier = one', 1), 3, "tier must be an integer"),
    ],
)
def test_essence_rejects_malformed_required_projected_or_duplicate_content(
    source: str, line: int, message: str
) -> None:
    with pytest.raises(ValueError, match=rf"Essence\.lua: line {line}: .*{message}"):
        parse_essence_source(source, "sources/pob/Data/Essence.lua")


def test_serialization_is_deterministic_utf8_lf_and_contains_source_metadata() -> None:
    bench_source = _bench_fixture().encode("utf-8")
    essence_source = _essence_fixture().encode("utf-8")
    bench = build_pob_bench_projection(bench_source)
    essences = build_pob_essences_projection(essence_source)

    first_bench = serialize_projection(bench)
    second_bench = serialize_projection(bench)
    first_essences = serialize_projection(essences)
    second_essences = serialize_projection(essences)

    assert first_bench == second_bench
    assert first_essences == second_essences
    assert first_bench.endswith(b"\n") and first_essences.endswith(b"\n")
    assert b"\r" not in first_bench and b"\r" not in first_essences
    for output, source, fields, array_name in [
        (first_bench, bench_source, BENCH_PROJECTION_FIELDS, "bench"),
        (first_essences, essence_source, ESSENCE_PROJECTION_FIELDS, "essences"),
    ]:
        loaded = json.loads(output)
        assert loaded["schema_version"] == 1
        assert loaded["projection_fields"] == list(fields)
        assert loaded["source"]["sha256"] == hashlib.sha256(source).hexdigest()
        assert loaded["source"]["record_count"] == 2
        assert loaded["source"]["pob_version"] == "2.67.2"
        assert loaded["source"]["poe_version"] == "3.29"
        assert "owner-supplied snapshot" in loaded["source"]["version_authority"]
        assert "upstream unverified" in loaded["source"]["version_authority"]
        assert "Q8" in loaded["source"]["version_authority"]
        assert len(loaded[array_name]) == 2


def test_full_s11_and_s22_snapshots_and_two_builds_are_deterministic() -> None:
    bench_raw = BENCH_SOURCE.read_bytes()
    essence_raw = ESSENCE_SOURCE.read_bytes()
    assert hashlib.sha256(bench_raw).hexdigest() == (
        "ddf3fb7499539db0596678d9527c433cc043fa68555f2ea47687b6ffd94cd301"
    )
    assert hashlib.sha256(essence_raw).hexdigest() == (
        "977d1d744bade2d16092511e2d86771b7a3ae7df72a74d97461ebeb310aa1b20"
    )

    bench = build_pob_bench_projection(bench_raw)
    essences = build_pob_essences_projection(essence_raw)
    bench_rows = bench["bench"]
    essence_rows = essences["essences"]

    assert len(bench_rows) == 732
    assert [bench_rows[0]["source_line"], bench_rows[-1]["source_line"]] == [5, 736]
    assert bench_rows[0] == {
        "source_index": 1,
        "source_path": "sources/pob/Data/ModMaster.lua",
        "source_line": 5,
        "type": "Prefix",
        "affix": "Upgraded",
        "level": 15,
        "group": "IncreasedLife",
        "modTags": ["resource", "life"],
        "statOrder": [1594],
        "stat_text": ["+(15-25) to maximum Life"],
        "types": {
            "Body Armour": True,
            "Gloves": True,
            "Boots": True,
            "Helmet": True,
            "Shield": True,
            "Ring": True,
            "Amulet": True,
            "Belt": True,
            "Quiver": True,
        },
    }
    assert bench_rows[-1]["source_index"] == 732
    assert bench_rows[-1]["source_line"] == 736
    assert bench_rows[-1]["group"] == "ItemGenerationCannotRollCasterAffixes"
    assert bench_rows[-1]["type"] == "Suffix"
    assert bench_rows[-1]["statOrder"] == [24]
    assert bench_rows[-1]["stat_text"] == ["Cannot roll Caster Modifiers"]
    assert next(
        row["statOrder"] for row in bench_rows if row["source_line"] == 308
    ) == [857, 857.1]

    assert len(essence_rows) == 105
    assert [essence_rows[0]["source_line"], essence_rows[-1]["source_line"]] == [5, 109]
    assert sum(len(row["mods"]) for row in essence_rows) == 2310
    assert {len(row["mods"]) for row in essence_rows} == {22}
    assert Counter(row["tier"] for row in essence_rows) == {
        1: 4,
        2: 8,
        3: 12,
        4: 16,
        5: 20,
        6: 20,
        7: 20,
        8: 5,
    }
    by_id = {row["id"]: row for row in essence_rows}
    rage = by_id["Metadata/Items/Currency/CurrencyEssenceRage4"]
    assert [rage["name"], rage["type"], rage["tier"]] == [
        "Shrieking Essence of Rage", 9, 6,
    ]
    assert [rage["source_path"], rage["source_line"]] == [
        "sources/pob/Data/Essence.lua", 65,
    ]
    assert rage["mods"]["Helmet"] == "Strength8"
    assert essence_rows[0]["id"] == "Metadata/Items/Currency/CurrencyEssenceHatred1"
    assert [essence_rows[0]["tier"], essence_rows[0]["type"]] == [1, 0]
    assert essence_rows[-1]["id"] == "Metadata/Items/Currency/CurrencyEssenceFaridun1"
    assert [essence_rows[-1]["name"], essence_rows[-1]["type"], essence_rows[-1]["tier"]] == [
        "Essence of Desolation", 24, 8,
    ]

    first_bench_path, first_essence_path = build()
    first_bench = first_bench_path.read_bytes()
    first_essences = first_essence_path.read_bytes()
    second_bench_path, second_essence_path = build()
    assert first_bench_path == second_bench_path
    assert first_essence_path == second_essence_path
    assert first_bench == second_bench_path.read_bytes() == serialize_projection(bench)
    assert first_essences == second_essence_path.read_bytes() == serialize_projection(essences)
