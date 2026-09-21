"""Literal extraction of Craft of Exile's frozen metamod behavior table.

This module observes only cells in the S14 snapshot.  It deliberately does not
interpret them as current Path of Exile rules.
"""

from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from typing import Any, Mapping


_STATUSES = frozenset({"yes", "no", "na", "yesno", ""})


class CoEMetamodParseError(ValueError):
    """The frozen page does not contain the expected S14 table structure."""


def _classes(attributes: list[tuple[str, str | None]]) -> tuple[str, ...]:
    return tuple(dict(attributes).get("class", "").split())


def _text(parts: list[str]) -> str:
    return " ".join("".join(parts).split())


class _MetamodHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_count = 0
        self.in_table_depth: int | None = None
        self.table_depth = 0
        self.div_depth = 0
        self.current_row: dict[str, Any] | None = None
        self.current_cell: dict[str, Any] | None = None
        self.note_depth = 0
        self.rows: list[dict[str, Any]] = []
        self.warning_depth = 0
        self.warning_parts: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = _classes(attrs)
        if tag == "div":
            self.div_depth += 1
        if tag == "div" and "gen_msg" in classes:
            self.warning_depth = self.div_depth
            self.warning_parts.append([])
        if tag == "table":
            self.table_depth += 1
            if {"mmode_none", "coe_tbl"}.issubset(classes):
                self.table_count += 1
                if self.table_count == 1:
                    self.in_table_depth = self.table_depth
            return
        if self.in_table_depth is None:
            return
        if tag == "tr":
            if self.current_row is not None:
                raise CoEMetamodParseError("nested table row")
            self.current_row = {"classes": classes, "line": self.getpos()[0], "cells": []}
        elif tag == "td" and self.current_row is not None:
            if self.current_cell is not None:
                raise CoEMetamodParseError("nested table cell")
            self.current_cell = {
                "classes": classes,
                "line": self.getpos()[0],
                "text": [],
                "note": [],
            }
        elif tag == "div" and self.current_cell is not None and "note" in classes:
            self.note_depth = self.div_depth

    def handle_endtag(self, tag: str) -> None:
        if self.in_table_depth is not None:
            if tag == "td" and self.current_cell is not None:
                assert self.current_row is not None
                self.current_row["cells"].append(self.current_cell)
                self.current_cell = None
                self.note_depth = 0
            elif tag == "tr" and self.current_row is not None:
                if self.current_cell is not None:
                    raise CoEMetamodParseError("unclosed table cell")
                self.rows.append(self.current_row)
                self.current_row = None
            if tag == "table" and self.table_depth == self.in_table_depth:
                self.in_table_depth = None
        if tag == "table":
            self.table_depth -= 1
        if tag == "div" and self.note_depth == self.div_depth:
            self.note_depth = 0
        if tag == "div" and self.warning_depth == self.div_depth:
            self.warning_depth = 0
        if tag == "div":
            self.div_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.warning_depth:
            self.warning_parts[-1].append(data)
        if self.current_cell is not None:
            self.current_cell["text"].append(data)
            if self.note_depth:
                self.current_cell["note"].append(data)

    def close(self) -> None:
        super().close()
        if self.current_row is not None or self.current_cell is not None or self.in_table_depth is not None:
            raise CoEMetamodParseError("malformed metamod table")


def _status(cell: Mapping[str, Any], label: str) -> str:
    classes = cell["classes"]
    if not classes:
        return ""
    if len(classes) != 1 or classes[0] not in _STATUSES:
        raise CoEMetamodParseError(f"unknown status for {label!r} at line {cell['line']}: {classes!r}")
    return classes[0]


def build_metamod_table(source_text: str, source_path: str) -> dict[str, Any]:
    """Return a strict, source-ordered S14 cell observation from cached HTML."""
    parser = _MetamodHTMLParser()
    parser.feed(source_text)
    parser.close()
    if parser.table_count == 0:
        raise CoEMetamodParseError("missing metamod table")
    if parser.table_count != 1:
        raise CoEMetamodParseError("duplicate metamod table")
    if not parser.rows:
        raise CoEMetamodParseError("metamod table has no rows")
    warnings = [_text(parts) for parts in parser.warning_parts]
    warning = next((value for value in warnings if value.startswith("Warning:")), None)
    if warning is None:
        raise CoEMetamodParseError("missing warning")

    header = parser.rows[0]
    if "header" not in header["classes"] or len(header["cells"]) != 5:
        raise CoEMetamodParseError("header expected five cells")
    if _text(header["cells"][0]["text"]) != "Crafting method":
        raise CoEMetamodParseError("header first cell must be Crafting method")
    columns = [_text(cell["text"]) for cell in header["cells"][1:]]
    if len(columns) != 4 or len(set(columns)) != 4 or any(not label for label in columns):
        raise CoEMetamodParseError("missing/duplicate metamod columns")

    groups: list[dict[str, Any]] = [{"heading": "General", "source_line": header["line"], "actions": []}]
    for row in parser.rows[1:]:
        cells = row["cells"]
        if "group" in row["classes"]:
            if len(cells) != 1:
                raise CoEMetamodParseError(f"group row at line {row['line']} must have one cell")
            heading = _text(cells[0]["text"])
            if not heading:
                raise CoEMetamodParseError(f"empty group heading at line {row['line']}")
            groups.append({"heading": heading, "source_line": row["line"], "actions": []})
            continue
        if len(cells) != 5:
            raise CoEMetamodParseError(f"action row at line {row['line']} expected five cells")
        if cells[0]["classes"] != ("label",):
            raise CoEMetamodParseError(f"action row at line {row['line']} missing label cell")
        label = _text(cells[0]["text"])
        if not label:
            raise CoEMetamodParseError(f"empty action label at line {row['line']}")
        groups[-1]["actions"].append(
            {
                "label": label,
                "source_line": row["line"],
                "cells": [
                    {"status": _status(cell, label), "note": _text(cell["note"]), "source_line": cell["line"]}
                    for cell in cells[1:]
                ],
            }
        )
    if not groups[0]["actions"]:
        raise CoEMetamodParseError("General group has no actions")
    if any(not group["actions"] for group in groups):
        raise CoEMetamodParseError("empty action group")
    return {
        "schema_version": 1,
        "confidence": "reimplemented-from-CoE",
        "scope": "frozen-source-observation",
        "current_game_applicability": "requires a lead fact sheet",
        "warning": warning,
        "source": {
            "id": "S14",
            "url": "https://www.craftofexile.com/?page=metamods",
            "cache_path": source_path,
            "original_read_date": "2026-09-20",
            "extraction_date": "2026-09-21",
            "sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        },
        "columns": columns,
        "groups": groups,
    }


def serialize_metamod_table(table: Mapping[str, object]) -> bytes:
    """Serialize an already validated table as deterministic UTF-8 JSON with LF."""
    return json.dumps(table, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
