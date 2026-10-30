"""The built-in default directories are git-ignored (ADR-0014), and nothing else by accident."""

import subprocess
from pathlib import Path

import pytest

from crafting_system.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def is_ignored(path: str) -> bool:
    """Whether git ignores `path` (relative to the repo root), whether or not it exists."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", path],
            cwd=REPO_ROOT,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError:
        pytest.fail("git is not installed or not on PATH; this test needs `git check-ignore`")
    if result.returncode not in (0, 1):
        pytest.fail(f"`git check-ignore` failed: {result.stderr.strip()}")
    return result.returncode == 0


@pytest.mark.parametrize("field", ["data_dir", "cache_dir", "output_dir"])
def test_each_built_in_default_directory_is_git_ignored(field):
    default = getattr(load_config(env={}, project_root=REPO_ROOT), field)

    relative = default.relative_to(REPO_ROOT).as_posix()

    assert is_ignored(relative + "/some-file.json")


@pytest.mark.parametrize("folder", ["local", "dist", "build"])
def test_root_only_ignores_do_not_hide_package_folders_of_the_same_name(folder):
    assert is_ignored(folder + "/x.py")
    assert not is_ignored("src/crafting_system/" + folder + "/x.py")


@pytest.mark.parametrize("path", [".venv/pyvenv.cfg", "src/crafting_system/__pycache__/x.pyc"])
def test_virtualenv_and_bytecode_are_ignored(path):
    assert is_ignored(path)
