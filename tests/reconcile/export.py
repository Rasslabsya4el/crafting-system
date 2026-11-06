"""The raw repoe-fork export, read straight from its JSON files.

The folder is `<CRAFTING_CACHE_DIR>/repoe-fork/<version>/` (the layout `data fetch` writes). The version
is the one the pin file names; without a pin file, the only version folder present. Nothing here is
checked against the pin's hashes: `data verify` does that in CI before any test runs.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN_FILE = REPO_ROOT / "src" / "crafting_system" / "data" / "PIN.json"
DEFAULT_CACHE = REPO_ROOT / "local" / "cache"


class ExportMissing(Exception):
    """The export is not in the cache folder; the message says where it looked."""


@dataclass(frozen=True)
class Export:
    """The two files the checks need: mods by id, and base items by metadata id."""

    mods: dict
    bases: dict
    source: str = ""


def cache_dir(environ=None) -> Path:
    environ = os.environ if environ is None else environ
    given = environ.get("CRAFTING_CACHE_DIR")
    return Path(given) if given else DEFAULT_CACHE


def version_folder(root: Path, pin_file: Path = PIN_FILE) -> Path:
    """The folder of the pinned version under `root/repoe-fork`, or the only one there."""
    holder = root / "repoe-fork"
    version = None
    if pin_file.is_file():
        version = json.loads(pin_file.read_text(encoding="utf-8")).get("version")
    if version:
        return holder / version
    found = sorted(path for path in holder.glob("*") if path.is_dir()) if holder.is_dir() else []
    if len(found) != 1:
        raise ExportMissing(f"no pin file and {len(found)} version folders in {holder}")
    return found[0]


def load_export(root: Path | None = None, pin_file: Path = PIN_FILE) -> Export:
    """Read `mods.json` and `base_items.json`; `ExportMissing` when either file is absent."""
    root = cache_dir() if root is None else root
    folder = version_folder(root, pin_file)
    files = {}
    for name in ("mods.json", "base_items.json"):
        path = folder / name
        if not path.is_file():
            raise ExportMissing(f"{name} is not in {folder}")
        files[name] = json.loads(path.read_text(encoding="utf-8"))
    return Export(mods=files["mods.json"], bases=files["base_items.json"], source=str(folder))
