"""Layering guard (ADR-0018): each of the eleven modules may import only modules listed before it."""

import ast
from pathlib import Path

import pytest

import crafting_system

LAYERS = (
    "data",
    "rules",
    "items",
    "actions",
    "abstraction",
    "solver",
    "risk",
    "simulator",
    "prices",
    "targets",
    "cli",
)


def imported_layers(tree: ast.AST, own_package: list[str], package_name: str) -> set[str]:
    """Names of the top-level folders of `package_name` that a parsed module imports.

    `own_package` is the dotted package the module sits in, as a list (for `pkg/a/b.py`
    it is `["pkg", "a"]`), which is what relative imports count from.
    """
    found: set[str] = set()

    def note(parts: list[str], names: list[str]) -> None:
        if parts[:1] != [package_name]:
            return
        if len(parts) > 1:
            found.add(parts[1])
        else:
            found.update(names)  # `from pkg import layer`

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                note(alias.name.split("."), [])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = (node.module or "").split(".")
            else:
                base = own_package[: len(own_package) - (node.level - 1)]
                if node.module:
                    base = base + node.module.split(".")
            note(base, [alias.name for alias in node.names])
    return found


def find_layer_violations(package_dir: Path, layers: tuple[str, ...]) -> list[str]:
    """One line per file that imports a module listed after its own."""
    package_name = package_dir.name
    violations = []
    for own_index, own_layer in enumerate(layers):
        for path in sorted((package_dir / own_layer).rglob("*.py")):
            relative = path.relative_to(package_dir)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            own_package = [package_name, *relative.parts[:-1]]
            for imported in sorted(imported_layers(tree, own_package, package_name)):
                if imported in layers and layers.index(imported) > own_index:
                    violations.append(f"{relative.as_posix()}: {own_layer} imports later {imported}")
    return violations


def make_package(root: Path, files: dict[str, str], layers: tuple[str, ...]) -> Path:
    """Build a synthetic package `pkg` with one empty folder per layer plus the given files."""
    package_dir = root / "pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("")
    for layer in layers:
        (package_dir / layer).mkdir()
        (package_dir / layer / "__init__.py").write_text("")
    for relative, source in files.items():
        target = package_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
    return package_dir


SYNTHETIC_LAYERS = ("first", "second", "third")


@pytest.mark.parametrize(
    "source",
    [
        "import pkg.third",
        "import pkg.third.deep as deep",
        "from pkg.third import thing",
        "from pkg.third.deep import thing",
        "from pkg import third",
        "from ..third import thing",
        "from ..third.deep import thing",
        "from .. import third",
        "def late():\n    from pkg.third import thing\n",
    ],
)
def test_import_of_a_later_module_is_reported(tmp_path, source):
    package_dir = make_package(tmp_path, {"first/mod.py": source}, SYNTHETIC_LAYERS)

    violations = find_layer_violations(package_dir, SYNTHETIC_LAYERS)

    assert len(violations) == 1
    assert "first" in violations[0] and "third" in violations[0]


def test_import_from_a_nested_file_is_reported(tmp_path):
    package_dir = make_package(
        tmp_path, {"second/sub/deep.py": "from ...third import thing"}, SYNTHETIC_LAYERS
    )

    violations = find_layer_violations(package_dir, SYNTHETIC_LAYERS)

    assert len(violations) == 1
    assert "second" in violations[0] and "third" in violations[0]


def test_import_in_an_init_file_is_reported(tmp_path):
    package_dir = make_package(
        tmp_path, {"first/__init__.py": "from .. import second"}, SYNTHETIC_LAYERS
    )

    assert len(find_layer_violations(package_dir, SYNTHETIC_LAYERS)) == 1


@pytest.mark.parametrize(
    "source",
    [
        "import pkg.first",
        "from pkg.first import thing",
        "from pkg import first",
        "from ..first import thing",
        "from .. import first",
        "from . import sibling",
        "from .sibling import thing",
        "import pkg.second.inner",
        "from pkg import config",
        "from .. import config",
        "import os\nfrom collections import OrderedDict",
        "import pkg",
    ],
)
def test_allowed_imports_are_not_reported(tmp_path, source):
    package_dir = make_package(tmp_path, {"second/mod.py": source}, SYNTHETIC_LAYERS)

    assert find_layer_violations(package_dir, SYNTHETIC_LAYERS) == []


def test_files_outside_the_layers_may_import_any_layer(tmp_path):
    package_dir = make_package(
        tmp_path, {"shared.py": "from pkg.third import thing"}, SYNTHETIC_LAYERS
    )

    assert find_layer_violations(package_dir, SYNTHETIC_LAYERS) == []


def test_every_module_folder_exists_in_the_real_package():
    package_dir = Path(crafting_system.__file__).parent

    missing = [layer for layer in LAYERS if not (package_dir / layer / "__init__.py").is_file()]

    assert missing == []


def test_real_package_imports_only_earlier_modules():
    package_dir = Path(crafting_system.__file__).parent

    assert find_layer_violations(package_dir, LAYERS) == []
