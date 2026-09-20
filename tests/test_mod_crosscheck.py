"""Known-answer checks for the frozen 54-mod comparison (read 2026-09-20)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.mod_crosscheck import (
    SourceValues,
    build_report_data,
    canonical_output_hash,
    differing_fields,
    parse_coe_assignment,
    parse_coe_ranges,
    parse_poedb_mods_view,
    parse_poedb_ranges,
    parse_pob_ranges,
    resolve_pob_spawn_weight,
    unique_match,
    unique_tier_match,
    render_report,
)


ROOT = Path(__file__).resolve().parents[1]


def _values(
    *,
    level: int = 1,
    weight: int = 1000,
    ranges: tuple[tuple[int, int], ...] = ((3, 9),),
    side: str = "Prefix",
    group: tuple[str, ...] = ("Life",),
) -> SourceValues:
    return SourceValues(level, weight, ranges, side, group)


def test_matching_values_have_no_differences() -> None:
    values = _values()

    assert differing_fields(values, values, values) == ()


def test_different_weight_and_group_name_exactly_name_those_fields() -> None:
    pob = _values(group=("LocalFireDamageTwoHand",))
    coe = _values(weight=900, group=("FireDamage",))
    poedb = _values(weight=900, group=("FireDamage",))

    assert differing_fields(pob, coe, poedb) == ("weight", "group")


def test_missing_and_ambiguous_source_matches_are_explicit() -> None:
    missing = unique_match([], "Hale", 1, "PoEDB fixture")
    ambiguous = unique_match(
        [{"Name": "Hale", "Level": "1"}, {"Name": "Hale", "Level": 1}],
        "Hale",
        1,
        "PoEDB fixture",
    )
    tier_missing = unique_tier_match([], 1, "CoE fixture")

    assert missing.value is None
    assert missing.issue == "missing PoEDB fixture Name/Level match"
    assert ambiguous.value is None
    assert ambiguous.issue == "ambiguous PoEDB fixture Name/Level match (2 rows)"
    assert tier_missing.value is None
    assert tier_missing.issue == "missing CoE fixture ilvl match"


def test_spawn_weight_uses_first_active_tag_including_zero() -> None:
    keys = ["blocked", "default"]
    values = [0, 1000]

    assert resolve_pob_spawn_weight(keys, values, {"blocked", "default"}) == 0
    assert resolve_pob_spawn_weight(keys, values, {"default"}) == 1000
    with pytest.raises(ValueError, match="no PoB spawn-weight tag"):
        resolve_pob_spawn_weight(keys, values, {"ring"})


@pytest.mark.parametrize(
    ("function", "source"),
    [
        (parse_coe_assignment, 'var poecd={"tiers":{}}'),
        (parse_coe_assignment, 'poecd={"tiers":{}}; trailing'),
        (parse_poedb_mods_view, 'new ModsView({"normal":[]})'),
        (parse_pob_ranges, "+(0-5) to Life"),
        (parse_pob_ranges, "+(3—5) to Life"),
        (parse_poedb_ranges, "+(3-5) to Life"),
    ],
)
def test_malformed_wrappers_and_ranges_are_rejected(function: object, source: str) -> None:
    with pytest.raises(ValueError):
        function(source)  # type: ignore[operator]


def test_coe_range_json_requires_positive_integer_pairs() -> None:
    assert parse_coe_ranges("[[3,9],[6,7]]") == ((3, 9), (6, 7))
    with pytest.raises(ValueError):
        parse_coe_ranges("[[3, 9.0]]")
    with pytest.raises(ValueError):
        parse_coe_ranges("[[9, 3]]")


def test_frozen_snapshot_reproduces_specified_counts_and_spot_checks() -> None:
    data = build_report_data(ROOT)
    rows = {row.pob_id: row for row in data.rows}

    assert len(data.rows) == 54
    assert data.selected_count == data.unique_count == 54
    assert data.class_counts == (
        ("Helmet", 10),
        ("Bow", 10),
        ("Ring", 14),
        ("Body Armour", 11),
        ("Gloves", 9),
    )
    assert [row.pob.level for row in data.rows if row.selection.label == "life"] == [
        1,
        5,
        11,
        18,
        24,
        30,
        36,
        44,
        54,
        64,
    ]
    assert [row.pob.level for row in data.rows if row.selection.label == "fire"] == [
        1,
        11,
        18,
        26,
        33,
        42,
        51,
        62,
        74,
        82,
    ]
    assert [row.pob.level for row in data.rows if row.selection.label == "cold"] == [
        1,
        14,
        26,
        38,
        50,
        60,
        72,
        84,
    ]
    assert [row.pob.level for row in data.rows if row.selection.label == "energy-shield"] == [
        3,
        11,
        17,
        23,
        29,
        35,
        43,
        51,
        60,
        69,
        75,
    ]
    assert [row.pob.level for row in data.rows if row.selection.label == "strength"] == [
        1,
        11,
        22,
        33,
        44,
        55,
        66,
        74,
        82,
    ]
    assert [row.pob.level for row in data.rows if row.selection.label == "chaos"] == [
        16,
        30,
        44,
        56,
        65,
        81,
    ]

    assert rows["IncreasedLife0"].pob.ranges == ((3, 9),)
    assert rows["IncreasedLife9"].pob.ranges == ((130, 144),)
    assert rows["LocalAddedFireDamageTwoHand1"].pob.ranges == ((3, 5), (6, 7))
    assert rows["LocalAddedFireDamageTwoHand10"].pob.ranges == ((165, 225), (335, 390))
    assert rows["LocalIncreasedEnergyShield1"].pob.ranges == ((3, 5),)
    assert rows["LocalIncreasedEnergyShield11"].pob.ranges == ((91, 100),)
    assert rows["ColdResist1"].pob.ranges == ((6, 11),)
    assert rows["ColdResist8"].pob.ranges == ((46, 48),)
    assert rows["Strength1"].pob.ranges == ((8, 12),)
    assert rows["Strength9"].pob.ranges == ((51, 55),)
    assert rows["ChaosResist1"].pob.ranges == ((5, 10),)
    assert rows["ChaosResist6"].pob.ranges == ((31, 35),)

    assert [row.pob.weight for row in data.rows if row.selection.label == "fire"] == [
        1400,
        1400,
        1400,
        1400,
        1400,
        1400,
        1400,
        1120,
        490,
        126,
    ]
    assert all(
        row.pob.weight == 250 for row in data.rows if row.selection.label == "chaos"
    )
    assert sum(row.pob.side == "Prefix" for row in data.rows) == 31
    assert sum(row.pob.side == "Suffix" for row in data.rows) == 23

    assert sum(row.coe is not None and row.poedb is not None for row in data.rows) == 54
    assert sum(
        row.coe is not None
        and row.poedb is not None
        and row.pob.level == row.coe.level == row.poedb.level
        for row in data.rows
    ) == 54
    assert sum(
        row.coe is not None
        and row.poedb is not None
        and row.pob.weight == row.coe.weight == row.poedb.weight
        for row in data.rows
    ) == 54
    assert sum(
        row.coe is not None
        and row.poedb is not None
        and row.pob.ranges == row.coe.ranges == row.poedb.ranges
        for row in data.rows
    ) == 54
    assert sum(
        row.coe is not None
        and row.poedb is not None
        and row.pob.side == row.coe.side == row.poedb.side
        for row in data.rows
    ) == 54
    assert sum(
        row.coe is not None
        and row.poedb is not None
        and row.pob.group == row.coe.group == row.poedb.group
        for row in data.rows
    ) == 33
    differing = [row for row in data.rows if row.differing_fields]
    assert len(differing) == 21
    assert all(row.differing_fields == ("group",) for row in differing)


def test_report_rendering_is_deterministic_and_has_a_verifiable_hash() -> None:
    first = render_report(build_report_data(ROOT))
    second = render_report(build_report_data(ROOT))

    assert first == second
    assert "\r" not in first
    declared = re.search(r"(?m)^\| output SHA-256 \| `([0-9a-f]{64})` \|$", first)
    assert declared is not None
    assert declared.group(1) == canonical_output_hash(first)
