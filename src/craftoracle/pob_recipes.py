"""Literal projections of PoB bench and essence generated tables.

Only the fixed table forms used by ``ModMaster.lua`` and ``Essence.lua`` are
accepted.  This module reads no Lua code and executes nothing: a projected
field must be a literal of the expected kind.  It deliberately does not infer
crafting costs, eligibility, weights, or action behavior.

Sources: PoB data ``Data/ModMaster.lua`` (S11) and ``Data/Essence.lua`` (S22),
owner-supplied snapshot read 2026-09-20.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping

from craftoracle.pob_bases import (
    _IDENTIFIER,
    _only_space_or_comments,
    _read_balanced_braces,
    _read_map_key,
    _read_string,
    _skip_space_and_comments,
    _split_top_level,
)


BENCH_SOURCE_PATH = "sources/pob/Data/ModMaster.lua"
ESSENCE_SOURCE_PATH = "sources/pob/Data/Essence.lua"
POB_VERSION = "2.67.2"
POE_VERSION = "3.29"
VERSION_AUTHORITY = (
    "AGENTS.md section 1 (owner-supplied snapshot; upstream unverified, Q8)"
)

BENCH_PROJECTION_FIELDS = (
    "source_index",
    "source_path",
    "source_line",
    "type",
    "affix",
    "level",
    "group",
    "modTags",
    "statOrder",
    "stat_text",
    "types",
)
ESSENCE_PROJECTION_FIELDS = (
    "id",
    "name",
    "type",
    "tier",
    "mods",
    "source_path",
    "source_line",
)

_INTEGER = re.compile(r"[+-]?[0-9]+")
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)")
_RETURN = re.compile(r"return\b")


def _line_number(source_text: str, index: int) -> int:
    return source_text.count("\n", 0, index) + 1


def _error(path: str, source_text: str, index: int, message: str) -> ValueError:
    return ValueError(f"{path}: line {_line_number(source_text, index)}: {message}")


def _line_error(path: str, line: int, message: str) -> ValueError:
    return ValueError(f"{path}: line {line}: {message}")


def _extract_return_table(source_text: str, path: str) -> tuple[int, int]:
    """Return the bounds inside the one literal ``return { ... }`` wrapper."""
    if not isinstance(source_text, str):
        raise ValueError(f"{path}: line 1: source text must be a string")

    index = _skip_space_and_comments(source_text)
    match = _RETURN.match(source_text, index)
    if match is None:
        raise _error(path, source_text, index, "expected return { wrapper")
    index = _skip_space_and_comments(source_text, match.end())
    if index >= len(source_text) or source_text[index] != "{":
        raise _error(path, source_text, index, "expected return { wrapper")

    opening = index
    try:
        after_closing = _read_balanced_braces(source_text, opening)
    except ValueError as error:
        if str(error) == "unclosed record":
            raise _line_error(
                path,
                max(1, len(source_text.splitlines())),
                "missing closing return table",
            ) from error
        raise _error(path, source_text, opening, str(error)) from error

    if not _only_space_or_comments(source_text, after_closing):
        raise _error(
            path,
            source_text,
            after_closing,
            "unexpected content after return table",
        )
    return opening + 1, after_closing - 1


def _parse_string(value: str, field: str) -> str:
    index = _skip_space_and_comments(value)
    try:
        parsed, index = _read_string(value, index, strict=True)
    except ValueError as error:
        raise ValueError(f"{field} must be a quoted string: {error}") from error
    if not _only_space_or_comments(value, index):
        raise ValueError(f"malformed {field}")
    return parsed


def _parse_integer(value: str, field: str) -> int:
    index = _skip_space_and_comments(value)
    match = _INTEGER.match(value, index)
    if match is None or not _only_space_or_comments(value, match.end()):
        raise ValueError(f"{field} must be an integer")
    return int(match.group(), 10)


def _parse_number(value: str, field: str) -> int | float:
    """Read the integer-or-decimal literal form used by PoB ``statOrder``."""
    index = _skip_space_and_comments(value)
    match = _NUMBER.match(value, index)
    if match is None or not _only_space_or_comments(value, match.end()):
        raise ValueError(f"{field} must be a numeric literal")
    literal = match.group()
    return float(literal) if "." in literal else int(literal, 10)


def _parse_table(value: str, field: str) -> str:
    index = _skip_space_and_comments(value)
    if index >= len(value) or value[index] != "{":
        raise ValueError(f"{field} must be a table")
    try:
        end = _read_balanced_braces(value, index)
    except ValueError as error:
        raise ValueError(f"malformed {field}: {error}") from error
    if not _only_space_or_comments(value, end):
        raise ValueError(f"malformed {field}")
    return value[index + 1:end - 1]


def _parts(inner: str, field: str) -> list[str]:
    try:
        return _split_top_level(inner)
    except ValueError as error:
        raise ValueError(f"malformed {field}: {error}") from error


def _parse_string_array(value: str, field: str) -> list[str]:
    result: list[str] = []
    parts = _parts(_parse_table(value, field), field)
    for part_number, part in enumerate(parts):
        index = _skip_space_and_comments(part)
        if index == len(part):
            if part_number == len(parts) - 1:
                continue
            raise ValueError(f"empty {field} array entry")
        result.append(_parse_string(part, field))
    return result


def _parse_number_array(value: str, field: str) -> list[int | float]:
    result: list[int | float] = []
    parts = _parts(_parse_table(value, field), field)
    for part_number, part in enumerate(parts):
        index = _skip_space_and_comments(part)
        if index == len(part):
            if part_number == len(parts) - 1:
                continue
            raise ValueError(f"empty {field} array entry")
        result.append(_parse_number(part, field))
    return result


def _parse_string_map(value: str, field: str) -> dict[str, str]:
    result: dict[str, str] = {}
    parts = _parts(_parse_table(value, field), field)
    for part_number, part in enumerate(parts):
        index = _skip_space_and_comments(part)
        if index == len(part):
            if part_number == len(parts) - 1:
                continue
            raise ValueError(f"empty {field} map entry")
        try:
            key, index = _read_map_key(part, index)
        except ValueError as error:
            raise ValueError(f"malformed {field} map key: {error}") from error
        index = _skip_space_and_comments(part, index)
        if index >= len(part) or part[index] != "=":
            raise ValueError(f"malformed {field} map entry")
        if key in result:
            raise ValueError(f"duplicate map key {key!r} in {field}")
        result[key] = _parse_string(part[index + 1:], field)
    return result


def _parse_boolean_map(value: str, field: str) -> dict[str, bool]:
    result: dict[str, bool] = {}
    parts = _parts(_parse_table(value, field), field)
    for part_number, part in enumerate(parts):
        index = _skip_space_and_comments(part)
        if index == len(part):
            if part_number == len(parts) - 1:
                continue
            raise ValueError(f"empty {field} map entry")
        try:
            key, index = _read_map_key(part, index)
        except ValueError as error:
            raise ValueError(f"malformed {field} map key: {error}") from error
        index = _skip_space_and_comments(part, index)
        if index >= len(part) or part[index] != "=":
            raise ValueError(f"malformed {field} map entry")
        index = _skip_space_and_comments(part, index + 1)
        match = _IDENTIFIER.match(part, index)
        if match is None or match.group() not in {"true", "false"}:
            raise ValueError(f"{field} values must be booleans")
        if not _only_space_or_comments(part, match.end()):
            raise ValueError(f"malformed {field} map entry")
        if key in result:
            raise ValueError(f"duplicate map key {key!r} in {field}")
        result[key] = match.group() == "true"
    return result


def _record_parts(record_text: str, field_name: str) -> list[str]:
    if not record_text.startswith("{") or not record_text.endswith("}"):
        raise ValueError("row must be a literal table")
    return _parts(record_text[1:-1], field_name)


def _parse_named_fields(record_text: str, field_name: str) -> tuple[dict[str, str], list[str]]:
    """Separate named fields and top-level unnamed quoted strings.

    Unknown named fields are structurally bounded but deliberately omitted from
    the projection.  They cannot be mistaken for the anonymous bench stat
    strings because only a whole, top-level quoted member enters ``stat_text``.
    """
    fields: dict[str, str] = {}
    anonymous_strings: list[str] = []
    parts = _record_parts(record_text, field_name)
    for part_number, part in enumerate(parts):
        index = _skip_space_and_comments(part)
        if index == len(part):
            if part_number == len(parts) - 1:
                continue
            raise ValueError("empty row entry")
        if part[index] in "\"'":
            anonymous_strings.append(_parse_string(part, "stat_text"))
            continue
        match = _IDENTIFIER.match(part, index)
        if match is None:
            raise ValueError("unsupported row expression")
        name = match.group()
        index = _skip_space_and_comments(part, match.end())
        if index >= len(part) or part[index] != "=":
            raise ValueError("unsupported row expression")
        if name in fields:
            raise ValueError(f"duplicate field {name!r}")
        fields[name] = part[index + 1:]
    return fields, anonymous_strings


def _require(fields: dict[str, str], names: tuple[str, ...]) -> None:
    for name in names:
        if name not in fields:
            raise ValueError(f"missing required projected field {name!r}")


def _project_bench_record(
    record_text: str, path: str, line: int, source_index: int
) -> dict:
    try:
        fields, stat_text = _parse_named_fields(record_text, "bench row")
        _require(
            fields,
            ("type", "affix", "modTags", "statOrder", "level", "group", "types"),
        )
        if not stat_text:
            raise ValueError("missing required projected field 'stat_text'")
        return {
            "source_index": source_index,
            "source_path": path,
            "source_line": line,
            "type": _parse_string(fields["type"], "type"),
            "affix": _parse_string(fields["affix"], "affix"),
            "level": _parse_integer(fields["level"], "level"),
            "group": _parse_string(fields["group"], "group"),
            "modTags": _parse_string_array(fields["modTags"], "modTags"),
            "statOrder": _parse_number_array(fields["statOrder"], "statOrder"),
            "stat_text": stat_text,
            "types": _parse_boolean_map(fields["types"], "types"),
        }
    except ValueError as error:
        raise _line_error(path, line, str(error)) from error


def _parse_essence_assignment(
    source_text: str, index: int, interior_end: int, path: str
) -> tuple[str, int, int]:
    """Read ``[\"id\"] = { ... }`` and return id/table bounds."""
    line = _line_number(source_text, index)
    if index >= interior_end or source_text[index] != "[":
        raise _line_error(path, line, "non-row content inside return table")
    index = _skip_space_and_comments(source_text, index + 1)
    try:
        essence_id, index = _read_string(source_text, index, strict=True)
    except ValueError as error:
        raise _line_error(path, line, f"malformed essence ID: {error}") from error
    index = _skip_space_and_comments(source_text, index)
    if index >= interior_end or source_text[index] != "]":
        raise _line_error(path, line, "malformed essence row assignment")
    index = _skip_space_and_comments(source_text, index + 1)
    if index >= interior_end or source_text[index] != "=":
        raise _line_error(path, line, "malformed essence row assignment")
    index = _skip_space_and_comments(source_text, index + 1)
    if index >= interior_end or source_text[index] != "{":
        raise _line_error(path, line, "essence row must be a literal table")
    try:
        after_record = _read_balanced_braces(source_text, index)
    except ValueError as error:
        raise _line_error(path, line, f"malformed essence row: {error}") from error
    return essence_id, index, after_record


def _project_essence_record(
    essence_id: str, record_text: str, path: str, line: int
) -> dict:
    try:
        fields, anonymous_strings = _parse_named_fields(record_text, "essence row")
        if anonymous_strings:
            raise ValueError("unsupported anonymous essence expression")
        _require(fields, ("name", "type", "tier", "mods"))
        return {
            "id": essence_id,
            "name": _parse_string(fields["name"], "name"),
            "type": _parse_integer(fields["type"], "type"),
            "tier": _parse_integer(fields["tier"], "tier"),
            "mods": _parse_string_map(fields["mods"], "mods"),
            "source_path": path,
            "source_line": line,
        }
    except ValueError as error:
        raise _line_error(path, line, str(error)) from error


def _after_row(
    source_text: str, index: int, interior_end: int, path: str, line: int
) -> int:
    index = _skip_space_and_comments(source_text, index)
    if index == interior_end:
        return index
    if index > interior_end or source_text[index] != ",":
        raise _line_error(path, line, "expected comma after row")
    return index + 1


def parse_bench_source(source_text: str, path: str = BENCH_SOURCE_PATH) -> list[dict]:
    """Project anonymous literal rows from a generated ``ModMaster.lua`` file."""
    interior_start, interior_end = _extract_return_table(source_text, path)
    result: list[dict] = []
    index = interior_start
    while True:
        index = _skip_space_and_comments(source_text, index)
        if index == interior_end:
            break
        if index > interior_end or source_text[index] != "{":
            raise _error(path, source_text, index, "non-row content inside return table")
        line = _line_number(source_text, index)
        try:
            after_record = _read_balanced_braces(source_text, index)
        except ValueError as error:
            raise _line_error(path, line, f"malformed bench row: {error}") from error
        result.append(
            _project_bench_record(
                source_text[index:after_record], path, line, len(result) + 1
            )
        )
        index = _after_row(source_text, after_record, interior_end, path, line)

    if not result:
        raise _line_error(path, 1, "empty return table")
    return result


def parse_essence_source(
    source_text: str, path: str = ESSENCE_SOURCE_PATH
) -> list[dict]:
    """Project keyed literal records from a generated ``Essence.lua`` file."""
    interior_start, interior_end = _extract_return_table(source_text, path)
    result: list[dict] = []
    ids: set[str] = set()
    index = interior_start
    while True:
        index = _skip_space_and_comments(source_text, index)
        if index == interior_end:
            break
        line = _line_number(source_text, index)
        essence_id, record_start, after_record = _parse_essence_assignment(
            source_text, index, interior_end, path
        )
        if essence_id in ids:
            raise _line_error(path, line, f"duplicate essence ID {essence_id!r}")
        ids.add(essence_id)
        result.append(
            _project_essence_record(
                essence_id, source_text[record_start:after_record], path, line
            )
        )
        index = _after_row(source_text, after_record, interior_end, path, line)

    if not result:
        raise _line_error(path, 1, "empty return table")
    return result


def _build_projection(
    source_bytes: bytes,
    path: str,
    parser: object,
    fields: tuple[str, ...],
    array_name: str,
) -> dict:
    if not isinstance(source_bytes, bytes):
        raise ValueError(f"{path}: source bytes must be bytes")
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{path}: source is not valid UTF-8") from error
    rows = parser(source_text, path)  # type: ignore[operator]
    return {
        "schema_version": 1,
        "projection_fields": list(fields),
        "source": {
            "path": path,
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
            "record_count": len(rows),
            "pob_version": POB_VERSION,
            "poe_version": POE_VERSION,
            "version_authority": VERSION_AUTHORITY,
        },
        array_name: rows,
    }


def build_pob_bench_projection(source_bytes: bytes) -> dict:
    """Build the full deterministic bench projection from S11 source bytes."""
    return _build_projection(
        source_bytes,
        BENCH_SOURCE_PATH,
        parse_bench_source,
        BENCH_PROJECTION_FIELDS,
        "bench",
    )


def build_pob_essences_projection(source_bytes: bytes) -> dict:
    """Build the full deterministic essence projection from S22 source bytes."""
    return _build_projection(
        source_bytes,
        ESSENCE_SOURCE_PATH,
        parse_essence_source,
        ESSENCE_PROJECTION_FIELDS,
        "essences",
    )


def serialize_projection(projection: Mapping[str, object]) -> bytes:
    """Serialize one validated projection as deterministic UTF-8 JSON with LF."""
    return (
        json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
