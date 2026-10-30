"""Test helpers for the trade-API pricing: a fake transport that answers from the recorded responses.

The network guard for these tests lives in `conftest.py`, where it covers every `test_prices_*.py` module.
"""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.trade_http import (
    HttpRequest,
    HttpResponse,
    RateLimiter,
    RequestBudget,
    TradeClient,
    user_agent,
)

TRADE_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "trade"
RECORDED = TRADE_FIXTURES / "recorded"
R12_SPEC = TRADE_FIXTURES / "r12_buy_spec.yaml"
SECRET = "SECRET-COOKIE-123"
NOW = datetime(2026, 10, 30, 21, 30, 0, tzinfo=UTC)


def recorded(name: str):
    return json.loads((RECORDED / name).read_text(encoding="utf-8"))


def kind_of(url: str) -> str:
    if "/data/stats" in url:
        return "stats"
    if "/search/" in url:
        return "search"
    if "/fetch/" in url:
        return "fetch"
    raise AssertionError(f"unexpected URL {url}")


class FakeTrade:
    """A `Transport` that serves the recorded stats list, search answer and fetch rows; no network.

    `stats`, `search` and `rows` hold the bodies to give (edit them to make other cases). Every request
    is kept in `requests`, its kind ("stats", "search", "fetch") in `kinds`. `fail(kind, how)` makes
    one kind answer with "403", "429" or "html" (HTTP 200 with a Cloudflare page) instead.
    """

    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []
        self.stats = recorded("stats_excerpt.json")
        self.search = recorded("search_r12.json")
        self.rows = recorded("fetch_r12.json")["result"]
        self.headers = {
            kind: recorded(f"headers_{kind}.json")["headers"] for kind in ("stats", "search", "fetch")
        }
        self.failures: dict[str, str] = {}

    @property
    def kinds(self) -> list[str]:
        return [kind_of(request.url) for request in self.requests]

    def fail(self, kind: str, how: str) -> None:
        self.failures[kind] = how

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        kind = kind_of(request.url)
        how = self.failures.get(kind)
        if how == "403":
            return HttpResponse(403, {"content-type": "application/json"}, b'{"error":{"message":"Forbidden"}}')
        if how == "429":
            return HttpResponse(429, {"retry-after": "60"}, b'{"error":{"message":"Rate limit exceeded"}}')
        if how == "html":
            page = b"<html><title>Just a moment...</title>Cloudflare</html>"
            return HttpResponse(200, {"content-type": "text/html"}, page)
        body = {
            "stats": self.stats,
            "search": self.search,
            "fetch": {"result": self.rows},
        }[kind]
        return HttpResponse(200, dict(self.headers[kind]), json.dumps(copy.deepcopy(body)).encode("utf-8"))

    def sent_text(self) -> str:
        """Everything the fake saw except the Cookie header values, for leak checks."""
        return "\n".join(f"{r.method} {r.url} {r.body!r}" for r in self.requests)

    def cookies(self) -> list[str | None]:
        return [request.headers.get("Cookie") for request in self.requests]


def api_row(amount=1, currency="chaos", *, fractured=True, influences=None, priced=True) -> dict:
    """One fetch row shaped like the recorded ones."""
    row = copy.deepcopy(recorded("fetch_r12.json")["result"][0])
    row["item"]["fractured"] = fractured
    if influences is not None:
        row["item"]["influences"] = influences
    if priced:
        row["listing"]["price"] = {"type": "~b/o", "amount": amount, "currency": currency}
    else:
        del row["listing"]["price"]
    return row


def price_file(**changes) -> PriceFile:
    """A poe.ninja-style price file for Allflame with the rates the conversions need."""
    fields = {
        "league": "Allflame",
        "fetched_at": datetime(2026, 10, 30, 20, 24, 0, tzinfo=UTC),
        "chaos_per_divine": 400.0,
        "prices": {
            "Chaos Orb": PriceEntry(1.0, "poe.ninja"),
            "Divine Orb": PriceEntry(400.0, "poe.ninja"),
            "Exalted Orb": PriceEntry(20.0, "poe.ninja"),
            "Hollow Fossil": PriceEntry(206.8, "poe.ninja"),
        },
    }
    fields.update(changes)
    return PriceFile(**fields)


def make_client(trade: FakeTrade, max_requests: int = 4, cookie: str | None = None) -> TradeClient:
    """A client on the fake: a frozen clock and a sleep that does nothing."""
    limiter = RateLimiter(lambda: 0.0, lambda seconds: None)
    return TradeClient(trade, user_agent("1.0"), limiter, RequestBudget(max_requests), cookie)
