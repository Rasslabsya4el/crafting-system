"""Literal, deliberately limited projection of five PoB item-base files.

The parser recognizes generated ``itemBases[\"Name\"] = { ... }`` records
without executing Lua.  It projects only the literal base tags needed for the
Phase 0 cross-check: name, type, optional subType/socketLimit, tags,
influenceTags, and assignment provenance.  Defence and weapon properties,
implicit text, requirements, and all eligibility/resolver behavior deliberately
remain unprojected.

Source: PoB data ``Data/Bases/{helmet,bow,ring,body,gloves}.lua``, supplied by
the owner as described in AGENTS.md section 1, read 2026-09-20.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping


PROJECTION_FIELDS = (
    "name",
    "type",
    "subType",
    "socketLimit",
    "tags",
    "influenceTags",
    "source",
)

POB_VERSION = "2.67.2"
POE_VERSION = "3.29"
VERSION_AUTHORITY = (
    "AGENTS.md section 1 (owner supplied; upstream revision unverified)"
)

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ASSIGNMENT = re.compile(r"[ \t]*itemBases[ \t]*\[[ \t]*")
_HEADER = "local itemBases = ..."


def _error(path: str, line: int, message: str) -> ValueError:
    return ValueError(f"{path}: line {line}: {message}")


def _line_number(source_text: str, index: int) -> int:
    return source_text.count("\n", 0, index) + 1


def _skip_space_and_comments(text: str, index: int = 0) -> int:
    """Skip Lua whitespace and line comments while outside quoted strings."""
    while index < len(text):
        if text[index].isspace():
            index += 1
        elif text.startswith("--", index):
            newline = text.find("\n", index + 2)
            index = len(text) if newline == -1 else newline + 1
        else:
            return index
    return index


def _read_string(
    text: str, index: int, *, strict: bool = False
) -> tuple[str, int]:
    """Read a quoted short string without evaluating Lua source.

    The structural reader accepts ignored-field strings sufficiently to find a
    matching quote.  Projected strings use ``strict=True`` so unsupported
    escapes and literal newlines fail instead of being silently changed.
    """
    if index >= len(text) or text[index] not in "\"'":
        raise ValueError("expected quoted string")
    quote = text[index]
    index += 1
    value: list[str] = []
    escapes = {
        "a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r",
        "t": "\t", "v": "\v", "\\": "\\", "\"": "\"", "'": "'",
    }
    while index < len(text):
        character = text[index]
        if character == quote:
            return "".join(value), index + 1
        if strict and character in "\r\n":
            raise ValueError("literal newline in projected string")
        if character != "\\":
            value.append(character)
            index += 1
            continue

        index += 1
        if index >= len(text):
            raise ValueError("unfinished string escape")
        escaped = text[index]
        if escaped.isdigit():
            digits = text[index:index + 3]
            digits = digits[: len(digits) - len(digits.lstrip("0123456789"))]
            number = int(digits, 10)
            if strict and number > 255:
                raise ValueError("decimal string escape exceeds 255")
            value.append(chr(number))
            index += len(digits)
            continue
        if escaped in escapes:
            value.append(escapes[escaped])
            index += 1
            continue
        if strict:
            raise ValueError("unknown string escape")
        value.append(escaped)
        index += 1
    raise ValueError("unclosed quoted string")


def _read_balanced_braces(text: str, opening_index: int) -> int:
    """Return the index after a brace-delimited value, respecting strings/comments."""
    if opening_index >= len(text) or text[opening_index] != "{":
        raise ValueError("expected opening {")
    depth = 1
    index = opening_index + 1
    while index < len(text):
        character = text[index]
        if character in "\"'":
            _, index = _read_string(text, index)
            continue
        if text.startswith("--", index):
            newline = text.find("\n", index + 2)
            index = len(text) if newline == -1 else newline + 1
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise ValueError("unclosed record")


def _split_top_level(text: str) -> list[str]:
    """Split comma-separated values without interpreting nested Lua tables."""
    parts: list[str] = []
    start = 0
    stack: list[str] = []
    closing = {"}": "{", "]": "[", ")": "("}
    index = 0
    while index < len(text):
        character = text[index]
        if character in "\"'":
            _, index = _read_string(text, index)
            continue
        if text.startswith("--", index):
            newline = text.find("\n", index + 2)
            index = len(text) if newline == -1 else newline + 1
            continue
        if character in "{[(":
            stack.append(character)
        elif character in "}])":
            if not stack or stack[-1] != closing[character]:
                raise ValueError("malformed nested value")
            stack.pop()
        elif character == "," and not stack:
            parts.append(text[start:index])
            start = index + 1
        index += 1
    if stack:
        raise ValueError("unclosed nested value")
    parts.append(text[start:])
    return parts


def _only_space_or_comments(text: str, index: int) -> bool:
    return _skip_space_and_comments(text, index) == len(text)


def _read_map_key(text: str, index: int) -> tuple[str, int]:
    if index < len(text) and text[index] in "\"'":
        return _read_string(text, index, strict=True)
    if index < len(text) and text[index] == "[":
        index = _skip_space_and_comments(text, index + 1)
        key, index = _read_string(text, index, strict=True)
        index = _skip_space_and_comments(text, index)
        if index >= len(text) or text[index] != "]":
            raise ValueError("malformed map key")
        return key, index + 1
    match = _IDENTIFIER.match(text, index)
    if match is None:
        raise ValueError("map key must be a string")
    return match.group(), match.end()


def _parse_map(value: str, expected_value: str) -> dict[str, object]:
    """Parse a simple string-keyed table into bool or string values."""
    index = _skip_space_and_comments(value)
    if index >= len(value) or value[index] != "{":
        raise ValueError("projected map must be a table")
    end = _read_balanced_braces(value, index)
    if not _only_space_or_comments(value, end):
        raise ValueError("unexpected text after projected map")
    inner = value[index + 1:end - 1]
    result: dict[str, object] = {}
    parts = _split_top_level(inner)
    for part_number, part in enumerate(parts):
        part_index = _skip_space_and_comments(part)
        if part_index == len(part):
            if len(parts) == 1 or part_number == len(parts) - 1:
                continue
            raise ValueError("empty projected map entry")
        key, part_index = _read_map_key(part, part_index)
        part_index = _skip_space_and_comments(part, part_index)
        if part_index >= len(part) or part[part_index] != "=":
            raise ValueError("malformed projected map entry")
        part_index = _skip_space_and_comments(part, part_index + 1)
        if expected_value == "bool":
            match = _IDENTIFIER.match(part, part_index)
            if match is None or match.group() not in {"true", "false"}:
                raise ValueError("tags values must be booleans")
            parsed: object = match.group() == "true"
            part_index = match.end()
        else:
            try:
                parsed, part_index = _read_string(part, part_index, strict=True)
            except ValueError as error:
                raise ValueError(
                    f"influenceTags values must be strings: {error}"
                ) from error
        if not _only_space_or_comments(part, part_index):
            raise ValueError("malformed projected map entry")
        if key in result:
            raise ValueError(f"duplicate projected map key {key!r}")
        result[key] = parsed
    return result


def _parse_string(value: str, field: str) -> str:
    index = _skip_space_and_comments(value)
    try:
        parsed, index = _read_string(value, index, strict=True)
    except ValueError as error:
        raise ValueError(f"{field} must be a quoted string: {error}") from error
    if not _only_space_or_comments(value, index):
        raise ValueError(f"malformed {field}")
    return parsed


def _parse_socket_limit(value: str) -> int:
    stripped_start = _skip_space_and_comments(value)
    stripped_end = len(value)
    while stripped_end > stripped_start and value[stripped_end - 1].isspace():
        stripped_end -= 1
    raw = value[stripped_start:stripped_end]
    if re.fullmatch(r"[0-9]+", raw) is None:
        raise ValueError("socketLimit must be a non-negative integer")
    return int(raw)


def _project_record(name: str, record_text: str, path: str, line: int) -> dict:
    fields: dict[str, str] = {}
    try:
        parts = _split_top_level(record_text[1:-1])
    except ValueError as error:
        raise _error(path, line, str(error)) from error
    for part in parts:
        index = _skip_space_and_comments(part)
        match = _IDENTIFIER.match(part, index)
        if match is None:
            continue
        field = match.group()
        index = _skip_space_and_comments(part, match.end())
        if index >= len(part) or part[index] != "=":
            continue
        if field not in {"type", "subType", "socketLimit", "tags", "influenceTags"}:
            continue
        if field in fields:
            raise _error(path, line, f"duplicate projected field {field!r}")
        fields[field] = part[index + 1:]

    missing = [field for field in ("type", "tags", "influenceTags") if field not in fields]
    if missing:
        raise _error(path, line, f"missing required projected field {missing[0]!r}")
    try:
        return {
            "name": name,
            "type": _parse_string(fields["type"], "type"),
            "subType": (
                _parse_string(fields["subType"], "subType")
                if "subType" in fields else None
            ),
            "socketLimit": (
                _parse_socket_limit(fields["socketLimit"])
                if "socketLimit" in fields else None
            ),
            "tags": _parse_map(fields["tags"], "bool"),
            "influenceTags": _parse_map(fields["influenceTags"], "string"),
            "source": {"path": path, "line": line},
        }
    except ValueError as error:
        raise _error(path, line, str(error)) from error


def _parse_assignment_start(source_text: str, index: int) -> tuple[str, int]:
    match = _ASSIGNMENT.match(source_text, index)
    if match is None:
        raise ValueError("malformed record assignment")
    try:
        name, index = _read_string(source_text, match.end(), strict=True)
    except ValueError as error:
        raise ValueError("malformed record name") from error
    index = _skip_space_and_comments(source_text, index)
    if index >= len(source_text) or source_text[index] != "]":
        raise ValueError("malformed record assignment")
    index = _skip_space_and_comments(source_text, index + 1)
    if index >= len(source_text) or source_text[index] != "=":
        raise ValueError("malformed record assignment")
    index = _skip_space_and_comments(source_text, index + 1)
    if index >= len(source_text) or source_text[index] != "{":
        raise ValueError("malformed record assignment")
    return name, index


def parse_base_source(source_text: str, path: str) -> list[dict]:
    """Return literal projections from one generated PoB ``Bases/*.lua`` file.

    Outside records, only the generated ``local itemBases = ...`` header,
    blank lines, and full-line comments are accepted.  Errors retain the source
    path and a one-based line derived from ``text.splitlines()`` positions.
    """
    if not isinstance(source_text, str):
        raise ValueError(f"{path}: line 1: source text must be a string")
    if not isinstance(path, str) or not path:
        raise ValueError("source path must be a non-empty string")

    header_seen = False
    result: list[dict] = []
    identities: set[tuple[str, int]] = set()
    index = 0
    while index < len(source_text):
        line_end = source_text.find("\n", index)
        if line_end == -1:
            line_end = len(source_text)
        line = source_text[index:line_end]
        stripped = line.strip()
        line_number = _line_number(source_text, index)
        if not stripped or stripped.startswith("--"):
            index = line_end + 1
            continue
        if stripped == _HEADER:
            if header_seen or result:
                raise _error(path, line_number, "unexpected header")
            header_seen = True
            index = line_end + 1
            continue
        if not header_seen:
            raise _error(path, line_number, "expected local itemBases = ... header")

        try:
            name, opening_index = _parse_assignment_start(source_text, index)
            closing_index = _read_balanced_braces(source_text, opening_index)
        except ValueError as error:
            message = str(error)
            error_line = line_number
            if message == "unclosed record":
                error_line = _line_number(source_text, len(source_text))
            elif message == "malformed record assignment":
                message = "unexpected outside content"
            raise _error(path, error_line, message) from error
        record_end_line = source_text.find("\n", closing_index)
        if record_end_line == -1:
            record_end_line = len(source_text)
        if source_text[closing_index:record_end_line].strip():
            raise _error(path, _line_number(source_text, closing_index), "unexpected outside content")
        identity = (path, line_number)
        if identity in identities:
            raise _error(path, line_number, "duplicate source identity")
        identities.add(identity)
        result.append(
            _project_record(name, source_text[opening_index:closing_index], path, line_number)
        )
        index = record_end_line + 1

    if not header_seen:
        raise _error(path, 1, "missing local itemBases = ... header")
    if not result:
        raise _error(path, 1, "empty base source")
    return result


def parse_base_sources(sources: Iterable[tuple[str, str]]) -> list[dict]:
    """Parse ordered text sources and reject duplicate provenance identities."""
    bases: list[dict] = []
    identities: set[tuple[str, int]] = set()
    for path, source_text in sources:
        for base in parse_base_source(source_text, path):
            source = base["source"]
            identity = (source["path"], source["line"])
            if identity in identities:
                raise _error(source["path"], source["line"], "duplicate source identity")
            identities.add(identity)
            bases.append(base)
    return bases


def build_pob_bases_projection(sources: Iterable[tuple[str, bytes]]) -> dict:
    """Validate all selected source bytes and build the fixed projection."""
    source_rows: list[dict] = []
    text_sources: list[tuple[str, str]] = []
    for path, raw in sources:
        if not isinstance(raw, bytes):
            raise ValueError(f"{path}: source bytes must be bytes")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"{path}: source is not valid UTF-8") from error
        text_sources.append((path, text))
        source_rows.append(
            {"path": path, "sha256": hashlib.sha256(raw).hexdigest()}
        )

    bases = parse_base_sources(text_sources)
    record_counts = {path: 0 for path, _ in text_sources}
    for base in bases:
        record_counts[base["source"]["path"]] += 1
    for source in source_rows:
        source["record_count"] = record_counts[source["path"]]
    return {
        "schema_version": 1,
        "projection_fields": list(PROJECTION_FIELDS),
        "sources": source_rows,
        "pob_version": POB_VERSION,
        "poe_version": POE_VERSION,
        "version_authority": VERSION_AUTHORITY,
        "bases": bases,
    }


def serialize_projection(projection: Mapping[str, object]) -> bytes:
    """Serialize a validated projection as deterministic UTF-8 JSON with LF."""
    return (
        json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
