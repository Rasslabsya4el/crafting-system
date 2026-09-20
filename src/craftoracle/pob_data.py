"""Limited deterministic projection of PoB ``ModExplicit.lua`` rows.

This module intentionally projects only the eight literal fields accepted by
``pob_row.parse_mod_row`` plus the row's source line.  It neither executes Lua
nor resolves modifier eligibility, stat lines, tiers, ranges, influences, or
weight-selection behavior.  Those unprojected source fields are required by a
future resolver.

Source: PoB data ``ModExplicit.lua`` (S1/S10 in ``docs/SOURCES.md``), read
2026-09-20.  The format accepted here is only its generated-file subset.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from craftoracle.pob_row import parse_mod_row


PROJECTION_FIELDS = (
    "id",
    "type",
    "affix",
    "level",
    "group",
    "weightKey",
    "weightVal",
    "modTags",
    "source_line",
)

_SOURCE_PATH = "sources/pob/Data/ModExplicit.lua"
_VERSION_AUTHORITY = (
    "AGENTS.md section 1 (owner supplied; upstream revision unverified)"
)


def _line_error(line_number: int, message: str) -> ValueError:
    return ValueError(f"line {line_number}: {message}")


def _is_ignorable(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("--")


def parse_mod_explicit_source(source_text: str) -> list[dict]:
    """Return literal projected rows from one generated ``ModExplicit.lua`` file.

    Blank lines and full-line Lua comments are ignored.  Apart from those lines,
    the file must consist of one ``return {`` wrapper, rows accepted by
    :func:`parse_mod_row`, and one closing ``}`` wrapper.  Each error identifies
    the relevant one-based source line.
    """
    if not isinstance(source_text, str):
        raise ValueError("line 1: source text must be a string")

    state = "before_wrapper"
    rows: list[dict] = []
    ids: set[str] = set()
    lines = source_text.splitlines()
    last_line = max(1, len(lines))

    for line_number, line in enumerate(lines, start=1):
        if _is_ignorable(line):
            continue

        stripped = line.strip()
        if state == "before_wrapper":
            if stripped != "return {":
                raise _line_error(line_number, "expected return { wrapper")
            state = "inside_wrapper"
            continue

        if state == "inside_wrapper":
            if stripped == "}":
                state = "after_wrapper"
                continue
            try:
                row = parse_mod_row(line)
            except ValueError as error:
                raise _line_error(line_number, str(error)) from error
            identifier = row["id"]
            if identifier in ids:
                raise _line_error(line_number, f"duplicate id {identifier!r}")
            ids.add(identifier)
            row["source_line"] = line_number
            rows.append(row)
            continue

        raise _line_error(line_number, "unexpected content after closing } wrapper")

    if state == "before_wrapper":
        raise _line_error(1, "missing return { wrapper")
    if state == "inside_wrapper":
        raise _line_error(last_line, "missing closing } wrapper")
    if not rows:
        raise _line_error(last_line, "empty modifier file")
    return rows


def build_pob_explicit_projection(source_text: str, source_sha256: str) -> dict:
    """Build metadata and rows for the fixed, intentionally incomplete projection."""
    rows = parse_mod_explicit_source(source_text)
    return {
        "schema_version": 1,
        "projection_fields": list(PROJECTION_FIELDS),
        "source": {
            "path": _SOURCE_PATH,
            "sha256": source_sha256,
            "pob_version": "2.67.2",
            "poe_version": "3.29",
            "version_authority": _VERSION_AUTHORITY,
            "record_count": len(rows),
        },
        "mods": rows,
    }


def serialize_projection(projection: Mapping[str, object]) -> bytes:
    """Serialize a validated projection as deterministic UTF-8 JSON with LF."""
    return (
        json.dumps(
            projection,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
