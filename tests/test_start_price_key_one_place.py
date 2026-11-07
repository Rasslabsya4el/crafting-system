"""The price key of a start item and its trade category are derived in one place of `src` (#471, OR-3, OR-26).

* A scan of `src`: the named functions that build a price name for an item are the ones listed below, each with its reason. Any other function
  that builds a key fails the scan, so a key is never typed a second time. A builder is, in a function (or at the top of a module):
  a call of `base_price_name` or `BuySpec` (also under an alias: `from m import base_price_name as name`, `name = base_price_name`),
  an f-string that makes an "item level" part of a key (`f"item level {low}-{high}"`), or `dataclasses.replace(x, name=...)`, which renames a
  buy spec without going through the key. The scan names functions, not whole modules: a new function in a listed module fails it too.
* The trade category of an item class is `targets.start_buy.TRADE_CATEGORY`. `tests/independent/ladder.py` keeps its own copy (that folder
  imports nothing from `crafting_system`), and this test holds the two equal, on every item class of the committed targets and on the table.
"""

import ast
import re
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from independent.ladder import TRADE_CATEGORY as INDEPENDENT_CATEGORY

from crafting_system.targets import load_target
from crafting_system.targets.start_buy import TRADE_CATEGORY

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "crafting_system"
TARGETS = ROOT / "examples" / "targets"

# "module path under src/crafting_system::function" -> why it may build a price name or a spec. Every one but the first is a name that is not derived
# from a target's start item. `<module>` is the code at the top of a module, outside every function.
NAME_BUILDERS = {
    "targets/start_buy.py::buy_spec_of": "the one place: the buy spec of a start item, named by its key",
    "targets/start_buy.py::_key": "the one place: the price key of a start item, made from the target's buy spec",
    "targets/start_buy.py::base_line_name": "the one place: the price name of the Normal base a vendor recipe buys",
    "targets/start_buy.py::ninja_line_name": "the one place: the name a poe.ninja line of that base has, to refuse it where the bases of its name differ",
    "prices/price_names.py::canonical_price_name": "the format of the poe.ninja-style base name: its canonical form",
    "prices/ninja_items.py::_stash_line": "names a poe.ninja stash line by the line's own name, level and variant (no target is involved)",
    "prices/trade_query.py::_parse_spec": "reads a spec file whose name the file gives; it derives nothing",
    "cli/_decide.py::decide": "`replace(level, name=...)` renames a search level, not a buy spec",
    "cli/_route_card.py::_properties": "the words of the route card's item line, not a price name",
    "cli/_route_trade.py::_accepts": "the lines of the page that say what a buy spec accepts, not a price name",
    "prices/query_compare.py::_level_words": "the words that say how two stored searches differ, not a price name",
}
BUILDERS = {
    "targets/start_buy.py::_key": "the one place: the price key of a start item is made here, from the target's buy spec",
    "targets/start_buy.py::buy_spec_of": "the one place: the buy spec of a start item, and the key as its name",
    "targets/start_buy.py::base_line_name": "the one place: the price name of the Normal base a vendor recipe buys",
    "targets/start_buy.py::ninja_line_name": "the one place: the name a poe.ninja line of that base has, to refuse it where the bases of its name differ",
    "prices/price_names.py::canonical_price_name": "the format of the poe.ninja-style base name: its canonical form",
    "prices/ninja_items.py::<ninja_items_function>": "names a poe.ninja stash line by the line's own name, level and variant (no target is involved)",
    "prices/trade_query.py::load_buy_spec": "reads a spec file whose name the file gives; it derives nothing",
}
BUILDERS = {"base_price_name", "BuySpec"}
_KEY_WORDS = re.compile(r"item level|\bto\b|or more|or less")


def _static_text(node: ast.JoinedStr) -> str:
    return "".join(part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str))


def _is_item_level_key(node: ast.JoinedStr) -> bool:
    """An f-string that says only "item level" and its numbers (`item level {a}`, `item level {a}-{b}`, `item level {a} or more`): a key part.

    A message that says more (`the item level {x} is outside ...`) is not.
    """
    text = _static_text(node)
    return "item level" in text and not re.sub(r"[\s,;:()\-]", "", _KEY_WORDS.sub("", text))


def _aliases(tree: ast.AST) -> dict[str, str]:
    """Local name -> the name it stands for, from `from m import x as y` and `y = x` (one step, the last binding wins)."""
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found.update({each.asname: each.name for each in node.names if each.asname})
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            found.update({target.id: node.value.id for target in node.targets if isinstance(target, ast.Name)})
    return found


def builders_in(source: str) -> dict[str, set[str]]:
    """The functions of `source` that build a price name: `{qualified function name: the detectors that fired}`."""
    tree = ast.parse(source)
    aliases = _aliases(tree)
    found: dict[str, set[str]] = {}
    path: list[str] = []

    def visit(node: ast.AST) -> None:
        is_scope = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        if is_scope:
            path.append(node.name)
        here = ".".join(path) or "<module>"
        if isinstance(node, ast.Call):
            function = node.func
            name = function.attr if isinstance(function, ast.Attribute) else getattr(function, "id", "")
            name = aliases.get(name, name)
            if name in BUILDERS:
                found.setdefault(here, set()).add(name)
            if name == "replace" and any(keyword.arg == "name" for keyword in node.keywords):
                found.setdefault(here, set()).add("replace(name=)")
        if isinstance(node, ast.JoinedStr) and _is_item_level_key(node):
            found.setdefault(here, set()).add("item-level f-string")
        for child in ast.iter_child_nodes(node):
            visit(child)
        if is_scope:
            path.pop()

    visit(tree)
    return found


def test_only_the_listed_functions_of_src_build_a_price_name():
    builders = {
        f"{path.relative_to(SRC).as_posix()}::{function}"
        for path in SRC.rglob("*.py")
        for function in builders_in(path.read_text(encoding="utf-8"))
    }

    assert builders == set(NAME_BUILDERS), sorted(builders ^ set(NAME_BUILDERS))


# -- each detector is red on a snippet that builds a key where it should not -------------------------------------


@pytest.mark.parametrize(
    ("snippet", "detector"),
    [
        ("def key(base):\n    return base_price_name(base, 84)\n", "base_price_name"),
        ("from prices import base_price_name as price_of\n\ndef key(base):\n    return price_of(base, 84)\n", "base_price_name"),
        ("import prices\n\ndef key(base):\n    return prices.base_price_name(base, 84)\n", "base_price_name"),
        ("make = base_price_name\n\ndef key(base):\n    return make(base, 84)\n", "base_price_name"),
        ("def spec():\n    return BuySpec(name='x')\n", "BuySpec"),
        ("from m import BuySpec as Wanted\n\ndef spec():\n    return Wanted(name='x')\n", "BuySpec"),
        ("def key(base, low):\n    return f'{base}, item level {low}'\n", "item-level f-string"),
        ("def key(base, low, high):\n    return f'{base}, item level {low}-{high}'\n", "item-level f-string"),
        ("def key(low):\n    return f'item level {low} or more'\n", "item-level f-string"),
        ("import dataclasses\n\ndef rename(spec):\n    return dataclasses.replace(spec, name='x')\n", "replace(name=)"),
        ("from dataclasses import replace\n\ndef rename(spec):\n    return replace(spec, name='x')\n", "replace(name=)"),
        ("from dataclasses import replace as swap\n\ndef rename(spec):\n    return swap(spec, name='x')\n", "replace(name=)"),
    ],
)
def test_each_detector_of_the_scan_is_red_on_a_snippet_that_builds_a_key(snippet, detector):
    assert detector in builders_in(snippet).get("key" if "def key" in snippet else "spec" if "def spec" in snippet else "rename", set())


@pytest.mark.parametrize(
    "snippet",
    [
        "def fail(x):\n    raise ValueError(f'the item level {x} is outside 1 to 100')\n",  # a message says more than the item level
        "def key(base):\n    return base.name\n",
        "from dataclasses import replace\n\ndef widen(spec):\n    return replace(spec, ilvl_min=1)\n",
    ],
)
def test_the_scan_stays_quiet_on_code_that_builds_no_key(snippet):
    assert builders_in(snippet) == {}


def test_a_new_function_in_a_listed_module_fails_the_scan():
    """The scan names functions: the listed `_key` passes, a second function next to it in the same module does not."""
    found = builders_in("def _key(base):\n    return base_price_name(base, 1)\n\ndef another(base):\n    return base_price_name(base, 2)\n")

    assert set(found) == {"_key", "another"}


def test_the_callers_that_look_a_start_price_up_get_the_key_from_the_one_place():
    """The modules that read a start price name the key through `start_price_key` / `buy_spec_of` / `base_line_name`, never a typed or built one."""
    callers = {
        "cli/_plan.py": "buy_spec_of",
        "cli/_benchmark.py": "start_price_key",
        "cli/_starts.py": "start_price_key",
        "cli/_start_options.py": "base_line_name",
    }
    for module, function in callers.items():
        called = {
            getattr(node.func, "attr", getattr(node.func, "id", ""))
            for node in ast.walk(ast.parse((SRC / module).read_text(encoding="utf-8")))
            if isinstance(node, ast.Call)
        }
        assert function in called, (module, function)


def test_the_trade_category_table_is_the_independent_one():
    assert TRADE_CATEGORY == INDEPENDENT_CATEGORY


def test_every_item_class_of_the_committed_targets_has_the_same_trade_category_in_src_and_in_the_independent_copy():
    data = real_game_data()
    classes = set()
    for path in sorted(TARGETS.glob("*.yaml")):
        classes.add(data.base_items[load_target(path, data).base_id].item_class)

    assert classes, "no committed target was read"
    for item_class in sorted(classes):
        assert TRADE_CATEGORY.get(item_class) == INDEPENDENT_CATEGORY.get(item_class), item_class  # a class in neither (the jewel of J01, a given start) agrees too


@pytest.mark.parametrize("item_class", sorted(INDEPENDENT_CATEGORY))
def test_each_class_of_the_independent_table_is_in_src(item_class):
    assert TRADE_CATEGORY[item_class] == INDEPENDENT_CATEGORY[item_class]
