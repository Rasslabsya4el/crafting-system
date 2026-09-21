"""Acceptance examples for PoB JSON keys under the provisional Q16/Q17 boundary.

Rule sources: docs/mechanics/pool_resolution.md and affix_generation.md; data comes
from data/pob_bases.json and data/pob_mod_families.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from craftoracle.item_model import (
    ItemState,
    ModRef,
    load_item_data,
    pool_totals,
    resolve_pool,
)


ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def item_data() -> tuple[dict[str, dict], dict[str, dict]]:
    return load_item_data(ROOT / "data/pob_bases.json", ROOT / "data/pob_mod_families.json")


def rare(base_name: str = "Royal Burgonet", mods: tuple[ModRef, ...] = ()) -> ItemState:
    return ItemState(base_name, 86, "rare", mods)


def by_id(entries):
    return {entry.mod_id: entry for entry in entries}


def test_royal_burgonet_single_mod_weights_and_first_match(item_data) -> None:
    bases, mods = item_data
    entries = by_id(resolve_pool(rare(), bases, mods))
    assert entries["IncreasedLife9"].weight == 1000
    assert "IncreasedLife10" not in entries
    assert "IncreasedLife11" not in entries
    assert entries["ChaosResist6"].weight == 250
    assert entries["FireResist7"].weight == 1000
    assert entries["FireResist8"].weight == 1000
    assert entries["ColdResist7"].weight == 1000
    assert entries["ColdResist8"].weight == 1000
    assert entries["LightningResist8"].weight == 1000
    assert entries["Strength8"].weight == 1000


def test_royal_burgonet_totals_and_side_order(item_data) -> None:
    bases, mods = item_data
    prefixes = resolve_pool(rare(), bases, mods, "Prefix")
    suffixes = resolve_pool(rare(), bases, mods, "Suffix")
    assert len(prefixes) == 41
    assert len(suffixes) == 84
    assert pool_totals(rare(), bases, mods) == {"Prefix": 39275, "Suffix": 78400}
    source_ids = [row["id"] for row in mods.values()]
    assert [entry.mod_id for entry in prefixes] == [
        mod_id for mod_id in source_ids if mod_id in {entry.mod_id for entry in prefixes}
    ]


@pytest.mark.parametrize(
    ("base_name", "expected"),
    [
        ("Iron Ring", {"Prefix": 60250, "Suffix": 103600}),
        ("Simple Robe", {"Prefix": 61000, "Suffix": 58200}),
        ("Iron Gauntlets", {"Prefix": 46000, "Suffix": 77000}),
        ("Crude Bow", {"Prefix": 54658, "Suffix": 59100}),
    ],
)
def test_additional_base_totals(item_data, base_name, expected) -> None:
    bases, mods = item_data
    assert pool_totals(rare(base_name), bases, mods) == expected


def test_group_exclusion_and_side_caps(item_data) -> None:
    bases, mods = item_data
    life = ModRef("IncreasedLife9", "Prefix", "IncreasedLife")
    chaos = ModRef("ChaosResist6", "Suffix", "ChaosResistance")
    assert all(entry.group != "IncreasedLife" for entry in resolve_pool(rare(mods=(life,)), bases, mods, "Prefix"))
    assert all(entry.group != "ChaosResistance" for entry in resolve_pool(rare(mods=(chaos,)), bases, mods, "Suffix"))
    other_prefix = next(entry for entry in resolve_pool(rare(), bases, mods, "Prefix") if entry.group != life.group)
    two_prefixes = (life, ModRef(other_prefix.mod_id, other_prefix.type, other_prefix.group))
    assert resolve_pool(rare(mods=two_prefixes), bases, mods, "Prefix")
    third_prefix = next(
        entry for entry in resolve_pool(rare(), bases, mods, "Prefix")
        if entry.group not in {mod.group for mod in two_prefixes}
    )
    three_prefixes = two_prefixes + (ModRef(third_prefix.mod_id, third_prefix.type, third_prefix.group),)
    assert not resolve_pool(rare(mods=three_prefixes), bases, mods, "Prefix")
    assert resolve_pool(rare(mods=three_prefixes), bases, mods, "Suffix")
    magic = ItemState("Royal Burgonet", 86, "magic", (life,))
    assert not resolve_pool(magic, bases, mods, "Prefix")
    assert not resolve_pool(ItemState("Royal Burgonet", 86, "normal"), bases, mods)


def test_fractured_identity_is_validated_and_still_blocks_its_group(item_data) -> None:
    bases, mods = item_data
    life = ModRef("IncreasedLife9", "Prefix", "IncreasedLife")
    fractured = ItemState("Royal Burgonet", 86, "rare", (life,), fractured=True, fractured_mod_id=life.id)
    assert all(entry.group != life.group for entry in resolve_pool(fractured, bases, mods))
    with pytest.raises(ValueError, match="requires fractured=True"):
        resolve_pool(ItemState("Royal Burgonet", 86, "rare", (life,), fractured_mod_id=life.id), bases, mods)
    with pytest.raises(NotImplementedError, match=r"^out of tonight's slice: Q9$"):
        resolve_pool(ItemState("Royal Burgonet", 86, "rare", (life,), fractured=True), bases, mods)
    with pytest.raises(ValueError, match="exactly once"):
        resolve_pool(ItemState("Royal Burgonet", 86, "rare", (life, life), fractured=True, fractured_mod_id=life.id), bases, mods)
    with pytest.raises(ValueError, match="ModRef"):
        resolve_pool(ItemState("Royal Burgonet", 86, "rare", (object(),), fractured=True, fractured_mod_id=life.id), bases, mods)  # type: ignore[arg-type]


@pytest.mark.parametrize("flag", ["corrupted", "influenced", "fractured", "synthesised", "mirrored", "split"])
def test_q9_flags_fail_before_pool_access(item_data, flag) -> None:
    bases, mods = item_data
    item = ItemState("missing base is deliberately hidden", 86, "rare", **{flag: True})
    with pytest.raises(NotImplementedError, match=r"^out of tonight's slice: Q9$"):
        resolve_pool(item, bases, mods)


def test_level_gate_invalid_inputs_and_unknown_ids(item_data) -> None:
    bases, mods = item_data
    assert "ColdResist8" not in by_id(resolve_pool(ItemState("Royal Burgonet", 83, "rare"), bases, mods))
    with pytest.raises(ValueError, match="unknown base"):
        resolve_pool(rare("not a base"), bases, mods)
    with pytest.raises(ValueError, match="rarity"):
        resolve_pool(ItemState("Royal Burgonet", 86, "unique"), bases, mods)
    with pytest.raises(ValueError, match="side"):
        resolve_pool(rare(), bases, mods, "Both")
    with pytest.raises(ValueError, match="unknown mod"):
        resolve_pool(rare(mods=(ModRef("missing", "Prefix", "x"),)), bases, mods)


@pytest.mark.parametrize("level", [True, False, 0, -1])
def test_invalid_item_levels_are_rejected(item_data, level) -> None:
    bases, mods = item_data
    with pytest.raises(ValueError, match="positive integer"):
        resolve_pool(ItemState("Royal Burgonet", level, "rare"), bases, mods)


def test_existing_mod_refs_must_be_possible(item_data) -> None:
    bases, mods = item_data
    life = ModRef("IncreasedLife9", "Prefix", "IncreasedLife")
    other_prefix = next(entry for entry in resolve_pool(rare(), bases, mods, "Prefix") if entry.group != life.group)
    other = ModRef(other_prefix.mod_id, other_prefix.type, other_prefix.group)
    with pytest.raises(ValueError, match="duplicate existing mod id"):
        resolve_pool(rare(mods=(life, life)), bases, mods)
    with pytest.raises(ValueError, match="duplicate existing mod group"):
        resolve_pool(rare(mods=(life, ModRef(other.id, "Prefix", life.group))), bases, mods)
    with pytest.raises(ValueError, match="differs from source row"):
        resolve_pool(rare(mods=(ModRef(life.id, "Suffix", life.group),)), bases, mods)
    with pytest.raises(ValueError, match="differs from source row"):
        resolve_pool(rare(mods=(ModRef(life.id, life.type, "forged"),)), bases, mods)
    unique_prefixes = {entry.group: entry for entry in resolve_pool(rare(), bases, mods, "Prefix")}
    four_prefixes = tuple(
        ModRef(entry.mod_id, entry.type, entry.group) for entry in list(unique_prefixes.values())[:4]
    )
    with pytest.raises(ValueError, match="side cap"):
        resolve_pool(rare(mods=four_prefixes), bases, mods)
    with pytest.raises(ValueError, match="normal side cap"):
        resolve_pool(ItemState("Royal Burgonet", 86, "normal", (life,)), bases, mods)


def test_load_rejects_duplicate_occurrences_ids_and_ambiguous_names(tmp_path: Path) -> None:
    base_rows = {
        "bases": [
            {"name": "Duplicate", "tags": {"default": True}, "source": {"path": "a", "line": 1}},
            {"name": "Duplicate", "tags": {"default": True}, "source": {"path": "b", "line": 1}},
        ]
    }
    mod_rows = {"mods": []}
    base_path, mod_path = tmp_path / "bases.json", tmp_path / "mods.json"
    base_path.write_text(json.dumps(base_rows), encoding="utf-8")
    mod_path.write_text(json.dumps(mod_rows), encoding="utf-8")
    bases, mods = load_item_data(base_path, mod_path)
    assert "Duplicate@a:1" in bases
    with pytest.raises(ValueError, match="ambiguous base"):
        resolve_pool(ItemState("Duplicate", 1, "rare"), bases, mods)

    base_rows["bases"][1]["source"] = {"path": "a", "line": 1}
    base_path.write_text(json.dumps(base_rows), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate base source occurrence"):
        load_item_data(base_path, mod_path)

    base_rows["bases"] = [base_rows["bases"][0]]
    explicit = {"id": "A", "type": "Prefix", "group": "A", "level": 1, "weightKey": ["default"], "weightVal": [1], "source_path": "ModExplicit.lua"}
    mod_rows["mods"] = [explicit, explicit.copy()]
    base_path.write_text(json.dumps(base_rows), encoding="utf-8")
    mod_path.write_text(json.dumps(mod_rows), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate explicit mod id"):
        load_item_data(base_path, mod_path)


def test_malformed_required_rows_raise_value_error() -> None:
    item = ItemState("Base", 1, "rare")
    with pytest.raises(ValueError, match="tags"):
        resolve_pool(item, {"Base": {"name": "Base", "tags": []}}, {})
    bad_mod = {"A": {"id": "A", "type": "Prefix", "group": "A", "level": 1, "weightKey": ["default"], "weightVal": [], "source_path": "ModExplicit.lua"}}
    with pytest.raises(ValueError, match="weightKey"):
        resolve_pool(item, {"Base": {"name": "Base", "tags": {"default": True}}}, bad_mod)
    for weight in (True, -1):
        bad_mod["A"]["weightVal"] = [weight]
        with pytest.raises(ValueError, match="weights"):
            resolve_pool(item, {"Base": {"name": "Base", "tags": {"default": True}}}, bad_mod)
