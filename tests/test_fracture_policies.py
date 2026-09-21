"""Known answers for the selected paid fracture-Life/Envy renewal policy."""

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
import random

import numpy as np
import pytest

import craftoracle.fracture_policies as fracture_policies
from craftoracle.actions import ActionData, load_action_data
from craftoracle.fracture_policies import (
    estimate_fracture_life_cost_p90,
    fracture_life_distributions,
    fracture_life_metrics,
)
from craftoracle.item_model import ItemState
from craftoracle.plan_inputs import load_loadout, load_spec


ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def real_inputs():
    data = load_action_data(ROOT)
    spec = load_spec(ROOT / "examples/helmet_life_chaos_res.yaml", data.mods)
    loadout = load_loadout(ROOT / "data/loadouts/endgame.json")
    cache: dict[object, object] = {}
    return data, spec, loadout, cache, fracture_life_distributions(spec, data, distribution_cache=cache)


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

    # Independent CDF facts for 4 * Geom(.25) + 3: the p90 is 39.
    rng = np.random.default_rng(20260921)
    costs = 4 * rng.geometric(0.25, size=50_000) + 3
    assert (costs <= 35).mean() == pytest.approx(1 - 0.75 ** 8, abs=0.01)
    assert (costs <= 39).mean() == pytest.approx(1 - 0.75 ** 9, abs=0.01)


def test_independent_direct_simulation_agrees_with_hand_mean() -> None:
    costs = _direct_hand_costs(samples=50_000, seed=20260921)
    assert sum(costs) / len(costs) == pytest.approx(34, abs=0.5)
    estimate = estimate_fracture_life_cost_p90(0.1, 0.4, 0.25, 0.5, 3, 2, 1, 5, 4)
    direct_p90 = _higher_quantile(costs, 0.9)
    assert estimate.sample_mean == pytest.approx(34, abs=4 * estimate.sample_standard_error)
    assert estimate.interval_lower <= direct_p90 <= estimate.interval_upper


def test_base_price_scales_by_expected_base_count() -> None:
    zero = fracture_life_metrics(0, 0.5, 0.25, 0.5, 0, 2, 1, 5, 4)
    raised = fracture_life_metrics(0, 0.5, 0.25, 0.5, 7, 2, 1, 5, 4)

    assert raised.mean_cost - zero.mean_cost == pytest.approx(28)


def test_real_selected_adapter_reproduces_accepted_action_values(real_inputs) -> None:
    _data, _spec, _loadout, _cache, result = real_inputs

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


def test_real_wrapper_reports_both_candidates_counts_and_terminal_mixture(real_inputs) -> None:
    data, spec, loadout, cache, _distributions = real_inputs
    policy = fracture_policies.fracture_life_envy_policy(spec, loadout, data, cache)

    audit = {row["parameters"]["alchemy_early_stop"]: row for row in policy["parameter_audit"]}
    assert audit[False]["four_mod_life9"] == pytest.approx(0.024298372342207553)
    assert audit[False]["expected_cost"] == pytest.approx(4244.571170153949)
    assert audit[True]["expected_cost"] == pytest.approx(4227.736691448135)
    assert policy["parameters"]["alchemy_early_stop"] is True
    assert policy["expected_action_counts"] == pytest.approx({
        "bases": 3.988050380133888, "alchemy": 164.0388811447735,
        "scour": 160.05083076463964, "fracturing": 3.9840671735118507,
        "envy": 16.324932396315752,
    })
    assert sum(row["probability"] for row in policy["terminal_distribution"]) == pytest.approx(1)
    fracture_stage = policy["stages"][1]
    assert fracture_stage["probability"] == pytest.approx(0.25)
    assert sum(row["probability"] for row in fracture_stage["attempt_distribution"]) == pytest.approx(1)
    assert policy["cost_confidence"] == 0.99
    assert policy["irreversible_item_destruction_risk"] == 0


@pytest.mark.parametrize("missing", ("fracturing", "Metadata/Items/Currency/CurrencyEssenceEnvy3"))
def test_wrapper_rejects_missing_permission_or_price_before_distribution(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    data = load_action_data(ROOT)
    spec = load_spec(ROOT / "examples/helmet_life_chaos_res.yaml", data.mods)
    base = load_loadout(ROOT / "data/loadouts/endgame.json")
    actions = base.allowed_actions - ({"fracturing"} if missing == "fracturing" else set())
    values = dict(base.values)
    if missing != "fracturing":
        values.pop(missing)
    loadout = replace(base, allowed_actions=frozenset(actions), values=values)
    monkeypatch.setattr(fracture_policies, "fracture_life_distributions", lambda *_args, **_kwargs: pytest.fail("distribution should not run"))

    policy = fracture_policies.fracture_life_envy_policy(spec, loadout, data, {})
    assert "reasons" in policy
    assert any("permit" in reason or "missing price" in reason for reason in policy["reasons"])


@pytest.mark.parametrize(
    "changed",
    [
        lambda spec: replace(spec, value_table={"IncreasedLife": {1: 1.0}}, threshold=1.0, values_note="fixture", required_mods=(), any_of=()),
        lambda spec: replace(spec, required_mods=spec.required_mods[:1]),
        lambda spec: replace(spec, required_mods=(*spec.required_mods, spec.required_mods[0])),
        lambda spec: replace(spec, any_of=()),
        lambda spec: replace(spec, item_level=85),
    ],
)
def test_adapter_rejects_changed_selected_predicate(changed) -> None:
    data = load_action_data(ROOT)
    spec = load_spec(ROOT / "examples/helmet_life_chaos_res.yaml", data.mods)

    with pytest.raises(ValueError, match="Life9/Chaos6/any elemental8|Royal Burgonet86"):
        fracture_life_distributions(changed(spec), data)


def test_zero_and_unreachable_probability_boundaries_are_explicit() -> None:
    early_only = fracture_life_metrics(0.25, 0, 0, 0, 1, 2, 3, 4, 5)
    assert early_only.expected_bases == pytest.approx(1)
    assert early_only.expected_envies == 0
    assert early_only.mean_cost == pytest.approx(18)
    assert estimate_fracture_life_cost_p90(0.25, 0, 0, 0, 1, 2, 3, 4, 5).p90 >= 0

    with pytest.raises(ValueError, match="unreachable"):
        fracture_life_metrics(0, 0, 0.25, 1, 0, 1, 1, 1, 1)
    with pytest.raises(ValueError, match="unreachable"):
        fracture_life_metrics(0, 0.5, 0, 1, 0, 1, 1, 1, 1)
    with pytest.raises(ValueError, match="zero target"):
        fracture_life_metrics(0, 0.5, 0.25, 0, 0, 1, 1, 1, 1)
    with pytest.raises(ValueError, match="int64"):
        estimate_fracture_life_cost_p90(0, 1e-20, 1, 1, 0, 1, 1, 1, 1)


@pytest.mark.parametrize(
    "inputs",
    [
        (math.nan, 0, 0, 0),
        (0, math.inf, 0, 0),
        (0.8, 0.3, 0, 0),
        (0, 0.5, -0.1, 1),
    ],
)
def test_invalid_probability_inputs_are_rejected(inputs: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError):
        fracture_life_metrics(*inputs, 0, 1, 1, 1, 1)


def test_caller_cache_tracks_resolved_weight_changes() -> None:
    data = _tiny_action_data()
    cache: dict[object, object] = {}
    item = ItemState("Base", 1, "normal")
    labels = {"A": "target"}
    first = fracture_policies._cached_distribution(cache, "alchemy", item, data, labels)
    original = data.mods["A"]["weightVal"][0]
    data.mods["A"]["weightVal"][0] = original + 1
    try:
        second = fracture_policies._cached_distribution(cache, "alchemy", item, data, labels)
    finally:
        data.mods["A"]["weightVal"][0] = original

    assert len(cache) == 2
    assert second != first


def _tiny_action_data() -> ActionData:
    def mod(mod_id: str, side: str) -> dict:
        return {
            "id": mod_id, "type": side, "group": mod_id, "level": 1,
            "weightKey": ["default"], "weightVal": [1], "modTags": [],
            "source_path": "ModExplicit.lua",
        }

    return ActionData(
        bases={"Base": {"name": "Base", "type": "Helmet", "tags": {"default": True}}},
        mods={
            "A": mod("A", "Prefix"), "B": mod("B", "Suffix"),
            "C": mod("C", "Prefix"), "D": mod("D", "Suffix"),
            "E": mod("E", "Prefix"),
        },
        bench={}, essences={},
        rules={
            "magic_caps": [1, 1], "rare_caps": [3, 3],
            "magic_count_weights": {"1": 1, "2": 1},
            "rare_count_weights": {"4": 8, "5": 3, "6": 1},
        },
    )


def _direct_hand_costs(*, samples: int, seed: int) -> list[float]:
    """Direct trial simulator, independent from the vectorized policy law."""
    rng = random.Random(seed)
    costs: list[float] = []
    for _ in range(samples):
        cost = 0.0
        while True:
            cost += 3  # fresh base
            while True:
                cost += 2  # Alchemy
                roll = rng.random()
                if roll < 0.1:  # early completion
                    costs.append(cost)
                    break
                if roll < 0.5:  # four-mod Life9 preparation
                    cost += 5  # Fracturing
                    if rng.random() < 0.25:
                        while True:
                            cost += 4
                            if rng.random() < 0.5:
                                costs.append(cost)
                                break
                        break
                    break  # wrong fracture: replacement base
                cost += 1  # Scour before the next Alchemy on this base
            if len(costs) == _ + 1:
                break
    return costs


def _higher_quantile(values: list[float], probability: float) -> float:
    return sorted(values)[math.ceil(probability * len(values)) - 1]
