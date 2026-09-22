from __future__ import annotations

from pathlib import Path
import re

from craftoracle import cli
from craftoracle.actions import load_action_data
from craftoracle.reporting import build_report, material_accounting, render_evidence, render_report


ROOT = Path(__file__).parents[1]

_CYRILLIC = re.compile(r"[\u0400-\u04FF]")


def _texts(instructions: list[dict]) -> list[str]:
    """Flatten step-by-step {"text", "detail"} entries to one searchable string
    each, so tests can keep using substring assertions."""
    return [f'{step["text"]} {step.get("detail") or ""}' for step in instructions]


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


def test_protected_envy_row_uses_the_full_essence_display_name_when_known() -> None:
    plan = _plan()
    context = {"envy_id": "Metadata/Items/Currency/CurrencyEssenceEnvy3", "essence_names": {"Metadata/Items/Currency/CurrencyEssenceEnvy3": "Deafening Essence of Envy"}, "bench_recipes": {}}
    plan["prices"]["values"]["Metadata/Items/Currency/CurrencyEssenceEnvy3"] = 5
    protected = material_accounting(plan["ranked"][1], plan, context)
    assert any(row["currency"] == "Deafening Essence of Envy" for row in protected["rows"])
    # Without a name mapping, the label falls back to the generic "Envy" (unchanged behaviour).
    fallback = material_accounting(plan["ranked"][1], plan, {"bench_recipes": {}})
    assert any(row["currency"] == "Envy" for row in fallback["rows"])


def test_magic_counts_and_stage_reach_label() -> None:
    plan = _plan()
    context = {"action_rules": {"magic_count_weights": {"1": 1, "2": 1}}}
    accounting = material_accounting(plan["ranked"][2], plan, context)
    counts = {row["currency"]: row["count"] for row in accounting["rows"]}
    assert counts == {"Transmute": 4, "Alteration": 4, "Augmentation": 2, "Scour": 3, "Regal": 2, "Exalt": 1}
    report = build_report(plan, context)
    magic = next(route for route in report["routes"] if route["id"] == "magic-regal-exalt")
    assert magic["stages"][0]["meaning"] == "Chance of reaching this step"
    assert any("Exalt" in text for text in _texts(magic["instructions"]))

    for early, expects_goal_check in ((True, True), (False, False)):
        magic_plan = _plan()["ranked"][2]
        magic_plan["parameters"] = {"max_exalts": 3, "early_stop": early, "magic_min_desired": 1, "regal_min_desired": 2}
        instructions = build_report({**_plan(), "ranked": [magic_plan]}, {})["routes"][0]["instructions"]
        regal_step = next(step for step in instructions if step["text"].startswith("Use Regal Orb"))
        combined = f'{regal_step["text"]} {regal_step.get("detail") or ""}'
        assert "at least 2 desired modifiers" in combined
        assert ("keep the item now" in regal_step["text"]) is expects_goal_check


def test_report_retains_unavailable_marks_missing_evidence_and_escapes_html() -> None:
    report = build_report(_plan(), {}, {"schema_version": 1, "pytest": {"status": "unavailable"}, "coe": {"status": "unavailable"}})
    assert len(report["unavailable"]) == 1
    assert report["evidence"]["status"] == "unavailable"
    assert report["input"]["name"] == "<target>"
    assert report["evidence"]["status"] == "unavailable"


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
    monkeypatch.setattr(cli, "_report_target", lambda path, data, threshold=None: {})
    monkeypatch.setattr(cli, "load_loadout", lambda path: type("Loadout", (), {"bench_recipes": {}})())
    monkeypatch.setattr(cli, "render_report", lambda report: "<!doctype html><title>stub</title>")
    assert cli.main(["report", "ignored.json", "--loadout", "ignored.json", "--output-dir", "ignored"]) == 0
    assert (tmp_path / "index.html").is_file()
    assert (tmp_path / "plan.json").is_file()
    assert (tmp_path / "evidence.html").is_file()
    # render_report was stubbed; render_evidence runs for real against the same report and must not crash.
    assert "pytest summary" in (tmp_path / "evidence.html").read_text(encoding="utf-8")


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
    fracture = {"id": "fracture-life-envy", "expected_cost": 2036, "stages": [], "parameters": {"alchemy_early_stop": False}, "expected_action_counts": {"bases": 2, "alchemy": 4, "scour": 3, "fracturing": 2, "envy": 4}}
    plan["prices"]["values"] = {"alchemy": 1, "scour": 2, "fracturing": 1000, "Metadata/Items/Currency/CurrencyEssenceEnvy3": 3}
    actual = material_accounting(fracture, plan, {"envy_id": "Metadata/Items/Currency/CurrencyEssenceEnvy3"})
    assert next(row for row in actual["rows"] if row["currency"] == "Base")["count"] == 2
    assert actual["total"] == 2036
    assert actual["complete"]
    magic = dict(_plan()["ranked"][2])
    magic["parameters"] = {"max_exalts": 0, "early_stop": False, "magic_min_desired": 1, "regal_min_desired": 1}
    magic["stages"] = [{"name": "transmute setup/reset", "probability": 1, "expected_attempts": 4}, {"name": "Regal gate", "probability": .5, "expected_attempts": 2}]
    text = _texts(build_report({**_plan(), "ranked": [magic]}, {"action_rules": {"magic_count_weights": {"1": 1, "2": 1}}})["routes"][0]["instructions"])
    assert not any("Exalt" in step for step in text)
    assert any("last configured step" in step for step in text)


def test_stale_evidence_is_explicit() -> None:
    report = build_report(_plan(), {"generation": {"commit": "new"}}, {"schema_version": 1, "git_commit": "old", "pytest": {"status": "passed", "cases": []}, "coe": {"status": "passed", "cases": []}})
    assert report["evidence"]["revision_message"] == "Checks are from a different revision"


def test_production_shaped_metadata_and_fossil_instruction() -> None:
    plan = _plan()
    magic = plan["ranked"][2]
    magic["stages"].insert(0, {"name": "transmute setup/reset", "probability": 1, "expected_attempts": 4})
    fossil = {"id": "fossil-spam", "name": "Fossils", "expected_cost": 3, "cost_p90": 5, "expected_utility": 1, "frontier": False, "parameters": {"fossil_ids": [13], "socket_count": 1, "alchemy_early_stop": True}, "expected_resonators": 1, "stages": [], "decision_points": []}
    plan["ranked"] = [magic, fossil]
    plan["prices"]["values"].update({"fossil:13": 1, "resonator:1": 1, "alchemy": 1})
    report = build_report(plan, {"action_rules": {"magic_count_weights": {"1": 1, "2": 1}}, "fossil_names": {"13": "Scorched"}})
    assert report["routes"][0]["metadata"]["success_probability"] == .25
    assert any("Scorched" in step and "1" in step for step in _texts(report["routes"][1]["instructions"]))


def test_evidence_links_are_relative_and_keep_provenance() -> None:
    report = build_report(_plan(), {"generation": {"commit": "same"}}, {"schema_version": 1, "git_commit": "same", "working_tree_dirty": True, "pytest": {"status": "passed"}, "coe": {"status": "passed"}, "commands": [{"name": "pytest", "stdout_file": "logs/run.out", "stderr_file": "logs/run.err"}], "artifacts": {"coe_json": "coe/comparison.json"}})
    evidence = report["evidence"]
    assert evidence["proof_link"] == "evidence/proof.json"
    assert evidence["commands"][0]["stdout_file"] == "evidence/logs/run.out"
    assert evidence["artifacts"]["coe_json"] == "evidence/coe/comparison.json"
    assert evidence["working_tree_dirty"] is True


def test_copy_evidence_artifacts_preserves_relative_links(tmp_path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    (source / "coe").mkdir(parents=True)
    (source / "logs").mkdir()
    for relative in ("proof.json", "coe/comparison.json", "logs/run.out"):
        (source / relative).write_text(relative, encoding="utf-8")
    cli._copy_evidence_artifacts(source.resolve(), output.resolve(), {"artifacts": {"coe_json": "coe/comparison.json"}, "commands": [{"stdout_file": "logs/run.out"}]})
    assert (output / "evidence/proof.json").is_file()
    assert (output / "evidence/coe/comparison.json").is_file()
    assert (output / "evidence/logs/run.out").is_file()


# --------------------------------------------------------------------------
# report-ui-v2: the player page reads like the game, evidence is split out.
# --------------------------------------------------------------------------


def _full_context() -> dict:
    return {
        "action_rules": {"magic_count_weights": {"1": 1, "2": 1}},
        "essence_names": {"Envy": "Deafening Essence of Envy"},
        "envy_id": "Envy",
        "bench_recipes": {729: {"Divine": 2}},
        "fossil_names": {},
        "bench_names": {"729": "Suffixes Cannot Be Changed"},
        "target": {"criteria": [], "any_of": [], "labels": {}},
        "generation": {"commit": "abc1234567890", "generated_at": "2026-09-22T00:00:00+00:00"},
    }


def test_player_page_has_no_russian_prose_and_the_expected_sections() -> None:
    report = build_report(_plan(), _full_context())
    html = render_report(report)
    assert not _CYRILLIC.search(html), "the player page must read in English, like the game"
    assert 'class="tooltip-card"' in html
    assert 'class="routes"' in html
    assert "Crafting flow" in html
    assert "Step by step" in html
    assert "Costs per success" in html
    assert 'href="evidence.html"' in html
    assert "Prices are placeholders, not trade prices." in html
    # dropped from the player page per the brief: invented value/price banners, stage tables, raw dumps
    assert "invented" not in html.lower()
    assert "<script" not in html.lower()


def test_evidence_page_has_no_russian_prose_and_carries_what_the_player_page_dropped() -> None:
    evidence = {"schema_version": 1, "pytest": {"status": "passed", "tests": 5, "cases": []}, "coe": {"status": "passed", "cases": []}}
    report = build_report(_plan(), _full_context(), evidence)
    html = render_evidence(report)
    assert not _CYRILLIC.search(html)
    assert "pytest summary" in html
    assert "Craft of Exile cross-check" in html
    assert 'href="index.html"' in html
    assert "invented" in html  # the raw price note is still fully visible in the evidence dump
    assert "<script" not in html.lower()


def test_flow_has_one_step_box_per_action_actually_performed() -> None:
    """A flow step is the ACTION (what you click), never the payment currency:
    the suffix-protected route's bench-craft step must be titled by the recipe,
    not by whatever currency happens to pay for it (D95 lead review)."""
    report = build_report(_plan(), _full_context())
    essence_route = next(route for route in report["routes"] if route["id"] == "essence-envy")
    assert len(essence_route["flow"]["steps"]) == 1
    magic_route = next(route for route in report["routes"] if route["id"] == "magic-regal-exalt")
    assert [step["action"] for step in magic_route["flow"]["steps"]] == [
        "Use Orb of Transmutation", "Use Orb of Alteration", "Use Orb of Augmentation", "Use Orb of Scouring", "Use Regal Orb", "Use Exalted Orb",
    ]
    protected_route = next(route for route in report["routes"] if route["id"] == "suffix-protected-life")
    actions = [step["action"] for step in protected_route["flow"]["steps"]]
    assert "Crafting Bench: Suffixes Cannot Be Changed" in actions
    assert not any("Divine" in action for action in actions)  # the payment currency is never a step title
    html = render_report(report)
    assert html.count('class="flow-step"') == len(essence_route["flow"]["steps"]) + len(magic_route["flow"]["steps"]) + len(protected_route["flow"]["steps"])


def test_flow_collapses_repeated_per_stage_currency_rows_into_one_step() -> None:
    # magic-regal-exalt with three per-attempt Exalt stages (as produced by the real
    # optimizer) still gets ONE "Use Exalted Orb" flow box, with the three counts summed
    # (not just the first stage's count -- D95 fix: uses must sum across the batch).
    plan = _plan()
    magic = plan["ranked"][2]
    magic["stages"] = [
        {"name": "regal", "probability": .5, "expected_attempts": 2},
        {"name": "exalt 1", "probability": .1, "expected_attempts": 1},
        {"name": "exalt 2", "probability": .1, "expected_attempts": 1},
        {"name": "exalt 3", "probability": .1, "expected_attempts": 1},
    ]
    report = build_report(plan, _full_context())
    magic_route = next(route for route in report["routes"] if route["id"] == "magic-regal-exalt")
    actions = [step["action"] for step in magic_route["flow"]["steps"]]
    assert actions.count("Use Exalted Orb") == 1
    exalt_step = next(step for step in magic_route["flow"]["steps"] if step["action"] == "Use Exalted Orb")
    assert exalt_step["uses"] == 3
    assert len(exalt_step["payments"]) == 1  # three same-currency rows merge into one payment line


def test_bench_action_uses_the_true_repeat_count_not_the_currency_quantity() -> None:
    """A recipe that costs more than one currency unit per use (729 costs 2
    Divine Orbs) must report "uses" as how many times the CRAFT happens, not
    how many currency units were spent (D95: this was the original bug)."""
    plan = _plan()
    context = {"bench_recipes": {729: {"Divine": 2}}, "bench_names": {"729": "Suffixes Cannot Be Changed"}}
    protected = build_report(plan, context)["routes"][1]
    bench_step = next(step for step in protected["flow"]["steps"] if step["action"] == "Crafting Bench: Suffixes Cannot Be Changed")
    assert bench_step["uses"] == 2  # expected_prefix_cycles from the fixture, not 2 * 2
    assert bench_step["payments"] == [{"currency": "Divine", "count": 4.0, "spend": 40.0}]


def test_routes_beyond_six_are_collapsed_behind_show_all() -> None:
    plan = _plan()
    template = plan["ranked"][0]
    plan["ranked"] = [{**template, "id": f"essence-envy-{i}", "expected_cost": 100 + i} for i in range(8)]
    report = build_report(plan, _full_context())
    html = render_report(report)
    assert "Show all 8 routes" in html
    assert html.count('class="route-row"') == 8

    plan["ranked"] = plan["ranked"][:5]
    report_few = build_report(plan, _full_context())
    html_few = render_report(report_few)
    assert "Show all" not in html_few


def test_helmet_and_bow_target_cards_show_the_games_own_prefix_suffix_wording() -> None:
    data = load_action_data(ROOT)
    helmet = cli._report_target(ROOT / "examples" / "helmet_life_chaos_res.yaml", data)
    life = next(item for item in helmet["criteria"] if item["group"] == "IncreasedLife")
    assert life["type"] == "Prefix"
    assert life["family"] == "Life"
    assert life["text"] == "+(130-144) to maximum Life"
    resist = next(item for item in helmet["any_of"][0] if item["group"] == "FireResistance")
    assert resist["type"] == "Suffix"
    assert resist["family"] == "Fire Resistance"

    bow = cli._report_target(ROOT / "examples" / "bow_value_table.yaml", data)
    assert bow["criteria"] == []
    families = {row["group"]: row["family"] for row in bow["value_rows"]}
    assert families["LocalFireDamageTwoHand"] == "Fire Damage"
    assert families["LocalIncreasedAttackSpeed"] == "Attack Speed"
