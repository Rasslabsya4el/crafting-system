"""The items the code builds to model a craft are not the player's start item (#545, OR-6; decision of the main chat, 2026-11-07).

A target file states the player's start item (`start_item:` with its `rarity:`) and the parser makes up none. Some items are built by the code
to model something, and they stay: the Magic item of a vendor-recipe step (I7), the rare item of a published-odds row (I8), the donors of the
Awakener's and the recombinator's models (I9, I10), the representative item of a state (I11) and the empty rare probe of the pool (I12).
The condition of keeping them is that none of them reaches the route page or the text answer as the start item. Three things show it:

* **Who can set the start item.** A `Target` is built by the parser alone, and its start item is replaced in three places only:
  `targets/floor.py` (the same item at a lower item level), `cli/_starts.py` (the vendor-recipe start I7) and `cli/_bought_starts.py` (the
  same base at another item level or with the influence a requirement needs, #351; listed as a start option, never a made-up item). No module of I8 to I12 builds a
  `Target` or replaces its start item (a scan of `src`, for I8, which only a real benchmark prints, and for the rest as a backstop).
* **I7, in the output.** When a vendor recipe wins, the text's "Start item" line is the Normal base the recipe takes, the recipe is a step of
  its own ("Step 1: Vendor recipe: ...") with its bill, and the Magic item it gives back is "You get back" and row 1 of the page.
* **I9 to I12, in the output.** A Normal start stays Normal (the empty rare probe, I12), a stated start mod is printed as written (the
  representative item of a state, I11), and no donor (I9, I10) appears in the page or the text.
"""

import ast
from pathlib import Path

from vendor_starts_support import BOOTS_TARGET, TOY, prices, toy_target

from crafting_system.cli import build_report, plan_with_starts, render_text
from crafting_system.cli._route_card import ANY_OR_EMPTY, card_of_item
from crafting_system.cli._route_view import build_section, route_input, write_route_page
from crafting_system.cli._start_types import SOURCE_PLAIN

SRC = Path(__file__).resolve().parents[1] / "src" / "crafting_system"
PARSER = "targets/parse.py"
FLOOR = "targets/floor.py"
VENDOR_START = "cli/_starts.py"
BOUGHT_START = "cli/_bought_starts.py"


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

    assert replacing == {FLOOR, VENDOR_START, BOUGHT_START}


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
    assert "Step 1: Vendor recipe" not in text and "vendor recipe" not in text

    row = build_section(route_input(plan), TOY).rows[0]
    assert row.title == "Start item (given)"
    assert row.after == card_of_item(TOY, target.start_item, tiers=True, rolled=False, filler=ANY_OR_EMPTY)
    assert row.after.properties == ("Rare", "item level 86")  # the file's `rarity: rare`, not the Magic item of a recipe


def test_a_plan_from_a_vendor_recipe_prints_the_base_it_takes_as_the_start_item_and_the_recipe_as_a_step():
    target = toy_target()
    plan = plan_with_starts(TOY, target, prices())
    assert plan.starts.chosen.source != SOURCE_PLAIN  # the recipe start wins here
    assert plan.target.start_item is not target.start_item  # the planner moved the item: the recipe's product (I7)

    text = render_text(build_report(plan, TOY), target_name="toy.yaml")
    lines = text.splitlines()
    # "Start item" is the true start: the Normal base the recipe takes, with its own price, not the Magic item the vendor gives back
    assert "Start item (Toy Boots (ilvl 86), a Normal base): 1.00 Chaos [trade-api]; the recipe below uses it up" in lines
    start_lines = [line for line in lines if line.startswith("Start item")]
    assert len(start_lines) == 1 and "vendor recipe" not in start_lines[0] and "Magic" not in start_lines[0]
    # the recipe is a step of its own, with its bill, and the product is "what you get back"
    first = lines.index("Step 1: Vendor recipe: Boots with movement speed, 5 recipes in a row")
    assert lines[first - 1] == start_lines[0]
    assert any(line.startswith("  You get back: Magic Toy Boots") for line in lines[first:])
    assert "Start item: given: its cost is not counted, and the plan never buys another" not in lines

    row = build_section(route_input(plan), TOY).rows[0]
    assert row.title == "Vendor recipe: Boots with movement speed, 5 recipes in a row"
    assert [field.label for field in row.fields] == ["Hand the vendor", "Recipes, each takes the item the one before made", "Cost per use"]
    assert row.after.properties == ("Magic", "item level 86")  # what the vendor hands back, shown as the product of the step


NORMAL_START = BOOTS_TARGET.replace("rarity: rare\n  mods: []", "rarity: normal").replace(
    "actions: [chaos-orb, regal-orb, exalted-orb]", "actions: [transmutation-orb, augmentation-orb, regal-orb, chaos-orb, exalted-orb]"
)
FRACTURED_START = BOOTS_TARGET.replace(
    "rarity: rare\n  mods: []",
    "rarity: rare\n  mods:\n    - mod: MovementVelocity5\n      values: [30]\n      fractured: true",
)


def plain_plan(text: str):
    return plan_with_starts(TOY, toy_target(text), prices(Orb_of_Transmutation=0.2), recipe_starts=False)


def test_the_empty_rare_probe_and_the_representative_items_do_not_make_a_normal_start_rare_on_the_page_or_in_the_text():
    """I11 and I12: the abstraction probes the pool with an empty rare and describes a state by a representative item; a Normal start stays Normal."""
    plan = plain_plan(NORMAL_START)

    assert plan.target.start_item.rarity.value == "normal"
    row = build_section(route_input(plan), TOY).rows[0]
    assert row.after.properties == ("Normal", "item level 86")
    assert all(slot.text == "empty" for slot in (*row.after.prefixes, *row.after.suffixes))  # not the "any mod or empty" of a rare
    text = render_text(build_report(plan, TOY), target_name="toy.yaml")
    assert "Start item: given" in text and "Rare" not in text.split("Policy (one block")[0]


def test_a_stated_start_mod_is_printed_as_the_file_wrote_it_not_as_a_representative_item_of_a_state():
    """I11: the page's start card is the file's item (the fractured mod at its written tier), the other slots read "any mod or empty"."""
    target = toy_target(FRACTURED_START)
    plan = plan_with_starts(TOY, target, prices(), recipe_starts=False)

    row = build_section(route_input(plan), TOY).rows[0]
    assert row.after == card_of_item(TOY, target.start_item, tiers=True, rolled=False, filler=ANY_OR_EMPTY)
    shown = [(slot.text, slot.tone) for slot in (*row.after.prefixes, *row.after.suffixes) if slot.tone == "mod"]
    assert shown == [("30% increased Movement Speed", "mod")]
    assert sum(slot.text == "any mod or empty" for slot in (*row.after.prefixes, *row.after.suffixes)) == 5


def test_the_donors_of_the_awakener_and_the_recombinator_are_nowhere_on_the_page_or_in_the_text(tmp_path):
    """I9 and I10: planner-off models; a plan neither offers them nor prints a donor item."""
    plan = plain_plan(BOOTS_TARGET)
    text = render_text(build_report(plan, TOY), target_name="toy.yaml")
    page = tmp_path / "route.html"
    write_route_page(page, build_report(plan, TOY), TOY, target_name="toy.yaml")
    html = page.read_text(encoding="utf-8")

    for output in (text, html):
        assert "donor" not in output.lower()
    assert "Awakener's Orb" in text and "Recombinators" in text  # listed as not offered, the only place they appear
    assert not [offer.label for offer in plan.offers if "Awakener" in offer.label or "Recombinator" in offer.label]
