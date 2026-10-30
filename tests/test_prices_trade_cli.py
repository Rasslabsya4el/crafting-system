"""`python -m crafting_system.prices trade`: the owner's hand-started trade pricing, on recorded responses (#39)."""

import json
import re
from datetime import timedelta

import pytest

from ninja_support import ninja  # noqa: F401  (a fixture)
from repoe_support import fixture_game_data
from trade_support import NOW, R12_SPEC, SECRET, FakeTrade, api_row, price_file

from crafting_system.data import DataError
from crafting_system.prices import (
    TRADE_SOURCE,
    PriceEntry,
    load_price_file,
    load_prices,
    package_version,
    user_agent,
    write_price_file,
)
from crafting_system.prices.__main__ import main
from crafting_system.prices.trade_pricing import QUERY_TTL

REPO_URL = "https://github.com/Rasslabsya4el/crafting-system"


@pytest.fixture(autouse=True)
def game_data(monkeypatch):
    """The repoe data the family ids come from: the small fixture set, not the real cache."""
    monkeypatch.setattr("crafting_system.prices.__main__.load_game_data", lambda **kwargs: fixture_game_data())


@pytest.fixture
def trade():
    return FakeTrade()


@pytest.fixture
def prices_path(tmp_path):
    path = tmp_path / "data" / "prices.json"
    write_price_file(path, price_file())
    return path


def run(tmp_path, trade, *argv, spec=R12_SPEC, now=NOW, env=None, ninja=None):
    environment = {"CRAFTING_DATA_DIR": str(tmp_path / "data"), "CRAFTING_CACHE_DIR": str(tmp_path / "cache")}
    environment.update(env or {})
    command = ["trade", "--spec", str(spec), *argv]
    return main(
        command,
        transport=trade,
        sleep=lambda seconds: None,
        monotonic=lambda: 0.0,
        now=now,
        env=environment,
    )


def search_body(trade):
    request = next(r for r, kind in zip(trade.requests, trade.kinds) if kind == "search")
    return json.loads(request.body)


# -- R12 end to end --------------------------------------------------------------------------------


def test_r12_is_priced_end_to_end_and_the_query_sent_is_the_r12_query(tmp_path, trade, prices_path):
    code = run(tmp_path, trade)

    assert code == 0
    body = search_body(trade)["query"]
    assert body["stats"][0]["filters"][0]["id"] == "fractured.stat_1671376347"
    filters = body["filters"]
    assert filters["misc_filters"]["filters"]["fractured_item"] == {"option": "true"}
    assert filters["misc_filters"]["filters"]["ilvl"] == {"min": 75}
    assert filters["misc_filters"]["filters"]["corrupted"] == {"option": "false"}
    assert filters["misc_filters"]["filters"]["mirrored"] == {"option": "false"}
    assert filters["type_filters"]["filters"]["category"] == {"option": "accessory.amulet"}
    assert "/search/Allflame" in trade.requests[1].url


def test_r12_entry_is_stored_beside_the_untouched_poe_ninja_prices(tmp_path, trade, prices_path):
    before = load_price_file(prices_path)

    run(tmp_path, trade)

    saved = load_price_file(prices_path)
    entry = saved.prices["R12 start amulet"]
    assert (entry.chaos, entry.source) == (1.0, TRADE_SOURCE)
    assert (entry.detail["listings"], entry.detail["used"], entry.detail["league"]) == (910, 5, "Allflame")
    assert re.fullmatch(r"[0-9a-f]{64}", entry.detail["query_hash"])
    assert entry.detail["query"] == search_body(trade)
    assert {k: v for k, v in saved.prices.items() if k != "R12 start amulet"} == before.prices
    assert (saved.fetched_at, saved.league, saved.chaos_per_divine) == (
        before.fetched_at,
        before.league,
        before.chaos_per_divine,
    )


def test_the_report_names_price_counts_league_and_requests(tmp_path, trade, prices_path, capsys):
    run(tmp_path, trade)

    out = capsys.readouterr().out
    assert "R12 start amulet" in out and "1 Chaos" in out and "0.0025 Divine" in out
    assert "5 of 10" in out and "910" in out and "Allflame" in out
    assert "3 requests" in out


def test_dropped_listings_are_reported_one_line_per_reason(tmp_path, trade, prices_path, capsys):
    trade.rows = [api_row(n) for n in (1, 2, 3, 4)] + [api_row(priced=False), api_row(5, "coin-of-doom")]

    run(tmp_path, trade)

    out = capsys.readouterr().out
    assert "1 no price" in out and "1 unknown currency" in out


def test_the_user_agent_names_the_tool_a_version_and_the_repo(tmp_path, trade, prices_path):
    run(tmp_path, trade)

    agents = {request.headers["User-Agent"] for request in trade.requests}
    assert agents == {user_agent(package_version())}
    assert re.fullmatch(rf"crafting-system/\S+ \(\+{re.escape(REPO_URL)}\)", agents.pop())


# -- budget and caches -----------------------------------------------------------------------------


def test_a_budget_of_two_stops_with_an_error_and_leaves_the_file_alone(tmp_path, trade, prices_path, capsys):
    before = prices_path.read_bytes()

    code = run(tmp_path, trade, "--max-requests", "2")

    assert code == 1
    assert "budget" in capsys.readouterr().err
    assert prices_path.read_bytes() == before


def test_a_second_run_is_answered_from_the_cache_with_no_request(tmp_path, trade, prices_path, capsys):
    run(tmp_path, trade)
    first = load_price_file(prices_path)
    trade.requests.clear()
    capsys.readouterr()

    code = run(tmp_path, trade)

    assert code == 0 and trade.requests == []
    assert "0 requests" in capsys.readouterr().out
    assert load_price_file(prices_path) == first


def test_refresh_stats_asks_for_the_list_again(tmp_path, trade, prices_path):
    run(tmp_path, trade)
    trade.requests.clear()

    run(tmp_path, trade, "--refresh-stats")

    assert trade.kinds == ["stats"]


def test_an_expired_query_cache_is_asked_again(tmp_path, trade, prices_path):
    run(tmp_path, trade)
    trade.requests.clear()

    run(tmp_path, trade, now=NOW + QUERY_TTL + timedelta(minutes=5))

    assert trade.kinds == ["search", "fetch"]


def test_k_and_league_are_taken_from_the_command_line(tmp_path, trade, prices_path):
    run(tmp_path, trade, "--k", "3", "--league", "Standard")

    assert "/search/Standard" in trade.requests[1].url
    detail = load_price_file(prices_path).prices["R12 start amulet"].detail
    assert (detail["k"], detail["used"], detail["league"]) == (3, 3, "Standard")


# -- failures leave the price file alone -----------------------------------------------------------


@pytest.mark.parametrize(
    ("how", "fragment"), [("403", "403"), ("429", "429"), ("html", "Cloudflare")]
)
@pytest.mark.parametrize("kind", ["stats", "search", "fetch"])
def test_a_refusal_exits_1_names_it_and_leaves_the_file_byte_identical(
    tmp_path, trade, prices_path, capsys, how, fragment, kind
):
    before = prices_path.read_bytes()
    trade.fail(kind, how)

    code = run(tmp_path, trade)

    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("Error:") and fragment in err
    assert prices_path.read_bytes() == before


def test_a_403_without_a_cookie_says_how_to_set_one(tmp_path, trade, prices_path, capsys):
    trade.fail("search", "403")

    run(tmp_path, trade)

    assert "POESESSID" in capsys.readouterr().err


def test_a_429_reports_the_retry_after(tmp_path, trade, prices_path, capsys):
    trade.fail("search", "429")

    run(tmp_path, trade)

    assert "60" in capsys.readouterr().err


def test_too_few_priced_listings_exit_1_and_leave_the_file(tmp_path, trade, prices_path, capsys):
    trade.rows = [api_row(1), api_row(2), api_row(priced=False)]
    before = prices_path.read_bytes()

    code = run(tmp_path, trade)

    assert code == 1
    assert "no price" in capsys.readouterr().err
    assert prices_path.read_bytes() == before


def test_a_search_with_no_listings_exits_1_and_leaves_the_file(tmp_path, trade, prices_path, capsys):
    trade.search.update(total=0, result=[])
    before = prices_path.read_bytes()

    assert run(tmp_path, trade) == 1
    assert prices_path.read_bytes() == before
    assert capsys.readouterr().err.startswith("Error:")


def test_a_name_that_is_a_poe_ninja_price_is_refused(tmp_path, trade, prices_path, capsys):
    spec = tmp_path / "spec.yaml"
    spec.write_text(R12_SPEC.read_text(encoding="utf-8").replace("R12 start amulet", "Hollow Fossil"), encoding="utf-8")
    before = prices_path.read_bytes()

    code = run(tmp_path, trade, spec=spec)

    assert code == 1
    assert "collides with a poe.ninja price" in capsys.readouterr().err
    assert prices_path.read_bytes() == before


def test_a_missing_price_file_says_to_run_fetch_first(tmp_path, trade, capsys):
    code = run(tmp_path, trade)

    assert code == 1
    assert "prices fetch" in capsys.readouterr().err
    assert trade.requests == []


def test_a_bad_spec_file_exits_1_without_a_request(tmp_path, trade, prices_path, capsys):
    spec = tmp_path / "spec.yaml"
    spec.write_text("name: x\nbogus: 1\n", encoding="utf-8")

    code = run(tmp_path, trade, spec=spec)

    assert code == 1
    assert "bogus" in capsys.readouterr().err and trade.requests == []


def test_without_game_data_a_text_stat_still_prices_and_a_note_is_printed(tmp_path, trade, prices_path, capsys, monkeypatch):
    def missing(**kwargs):
        raise DataError("no cache")

    monkeypatch.setattr("crafting_system.prices.__main__.load_game_data", missing)
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "name: Text amulet\ncategory: accessory.amulet\nmods:\n  - stat: '+#% to Lightning Resistance'\n    fractured: true\n",
        encoding="utf-8",
    )

    code = run(tmp_path, trade, spec=spec)

    assert code == 0
    assert "crafting_system.data fetch" in capsys.readouterr().out
    assert "Text amulet" in load_price_file(prices_path).prices


# -- a hand override wins --------------------------------------------------------------------------


def test_a_hand_override_for_the_spec_name_means_no_request_and_the_override_wins(tmp_path, trade, prices_path, capsys):
    overrides = tmp_path / "data" / "price_overrides.toml"
    overrides.write_text('[prices]\n"R12 start amulet" = 7\n', encoding="utf-8")
    before = prices_path.read_bytes()

    code = run(tmp_path, trade)

    assert code == 0 and trade.requests == []
    assert "override" in capsys.readouterr().out
    assert prices_path.read_bytes() == before
    assert load_prices(prices_path, overrides).prices["R12 start amulet"] == PriceEntry(7.0, "override")


# -- fetch keeps the trade prices ------------------------------------------------------------------


def old_file_with_trade(path, league="Allflame"):
    base = price_file(league=league)
    entry = PriceEntry(2.0, TRADE_SOURCE, "median", {"league": league, "listings": 910})
    write_price_file(path, price_file(league=league, prices={**base.prices, "R12 start amulet": entry}))


def fetch(tmp_path, ninja, trade, *argv):
    env = {"CRAFTING_DATA_DIR": str(tmp_path / "data"), "CRAFTING_CACHE_DIR": str(tmp_path / "cache")}
    return main(["fetch", *argv], get_json=ninja, now=NOW, env=env, transport=trade)


def test_fetch_keeps_a_trade_price_of_the_same_league_and_never_calls_the_trade_site(tmp_path, ninja, trade, prices_path):
    old_file_with_trade(prices_path)

    code = fetch(tmp_path, ninja, trade)

    assert code == 0 and trade.requests == []
    saved = load_price_file(prices_path)
    assert saved.prices["R12 start amulet"].detail == {"league": "Allflame", "listings": 910}
    assert saved.prices["Hollow Fossil"].chaos == 206.8  # the fresh poe.ninja number


def test_fetch_for_another_league_drops_the_trade_price_with_a_warning(tmp_path, ninja, trade, prices_path, capsys):
    old_file_with_trade(prices_path)

    fetch(tmp_path, ninja, trade, "--league", "Standard")

    assert "R12 start amulet" not in load_price_file(prices_path).prices
    out = capsys.readouterr().out
    assert any(line.startswith("Warning:") and "R12 start amulet" in line for line in out.splitlines())


def test_fetch_ignores_an_old_file_that_does_not_load(tmp_path, ninja, trade, prices_path):
    prices_path.write_text("{not json", encoding="utf-8")

    assert fetch(tmp_path, ninja, trade) == 0
    assert load_price_file(prices_path).league == "Allflame"


# -- the session cookie ----------------------------------------------------------------------------


def test_the_cookie_is_sent_only_when_set_and_only_as_a_cookie_header(tmp_path, trade, prices_path):
    run(tmp_path, trade, env={"POESESSID": SECRET})

    assert trade.cookies() == [f"POESESSID={SECRET}"] * 3
    assert SECRET not in trade.sent_text()


def test_without_the_variable_or_with_an_empty_one_no_cookie_is_sent(tmp_path, trade, prices_path):
    run(tmp_path, trade, env={"POESESSID": ""})

    assert trade.cookies() == [None] * 3


def tree_text(tmp_path):
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in tmp_path.rglob("*") if p.is_file())


def test_the_cookie_value_is_in_no_output_price_file_or_cache_file(tmp_path, trade, prices_path, capsys):
    run(tmp_path, trade, env={"POESESSID": SECRET})

    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert SECRET not in tree_text(tmp_path)


@pytest.mark.parametrize("how", ["403", "429", "html"])
def test_the_cookie_value_is_in_no_error_message_either(tmp_path, trade, prices_path, capsys, how):
    trade.fail("search", how)

    code = run(tmp_path, trade, env={"POESESSID": SECRET})

    captured = capsys.readouterr()
    assert code == 1 and SECRET not in captured.out + captured.err
    assert SECRET not in tree_text(tmp_path)
