"""The shared loader of the raw export on hand-made folders, one test per rule (ticket #432). No real dump is read here.

The two loaders it replaced (`Export.from_cache` of the goal oracle, `load_export` of the reconciliation) differed in the default
cache folder, the error, what a missing pin file did and the files read. The rule that was kept for each is a test below.
"""

import json
from pathlib import Path

import pytest
from independent import export as shared


def pin(tmp_path: Path, document: dict, name: str = "PIN.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def version(root: Path, name: str, **files) -> Path:
    """A version folder `root/repoe-fork/<name>` with the given files (file name without `.json` -> its JSON value)."""
    folder = root / "repoe-fork" / name
    folder.mkdir(parents=True)
    for file, document in files.items():
        (folder / f"{file}.json").write_text(json.dumps(document), encoding="utf-8")
    return folder


def test_the_pinned_version_is_read_with_its_mods_and_bases(tmp_path):
    folder = version(tmp_path / "cache", "9.9", mods={"M": {}}, base_items={"B": {}})
    version(tmp_path / "cache", "1.0", mods={"Other": {}}, base_items={})

    export = shared.load_export(tmp_path / "cache", pin(tmp_path, {"version": "9.9"}))

    assert export.mods == {"M": {}} and export.bases == {"B": {}}
    assert export.source == str(folder)
    assert shared.version_folder(tmp_path / "cache", pin(tmp_path, {"version": "9.9"})) == folder


def test_the_bench_options_and_the_essences_are_read_when_there_and_empty_when_not(tmp_path):
    version(tmp_path / "with", "9.9", mods={}, base_items={}, crafting_bench_options=[{"actions": {}}], essences={"E": {"x": 1}})
    version(tmp_path / "without", "9.9", mods={}, base_items={})
    given = pin(tmp_path, {"version": "9.9"})

    full = shared.load_export(tmp_path / "with", given)
    bare = shared.load_export(tmp_path / "without", given)

    assert full.bench_options == [{"actions": {}}] and full.essences == {"E": {"x": 1}}
    assert bare.bench_options == [] and bare.essences == {}


@pytest.mark.parametrize("missing", ["mods", "base_items"])
def test_a_missing_required_file_is_export_missing_naming_the_file_and_the_folder(tmp_path, missing):
    present = {"mods": {}, "base_items": {}}
    del present[missing]
    version(tmp_path / "cache", "9.9", **present)

    with pytest.raises(shared.ExportMissing, match=f"{missing}.json is not in .*9.9"):
        shared.load_export(tmp_path / "cache", pin(tmp_path, {"version": "9.9"}))
    assert issubclass(shared.ExportMissing, FileNotFoundError)  # a test that skips on a missing file still does


def test_the_version_folder_of_a_cache_without_the_export_is_export_missing(tmp_path):
    with pytest.raises(shared.ExportMissing, match="mods.json is not in"):
        shared.load_export(tmp_path / "empty-cache", pin(tmp_path, {"version": "9.9"}))
    with pytest.raises(shared.ExportMissing, match="no pin file and 0 version folders"):
        shared.load_export(tmp_path / "empty-cache", None)


def test_with_no_pin_the_only_version_folder_is_used_and_two_are_refused(tmp_path):
    only = version(tmp_path, "1.0", mods={"M": {}}, base_items={})

    assert shared.version_folder(tmp_path, None) == only
    assert shared.load_export(tmp_path, None).mods == {"M": {}}
    (tmp_path / "repoe-fork" / "2.0").mkdir()  # a folder of any content counts as a version
    with pytest.raises(shared.ExportMissing, match="no pin file and 2 version folders in"):
        shared.version_folder(tmp_path, None)


def test_a_pin_file_that_is_given_but_absent_is_an_error_and_never_a_fallback(tmp_path):
    version(tmp_path, "1.0", mods={}, base_items={})  # the only version folder: the reconcile loader used to take it

    with pytest.raises(shared.ExportMissing, match="the pin file .*no-pin.json is not there"):
        shared.version_folder(tmp_path, tmp_path / "no-pin.json")


@pytest.mark.parametrize("document", [{}, {"version": ""}, {"version": None}, {"version": 3}])
def test_a_pin_file_that_names_no_version_text_is_an_error(tmp_path, document):
    with pytest.raises(shared.ExportMissing, match="names no version"):
        shared.version_folder(tmp_path, pin(tmp_path, document))


def test_the_default_pin_file_is_the_one_of_the_repo_and_it_names_a_version():
    assert shared.PIN_FILE.is_file()
    assert shared.pinned_version(shared.PIN_FILE)


def test_the_cache_dir_is_the_environment_then_the_default_folder_of_the_repo(tmp_path):
    assert shared.cache_dir({"CRAFTING_CACHE_DIR": str(tmp_path)}) == tmp_path
    assert shared.cache_dir({}) == shared.DEFAULT_CACHE
    assert shared.cache_dir({"CRAFTING_CACHE_DIR": ""}) == shared.DEFAULT_CACHE  # set but empty: the default, as the planner reads it
    assert shared.DEFAULT_CACHE == shared.REPO_ROOT / "local" / "cache"
    assert (shared.REPO_ROOT / "tests" / "independent" / "export.py").is_file()


def test_the_cache_dir_of_the_environment_is_where_the_default_load_looks(tmp_path, monkeypatch):
    version(tmp_path, shared.pinned_version(shared.PIN_FILE), mods={"M": {}}, base_items={"B": {}})
    monkeypatch.setenv("CRAFTING_CACHE_DIR", str(tmp_path))

    export = shared.load_export()

    assert export.mods == {"M": {}} and export.bases == {"B": {}}
