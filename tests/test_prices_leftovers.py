"""The points the price tickets left open (#84): aged trade prices, canonical stored names, a failed stash overview."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from ninja_support import ninja  # noqa: F401  (a fixture)
from repoe_support import fixture_game_data
from trade_support import NOW, R12_SPEC, FakeTrade, price_file

from crafting_system.prices import (
    TRADE_SOURCE,
    PriceEntry,
    PriceFile,
    SourceError,
    StageResult,
    load_price_file,
    write_price_file,
)
from crafting_system.prices.__main__ import main
from crafting_system.prices.fetch import fetch_price_file
from crafting_system.prices.trade_pricing import merge_trade_prices, stale_trade_warnings

NAME = "R12 start amulet"
UNORDERED = "Stygian Vise (ilvl 85, Warlord/Hunter)"
CANONICAL = "Stygian Vise (ilvl 85, Hunter/Warlord)"


@pytest.fixture(autouse=True)
def game_data(monkeypatch):
    monkeypatch.setattr("crafting_system.prices.__main__.load_game_data", lambda **kwargs: fixture_game_data())


def trade_entry(days_old: int, chaos: float = 2.0) -> PriceEntry:
    day = (NOW - timedelta(days=days_old)).date().isoformat()
    return PriceEntry(chaos, TRADE_SOURCE, "median", {"league": "Allflame", "date": day, "listings": 910})


def file_with_trade(days_old: int, name: str = NAME) -> PriceFile:
    base = price_file()
    return price_file(prices={**base.prices, name: trade_entry(days_old)})


class Asked:
    """A fallback stage that records the names it is asked about and prices none."""

    def __init__(self):
        self.names: list[str] = []

    def __call__(self, get_json, context, gaps):
        self.names += [gap.name for gap in gaps]
        return StageResult({}, [])


def cli_env(tmp_path):
    return {"CRAFTING_DATA_DIR": str(tmp_path / "data"), "CRAFTING_CACHE_DIR": str(tmp_path / "cache")}


# -- an aged trade price ---------------------------------------------------------------------------


def test_a_trade_price_within_the_stale_limit_still_covers_its_name(ninja):
    asked = Asked()

    fetch_price_file(ninja, NOW, [NAME], stages=(asked,), old_price_file=file_with_trade(7))

    assert asked.names == []


def test_a_trade_price_older_than_the_stale_limit_no_longer_covers_its_name(ninja):
    asked = Asked()

    fetch_price_file(ninja, NOW, [NAME], stages=(asked,), old_price_file=file_with_trade(8))

    assert asked.names == [NAME]


def test_a_kept_aged_trade_price_is_flagged_stale_by_the_merge(ninja):
    new = fetch_price_file(ninja, NOW).price_file

    merged, warnings = merge_trade_prices(new, file_with_trade(9))

    assert merged.prices[NAME].source == TRADE_SOURCE
    assert any(NAME in line and "9 days old" in line and "trade" in line for line in warnings)


def test_a_fresh_trade_price_is_not_flagged(ninja):
    new = fetch_price_file(ninja, NOW).price_file

    _, warnings = merge_trade_prices(new, file_with_trade(7))

    assert warnings == []


def test_stale_trade_warnings_skip_an_undated_trade_price_and_other_sources():
    prices = {
        "Undated": PriceEntry(2.0, TRADE_SOURCE, None, {"league": "Allflame"}),
        "Plain": PriceEntry(2.0, TRADE_SOURCE),
        "Ninja": PriceEntry(2.0, "poe.ninja", None, {"date": "2020-01-01"}),
        "Broken": PriceEntry(2.0, TRADE_SOURCE, None, {"date": "last week"}),
    }

    assert stale_trade_warnings(price_file(prices=prices), date(2026, 10, 30)) == []


def test_check_flags_an_aged_trade_price(tmp_path, capsys):
    write_price_file(tmp_path / "data" / "prices.json", file_with_trade(10))

    code = main(["check"], today=NOW.date(), env=cli_env(tmp_path))

    assert code == 0
    assert any(line.startswith("Warning:") and NAME in line and "10 days old" in line
               for line in capsys.readouterr().out.splitlines())


def test_fetch_prints_the_stale_flag_and_keeps_the_aged_price(tmp_path, ninja, capsys):
    path = tmp_path / "data" / "prices.json"
    write_price_file(path, file_with_trade(12))

    code = main(["fetch"], get_json=ninja, now=NOW, env=cli_env(tmp_path))

    assert code == 0
    assert load_price_file(path).prices[NAME].source == TRADE_SOURCE
    assert any(NAME in line and "12 days old" in line for line in capsys.readouterr().out.splitlines())


def test_the_next_trade_run_re_requests_an_aged_price_and_replaces_it(tmp_path, capsys):
    path = tmp_path / "data" / "prices.json"
    write_price_file(path, file_with_trade(9, NAME))
    trade = FakeTrade()

    code = main(
        ["trade", "--spec", str(R12_SPEC)],
        transport=trade, sleep=lambda seconds: None, monotonic=lambda: 0.0, now=NOW, env=cli_env(tmp_path),
    )

    assert code == 0
    assert "search" in trade.kinds and "fetch" in trade.kinds  # the network was asked again
    stored = load_price_file(path).prices[NAME]
    assert stored.detail["date"] == NOW.date().isoformat()
    assert stale_trade_warnings(load_price_file(path), NOW.date()) == []


# -- non-canonical names in the price file ---------------------------------------------------------


def write_raw(path, prices):
    document = {
        "unit": "chaos", "league": "Allflame", "fetched_at": "2026-10-30T20:24:00Z",
        "chaos_per_divine": 400.0, "prices": prices,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_a_stored_base_name_is_read_in_game_order(tmp_path):
    path = tmp_path / "prices.json"
    write_raw(path, {UNORDERED: {"chaos": 5, "source": TRADE_SOURCE}})

    assert list(load_price_file(path).prices) == [CANONICAL]


def test_two_stored_names_that_become_one_are_an_error(tmp_path):
    path = tmp_path / "prices.json"
    write_raw(path, {
        UNORDERED: {"chaos": 5, "source": TRADE_SOURCE},
        CANONICAL: {"chaos": 6, "source": "poe.ninja"},
    })

    with pytest.raises(ValueError, match="same price name"):
        load_price_file(path)


def test_a_trade_price_stored_under_a_non_canonical_name_still_covers_the_canonical_wanted_name(tmp_path, ninja):
    path = tmp_path / "data" / "prices.json"
    entry = {"chaos": 5, "source": TRADE_SOURCE, "detail": {"league": "Allflame", "date": "2026-10-29"}}
    write_raw(path, {"Chaos Orb": {"chaos": 1, "source": "poe.ninja"}, UNORDERED: entry})
    wanted = tmp_path / "wanted.txt"
    wanted.write_text(CANONICAL + "\n", encoding="utf-8")
    asked = Asked()

    old = load_price_file(path)
    fetch_price_file(ninja, NOW, [CANONICAL], stages=(asked,), old_price_file=old)
    code = main(["fetch", "--wanted-file", str(wanted)], get_json=ninja, now=NOW, env=cli_env(tmp_path))

    assert asked.names == []
    assert code == 0
    assert load_price_file(path).prices[CANONICAL].source == TRADE_SOURCE  # kept, under the canonical name
    assert UNORDERED not in load_price_file(path).prices


# -- a failed stash overview ------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["Beast", "BaseType"])
def test_a_failed_stash_overview_warns_and_the_other_categories_finish(ninja, kind):
    ninja.stash_overviews[kind] = SourceError(f"HTTP 500 for {kind}")
    other = "BaseType" if kind == "Beast" else "Beast"

    result = fetch_price_file(ninja, NOW)

    assert any(kind in line and f"HTTP 500 for {kind}" in line for line in result.warnings)
    assert "Hollow Fossil" in result.price_file.prices
    keys = result.price_file.prices
    if kind == "Beast":
        assert "Wild Bristle Matron" not in keys and any("ilvl" in name for name in keys)
    else:
        assert "Wild Bristle Matron" in keys and not any("ilvl" in name for name in keys)
    assert other not in " ".join(result.warnings)


def old_file_with_stash_prices():
    return PriceFile("Allflame", datetime(2026, 10, 25, tzinfo=UTC), 400.0, {
        "Chaos Orb": PriceEntry(1.0, "poe.ninja"),
        "Wild Bristle Matron": PriceEntry(7.0, "poe.ninja"),
        CANONICAL: PriceEntry(9.0, "poe.ninja"),
        "Old Trade Thing": PriceEntry(3.0, TRADE_SOURCE),
    })


def test_a_failed_beast_overview_keeps_the_old_beast_prices(ninja):
    ninja.stash_overviews["Beast"] = SourceError("HTTP 500 for Beast")

    result = fetch_price_file(ninja, NOW, old_price_file=old_file_with_stash_prices())

    assert result.price_file.prices["Wild Bristle Matron"] == PriceEntry(7.0, "poe.ninja")
    assert CANONICAL not in result.price_file.prices or result.price_file.prices[CANONICAL].chaos != 9.0
    assert "Old Trade Thing" not in result.price_file.prices  # the merge, not the fetch, keeps trade prices
    assert any("Beast" in line and "kept" in line for line in result.warnings)


def test_a_failed_base_overview_keeps_the_old_base_prices(ninja):
    ninja.stash_overviews["BaseType"] = SourceError("HTTP 500 for BaseType")

    result = fetch_price_file(ninja, NOW, old_price_file=old_file_with_stash_prices())

    assert result.price_file.prices[CANONICAL] == PriceEntry(9.0, "poe.ninja")
    assert result.price_file.prices["Wild Bristle Matron"].chaos != 7.0  # the fresh beast overview
    assert any("BaseType" in line and "kept" in line for line in result.warnings)


def test_old_stash_prices_of_another_league_are_not_kept(ninja):
    ninja.stash_overviews["Beast"] = SourceError("HTTP 500 for Beast")
    old = old_file_with_stash_prices()

    result = fetch_price_file(ninja, NOW, old_price_file=PriceFile("Standard", old.fetched_at, 400.0, old.prices))

    assert "Wild Bristle Matron" not in result.price_file.prices


def test_a_wanted_beast_with_a_kept_price_is_not_sent_down_the_fallbacks(ninja):
    ninja.stash_overviews["Beast"] = SourceError("HTTP 500 for Beast")
    asked = Asked()

    result = fetch_price_file(
        ninja, NOW, ["Wild Bristle Matron"], stages=(asked,), old_price_file=old_file_with_stash_prices()
    )

    assert asked.names == [] and result.missing == []


def test_a_failed_stash_overview_still_writes_the_file_from_the_command_line(tmp_path, ninja, capsys):
    ninja.stash_overviews["Beast"] = SourceError("HTTP 500 for Beast")
    path = tmp_path / "data" / "prices.json"
    write_price_file(path, old_file_with_stash_prices())

    code = main(["fetch"], get_json=ninja, now=NOW, env=cli_env(tmp_path))

    assert code == 0
    saved = load_price_file(path)
    assert saved.fetched_at == NOW.replace(microsecond=0)
    assert saved.prices["Wild Bristle Matron"].chaos == 7.0
    assert any(line.startswith("Warning:") and "Beast" in line for line in capsys.readouterr().out.splitlines())


def test_a_failed_exchange_overview_still_aborts_the_fetch(ninja):
    ninja.overviews["Fossil"] = SourceError("HTTP 500 for Fossil")

    with pytest.raises(SourceError, match="Fossil"):
        fetch_price_file(ninja, NOW)
