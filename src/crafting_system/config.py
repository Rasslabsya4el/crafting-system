"""Where the data, cache and output directories are (ADR-0014).

Shared infrastructure, outside the eleven modules: it imports none of them.

For each directory the first of these wins: an environment variable, the config file,
the built-in default. The config file is `crafting.toml` at the project root, or the file
named by `CRAFTING_CONFIG` instead. Relative paths in a config file count from that file's
directory; relative paths in environment variables and built-in defaults count from the
project root. Empty environment values count as unset. Nothing here creates a directory.
"""

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


@dataclass(frozen=True)
class Config:
    data_dir: Path
    cache_dir: Path
    output_dir: Path


def find_project_root(start: Path | None = None) -> Path:
    """First directory at or above `start` (default: this package) holding `pyproject.toml`.

    Without one (a non-editable install) the current directory is the project root.
    """
    here = (start if start is not None else Path(__file__).parent).resolve()
    for directory in (here, *here.parents):
        if (directory / "pyproject.toml").is_file():
            return directory
    return Path.cwd()


def load_config(env: Mapping[str, str] | None = None, project_root: Path | None = None) -> Config:
    if env is None:
        env = os.environ
    root = Path(os.path.abspath(project_root if project_root is not None else find_project_root()))

    config_file, file_base = _config_file(env, root)
    from_file = _read_paths(config_file) if config_file is not None else {}

    resolved = {}
    for key, (env_var, default) in _PATH_SETTINGS.items():
        if env.get(env_var):
            raw, base = env[env_var], root
        elif key in from_file:
            raw, base = from_file[key], file_base
        else:
            raw, base = default, root
        resolved[key] = Path(os.path.abspath(base / raw))
    return Config(data_dir=resolved["data"], cache_dir=resolved["cache"], output_dir=resolved["output"])


def _config_file(env: Mapping[str, str], root: Path) -> tuple[Path | None, Path]:
    """The config file to read (None if the project has none) and the directory it counts from."""
    named = env.get(CONFIG_ENV_VAR)
    if named:
        path = Path(os.path.abspath(root / named))
        if not path.is_file():
            raise ValueError(f"{CONFIG_ENV_VAR} names a config file that does not exist: {path}")
        return path, path.parent
    project_file = root / CONFIG_FILE_NAME
    return (project_file if project_file.is_file() else None), root


def _read_paths(path: Path) -> dict[str, str]:
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path}: not valid TOML: {error}") from error

    unknown_tables = sorted(set(document) - {"paths"})
    if unknown_tables:
        raise ValueError(f"{path}: unknown key {unknown_tables[0]!r} (only [paths] is allowed)")
    paths = document.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError(f"{path}: 'paths' must be a table")

    for key, value in paths.items():
        if key not in _PATH_SETTINGS:
            raise ValueError(
                f"{path}: unknown key {key!r} in [paths] (known: {', '.join(_PATH_SETTINGS)})"
            )
        if not isinstance(value, str) or not value:
            raise ValueError(f"{path}: [paths] {key!r} must be a non-empty string")
    return paths
