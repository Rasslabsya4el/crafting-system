"""Shared helpers for the `data` tests: fixture loading, a fake downloader, a network block.

Not a test module and not a conftest: each `tests/test_data_*.py` imports what it needs, and
`no_network` below is an autouse fixture, so importing it into a test module switches it on for
every test of that module.
"""

import hashlib
import io
import json
import socket
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path

import pytest

from crafting_system.data.model import GameData
from crafting_system.data.normalize import normalize_game_data
from crafting_system.data.pin import PinnedFile, RepoePin

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "repoe"

FILE_NAMES = (
    "mods.json",
    "base_items.json",
    "essences.json",
    "fossils.json",
    "crafting_bench_options.json",
)

TEST_VERSION = "0.0-test"
TEST_COMMIT = "a" * 40
TEST_BASE_URL = "https://example.test/repoe"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any real network use fails the test: the data tests are offline."""

    def refuse(*args, **kwargs):
        raise AssertionError("the test used the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def fixture_bytes() -> dict[str, bytes]:
    """The committed excerpt files, by file name."""
    return {name: (FIXTURE_DIR / name).read_bytes() for name in FILE_NAMES}


def raw_fixtures() -> dict[str, object]:
    """The committed excerpts parsed, by file name."""
    return {name: json.loads(data) for name, data in fixture_bytes().items()}


def fixture_game_data() -> GameData:
    raw = raw_fixtures()
    return normalize_game_data(
        raw["mods.json"],
        raw["base_items.json"],
        raw["fossils.json"],
        raw["essences.json"],
        raw["crafting_bench_options.json"],
        version=TEST_VERSION,
    )


def make_pin(payloads: Mapping[str, bytes], *, version: str = TEST_VERSION) -> RepoePin:
    """A pin whose sizes and hashes are computed from `payloads` (file name -> bytes)."""
    files = tuple(
        PinnedFile(name=name, sha256=hashlib.sha256(data).hexdigest(), size=len(data))
        for name, data in payloads.items()
    )
    return RepoePin(version=version, commit=TEST_COMMIT, base_url=TEST_BASE_URL, files=files)


class FakeOpener:
    """Stands in for `open_url`: serves bytes by URL and remembers every URL it was asked for."""

    def __init__(self, pin: RepoePin, payloads: Mapping[str, bytes]):
        self.served = {pin.url_for(name): data for name, data in payloads.items()}
        self.urls: list[str] = []

    def __call__(self, url: str):
        self.urls.append(url)
        if url not in self.served:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        return io.BytesIO(self.served[url])


def fixture_pin_and_opener() -> tuple[RepoePin, FakeOpener]:
    payloads = fixture_bytes()
    pin = make_pin(payloads)
    return pin, FakeOpener(pin, payloads)


def leftover_temp_files(folder: Path) -> list[str]:
    """Names in `folder` that are not one of the data files: a temp file left behind would show here."""
    return sorted(path.name for path in folder.iterdir() if path.name not in FILE_NAMES)
