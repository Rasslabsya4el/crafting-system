"""Seeded Monte Carlo checks against the exact grouped-draw kernel.

The real-pool fixtures use committed PoB projection data.  Their eligible-pool
semantics are covered by the item-model and affix-generation fact sheets; this
module only checks sampling mathematics.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from craftoracle.distributions import DrawEntry, OutcomeClass, draw_distribution
from craftoracle.item_model import ItemState, load_item_data, resolve_pool
from craftoracle.monte_carlo import (
    estimate_compound_cost_p90,
    sample_distribution,
    wilson_interval,
)


ROOT = Path(__file__).parents[1]


def _entry(mod_id: str, side: str, group: str, weight: int) -> DrawEntry:
    return DrawEntry(mod_id, side, group, weight)


def _hoeffding_bound(classes: int, samples: int, alpha: float = 0.001) -> float:
    return math.sqrt(math.log(2 * classes / alpha) / (2 * samples))


def _target_probability(distribution: dict[OutcomeClass, float]) -> float:
    return sum(mass for outcome, mass in distribution.items() if "target" in outcome.labels)


def test_synthetic_hand_case_reproducibility_and_wilson_intervals() -> None:
    entries = [
        _entry("A", "Prefix", "A", 1),
        _entry("B", "Prefix", "B", 1),
        _entry("C", "Prefix", "C", 2),
    ]
    labels = {"A": "A", "B": "B", "C": "C"}
    first = sample_distribution(entries, 2, labels, samples=12_000, seed=314159)
    second = sample_distribution(entries, 2, labels, samples=12_000, seed=314159)
    exact = draw_distribution(entries, 2, labels)

    assert first == second
    assert sum(first.counts.values()) == first.samples
    assert sum(first.probabilities.values()) == pytest.approx(1)
    assert first.method == "estimated"
    assert sum(mass for outcome, mass in exact.items() if "A" in outcome.labels) == pytest.approx(7 / 12)
    assert exact[OutcomeClass(("A", "B"), 2, 0)] == pytest.approx(1 / 6)

    inclusion = sum(
        mass for outcome, mass in first.probabilities.items() if "A" in outcome.labels
    )
    pair = first.probabilities.get(OutcomeClass(("A", "B"), 2, 0), 0.0)
    bound = _hoeffding_bound(2, first.samples)
    assert abs(inclusion - 7 / 12) <= bound
    assert abs(pair - 1 / 6) <= bound
    assert wilson_interval(0, 10)[1] > 0
    assert 0 < wilson_interval(1, 1)[0] < 1


def test_caps_blocked_groups_and_exhaustion_keep_terminal_identity() -> None:
    entries = [
        _entry("A", "Prefix", "A", 1),
        _entry("B", "Suffix", "B", 3),
        _entry("C", "Suffix", "C", 2),
    ]
    result = sample_distribution(
        entries,
        4,
        {"A": "a", "B": "b", "C": "c"},
        samples=200,
        seed=7,
        prefix_cap=1,
        suffix_cap=1,
        initial_labels=("seed",),
        blocked_groups=("B",),
    )

    assert set(result.probabilities) == {OutcomeClass(("a", "c", "seed"), 1, 1)}
    assert sum(result.counts.values()) == 200


@pytest.mark.parametrize(
    ("base_name", "draws", "target_id", "seed"),
    [
        ("Royal Burgonet", 6, "IncreasedLife9", 202609211),
        ("Iron Ring", 2, "Strength8", 202609212),
        ("Simple Robe", 3, "LocalIncreasedEnergyShield8", 202609213),
        ("Iron Gauntlets", 3, "Strength8", 202609214),
        ("Crude Bow", 2, "LocalAddedFireDamageTwoHand7", 202609215),
    ],
)
def test_real_pools_match_exact_distribution_with_hoeffding_bound(
    base_name: str, draws: int, target_id: str, seed: int
) -> None:
    bases, mods = load_item_data(ROOT / "data/pob_bases.json", ROOT / "data/pob_mod_families.json")
    entries = resolve_pool(ItemState(base_name, 86, "rare"), bases, mods)
    labels = {target_id: "target"}
    exact = draw_distribution(entries, draws, labels)
    sampled = sample_distribution(entries, draws, labels, samples=8_000, seed=seed)

    keys = set(exact) | set(sampled.probabilities)
    bound = _hoeffding_bound(len(keys), sampled.samples)
    deviation = max(abs(exact.get(key, 0.0) - sampled.probabilities.get(key, 0.0)) for key in keys)
    assert deviation <= bound
    assert abs(_target_probability(exact) - _target_probability(sampled.probabilities)) <= bound
    assert sum(sampled.probabilities.values()) == pytest.approx(1)


def test_invalid_sampling_input_is_rejected() -> None:
    valid = [_entry("A", "Prefix", "A", 1)]
    with pytest.raises(ValueError):
        sample_distribution(valid, 1, samples=0, seed=1)
    with pytest.raises(ValueError):
        sample_distribution(valid, 1, samples=1, seed=True)
    with pytest.raises(ValueError):
        sample_distribution([_entry("A", "Prefix", "A", 1), _entry("B", "Suffix", "A", 1)], 1, samples=1, seed=1)
    with pytest.raises(ValueError):
        sample_distribution(valid, 1, samples=1, seed=1, initial_prefixes=4)


def test_compound_cost_estimator_has_dkw_interval_and_replays_seed() -> None:
    result = estimate_compound_cost_p90(
        0.5, 2, 2, 0.5, samples=50_000, seed=20260921
    )
    replay = estimate_compound_cost_p90(
        0.5, 2, 2, 0.5, samples=50_000, seed=20260921
    )
    assert result == replay
    assert result.interval_lower <= 8 <= result.interval_upper
    assert result.dkw_epsilon > 0

    deterministic = estimate_compound_cost_p90(
        1, 0, 0, 0, samples=50_000, seed=4
    )
    assert deterministic.p90 == deterministic.interval_lower == deterministic.interval_upper == 0


@pytest.mark.parametrize(
    "args",
    [
        (0, 1, 1, 0.5),
        (math.nan, 1, 1, 0.5),
        (0.5, -1, 1, 0.5),
        (0.5, 2, 1, 0.5),
        (0.5, 1, 1, math.nan),
    ],
)
def test_compound_cost_estimator_rejects_invalid_inputs(args: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError):
        estimate_compound_cost_p90(*args, samples=50_000)
