"""Which tests a mutant runs (ticket #399, step 5): the tests that execute its line, read from the coverage data.

Step 3 of the chain runs the whole suite under coverage with `dynamic_context = test_function`, so the combined data
file knows, for every line, the names of the test functions that ran it (`test_actions_scour.test_a_magic_item`, or
`test_x.TestClass.test_y`: the module name as pytest imported it, then the qualified name). This module turns a
context name into a pytest node id (`tests/test_actions_scour.py::test_a_magic_item`; a node id without brackets runs
every parametrisation of the function) and a line into the list of node ids.

Three cases, and what each gives:
  * the line has named test contexts: those tests. If the line also ran outside any test (the context `""`: a
    module-scoped fixture, `setup_module`), the tests that use that fixture are not named, so the whole test files
    of the named tests run instead. A context that does not resolve to a test of the files is dropped.
  * the line has no context at all, or only the empty one: no test is known. With the data present the mutant is
    "unreached" and is not run (the coverage step reports such code); the trial runs it anyway.
  * no data file (the artifact is missing): the test files that import the module. If none does, the files that
    import a module that imports it, and so on up to a few layers. Test helper modules count as imports of their
    importers.

A set is cut at `MAX_TESTS` entries, fastest test files first (`tests/shard_durations.json` gives seconds per test
file); the plan marks such a mutant as capped, since a survivor of a cut set might be killed by the tests left out.
"""

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

MAX_TESTS = 300
FALLBACK_LAYERS = 6
PACKAGE = "crafting_system"


@dataclass
class FileInfo:
    path: str  # posix, relative to the repo root: tests/test_x.py
    module: str  # as pytest imports it: test_x (tests/ has no __init__.py), or sub.test_x
    defs: set[tuple[str, ...]] = field(default_factory=set)  # ("test_f",), ("TestC", "test_m")
    imports: set[str] = field(default_factory=set)
    from_names: set[tuple[str, str]] = field(default_factory=set)  # (module, name) of `from module import name`


@dataclass
class SrcGraph:
    imports: dict[str, set[str]]  # module -> the package modules it imports
    defined: dict[str, set[str]]  # module -> the names it defines at top level


@dataclass
class TestIndex:
    tests: dict[str, FileInfo]  # test files by path
    helpers: dict[str, FileInfo]  # the other .py files of tests/ by module name (stem)
    fallback: dict[str, list[str]] = field(default_factory=dict)  # module -> its import fallback, computed once


def _imports_of(tree: ast.AST) -> tuple[set[str], set[tuple[str, str]]]:
    found: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
            pairs.update((node.module, alias.name) for alias in node.names)
    return found, pairs


def _definitions(tree: ast.Module) -> set[tuple[str, ...]]:
    found: set[tuple[str, ...]] = set()

    def walk(body, chain):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                found.add((*chain, node.name))
            elif isinstance(node, ast.ClassDef):
                walk(node.body, (*chain, node.name))

    walk(tree.body, ())
    return found


def build_index(tests_dir: Path, root: Path) -> TestIndex:
    """Parse every .py file under `tests_dir`; paths in the index are relative to `root`."""
    tests: dict[str, FileInfo] = {}
    helpers: dict[str, FileInfo] = {}
    for path in sorted(tests_dir.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        relative_to_tests = path.relative_to(tests_dir).with_suffix("")
        imports, pairs = _imports_of(tree)
        info = FileInfo(
            path=path.relative_to(root).as_posix(),
            module=".".join(relative_to_tests.parts),
            defs=_definitions(tree),
            imports=imports,
            from_names=pairs,
        )
        if path.name.startswith("test_"):
            tests[info.path] = info
        else:
            helpers[path.stem] = info
    return TestIndex(tests, helpers)


def resolve_context(index: TestIndex, context: str) -> str | None:
    """`test_x.TestC.test_m` -> `tests/test_x.py::TestC::test_m`; None when no test file has that function."""
    parts = context.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        module, chain = ".".join(parts[:cut]), tuple(parts[cut:])
        for info in index.tests.values():
            known = info.module
            if (module == known or known.endswith("." + module) or module.endswith("." + known)) and chain in info.defs:
                return "::".join([info.path, *chain])
    return None


def dotted_module(source_file: str) -> str:
    """`src/crafting_system/actions/draw.py` -> `crafting_system.actions.draw` (a package for `__init__.py`)."""
    parts = Path(source_file).with_suffix("").parts
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _top_level_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def build_src_graph(src_root: Path) -> SrcGraph:
    """The package's modules: what each imports (relative imports resolved) and what each defines at top level."""
    modules = {dotted_module(str(path.relative_to(src_root))) for path in src_root.rglob("*.py")}
    graph = SrcGraph({}, {})
    for path in sorted(src_root.rglob("*.py")):
        name = dotted_module(str(path.relative_to(src_root)))
        package = name if path.name == "__init__.py" else name.rpartition(".")[0]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names if alias.name in modules)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    anchor = package.split(".")
                    anchor = anchor[: len(anchor) - (node.level - 1)] if node.level > 1 else anchor
                    base = ".".join([*anchor, *([node.module] if node.module else [])])
                if base in modules:
                    found.add(base)
                found.update(f"{base}.{alias.name}" for alias in node.names if f"{base}.{alias.name}" in modules)
        graph.imports[name] = found - {name}
        graph.defined[name] = _top_level_names(tree)
    return graph


def _closure(index: TestIndex, info: FileInfo, memo: dict[str, tuple[set[str], set[tuple[str, str]]]]):
    """(module names, (module, name) pairs) the file imports, directly or through helper modules of tests/."""
    if info.path in memo:
        return memo[info.path]
    names = set(info.imports)
    pairs = set(info.from_names)
    queue = [info]
    visited = {info.path}
    while queue:
        for name in queue.pop().imports:
            helper = None if name.split(".")[0] == PACKAGE else index.helpers.get(name.split(".")[-1])
            if helper is not None and helper.path not in visited:
                visited.add(helper.path)
                names |= helper.imports
                pairs |= helper.from_names
                queue.append(helper)
    memo[info.path] = (names, pairs)
    return memo[info.path]


def _importing_tests(index: TestIndex, graph: SrcGraph, wanted: set[str], memo: dict) -> set[str]:
    """Test files that use one of the modules `wanted`.

    A file uses a module when it imports it by its dotted name, or imports from a package (or the module) a name that
    the module defines: `from crafting_system.actions import ScouringOrb` uses `actions.scour`, which defines it
    and which the package's `__init__` re-exports. Helper modules of tests/ count as part of their importers.
    """
    result = set()
    for path, info in index.tests.items():
        names, pairs = _closure(index, info, memo)
        if names & wanted:
            result.add(path)
            continue
        for package, name in pairs:
            if any(
                (module == package or module.startswith(package + ".")) and name in graph.defined.get(module, ())
                for module in wanted
            ):
                result.add(path)
                break
    return result


def import_fallback(index: TestIndex, graph: SrcGraph, module: str) -> list[str]:
    """Test files that import the module; failing that, the files that import its importers, a few layers up."""
    if module in index.fallback:
        return list(index.fallback[module])
    importers: dict[str, set[str]] = defaultdict(set)
    for name, imported in graph.imports.items():
        for target in imported:
            importers[target].add(name)
    layer = {module}
    seen = {module}
    memo: dict[str, set[str]] = {}
    for _ in range(FALLBACK_LAYERS):
        found = _importing_tests(index, graph, layer, memo)
        if found:
            index.fallback[module] = sorted(found)
            return sorted(found)
        layer = {name for target in layer for name in importers[target]} - seen
        if not layer:
            break
        seen |= layer
    index.fallback[module] = []
    return []


def file_speeds(durations: dict) -> dict[str, float]:
    """Seconds per test of each test file, from the groups of `tests/shard_durations.json` (`file` or `file[param#i]`)."""
    seconds: dict[str, float] = defaultdict(float)
    count: dict[str, int] = defaultdict(int)
    for group, entry in durations.items():
        name = group.split("[", 1)[0]
        seconds[name] += float(entry["seconds"])
        count[name] += int(entry["tests"])
    return {name: seconds[name] / count[name] for name in seconds if count[name]}


def tests_for_line(
    index: TestIndex,
    graph: SrcGraph,
    module: str,
    contexts: dict[int, list[str]] | None,
    line: int,
    speeds: dict[str, float] | None = None,
    reach_fallback: bool = False,
) -> tuple[list[str], str, int]:
    """(node ids, where they came from, entries cut), for the statement at `line` of `module`.

    The source is "coverage", "imports" (files that import the module) or "none" (no known test, nothing to run).
    `contexts` is None when the data file is missing; `reach_fallback` lets a line without a context use the
    import fallback as well (the trial).
    """
    speeds = speeds or {}
    chosen: list[str] = []
    origin = "none"
    if contexts is not None:
        names = contexts.get(line, [])
        resolved = sorted({node for node in (resolve_context(index, name) for name in names if name) if node})
        if resolved:
            origin, chosen = "coverage", resolved
            if "" in names:  # also ran in a fixture: the users of the fixture are not named, run the files whole
                chosen = sorted({node.split("::", 1)[0] for node in resolved})
        elif names or reach_fallback:
            chosen = import_fallback(index, graph, module)
            origin = "imports" if chosen else "none"
    else:
        chosen = import_fallback(index, graph, module)
        origin = "imports" if chosen else "none"
    chosen.sort(key=lambda node: (speeds.get(node.split("::", 1)[0], 0.0), node))
    cut = max(0, len(chosen) - MAX_TESTS)
    return chosen[:MAX_TESTS], origin, cut


def read_line_contexts(data_file: Path, source_file: str) -> dict[int, list[str]] | None:
    """Line -> test contexts of one source file from a coverage data file; None when the data has no such file.

    Needs the `coverage` package (the plan job installs it). File names are matched on the posix form of the path,
    since the data holds the names the measuring run wrote (relative with `relative_files = true`).
    """
    from coverage import CoverageData

    data = CoverageData(basename=str(data_file))
    data.read()
    wanted = source_file.replace("\\", "/")
    for name in data.measured_files():
        posix = name.replace("\\", "/")
        if posix == wanted or posix.endswith("/" + wanted) or wanted.endswith("/" + posix):
            return {line: list(names) for line, names in data.contexts_by_lineno(name).items()}
    return None
