"""Validated item targets and economic inputs for the prototype planner.

Input facts are supplied by the item-spec and loadout files. Modifier identity
is checked against the caller's accepted PoB rows (S24); bench-price examples
carry their own cited input sources. YAML-named specs deliberately accept only
the JSON-compatible YAML subset, parsed by :mod:`json`.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_VERSION = 1
_FLAGS = (
    "corrupted",
    "influenced",
    "fractured",
    "synthesised",
    "mirrored",
    "split",
)
_SUPPORTED_ACTIONS = frozenset(
    (
        "transmute",
        "alteration",
        "augmentation",
        "regal",
        "alchemy",
        "chaos",
        "exalted",
        "annul",
        "scour",
        "essence",
        "bench",
        "harvest_reforge:fire",
        "harvest_reforge:cold",
        "harvest_reforge:lightning",
        "harvest_reforge:physical",
        "harvest_reforge:life",
        "harvest_reforge:defence",
        "harvest_reforge:chaos",
        "harvest_reforge:attack",
        "harvest_reforge:caster",
        "harvest_reforge:speed",
        "harvest_reforge:critical",
        "harvest_reforge:minion",
        "harvest_reforge:elemental",
        "harvest_reforge:attribute",
        "harvest_reforge:mana",
        "fossil",
    )
)
_ESSENCE_ID_PREFIX = "Metadata/Items/Currency/"

_SPEC_REQUIRED_KEYS = {
    "schema_version",
    "name",
    "base",
    "item_level",
    "quality",
    "tier_ids",
    "sources",
}
_SPEC_KEYS = _SPEC_REQUIRED_KEYS | {
    "flags",
    "required_mods",
    "any_of",
    "value_table",
    "threshold",
    "values_note",
}
_LOADOUT_REQUIRED_KEYS = {
    "schema_version",
    "name",
    "allowed_actions",
    "allowed_essences",
    "allowed_bench",
    "prices_file",
    "budget",
    "base_cost",
}
_LOADOUT_KEYS = _LOADOUT_REQUIRED_KEYS | {"allowed_fossils"}
_SUPPORTED_FOSSIL_IDS = frozenset((1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 21, 22, 23))
_PRICE_KEYS = {
    "schema_version",
    "unit",
    "values",
    "bench_recipes",
    "note",
    "sources",
}


@dataclass(frozen=True)
class Criterion:
    """One requested PoB modifier group and the worst allowed tier number."""

    group: str
    max_tier: int


@dataclass(frozen=True)
class ItemSpec:
    """An explicit predicate target or additive caller-supplied utility target."""

    schema_version: int
    name: str
    base: str
    item_level: int
    quality: int
    flags: dict[str, bool]
    tier_ids: dict[str, tuple[tuple[str, ...], ...]]
    required_mods: tuple[Criterion, ...]
    any_of: tuple[tuple[Criterion, ...], ...]
    value_table: dict[str, dict[int, float]] | None
    threshold: float | None
    values_note: str | None
    sources: tuple[str, ...]
    labels: dict[str, str]

    def matches(self, outcome: object) -> bool:
        """Return whether an engine outcome satisfies this spec's stop rule."""
        if self.value_table is not None:
            assert self.threshold is not None
            return self.utility(outcome) >= self.threshold
        tiers = _outcome_tiers(outcome)
        return all(_criterion_matches(tiers, criterion) for criterion in self.required_mods) and all(
            any(_criterion_matches(tiers, criterion) for criterion in alternatives)
            for alternatives in self.any_of
        )

    def utility(self, outcome: object) -> float:
        """Return table utility (an omitted tier is 0), or a 0/1 predicate utility."""
        if self.value_table is None:
            return float(self.matches(outcome))
        tiers = _outcome_tiers(outcome)
        return sum(
            values.get(tier, 0.0)
            for group, tier in tiers.items()
            if (values := self.value_table.get(group)) is not None
        )


@dataclass(frozen=True)
class Loadout:
    """Allowed prototype actions together with user-provided currency prices."""

    schema_version: int
    name: str
    allowed_actions: frozenset[str]
    allowed_essences: frozenset[str]
    allowed_bench: frozenset[int]
    prices_file: Path
    budget: float
    base_cost: float
    unit: str
    values: dict[str, float]
    bench_recipes: dict[int, dict[str, float]]
    note: str
    sources: tuple[str, ...]
    allowed_fossils: frozenset[int] = frozenset()

    def price(self, currency: str) -> float:
        """Return a quoted input price; an absent quote is always an error."""
        if not isinstance(currency, str) or not currency:
            raise ValueError("currency must be a non-empty string")
        try:
            return self.values[currency]
        except KeyError as exc:
            raise ValueError(f"missing price for currency: {currency}") from exc

    def bench_cost(self, index: int) -> float:
        """Return one bench recipe's cost using the same input price table."""
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValueError("bench index must be an integer")
        try:
            recipe = self.bench_recipes[index]
        except KeyError as exc:
            raise ValueError(f"missing bench recipe: {index}") from exc
        return sum(quantity * self.price(currency) for currency, quantity in recipe.items())

    def permits(
        self,
        actions: str | Iterable[str],
        essence_id: str | None = None,
        bench_index: int | None = None,
    ) -> bool:
        """Check explicit permission only; prices never imply an action is allowed."""
        requested = _action_sequence(actions)
        if not all(action in self.allowed_actions for action in requested):
            return False
        if essence_id is not None:
            if "essence" not in requested or essence_id not in self.allowed_essences:
                return False
        if bench_index is not None:
            if "bench" not in requested or bench_index not in self.allowed_bench:
                return False
        return True


def load_spec(path: str | Path, mod_rows: Mapping[str, Mapping[str, Any]]) -> ItemSpec:
    """Load a JSON-compatible YAML/JSON item specification under this repository."""
    if not isinstance(mod_rows, Mapping):
        raise ValueError("mod_rows must map modifier ids to source rows")
    resolved_path = _resolve_under_root(path, _REPOSITORY_ROOT)
    document = _read_json(resolved_path, "item spec")
    _exact_document_keys(document, _SPEC_REQUIRED_KEYS, _SPEC_KEYS, "item spec")
    _schema_version(document, "item spec")

    name = _nonempty_string(document["name"], "item spec name")
    base = _nonempty_string(document["base"], "item spec base")
    item_level = _positive_integer(document["item_level"], "item_level")
    quality = _nonnegative_integer(document["quality"], "quality")
    flags = _parse_flags(document.get("flags"))
    tier_ids, labels = _parse_tier_ids(document["tier_ids"], mod_rows)
    sources = _string_list(document["sources"], "sources", require_nonempty=True)

    criteria_mode = "required_mods" in document or "any_of" in document
    value_mode = any(key in document for key in ("value_table", "threshold", "values_note"))
    if criteria_mode and value_mode:
        raise ValueError("target mode cannot mix criteria and value_table")
    if not criteria_mode and not value_mode:
        raise ValueError("item spec needs a criteria target or value_table target")

    if criteria_mode:
        required_mods = _parse_criteria_list(
            document.get("required_mods", []), tier_ids, "required_mods"
        )
        any_of = _parse_any_of(document.get("any_of", []), tier_ids)
        if not required_mods and not any_of:
            raise ValueError("item spec target must not be empty")
        return ItemSpec(
            _SCHEMA_VERSION,
            name,
            base,
            item_level,
            quality,
            flags,
            tier_ids,
            required_mods,
            any_of,
            None,
            None,
            None,
            sources,
            labels,
        )

    missing = {"value_table", "threshold", "values_note"} - document.keys()
    if missing:
        raise ValueError(f"value_table target missing fields: {', '.join(sorted(missing))}")
    value_table = _parse_value_table(document["value_table"], tier_ids)
    threshold = _finite_number(document["threshold"], "threshold")
    values_note = _nonempty_string(document["values_note"], "values_note")
    return ItemSpec(
        _SCHEMA_VERSION,
        name,
        base,
        item_level,
        quality,
        flags,
        tier_ids,
        (),
        (),
        value_table,
        threshold,
        values_note,
        sources,
        labels,
    )


def load_loadout(path: str | Path) -> Loadout:
    """Load a loadout and its relative price file without leaving the repository."""
    resolved_path = _resolve_under_root(path, _REPOSITORY_ROOT)
    document = _read_json(resolved_path, "loadout")
    _exact_document_keys(document, _LOADOUT_REQUIRED_KEYS, _LOADOUT_KEYS, "loadout")
    _schema_version(document, "loadout")

    name = _nonempty_string(document["name"], "loadout name")
    allowed_actions = frozenset(_allowed_actions(document["allowed_actions"]))
    allowed_essences = frozenset(_essence_ids(document["allowed_essences"]))
    allowed_bench = frozenset(_bench_indices(document["allowed_bench"]))
    allowed_fossils = frozenset(_allowed_fossils(document.get("allowed_fossils", [])))
    prices_file_name = _nonempty_string(document["prices_file"], "prices_file")
    prices_file = _resolve_under_root(prices_file_name, resolved_path.parent)
    budget = _finite_nonnegative(document["budget"], "budget")
    base_cost = _finite_nonnegative(document["base_cost"], "base_cost")

    prices = _read_json(prices_file, "price data")
    _exact_document_keys(prices, _PRICE_KEYS, _PRICE_KEYS, "price data")
    _schema_version(prices, "price data")
    unit = _nonempty_string(prices["unit"], "price unit")
    values = _currency_values(prices["values"])
    bench_recipes = _bench_recipes(prices["bench_recipes"], values)
    note = _nonempty_string(prices["note"], "price note")
    sources = _string_list(prices["sources"], "price sources", require_nonempty=True)
    return Loadout(
        _SCHEMA_VERSION,
        name,
        allowed_actions,
        allowed_essences,
        allowed_bench,
        prices_file,
        budget,
        base_cost,
        unit,
        values,
        bench_recipes,
        note,
        sources,
        allowed_fossils,
    )


def _resolve_under_root(path: str | Path, relative_to: Path) -> Path:
    if not isinstance(path, (str, Path)):
        raise ValueError("input path must be a string or Path")
    raw_path = Path(path)
    candidate = raw_path if raw_path.is_absolute() else relative_to / raw_path
    lexical = Path(os.path.normpath(candidate))
    try:
        lexical.relative_to(_REPOSITORY_ROOT)
    except ValueError as exc:
        raise ValueError("input path escapes the repository root") from exc
    try:
        resolved = lexical.resolve(strict=False)
    except OSError as exc:
        raise ValueError(f"unable to resolve input path: {candidate}") from exc
    try:
        resolved.relative_to(_REPOSITORY_ROOT)
    except ValueError as exc:
        raise ValueError("input path escapes the repository root") from exc
    return resolved


def _read_json(path: Path, kind: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"unable to read {kind}: {path}") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        if path.suffix.lower() == ".yaml":
            raise ValueError(
                "JSON-compatible YAML only; unsupported YAML feature or invalid JSON"
            ) from exc
        raise ValueError(f"invalid JSON {kind}: {path}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"{kind} must be a JSON object")
    return document


def _exact_document_keys(
    document: Mapping[str, Any], required: set[str], allowed: set[str], name: str
) -> None:
    missing = required - document.keys()
    unknown = document.keys() - allowed
    if missing:
        raise ValueError(f"{name} missing keys: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"{name} has unknown top-level keys: {', '.join(sorted(unknown))}")


def _schema_version(document: Mapping[str, Any], name: str) -> None:
    version = document["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != _SCHEMA_VERSION:
        raise ValueError(f"unsupported {name} schema_version: {version!r}")


def _nonempty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _positive_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _nonnegative_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _finite_nonnegative(value: object, name: str) -> float:
    value = _finite_number(value, name)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _string_list(value: object, name: str, *, require_nonempty: bool) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list of strings")
    result = tuple(_nonempty_string(item, name) for item in value)
    if require_nonempty and not result:
        raise ValueError(f"{name} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _parse_flags(value: object) -> dict[str, bool]:
    if value is None:
        return {flag: False for flag in _FLAGS}
    if not isinstance(value, Mapping):
        raise ValueError("flags must be an object")
    unknown = value.keys() - set(_FLAGS)
    if unknown:
        raise ValueError(f"unsupported flags: {', '.join(sorted(unknown))}")
    flags = {flag: False for flag in _FLAGS}
    for flag, enabled in value.items():
        if not isinstance(enabled, bool):
            raise ValueError(f"flag {flag} must be boolean")
        flags[flag] = enabled
    if any(flags.values()):
        raise NotImplementedError("out of tonight's slice: Q9")
    return flags


def _parse_tier_ids(
    value: object, mod_rows: Mapping[str, Mapping[str, Any]]
) -> tuple[dict[str, tuple[tuple[str, ...], ...]], dict[str, str]]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("tier_ids must be a non-empty object")
    result: dict[str, tuple[tuple[str, ...], ...]] = {}
    labels: dict[str, str] = {}
    seen_ids: set[str] = set()
    for group, raw_tiers in value.items():
        group = _nonempty_string(group, "tier_ids group")
        if not isinstance(raw_tiers, list) or not raw_tiers:
            raise ValueError(f"tier_ids[{group}] must be a non-empty list of tier lists")
        tiers: list[tuple[str, ...]] = []
        for tier_number, raw_ids in enumerate(raw_tiers, start=1):
            if not isinstance(raw_ids, list) or not raw_ids:
                raise ValueError(f"tier_ids[{group}] tier {tier_number} must not be empty")
            ids: list[str] = []
            for mod_id in raw_ids:
                mod_id = _nonempty_string(mod_id, "tier modifier id")
                if mod_id in seen_ids:
                    raise ValueError(f"ambiguous tier assignment for mod id: {mod_id}")
                source_row = mod_rows.get(mod_id)
                if not isinstance(source_row, Mapping):
                    raise ValueError(f"unknown mod id: {mod_id}")
                if source_row.get("group") != group:
                    raise ValueError(
                        f"tier id {mod_id} source group does not match tier_ids group {group}"
                    )
                seen_ids.add(mod_id)
                ids.append(mod_id)
                labels[mod_id] = f"{group}:{tier_number}"
            tiers.append(tuple(ids))
        result[group] = tuple(tiers)
    return result, labels


def _parse_criteria_list(
    value: object, tier_ids: Mapping[str, tuple[tuple[str, ...], ...]], name: str
) -> tuple[Criterion, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    result = tuple(_parse_criterion(raw, tier_ids, name) for raw in value)
    groups = [criterion.group for criterion in result]
    if len(set(groups)) != len(groups):
        raise ValueError(f"ambiguous target: repeated group in {name}")
    return result


def _parse_any_of(
    value: object, tier_ids: Mapping[str, tuple[tuple[str, ...], ...]]
) -> tuple[tuple[Criterion, ...], ...]:
    if not isinstance(value, list):
        raise ValueError("any_of must be a list of lists")
    groups_of_alternatives: list[tuple[Criterion, ...]] = []
    for index, raw_alternatives in enumerate(value, start=1):
        criteria = _parse_criteria_list(raw_alternatives, tier_ids, f"any_of[{index}]")
        if not criteria:
            raise ValueError(f"any_of[{index}] must not be empty")
        groups_of_alternatives.append(criteria)
    return tuple(groups_of_alternatives)


def _parse_criterion(
    value: object, tier_ids: Mapping[str, tuple[tuple[str, ...], ...]], name: str
) -> Criterion:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} entries must be objects")
    expected = {"group", "max_tier"}
    if value.keys() != expected:
        raise ValueError(f"{name} entries require exactly group and max_tier")
    group = _nonempty_string(value["group"], f"{name}.group")
    max_tier = _positive_integer(value["max_tier"], f"{name}.max_tier")
    try:
        tiers = tier_ids[group]
    except KeyError as exc:
        raise ValueError(f"unknown tier group in {name}: {group}") from exc
    if max_tier > len(tiers):
        raise ValueError(f"unknown tier {max_tier} for group {group}")
    return Criterion(group, max_tier)


def _parse_value_table(
    value: object, tier_ids: Mapping[str, tuple[tuple[str, ...], ...]]
) -> dict[str, dict[int, float]]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("value_table must be a non-empty object")
    result: dict[str, dict[int, float]] = {}
    for group, raw_values in value.items():
        group = _nonempty_string(group, "value_table group")
        if group not in tier_ids:
            raise ValueError(f"unknown tier group in value_table: {group}")
        if not isinstance(raw_values, Mapping) or not raw_values:
            raise ValueError(f"value_table[{group}] must be a non-empty object")
        tier_values: dict[int, float] = {}
        for raw_tier, raw_number in raw_values.items():
            if not isinstance(raw_tier, str) or not raw_tier:
                raise ValueError(f"value_table[{group}] tiers must be integer strings")
            try:
                tier = int(raw_tier)
            except ValueError as exc:
                raise ValueError(f"value_table[{group}] tiers must be integer strings") from exc
            if str(tier) != raw_tier or tier <= 0:
                raise ValueError(f"value_table[{group}] tiers must be positive integer strings")
            if tier > len(tier_ids[group]):
                raise ValueError(f"unknown tier {tier} for group {group}")
            tier_values[tier] = _finite_number(raw_number, f"value_table[{group}][{raw_tier}]")
        result[group] = tier_values
    return result


def _outcome_tiers(outcome: object) -> dict[str, int]:
    try:
        labels = outcome.labels  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise ValueError("outcome must expose labels") from exc
    result: dict[str, int] = {}
    if isinstance(labels, Mapping):
        items = labels.items()
        for group, tier in items:
            group = _nonempty_string(group, "outcome label group")
            tier = _positive_integer(tier, f"outcome label tier for {group}")
            result[group] = min(result.get(group, tier), tier)
        return result
    if isinstance(labels, str):
        raise ValueError("outcome labels must be an iterable of group:tier strings")
    try:
        raw_labels = tuple(labels)
    except TypeError as exc:
        raise ValueError("outcome labels must be an iterable of group:tier strings") from exc
    for label in raw_labels:
        if not isinstance(label, str):
            raise ValueError("outcome labels must be group:tier strings")
        group, separator, raw_tier = label.rpartition(":")
        if not separator or not group or not raw_tier:
            raise ValueError(f"invalid outcome label: {label!r}")
        try:
            tier = int(raw_tier)
        except ValueError as exc:
            raise ValueError(f"invalid outcome label: {label!r}") from exc
        if str(tier) != raw_tier or tier <= 0:
            raise ValueError(f"invalid outcome label: {label!r}")
        result[group] = min(result.get(group, tier), tier)
    return result


def _criterion_matches(tiers: Mapping[str, int], criterion: Criterion) -> bool:
    tier = tiers.get(criterion.group)
    return tier is not None and tier <= criterion.max_tier


def _action_sequence(actions: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(actions, str):
        result = (actions,)
    else:
        try:
            result = tuple(actions)
        except TypeError as exc:
            raise ValueError("actions must be a string or iterable of strings") from exc
    if not result or any(not isinstance(action, str) or not action for action in result):
        raise ValueError("actions must contain non-empty strings")
    return result


def _allowed_actions(value: object) -> tuple[str, ...]:
    actions = _string_list(value, "allowed_actions", require_nonempty=False)
    unknown = set(actions) - _SUPPORTED_ACTIONS
    if unknown:
        raise ValueError(f"unsupported actions: {', '.join(sorted(unknown))}")
    return actions


def _essence_ids(value: object) -> tuple[str, ...]:
    result = _string_list(value, "allowed_essences", require_nonempty=False)
    if any(not essence_id.startswith(_ESSENCE_ID_PREFIX) for essence_id in result):
        raise ValueError("allowed_essences must use full Metadata/Items/Currency IDs")
    return result


def _bench_indices(value: object) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError("allowed_bench must be a list of integers")
    result = tuple(_positive_integer(index, "allowed_bench index") for index in value)
    if len(set(result)) != len(result):
        raise ValueError("allowed_bench must not contain duplicates")
    return result


def _allowed_fossils(value: object) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError("allowed_fossils must be a list of supported integer IDs")
    if len(value) > 4:
        raise ValueError("allowed_fossils supports at most four fossils")
    result = tuple(_positive_integer(fossil, "allowed_fossils id") for fossil in value)
    if len(set(result)) != len(result):
        raise ValueError("allowed_fossils must not contain duplicates")
    unsupported = set(result) - _SUPPORTED_FOSSIL_IDS
    if unsupported:
        raise ValueError(f"allowed_fossils has unsupported special or unknown IDs: {', '.join(str(value) for value in sorted(unsupported))}")
    return result


def _currency_values(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError("price values must be an object")
    return {
        _nonempty_string(currency, "price currency"): _finite_nonnegative(price, f"price {currency}")
        for currency, price in value.items()
    }


def _bench_recipes(value: object, prices: Mapping[str, float]) -> dict[int, dict[str, float]]:
    if not isinstance(value, Mapping):
        raise ValueError("bench_recipes must be an object")
    result: dict[int, dict[str, float]] = {}
    for raw_index, raw_recipe in value.items():
        if not isinstance(raw_index, str) or not raw_index:
            raise ValueError("bench_recipes keys must be source_index strings")
        try:
            index = int(raw_index)
        except ValueError as exc:
            raise ValueError("bench_recipes keys must be source_index strings") from exc
        if str(index) != raw_index or index <= 0:
            raise ValueError("bench_recipes keys must be positive source_index strings")
        if index in result:
            raise ValueError(f"duplicate bench recipe: {index}")
        if not isinstance(raw_recipe, Mapping) or not raw_recipe:
            raise ValueError(f"bench recipe {index} must be a non-empty currency map")
        recipe: dict[str, float] = {}
        for currency, quantity in raw_recipe.items():
            currency = _nonempty_string(currency, f"bench recipe {index} currency")
            if currency not in prices:
                raise ValueError(f"bench recipe {index} uses missing price currency: {currency}")
            recipe[currency] = _finite_nonnegative(quantity, f"bench recipe {index} quantity")
        result[index] = recipe
    return result
