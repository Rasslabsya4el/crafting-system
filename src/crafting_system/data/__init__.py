"""Fetch, pin and normalize repoe-fork; knows nothing of crafting. Imports no other module of the package."""

from .candidate import candidate_pin, pin_lines
from .diff import PatchDiff, compare_game_data, diff_game_data, render_diff
from .errors import DataError, FetchError, HashMismatchError, MissingDataError, RawFormatError
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
from .pin import PIN, PinnedFile, RepoePin

__all__ = [
    "PIN",
    "BaseItem",
    "BenchActions",
    "BenchOption",
    "ClaimReference",
    "CostEntry",
    "DataChanges",
    "DataError",
    "Essence",
    "EssenceMod",
    "FetchError",
    "FetchResult",
    "Fossil",
    "GameData",
    "HashMismatchError",
    "Impact",
    "MissingDataError",
    "Mod",
    "PatchDiff",
    "PinnedFile",
    "RawFormatError",
    "Reference",
    "ReferencingTestFile",
    "RepoePin",
    "StatRange",
    "Weight",
    "cache_folder",
    "candidate_pin",
    "compare_game_data",
    "compute_impact",
    "conflicts",
    "diff_game_data",
    "find_repo_root",
    "load_game_data",
    "normalize_game_data",
    "pin_lines",
    "render_diff",
    "render_impact",
    "verify_cache",
]
