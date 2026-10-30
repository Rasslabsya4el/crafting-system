"""The trade-API HTTP layer: rate-limit headers, the limiter, the budget, the client and the stop rules.

Everything runs on canned responses, a fake clock and a fake sleep; the real transport is tried only
against a local server on 127.0.0.1. No test imports a clock module (ADR-0014).
"""

import http.server
import json
import socket
import threading

import pytest
from trade_support import network_guard  # noqa: F401

from crafting_system.prices.trade_http import (
    BudgetExceeded,
    HttpRequest,
    HttpResponse,
    RateLimiter,
    RateReport,
    RateRule,
    RequestBudget,
    RuleState,
    TradeBlocked,
    TradeClient,
    TradeError,
    package_version,
    parse_rate_limits,
    urllib_transport,
    user_agent,
)

REPO_URL = "https://github.com/Rasslabsya4el/crafting-system"
SECRET = "SECRET-COOKIE-123"

SEARCH_HEADERS = {
    "x-rate-limit-policy": "trade-search-request-limit",
    "x-rate-limit-rules": "Ip",
    "x-rate-limit-ip": "8:10:60,15:60:120,60:300:1800",
    "x-rate-limit-ip-state": "1:10:0,1:60:0,1:300:0",
}


def search_headers(state: str, limit: str = "8:10:60,15:60:120,60:300:1800") -> dict[str, str]:
    return {**SEARCH_HEADERS, "x-rate-limit-ip": limit, "x-rate-limit-ip-state": state}


class FakeClock:
    """A clock the test moves by hand; `sleep` records the request and moves the clock."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_limiter(clock: FakeClock, **options) -> RateLimiter:
    return RateLimiter(clock, clock.sleep, **options)


# --- parsing the headers -------------------------------------------------------------------


def test_parse_the_research_sample() -> None:
    report = parse_rate_limits(SEARCH_HEADERS)
    assert report == RateReport(
        policy="trade-search-request-limit",
        rules=(
            (
                "Ip",
                (
                    (RateRule(8, 10, 60), RuleState(1, 10, 0)),
                    (RateRule(15, 60, 120), RuleState(1, 60, 0)),
                    (RateRule(60, 300, 1800), RuleState(1, 300, 0)),
                ),
            ),
        ),
    )


def test_parse_two_rules() -> None:
    headers = {
        **SEARCH_HEADERS,
        "x-rate-limit-rules": "Ip,Account",
        "x-rate-limit-account": "3:5:60",
        "x-rate-limit-account-state": "2:5:0",
    }
    report = parse_rate_limits(headers)
    assert report is not None
    assert [name for name, _ in report.rules] == ["Ip", "Account"]
    assert report.rules[1][1] == ((RateRule(3, 5, 60), RuleState(2, 5, 0)),)


def test_parse_without_a_policy_header_is_none() -> None:
    assert parse_rate_limits({}) is None
    assert parse_rate_limits({"content-type": "application/json"}) is None


@pytest.mark.parametrize(
    ("change", "named"),
    [
        ({"x-rate-limit-ip": "8:10"}, "x-rate-limit-ip"),
        ({"x-rate-limit-ip": "8:ten:60,15:60:120,60:300:1800"}, "x-rate-limit-ip"),
        ({"x-rate-limit-ip-state": "1:10:0"}, "x-rate-limit-ip-state"),
        ({"x-rate-limit-ip-state": "1:10:0,1:60:0,x:300:0"}, "x-rate-limit-ip-state"),
        ({"x-rate-limit-ip-state": ""}, "x-rate-limit-ip-state"),
        ({"x-rate-limit-ip": None}, "x-rate-limit-ip"),
        ({"x-rate-limit-rules": None}, "x-rate-limit-rules"),
    ],
)
def test_parse_a_malformed_header_names_it(change: dict, named: str) -> None:
    headers = {**SEARCH_HEADERS, **change}
    headers = {key: value for key, value in headers.items() if value is not None}
    with pytest.raises(TradeError, match=named):
        parse_rate_limits(headers)


# --- the limiter ---------------------------------------------------------------------------


def test_no_report_yet_means_no_wait() -> None:
    clock = FakeClock()
    make_limiter(clock).before("search")
    assert clock.sleeps == []


def test_a_response_without_rate_headers_means_no_wait() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.after("search", {"content-type": "application/json"})
    limiter.before("search")
    assert clock.sleeps == []


def test_no_wait_below_the_margin() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.after("search", search_headers("6:10:0,1:60:0,1:300:0"))  # 6 of 8: two left
    limiter.before("search")
    assert clock.sleeps == []


def test_wait_one_period_when_one_hit_is_left() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.after("search", search_headers("7:10:0,1:60:0,1:300:0"))  # 7 >= 8 - 1
    limiter.before("search")
    assert clock.sleeps == [10]


def test_margin_is_a_setting() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock, margin=3)
    limiter.after("search", search_headers("5:10:0,1:60:0,1:300:0"))  # 5 >= 8 - 3
    limiter.before("search")
    assert clock.sleeps == [10]


def test_the_longest_period_among_full_rules_wins() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.after("search", search_headers("7:10:0,14:60:0,1:300:0"))
    limiter.before("search")
    assert clock.sleeps == [60]


def test_wait_the_restricted_seconds() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.after("search", search_headers("9:10:45,1:60:0,1:300:0"))
    limiter.before("search")
    assert clock.sleeps == [45]


def test_time_already_passed_is_subtracted() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.after("search", search_headers("7:10:0,1:60:0,1:300:0"))
    clock.now += 4
    limiter.before("search")
    assert clock.sleeps == [6]


def test_no_sleep_when_the_wait_has_passed() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.after("search", search_headers("7:10:0,1:60:0,1:300:0"))
    clock.now += 10
    limiter.before("search")
    assert clock.sleeps == []


def test_a_wait_over_max_wait_stops_without_sleeping() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock, max_wait=120.0)
    limiter.after("search", search_headers("1:10:1800,1:60:0,1:300:0"))
    with pytest.raises(TradeBlocked, match=r"1800 s .* 120 s .* stopping"):
        limiter.before("search")
    assert clock.sleeps == []


def test_a_wait_equal_to_max_wait_is_allowed() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock, max_wait=60.0)
    limiter.after("search", search_headers("1:10:60,1:60:0,1:300:0"))
    limiter.before("search")
    assert clock.sleeps == [60]


def test_kinds_are_independent() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.after("search", search_headers("7:10:0,1:60:0,1:300:0"))
    limiter.before("fetch")
    limiter.before("data")
    assert clock.sleeps == []
    limiter.before("search")
    assert clock.sleeps == [10]


def test_the_latest_report_replaces_the_older_one() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.after("search", search_headers("7:10:0,1:60:0,1:300:0"))
    limiter.after("search", search_headers("1:10:0,1:60:0,1:300:0"))
    limiter.before("search")
    assert clock.sleeps == []


# --- the budget ----------------------------------------------------------------------------


def test_budget_counts_and_refuses_the_next_request() -> None:
    budget = RequestBudget(2)
    assert (budget.used, budget.remaining) == (0, 2)
    budget.spend("search Allflame")
    budget.spend("fetch")
    assert (budget.used, budget.remaining) == (2, 0)
    with pytest.raises(BudgetExceeded, match=r"search again.*2.*2"):
        budget.spend("search again")
    assert budget.used == 2


@pytest.mark.parametrize("bad", [0, -1])
def test_budget_needs_at_least_one_request(bad: int) -> None:
    with pytest.raises(ValueError):
        RequestBudget(bad)


# --- the client ----------------------------------------------------------------------------

BASE = "https://www.pathofexile.com/api/trade"
JSON_HEADERS = {"content-type": "application/json"}


def ok(payload: object = None, headers: dict[str, str] | None = None) -> HttpResponse:
    body = json.dumps({"result": []} if payload is None else payload).encode()
    return HttpResponse(200, {**JSON_HEADERS, **(headers or {})}, body)


class FakeTransport:
    """Hands out canned responses in order and records every request it was given."""

    def __init__(self, *responses: HttpResponse) -> None:
        self.responses = list(responses)
        self.requests: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def make_client(
    *responses: HttpResponse,
    cookie: str | None = None,
    budget: int = 10,
    clock: FakeClock | None = None,
) -> tuple[TradeClient, FakeTransport, FakeClock]:
    clock = clock or FakeClock()
    transport = FakeTransport(*responses)
    client = TradeClient(
        transport,
        user_agent("9.9.9"),
        make_limiter(clock),
        RequestBudget(budget),
        session_cookie=cookie,
    )
    return client, transport, clock


def test_user_agent_names_the_tool_version_and_repo() -> None:
    assert user_agent("1.2.3") == f"crafting-system/1.2.3 (+{REPO_URL})"
    assert REPO_URL in user_agent(package_version())


def test_data_stats_request() -> None:
    client, transport, _ = make_client(ok({"result": [{"id": "explicit"}]}))
    assert client.data_stats() == {"result": [{"id": "explicit"}]}
    (request,) = transport.requests
    assert request.method == "GET"
    assert request.url == f"{BASE}/data/stats"
    assert request.body is None
    assert request.headers == {"User-Agent": user_agent("9.9.9"), "Accept": "application/json"}


def test_search_request() -> None:
    client, transport, _ = make_client(ok({"id": "QUERYID", "result": ["a"], "total": 1}))
    body = {"query": {"status": {"option": "online"}}, "sort": {"price": "asc"}}
    assert client.search("Allflame", body)["id"] == "QUERYID"
    (request,) = transport.requests
    assert request.method == "POST"
    assert request.url == "https://www.pathofexile.com/api/trade/search/Allflame"
    assert json.loads(request.body) == body
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["User-Agent"] == user_agent("9.9.9")
    assert request.headers["Accept"] == "application/json"


def test_search_quotes_the_league() -> None:
    client, transport, _ = make_client(ok())
    client.search("Hardcore Allflame", {})
    assert transport.requests[0].url == f"{BASE}/search/Hardcore%20Allflame"


def test_fetch_request() -> None:
    client, transport, _ = make_client(ok())
    client.fetch(["id1", "id2", "id3"], "QUERYID")
    (request,) = transport.requests
    assert request.method == "GET"
    assert request.url == f"{BASE}/fetch/id1,id2,id3?query=QUERYID"
    assert request.body is None


def test_fetch_takes_ten_ids_and_no_more() -> None:
    ten = [f"id{n}" for n in range(10)]
    client, transport, _ = make_client(ok())
    client.fetch(ten, "Q")
    assert transport.requests[0].url == f"{BASE}/fetch/{','.join(ten)}?query=Q"
    with pytest.raises(ValueError):
        client.fetch(ten + ["id10"], "Q")
    with pytest.raises(ValueError):
        client.fetch([], "Q")
    assert len(transport.requests) == 1  # the refused calls did not spend budget or send anything
    assert client.budget.used == 1


def test_the_budget_stops_the_next_request_before_it_is_sent() -> None:
    client, transport, _ = make_client(ok(), ok(), budget=2)
    client.data_stats()
    client.search("Allflame", {})
    with pytest.raises(BudgetExceeded):
        client.fetch(["id1"], "Q")
    assert len(transport.requests) == 2


def test_the_limiter_sleeps_between_calls_of_one_kind() -> None:
    limited = ok(headers=search_headers("7:10:0,1:60:0,1:300:0"))
    client, transport, clock = make_client(limited, ok())
    client.search("Allflame", {})
    client.search("Allflame", {})
    assert clock.sleeps == [10]
    assert len(transport.requests) == 2


def test_limits_of_an_error_response_are_kept() -> None:
    refused = HttpResponse(
        400,
        {**JSON_HEADERS, **search_headers("9:10:30,1:60:0,1:300:0")},
        json.dumps({"error": {"code": 2, "message": "Query is too complex."}}).encode(),
    )
    client, _, clock = make_client(refused, ok())
    with pytest.raises(TradeError):
        client.search("Allflame", {})
    client.search("Allflame", {})
    assert clock.sleeps == [30]


def test_a_wait_over_max_wait_stops_before_the_next_request() -> None:
    limited = ok(headers=search_headers("1:10:1800,1:60:0,1:300:0"))
    client, transport, clock = make_client(limited, ok())
    client.search("Allflame", {})
    with pytest.raises(TradeBlocked):
        client.search("Allflame", {})
    assert clock.sleeps == []
    assert len(transport.requests) == 1


# --- the stop rules ------------------------------------------------------------------------


def test_403_stops_and_hints_about_a_session_when_none_was_sent() -> None:
    client, transport, _ = make_client(HttpResponse(403, JSON_HEADERS, b"{}"))
    with pytest.raises(TradeBlocked) as caught:
        client.search("Allflame", {})
    text = str(caught.value)
    assert "HTTP 403" in text and "Cloudflare challenge or login needed" in text
    assert "nothing was changed" in text
    assert "set POESESSID in your environment yourself; this tool never asks for it" in text
    assert len(transport.requests) == 1  # no retry


def test_403_with_a_cookie_has_no_hint() -> None:
    client, _, _ = make_client(HttpResponse(403, JSON_HEADERS, b"{}"), cookie=SECRET)
    with pytest.raises(TradeBlocked) as caught:
        client.search("Allflame", {})
    text = str(caught.value)
    assert "HTTP 403" in text
    assert "POESESSID" not in text
    assert SECRET not in text


def test_401_is_a_refusal_too() -> None:
    client, _, _ = make_client(HttpResponse(401, JSON_HEADERS, b"{}"))
    with pytest.raises(TradeBlocked, match="HTTP 401"):
        client.data_stats()


def test_429_stops_and_reports_retry_after() -> None:
    client, transport, _ = make_client(
        HttpResponse(429, {**JSON_HEADERS, "retry-after": "60"}, b'{"error": {"code": 3, "message": "Rate limit exceeded"}}')
    )
    with pytest.raises(TradeBlocked, match=r"HTTP 429.*60 s") as caught:
        client.search("Allflame", {})
    assert "retry" in str(caught.value).lower()
    assert len(transport.requests) == 1


def test_429_without_retry_after_still_stops() -> None:
    client, _, _ = make_client(HttpResponse(429, JSON_HEADERS, b"{}"))
    with pytest.raises(TradeBlocked, match="HTTP 429"):
        client.search("Allflame", {})


def test_a_challenge_page_on_200_is_blocked() -> None:
    page = b"<!DOCTYPE html><html><head><title>Just a moment...</title></head></html>"
    client, _, _ = make_client(HttpResponse(200, {"content-type": "text/html"}, page))
    with pytest.raises(TradeBlocked, match="challenge"):
        client.data_stats()


@pytest.mark.parametrize("status", [200, 503])
def test_cloudflare_text_without_html_tags_is_blocked(status: int) -> None:
    client, _, _ = make_client(HttpResponse(status, {}, b"Attention Required! | Cloudflare"))
    with pytest.raises(TradeBlocked):
        client.data_stats()


def test_cf_mitigated_header_is_a_challenge() -> None:
    client, _, _ = make_client(HttpResponse(200, {**JSON_HEADERS, "cf-mitigated": "challenge"}, b"{}"))
    with pytest.raises(TradeBlocked, match="challenge"):
        client.data_stats()


def test_a_site_error_message_is_reported() -> None:
    body = json.dumps({"error": {"code": 2, "message": "Query is too complex."}}).encode()
    client, _, _ = make_client(HttpResponse(400, JSON_HEADERS, body))
    with pytest.raises(TradeError, match="Query is too complex.") as caught:
        client.search("Allflame", {})
    assert not isinstance(caught.value, TradeBlocked)
    assert "400" in str(caught.value)


def test_other_4xx_without_a_message_is_an_error() -> None:
    client, _, _ = make_client(HttpResponse(404, JSON_HEADERS, b"{}"))
    with pytest.raises(TradeError, match="404") as caught:
        client.fetch(["id1"], "Q")
    assert not isinstance(caught.value, TradeBlocked)


def test_500_is_an_error() -> None:
    client, _, _ = make_client(HttpResponse(500, JSON_HEADERS, b'{"oops": true}'))
    with pytest.raises(TradeError, match="500") as caught:
        client.data_stats()
    assert not isinstance(caught.value, TradeBlocked)


def test_a_redirect_is_an_error_not_followed() -> None:
    client, _, _ = make_client(HttpResponse(302, {"location": "https://elsewhere.example/"}, b""))
    with pytest.raises(TradeError, match="302"):
        client.data_stats()


@pytest.mark.parametrize("body", [b"not json at all", b"[1, 2]", b'"text"', b""])
def test_a_2xx_that_is_not_a_json_object_is_an_error(body: bytes) -> None:
    client, _, _ = make_client(HttpResponse(200, JSON_HEADERS, body))
    with pytest.raises(TradeError) as caught:
        client.data_stats()
    assert not isinstance(caught.value, TradeBlocked)


# --- the session cookie never leaks --------------------------------------------------------


def test_the_cookie_header_is_sent_only_when_given() -> None:
    client, transport, _ = make_client(ok(), ok(), ok(), cookie=SECRET)
    client.data_stats()
    client.search("Allflame", {})
    client.fetch(["id1"], "Q")
    assert all(request.headers["Cookie"] == f"POESESSID={SECRET}" for request in transport.requests)

    client, transport, _ = make_client(ok(), ok(), ok())
    client.data_stats()
    client.search("Allflame", {})
    client.fetch(["id1"], "Q")
    assert all("Cookie" not in request.headers for request in transport.requests)


def test_the_cookie_is_in_no_text() -> None:
    responses = [
        HttpResponse(403, JSON_HEADERS, b"{}"),
        HttpResponse(429, {"retry-after": "5"}, b"{}"),
        HttpResponse(200, {}, b"<html>Just a moment</html>"),
        HttpResponse(400, JSON_HEADERS, b'{"error": {"code": 2, "message": "Bad."}}'),
        HttpResponse(500, JSON_HEADERS, b"{}"),
        HttpResponse(200, JSON_HEADERS, b"nope"),
    ]
    client, transport, _ = make_client(*responses, cookie=SECRET)
    for _ in responses:
        with pytest.raises(TradeError) as caught:
            client.data_stats()
        assert SECRET not in str(caught.value)
        assert SECRET not in repr(caught.value)
    assert len(transport.requests) == len(responses)
    request = transport.requests[0]
    assert request.headers["Cookie"] == f"POESESSID={SECRET}"  # it was sent, yet:
    assert SECRET not in repr(request)
    assert SECRET not in str(request)
    assert SECRET not in repr(client)
    assert SECRET not in str(client)
    assert "Cookie" not in repr(request)


def test_a_request_repr_hides_headers_and_body() -> None:
    request = HttpRequest("POST", "https://example.test/x", {"Cookie": f"POESESSID={SECRET}"}, b"payload-body")
    assert "payload-body" not in repr(request)
    assert SECRET not in repr(request)
    assert "POST" in repr(request) and "https://example.test/x" in repr(request)


# --- the real transport, against a local server --------------------------------------------


class _Handler(http.server.BaseHTTPRequestHandler):
    def _answer(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        received = self.rfile.read(length) if length else b""
        if self.path == "/limited":
            self.send_response(429)
            self.send_header("Retry-After", "30")
            payload = b'{"error": {"code": 3, "message": "Rate limit exceeded"}}'
        elif self.path == "/moved":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:9/never")
            payload = b""
        elif self.path == "/cut":
            self.send_response(200)
            payload = b"short"  # the length header below promises 100 bytes
        else:
            self.send_response(200)
            self.send_header("X-Rate-Limit-Policy", "trade-search-request-limit")
            self.send_header("Content-Type", "application/json")
            payload = json.dumps(
                {"method": self.command, "seen": received.decode(), "agent": self.headers["User-Agent"]}
            ).encode()
        self.send_header("Content-Length", str(len(payload)) if self.path != "/cut" else "100")
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()
        if self.path == "/cut":
            self.close_connection = True

    do_GET = do_POST = _answer

    def log_message(self, *args) -> None:
        pass


@pytest.fixture
def local_url():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_urllib_transport_returns_status_lowercased_headers_and_body(local_url: str) -> None:
    transport = urllib_transport(timeout=5)
    response = transport(HttpRequest("POST", f"{local_url}/ok", {"User-Agent": "probe/1"}, b'{"a": 1}'))
    assert response.status == 200
    assert response.headers["x-rate-limit-policy"] == "trade-search-request-limit"
    assert response.headers["content-type"] == "application/json"
    assert json.loads(response.body) == {"method": "POST", "seen": '{"a": 1}', "agent": "probe/1"}


def test_urllib_transport_gives_back_an_error_status_as_a_response(local_url: str) -> None:
    response = urllib_transport(timeout=5)(HttpRequest("GET", f"{local_url}/limited", {}))
    assert response.status == 429
    assert response.headers["retry-after"] == "30"
    assert b"Rate limit exceeded" in response.body


def test_urllib_transport_does_not_follow_redirects(local_url: str) -> None:
    response = urllib_transport(timeout=5)(HttpRequest("GET", f"{local_url}/moved", {"Cookie": f"POESESSID={SECRET}"}))
    assert response.status == 302
    assert response.headers["location"] == "http://127.0.0.1:9/never"


def test_urllib_transport_failures_are_trade_errors_without_headers(local_url: str) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    request = HttpRequest("GET", f"http://127.0.0.1:{closed_port}/x", {"Cookie": f"POESESSID={SECRET}"})
    with pytest.raises(TradeError) as caught:
        urllib_transport(timeout=5)(request)
    assert SECRET not in str(caught.value)

    cut = HttpRequest("GET", f"{local_url}/cut", {"Cookie": f"POESESSID={SECRET}"})
    with pytest.raises(TradeError) as caught:
        urllib_transport(timeout=5)(cut)
    assert SECRET not in str(caught.value)


# --- a cookie value that cannot be sent never reaches the wire or an error text -------------

BAD_COOKIES = [
    f"{SECRET}\n",
    f"{SECRET} ",
    f"{SECRET}\r\nX-Evil: 1",
    f"{SECRET}\x00",
    f"{SECRET}\u0436",
    "\u0436",
]


@pytest.mark.parametrize("cookie", BAD_COOKIES)
def test_a_cookie_with_whitespace_control_or_non_ascii_is_refused_before_anything_is_spent(cookie: str) -> None:
    client, transport, _ = make_client(ok(), cookie=cookie)
    with pytest.raises(TradeError, match="POESESSID in the environment is not a valid cookie value") as caught:
        client.data_stats()
    assert "fix the variable" in str(caught.value)
    assert SECRET not in str(caught.value) and SECRET not in repr(caught.value)
    assert transport.requests == []
    assert client.budget.used == 0


@pytest.mark.parametrize("cookie", [SECRET, "a~b!c", "0123456789abcdef"])
def test_a_printable_ascii_cookie_is_accepted(cookie: str) -> None:
    client, transport, _ = make_client(ok(), cookie=cookie)
    client.data_stats()
    assert transport.requests[0].headers["Cookie"] == f"POESESSID={cookie}"


# what http.client itself refuses (a space or NUL passes it; only the client's own check stops those)
HTTP_CLIENT_REFUSES = [BAD_COOKIES[0], BAD_COOKIES[2], BAD_COOKIES[4], BAD_COOKIES[5]]


@pytest.mark.parametrize("cookie", HTTP_CLIENT_REFUSES)
def test_the_real_transport_never_shows_a_header_value_that_http_client_rejects(
    local_url: str, cookie: str
) -> None:
    request = HttpRequest("GET", f"{local_url}/x", {"Cookie": f"POESESSID={cookie}"})
    with pytest.raises(TradeError) as caught:
        urllib_transport(timeout=5)(request)
    assert str(caught.value) == "the request could not be built"
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    assert SECRET not in str(caught.value) and SECRET not in repr(caught.value)


# --- the network guard of the trade tests ---------------------------------------------------


def test_the_guard_stops_a_real_call_to_the_trade_site_before_any_connection() -> None:
    request = HttpRequest("GET", "https://www.pathofexile.com/api/trade/data/stats", {})
    with pytest.raises(AssertionError, match="the test used the network: 'www.pathofexile.com'"):
        urllib_transport(timeout=5)(request)
