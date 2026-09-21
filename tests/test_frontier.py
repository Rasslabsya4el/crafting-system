"""Checks for the documented policy frontier and utility threshold comparison."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest

import craftoracle.policies as policies
from craftoracle.actions import load_action_data
from craftoracle.costs import geometric_cost
from craftoracle.distributions import OutcomeClass
from craftoracle.frontier import evaluate_frontier, pareto_frontier
from craftoracle.plan_inputs import load_loadout, load_spec
from craftoracle.policies import _conditional_expected_utility


ROOT = Path(__file__).resolve().parents[1]


def _record(identifier: str, cost: float, p90: float, utility: float, risk: float = 0.0) -> dict[str, float | str]:
    return {
        "id": identifier,
        "expected_cost": cost,
        "cost_p90": p90,
        "expected_utility": utility,
        "irreversible_failure_risk": risk,
    }


def test_pareto_frontier_matches_documented_two_threshold_case() -> None:
    # Source: docs/design/build_contract.md, "Synthetic acceptance case: one
    # stage, two stopping rules". These are invented mathematical fixtures.
    threshold_six_cost = geometric_cost(1 / 2, 2)
    threshold_ten_cost = geometric_cost(1 / 6, 2)
    stage_expected_utility = (1 / 2) * 0 + (1 / 3) * 6 + (1 / 6) * 10
    threshold_six_utility = ((1 / 3) * 6 + (1 / 6) * 10) / (1 / 2)

    assert stage_expected_utility == pytest.approx(11 / 3)
    assert (threshold_six_cost.expected_cost, threshold_six_cost.cost_p90) == pytest.approx((4, 8))
    assert (threshold_ten_cost.expected_cost, threshold_ten_cost.cost_p90) == pytest.approx((12, 26))
    assert threshold_six_utility == pytest.approx(22 / 3)

    records = [
        _record("spam@6", threshold_six_cost.expected_cost, threshold_six_cost.cost_p90, threshold_six_utility),
        _record("spam@10", threshold_ten_cost.expected_cost, threshold_ten_cost.cost_p90, 10),
        _record("dominated", 5, 9, 6),
        _record("duplicate@6", threshold_six_cost.expected_cost, threshold_six_cost.cost_p90, threshold_six_utility),
        _record("cheaper-but-riskier", 3, 8, threshold_six_utility, 0.1),
    ]

    assert [record["id"] for record in pareto_frontier(records)] == [
        "spam@6",
        "spam@10",
        "duplicate@6",
        "cheaper-but-riskier",
    ]


def test_pareto_frontier_requires_every_finite_metric_without_defaulting_risk() -> None:
    valid = _record("risk-is-explicit", 4, 8, 22 / 3, 0)
    assert pareto_frontier([valid]) == [valid]

    missing_risk = dict(valid)
    missing_risk.pop("irreversible_failure_risk")
    with pytest.raises(ValueError, match="irreversible_failure_risk"):
        pareto_frontier([missing_risk])

    nonfinite_cost = dict(valid, expected_cost=float("nan"))
    with pytest.raises(ValueError, match="expected_cost"):
        pareto_frontier([nonfinite_cost])


@dataclass(frozen=True)
class _UtilitySpec:
    value_table: dict[str, dict[int, float]]
    threshold: float


def test_evaluate_frontier_compares_thresholds_with_one_raw_distribution_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _UtilitySpec({"value": {1: 10}}, 6)
    cache_ids: list[int] = []
    raw_distribution_calls = 0

    def fake_evaluate_policies(current_spec, loadout, data, *, distribution_cache):
        nonlocal raw_distribution_calls
        cache_ids.append(id(distribution_cache))
        if "raw distribution" not in distribution_cache:
            distribution_cache["raw distribution"] = object()
            raw_distribution_calls += 1
        if current_spec.threshold == 6:
            ranked = [_record("spam", 4, 8, 22 / 3)]
        else:
            ranked = [_record("spam", 12, 26, 10)]
        return {
            "ranked": ranked,
            "unavailable": [{"id": "blocked", "name": "Blocked", "reasons": ["fixture"]}],
            "assumptions": ["fixture"],
        }

    monkeypatch.setattr("craftoracle.frontier.evaluate_policies", fake_evaluate_policies)
    result = evaluate_frontier(spec, object(), object(), thresholds=(6, 10))

    assert spec.threshold == 6
    assert raw_distribution_calls == 1
    assert len(set(cache_ids)) == 1
    assert [policy["id"] for policy in result["ranked"]] == ["spam@6", "spam@10"]
    assert [policy["stopping_threshold"] for policy in result["ranked"]] == [6, 10]
    assert all(policy["frontier"] for policy in result["ranked"])
    assert [candidate["id"] for candidate in result["unavailable"]] == ["blocked@6", "blocked@10"]


def test_evaluate_frontier_reuses_real_bow_raw_distributions(monkeypatch: pytest.MonkeyPatch) -> None:
    # Source: docs/specs/2026-09-21-stretch-frontier.md, real bow checkable
    # case. The restricted loadout avoids the magic policy's MC p90 fallback.
    data = load_action_data(ROOT)
    spec = load_spec(ROOT / "examples/bow_value_table.yaml", data.mods)
    loadout = replace(
        load_loadout(ROOT / "data/loadouts/endgame.json"),
        allowed_actions=frozenset({"alchemy", "chaos", "scour"}),
        allowed_essences=frozenset(),
        allowed_bench=frozenset(),
    )
    original = policies.action_distribution
    calls = 0

    def spy(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(policies, "action_distribution", spy)
    result = evaluate_frontier(spec, loadout, data, thresholds=(60, 100))

    assert calls == 2
    policies_by_id = {policy["id"]: policy for policy in result["ranked"]}
    assert policies_by_id["alchemy-scour@100"]["stages"][-1]["probability"] <= policies_by_id[
        "alchemy-scour@60"
    ]["stages"][-1]["probability"]


@pytest.mark.parametrize(
    ("thresholds", "message"),
    [
        ((), "non-empty"),
        ((6, 6), "distinct"),
        ((float("nan"),), "finite"),
        ((5,), "at least"),
    ],
)
def test_evaluate_frontier_rejects_invalid_comparison_thresholds(thresholds: tuple[float, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        evaluate_frontier(_UtilitySpec({"value": {1: 10}}, 6), object(), object(), thresholds=thresholds)


@dataclass(frozen=True)
class _CriteriaSpec:
    value_table: None = None
    threshold: None = None


@pytest.mark.parametrize(
    ("argument", "message"),
    [
        ("bad", "comma-separated"),
        ("", "non-empty"),
        ("60,60", "distinct"),
        ("nan,100", "finite"),
        ("50,100", "at least"),
    ],
)
def test_cli_returns_normal_input_errors_for_invalid_comparison_thresholds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], argument: str, message: str
) -> None:
    monkeypatch.setattr("craftoracle.cli.load_action_data", lambda root: type("Data", (), {"mods": {}})())
    monkeypatch.setattr("craftoracle.cli.load_spec", lambda path, mods: _UtilitySpec({"value": {1: 10}}, 60))
    monkeypatch.setattr("craftoracle.cli.load_loadout", lambda path: type("Loadout", (), {"allowed_actions": {"alchemy"}})())

    from craftoracle import cli

    with pytest.raises(SystemExit) as error:
        cli.main(["plan", "item.yaml", "--loadout", "loadout.json", "--compare-thresholds", argument])

    assert error.value.code == 2
    assert message in capsys.readouterr().err


def test_cli_rejects_comparison_thresholds_for_required_mod_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("craftoracle.cli.load_action_data", lambda root: type("Data", (), {"mods": {}})())
    monkeypatch.setattr("craftoracle.cli.load_spec", lambda path, mods: _CriteriaSpec())
    monkeypatch.setattr("craftoracle.cli.load_loadout", lambda path: type("Loadout", (), {"allowed_actions": {"alchemy"}})())

    from craftoracle import cli

    with pytest.raises(SystemExit) as error:
        cli.main(["plan", "item.yaml", "--loadout", "loadout.json", "--compare-thresholds", "60,100"])

    assert error.value.code == 2
    assert "utility" in capsys.readouterr().err


def test_evaluate_frontier_keeps_single_threshold_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_evaluate_policies(spec, loadout, data, *, distribution_cache):
        return {
            "ranked": [_record("spam", 4, 8, 22 / 3)],
            "unavailable": [],
            "assumptions": ["fixture"],
        }

    monkeypatch.setattr("craftoracle.frontier.evaluate_policies", fake_evaluate_policies)

    result = evaluate_frontier(_UtilitySpec({"value": {1: 10}}, 6), object(), object())

    assert result["ranked"][0]["id"] == "spam"
    assert result["ranked"][0]["frontier"] is True
    assert "stopping_threshold" not in result["ranked"][0]


@dataclass(frozen=True)
class _ConstantUtilitySpec:
    value_table: dict[str, dict[int, float]]
    threshold: float = 1

    @staticmethod
    def utility(outcome: object) -> float:
        return 100.0


def test_conditional_utility_keeps_unequal_constant_accepted_utilities_exact() -> None:
    distribution = {
        OutcomeClass(("first",), 1, 0): 0.0053171974267639515,
        OutcomeClass(("second",), 0, 1): 0.00008640408995079098,
        OutcomeClass(("third",), 1, 1): 0.9945963984832853,
    }

    assert _conditional_expected_utility(_ConstantUtilitySpec({"value": {1: 100}}), distribution) == 100.0
