"""The lists of tests that wait for #1101 (`conftest.WAITS_FOR_1101`, `conftest.RERECORD_FOR_1101`, #886) name tests that exist.

A pattern of `WAITS_FOR_1101` is an xfail that is not run, so nothing else would notice one that names a test renamed or moved away. Each
pattern names its file, and its test function and its parameter where it gives them; the file must exist, the function must be defined in
it, and the parameter must be written in it.
"""

import ast
import re
from pathlib import Path

import pytest
from conftest import RERECORD_FOR_1101, WAITS_FOR_1101

ROOT = Path(__file__).resolve().parents[1]


def _parts(pattern: str) -> tuple[str, str, str | None]:
    path, _, rest = pattern.partition("::")
    match = re.fullmatch(r"([^[]*?)(?:\[\[\](.*)\[\]\])?", rest)
    assert match, pattern
    return path, match.group(1), match.group(2)


@pytest.mark.parametrize("pattern", [*WAITS_FOR_1101, *RERECORD_FOR_1101])
def test_each_pattern_names_a_file_a_test_and_a_parameter_that_exist(pattern):
    path, name, parameter = _parts(pattern)
    source = (ROOT / path).read_text(encoding="utf-8")
    tests = [node.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    prefix = name.rstrip("*")
    assert any(test == name or (name.endswith("*") and test.startswith(prefix)) for test in tests), pattern
    if parameter is not None:
        assert all(part in source for part in parameter.split("*") if part), pattern
