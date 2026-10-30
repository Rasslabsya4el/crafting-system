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
`get_rule` must be called by that name, with exactly one argument.
"""

import re
from collections.abc import Mapping
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
PATCH_PATTERN = re.compile(r"\d+(\.\d+){2,3}[a-z]?")
MAX_QUOTE_LENGTH = 400
URL_PREFIXES = ("https://", "http://")
CLAIMS_SUFFIX = ".yaml"


class RegistryError(ValueError):
    """A claims file or the claims folder is not valid."""


class UnknownRuleError(KeyError):
    """Code asked for a rule id that is not in the registry."""


class SourceKind(StrEnum):
    """What kind of source admits a rule (GLOSSARY: Source kind)."""

    OFFICIAL = "official"
    WIKI = "wiki"
    DATAMINED = "datamined"
    EXPERIMENT = "experiment"  # large-sample experiment
    COE = "coe"  # Craft of Exile
    OWNER = "owner"


@dataclass(frozen=True)
class Rule:
    """One admitted claim. `value` is the number or structure that code reads, if the claim has one."""

    id: str
    statement: str
    source_kind: SourceKind
    url: str
    quote: str
    patch_verified: str
    date_checked: date
    value: Any = None


REQUIRED_FIELDS = (
    "id", "statement", "source_kind", "url", "quote", "patch_verified", "date_checked",
)  # fmt: skip
ALLOWED_FIELDS = (*REQUIRED_FIELDS, "value")


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
    if not isinstance(value, str) or not value.startswith(URL_PREFIXES):
        return f"url must be a string starting with https:// or http://, got {value!r}"
    return None


def _check_patch(value: object) -> str | None:
    if isinstance(value, float):
        return f"patch_verified {value!r} was read as a number; quote it, like \"{value}\""
    if not isinstance(value, str) or not PATCH_PATTERN.fullmatch(value):
        return f"patch_verified must be a quoted patch like \"3.29.3.3\", got {value!r}"
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


def _parse_entry(entry: object, number: int, file_name: str, seen: set[str]) -> Rule:
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
    if problem is not None:
        raise fail(problem)
    if entry["id"] in seen:
        raise fail("duplicate id, it is already used by an earlier entry")
    seen.add(entry["id"])
    return Rule(**{**entry, "source_kind": SourceKind(entry["source_kind"])})


def _parse_file(text: str, file_name: str, seen: set[str]) -> list[Rule]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise RegistryError(f"{file_name}: invalid YAML: {error}") from error
    if not isinstance(data, dict) or "rules" not in data:
        raise RegistryError(f"{file_name}: the top level must be a mapping with a `rules` key")
    if set(data) != {"rules"}:
        extra = sorted(str(key) for key in data if key != "rules")
        raise RegistryError(f"{file_name}: unknown top-level key {', '.join(extra)}")
    if not isinstance(data["rules"], list) or not data["rules"]:
        raise RegistryError(f"{file_name}: `rules` must be a non-empty list")
    return [
        _parse_entry(entry, number, file_name, seen)
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
    try:
        return _default_registry()[rule_id]
    except KeyError:
        raise UnknownRuleError(f"unknown rule id {rule_id!r}") from None
