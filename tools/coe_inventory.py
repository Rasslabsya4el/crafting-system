"""Mechanically inventory Craft of Exile's cached ``poec_cmethods`` object.

The reader deliberately accepts only the small JavaScript literal subset used by the
target assignment.  It does not execute JavaScript and does not inspect the rest of
the application except for declaration-line anchors requested by the inventory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


DECLARATION_NAMES = (
    "poec_simApplyCraftGO",
    "poec_simRerollItem",
    "poec_simRollAffix",
    "poec_simRemoveAffix",
    "poec_simClearItem",
    "poec_simRerollValues",
    "poec_simRecombinate",
    "poec_simCheckHReroll",
    "poec_computeBestFossils",
    "poec_simRollImplicits",
    "poec_nsimExecute",
    "poec_simApplyBenchCraft",
)


class CMethodParseError(ValueError):
    """The target assignment contains syntax outside the offline reader's subset."""


@dataclass(frozen=True)
class UnresolvedReference:
    """A dotted JavaScript identifier deliberately retained without evaluation."""

    expression: str


@dataclass(frozen=True)
class ObjectEntry:
    key: str
    value: "Value"
    position: int
    line: int


@dataclass(frozen=True)
class JsObject:
    entries: tuple[ObjectEntry, ...]

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and any(entry.key == key for entry in self.entries)

    def __getitem__(self, key: str) -> "Value":
        for entry in self.entries:
            if entry.key == key:
                return entry.value
        raise KeyError(key)

    def get(self, key: str, default: "Value | None" = None) -> "Value | None":
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self) -> Iterator[str]:
        return (entry.key for entry in self.entries)


Value = str | int | float | bool | None | UnresolvedReference | JsObject | tuple["Value", ...]


class _LiteralParser:
    def __init__(self, source: str, position: int) -> None:
        self.source = source
        self.position = position

    def parse_value(self) -> Value:
        self._skip_whitespace()
        if self.position >= len(self.source):
            self._error("unexpected end of input while reading a value")

        character = self.source[self.position]
        if character == "{":
            return self._parse_object()
        if character == "[":
            return self._parse_array()
        if character in "\"'":
            return self._parse_string()
        if self.source.startswith("!0", self.position):
            self.position += 2
            return True
        if self.source.startswith("!1", self.position):
            self.position += 2
            return False
        if self._is_word_boundary_after("null"):
            self.position += 4
            return None
        if character == "-" or character.isdigit():
            return self._parse_number()
        if character.isalpha() or character in "_$":
            return self._parse_dotted_reference()
        self._error(f"unsupported value starting with {character!r}")

    def _parse_object(self) -> JsObject:
        self._expect("{")
        entries: list[ObjectEntry] = []
        self._skip_whitespace()
        if self._consume("}"):
            return JsObject(tuple(entries))

        while True:
            self._skip_whitespace()
            key_position = self.position
            if self.position >= len(self.source) or self.source[self.position] not in "\"'":
                self._error("object keys must be quoted strings")
            key = self._parse_string()
            self._skip_whitespace()
            self._expect(":")
            value = self.parse_value()
            entries.append(
                ObjectEntry(
                    key=key,
                    value=value,
                    position=key_position,
                    line=self.source.count("\n", 0, key_position) + 1,
                )
            )
            self._skip_whitespace()
            if self._consume("}"):
                return JsObject(tuple(entries))
            self._expect(",")
            self._skip_whitespace()
            if self._consume("}"):
                return JsObject(tuple(entries))

    def _parse_array(self) -> tuple[Value, ...]:
        self._expect("[")
        values: list[Value] = []
        self._skip_whitespace()
        if self._consume("]"):
            return tuple(values)

        while True:
            values.append(self.parse_value())
            self._skip_whitespace()
            if self._consume("]"):
                return tuple(values)
            self._expect(",")
            self._skip_whitespace()
            if self._consume("]"):
                return tuple(values)

    def _parse_string(self) -> str:
        quote = self.source[self.position]
        self.position += 1
        characters: list[str] = []
        escapes = {
            "\"": "\"",
            "'": "'",
            "\\": "\\",
            "/": "/",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
        }
        while self.position < len(self.source):
            character = self.source[self.position]
            self.position += 1
            if character == quote:
                return "".join(characters)
            if character != "\\":
                characters.append(character)
                continue
            if self.position >= len(self.source):
                self._error("unterminated escape sequence")
            escaped = self.source[self.position]
            self.position += 1
            if escaped == "u":
                codepoint = self.source[self.position : self.position + 4]
                if len(codepoint) != 4 or not re.fullmatch(r"[0-9A-Fa-f]{4}", codepoint):
                    self._error("invalid unicode escape")
                characters.append(chr(int(codepoint, 16)))
                self.position += 4
            elif escaped in escapes:
                characters.append(escapes[escaped])
            else:
                self._error(f"unsupported string escape \\{escaped}")
        self._error("unterminated string")

    def _parse_number(self) -> int | float:
        match = re.match(
            r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?",
            self.source[self.position :],
        )
        if match is None:
            self._error("invalid number")
        text = match.group(0)
        self.position += len(text)
        if "." in text or "e" in text.lower():
            return float(text)
        return int(text)

    def _parse_dotted_reference(self) -> UnresolvedReference:
        match = re.match(
            r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+",
            self.source[self.position :],
        )
        if match is None:
            unsupported = re.match(r"[A-Za-z_$][A-Za-z0-9_$]*", self.source[self.position :])
            detail = unsupported.group(0) if unsupported else self.source[self.position]
            self._error(f"unsupported identifier or executable expression {detail!r}")
        expression = match.group(0)
        self.position += len(expression)
        return UnresolvedReference(expression)

    def _is_word_boundary_after(self, word: str) -> bool:
        if not self.source.startswith(word, self.position):
            return False
        end = self.position + len(word)
        return end == len(self.source) or not (
            self.source[end].isalnum() or self.source[end] in "_$"
        )

    def _skip_whitespace(self) -> None:
        while self.position < len(self.source) and self.source[self.position].isspace():
            self.position += 1

    def _consume(self, expected: str) -> bool:
        if self.source.startswith(expected, self.position):
            self.position += len(expected)
            return True
        return False

    def _expect(self, expected: str) -> None:
        if not self._consume(expected):
            found = self.source[self.position] if self.position < len(self.source) else "end of input"
            self._error(f"expected {expected!r}, found {found!r}")

    def _error(self, message: str) -> None:
        line = self.source.count("\n", 0, self.position) + 1
        raise CMethodParseError(f"poec_cmethods parse error at line {line}, offset {self.position}: {message}")


def extract_cmethods(source: str) -> JsObject:
    """Return the one object assigned to ``var poec_cmethods`` in *source*."""

    match = re.search(r"\bvar\s+poec_cmethods\s*=", source)
    if match is None:
        raise CMethodParseError("could not find 'var poec_cmethods=' assignment")
    parser = _LiteralParser(source, match.end())
    value = parser.parse_value()
    if not isinstance(value, JsObject):
        raise CMethodParseError("poec_cmethods assignment must contain an object")
    parser._skip_whitespace()
    parser._expect(";")
    return value


def parse_cmethods_source(source: str) -> JsObject:
    """Compatibility entry point for parsing a source string in tests and callers."""

    return extract_cmethods(source)


@dataclass(frozen=True)
class OptionInventory:
    id: Value | None
    default: Value | None
    choices: tuple[Value, ...]


@dataclass(frozen=True)
class MethodNode:
    path: str
    name: str
    subset: str
    subsim: Value | None
    required: Value | None
    cannot: Value | None
    nosim: Value | None
    options: tuple[OptionInventory, ...]
    line: int


@dataclass(frozen=True)
class Inventory:
    nodes: tuple[MethodNode, ...]
    total_nodes: int
    leaf_nodes: int
    custom_subsets: int
    option_count: int
    choice_count: int
    declaration_lines: tuple[tuple[str, int | None], ...]
    source_sha256: str


def inventory_methods(methods: JsObject, source: str) -> Inventory:
    """Walk named nodes reachable through ``subset`` dictionaries in source order."""

    nodes: list[MethodNode] = []
    leaf_nodes = 0
    custom_subsets = 0
    option_count = 0
    choice_count = 0

    def walk(mapping: JsObject, prefix: tuple[str, ...]) -> None:
        nonlocal leaf_nodes, custom_subsets, option_count, choice_count
        for entry in mapping.entries:
            if not isinstance(entry.value, JsObject):
                continue
            method = entry.value
            path = ".".join((*prefix, entry.key))
            subset_value = method.get("subset")
            if isinstance(subset_value, JsObject):
                subset_marker = "dictionary"
            elif subset_value is None:
                subset_marker = "absent"
            elif isinstance(subset_value, str):
                subset_marker = subset_value
            else:
                subset_marker = _value_text(subset_value)

            options = _inventory_options(method.get("options"))
            option_count += len(options)
            choice_count += sum(len(option.choices) for option in options)
            if subset_marker == "custom":
                custom_subsets += 1
            if not isinstance(subset_value, JsObject):
                leaf_nodes += 1

            name = method.get("name")
            if isinstance(name, str):
                nodes.append(
                    MethodNode(
                        path=path,
                        name=name,
                        subset=subset_marker,
                        subsim=method.get("subsim"),
                        required=method.get("required"),
                        cannot=method.get("cannot"),
                        nosim=method.get("nosim"),
                        options=options,
                        line=entry.line,
                    )
                )
            if isinstance(subset_value, JsObject):
                walk(subset_value, (*prefix, entry.key))

    walk(methods, ())
    declarations = tuple((name, _find_declaration_line(source, name)) for name in DECLARATION_NAMES)
    return Inventory(
        nodes=tuple(nodes),
        total_nodes=len(nodes),
        leaf_nodes=leaf_nodes,
        custom_subsets=custom_subsets,
        option_count=option_count,
        choice_count=choice_count,
        declaration_lines=declarations,
        source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
    )


def _inventory_options(value: Value | None) -> tuple[OptionInventory, ...]:
    if not isinstance(value, tuple):
        return ()
    options: list[OptionInventory] = []
    for option in value:
        if not isinstance(option, JsObject):
            continue
        choices_value = option.get("choices")
        choices: list[Value] = []
        if isinstance(choices_value, tuple):
            for choice in choices_value:
                if isinstance(choice, JsObject) and "value" in choice:
                    choices.append(choice["value"])
        options.append(
            OptionInventory(
                id=option.get("id"),
                default=option.get("default"),
                choices=tuple(choices),
            )
        )
    return tuple(options)


def _find_declaration_line(source: str, name: str) -> int | None:
    patterns = (
        rf"\bfunction\s+{re.escape(name)}\b",
        rf"\b(?:var|let|const)\s+{re.escape(name)}\b",
        rf"\b{re.escape(name)}\s*=\s*function\b",
    )
    positions = [match.start() for pattern in patterns for match in re.finditer(pattern, source)]
    if not positions:
        return None
    return source.count("\n", 0, min(positions)) + 1


def _value_text(value: Value) -> str:
    if isinstance(value, UnresolvedReference):
        return value.expression
    if isinstance(value, JsObject):
        return "{" + ",".join(
            f"{json.dumps(entry.key, ensure_ascii=False)}:{_value_text(entry.value)}"
            for entry in value.entries
        ) + "}"
    if isinstance(value, tuple):
        return "[" + ",".join(_value_text(item) for item in value) + "]"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _cell(value: Value | None) -> str:
    return "absent" if value is None else _markdown_escape(_value_text(value))


def _markdown_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _options_text(options: tuple[OptionInventory, ...]) -> str:
    if not options:
        return "absent"
    rendered = []
    for option in options:
        option_id = _value_text(option.id) if option.id is not None else "absent"
        default = _value_text(option.default) if option.default is not None else "absent"
        choices = ", ".join(_value_text(choice) for choice in option.choices) or "absent"
        rendered.append(f"{option_id} (default {default}; choices {choices})")
    return _markdown_escape("; ".join(rendered))


def render_inventory(inventory: Inventory, source: str, source_path: str) -> str:
    """Render a deterministic Markdown report without descriptions or game-rule claims."""

    command = (
        "python tools/coe_inventory.py --source "
        f"{source_path} --output docs/research/coe-method-inventory.md"
    )
    lines = [
        "# Craft of Exile method inventory (mechanical extraction)",
        "",
        "This is syntax-level evidence from cached CoE application code. It does not approve mechanics, "
        "availability, or a crafting action catalogue.",
        "",
        "| field | value |",
        "| --- | --- |",
        f"| source | `{_markdown_escape(source_path)}` |",
        f"| source SHA-256 | `{inventory.source_sha256}` |",
        f"| extraction command | `{_markdown_escape(command)}` |",
        f"| total named nodes | {inventory.total_nodes} |",
        f"| leaf nodes | {inventory.leaf_nodes} |",
        f"| custom subsets | {inventory.custom_subsets} |",
        f"| options | {inventory.option_count} |",
        f"| option choices | {inventory.choice_count} |",
        "",
        "## Named method nodes",
        "",
        "`required`, `cannot`, and `nosim` are local fields only. `absent` means no local field was present; "
        "the report makes no inherited-availability claim.",
        "",
        "| key path | name | subset | subsim | required | cannot | nosim | options | source line |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for node in inventory.nodes:
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_escape(node.path),
                    _markdown_escape(node.name),
                    _markdown_escape(node.subset),
                    _cell(node.subsim),
                    _cell(node.required),
                    _cell(node.cannot),
                    _cell(node.nosim),
                    _options_text(node.options),
                    f"`{_markdown_escape(source_path)}:{node.line}`",
                )
            )
            + " |"
        )

    lines.extend(
        (
            "",
            "## Requested declaration anchors",
            "",
            "This table records declaration locations only; it does not infer a call graph.",
            "",
            "| name | declaration line |",
            "| --- | --- |",
        )
    )
    for name, line in inventory.declaration_lines:
        value = "absent" if line is None else str(line)
        lines.append(f"| {name} | {value} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="cached CoE package.js")
    parser.add_argument("--output", type=Path, required=True, help="Markdown inventory destination")
    args = parser.parse_args()

    source = args.source.read_text(encoding="utf-8")
    inventory = inventory_methods(extract_cmethods(source), source)
    report = render_inventory(inventory, source, args.source.as_posix())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
