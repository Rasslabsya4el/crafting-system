"""The reachability report (ticket #414, audit #396 class 3): which action kinds and which settings a plan can reach today.

The report reads the planner's own code, so unlike an oracle it imports `crafting_system`. It never solves anything:

* **Action kinds.** Every kind of the action catalog with its `planner` flag. For each benchmark target of
  `examples/targets/` it runs the real planner entry, `make_plan(..., solve_it=False)` (the gates, `offers_for`, the pricing
  and the abstraction, with nothing solved), and also the start options `vendor_recipe_starts` gives. A kind is *reachable*
  when some target's entry offers one of its actions; a kind no target is offered gets the reason the code gives.
* **Settings and flags.** Every key `crafting.toml` accepts and every flag of the command line. An AST search of `src/` follows
  each one from where it is read (`args.flag`, `config.key`) through the parameters, fields and variables it is passed on to, and
  reports the places where the value is *used* (compared, tested, formatted, handed to code outside `src/`) as opposed to only
  parsed, stored or forwarded.
* **Built modules.** The modules the audit names (the market rule, the item-level floor, the donor loop): who in `src/` refers to
  each public name, and whether the planner entry reaches it.

The text has no line numbers, timings or paths of this machine, so it only changes when the code does. The committed copy is
`tests/golden/reachability.md`; `tests/test_reachability_report.py` fails with a diff when the two differ.

    uv run --no-sync python .github/scripts/reachability_report.py --out reachability.md [--target-seconds 30] [--summary]

`--summary` also appends the report to `$GITHUB_STEP_SUMMARY`. The data comes from `CRAFTING_CACHE_DIR` (`data fetch`).
"""

import argparse
import ast
import dataclasses
import os
import sys
import threading
import time
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "crafting_system"
SRC = ROOT / "src" / PACKAGE
TARGETS_DIR = ROOT / "examples" / "targets"
DEFAULT_PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
FIXED_DAY = date(2026, 11, 6)  # the day the start sources are asked on, so the report does not move with the clock
TARGET_SECONDS = 30.0
BY_NAME_LIMIT = 3  # a method found by its name alone counts only when at most this many classes have a method of that name

# the places a plan starts from: the command line, the planner entry and the start choice
ENTRY_POINTS = (
    (f"{PACKAGE}.cli._main", "main"),
    (f"{PACKAGE}.cli._benchmark", "benchmark_main"),
    (f"{PACKAGE}.cli._plan", "make_plan"),
    (f"{PACKAGE}.cli._starts", "plan_with_starts"),
)

# the modules the audit says are built and not wired: (what it is, module, finding ids)
BUILT_MODULES = (
    ("the market rule", f"{PACKAGE}.prices.trade_market", "INPUTS-2"),
    ("the price-source rule", f"{PACKAGE}.prices.price_source", "INPUTS-2, PLANNING-6"),
    ("the item-level floor", f"{PACKAGE}.targets.floor", "TARGETS-3, PLANNING-8, ROUTES-13"),
    ("the donor loop of two-input actions", f"{PACKAGE}.cli._donors", "ACT2-11"),
)

# the findings of the audit that touch a kind, for the reader: ids only, no claim (the claim is the audit's)
KIND_FINDINGS = {
    "alchemy-orb": "ACT1-4, PLANNING-2",
    "scouring-orb": "ACT1-4, PLANNING-2",
    "harvest-reforge-likelihood": "ACT1-4",
    "vaal": "ACT2-1",
    "awakeners-orb": "ACT2-11",
    "recombinator": "ACT2-11",
}

STRANDS_KEYS = ("memory_strands", "--strands")  # the setting and the flag that turn Memory Strands on, which `make_plan` refuses
TARGET_FIELD_NOTES = {"item_level_floor": "TARGETS-3, PLANNING-8"}


# ---------------------------------------------------------------------------------------------------------------------
# The source index: modules, functions, classes, what a name means in a module, and who refers to whom
# ---------------------------------------------------------------------------------------------------------------------


@dataclasses.dataclass(eq=False)
class FuncInfo:
    module: str
    qual: str  # `f` or `Class.method`
    node: ast.AST
    cls: str | None
    params: list[str]

    @property
    def kwarg(self) -> str | None:
        """The name of the `**kwargs` parameter, if the function has one."""
        found = self.node.args.kwarg  # type: ignore[attr-defined]
        return found.arg if found is not None else None

    @property
    def key(self) -> tuple[str, str, str]:
        return ("func", self.module, self.qual)


@dataclasses.dataclass(eq=False)
class ClassInfo:
    module: str
    name: str
    node: ast.ClassDef
    fields: list[str]  # the annotated names of the class body, in order (a dataclass's fields)
    methods: dict[str, FuncInfo]

    @property
    def key(self) -> tuple[str, str, str]:
        return ("class", self.module, self.name)


@dataclasses.dataclass(eq=False)
class ModuleInfo:
    name: str
    rel: str  # path under the package, with forward slashes
    tree: ast.Module
    is_package: bool
    imports: dict[str, tuple[str, str | None]]  # alias -> (module, name or None for a module)
    funcs: dict[str, FuncInfo]  # top-level functions
    classes: dict[str, ClassInfo]


def _params(node: ast.AST) -> list[str]:
    arguments = node.args  # type: ignore[attr-defined]
    return [a.arg for a in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)]


class SourceIndex:
    """Every module under a source root, parsed once, with parents of nodes and the references between them."""

    def __init__(self, src_root: Path, package: str = PACKAGE) -> None:
        self.package = package
        self.modules: dict[str, ModuleInfo] = {}
        self.parent: dict[ast.AST, ast.AST] = {}
        self.funcs: dict[tuple[str, str, str], FuncInfo] = {}
        self.classes: dict[tuple[str, str, str], ClassInfo] = {}
        self.methods_by_name: dict[str, list[FuncInfo]] = defaultdict(list)
        for path in sorted(src_root.rglob("*.py")):
            relative = path.relative_to(src_root)
            parts = list(relative.with_suffix("").parts)
            is_package = parts[-1] == "__init__"
            if is_package:
                parts = parts[:-1]
            name = ".".join([package, *parts])
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(relative.as_posix()))
            self.modules[name] = ModuleInfo(name, relative.as_posix(), tree, is_package, {}, {}, {})
        for info in self.modules.values():
            for outer in ast.walk(info.tree):
                for child in ast.iter_child_nodes(outer):
                    self.parent[child] = outer
            self._collect(info)
        self._graph: tuple[dict, dict] | None = None
        self._nodes: dict[FuncInfo, list[ast.AST]] = {}
        self._calls_by_name: dict[str, list[tuple[FuncInfo, ast.Call]]] | None = None
        self._attribute_loads: dict[str, list[tuple[FuncInfo, ast.Attribute]]] | None = None

    def nodes(self, func: FuncInfo) -> list[ast.AST]:
        """Every node under a function, walked once."""
        found = self._nodes.get(func)
        if found is None:
            found = self._nodes[func] = list(ast.walk(func.node))
        return found

    def calls_named(self, name: str) -> list[tuple[FuncInfo, ast.Call]]:
        """Every call in `src` whose callee is written `name(...)` or `x.name(...)`."""
        if self._calls_by_name is None:
            found: dict[str, list[tuple[FuncInfo, ast.Call]]] = defaultdict(list)
            for func in self.funcs.values():
                for node in self.nodes(func):
                    if isinstance(node, ast.Call):
                        called = node.func
                        label = called.id if isinstance(called, ast.Name) else called.attr if isinstance(called, ast.Attribute) else None
                        if label:
                            found[label].append((func, node))
            self._calls_by_name = found
        return self._calls_by_name.get(name, [])

    def attribute_loads(self, attr: str) -> list[tuple[FuncInfo, ast.Attribute]]:
        """Every read of `x.attr` in `src`."""
        if self._attribute_loads is None:
            found: dict[str, list[tuple[FuncInfo, ast.Attribute]]] = defaultdict(list)
            for func in self.funcs.values():
                for node in self.nodes(func):
                    if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                        found[node.attr].append((func, node))
            self._attribute_loads = found
        return self._attribute_loads.get(attr, [])

    # -- collecting definitions and imports

    def _collect(self, info: ModuleInfo) -> None:
        package = info.name if info.is_package else info.name.rpartition(".")[0]
        for node in ast.walk(info.tree):
            if isinstance(node, ast.ImportFrom):
                base = package.split(".")
                if node.level:
                    base = base[: len(base) - (node.level - 1)]
                    target = ".".join([*base, *([node.module] if node.module else [])])
                else:
                    target = node.module or ""
                for alias in node.names:
                    info.imports[alias.asname or alias.name] = (target, alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    info.imports[alias.asname or alias.name.split(".")[0]] = (alias.name if alias.asname else alias.name.split(".")[0], None)
        for node in info.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = FuncInfo(info.name, node.name, node, None, _params(node))
                info.funcs[node.name] = func
                self.funcs[func.key] = func
            elif isinstance(node, ast.ClassDef):
                fields = [s.target.id for s in node.body if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)]
                klass = ClassInfo(info.name, node.name, node, fields, {})
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method = FuncInfo(info.name, f"{node.name}.{member.name}", member, node.name, _params(member))
                        klass.methods[member.name] = method
                        self.funcs[method.key] = method
                        self.methods_by_name[member.name].append(method)
                info.classes[node.name] = klass
                self.classes[klass.key] = klass

    # -- what a name means

    def resolve_name(self, module: str, name: str, depth: int = 0) -> tuple[str, object] | None:
        """`('func', FuncInfo)`, `('class', ClassInfo)` or `('module', dotted name)` for a name used in `module`, else None."""
        info = self.modules.get(module)
        if info is None or depth > 8:
            return None
        if name in info.funcs:
            return ("func", info.funcs[name])
        if name in info.classes:
            return ("class", info.classes[name])
        imported = info.imports.get(name)
        if imported is None:
            return None
        target, original = imported
        if original is None:
            return ("module", target) if target in self.modules else None
        if f"{target}.{original}" in self.modules:
            return ("module", f"{target}.{original}")
        if target in self.modules:
            return self.resolve_name(target, original, depth + 1)
        return None

    def enclosing_func(self, node: ast.AST) -> ast.AST | None:
        """The outermost function or method that holds `node` (nested functions count as part of it)."""
        found = None
        current = self.parent.get(node)
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found = current
            current = self.parent.get(current)
        return found

    def func_of_node(self, module: str, node: ast.AST) -> FuncInfo | None:
        outer = self.enclosing_func(node)
        if outer is None:
            return None
        info = self.modules[module]
        klass = self.parent.get(outer)
        if isinstance(klass, ast.ClassDef):
            return info.classes[klass.name].methods.get(outer.name)  # type: ignore[attr-defined]
        return info.funcs.get(outer.name)  # type: ignore[attr-defined]

    def callees(self, call: ast.Call, module: str, caller: FuncInfo | None) -> list[tuple[str, object]]:
        """What a call may run: functions and classes of the index; empty when it leaves the index (a builtin, the standard library)."""
        func = call.func
        if isinstance(func, ast.Name):
            found = self.resolve_name(module, func.id)
            return [found] if found and found[0] in ("func", "class") else []
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                found = self.resolve_name(module, func.value.id)
                if found and found[0] == "module":
                    inner = self.resolve_name(str(found[1]), func.attr)
                    return [inner] if inner and inner[0] in ("func", "class") else []
                if func.value.id in ("self", "cls") and caller is not None and caller.cls:
                    own = self.modules[module].classes[caller.cls].methods.get(func.attr)
                    if own is not None:
                        return [("func", own)]
            return [("func", m) for m in self.named_methods(func.attr)]
        return []

    def named_methods(self, name: str) -> list[FuncInfo]:
        """The methods a call `x.name(...)` may run when the type of `x` is not known: all of them when the name is rare, none when it is a
        dunder or so common (more than `BY_NAME_LIMIT` classes) that the name says nothing."""
        found = self.methods_by_name.get(name, [])
        return [] if name.startswith("__") or len(found) > BY_NAME_LIMIT else found

    # -- the graph of references (a function refers to what its body names), and what it reaches

    def graph(self) -> tuple[dict, dict]:
        """(edges, how): node -> set of nodes it refers to; (node, node) -> 'by name' for a method found by its name only."""
        if self._graph is not None:
            return self._graph
        edges: dict[tuple, set] = defaultdict(set)
        how: dict[tuple, str] = {}

        def add(source: tuple, target: tuple, by_name: bool = False) -> None:
            edges[source].add(target)
            if by_name:
                how.setdefault((source, target), "method by name")

        def scan(source: tuple, module: str, nodes: Iterable[ast.AST], caller: FuncInfo | None) -> None:
            for root in nodes:
                typed: set[int] = set()  # a type annotation names a class without using it
                for node in ast.walk(root):
                    annotation = getattr(node, "annotation", None) if isinstance(node, (ast.AnnAssign, ast.arg)) else getattr(node, "returns", None)
                    if annotation is not None:
                        typed.update(id(inner) for inner in ast.walk(annotation))
                for node in ast.walk(root):
                    if id(node) in typed:
                        continue
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                        found = self.resolve_name(module, node.id)
                        if found and found[0] in ("func", "class"):
                            add(source, found[1].key)  # type: ignore[attr-defined]
                    elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and isinstance(node.value, ast.Name):
                        found = self.resolve_name(module, node.value.id)
                        if found and found[0] == "module":
                            inner = self.resolve_name(str(found[1]), node.attr)
                            if inner and inner[0] in ("func", "class"):
                                add(source, inner[1].key)  # type: ignore[attr-defined]
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        for kind, target in self.callees(node, module, caller):
                            if kind == "func":
                                add(source, target.key, by_name=True)  # type: ignore[attr-defined]

        for info in self.modules.values():
            module_source = ("mod", info.name, "")
            module_level: list[ast.AST] = []
            for node in info.tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    module_level.extend(node.decorator_list)
                    module_level.extend(node.args.defaults + [d for d in node.args.kw_defaults if d is not None])
                elif isinstance(node, ast.ClassDef):
                    module_level.extend(node.decorator_list)
                    module_level.extend(s for s in node.body if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)))
                elif not isinstance(node, (ast.Import, ast.ImportFrom)):
                    module_level.append(node)
            scan(module_source, info.name, module_level, None)
            for func in info.funcs.values():
                scan(func.key, info.name, [func.node], func)
                add(func.key, module_source)
            for klass in info.classes.values():
                for dunder in ("__init__", "__post_init__"):
                    if dunder in klass.methods:
                        add(klass.key, klass.methods[dunder].key)
                add(klass.key, module_source)
                for method in klass.methods.values():
                    scan(method.key, info.name, [method.node], method)
                    add(method.key, module_source)
        self._graph = (edges, how)
        return self._graph

    def reachable_from(self, roots: Iterable[tuple]) -> dict[tuple, tuple | None]:
        """Every node the roots reach, with the node it was reached from (None for a root)."""
        edges, _ = self.graph()
        seen: dict[tuple, tuple | None] = {}
        queue: deque = deque()
        for root in roots:
            seen[root] = None
            queue.append(root)
        while queue:
            node = queue.popleft()
            for nxt in sorted(edges.get(node, ())):
                if nxt not in seen:
                    seen[nxt] = node
                    queue.append(nxt)
        return seen

    def referrers(self, key: tuple) -> list[tuple]:
        """The nodes that refer to `key`, in sorted order."""
        edges, _ = self.graph()
        return sorted(source for source, targets in edges.items() if key in targets)


def _node_name(key: tuple) -> str:
    """A node as the report writes it: `cli/_plan.py: make_plan`."""
    return f"{key[1]}:{key[2]}" if key[0] != "mod" else key[1]


def _short_module(module: str) -> str:
    return module.removeprefix(PACKAGE + ".")


def _site_name(index: SourceIndex, module: str, func: str) -> str:
    return f"{index.modules[module].rel}: {func}"


# ---------------------------------------------------------------------------------------------------------------------
# Where a value is read: seeds (`args.flag`, `config.key`) followed through parameters, fields and variables
# ---------------------------------------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Site:
    module: str
    func: str
    how: str


@dataclasses.dataclass(eq=False)
class Trace:
    """What became of one value: where it is used, where it was handed on and stopped, and the places it was only forwarded."""

    sites: set[Site] = dataclasses.field(default_factory=set)
    ends: set[str] = dataclasses.field(default_factory=set)  # slots the value reached that no code reads
    unresolved: set[str] = dataclasses.field(default_factory=set)  # reads of a same-named attribute on a receiver of unknown type
    forwarded: set[str] = dataclasses.field(default_factory=set)


class Tracer:
    def __init__(self, index: SourceIndex) -> None:
        self.index = index

    # -- the types of the names of a function: which names hold a given class

    def typed_names(self, func: FuncInfo, klass: ClassInfo, extra: Iterable[str] = (), factories: Iterable[str] = ()) -> set[str]:
        names: set[str] = {n for n in extra if n in func.params}
        if func.cls == klass.name and func.module == klass.module and func.params and func.params[0] in ("self", "cls"):
            names.add(func.params[0])
        arguments = func.node.args  # type: ignore[attr-defined]
        for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
            if arg.annotation is not None and self._annotation_names(arg.annotation) & {klass.name}:
                names.add(arg.arg)
        for node in self.index.nodes(func):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                called = node.value.func
                called_name = called.id if isinstance(called, ast.Name) else called.attr if isinstance(called, ast.Attribute) else ""
                found = self.index.resolve_name(func.module, called_name) if called_name else None
                makes = (found and found[0] == "class" and found[1] is klass) or called_name in set(factories)
                if makes:
                    names.update(t.id for t in node.targets if isinstance(t, ast.Name))
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and self._annotation_names(node.annotation) & {klass.name}:
                names.add(node.target.id)
        return names

    @staticmethod
    def _annotation_names(annotation: ast.AST) -> set[str]:
        found = set()
        for node in ast.walk(annotation):
            if isinstance(node, ast.Name):
                found.add(node.id)
            elif isinstance(node, ast.Attribute):
                found.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.update(part.strip() for part in node.value.replace("|", " ").replace("[", " ").replace("]", " ").split())
        return found

    # -- seeds

    def attribute_reads(self, klass: ClassInfo, attr: str, extra: Iterable[str] = (), factories: Iterable[str] = (), skip: Callable[[str], bool] = lambda m: False) -> tuple[list[tuple[FuncInfo, ast.Attribute]], list[tuple[FuncInfo, ast.Attribute]]]:
        """(reads on a receiver known to hold `klass`, reads of the same attribute name on a receiver of unknown type)."""
        typed: list[tuple[FuncInfo, ast.Attribute]] = []
        unknown: list[tuple[FuncInfo, ast.Attribute]] = []
        names_of: dict[FuncInfo, set[str]] = {}
        reads: list[tuple[FuncInfo, ast.AST, ast.AST]] = [(func, node, node.value) for func, node in self.index.attribute_loads(attr)]
        for func, call in self.index.calls_named("getattr"):  # `getattr(target, "name", default)` reads the attribute too
            if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and call.args[1].value == attr:
                reads.append((func, call, call.args[0]))
        for func, node, value in reads:
            if skip(func.module):
                continue
            if func not in names_of:
                names_of[func] = self.typed_names(func, klass, extra, factories)
            if isinstance(value, ast.Name) and value.id in names_of[func]:
                typed.append((func, node))
            elif (
                isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.value.id in ("self", "cls")
                and value.attr in set(extra)
            ):
                typed.append((func, node))
            else:
                unknown.append((func, node))
        return typed, unknown

    def flag_reads(self, dest: str) -> list[tuple[FuncInfo, ast.Attribute]]:
        """`args.<dest>` in a function that makes `args` with `parser.parse_args(...)`."""
        found = []
        holders_of: dict[FuncInfo, set[str]] = {}
        for func, node in self.index.attribute_loads(dest):
            if func not in holders_of:
                holders: set[str] = set()
                for inner in self.index.nodes(func):
                    if isinstance(inner, ast.Assign) and isinstance(inner.value, ast.Call):
                        called = inner.value.func
                        if isinstance(called, ast.Attribute) and called.attr == "parse_args":
                            holders.update(t.id for t in inner.targets if isinstance(t, ast.Name))
                holders_of[func] = holders
            if isinstance(node.value, ast.Name) and node.value.id in holders_of[func]:
                found.append((func, node))
        return found

    # -- following a value

    def trace(self, starts: Iterable[tuple[FuncInfo, ast.AST]]) -> Trace:
        result = Trace()
        seen: set = set()
        work: list = [("expr", func, node) for func, node in starts]
        while work:
            item = work.pop()
            if item in seen:
                continue
            seen.add(item)
            if item[0] == "expr":
                _, func, node = item
                for outcome in self._use(func, node):
                    self._take(outcome, result, work)
            elif item[0] == "slot-local":
                _, func, name = item
                loads = [n for n in self.index.nodes(func) if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)]
                if not loads:
                    result.ends.add(f"{_short_module(func.module)}: {func.qual}: the variable `{name}`")
                for load in loads:
                    work.append(("expr", func, load))
            elif item[0] == "slot-field":
                _, klass_key, field = item
                klass = self.index.classes[klass_key]
                typed, unknown = self.attribute_reads(klass, field)
                label = f"{klass.name}.{field}"
                result.forwarded.add(f"the field `{label}`")
                if not typed:
                    result.ends.add(f"the field `{label}`")
                for func, node in typed:
                    work.append(("expr", func, node))
                result.unresolved.update(f"{_short_module(f.module)}: {f.qual}" for f, _ in unknown)
            elif item[0] == "slot-kw":
                _, func, key = item
                name = func.kwarg
                loads = [n for n in self.index.nodes(func) if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)]
                if not loads:
                    result.ends.add(f"{_short_module(func.module)}: {func.qual}: the unused `**{name}`")
                for load in loads:
                    parent = self.index.parent.get(load)
                    if isinstance(parent, ast.keyword) and parent.arg is None:
                        for outcome in self._forward(func, self.index.parent[parent], keyword=key):
                            self._take(outcome, result, work)
                    else:
                        result.sites.add(Site(func.module, func.qual, f"read from `**{name}`"))
            elif item[0] == "slot-return":
                _, func = item
                result.forwarded.add(f"the return value of `{func.qual}`")
                callers = [
                    (caller, call)
                    for caller, call in self.index.calls_named(func.qual.rpartition(".")[2])
                    if ("func", func) in self.index.callees(call, caller.module, caller)
                ]
                if not callers:
                    result.ends.add(f"the return value of `{func.qual}`")
                for caller, call in callers:
                    work.append(("expr", caller, call))
        return result

    def _take(self, outcome: tuple, result: Trace, work: list) -> None:
        kind = outcome[0]
        if kind == "consume":
            result.sites.add(outcome[1])
        elif kind == "end":
            result.ends.add(outcome[1])
        else:
            work.append(outcome)

    def _use(self, func: FuncInfo, node: ast.AST) -> list[tuple]:
        """What is done with the value of `node`: ('consume', Site), ('end', text), or a slot to follow."""
        index = self.index
        current = node
        while True:
            parent = index.parent.get(current)
            if parent is None:
                return [("end", f"{_short_module(func.module)}: {func.qual}: value dropped")]
            if isinstance(parent, ast.BoolOp):
                current = parent
            elif isinstance(parent, ast.IfExp):
                if current is parent.test:
                    return [("consume", Site(func.module, func.qual, "decides a branch"))]
                current = parent
            elif isinstance(parent, (ast.Tuple, ast.List, ast.Set, ast.Starred, ast.Await, ast.Expr)):
                if isinstance(parent, ast.Expr):
                    return []
                current = parent
            elif isinstance(parent, ast.Dict):
                if current in parent.values:
                    current = parent
                else:
                    return [("consume", Site(func.module, func.qual, "used as a key"))]
            elif isinstance(parent, ast.keyword):
                call = index.parent[parent]
                if parent.arg is None:
                    return [("consume", Site(func.module, func.qual, "passed on in `**`"))]
                return self._forward(func, call, keyword=parent.arg)
            elif isinstance(parent, ast.Call):
                if current is parent.func:
                    return [("consume", Site(func.module, func.qual, "called"))]
                position = parent.args.index(current) if current in parent.args else -1
                if position < 0 or any(isinstance(a, ast.Starred) for a in parent.args[: position + 1]):
                    return [("consume", Site(func.module, func.qual, "passed on in `*`"))]
                return self._forward(func, parent, position=position)
            elif isinstance(parent, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                if current is not parent.value:
                    return [("consume", Site(func.module, func.qual, "used as a target"))]
                targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
                out: list[tuple] = []
                for target in targets:
                    if isinstance(target, ast.Name):
                        out.append(("slot-local", func, target.id))
                    elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self" and func.cls:
                        klass = index.modules[func.module].classes[func.cls]
                        out.append(("slot-field", klass.key, target.attr))
                    else:
                        out.append(("end", f"{_short_module(func.module)}: {func.qual}: unpacked into several names"))
                return out
            elif isinstance(parent, (ast.Return, ast.Yield, ast.YieldFrom)):
                return [("slot-return", func)]
            elif isinstance(parent, (ast.Compare, ast.If, ast.While, ast.Assert)):
                how = "compared" if isinstance(parent, ast.Compare) else "decides a branch"
                return [("consume", Site(func.module, func.qual, how))]
            elif isinstance(parent, (ast.BinOp, ast.UnaryOp, ast.AugAssign)):
                return [("consume", Site(func.module, func.qual, "used in an operation"))]
            elif isinstance(parent, (ast.JoinedStr, ast.FormattedValue)):
                return [("consume", Site(func.module, func.qual, "formatted into text"))]
            elif isinstance(parent, ast.Attribute):
                return [("consume", Site(func.module, func.qual, "an attribute or method of it is used"))]
            elif isinstance(parent, ast.Subscript):
                return [("consume", Site(func.module, func.qual, "used as an index or container"))]
            else:
                return [("consume", Site(func.module, func.qual, f"used in {type(parent).__name__}"))]

    def _forward(self, func: FuncInfo, call: ast.Call, *, keyword: str | None = None, position: int | None = None) -> list[tuple]:
        """The value is an argument of `call`: follow it into the parameter or field it lands in, or count it used when the callee is outside `src`."""
        found = self.index.callees(call, func.module, func)
        called = ast.unparse(call.func)
        if not found:
            return [("consume", Site(func.module, func.qual, f"passed to `{called}` (outside src)"))]
        out: list[tuple] = []
        for kind, target in found:
            if kind == "class":
                klass: ClassInfo = target  # type: ignore[assignment]
                init = klass.methods.get("__init__")
                if init is not None:
                    names = init.params[1:]
                    chosen = keyword if keyword is not None else names[position] if position is not None and position < len(names) else None
                    if chosen and chosen in names:
                        out.append(("slot-local", init, chosen))
                        continue
                names = klass.fields
                chosen = keyword if keyword is not None else names[position] if position is not None and position < len(names) else None
                if chosen and chosen in names:
                    out.append(("slot-field", klass.key, chosen))
                else:
                    out.append(("end", f"{klass.name}: no parameter for this argument"))
            else:
                callee: FuncInfo = target  # type: ignore[assignment]
                names = callee.params[1:] if callee.cls and callee.params and callee.params[0] in ("self", "cls") else callee.params
                chosen = keyword if keyword is not None else names[position] if position is not None and position < len(names) else None
                if chosen and chosen in callee.params:
                    out.append(("slot-local", callee, chosen))
                elif keyword is not None and callee.kwarg:
                    out.append(("slot-kw", callee, keyword))
                else:
                    out.append(("end", f"{callee.qual}: no parameter for this argument"))
        return out


# ---------------------------------------------------------------------------------------------------------------------
# Settings and flags
# ---------------------------------------------------------------------------------------------------------------------


@dataclasses.dataclass(eq=False)
class SettingRow:
    name: str  # as the user writes it
    where: str  # `[planner]`, `[paths]` or the command
    default: str
    trace: Trace
    named_consumers: list[str]
    read: bool


def cli_flags(index: SourceIndex, prefix: str = f"{PACKAGE}.cli.") -> list[tuple[str, str, str, str]]:
    """(flag text, dest, command, module) for each `add_argument` call of the modules whose name begins with `prefix`."""
    found = []
    for func in index.funcs.values():
        if not func.module.startswith(prefix):
            continue
        for node in ast.walk(func.node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument" and node.args:
                names = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                dest = next((k.value.value for k in node.keywords if k.arg == "dest" and isinstance(k.value, ast.Constant)), None)
                if dest is None:
                    longs = [n for n in names if n.startswith("--")]
                    dest = (longs[0] if longs else names[0]).lstrip("-").replace("-", "_")
                command = {"benchmark_main": "benchmark", "trade_main": "trade"}.get(func.qual, "plan")
                found.append((" / ".join(names), dest, command, func.module))
    return sorted(found)


def config_keys() -> list[tuple[str, str, str, str]]:
    """(key, table, config field, default) for every key `crafting.toml` accepts."""
    from crafting_system import config as config_module

    fields = {f.name: f for f in dataclasses.fields(config_module.Config)}
    rows = []
    for key in config_module._PATH_SETTINGS:
        rows.append((key, "[paths]", f"{key}_dir", f"`{config_module._PATH_SETTINGS[key][1]}`"))
    for key in config_module._PLANNER_SETTINGS:
        default = fields[key].default
        rows.append((key, "[planner]", key, f"`{str(default).lower() if isinstance(default, bool) else default}`"))
    return rows


def named_consumers(index: SourceIndex, key: str) -> list[str]:
    """Code that takes the setting by its own name: a parameter called `key`, or a context variable named `key`, and who in `src` calls it."""
    found = []
    for func in sorted(index.funcs.values(), key=lambda f: f.key):
        if func.module == f"{PACKAGE}.config":
            continue
        if key in func.params:
            referrers = [r for r in index.referrers(func.key) if r[1] != func.module]
            passing = 0
            for caller_key in referrers:
                caller = index.funcs.get(caller_key)
                if caller is None:
                    continue
                for call in index.nodes(caller):
                    if isinstance(call, ast.Call) and ("func", func) in index.callees(call, caller.module, caller):
                        position = func.params.index(key) - (1 if func.cls else 0)
                        if any(k.arg == key for k in call.keywords) or len(call.args) > position >= 0:
                            passing += 1
            found.append(
                f"parameter `{key}` of `{_site_name(index, func.module, func.qual)}`: "
                f"{len(referrers)} referrer(s) outside its module, {passing} pass the parameter"
            )
    for info in index.modules.values():
        for node in info.tree.body:
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.value, ast.Call)
                and ast.unparse(node.value.func).endswith("ContextVar")
                and node.value.args
                and isinstance(node.value.args[0], ast.Constant)
                and node.value.args[0].value == key
                and isinstance(node.target, ast.Name)
            ):
                setters = []
                for func in info.funcs.values():
                    text = ast.unparse(func.node)
                    if f"{node.target.id}.set(" in text:
                        outside = [r for r in index.referrers(func.key) if r[1] != info.name]
                        setters.append(f"`{func.qual}` ({len(outside)} referrer(s) outside its module)")
                found.append(
                    f"context variable `{key}` in `{info.rel}`: set by {', '.join(setters) if setters else 'nothing'}"
                )
    return found


def settings_rows(index: SourceIndex) -> list[SettingRow]:
    tracer = Tracer(index)
    config_module = f"{PACKAGE}.config"
    config_class = index.classes[("class", config_module, "Config")]
    rows: list[SettingRow] = []
    for key, table, field, default in config_keys():
        typed, _ = tracer.attribute_reads(config_class, field, extra=("config", "cfg"), factories=("load_config",), skip=lambda m: m == config_module)
        trace = tracer.trace(typed)
        rows.append(SettingRow(key, table, default, trace, named_consumers(index, key), bool(trace.sites)))
    for flag, dest, command, _module in cli_flags(index):
        if not flag.startswith("-"):
            continue  # the target file is the thing planned, not a setting
        trace = tracer.trace(tracer.flag_reads(dest))
        rows.append(SettingRow(flag, f"command `{command}`", "", trace, [], bool(trace.sites)))
    return rows


def target_field_rows(index: SourceIndex) -> list[tuple[str, list[str], str]]:
    """(field, modules outside the targets package that read it, finding ids) for each field of the `Target` YAML model."""
    from crafting_system.targets import Target

    tracer = Tracer(index)
    klass = index.classes[("class", f"{PACKAGE}.targets.model", "Target")]
    rows = []
    for field in dataclasses.fields(Target):
        typed, _ = tracer.attribute_reads(klass, field.name, extra=("target",), factories=("load_target",), skip=lambda m: m.startswith(f"{PACKAGE}.targets"))
        readers = sorted({f"{index.modules[f.module].rel}" for f, _ in typed})
        rows.append((field.name, readers, TARGET_FIELD_NOTES.get(field.name, "")))
    return rows


# ---------------------------------------------------------------------------------------------------------------------
# The planner entry for each benchmark target
# ---------------------------------------------------------------------------------------------------------------------

TOO_SLOW = "not measured, too slow"


@dataclasses.dataclass(eq=False)
class Probe:
    """One run of the planner entry: a benchmark target's own start item, or a start option the recipe source offers for it."""

    target_id: str
    option: str  # "" for the target's own start item, else the label of the recipe start
    outcome: str  # "plans", "refused" or TOO_SLOW
    message: str = ""
    plan: object = None
    target: object = None
    members: dict = dataclasses.field(default_factory=dict)  # kind name -> its actions for the start item
    owner: dict = dataclasses.field(default_factory=dict)  # action -> the kind that lists it

    @property
    def label(self) -> str:
        return self.target_id + (f" ({self.option})" if self.option else "")


def run_with_limit(function: Callable[[], object], seconds: float) -> tuple[bool, object]:
    """(finished, result or raised exception). A run still going after `seconds` is left behind on a daemon thread."""
    box: dict = {}

    def work() -> None:
        try:
            box["value"] = function()
        except BaseException as error:  # noqa: BLE001  (an error of the planner is a result to report)
            box["error"] = error

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        return False, None
    return True, box.get("error", box.get("value"))


def short_ids(stems: list[str]) -> dict[str, str]:
    """`r12` for `r12-lightning-amulet`; the whole stem when two files begin alike."""
    firsts = Counter(stem.split("-")[0] for stem in stems)
    return {stem: (stem.split("-")[0] if firsts[stem.split("-")[0]] == 1 else stem) for stem in stems}


def first_sentence(text: str) -> str:
    text = " ".join(text.split())
    for stop in (". ", "; "):
        if stop in text:
            return text.split(stop)[0].rstrip(".") + "."
    return text


def probe_targets(data, seconds: float, prices_path: Path = DEFAULT_PRICES, targets_dir: Path = TARGETS_DIR) -> list[Probe]:
    from crafting_system.actions import kinds
    from crafting_system.cli import StartContext, make_plan, vendor_recipe_starts
    from crafting_system.cli._plan import PlanError, StartPrice
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    default_prices = load_price_file(prices_path)
    stems = sorted(path.stem for path in targets_dir.glob("*.yaml"))
    ids = short_ids(stems)
    probes: list[Probe] = []

    def members_of(item) -> tuple[dict, dict]:
        by_kind, owner = {}, {}
        for entry in kinds(planner_only=True):
            try:
                found = list(entry.members(data, item))
            except Exception:  # noqa: BLE001  (a kind that cannot list for this item offers nothing)
                found = []
            by_kind[entry.name] = found
            for action in found:
                owner.setdefault(action, entry.name)
        return by_kind, owner

    def plan_one(label: str, option: str, target, prices, **kwargs) -> Probe:
        done, result = run_with_limit(lambda: make_plan(data, target, prices, solve_it=False, **kwargs), seconds)
        if not done:
            return Probe(label, option, TOO_SLOW, f"the entry took over {seconds:g} s", target=target)
        if isinstance(result, PlanError):
            return Probe(label, option, "refused", str(result), target=target)
        if isinstance(result, BaseException):
            return Probe(label, option, "refused", f"{type(result).__name__}: {result}", target=target)
        members, owner = members_of(target.start_item)
        return Probe(label, option, "plans", plan=result, target=target, members=members, owner=owner)

    for stem in stems:
        target = load_target(targets_dir / f"{stem}.yaml", data)
        prices = load_price_file(Path(target.price_file)) if target.price_file else default_prices
        probes.append(plan_one(ids[stem], "", target, prices))
        try:
            listing = vendor_recipe_starts(StartContext(data, target, prices, "both", 20.0, FIXED_DAY))
        except Exception:  # noqa: BLE001
            continue
        seen_items = set()
        for candidate in listing.candidates:
            if candidate.item in seen_items:
                continue
            seen_items.add(candidate.item)
            moved = dataclasses.replace(target, start_item=candidate.item, buys_start_item=False)
            price = StartPrice(candidate.price_name, candidate.price, candidate.price_source)
            probes.append(plan_one(ids[stem], "recipe start", moved, prices, start_price_of=price))
    return probes


def offered_kinds(probe: Probe) -> dict[str, int]:
    """kind -> number of offers of that kind in the plan of the probe (the restart offer is not an action of the catalog)."""
    from crafting_system.cli._offers import BuyStartItem

    counts: Counter = Counter()
    for priced in probe.plan.offers:  # type: ignore[attr-defined]
        action = priced.offer.action
        if isinstance(action, BuyStartItem):
            continue
        counts[probe.owner.get(action, "(not in the catalog)")] += 1
    return dict(counts)


ACTION_LIMITS = frozenset({"crafts", "fixed-mod", "rolls", "proved-unneeded"})  # the limits (`cli/_limits.py`) whose labels are actions


def why_not_offered(data, kind, probe: Probe) -> str:
    """The first reason, in the order the planner applies them, that this planner kind gives no offer on this probe."""
    from crafting_system.abstraction import Goal

    if probe.outcome == TOO_SLOW:
        return TOO_SLOW
    if probe.outcome == "refused":
        return "the target is refused by `make_plan` (section 3)"
    plan, target = probe.plan, probe.target
    goal = Goal.from_target(target)  # type: ignore[arg-type]
    names = target.actions  # type: ignore[attr-defined]
    if kind.needs_strands and target.start_item.memory_strands < 1:  # type: ignore[attr-defined]
        return "needs Memory Strands, which `make_plan` refuses to plan with"
    if kind.corrupting and not goal.takes_corrupted:
        return "it corrupts the item and the target takes no corrupted item"
    members = probe.members.get(kind.name, [])
    labels = {a.label(data) for a in members}
    if names is not None and kind.name not in names and not (labels & set(names)):
        return "not named in the target's `actions:`"
    if kind.opt_in and names is None:
        return "an opt-in kind and the target has no `actions:` key"
    if not members:
        return "the kind lists no action for this start item"
    left = {}
    for group in plan.limits:  # type: ignore[attr-defined]
        if group.kind in ACTION_LIMITS:  # the other limits list kinds by name, not actions by label
            for label in group.labels:
                left.setdefault(label, group.why)
    dropped = {label: limit.names for limit in plan.limits if limit.kind == "unpriced" for label in limit.labels}  # type: ignore[attr-defined]
    fates: Counter = Counter()
    for action in members:
        label = action.label(data)
        if label in left:
            fates[f"left out: {left[label]}"] += 1
            continue
        missing = next((m for name, m in dropped.items() if name == label or name.startswith(label + " [")), None)
        if missing is not None:
            fates[f"dropped for lack of a price (missing: {missing[0]})"] += 1
        else:
            fates["not offered (removed by `usable_actions`, which needs a crafted mod)"] += 1
    return "; ".join(f"{text} ({count} of {len(members)})" if len(fates) > 1 or count != len(members) else text for text, count in sorted(fates.items()))


def _message_text(node: ast.AST) -> str:
    """The text of a message as the code writes it; `{...}` stands for a part the code fills in."""
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.JoinedStr):
        return "".join(_message_text(part) for part in node.values)
    if isinstance(node, ast.FormattedValue):
        return "{" + ast.unparse(node.value) + "}"
    return "{" + ast.unparse(node) + "}"


def entry_gates(index: SourceIndex) -> list[tuple[str, str]]:
    """(condition, message) of each `if ...: raise PlanError(...)` of `make_plan` before it builds the abstraction, as the code writes them."""
    func = index.funcs[("func", f"{PACKAGE}.cli._plan", "make_plan")]
    gates = []
    for statement in func.node.body:  # type: ignore[attr-defined]
        if any(isinstance(n, ast.Call) and ast.unparse(n.func) == "Abstraction" for n in ast.walk(statement)):
            break  # what follows is the solve
        if isinstance(statement, ast.If) and statement.body and isinstance(statement.body[0], ast.Raise):
            call = statement.body[0].exc
            if isinstance(call, ast.Call) and ast.unparse(call.func) == "PlanError" and call.args:
                gates.append((ast.unparse(statement.test), " ".join(_message_text(call.args[0]).split())))
    return gates


def closed_inputs(index: SourceIndex) -> list[str]:
    """Where `make_plan` builds the abstraction with `allow_inputs=False`, as the code writes it."""
    func = index.funcs[("func", f"{PACKAGE}.cli._plan", "make_plan")]
    found = []
    for node in ast.walk(func.node):
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "Abstraction":
            for keyword in node.keywords:
                if keyword.arg == "allow_inputs":
                    found.append(f"Abstraction(..., allow_inputs={ast.unparse(keyword.value)}) in make_plan")
    return found


# ---------------------------------------------------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------------------------------------------------


def cell(text: object) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(cell(c) for c in row) + " |" for row in rows)
    return lines


def takes_inputs(action) -> bool:
    from crafting_system.actions import Action

    return type(action).inputs is not Action.inputs




def _listing(names: Iterable[str], limit: int = 4) -> str:
    names = sorted(set(names))
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:limit]) + f", and {len(names) - limit} more"


def _who(labels: list[str], total: int) -> str:
    return ", ".join(sorted(labels)) if len(labels) <= 3 else f"{len(labels)} of {total} entries"


def _site_text(index: SourceIndex, site: Site, reach: dict) -> str:
    on_path = ("func", site.module, site.func) in reach
    return f"{_site_name(index, site.module, site.func)} ({site.how}; {'on' if on_path else 'not on'} the planning path)"


def _setting_result(index: SourceIndex, row: SettingRow, reach: dict) -> tuple[str, str]:
    """(verdict, detail) of one setting or flag."""
    if not row.trace.sites:
        ends = sorted(row.trace.ends)
        detail = "stops at " + _listing(ends, 3) if ends else "no code reads it"
        return "never read", detail
    on_path = [s for s in row.trace.sites if ("func", s.module, s.func) in reach]
    sites = sorted(row.trace.sites, key=lambda s: (s.module, s.func, s.how))
    shown = "; ".join(_site_text(index, s, reach) for s in sites[:2]) + (f"; and {len(sites) - 2} more" if len(sites) > 2 else "")
    return ("read" if on_path else "read, but not on the planning path"), shown


def build_report(data, seconds: float = TARGET_SECONDS, src_root: Path = SRC, log: Callable[[str], None] = lambda text: None) -> str:
    from crafting_system.abstraction import Goal
    from crafting_system.actions import kinds
    from crafting_system.cli._plan import PlanError, make_plan
    from crafting_system.data import PIN
    from crafting_system.prices import load_price_file

    started = time.perf_counter()
    index = SourceIndex(src_root)
    log(f"source indexed: {len(index.modules)} modules, {len(index.funcs)} functions")
    reach = index.reachable_from([("func", module, name) for module, name in ENTRY_POINTS if ("func", module, name) in index.funcs])
    probes = probe_targets(data, seconds)
    log(f"{len(probes)} planner-entry runs done at {time.perf_counter() - started:.1f} s")
    all_kinds = kinds()

    offered: dict[str, dict[str, int]] = defaultdict(dict)  # kind -> probe label -> offers
    for probe in probes:
        if probe.outcome == "plans":
            for name, count in offered_kinds(probe).items():
                offered[name][probe.label] = count

    plain = [p for p in probes if not p.option]
    planner_kinds = [k for k in all_kinds if k.planner]
    closed_kinds = [k for k in all_kinds if not k.planner]
    reachable = [k for k in planner_kinds if k.name in offered]
    idle = [k for k in planner_kinds if k.name not in offered]
    settings = settings_rows(index)
    planned = [p for p in probes if not p.option and p.outcome == "plans"]
    first = planned[0] if planned else None
    strands_refusal = ""  # what `make_plan` says when Memory Strands are turned on, the one setting that is read and then refuses
    if first is not None:
        done, result = run_with_limit(lambda: make_plan(data, first.target, load_price_file(DEFAULT_PRICES), solve_it=False, strands=True), seconds)  # type: ignore[arg-type]
        strands_refusal = first_sentence(str(result)) if isinstance(result, PlanError) else ""
    refusing = [row for row in settings if row.name in STRANDS_KEYS and row.trace.sites and strands_refusal]

    out: list[str] = []
    out.append("# Reachability report")
    out.append("")
    out.append(
        "What a plan can reach today, read from the planner's own code (ticket #414, audit #396 class 3). Made by "
        "`.github/scripts/reachability_report.py`; the committed copy is `tests/golden/reachability.md`, and a test fails with a "
        "diff when this text changes, so a kind that becomes reachable shows up in review. Nothing here solves a plan."
    )
    out.append("")
    out.append(f"- Game data: repoe-fork {PIN.version} (commit {PIN.commit[:8]}).")
    out.append(
        f"- Targets: the {len(plain)} files of `examples/targets/`, each through `make_plan(..., solve_it=False)` (the gates, `offers_for`, "
        "the pricing and the abstraction, nothing solved), and each start option `vendor_recipe_starts` lists for it."
    )
    out.append(
        f"- Prices: `{DEFAULT_PRICES.relative_to(ROOT).as_posix()}`, or the target's own `price_file`; they only decide which offers are dropped for lack of a price."
    )
    out.append(f"- A run of the entry that outlasts `--target-seconds` is reported as \"{TOO_SLOW}\" ({sum(p.outcome == TOO_SLOW for p in probes) or 'none'} did).")
    out.append("")

    out.append("## Summary")
    out.append("")
    refused = [p for p in plain if p.outcome == "refused"]
    slow = [p for p in plain if p.outcome == TOO_SLOW]
    read = [r for r in settings if r.trace.sites]
    never = [r for r in settings if not r.trace.sites]
    summary_rows = [
        ["Action kinds in the catalog", len(all_kinds)],
        ["- with `planner=False` (no plan can use them)", len(closed_kinds)],
        ["- with `planner=True`", len(planner_kinds)],
        ["- `planner=True` and offered by at least one target (reachable)", len(reachable)],
        ["- `planner=True` and offered by no target", len(idle)],
        ["Benchmark targets", len(plain)],
        ["- the planner entry plans them", len(planned)],
        ["- the planner entry refuses them", len(refused)],
        [f"- {TOO_SLOW}", len(slow)],
        ["Settings and flags the planner accepts", len(settings)],
        ["- read by some code", len(read)],
        ["- never read", len(never)],
        ["- read, and turned on they make `make_plan` refuse every plan", len(refusing)],
    ]
    out.extend(table(["", "Count"], summary_rows))
    out.append("")
    out.append(
        f"Kinds that no target is offered: {len(closed_kinds) + len(idle)} of {len(all_kinds)} "
        f"({len(closed_kinds)} closed by `planner=False`, {len(idle)} planner kinds that no benchmark target reaches)."
    )
    out.append("")

    # -- 1. kinds
    out.append("## 1. Action kinds")
    out.append("")
    out.append(
        "One row per kind of `actions.catalog`, in catalog order. *Offered by* lists the targets whose planner entry offers an action "
        "of the kind after the filters and the pricing. *Why not* is what the code says: `why_not` of a `planner=False` kind, "
        "and for a planner kind the first gate or filter that removes it, with the targets it removes it for."
    )
    out.append("")
    start_items = [p.target.start_item for p in plain if p.target is not None]
    rows = []
    for entry in all_kinds:
        flags = [
            name
            for name, on in (
                ("opt-in", entry.opt_in),
                ("needs strands", entry.needs_strands),
                ("corrupting", entry.corrupting),
                ("burns", entry.burns),
            )
            if on
        ]
        if entry.applies_only_to:
            flags.append(f"only: {entry.applies_only_to}")
        if entry.reads_item_state_while_not_planner:
            flags.append(f"reads: {entry.reads_item_state_while_not_planner}")
        who = offered.get(entry.name, {})
        if who:
            plain_ids = sorted({label for label in who if " (" not in label})
            via_recipe = sorted({label.split(" (")[0] + " (recipe start)" for label in who if " (" in label and label.split(" (")[0] not in plain_ids})
            offered_by = f"all {len(plain)}" if len(plain_ids) == len(plain) else _listing([*plain_ids, *via_recipe], 20)
            why = ""
        elif not entry.planner:
            taking = 0
            listed_on = 0
            for item in start_items:
                try:
                    found = list(entry.members(data, item))
                except Exception:  # noqa: BLE001
                    found = []
                listed_on += bool(found)
                taking += any(takes_inputs(a) for a in found)
            why = f"`planner=False`: {entry.why_not}"
            if taking:
                why += f"; it takes donor items, and `make_plan` builds the abstraction with `allow_inputs=False` ({taking} of {len(start_items)} start items list such actions)"
            if not listed_on:
                why += "; the kind lists no action for any benchmark start item"
            offered_by = "none"
        else:
            reasons: dict[str, list[str]] = defaultdict(list)
            for probe in probes:
                reasons[why_not_offered(data, entry, probe)].append(probe.label)
            why = "; ".join(f"{reason} ({_who(labels, len(probes))})" for reason, labels in sorted(reasons.items()))
            offered_by = "none"
        rows.append([f"`{entry.name}`", "yes" if entry.planner else "**no**", ", ".join(flags), offered_by, why, KIND_FINDINGS.get(entry.name, "")])
    out.extend(table(["Kind", "Planner", "Flags", "Offered by", "Why not", "Audit"], rows))
    out.append("")

    # -- 2. targets
    out.append("## 2. The planner entry, target by target")
    out.append("")
    rows = []
    for probe in probes:
        if probe.outcome == "plans":
            plan = probe.plan
            kinds_here = offered_kinds(probe)
            restart = sum(1 for priced in plan.offers if priced.label == "restart")  # type: ignore[attr-defined]
            with_inputs = sum(1 for priced in plan.offers if priced.offer.inputs)  # type: ignore[attr-defined]
            names = probe.target.actions  # type: ignore[attr-defined]
            rows.append(
                [
                    probe.label,
                    "plans",
                    f"{len(names)} names" if names is not None else "no key",
                    len(plan.offers) - restart,  # type: ignore[attr-defined]
                    sum(len(limit.labels) for limit in plan.limits if limit.kind == "unpriced"),  # type: ignore[attr-defined]
                    with_inputs,
                    len(kinds_here),
                    _listing(sorted(kinds_here), 40),
                ]
            )
        else:
            rows.append([probe.label, f"{probe.outcome}: {first_sentence(probe.message)}", "", "", "", "", "", ""])
    out.extend(table(["Target", "Entry", "`actions:`", "Offers", "Dropped (no price)", "Offers with donor items", "Kinds", "Kinds offered"], rows))
    out.append("")

    # -- 3. gates
    out.append("## 3. What closes the entry")
    out.append("")
    out.append("The refusals at the top of `make_plan`, as the code states them (the condition, then the message):")
    out.append("")
    gate_rows = []
    for condition, message in entry_gates(index):
        hit = [p.label for p in probes if p.outcome == "refused" and p.message.startswith(message.split("{")[0][:50]) and message.split("{")[0]]
        gate_rows.append([f"`{condition}`", message, _listing(hit, 14) or "no benchmark target"])
    out.extend(table(["Condition", "Message", "Benchmark targets it refuses"], gate_rows))
    out.append("")
    for text in closed_inputs(index):
        out.append(f"- `{text}`: an action that consumes other items is refused by the kernel, so the Awakener's Orb and the recombinator cannot be planned.")
    if first is not None:
        out.append(f"- `memory_strands` on (`--strands`, or the setting): `make_plan` says \"{strands_refusal or 'nothing'}\"")
    corrupting = sum(
        1
        for probe in probes
        if probe.outcome == "plans"
        for priced in probe.plan.offers  # type: ignore[attr-defined]
        if priced.label != "restart" and priced.offer.action.adds(data, probe.target.start_item).corrupts  # type: ignore[attr-defined]
    )
    takers = [p.label for p in probes if p.target is not None and Goal.from_target(p.target).takes_corrupted]  # type: ignore[arg-type]
    out.append(f"- Targets that take a corrupted item (`allow_corrupted`, or a corrupted implicit): {_listing(takers, 14) or 'none'}; offers of a corrupting action over all entries: {corrupting}.")
    bloodstained = {}
    bloodstained_offered = 0
    for probe in planned:
        offered_actions = {priced.offer.action for priced in probe.plan.offers}  # type: ignore[attr-defined]
        for action in probe.members.get("fossil-set", []):
            if action.adds(data, probe.target.start_item).asked_only:  # type: ignore[attr-defined]
                bloodstained[probe.label] = bloodstained.get(probe.label, 0) + 1
                bloodstained_offered += action in offered_actions
    most = max(bloodstained.values(), default=0)
    out.append(
        f"- Fossil sets that use the Bloodstained Fossil (offered only when the target asks for a corrupted implicit): up to {most} listed for one start item, "
        f"{bloodstained_offered} offered by any entry."
    )
    out.append("")

    # -- 4. settings
    out.append("## 4. Settings and flags")
    out.append("")
    out.append(
        "Every key `crafting.toml` accepts and every flag of the plan and `benchmark` commands. An AST search of `src/` follows each value from "
        "where it is read (`config.key`, `args.flag`) through the parameters, fields and variables it is handed on to. *Read* means the value "
        "is compared, tested, formatted, calculated with or handed to code outside `src/`; storing it and passing it on is not reading. "
        "*Planning path* means the function that reads it is reached from `main`, `make_plan` or `plan_with_starts`."
    )
    out.append("")
    rows = []
    for row in settings:
        verdict, detail = _setting_result(index, row, reach)
        if row.name in STRANDS_KEYS and strands_refusal:
            detail += "; turned on, it makes `make_plan` refuse every plan (section 3)"
        rows.append([f"`{row.name}`", row.where, row.default, f"**{verdict}**" if verdict == "never read" else verdict, detail])
    out.extend(table(["Setting or flag", "Accepted in", "Default", "Verdict", "Where it is read, or where it stops"], rows))
    out.append("")
    extra = [(row, text) for row in settings if not row.trace.sites for text in row.named_consumers]
    if extra:
        out.append("Code that takes a never-read setting by its own name:")
        out.append("")
        for row, text in extra:
            out.append(f"- `{row.name}`: {text}")
        out.append("")
    unresolved = [(row, row.trace.unresolved) for row in settings if not row.trace.sites and row.trace.unresolved]
    for row, places in unresolved:
        out.append(f"- `{row.name}`: reads of an attribute with the same name on a receiver of unknown type, not counted: {_listing(places, 6)}.")
    if unresolved:
        out.append("")

    # -- 5. built modules
    out.append("## 5. Built modules")
    out.append("")
    out.append(
        "The public names of the modules the audit says are built and not wired. *Referenced by* lists the other modules of `src/` that name "
        "it (tests are not counted); *Planning path* says whether `main`, `make_plan` or `plan_with_starts` reaches it through such references."
    )
    out.append("")
    rows = []
    for what, module, findings in BUILT_MODULES:
        info = index.modules[module]
        names = [(n, f) for n, f in info.funcs.items() if not n.startswith("_")] + [(n, c) for n, c in info.classes.items() if not n.startswith("_")]
        for name, definition in sorted(names, key=lambda pair: pair[0]):
            refs = [r for r in index.referrers(definition.key) if r[1] != module]
            texts = [f"{index.modules[r[1]].rel}: {r[2]}" if r[0] != "mod" else f"{index.modules[r[1]].rel} (module level)" for r in refs]
            rows.append([what, f"`{name}`", f"`{info.rel}`", _listing(texts, 3) or "nothing", "yes" if definition.key in reach else "**no**", findings])
    out.extend(table(["Built module", "Name", "In", "Referenced by", "Planning path", "Audit"], rows))
    out.append("")

    # -- 6. target keys
    out.append("## 6. Target keys")
    out.append("")
    out.append(
        "The fields of the `Target` a YAML file fills in, and the modules outside `targets/` that read each one on a receiver known to be a `Target` "
        "(a parameter annotated `Target`, or named `target`). A key nothing reads is accepted and ignored."
    )
    out.append("")
    rows = [[f"`{field}`", _listing(readers, 5) or "**nothing**", note] for field, readers, note in target_field_rows(index)]
    out.extend(table(["Target field", "Read by", "Audit"], rows))
    out.append("")
    log(f"report built at {time.perf_counter() - started:.1f} s")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", metavar="FILE", help="where to write the report (default: print it)")
    parser.add_argument("--target-seconds", type=float, default=TARGET_SECONDS, help=f"a planner-entry run longer than this is reported as \"{TOO_SLOW}\" (default {TARGET_SECONDS:g})")
    parser.add_argument("--summary", action="store_true", help="also append the report to $GITHUB_STEP_SUMMARY")
    args = parser.parse_args(argv)
    from crafting_system.data import load_game_data

    began = time.perf_counter()
    data = load_game_data()
    text = build_report(data, args.target_seconds, log=lambda line: print(line, file=sys.stderr, flush=True)) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if args.summary and summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    print(f"reachability report: {time.perf_counter() - began:.1f} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
