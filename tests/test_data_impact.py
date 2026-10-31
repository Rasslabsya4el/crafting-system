"""The impact report: what a patch diff touches in this repo (targets, routes, claims, tests).

The two data versions are the committed excerpts and `seeded_raw()` (see `seeded_versions.py`).
The repo they are matched against is the small committed one in `fixtures/impact_repo`, whose
files each say what they are for. The data tests are offline.
"""

import copy
from pathlib import Path

import pytest
from repoe_support import fixture_game_data, game_data_from_raw, no_network, raw_fixtures  # noqa: F401
from seeded_versions import seeded_raw

from crafting_system.data import compute_impact, find_repo_root, render_impact

FIXTURE_REPO = Path(__file__).resolve().parent / "fixtures" / "impact_repo"
REAL_REPO = Path(__file__).resolve().parents[1]

TOUCHES = "examples/targets/touches-changes.yaml"
TOUCHES_BASE = "examples/targets/touches-base.yaml"
UNTOUCHED = "examples/targets/untouched.yaml"
ROUTE = "examples/routes/touches-changes.yaml"


@pytest.fixture(scope="module")
def old_data():
    return fixture_game_data()


@pytest.fixture(scope="module")
def new_data():
    return game_data_from_raw(seeded_raw())


@pytest.fixture(scope="module")
def report(old_data, new_data):
    return compute_impact(old_data, new_data, FIXTURE_REPO)


def paths(references) -> set[str]:
    return {reference.path for reference in references}


# --- targets and routes --------------------------------------------------------------------------


def test_a_target_naming_the_family_of_a_changed_mod_is_reported(report):
    assert TOUCHES in paths(report.examples)


def test_a_target_naming_only_unchanged_things_is_not_reported(report):
    assert UNTOUCHED not in paths(report.examples)


def test_the_reference_says_the_line_and_what_changed(report):
    family = next(r for r in report.examples if r.path == TOUCHES and r.token == "ColdResistance")

    assert family.line == 6
    assert "family of a changed mod" in family.kinds


def test_a_target_naming_a_mod_text_matches_with_or_without_the_ranges(report):
    by_text = [r for r in report.examples if r.path == TOUCHES and r.token == "+#% to Cold Resistance"]

    assert [r.line for r in by_text] == [9]


def test_a_target_naming_a_changed_base_item_by_its_name_is_reported(report):
    base = next(r for r in report.examples if r.path == TOUCHES_BASE)

    assert (base.token, base.line, base.kinds) == ("Driftwood Sceptre", 2, ("base item changed",))


def test_a_target_that_names_a_base_of_the_new_version_only_is_not_a_removal(old_data, new_data):
    report = compute_impact(new_data, old_data, FIXTURE_REPO)  # the reverse direction

    assert "Test Robe" not in {r.token for r in report.examples}


def test_a_route_reading_a_touched_family_is_reported(report):
    assert ROUTE in paths(report.examples)


def test_a_removed_mod_is_told_apart_from_a_changed_one(old_data, new_data, tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "t.yaml").write_text("- mod: FireDamagePrefixOnWeapon1\n- mod: ColdResist1\n", "utf-8")

    found = {r.token: r.kinds for r in compute_impact(old_data, new_data, tmp_path).examples}

    assert found["FireDamagePrefixOnWeapon1"] == ("mod removed",)
    assert "mod changed" in found["ColdResist1"]


def test_an_added_mod_cannot_be_named_by_the_old_files_but_its_family_can(old_data, new_data, tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "t.yaml").write_text("- mod: LightningResistTest1\n- family: LightningResistance\n", "utf-8")

    found = {r.token: r.kinds for r in compute_impact(old_data, new_data, tmp_path).examples}

    assert found["LightningResistTest1"] == ("mod added",)
    assert found["LightningResistance"] == ("family of a changed mod",)


# --- claims --------------------------------------------------------------------------------------


def test_a_claim_naming_a_changed_essence_is_reported_with_its_id(report):
    claims = {c.claim: c for c in report.claims}

    assert claims["essence.fixture_changed"].path == "src/crafting_system/rules/claims/essence.yaml"
    assert claims["essence.fixture_changed"].tokens == ("ColdDamagePercentEssence1", "CurrencyEssenceHatred1")  # the mod it no longer forces


def test_a_claim_naming_a_changed_fossil_is_reported(report):
    assert "fossils.fixture_changed" in {c.claim for c in report.claims}


def test_a_claim_naming_only_unchanged_things_is_not_reported(report):
    assert "essence.fixture_untouched" not in {c.claim for c in report.claims}


# --- tests ---------------------------------------------------------------------------------------


def test_a_test_file_naming_a_changed_mod_is_reported_with_the_number_of_lines(report):
    found = {t.path: t for t in report.tests}

    assert found["tests/pin_other_numbers.py"].lines == 1
    assert found["tests/pin_other_numbers.py"].tokens == ("ColdResist1",)
    assert found["tests/pin_real_numbers_real.py"].lines == 2  # the id and the text


def test_a_test_file_naming_only_unchanged_things_is_not_reported(report):
    assert "tests/pin_untouched_numbers.py" not in {t.path for t in report.tests}


def test_the_files_that_read_the_real_cache_are_always_listed_to_be_re_run(report, old_data):
    assert report.real_tests == ("tests/pin_real_numbers_real.py",)

    nothing = compute_impact(old_data, old_data, FIXTURE_REPO)
    assert nothing.real_tests == ("tests/pin_real_numbers_real.py",)


# --- what changed in the data --------------------------------------------------------------------


def test_the_changed_essences_fossils_and_bench_options_are_listed(report):
    text = render_impact(report)

    assert "essence CurrencyEssenceHatred1 (changed)" in text
    assert "essence CurrencyCorruptMonolith (removed)" in text
    assert "fossil CurrencyDelveCraftingFire (changed)" in text
    assert "fossil CurrencyDelveCraftingTest (added)" in text
    assert "bench Niko, Master of the Depths: add_explicit_mod ColdResist1 (added)" in text
    assert "bench Einhar, Beastmaster: add_explicit_mod StrMasterItemGenerationCannotChangePrefixes (removed)" in text


def test_a_bench_option_with_only_a_new_cost_is_changed_not_added_and_removed(report):
    text = render_impact(report)

    jun = [line for line in text.splitlines() if line.strip().startswith("bench Jun")]
    assert len(jun) == 1
    assert jun[0].endswith("(changed)")


def test_a_mod_a_changed_essence_or_fossil_forces_counts_as_touched(old_data, new_data, tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "t.yaml").write_text("- mod: DelveDexterityGemLevel1\n", "utf-8")

    found = compute_impact(old_data, new_data, tmp_path).examples

    assert [r.kinds for r in found] == [("mod of a changed fossil",)]


def test_the_summary_counts_each_kind_of_change(report):
    text = render_impact(report)

    assert "Changed in the data: 11 mods, 11 families, 3 base items, 4 essences, 3 fossils, 4 bench options" in text


# --- the text ------------------------------------------------------------------------------------


def test_the_text_has_a_header_and_one_section_per_kind(report):
    text = render_impact(report, old_label="old", new_label="new")
    lines = text.splitlines()

    assert lines[0] == "Impact of the patch on this repo: old -> new"
    for title in (
        "Targets and routes (examples/):",
        "Claims (src/crafting_system/rules/claims/):",
        "Tests that name changed things (tests/):",
        "Tests that read the real cache, to re-run in full:",
        "Essences, fossils and bench options that changed (their actions):",
    ):
        assert title in lines


def test_the_text_is_the_same_every_time(old_data, new_data):
    first = render_impact(compute_impact(old_data, new_data, FIXTURE_REPO))
    second = render_impact(compute_impact(old_data, new_data, FIXTURE_REPO))

    assert first == second


def test_no_change_says_so_and_still_lists_nothing_else(old_data):
    text = render_impact(compute_impact(old_data, old_data, FIXTURE_REPO), old_label="a", new_label="b")

    assert text.splitlines()[:2] == ["Impact of the patch on this repo: a -> b", "No changes in the data."]
    assert "Targets and routes" not in text


def test_a_change_that_nothing_in_the_repo_names_says_so(old_data, tmp_path):
    raw = copy.deepcopy(raw_fixtures())
    raw["mods.json"]["IncreasedLife1"]["required_level"] = 3
    data = game_data_from_raw(raw)

    text = render_impact(compute_impact(old_data, data, tmp_path))

    assert "Nothing in the targets, routes, claims or tests names a changed id." in text


# --- the repo ------------------------------------------------------------------------------------


def test_a_root_without_the_folders_gives_an_empty_report(old_data, new_data, tmp_path):
    report = compute_impact(old_data, new_data, tmp_path)

    assert (report.examples, report.claims, report.tests, report.real_tests) == ((), (), (), ())


def test_the_repo_root_is_found_from_the_package_and_a_folder_without_it_is_not():
    assert find_repo_root() == REAL_REPO
    assert find_repo_root(Path(__file__).resolve().anchor) is None


def test_the_real_repo_can_be_scanned(old_data, new_data):
    report = compute_impact(old_data, new_data, REAL_REPO)

    assert report.real_tests  # the repo has tests that read the real cache
    assert render_impact(report).startswith("Impact of the patch on this repo:")
