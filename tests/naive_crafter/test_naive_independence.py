"""The naive crafter imports nothing of the planner and runs no code it cannot see (ticket #555, independence).

The scan reads the AST of every `.py` file under `tests/naive_crafter/` and fails on:

- any import of the planner, plain or `from`;
- any relative import that leaves the folder or does not name a module of it;
- any import outside the standard library, `yaml` and the package itself (`pytest` too in a test file), except the three modules the other
  independent checks share: `independent.ladder` and `independent.export` (tickets #419, #432) and the goal oracle `oracle.goal_oracle`
  (ticket #411), imported as `from independent import ladder`, `from oracle import goal_oracle as g`, `from oracle.goal_oracle import x`
  and so on; any other module of `independent` or `oracle` is outside;
- the dynamic ways around an import: the import machinery module, the `__import__` builtin, `exec`, `eval`, `spec_from_file_location`,
  `import_module`, whether imported, called, read as an attribute, or named as a string.

The three shared modules are scanned too, with the rule they have for themselves (standard library, `yaml` and `independent`), so what the
naive crafter reaches through them is planner-free as well: the guard does not trust their own guards to be run.

The banned names and the planner's name are assembled from pieces here, so this file does not flag itself.
"""

import ast
import sys
from pathlib import Path

import pytest

PACKAGE_NAME = "naive_crafter"
PACKAGE = Path(__file__).resolve().parent
TESTS = PACKAGE.parent
PLANNER = "crafting_" + "system"
OUTSIDE = "<outside tests/naive_crafter>"
BANNED = frozenset({"import" + "lib", "__imp" + "ort__", "ex" + "ec", "ev" + "al", "spec_from_" + "file_location", "import_" + "module"})
SHARED = {"independent": frozenset({"ladder", "export"}), "oracle": frozenset({"goal_oracle"})}  # package -> the modules of it this one may import
SHARED_FILES = (TESTS / "independent" / "ladder.py", TESTS / "independent" / "export.py", TESTS / "oracle" / "goal_oracle.py")
ALLOWED_IN_CODE = set(sys.stdlib_module_names) | {"yaml", PACKAGE_NAME}
ALLOWED_IN_TESTS = ALLOWED_IN_CODE | {"pytest"}
ALLOWED_IN_SHARED = set(sys.stdlib_module_names) | {"yaml", "independent"}


def package_of(path: Path, root: Path = PACKAGE) -> tuple[str, ...]:
    return (PACKAGE_NAME, *path.resolve().relative_to(root.resolve()).parent.parts)


def scan_source(source: str, package: tuple[str, ...] = (PACKAGE_NAME,)) -> tuple[set[str], set[tuple[str, ...]], set[str]]:
    """What a source imports and misuses: (top-level names, resolved relative modules, banned names used).

    A shared module imported as allowed adds no top-level name; anything else of `independent` or `oracle` does. A relative import is
    resolved against `package`: `OUTSIDE` stands for one that leaves the folder.
    """
    roots: set[str] = set()
    relative: set[tuple[str, ...]] = set()
    banned: set[str] = set()

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top, _, rest = alias.name.partition(".")
                if not (top in SHARED and rest in SHARED[top]):
                    roots.add(top)
                banned |= {top} & BANNED
        elif isinstance(node, ast.ImportFrom):
            names = {alias.name for alias in node.names}
            banned |= names & BANNED
            if node.level == 0:
                module = node.module or ""
                top, _, rest = module.partition(".")
                if not (top in SHARED and ((rest in SHARED[top]) if rest else names <= SHARED[top])):
                    roots.add(top)
                banned |= {top} & BANNED
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
    path = root.joinpath(*parts[1:])
    return path.is_dir() or path.with_suffix(".py").is_file()


def package_files(root: Path = PACKAGE) -> list[Path]:
    return sorted(root.rglob("*.py"))


def test_the_package_has_code_and_tests_to_scan_and_the_shared_modules_are_there():
    names = {path.name for path in package_files()}

    assert {"craft.py", "play.py", "world.py", "tally.py", "rules.py", "frequencies.py"} <= names
    assert any(name.startswith("test_") for name in names)
    assert all(path.is_file() for path in SHARED_FILES)


@pytest.mark.parametrize("path", package_files(), ids=lambda path: path.name)
def test_no_file_imports_the_planner_or_leaves_the_package_or_goes_around_an_import(path):
    roots, relative, banned = scan_source(path.read_text(encoding="utf-8"), package_of(path))
    allowed = ALLOWED_IN_TESTS if path.name.startswith("test_") else ALLOWED_IN_CODE

    assert PLANNER not in roots
    assert OUTSIDE not in roots
    assert roots <= allowed, sorted(roots - allowed)
    assert all(resolves_inside(parts) for parts in relative), sorted(parts for parts in relative if not resolves_inside(parts))
    assert banned == set()


@pytest.mark.parametrize("path", SHARED_FILES, ids=lambda path: path.name)
def test_the_shared_modules_it_reaches_are_planner_free_too(path):
    roots, _, banned = scan_source(path.read_text(encoding="utf-8"), ("independent",))

    assert PLANNER not in roots
    assert roots <= ALLOWED_IN_SHARED, sorted(roots - ALLOWED_IN_SHARED)
    assert banned == set()


# --- the scanner itself: each hole it must catch ---------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "from independent import ladder",
        "from independent import ladder as shared",
        "from independent.ladder import item_tags, spawn_weight",
        "import independent.ladder",
        "from independent import export",
        "from independent.export import load_export, ExportMissing",
        "import independent.export, independent.ladder",
        "from oracle import goal_oracle",
        "from oracle import goal_oracle as g",
        "from oracle.goal_oracle import Oracle, OMod",
        "import oracle.goal_oracle",
    ],
)
def test_the_three_shared_modules_are_the_only_imports_from_outside_the_package_that_are_allowed(source):
    assert scan_source(source)[0] <= ALLOWED_IN_CODE


@pytest.mark.parametrize(
    "source",
    [
        "import independent",
        "from independent import other",
        "from independent import ladder, other",
        "from independent.other import x",
        "import independent.other",
        "import oracle",
        "from oracle import page_lint",
        "from oracle import goal_oracle, page_lint",
        "from oracle.page_lint import x",
        "import reconcile",
        "from reconcile.ladder import ladder",
        "import numpy",
    ],
)
def test_any_other_module_of_the_shared_packages_or_outside_is_not_allowed(source):
    assert not scan_source(source)[0] <= ALLOWED_IN_CODE


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


@pytest.mark.parametrize("source", ["from .. import craft", "from ..play import Player", "from ...anything import value", "def late():\n    from .. import x\n"])
def test_a_relative_import_that_leaves_the_package_is_outside(source):
    assert OUTSIDE in scan_source(source)[0]


def test_a_relative_import_is_resolved_to_its_real_module_and_must_name_one_that_exists(tmp_path):
    inside = scan_source("from . import craft\nfrom .play import Player", (PACKAGE_NAME,))
    (tmp_path / "real.py").write_text("", encoding="utf-8")

    assert inside[1] == {(PACKAGE_NAME,), (PACKAGE_NAME, "play")}
    assert resolves_inside((PACKAGE_NAME, "real"), tmp_path)
    assert not resolves_inside((PACKAGE_NAME, "missing"), tmp_path)


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
    ["import json\nfrom pathlib import Path", "import re\npattern = re.compile('x')", "from . import craft", "import yaml", "x = 'crafting_system'", "executed = 1\nevaluate = 2\nimportance = 3"],
)
def test_the_scan_does_not_flag_ordinary_code(source):
    roots, _, banned = scan_source(source)

    assert PLANNER not in roots
    assert OUTSIDE not in roots
    assert banned == set()
