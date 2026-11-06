"""The one loader of the raw repoe-fork export for the independent checks (ticket #432).

`tests/oracle/` (the goal oracle, #411) and `tests/reconcile/` (the reconciliation checks, #412) both read the export
straight from its JSON files, with no planner code. They had a loader each; this is the one they now share. It imports the
standard library only (`test_independent_guard.py` scans it).

The folder is `<cache dir>/repoe-fork/<version>/`, the layout `data fetch` writes. Nothing here is checked against the
pin's hashes: `data verify` does that in CI before any test runs.

Settled when the two loaders were merged (the tests of both suites say the same, see `test_export_loader.py`)
  * Cache dir. `CRAFTING_CACHE_DIR`, else `<repo>/local/cache`. The oracle loader read the environment only and failed with
    a `KeyError` when it was not set (its support module added the default itself); the default is now in one place.
  * Error. One type, `ExportMissing`, a `FileNotFoundError` (so a test that skips on a missing file still does). The oracle
    loader raised a bare `FileNotFoundError` with the file path, or 'holds N versions with a mods file; give the pin file';
    the reconcile one `ExportMissing` with 'mods.json is not in <folder>' or 'no pin file and N version folders in <holder>'.
    The reconcile messages are kept (the real-data tests match them).
  * The pin file. `pin_file` is the repo's `PIN.json` by default. A pin file that is given but is not there, or that names no
    `version`, is an error: the reconcile loader fell back to the only version folder when the pin file was absent, which hides
    a wrong path. `pin_file=None` means there is no pin: then the cache must hold exactly one version folder (a folder
    of any content counts, as in the reconcile loader; the oracle one counted only folders with a mods file).
  * Files. `mods.json` and `base_items.json` are required. `crafting_bench_options.json` and `essences.json` are read when
    they are there (the oracle needs them; the reconciliation ignores them) and are empty when they are not.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN_FILE = REPO_ROOT / "src" / "crafting_system" / "data" / "PIN.json"
DEFAULT_CACHE = REPO_ROOT / "local" / "cache"

MODS_FILE = "mods.json"
BASES_FILE = "base_items.json"
BENCH_FILE = "crafting_bench_options.json"
ESSENCES_FILE = "essences.json"


class ExportMissing(FileNotFoundError):
    """The export, a file of it or the pin file is not where it is looked for; the message says where."""


@dataclass(frozen=True)
class RawExport:
    """The files of one version, as the plain JSON values they hold: mods by id, bases by metadata id, bench options, essences."""

    mods: dict
    bases: dict
    bench_options: list = field(default_factory=list)
    essences: dict = field(default_factory=dict)
    source: str = ""


def cache_dir(environ=None) -> Path:
    """`CRAFTING_CACHE_DIR`, or the project's default folder (`local/cache`) when it is not set, as the planner finds it."""
    environ = os.environ if environ is None else environ
    given = environ.get("CRAFTING_CACHE_DIR")
    return Path(given) if given else DEFAULT_CACHE


def pinned_version(pin_file: Path) -> str:
    """The `version` a pin file names; `ExportMissing` when the file is not there or names none."""
    if not pin_file.is_file():
        raise ExportMissing(f"the pin file {pin_file} is not there")
    version = json.loads(pin_file.read_text(encoding="utf-8")).get("version")
    if not isinstance(version, str) or not version:
        raise ExportMissing(f"the pin file {pin_file} names no version")
    return version


def version_folder(root: Path, pin_file: Path | None = PIN_FILE) -> Path:
    """The folder of the pinned version under `root/repoe-fork`; with `pin_file=None`, the only one there."""
    holder = root / "repoe-fork"
    if pin_file is not None:
        return holder / pinned_version(pin_file)
    found = sorted(path for path in holder.glob("*") if path.is_dir()) if holder.is_dir() else []
    if len(found) != 1:
        raise ExportMissing(f"no pin file and {len(found)} version folders in {holder}")
    return found[0]


def read_folder(folder: Path) -> RawExport:
    """Read the files of one version folder; `ExportMissing` when `mods.json` or `base_items.json` is absent."""
    required = {}
    for name in (MODS_FILE, BASES_FILE):
        path = folder / name
        if not path.is_file():
            raise ExportMissing(f"{name} is not in {folder}")
        required[name] = json.loads(path.read_text(encoding="utf-8"))
    optional = {}
    for name in (BENCH_FILE, ESSENCES_FILE):
        path = folder / name
        optional[name] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    return RawExport(
        mods=required[MODS_FILE],
        bases=required[BASES_FILE],
        bench_options=optional[BENCH_FILE] or [],
        essences=optional[ESSENCES_FILE] or {},
        source=str(folder),
    )


def load_export(root: Path | None = None, pin_file: Path | None = PIN_FILE) -> RawExport:
    """The export of the pinned version in `root` (default: `cache_dir()`); `pin_file=None` takes the only version there."""
    root = cache_dir() if root is None else root
    return read_folder(version_folder(root, pin_file))
