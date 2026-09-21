"""Exact grouped weighted-draw distribution checks from the worker spec."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from craftoracle.distributions import (
    DrawEntry,
    OutcomeClass,
    draw_distribution,
    expected_value,
    mixture_distribution,
    probability,
    scheduled_distribution,
)


def _entry(
    mod_id: str, side: str, group: str, weight: int
) -> DrawEntry:
    return DrawEntry(mod_id, side, group, weight)


def _mass(distribution: dict[OutcomeClass, float]) -> float:
    return sum(distribution.values())


def _label_mass(distribution: dict[OutcomeClass, float], *labels: str) -> float:
    wanted = tuple(sorted(labels))
    return probability(distribution, lambda outcome: all(
        outcome.labels.count(label) >= wanted.count(label) for label in set(wanted)
    ))


def test_three_distinct_groups_reproduce_hand_arithmetic() -> None:
    distribution = draw_distribution(
        [
            _entry("A", "Prefix", "A", 1),
            _entry("B", "Prefix", "B", 1),
            _entry("C", "Prefix", "C", 2),
        ],
        2,
        {"A": "A", "B": "B", "C": "C"},
    )

    assert distribution == {
        OutcomeClass(("A", "B"), 2, 0): pytest.approx(1 / 6),
        OutcomeClass(("A", "C"), 2, 0): pytest.approx(5 / 12),
        OutcomeClass(("B", "C"), 2, 0): pytest.approx(5 / 12),
    }
    assert _label_mass(distribution, "A") == pytest.approx(7 / 12)
    assert _mass(distribution) == pytest.approx(1)


@dataclass
class _PoolEntryLike:
    mod_id: str
    type: str
    group: str
    weight: int


def test_attribute_entries_and_zero_draws_keep_the_initial_state() -> None:
    distribution = draw_distribution(
        [_PoolEntryLike("A", "Prefix", "A", 1)],
        0,
        {"A": "a"},
        initial_prefixes=1,
        initial_labels=("seed",),
    )

    assert distribution == {OutcomeClass(("seed",), 1, 0): pytest.approx(1)}


def test_group_internal_label_weight_and_junk_are_not_reusable() -> None:
    distribution = draw_distribution(
        [
            _entry("A1", "Prefix", "A", 1),
            _entry("A2", "Prefix", "A", 3),
            _entry("B", "Prefix", "B", 2),
            _entry("C", "Prefix", "C", 2),
        ],
        2,
        {"A1": "hit", "B": "b"},
    )

    assert _label_mass(distribution, "hit") == pytest.approx(5 / 24)
    assert _label_mass(distribution, "hit", "b") == pytest.approx(5 / 48)
    assert _mass(distribution) == pytest.approx(1)


def test_caps_block_sides_and_mixture_preserves_outcomes() -> None:
    entries = [
        _entry("A", "Prefix", "A", 1),
        _entry("B", "Suffix", "B", 3),
    ]
    labels = {"A": "a", "B": "b"}
    one_draw = draw_distribution(entries, 1, labels, prefix_cap=1, suffix_cap=1)
    two_draws = draw_distribution(entries, 2, labels, prefix_cap=1, suffix_cap=1)
    mixture = mixture_distribution([(1, one_draw), (1, two_draws)])

    assert one_draw == {
        OutcomeClass(("a",), 1, 0): pytest.approx(1 / 4),
        OutcomeClass(("b",), 0, 1): pytest.approx(3 / 4),
    }
    assert two_draws == {OutcomeClass(("a", "b"), 1, 1): pytest.approx(1)}
    assert mixture == {
        OutcomeClass(("a",), 1, 0): pytest.approx(1 / 8),
        OutcomeClass(("b",), 0, 1): pytest.approx(3 / 8),
        OutcomeClass(("a", "b"), 1, 1): pytest.approx(1 / 2),
    }
    assert expected_value(mixture, lambda outcome: outcome.prefixes + outcome.suffixes) == pytest.approx(3 / 2)


def test_blocked_and_empty_pool_leave_fixed_initial_state() -> None:
    entries = [
        _entry("A", "Prefix", "A", 1),
        _entry("B", "Suffix", "B", 3),
    ]
    labels = {"A": "a", "B": "b"}

    assert draw_distribution(
        entries, 2, labels, prefix_cap=1, suffix_cap=1, blocked_groups=("B",)
    ) == {OutcomeClass(("a",), 1, 0): pytest.approx(1)}
    assert draw_distribution([], 2, initial_labels=("seed",)) == {
        OutcomeClass(("seed",), 0, 0): pytest.approx(1)
    }


def test_initial_state_and_blocked_group_preserve_seed() -> None:
    distribution = draw_distribution(
        [
            _entry("A", "Prefix", "A", 1),
            _entry("B", "Prefix", "B", 1),
            _entry("C", "Prefix", "C", 2),
        ],
        1,
        {"A": "a", "B": "b", "C": "c"},
        initial_prefixes=1,
        initial_labels=("seed",),
        blocked_groups=("A",),
    )

    assert distribution == {
        OutcomeClass(("b", "seed"), 2, 0): pytest.approx(1 / 3),
        OutcomeClass(("c", "seed"), 2, 0): pytest.approx(2 / 3),
    }


def test_schedule_keeps_group_information_through_magic_stage() -> None:
    distribution = scheduled_distribution(
        [
            _entry("A", "Prefix", "A", 1),
            _entry("B", "Prefix", "B", 1),
            _entry("C", "Suffix", "C", 1),
            _entry("D", "Suffix", "D", 1),
        ],
        [(2, 1, 1), (1, 3, 3)],
        {"A": "A", "B": "B", "C": "C", "D": "D"},
    )

    assert distribution == {
        OutcomeClass(("A", "B", "C"), 2, 1): pytest.approx(1 / 4),
        OutcomeClass(("A", "B", "D"), 2, 1): pytest.approx(1 / 4),
        OutcomeClass(("A", "C", "D"), 1, 2): pytest.approx(1 / 4),
        OutcomeClass(("B", "C", "D"), 1, 2): pytest.approx(1 / 4),
    }


def test_utility_helpers_use_the_supplied_distribution() -> None:
    distribution = {
        OutcomeClass(("a",), 1, 0): 1 / 2,
        OutcomeClass(("b",), 1, 0): 1 / 3,
        OutcomeClass(("c",), 1, 0): 1 / 6,
    }
    values = {"a": 0, "b": 6, "c": 10}

    assert expected_value(distribution, lambda outcome: values[outcome.labels[0]]) == pytest.approx(11 / 3)
    assert probability(distribution, lambda outcome: values[outcome.labels[0]] >= 6) == pytest.approx(1 / 2)
    assert probability(distribution, lambda outcome: values[outcome.labels[0]] >= 10) == pytest.approx(1 / 6)


@pytest.mark.parametrize(
    "entries,draws,kwargs",
    [
        ([_entry("A", "Prefix", "A", 1), _entry("A", "Prefix", "B", 1)], 1, {}),
        ([_entry("A", "Other", "A", 1)], 1, {}),
        ([_entry("A", "Prefix", "A", 1), _entry("B", "Suffix", "A", 1)], 1, {}),
        ([_entry("A", "Prefix", "A", 0)], 1, {}),
        ([_entry("A", "Prefix", "A", 1)], -1, {}),
        ([_entry("A", "Prefix", "A", 1)], 1, {"prefix_cap": -1}),
        ([_entry("A", "Prefix", "A", 1)], 1, {"initial_prefixes": 4}),
    ],
)
def test_invalid_draw_inputs_raise_value_error(
    entries: list[DrawEntry], draws: int, kwargs: dict[str, int]
) -> None:
    with pytest.raises(ValueError):
        draw_distribution(entries, draws, **kwargs)


def _royal_burgonet_entries() -> tuple[list[DrawEntry], dict[str, str]]:
    root = Path(__file__).resolve().parents[1]
    rows = json.loads((root / "data/pob_mod_explicit.json").read_text(encoding="utf-8"))["mods"]
    base_rows = json.loads((root / "data/pob_bases.json").read_text(encoding="utf-8"))["bases"]
    burgonet = next(row for row in base_rows if row["name"] == "Royal Burgonet")
    tags = set(burgonet["tags"])
    entries: list[DrawEntry] = []
    for row in rows:
        if row["level"] > 86:
            continue
        weight = next(
            (weight for key, weight in zip(row["weightKey"], row["weightVal"], strict=True) if key in tags),
            0,
        )
        if weight > 0:
            entries.append(DrawEntry(row["id"], row["type"], row["group"], weight))
    return entries, {
        "IncreasedLife9": "life",
        "ChaosResist6": "chaos",
        "FireResist8": "elemental",
        "ColdResist8": "elemental",
        "LightningResist8": "elemental",
    }


def test_real_royal_burgonet_pool_is_exact_and_normalized() -> None:
    entries, labels = _royal_burgonet_entries()
    started = time.perf_counter()
    distribution = draw_distribution(entries, 6, labels)
    elapsed = time.perf_counter() - started

    target = probability(
        distribution,
        lambda outcome: "life" in outcome.labels
        and "chaos" in outcome.labels
        and "elemental" in outcome.labels,
    )
    assert _mass(distribution) == pytest.approx(1)
    assert all(value >= 0 for value in distribution.values())
    assert target >= 0
    assert elapsed < 60


def test_parameter_file_has_provisional_count_weights_and_caps() -> None:
    root = Path(__file__).resolve().parents[1]
    rules = json.loads((root / "data/rules/ordinary.json").read_text(encoding="utf-8"))

    assert rules["rare_count_weights"] == {"4": 8, "5": 3, "6": 1}
    assert rules["magic_count_weights"] == {"1": 1, "2": 1}
    assert rules["rare_caps"] == [3, 3]
    assert rules["magic_caps"] == [1, 1]
    assert rules["confidence"] == "reimplemented-from-CoE"
