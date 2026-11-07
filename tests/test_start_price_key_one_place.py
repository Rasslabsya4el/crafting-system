"""The price key of a start item and its trade category are derived in one place of `src` (#471, OR-3, OR-26).

* A scan of `src`: the modules that build a price name for an item (`base_price_name`, a `BuySpec` with a name) are the ones listed below, each
  with its reason. Any other module that builds a key fails the scan, so a key is never typed a second time.
* The trade category of an item class is `targets.start_buy.TRADE_CATEGORY`. `tests/independent/ladder.py` keeps its own copy (that folder
  imports nothing from `crafting_system`), and this test holds the two equal, on every item class of the committed targets and on the table.
"""

import ast
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from independent.ladder import TRADE_CATEGORY as INDEPENDENT_CATEGORY

from crafting_system.targets import load_target
from crafting_system.targets.start_buy import TRADE_CATEGORY

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "crafting_system"
TARGETS = ROOT / "examples" / "targets"

# module (path under src/crafting_system) -> why it may build a price name or a spec; every one is a name that is not derived from a target's start item
# except `targets/start_buy.py`, the one place that derives it.
NAME_BUILDERS = {
    "targets/start_buy.py": "the one place: the price key of a start item and the price name of a Normal base are derived here from the target",
    "prices/price_names.py": "the format of the poe.ninja-style base name, and its parser and canonical form",
    "prices/ninja_items.py": "names a poe.ninja stash line by the line's own name, level and variant (no target is involved)",
    "prices/trade_query.py": "`load_buy_spec` reads a spec file whose name the file gives; it derives nothing",
}
BUILDERS = {"base_price_name", "BuySpec"}


def calls_in(path: Path) -> set[str]:
    """The names of the functions and classes `path` calls (`base_price_name(...)`, `x.BuySpec(...)`)."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call):
            function = node.func
            found.add(function.attr if isinstance(function, ast.Attribute) else getattr(function, "id", ""))
    return found


def test_only_the_listed_modules_of_src_build_a_price_name():
    builders = {path.relative_to(SRC).as_posix() for path in SRC.rglob("*.py") if calls_in(path) & BUILDERS}

    assert builders == set(NAME_BUILDERS), sorted(builders ^ set(NAME_BUILDERS))


def test_the_callers_that_look_a_start_price_up_get_the_key_from_the_one_place():
    """The modules that read a start price name the key through `start_price_key` / `buy_spec_of` / `base_line_name`, never a typed or built one."""
    callers = {
        "cli/_plan.py": "buy_spec_of",
        "cli/_benchmark.py": "start_price_key",
        "cli/_starts.py": "start_price_key",
        "cli/_start_options.py": "base_line_name",
    }
    for module, function in callers.items():
        assert function in calls_in(SRC / module), (module, function)


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
