"""Static check (ADR-0004): code refers to rules only as `get_rule("<id>")` with a registered id.

The check reads the source of the package with `ast`, so it needs no import and sees code that
no test runs. `get_rule` must be called by that name with one string literal; anything the check
cannot read (a variable, an f-string, another name for the function) is reported too.
"""

import ast
from pathlib import Path

import pytest

import crafting_system
from crafting_system.rules import load_registry

FUNCTION = "get_rule"


def find_rule_reference_problems(source: str, filename: str, known_ids: set[str]) -> list[str]:
    """One line `filename:line: problem` per bad reference to a rule in `source`."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as error:
        return [f"{filename}:{error.lineno or 1}: the file does not parse: {error.msg}"]

    problems: list[str] = []
    called: set[int] = set()  # ids of the nodes that are the function of a call

    def report(node: ast.AST, text: str) -> None:
        problems.append(f"{filename}:{node.lineno}: {text}")  # type: ignore[attr-defined]

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _names_get_rule(node.func):
            called.add(id(node.func))
            _check_call(node, known_ids, report)
        elif isinstance(node, ast.Call) and _is_getattr_of_get_rule(node):
            report(node, f"{FUNCTION} must not be fetched with getattr; call {FUNCTION}(\"<id>\")")
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == FUNCTION and alias.asname not in (None, FUNCTION):
                    report(node, f"{FUNCTION} is imported as {alias.asname}; import it by its name")
    for node in ast.walk(tree):
        if _names_get_rule(node) and id(node) not in called:
            report(node, f"{FUNCTION} must be called as {FUNCTION}(\"<id>\"), not used as a value")
    return sorted(problems, key=_line_number)


def _line_number(problem: str) -> int:
    return int(problem.split(":")[1])


def _names_get_rule(node: ast.AST) -> bool:
    """Whether `node` is the bare name `get_rule` or an attribute access ending in it."""
    return (isinstance(node, ast.Name) and node.id == FUNCTION) or (
        isinstance(node, ast.Attribute) and node.attr == FUNCTION
    )


def _is_getattr_of_get_rule(call: ast.Call) -> bool:
    """Whether `call` is `getattr(<anything>, "get_rule", ...)`."""
    return (
        isinstance(call.func, ast.Name)
        and call.func.id == "getattr"
        and len(call.args) >= 2
        and isinstance(call.args[1], ast.Constant)
        and call.args[1].value == FUNCTION
    )


def _check_call(call: ast.Call, known_ids: set[str], report) -> None:
    arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
    keywords_ok = all(keyword.arg == "rule_id" for keyword in call.keywords)
    argument = arguments[0] if len(arguments) == 1 and keywords_ok else None
    if not (isinstance(argument, ast.Constant) and isinstance(argument.value, str)):
        report(call, f"{FUNCTION} needs exactly one string literal as the rule id")
    elif argument.value not in known_ids:
        report(call, f"unknown rule id {argument.value!r}")


def find_package_reference_problems(package_dir: Path, known_ids: set[str]) -> list[str]:
    """Problems in every `.py` file under `package_dir`."""
    problems = []
    for path in sorted(package_dir.rglob("*.py")):
        name = path.relative_to(package_dir).as_posix()
        source = path.read_text(encoding="utf-8")
        problems.extend(find_rule_reference_problems(source, name, known_ids))
    return problems


KNOWN = {"fam.thing", "fam.other"}


def problems_of(source: str) -> list[str]:
    return find_rule_reference_problems(source, "mod.py", KNOWN)


# --- allowed forms ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        'THING = get_rule("fam.thing")',
        "THING = get_rule('fam.other')",
        'THING = get_rule(rule_id="fam.thing")',
        'THING = get_rule("fam." "thing")',  # adjacent literals are one literal for the parser
        'THING = registry.get_rule("fam.thing")',
        'THING = crafting_system.rules.get_rule("fam.thing")',
        'def f():\n    return get_rule("fam.thing").value',
        'x = [get_rule("fam.thing"), get_rule("fam.other")]',
        "from crafting_system.rules import get_rule",
        "from .registry import get_rule, load_registry",
        "from crafting_system.rules import get_rule as get_rule",
        '__all__ = ["get_rule", "load_registry"]',
        "def get_rule(rule_id):\n    return rule_id",
        'DOC = "call get_rule(some_variable) like this"',
        '"""Docs: get_rule(name)."""',
        "get_rules = []\nmy_get_rule = 1\nx = my_get_rule",
        "import os",
        "",
    ],
)
def test_allowed_forms_are_not_reported(source):
    assert problems_of(source) == []


# --- unknown id (the ticket's "code refers to an unknown id") -----------------------------------


def test_a_known_id_passes():
    assert problems_of('THING = get_rule("fam.thing")') == []


def test_an_unknown_id_is_reported_with_file_line_and_id():
    problems = problems_of('x = 1\nTHING = get_rule("fam.nothing")')

    assert len(problems) == 1
    assert problems[0].startswith("mod.py:2:")
    assert "fam.nothing" in problems[0]


def test_an_unknown_id_in_a_method_call_is_reported():
    problems = problems_of('THING = rules.get_rule("fam.nothing")')

    assert len(problems) == 1
    assert "fam.nothing" in problems[0]


def test_every_bad_reference_is_reported_separately():
    source = 'a = get_rule("x.y")\nb = get_rule("fam.thing")\nc = get_rule("p.q")'

    problems = problems_of(source)

    assert [problem.split(":")[1] for problem in problems] == ["1", "3"]


# --- the forms the check cannot read ------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "THING = get_rule(rule_id)",
        'THING = get_rule(f"fam.{name}")',
        'THING = get_rule("fam." + name)',
        "THING = get_rule(*names)",
        "THING = get_rule(**options)",
        "THING = get_rule()",
        'THING = get_rule("fam.thing", "fam.other")',
        'THING = get_rule("fam.thing", extra=1)',
        "THING = get_rule(42)",
        "THING = get_rule(None)",
        "THING = get_rule(b'fam.thing')",
        'THING = rules.get_rule(name)',
        'THING = get_rule(rule_id=name)',
    ],
)
def test_a_call_without_exactly_one_string_literal_is_reported(source):
    problems = problems_of(source)

    assert len(problems) == 1
    assert problems[0].startswith("mod.py:1:")


# --- other names and other uses of the function ------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "from crafting_system.rules import get_rule as g",
        "from .registry import get_rule as lookup",
        "from crafting_system.rules.registry import (\n    get_rule as g,\n)",
    ],
)
def test_importing_get_rule_under_another_name_is_reported(source):
    problems = problems_of(source)

    assert len(problems) == 1
    assert problems[0].startswith("mod.py:")


@pytest.mark.parametrize(
    "source",
    [
        "lookup = get_rule",
        "lookup = rules.get_rule",
        "THINGS = list(map(get_rule, names))",
        "register(get_rule)",
        "x = [get_rule]",
        "get_rule = other",
        "rules.get_rule = other",
        "def f(fn=get_rule):\n    return fn",
        "@get_rule\ndef f():\n    pass",
        "import functools\nlookup = functools.partial(get_rule)",
        'lookup = getattr(rules, "get_rule")',
        'THING = getattr(rules, "get_rule")("fam.thing")',
        'lookup = getattr(rules, "get_rule", None)',
        'import crafting_system.rules as r\nfn = getattr(r, "get_rule")',
    ],
)
def test_using_get_rule_as_something_other_than_a_called_function_is_reported(source):
    problems = problems_of(source)

    assert len(problems) >= 1
    assert all(problem.startswith("mod.py:") for problem in problems)


def test_a_file_that_does_not_parse_is_reported():
    problems = problems_of("def broken(:\n")

    assert len(problems) == 1
    assert problems[0].startswith("mod.py:1:")


# --- the walker -----------------------------------------------------------------------------------


def test_the_walker_reports_the_file_of_each_problem(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "ok.py").write_text('A = get_rule("fam.thing")\n', encoding="utf-8")
    (tmp_path / "sub" / "bad.py").write_text('A = get_rule("fam.nothing")\n', encoding="utf-8")

    problems = find_package_reference_problems(tmp_path, KNOWN)

    assert len(problems) == 1
    assert problems[0].startswith("sub/bad.py:1:")


# --- the real package -----------------------------------------------------------------------------


def test_real_package_refers_only_to_registered_rule_ids():
    package_dir = Path(crafting_system.__file__).parent

    problems = find_package_reference_problems(package_dir, set(load_registry()))

    assert problems == []
