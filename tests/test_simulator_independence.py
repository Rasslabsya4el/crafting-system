"""`simulator` is independent of the kernel (ADR-0019, layer 2): it imports none of `abstraction`, `solver`, `risk`.

ADR-0018 would let it import them; the verification layer exists to disagree with them, so it is
written from the documented behaviour of `actions` alone. The scan reads every file under
`simulator/` and reports an import of a forbidden module by any spelling: `import`, `from ... import`,
a relative import, a name taken from the package (`from crafting_system import risk`), an import
inside a function, and a module named in a string (as `importlib.import_module` would take it). It
also checks that nothing outside the standard library and the package is imported. That `prices` and
`targets` are never imported is the layering test's job (`test_layering.py`).
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

import crafting_system

SIMULATOR_DIR = Path(crafting_system.__file__).parent / "simulator"
OWN_PACKAGE = ("crafting_system", "simulator")
FORBIDDEN = {"abstraction", "solver", "risk"}


def forbidden_uses(source: str, own_package: tuple[str, ...], forbidden: set[str] = FORBIDDEN) -> list[str]:
    """One line per use of a forbidden `crafting_system` module in `source`, by any spelling."""
    found = []

    def note(parts: list[str], names: list[str], line: int) -> None:
        if parts[:1] != ["crafting_system"]:
            return
        if len(parts) > 1 and parts[1] in forbidden:
            found.append(f"line {line}: imports {'.'.join(parts)}")
        elif len(parts) == 1:
            found.extend(f"line {line}: imports {name}" for name in names if name in forbidden)

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
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            note(node.value.split("."), [], node.lineno)
    return found


@pytest.mark.parametrize(
    "source",
    [
        "from ..abstraction import compress",
        "from ..solver import solve",
        "from ..risk import evaluate",
        "from ..risk._evaluate import evaluate",
        "from .. import risk",
        "from .. import actions, solver",
        "from crafting_system import abstraction",
        "from crafting_system.solver import Action",
        "from crafting_system.risk.report import Thing",
        "import crafting_system.risk",
        "import crafting_system.abstraction.kernel as kernel",
        "import os, crafting_system.solver",
        "def late():\n    from ..solver import solve\n",
        "import importlib\nimportlib.import_module('crafting_system.solver')",
        "__import__('crafting_system.risk')",
    ],
)
def test_a_use_of_a_kernel_module_is_reported(source):
    assert forbidden_uses(source, OWN_PACKAGE) != []


@pytest.mark.parametrize(
    "source",
    [
        "from ..actions import ChaosOrb",
        "from ..items import Item",
        "from ..data import GameData",
        "from crafting_system.rules import get_rule",
        "from .. import actions, items",
        "from ._estimate import mean",
        "from . import _step",
        "import math, statistics, random",
        "import crafting_system",
        "x = 'the solver is not used here'",
        "x = 'crafting_system.actions'",
        "from crafting_system.simulator import simulate",
    ],
)
def test_other_imports_are_not_reported(source):
    assert forbidden_uses(source, OWN_PACKAGE) == []


def test_no_simulator_file_uses_the_abstraction_solver_or_risk():
    problems = {}
    for path in sorted(SIMULATOR_DIR.rglob("*.py")):
        found = forbidden_uses(path.read_text(encoding="utf-8"), OWN_PACKAGE)
        if found:
            problems[path.name] = found

    assert problems == {}


def test_the_scan_covers_the_simulator_files():
    names = {path.name for path in SIMULATOR_DIR.rglob("*.py")}

    assert {"__init__.py", "_step.py", "_estimate.py", "_report.py", "_simulate.py"} <= names


def test_simulator_uses_only_the_standard_library_and_the_package():
    outside = {}
    for path in sorted(SIMULATOR_DIR.rglob("*.py")):
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


def test_importing_the_simulator_loads_no_kernel_module():
    """Checked in a fresh interpreter, so another test's imports cannot hide a dependency."""
    code = (
        "import sys, crafting_system.simulator\n"
        "loaded = sorted(m for m in sys.modules if m.split('.')[:2] in "
        "(['crafting_system', 'abstraction'], ['crafting_system', 'solver'], ['crafting_system', 'risk']))\n"
        "print(','.join(loaded))"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

    assert result.stdout.strip() == ""
