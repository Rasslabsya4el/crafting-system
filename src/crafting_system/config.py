"""Where the data, cache and output directories are (ADR-0014), and the planner setting for Memory Strands (ADR-0040).

Shared infrastructure, outside the eleven modules: it imports none of them.

For each directory the first of these wins: an environment variable, the config file,
the built-in default. The config file is `crafting.toml` at the project root, or the file
named by `CRAFTING_CONFIG` instead. Relative paths in a config file count from that file's
directory; relative paths in environment variables and built-in defaults count from the
project root. Empty environment values count as unset. Nothing here creates a directory.

The setting `memory_strands` (`[planner]` table of the config file, `true` or `false`, default `false`) turns the Memory Strands
of the planner on: the Orb of Remembrance, the Foulborn orbs, the Orb of Unravelling and the tier cut of an item with strands.
A start item with strands turns it on by itself and the command line has `--strands`; neither is read here.

The setting `recipe_starts` (same table, `true` or `false`, default `true`) lets the planner compare the plain start item with
the start items a vendor recipe can make and keep the cheapest total (ADR-0059, ticket #330). With `false`, or `--no-recipe-starts`
for one run, the plan is the one made before recipe starts existed, byte for byte. Ticket #323 will turn every method on or off the
same way; this is its first setting.

The setting `recombinator_junk_craft` (same table, default `false`) offers the recombinator variant that crafts a cheap mod on each
input first (ADR-0035, ticket #216).

The setting `price_source` (same table, `ninja`, `trade` or `both`, default `both`) says which price a bought start item is priced
with: the poe.ninja price, the trade price, or the trade price with poe.ninja as the fallback when the trade price is missing or
stale (ADR-0061 decision 2, ticket #357).

The setting `price_gap_percent` (same table, a number above zero, default 20) is the gap between the trade price and the poe.ninja
price above which the answer flags it; 20 means 20%.
"""

import math
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILE_NAME = "crafting.toml"
CONFIG_ENV_VAR = "CRAFTING_CONFIG"

# config key -> (environment variable, built-in default)
_PATH_SETTINGS = {
    "data": ("CRAFTING_DATA_DIR", "local/data"),
    "cache": ("CRAFTING_CACHE_DIR", "local/cache"),
    "output": ("CRAFTING_OUTPUT_DIR", "local/output"),
}

_PLANNER_SETTINGS = ("memory_strands", "recipe_starts", "recombinator_junk_craft", "price_source", "price_gap_percent")

# values of the `price_source` setting (ADR-0061 decision 2); kept here, not imported from prices/, because this module imports nothing
PRICE_SOURCES = ("ninja", "trade", "both")


@dataclass(frozen=True)
class Config:
    data_dir: Path
    cache_dir: Path
    output_dir: Path
    memory_strands: bool = False
    recipe_starts: bool = True
    recombinator_junk_craft: bool = False
    price_source: str = "both"
    price_gap_percent: float = 20.0


def find_project_root(start: Path | None = None, *, search_up_to: Path | None = None) -> Path:
    """First directory at or above `start` (default: this package) holding `pyproject.toml`.

    The walk stops after `search_up_to` (default: it goes up to the filesystem root); this lets
    a test keep it inside a temporary folder. Without a match (a non-editable install) the
    current directory is the project root.
    """
    here = (start if start is not None else Path(__file__).parent).resolve()
    limit = search_up_to.resolve() if search_up_to is not None else None
    for directory in (here, *here.parents):
        if (directory / "pyproject.toml").is_file():
            return directory
        if directory == limit:
            break
    return Path.cwd()


def load_config(env: Mapping[str, str] | None = None, project_root: Path | None = None) -> Config:
    if env is None:
        env = os.environ
    root = Path(os.path.abspath(project_root if project_root is not None else find_project_root()))

    config_file, file_base = _config_file(env, root)
    from_file, planner = _read_document(config_file) if config_file is not None else ({}, {})

    resolved = {}
    for key, (env_var, default) in _PATH_SETTINGS.items():
        if not _is_blank(env.get(env_var)):
            raw, base = env[env_var], root
        elif key in from_file:
            raw, base = from_file[key], file_base
        else:
            raw, base = default, root
        resolved[key] = _absolute(base, raw)
    return Config(
        data_dir=resolved["data"],
        cache_dir=resolved["cache"],
        output_dir=resolved["output"],
        memory_strands=planner.get("memory_strands", False),
        recipe_starts=planner.get("recipe_starts", True),
        recombinator_junk_craft=planner.get("recombinator_junk_craft", False),
        price_source=planner.get("price_source", "both"),
        price_gap_percent=float(planner.get("price_gap_percent", 20.0)),
    )


def _is_blank(value: str | None) -> bool:
    """Unset, empty or only whitespace."""
    return value is None or not value.strip()


def _absolute(base: Path, raw: str) -> Path:
    """`raw` as an absolute path: a leading `~` is the home folder, a relative path counts from `base`."""
    try:
        path = Path(raw).expanduser()
    except RuntimeError as error:  # no home folder can be found
        raise ValueError(f"cannot expand {raw!r}: {error}") from error
    return Path(os.path.abspath(base / path))


def _config_file(env: Mapping[str, str], root: Path) -> tuple[Path | None, Path]:
    """The config file to read (None if the project has none) and the directory it counts from."""
    named = env.get(CONFIG_ENV_VAR)
    if not _is_blank(named):
        path = _absolute(root, named)
        if not path.is_file():
            raise ValueError(f"{CONFIG_ENV_VAR} names a config file that does not exist: {path}")
        return path, path.parent
    project_file = root / CONFIG_FILE_NAME
    return (project_file if project_file.is_file() else None), root


def _read_document(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    """The `[paths]` and the `[planner]` tables of a config file, each checked."""
    try:
        document = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
    except UnicodeDecodeError as error:
        raise ValueError(f"{path}: not a UTF-8 text file (save it as UTF-8): {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path}: not valid TOML: {error}") from error

    unknown_tables = sorted(set(document) - {"paths", "planner"})
    if unknown_tables:
        raise ValueError(f"{path}: unknown key {unknown_tables[0]!r} (only [paths] and [planner] are allowed)")
    paths = document.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError(f"{path}: 'paths' must be a table")

    for key, value in paths.items():
        if key not in _PATH_SETTINGS:
            raise ValueError(
                f"{path}: unknown key {key!r} in [paths] (known: {', '.join(_PATH_SETTINGS)})"
            )
        if not isinstance(value, str) or _is_blank(value):
            raise ValueError(f"{path}: [paths] {key!r} must be a non-empty string")
    return paths, _read_planner(path, document.get("planner", {}))


def _read_planner(path: Path, planner: object) -> dict[str, object]:
    if not isinstance(planner, dict):
        raise ValueError(f"{path}: 'planner' must be a table")
    for key, value in planner.items():
        if key not in _PLANNER_SETTINGS:
            raise ValueError(
                f"{path}: unknown key {key!r} in [planner] (known: {', '.join(_PLANNER_SETTINGS)})"
            )
        if key == "price_source":
            if type(value) is not str or value not in PRICE_SOURCES:
                raise ValueError(f"{path}: [planner] {key!r}: must be one of ninja, trade, both")
        elif key == "price_gap_percent":
            if not _is_percent(value):
                raise ValueError(
                    f"{path}: [planner] {key!r}: must be a number of percent above zero (20 means 20%)"
                )
        elif type(value) is not bool:
            raise ValueError(f"{path}: [planner] {key!r} must be true or false")
    return planner


def _is_percent(value: object) -> bool:
    """A finite int or float above zero; a bool is not a number here."""
    if type(value) not in (int, float):
        return False
    return math.isfinite(value) and value > 0
