"""Load the pinned data from the cache, offline, into the typed model."""

import json
from pathlib import Path
from typing import Any

from .errors import MissingDataError, RawFormatError
from .fetch import read_verified_files
from .model import GameData
from .normalize import (
    BASE_ITEMS_FILE,
    BENCH_OPTIONS_FILE,
    ESSENCES_FILE,
    FOSSILS_FILE,
    MODS_FILE,
    normalize_game_data,
)
from .pin import PIN, RepoePin


def load_game_data(pin: RepoePin = PIN, cache_dir: Path | None = None) -> GameData:
    """Verify the cached files against the pin, parse them and normalize them.

    Never opens a network connection: a missing file raises `MissingDataError` (run the fetch
    command), a changed one `HashMismatchError`, a file that is not the expected JSON shape
    `RawFormatError`.
    """
    contents = read_verified_files(pin, cache_dir)
    needed = (MODS_FILE, BASE_ITEMS_FILE, FOSSILS_FILE, ESSENCES_FILE, BENCH_OPTIONS_FILE)
    unlisted = [name for name in needed if name not in contents]
    if unlisted:
        raise MissingDataError(f"the pin for {pin.version} does not list {', '.join(unlisted)}")
    raw = {name: _parse(name, contents[name]) for name in needed}
    return normalize_game_data(
        raw[MODS_FILE],
        raw[BASE_ITEMS_FILE],
        raw[FOSSILS_FILE],
        raw[ESSENCES_FILE],
        raw[BENCH_OPTIONS_FILE],
        version=pin.version,
    )


def _parse(name: str, data: bytes) -> Any:
    try:
        return json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RawFormatError(f"{name}: not valid JSON: {error}") from error
