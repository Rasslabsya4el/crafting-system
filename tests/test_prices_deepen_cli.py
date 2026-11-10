"""`python -m crafting_system.prices fetch --trade-below N`: the thin lines are read beside the trade site's offers, anonymously (#616)."""

import json
from datetime import UTC, datetime

from ninja_support import ninja  # noqa: F401  (a fixture)

from crafting_system.prices import load_price_file
from crafting_system.prices.__main__ import main
from crafting_system.prices.trade_http import HttpRequest, HttpResponse

NOW = datetime(2026, 10, 30, 21, 0, 5, tzinfo=UTC)
STATIC = {"result": [{"id": "Delve", "entries": [{"id": "hollow-fossil", "text": "Hollow Fossil"}, {"id": "bound-fossil", "text": "Bound Fossil"}]}]}
RATE_HEADERS = {"content-type": "application/json", "x-rate-limit-policy": "trade-exchange-request-limit", "x-rate-limit-rules": "Ip", "x-rate-limit-ip": "5:10:60", "x-rate-limit-ip-state": "1:10:0"}


def offers(*asks_and_stock):
    return {"total": len(asks_and_stock), "result": {f"id{i}": {"listing": {"offers": [{"exchange": {"currency": "chaos", "amount": ask}, "item": {"amount": 1, "stock": stock}}]}} for i, (ask, stock) in enumerate(asks_and_stock)}}


class FakeExchange:
    """The trade site's static list and bulk exchange: the offers asked for by item id are in `answers`."""

    def __init__(self, answers):
        self.answers = answers
        self.requests: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        if request.url.endswith("/data/static"):
            return HttpResponse(200, dict(RATE_HEADERS), json.dumps(STATIC).encode())
        assert "/exchange/Allflame" in request.url and request.method == "POST", request.url
        item = json.loads(request.body)["query"]["want"][0]
        return HttpResponse(200, dict(RATE_HEADERS), json.dumps(self.answers[item]).encode())


def run(tmp_path, ninja, transport, *argv):
    env = {"CRAFTING_DATA_DIR": str(tmp_path / "data")}
    return main(["fetch", *argv], get_json=ninja, now=NOW, env=env, transport=transport, sleep=lambda seconds: None, monotonic=lambda: 0.0)


def wanted(tmp_path, *names):
    path = tmp_path / "wanted.txt"
    path.write_text("\n".join(names) + "\n", encoding="utf-8")
    return str(path)


def test_a_thin_line_is_replaced_by_the_deeper_trade_reading_and_the_other_is_kept_in_the_provenance(ninja, tmp_path):
    shallow = load_price_file(_first_fetch(ninja, tmp_path)).prices["Hollow Fossil"]
    exchange = FakeExchange({"hollow-fossil": offers(*[(300 + i, 10) for i in range(12)]), "bound-fossil": offers(*[(1, 1)] * 12)})

    code = run(tmp_path, ninja, exchange, "--wanted-file", wanted(tmp_path, "Hollow Fossil", "Bound Fossil"), "--trade-below", "1000000")

    assert code == 0
    saved = load_price_file(tmp_path / "data" / "prices.json").prices
    hollow = saved["Hollow Fossil"]
    assert (hollow.source, hollow.chaos, hollow.provenance.kind, hollow.provenance.depth) == ("trade-api", 300.0, "trade", 10.0)
    assert hollow.provenance.other == {"kind": "ninja-exchange", "chaos": shallow.chaos, "depth": shallow.provenance.depth}
    assert saved["Bound Fossil"].source == "poe.ninja" and saved["Bound Fossil"].provenance.other["kind"] == "trade"  # the exchange line is the deeper one


def _first_fetch(ninja, tmp_path):
    code = main(["fetch"], get_json=ninja, now=NOW, env={"CRAFTING_DATA_DIR": str(tmp_path / "plain")})
    assert code == 0
    return tmp_path / "plain" / "prices.json"


def test_without_the_option_no_request_goes_to_the_trade_site(ninja, tmp_path):
    exchange = FakeExchange({})

    code = run(tmp_path, ninja, exchange, "--wanted-file", wanted(tmp_path, "Hollow Fossil"))

    assert code == 0 and exchange.requests == []


def test_the_requests_are_anonymous(ninja, tmp_path):
    exchange = FakeExchange({"hollow-fossil": offers((300, 40)), "bound-fossil": offers((1, 1))})

    run(tmp_path, ninja, exchange, "--wanted-file", wanted(tmp_path, "Hollow Fossil"), "--trade-below", "1000000")

    assert exchange.requests and all("Cookie" not in request.headers for request in exchange.requests)


# --- a site that stops the run: what poe.ninja gave is written, and every name left unread is reported and marked (#616) ----------------------------------


class BlockingExchange(FakeExchange):
    """The static list and the first `allowed` exchange answers are served; the next exchange request is refused with a 403 (a block)."""

    def __init__(self, answers, allowed):
        super().__init__(answers)
        self.allowed = allowed

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.url.endswith("/data/static") or self.allowed > 0:
            self.allowed -= not request.url.endswith("/data/static")
            return super().__call__(request)
        self.requests.append(request)
        return HttpResponse(403, {"content-type": "application/json"}, b'{"error":{"message":"Forbidden"}}')


ANSWERS = {"hollow-fossil": offers(*[(300 + i, 10) for i in range(12)]), "bound-fossil": offers(*[(2, 30)] * 12)}


def test_a_blocked_trade_site_does_not_throw_away_the_poe_ninja_prices_and_the_unread_names_are_reported_and_marked(ninja, tmp_path, capsys):
    exchange = BlockingExchange(ANSWERS, allowed=1)  # Bound Fossil is read, Hollow Fossil meets the block

    code = run(tmp_path, ninja, exchange, "--wanted-file", wanted(tmp_path, "Hollow Fossil", "Bound Fossil"), "--trade-below", "1000000")

    saved = load_price_file(tmp_path / "data" / "prices.json").prices
    shallow = load_price_file(_first_fetch(ninja, tmp_path)).prices["Hollow Fossil"]
    err = capsys.readouterr().err
    assert code == 1  # the run is incomplete and says so, after it has written
    assert saved["Hollow Fossil"].chaos == shallow.chaos and saved["Hollow Fossil"].source == "poe.ninja"  # the poe.ninja price is kept
    assert saved["Hollow Fossil"].provenance.trade_unread == "the trade site blocked the run"
    assert saved["Bound Fossil"].provenance.trade_unread is None  # read before the block
    assert "1 names were not read on the trade site (the trade site blocked the run)" in err and "  Hollow Fossil" in err
    assert len(saved) > 2  # the whole poe.ninja fetch is there, not only the wanted names


def test_a_spent_request_budget_does_not_throw_away_the_poe_ninja_prices_and_the_unread_names_are_reported_and_marked(ninja, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("crafting_system.prices.__main__.MAX_DEEPEN_REQUESTS", 2)  # the static list and one exchange read
    exchange = FakeExchange(ANSWERS)

    code = run(tmp_path, ninja, exchange, "--wanted-file", wanted(tmp_path, "Hollow Fossil", "Bound Fossil"), "--trade-below", "1000000")

    saved = load_price_file(tmp_path / "data" / "prices.json").prices
    err = capsys.readouterr().err
    assert code == 1
    assert saved["Hollow Fossil"].source == "poe.ninja"
    assert saved["Hollow Fossil"].provenance.trade_unread == "the request budget of the run was spent"
    assert "1 names were not read on the trade site (the request budget of the run was spent)" in err and "  Hollow Fossil" in err
    assert len(exchange.requests) == 2


def test_a_site_that_blocks_the_static_list_leaves_every_wanted_name_unread_and_still_writes_the_file(ninja, tmp_path, capsys):
    def blocked(request: HttpRequest) -> HttpResponse:
        return HttpResponse(403, {"content-type": "application/json"}, b"{}")

    code = run(tmp_path, ninja, blocked, "--wanted-file", wanted(tmp_path, "Hollow Fossil", "Bound Fossil"), "--trade-below", "1000000")

    saved = load_price_file(tmp_path / "data" / "prices.json").prices
    err = capsys.readouterr().err
    assert code == 1
    assert saved["Hollow Fossil"].provenance.trade_unread == saved["Bound Fossil"].provenance.trade_unread == "the trade site blocked the run"
    assert "names were not read on the trade site (the trade site blocked the run)" in err and "  Hollow Fossil" in err and "  Bound Fossil" in err
