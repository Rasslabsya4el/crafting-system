"""Known answers for the selected paid fracture-Life/Envy renewal policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from craftoracle.actions import load_action_data
from craftoracle.fracture_policies import (
    estimate_fracture_life_cost_p90,
    fracture_life_distributions,
    fracture_life_metrics,
)
from craftoracle.plan_inputs import load_spec


ROOT = Path(__file__).parents[1]


def test_hand_case_exact_mean_and_counts_without_early_stop() -> None:
    result = fracture_life_metrics(0, 0.5, 0.25, 0.5, 3, 2, 1, 5, 4)

    assert result.mean_cost == pytest.approx(60)
    assert result.expected_bases == pytest.approx(4)
    assert result.expected_alchemies == pytest.approx(8)
    assert result.expected_scours == pytest.approx(4)
    assert result.expected_fracturings == pytest.approx(4)
    assert result.expected_envies == pytest.approx(2)
    assert result.wrong_fracture_risk_per_trial == pytest.approx(0.75)
    assert result.expected_discarded_bases == pytest.approx(3)
    assert result.irreversible_item_destruction_risk == 0


def test_hand_case_early_stop_exact_mean_and_counts() -> None:
    result = fracture_life_metrics(0.1, 0.4, 0.25, 0.5, 3, 2, 1, 5, 4)

    assert result.mean_cost == pytest.approx(34)
    assert result.expected_bases == pytest.approx(2.5)
    assert result.expected_alchemies == pytest.approx(5)
    assert result.expected_scours == pytest.approx(2.5)
    assert result.expected_fracturings == pytest.approx(2)
    assert result.expected_envies == pytest.approx(1)


def test_seeded_p90_law_matches_bounded_fixture_and_replays() -> None:
    first = estimate_fracture_life_cost_p90(0, 1, 0.25, 1, 1, 1, 0, 2, 3)
    replay = estimate_fracture_life_cost_p90(0, 1, 0.25, 1, 1, 1, 0, 2, 3)

    assert first == replay
    assert first.mean_cost == pytest.approx(19)
    assert first.p90 == pytest.approx(39)
    assert first.interval_lower <= first.p90 <= first.interval_upper
    assert first.samples == 50_000
    assert first.seed == 20260921
    assert first.confidence == 0.99
    assert first.dkw_epsilon > 0


def test_base_price_scales_by_expected_base_count() -> None:
    zero = fracture_life_metrics(0, 0.5, 0.25, 0.5, 0, 2, 1, 5, 4)
    raised = fracture_life_metrics(0, 0.5, 0.25, 0.5, 7, 2, 1, 5, 4)

    assert raised.mean_cost - zero.mean_cost == pytest.approx(28)


def test_real_selected_adapter_reproduces_accepted_action_values() -> None:
    data = load_action_data(ROOT)
    spec = load_spec(ROOT / "examples/helmet_life_chaos_res.yaml", data.mods)
    result = fracture_life_distributions(spec, data)

    assert result.fracture_probability == pytest.approx(0.25)
    assert result.finishing_probability == pytest.approx(0.06101200110346221)
    assert len(result.finishing_distribution) == 30
    assert sum(result.finishing_distribution.values()) == pytest.approx(1)
    assert result.preparation_early_probability == pytest.approx(0.000024282088455126462)
    assert result.preparation_probability == pytest.approx(0.02428733447648724)


def test_adapter_rejects_another_base_without_guessing_tier_mapping() -> None:
    data = load_action_data(ROOT)
    spec = load_spec(ROOT / "examples/bow_value_table.yaml", data.mods)

    with pytest.raises(ValueError, match="ordinary Royal Burgonet86"):
        fracture_life_distributions(spec, data)
