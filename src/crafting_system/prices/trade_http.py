# Rate-limit header parsing adapted from PoEQuery `x_rate_limiter.py`, MIT, (c) 2021 Nick Ryder,
# licence in `third_party/PoEQuery-LICENSE.txt`.
"""The HTTP side of the trade-API pricing: transport, rate limits, request budget and stop rules.

GGG's trade API is undocumented. The system learns its limits from the `X-Rate-Limit-*` headers and
regulates itself so that it never reaches them; it never probes a limit by hitting it. So:

- the limits are read from the `X-Rate-Limit-*` headers of every response, never hard-coded: each
  window's limit and its current use. The `RateLimiter` keeps a configurable margin below every
  window (`margin` requests and/or `margin_fraction` of the limit, whichever is larger) and waits
  before a request that would use the last allowed hit of a window. The only request that cannot be
  regulated is the first of each policy, which is what teaches the limiter the limits;
- the state is kept per policy name (`X-Rate-Limit-Policy`), not per kind of request: two kinds the
  site puts under one policy share their windows;
- a 429 is honoured, not retried: the client raises `TradeRateLimited` (a `TradeBlocked`) and the
  limiter makes the NEXT request wait the `Retry-After` time (or `backoff_base` without it), doubled
  for every 429 in a row and capped. A service that wants to keep going after `TradeRateLimited`
  simply calls again: the limiter does the waiting. A wait over `max_wait` is `TradeWaitTooLong`
  (also a `TradeBlocked`), raised before anything is sent. A request that got no answer (timeout,
  cut-off) is counted as a hit anyway (`RateLimiter.lost`), because the site may have counted it;
- a 401, 403, a Cloudflare challenge or an HTML page instead of JSON stops the run with
  `TradeBlocked`: no retry, no bypass, nothing is changed;
- the limits it observes are logged (`logging.getLogger("crafting_system.prices.trade_http")`): the
  first sight of a policy at INFO and any change of its limits at WARNING, with the date of the
  response, so the limits can be checked over time (and kept in `RateLimiter.observations`); the use
  of every window at DEBUG; a window seen over its limit, or restricted, at WARNING;
- a hard `RequestBudget` bounds how many requests one run may send;
- the session cookie is sent only when the caller passes one. It is kept out of every `repr`,
  message, exception and log line raised here; the caller reads it from the environment itself.

One limiter serves one sequential caller: it is not thread-safe, by design (two threads would race
on the windows it is protecting). The waits run from the time the response arrived, which is later
than the time the server received the request, so they err on the safe side.

The transport, the clock and the sleep are injected; `urllib_transport` is the real transport.
"""

import http.client
import importlib.metadata
import json
import logging
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

_log = logging.getLogger(__name__)

TRADE_URL = "https://www.pathofexile.com/api/trade"
REPO_URL = "https://github.com/Rasslabsya4el/crafting-system"
TIMEOUT_SECONDS = 30
MIN_BACKOFF = 1.0  # seconds: the shortest pause after a 429
MAX_FETCH_IDS = 10  # the trade site's limit for one fetch call
SESSION_HINT = (
    "If you want to try with a session, set POESESSID in your environment yourself; "
    "this tool never asks for it"
)


class TradeError(Exception):
    """A trade request failed: network, an HTTP error, an unusable answer or a malformed header."""


class TradeBlocked(TradeError):
    """The site refused: HTTP 401/403/429, a Cloudflare challenge, or HTML instead of JSON.

    Its subclasses: `TradeRateLimited` (a 429) and `TradeWaitTooLong` (the limiter's wait would
    exceed its `max_wait`). The run stops.
    """


class TradeWaitTooLong(TradeBlocked):
    """The limiter needs to wait `wait` seconds, more than its `max_wait`; nothing was sent."""

    def __init__(self, wait: float, max_wait: float | None = None) -> None:
        limit = f"more than the {max_wait:g} s allowed" if max_wait is not None else "too long"
        super().__init__(f"the site asks for {wait:g} s of waiting, which is {limit}; stopping")
        self.wait = wait


class TradeRateLimited(TradeBlocked):
    """HTTP 429. `retry_after` is the site's `Retry-After` in seconds (or `None`).

    `backoff` is how long the limiter makes the next request wait. The client does not retry;
    the caller may simply call again.
    """

    def __init__(self, message: str, retry_after: float | None, backoff: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.backoff = backoff


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


_RETRY_SECONDS = re.compile(r"\d+(?:\.\d+)?", re.ASCII)


def _http_date(value: str | None) -> datetime | None:
    """An HTTP-date header value as an aware UTC datetime, or `None` when missing or unreadable."""
    if value is None:
        return None
    try:
        moment = parsedate_to_datetime(value.strip())
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def parse_retry_after(headers: Mapping[str, str]) -> float | None:
    """The `retry-after` header (lower-cased names) in seconds, or `None`.

    Understood: whole or decimal seconds (>= 0), or an HTTP-date, which is taken relative to the
    response's own `date` header (never below 0). A missing header, anything else, or an HTTP-date
    with no readable `date` header is `None`.
    """
    value = headers.get("retry-after")
    if value is None:
        return None
    value = value.strip()
    if _RETRY_SECONDS.fullmatch(value):
        seconds = float(value)
        return seconds if math.isfinite(seconds) else None
    when, sent = _http_date(value), _http_date(headers.get("date"))
    if when is None or sent is None:
        return None
    return max(0.0, (when - sent).total_seconds())


@dataclass(frozen=True)
class LimitObservation:
    """The limits a policy was seen with: the first sight (`changed` False) or a change (True)."""

    kind: str
    policy: str
    date: str | None  # ISO UTC of the response's `date` header, `None` when it had none
    rules: tuple[tuple[str, tuple[RateRule, ...]], ...]
    changed: bool


def _limits_of(report: RateReport) -> tuple[tuple[str, tuple[RateRule, ...]], ...]:
    """The limits of a report without the state: what has to be compared over time."""
    return tuple((name, tuple(rule for rule, _ in pairs)) for name, pairs in report.rules)


def _limits_text(limits: tuple[tuple[str, tuple[RateRule, ...]], ...]) -> str:
    """`Ip=5:10:60,15:60:300; Account=...` : the triples as the header spells them."""
    return "; ".join(
        f"{name}=" + ",".join(f"{rule.hits}:{rule.period}:{rule.restricted}" for rule in rules)
        for name, rules in limits
    )


class RateLimiter:
    """Waits so that no window of a policy is ever used beyond its limit minus a margin.

    One limiter serves one sequential caller (it is not thread-safe, by design). Kinds of request
    are "search", "fetch", "data". The site puts each kind under a policy; the state is kept per
    policy name, so kinds that share a policy share the windows. A kind is mapped to the policy of
    its latest response; with no policy header ever seen the kind's own name stands in.

    `after(kind, headers, status)` stores the parsed report with the clock time of the response and,
    on a 429, records the back-off. `before(kind)` works out the wait, simply and conservatively.
    For every (rule, state) pair of the last report of the policy: if `state.restricted > 0` the
    wait is that many seconds from the response; else if `state.hits >= allowed_hits(rule)` it is
    `rule.period` seconds from the response (every hit counted then is out of the window by then).
    The wait is the maximum over all pairs and the back-off still running, minus the time already
    passed. A wait over `max_wait` raises `TradeWaitTooLong` instead of sleeping. A kind never
    seen has no wait: the first request of a policy is the only one that cannot be regulated.
    The waits run from the arrival of the response, later than the server's receipt of the
    request, so they err on the safe side.

    Per window the allowed number of hits is
    `max(1, rule.hits - max(margin, ceil(rule.hits * margin_fraction)))`.

    A 429 sets the back-off: `Retry-After` (or `backoff_base` when it is absent or unreadable),
    doubled for every 429 in a row (a 2xx resets the count), capped at `backoff_cap` but never
    below `Retry-After`. The next `before` of that policy waits it out.

    `observations` collects a `LimitObservation` each time a policy is first seen or its limits
    change; the same facts go to the log (see the module docstring).
    """

    def __init__(
        self,
        clock: Callable[[], float],
        sleep: Callable[[float], None],
        max_wait: float = 120.0,
        margin: int = 1,
        margin_fraction: float = 0.0,
        backoff_base: float = 60.0,
        backoff_cap: float = 3600.0,
    ) -> None:
        self._clock = clock
        self._sleep = sleep
        self.max_wait = max_wait
        self.margin = margin
        self.margin_fraction = margin_fraction
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.observations: list[LimitObservation] = []
        self._policy_of: dict[str, str] = {}  # kind -> policy of its latest response
        self._last: dict[str, tuple[RateReport, float]] = {}  # key -> (report, response time)
        self._blocked_until: dict[str, float] = {}
        self._consecutive: dict[str, int] = {}
        self._limits_seen: dict[str, tuple[tuple[str, tuple[RateRule, ...]], ...]] = {}

    def allowed_hits(self, rule: RateRule) -> int:
        """How many hits of the window this limiter lets the state reach: at least 1."""
        cut = max(self.margin, math.ceil(rule.hits * self.margin_fraction - 1e-9))
        return max(1, rule.hits - cut)

    def _key(self, kind: str) -> str:
        return self._policy_of.get(kind, kind)

    def after(self, kind: str, headers: Mapping[str, str], status: int | None = None) -> float | None:
        """Take in a response. Returns the back-off in seconds after a 429, else `None`.

        The back-off is recorded before the headers are parsed, so a malformed rate header
        (`TradeError`) still leaves the next request waiting.
        """
        policy = headers.get("x-rate-limit-policy")
        if policy is not None:
            self._policy_of[kind] = policy
            self._adopt(kind, policy)
        key = self._key(kind)
        backoff = None
        if status == 429:
            backoff = self._back_off(kind, key, headers)
        elif status is not None and 200 <= status < 300:
            self._consecutive[key] = 0
        report = parse_rate_limits(headers)
        if report is not None:
            self._last[key] = (report, self._clock())
            self._observe(kind, report, headers)
        return backoff

    def _adopt(self, kind: str, policy: str) -> None:
        """A back-off kept under the kind's own name (no policy known then) moves to the policy."""
        if policy == kind:
            return
        if kind in self._blocked_until:
            until = self._blocked_until.pop(kind)
            self._blocked_until[policy] = max(until, self._blocked_until.get(policy, until))
        if kind in self._consecutive:
            count = self._consecutive.pop(kind)
            self._consecutive[policy] = max(count, self._consecutive.get(policy, count))

    def _back_off(self, kind: str, key: str, headers: Mapping[str, str]) -> float:
        count = self._consecutive.get(key, 0) + 1
        self._consecutive[key] = count
        retry_after = parse_retry_after(headers)
        base = retry_after if retry_after is not None else self.backoff_base
        wait = min(base * 2.0 ** min(count - 1, 64), self.backoff_cap)
        if retry_after is not None:
            wait = max(wait, retry_after)
        wait = max(wait, MIN_BACKOFF)  # a `Retry-After: 0` after a 429 still gets a pause
        self._blocked_until[key] = self._clock() + wait
        shown = "none" if retry_after is None else f"{retry_after:g} s"
        _log.warning(
            "rate limit hit (HTTP 429): kind=%s policy=%s retry-after=%s consecutive=%d; "
            "the next request waits %g s",
            kind,
            key,
            shown,
            count,
            wait,
        )
        return wait

    def _observe(self, kind: str, report: RateReport, headers: Mapping[str, str]) -> None:
        limits = _limits_of(report)
        previous = self._limits_seen.get(report.policy)
        if previous != limits:
            moment = _http_date(headers.get("date"))
            date = None if moment is None else moment.strftime("%Y-%m-%dT%H:%M:%SZ")
            changed = previous is not None
            self._limits_seen[report.policy] = limits
            self.observations.append(LimitObservation(kind, report.policy, date, limits, changed))
            line = (
                f"rate limits {'changed' if changed else 'first seen'}: kind={kind} "
                f"policy={report.policy} date={date or 'unknown'} {_limits_text(limits)}"
            )
            if previous is None:
                _log.info(line)
            else:
                _log.warning("%s (was %s)", line, _limits_text(previous))
        if _log.isEnabledFor(logging.DEBUG):
            use = "; ".join(
                f"{name}=" + ",".join(f"{state.hits}/{rule.hits} per {rule.period} s" for rule, state in pairs)
                for name, pairs in report.rules
            )
            _log.debug("rate use: kind=%s policy=%s %s", kind, report.policy, use)
        for name, pairs in report.rules:
            for rule, state in pairs:
                if state.hits > rule.hits or state.restricted > 0:
                    _log.warning(
                        "a rate limit was hit: kind=%s policy=%s %s window %d s: %d of %d used, restricted for %d s",
                        kind,
                        report.policy,
                        name,
                        rule.period,
                        state.hits,
                        rule.hits,
                        state.restricted,
                    )

    def lost(self, kind: str) -> None:
        """A request of this kind was sent but no answer came (timeout, cut-off): count it.

        The server may have counted the hit, so every window of the policy's last report is raised
        by one hit and dated now (hits only expire with time, so this errs on the safe side).
        """
        key = self._key(kind)
        if key not in self._last:
            return
        report, _ = self._last[key]
        rules = tuple(
            (name, tuple((rule, RuleState(state.hits + 1, state.period, state.restricted)) for rule, state in pairs))
            for name, pairs in report.rules
        )
        self._last[key] = (RateReport(report.policy, rules), self._clock())

    def before(self, kind: str) -> None:
        key = self._key(kind)
        now = self._clock()
        remaining = 0.0
        if key in self._last:
            report, at = self._last[key]
            waits = [0.0]
            for _, pairs in report.rules:
                for rule, state in pairs:
                    if state.restricted > 0:
                        waits.append(float(state.restricted))
                    elif state.hits >= self.allowed_hits(rule):
                        waits.append(float(rule.period))
            remaining = max(waits) - (now - at)
        if key in self._blocked_until:
            remaining = max(remaining, self._blocked_until[key] - now)
        if remaining <= 0:
            return
        if remaining > self.max_wait:
            raise TradeWaitTooLong(remaining, self.max_wait)
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
    response headers and status (error responses too, so a 429's limits and back-off are kept) and
    then applies the stop rules. A 429 raises `TradeRateLimited`; the client does not retry, the
    caller may call again and the limiter makes that request wait. The cookie, when given, is sent
    as `Cookie: POESESSID=...` and appears nowhere else.
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
        try:
            response = self.transport(HttpRequest(method, url, headers, body))
        except TradeError:
            self.limiter.lost(kind)  # the server may have counted it although no answer came
            raise
        backoff = self.limiter.after(kind, response.headers, response.status)
        return self._classify(response, what, backoff)

    def _classify(self, response: HttpResponse, what: str, backoff: float | None = None) -> dict:
        status = response.status
        if status in (401, 403):
            hint = "" if self.session_cookie is not None else f". {SESSION_HINT}"
            raise TradeBlocked(
                f"{what}: refused with HTTP {status}: Cloudflare challenge or login needed; "
                f"nothing was changed{hint}"
            )
        if status == 429:
            retry_after = parse_retry_after(response.headers)
            asked = f"; the site asks to retry after {retry_after:g} s" if retry_after is not None else ""
            raise TradeRateLimited(
                f"{what}: refused with HTTP 429 (too many requests){asked}; stopping, nothing was changed"
                f"; the next request waits {backoff or 0.0:g} s",
                retry_after,
                backoff or 0.0,
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
