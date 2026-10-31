"""`python -m crafting_system.data diff OLD NEW`: output, learning a commit, errors, exit codes."""

import hashlib
import io
import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest
from repoe_support import (
    FILE_NAMES,
    TEST_COMMIT,
    TEST_VERSION,
    FakeOpener,
    fixture_bytes,
    make_pin,
    no_network,  # noqa: F401
    raw_to_bytes,
)
from seeded_versions import SEEDED_DIFF_TEXT, seeded_raw

from crafting_system.data import __main__ as data_main
from crafting_system.data import candidate
from crafting_system.data.__main__ import main

COMMIT = "b" * 40
OTHER_COMMIT = "c" * 40
PIN_LABEL = f"{TEST_VERSION} ({TEST_COMMIT[:8]})"
COMMIT_LABEL = f"commit {COMMIT[:12]}"
MOVE_LINE = "To move the pin to this export: python -m crafting_system.data pin "


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """The configured cache directory, redirected into `tmp_path`."""
    monkeypatch.delenv("CRAFTING_CONFIG", raising=False)
    monkeypatch.setenv("CRAFTING_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(data_main, "find_repo_root", lambda: None)  # no impact report; see the tests at the end
    return tmp_path / "cache"


def build_world(candidates=None):
    """(the active pin, an opener serving it and the commits). `candidates`: commit -> file bytes."""
    pin = make_pin(fixture_bytes())
    opener = FakeOpener(pin, fixture_bytes())
    if candidates is None:
        candidates = {COMMIT: raw_to_bytes(seeded_raw())}
    for commit, payloads in candidates.items():
        opener.served.update(FakeOpener(make_pin(payloads, version=commit, commit=commit), payloads).served)
    return pin, opener


def run(capsys, argv, pin, opener):
    code = main(argv, pin=pin, open_url=opener)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def folder_of(cache, version):
    return cache / "repoe-fork" / version


def listing(folder):
    return sorted(path.name for path in folder.iterdir())


def diff_body(out):
    """The diff part of the output (without the line that follows it, naming the command that moves the pin)."""
    return out.split("\n\n" + MOVE_LINE)[0]


def test_diff_of_the_pin_and_a_new_commit_lists_the_seeded_changes(cache, capsys):
    pin, opener = build_world()

    code, out, err = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert code == 0
    assert err == ""
    lines = diff_body(out).split("\n")
    assert lines[0] == f"Patch diff: {PIN_LABEL} -> {COMMIT_LABEL}"
    assert lines[1:] == SEEDED_DIFF_TEXT.split("\n")[1:]


def test_the_command_that_moves_the_pin_is_printed_for_the_commit_that_is_not_pinned(cache, capsys):
    pin, opener = build_world()

    _, out, _ = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert out.endswith(f"\n\n{MOVE_LINE}{COMMIT} <version>\n")
    assert "paste" not in out.lower()
    assert TEST_COMMIT not in out.split(MOVE_LINE)[1]


def test_the_first_run_learns_the_commit_and_writes_its_manifest(cache, capsys):
    pin, opener = build_world()

    run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert listing(folder_of(cache, COMMIT)) == sorted([*FILE_NAMES, "pin.json"])
    assert listing(folder_of(cache, TEST_VERSION)) == sorted(FILE_NAMES)
    assert len(opener.urls) == 2 * len(FILE_NAMES)


def test_a_second_run_downloads_nothing_and_prints_the_same(cache, capsys):
    pin, opener = build_world()
    first = run(capsys, ["diff", "pinned", COMMIT], pin, opener)
    downloads = len(opener.urls)

    second = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert second == first
    assert len(opener.urls) == downloads


def test_a_corrupted_cached_file_of_the_commit_is_repaired_against_the_manifest(cache, capsys):
    pin, opener = build_world()
    first = run(capsys, ["diff", "pinned", COMMIT], pin, opener)
    (folder_of(cache, COMMIT) / "mods.json").write_bytes(b"corrupt")
    downloads = len(opener.urls)

    second = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert second == first
    assert len(opener.urls) == downloads + 1
    assert opener.urls[-1].endswith(f"/{COMMIT}/data/mods.json")


def test_a_corrupted_cached_file_of_the_pin_is_repaired(cache, capsys):
    pin, opener = build_world()
    first = run(capsys, ["diff", "pinned", COMMIT], pin, opener)
    (folder_of(cache, TEST_VERSION) / "fossils.json").write_bytes(b"corrupt")

    second = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert second == first
    assert opener.urls[-1] == pin.url_for("fossils.json")


def test_only_the_files_that_are_needed_are_downloaded(cache, capsys):
    pin, opener = build_world()
    run(capsys, ["diff", "pinned", COMMIT], pin, opener)
    opener.urls.clear()
    (folder_of(cache, TEST_VERSION) / "essences.json").unlink()

    run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert opener.urls == [pin.url_for("essences.json")]


def test_two_commits_are_compared_and_both_get_their_move_command(cache, capsys):
    other = raw_to_bytes(seeded_raw())
    other["fossils.json"] = fixture_bytes()["fossils.json"]
    pin, opener = build_world({COMMIT: raw_to_bytes(seeded_raw()), OTHER_COMMIT: other})

    code, out, _ = run(capsys, ["diff", COMMIT, OTHER_COMMIT], pin, opener)

    assert code == 0
    assert diff_body(out).split("\n")[0] == f"Patch diff: {COMMIT_LABEL} -> commit {OTHER_COMMIT[:12]}"
    assert "Fossils: 1 removed, 2 changed" in out  # the other commit has the original fossils
    assert f"{MOVE_LINE}{COMMIT} <version>" in out
    assert f"{MOVE_LINE}{OTHER_COMMIT} <version>" in out


def test_the_reverse_diff_swaps_added_and_removed(cache, capsys):
    pin, opener = build_world()

    _, out, _ = run(capsys, ["diff", COMMIT, "pinned"], pin, opener)

    body = diff_body(out)
    assert body.split("\n")[0] == f"Patch diff: {COMMIT_LABEL} -> {PIN_LABEL}"
    assert "Mods: 1 added, 1 removed, 3 changed" in body
    assert '+ FireDamagePrefixOnWeapon1 "Searing"' in body
    assert '- LightningResistTest1 "of the Storm"' in body
    assert "    required_level: 5 -> 1" in body


def test_the_commit_of_the_active_pin_counts_as_pinned(cache, capsys):
    pin, opener = build_world()

    code, out, _ = run(capsys, ["diff", TEST_COMMIT, COMMIT], pin, opener)

    assert code == 0
    assert diff_body(out).split("\n")[0] == f"Patch diff: {PIN_LABEL} -> {COMMIT_LABEL}"
    assert f"{MOVE_LINE}{COMMIT} " in out
    assert f"{MOVE_LINE}{TEST_COMMIT}" not in out
    assert not folder_of(cache, TEST_COMMIT).exists()


def test_a_commit_in_capitals_is_the_same_commit(cache, capsys):
    pin, opener = build_world()

    code, out, _ = run(capsys, ["diff", "pinned", COMMIT.upper()], pin, opener)

    assert code == 0
    assert COMMIT_LABEL in out
    assert folder_of(cache, COMMIT).is_dir()


# --- errors ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad", ["xyz", "b" * 39, "b" * 41, "g" * 40, "pinnedd", "Pinned", "", "../" + "b" * 37, "b" * 12]
)
def test_an_invalid_commit_is_a_usage_error_that_says_what_is_accepted(cache, capsys, bad):
    pin, opener = build_world()

    code, out, err = run(capsys, ["diff", "pinned", bad], pin, opener)

    assert code == 2
    assert out == ""
    assert "usage:" in err
    assert "'pinned'" in err
    assert "40" in err
    assert opener.urls == []


@pytest.mark.parametrize(
    "argv",
    [
        ["diff", "pinned", "pinned"],
        ["diff", COMMIT, COMMIT],
        ["diff", TEST_COMMIT, "pinned"],
        ["diff", COMMIT, COMMIT.upper()],
    ],
)
def test_comparing_a_version_with_itself_is_a_usage_error(cache, capsys, argv):
    pin, opener = build_world()

    code, out, err = run(capsys, argv, pin, opener)

    assert code == 2
    assert out == ""
    assert "same version" in err
    assert opener.urls == []


@pytest.mark.parametrize("argv", [["diff"], ["diff", "pinned"], ["diff", "pinned", COMMIT, COMMIT]])
def test_a_wrong_number_of_versions_is_a_usage_error(cache, capsys, argv):
    pin, opener = build_world()

    code, out, err = run(capsys, argv, pin, opener)

    assert code == 2
    assert "usage:" in err
    assert out == ""


def test_an_http_404_for_the_commit_exits_one_names_the_url_and_leaves_no_file(cache, capsys):
    pin, opener = build_world(candidates={})

    code, out, err = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert code == 1
    assert out == ""
    assert err.startswith("error: ")
    assert "404" in err
    assert f"/{COMMIT}/data/mods.json" in err
    assert listing(folder_of(cache, COMMIT)) == []


def test_a_download_larger_than_the_bound_exits_one_and_leaves_no_file(cache, capsys, monkeypatch):
    monkeypatch.setattr(candidate, "MAX_FILE_BYTES", 10_000)  # mods.json is bigger
    pin, opener = build_world()

    code, out, err = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert code == 1
    assert out == ""
    assert err.startswith("error: ")
    assert "mods.json" in err
    assert "larger than 10000 bytes" in err
    assert listing(folder_of(cache, COMMIT)) == []


def test_a_network_failure_exits_one_with_an_error_line(cache, capsys):
    pin, _ = build_world()

    def failing(url):
        raise urllib.error.URLError("no route to host")

    code, out, err = run(capsys, ["diff", "pinned", COMMIT], pin, failing)

    assert code == 1
    assert out == ""
    assert "no route to host" in err
    assert "Traceback" not in err


@pytest.mark.parametrize("content", [b"", b"{", b"garbage", b"[]", b"\xff\xfe\x00"])
def test_a_garbage_manifest_exits_one_and_names_it(cache, capsys, content):
    pin, opener = build_world()
    run(capsys, ["diff", "pinned", COMMIT], pin, opener)
    (folder_of(cache, COMMIT) / "pin.json").write_bytes(content)
    downloads = len(opener.urls)

    code, out, err = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert code == 1
    assert out == ""
    assert err.startswith("error: ")
    assert "pin.json" in err
    assert "Traceback" not in err
    assert len(opener.urls) == downloads


def test_a_manifest_for_other_hashes_makes_the_repair_fail_instead_of_trusting_the_download(cache, capsys):
    pin, opener = build_world()
    run(capsys, ["diff", "pinned", COMMIT], pin, opener)
    manifest = folder_of(cache, COMMIT) / "pin.json"
    text = manifest.read_text(encoding="utf-8")
    first_hash = make_pin(raw_to_bytes(seeded_raw())).files[0].sha256
    manifest.write_text(text.replace(first_hash, "0" * 64), encoding="utf-8")

    code, out, err = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert code == 1
    assert out == ""
    assert "mods.json" in err
    assert "is not the pinned file" in err
    assert "nothing was kept" in err


def test_a_commit_whose_first_download_is_not_json_is_not_recorded_and_works_on_the_next_run(cache, capsys):
    pin, opener = build_world()
    url = f"{pin.base_url}/{COMMIT}/data/mods.json"
    good = opener.served[url]
    opener.served[url] = b"<html>Service unavailable</html>"

    code, out, err = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert code == 1
    assert out == ""
    assert err.startswith("error: ")
    assert "mods.json" in err
    assert "not valid JSON" in err
    assert listing(folder_of(cache, COMMIT)) == []

    opener.served[url] = good
    code, out, err = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert code == 0
    assert err == ""
    assert "Mods: 1 added, 1 removed, 3 changed" in out
    assert "pin.json" in listing(folder_of(cache, COMMIT))


def test_a_learned_commit_whose_files_cannot_be_read_says_how_to_start_over(cache, capsys):
    pin, opener = build_world()
    run(capsys, ["diff", "pinned", COMMIT], pin, opener)
    folder = folder_of(cache, COMMIT)
    bad = b"[]"  # valid JSON, wrong shape: the manifest is rewritten to match it, as a poisoned one would be
    (folder / "mods.json").write_bytes(bad)
    manifest = json.loads((folder / "pin.json").read_text(encoding="utf-8"))
    manifest["files"][0].update(sha256=hashlib.sha256(bad).hexdigest(), size=len(bad))
    (folder / "pin.json").write_text(json.dumps(manifest), encoding="utf-8")

    code, out, err = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert code == 1
    assert out == ""
    assert "mods.json" in err
    assert str(folder) in err
    assert "delete" in err.lower()


def test_an_error_prints_nothing_on_stdout_even_after_the_pinned_side_loaded(cache, capsys):
    pin, opener = build_world(candidates={})

    _, out, _ = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert out == ""
    assert listing(folder_of(cache, TEST_VERSION)) == sorted(FILE_NAMES)


# --- printing ----------------------------------------------------------------------------------


def test_text_a_windows_console_cannot_show_is_printed_with_escapes_not_a_crash(cache, monkeypatch, capsys):
    raw = seeded_raw()
    raw["mods.json"]["ColdResist1"]["text"] = "Cyrillic Ж and a line\nbreak and a lone half \ud800"
    pin, opener = build_world({COMMIT: raw_to_bytes(raw)})
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict", newline="")
    monkeypatch.setattr(sys, "stdout", console)

    code = main(["diff", "pinned", COMMIT], pin=pin, open_url=opener)

    console.flush()
    printed = console.buffer.getvalue().decode("cp1252")
    assert code == 0
    assert capsys.readouterr().err == ""
    assert "Cyrillic \\u0416 and a line\\nbreak and a lone half \\ud800" in printed
    assert printed.isascii()


def test_diff_is_listed_in_the_help(capsys):
    assert main(["--help"]) == 0
    assert "diff" in capsys.readouterr().out


def test_diff_help_explains_pinned_and_commits(capsys):
    assert main(["diff", "--help"]) == 0
    out = capsys.readouterr().out
    assert "pinned" in out
    assert "commit" in out


def test_running_the_module_as_a_command_rejects_a_bad_version(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "crafting_system.data", "diff", "pinned", "nothex"],
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "CRAFTING_CACHE_DIR": str(tmp_path / "empty")},
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "usage:" in result.stderr
    assert not (tmp_path / "empty").exists()


# --- the impact report after the diff ------------------------------------------------------------

FIXTURE_REPO = Path(__file__).resolve().parent / "fixtures" / "impact_repo"


def test_the_diff_is_followed_by_the_impact_report_of_the_repo_it_runs_in(cache, capsys, monkeypatch):
    monkeypatch.setattr(data_main, "find_repo_root", lambda: FIXTURE_REPO)
    pin, opener = build_world()

    code, out, _ = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert code == 0
    diff, rest = out.split("\n\nImpact of the patch on this repo: ")
    assert diff.split("\n")[1:] == SEEDED_DIFF_TEXT.split("\n")[1:]
    impact, move_line = rest.split("\n\n" + MOVE_LINE)
    assert impact.split("\n")[0] == f"{PIN_LABEL} -> {COMMIT_LABEL}"
    assert "examples/targets/touches-changes.yaml:6  ColdResistance (family of a changed mod)" in impact
    assert "examples/targets/untouched.yaml" not in impact
    assert move_line == f"{COMMIT} <version>\n"


def test_no_impact_leaves_the_report_out(cache, capsys, monkeypatch):
    monkeypatch.setattr(data_main, "find_repo_root", lambda: FIXTURE_REPO)
    pin, opener = build_world()

    _, out, _ = run(capsys, ["diff", "pinned", COMMIT, "--no-impact"], pin, opener)

    assert "Impact of the patch" not in out
    assert diff_body(out).split("\n")[1:] == SEEDED_DIFF_TEXT.split("\n")[1:]


def test_a_package_without_a_checkout_prints_no_report(cache, capsys):
    pin, opener = build_world()  # `cache` made find_repo_root return None, as in an installed copy

    _, out, _ = run(capsys, ["diff", "pinned", COMMIT], pin, opener)

    assert "Impact of the patch" not in out
