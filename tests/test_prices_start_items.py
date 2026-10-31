"""The start prices of the real routes name their recorded search (ticket #163).

`tests/fixtures/prices/routes-allflame-2026-10-31.json` holds one `trade-api` price per start item; each comes from
an instant-buyout search of any listing age, recorded in `fixtures/trade/recorded/start_items/` (see the README
there). The files need no network: the checks replay the recording against the price entry.
"""

import json
import statistics
from pathlib import Path

import pytest

from crafting_system.prices import load_price_file
from crafting_system.prices.trade_pricing import CURRENCY_NAMES, DEFAULT_K, TRADE_SOURCE
from crafting_system.prices.trade_query import query_hash

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PRICES = FIXTURES / "prices" / "routes-allflame-2026-10-31.json"
RECORDED = FIXTURES / "trade" / "recorded" / "start_items"
STARTS = {
    "r10": "R10 start boots",
    "r11": "R11 start helmet",
    "r05": "R05 start ring",
    "r12": "R12 start amulet",
}


def recorded(name: str):
    return json.loads((RECORDED / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def price_file():
    return load_price_file(PRICES)


@pytest.mark.parametrize("tag", STARTS)
def test_the_price_is_the_recorded_search_of_the_start_item(tag, price_file):
    entry = price_file.prices[STARTS[tag]]
    body = recorded(f"search_body_{tag}.json")

    assert entry.source == TRADE_SOURCE
    assert entry.detail["query"] == body
    assert entry.detail["query_hash"] == query_hash(price_file.league, body)
    assert entry.detail["listings"] == recorded(f"search_{tag}.json")["total"]
    assert entry.detail["date"] == "2026-10-31"


@pytest.mark.parametrize("tag", STARTS)
def test_the_search_asked_for_instant_buyout_of_any_age(tag):
    query = recorded(f"search_body_{tag}.json")["query"]

    assert query["status"] == {"option": "securable"}
    assert "trade_filters" not in query["filters"]


@pytest.mark.parametrize("tag", STARTS)
def test_the_price_is_the_mean_of_the_five_cheapest_recorded_listings(tag, price_file):
    entry = price_file.prices[STARTS[tag]]
    rows = recorded(f"fetch_{tag}.json")["result"]

    chaos = []
    for row in rows:
        price = row["listing"]["price"]
        assert row["item"]["fractured"] is True
        chaos.append(price["amount"] * price_file.prices[CURRENCY_NAMES[price["currency"]]].chaos)
    cheapest = sorted(chaos)[:DEFAULT_K]

    assert entry.detail["used"] == len(cheapest) == entry.detail["k"]
    assert entry.chaos == pytest.approx(statistics.fmean(cheapest))


def test_the_r11_helmet_is_searched_at_tier_1_chaos_resistance(price_file):
    """The owner's tier rule: the helmet's fractured Chaos Resistance is tier 1, so a roll of 31 or more."""
    (group,) = recorded("search_body_r11.json")["query"]["stats"]
    (stat,) = group["filters"]

    assert stat["id"].startswith("fractured.")
    assert stat["value"] == {"min": 31}
