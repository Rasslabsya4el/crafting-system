"""The prices an answer buys with: their source, depth and marks, on the text report, the page and the approximate inputs (#616, #598 point 2).

The plan is R12 on the fixture data: a bought amulet, then Harvest Reforge Lightning (50 Primal Crystallised Lifeforce a use) until the gem
shows. The lifeforce price and the start price are given a provenance here, so each case is arithmetic on what the plan expects to buy.
"""

import dataclasses
from datetime import UTC, datetime

import pytest
from cli_support import LIFEFORCE, R12, START, price_file
from items_support import DATA
from oracle import page_lint

from crafting_system.cli import make_plan
from crafting_system.cli._marking import PRICE_CLAIM, approximate_inputs, approximate_inputs_document
from crafting_system.cli._price_marks import price_lines, price_uses
from crafting_system.cli._report import build_report, policy_document, render_text
from crafting_system.cli._route_view import build_section, route_input
from crafting_system.prices import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, TRADE, WIDER, Provenance
from crafting_system.targets import load_target

DAY = "2026-10-30"


def plan_with(lifeforce_depth: float | None, start: Provenance | None = None):
    prices = price_file()
    prices.prices[LIFEFORCE] = PriceEntry(0.01, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", DAY, lifeforce_depth))
    if start is not None:
        prices.prices[START] = PriceEntry(4.0, "trade-api", None, None, start)
    return make_plan(DATA, load_target(R12, DATA), prices)


@pytest.fixture(scope="module")
def deep_plan():
    return plan_with(1e12)


@pytest.fixture(scope="module")
def thin_plan():
    return plan_with(10.0)


def uses_of(plan, name=LIFEFORCE):
    return next(use for use in price_uses(plan, plan.view_policy) if use.name == name)


def test_the_plan_lists_the_price_of_every_resource_it_buys_with_its_source_and_depth(deep_plan):
    uses = {use.name: use for use in price_uses(deep_plan, deep_plan.view_policy)}

    assert LIFEFORCE in uses and START in uses
    assert uses[LIFEFORCE].source == f"poe.ninja exchange, Test, {DAY}"
    assert uses[LIFEFORCE].depth == 1e12 and uses[LIFEFORCE].marks == ()
    assert uses[START].source.startswith("trade site, instant buyout")  # a legacy entry: its source string says what it is


def test_a_price_deep_enough_for_the_plan_is_a_plain_fact_and_makes_no_approximate_input(deep_plan):
    assert not any(i.claim.startswith(PRICE_CLAIM) for i in approximate_inputs(deep_plan, deep_plan.view_policy, DATA))


def test_a_price_on_fewer_units_than_the_plan_buys_is_an_approximate_input_with_the_units_in_its_reason(thin_plan):
    use = uses_of(thin_plan)
    wanted = [i for i in approximate_inputs(thin_plan, thin_plan.view_policy, DATA) if i.claim == PRICE_CLAIM + LIFEFORCE]

    assert use.uses > 10 and [m.reason for m in use.marks] == ["price on 10 units"]
    assert len(wanted) == 1
    assert wanted[0].reason == "price on 10 units"
    assert wanted[0].source == f"poe.ninja exchange, Test, {DAY}"
    assert "approximate input: price on 10 units" in wanted[0].statement and "expects to buy about" in wanted[0].statement


def test_the_expected_uses_are_the_expected_visits_of_the_policy():
    """The mean cost still to pay is every use of the lifeforce reforge times its price plus the restarts' amulets (the first amulet is the start price)."""
    plan = plan_with(10.0, Provenance(TRADE, "Test", DAY, 1.0, "units", 1))
    spent_on_lifeforce = uses_of(plan).uses * 0.01
    restarts = uses_of(plan, START).uses - 1.0

    assert spent_on_lifeforce + restarts * 4.0 == pytest.approx(plan.mean_remaining, rel=1e-9)


def test_a_wider_start_item_is_marked_with_what_the_exact_item_has():
    p = Provenance(TRADE, "Test", DAY, 5.0, "units", 5, WIDER, "an amulet of any item level", 1, 120.0)
    plan = plan_with(1e12, p)

    use = uses_of(plan, START)

    assert [m.reason for m in use.marks][0] == "price of a wider item; the exact item has 1 listing at 120 Chaos"


def test_the_text_report_prints_each_price_with_its_source_and_marks(thin_plan):
    text = render_text(build_report(thin_plan, DATA))

    line = next(each for each in text.splitlines() if each.startswith(f"  {LIFEFORCE}: "))
    assert line.startswith(f"  {LIFEFORCE}: 0.01 Chaos, poe.ninja exchange, Test, {DAY}, 10 units behind it, the plan buys about ")
    assert line.endswith("; approximate: price on 10 units")
    assert "Approximate inputs (claims that no other source settles):" in text
    assert text.index("Prices: league") < text.index(f"  {LIFEFORCE}: 0.01 Chaos") < text.index("Start item")


def test_the_json_policy_lists_the_marked_price_among_the_approximate_inputs(thin_plan):
    document = approximate_inputs_document(approximate_inputs(thin_plan, thin_plan.view_policy, DATA))

    assert {"claim": PRICE_CLAIM + LIFEFORCE, "reason": "price on 10 units"} in document
    assert "approximate_inputs" in policy_document(build_report(thin_plan, DATA))


def test_the_page_prints_the_source_of_each_price_and_its_marks(thin_plan):
    section = build_section(route_input(thin_plan), DATA)

    prices = next(field for field in section.goal.fields if field.label == "Prices")
    approximate = next(field for field in section.goal.fields if field.label == "Approximate inputs")
    lines = [line.text for line in prices.lines]

    assert lines[0] == "league Test, fetched 2026-10-30"
    line = next(each for each in lines if each.startswith(f"{LIFEFORCE}: "))
    assert line.startswith(f"{LIFEFORCE}: 0.01 Chaos, poe.ninja exchange, Test, {DAY}, 10 units behind it, the plan buys about ")
    assert line.endswith("; approximate: price on 10 units")
    assert any("price on 10 units" in line.text and "Source: poe.ninja exchange, Test" in line.text for line in approximate.lines)


def test_a_price_with_no_entry_in_the_file_is_not_listed(deep_plan):
    names = {use.name for use in price_uses(deep_plan, deep_plan.view_policy)}

    assert "Chaos Orb" not in names and "Divine Orb" not in names


def test_without_a_policy_only_the_start_item_is_listed_and_nothing_is_solved(thin_plan):
    assert [use.name for use in price_uses(thin_plan, None)] == [START]
    assert price_lines(price_uses(thin_plan, None, solve_uses=False))[0].startswith(f"  {START}")


def test_a_plan_that_was_not_solved_still_lists_its_prices():
    plan = dataclasses.replace(plan_with(10.0), solution=dataclasses.replace(plan_with(10.0).solution, values={}))

    uses = price_uses(plan, plan.view_policy)

    assert {use.name for use in uses} >= {LIFEFORCE, START}
    assert datetime(2026, 10, 30, tzinfo=UTC) == plan.prices.fetched_at


def lint_of_page(plan, check):
    from crafting_system.cli._route_html import render_page
    from crafting_system.cli._route_view import Page

    html = render_page(Page("Test page", (build_section(route_input(plan), DATA),)))
    return check(page_lint.read_page(html))


def test_the_page_the_planner_draws_passes_the_check_of_price_sources_for_a_thin_and_a_deep_price(thin_plan, deep_plan):
    assert lint_of_page(thin_plan, page_lint.check_price_source_shown) == []
    assert lint_of_page(deep_plan, page_lint.check_price_source_shown) == []


def test_the_check_of_price_sources_fails_on_the_same_page_when_the_mark_is_taken_out(thin_plan):
    from crafting_system.cli._route_html import render_page
    from crafting_system.cli._route_view import Page

    html = render_page(Page("Test page", (build_section(route_input(thin_plan), DATA),))).replace("; approximate: price on 10 units", "")

    assert page_lint.check_price_source_shown(page_lint.read_page(html))
