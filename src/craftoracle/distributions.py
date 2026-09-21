"""Exact finite distributions for group-exclusive weighted affix draws.

The functions enumerate the documented unbiased weighted process using binary
floats.  Results have ordinary floating-point rounding (normally within
``1e-10`` of unit mass), but no sampling error.  They deliberately retain
group-profile state until the final ``OutcomeClass`` projection: a projected
terminal distribution cannot be safely used for later arbitrary item changes.

Sources: ``docs/mechanics/affix_generation.md`` and
``docs/mechanics/pool_resolution.md``; provisional GOAL Q2/Q4/Q16/Q17.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
import math


_MAX_STATES = 1_000_000


@dataclass(frozen=True)
class DrawEntry:
    """Minimal standalone input record for one eligible modifier."""

    mod_id: str
    type: str
    group: str
    weight: int


@dataclass(frozen=True, order=True)
class OutcomeClass:
    """Terminal projection retaining selected target-label multiplicities."""

    labels: tuple[str, ...]
    prefixes: int
    suffixes: int


@dataclass(frozen=True)
class _Profile:
    side: str
    weight: int
    labels: tuple[tuple[str, int], ...]
    junk_weight: int
    multiplicity: int


@dataclass(frozen=True)
class _State:
    prefixes: int
    suffixes: int
    labels: tuple[str, ...]
    selected: tuple[int, ...]


def _nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_weight(value: object, mod_id: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"weight for {mod_id!r} must be a positive integer")
    return value


def _validate_labels(labels: Mapping[str, str] | None) -> Mapping[str, str]:
    if labels is None:
        return {}
    if not isinstance(labels, Mapping):
        raise ValueError("labels must be a mapping of mod ids to strings")
    for mod_id, label in labels.items():
        if not isinstance(mod_id, str) or not isinstance(label, str):
            raise ValueError("labels must map string mod ids to string labels")
    return labels


def _profiles(
    entries: Iterable[object], labels: Mapping[str, str], blocked_groups: Iterable[str]
) -> tuple[_Profile, ...]:
    try:
        blocked = set(blocked_groups)
    except TypeError as error:
        raise ValueError("blocked_groups must be an iterable of group strings") from error
    if not all(isinstance(group, str) for group in blocked):
        raise ValueError("blocked_groups must contain group strings")

    groups: dict[str, tuple[str, int, dict[str, int], int]] = {}
    mod_ids: set[str] = set()
    for entry in entries:
        try:
            mod_id = entry.mod_id
            side = entry.type
            group = entry.group
            weight = entry.weight
        except AttributeError as error:
            raise ValueError("each entry needs mod_id, type, group, and weight") from error
        if not isinstance(mod_id, str) or not mod_id:
            raise ValueError("mod_id must be a non-empty string")
        if mod_id in mod_ids:
            raise ValueError(f"duplicate mod_id {mod_id!r}")
        mod_ids.add(mod_id)
        if side not in {"Prefix", "Suffix"}:
            raise ValueError(f"invalid modifier type {side!r}")
        if not isinstance(group, str) or not group:
            raise ValueError("group must be a non-empty string")
        weight = _positive_weight(weight, mod_id)
        label = labels.get(mod_id)
        if group in groups:
            old_side, total, label_weights, junk_weight = groups[group]
            if old_side != side:
                raise ValueError(f"group {group!r} has inconsistent sides")
        else:
            old_side, total, label_weights, junk_weight = side, 0, {}, 0
        total += weight
        if label is None:
            junk_weight += weight
        else:
            label_weights[label] = label_weights.get(label, 0) + weight
        groups[group] = (old_side, total, label_weights, junk_weight)

    collapsed: dict[tuple[str, int, tuple[tuple[str, int], ...], int], int] = {}
    for group, (side, total, label_weights, junk_weight) in groups.items():
        if group in blocked:
            continue
        key = (side, total, tuple(sorted(label_weights.items())), junk_weight)
        collapsed[key] = collapsed.get(key, 0) + 1
    return tuple(
        _Profile(side, weight, label_weights, junk_weight, multiplicity)
        for (side, weight, label_weights, junk_weight), multiplicity in sorted(
            collapsed.items()
        )
    )


def _validate_initial(
    prefix_cap: object,
    suffix_cap: object,
    initial_prefixes: object,
    initial_suffixes: object,
    initial_labels: Iterable[str],
) -> tuple[int, int, int, int, tuple[str, ...]]:
    prefix_cap = _nonnegative_int(prefix_cap, "prefix_cap")
    suffix_cap = _nonnegative_int(suffix_cap, "suffix_cap")
    initial_prefixes = _nonnegative_int(initial_prefixes, "initial_prefixes")
    initial_suffixes = _nonnegative_int(initial_suffixes, "initial_suffixes")
    if initial_prefixes > prefix_cap or initial_suffixes > suffix_cap:
        raise ValueError("initial counts must not exceed their caps")
    try:
        fixed_labels = tuple(initial_labels)
    except TypeError as error:
        raise ValueError("initial_labels must be an iterable of strings") from error
    if not all(isinstance(label, str) for label in fixed_labels):
        raise ValueError("initial_labels must contain strings")
    return prefix_cap, suffix_cap, initial_prefixes, initial_suffixes, tuple(sorted(fixed_labels))


def _advance(
    states: dict[_State, float], profiles: tuple[_Profile, ...], prefix_cap: int, suffix_cap: int
) -> dict[_State, float]:
    advanced: dict[_State, float] = defaultdict(float)
    for state, mass in states.items():
        eligible: list[tuple[int, int]] = []
        denominator = 0
        for index, profile in enumerate(profiles):
            if (profile.side == "Prefix" and state.prefixes >= prefix_cap) or (
                profile.side == "Suffix" and state.suffixes >= suffix_cap
            ):
                continue
            remaining = profile.multiplicity - state.selected[index]
            if remaining:
                total = remaining * profile.weight
                eligible.append((index, total))
                denominator += total
        if denominator == 0:
            advanced[state] += mass
            continue
        for index, profile_weight in eligible:
            profile = profiles[index]
            group_mass = mass * profile_weight / denominator
            selected = list(state.selected)
            selected[index] += 1
            prefixes = state.prefixes + (profile.side == "Prefix")
            suffixes = state.suffixes + (profile.side == "Suffix")
            if profile.junk_weight:
                advanced[_State(prefixes, suffixes, state.labels, tuple(selected))] += (
                    group_mass * profile.junk_weight / profile.weight
                )
            for label, label_weight in profile.labels:
                advanced[_State(
                    prefixes,
                    suffixes,
                    tuple(sorted((*state.labels, label))),
                    tuple(selected),
                )] += group_mass * label_weight / profile.weight
    if len(advanced) > _MAX_STATES:
        raise NotImplementedError(
            f"exact distribution exceeded deterministic {_MAX_STATES}-state complexity limit"
        )
    return dict(advanced)


def _terminal(states: Mapping[_State, float]) -> dict[OutcomeClass, float]:
    result: dict[OutcomeClass, float] = defaultdict(float)
    for state, mass in states.items():
        result[OutcomeClass(state.labels, state.prefixes, state.suffixes)] += mass
    return dict(result)


def scheduled_distribution(
    entries: Iterable[object],
    stages: Sequence[tuple[int, int, int]],
    labels: Mapping[str, str] | None = None,
    *,
    initial_prefixes: int = 0,
    initial_suffixes: int = 0,
    initial_labels: Iterable[str] = (),
    blocked_groups: Iterable[str] = (),
) -> dict[OutcomeClass, float]:
    """Return exact outcomes after staged draws with potentially growing caps.

    It is valid for an exhausted stage to reach a later stage with larger caps.
    The returned terminal classes have discarded selected-group state and cannot
    drive a later arbitrary transition exactly.
    """
    labels = _validate_labels(labels)
    parsed_stages: list[tuple[int, int, int]] = []
    for stage in stages:
        try:
            draws, prefix_cap, suffix_cap = stage
        except (TypeError, ValueError) as error:
            raise ValueError("each stage must be (draw_count, prefix_cap, suffix_cap)") from error
        parsed_stages.append((
            _nonnegative_int(draws, "draw_count"),
            _nonnegative_int(prefix_cap, "prefix_cap"),
            _nonnegative_int(suffix_cap, "suffix_cap"),
        ))
    if not parsed_stages:
        raise ValueError("stages must not be empty")
    first_prefix_cap, first_suffix_cap = parsed_stages[0][1:]
    _, _, initial_prefixes, initial_suffixes, initial_labels = _validate_initial(
        first_prefix_cap, first_suffix_cap, initial_prefixes, initial_suffixes, initial_labels
    )
    profiles = _profiles(entries, labels, blocked_groups)
    states = {
        _State(initial_prefixes, initial_suffixes, initial_labels, (0,) * len(profiles)): 1.0
    }
    for draws, prefix_cap, suffix_cap in parsed_stages:
        for _ in range(draws):
            states = _advance(states, profiles, prefix_cap, suffix_cap)
    return _terminal(states)


def draw_distribution(
    entries: Iterable[object],
    draws: int,
    labels: Mapping[str, str] | None = None,
    *,
    prefix_cap: int = 3,
    suffix_cap: int = 3,
    initial_prefixes: int = 0,
    initial_suffixes: int = 0,
    initial_labels: Iterable[str] = (),
    blocked_groups: Iterable[str] = (),
) -> dict[OutcomeClass, float]:
    """Return exact outcomes of up to ``draws`` group-exclusive weighted draws."""
    _nonnegative_int(draws, "draws")
    return scheduled_distribution(
        entries,
        [(draws, prefix_cap, suffix_cap)],
        labels,
        initial_prefixes=initial_prefixes,
        initial_suffixes=initial_suffixes,
        initial_labels=initial_labels,
        blocked_groups=blocked_groups,
    )


def _validated_distribution(distribution: Mapping[OutcomeClass, float]) -> Mapping[OutcomeClass, float]:
    if not isinstance(distribution, Mapping):
        raise ValueError("distribution must be a mapping")
    mass = 0.0
    for outcome, value in distribution.items():
        if not isinstance(outcome, OutcomeClass):
            raise ValueError("distribution keys must be OutcomeClass values")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("distribution masses must be finite non-negative numbers")
        mass += value
    if not math.isclose(mass, 1.0, rel_tol=0.0, abs_tol=1e-10):
        raise ValueError("distribution mass must be one within 1e-10")
    return distribution


def mixture_distribution(
    weighted_distributions: Iterable[tuple[float, Mapping[OutcomeClass, float]]],
) -> dict[OutcomeClass, float]:
    """Normalize mixture weights and merge equal terminal outcome classes."""
    parts = list(weighted_distributions)
    if not parts:
        raise ValueError("weighted_distributions must not be empty")
    total_weight = 0.0
    checked: list[tuple[float, Mapping[OutcomeClass, float]]] = []
    for weight, distribution in parts:
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight <= 0:
            raise ValueError("mixture weights must be finite positive numbers")
        checked.append((float(weight), _validated_distribution(distribution)))
        total_weight += weight
    result: dict[OutcomeClass, float] = defaultdict(float)
    for weight, distribution in checked:
        for outcome, mass in distribution.items():
            result[outcome] += weight / total_weight * mass
    return dict(result)


def probability(
    distribution: Mapping[OutcomeClass, float], predicate: Callable[[OutcomeClass], bool]
) -> float:
    """Sum the mass of terminal outcomes satisfying ``predicate``."""
    return sum(mass for outcome, mass in _validated_distribution(distribution).items() if predicate(outcome))


def expected_value(
    distribution: Mapping[OutcomeClass, float], value_function: Callable[[OutcomeClass], float]
) -> float:
    """Return the exact-distribution expectation of ``value_function``."""
    return sum(mass * value_function(outcome) for outcome, mass in _validated_distribution(distribution).items())
