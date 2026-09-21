"""Accepted exact and sampled ordinary tagged Harvest reforges.

The model is recorded in ``docs/mechanics/harvest.md`` and its accepted
configuration metadata is in ``data/rules/harvest.json``.  Exact evaluation
enumerates the forced individual modifier before delegating later ordinary
draws to the group-aware distribution DP; it never continues from a projected
terminal class.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import random

from craftoracle.actions import (
    ActionData,
    _candidate_entries,
    _caps,
    _counts,
    _labels_for,
    _meta_flags,
    _replace_item,
    _retained_for_reroll,
    _validate_action_data,
    _validate_item,
    _validate_labels,
)
from craftoracle.distributions import DrawEntry, OutcomeClass, draw_distribution, mixture_distribution
from craftoracle.item_model import ItemState, ModRef


_RULE_PATH = Path(__file__).resolve().parents[2] / "data" / "rules" / "harvest.json"


@dataclass(frozen=True)
class HarvestPlan:
    """Immutable resolved pool for repeated direct samples of one reforge."""

    item: ItemState
    retained: tuple[ModRef, ...]
    forced: tuple[DrawEntry, ...]
    ordinary: tuple[DrawEntry, ...]
    counts: tuple[tuple[int, int], ...]
    prefix_cap: int
    suffix_cap: int


def harvest_distribution(
    item: ItemState,
    data: ActionData,
    tag: str,
    labels: Mapping[str, str] | None = None,
    *,
    type_filter: str = "first_only",
) -> dict[OutcomeClass, float]:
    """Return the exact terminal distribution of one accepted tagged reforge."""
    checked_labels, retained, forced, ordinary_flags, counts = _prepare(
        item, data, tag, labels, type_filter
    )
    cap = _caps(data, "rare")
    retained_groups = tuple(mod.group for mod in retained)
    forced_weight = sum(entry.weight for entry in forced)
    parts: list[tuple[float, dict[OutcomeClass, float]]] = []
    cached: dict[tuple[str, str, str | None], dict[OutcomeClass, float]] = {}
    for entry in forced:
        forced_mod = ModRef(entry.mod_id, entry.type, entry.group)
        forced_label = checked_labels.get(entry.mod_id)
        cache_key = (entry.type, entry.group, forced_label)
        distribution = cached.get(cache_key)
        if distribution is None:
            after_forced = (*retained, forced_mod)
            initial_prefixes, initial_suffixes = _counts(after_forced)
            ordinary = _candidate_entries(item, data, after_forced, ordinary_flags, None)
            blocked = (*retained_groups, forced_mod.group)
            initial_labels = _labels_for(after_forced, checked_labels)
            per_count = []
            for target, count_weight in counts:
                draws = max(0, target - len(after_forced))
                per_count.append((count_weight, _ordinary_distribution(
                    ordinary,
                    draws,
                    checked_labels,
                    prefix_cap=cap[0],
                    suffix_cap=cap[1],
                    initial_prefixes=initial_prefixes,
                    initial_suffixes=initial_suffixes,
                    initial_labels=initial_labels,
                    blocked_groups=blocked,
                )))
            distribution = mixture_distribution(per_count)
            cached[cache_key] = distribution
        parts.append((entry.weight / forced_weight, distribution))
    return mixture_distribution(parts)


def apply_harvest(
    item: ItemState,
    data: ActionData,
    tag: str,
    rng: random.Random,
    *,
    type_filter: str = "first_only",
) -> ItemState:
    """Sample one reforge through direct individual weighted draws.

    The supplied ``random.Random`` is the sole entropy source.  This function
    deliberately does not sample the exact terminal distribution.
    """
    return sample_harvest(prepare_harvest(item, data, tag, type_filter=type_filter), rng)


def prepare_harvest(
    item: ItemState,
    data: ActionData,
    tag: str,
    *,
    type_filter: str = "first_only",
) -> HarvestPlan:
    """Resolve immutable candidates once for a caller-managed sample series."""
    _, retained, forced, ordinary_flags, counts = _prepare(item, data, tag, None, type_filter)
    ordinary = _candidate_entries(item, data, retained, ordinary_flags, None)
    prefix_cap, suffix_cap = _caps(data, "rare")
    return HarvestPlan(item, retained, forced, ordinary, counts, prefix_cap, suffix_cap)


def sample_harvest(plan: HarvestPlan, rng: random.Random) -> ItemState:
    """Sample one prepared plan using only direct individual weighted draws."""
    if not isinstance(plan, HarvestPlan):
        raise ValueError("plan must be HarvestPlan")
    if not isinstance(rng, random.Random):
        raise ValueError("rng must be random.Random")
    target = _weighted_choice(plan.counts, rng)[0]
    chosen = _weighted_choice(plan.forced, rng)
    current: list[ModRef] = [*plan.retained, ModRef(chosen.mod_id, chosen.type, chosen.group)]
    while len(current) < target:
        prefixes, suffixes = _counts(current)
        occupied_groups = {mod.group for mod in current}
        eligible = tuple(
            entry for entry in plan.ordinary
            if entry.group not in occupied_groups
            and ((entry.type == "Prefix" and prefixes < plan.prefix_cap)
                 or (entry.type == "Suffix" and suffixes < plan.suffix_cap))
        )
        if not eligible:
            break
        selected = _weighted_choice(eligible, rng)
        current.append(ModRef(selected.mod_id, selected.type, selected.group))
    return _replace_item(plan.item, "rare", current)


def _prepare(item, data, tag, labels, type_filter):
    _validate_action_data(data)
    _validate_item(item, data)
    if item.fractured:
        raise NotImplementedError("out of tonight's slice: Q9")
    checked_labels = _validate_labels(labels)
    rules = _rules()
    if item.rarity != rules["ordinary_reforge"]["rarity"]:
        raise ValueError("harvest reforge requires rare item")
    if not isinstance(tag, str) or tag not in rules["supported_tags"]:
        raise ValueError(f"unknown harvest tag: {tag}")
    if type_filter not in rules["ordinary_reforge"]["type_filter_modes"]:
        raise ValueError(f"unknown harvest type_filter: {type_filter}")
    retained = _retained_for_reroll(item)
    cap = _caps(data, "rare")
    retained_prefixes, retained_suffixes = _counts(retained)
    original_flags = _meta_flags(item.mods)
    candidates = _candidate_entries(item, data, retained, original_flags, None)
    literal_tag = rules["tag_literals"].get(tag, tag)
    forced = tuple(
        entry for entry in candidates
        if literal_tag in (data.mods[entry.mod_id].get("modTags") or [])
        and ((entry.type == "Prefix" and retained_prefixes < cap[0])
             or (entry.type == "Suffix" and retained_suffixes < cap[1]))
    )
    if not forced:
        raise ValueError("no eligible tagged modifier can be added")
    counts = _harvest_counts(data)
    ordinary_flags = original_flags if type_filter == "all_draws" else (False, False)
    return checked_labels, retained, forced, ordinary_flags, counts


def _harvest_counts(data: ActionData) -> tuple[tuple[int, int], ...]:
    source = data.rules.get("rare_count_weights")
    if not isinstance(source, dict) or not source or not set(source) <= {"4", "5", "6"}:
        raise ValueError("harvest requires rare count weights drawn from 4, 5, and 6")
    result: list[tuple[int, int]] = []
    for count in (4, 5, 6):
        if str(count) not in source:
            continue
        weight = source[str(count)]
        if isinstance(weight, bool) or not isinstance(weight, int) or weight <= 0:
            raise ValueError("harvest count weights must be positive integers")
        result.append((count, weight))
    return tuple(result)


def _weighted_choice(entries, rng):
    total = sum(entry.weight if hasattr(entry, "weight") else entry[1] for entry in entries)
    ticket = rng.randrange(total)
    for entry in entries:
        weight = entry.weight if hasattr(entry, "weight") else entry[1]
        if ticket < weight:
            return entry
        ticket -= weight
    raise AssertionError("weighted ticket fell outside its entries")


def _ordinary_distribution(entries, draws, labels, **kwargs):
    """Use an identity-preserving small-draw DP where it avoids large profiles."""
    if draws > 2:
        return draw_distribution(entries, draws, labels, **kwargs)
    prefix_cap = kwargs["prefix_cap"]
    suffix_cap = kwargs["suffix_cap"]
    prefix_count = kwargs["initial_prefixes"]
    suffix_count = kwargs["initial_suffixes"]
    initial_labels = tuple(sorted(kwargs["initial_labels"]))
    initial_groups = frozenset(kwargs["blocked_groups"])
    states = {(prefix_count, suffix_count, initial_labels, initial_groups): 1.0}
    for _ in range(draws):
        advanced = defaultdict(float)
        for (prefixes, suffixes, state_labels, blocked), mass in states.items():
            eligible = tuple(
                entry for entry in entries
                if entry.group not in blocked
                and ((entry.type == "Prefix" and prefixes < prefix_cap)
                     or (entry.type == "Suffix" and suffixes < suffix_cap))
            )
            total = sum(entry.weight for entry in eligible)
            if total == 0:
                advanced[(prefixes, suffixes, state_labels, blocked)] += mass
                continue
            for entry in eligible:
                label = labels.get(entry.mod_id)
                next_labels = state_labels if label is None else tuple(sorted((*state_labels, label)))
                advanced[(
                    prefixes + (entry.type == "Prefix"),
                    suffixes + (entry.type == "Suffix"),
                    next_labels,
                    blocked | {entry.group},
                )] += mass * entry.weight / total
        states = advanced
    result = defaultdict(float)
    for (prefixes, suffixes, state_labels, _), mass in states.items():
        result[OutcomeClass(state_labels, prefixes, suffixes)] += mass
    return dict(result)


@lru_cache(maxsize=1)
def _rules() -> dict:
    try:
        rules = json.loads(_RULE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"unable to load harvest rules: {_RULE_PATH}") from error
    if not isinstance(rules, dict):
        raise ValueError("malformed harvest rules")
    tags = rules.get("supported_tags")
    model = rules.get("ordinary_reforge")
    if not isinstance(tags, list) or not all(isinstance(value, str) for value in tags):
        raise ValueError("malformed harvest rules: supported_tags")
    if not isinstance(model, dict) or model.get("rarity") != "rare":
        raise ValueError("malformed harvest rules: ordinary_reforge")
    modes = model.get("type_filter_modes")
    if not isinstance(modes, list) or set(modes) != {"first_only", "all_draws"}:
        raise ValueError("malformed harvest rules: type_filter_modes")
    literals = rules.get("tag_literals")
    if not isinstance(literals, dict) or any(
        not isinstance(public, str) or not isinstance(literal, str)
        for public, literal in literals.items()
    ) or set(literals) - set(tags):
        raise ValueError("malformed harvest rules: tag_literals")
    return rules
