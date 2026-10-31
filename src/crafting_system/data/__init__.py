"""Fetch, pin and normalize repoe-fork; knows nothing of crafting. Imports no other module of the package."""

from .candidate import candidate_pin
from .diff import PatchDiff, compare_game_data, diff_game_data, render_diff
from .errors import (
    DataError,
    FetchError,
    HashMismatchError,
    MissingDataError,
    PinFileError,
    RawFormatError,
    VersionNotFoundError,
)
# `fetch` the function stays in the `fetch` module: re-exporting it here would hide the module.
from .fetch import FetchResult, cache_folder, verify_cache
from .impact import (
    ClaimReference,
    DataChanges,
    Impact,
    Reference,
    ReferencingTestFile,
    compute_impact,
    find_repo_root,
    render_impact,
)
from .load import load_game_data
from .model import (
    BaseItem,
    BenchActions,
    BenchOption,
    CostEntry,
    Essence,
    EssenceMod,
    Fossil,
    GameData,
    Mod,
    StatRange,
    Weight,
    conflicts,
)
from .normalize import normalize_game_data
from .pin import PIN, PIN_FILE, PinnedFile, RepoePin, load_pin, write_pin
from .resolve import Export, export_of_commit, is_version_name, resolve_version

__all__ = [
    "PIN",
    "PIN_FILE",
    "BaseItem",
    "BenchActions",
    "BenchOption",
    "ClaimReference",
    "CostEntry",
    "DataChanges",
    "DataError",
    "Essence",
    "EssenceMod",
    "Export",
    "FetchError",
    "FetchResult",
    "Fossil",
    "GameData",
    "HashMismatchError",
    "Impact",
    "MissingDataError",
    "Mod",
    "PatchDiff",
    "PinFileError",
    "PinnedFile",
    "RawFormatError",
    "Reference",
    "ReferencingTestFile",
    "RepoePin",
    "StatRange",
    "VersionNotFoundError",
    "Weight",
    "cache_folder",
    "candidate_pin",
    "compare_game_data",
    "compute_impact",
    "conflicts",
    "diff_game_data",
    "export_of_commit",
    "find_repo_root",
    "is_version_name",
    "load_game_data",
    "load_pin",
    "normalize_game_data",
    "render_diff",
    "render_impact",
    "resolve_version",
    "verify_cache",
    "write_pin",
]
