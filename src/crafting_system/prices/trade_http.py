# Rate-limit header parsing adapted from PoEQuery `x_rate_limiter.py`, MIT, (c) 2021 Nick Ryder,
# licence in `third_party/PoEQuery-LICENSE.txt`.
"""The HTTP side of the trade-API pricing: transport, rate limits, request budget and stop rules.

GGG's trade API is undocumented, and the owner starts every run by hand with a few requests. So:

- the limits are read from the `X-Rate-Limit-*` headers of every response, never hard-coded;
- a 401, 403, 429, a Cloudflare challenge or an HTML page instead of JSON stops the run with
  `TradeBlocked`: no retry, no bypass, nothing is changed;
- a hard `RequestBudget` bounds how many requests one run may send;
- the session cookie is sent only when the caller passes one. It is kept out of every `repr`,
  message and exception raised here; the caller reads it from the environment itself.

The transport, the clock and the sleep are injected; `urllib_transport` is the real transport.
"""

import http.client
import importlib.metadata
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

TRADE_URL = "https://www.pathofexile.com/api/trade"
REPO_URL = "https://github.com/Rasslabsya4el/crafting-system"
TIMEOUT_SECONDS = 30
MAX_FETCH_IDS = 10  # the trade site's limit for one fetch call
SESSION_HINT = (
    "If you want to try with a session, set POESESSID in your environment yourself; "
    "this tool never asks for it"
)


class TradeError(Exception):
    """A trade request failed: network, an HTTP error, an unusable answer or a malformed header."""


class TradeBlocked(TradeError):
    """The site refused: HTTP 401/403/429, a Cloudflare challenge, or HTML instead of JSON.

    Also raised when the site asks for a longer wait than the limiter allows. The run stops.
    """


class BudgetExceeded(TradeError):
    """The run's request budget is used up; the refused request was not sent."""


def package_version() -> str:
    try:
        return importlib.metadata.version("crafting-system")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def user_agent(version: str) -> str:
    """Tool name, version and the repo URL as contact."""
    return f"crafting-system/{version} (+{REPO_URL})"


# --- transport -----------------------------------------------------------------------------


@dataclass(frozen=True)
class HttpRequest:
    """One request. Headers (which may carry the cookie) and body stay out of the repr."""

    method: str
    url: str
    headers: Mapping[str, str] = field(repr=False)
    body: bytes | None = field(default=None, repr=False)


@dataclass(frozen=True)
class HttpResponse:
    """One answer, whatever its status. Header names are lower-cased by whoever builds it."""

    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[HttpRequest], HttpResponse]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects are not followed: they would carry the cookie to whatever host they name."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def urllib_transport(timeout: float = TIMEOUT_SECONDS) -> Transport:
    """The real transport. HTTP error statuses come back as normal responses.

    Network failures, timeouts and cut-off answers raise `TradeError`; the message names the URL
    and the cause, never the request headers.
    """
    opener = urllib.request.build_opener(_NoRedirect)

    def send(request: HttpRequest) -> HttpResponse:
        wire = urllib.request.Request(
            request.url, data=request.body, headers=dict(request.headers), method=request.method
        )
        try:
            try:
                response = opener.open(wire, timeout=timeout)
            except urllib.error.HTTPError as error:  # a status >= 300 is still an answer
                response = error
            with response:
                headers = {name.lower(): value for name, value in response.headers.items()}
                return HttpResponse(response.status, headers, response.read())
        except (OSError, http.client.HTTPException) as error:  # URLError, timeouts, cut-off answers
            raise TradeError(f"cannot reach {request.url}: {error}") from error
        except (ValueError, UnicodeError):
            # http.client names the offending header value in its text, so the text is dropped
            raise TradeError("the request could not be built") from None

    return send


# --- budget --------------------------------------------------------------------------------


class RequestBudget:
    """At most `max_requests` requests per run; `spend` is called before each one is sent."""

    def __init__(self, max_requests: int) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        self.max_requests = max_requests
        self._used = 0

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return self.max_requests - self._used

    def spend(self, what: str) -> None:
        if self._used >= self.max_requests:
            raise BudgetExceeded(
                f"request budget used up: refused '{what}'; "
                f"{self._used} of {self.max_requests} requests already used"
            )
        self._used += 1


# --- rate limits ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RateRule:
    """A limit: at most `hits` requests per `period` seconds; breaking it restricts for `restricted` s."""

    hits: int
    period: int
    restricted: int


@dataclass(frozen=True)
class RuleState:
    """The same triple as seen now: `hits` counted in the `period`, `restricted` seconds left."""

    hits: int
    period: int
    restricted: int


@dataclass(frozen=True)
class RateReport:
    """What one response said: the policy and, per rule name, its (limit, state) pairs."""

    policy: str
    rules: tuple[tuple[str, tuple[tuple[RateRule, RuleState], ...]], ...]


_TRIPLE = re.compile(r"(\d+):(\d+):(\d+)", re.ASCII)


def _triples(headers: Mapping[str, str], name: str) -> list[tuple[int, int, int]]:
    value = headers.get(name)
    if value is None:
        raise TradeError(f"rate-limit header {name} is missing")
    triples = []
    for part in value.split(","):
        match = _TRIPLE.fullmatch(part.strip())
        if match is None:
            raise TradeError(f"rate-limit header {name} is malformed: {value!r}")
        triples.append((int(match[1]), int(match[2]), int(match[3])))
    return triples


def parse_rate_limits(headers: Mapping[str, str]) -> RateReport | None:
    """Parse `x-rate-limit-policy`, `-rules`, `-{rule}` and `-{rule}-state` (lower-cased names).

    `None` when the policy header is absent. A malformed or missing companion header raises
    `TradeError` naming it.
    """
    policy = headers.get("x-rate-limit-policy")
    if policy is None:
        return None
    rules_value = headers.get("x-rate-limit-rules")
    if rules_value is None:
        raise TradeError("rate-limit header x-rate-limit-rules is missing")
    rules = []
    for rule in (part.strip() for part in rules_value.split(",")):
        if not rule:
            continue
        limit_name = f"x-rate-limit-{rule.lower()}"
        state_name = f"{limit_name}-state"
        limits = _triples(headers, limit_name)
        states = _triples(headers, state_name)
        if len(limits) != len(states):
            raise TradeError(f"rate-limit header {state_name} does not match {limit_name}")
        pairs = tuple((RateRule(*limit), RuleState(*state)) for limit, state in zip(limits, states))
        rules.append((rule, pairs))
    return RateReport(policy, tuple(rules))


class RateLimiter:
    """Waits as the last response of each kind of request said (kinds: "search", "fetch", "data").

    `after(kind, headers)` stores the parsed report with the clock time of the response.
    `before(kind)` works out the wait from that report, simply and conservatively. For every
    (rule, state) pair: if `state.restricted > 0` the wait is that many seconds from the response;
    else if `state.hits >= rule.hits - margin` the wait is `rule.period` seconds from the response.
    The wait is the maximum over all pairs, minus the time already passed. A wait over `max_wait`
    raises `TradeBlocked` instead of sleeping. No report yet, or no rate headers, means no wait.
    """

    def __init__(
        self,
        clock: Callable[[], float],
        sleep: Callable[[float], None],
        max_wait: float = 120.0,
        margin: int = 1,
    ) -> None:
        self._clock = clock
        self._sleep = sleep
        self.max_wait = max_wait
        self.margin = margin
        self._last: dict[str, tuple[RateReport, float]] = {}

    def after(self, kind: str, headers: Mapping[str, str]) -> None:
        report = parse_rate_limits(headers)
        if report is not None:
            self._last[kind] = (report, self._clock())

    def before(self, kind: str) -> None:
        if kind not in self._last:
            return
        report, at = self._last[kind]
        waits = [0.0]
        for _, pairs in report.rules:
            for rule, state in pairs:
                if state.restricted > 0:
                    waits.append(float(state.restricted))
                elif state.hits >= rule.hits - self.margin:
                    waits.append(float(rule.period))
        remaining = max(waits) - (self._clock() - at)
        if remaining <= 0:
            return
        if remaining > self.max_wait:
            raise TradeBlocked(
                f"the site asks for {remaining:g} s of waiting, which is more than the "
                f"{self.max_wait:g} s allowed; stopping"
            )
        self._sleep(remaining)


# --- the client ----------------------------------------------------------------------------


_COOKIE_VALUE = re.compile(r"[\x21-\x7e]*")  # printable ASCII only: no whitespace, control or non-ASCII
COOKIE_INVALID = (
    "POESESSID in the environment is not a valid cookie value "
    "(it has whitespace or a non-ASCII character); fix the variable"
)


def _json_object(body: bytes) -> dict | None:
    """The body as a JSON object, or `None` when it is not one."""
    try:
        parsed = json.loads(body.decode("utf-8"))
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _is_json(body: bytes) -> bool:
    try:
        json.loads(body.decode("utf-8"))
    except ValueError:
        return False
    return True


def _looks_like_challenge(body: bytes) -> bool:
    if _is_json(body):
        return False
    text = body.decode("utf-8", errors="replace").lower()
    return any(marker in text for marker in ("<html", "just a moment", "cloudflare"))


@dataclass(frozen=True)
class TradeClient:
    """Three calls to the trade API, each returning the parsed JSON object.

    Each call spends from the budget, lets the limiter wait if due, sends, feeds the limiter the
    response headers (error responses too, so a 429's limits are kept) and then applies the stop
    rules. The cookie, when given, is sent as `Cookie: POESESSID=...` and appears nowhere else.
    """

    transport: Transport
    agent: str
    limiter: RateLimiter
    budget: RequestBudget
    session_cookie: str | None = field(default=None, repr=False)

    def data_stats(self) -> dict:
        """GET the list of stat ids the site knows."""
        return self._call("data", "data/stats", "GET", f"{TRADE_URL}/data/stats")

    def search(self, league: str, body: dict) -> dict:
        """POST a query to the league; the answer has the search `id` and the result ids."""
        url = f"{TRADE_URL}/search/{urllib.parse.quote(league, safe='')}"
        return self._call("search", f"search {league}", "POST", url, json.dumps(body).encode("utf-8"))

    def fetch(self, ids: Sequence[str], search_id: str) -> dict:
        """GET up to 10 listings of a search by their ids."""
        if not ids or len(ids) > MAX_FETCH_IDS:
            raise ValueError(f"fetch takes 1 to {MAX_FETCH_IDS} ids, got {len(ids)}")
        joined = ",".join(urllib.parse.quote(item, safe="") for item in ids)
        url = f"{TRADE_URL}/fetch/{joined}?query={urllib.parse.quote(search_id, safe='')}"
        return self._call("fetch", f"fetch {len(ids)} listings", "GET", url)

    def _call(self, kind: str, what: str, method: str, url: str, body: bytes | None = None) -> dict:
        headers = {"User-Agent": self.agent, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.session_cookie is not None:
            if not _COOKIE_VALUE.fullmatch(self.session_cookie):
                raise TradeError(COOKIE_INVALID)  # the value itself is never in the message
            headers["Cookie"] = f"POESESSID={self.session_cookie}"
        self.budget.spend(what)
        self.limiter.before(kind)
        response = self.transport(HttpRequest(method, url, headers, body))
        self.limiter.after(kind, response.headers)
        return self._classify(response, what)

    def _classify(self, response: HttpResponse, what: str) -> dict:
        status = response.status
        if status in (401, 403):
            hint = "" if self.session_cookie is not None else f". {SESSION_HINT}"
            raise TradeBlocked(
                f"{what}: refused with HTTP {status}: Cloudflare challenge or login needed; "
                f"nothing was changed{hint}"
            )
        if status == 429:
            retry = response.headers.get("retry-after")
            wait = f"; the site asks to retry after {retry} s" if retry else ""
            raise TradeBlocked(
                f"{what}: refused with HTTP 429 (too many requests){wait}; stopping, nothing was changed"
            )
        if "cf-mitigated" in response.headers or _looks_like_challenge(response.body):
            raise TradeBlocked(
                f"{what}: the site answered with a Cloudflare challenge or an HTML page "
                f"(HTTP {status}) instead of JSON; stopping, nothing was changed"
            )
        parsed = _json_object(response.body)
        if 200 <= status < 300:
            if parsed is None:
                raise TradeError(f"{what}: HTTP {status} but the answer is not a JSON object")
            return parsed
        if 400 <= status < 500:
            message = _site_message(parsed)
            raise TradeError(f"{what}: HTTP {status}" + (f": {message}" if message else ""))
        if status >= 500:
            raise TradeError(f"{what}: the trade site failed with HTTP {status}")
        raise TradeError(f"{what}: unexpected HTTP {status} (redirects are not followed)")


def _site_message(parsed: dict | None) -> str | None:
    error = parsed.get("error") if parsed else None
    message = error.get("message") if isinstance(error, dict) else None
    return message if isinstance(message, str) and message.strip() else None
