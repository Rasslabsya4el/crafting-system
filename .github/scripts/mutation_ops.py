"""The mutation operators of the measurement chain (ticket #399, step 5): numbered mutants of one source file.

A mutant is one small change of the source text: its place (line, columns), the operator that made it, the
original text of the node and the text that replaces it. The module touches no file: `find_mutants(source)` lists
the mutants, `apply_mutant(source, mutant)` returns the mutated source. The same source gives the same list in the
same order, so a mutant can be named by its number in the plan.

Only code that a test can reach is mutated, and only the code inside function bodies: a line of a function runs in
the context of the test that calls it, which is what the coverage data (`dynamic_context = test_function`) records.
Module and class level statements run once at import, in no test, so they are skipped. Also skipped: docstrings,
logging and print calls, `raise` statements (the error text), f-strings, annotations, `if TYPE_CHECKING`, the
`__repr__`/`__str__` methods, and any statement with a `pragma: no cover` or `no mutate` comment.

Operators (one mutant per place and per replacement):
  compare   `<`->`<=` and `>`, `<=`->`<` and `>=`, and the same for `>`, `>=`; `==`<->`!=`, `is`<->`is not`,
            `in`<->`not in` (each operator of a chain)
  arith     `+`<->`-`, `*`<->`/`, also as `+=`, `-=`, `*=`, `/=` (not where an operand is a string or a literal list)
  const     an integer constant n becomes n + 1, and n - 1 when n is 1 or more
  bool      `True`<->`False`
  boolop    `and`<->`or`
  not       `not x` becomes `x`
  return    `return x` becomes the neutral value of the function's annotated type (0, 0.0, False, "", [], (), {},
            set(), frozenset(), Fraction(0), None for `X | None`); not where `x` is a constant already

The edit replaces the exact source text of one node with `ast.unparse` of the changed node, so the rest of the file
and its line numbers stay as they are. A mutant whose edited file does not parse is dropped.
"""

import ast
from dataclasses import asdict, dataclass

COMPARE_FLIPS = {  # each operator: the operators it becomes (the boundary, then the direction)
    ast.Lt: (ast.LtE, ast.Gt), ast.LtE: (ast.Lt, ast.GtE), ast.Gt: (ast.GtE, ast.Lt), ast.GtE: (ast.Gt, ast.LtE),
    ast.Eq: (ast.NotEq,), ast.NotEq: (ast.Eq,), ast.Is: (ast.IsNot,), ast.IsNot: (ast.Is,),
    ast.In: (ast.NotIn,), ast.NotIn: (ast.In,),
}  # fmt: skip
ARITH_SWAPS = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
LOG_NAMES = frozenset({"log", "logger", "logging", "warnings", "print", "pprint"})
SKIPPED_METHODS = frozenset({"__repr__", "__str__", "__format__", "__rich_repr__"})
NO_MUTATE_MARKS = ("pragma: no cover", "no mutate")
LITERAL_CONTAINERS = (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.ListComp, ast.SetComp, ast.DictComp, ast.JoinedStr)
ATOMS = (ast.Name, ast.Attribute, ast.Call, ast.Subscript, ast.Constant)
NEUTRAL_BY_ANNOTATION = {
    "int": "0", "float": "0.0", "bool": "False", "str": '""', "bytes": 'b""', "list": "[]", "tuple": "()",
    "dict": "{}", "set": "set()", "frozenset": "frozenset()",
}  # fmt: skip


@dataclass(frozen=True)
class Mutant:
    """One change: `original` (the text of the node at line:col .. end_line:end_col) becomes `mutated`.

    Columns count UTF-8 bytes, as `ast` does. `line` is the line of the node, `stmt_line` the first line of the
    statement that holds it: the line the coverage data knows.
    """

    file: str
    line: int
    stmt_line: int
    col: int
    end_line: int
    end_col: int
    operator: str
    original: str
    mutated: str

    def to_json(self) -> dict:
        return asdict(self)


def _segment(source_lines: list[str], node: ast.AST) -> str:
    return ast.get_source_segment("\n".join(source_lines), node) or ""


def _is_log_call(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return False
    target = statement.value.func
    while isinstance(target, ast.Attribute):
        target = target.value
    return isinstance(target, ast.Name) and target.id in LOG_NAMES


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _neutral_value(returns: ast.expr | None, module_names: frozenset[str]) -> str | None:
    """The source text of the neutral value of an annotated return type, None when there is no safe one."""
    if returns is None:
        return None
    if isinstance(returns, ast.BinOp) and isinstance(returns.op, ast.BitOr):
        sides = [ast.unparse(returns.left), ast.unparse(returns.right)]
        return "None" if "None" in sides else None
    if isinstance(returns, ast.Constant):
        return None
    if isinstance(returns, ast.Subscript):
        base = ast.unparse(returns.value)
        return "None" if base in ("Optional", "typing.Optional") else NEUTRAL_BY_ANNOTATION.get(base)
    name = ast.unparse(returns)
    if name == "Fraction" and "Fraction" in module_names:
        return "Fraction(0)"
    return NEUTRAL_BY_ANNOTATION.get(name)


class _Collector:
    """Walks a module and gathers the mutants of the function bodies, in no particular order."""

    def __init__(self, source: str, file: str):
        self.source = source
        self.file = file
        self.lines = source.split("\n")
        self.found: list[Mutant] = []
        tree = ast.parse(source)
        self.module_names = frozenset(
            alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names
        )
        self._module_body(tree.body)

    def _marked(self, statement: ast.stmt) -> bool:
        first, last = statement.lineno, statement.end_lineno or statement.lineno
        compound = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Match)
        if isinstance(statement, compound):
            last = first  # a compound statement: its first line only; the body statements are checked one by one
        return any(mark in self.lines[line - 1] for line in range(first, last + 1) for mark in NO_MUTATE_MARKS)

    def _add(self, node: ast.AST, stmt_line: int, operator: str, mutated: str) -> None:
        original = _segment(self.lines, node)
        if not original or mutated == original:
            return
        self.found.append(
            Mutant(self.file, node.lineno, stmt_line, node.col_offset, node.end_lineno, node.end_col_offset, operator, original, mutated)
        )

    def _module_body(self, body: list[ast.stmt]) -> None:
        """Module and class level: only the functions inside are mutated."""
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._function(statement)
            elif isinstance(statement, ast.ClassDef):
                self._module_body(statement.body)
            elif isinstance(statement, ast.If):
                if not _is_type_checking(statement.test):
                    self._module_body(statement.body)
                self._module_body(statement.orelse)
            elif isinstance(statement, (ast.Try, ast.With, ast.For, ast.While)):
                for field in ("body", "orelse", "finalbody"):
                    self._module_body(getattr(statement, field, []))
                for handler in getattr(statement, "handlers", []):
                    self._module_body(handler.body)

    def _function(self, function: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if function.name in SKIPPED_METHODS or self._marked(function):
            return
        has_yield = any(isinstance(node, (ast.Yield, ast.YieldFrom)) for node in ast.walk(function))
        returns = None if has_yield else function.returns
        self._statements(function.body, function, returns, skip_first_docstring=True)

    def _statements(self, body, function, returns, skip_first_docstring=False) -> None:
        for index, statement in enumerate(body):
            if skip_first_docstring and index == 0 and isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                continue
            self._statement(statement, function, returns)

    def _statement(self, statement: ast.stmt, function, returns) -> None:
        if self._marked(statement):
            return
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._function(statement)
            return
        if isinstance(statement, ast.ClassDef):
            self._module_body(statement.body)
            return
        if isinstance(statement, (ast.Raise, ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Pass)) or _is_log_call(statement):
            return
        line = statement.lineno
        if isinstance(statement, ast.Return):
            self._return(statement, returns)
            if statement.value is not None:
                self._expression(statement.value, line)
            return
        if isinstance(statement, ast.AugAssign):
            self._augmented(statement)
            self._expression(statement.value, line)
            return
        if isinstance(statement, ast.AnnAssign):  # the annotation is skipped
            if statement.value is not None:
                self._expression(statement.value, line)
            return
        if isinstance(statement, ast.Assert):  # the message is skipped
            self._expression(statement.test, line)
            return
        if isinstance(statement, ast.If) and _is_type_checking(statement.test):
            return
        for field, value in ast.iter_fields(statement):
            if field in ("body", "orelse", "finalbody") and isinstance(value, list):
                self._statements(value, function, returns)
            elif field == "handlers":
                for handler in value:
                    self._statements(handler.body, function, returns)
            elif field == "cases":
                for case in value:
                    self._statements(case.body, function, returns)
            elif isinstance(value, ast.expr):
                self._expression(value, line)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.expr):
                        self._expression(item, line)
                    elif isinstance(item, ast.withitem):
                        self._expression(item.context_expr, line)
                    elif isinstance(item, ast.comprehension):
                        self._expression(item, line)

    def _return(self, statement: ast.Return, returns: ast.expr | None) -> None:
        if statement.value is None or isinstance(statement.value, ast.Constant):
            return
        neutral = _neutral_value(returns, self.module_names)
        if neutral is not None and ast.unparse(statement.value) != neutral:
            self._add(statement, statement.lineno, "return", f"return {neutral}")

    def _augmented(self, statement: ast.AugAssign) -> None:
        swap = ARITH_SWAPS.get(type(statement.op))
        if swap is None or _joins_sequences(statement.value):
            return
        mutated = ast.AugAssign(statement.target, swap(), statement.value)
        self._add(statement, statement.lineno, "arith", ast.unparse(mutated))

    def _expression(self, node: ast.AST, stmt_line: int) -> None:
        if isinstance(node, ast.JoinedStr):  # an f-string is text
            return
        if isinstance(node, ast.Lambda):
            self._expression(node.body, stmt_line)
            return
        if isinstance(node, ast.Compare):
            for index, operator in enumerate(node.ops):
                if _compares_text(node):
                    continue
                for flip in COMPARE_FLIPS.get(type(operator), ()):
                    ops = list(node.ops)
                    ops[index] = flip()
                    self._add(node, stmt_line, "compare", ast.unparse(ast.Compare(node.left, ops, node.comparators)))
        elif isinstance(node, ast.BinOp):
            swap = ARITH_SWAPS.get(type(node.op))
            if swap is not None and not _joins_sequences(node):
                self._add(node, stmt_line, "arith", ast.unparse(ast.BinOp(node.left, swap(), node.right)))
        elif isinstance(node, ast.BoolOp):
            swapped = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            self._add(node, stmt_line, "boolop", ast.unparse(ast.BoolOp(swapped, node.values)))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            inner = ast.unparse(node.operand)
            self._add(node, stmt_line, "not", inner if isinstance(node.operand, ATOMS) else f"({inner})")
        elif isinstance(node, ast.Constant):
            if node.value is True or node.value is False:
                self._add(node, stmt_line, "bool", repr(not node.value))
            elif type(node.value) is int:
                self._add(node, stmt_line, "const", str(node.value + 1))
                if node.value >= 1:
                    self._add(node, stmt_line, "const", str(node.value - 1))
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr_context):
                continue
            self._expression(child, stmt_line)


def _joins_sequences(node: ast.AST) -> bool:
    """Whether an operand of the arithmetic (down a chain of `+`) is a string or a literal container: `-` would only raise."""
    if isinstance(node, ast.BinOp):
        return _joins_sequences(node.left) or _joins_sequences(node.right)
    return isinstance(node, LITERAL_CONTAINERS) or _is_text(node)


def _is_text(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes))


def _compares_text(node: ast.Compare) -> bool:
    return any(_is_text(side) for side in [node.left, *node.comparators])


def _to_index(lines: list[str], line: int, col: int) -> int:
    """Offset in the text of `lines` joined by newlines for a (line, UTF-8 byte column) place."""
    before = sum(len(text) + 1 for text in lines[: line - 1])
    return before + len(lines[line - 1].encode("utf-8")[:col].decode("utf-8"))


def apply_mutant(source: str, mutant: Mutant) -> str:
    """The source with the mutant's node text replaced."""
    lines = source.split("\n")
    start = _to_index(lines, mutant.line, mutant.col)
    end = _to_index(lines, mutant.end_line, mutant.end_col)
    return source[:start] + mutant.mutated + source[end:]


def find_mutants(source: str, file: str = "<source>", check: bool = True) -> list[Mutant]:
    """All mutants of `source` in source order (line, column, operator, text); each one parses after its edit.

    `check=False` skips the parse of every edited file (the unit tests use it on tiny sources, the plan does not).
    """
    source = source.replace("\r\n", "\n")
    found = _Collector(source, file).found
    unique = {(m.line, m.col, m.end_line, m.end_col, m.operator, m.mutated): m for m in found}
    ordered = [unique[key] for key in sorted(unique, key=lambda key: (key[0], key[1], key[4], key[5], key[2], key[3]))]
    if not check:
        return ordered
    kept = []
    for mutant in ordered:
        try:
            ast.parse(apply_mutant(source, mutant))
        except SyntaxError:
            continue
        kept.append(mutant)
    return kept
