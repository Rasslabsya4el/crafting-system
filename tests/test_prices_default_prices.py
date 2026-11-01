"""The default prices of Thaumaturgic Dust and Gold (ADR-0035, #216): in every fetched price file, and overridable by hand."""

from datetime import UTC, datetime

from ninja_support import ninja  # noqa: F401  (ninja is a fixture)
from crafting_system.prices import DUST, GOLD, PriceEntry, default_prices, load_prices, write_price_file
from crafting_system.prices.default_prices import DEFAULT_SOURCE
from crafting_system.prices.fetch import fetch_price_file

NOW = datetime(2026, 10, 30, 21, 0, 5, tzinfo=UTC)


def test_the_defaults_are_exactly_dust_and_gold_with_the_default_source():
    prices = default_prices()

    assert set(prices) == {DUST, GOLD}
    assert {entry.source for entry in prices.values()} == {DEFAULT_SOURCE} == {"default"}


def test_the_defaults_are_the_adr_0035_prices_in_chaos_per_one_unit():
    prices = default_prices()

    assert prices[DUST].chaos == 1 / 150_000  # 150,000 Dust per Chaos Orb
    assert prices[GOLD].chaos == 0.0005  # 500 Chaos Orbs per million Gold


def test_every_fetched_price_file_carries_both_defaults(ninja, tmp_path):
    price_file = fetch_price_file(ninja, NOW).price_file

    assert price_file.prices[DUST] == default_prices()[DUST]
    assert price_file.prices[GOLD] == default_prices()[GOLD]
    assert price_file.prices[DUST].source == "default"

    path = tmp_path / "prices.json"
    write_price_file(path, price_file)
    assert load_prices(path, tmp_path / "missing.toml").prices[DUST] == default_prices()[DUST]


def test_a_hand_price_for_dust_wins_over_the_default(ninja, tmp_path):
    prices_path = tmp_path / "prices.json"
    overrides_path = tmp_path / "price_overrides.toml"
    write_price_file(prices_path, fetch_price_file(ninja, NOW).price_file)
    overrides_path.write_text('[prices]\n"Thaumaturgic Dust" = 0.0002\n', encoding="utf-8")

    merged = load_prices(prices_path, overrides_path)

    assert merged.prices[DUST] == PriceEntry(0.0002, "override")
    assert merged.prices[GOLD] == default_prices()[GOLD]
