"""A trade price is written with its provenance by the one function every writer shares (`entry_for`), and `cli trade` shows it (#616, finding 1 of the checker).

`cli trade` prices a start item from a search built out of the spec, on recorded responses. Before this the entry it wrote carried no provenance: on the page and in the
report the price read as unrecorded, a stand-in for a wider item could not be told from the item, and the page lint could not see the gap.
"""

import datetime
from pathlib import Path

import pytest
from cli_support import R12, START
from cli_support import price_file as cli_price_file
from items_support import DATA
from oracle import page_lint
from test_prices_trade_cli import run
from trade_support import FakeTrade

from crafting_system.cli import make_plan
from crafting_system.cli._price_marks import price_uses, use_line
from crafting_system.cli._report import build_report, render_text
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.prices import PriceEntry, load_price_file, write_price_file
from crafting_system.prices.price_marks import NOT_RECORDED_WORDS
from crafting_system.prices.provenance import EXACT, TRADE, WIDER, Provenance
from crafting_system.prices.query_compare import other_item, wider_words
from crafting_system.prices.trade_pricing import ExactListings, TradePrice, entry_for, trade_provenance
from crafting_system.targets import buy_spec_of, load_target

def priced_by_cli_trade(tmp_path):
    """The R12 of the examples on the fixture data: the file holds the lifeforce price only, `cli trade` prices the start amulet on the recorded responses."""
    path = tmp_path / "data" / "prices.json"
    base = cli_price_file(start=None)
    base.prices.update({"Chaos Orb": PriceEntry(1.0, "poe.ninja"), "Divine Orb": PriceEntry(base.chaos_per_divine, "poe.ninja")})  # the rates the listings are turned to Chaos with
    write_price_file(path, base)
    assert run(tmp_path, FakeTrade(), target=R12, data=DATA) == 0
    return load_price_file(path)


def plan_of(prices):
    return make_plan(DATA, load_target(R12, DATA), prices)


def test_cli_trade_writes_the_provenance_of_what_it_read(tmp_path):
    entry = priced_by_cli_trade(tmp_path).prices[START]

    p = entry.provenance
    assert p is not None and p.recorded
    assert (p.kind, p.league, p.date, p.item) == (TRADE, "Test", "2026-10-30", EXACT)
    assert (p.depth, p.depth_unit, p.listings) == (float(entry.detail["used"]), "units", entry.detail["used"])
    assert p.for_item is None and p.exact_listings is None


def test_the_start_item_priced_by_cli_trade_is_a_recorded_price_on_the_report_and_the_page(tmp_path):
    plan = plan_of(priced_by_cli_trade(tmp_path))

    use = next(each for each in price_uses(plan, plan.view_policy) if each.name == START)
    line = use_line(use)
    text = render_text(build_report(plan, DATA))
    section = build_section(route_input(plan), DATA)
    page = [line.text for field in section.goal.fields if field.label == "Prices" for line in field.lines]

    assert use.source == "trade site, instant buyout, Test, 2026-10-30" and use.depth == 5.0
    assert NOT_RECORDED_WORDS not in line and "5 units behind it" in line
    assert any(each.startswith(f"{START}: ") and "5 units behind it" in each for each in page)
    assert f"  {line}" in text


def test_a_stand_in_start_item_is_marked_on_the_report_and_the_page_and_the_page_lint_sees_it(tmp_path):
    """A price taken for a wider item (the search was wider than the item the key names) reads as one, with what the exact item has."""
    prices = priced_by_cli_trade(tmp_path)
    entry = prices.prices[START]
    spec = buy_spec_of(DATA, load_target(R12, DATA))
    wide = {"query": {key: value for key, value in entry.detail["query"]["query"].items() if key != "type"}}  # the same search without the base type
    price = TradePrice(START, entry.chaos, "Test", datetime.date(2026, 10, 30), 910, 5, 10, 5, 10, {}, entry.detail["query_hash"], wide)
    assert other_item(spec, wide) is not None
    stand_in = entry_for(price, wider_words(other_item(spec, wide)), ExactListings(2, 744.4))
    prices.prices[START] = stand_in
    plan = plan_of(prices)

    use = next(each for each in price_uses(plan, plan.view_policy) if each.name == START)
    text = render_text(build_report(plan, DATA))
    html = render_page(Page("Test page", (build_section(route_input(plan), DATA),)))
    mark = "approximate: price of a wider item; the exact item has 2 listings at 744 Chaos"

    assert stand_in.provenance.item == WIDER and stand_in.provenance.exact_listings == 2
    assert use.wider and "taken for a wider item" in use_line(use)
    assert [m.reason for m in use.marks][0] == mark.removeprefix("approximate: ")
    assert "taken for a wider item" in text and mark in text
    assert page_lint.check_price_source_shown(page_lint.read_page(html)) == []
    unmarked = html.replace("; " + mark, "")
    assert unmarked != html and any("wider item" in fault.what for fault in page_lint.check_price_source_shown(page_lint.read_page(unmarked)))


def test_an_unrecorded_start_price_is_marked_and_the_page_lint_sees_a_market_price_that_shows_no_depth(tmp_path):
    prices = priced_by_cli_trade(tmp_path)
    entry = prices.prices[START]
    prices.prices[START] = PriceEntry(entry.chaos, entry.source, entry.note, entry.detail)  # the entry as `cli trade` wrote it before this
    plan = plan_of(prices)

    use = next(each for each in price_uses(plan, plan.view_policy) if each.name == START)
    html = render_page(Page("Test page", (build_section(route_input(plan), DATA),)))

    assert [mark.reason for mark in use.marks] == [NOT_RECORDED_WORDS]
    assert page_lint.check_price_source_shown(page_lint.read_page(html)) == []
    unmarked = html.replace("; approximate: " + NOT_RECORDED_WORDS, "")
    assert unmarked != html and any("shows no depth" in fault.what for fault in page_lint.check_price_source_shown(page_lint.read_page(unmarked)))


def test_the_snapshot_script_and_cli_trade_share_one_writer():
    """The provenance of a trade price is made by `trade_provenance`; the script calls `entry_for` and writes no `Provenance` of a trade price by hand."""
    script = (Path(__file__).resolve().parents[1] / ".github" / "scripts" / "price_snapshot.py").read_text(encoding="utf-8")

    assert "entry_for(" in script and "Provenance(TRADE" not in script
    assert trade_provenance.__module__ == entry_for.__module__


@pytest.mark.parametrize(("taken_for", "stand_in", "item"), [(None, None, EXACT), ("item level 84 or more", None, WIDER), (None, "any of the bases", WIDER)])
def test_the_item_is_exact_unless_the_search_or_the_price_is_a_stand_in(taken_for, stand_in, item):
    price = TradePrice("X", 3.0, "Allflame", datetime.date(2026, 11, 8), 40, 5, 9, 5, 10, {}, "h", {"query": {}})

    p = trade_provenance(price, taken_for, ExactListings(3, 20.0), stand_in)

    assert (p.item, p.depth, p.listings, p.league, p.date) == (item, 5.0, 5, "Allflame", "2026-11-08")
    assert (p.exact_listings, p.exact_price) == ((3, 20.0) if item == WIDER else (None, None))
