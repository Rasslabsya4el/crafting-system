"""Mechanically cross-check selected PoB modifier rows against frozen CoE and PoEDB snapshots.

The fixed correspondences below are supplied by the lead in
``docs/specs/2026-09-20-mod-crosscheck.md``.  This program only compares their
literal fields; it does not resolve canonical game group aliases or game rules.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = WORKTREE_ROOT / "docs/research/mod-crosscheck.md"
DATE_READ = "2026-09-20"
OUTPUT_HASH_TOKEN = "<OUTPUT-SHA256-CANONICALIZED>"


@dataclass(frozen=True)
class Selection:
    """One lead-selected correspondence family, in report order."""

    label: str
    class_name: str
    base_name: str
    pob_ids: tuple[str, ...]
    pob_group: str
    coe_modifier_id: str
    coe_base_id: str
    poedb_file: str
    family: str
    active_tags: frozenset[str]


SELECTIONS = (
    Selection(
        label="life",
        class_name="Helmet",
        base_name="Iron Hat",
        pob_ids=tuple(f"IncreasedLife{number}" for number in range(10)),
        pob_group="IncreasedLife",
        coe_modifier_id="1775",
        coe_base_id="52",
        poedb_file="Helmets_str.html",
        family="IncreasedLife",
        active_tags=frozenset({"armour", "default", "helmet", "str_armour"}),
    ),
    Selection(
        label="fire",
        class_name="Bow",
        base_name="Crude Bow",
        pob_ids=(
            *(f"LocalAddedFireDamageTwoHand{number}" for number in range(1, 8)),
            "LocalAddedFireDamageTwoHand8_",
            "LocalAddedFireDamageTwoHand9",
            "LocalAddedFireDamageTwoHand10",
        ),
        pob_group="LocalFireDamageTwoHand",
        coe_modifier_id="1972",
        coe_base_id="20",
        poedb_file="Bows.html",
        family="FireDamage",
        active_tags=frozenset(
            {"bow", "default", "ranged", "two_hand_weapon", "twohand", "weapon"}
        ),
    ),
    Selection(
        label="cold",
        class_name="Ring",
        base_name="Iron Ring",
        pob_ids=tuple(f"ColdResist{number}" for number in range(1, 9)),
        pob_group="ColdResistance",
        coe_modifier_id="684",
        coe_base_id="1",
        poedb_file="Rings.html",
        family="ColdResistance",
        active_tags=frozenset({"default", "ring"}),
    ),
    Selection(
        label="energy-shield",
        class_name="Body Armour",
        base_name="Simple Robe",
        pob_ids=tuple(f"LocalIncreasedEnergyShield{number}" for number in range(1, 12)),
        pob_group="LocalEnergyShield",
        coe_modifier_id="2007",
        coe_base_id="47",
        poedb_file="Body_Armours_int.html",
        family="BaseLocalDefences",
        active_tags=frozenset(
            {"armour", "body_armour", "default", "int_armour"}
        ),
    ),
    Selection(
        label="strength",
        class_name="Gloves",
        base_name="Iron Gauntlets",
        pob_ids=tuple(f"Strength{number}" for number in range(1, 10)),
        pob_group="Strength",
        coe_modifier_id="2336",
        coe_base_id="33",
        poedb_file="Gloves_str.html",
        family="Strength",
        active_tags=frozenset({"armour", "default", "gloves", "str_armour"}),
    ),
    Selection(
        label="chaos",
        class_name="Ring",
        base_name="Iron Ring",
        pob_ids=tuple(f"ChaosResist{number}" for number in range(1, 7)),
        pob_group="ChaosResistance",
        coe_modifier_id="661",
        coe_base_id="1",
        poedb_file="Rings.html",
        family="ChaosResistance",
        active_tags=frozenset({"default", "ring"}),
    ),
)


@dataclass(frozen=True)
class SourceValues:
    """Comparable literal fields from one source."""

    level: int
    weight: int
    ranges: tuple[tuple[int, int], ...]
    side: str
    group: tuple[str, ...]


@dataclass(frozen=True)
class MatchResult:
    """A unique source row, or an explicit missing/ambiguous observation."""

    value: Mapping[str, Any] | None
    index: int | None
    issue: str | None


@dataclass(frozen=True)
class ComparedRow:
    selection: Selection
    pob_id: str
    source_line: int
    coe_modifier_id: str
    coe_base_id: str
    poedb_file: str
    poedb_index: int | None
    poedb_name: str | None
    poedb_level: int | None
    pob: SourceValues
    coe: SourceValues | None
    poedb: SourceValues | None
    differing_fields: tuple[str, ...]
    observations: tuple[str, ...]


@dataclass(frozen=True)
class InputRecord:
    snapshot: str
    path: str
    sha256: str
    count: str


@dataclass(frozen=True)
class ReportData:
    inputs: tuple[InputRecord, ...]
    rows: tuple[ComparedRow, ...]
    class_counts: tuple[tuple[str, int], ...]
    selected_count: int
    unique_count: int
    pob_version: str
    poe_version: str
    pob_version_authority: str


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html(value: str) -> str:
    """Return visible PoEDB text without relying on a browser or JS execution."""

    parser = _TextCollector()
    parser.feed(value)
    parser.close()
    return " ".join("".join(parser.parts).split())


def parse_coe_assignment(source: str) -> Mapping[str, Any]:
    """Parse exactly the frozen ``poecd=<JSON>[;]`` wrapper."""

    prefix = "poecd="
    if not source.startswith(prefix):
        raise ValueError("CoE source must start with 'poecd='")
    payload = source[len(prefix) :].strip()
    if payload.endswith(";"):
        payload = payload[:-1].rstrip()
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError("invalid JSON after CoE poecd assignment") from error
    if not isinstance(decoded, dict):
        raise ValueError("CoE assignment must contain a JSON object")
    return decoded


def parse_poedb_mods_view(source: str) -> Mapping[str, Any]:
    """Parse the one JSON literal passed to ``new ModsView(...)`` in frozen HTML."""

    marker = "new ModsView("
    if source.count(marker) != 1:
        raise ValueError("PoEDB HTML must contain exactly one 'new ModsView(' marker")
    start = source.index(marker) + len(marker)
    try:
        decoded, consumed = json.JSONDecoder().raw_decode(source[start:])
    except json.JSONDecodeError as error:
        raise ValueError("PoEDB ModsView payload is not JSON") from error
    if not isinstance(decoded, dict):
        raise ValueError("PoEDB ModsView payload must be a JSON object")
    if not source[start + consumed :].lstrip().startswith(");"):
        raise ValueError("PoEDB ModsView JSON must be followed by ');'")
    normal = decoded.get("normal")
    if not isinstance(normal, list):
        raise ValueError("PoEDB ModsView payload has no normal-row list")
    return decoded


def _parse_positive_ranges(value: str, dash: str, source_name: str) -> tuple[tuple[int, int], ...]:
    pattern = re.compile(rf"\(([1-9][0-9]*){re.escape(dash)}([1-9][0-9]*)\)")
    matches = list(pattern.finditer(value))
    if not matches:
        raise ValueError(f"{source_name} has no positive integer {dash!r} ranges: {value!r}")
    if value.count("(") != len(matches) or value.count(")") != len(matches):
        raise ValueError(f"{source_name} contains an unsupported parenthesized value: {value!r}")
    ranges = tuple((int(match.group(1)), int(match.group(2))) for match in matches)
    if any(low > high for low, high in ranges):
        raise ValueError(f"{source_name} range lower bound exceeds upper bound: {value!r}")
    return ranges


def parse_pob_ranges(value: str) -> tuple[tuple[int, int], ...]:
    """Parse the selected PoB raw stat syntax, ``(a-b)`` only."""

    return _parse_positive_ranges(value, "-", "PoB stat")


def parse_poedb_ranges(value: str) -> tuple[tuple[int, int], ...]:
    """Parse the selected visible PoEDB stat syntax, ``(a-b)`` with an em dash."""

    return _parse_positive_ranges(value, "—", "PoEDB stat")


def parse_coe_ranges(value: object) -> tuple[tuple[int, int], ...]:
    """Decode CoE's ``nvalues`` JSON and require lists of positive integer pairs."""

    if not isinstance(value, str):
        raise ValueError("CoE nvalues must be a JSON string")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("CoE nvalues is invalid JSON") from error
    if not isinstance(decoded, list) or not decoded:
        raise ValueError("CoE nvalues must be a non-empty list")
    ranges: list[tuple[int, int]] = []
    for pair in decoded:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or any(type(number) is not int for number in pair)
        ):
            raise ValueError("CoE nvalues must contain two-integer lists")
        low, high = pair
        if low <= 0 or high <= 0 or low > high:
            raise ValueError("CoE nvalues contains an invalid positive range")
        ranges.append((low, high))
    return tuple(ranges)


_RAW_ROW = re.compile(
    r'^\s*\["(?P<id>[^"]+)"\]\s*=\s*\{(?P<body>.*)\}\s*,?\s*$'
)
_AFFIX_THEN_STAT = re.compile(
    r'\baffix\s*=\s*"(?P<affix>[^"\\]*)"\s*,\s*"(?P<stat>[^"\\]*)"'
)


def read_pob_raw_stat(raw_line: str, expected_id: str) -> tuple[str, str]:
    """Verify an S24 row ID and read its first unnamed stat string after ``affix``."""

    row = _RAW_ROW.fullmatch(raw_line)
    if row is None:
        raise ValueError("PoB source_line does not contain one supported modifier row")
    if row.group("id") != expected_id:
        raise ValueError(
            f"PoB source_line ID {row.group('id')!r} does not match {expected_id!r}"
        )
    match = _AFFIX_THEN_STAT.search(row.group("body"))
    if match is None:
        raise ValueError("PoB row lacks an unnamed quoted stat immediately after affix")
    return match.group("affix"), match.group("stat")


def resolve_pob_spawn_weight(
    weight_keys: Sequence[object], weight_values: Sequence[object], active_tags: Iterable[str]
) -> int:
    """Return the first active tag's raw PoB weight, including an explicit zero."""

    if len(weight_keys) != len(weight_values):
        raise ValueError("PoB weightKey and weightVal lengths differ")
    active = set(active_tags)
    for key, value in zip(weight_keys, weight_values, strict=True):
        if not isinstance(key, str) or type(value) is not int:
            raise ValueError("PoB spawn weight entries must be string/integer pairs")
        if key in active:
            return value
    raise ValueError("no PoB spawn-weight tag matches the active base tags")


def unique_match(
    rows: Sequence[Mapping[str, Any]], name: str, level: int, label: str
) -> MatchResult:
    """Find the one PoEDB normal row selected by the spec's Name plus Level rule."""

    matches = [
        (index, row)
        for index, row in enumerate(rows)
        if row.get("Name") == name and str(row.get("Level")) == str(level)
    ]
    if len(matches) == 1:
        index, row = matches[0]
        return MatchResult(row, index, None)
    if not matches:
        return MatchResult(None, None, f"missing {label} Name/Level match")
    return MatchResult(None, None, f"ambiguous {label} Name/Level match ({len(matches)} rows)")


def unique_tier_match(
    rows: Sequence[Mapping[str, Any]], level: int, label: str
) -> MatchResult:
    """Find the one CoE tier on the selected base and item level."""

    matches = [
        (index, row)
        for index, row in enumerate(rows)
        if str(row.get("ilvl")) == str(level)
    ]
    if len(matches) == 1:
        index, row = matches[0]
        return MatchResult(row, index, None)
    if not matches:
        return MatchResult(None, None, f"missing {label} ilvl match")
    return MatchResult(None, None, f"ambiguous {label} ilvl match ({len(matches)} rows)")


def coe_side(value: object) -> str:
    if value == "prefix":
        return "Prefix"
    if value == "suffix":
        return "Suffix"
    raise ValueError(f"unsupported CoE affix side: {value!r}")


def poedb_side(value: object) -> str:
    if str(value) == "1":
        return "Prefix"
    if str(value) == "2":
        return "Suffix"
    raise ValueError(f"unsupported PoEDB ModGenerationTypeID: {value!r}")


def _required_int(row: Mapping[str, Any], field: str, source_name: str) -> int:
    value = row.get(field)
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    raise ValueError(f"{source_name} {field} must be an integer")


def _required_str(row: Mapping[str, Any], field: str, source_name: str) -> str:
    value = row.get(field)
    if not isinstance(value, str):
        raise ValueError(f"{source_name} {field} must be a string")
    return value


def _required_string_list(row: Mapping[str, Any], field: str, source_name: str) -> tuple[str, ...]:
    value = row.get(field)
    if not isinstance(value, list) or not value or not all(isinstance(entry, str) for entry in value):
        raise ValueError(f"{source_name} {field} must be a non-empty string list")
    return tuple(value)


def differing_fields(
    pob: SourceValues, coe: SourceValues, poedb: SourceValues
) -> tuple[str, ...]:
    """Name exactly the literal field families whose three source values differ."""

    fields: list[str] = []
    for field in ("level", "weight", "ranges", "side", "group"):
        values = (getattr(pob, field), getattr(coe, field), getattr(poedb, field))
        if values[0] != values[1] or values[1] != values[2]:
            fields.append("range" if field == "ranges" else field)
    return tuple(fields)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {path.as_posix()}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path.as_posix()}")
    return value


def _selected_ids() -> tuple[str, ...]:
    return tuple(identifier for selection in SELECTIONS for identifier in selection.pob_ids)


def _class_counts() -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    order: list[str] = []
    for selection in SELECTIONS:
        if selection.class_name not in counts:
            counts[selection.class_name] = 0
            order.append(selection.class_name)
        counts[selection.class_name] += len(selection.pob_ids)
    return tuple((name, counts[name]) for name in order)


def _load_poedb_snapshots(root: Path) -> tuple[dict[str, Mapping[str, Any]], list[InputRecord]]:
    snapshots: dict[str, Mapping[str, Any]] = {}
    input_records: list[InputRecord] = []
    labels = {
        "Helmets_str.html": "S28",
        "Bows.html": "S29",
        "Rings.html": "S30",
        "Body_Armours_int.html": "S31",
        "Gloves_str.html": "S32",
    }
    for filename in labels:
        path = root / "sources/raw/poedb" / filename
        snapshot = parse_poedb_mods_view(path.read_text(encoding="utf-8"))
        normal = snapshot["normal"]
        assert isinstance(normal, list)  # enforced by parse_poedb_mods_view
        snapshots[filename] = snapshot
        input_records.append(
            InputRecord(
                labels[filename],
                f"sources/raw/poedb/{filename}",
                _sha256(path),
                f"{len(normal)} normal rows",
            )
        )
    return snapshots, input_records


def build_report_data(root: Path = WORKTREE_ROOT) -> ReportData:
    """Read every frozen input and form one report row per selected PoB modifier."""

    projection_path = root / "data/pob_mod_explicit.json"
    raw_pob_path = root / "sources/pob/Data/ModExplicit.lua"
    coe_path = root / "sources/raw/coe/poec_data.json"

    projection = _load_json(projection_path)
    projection_mods = projection.get("mods")
    if not isinstance(projection_mods, list):
        raise ValueError("PoB projection lacks a mods list")
    projection_source = projection.get("source")
    if not isinstance(projection_source, dict):
        raise ValueError("PoB projection lacks source metadata")
    pob_version = _required_str(projection_source, "pob_version", "PoB projection source")
    poe_version = _required_str(projection_source, "poe_version", "PoB projection source")
    pob_version_authority = _required_str(
        projection_source, "version_authority", "PoB projection source"
    )
    pob_by_id: dict[str, Mapping[str, Any]] = {}
    for mod in projection_mods:
        if not isinstance(mod, dict) or not isinstance(mod.get("id"), str):
            raise ValueError("PoB projection has a malformed mod record")
        identifier = mod["id"]
        if identifier in pob_by_id:
            raise ValueError(f"PoB projection has duplicate ID {identifier!r}")
        pob_by_id[identifier] = mod

    selected_ids = _selected_ids()
    if len(selected_ids) != 54 or len(set(selected_ids)) != 54:
        raise ValueError("fixed selection must contain exactly 54 distinct PoB IDs")
    missing_pob_ids = sorted(set(selected_ids) - set(pob_by_id))
    if missing_pob_ids:
        raise ValueError(f"selected PoB IDs missing from projection: {missing_pob_ids!r}")

    raw_pob_lines = raw_pob_path.read_text(encoding="utf-8").splitlines()
    coe = parse_coe_assignment(coe_path.read_text(encoding="utf-8"))
    modifiers = coe.get("modifiers")
    tiers = coe.get("tiers")
    if not isinstance(modifiers, dict) or not isinstance(modifiers.get("seq"), list):
        raise ValueError("CoE source lacks modifiers.seq")
    if not isinstance(tiers, dict):
        raise ValueError("CoE source lacks tiers object")
    modifier_rows = modifiers["seq"]
    if not all(isinstance(row, dict) for row in modifier_rows):
        raise ValueError("CoE modifiers.seq contains a malformed row")

    poedb, poedb_inputs = _load_poedb_snapshots(root)
    coe_by_id: dict[str, list[Mapping[str, Any]]] = {}
    for modifier in modifier_rows:
        identifier = modifier.get("id_modifier")
        if isinstance(identifier, str):
            coe_by_id.setdefault(identifier, []).append(modifier)

    compared: list[ComparedRow] = []
    for selection in SELECTIONS:
        matching_modifiers = coe_by_id.get(selection.coe_modifier_id, [])
        if len(matching_modifiers) != 1:
            raise ValueError(
                f"CoE modifier ID {selection.coe_modifier_id} is not unique and present"
            )
        coe_modifier = matching_modifiers[0]
        coe_group = _required_str(coe_modifier, "modgroup", "CoE modifier")
        coe_affix = _required_str(coe_modifier, "affix", "CoE modifier")
        tier_by_base = tiers.get(selection.coe_modifier_id)
        if not isinstance(tier_by_base, dict):
            raise ValueError(f"CoE has no tiers for modifier {selection.coe_modifier_id}")
        coe_base_tiers = tier_by_base.get(selection.coe_base_id)
        if not isinstance(coe_base_tiers, list) or not all(
            isinstance(row, dict) for row in coe_base_tiers
        ):
            raise ValueError(
                f"CoE has no valid tiers for modifier/base "
                f"{selection.coe_modifier_id}/{selection.coe_base_id}"
            )
        poedb_normal = poedb[selection.poedb_file]["normal"]
        assert isinstance(poedb_normal, list)

        for identifier in selection.pob_ids:
            pob_record = pob_by_id[identifier]
            source_line = _required_int(pob_record, "source_line", "PoB projection")
            if not 1 <= source_line <= len(raw_pob_lines):
                raise ValueError(f"PoB source_line for {identifier} is outside ModExplicit.lua")
            raw_affix, raw_stat = read_pob_raw_stat(raw_pob_lines[source_line - 1], identifier)
            projected_affix = _required_str(pob_record, "affix", "PoB projection")
            if raw_affix != projected_affix:
                raise ValueError(
                    f"PoB projection affix differs from raw source for {identifier}: "
                    f"{projected_affix!r} != {raw_affix!r}"
                )

            pob_level = _required_int(pob_record, "level", "PoB projection")
            pob_group = _required_str(pob_record, "group", "PoB projection")
            pob_type = _required_str(pob_record, "type", "PoB projection")
            weight_keys = pob_record.get("weightKey")
            weight_values = pob_record.get("weightVal")
            if not isinstance(weight_keys, list) or not isinstance(weight_values, list):
                raise ValueError(f"PoB projection weights malformed for {identifier}")
            pob = SourceValues(
                level=pob_level,
                weight=resolve_pob_spawn_weight(
                    weight_keys, weight_values, selection.active_tags
                ),
                ranges=parse_pob_ranges(raw_stat),
                side=pob_type,
                group=(pob_group,),
            )

            coe_match = unique_tier_match(
                coe_base_tiers, pob_level, f"CoE {selection.coe_modifier_id}/{selection.coe_base_id}"
            )
            poedb_match = unique_match(
                poedb_normal, projected_affix, pob_level, f"PoEDB {selection.poedb_file}"
            )
            observations: list[str] = []
            if pob_group != selection.pob_group:
                observations.append(
                    f"PoB group {pob_group!r} differs from selected family {selection.pob_group!r}"
                )
            if coe_group != selection.family:
                observations.append(
                    f"CoE group {coe_group!r} differs from selected family {selection.family!r}"
                )

            coe_values: SourceValues | None = None
            if coe_match.value is None:
                assert coe_match.issue is not None
                observations.append(coe_match.issue)
            else:
                coe_tier = coe_match.value
                coe_values = SourceValues(
                    level=_required_int(coe_tier, "ilvl", "CoE tier"),
                    weight=_required_int(coe_tier, "weighting", "CoE tier"),
                    ranges=parse_coe_ranges(coe_tier.get("nvalues")),
                    side=coe_side(coe_affix),
                    group=(coe_group,),
                )

            poedb_values: SourceValues | None = None
            poedb_index: int | None = None
            poedb_name: str | None = None
            poedb_level: int | None = None
            if poedb_match.value is None:
                assert poedb_match.issue is not None
                observations.append(poedb_match.issue)
            else:
                poedb_row = poedb_match.value
                poedb_index = poedb_match.index
                poedb_name = _required_str(poedb_row, "Name", "PoEDB normal row")
                poedb_level = _required_int(poedb_row, "Level", "PoEDB normal row")
                poedb_groups = _required_string_list(
                    poedb_row, "ModFamilyList", "PoEDB normal row"
                )
                if poedb_groups != (selection.family,):
                    observations.append(
                        f"PoEDB family {poedb_groups!r} differs from selected family "
                        f"{selection.family!r}"
                    )
                poedb_values = SourceValues(
                    level=poedb_level,
                    weight=_required_int(poedb_row, "DropChance", "PoEDB normal row"),
                    ranges=parse_poedb_ranges(
                        strip_html(_required_str(poedb_row, "str", "PoEDB normal row"))
                    ),
                    side=poedb_side(poedb_row.get("ModGenerationTypeID")),
                    group=poedb_groups,
                )

            if coe_values is not None and poedb_values is not None:
                fields = list(differing_fields(pob, coe_values, poedb_values))
            else:
                fields = []
                if coe_values is None:
                    fields.append("coe-tier-match")
                if poedb_values is None:
                    fields.append("poedb-normal-match")
            if any("selected family" in observation for observation in observations):
                fields.append("family")
            compared.append(
                ComparedRow(
                    selection=selection,
                    pob_id=identifier,
                    source_line=source_line,
                    coe_modifier_id=selection.coe_modifier_id,
                    coe_base_id=selection.coe_base_id,
                    poedb_file=selection.poedb_file,
                    poedb_index=poedb_index,
                    poedb_name=poedb_name,
                    poedb_level=poedb_level,
                    pob=pob,
                    coe=coe_values,
                    poedb=poedb_values,
                    differing_fields=tuple(fields),
                    observations=tuple(observations),
                )
            )

    if len(compared) != 54:
        raise ValueError(f"expected 54 selected rows, found {len(compared)}")

    input_records = [
        InputRecord(
            "S24",
            "sources/pob/Data/ModExplicit.lua",
            _sha256(raw_pob_path),
            f"{len(raw_pob_lines)} source lines",
        ),
        InputRecord(
            "S24",
            "data/pob_mod_explicit.json",
            _sha256(projection_path),
            f"{len(projection_mods)} projected mod records",
        ),
        InputRecord(
            "S4",
            "sources/raw/coe/poec_data.json",
            _sha256(coe_path),
            f"{len(modifier_rows)} modifier rows; {len(tiers)} tier modifier IDs",
        ),
    ]
    for base_filename in ("helmet.lua", "bow.lua", "ring.lua", "body.lua", "gloves.lua"):
        base_path = root / "sources/pob/Data/Bases" / base_filename
        input_records.append(
            InputRecord(
                "S27",
                f"sources/pob/Data/Bases/{base_filename}",
                _sha256(base_path),
                "provenance pointer; active tags remain fixed by the lead-supplied selection",
            )
        )
    input_records.extend(poedb_inputs)
    return ReportData(
        inputs=tuple(input_records),
        rows=tuple(compared),
        class_counts=_class_counts(),
        selected_count=len(selected_ids),
        unique_count=len(set(selected_ids)),
        pob_version=pob_version,
        poe_version=poe_version,
        pob_version_authority=pob_version_authority,
    )


def _format_ranges(value: tuple[tuple[int, int], ...] | None) -> str:
    if value is None:
        return "MISSING"
    return json.dumps(value, separators=(",", ":"))


def _format_source_value(value: int | None) -> str:
    return "MISSING" if value is None else str(value)


def _format_group(value: tuple[str, ...] | None) -> str:
    return "MISSING" if value is None else json.dumps(value, separators=(",", ":"))


def _format_side(value: SourceValues | None, native: str | None = None) -> str:
    if value is None:
        return "MISSING"
    if native is None:
        return value.side
    return f"{native} ({value.side})"


def _markdown_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _all_equal(row: ComparedRow, field: str) -> bool:
    if row.coe is None or row.poedb is None:
        return False
    values = (getattr(row.pob, field), getattr(row.coe, field), getattr(row.poedb, field))
    return values[0] == values[1] == values[2]


def group_comparison_counts(rows: Iterable[ComparedRow]) -> tuple[int, int, int]:
    """Return equal, unequal, and uncomparable native-group triple counts."""

    equal = 0
    unequal = 0
    uncomparable = 0
    for row in rows:
        if row.coe is None or row.poedb is None:
            uncomparable += 1
        elif _all_equal(row, "group"):
            equal += 1
        else:
            unequal += 1
    return equal, unequal, uncomparable


def canonical_output_hash(report: str) -> str:
    """Hash report bytes after replacing its self-reference with the fixed marker."""

    match = re.search(r"(?m)^\| output SHA-256 \| `([0-9a-f]{64})` \|$", report)
    if match is None:
        raise ValueError("report lacks its output SHA-256 row")
    normalized = report[: match.start(1)] + OUTPUT_HASH_TOKEN + report[match.end(1) :]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def render_report(data: ReportData) -> str:
    """Render the deterministic UTF-8/LF Markdown report without filesystem writes."""

    level_matches = sum(_all_equal(row, "level") for row in data.rows)
    weight_matches = sum(_all_equal(row, "weight") for row in data.rows)
    range_matches = sum(_all_equal(row, "ranges") for row in data.rows)
    side_matches = sum(_all_equal(row, "side") for row in data.rows)
    group_matches, group_differences, uncomparable_rows = group_comparison_counts(data.rows)
    coe_tier_matches = sum(row.coe is not None for row in data.rows)
    poedb_matches = sum(row.poedb is not None for row in data.rows)
    discrepancies = [row for row in data.rows if row.differing_fields or row.observations]

    lines = [
        "# Frozen 54-mod cross-check",
        "",
        "Mechanical comparison of the lead-selected correspondences from "
        "`docs/specs/2026-09-20-mod-crosscheck.md`. It preserves source-native "
        "group labels and records observations only; it does not select a canonical alias.",
        "",
        "| field | value |",
        "| --- | --- |",
        f"| date read | {DATE_READ} |",
        f"| PoB version metadata (S24) | PoB {data.pob_version} / PoE {data.poe_version}; "
        f"{data.pob_version_authority} |",
        "| source IDs | S4 = CoE snapshot; S27 = PoB base-tag sources; S28-S32 = PoEDB snapshots |",
        f"| selected PoB IDs | {data.selected_count} |",
        f"| unique PoB IDs | {data.unique_count} |",
        f"| emitted comparison rows | {len(data.rows)} |",
        f"| CoE unique ilvl matches | {coe_tier_matches} |",
        f"| PoEDB unique normal Name/Level matches | {poedb_matches} |",
        f"| level agreements | {level_matches} |",
        f"| weight agreements | {weight_matches} |",
        f"| range agreements | {range_matches} |",
        f"| side agreements | {side_matches} |",
        f"| group agreements (fully comparable triples) | {group_matches} |",
        f"| group-label differences (fully comparable triples) | {group_differences} |",
        f"| uncomparable source rows | {uncomparable_rows} |",
        "| deterministic two-run equality | true; CLI re-renders after re-reading all inputs before write |",
        "| output SHA-256 | `" + OUTPUT_HASH_TOKEN + "` |",
        "",
        "The output hash is SHA-256 of this UTF-8/LF report after replacing the value in "
        "its self-reference row with `<OUTPUT-SHA256-CANONICALIZED>`.",
        "",
        "## Source snapshots",
        "",
        "| snapshot | path | SHA-256 | source count / role |",
        "| --- | --- | --- | --- |",
    ]
    for record in data.inputs:
        lines.append(
            "| "
            + " | ".join(
                (
                    record.snapshot,
                    f"`{record.path}`",
                    f"`{record.sha256}`",
                    _markdown_cell(record.count),
                )
            )
            + " |"
        )

    lines.extend(("", "## Per-class counts", "", "| class | selected rows |", "| --- | --- |"))
    for class_name, count in data.class_counts:
        lines.append(f"| {class_name} | {count} |")

    lines.extend(
        (
            "",
            "## Row comparison",
            "",
            "PoB raw ranges come from the first unnamed quoted stat after `affix = ...` at "
            "the recorded S24 source line. CoE ranges are `nvalues`; PoEDB ranges are visible "
            "text after HTML parsing. CoE exact modifier/base IDs and PoEDB normal-row pointers "
            "are included for every row.",
            "",
            "| class / base | PoB ID + source line | CoE modifier / base | PoEDB normal row | "
            "level PoB / CoE / PoEDB | weight PoB / CoE / PoEDB | range PoB / CoE / PoEDB | "
            "affix side PoB / CoE / PoEDB | source-native group PoB / CoE / PoEDB | differing fields |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        )
    )
    for row in data.rows:
        coe = row.coe
        poedb = row.poedb
        poedb_pointer = "MISSING"
        if row.poedb_index is not None:
            poedb_pointer = (
                f"`{row.poedb_file}` normal[{row.poedb_index}] "
                f"{row.poedb_name!r} / {row.poedb_level}"
            )
        coe_native = "MISSING" if coe is None else coe.side.lower()
        poedb_native = "MISSING" if poedb is None else (
            "1" if poedb.side == "Prefix" else "2"
        )
        observations = list(row.differing_fields) + list(row.observations)
        cells = (
            f"{row.selection.class_name} / {row.selection.base_name}",
            f"`{row.pob_id}` / `ModExplicit.lua:{row.source_line}`",
            f"`{row.coe_modifier_id}` / `{row.coe_base_id}`",
            poedb_pointer,
            " / ".join(
                (
                    str(row.pob.level),
                    _format_source_value(None if coe is None else coe.level),
                    _format_source_value(None if poedb is None else poedb.level),
                )
            ),
            " / ".join(
                (
                    str(row.pob.weight),
                    _format_source_value(None if coe is None else coe.weight),
                    _format_source_value(None if poedb is None else poedb.weight),
                )
            ),
            " / ".join(
                (_format_ranges(row.pob.ranges), _format_ranges(None if coe is None else coe.ranges), _format_ranges(None if poedb is None else poedb.ranges))
            ),
            " / ".join(
                (
                    _format_side(row.pob),
                    _format_side(coe, coe_native),
                    _format_side(poedb, poedb_native),
                )
            ),
            " / ".join(
                (_format_group(row.pob.group), _format_group(None if coe is None else coe.group), _format_group(None if poedb is None else poedb.group))
            ),
            "; ".join(observations) if observations else "none",
        )
        lines.append("| " + " | ".join(_markdown_cell(cell) for cell in cells) + " |")

    lines.extend(
        (
            "",
            "## Discrepant rows",
            "",
            "| PoB ID | differing fields | source-native group triplet | observations |",
            "| --- | --- | --- | --- |",
        )
    )
    if discrepancies:
        for row in discrepancies:
            fields = ", ".join(row.differing_fields) or "none"
            groups = " / ".join(
                (
                    _format_group(row.pob.group),
                    _format_group(None if row.coe is None else row.coe.group),
                    _format_group(None if row.poedb is None else row.poedb.group),
                )
            )
            notes = "; ".join(row.observations) if row.observations else "none"
            lines.append(
                "| "
                + " | ".join(
                    _markdown_cell(value) for value in (row.pob_id, fields, groups, notes)
                )
                + " |"
            )
    else:
        lines.append("| none | none | none | none |")

    template = "\n".join(lines) + "\n"
    digest = hashlib.sha256(template.encode("utf-8")).hexdigest()
    return template.replace(OUTPUT_HASH_TOKEN, digest, 1)


def write_report(report: str, path: Path = REPORT_PATH) -> str:
    """Atomically replace the report only after its complete bytes have been prepared."""

    if not report.endswith("\n") or "\r" in report:
        raise ValueError("report must use deterministic LF line endings")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(report, encoding="utf-8", newline="\n")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return hashlib.sha256(report.encode("utf-8")).hexdigest()


def build() -> tuple[Path, str]:
    """Build the report using paths anchored to this script's own worktree."""

    report = render_report(build_report_data(WORKTREE_ROOT))
    if report != render_report(build_report_data(WORKTREE_ROOT)):
        raise ValueError("two fresh frozen-input report renders differ")
    return REPORT_PATH, write_report(report, REPORT_PATH)


def main() -> int:
    path, digest = build()
    print(f"{path.relative_to(WORKTREE_ROOT).as_posix()} SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
