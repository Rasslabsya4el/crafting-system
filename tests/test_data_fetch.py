"""Fetching, verifying and loading the pinned repoe-fork files, all against a fake downloader."""

import hashlib
import http.client
import urllib.error
import urllib.request

import pytest
from repoe_support import (
    FILE_NAMES,
    TEST_COMMIT,
    FakeOpener,
    fixture_bytes,
    fixture_game_data,
    fixture_pin_and_opener,
    leftover_temp_files,
    make_pin,
    no_network,  # noqa: F401
)

from crafting_system.data import fetch as fetch_module
from crafting_system.data.errors import (
    DataError,
    FetchError,
    HashMismatchError,
    MissingDataError,
    RawFormatError,
)
from crafting_system.data.fetch import FetchResult, cache_folder, fetch, verify_cache
from crafting_system.data.load import load_game_data
from crafting_system.data.pin import PIN, PinnedFile, RepoePin

FETCH_COMMAND = "python -m crafting_system.data fetch"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetched(tmp_path):
    """Fetch the fixtures into `tmp_path`; the pin, the opener and the cache folder."""
    pin, opener = fixture_pin_and_opener()
    fetch(pin, tmp_path, open_url=opener)
    return pin, opener, cache_folder(pin, tmp_path)


def forbidden_open_url(url):
    raise AssertionError(f"tried to download {url}")


# --- layout and results -------------------------------------------------------------------


def test_cache_layout_is_cache_dir_repoe_fork_version(tmp_path):
    pin, _ = fixture_pin_and_opener()

    assert cache_folder(pin, tmp_path) == tmp_path / "repoe-fork" / pin.version


def test_first_fetch_downloads_every_file_into_the_cache_folder(tmp_path):
    pin, opener = fixture_pin_and_opener()
    payloads = fixture_bytes()

    results = fetch(pin, tmp_path, open_url=opener)

    folder = cache_folder(pin, tmp_path)
    assert [r.name for r in results] == list(FILE_NAMES)
    assert {r.status for r in results} == {"downloaded"}
    assert opener.urls == [pin.url_for(name) for name in FILE_NAMES]
    for result in results:
        data = payloads[result.name]
        assert (folder / result.name).read_bytes() == data
        assert result == FetchResult(result.name, "downloaded", sha(data), len(data))
    assert leftover_temp_files(folder) == []


def test_fetch_creates_the_cache_folder_as_needed(tmp_path):
    pin, opener = fixture_pin_and_opener()
    deep = tmp_path / "a" / "b"

    fetch(pin, deep, open_url=opener)

    assert (cache_folder(pin, deep) / "mods.json").is_file()


def test_second_fetch_makes_no_download_at_all(tmp_path):
    pin, opener, _ = fetched(tmp_path)
    calls_after_first = list(opener.urls)

    results = fetch(pin, tmp_path, open_url=opener)

    assert opener.urls == calls_after_first
    assert [r.status for r in results] == ["cached"] * len(FILE_NAMES)
    assert [r.sha256 for r in results] == [f.sha256 for f in pin.files]
    assert [r.size for r in results] == [f.size for f in pin.files]


def test_second_fetch_works_with_an_opener_that_must_not_be_called(tmp_path):
    pin, _, _ = fetched(tmp_path)

    results = fetch(pin, tmp_path, open_url=forbidden_open_url)

    assert {r.status for r in results} == {"cached"}


def test_fetch_repairs_a_corrupt_cached_file_and_leaves_the_good_ones(tmp_path):
    pin, opener, folder = fetched(tmp_path)
    (folder / "fossils.json").write_bytes(b"garbage")
    opener.urls.clear()

    results = fetch(pin, tmp_path, open_url=opener)

    assert {r.name: r.status for r in results} == {
        name: ("repaired" if name == "fossils.json" else "cached") for name in FILE_NAMES
    }
    assert opener.urls == [pin.url_for("fossils.json")]
    assert (folder / "fossils.json").read_bytes() == fixture_bytes()["fossils.json"]


def test_fetch_repairs_a_cached_file_of_the_right_size_but_the_wrong_hash(tmp_path):
    pin, opener, folder = fetched(tmp_path)
    good = (folder / "mods.json").read_bytes()
    (folder / "mods.json").write_bytes(b"X" * len(good))

    results = fetch(pin, tmp_path, open_url=opener)

    assert results[0] == FetchResult("mods.json", "repaired", sha(good), len(good))


def test_fetch_downloads_only_the_files_that_are_missing(tmp_path):
    pin, opener, folder = fetched(tmp_path)
    (folder / "essences.json").unlink()
    opener.urls.clear()

    results = fetch(pin, tmp_path, open_url=opener)

    assert {r.name: r.status for r in results}["essences.json"] == "downloaded"
    assert opener.urls == [pin.url_for("essences.json")]


# --- a download that is wrong -------------------------------------------------------------


def tampered_opener(pin, name, change):
    payloads = fixture_bytes()
    payloads[name] = change(payloads[name])
    return FakeOpener(pin, payloads)


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data[:-1] + bytes([data[-1] ^ 1]),  # same size, one bit flipped
        lambda data: data[:-5],  # truncated
        lambda data: data + b"\n",  # one byte too many
    ],
    ids=["flipped", "truncated", "longer"],
)
def test_a_download_that_differs_from_the_pin_fails_loudly_and_keeps_nothing(tmp_path, change):
    pin, _ = fixture_pin_and_opener()
    opener = tampered_opener(pin, "essences.json", change)
    pinned = next(f for f in pin.files if f.name == "essences.json")

    with pytest.raises(HashMismatchError) as caught:
        fetch(pin, tmp_path, open_url=opener)

    message = str(caught.value)
    assert "essences.json" in message
    assert pinned.sha256 in message
    assert pin.url_for("essences.json") in message
    assert "nothing was kept" in message
    folder = cache_folder(pin, tmp_path)
    assert not (folder / "essences.json").exists()
    assert leftover_temp_files(folder) == []


def test_a_bad_download_does_not_replace_a_good_cached_copy_of_another_file(tmp_path):
    pin, opener, folder = fetched(tmp_path)
    good_mods = (folder / "mods.json").read_bytes()
    (folder / "fossils.json").write_bytes(b"corrupt")
    broken = tampered_opener(pin, "fossils.json", lambda data: data[:-1])

    with pytest.raises(HashMismatchError):
        fetch(pin, tmp_path, open_url=broken)

    assert (folder / "mods.json").read_bytes() == good_mods
    assert (folder / "fossils.json").read_bytes() == b"corrupt"  # untouched; verify will flag it
    assert leftover_temp_files(folder) == []


class EndlessStream:
    """A binary stream that never ends: a server sending far more than the pin allows."""

    def __init__(self, limit=64 * 1024 * 1024):
        self.served = 0
        self.limit = limit

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size=-1):
        size = 1024 * 1024 if size is None or size < 0 else size
        size = min(size, self.limit - self.served)
        self.served += size
        return b"x" * size


def test_a_download_larger_than_the_pin_is_aborted_early(tmp_path):
    pin, _ = fixture_pin_and_opener()
    stream = EndlessStream()

    with pytest.raises(HashMismatchError) as caught:
        fetch(pin, tmp_path, open_url=lambda url: stream)

    assert "more than" in str(caught.value)
    assert stream.served < 8 * 1024 * 1024  # stopped after a chunk or two, not 64 MiB
    folder = cache_folder(pin, tmp_path)
    assert list(folder.iterdir()) == []


# --- the network fails --------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("no route"),
        urllib.error.HTTPError("u", 503, "Service Unavailable", None, None),
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
        OSError("disk or network"),
        http.client.IncompleteRead(b"abc"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_a_failing_open_url_becomes_a_fetch_error_naming_the_url(tmp_path, error):
    pin, _ = fixture_pin_and_opener()

    def failing(url):
        raise error

    with pytest.raises(FetchError) as caught:
        fetch(pin, tmp_path, open_url=failing)

    assert pin.url_for("mods.json") in str(caught.value)
    assert list(cache_folder(pin, tmp_path).iterdir()) == []


class DyingStream:
    """Delivers some bytes, then the connection drops."""

    def __init__(self, data):
        self.data = data
        self.sent = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size=-1):
        if not self.sent:
            self.sent = True
            return self.data[: len(self.data) // 2]
        raise ConnectionResetError("connection dropped")


def test_a_connection_that_drops_mid_download_leaves_no_temp_file(tmp_path):
    pin, _ = fixture_pin_and_opener()
    data = fixture_bytes()["mods.json"]

    with pytest.raises(FetchError, match="mods.json"):
        fetch(pin, tmp_path, open_url=lambda url: DyingStream(data))

    assert list(cache_folder(pin, tmp_path).iterdir()) == []


def test_the_default_downloader_sends_a_user_agent_and_a_timeout(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["url"] = request.full_url
        seen["agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return "response"

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert fetch_module.default_open_url("https://example.test/file") == "response"
    assert seen == {"url": "https://example.test/file", "agent": "crafting-system", "timeout": 60}


def test_fetch_without_open_url_uses_the_default_downloader(tmp_path, monkeypatch):
    pin, opener = fixture_pin_and_opener()
    monkeypatch.setattr(fetch_module, "default_open_url", opener)

    fetch(pin, tmp_path)

    assert len(opener.urls) == len(FILE_NAMES)


# --- verify and load ----------------------------------------------------------------------


def test_verify_cache_accepts_a_good_cache(tmp_path):
    pin, _, _ = fetched(tmp_path)

    assert verify_cache(pin, tmp_path) is None


def test_load_game_data_after_a_fetch_is_offline(tmp_path, monkeypatch):
    pin, _, _ = fetched(tmp_path)
    monkeypatch.setattr(fetch_module, "default_open_url", forbidden_open_url)

    data = load_game_data(pin, tmp_path)

    assert data == fixture_game_data()
    assert data.version == pin.version
    assert "LocalAddedFireDamageTwoHand1" in data.mods


@pytest.mark.parametrize("name", FILE_NAMES)
@pytest.mark.parametrize("how", ["flip", "truncate", "extend", "empty"])
def test_a_tampered_cached_file_is_caught_by_verify_and_load(tmp_path, name, how):
    pin, _, folder = fetched(tmp_path)
    original = (folder / name).read_bytes()
    tampered = {
        "flip": original[:-1] + bytes([original[-1] ^ 1]),
        "truncate": original[:-1],
        "extend": original + b" ",
        "empty": b"",
    }[how]
    (folder / name).write_bytes(tampered)
    pinned = next(f for f in pin.files if f.name == name)

    for action in (lambda: verify_cache(pin, tmp_path), lambda: load_game_data(pin, tmp_path)):
        with pytest.raises(HashMismatchError) as caught:
            action()
        message = str(caught.value)
        assert name in message
        assert pinned.sha256 in message  # expected
        assert sha(tampered) in message  # actual


def test_a_missing_cache_tells_the_user_to_run_fetch(tmp_path):
    pin, _ = fixture_pin_and_opener()

    for action in (lambda: verify_cache(pin, tmp_path), lambda: load_game_data(pin, tmp_path)):
        with pytest.raises(MissingDataError) as caught:
            action()
        assert FETCH_COMMAND in str(caught.value)
        assert "mods.json" in str(caught.value)


def test_one_missing_file_is_reported_by_name(tmp_path):
    pin, _, folder = fetched(tmp_path)
    (folder / "fossils.json").unlink()

    with pytest.raises(MissingDataError, match="fossils.json"):
        load_game_data(pin, tmp_path)


def test_stale_temp_files_are_not_mistaken_for_data(tmp_path):
    pin, _, folder = fetched(tmp_path)
    stale = folder / "mods.json.stale.part"
    stale.write_bytes(b"half a file")
    (folder / "essences.json").unlink()
    (folder / "essences.json.stale.part").write_bytes(fixture_bytes()["essences.json"])

    with pytest.raises(MissingDataError, match="essences.json"):
        load_game_data(pin, tmp_path)
    fetch(pin, tmp_path, open_url=FakeOpener(pin, fixture_bytes()))

    assert load_game_data(pin, tmp_path) == fixture_game_data()
    assert stale.read_bytes() == b"half a file"


def test_cached_json_that_is_not_json_raises_raw_format_error(tmp_path):
    payloads = fixture_bytes()
    payloads["mods.json"] = b"{ not json"
    pin = make_pin(payloads)
    fetch(pin, tmp_path, open_url=FakeOpener(pin, payloads))

    with pytest.raises(RawFormatError, match="mods.json"):
        load_game_data(pin, tmp_path)


def test_every_failure_is_a_data_error():
    for error in (HashMismatchError, MissingDataError, FetchError, RawFormatError):
        assert issubclass(error, DataError)


# --- the default cache directory ----------------------------------------------------------


def test_default_cache_dir_comes_from_the_configured_cache_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("CRAFTING_CONFIG", raising=False)
    monkeypatch.setenv("CRAFTING_CACHE_DIR", str(tmp_path / "configured"))
    pin, opener = fixture_pin_and_opener()

    fetch(pin, open_url=opener)

    assert (tmp_path / "configured" / "repoe-fork" / pin.version / "mods.json").is_file()
    assert verify_cache(pin) is None
    assert load_game_data(pin) == fixture_game_data()
    assert cache_folder(pin) == tmp_path / "configured" / "repoe-fork" / pin.version


# --- the pin ------------------------------------------------------------------------------


def test_the_real_pin_is_the_pinned_3_29_3_3_export():
    assert PIN.version == "3.29.3.3"
    assert PIN.commit == "ee2084dec1f17180a132b5d133082af5b3136ace"
    assert [f.name for f in PIN.files] == [
        "mods.json",
        "base_items.json",
        "essences.json",
        "fossils.json",
        "crafting_bench_options.json",
    ]
    assert PIN.url_for("mods.json") == (
        "https://raw.githubusercontent.com/repoe-fork/repoe-fork.github.io/"
        "ee2084dec1f17180a132b5d133082af5b3136ace/data/mods.json"
    )
    assert {f.name: (f.size, f.sha256) for f in PIN.files}["mods.json"] == (
        34279067,
        "defbba31b60f9191080c78197278057f834f7f927c1a2a080a7ca6ed3ea686b5",
    )


GOOD_FILE = PinnedFile("a.json", "0" * 64, 10)


def pin_with(**changes):
    fields = dict(version="1.0", commit=TEST_COMMIT, base_url="https://example.test/x", files=(GOOD_FILE,))
    fields.update(changes)
    return RepoePin(**fields)


@pytest.mark.parametrize(
    "changes",
    [
        {"base_url": "http://example.test/x"},
        {"base_url": "https://example.test/x/"},
        {"commit": "abc"},
        {"commit": "A" * 40},
        {"commit": "g" * 40},
        {"version": ""},
        {"version": "../escape"},
        {"version": "a/b"},
        {"files": ()},
        {"files": (GOOD_FILE, GOOD_FILE)},
    ],
)
def test_a_bad_pin_is_rejected_on_construction(changes):
    with pytest.raises(ValueError):
        pin_with(**changes)


@pytest.mark.parametrize(
    "fields",
    [
        {"sha256": "0" * 63},
        {"sha256": "g" * 64},
        {"sha256": "A" * 64},
        {"size": 0},
        {"size": -1},
        {"size": True},
        {"size": 1.5},
        {"name": ""},
        {"name": "sub/dir.json"},
        {"name": "..\\x.json"},
        {"name": ".."},
    ],
)
def test_a_bad_pinned_file_is_rejected_on_construction(fields):
    arguments = dict(name="a.json", sha256="0" * 64, size=10)
    arguments.update(fields)

    with pytest.raises(ValueError):
        PinnedFile(**arguments)


def test_pin_and_files_are_frozen():
    with pytest.raises(AttributeError):
        PIN.version = "x"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        PIN.files[0].size = 1  # type: ignore[misc]
