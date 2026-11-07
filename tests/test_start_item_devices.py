"""The items the code builds to model a craft are not the player's start item (#545, OR-6; decision of the main chat, 2026-11-07).

A target file states the player's start item (`start_item:` with its `rarity:`) and the parser makes up none. Some items are built by the code
to model something, and they stay: the Magic item of a vendor-recipe step (I7), the rare item of a published-odds row (I8), the donors of the
Awakener's and the recombinator's models (I9, I10), the representative item of a state (I11) and the empty rare probe of the pool (I12).
The condition of keeping them is that none of them reaches the route page or the text answer as the start item. Two things show it:

* **Who can set the start item.** The page and the text read `Target.start_item`; a `Target` is built by the parser alone, and its start item
  is replaced in two places only: `targets/floor.py` (the same item at a lower item level) and `cli/_starts.py` (the vendor-recipe start I7,
  which the page and the text print as the recipe's product, below). No module of I8 to I12 builds a `Target` or replaces its start item.
* **What the page and the text print.** A plan from the target's own start item prints that item; a plan that wins from a vendor recipe prints
  the recipe, its bill and "You get back", never the "Accepts" or "Trade" of a bought item.
"""

import ast
from pathlib import Path

from vendor_starts_support import TOY, prices, toy_target

from crafting_system.cli import build_report, plan_with_starts, render_text
from crafting_system.cli._route_card import ANY_OR_EMPTY, card_of_item
from crafting_system.cli._route_view import build_section, route_input
from crafting_system.cli._start_types import SOURCE_PLAIN

SRC = Path(__file__).resolve().parents[1] / "src" / "crafting_system"
PARSER = "targets/parse.py"
FLOOR = "targets/floor.py"
VENDOR_START = "cli/_starts.py"


def calls_named(names: set[str]):
    """Every call in `src` of a function called one of `names`, as (relative path, the call)."""
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
                if name in names:
                    yield path.relative_to(SRC).as_posix(), node


def test_a_target_is_built_by_the_parser_alone():
    assert {path for path, _ in calls_named({"Target"})} == {PARSER}


def test_the_start_item_of_a_target_is_replaced_in_the_floor_and_the_vendor_start_only():
    replacing = {path for path, call in calls_named({"replace"}) if any(keyword.arg == "start_item" for keyword in call.keywords)}

    assert replacing == {FLOOR, VENDOR_START}


def test_the_modules_that_build_the_other_items_never_set_a_start_item():
    devices = [
        "cli/_benchmark_outcomes.py",  # I8: the rare item of a published-odds row
        "actions/awakener.py",  # I9: the donors
        "actions/recombinator.py",  # I10: the donors and the result item
        "abstraction/_kernel.py",  # I11 and I12: the representative item of a state and the empty probe
        "abstraction/_kinds.py",
        "abstraction/_inputs.py",
        "abstraction/_coarse.py",
    ]
    for device in devices:
        text = (SRC / device).read_text(encoding="utf-8")
        assert "start_item=" not in text and "Target(" not in text, device


def test_a_plan_from_the_targets_own_item_prints_that_item_on_the_page_and_in_the_text():
    target = toy_target()
    plan = plan_with_starts(TOY, target, prices(), recipe_starts=False)

    assert plan.target.start_item is target.start_item
    text = render_text(build_report(plan, TOY), target_name="toy.yaml")
    assert "Start item: given: its cost is not counted, and the plan never buys another" in text.splitlines()
    assert "First step, before S1" not in text and "vendor recipe" not in text

    row = build_section(route_input(plan), TOY).rows[0]
    assert row.title == "Start item (given)"
    assert row.after == card_of_item(TOY, target.start_item, tiers=True, rolled=False, filler=ANY_OR_EMPTY)
    assert row.after.properties == ("Rare", "item level 86")  # the file's `rarity: rare`, not the Magic item of a recipe


def test_a_plan_from_a_vendor_recipe_prints_the_recipe_and_what_it_gives_back_not_a_bought_start_item():
    target = toy_target()
    plan = plan_with_starts(TOY, target, prices())
    assert plan.starts.chosen.source != SOURCE_PLAIN  # the recipe start wins here
    assert plan.target.start_item is not target.start_item  # the planner moved the item: the recipe's product (I7)

    text = render_text(build_report(plan, TOY), target_name="toy.yaml")
    lines = text.splitlines()
    assert any(line.startswith("Start item (Boots with movement speed (vendor recipe") for line in lines)  # named by its recipe, with its price
    assert "First step, before S1: Vendor recipe: Boots with movement speed, 5 recipes in a row" in lines
    assert any(line.startswith("  You get back: Magic Toy Boots") for line in lines)
    assert "Start item: given: its cost is not counted, and the plan never buys another" not in lines

    row = build_section(route_input(plan), TOY).rows[0]
    assert row.title == "Vendor recipe: Boots with movement speed, 5 recipes in a row"
    assert [field.label for field in row.fields] == ["Hand the vendor", "Recipes, each takes the item the one before made", "Cost per use"]
    assert row.after.properties == ("Magic", "item level 86")  # what the vendor hands back
