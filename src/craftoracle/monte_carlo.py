"""Independent seeded estimators for grouped affix draws and loop costs.

``sample_distribution`` implements the unbiased individual weighted-draw
process described in ``docs/mechanics/affix_generation.md``.  It deliberately
does not call or sample the exact distribution DP: each trial draws a concrete
entry and removes every entry in that exclusion group.

The compound-cost estimator is statistical mathematics for exact-cost-limit
fallbacks.  It does not estimate crafting success probabilities.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import math
from numbers import Real
import random

import numpy as np

from craftoracle.distributions import OutcomeClass


@dataclass(frozen=True)
class SampleDistribution:
    """Terminal Monte Carlo frequencies and binomial Wilson intervals."""

    probabilities: dict[OutcomeClass, float]
    counts: dict[OutcomeClass, int]
    intervals: dict[OutcomeClass, tuple[float, float]]
    samples: int
    seed: int
    method: str = "estimated"


@dataclass(frozen=True)
class CompoundCostEstimate:
    """Empirical p90 with a DKW probability-space confidence interval."""

    p90: float
    interval_lower: float
    interval_upper: float
    samples: int
    seed: int
    confidence: float
    dkw_epsilon: float
    method: str = "estimated-dkw-monte-carlo"


@dataclass(frozen=True)
class _Entry:
    mod_id: str
    side: str
    group: str
    weight: int
    label: str | None


def sample_distribution(
    entries: Iterable[object],
    draws: int,
    labels: Mapping[str, str] | None = None,
    *,
    samples: int,
    seed: int,
    prefix_cap: int = 3,
    suffix_cap: int = 3,
    initial_prefixes: int = 0,
    initial_suffixes: int = 0,
    initial_labels: Iterable[str] = (),
    blocked_groups: Iterable[str] = (),
) -> SampleDistribution:
    """Estimate terminal outcomes with direct group-exclusive weighted draws.

    The local ``random.Random`` instance makes a result reproducible from its
    input seed.  Pool exhaustion leaves a trial at its actual terminal state.
    """
    draw_count = _nonnegative_int(draws, "draws")
    trial_count = _positive_int(samples, "samples")
    parsed_seed = _seed(seed)
    prefix_cap, suffix_cap, prefixes, suffixes, fixed_labels = _initial_state(
        prefix_cap,
        suffix_cap,
        initial_prefixes,
        initial_suffixes,
        initial_labels,
    )
    label_map = _labels(labels)
    blocked = _blocked_groups(blocked_groups)
    pool = _entries(entries, label_map)
    active_initial = tuple(entry for entry in pool if entry.group not in blocked)
    rng = random.Random(parsed_seed)
    counts: Counter[OutcomeClass] = Counter()

    for _ in range(trial_count):
        current_prefixes = prefixes
        current_suffixes = suffixes
        current_labels = list(fixed_labels)
        active = list(active_initial)
        for _ in range(draw_count):
            eligible = [
                entry
                for entry in active
                if not (
                    (entry.side == "Prefix" and current_prefixes >= prefix_cap)
                    or (entry.side == "Suffix" and current_suffixes >= suffix_cap)
                )
            ]
            total_weight = sum(entry.weight for entry in eligible)
            if total_weight == 0:
                break
            ticket = rng.randrange(total_weight)
            selected = _select_entry(eligible, ticket)
            active = [entry for entry in active if entry.group != selected.group]
            if selected.side == "Prefix":
                current_prefixes += 1
            else:
                current_suffixes += 1
            if selected.label is not None:
                current_labels.append(selected.label)
        counts[OutcomeClass(tuple(sorted(current_labels)), current_prefixes, current_suffixes)] += 1

    plain_counts = dict(counts)
    probabilities = {outcome: count / trial_count for outcome, count in plain_counts.items()}
    intervals = {outcome: wilson_interval(count, trial_count) for outcome, count in plain_counts.items()}
    return SampleDistribution(probabilities, plain_counts, intervals, trial_count, parsed_seed)


def wilson_interval(
    successes: int,
    samples: int,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    """Return the usual two-sided binomial Wilson-score confidence interval."""
    hits = _nonnegative_int(successes, "successes")
    trials = _positive_int(samples, "samples")
    if hits > trials:
        raise ValueError("successes must not exceed samples")
    score = _finite_number(z, "z")
    if score <= 0:
        raise ValueError("z must be positive")
    proportion = hits / trials
    score_squared = score * score
    denominator = 1 + score_squared / trials
    center = (proportion + score_squared / (2 * trials)) / denominator
    half_width = score * math.sqrt(
        (proportion * (1 - proportion) + score_squared / (4 * trials)) / trials
    ) / denominator
    return max(0.0, center - half_width), min(1.0, center + half_width)


def estimate_compound_cost_p90(
    p: float,
    low_cost: float,
    high_cost: float,
    high_probability: float,
    *,
    reset_cost: float = 0,
    setup_cost: float = 0,
    samples: int = 50_000,
    seed: int = 20260921,
    confidence: float = 0.99,
) -> CompoundCostEstimate:
    """Estimate compound-loop p90 and bound its quantile using DKW.

    ``N`` includes the successful attempt.  Conditional on ``N``, each of its
    independent attempt prices is high with ``high_probability``.
    """
    success_probability = _finite_number(p, "p")
    if success_probability <= 0 or success_probability > 1:
        raise ValueError("p must be in (0, 1]")
    low = _nonnegative_cost(low_cost, "low_cost")
    high = _nonnegative_cost(high_cost, "high_cost")
    if low > high:
        raise ValueError("low_cost must not exceed high_cost")
    high_chance = _probability(high_probability, "high_probability")
    reset = _nonnegative_cost(reset_cost, "reset_cost")
    setup = _nonnegative_cost(setup_cost, "setup_cost")
    trial_count = _positive_int(samples, "samples")
    parsed_seed = _seed(seed)
    coverage = _finite_number(confidence, "confidence")
    if coverage < 0 or coverage >= 1:
        raise ValueError("confidence must be in [0, 1)")
    epsilon = math.sqrt(math.log(2 / (1 - coverage)) / (2 * trial_count))
    if epsilon >= 0.1:
        raise ValueError("samples are insufficient to bracket the 0.9 quantile")

    rng = np.random.default_rng(parsed_seed)
    attempts = rng.geometric(success_probability, size=trial_count)
    high_attempts = rng.binomial(attempts, high_chance)
    costs = setup + attempts * low + (high - low) * high_attempts + reset * (attempts - 1)
    ordered = np.sort(costs)
    return CompoundCostEstimate(
        _higher_quantile(ordered, 0.9),
        _higher_quantile(ordered, max(0.0, 0.9 - epsilon)),
        _higher_quantile(ordered, min(1.0, 0.9 + epsilon)),
        trial_count,
        parsed_seed,
        coverage,
        epsilon,
    )


def _select_entry(entries: list[_Entry], ticket: int) -> _Entry:
    cumulative = 0
    for entry in entries:
        cumulative += entry.weight
        if ticket < cumulative:
            return entry
    raise AssertionError("ticket was outside the eligible integer weight range")


def _higher_quantile(ordered: np.ndarray, probability: float) -> float:
    rank = max(0, min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1))
    return float(ordered[rank])


def _entries(entries: Iterable[object], labels: Mapping[str, str]) -> tuple[_Entry, ...]:
    try:
        iterator = iter(entries)
    except TypeError as error:
        raise ValueError("entries must be iterable") from error
    seen_ids: set[str] = set()
    sides_by_group: dict[str, str] = {}
    parsed: list[_Entry] = []
    for entry in iterator:
        try:
            mod_id, side, group, weight = entry.mod_id, entry.type, entry.group, entry.weight
        except AttributeError as error:
            raise ValueError("each entry needs mod_id, type, group, and weight") from error
        if not isinstance(mod_id, str) or not mod_id:
            raise ValueError("mod_id must be a non-empty string")
        if mod_id in seen_ids:
            raise ValueError(f"duplicate mod_id {mod_id!r}")
        if side not in {"Prefix", "Suffix"}:
            raise ValueError(f"invalid modifier type {side!r}")
        if not isinstance(group, str) or not group:
            raise ValueError("group must be a non-empty string")
        if group in sides_by_group and sides_by_group[group] != side:
            raise ValueError(f"group {group!r} has inconsistent sides")
        seen_ids.add(mod_id)
        sides_by_group[group] = side
        parsed.append(_Entry(mod_id, side, group, _positive_int(weight, f"weight for {mod_id!r}"), labels.get(mod_id)))
    return tuple(parsed)


def _labels(labels: Mapping[str, str] | None) -> Mapping[str, str]:
    if labels is None:
        return {}
    if not isinstance(labels, Mapping):
        raise ValueError("labels must be a mapping of mod ids to strings")
    if not all(isinstance(mod_id, str) and isinstance(label, str) for mod_id, label in labels.items()):
        raise ValueError("labels must map string mod ids to string labels")
    return labels


def _blocked_groups(groups: Iterable[str]) -> set[str]:
    try:
        blocked = set(groups)
    except TypeError as error:
        raise ValueError("blocked_groups must be an iterable of group strings") from error
    if not all(isinstance(group, str) for group in blocked):
        raise ValueError("blocked_groups must contain group strings")
    return blocked


def _initial_state(
    prefix_cap: int,
    suffix_cap: int,
    initial_prefixes: int,
    initial_suffixes: int,
    initial_labels: Iterable[str],
) -> tuple[int, int, int, int, tuple[str, ...]]:
    prefix_cap = _nonnegative_int(prefix_cap, "prefix_cap")
    suffix_cap = _nonnegative_int(suffix_cap, "suffix_cap")
    prefixes = _nonnegative_int(initial_prefixes, "initial_prefixes")
    suffixes = _nonnegative_int(initial_suffixes, "initial_suffixes")
    if prefixes > prefix_cap or suffixes > suffix_cap:
        raise ValueError("initial counts must not exceed their caps")
    try:
        labels = tuple(initial_labels)
    except TypeError as error:
        raise ValueError("initial_labels must be an iterable of strings") from error
    if not all(isinstance(label, str) for label in labels):
        raise ValueError("initial_labels must contain strings")
    return prefix_cap, suffix_cap, prefixes, suffixes, tuple(sorted(labels))


def _nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _seed(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("seed must be an integer")
    return value


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{name} must be a finite number")
    return parsed


def _nonnegative_cost(value: object, name: str) -> float:
    cost = _finite_number(value, name)
    if cost < 0:
        raise ValueError(f"{name} must be non-negative")
    return cost


def _probability(value: object, name: str) -> float:
    probability = _finite_number(value, name)
    if probability < 0 or probability > 1:
        raise ValueError(f"{name} must be in [0, 1]")
    return probability
