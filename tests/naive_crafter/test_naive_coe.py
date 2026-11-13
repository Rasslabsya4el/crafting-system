"""The naive crafter's orbs against the recorded Craft of Exile counts of the B1 core (ticket #555, #544).

`tests/fixtures/coe_recorded/b1_core.json` holds counts of finished items from the Craft of Exile emulator on the real bases of the benchmark
routes. Here every case that is a plain-spam orb (Alteration, Augmentation, Regal, Chaos, the essences) is played by `naive_crafter` on the
same start item, 60,000 times, and the chance that the finished item holds each mod, and has each shape, is put beside the emulator's count
by the statistic of `frequencies.py` (a pooled two-sample z, Bonferroni-corrected over the whole module, `ALPHA` = 0.01, no percentage threshold).
A cell that fails is a disagreement between the naive crafter and the emulator and is filed as an issue (OR-29), never hidden by a wider limit.

The two fossil cases (a Dense and a Shuddering Fossil on R08's boots, a Pristine and a Shuddering Fossil on R09's) are played too since #608: the fossils
change the weights of the pool by the tags of the mods, and the recorded counts say whether the tags of the export are the emulator's.

The seeds are fixed, so a run repeats. Needs the cached dump (`CRAFTING_CACHE_DIR`); CI fetches it. Rules: OR-21 (the emulator is one source among
others), OR-22 (the rules of the crafter carry their sources), OR-29.
"""

import json
from pathlib import Path

import pytest
from independent import export as shared_export
from naive_crafter import frequencies as f
from naive_crafter.craft import Crafter, Laws
from naive_crafter.fossils import read_fossils

RECORDED = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "coe_recorded" / "b1_core.json").read_text(encoding="utf-8"))
CASES = RECORDED["cases"]
NOT_PLAYED: dict[str, str] = {}
PLAYED = [name for name in CASES if name not in NOT_PLAYED]
APPLICATIONS = 60_000


@pytest.fixture(scope="module")
def raw():
    try:
        return shared_export.load_export()
    except shared_export.ExportMissing as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


def crafter_of(raw, case: dict, laws: Laws | None = None) -> Crafter:
    item = case["item"]
    return Crafter(raw, item["base"], item["item_level"], laws=laws)


def count(raw, name: str, laws: Laws | None = None, applications: int = APPLICATIONS) -> f.Frequencies:
    case = CASES[name]
    crafter = crafter_of(raw, case, laws)
    seed = 555_000 + list(CASES).index(name)
    return f.count_applications(crafter, f.item_of(crafter, case["item"]), case["action"], raw.essences, applications, seed, read_fossils(raw.source))


@pytest.fixture(scope="module")
def counted(raw):
    return {name: count(raw, name) for name in PLAYED}


@pytest.fixture(scope="module")
def cells(counted):
    return {name: f.cells_of(name, CASES[name], counted[name]) for name in PLAYED}


@pytest.fixture(scope="module")
def tested(cells):
    return sum(cell.testable for per_case in cells.values() for cell in per_case)


def test_every_recorded_case_is_played_and_nothing_is_left_out():
    assert NOT_PLAYED == {}
    assert set(PLAYED) == {
        "alteration-r13-belt",
        "augmentation-r13-belt",
        "chaos-r12-amulet",
        "chaos-r13-belt",
        "essence-c02-helmet",
        "essence-r05-ring",
        "essence-r08-fear",  # #627: the essences the actions: key hides
        "essence-r09-spite",
        "essence-r10-boots",
        "essence-r11-helmet",
        "essence-r13-hatred",
        "fossil-r08-boots",
        "fossil-r09-boots",
        "regal-r13-belt",
        "start-r08-pair",
        "start-r08-prismatic",
        "start-r09-pair",
        "start-r09-prismatic",
    }


@pytest.mark.parametrize("name", PLAYED)
def test_no_orb_chance_differs_from_the_emulators_count(counted, cells, tested, name):
    assert counted[name].refused == 0
    assert tested > 400  # the family is large enough for the correction to mean something
    failed = f.failures(cells[name], tested)

    assert not failed, "\n".join(cell.describe() for cell in failed)


@pytest.mark.parametrize("name", PLAYED)
def test_every_mod_the_emulator_gave_is_a_mod_the_naive_crafter_gives(cells, name):
    missing = f.unsupported(cells[name])

    assert not missing, "\n".join(cell.describe() for cell in missing)


@pytest.mark.parametrize("name", PLAYED)
def test_the_two_agree_on_the_forced_and_the_kept_mods_exactly(counted, name):
    """An essence's forced mod and a fractured mod are in every finished item, on both sides."""
    case = CASES[name]
    for mod_id in case["item"].get("fractured") or ():
        assert case["mods"][mod_id] == case["applied"]
        assert counted[name].mods[mod_id] == counted[name].applied


def test_a_wrong_count_of_mods_for_the_magic_orbs_is_rejected(raw):
    """The statistic has the power to see a law that is wrong: Alteration leaving 2 mods twice as often as 1 is far from the recorded one third and two thirds of 1 against 2."""
    name = "alteration-r13-belt"
    wrong = count(raw, name, Laws(magic=((1, 1), (2, 2))), applications=20_000)
    shapes = [cell for cell in f.cells_of(name, CASES[name], wrong) if cell.kind == "shape"]

    assert f.failures(shapes, tested=len(shapes))


def test_a_wrong_ratio_of_the_rare_counts_is_rejected(raw):
    name = "chaos-r13-belt"
    wrong = count(raw, name, Laws(rare=((4, 1), (5, 1), (6, 1))), applications=20_000)
    shapes = [cell for cell in f.cells_of(name, CASES[name], wrong) if cell.kind == "shape"]

    assert f.failures(shapes, tested=len(shapes))


def test_the_statistic_on_a_known_case():
    same = f.Cell("c", "mod", "m", 1000, 100, 1000, 100)
    apart = f.Cell("c", "mod", "m", 20000, 2000, 60000, 7200)

    assert same.z == 0.0
    assert apart.z < -5 and apart.testable
    assert not f.failures([same], tested=1)
    assert f.failures([apart], tested=1)
    assert f.critical_z(1000) > f.critical_z(1) > 2.5
