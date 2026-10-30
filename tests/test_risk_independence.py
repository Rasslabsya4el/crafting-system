"""`risk` reaches the solver only through its public names, and uses nothing outside the standard library."""

import ast
import sys
from pathlib import Path

import pytest

import crafting_system

RISK_DIR = Path(crafting_system.__file__).parent / "risk"
OWN_PACKAGE = ("crafting_system", "risk")


def solver_private_imports(source: str, own_package: tuple[str, ...]) -> list[str]:
    """One line per import of a `solver` submodule or `_private` name, by any spelling."""
    found = []

    def note(parts: list[str], names: list[str], line: int) -> None:
        if parts[:2] != ["crafting_system", "solver"]:
            return
        if len(parts) > 2:
            found.append(f"line {line}: imports {'.'.join(parts)}")
        found.extend(f"line {line}: imports {name}" for name in names if name.startswith("_"))

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                note(alias.name.split("."), [], node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = (node.module or "").split(".")
            else:
                base = list(own_package[: len(own_package) - (node.level - 1)])
                if node.module:
                    base += node.module.split(".")
            note(base, [alias.name for alias in node.names], node.lineno)
    return found


@pytest.mark.parametrize(
    "source",
    [
        "from ..solver._model import Action",
        "from ..solver import _model",
        "from crafting_system.solver._solve import solve",
        "import crafting_system.solver._graph",
        "from crafting_system.solver import _certify",
        "def late():\n    from ..solver._scc import strongly_connected_components\n",
    ],
)
def test_a_solver_private_import_is_reported(source):
    assert solver_private_imports(source, OWN_PACKAGE) != []


@pytest.mark.parametrize(
    "source",
    [
        "from ..solver import Action, TabularModel, solve",
        "from crafting_system.solver import Solution",
        "from ._chain import Chain",
        "import math",
        "from .. import solver",
    ],
)
def test_public_solver_imports_are_not_reported(source):
    assert solver_private_imports(source, OWN_PACKAGE) == []


def test_no_risk_file_imports_a_solver_private_module():
    problems = {}
    for path in sorted(RISK_DIR.rglob("*.py")):
        found = solver_private_imports(path.read_text(encoding="utf-8"), OWN_PACKAGE)
        if found:
            problems[path.name] = found

    assert problems == {}


def test_the_scan_covers_the_risk_files():
    names = {path.name for path in RISK_DIR.rglob("*.py")}

    assert {"__init__.py", "_chain.py", "_budget.py", "_evaluate.py"} <= names


def test_risk_uses_only_the_standard_library_and_the_package():
    outside = {}
    for path in sorted(RISK_DIR.rglob("*.py")):
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
