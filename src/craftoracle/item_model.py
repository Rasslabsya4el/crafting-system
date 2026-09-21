"""Ordinary explicit-mod pool resolution from the accepted PoB projections."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_SIDES = frozenset(("Prefix", "Suffix"))
_RARITY_CAPS = {"normal": 0, "magic": 1, "rare": 3}
_Q9_ERROR = "out of tonight's slice: Q9"


@dataclass(frozen=True)
class ModRef:
    id: str
    type: str
    group: str


@dataclass(frozen=True)
class ItemState:
    base_name: str
    item_level: int
    rarity: str
    mods: tuple[ModRef, ...] = ()
    corrupted: bool = False
    influenced: bool = False
    fractured: bool = False
    synthesised: bool = False
    mirrored: bool = False
    split: bool = False


@dataclass(frozen=True)
class PoolEntry:
    mod_id: str
    type: str
    group: str
    weight: int
    level: int


def load_item_data(base_json: Path, mods_json: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    """Load projections while preserving their JSON record order."""
    bases_doc = _load_json_object(base_json, "base")
    mods_doc = _load_json_object(mods_json, "mod")
    bases = _required_list(bases_doc, "bases", "base")
    mods = _required_list(mods_doc, "mods", "mod")

    rows_by_name: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    seen_occurrences: set[str] = set()
    for row in bases:
        if not isinstance(row, dict):
            raise ValueError("malformed base row")
        name = row.get("name")
        source = row.get("source")
        if not isinstance(name, str) or not isinstance(source, dict):
            raise ValueError("malformed base row: name and source are required")
        path, line = source.get("path"), source.get("line")
        if not isinstance(path, str) or not isinstance(line, int):
            raise ValueError("malformed base row: source.path and source.line are required")
        occurrence = f"{name}@{path}:{line}"
        if occurrence in seen_occurrences:
            raise ValueError(f"duplicate base source occurrence: {occurrence}")
        seen_occurrences.add(occurrence)
        rows_by_name.setdefault(name, []).append((occurrence, row))

    base_rows: dict[str, dict] = {}
    for name, occurrences in rows_by_name.items():
        for occurrence, row in occurrences:
            base_rows[occurrence] = row
        if len(occurrences) == 1:
            base_rows[name] = occurrences[0][1]

    mod_rows: dict[str, dict] = {}
    seen_mod_occurrences: set[tuple[str, int]] = set()
    for row in mods:
        if not isinstance(row, dict):
            raise ValueError("malformed mod row")
        source_path = row.get("source_path")
        if not isinstance(source_path, str) or not source_path.endswith("ModExplicit.lua"):
            continue
        mod_id = row.get("id")
        if not isinstance(mod_id, str):
            raise ValueError("malformed explicit mod row: id is required")
        if mod_id in mod_rows:
            raise ValueError(f"duplicate explicit mod id: {mod_id}")
        source_line = row.get("source_line")
        if isinstance(source_line, int):
            occurrence = (source_path, source_line)
            if occurrence in seen_mod_occurrences:
                raise ValueError(f"duplicate mod source occurrence: {source_path}:{source_line}")
            seen_mod_occurrences.add(occurrence)
        mod_rows[mod_id] = row
    return base_rows, mod_rows


def resolve_pool(
    item: ItemState,
    base_rows: dict[str, dict],
    mod_rows: dict[str, dict],
    side: str | None = None,
) -> tuple[PoolEntry, ...]:
    """Return ordered, positive ordinary-explicit candidates for an item state."""
    if any((item.corrupted, item.influenced, item.fractured, item.synthesised, item.mirrored, item.split)):
        raise NotImplementedError(_Q9_ERROR)
    if item.rarity not in _RARITY_CAPS:
        raise ValueError(f"invalid rarity: {item.rarity}")
    if side is not None and side not in _SIDES:
        raise ValueError(f"invalid side: {side}")
    if not isinstance(item.item_level, int):
        raise ValueError("item level must be an integer")
    base = _resolve_base(item.base_name, base_rows)
    tags = base.get("tags")
    if not isinstance(tags, dict):
        raise ValueError(f"malformed base row for {item.base_name}: tags must be an object")
    active_tags = {tag for tag, enabled in tags.items() if isinstance(tag, str) and enabled is True}
    _validate_existing_mods(item.mods, mod_rows)
    cap = _RARITY_CAPS[item.rarity]
    counts = {candidate_side: sum(mod.type == candidate_side for mod in item.mods) for candidate_side in _SIDES}
    excluded_groups = {mod.group for mod in item.mods}

    entries: list[PoolEntry] = []
    for mod_id, row in mod_rows.items():
        if not isinstance(row, dict):
            raise ValueError(f"malformed mod row: {mod_id}")
        source_path = row.get("source_path")
        if not isinstance(source_path, str):
            raise ValueError(f"malformed mod row source_path: {mod_id}")
        if not source_path.endswith("ModExplicit.lua"):
            continue
        validated = _validate_mod_row(mod_id, row)
        mod_type, group, level, keys, values, source_path = validated
        if level > item.item_level:
            continue
        if side is not None and mod_type != side:
            continue
        if counts[mod_type] >= cap or group in excluded_groups:
            continue
        weight = _first_matching_weight(keys, values, active_tags)
        if weight > 0:
            entries.append(PoolEntry(mod_id, mod_type, group, weight, level))
    return tuple(entries)


def pool_totals(item: ItemState, base_rows: dict[str, dict], mod_rows: dict[str, dict]) -> dict[str, int]:
    """Return independent prefix and suffix weight totals for the current state."""
    return {
        side: sum(entry.weight for entry in resolve_pool(item, base_rows, mod_rows, side))
        for side in ("Prefix", "Suffix")
    }


def _load_json_object(path: Path, kind: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load {kind} JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"malformed {kind} JSON document")
    return data


def _required_list(data: dict[str, Any], key: str, kind: str) -> list[Any]:
    rows = data.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"malformed {kind} JSON: {key} must be a list")
    return rows


def _resolve_base(name: str, base_rows: dict[str, dict]) -> dict:
    row = base_rows.get(name)
    if row is not None:
        return row
    same_name = {
        id(row): row
        for key, row in base_rows.items()
        if isinstance(row, dict) and row.get("name") == name and "@" in key
    }
    if same_name:
        raise ValueError(f"ambiguous base name: {name}")
    raise ValueError(f"unknown base: {name}")


def _validate_existing_mods(mods: tuple[ModRef, ...], mod_rows: dict[str, dict]) -> None:
    for mod in mods:
        if mod.id not in mod_rows:
            raise ValueError(f"unknown mod id: {mod.id}")
        if mod.type not in _SIDES:
            raise ValueError(f"invalid existing mod side: {mod.type}")
        if not isinstance(mod.group, str):
            raise ValueError(f"invalid existing mod group: {mod.id}")


def _validate_mod_row(mod_id: str, row: dict) -> tuple[str, str, int, list[Any], list[Any], str]:
    if not isinstance(row, dict):
        raise ValueError(f"malformed mod row: {mod_id}")
    mod_type, group, level = row.get("type"), row.get("group"), row.get("level")
    keys, values, source_path = row.get("weightKey"), row.get("weightVal"), row.get("source_path")
    if mod_type not in _SIDES or not isinstance(group, str) or not isinstance(level, int):
        raise ValueError(f"malformed mod row: {mod_id}")
    if not isinstance(keys, list) or not isinstance(values, list) or len(keys) != len(values):
        raise ValueError(f"malformed mod row weightKey/weightVal: {mod_id}")
    if not isinstance(source_path, str):
        raise ValueError(f"malformed mod row source_path: {mod_id}")
    if any(not isinstance(key, str) or not isinstance(value, int) for key, value in zip(keys, values)):
        raise ValueError(f"malformed mod row weights: {mod_id}")
    return mod_type, group, level, keys, values, source_path


def _first_matching_weight(keys: list[Any], values: list[Any], active_tags: set[str]) -> int:
    for key, value in zip(keys, values):
        if key in active_tags:
            return value
    return 0
