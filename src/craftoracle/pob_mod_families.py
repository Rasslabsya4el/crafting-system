"""Literal, source-preserving projection of generated PoB modifier tables.

The accepted syntax is the generated-table subset used by the six owner-supplied
PoB data files.  It is deliberately a parser, not a Lua evaluator and not a
modifier-pool resolver.  Source: S1/S24/S25 in ``docs/SOURCES.md``, read
2026-09-20; snapshot identity is recorded in the generated JSON.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass


SOURCE_PATHS = (
    "sources/pob/Data/ModExplicit.lua",
    "sources/pob/Data/ModVeiled.lua",
    "sources/pob/Data/ModEldritch.lua",
    "sources/pob/Data/ModCorrupted.lua",
    "sources/pob/Data/ModDelve.lua",
    "sources/pob/Data/ModSynthesis.lua",
)

PROJECTION_FIELDS = (
    "source_path",
    "source_line",
    "id",
    "type",
    "affix",
    "level",
    "group",
    "weightKey",
    "weightVal",
    "modTags",
    "stat_text",
    "statOrder",
    "tags",
    "weightMultiplierKey",
    "weightMultiplierVal",
)

_REQUIRED_STRING_FIELDS = frozenset(("type", "affix", "group"))
_REQUIRED_INTEGER_FIELDS = frozenset(("level",))
_REQUIRED_STRING_ARRAY_FIELDS = frozenset(("weightKey", "modTags"))
_REQUIRED_INTEGER_ARRAY_FIELDS = frozenset(("weightVal", "statOrder"))
_OPTIONAL_STRING_ARRAY_FIELDS = frozenset(("tags", "weightMultiplierKey"))
_OPTIONAL_INTEGER_ARRAY_FIELDS = frozenset(("weightMultiplierVal",))
_PROJECTED_NAMED_FIELDS = (
    _REQUIRED_STRING_FIELDS
    | _REQUIRED_INTEGER_FIELDS
    | _REQUIRED_STRING_ARRAY_FIELDS
    | _REQUIRED_INTEGER_ARRAY_FIELDS
    | _OPTIONAL_STRING_ARRAY_FIELDS
    | _OPTIONAL_INTEGER_ARRAY_FIELDS
)


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    line: int


def _error(source_path: str, line: int, message: str) -> ValueError:
    return ValueError(f"{source_path}:{line}: {message}")


def _tokenize(source_text: str, source_path: str) -> list[_Token]:
    """Tokenize the literal subset while retaining one-based source lines."""
    tokens: list[_Token] = []
    index = 0
    line = 1
    punctuation = {
        "{": "LBRACE",
        "}": "RBRACE",
        "[": "LBRACKET",
        "]": "RBRACKET",
        "=": "EQUAL",
        ",": "COMMA",
    }

    while index < len(source_text):
        character = source_text[index]
        if character in " \t\r":
            index += 1
            continue
        if character == "\n":
            line += 1
            index += 1
            continue
        if source_text.startswith("--", index):
            index += 2
            if source_text.startswith("[[", index):
                end = source_text.find("]]", index + 2)
                if end == -1:
                    raise _error(source_path, line, "unterminated block comment")
                line += source_text[index : end + 2].count("\n")
                index = end + 2
            else:
                end = source_text.find("\n", index)
                if end == -1:
                    break
                index = end
            continue
        kind = punctuation.get(character)
        if kind is not None:
            tokens.append(_Token(kind, character, line))
            index += 1
            continue
        if character == '"':
            string_line = line
            index += 1
            characters: list[str] = []
            while index < len(source_text):
                current = source_text[index]
                if current == '"':
                    index += 1
                    tokens.append(_Token("STRING", "".join(characters), string_line))
                    break
                if current == "\n":
                    raise _error(source_path, string_line, "unterminated string literal")
                if current != "\\":
                    characters.append(current)
                    index += 1
                    continue
                if index + 1 >= len(source_text):
                    raise _error(source_path, string_line, "unterminated escape sequence")
                escaped = source_text[index + 1]
                simple_escapes = {
                    '"': '"',
                    "'": "'",
                    "\\": "\\",
                    "a": "\a",
                    "b": "\b",
                    "f": "\f",
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                    "v": "\v",
                }
                if escaped in simple_escapes:
                    characters.append(simple_escapes[escaped])
                    index += 2
                    continue
                if escaped.isdigit():
                    digits = source_text[index + 1 : index + 4]
                    if not digits or not all(digit.isdigit() for digit in digits):
                        raise _error(source_path, string_line, "invalid decimal escape")
                    codepoint = int(digits)
                    if codepoint > 255:
                        raise _error(source_path, string_line, "decimal escape exceeds 255")
                    characters.append(chr(codepoint))
                    index += 4
                    continue
                raise _error(source_path, string_line, f"unsupported escape \\{escaped}")
            else:
                raise _error(source_path, string_line, "unterminated string literal")
            continue
        if character == "-" or character.isdigit():
            number_line = line
            start = index
            if character == "-":
                index += 1
                if index >= len(source_text) or not source_text[index].isdigit():
                    raise _error(source_path, number_line, "unsupported expression")
            while index < len(source_text) and source_text[index].isdigit():
                index += 1
            if index < len(source_text) and source_text[index] == ".":
                index += 1
                decimal_start = index
                while index < len(source_text) and source_text[index].isdigit():
                    index += 1
                if index == decimal_start:
                    raise _error(source_path, number_line, "invalid decimal literal")
            tokens.append(_Token("NUMBER", source_text[start:index], number_line))
            continue
        if character.isalpha() or character == "_":
            identifier_line = line
            start = index
            index += 1
            while index < len(source_text) and (
                source_text[index].isalnum() or source_text[index] == "_"
            ):
                index += 1
            tokens.append(_Token("IDENTIFIER", source_text[start:index], identifier_line))
            continue
        raise _error(source_path, line, f"unsupported character {character!r}")

    tokens.append(_Token("EOF", "", line))
    return tokens


class _LiteralParser:
    def __init__(self, source_text: str, source_path: str) -> None:
        self.source_path = source_path
        self.tokens = _tokenize(source_text, source_path)
        self.index = 0

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def _advance(self) -> _Token:
        token = self.current
        self.index += 1
        return token

    def _fail(self, message: str, token: _Token | None = None) -> None:
        location = self.current if token is None else token
        raise _error(self.source_path, location.line, message)

    def _expect(self, kind: str, message: str) -> _Token:
        if self.current.kind != kind:
            self._fail(message)
        return self._advance()

    def _expect_identifier(self, value: str, message: str) -> _Token:
        token = self._expect("IDENTIFIER", message)
        if token.value != value:
            self._fail(message, token)
        return token

    def parse_file(self) -> list[dict]:
        self._expect_identifier("return", "expected return { wrapper")
        self._expect("LBRACE", "expected return { wrapper")
        records: list[dict] = []
        identifiers: set[str] = set()

        while self.current.kind != "RBRACE":
            if self.current.kind == "EOF":
                self._fail("missing closing } wrapper")
            row_line = self.current.line
            self._expect("LBRACKET", "non-row content inside returned table")
            identifier = self._expect("STRING", "row id must be a quoted string").value
            self._expect("RBRACKET", "malformed row id")
            self._expect("EQUAL", "expected = after row id")
            self._expect("LBRACE", "row value must be a table")
            if identifier in identifiers:
                self._fail(f"duplicate id {identifier!r}", _Token("ROW", "", row_line))
            identifiers.add(identifier)
            records.append(self._parse_row(identifier, row_line))
            self._after_table_entry("row")

        self._advance()
        if self.current.kind != "EOF":
            self._fail("unexpected content after closing } wrapper")
        return records

    def _after_table_entry(self, description: str) -> None:
        if self.current.kind == "COMMA":
            self._advance()
            return
        if self.current.kind == "RBRACE":
            return
        if self.current.kind == "EOF":
            self._fail("missing closing } wrapper")
        self._fail(f"expected comma or closing }} after {description}")

    def _parse_row(self, identifier: str, row_line: int) -> dict:
        named: dict[str, object] = {}
        stat_text: list[str] = []
        while self.current.kind != "RBRACE":
            if self.current.kind == "EOF":
                self._fail("missing closing } for modifier row")
            if self.current.kind == "STRING":
                stat_text.append(self._advance().value)
            elif self.current.kind == "IDENTIFIER":
                field = self._advance()
                self._expect("EQUAL", f"expected = after field {field.value!r}")
                if field.value in _PROJECTED_NAMED_FIELDS:
                    if field.value in named:
                        self._fail(f"duplicate projected key {field.value!r}", field)
                    named[field.value] = self._parse_projected_value(field.value)
                else:
                    self._skip_value()
            elif self.current.kind == "LBRACKET":
                self._skip_keyed_entry()
            else:
                self._fail("unsupported expression in modifier row")
            self._after_table_entry("modifier row entry")

        self._advance()
        required_fields = (
            _REQUIRED_STRING_FIELDS
            | _REQUIRED_INTEGER_FIELDS
            | _REQUIRED_STRING_ARRAY_FIELDS
            | _REQUIRED_INTEGER_ARRAY_FIELDS
        )
        missing = sorted(required_fields - named.keys())
        if missing:
            self._fail(
                "missing required projected field" + ("s" if len(missing) > 1 else "")
                + ": "
                + ", ".join(missing),
                _Token("ROW", "", row_line),
            )

        weight_key = named["weightKey"]
        weight_val = named["weightVal"]
        if len(weight_key) != len(weight_val):
            self._fail("weightKey and weightVal lengths differ", _Token("ROW", "", row_line))

        multiplier_key = named.get("weightMultiplierKey")
        multiplier_val = named.get("weightMultiplierVal")
        if (multiplier_key is None) != (multiplier_val is None):
            self._fail(
                "weightMultiplierKey and weightMultiplierVal must both be present",
                _Token("ROW", "", row_line),
            )
        if multiplier_key is not None and len(multiplier_key) != len(multiplier_val):
            self._fail(
                "weightMultiplierKey and weightMultiplierVal lengths differ",
                _Token("ROW", "", row_line),
            )

        return {
            "source_path": self.source_path,
            "source_line": row_line,
            "id": identifier,
            "type": named["type"],
            "affix": named["affix"],
            "level": named["level"],
            "group": named["group"],
            "weightKey": weight_key,
            "weightVal": weight_val,
            "modTags": named["modTags"],
            "stat_text": stat_text,
            "statOrder": named["statOrder"],
            "tags": named.get("tags"),
            "weightMultiplierKey": multiplier_key,
            "weightMultiplierVal": multiplier_val,
        }

    def _parse_projected_value(self, field: str) -> object:
        if field in _REQUIRED_STRING_FIELDS:
            return self._expect("STRING", f"expected string literal for {field}").value
        if field in _REQUIRED_INTEGER_FIELDS:
            token = self._expect(
                "NUMBER", f"expected integer literal for {field}; unsupported expression"
            )
            if not token.value.isdigit():
                self._fail(f"expected integer literal for {field}", token)
            value = int(token.value)
            return value
        if field in _REQUIRED_STRING_ARRAY_FIELDS | _OPTIONAL_STRING_ARRAY_FIELDS:
            return self._parse_array("STRING", field)
        if field in _OPTIONAL_INTEGER_ARRAY_FIELDS:
            return self._parse_array("INTEGER", field)
        if field == "statOrder":
            return self._parse_array("NUMBER", field)
        if field == "weightVal":
            return self._parse_array("INTEGER", field)
        self._fail(f"unsupported projected field {field!r}")

    def _parse_array(self, member_kind: str, field: str) -> list[object]:
        self._expect("LBRACE", f"expected literal array for {field}; unsupported expression")
        values: list[object] = []
        while self.current.kind != "RBRACE":
            if self.current.kind == "EOF":
                self._fail(f"missing closing }} for {field}")
            expected_kind = "NUMBER" if member_kind in {"INTEGER", "NUMBER"} else member_kind
            token = self._expect(
                expected_kind,
                f"expected {member_kind.lower()} literal in {field}; unsupported expression",
            )
            if member_kind == "INTEGER":
                if not token.value.isdigit():
                    self._fail(f"expected integer literal in {field}", token)
                value = int(token.value)
                values.append(value)
            elif member_kind == "NUMBER":
                values.append(int(token.value) if token.value.isdigit() else float(token.value))
            else:
                values.append(token.value)
            if self.current.kind == "COMMA":
                self._advance()
                continue
            if self.current.kind != "RBRACE":
                self._fail(f"expected comma or closing }} in {field}")
        self._advance()
        return values

    def _skip_keyed_entry(self) -> None:
        self._expect("LBRACKET", "expected keyed entry")
        self._skip_value()
        self._expect("RBRACKET", "missing closing ] in unprojected key")
        self._expect("EQUAL", "expected = after unprojected key")
        self._skip_value()

    def _skip_value(self) -> None:
        """Consume a structurally valid but unprojected literal value."""
        if self.current.kind in {"STRING", "NUMBER", "IDENTIFIER"}:
            self._advance()
            return
        if self.current.kind != "LBRACE":
            self._fail("unsupported expression in unprojected field")
        self._advance()
        while self.current.kind != "RBRACE":
            if self.current.kind == "EOF":
                self._fail("missing closing } in unprojected field")
            if self.current.kind == "LBRACKET":
                self._skip_keyed_entry()
            elif (
                self.current.kind == "IDENTIFIER"
                and self.tokens[self.index + 1].kind == "EQUAL"
            ):
                self._advance()
                self._advance()
                self._skip_value()
            else:
                self._skip_value()
            self._after_table_entry("unprojected field")
        self._advance()


def parse_mod_source(source_text: str, source_path: str) -> list[dict]:
    """Parse one generated PoB modifier table without executing Lua."""
    if not isinstance(source_text, str):
        raise ValueError(f"{source_path}:1: source text must be a string")
    if not isinstance(source_path, str) or not source_path:
        raise ValueError("source path must be a non-empty string")
    return _LiteralParser(source_text, source_path).parse_file()


def build_pob_mod_families_projection(
    source_payloads: Mapping[str, bytes],
) -> dict:
    """Build all six literal projections in fixed source and row order."""
    expected = set(SOURCE_PATHS)
    supplied = set(source_payloads)
    missing = sorted(expected - supplied)
    unexpected = sorted(supplied - expected)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append("missing sources: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected sources: " + ", ".join(unexpected))
        raise ValueError("; ".join(details))

    sources: list[dict] = []
    mods: list[dict] = []
    for source_path in SOURCE_PATHS:
        source_bytes = source_payloads[source_path]
        if not isinstance(source_bytes, bytes):
            raise ValueError(f"{source_path}: source bytes must be bytes")
        try:
            source_text = source_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"{source_path}: invalid UTF-8 source") from error
        rows = parse_mod_source(source_text, source_path)
        sources.append(
            {
                "path": source_path,
                "sha256": hashlib.sha256(source_bytes).hexdigest(),
                "record_count": len(rows),
            }
        )
        mods.extend(rows)

    return {
        "schema_version": 1,
        "projection_fields": list(PROJECTION_FIELDS),
        "source_metadata": {
            "pob_version": "2.67.2",
            "poe_version": "3.29",
            "authority": "owner-supplied snapshot",
            "upstream_revision": "unverified (Q8)",
        },
        "sources": sources,
        "mods": mods,
    }


def serialize_projection(projection: Mapping[str, object]) -> bytes:
    """Serialize a projection as sorted-key, UTF-8 LF JSON with a final newline."""
    return (
        json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
