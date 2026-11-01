"""The self-regulating rate limiter of the trade client (#358).

The owner's rule: the system learns GGG's limits from the `X-Rate-Limit-*` headers and regulates itself so
it never reaches them; it never probes a limit by hitting it. Everything here runs on a fake clock, a fake
sleep and fake transports: the replay uses a sliding-window server built from the limits of the RECORDED
headers (`tests/fixtures/trade/recorded/headers_{search,fetch}.json`). No clock module, no network.
"""

import json
import logging
from bisect import bisect_right
from collections.abc import Mapping
from math import ceil

import pytest
from trade_support import SECRET, recorded

from crafting_system.prices import TradeRateLimited as ExportedTradeRateLimited
from crafting_system.prices import TradeWaitTooLong as ExportedTradeWaitTooLong
from crafting_system.prices.trade_http import (
    HttpRequest,
    HttpResponse,
    RateLimiter,
    RateRule,
    RequestBudget,
    TradeBlocked,
    TradeClient,
    TradeError,
    TradeRateLimited,
    TradeWaitTooLong,
    parse_rate_limits,
    parse_retry_after,
    user_agent,
)

LOGGER = "crafting_system.prices.trade_http"
SEARCH = recorded("headers_search.json")["headers"]  # trade-search-request-limit, 5:10:60,15:60:300,...
FETCH = recorded("headers_fetch.json")["headers"]  # trade-fetch-request-limit, 12:4:10,16:12:300,...
SEARCH_LIMITS = "5:10:60,15:60:300,30:300:1800,600:21600:3600"
JSON_HEADERS = {"content-type": "application/json"}


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


def headers_of(
    base: Mapping[str, str], limit: str | None = None, state: str | None = None
) -> dict[str, str]:
    """A recorded header set with its limits and/or its state replaced."""
    changed = dict(base)
    if limit is not None:
        changed["x-rate-limit-ip"] = limit
    if state is not None:
        changed["x-rate-limit-ip-state"] = state
    return changed


def rules_of(base: Mapping[str, str]) -> tuple[str, list[RateRule]]:
    report = parse_rate_limits(base)
    assert report is not None and len(report.rules) == 1
    return report.policy, [rule for rule, _ in report.rules[0][1]]


# --- a sliding-window server built from the recorded limits ---------------------------------


class SlidingWindowServer:
    """A fake `Transport` that behaves like the site's limiter, with the limits of the recorded headers.

    Per rule it keeps the timestamps of the hits it served, counts the ones newer than `now - period`
    (plus the request itself) and answers with the same `x-rate-limit-*` headers the site sends. If a
    window would go above its limit it answers 429 with `Retry-After` and records a violation. It records,
    per (policy, period), the highest count ever served (`peak`), the count of the first request of the
    policy (`first`) and the highest count after it (`peak_after_first`). `others(kind, ages)` pre-loads
    hits of "other clients", `ages` seconds ago, which the limiter can only learn of from the first answer.
    """

    def __init__(self, clock: FakeClock, latency: float = 0.0) -> None:
        self.clock = clock
        self.latency = latency  # seconds between the server's receipt and the client's response time
        self.policies = {"search": rules_of(SEARCH), "fetch": rules_of(FETCH)}
        self.hits: dict[tuple[str, int], list[float]] = {
            (policy, rule.period): [] for policy, rules in self.policies.values() for rule in rules
        }
        self.peak: dict[tuple[str, int], int] = {}
        self.first: dict[tuple[str, int], int] = {}
        self.peak_after_first: dict[tuple[str, int], int] = {}
        self.violations: list[tuple[str, int, int]] = []  # (policy, period, count)
        self.served: dict[str, int] = {"search": 0, "fetch": 0}
        self.refused = 0

    def others(self, kind: str, ages: list[float]) -> None:
        policy, rules = self.policies[kind]
        for rule in rules:
            self.hits[(policy, rule.period)] += sorted(self.clock() - age for age in ages)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        kind = "search" if "/search/" in request.url else "fetch"
        policy, rules = self.policies[kind]
        now = self.clock()
        counts = []
        for rule in rules:
            hits = self.hits[(policy, rule.period)]
            counts.append(len(hits) - bisect_right(hits, now - rule.period) + 1)
        over = [(rule, count) for rule, count in zip(rules, counts) if count > rule.hits]
        headers = {**JSON_HEADERS, "x-rate-limit-policy": policy, "x-rate-limit-rules": "Ip"}
        headers["x-rate-limit-ip"] = ",".join(f"{r.hits}:{r.period}:{r.restricted}" for r in rules)
        if over:
            self.refused += 1
            self.violations += [(policy, rule.period, count) for rule, count in over]
            headers["x-rate-limit-ip-state"] = ",".join(
                f"{c}:{r.period}:{r.restricted if c > r.hits else 0}" for r, c in zip(rules, counts)
            )
            headers["retry-after"] = str(max(rule.restricted for rule, _ in over))
            response = HttpResponse(429, headers, b'{"error": {"code": 3, "message": "Rate limit exceeded"}}')
        else:
            first = self.served[kind] == 0
            self.served[kind] += 1
            for rule, count in zip(rules, counts):
                key = (policy, rule.period)
                self.hits[key].append(now)
                self.peak[key] = max(self.peak.get(key, 0), count)
                if first:
                    self.first[key] = count
                else:
                    self.peak_after_first[key] = max(self.peak_after_first.get(key, 0), count)
            headers["x-rate-limit-ip-state"] = ",".join(f"{c}:{r.period}:0" for r, c in zip(rules, counts))
            response = HttpResponse(200, headers, b'{"result": [], "id": "Q"}')
        self.clock.now += self.latency
        return response


def allowed(hits: int, margin: int, percent: int) -> int:
    """The test's own, integer-only reading of 'limit minus margin' (the limiter uses a float fraction)."""
    return max(1, hits - max(margin, -(-hits * percent // 100)))


def drive(
    pairs: int,
    *,
    fetches: int = 1,
    others: bool = False,
    latency: float = 0.0,
    max_wait: float = 7200.0,
    **options,
) -> tuple[SlidingWindowServer, FakeClock, RateLimiter]:
    clock = FakeClock()
    server = SlidingWindowServer(clock, latency)
    if others:
        server.others("search", [1.0, 2.0])
        server.others("fetch", [1.0, 2.0])
    limiter = RateLimiter(clock, clock.sleep, max_wait=max_wait, **options)
    client = TradeClient(server, user_agent("t"), limiter, RequestBudget(100_000))
    for _ in range(pairs):
        client.search("Allflame", {})
        for _ in range(fetches):
            client.fetch(["id1"], "Q")
    return server, clock, limiter


def forced_time(server: SlidingWindowServer, margin: int, percent: int) -> tuple[float, float]:
    """(lower, upper) bound on the elapsed fake time, derived from the windows alone.

    Lower: in a window that allows `A` hits per `period`, request `k + A` comes at least `period`
    after request `k`, so `n` requests need at least `(n - 1) // A` periods. Upper: a window fires a
    wait of one `period` only after `A` new hits (it is empty after the wait), so it fires at most
    `(n + 2) // A` times (2 = the pre-loaded hits of other clients); a sleep is at most the longest
    period that fires, so the sum over all windows bounds the total sleep. Latency is added on top.
    """
    lower = upper = 0.0
    for kind, (policy, rules) in server.policies.items():
        n = server.served[kind]
        for rule in rules:
            a = allowed(rule.hits, margin, percent)
            lower = max(lower, ((n - 1) // a) * rule.period)
            upper += ((n + 2) // a) * rule.period
    return lower, upper + (server.served["search"] + server.served["fetch"]) * server.latency


CONFIGS = [
    pytest.param({}, 1, 0, id="default-margin"),
    pytest.param({"margin": 3, "margin_fraction": 0.2}, 3, 20, id="margin3-fraction20"),
]


@pytest.mark.parametrize("latency", [0.0, 0.5])
@pytest.mark.parametrize("others", [False, True], ids=["alone", "other-clients"])
@pytest.mark.parametrize("fetches", [1, 3])
@pytest.mark.parametrize(("options", "margin", "percent"), CONFIGS)
def test_replay_never_puts_a_window_above_limit_minus_margin(
    options: dict, margin: int, percent: int, fetches: int, others: bool, latency: float
) -> None:
    pairs = 60
    server, clock, limiter = drive(pairs, fetches=fetches, others=others, latency=latency, **options)

    # the site never saw a hit above any limit, and never had to say 429
    assert server.violations == []
    assert server.refused == 0
    assert server.served == {"search": pairs, "fetch": pairs * fetches}

    # EVERY window of BOTH recorded policies (5:10, 15:60, 30:300, 600:21600 / 12:4, 16:12, 50:300, 1000:21600)
    seen = 0
    for policy, rules in server.policies.values():
        for rule in rules:
            key = (policy, rule.period)
            limit = allowed(rule.hits, margin, percent)
            assert limiter.allowed_hits(rule) == limit
            # after the first answer taught the limiter the limits, no request went above limit - margin
            assert server.peak_after_first[key] <= limit, key
            seen += 1
    assert seen == 8

    if others:
        # the two hits of other clients could only be learned from the first answer: it counted them
        assert server.first[("trade-search-request-limit", 10)] == 3
        assert server.first[("trade-fetch-request-limit", 4)] == 3
    elif latency == 0.0:  # (with latency the requests spread out and the 4 s window is not always filled)
        # the windows that pace the run were really used up to the allowed count: with one fetch per search
        # the search windows; with three, the fetch windows (the searches then pace nothing but themselves)
        kind, periods = ("search", (10, 60, 300)) if fetches == 1 else ("fetch", (4, 12, 300))
        policy, rules = server.policies[kind]
        for rule in rules:
            if rule.period in periods:
                assert server.peak[policy, rule.period] == allowed(rule.hits, margin, percent), (kind, rule)

    lower, upper = forced_time(server, margin, percent)
    assert lower >= 600  # sanity: 60 searches do not fit in two 30:300 windows
    assert clock.now - 1000.0 >= lower  # not faster than the windows force ...
    assert clock.now - 1000.0 <= upper  # ... and not stalled


def test_replay_reaches_the_21600_second_window_too() -> None:
    """620 searches pass the 600:21600 window (allowed 599) and never put it above 599."""
    server, clock, limiter = drive(620, max_wait=30_000.0)
    assert server.violations == [] and server.refused == 0
    key = ("trade-search-request-limit", 21600)
    assert server.peak[key] == 599  # reached, never 600
    assert server.peak_after_first[key] <= limiter.allowed_hits(RateRule(600, 21600, 3600)) == 599
    for policy, rules in server.policies.values():
        for rule in rules:
            assert server.peak_after_first[(policy, rule.period)] <= allowed(rule.hits, 1, 0)
    lower, upper = forced_time(server, 1, 0)
    assert lower >= 21600  # request 600 comes a whole 21600 s after request 1
    assert lower <= clock.now - 1000.0 <= upper


def test_the_first_request_of_a_policy_is_never_waited_for() -> None:
    clock = FakeClock()
    server = SlidingWindowServer(clock)
    limiter = RateLimiter(clock, clock.sleep, max_wait=7200.0)
    client = TradeClient(server, user_agent("t"), limiter, RequestBudget(10))
    client.search("Allflame", {})
    client.fetch(["id1"], "Q")
    assert clock.sleeps == []  # nothing was known before the first answer of each policy


# --- allowed hits per window --------------------------------------------------------------------


def test_allowed_hits_is_limit_minus_the_larger_margin_and_at_least_one() -> None:
    clock = FakeClock()
    plain = RateLimiter(clock, clock.sleep)
    assert [plain.allowed_hits(RateRule(h, 10, 60)) for h in (1, 2, 5, 15, 30, 600)] == [1, 1, 4, 14, 29, 599]
    wide = RateLimiter(clock, clock.sleep, margin=3, margin_fraction=0.2)
    assert [wide.allowed_hits(RateRule(h, 10, 60)) for h in (5, 15, 30, 600)] == [2, 12, 24, 480]
    assert [wide.allowed_hits(RateRule(h, 4, 10)) for h in (12, 16, 50, 1000)] == [9, 12, 40, 800]
    assert wide.allowed_hits(RateRule(1, 10, 60)) == 1  # never below 1, whatever the margin
    assert wide.allowed_hits(RateRule(3, 10, 60)) == 1
    assert RateLimiter(clock, clock.sleep, margin=50).allowed_hits(RateRule(2, 10, 60)) == 1


def test_a_limit_of_one_hit_still_lets_the_first_hit_through() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock, clock.sleep, margin=3)
    limiter.after("search", headers_of(SEARCH, "1:10:60,15:60:300", "0:10:0,0:60:0"), 200)
    limiter.before("search")
    assert clock.sleeps == []  # allowed is 1, not 0: a window with no hits is not waited for
    limiter.after("search", headers_of(SEARCH, "1:10:60,15:60:300", "1:10:0,1:60:0"), 200)
    limiter.before("search")
    assert clock.sleeps == [10]  # one hit used = the allowed one


# --- a 429: the wait and the back-off -----------------------------------------------------------

BASE = "https://www.pathofexile.com/api/trade"


def ok(headers: Mapping[str, str] | None = None) -> HttpResponse:
    return HttpResponse(200, {**JSON_HEADERS, **(headers or {})}, b'{"result": []}')


def limited(retry_after: str | None = "30", headers: Mapping[str, str] | None = None) -> HttpResponse:
    extra = {} if retry_after is None else {"retry-after": retry_after}
    body = b'{"error": {"code": 3, "message": "Rate limit exceeded"}}'
    return HttpResponse(429, {**JSON_HEADERS, **(headers or {}), **extra}, body)


class FakeTransport:
    """Hands out canned responses in order and records every request it was given."""

    def __init__(self, *responses: HttpResponse) -> None:
        self.responses = list(responses)
        self.requests: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def make_client(
    *responses: HttpResponse, cookie: str | None = None, **options
) -> tuple[TradeClient, FakeTransport, FakeClock]:
    clock = FakeClock()
    transport = FakeTransport(*responses)
    client = TradeClient(
        transport, user_agent("9.9.9"), RateLimiter(clock, clock.sleep, **options), RequestBudget(50), cookie
    )
    return client, transport, clock


def refusal(client: TradeClient) -> TradeRateLimited:
    with pytest.raises(TradeRateLimited) as caught:
        client.search("Allflame", {})
    return caught.value


def test_the_new_exceptions_are_trade_blocked_and_exported() -> None:
    assert issubclass(TradeRateLimited, TradeBlocked) and issubclass(TradeWaitTooLong, TradeBlocked)
    assert ExportedTradeRateLimited is TradeRateLimited and ExportedTradeWaitTooLong is TradeWaitTooLong


@pytest.mark.parametrize("policy_header", [False, True], ids=["no-policy-header", "with-policy-header"])
def test_429_with_retry_after_raises_and_the_next_call_waits_it_out(policy_header: bool) -> None:
    extra = headers_of(SEARCH) if policy_header else {}
    client, transport, clock = make_client(limited("30", extra), ok(extra))
    error = refusal(client)
    assert isinstance(error, TradeBlocked)
    assert error.retry_after == 30 and error.backoff == 30
    assert "HTTP 429" in str(error) and "30 s" in str(error) and "the next request waits 30 s" in str(error)
    assert clock.sleeps == [] and len(transport.requests) == 1  # no retry inside the client
    assert client.search("Allflame", {}) == {"result": []}
    assert clock.sleeps == [30]
    assert len(transport.requests) == 2


def test_the_wait_runs_from_the_429_so_time_already_passed_counts() -> None:
    client, _, clock = make_client(limited("30"), ok())
    refusal(client)
    clock.now += 12
    client.search("Allflame", {})
    assert clock.sleeps == [18]


def test_429s_in_a_row_double_and_a_2xx_starts_again() -> None:
    client, transport, clock = make_client(limited("30"), limited("30"), limited("30"), ok(), limited("30"), ok())
    assert refusal(client).backoff == 30
    assert refusal(client).backoff == 60  # 30 * 2
    assert refusal(client).backoff == 120  # 30 * 4
    assert clock.sleeps == [30, 60]  # each call waited the previous back-off before sending
    client.search("Allflame", {})  # waits 120, then succeeds
    assert clock.sleeps == [30, 60, 120]
    assert refusal(client).backoff == 30  # the 2xx reset the count: n = 1 again
    client.search("Allflame", {})
    assert clock.sleeps == [30, 60, 120, 30]
    assert len(transport.requests) == 6


def test_429_without_retry_after_uses_backoff_base_then_doubles() -> None:
    client, _, clock = make_client(limited(None), limited(None), limited(None), ok(), backoff_base=10.0)
    errors = [refusal(client), refusal(client), refusal(client)]
    assert [e.retry_after for e in errors] == [None, None, None]
    assert [e.backoff for e in errors] == [10, 20, 40]
    assert "retry after" not in str(errors[0])
    client.search("Allflame", {})
    assert clock.sleeps == [10, 20, 40]


def test_the_default_backoff_is_sixty_seconds_and_one_hour_at_most() -> None:
    client, _, _ = make_client(*[limited(None)] * 8, max_wait=10_000.0)
    backoffs = [refusal(client).backoff for _ in range(8)]
    assert backoffs == [60, 120, 240, 480, 960, 1920, 3600, 3600]


def test_the_cap_is_respected_but_never_below_retry_after() -> None:
    client, _, clock = make_client(
        limited("30"), limited("30"), limited("30"), limited("30"), ok(), backoff_cap=100.0
    )
    assert [refusal(client).backoff for _ in range(4)] == [30, 60, 100, 100]
    assert clock.sleeps == [30, 60, 100]
    client.search("Allflame", {})
    assert clock.sleeps == [30, 60, 100, 100]

    client, _, clock = make_client(limited("500"), limited("500"), backoff_cap=100.0, max_wait=1000.0)
    assert refusal(client).backoff == 500  # the site's own word is never shortened
    assert refusal(client).backoff == 500
    assert clock.sleeps == [500]


def test_retry_after_as_an_http_date_is_taken_against_the_date_header() -> None:
    date = "Fri, 30 Oct 2026 21:21:02 GMT"
    retry = "Fri, 30 Oct 2026 21:21:47 GMT"
    client, _, clock = make_client(limited(retry, {"date": date}), ok())
    error = refusal(client)
    assert error.retry_after == 45 and error.backoff == 45
    client.search("Allflame", {})
    assert clock.sleeps == [45]


def test_a_garbage_retry_after_is_treated_as_missing() -> None:
    client, _, clock = make_client(limited("soon-ish"), ok(), backoff_base=15.0)
    error = refusal(client)
    assert error.retry_after is None and error.backoff == 15
    client.search("Allflame", {})
    assert clock.sleeps == [15]


def test_a_backoff_over_max_wait_stops_the_next_call_before_it_sleeps_or_sends() -> None:
    client, transport, clock = make_client(limited("500"), ok(), max_wait=120.0)
    assert refusal(client).backoff == 500
    with pytest.raises(TradeWaitTooLong) as caught:
        client.search("Allflame", {})
    assert caught.value.wait == 500
    assert isinstance(caught.value, TradeBlocked)
    assert "500 s" in str(caught.value) and "120 s" in str(caught.value)
    assert clock.sleeps == []
    assert len(transport.requests) == 1  # the second request was not sent


def test_a_backoff_is_shared_by_the_kinds_of_one_policy_and_not_by_another() -> None:
    clock = FakeClock()
    other = headers_of(FETCH)
    transport = FakeTransport(ok(headers_of(SEARCH)), ok(other), limited("30", headers_of(SEARCH)), ok(), ok())
    limiter = RateLimiter(clock, clock.sleep)
    client = TradeClient(transport, user_agent("t"), limiter, RequestBudget(20))
    client.search("Allflame", {})
    client.fetch(["id1"], "Q")
    refusal(client)
    client.fetch(["id1"], "Q")  # another policy: not held back by the search back-off
    assert clock.sleeps == []
    client.search("Allflame", {})
    assert clock.sleeps == [30]


def test_a_backoff_set_before_the_policy_was_known_moves_to_the_policy() -> None:
    client, _, clock = make_client(limited("30"), ok(headers_of(SEARCH)), ok())
    refusal(client)  # a 429 with no policy header: kept under the kind
    client.search("Allflame", {})  # waits 30, learns the policy
    assert clock.sleeps == [30]
    client.search("Allflame", {})
    assert clock.sleeps == [30]  # the old back-off is over, and is not applied twice


def test_a_malformed_rate_header_on_a_429_still_leaves_the_backoff_in_place() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock, clock.sleep)
    broken = {"x-rate-limit-policy": "p", "retry-after": "30"}  # the rules header is missing
    with pytest.raises(TradeError, match="x-rate-limit-rules"):
        limiter.after("search", broken, 429)
    limiter.before("search")
    assert clock.sleeps == [30]


def test_after_returns_the_backoff_only_for_a_429() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock, clock.sleep)
    assert limiter.after("search", headers_of(SEARCH)) is None
    assert limiter.after("search", headers_of(SEARCH), 200) is None
    assert limiter.after("search", headers_of(SEARCH), 400) is None
    assert limiter.after("search", {"retry-after": "7"}, 429) == 7


def test_restricted_seconds_and_the_backoff_do_not_add_up_the_longer_one_wins() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock, clock.sleep)
    hot = headers_of(SEARCH, state="6:10:45,1:60:0,1:300:0,1:21600:0")
    assert limiter.after("search", {**hot, "retry-after": "30"}, 429) == 30
    limiter.before("search")
    assert clock.sleeps == [45]


# --- Retry-After units --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "seconds"),
    [("30", 30.0), ("0", 0.0), ("1.5", 1.5), (" 7 ", 7.0), ("3600", 3600.0)],
)
def test_parse_retry_after_seconds(value: str, seconds: float) -> None:
    assert parse_retry_after({"retry-after": value}) == seconds


def test_parse_retry_after_http_date() -> None:
    date = {"date": "Fri, 30 Oct 2026 21:21:02 GMT"}
    assert parse_retry_after({**date, "retry-after": "Fri, 30 Oct 2026 21:22:02 GMT"}) == 60
    assert parse_retry_after({**date, "retry-after": "Fri, 30 Oct 2026 21:21:00 GMT"}) == 0  # in the past
    assert parse_retry_after({"retry-after": "Fri, 30 Oct 2026 21:22:02 GMT"}) is None  # no date header
    assert parse_retry_after({"date": "yesterday", "retry-after": "Fri, 30 Oct 2026 21:22:02 GMT"}) is None


@pytest.mark.parametrize("value", ["", "soon", "-5", "1e3", "inf", "nan", "30s", "3,0", "Fri, 99 Zzz 2026"])
def test_parse_retry_after_garbage_is_none(value: str) -> None:
    assert parse_retry_after({"date": "Fri, 30 Oct 2026 21:21:02 GMT", "retry-after": value}) is None


def test_parse_retry_after_missing_is_none() -> None:
    assert parse_retry_after({}) is None


# --- TradeWaitTooLong ---------------------------------------------------------------------------


def test_trade_wait_too_long_carries_the_wait_and_keeps_the_old_message() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock, clock.sleep, max_wait=120.0)
    limiter.after("search", headers_of(SEARCH, state="1:10:1800,1:60:0,1:300:0,1:21600:0"), 200)
    with pytest.raises(TradeWaitTooLong, match=r"1800 s .* 120 s .* stopping") as caught:
        limiter.before("search")
    assert caught.value.wait == 1800
    assert clock.sleeps == []
    assert str(TradeWaitTooLong(5.0)) == "the site asks for 5 s of waiting, which is too long; stopping"


# --- one policy, several kinds ------------------------------------------------------------------


def test_kinds_that_share_a_policy_share_the_windows() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock, clock.sleep)
    full = "4:10:0,1:60:0,1:300:0,1:21600:0"  # 4 of 5: the allowed 4 are used
    limiter.after("search", headers_of(SEARCH, state="1:10:0,1:60:0,1:300:0,1:21600:0"), 200)
    limiter.after("search-more", headers_of(SEARCH, state=full), 200)  # same policy name, another kind
    limiter.before("search")  # sees the state reported through the other kind
    assert clock.sleeps == [10]
    limiter.before("search-more")
    assert clock.sleeps == [10]  # that wait has passed for both

    limiter.after("fetch", headers_of(FETCH), 200)  # another policy has its own windows
    limiter.before("fetch")
    assert clock.sleeps == [10]


def test_a_kind_never_seen_has_no_wait() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock, clock.sleep)
    limiter.after("search", headers_of(SEARCH, state="5:10:60,1:60:0,1:300:0,1:21600:0"), 200)
    limiter.before("brand-new-kind")
    assert clock.sleeps == []


# --- changed headers: the new limits decide, and are logged ---------------------------------------


def our_records(caplog: pytest.LogCaptureFixture, level: int = logging.INFO) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOGGER and r.levelno >= level]


def test_changed_limits_decide_the_next_wait_and_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    clock = FakeClock()
    limiter = RateLimiter(clock, clock.sleep)
    state = "1:10:0,1:60:0,1:300:0,1:21600:0"

    # first sight: INFO with the policy, the date and the limits
    limiter.after("search", headers_of(SEARCH, state=state), 200)
    (first,) = our_records(caplog)
    assert first.levelno == logging.INFO
    assert first.getMessage() == (
        "rate limits first seen: kind=search policy=trade-search-request-limit "
        f"date=2026-10-30T21:21:02Z Ip={SEARCH_LIMITS}"
    )
    limiter.before("search")
    assert clock.sleeps == []  # 1 hit of 5: the recorded limits allow it

    # the same state under changed limits (search is now 2 per 10 s): a WARNING with old and new
    caplog.clear()
    changed = "2:10:60,15:60:300,30:300:1800,600:21600:3600"
    limiter.after("search", headers_of(SEARCH, changed, state), 200)
    (warning,) = our_records(caplog)
    assert warning.levelno == logging.WARNING
    text = warning.getMessage()
    assert text.startswith("rate limits changed: kind=search policy=trade-search-request-limit ")
    assert f"Ip={changed}" in text and f"(was Ip={SEARCH_LIMITS})" in text
    limiter.before("search")
    assert clock.sleeps == [10]  # the NEW limit decides: allowed max(1, 2 - 1) = 1, and 1 hit is used

    first_seen, second = limiter.observations
    assert (first_seen.changed, second.changed) == (False, True)
    assert first_seen.kind == second.kind == "search"
    assert first_seen.policy == second.policy == "trade-search-request-limit"
    assert first_seen.date == second.date == "2026-10-30T21:21:02Z"
    assert first_seen.rules == (("Ip", tuple(RateRule(*map(int, t.split(":"))) for t in SEARCH_LIMITS.split(","))),)
    assert second.rules[0][1][0] == RateRule(2, 10, 60)


def test_an_unchanged_response_logs_nothing_at_info_or_above(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    limiter = RateLimiter(FakeClock(), lambda seconds: None)
    limiter.after("search", headers_of(SEARCH), 200)
    caplog.clear()
    for state in ("2:10:0,2:60:0,2:300:0,2:21600:0", "3:10:0,3:60:0,3:300:0,3:21600:0"):
        limiter.after("search", headers_of(SEARCH, state=state), 200)  # only the state differs
    assert our_records(caplog) == []
    assert len(limiter.observations) == 1
    debug = [r.getMessage() for r in our_records(caplog, logging.DEBUG)]
    assert len(debug) == 2 and all(line.startswith("rate use: kind=search policy=") for line in debug)
    assert "Ip=3/5 per 10 s,3/15 per 60 s,3/30 per 300 s,3/600 per 21600 s" in debug[1]


def test_a_second_kind_on_a_known_policy_with_the_same_limits_is_not_news(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    limiter = RateLimiter(FakeClock(), lambda seconds: None)
    limiter.after("search", headers_of(SEARCH), 200)
    caplog.clear()
    limiter.after("other-kind", headers_of(SEARCH), 200)
    assert our_records(caplog) == []
    limiter.after("fetch", headers_of(FETCH), 200)  # a policy not seen before is
    (line,) = our_records(caplog)
    assert "first seen: kind=fetch policy=trade-fetch-request-limit" in line.getMessage()


def test_a_missing_date_header_is_logged_as_unknown(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    undated = {k: v for k, v in SEARCH.items() if k != "date"}
    limiter = RateLimiter(FakeClock(), lambda seconds: None)
    limiter.after("search", undated, 200)
    assert " date=unknown " in our_records(caplog)[0].getMessage()
    assert limiter.observations[0].date is None


def test_a_window_seen_over_its_limit_or_restricted_is_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    limiter = RateLimiter(FakeClock(), lambda seconds: None)
    limiter.after("search", headers_of(SEARCH), 200)
    caplog.clear()
    limiter.after("search", headers_of(SEARCH, state="5:10:0,1:60:0,1:300:0,1:21600:0"), 200)
    assert our_records(caplog) == []  # exactly at the limit is not over it
    limiter.after("search", headers_of(SEARCH, state="6:10:0,1:60:0,1:300:0,1:21600:0"), 200)
    (over,) = our_records(caplog)
    assert over.levelno == logging.WARNING
    assert "a rate limit was hit" in over.getMessage() and "10 s: 6 of 5" in over.getMessage()
    caplog.clear()
    limiter.after("search", headers_of(SEARCH, state="1:10:0,1:60:0,1:300:0,1:21600:1800"), 200)
    (restricted,) = our_records(caplog)
    assert restricted.levelno == logging.WARNING and "restricted for 1800 s" in restricted.getMessage()


def test_a_429_is_logged_with_its_backoff(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    limiter = RateLimiter(FakeClock(), lambda seconds: None)
    limiter.after("search", {"retry-after": "30"}, 429)
    (line,) = our_records(caplog)
    assert line.levelno == logging.WARNING
    assert "HTTP 429" in line.getMessage() and "the next request waits 30 s" in line.getMessage()


# --- the cookie, and every header that is not a rate limit, stay out of the log ---------------------


def test_no_log_line_has_the_cookie_or_a_foreign_header(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    foreign = {"set-cookie": f"POESESSID={SECRET}; path=/", "x-secret-note": "FOREIGN-HEADER-VALUE", "server": "cloudflare"}
    state = "1:10:0,1:60:0,1:300:0,1:21600:0"
    over = "6:10:30,1:60:0,1:300:0,1:21600:0"
    client, transport, _ = make_client(
        ok({**headers_of(SEARCH, state=state), **foreign}),
        ok({**headers_of(SEARCH, "2:10:60,15:60:300,30:300:1800,600:21600:3600", state), **foreign}),
        limited("30", {**headers_of(SEARCH, state=over), **foreign}),
        ok({**headers_of(FETCH), **foreign}),
        cookie=SECRET,
        max_wait=1000.0,
    )
    client.search("Allflame", {})
    client.search("Allflame", {})
    refusal(client)
    client.fetch(["id1"], "Q")
    assert all(request.headers["Cookie"] == f"POESESSID={SECRET}" for request in transport.requests)

    records = our_records(caplog, logging.DEBUG)
    assert len(records) >= 6  # first seen, changed, use lines, the hit, the 429 : the log is not empty
    everything = caplog.text + "\n".join(r.getMessage() + repr(r.args) + repr(r.msg) for r in records)
    assert SECRET not in everything and "POESESSID" not in everything
    assert "FOREIGN-HEADER-VALUE" not in everything and "cloudflare" not in everything


def test_the_429_message_names_no_cookie() -> None:
    client, _, _ = make_client(limited("30"), cookie=SECRET)
    error = refusal(client)
    assert SECRET not in str(error) and SECRET not in repr(error)
    assert json.dumps(error.args).count(SECRET) == 0
