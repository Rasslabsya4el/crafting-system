"""Sourced ordinary Chaotic-resonator fossil rerolls.

Rules: ``docs/mechanics/fossils_resonators.md`` and
``data/rules/fossils.json`` (S3/S4, read 2026-09-21).  This module only
implements the accepted ordinary weight transform; special fossils stay on
their explicit Q19 path.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import gcd
from pathlib import Path
import json
import random
from types import MappingProxyType
from typing import Mapping, Sequence

from craftoracle.actions import (
    ActionData, _candidate_entries, _caps, _counts,
    _replace_item, _validate_action_data, _validate_item,
)
from craftoracle.distributions import DrawEntry, OutcomeClass, draw_distribution, mixture_distribution
from craftoracle.item_model import ItemState, ModRef


_RULE_PATH = Path(__file__).parents[2] / "data" / "rules" / "fossils.json"
_OUTCOME_METAMODS = frozenset((
    "ItemGenerationCannotChangePrefixes", "ItemGenerationCannotChangeSuffixes",
    "ItemGenerationCannotRollAttackAffixes", "ItemGenerationCannotRollCasterAffixes",
))


@dataclass(frozen=True)
class FossilPlan:
    """Immutable resolved pool for one fossil reroll, including common scale."""

    item: ItemState
    entries: tuple[DrawEntry, ...]
    draw_counts: tuple[tuple[int, int], ...]
    prefix_cap: int
    suffix_cap: int
    labels: Mapping[str, str]
    scale: Fraction
    effective_weights: Mapping[str, Fraction]
    fossils: tuple[int, ...]
    mode: str


def fossil_distribution(
    item: ItemState,
    data: ActionData,
    fossils: Sequence[int],
    labels: Mapping[str, str] | None = None,
    *,
    mode: str = "additive",
    socket_count: int | None = None,
) -> dict[OutcomeClass, float]:
    """Return exact terminal fossil-reroll outcomes for a full resonator."""
    plan = prepare_fossils(item, data, fossils, labels, mode=mode, socket_count=socket_count)
    parts = [
        (weight, draw_distribution(
            plan.entries, draws, plan.labels,
            prefix_cap=plan.prefix_cap, suffix_cap=plan.suffix_cap,
        ))
        for draws, weight in plan.draw_counts
    ]
    return mixture_distribution(parts)


def prepare_fossils(
    item: ItemState,
    data: ActionData,
    fossils: Sequence[int],
    labels: Mapping[str, str] | None = None,
    *,
    mode: str = "additive",
    socket_count: int | None = None,
) -> FossilPlan:
    """Resolve a new immutable pool; mutable ``data`` is never cache-keyed."""
    _validate_action_data(data)
    _validate_item(item, data)
    checked_labels = _checked_labels(labels)
    selected = _validate_selection(fossils, socket_count)
    if mode not in {"additive", "multiplicative"}:
        raise ValueError("fossil mode must be additive or multiplicative")
    if item.rarity != "rare":
        raise ValueError("ordinary Chaotic resonator requires rare item")
    groups = {mod.group for mod in item.mods}
    if groups & _OUTCOME_METAMODS:
        raise ValueError("outcome-affecting metamod prevents fossil use")

    rules = _rules()
    rows = {row["id"]: row for row in rules["ordinary"]}
    unknown = [fossil for fossil in selected if fossil not in rows]
    if unknown:
        raise NotImplementedError(f"unsourced: Q13 fossil id {unknown[0]}")
    candidates = _candidate_entries(item, data, (), (False, False), None)
    rational = {
        entry.mod_id: transformed_weight(
            entry.weight, data.mods[entry.mod_id].get("modTags") or (),
            tuple(rows[fossil] for fossil in selected), mode,
        )
        for entry in candidates
    }
    active = {mod_id: weight for mod_id, weight in rational.items() if weight > 0}
    if not active:
        raise ValueError("unreachable fossil pool: every candidate has zero weight")
    scale, integers = _integer_weights(active)
    entries = tuple(
        DrawEntry(entry.mod_id, entry.type, entry.group, integers[entry.mod_id])
        for entry in candidates if entry.mod_id in integers
    )
    return FossilPlan(
        item, entries, _rare_counts(data), *_caps(data, "rare"), MappingProxyType(dict(checked_labels)),
        scale, MappingProxyType(dict(rational)), selected, mode,
    )


def apply_fossils(
    item: ItemState,
    data: ActionData,
    fossils: Sequence[int],
    rng: random.Random,
    labels: Mapping[str, str] | None = None,
    *,
    mode: str = "additive",
    socket_count: int | None = None,
) -> ItemState:
    """Independently sample a full fossil reroll through the supplied RNG."""
    if not isinstance(rng, random.Random):
        raise ValueError("rng must be random.Random")
    plan = prepare_fossils(item, data, fossils, labels, mode=mode, socket_count=socket_count)
    return sample_fossils(plan, rng)


def sample_fossils(plan: FossilPlan, rng: random.Random) -> ItemState:
    """Sample an already prepared immutable plan with an independent RNG."""
    if not isinstance(plan, FossilPlan):
        raise ValueError("plan must be a FossilPlan")
    if not isinstance(rng, random.Random):
        raise ValueError("rng must be random.Random")
    target = _weighted_choice(plan.draw_counts, rng)
    current: list[ModRef] = []
    while len(current) < target:
        prefixes, suffixes = _counts(current)
        occupied = {mod.group for mod in current}
        eligible = tuple(
            entry for entry in plan.entries
            if entry.group not in occupied
            and ((entry.type == "Prefix" and prefixes < plan.prefix_cap)
                 or (entry.type == "Suffix" and suffixes < plan.suffix_cap))
        )
        if not eligible:
            break
        chosen = _weighted_choice(eligible, rng, weight=lambda entry: entry.weight)
        current.append(ModRef(chosen.mod_id, chosen.type, chosen.group))
    return _replace_item(plan.item, "rare", current)


def transformed_weight(
    base_weight: int, mod_tags: Sequence[str], fossils: Sequence[Mapping[str, object]], mode: str = "additive"
) -> Fraction:
    """Return one S3 transformed weight exactly, before common-pool scaling."""
    if isinstance(base_weight, bool) or not isinstance(base_weight, int) or base_weight < 0:
        raise ValueError("base_weight must be a non-negative integer")
    if mode not in {"additive", "multiplicative"}:
        raise ValueError("fossil mode must be additive or multiplicative")
    tags = set(mod_tags)
    if not all(isinstance(tag, str) for tag in tags):
        raise ValueError("mod_tags must contain strings")
    positive: list[Fraction] = []
    negative: list[Fraction] = []
    bypassed: set[str] = set()
    for fossil in fossils:
        for hybrid in fossil.get("hybrids", ()):  # type: ignore[union-attr]
            required = set(hybrid["tags"])  # type: ignore[index]
            if required <= tags:
                factor = _fraction(hybrid["factor"])  # type: ignore[index]
                if factor == 0:
                    return Fraction(0)
                positive.append(factor)
                bypassed.update(required)
    # Single tag blocks have priority even when another fossil has a hybrid match.
    for fossil in fossils:
        for tag, raw in fossil.get("negative", {}).items():  # type: ignore[union-attr]
            factor = _fraction(raw)
            if tag in tags and factor == 0:
                return Fraction(0)
    for fossil in fossils:
        if not tags and "untagged_factor" in fossil:
            factor = _fraction(fossil["untagged_factor"])
            if factor == 0:
                return Fraction(0)
            positive.append(factor)
        for tag, raw in fossil.get("positive", {}).items():  # type: ignore[union-attr]
            if tag in tags and tag not in bypassed:
                positive.append(_fraction(raw))
        for tag, raw in fossil.get("negative", {}).items():  # type: ignore[union-attr]
            if tag in tags and tag not in bypassed:
                negative.append(_fraction(raw))
    positive_factor = _combine_positive(positive, mode)
    negative_factor = _product(negative) if negative else Fraction(1)
    return Fraction(base_weight) * positive_factor * negative_factor


def _combine_positive(factors: Sequence[Fraction], mode: str) -> Fraction:
    if not factors:
        return Fraction(1)
    if mode == "additive":
        return sum(factors, Fraction(0))
    return _product(factors)


def _product(factors: Sequence[Fraction]) -> Fraction:
    result = Fraction(1)
    for factor in factors:
        result *= factor
    return result


def _integer_weights(weights: Mapping[str, Fraction]) -> tuple[Fraction, dict[str, int]]:
    scale = 1
    for weight in weights.values():
        scale = _lcm(scale, weight.denominator)
    raw = {mod_id: int(weight * scale) for mod_id, weight in weights.items()}
    common = 0
    for weight in raw.values():
        common = gcd(common, weight)
    # ``scale`` maps rational weights to integers; reducing the common gcd
    # changes that conversion factor by the same exact fraction.
    return Fraction(scale, common), {mod_id: weight // common for mod_id, weight in raw.items()}


def _lcm(left: int, right: int) -> int:
    return left * right // gcd(left, right)


def _rare_counts(data: ActionData) -> tuple[tuple[int, int], ...]:
    weights = data.rules["rare_count_weights"]
    return tuple((int(count), weight) for count, weight in weights.items())


def _validate_selection(fossils: Sequence[int], socket_count: int | None) -> tuple[int, ...]:
    if isinstance(fossils, (str, bytes)):
        raise ValueError("fossils must be a sequence of ids")
    try:
        selected = tuple(fossils)
    except TypeError as error:
        raise ValueError("fossils must be a sequence of ids") from error
    if not 1 <= len(selected) <= 4:
        raise ValueError("a full Chaotic resonator needs 1 through 4 fossils")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in selected):
        raise ValueError("fossil ids must be integers")
    if len(set(selected)) != len(selected):
        raise ValueError("duplicate fossil types are not allowed")
    if socket_count is not None:
        if isinstance(socket_count, bool) or not isinstance(socket_count, int):
            raise ValueError("socket_count must be an integer")
        if socket_count != len(selected):
            raise ValueError("socket_count must equal selected fossil count")
    return selected


def _fraction(value: object) -> Fraction:
    if not isinstance(value, str):
        raise ValueError("malformed fossil factor")
    return Fraction(value)


def _checked_labels(labels: Mapping[str, str] | None) -> Mapping[str, str]:
    if labels is None:
        return {}
    if not isinstance(labels, Mapping) or not all(isinstance(key, str) and isinstance(value, str) for key, value in labels.items()):
        raise ValueError("labels must map string modifier ids to strings")
    return labels


def _weighted_choice(entries, rng, weight=lambda pair: pair[1]):
    total = sum(weight(entry) for entry in entries)
    ticket = rng.randrange(total)
    for entry in entries:
        current = weight(entry)
        if ticket < current:
            return entry[0] if isinstance(entry, tuple) else entry
        ticket -= current
    raise AssertionError("weighted ticket fell outside entries")


@lru_cache(maxsize=1)
def _rules() -> dict:
    try:
        rules = json.loads(_RULE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"unable to load fossil rules: {_RULE_PATH}") from error
    ordinary = rules.get("ordinary") if isinstance(rules, dict) else None
    if not isinstance(ordinary, list):
        raise ValueError("malformed fossil rules: ordinary")
    return rules
