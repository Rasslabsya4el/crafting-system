"""The solver is generic (ADR-0018): nothing under `solver/` imports the game-specific modules."""

import ast
import sys
from pathlib import Path

import pytest

import crafting_system

SOLVER_DIR = Path(crafting_system.__file__).parent / "solver"
GAME_MODULES = {"data", "rules", "items", "actions", "abstraction"}


def game_modules_imported(source: str, own_package: tuple[str, ...]) -> set[str]:
    """Names among the five game modules that `source` imports, by any spelling."""
    found = set()

    def note(parts: list[str], names: list[str]) -> None:
        if parts[:1] != ["crafting_system"]:
            return
        if len(parts) > 1:
            found.add(parts[1])
        else:
            found.update(names)

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                note(alias.name.split("."), [])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = (node.module or "").split(".")
            else:
                base = list(own_package[: len(own_package) - (node.level - 1)])
                if node.module:
                    base += node.module.split(".")
            note(base, [alias.name for alias in node.names])
    return found & GAME_MODULES


@pytest.mark.parametrize(
    "source",
    [
        "import crafting_system.items",
        "from crafting_system.actions import thing",
        "from crafting_system import rules",
        "from ..data import thing",
        "from .. import abstraction",
        "def late():\n    from ..items.sub import thing\n",
    ],
)
def test_an_import_of_a_game_module_is_reported(source):
    assert game_modules_imported(source, ("crafting_system", "solver")) != set()


@pytest.mark.parametrize(
    "source",
    ["import math", "from . import _model", "from ._graph import Graph", "from ..config import x"],
)
def test_standard_library_and_own_imports_are_not_reported(source):
    assert game_modules_imported(source, ("crafting_system", "solver")) == set()


def test_no_solver_file_imports_a_game_module():
    problems = {}
    for path in sorted(SOLVER_DIR.rglob("*.py")):
        found = game_modules_imported(path.read_text(encoding="utf-8"), ("crafting_system", "solver"))
        if found:
            problems[path.name] = sorted(found)

    assert problems == {}


def test_the_scan_covers_the_solver_files():
    names = {path.name for path in SOLVER_DIR.rglob("*.py")}

    assert {"__init__.py", "_solve.py", "_graph.py"} <= names


def test_the_solver_uses_only_the_standard_library():
    outside = {}
    for path in sorted(SOLVER_DIR.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [(node.module or "").split(".")[0]]
            for name in names:
                if name not in sys.stdlib_module_names and name != "crafting_system":
                    outside.setdefault(path.name, set()).add(name)

    assert outside == {}
