"""The recipe start in the report, the JSON and the route page (ticket #331, ADR-0059).

"Done when" of the ticket, the report line: the report names the recipe inputs with counts and the start price, and a test pins it.

* `test_the_text_report_names_the_goods_with_counts_the_item_that_comes_back_and_the_start_price` pins the text on the toy boots.
* `test_the_json_first_step_holds_the_same_bill_recipes_and_item` pins the JSON.
* `test_the_route_page_row_1_is_the_recipe_with_the_bill_and_no_trade_link` and `test_the_costs_of_the_rows_add_up_...` pin the route page.
* The start that wins on the real data, and the benchmark route, are `test_vendor_benchmark_real.py`.

The toy game of `vendor_starts_support` has boots and a wand; every plan here solves in well under a second.
"""

import dataclasses
import json
from pathlib import Path

import pytest
from vendor_starts_support import (
    AUGMENTATION,
    AUGMENTATION_PRICE,
    BASE_PRICE,
    BOOTS_NAME,
    FLASK_PRICE,
    QUICKSILVER,
    RUBY,
    TOY,
    WAND_NAME,
    WAND_TARGET,
    prices,
    toy_target,
)

from crafting_system.cli import build_report, plan_with_starts, policy_document, render_text
from crafting_system.cli._route_view import build_section, route_input, write_route_page
from crafting_system.cli._start_step import ROLE_AUGMENTATION, ROLE_BASE, ROLE_FLASK, first_step
from crafting_system.cli._start_types import SOURCE_PLAIN
from crafting_system.prices import load_buy_spec

ROOT = Path(__file__).resolve().parents[1]
FIVE_STEPS = BASE_PRICE + 5 * (FLASK_PRICE + AUGMENTATION_PRICE)
TIERS = [(10, 6), (15, 5), (20, 4), (25, 3), (30, 2)]  # the movement speed ladder the recipe climbs: per cent and tier from the top


def toy_plan(**kwargs):
    return plan_with_starts(TOY, toy_target(), prices(**kwargs))


def text_of(plan, data=TOY) -> str:
    return render_text(build_report(plan, data), target_name="toy.yaml")


def document_of(plan, data=TOY) -> dict:
    document = policy_document(build_report(plan, data), None, target_name="toy.yaml")
    document.pop("timings_seconds")
    return json.loads(json.dumps(document))


# --- the text -------------------------------------------------------------------------------------------------------------------


def test_the_text_report_names_the_goods_with_counts_the_item_that_comes_back_and_the_start_price():
    plan = toy_plan()
    assert plan.starts.chosen.recipe == "boots_movement_speed"  # the recipe start wins here

    text = text_of(plan)

    assert text.isascii()
    lines = text.splitlines()
    first = lines.index("First step, before S1: Vendor recipe: Boots with movement speed, 5 recipes in a row")
    assert lines[first - 1].startswith("Memory Strands:")  # the step sits in the header, before the options and the policy
    assert lines.index(next(line for line in lines if line.startswith("Start options"))) > first
    assert lines.index("Policy (S = a state of the item; the start is S1)") > first
    assert lines[first + 1 : first + 5] == [
        "  You hand the vendor:",
        f"    1 {BOOTS_NAME}, a Normal base: {BASE_PRICE:,.2f} Chaos [trade-api]",
        f"    5 {QUICKSILVER}: {5 * FLASK_PRICE:,.2f} Chaos [trade-api]",
        f"    5 {AUGMENTATION}: {5 * AUGMENTATION_PRICE:,.2f} Chaos [fixture]",
    ]
    assert "  Recipe by recipe (each takes the Magic item the recipe before made; the first takes the Normal base):" in lines
    for number, (percent, tier) in enumerate(TIERS, start=1):
        assert f"    recipe {number}: 1 {QUICKSILVER} + 1 {AUGMENTATION} -> {percent}% increased Movement Speed, T{tier}" in lines
    assert "  You get back: Magic Toy Boots, item level 86, with only 30% increased Movement Speed, T2 (the recipe wipes every other mod)" in lines
    assert f"  Start price: {FIVE_STEPS:,.2f} Chaos = the goods above; a restart makes the item again at this price" in lines
    assert text.count("You hand the vendor:") == 1 and "hand the vendor: " not in text  # the bill is told once, in the step


def test_the_start_price_of_the_step_is_the_sum_of_the_bill_and_the_start_price_of_the_plan():
    plan = toy_plan()

    step = first_step(plan.starts.chosen, TOY, plan.target)

    assert step.price == pytest.approx(FIVE_STEPS) == pytest.approx(plan.start_price.chaos)
    assert sum(good.chaos for good in step.hand) == pytest.approx(step.price)
    assert [(good.role, good.count) for good in step.hand] == [(ROLE_BASE, 1), (ROLE_FLASK, 5), (ROLE_AUGMENTATION, 5)]


def test_a_dearer_flask_changes_the_bill_and_the_price_in_the_report():
    plan = toy_plan(flask=3.0)  # 1 + 5 x (3 + 0.5) = 18.5: still cheaper than the plain start

    text = text_of(plan)

    assert plan.starts.chosen.recipe == "boots_movement_speed"
    assert f"    5 {QUICKSILVER}: 15.00 Chaos [trade-api]" in text
    assert "  Start price: 18.50 Chaos = the goods above" in text


def test_a_roll_inside_a_range_is_said_to_be_counted_at_its_lowest():
    target = toy_target(WAND_TARGET.replace("min_tier: 2", "min_tier: 3"))  # T3 fire damage: eight steps at either reading of the cap
    plan = plan_with_starts(TOY, target, prices(base=None, flask=None, **{WAND_NAME.replace(" ", "_"): BASE_PRICE, "Ruby_Flask": FLASK_PRICE}))
    assert plan.starts.chosen.key == "vendor:weapon_fire:8"

    text = text_of(plan)
    step = first_step(plan.starts.chosen, TOY, plan.target)

    assert f"1 {RUBY} + 1 {AUGMENTATION} -> Adds" in text
    assert step.roll_note and f"  Roll: {step.roll_note}" in text
    assert text.isascii()


def test_a_plain_start_prints_no_first_step_anywhere():
    plan = toy_plan(flask=60.0)  # the goods cost more than the crafting saves: the plain start wins
    assert plan.starts.chosen.source == SOURCE_PLAIN

    text = text_of(plan)
    document = document_of(plan)

    assert "First step" not in text
    assert first_step(plan.starts.chosen, TOY, plan.target) is None
    assert document["start_options"]["first_step"] is None


def test_a_candidate_of_another_source_has_no_first_step_here():
    plan = toy_plan()
    bought = dataclasses.replace(plan.starts.chosen, source="bought", recipe=None)

    assert first_step(bought, TOY, plan.target) is None


def test_the_setting_off_prints_no_first_step_and_no_start_block():
    plan = plan_with_starts(TOY, toy_target(), prices(), recipe_starts=False)

    text = text_of(plan)

    assert "First step" not in text and "Start options" not in text
    assert "start_options" not in document_of(plan)


# --- the JSON -------------------------------------------------------------------------------------------------------------------


def test_the_json_first_step_holds_the_same_bill_recipes_and_item():
    plan = toy_plan()

    block = document_of(plan)["start_options"]["first_step"]

    assert block["recipe"] == "boots_movement_speed" and block["price_chaos"] == pytest.approx(FIVE_STEPS)
    assert block["title"] == "Vendor recipe: Boots with movement speed, 5 recipes in a row"
    assert [(good["role"], good["count"], good["name"], good["chaos"]) for good in block["hand"]] == [
        (ROLE_BASE, 1, BOOTS_NAME, BASE_PRICE),
        (ROLE_FLASK, 5, QUICKSILVER, 5 * FLASK_PRICE),
        (ROLE_AUGMENTATION, 5, AUGMENTATION, 5 * AUGMENTATION_PRICE),
    ]
    assert [(each["number"], each["gives"], each["tier"]) for each in block["recipes"]] == [
        (number, f"{percent}% increased Movement Speed", tier) for number, (percent, tier) in enumerate(TIERS, start=1)
    ]
    assert all(each["hand"] == f"1 {QUICKSILVER} + 1 {AUGMENTATION}" for each in block["recipes"])
    assert block["gets"] == {
        "base": "Toy Boots",
        "properties": ["Magic", "item level 86"],
        "mods": [{"text": "30% increased Movement Speed", "tier": "T2"}],
    }
    assert block["roll_note"] == ""


# --- the route page -------------------------------------------------------------------------------------------------------------


def field_of(row, label: str):
    return next((field for field in row.fields if field.label == label), None)


def test_the_route_page_row_1_is_the_recipe_with_the_bill_and_no_trade_link(tmp_path):
    plan = toy_plan()
    section = build_section(route_input(plan), TOY)

    row = section.rows[0]

    assert row.number == 1 and row.title == "Vendor recipe: Boots with movement speed, 5 recipes in a row"
    assert [line.text for line in field_of(row, "Hand the vendor").lines] == [
        f"1 × {BOOTS_NAME}, a Normal base 1 c",
        f"5 × {QUICKSILVER} 10 c",
        f"5 × {AUGMENTATION} 2.5 c",
    ]
    recipes = field_of(row, "Recipes, each takes the item the one before made")
    assert [line.text for line in recipes.lines][-1] == f"5. 1 {QUICKSILVER} + 1 {AUGMENTATION} → 30% increased Movement Speed · T2"
    assert [line.text for line in field_of(row, "Cost per use").lines] == ["13.5 c"]
    assert field_of(row, "Accepts") is None and field_of(row, "Trade") is None
    assert row.cost == pytest.approx(FIVE_STEPS)
    assert [(slot.text, slot.note) for slot in row.after.prefixes if slot.tone == "mod"] == [("30% increased Movement Speed", "T2")]
    assert row.after.properties == ("Magic", "item level 86")
    start = field_of(section.goal, "Start")
    assert [line.text.split(":")[0] for line in start.lines] == ["planned", "chosen"]  # the plain start and the recipe, side by side

    page = tmp_path / "route.html"
    spec = load_buy_spec(ROOT / "examples" / "buy" / "r10-start-boots.yaml")
    write_route_page(page, build_report(plan, TOY), TOY, buy_spec=spec, target_name="toy.yaml")
    html = page.read_text(encoding="utf-8")
    assert "Vendor recipe: Boots with movement speed" in html and "Hand the vendor" in html
    assert "pathofexile.com/trade" not in html and "Search on the trade site" not in html  # the buy spec describes a bought item


def test_the_restart_row_makes_the_item_again_instead_of_buying_it():
    plan = toy_plan()
    section = build_section(route_input(plan), TOY)

    restarts = [row for row in section.rows if row.title.startswith("Restart")]

    assert all(row.title == "Restart: make the start item at the vendor again" for row in restarts)
    assert all("Buy" not in row.title for row in section.rows)


def test_the_costs_of_the_rows_add_up_to_the_mean_plus_the_start_price():
    plan = toy_plan()
    section = build_section(route_input(plan), TOY)

    total = sum(row.cost for row in section.rows if row.cost is not None)

    assert total == pytest.approx(plan.risk.mean.value + plan.start_price.chaos, rel=1e-6)


def test_the_page_of_a_plain_start_is_unchanged_by_the_ticket():
    plan = toy_plan(flask=60.0)

    section = build_section(route_input(plan), TOY)

    assert section.rows[0].title == "Start item" and field_of(section.goal, "Start") is None
