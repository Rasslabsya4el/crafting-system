"""The shared folder imports nothing of the planner and nothing of the packages that use it (ticket #419, independence).

`tests/independent/` holds the code that `tests/oracle/` and `tests/reconcile/` share. The scan reads the AST of every `.py`
file in this folder and fails on:

- any import of the planner, plain or `from`;
- any import outside the standard library, `yaml` and this folder by its package name `independent` (`pytest` too in a test file),
  so the shared code cannot reach back into `oracle` or `reconcile`, and neither can it use a third-party package;
- any relative import that leaves the folder or does not name a module in it;
- the dynamic ways around an import: the import machinery module, the `__import__` builtin, `exec`, `eval`,
  `spec_from_file_location`, `import_module`, whether imported, called, read as an attribute, or named as a string.

Two sibling guards allow exactly the modules `ladder.py` and `export.py` (the raw export loader, ticket #432) of this folder
and no other: `tests/test_goal_oracle.py` for the oracle, `tests/reconcile/test_reconcile_independence.py` for the reconciliation. The banned names are assembled from pieces here, so this
file does not flag itself.
"""

import ast
import sys
from pathlib import Path

import pytest

FOLDER = Path(__file__).resolve().parent
PLANNER = "crafting_" + "system"
OUTSIDE = "<outside tests/independent>"
BANNED = frozenset({"import" + "lib", "__imp" + "ort__", "ex" + "ec", "ev" + "al", "spec_from_" + "file_location", "import_" + "module"})
ALLOWED_IN_CODE = set(sys.stdlib_module_names) | {"yaml", "independent"}  # `independent` is this folder, imported by its package name
ALLOWED_IN_TESTS = ALLOWED_IN_CODE | {"pytest"}


def scan_source(source: str) -> tuple[set[str], set[str], set[str]]:
    """What a source imports and misuses: (top-level names, relative modules, banned names used).

    A relative import of two dots or more leaves the folder: the name `OUTSIDE` stands for it. One dot names a module
    of the folder (`from . import ladder` names `ladder`, `from .ladder import x` names `ladder`).
    """
    roots: set[str] = set()
    relative: set[str] = set()
    banned: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
            banned |= {alias.name.split(".")[0] for alias in node.names} & BANNED
        elif isinstance(node, ast.ImportFrom):
            names = {alias.name for alias in node.names}
            banned |= names & BANNED
            if node.level == 0:
                roots.add((node.module or "").split(".")[0])
                banned |= {(node.module or "").split(".")[0]} & BANNED
            elif node.level > 1:
                roots.add(OUTSIDE)
            elif node.module:
                relative.add(node.module.split(".")[0])
            else:
                relative |= names
        elif isinstance(node, ast.Name) and node.id in BANNED:
            banned.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in BANNED:
            banned.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in BANNED:
            banned.add(node.value)
    return roots, relative, banned


def folder_files(root: Path = FOLDER) -> list[Path]:
    return sorted(root.rglob("*.py"))


def test_the_folder_holds_the_shared_ladder_the_shared_export_loader_and_this_guard():
    names = {path.name for path in folder_files()}

    assert {"__init__.py", "ladder.py", "export.py", "test_independent_guard.py"} <= names


@pytest.mark.parametrize("path", folder_files(), ids=lambda path: path.name)
def test_no_file_imports_the_planner_or_a_user_of_the_folder_or_goes_around_an_import(path):
    roots, relative, banned = scan_source(path.read_text(encoding="utf-8"))
    allowed = ALLOWED_IN_TESTS if path.name.startswith("test_") else ALLOWED_IN_CODE

    assert PLANNER not in roots
    assert OUTSIDE not in roots
    assert roots <= allowed, sorted(roots - allowed)
    assert all((FOLDER / f"{name}.py").is_file() for name in relative), sorted(relative)
    assert banned == set()


@pytest.mark.parametrize("name", ["ladder.py", "export.py"])
def test_the_shared_modules_use_the_standard_library_only(name):
    roots, _, _ = scan_source((FOLDER / name).read_text(encoding="utf-8"))

    assert roots <= set(sys.stdlib_module_names)


# --- the scanner itself: each hole it must catch ---------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        f"import {PLANNER}",
        f"from {PLANNER}.items import tiers",
        f"import json, {PLANNER}",
        f"def late():\n    from {PLANNER}.prices import price_file\n",
        "import reconcile",
        "from oracle import goal_oracle",
        "from reconcile.ladder import ladder",
        "import numpy",
    ],
)
def test_an_import_of_the_planner_or_of_a_user_of_the_folder_is_not_allowed(source):
    assert not scan_source(source)[0] <= ALLOWED_IN_CODE


@pytest.mark.parametrize("source", ["from .. import checks", "from ..known import KNOWN", "from ...x import y", "def late():\n    from .. import x\n"])
def test_a_relative_import_that_leaves_the_folder_is_outside(source):
    assert OUTSIDE in scan_source(source)[0]


def test_a_sibling_import_is_read_as_the_module_it_names():
    assert scan_source("from . import ladder")[1] == {"ladder"}
    assert scan_source("from .ladder import ladder_of")[1] == {"ladder"}
    assert scan_source("from .no_such import x")[1] == {"no_such"}


@pytest.mark.parametrize(
    ("source", "name"),
    [
        ("import " + "import" + "lib", "import" + "lib"),
        ("from " + "import" + "lib import util", "import" + "lib"),
        ("from os import path as p\nfrom x import " + "import_" + "module", "import_" + "module"),
        ("x = " + "__imp" + "ort__" + "('json')", "__imp" + "ort__"),
        ("name = 'json'\n" + "ex" + "ec" + "('import ' + name)", "ex" + "ec"),
        ("v = " + "ev" + "al" + "('1')", "ev" + "al"),
        ("util." + "spec_from_" + "file_location" + "('m', 'p')", "spec_from_" + "file_location"),
        ("m = pkg." + "import_" + "module" + "(name)", "import_" + "module"),
        ("f = getattr(__builtins__, '" + "ex" + "ec" + "')", "ex" + "ec"),
    ],
)
def test_every_way_around_an_import_is_a_banned_use(source, name):
    assert name in scan_source(source)[2]


@pytest.mark.parametrize(
    "source",
    ["import json\nfrom pathlib import Path", "import re", "import yaml", "from . import ladder", "x = 'crafting_system'", "executed = 1\nevaluate = 2"],
)
def test_the_scan_does_not_flag_ordinary_code(source):
    roots, relative, banned = scan_source(source)

    assert PLANNER not in roots
    assert OUTSIDE not in roots
    assert banned == set()
