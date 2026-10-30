"""Test helpers for the trade-API pricing: a fake transport that answers from the recorded responses.

Not a conftest: a test module imports `network_guard` (an autouse fixture) to switch it on for every
test of that module, the way the `data` tests import `no_network` from `repoe_support`.
"""

import copy
import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest

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


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


@pytest.fixture(autouse=True)
def network_guard(monkeypatch):
    """Any connection (or name lookup) to a host other than loopback fails with AssertionError.

    The local `http.server` tests of the real transport still work; the pathofexile.com host never
    gets a packet, not even a DNS question.
    """

    def check(host) -> None:
        if isinstance(host, bytes):
            host = host.decode("ascii", errors="replace")
        if host not in LOOPBACK_HOSTS:
            raise AssertionError(f"the test used the network: {host!r}")

    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    real_getaddrinfo, real_create_connection = socket.getaddrinfo, socket.create_connection

    def connect(self, address, *args, **kwargs):
        if isinstance(address, tuple):
            check(address[0])
        return real_connect(self, address, *args, **kwargs)

    def connect_ex(self, address, *args, **kwargs):
        if isinstance(address, tuple):
            check(address[0])
        return real_connect_ex(self, address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):
        check(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def create_connection(address, *args, **kwargs):
        check(address[0])
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", create_connection)


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
