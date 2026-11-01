"""The mechanics rules registry: every admitted claim with its provenance (ADR-0004).

The claims live in YAML files in the `claims` folder next to this module, one file per mechanic
family (`affix_count.yaml`, `fossils.yaml`, ...). Each entry has an id of the form
`<family>.<name>`, both parts lowercase snake_case, where `<family>` is the file name without
`.yaml`. ("Family" is this project's word for what the wiki calls a mod "group".)

Code refers to a rule by calling `get_rule` with the id as a string literal, usually as a
module-level constant:

    FAMILY_EXCLUSION = get_rule("affix_draw.family_exclusion")

The id is a literal on purpose: a test reads the source of the whole package and checks every
`get_rule(...)` argument against the registry without running the code, so a reference to an
unregistered claim fails the build. The same call also fails at import time. For the same reason
`get_rule` must be called by that name, with exactly one argument. Code that holds an id in a variable
(the approximate inputs of an answer, ADR-0028) asks `rule_by_id` instead, which the check does not read.

A claim may carry two optional fields beyond its provenance (ADR-0028):

    approximate: true
    approximate_reason: "Only Craft of Exile's code gives this count."

`approximate` is exactly `true` or absent (`false` is refused: a claim that is not approximate says
nothing); it marks a claim that no other source settles, and every answer that reads it names it.
`approximate_reason` is a non-empty one-line string, required with `approximate: true` and refused
without it. They are the model's uncertainty, not the certified gap of ADR-0023.
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import cache
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

ID_PATTERN = re.compile(r"([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)")
PATCH_PATTERN = re.compile(r"[0-9]+(\.[0-9]+){2,3}[a-z]?")
MAX_QUOTE_LENGTH = 400
URL_PATTERN = re.compile(r"https?://\S+")  # a scheme, then something, and no whitespace
CLAIMS_SUFFIX = ".yaml"


class RegistryError(ValueError):
    """A claims file or the claims folder is not valid."""


class UnknownRuleError(KeyError):
    """Code asked for a rule id that is not in the registry."""


class FrozenMap(Mapping):
    """A read-only, hashable mapping: the form a YAML mapping takes in `Rule.value`."""

    def __init__(self, items: Mapping) -> None:
        self._items = dict(items)

    def __getitem__(self, key: Any) -> Any:
        return self._items[key]

    def __iter__(self) -> Iterator:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __hash__(self) -> int:
        return hash(frozenset(self._items.items()))

    def __repr__(self) -> str:
        return f"FrozenMap({self._items!r})"


def _freeze(value: Any) -> Any:
    """Mappings become `FrozenMap`, lists tuples and sets frozensets, all the way down."""
    if isinstance(value, dict):
        return FrozenMap({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


class _UniqueKeyLoader(yaml.SafeLoader):
    """`safe_load` that refuses a mapping with a repeated key instead of keeping the last one."""

    def __init__(self, stream) -> None:  # noqa: ANN001
        super().__init__(stream)
        self.nodes: dict[int, yaml.MappingNode] = {}

    def construct_mapping(self, node, deep=False):  # noqa: ANN001
        if isinstance(node, yaml.MappingNode):
            seen = set()
            for key_node, _ in node.value:
                key = self.construct_object(key_node, deep=True)
                try:
                    repeated = key in seen
                    seen.add(key)
                except TypeError:  # an unhashable key: the parent class reports it
                    break
                if repeated:
                    raise yaml.constructor.ConstructorError(
                        None, None, f"duplicate key {key!r}", key_node.start_mark
                    )
        return super().construct_mapping(node, deep)

    def construct_yaml_map(self, node):  # noqa: ANN001, ANN201
        for data in super().construct_yaml_map(node):
            self.nodes[id(data)] = node  # the parsed dict is alive as long as the document is
            yield data


_UniqueKeyLoader.add_constructor("tag:yaml.org,2002:map", _UniqueKeyLoader.construct_yaml_map)


class _Lines:
    """Where in the file a parsed mapping, and each of its keys, stands (1-based line numbers)."""

    def __init__(self, nodes: dict[int, yaml.MappingNode]) -> None:
        self._nodes = nodes

    def of(self, mapping: object, key: str | None = None) -> str:
        """` (line N)` for the mapping, or for its key `key`; empty when the place is unknown."""
        node = self._nodes.get(id(mapping))
        if node is None:
            return ""
        if key is not None:
            for key_node, _ in node.value:
                if getattr(key_node, "value", None) == key:
                    return f" (line {key_node.start_mark.line + 1})"
        return f" (line {node.start_mark.line + 1})"


class SourceKind(StrEnum):
    """What kind of source admits a rule (GLOSSARY: Source kind)."""

    OFFICIAL = "official"
    WIKI = "wiki"
    DATAMINED = "datamined"
    EXPERIMENT = "experiment"  # large-sample experiment
    COE = "coe"  # Craft of Exile
    OWNER = "owner"


@dataclass(frozen=True)
class HistoryEntry:
    """What a claim said before a patch changed it, and the source that showed the change.

    `held_until` is the last patch the old `statement` or `value` was verified on (the claim's own
    `patch_verified` before the change). At least one of `statement` and `value` is given. Code
    reads `Rule.value`, never a history entry: history is for the people who trace a changed rule.
    """

    held_until: str
    source_kind: SourceKind
    url: str
    quote: str
    statement: str | None = None
    value: Any = None


@dataclass(frozen=True)
class Rule:
    """One admitted claim. `value` is the number or structure that code reads, if the claim has one.

    The value is frozen on load (mappings read-only, lists tuples), so a rule is hashable and the
    cached registry cannot be changed by the code that reads it. `history` lists the earlier
    versions of the claim, oldest first (empty for a claim that never changed). `approximate` marks a
    claim that no other source settles, with the one-line `approximate_reason` (ADR-0028).
    """

    id: str
    statement: str
    source_kind: SourceKind
    url: str
    quote: str
    patch_verified: str
    date_checked: date
    value: Any = None
    history: tuple[HistoryEntry, ...] = ()
    approximate: bool = False
    approximate_reason: str = ""


REQUIRED_FIELDS = (
    "id", "statement", "source_kind", "url", "quote", "patch_verified", "date_checked",
)  # fmt: skip
ALLOWED_FIELDS = (*REQUIRED_FIELDS, "value", "history", "approximate", "approximate_reason")
HISTORY_REQUIRED_FIELDS = ("held_until", "source_kind", "url", "quote")
HISTORY_FIELDS = (*HISTORY_REQUIRED_FIELDS, "statement", "value")


def patch_order_key(patch: str) -> tuple[tuple[int, ...], str]:
    """Sort key of a patch name: `3.29.3` and `3.29.3.0` are the same patch, `3.29.3.3a` follows `3.29.3.3`."""
    number = patch[:-1] if patch[-1].isalpha() else patch
    numbers = [int(part) for part in number.split(".")]
    return tuple(numbers + [0] * (4 - len(numbers))), patch[len(number):]


def _check_text(field: str, value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"{field} must be a non-empty string"
    if field == "quote" and len(value) > MAX_QUOTE_LENGTH:
        return f"quote must be a short quote of at most {MAX_QUOTE_LENGTH} characters, got {len(value)}"
    return None


def _check_source_kind(value: object) -> str | None:
    allowed = [kind.value for kind in SourceKind]
    if not isinstance(value, str) or value not in allowed:
        return f"source_kind must be one of {', '.join(allowed)}, got {value!r}"
    return None


def _check_url(value: object) -> str | None:
    if not isinstance(value, str) or not URL_PATTERN.fullmatch(value):
        return f"url must start with https:// or http://, continue after it, and hold no whitespace, got {value!r}"
    return None


def _check_patch(value: object, field: str = "patch_verified") -> str | None:
    if isinstance(value, float):
        return f"{field} {value!r} was read as a number; quote it, like \"{value}\""
    if not isinstance(value, str) or not PATCH_PATTERN.fullmatch(value):
        return f"{field} must be a quoted patch like \"3.29.3.3\", got {value!r}"
    return None


def _check_date(value: object) -> str | None:
    if type(value) is not date:  # a datetime is a date subclass, and not accepted
        return f"date_checked must be an unquoted YYYY-MM-DD date, got {value!r}"
    return None


_CHECKS = {
    "statement": lambda value: _check_text("statement", value),
    "quote": lambda value: _check_text("quote", value),
    "source_kind": _check_source_kind,
    "url": _check_url,
    "patch_verified": _check_patch,
    "date_checked": _check_date,
}


def _check_id(value: object, family: str) -> str | None:
    match = ID_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        return f"id must look like <family>.<name> in lowercase snake_case, got {value!r}"
    if match.group(1) != family:
        return f"id family {match.group(1)!r} must equal the file name {family + CLAIMS_SUFFIX!r}"
    return None


def _check_approximate(entry: dict) -> str | None:
    """The problem with the `approximate` / `approximate_reason` pair of a claim, or None."""
    if "approximate" not in entry:
        if "approximate_reason" in entry:
            return "approximate_reason is allowed only with approximate: true"
        return None
    if entry["approximate"] is not True:
        return f"approximate must be true when present (leave it out for a claim that is not approximate), got {entry['approximate']!r}"
    if "approximate_reason" not in entry:
        return "approximate: true needs an approximate_reason, one line on why no other source settles the claim"
    reason = entry["approximate_reason"]
    if not isinstance(reason, str) or not reason.strip():
        return "approximate_reason must be a non-empty string"
    if "\n" in reason or "\r" in reason:
        return "approximate_reason must be one line, with no newline"
    return None


def _parse_history(
    history: object, patch_verified: str, where: str, entry: dict, lines: _Lines
) -> tuple[HistoryEntry, ...]:
    """The `history` list of one claim; every problem names the file, the claim and the line."""
    if not isinstance(history, list) or not history:
        raise RegistryError(
            f"{where}: history{lines.of(entry, 'history')}: history must be a non-empty list of entries"
        )
    parsed: list[HistoryEntry] = []
    for number, item in enumerate(history, start=1):
        if not isinstance(item, dict):
            raise RegistryError(
                f"{where}: history entry #{number}{lines.of(entry, 'history')}: a history entry"
                f" must be a mapping, got {type(item).__name__}"
            )

        def fail(problem: str, key: str | None = None) -> RegistryError:
            return RegistryError(f"{where}: history entry #{number}{lines.of(item, key)}: {problem}")

        unknown = sorted(str(key) for key in item if key not in HISTORY_FIELDS)
        if unknown:
            raise fail(f"unknown key {', '.join(unknown)} (allowed: {', '.join(HISTORY_FIELDS)})")
        for field in HISTORY_REQUIRED_FIELDS:
            if field not in item:
                raise fail(f"missing required field {field}")
        if "statement" not in item and item.get("value") is None:
            raise fail("give the old statement or the old value (or both)")
        checks = {
            "held_until": lambda value: _check_patch(value, "held_until"),
            "source_kind": _check_source_kind,
            "url": _check_url,
            "quote": lambda value: _check_text("quote", value),
        }
        if "statement" in item:
            checks["statement"] = lambda value: _check_text("statement", value)
        for field, check in checks.items():
            problem = check(item[field])
            if problem is not None:
                raise fail(problem, field)
        if parsed and patch_order_key(item["held_until"]) <= patch_order_key(parsed[-1].held_until):
            raise fail(
                f"held_until {item['held_until']} must be later than the entry before it"
                f" ({parsed[-1].held_until}): list the history oldest first",
                "held_until",
            )
        if patch_order_key(item["held_until"]) >= patch_order_key(patch_verified):
            raise fail(
                f"held_until {item['held_until']} must be earlier than the claim's patch_verified"
                f" {patch_verified}: the claim was rewritten after it",
                "held_until",
            )
        parsed.append(
            HistoryEntry(
                held_until=item["held_until"],
                source_kind=SourceKind(item["source_kind"]),
                url=item["url"],
                quote=item["quote"],
                statement=item.get("statement"),
                value=_freeze(item.get("value")),
            )
        )
    return tuple(parsed)


def _parse_entry(
    entry: object, number: int, file_name: str, seen: set[str], lines: _Lines
) -> Rule:
    family = file_name.removesuffix(CLAIMS_SUFFIX)
    where = f"{file_name}: entry #{number}"
    if not isinstance(entry, dict):
        raise RegistryError(f"{where}: an entry must be a mapping, got {type(entry).__name__}")
    if isinstance(entry.get("id"), str):
        where = f"{file_name}: rule {entry['id']}"

    def fail(problem: str) -> RegistryError:
        return RegistryError(f"{where}: {problem}")

    unknown = sorted(str(key) for key in entry if key not in ALLOWED_FIELDS)
    if unknown:
        raise fail(f"unknown key {', '.join(unknown)} (allowed: {', '.join(ALLOWED_FIELDS)})")
    for field in REQUIRED_FIELDS:
        if field not in entry:
            raise fail(f"missing required field {field}")
    problem = _check_id(entry["id"], family)
    if problem is None:
        for field, check in _CHECKS.items():
            problem = check(entry[field])
            if problem is not None:
                break
    if problem is None:
        problem = _check_approximate(entry)
    if problem is not None:
        raise fail(problem)
    if entry["id"] in seen:
        raise fail("duplicate id, it is already used by an earlier entry")
    seen.add(entry["id"])
    fields = {**entry, "source_kind": SourceKind(entry["source_kind"])}
    if "value" in fields:
        fields["value"] = _freeze(fields["value"])
    if "history" in fields:
        fields["history"] = _parse_history(
            fields["history"], entry["patch_verified"], where, entry, lines
        )
    return Rule(**fields)


def _parse_file(text: str, file_name: str, seen: set[str]) -> list[Rule]:
    loader = _UniqueKeyLoader(text)
    try:
        data = loader.get_single_data()
    except (yaml.YAMLError, ValueError) as error:  # ValueError: a date such as 2026-02-30
        raise RegistryError(f"{file_name}: invalid YAML: {error}") from error
    finally:
        loader.dispose()
    if not isinstance(data, dict) or "rules" not in data:
        raise RegistryError(f"{file_name}: the top level must be a mapping with a `rules` key")
    if set(data) != {"rules"}:
        extra = sorted(str(key) for key in data if key != "rules")
        raise RegistryError(f"{file_name}: unknown top-level key {', '.join(extra)}")
    if not isinstance(data["rules"], list) or not data["rules"]:
        raise RegistryError(f"{file_name}: `rules` must be a non-empty list")
    return [
        _parse_entry(entry, number, file_name, seen, _Lines(loader.nodes))
        for number, entry in enumerate(data["rules"], start=1)
    ]


def load_registry(directory: Path | None = None) -> Mapping[str, Rule]:
    """Read and validate every claims file; return a read-only mapping from id to rule.

    Without an argument it reads the claims shipped inside the package (found through
    `importlib.resources`, so it works from an installed wheel). Files are read in name order.
    """
    folder = directory if directory is not None else files("crafting_system.rules") / "claims"
    try:
        children = sorted(folder.iterdir(), key=lambda child: child.name)
    except OSError as error:
        raise RegistryError(f"cannot read the claims folder {folder.name!r}: {error}") from error
    claim_files = [child for child in children if child.is_file()]
    stray = [child.name for child in claim_files if not child.name.endswith(CLAIMS_SUFFIX)]
    if stray:
        raise RegistryError(
            f"the claims folder may hold only {CLAIMS_SUFFIX} files, found: {', '.join(stray)}"
        )
    if not claim_files:
        raise RegistryError(
            f"no {CLAIMS_SUFFIX} files in the claims folder {folder.name!r}"
            " (is the package data missing?)"
        )
    rules: dict[str, Rule] = {}
    seen: set[str] = set()
    for child in claim_files:
        try:
            text = child.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise RegistryError(f"{child.name}: cannot read the file as UTF-8: {error}") from error
        for rule in _parse_file(text, child.name, seen):
            rules[rule.id] = rule
    return MappingProxyType(rules)


@cache
def _default_registry() -> Mapping[str, Rule]:
    return load_registry()


def get_rule(rule_id: str) -> Rule:
    """The rule with this id from the shipped registry (loaded once).

    Call it with a string literal so the static check can read the id; see the module docstring.
    """
    return rule_by_id(rule_id)


def rule_by_id(rule_id: str) -> Rule:
    """The rule with this id, for code that holds the id in a variable (`get_rule` takes a literal only)."""
    try:
        return _default_registry()[rule_id]
    except KeyError:
        raise UnknownRuleError(f"unknown rule id {rule_id!r}") from None
