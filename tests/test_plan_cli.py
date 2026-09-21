from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

from craftoracle import cli
from craftoracle.distributions import OutcomeClass


ROOT = Path(__file__).resolve().parents[1]
# Accepted provisional-model predictions, not game measurements:
# docs/specs/2026-09-21-policy-evaluation.md, Acceptance numbers / source.
HELMET_PROBABILITY = 0.000024282088455126466
ENVY_PROBABILITY = 0.0025940606844434217


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, "-m", "craftoracle", *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _distribution() -> dict[OutcomeClass, float]:
    return {
        OutcomeClass(("IncreasedLife:1", "ChaosResistance:1", "ColdResistance:1"), 1, 3): 0.5,
        OutcomeClass(("IncreasedLife:1", "ChaosResistance:1", "FireResistance:1"), 1, 3): 0.5,
    }


def _policy(identifier: str, name: str, probability: float, cost: float) -> dict:
    return {
        "id": identifier,
        "name": name,
        "stages": [{
            "name": "Rare roll",
            "probability": probability,
            "expected_attempts": 1 / probability,
            "actions": ["Alchemy", "Chaos"],
            "decisions": ["Keep target; otherwise restart."],
            "target_probability_after_stage": probability,
            "attempt_distribution": _distribution(),
        }],
        "expected_cost": cost,
        "cost_p90": cost * 2,
        "cost_method": "exact-geometric",
        "expected_utility": 1.0,
        "irreversible_failure_risk": 0.0,
        "rare_inputs": [],
        "assumptions": ["ordinary 3.29/Q9 scope"],
        "steps": ["Roll a rare item."],
        "decision_points": ["Restart on every non-target."],
        "within_budget": True,
        "frontier": False,
        "method": "exact",
        "p90_over_budget": False,
        "terminal_distribution": _distribution(),
    }


def _result() -> dict:
    return {
        "ranked": [
            _policy("alchemy-scour", "Alchemy and Scour", 0.000024282088455126466, 41182),
            _policy("chaos", "Chaos spam", 0.000024282088455126466, 41183),
            _policy("essence-envy", "Deafening Envy", 0.0025940606844434217, 1927),
        ],
        "unavailable": [{"id": "harvest", "name": "Harvest", "reasons": ["Q6 is out of scope"]}],
        "assumptions": ["prices are invented caller inputs", "exact under provisional assumptions"],
    }


def _evaluate(spec, loadout, data):
    assert spec.base == "Royal Burgonet"
    assert loadout.unit == "chaos-equivalent"
    return _result()


def test_root_module_bootstrap_needs_no_pythonpath() -> None:
    completed = _run_cli("--help")

    assert completed.returncode == 0
    assert "plan" in completed.stdout


def test_json_contract_preserves_policy_fields_and_outcome_distribution() -> None:
    document = cli.evaluate_plan(
        "examples/helmet_life_chaos_res.yaml",
        "data/loadouts/endgame.json",
        evaluator=_evaluate,
    )

    serialized = json.dumps(document, allow_nan=False)
    loaded = json.loads(serialized)
    assert loaded["schema_version"] == 1
    assert loaded["input"] == {
        "name": "Royal Burgonet T1 life, chaos resistance, and elemental resistance",
        "base": "Royal Burgonet",
        "item_level": 86,
        "quality": 20,
        "flags": {
            "corrupted": False,
            "influenced": False,
            "fractured": False,
            "synthesised": False,
            "mirrored": False,
            "split": False,
        },
        "sources": loaded["input"]["sources"],
        "utility_threshold": None,
        "values_note": None,
    }
    assert loaded["prices"]["unit"] == "chaos-equivalent"
    assert len(loaded["ranked"]) == 3
    assert {policy["id"] for policy in loaded["ranked"]} == {"alchemy-scour", "chaos", "essence-envy"}
    for policy in loaded["ranked"]:
        assert policy["steps"] and policy["decision_points"] and policy["assumptions"]
        assert policy["cost_method"] == "exact-geometric"
        for stage in policy["stages"]:
            assert 0 <= stage["probability"] <= 1
            assert stage["expected_attempts"] > 0
            assert sum(entry["probability"] for entry in stage["attempt_distribution"]) == pytest.approx(1)
        assert sum(entry["probability"] for entry in policy["terminal_distribution"]) == pytest.approx(1)
        assert isinstance(policy["terminal_distribution"], list)


def test_text_table_retains_tiny_probability_and_decisions() -> None:
    document = cli.evaluate_plan(
        "examples/helmet_life_chaos_res.yaml",
        "data/loadouts/endgame.json",
        evaluator=_evaluate,
    )
    output = cli.format_plan(document)

    assert "2.42820884551e-05" in output
    assert "expected attempts" in output
    assert "Alchemy and Scour" in output
    assert "Steps:" in output
    assert "Decisions:" in output
    assert "Shared assumptions:" in output
    assert "Actions: Alchemy; Chaos" in output
    assert "Budget: 100000 chaos-equivalent" in output


def test_text_format_allows_stages_without_target_after_probability() -> None:
    result = _result()
    result["ranked"] = result["ranked"][:1]
    result["ranked"][0]["stages"][0].pop("target_probability_after_stage")
    document = cli.evaluate_plan(
        "examples/helmet_life_chaos_res.yaml",
        "data/loadouts/endgame.json",
        evaluator=lambda spec, loadout, data: result,
    )

    assert "target after stage" not in cli.format_plan(document)


def test_estimated_p90_metadata_is_preserved_and_shown() -> None:
    result = _result()
    result["ranked"][0].update({
        "cost_p90_interval": [80.0, 120.0],
        "cost_sample_count": 50_000,
        "cost_seed": 20260921,
        "cost_error_bound": 0.01,
    })
    document = cli.evaluate_plan(
        "examples/helmet_life_chaos_res.yaml",
        "data/loadouts/endgame.json",
        evaluator=lambda spec, loadout, data: result,
    )

    assert document["ranked"][0]["cost_p90_interval"] == [80.0, 120.0]
    output = cli.format_plan(document)
    assert "Estimated p90 uncertainty: 80-120 chaos-equivalent" in output
    assert "samples=50000, seed=20260921, error bound=0.01" in output


def test_real_helmet_json_subprocess_has_all_ranked_policies() -> None:
    completed = _run_cli(
        "plan",
        "examples/helmet_life_chaos_res.yaml",
        "--loadout",
        "data/loadouts/endgame.json",
        "--json",
    )

    assert completed.returncode == 0, completed.stderr
    document = json.loads(completed.stdout)
    assert document["schema_version"] == 1
    assert document["input"]["base"] == "Royal Burgonet"
    assert document["input"]["item_level"] == 86
    assert document["prices"]["unit"] == "chaos-equivalent"
    assert len(document["ranked"]) == 9
    assert document["unavailable"] == []
    policies = {policy["id"]: policy for policy in document["ranked"]}
    assert policies["chaos-spam"]["stages"][-1]["probability"] == pytest.approx(HELMET_PROBABILITY)
    assert policies["alchemy-scour"]["stages"][-1]["probability"] == pytest.approx(HELMET_PROBABILITY)
    assert policies["essence-CurrencyEssenceEnvy3"]["stages"][-1]["probability"] == pytest.approx(ENVY_PROBABILITY)
    assert policies["magic-regal-exalt"]["cost_method"] == "estimated p90; exact mean"
    assert policies["magic-regal-exalt"]["cost_p90_interval"]
    assert policies["magic-regal-exalt"]["cost_sample_count"] == 50_000
    for policy in document["ranked"]:
        assert math.isfinite(policy["expected_cost"])
        assert math.isfinite(policy["cost_p90"])
        assert policy["steps"] and policy["decision_points"] and policy["assumptions"]
        assert isinstance(policy["within_budget"], bool)
        assert isinstance(policy["p90_over_budget"], bool)
        assert sum(row["probability"] for row in policy["terminal_distribution"]) == pytest.approx(1)
        for stage in policy["stages"]:
            assert 0 <= stage["probability"] <= 1
            assert stage["expected_attempts"] > 0
            assert stage["actions"] and stage["decisions"]
            assert sum(row["probability"] for row in stage["attempt_distribution"]) == pytest.approx(1)

    text = cli.format_plan(document)
    assert "2.42820884551e-05" in text
    assert "roll protected life prefix" in text
    assert "Estimated p90 uncertainty:" in text


def test_real_bow_threshold_subprocess_changes_utility_stop_rule() -> None:
    completed = _run_cli(
        "plan",
        "examples/bow_value_table.yaml",
        "--loadout",
        "data/loadouts/endgame.json",
        "--threshold",
        "100",
        "--json",
    )

    assert completed.returncode == 0, completed.stderr
    document = json.loads(completed.stdout)
    assert document["input"]["utility_threshold"] == 100
    assert document["input"]["values_note"].startswith("Invented additive utility")
    assert len(document["ranked"]) == 6
    assert len(document["unavailable"]) == 3
    assert all(policy["expected_utility"] == pytest.approx(100) for policy in document["ranked"])
    assert all(policy["stages"][-1]["probability"] > 0 for policy in document["ranked"])


def test_utility_threshold_override_replaces_only_the_stop_rule() -> None:
    recorded: list[object] = []

    def evaluator(spec, loadout, data):
        recorded.append(spec)
        return _result()

    cli.evaluate_plan(
        "examples/bow_value_table.yaml",
        "data/loadouts/endgame.json",
        threshold=100,
        evaluator=evaluator,
    )

    assert len(recorded) == 1
    changed = recorded[0]
    assert changed.threshold == 100
    assert changed.value_table is not None
    assert changed.base == "Crude Bow"
    assert changed.required_mods == ()
    assert changed.values_note is not None
    with pytest.raises(cli.PlanInputError, match="utility"):
        cli.evaluate_plan(
            "examples/helmet_life_chaos_res.yaml",
            "data/loadouts/endgame.json",
            threshold=1,
            evaluator=evaluator,
        )


def test_invalid_path_flag_and_empty_action_loadout_exit_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as missing:
        cli.main(["plan", "examples/no-such-spec.yaml", "--loadout", "data/loadouts/endgame.json"])
    assert missing.value.code == 2
    assert "unable to read item spec" in capsys.readouterr().err

    with pytest.raises(SystemExit) as invalid_flag:
        cli.main(["plan", "examples/helmet_life_chaos_res.yaml", "--loadout", "data/loadouts/endgame.json", "--skip-q9"])
    assert invalid_flag.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err

    loadout = {
        "schema_version": 1,
        "name": "empty permissions",
        "allowed_actions": [],
        "allowed_essences": [],
        "allowed_bench": [],
        "prices_file": "../../data/prices.example.json",
        "budget": 0,
        "base_cost": 0,
    }
    path = tmp_path / "no-actions.json"
    path.write_text(json.dumps(loadout), encoding="utf-8")
    with pytest.raises(SystemExit) as empty:
        cli.main(["plan", "examples/helmet_life_chaos_res.yaml", "--loadout", str(path.relative_to(ROOT))])
    assert empty.value.code == 2
    assert "permits no crafting actions" in capsys.readouterr().err
