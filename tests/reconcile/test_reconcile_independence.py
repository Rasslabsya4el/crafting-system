"""The reconcile package imports nothing from the planner and runs no code it cannot see (ticket #412, independence).

The scan reads the AST of every `.py` file under `tests/reconcile/`, subfolders included, and fails on:

- any import of the planner, plain or `from`;
- any relative import that leaves `tests/reconcile/` (it is resolved to its real module, so `from .. import x` in
  a top-level file is outside) or does not name a module of the package;
- any import outside the standard library, `yaml` and the package itself (`pytest` too in a test file), except the one shared module
  `independent.ladder` (ticket #419) and the raw export loader `independent.export` (ticket #432), imported as
  `from independent import ladder` or `from independent.ladder import x` (and the same for `export`); any other module of
  `independent` is outside;
- any use of the dynamic ways around an import: the import machinery module, the `__import__` builtin, `exec`, `eval`,
  `spec_from_file_location`, `import_module`, whether imported, called, read as an attribute, or named as a string
  (`getattr(builtins, "exec")`).

The banned names and the planner's name are assembled from pieces here, so this file does not flag itself.
"""

import ast
import sys
from pathlib import Path

import pytest

PACKAGE_NAME = "reconcile"
PACKAGE = Path(__file__).resolve().parent
PLANNER = "crafting_" + "system"
OUTSIDE = "<outside tests/reconcile>"
BANNED = frozenset({"import" + "lib", "__imp" + "ort__", "ex" + "ec", "ev" + "al", "spec_from_" + "file_location", "import_" + "module"})
SHARED_PACKAGE = "independent"
SHARED_MODULES = frozenset({"independent.ladder", "independent.export"})  # the shared modules this package may import
SHARED_NAMES = frozenset({"ladder", "export"})  # the same, as the names `from independent import <name>` takes
ALLOWED_IN_CODE = set(sys.stdlib_module_names) | {"yaml", PACKAGE_NAME}
ALLOWED_IN_TESTS = ALLOWED_IN_CODE | {"pytest"}


def package_of(path: Path, root: Path = PACKAGE) -> tuple[str, ...]:
    """The dotted package a file belongs to, as parts: `("reconcile",)` for a top-level file of the package."""
    return (PACKAGE_NAME, *path.resolve().relative_to(root.resolve()).parent.parts)


def scan_source(source: str, package: tuple[str, ...] = (PACKAGE_NAME,)) -> tuple[set[str], set[tuple[str, ...]], set[str]]:
    """What a source imports and misuses: (top-level names, resolved relative modules, banned names used).

    A relative import is resolved against `package`: the name `OUTSIDE` stands for one that leaves the package
    folder; otherwise the resolved module is returned as parts, for `resolves_inside` to look up.
    """
    roots: set[str] = set()
    relative: set[tuple[str, ...]] = set()
    banned: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names if alias.name not in SHARED_MODULES}
            banned |= {alias.name.split(".")[0] for alias in node.names} & BANNED
        elif isinstance(node, ast.ImportFrom):
            names = {alias.name for alias in node.names}
            banned |= names & BANNED
            if node.level == 0:
                shared_ok = node.module in SHARED_MODULES or (node.module == SHARED_PACKAGE and names <= SHARED_NAMES)
                if not shared_ok:
                    roots.add((node.module or "").split(".")[0])
                banned |= {(node.module or "").split(".")[0]} & BANNED
                continue
            up = node.level - 1
            if up >= len(package):
                roots.add(OUTSIDE)
                continue
            parts = (*package[: len(package) - up], *(node.module.split(".") if node.module else ()))
            roots.add(parts[0])
            relative.add(parts)
        elif isinstance(node, ast.Name) and node.id in BANNED:
            banned.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in BANNED:
            banned.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in BANNED:
            banned.add(node.value)
    return roots, relative, banned


def resolves_inside(parts: tuple[str, ...], root: Path = PACKAGE) -> bool:
    """Whether the relative module `parts` (first part: the package) is a folder or a `.py` file of the package."""
    path = root.joinpath(*parts[1:])
    return path.is_dir() or path.with_suffix(".py").is_file()


def package_files(root: Path = PACKAGE) -> list[Path]:
    return sorted(root.rglob("*.py"))


def test_the_shared_modules_are_where_the_package_expects_them():
    assert (PACKAGE.parent / "independent" / "ladder.py").is_file()
    assert (PACKAGE.parent / "independent" / "export.py").is_file()


@pytest.mark.parametrize(
    "source",
    [
        "from independent import ladder",
        "from independent import ladder as shared",
        "from independent.ladder import ladder_of, item_tags",
        "import independent.ladder",
        "from independent import export",
        "from independent import export as shared_export",
        "from independent import ladder, export",
        "from independent.export import load_export, ExportMissing",
        "import independent.export",
        "import independent.export, independent.ladder",
    ],
)
def test_the_two_shared_modules_are_the_only_imports_from_outside_the_package_that_are_allowed(source):
    assert scan_source(source)[0] <= ALLOWED_IN_CODE


@pytest.mark.parametrize(
    "source",
    [
        "import independent",
        "from independent import other",
        "from independent import ladder, other",
        "from independent import *",
        "from independent.other import x",
        "import independent.other",
        "import independent.other, independent.ladder",
        "import oracle",
        "from oracle import goal_oracle",
    ],
)
def test_any_other_module_of_the_shared_package_or_of_the_oracle_is_outside(source):
    assert not scan_source(source)[0] <= ALLOWED_IN_CODE


def test_the_package_has_code_and_tests_to_scan():
    names = {path.name for path in package_files()}

    assert {"checks.py", "export.py", "files.py", "ladder.py", "known.py"} <= names
    assert any(name.startswith("test_") for name in names)


@pytest.mark.parametrize("path", package_files(), ids=lambda path: path.name)
def test_no_file_imports_the_planner_or_leaves_the_package_or_goes_around_an_import(path):
    roots, relative, banned = scan_source(path.read_text(encoding="utf-8"), package_of(path))
    allowed = ALLOWED_IN_TESTS if path.name.startswith("test_") else ALLOWED_IN_CODE

    assert PLANNER not in roots
    assert OUTSIDE not in roots
    assert roots <= allowed, sorted(roots - allowed)
    assert all(resolves_inside(parts) for parts in relative), sorted(parts for parts in relative if not resolves_inside(parts))
    assert banned == set()


# --- the scanner itself: each hole it must catch ---------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        f"import {PLANNER}",
        f"import {PLANNER}.items.tiers as tiers",
        f"from {PLANNER} import data",
        f"from {PLANNER}.items import tiers",
        f"import json, {PLANNER}",
        f"def late():\n    from {PLANNER}.prices import price_file\n",
    ],
)
def test_the_scan_sees_every_plain_import_of_the_planner(source):
    assert PLANNER in scan_source(source)[0]


@pytest.mark.parametrize(
    "source",
    [
        "from .. import checks",
        "from ..known import KNOWN",
        "from ...anything import value",
        "def late():\n    from .. import x\n",
    ],
)
def test_a_relative_import_that_leaves_the_package_is_outside(source):
    assert OUTSIDE in scan_source(source)[0]


def test_a_relative_import_is_resolved_to_its_real_module_by_the_folder_of_the_file():
    inside = scan_source("from . import checks\nfrom .ladder import ladder\nfrom ..export import Export", ("reconcile", "sub"))

    assert inside[1] == {("reconcile", "sub"), ("reconcile", "sub", "ladder"), ("reconcile", "export")}
    assert OUTSIDE not in inside[0]
    assert OUTSIDE in scan_source("from ... import x", ("reconcile", "sub"))[0]
    assert OUTSIDE not in scan_source("from .. import x", ("reconcile", "sub"))[0]


def test_a_relative_import_must_name_a_module_that_exists_in_the_package(tmp_path):
    (tmp_path / "real.py").write_text("", encoding="utf-8")
    (tmp_path / "folder").mkdir()

    assert resolves_inside(("reconcile", "real"), tmp_path)
    assert resolves_inside(("reconcile", "folder"), tmp_path)
    assert resolves_inside(("reconcile",), tmp_path)
    assert not resolves_inside(("reconcile", "missing"), tmp_path)
    assert not resolves_inside(("reconcile", "folder", "missing"), tmp_path)


@pytest.mark.parametrize(
    ("source", "name"),
    [
        ("import " + "import" + "lib", "import" + "lib"),
        ("from " + "import" + "lib import util", "import" + "lib"),
        ("import " + "import" + "lib.util", "import" + "lib"),
        ("from os import path as p\nfrom x import " + "import_" + "module", "import_" + "module"),
        ("x = " + "__imp" + "ort__" + "('json')", "__imp" + "ort__"),
        ("name = 'json'\n" + "ex" + "ec" + "('import ' + name)", "ex" + "ec"),
        ("v = " + "ev" + "al" + "('1')", "ev" + "al"),
        ("util." + "spec_from_" + "file_location" + "('m', 'p')", "spec_from_" + "file_location"),
        ("m = pkg." + "import_" + "module" + "(name)", "import_" + "module"),
        ("f = getattr(__builtins__, '" + "ex" + "ec" + "')", "ex" + "ec"),
        ("from " + "spec_from_" + "file_location" + " import x", "spec_from_" + "file_location"),
    ],
)
def test_every_way_around_an_import_is_a_banned_use(source, name):
    assert name in scan_source(source)[2]


@pytest.mark.parametrize(
    "source",
    [
        "import json\nfrom pathlib import Path",
        "import re\npattern = re.compile('x')",
        "from . import checks\nfrom .ladder import ladder",
        "import yaml",
        "x = 'crafting_system'",
        "executed = 1\nevaluate = 2\nimportance = 3",
    ],
)
def test_the_scan_does_not_flag_ordinary_code(source):
    roots, relative, banned = scan_source(source)

    assert PLANNER not in roots
    assert OUTSIDE not in roots
    assert banned == set()


def test_the_scan_walks_subfolders_and_reads_their_package_name(tmp_path):
    (tmp_path / "deep" / "deeper").mkdir(parents=True)
    (tmp_path / "top.py").write_text("", encoding="utf-8")
    (tmp_path / "deep" / "mid.py").write_text("", encoding="utf-8")
    (tmp_path / "deep" / "deeper" / "low.py").write_text("", encoding="utf-8")

    found = package_files(tmp_path)

    assert [path.name for path in found] == ["low.py", "mid.py", "top.py"]
    assert package_of(tmp_path / "top.py", tmp_path) == ("reconcile",)
    assert package_of(tmp_path / "deep" / "deeper" / "low.py", tmp_path) == ("reconcile", "deep", "deeper")


def test_a_planner_import_in_a_subfolder_file_is_found_through_the_walk(tmp_path):
    (tmp_path / "deep").mkdir()
    bad = tmp_path / "deep" / "bad.py"
    bad.write_text(f"from {PLANNER} import data\nfrom ...x import y\n", encoding="utf-8")

    roots = set().union(*(scan_source(path.read_text(encoding="utf-8"), package_of(path, tmp_path))[0] for path in package_files(tmp_path)))

    assert PLANNER in roots
    assert OUTSIDE in roots
