from __future__ import annotations

import math
import random
from pathlib import Path

import pytest

from craftoracle.actions import load_action_data, scour_item
from craftoracle.item_model import ItemState
from craftoracle.quality import apply_catalyst, catalyst_distribution, plan_catalyst


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def action_data():
    return load_action_data(ROOT)


def ring(level: int = 86, **changes) -> ItemState:
    return ItemState("Vermillion Ring", level, "rare", **changes)


def test_increment_formula_and_cap_are_exact(action_data) -> None:
    low = catalyst_distribution(ring(1), action_data, "Abrasive")
    assert {(state.quality, state.catalyst_type): probability for state, probability in low.items()} == {
        (20, "Abrasive"): 1.0
    }
    high = catalyst_distribution(ring(95), action_data, "Abrasive")
    assert {(state.quality, state.catalyst_type): probability for state, probability in high.items()} == {
        (1, "Abrasive"): 1.0
    }

    at_86 = catalyst_distribution(ring(), action_data, "Abrasive")
    probabilities = {state.quality: probability for state, probability in at_86.items()}
    assert probabilities[1] == pytest.approx(0.5933528496169547)
    assert probabilities[2] == pytest.approx(0.40664715038304533)
    assert sum(at_86.values()) == pytest.approx(1.0)


def test_validation_switching_and_metadata_preservation(action_data) -> None:
    original = ring(quality=20, catalyst_type="Abrasive")
    switched = catalyst_distribution(original, action_data, "Prismatic")
    assert {(state.quality, state.catalyst_type): probability for state, probability in switched.items()} == {
        (1, "Prismatic"): pytest.approx(0.5933528496169547),
        (2, "Prismatic"): pytest.approx(0.40664715038304533),
    }
    assert all(state.base_name == original.base_name and state.rarity == original.rarity for state in switched)
    assert all(state.quality <= 20 for state in switched)

    with pytest.raises(ValueError, match="jewellery"):
        catalyst_distribution(ItemState("Royal Burgonet", 86, "rare"), action_data, "Abrasive")
    with pytest.raises(ValueError, match="rarity"):
        catalyst_distribution(ItemState("Vermillion Ring", 86, "unique"), action_data, "Abrasive")
    with pytest.raises(NotImplementedError, match="Q9"):
        catalyst_distribution(ring(corrupted=True), action_data, "Abrasive")
    with pytest.raises(ValueError, match="supported regular catalyst"):
        catalyst_distribution(ring(), action_data, "Tainted")
    with pytest.raises(ValueError, match="quality"):
        catalyst_distribution(ring(quality=21), action_data, "Abrasive")
    with pytest.raises(ValueError, match="catalyst_type"):
        catalyst_distribution(ring(quality=1), action_data, "Abrasive")


def test_seeded_sampling_and_ordinary_action_keep_quality_metadata(action_data) -> None:
    item = ring(quality=19, catalyst_type="Abrasive")
    result = apply_catalyst(item, action_data, "Abrasive", rng=random.Random(20260921))
    assert result.quality == 20
    assert result.catalyst_type == "Abrasive"
    assert scour_item(item, action_data) == ItemState(
        "Vermillion Ring", 86, "normal", quality=19, catalyst_type="Abrasive"
    )


def test_finite_plan_exact_edges_and_costs(action_data, monkeypatch) -> None:
    plan = plan_catalyst(ring(), action_data, "Abrasive", 20, 2)
    assert plan["expected_applications"] == pytest.approx(14.423723570517014)
    assert plan["applications_p90"] == 16
    assert plan["expected_cost"] == pytest.approx(28.847447141034028)
    assert plan["cost_p90"] == pytest.approx(32.0)
    assert sum(probability for count, probability in plan["count_distribution"].items() if count <= 15) == pytest.approx(
        0.7978286383138568
    )
    assert sum(probability for count, probability in plan["count_distribution"].items() if count <= 16) == pytest.approx(
        0.9413199321203
    )
    assert sum(plan["final_quality_distribution"].values()) == pytest.approx(1.0)
    assert all(state.quality <= 20 for state in plan["final_quality_distribution"])

    complete = plan_catalyst(ring(quality=20, catalyst_type="Abrasive"), action_data, "Abrasive", 20, 2)
    assert complete["count_distribution"] == {0: 1.0}
    assert complete["expected_cost"] == 0.0
    switched = plan_catalyst(ring(quality=20, catalyst_type="Prismatic"), action_data, "Abrasive", 20, 2)
    assert switched["count_distribution"] == plan["count_distribution"]

    one_step = plan_catalyst(ring(quality=19, catalyst_type="Abrasive"), action_data, "Abrasive", 20, 2)
    assert one_step["count_distribution"] == {1: 1.0}
    assert plan_catalyst(ring(95, quality=18, catalyst_type="Abrasive"), action_data, "Abrasive", 20, 1)[
        "expected_applications"
    ] == 2.0
    monkeypatch.setattr("craftoracle.quality._increment_distribution", lambda item_level: {2: 1.0})
    assert plan_catalyst(ring(95, quality=17, catalyst_type="Abrasive"), action_data, "Abrasive", 20, 1)[
        "expected_applications"
    ] == 2.0

    with pytest.raises(ValueError, match="target_quality"):
        plan_catalyst(ring(), action_data, "Abrasive", 0, 1)
    with pytest.raises(ValueError, match="unit_price"):
        plan_catalyst(ring(), action_data, "Abrasive", 20, math.inf)


def test_independent_seeded_repeated_application_cdf_matches_exact_bound(action_data) -> None:
    seed = 20260921
    samples = 10_000
    exact = plan_catalyst(ring(), action_data, "Abrasive", 20, 1)
    exact_cdf = sum(probability for count, probability in exact["count_distribution"].items() if count <= 16)
    rng = random.Random(seed)
    completed_by_16 = 0
    for _ in range(samples):
        item = ring()
        for applications in range(1, 21):
            item = apply_catalyst(item, action_data, "Abrasive", rng=rng)
            if item.quality >= 20:
                if applications <= 16:
                    completed_by_16 += 1
                break
    bound = math.sqrt(math.log(2000) / (2 * samples))
    assert bound == pytest.approx(0.019494746035204052)
    assert abs(completed_by_16 / samples - exact_cdf) <= bound
