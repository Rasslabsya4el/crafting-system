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

The guard follows imports transitively (`walk`): it starts from every file of the package and every code file under `tests/independent/`, and
every name that resolves to a file of `independent` or `oracle` (a `from independent import helper`, a relative import, whatever
`goal_oracle` imports) puts that file in the queue, to be scanned on its own, never trusting another guard. A helper added later is
scanned without anyone listing it. Tests plant an indirect import of the planner in a made-up tree and show the walk refuses it.

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


def dotted_imports(source: str, here: tuple[str, ...]) -> tuple[set[str], list[str]]:
    """Every dotted name a source imports (a `from` adds the module and each name after it), and the relative imports that leave the folder.

    `here` is the folder of the file as a package path, `("independent",)` for `tests/independent/ladder.py`. A relative import is resolved
    against it; one that climbs above the top folder is a problem, not a name.
    """
    names: set[str] = set()
    problems: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            elif node.level - 1 >= len(here):
                problems.append(f"a relative import of {node.level} dots leaves {'.'.join(here)}")
                continue
            else:
                base = ".".join((*here[: len(here) - (node.level - 1)], *((node.module,) if node.module else ())))
            names.add(base)
            names |= {f"{base}.{alias.name}" if base else alias.name for alias in node.names}
    return {name for name in names if name}, problems


def module_file(name: str, tests_root: Path) -> Path | None:
    """The file of a dotted name under `tests_root`: the longest prefix that is a module or a package (`from independent import helper` is `independent/helper.py`)."""
    parts = name.split(".")
    for size in range(len(parts), 0, -1):
        base = tests_root.joinpath(*parts[:size])
        if base.with_suffix(".py").is_file():
            return base.with_suffix(".py")
        if (base / "__init__.py").is_file():
            return base / "__init__.py"
    return None


def walk(entries: list[Path], tests_root: Path = TESTS) -> tuple[set[Path], list[str]]:
    """Follow the imports of `entries` through `independent` and `oracle` to every file they reach, and scan each one on its own.

    Every file reached must import the standard library, `yaml`, `independent` or `oracle` only (the naive crafter's own package only
    from the entries), nothing of the planner, no relative import out of its folder, and use none of the banned ways around an import.
    A name that resolves to a file of a shared package puts that file in the queue, so a helper added later is scanned without anyone
    listing it here. Returns the files reached (the entries included) and the problems, each naming the file.
    """
    reached: set[Path] = set()
    problems: list[str] = []
    queue = [path.resolve() for path in entries]
    entry_set = set(queue)
    while queue:
        path = queue.pop()
        if path in reached:
            continue
        reached.add(path)
        source = path.read_text(encoding="utf-8")
        here = path.parent.resolve().relative_to(tests_root.resolve()).parts
        names, relative_problems = dotted_imports(source, here)
        problems += [f"{path.name}: {problem}" for problem in relative_problems]
        problems += [f"{path.name}: uses {name}" for name in sorted(scan_source(source, (PACKAGE_NAME,))[2])]
        for name in sorted(names):
            top = name.split(".")[0]
            if top == PLANNER:
                problems.append(f"{path.name}: imports the planner ({name})")
            elif top in SHARED:
                target = module_file(name, tests_root)
                if target is None and name == top and (tests_root / top).is_dir():
                    continue  # the bare package name of a `from package import module`: the module is its own name in the list
                if target is None:
                    problems.append(f"{path.name}: {name} is not a file under {tests_root.name}/")
                else:
                    queue.append(target.resolve())
            elif top == PACKAGE_NAME:
                if path not in entry_set:
                    problems.append(f"{path.name}: reaches back into {PACKAGE_NAME} ({name})")
            elif top not in ALLOWED_IN_SHARED and not (path in entry_set and path.name.startswith("test_") and top in ALLOWED_IN_TESTS):
                problems.append(f"{path.name}: imports {top}")
    return reached, problems


def shared_entries(tests_root: Path = TESTS) -> list[Path]:
    """The files the walk starts from: the whole package, and every code file (not a test) under `tests/independent/`."""
    code = [path for path in sorted((tests_root / "independent").rglob("*.py")) if not path.name.startswith("test_")]
    return [*sorted((tests_root / PACKAGE_NAME).rglob("*.py")), *code]


def test_everything_the_player_reaches_is_planner_free_followed_through_every_import():
    reached, problems = walk(shared_entries())
    names = {path.name for path in reached}

    assert problems == []
    assert {"ladder.py", "export.py", "goal_oracle.py", "__init__.py"} <= names
    assert {path.resolve() for path in SHARED_FILES} <= reached


def test_the_walk_starts_from_every_code_file_of_the_independent_folder_and_the_whole_package():
    entries = {path.name for path in shared_entries()}

    assert {"ladder.py", "export.py", "__init__.py", "craft.py", "play.py", "test_naive_independence.py"} <= entries
    assert "test_ladder_unit.py" not in entries


def plant(root: Path, files: dict[str, str]) -> list[Path]:
    """Write a made-up `tests/` tree and give back the entry files (the code under `independent/` and the package's)."""
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return shared_entries(root)


PLAY = "from independent import ladder\n"
INDIRECT = [
    # a helper that a shared file imports by name, which imports the planner
    ({"independent/ladder.py": "from independent import helper\n", "independent/helper.py": f"import {PLANNER}\n", "naive_crafter/play.py": PLAY}, "imports the planner"),
    # the same through a relative import
    ({"independent/ladder.py": "from . import helper\n", "independent/helper.py": f"from {PLANNER}.items import tiers\n", "naive_crafter/play.py": PLAY}, "imports the planner"),
    # two steps away, through the oracle, whose helper is a third-party package
    (
        {
            "oracle/goal_oracle.py": "from independent import deeper\n",
            "independent/deeper.py": "import numpy\n",
            "independent/ladder.py": "",
            "naive_crafter/play.py": "from oracle import goal_oracle\n",
        },
        "imports numpy",
    ),
    # a relative import that climbs out of the folder
    ({"independent/ladder.py": "from .. import oracle\n", "naive_crafter/play.py": PLAY}, "leaves independent"),
    # a way around an import in a file reached only through another
    (
        {"independent/ladder.py": "from independent import helper\n", "independent/helper.py": "name = 'x'\n" + "ex" + "ec" + "('import ' + name)\n", "naive_crafter/play.py": PLAY},
        "uses " + "ex" + "ec",
    ),
    # a code file of independent/ that nothing imports yet is still scanned
    ({"independent/ladder.py": "", "independent/unused.py": f"import {PLANNER}\n", "naive_crafter/play.py": PLAY}, "imports the planner"),
]


@pytest.mark.parametrize(("files", "wanted"), INDIRECT, ids=[wanted for _, wanted in INDIRECT])
def test_the_walk_refuses_an_indirect_import_of_the_planner_or_of_anything_outside(tmp_path, files, wanted):
    entries = plant(tmp_path, files)
    _, problems = walk(entries, tmp_path)

    assert any(wanted in problem for problem in problems), problems


def test_the_walk_passes_a_clean_chain_and_follows_it_to_the_end(tmp_path):
    entries = plant(
        tmp_path,
        {
            "independent/__init__.py": "",
            "independent/ladder.py": "import json\nfrom independent import helper\n",
            "independent/helper.py": "import yaml\nfrom . import leaf\n",
            "independent/leaf.py": "import re\n",
            "oracle/goal_oracle.py": "from independent import ladder\n",
            "naive_crafter/play.py": "from oracle import goal_oracle\n",
        },
    )
    reached, problems = walk(entries, tmp_path)

    assert problems == []
    assert {path.name for path in reached} >= {"leaf.py", "helper.py", "goal_oracle.py"}


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
