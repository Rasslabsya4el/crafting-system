"""`python -m crafting_system.data pin`, and the pin file `PIN.json`: moving the pin without a second download."""

import json
from pathlib import Path

import pytest
from github_support import FakeGitHub, commit_entry, files_world, routed, sha_of
from repoe_support import (
    FILE_NAMES,
    TEST_COMMIT,
    game_data_from_raw,
    make_pin,
    no_network,  # noqa: F401
    raw_to_bytes,
)
from seeded_versions import seeded_raw

from crafting_system.data import PIN, PIN_FILE, PinFileError, RepoePin, load_game_data, load_pin, write_pin
from crafting_system.data import __main__ as data_main
from crafting_system.data.__main__ import main
from crafting_system.data.resolve import COMMITS_URL

COMMIT = "b" * 40
NEW_VERSION = "5.1.2"
PIN_VERSION = "9.9.9"  # the active pin of these tests: the committed excerpt under a made-up game version


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """The configured cache directory, redirected into `tmp_path`."""
    monkeypatch.delenv("CRAFTING_CONFIG", raising=False)
    monkeypatch.setenv("CRAFTING_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(data_main, "find_repo_root", lambda: None)
    return tmp_path / "cache"


def refuse_download(url):
    raise AssertionError(f"the test downloaded {url}")


def new_files() -> dict[str, bytes]:
    """The files of the second version (the seeded changes), as served at COMMIT."""
    return raw_to_bytes(seeded_raw())


def expected_pin(version=NEW_VERSION, commit=COMMIT) -> RepoePin:
    return make_pin(new_files(), version=version, commit=commit)


def folder_of(cache, name):
    return cache / "repoe-fork" / name


def listing(folder):
    return sorted(path.name for path in folder.iterdir())


def run(capsys, argv, pin, open_url, pin_file):
    code = main(argv, pin=pin, open_url=open_url, pin_file=pin_file)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def commit_answer(commit, message):
    return FakeGitHub(commits={commit: commit_entry(commit, message)})


# --- moving the pin ----------------------------------------------------------------------------------


def test_pin_after_a_diff_moves_the_pin_and_verify_passes_with_no_download(cache, tmp_path, capsys):
    pin, files = files_world({COMMIT: new_files()})
    pin_file = tmp_path / "PIN.json"
    assert main(["diff", "pinned", COMMIT, "--no-impact"], pin=pin, open_url=files) == 0
    capsys.readouterr()
    downloads = len(files.urls)

    code, out, err = run(capsys, ["pin", COMMIT, NEW_VERSION], pin, refuse_download, pin_file)

    assert code == 0
    assert err == ""
    assert len(files.urls) == downloads
    moved = load_pin(pin_file)
    assert moved == expected_pin()
    assert listing(folder_of(cache, NEW_VERSION)) == sorted(FILE_NAMES)  # the learned manifest is gone
    assert not folder_of(cache, COMMIT).exists()
    assert listing(folder_of(cache, PIN_VERSION)) == sorted(FILE_NAMES)  # the old pin's folder stays
    # five fetch lines in the format of `fetch`, then the line about the pin file
    lines = out.splitlines()
    assert lines[:5] == [
        f"{pinned.name}: cached, {pinned.size} bytes, sha256 {pinned.sha256[:12]}" for pinned in moved.files
    ]
    assert lines[5] == f"{pin_file} was written: the pin is now version {NEW_VERSION}, commit {COMMIT}"
    assert len(lines) == 6
    assert main(["verify"], pin=moved) == 0
    capsys.readouterr()
    assert load_game_data(moved) == game_data_from_raw(seeded_raw(), version=NEW_VERSION)


def test_the_new_pin_file_has_the_layout_of_the_committed_one(cache, tmp_path, capsys):
    pin, files = files_world({COMMIT: new_files()})
    pin_file = tmp_path / "PIN.json"

    run(capsys, ["pin", COMMIT, NEW_VERSION], pin, files, pin_file)

    text = pin_file.read_bytes().decode("utf-8")
    assert text == json.dumps(json.loads(text), indent=2) + "\n"
    assert "\r" not in text
    assert list(json.loads(text)) == ["version", "commit", "base_url", "files"]
    assert [file["name"] for file in json.loads(text)["files"]] == list(FILE_NAMES)


def test_a_commit_never_seen_is_downloaded_once_and_the_cache_is_usable(cache, tmp_path, capsys):
    pin, files = files_world({COMMIT: new_files()})
    pin_file = tmp_path / "PIN.json"

    code, out, _ = run(capsys, ["pin", COMMIT, NEW_VERSION], pin, files, pin_file)

    assert code == 0
    assert sorted(files.urls) == sorted(expected_pin(commit=COMMIT).url_for(name) for name in FILE_NAMES)
    assert all(": cached, " in line for line in out.splitlines()[:5])  # the learning download was the only one
    moved = load_pin(pin_file)
    assert moved == expected_pin()
    assert main(["verify"], pin=moved) == 0
    assert listing(folder_of(cache, NEW_VERSION)) == sorted(FILE_NAMES)
    assert not folder_of(cache, COMMIT).exists()
    assert len(files.urls) == len(FILE_NAMES)


def test_a_commit_in_capitals_is_the_same_commit(cache, tmp_path, capsys):
    pin, files = files_world({COMMIT: new_files()})
    pin_file = tmp_path / "PIN.json"

    code, _, _ = run(capsys, ["pin", COMMIT.upper(), NEW_VERSION], pin, files, pin_file)

    assert code == 0
    assert load_pin(pin_file).commit == COMMIT


def test_a_commit_without_a_version_takes_it_from_the_message_on_github(cache, tmp_path, capsys):
    pin, files = files_world({COMMIT: new_files()})
    github = commit_answer(COMMIT, f"[skip ci] Export {NEW_VERSION}")
    pin_file = tmp_path / "PIN.json"

    code, out, _ = run(capsys, ["pin", COMMIT], pin, routed(files, github), pin_file)

    assert code == 0
    assert github.urls == [f"{COMMITS_URL}/{COMMIT}"]
    assert load_pin(pin_file) == expected_pin()
    assert f"version {NEW_VERSION}, commit {COMMIT}" in out


def test_a_version_given_with_a_commit_is_not_checked_against_github(cache, tmp_path, capsys):
    pin, files = files_world({COMMIT: new_files()})
    github = commit_answer(COMMIT, "[skip ci] Export 7.7.7")
    pin_file = tmp_path / "PIN.json"

    run(capsys, ["pin", COMMIT, NEW_VERSION], pin, routed(files, github), pin_file)

    assert github.urls == []
    assert load_pin(pin_file).version == NEW_VERSION


def test_a_version_name_goes_through_the_api_to_its_export(cache, tmp_path, capsys):
    export = sha_of("926da1c0")  # Export 3.29.3.2
    pin, files = files_world({export: new_files()})
    github = FakeGitHub()
    pin_file = tmp_path / "PIN.json"

    code, out, _ = run(capsys, ["pin", "3.29.3.2"], pin, routed(files, github), pin_file)

    assert code == 0
    assert out.splitlines()[0].startswith(f"Export of 3.29.3.2: commit {export}")
    assert load_pin(pin_file) == expected_pin(version="3.29.3.2", commit=export)
    assert listing(folder_of(cache, "3.29.3.2")) == sorted(FILE_NAMES)
    assert main(["verify"], pin=load_pin(pin_file)) == 0


def test_a_version_name_with_the_same_version_repeated_is_accepted(cache, tmp_path, capsys):
    export = sha_of("926da1c0")
    pin, files = files_world({export: new_files()})
    pin_file = tmp_path / "PIN.json"

    code, _, _ = run(capsys, ["pin", "3.29.3.2", "3.29.3.2"], pin, routed(files, FakeGitHub()), pin_file)

    assert code == 0
    assert load_pin(pin_file).commit == export


def test_an_existing_version_folder_is_overwritten_by_the_moved_files_without_a_download(cache, tmp_path, capsys):
    pin, files = files_world({COMMIT: new_files()})
    folder = folder_of(cache, NEW_VERSION)
    folder.mkdir(parents=True)
    (folder / "fossils.json").write_bytes(b"an older export of this version")
    assert main(["diff", "pinned", COMMIT, "--no-impact"], pin=pin, open_url=files) == 0
    capsys.readouterr()
    pin_file = tmp_path / "PIN.json"

    code, out, _ = run(capsys, ["pin", COMMIT, NEW_VERSION], pin, refuse_download, pin_file)

    assert code == 0
    assert {line.split(":")[1].split(",")[0] for line in out.splitlines()[:5]} == {" cached"}
    assert (folder / "fossils.json").read_bytes() == new_files()["fossils.json"]
    assert not folder_of(cache, COMMIT).exists()
    assert main(["verify"], pin=load_pin(pin_file)) == 0


@pytest.mark.parametrize("failing", ["fetch", "write_pin"])
def test_a_failure_before_the_pin_is_written_leaves_the_pin_and_the_learned_commit_as_they_were(
    cache, tmp_path, capsys, monkeypatch, failing
):
    pin, files = files_world({COMMIT: new_files()})
    pin_file = tmp_path / "PIN.json"
    pin_file.write_bytes(b"the old pin")
    assert main(["diff", "pinned", COMMIT, "--no-impact"], pin=pin, open_url=files) == 0
    capsys.readouterr()
    calls = []

    def broken(*args, **kwargs):
        calls.append(failing)
        raise PinFileError(f"{failing} failed")

    monkeypatch.setattr(data_main, failing, broken)

    code, out, err = run(capsys, ["pin", COMMIT, NEW_VERSION], pin, refuse_download, pin_file)

    assert code == 1 and calls == [failing]
    assert err.startswith("error: ") and f"{failing} failed" in err
    assert pin_file.read_bytes() == b"the old pin"
    assert "was written" not in out
    assert listing(folder_of(cache, COMMIT)) == sorted([*FILE_NAMES, "pin.json"])  # the commit is still learned
    assert not folder_of(cache, NEW_VERSION).exists() or listing(folder_of(cache, NEW_VERSION)) == []

    monkeypatch.undo()
    monkeypatch.setenv("CRAFTING_CACHE_DIR", str(cache))
    monkeypatch.delenv("CRAFTING_CONFIG", raising=False)
    monkeypatch.setattr(data_main, "find_repo_root", lambda: None)
    code, _, _ = run(capsys, ["pin", COMMIT, NEW_VERSION], pin, refuse_download, pin_file)  # a rerun downloads nothing
    assert code == 0
    assert main(["verify"], pin=load_pin(pin_file)) == 0


# --- refusals ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("target", [TEST_COMMIT, TEST_COMMIT.upper()])
def test_the_active_pin_is_refused(cache, tmp_path, capsys, target):
    pin, files = files_world({})
    github = FakeGitHub()
    pin_file = tmp_path / "PIN.json"

    code, out, err = run(capsys, ["pin", target], pin, routed(files, github), pin_file)

    assert code == 1
    assert out == ""
    assert err.startswith("error: ")
    assert "already the pin" in err
    assert files.urls == [] and github.urls == []
    assert not pin_file.exists()
    assert not (cache / "repoe-fork").exists()


def test_a_new_export_of_the_active_pins_version_can_be_pinned(cache, tmp_path, capsys):
    pin, files = files_world({COMMIT: new_files()})
    pin_file = tmp_path / "PIN.json"

    code, _, _ = run(capsys, ["pin", COMMIT, PIN_VERSION], pin, files, pin_file)

    assert code == 0
    assert load_pin(pin_file) == expected_pin(version=PIN_VERSION)
    assert main(["verify"], pin=load_pin(pin_file)) == 0


def test_a_name_whose_export_is_the_pin_commit_is_refused(cache, tmp_path, capsys):
    pin, files = files_world({}, pin_commit=sha_of("926da1c0"))  # the pin is Export 3.29.3.2
    pin_file = tmp_path / "PIN.json"

    code, _, err = run(capsys, ["pin", "3.29.3.2"], pin, routed(files, FakeGitHub()), pin_file)

    assert code == 1
    assert "already the pin" in err
    assert files.urls == []
    assert not pin_file.exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["pin"],
        ["pin", "xyz"],
        ["pin", "b" * 39],
        ["pin", COMMIT, "notaversion"],
        ["pin", COMMIT, "5"],
        ["pin", COMMIT, "5.1.2", "extra"],
        ["pin", "3.29.3.2", "3.29.3.1"],
    ],
)
def test_wrong_usage_of_pin_exits_two_before_any_work(cache, tmp_path, capsys, argv):
    pin, files = files_world({COMMIT: new_files()})
    github = FakeGitHub()
    pin_file = tmp_path / "PIN.json"

    code, out, err = run(capsys, argv, pin, routed(files, github), pin_file)

    assert code == 2
    assert out == ""
    assert "usage:" in err
    assert files.urls == [] and github.urls == []
    assert not pin_file.exists()


@pytest.mark.parametrize("message", ["[skip ci] Version 5.1.2", "[skip ci] Export Internal Server Error", "Merge pull request #3"])
def test_a_commit_whose_message_names_no_export_needs_a_version(cache, tmp_path, capsys, message):
    pin, files = files_world({COMMIT: new_files()})
    pin_file = tmp_path / "PIN.json"

    code, out, err = run(capsys, ["pin", COMMIT], pin, routed(files, commit_answer(COMMIT, message)), pin_file)

    assert code == 1
    assert out == ""
    assert err.startswith("error: ")
    assert "VERSION" in err
    assert f"pin {COMMIT} <version>" in err
    assert files.urls == []
    assert not pin_file.exists()
    assert not (cache / "repoe-fork").exists()


def test_github_failing_for_a_commit_without_a_version_exits_one(cache, tmp_path, capsys):
    pin, files = files_world({COMMIT: new_files()})
    pin_file = tmp_path / "PIN.json"

    code, _, err = run(capsys, ["pin", COMMIT], pin, routed(files, FakeGitHub()), pin_file)  # the API knows no such commit

    assert code == 1
    assert "422" in err
    assert f"{COMMITS_URL}/{COMMIT}" in err
    assert not pin_file.exists()


def test_a_version_name_with_no_export_exits_one(cache, tmp_path, capsys):
    pin, files = files_world({})
    pin_file = tmp_path / "PIN.json"

    code, out, err = run(capsys, ["pin", "3.29.9.9"], pin, routed(files, FakeGitHub()), pin_file)

    assert code == 1
    assert out == ""
    assert "no export of 3.29.9.9" in err
    assert files.urls == []
    assert not pin_file.exists()


def test_a_commit_that_does_not_exist_downloads_nothing_and_leaves_the_pin(cache, tmp_path, capsys):
    pin, files = files_world({})
    pin_file = tmp_path / "PIN.json"
    pin_file.write_bytes(b"the old pin")

    code, _, err = run(capsys, ["pin", COMMIT, NEW_VERSION], pin, files, pin_file)

    assert code == 1
    assert "404" in err
    assert pin_file.read_bytes() == b"the old pin"
    assert not folder_of(cache, NEW_VERSION).exists()


def test_pin_is_listed_in_the_help(capsys):
    assert main(["--help"]) == 0
    assert "pin" in capsys.readouterr().out
    assert main(["pin", "--help"]) == 0
    out = capsys.readouterr().out
    assert "TARGET" in out
    assert "VERSION" in out


# --- the pin file ---------------------------------------------------------------------------------------


def test_the_committed_pin_file_loads_and_is_the_pin():
    assert PIN_FILE.name == "PIN.json"
    assert PIN_FILE.parent == Path(data_main.__file__).parent  # inside the package, so an install ships it
    assert load_pin() == PIN
    assert [file.name for file in PIN.files] == list(FILE_NAMES)


def test_the_committed_pin_file_round_trips_byte_for_byte(tmp_path):
    copy = tmp_path / "PIN.json"

    write_pin(load_pin(), copy)

    assert copy.read_bytes() == PIN_FILE.read_bytes()
    assert not PIN_FILE.read_bytes().endswith(b"\n\n")
    assert PIN_FILE.read_bytes().endswith(b"\n")
    assert b"\r" not in PIN_FILE.read_bytes()
    assert PIN_FILE.read_bytes().startswith(b'{\n  "version": ')


def test_write_pin_replaces_the_file_whole_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "PIN.json"
    path.write_bytes(b"old")

    write_pin(expected_pin(), path)

    assert load_pin(path) == expected_pin()
    assert listing(tmp_path) == ["PIN.json"]


def test_write_pin_into_a_missing_folder_is_a_clear_error(tmp_path):
    with pytest.raises(PinFileError, match="could not write the pin file"):
        write_pin(expected_pin(), tmp_path / "missing" / "PIN.json")


def valid_document():
    return json.loads(PIN_FILE.read_text(encoding="utf-8"))


def without(key):
    def change(document):
        del document[key]

    return change


def edit(key, value):
    def change(document):
        document[key] = value

    return change


def edit_file(key, value):
    def change(document):
        document["files"][0][key] = value

    return change


def drop_file_key(document):
    del document["files"][0]["size"]


def duplicate_file(document):
    document["files"].append(dict(document["files"][0]))


@pytest.mark.parametrize(
    "tamper",
    [
        without("version"),
        without("files"),
        edit("extra", 1),
        edit("version", "../escape"),
        edit("version", 3),
        edit("commit", "XYZ"),
        edit("commit", "b" * 39),
        edit("base_url", "http://example.test/repoe"),
        edit("base_url", "https://example.test/repoe/"),
        edit("files", {}),
        edit("files", []),
        edit("files", "mods.json"),
        edit_file("sha256", "XYZ"),
        edit_file("size", 0),
        edit_file("size", "12"),
        edit_file("name", "a/b.json"),
        drop_file_key,
        duplicate_file,
    ],
)
def test_a_pin_file_that_does_not_fit_is_a_clear_error_naming_the_file(tmp_path, tamper):
    document = valid_document()
    tamper(document)
    path = tmp_path / "PIN.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PinFileError) as caught:
        load_pin(path)

    assert str(path) in str(caught.value)


@pytest.mark.parametrize("content", [b"", b"{", b"not json", b"[]", b"null", b"\xff\xfe\x00", b"[" * 200_000])
def test_a_corrupt_pin_file_is_a_clear_error_naming_the_file(tmp_path, content):
    path = tmp_path / "PIN.json"
    path.write_bytes(content)

    with pytest.raises(PinFileError, match="cannot be used") as caught:
        load_pin(path)

    assert str(path) in str(caught.value)


def test_a_missing_pin_file_is_a_clear_error_naming_the_file(tmp_path):
    with pytest.raises(PinFileError) as caught:
        load_pin(tmp_path / "PIN.json")

    assert str(tmp_path / "PIN.json") in str(caught.value)


def test_a_pin_file_error_is_printed_as_an_error_line_by_the_command(tmp_path, capsys):
    pin, files = files_world({COMMIT: new_files()})
    pin_file = tmp_path / "missing" / "PIN.json"  # the folder is not there: the last step fails

    code = main(["pin", COMMIT, NEW_VERSION], pin=pin, open_url=files, pin_file=pin_file)

    assert code == 1
    assert "could not write the pin file" in capsys.readouterr().err


def test_no_text_of_the_data_package_tells_anyone_to_paste_into_pin():
    for path in Path(data_main.__file__).parent.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "paste into pin" not in text, path.name
        assert "edit `pin`" not in text, path.name

