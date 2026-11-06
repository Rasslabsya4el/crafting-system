"""The reconcile package imports nothing from the planner (ticket #412, the principle of independence).

The scan reads the AST of every `.py` file of `tests/reconcile/` and fails on any import of `crafting_system`, plain,
`from`, or through `__import__` / `importlib.import_module` with a literal name. The package code (not the tests) may use the
standard library and `yaml` only. The planner's name is assembled from pieces in the samples below, so the scan does not
flag this file for them.
"""

import ast
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent
PLANNER = "crafting_" + "system"
ALLOWED_IN_CODE = set(sys.stdlib_module_names) | {"yaml"}
ALLOWED_IN_TESTS = ALLOWED_IN_CODE | {"pytest"}
DYNAMIC = {"__import__", "import_module"}


def imported_roots(source: str) -> set[str]:
    """The top-level names this source imports, absolute imports only (a relative import stays inside the package).

    A call of `__import__` or `import_module` with a literal name counts as an import of that name.
    """
    roots = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            function = node.func
            name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", None)
            if name in DYNAMIC and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                roots.add(node.args[0].value.split(".")[0])
    return roots


def package_files() -> list[Path]:
    return sorted(PACKAGE.glob("*.py"))


def test_the_package_has_code_and_tests_to_scan():
    names = {path.name for path in package_files()}

    assert {"checks.py", "export.py", "files.py", "ladder.py", "known.py"} <= names
    assert any(name.startswith("test_") for name in names)


@pytest.mark.parametrize("path", package_files(), ids=lambda path: path.name)
def test_no_file_imports_the_planner(path):
    assert PLANNER not in imported_roots(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", package_files(), ids=lambda path: path.name)
def test_the_package_uses_the_standard_library_and_yaml_only(path):
    allowed = ALLOWED_IN_TESTS if path.name.startswith("test_") else ALLOWED_IN_CODE

    assert imported_roots(path.read_text(encoding="utf-8")) <= allowed


@pytest.mark.parametrize(
    "source",
    [
        f"import {PLANNER}",
        f"import {PLANNER}.items.tiers as tiers",
        f"from {PLANNER} import data",
        f"from {PLANNER}.items import tiers",
        f"import json, {PLANNER}",
        f"def late():\n    from {PLANNER}.prices import price_file\n",
        f"importlib.import_module('{PLANNER}.items')",
        f"__import__('{PLANNER}')",
    ],
)
def test_the_scan_sees_every_way_to_import_the_planner(source):
    assert PLANNER in imported_roots(source)


@pytest.mark.parametrize(
    "source",
    ["import json\nfrom pathlib import Path", "from . import checks", "from .ladder import ladder", "import yaml", "x = 'crafting_system'"],
)
def test_the_scan_does_not_flag_other_code_or_a_relative_import(source):
    assert PLANNER not in imported_roots(source)
