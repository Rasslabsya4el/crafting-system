"""The raw repoe-fork export, read straight from its JSON files.

The loader is `tests/independent/export.py`, the one module this package shares with `tests/oracle/` (ticket #432): the folder
is `<CRAFTING_CACHE_DIR>/repoe-fork/<version>/` (the layout `data fetch` writes), the version the one the pin file names. What
is here is the `Export` the checks hold: the shared files, plus a cache of data derived from them (mod pools).
"""

from dataclasses import dataclass, field
from pathlib import Path

from independent import export as shared
from independent.export import DEFAULT_CACHE, PIN_FILE, REPO_ROOT, ExportMissing, cache_dir, version_folder

__all__ = ["DEFAULT_CACHE", "PIN_FILE", "REPO_ROOT", "Export", "ExportMissing", "cache_dir", "load_export", "version_folder"]


@dataclass(frozen=True)
class Export(shared.RawExport):
    """The shared export (mods by id, bases by metadata id), with a cache of derived data filled on demand."""

    cache: dict = field(default_factory=dict, compare=False, repr=False)


def load_export(root: Path | None = None, pin_file: Path | None = PIN_FILE) -> Export:
    """Read the pinned version from `root`; `ExportMissing` when it, a file of it or the pin file is absent."""
    raw = shared.load_export(root, pin_file)
    return Export(mods=raw.mods, bases=raw.bases, bench_options=raw.bench_options, essences=raw.essences, source=raw.source)
