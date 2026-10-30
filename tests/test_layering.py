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


def layers_imported_by(path: Path, package_dir: Path, layers: tuple[str, ...]) -> list[str]:
    relative = path.relative_to(package_dir)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    own_package = [package_dir.name, *relative.parts[:-1]]
    return sorted(imported_layers(tree, own_package, package_dir.name) & set(layers))


def find_layer_violations(package_dir: Path, layers: tuple[str, ...]) -> list[str]:
    """One line per file that imports a module listed after its own.

    A top-level module outside the layers (like `config.py`) is shared infrastructure and may
    import none of them: otherwise a layer could reach a later one through it.
    """
    violations = []
    for own_index, own_layer in enumerate(layers):
        for path in sorted((package_dir / own_layer).rglob("*.py")):
            for imported in layers_imported_by(path, package_dir, layers):
                if layers.index(imported) > own_index:
                    relative = path.relative_to(package_dir).as_posix()
                    violations.append(f"{relative}: {own_layer} imports later {imported}")
    for path in sorted(package_dir.glob("*.py")):
        for imported in layers_imported_by(path, package_dir, layers):
            violations.append(f"{path.name}: sits outside the layers but imports {imported}")
    return violations


def find_unexpected_subpackages(package_dir: Path, layers: tuple[str, ...]) -> list[str]:
    """Folders holding Python files that are not one of the layers (bytecode leftovers do not count)."""
    return sorted(
        folder.name
        for folder in package_dir.iterdir()
        if folder.is_dir() and folder.name not in layers and any(folder.rglob("*.py"))
    )


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


@pytest.mark.parametrize(
    "source",
    [
        "import pkg.first",
        "from pkg.first import thing",
        "from pkg import second",
        "from .third import thing",
        "from . import first",
        "from .first.deep import thing",
        "def late():\n    from pkg.second import thing\n",
    ],
)
def test_a_top_level_module_outside_the_layers_may_import_none_of_them(tmp_path, source):
    package_dir = make_package(tmp_path, {"shared.py": source}, SYNTHETIC_LAYERS)

    violations = find_layer_violations(package_dir, SYNTHETIC_LAYERS)

    assert len(violations) == 1
    assert violations[0].startswith("shared.py")


def test_the_package_init_counts_as_outside_the_layers(tmp_path):
    package_dir = make_package(tmp_path, {"__init__.py": "from . import first"}, SYNTHETIC_LAYERS)

    assert len(find_layer_violations(package_dir, SYNTHETIC_LAYERS)) == 1


def test_a_layer_cannot_reach_a_later_layer_through_a_shared_module(tmp_path):
    package_dir = make_package(
        tmp_path,
        {"first/mod.py": "from .. import shared", "shared.py": "from .third import thing"},
        SYNTHETIC_LAYERS,
    )

    violations = find_layer_violations(package_dir, SYNTHETIC_LAYERS)

    assert len(violations) == 1
    assert violations[0].startswith("shared.py")


def test_top_level_modules_may_import_each_other_and_the_standard_library(tmp_path):
    package_dir = make_package(
        tmp_path,
        {
            "shared.py": "import os\nfrom . import config\nimport pkg.config",
            "config.py": "import tomllib",
        },
        SYNTHETIC_LAYERS,
    )

    assert find_layer_violations(package_dir, SYNTHETIC_LAYERS) == []


def test_a_layer_may_import_a_top_level_module(tmp_path):
    package_dir = make_package(
        tmp_path,
        {"first/mod.py": "from ..config import load_config\nfrom .. import config", "config.py": ""},
        SYNTHETIC_LAYERS,
    )

    assert find_layer_violations(package_dir, SYNTHETIC_LAYERS) == []


def test_an_extra_subpackage_is_reported(tmp_path):
    package_dir = make_package(tmp_path, {"fourth/__init__.py": ""}, SYNTHETIC_LAYERS)

    assert find_unexpected_subpackages(package_dir, SYNTHETIC_LAYERS) == ["fourth"]


def test_an_extra_folder_with_python_files_but_no_init_is_reported(tmp_path):
    package_dir = make_package(tmp_path, {"fourth/mod.py": ""}, SYNTHETIC_LAYERS)

    assert find_unexpected_subpackages(package_dir, SYNTHETIC_LAYERS) == ["fourth"]


def test_leftover_bytecode_folders_are_not_subpackages(tmp_path):
    package_dir = make_package(tmp_path, {}, SYNTHETIC_LAYERS)
    (package_dir / "__pycache__").mkdir()
    (package_dir / "old" / "__pycache__").mkdir(parents=True)
    (package_dir / "old" / "__pycache__" / "x.pyc").write_bytes(b"")

    assert find_unexpected_subpackages(package_dir, SYNTHETIC_LAYERS) == []


def test_exactly_the_given_subpackages_pass(tmp_path):
    package_dir = make_package(tmp_path, {}, SYNTHETIC_LAYERS)

    assert find_unexpected_subpackages(package_dir, SYNTHETIC_LAYERS) == []


def test_every_module_folder_exists_in_the_real_package():
    package_dir = Path(crafting_system.__file__).parent

    missing = [layer for layer in LAYERS if not (package_dir / layer / "__init__.py").is_file()]

    assert missing == []


def test_real_package_has_exactly_the_eleven_subpackages():
    package_dir = Path(crafting_system.__file__).parent

    assert find_unexpected_subpackages(package_dir, LAYERS) == []


def test_real_package_imports_only_earlier_modules():
    package_dir = Path(crafting_system.__file__).parent

    assert find_layer_violations(package_dir, LAYERS) == []
