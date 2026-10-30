"""A repoe-fork commit that is not the active pin: its files and manifest are learned once, then checked."""

import dataclasses
import hashlib
import json
import urllib.error

import pytest
from repoe_support import (
    FILE_NAMES,
    TEST_BASE_URL,
    FakeOpener,
    fixture_bytes,
    fixture_pin_and_opener,
    make_pin,
    no_network,  # noqa: F401
)

from crafting_system.data import FetchError, HashMismatchError, candidate
from crafting_system.data.candidate import MANIFEST_NAME, candidate_pin
from crafting_system.data.fetch import fetch, read_verified_files

COMMIT = "b" * 40
TEMPLATE, _ = fixture_pin_and_opener()  # the active pin of these tests: its base URL and file names are used


def served_pin(payloads=None, commit=COMMIT):
    """(the pin the files at `commit` would have, an opener serving them)."""
    payloads = fixture_bytes() if payloads is None else payloads
    pin = make_pin(payloads, version=commit, commit=commit)
    return pin, FakeOpener(pin, payloads)


def folder_of(tmp_path):
    return tmp_path / "repoe-fork" / COMMIT


def listing(folder):
    return sorted(path.name for path in folder.iterdir())


def test_the_first_use_downloads_the_five_files_and_learns_their_hashes(tmp_path):
    expected, opener = served_pin()

    pin = candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)

    assert pin == expected
    assert opener.urls == [expected.url_for(name) for name in FILE_NAMES]
    assert pin.version == pin.commit == COMMIT
    for pinned in pin.files:
        data = fixture_bytes()[pinned.name]
        assert pinned.size == len(data)
        assert pinned.sha256 == hashlib.sha256(data).hexdigest()
        assert (folder_of(tmp_path) / pinned.name).read_bytes() == data


def test_the_manifest_records_the_commit_the_base_url_and_each_file(tmp_path):
    _, opener = served_pin()

    candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)

    manifest = json.loads((folder_of(tmp_path) / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest == {
        "commit": COMMIT,
        "base_url": TEMPLATE.base_url,
        "files": [
            {"name": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in fixture_bytes().items()
        ],
    }


def test_nothing_but_the_five_files_and_the_manifest_is_left_in_the_folder(tmp_path):
    _, opener = served_pin()

    candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)

    assert listing(folder_of(tmp_path)) == sorted([*FILE_NAMES, MANIFEST_NAME])


def test_a_later_use_loads_the_manifest_and_opens_no_connection(tmp_path):
    _, opener = served_pin()
    first = candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)

    def refuse(url):
        raise AssertionError("the network was used")

    second = candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=refuse)

    assert second == first


def test_the_learned_pin_goes_through_the_ordinary_fetch_and_verify_path(tmp_path):
    _, opener = served_pin()
    pin = candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)
    downloads = len(opener.urls)

    results = fetch(pin, tmp_path, open_url=opener)

    assert [result.status for result in results] == ["cached"] * len(FILE_NAMES)
    assert len(opener.urls) == downloads
    assert read_verified_files(pin, tmp_path) == fixture_bytes()


def test_a_corrupted_cached_file_is_downloaded_again_and_checked_against_the_manifest(tmp_path):
    _, opener = served_pin()
    candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)
    (folder_of(tmp_path) / "fossils.json").write_bytes(b"corrupt")
    pin = candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=None)

    results = fetch(pin, tmp_path, open_url=opener)

    assert {result.name: result.status for result in results}["fossils.json"] == "repaired"
    assert (folder_of(tmp_path) / "fossils.json").read_bytes() == fixture_bytes()["fossils.json"]


def test_a_repair_that_does_not_match_the_manifest_is_refused_and_keeps_nothing(tmp_path):
    _, opener = served_pin()
    candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)
    (folder_of(tmp_path) / "fossils.json").write_bytes(b"corrupt")
    changed = fixture_bytes()
    changed["fossils.json"] = changed["fossils.json"] + b" "
    pin = candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=None)

    with pytest.raises(HashMismatchError, match="fossils.json"):
        fetch(pin, tmp_path, open_url=served_pin(changed)[1])

    assert listing(folder_of(tmp_path)) == sorted([*FILE_NAMES, MANIFEST_NAME])


def test_files_without_a_manifest_are_learned_again(tmp_path):
    _, opener = served_pin()
    candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)
    (folder_of(tmp_path) / MANIFEST_NAME).unlink()
    (folder_of(tmp_path) / "mods.json").write_bytes(b"left over from an interrupted run")
    _, second_opener = served_pin()

    pin = candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=second_opener)

    assert len(second_opener.urls) == len(FILE_NAMES)
    assert read_verified_files(pin, tmp_path) == fixture_bytes()


def test_an_http_404_names_the_url_and_leaves_no_file(tmp_path):
    expected, _ = served_pin()

    with pytest.raises(FetchError, match="404") as caught:
        candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=FakeOpener(expected, {}))

    assert expected.url_for("mods.json") in str(caught.value)
    assert listing(folder_of(tmp_path)) == []


def test_a_network_failure_is_a_fetch_error(tmp_path):
    def failing(url):
        raise urllib.error.URLError("no route to host")

    with pytest.raises(FetchError, match="no route to host"):
        candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=failing)

    assert listing(folder_of(tmp_path)) == []


def test_a_download_over_the_size_bound_is_cut_off_and_removes_the_files_already_stored(tmp_path, monkeypatch):
    reversed_template = dataclasses.replace(TEMPLATE, files=tuple(reversed(TEMPLATE.files)))
    # mods.json is the biggest excerpt and now comes last, after four files that fit under the bound
    monkeypatch.setattr(candidate, "MAX_FILE_BYTES", 8000)
    _, opener = served_pin()

    with pytest.raises(FetchError, match=r"mods\.json.*larger than 8000 bytes"):
        candidate_pin(COMMIT, reversed_template, tmp_path, open_url=opener)

    assert listing(folder_of(tmp_path)) == []


def test_an_empty_download_is_refused(tmp_path):
    payloads = fixture_bytes()
    pin, _ = served_pin()
    opener = FakeOpener(pin, payloads)
    opener.served[pin.url_for("essences.json")] = b""

    with pytest.raises(FetchError, match=r"essences\.json.*empty"):
        candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)

    assert listing(folder_of(tmp_path)) == []


def good_manifest(tmp_path):
    _, opener = served_pin()
    candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)
    path = folder_of(tmp_path) / MANIFEST_NAME
    return path, json.loads(path.read_text(encoding="utf-8"))


def drop_file(manifest):
    manifest["files"].pop()


def add_file(manifest):
    manifest["files"].append({"name": "extra.json", "sha256": "0" * 64, "size": 1})


def wrong_commit(manifest):
    manifest["commit"] = "c" * 40


def bad_hash(manifest):
    manifest["files"][0]["sha256"] = "XYZ"


def bad_size(manifest):
    manifest["files"][0]["size"] = 0


def http_url(manifest):
    manifest["base_url"] = "http://example.test/repoe"


def files_not_a_list(manifest):
    manifest["files"] = {"mods.json": "x"}


def missing_key(manifest):
    del manifest["base_url"]


@pytest.mark.parametrize(
    "tamper",
    [drop_file, add_file, wrong_commit, bad_hash, bad_size, http_url, files_not_a_list, missing_key],
)
def test_a_manifest_that_is_wrong_is_a_clear_error_and_is_not_silently_replaced(tmp_path, tamper):
    path, manifest = good_manifest(tmp_path)
    tamper(manifest)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    broken = path.read_bytes()

    with pytest.raises(FetchError, match=r"pin\.json") as caught:
        candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=served_pin()[1])

    assert "delete" in str(caught.value).lower()
    assert path.read_bytes() == broken


@pytest.mark.parametrize("content", [b"", b"{\"commit\": ", b"not json", b"[]", b"\xff\xfe", b"null"])
def test_a_half_written_or_garbage_manifest_is_a_clear_error(tmp_path, content):
    path, _ = good_manifest(tmp_path)
    path.write_bytes(content)

    with pytest.raises(FetchError, match=r"pin\.json"):
        candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=served_pin()[1])


def test_a_manifest_that_is_a_folder_is_a_clear_error(tmp_path):
    path, _ = good_manifest(tmp_path)
    path.unlink()
    path.mkdir()

    with pytest.raises(FetchError, match=r"pin\.json"):
        candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=served_pin()[1])


def test_a_file_where_the_cache_folder_should_be_is_a_clear_error(tmp_path):
    (tmp_path / "repoe-fork").mkdir()
    (tmp_path / "repoe-fork" / COMMIT).write_bytes(b"a file")

    with pytest.raises(FetchError, match="could not create the cache folder"):
        candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=served_pin()[1])


def test_the_manifest_base_url_is_used_for_later_downloads(tmp_path):
    expected, opener = served_pin()
    candidate_pin(COMMIT, TEMPLATE, tmp_path, open_url=opener)
    other_template = dataclasses.replace(TEMPLATE, base_url="https://elsewhere.test/repoe")

    pin = candidate_pin(COMMIT, other_template, tmp_path, open_url=None)

    assert pin.base_url == TEST_BASE_URL
    assert pin.url_for("mods.json") == expected.url_for("mods.json")
