from __future__ import annotations

from pathlib import Path

import pytest
from craftoracle import cli
from craftoracle.reporting import build_report, material_accounting, render_report


def _plan() -> dict:
    return {
        "input": {"name": "<target>", "base": "Royal Burgonet", "item_level": 86, "quality": 20},
        "prices": {"unit": "c", "values": {"Envy": 5, "Exalt": 10, "Divine": 10, "Transmute": 1, "Alteration": 2, "Augmentation": 3, "Scour": 4, "Regal": 5}, "base_cost": 0, "note": "invented"},
        "ranked": [
            {"id": "essence-envy", "name": "<Essence>", "expected_cost": 1927.4799660566896, "cost_p90": 3000, "cost_method": "exact", "expected_utility": 1, "frontier": True, "stages": [{"name": "essence", "probability": .1, "expected_attempts": 385.4959932113379}], "parameters": {"essence_id": "Envy"}, "steps": [], "decision_points": []},
            {"id": "suffix-protected-life", "name": "Protected", "expected_cost": 100, "cost_p90": 200, "cost_method": "exact", "expected_utility": 1, "frontier": False, "stages": [], "parameters": {"max_exalts": 2}, "recovery": {"expected_envy_applications": 1, "expected_prefix_cycles": 2, "first_hit_probabilities": [.25, .25]}, "steps": [], "decision_points": []},
            {"id": "magic-regal-exalt", "name": "Magic", "expected_cost": 40, "cost_p90": 60, "cost_method": "exact", "expected_utility": 1, "frontier": False, "stages": [{"name": "regal", "probability": .5, "expected_attempts": 2}, {"name": "exalt 1", "probability": .25, "expected_attempts": 1}], "parameters": {"max_exalts": 1}, "expected_attempts": 4, "steps": [], "decision_points": []},
        ],
        "unavailable": [{"id": "missing", "name": "Unavailable", "reasons": ["missing input"]}],
        "assumptions": ["model only"],
    }


def test_accounting_reprices_essence_and_protected_exalts() -> None:
    plan = _plan()
    essence = material_accounting(plan["ranked"][0], plan, {"essence_names": {"Envy": "Envy"}})
    assert essence["complete"]
    assert essence["total"] == 1927.4799660566896
    plan["prices"]["values"]["Envy"] = 10
    repriced = material_accounting(plan["ranked"][0], plan, {"essence_names": {"Envy": "Envy"}})
    assert repriced["total"] == 3854.959932113379
    protected = material_accounting(plan["ranked"][1], plan, {"bench_recipes": {729: {"Divine": 1}}})
    assert next(row for row in protected["rows"] if row["currency"] == "Exalt")["count"] == 3.5


def test_magic_counts_and_stage_reach_label() -> None:
    plan = _plan()
    context = {"action_rules": {"magic_count_weights": {"1": 1, "2": 1}}}
    accounting = material_accounting(plan["ranked"][2], plan, context)
    counts = {row["currency"]: row["count"] for row in accounting["rows"]}
    assert counts == {"Transmute": 4, "Alteration": 4, "Augmentation": 2, "Scour": 3, "Regal": 2, "Exalt": 1}
    report = build_report(plan, context)
    magic = next(route for route in report["routes"] if route["id"] == "magic-regal-exalt")
    assert magic["stages"][0]["meaning"] == "Шанс дойти до этапа"
    assert any("Exalt" in step for step in magic["instructions"])


def test_report_retains_unavailable_marks_missing_evidence_and_escapes_html() -> None:
    report = build_report(_plan(), {}, {"schema_version": 1, "pytest": {"status": "unavailable"}, "coe": {"status": "unavailable"}})
    assert len(report["unavailable"]) == 1
    assert report["evidence"]["status"] == "unavailable"
    if not _template_exists():
        pytest.skip("surface worker owns template.html")
    html = render_report(report)
    assert "\\u003ctarget\\u003e" in html
    assert "<target>" not in html
    assert "Проверки недоступны" in html
    assert "script" in html


def test_duplicate_route_ids_keep_distinct_threshold_selection_keys() -> None:
    plan = _plan()
    duplicate = dict(plan["ranked"][0])
    duplicate["stopping_threshold"] = 100
    plan["ranked"][0]["stopping_threshold"] = 60
    plan["ranked"].append(duplicate)
    routes = build_report(plan, {})["routes"]
    matches = [route for route in routes if route["id"] == "essence-envy"]
    assert len(matches) == 2
    assert len({route["key"] for route in matches}) == 2


def test_real_shaped_optimizer_names_and_cli_writes_sibling_files(tmp_path, monkeypatch) -> None:
    plan = _plan()
    plan["ranked"][0]["parameters"] = {"forced_essence_id": "Envy"}
    plan["ranked"][0]["stages"][0]["name"] = "essence trial"
    plan["ranked"][2].pop("expected_attempts")
    plan["ranked"][2]["stages"].insert(0, {"name": "transmute setup/reset", "probability": 1, "expected_attempts": 4})
    assert material_accounting(plan["ranked"][2], plan, {"action_rules": {"magic_count_weights": {"1": 1, "2": 1}}})["rows"][0]["count"] == 4
    monkeypatch.setattr(cli, "evaluate_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(cli, "_report_output_dir", lambda path: tmp_path)
    monkeypatch.setattr(cli, "_report_target", lambda path, data: {})
    monkeypatch.setattr(cli, "load_loadout", lambda path: type("Loadout", (), {"bench_recipes": {}})())
    if not _template_exists():
        pytest.skip("surface worker owns template.html")
    assert cli.main(["report", "ignored.json", "--loadout", "ignored.json", "--output-dir", "ignored"]) == 0
    assert (tmp_path / "index.html").is_file()
    assert (tmp_path / "plan.json").is_file()


def test_report_rejects_paths_outside_repository_before_evaluation(monkeypatch) -> None:
    monkeypatch.setattr(cli, "evaluate_plan", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not evaluate")))
    try:
        cli.main(["report", "C:/outside.json", "--loadout", "data/loadouts/endgame.json", "--output-dir", "out/x"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("expected argument error")


def test_fracture_base_count_uses_production_keys_and_no_exalt_when_k_zero() -> None:
    plan = _plan()
    plan["prices"]["base_cost"] = 7
    fracture = {"id": "fracture-life-envy", "expected_cost": 2034, "stages": [], "parameters": {"alchemy_early_stop": False}, "expected_action_counts": {"bases": 2, "alchemy": 4, "scour": 3, "fracturing": 2, "envy": 4}}
    plan["prices"]["values"] = {"alchemy": 1, "scour": 2, "fracturing": 1000, "Metadata/Items/Currency/CurrencyEssenceEnvy3": 3}
    actual = material_accounting(fracture, plan, {"envy_id": "Metadata/Items/Currency/CurrencyEssenceEnvy3"})
    assert next(row for row in actual["rows"] if row["currency"] == "Base")["count"] == 2
    assert actual["total"] == 2036
    magic = dict(_plan()["ranked"][2])
    magic["parameters"] = {"max_exalts": 0, "early_stop": False, "magic_min_desired": 1, "regal_min_desired": 1}
    magic["stages"] = [{"name": "transmute setup/reset", "probability": 1, "expected_attempts": 4}, {"name": "Regal gate", "probability": .5, "expected_attempts": 2}]
    text = build_report({**_plan(), "ranked": [magic]}, {"action_rules": {"magic_count_weights": {"1": 1, "2": 1}}})["routes"][0]["instructions"]
    assert not any("Exalt" in step for step in text)
    assert any("только на последнем" in step for step in text)


def test_stale_evidence_is_explicit() -> None:
    report = build_report(_plan(), {"generation": {"commit": "new"}}, {"schema_version": 1, "git_commit": "old", "pytest": {"status": "passed", "cases": []}, "coe": {"status": "passed", "cases": []}})
    assert report["evidence"]["revision_message"] == "Проверки другой ревизии"


def test_production_shaped_metadata_and_fossil_instruction() -> None:
    plan = _plan()
    magic = plan["ranked"][2]
    magic["stages"].insert(0, {"name": "transmute setup/reset", "probability": 1, "expected_attempts": 4})
    fossil = {"id": "fossil-spam", "name": "Fossils", "expected_cost": 3, "cost_p90": 5, "expected_utility": 1, "frontier": False, "parameters": {"fossil_ids": [13], "socket_count": 1, "alchemy_early_stop": True}, "expected_resonators": 1, "stages": [], "decision_points": []}
    plan["ranked"] = [magic, fossil]
    plan["prices"]["values"].update({"fossil:13": 1, "resonator:1": 1, "alchemy": 1})
    report = build_report(plan, {"action_rules": {"magic_count_weights": {"1": 1, "2": 1}}, "fossil_names": {"13": "Scorched"}})
    assert report["routes"][0]["metadata"]["success_probability"] == .25
    assert any("Scorched" in step and "1" in step for step in report["routes"][1]["instructions"])


def test_html_hash_handler_does_not_pass_event_to_search() -> None:
    if not _template_exists():
        pytest.skip("surface worker owns template.html")
    assert "window.onhashchange=()=>draw()" in render_report(build_report(_plan(), {}))


def _template_exists() -> bool:
    return (Path(__file__).parents[1] / "src/craftoracle/report_assets/template.html").is_file()
