"""The shared read-only transport of the price fetchers: one GET, decoded as JSON.

poe.ninja and poe.watch are both read through `GetJson`, so a test injects one fake that answers
for both hosts, and the real one is `http_get_json`. Every failure is a `SourceError`.
"""

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

USER_AGENT = "crafting-system price fetcher (https://github.com/Rasslabsya4el/crafting-system)"
TIMEOUT_SECONDS = 30

GetJson = Callable[[str], Any]


class SourceError(Exception):
    """A price source failed: HTTP error, network error, invalid JSON or a changed shape."""


def http_get_json(url: str, timeout: float = TIMEOUT_SECONDS) -> Any:
    """The real transport: one GET, decoded as JSON; every failure is a `SourceError`."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise SourceError(f"HTTP {error.code} from {url}") from error
    except (OSError, http.client.HTTPException) as error:  # URLError, timeouts, cut-off answers
        raise SourceError(f"cannot reach {url}: {error}") from error
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as error:  # bad UTF-8 or bad JSON
        raise SourceError(f"invalid JSON from {url}: {error}") from error


PAUSE_SECONDS = 0.3


def paced(
    get_json: GetJson,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
    interval: float = PAUSE_SECONDS,
) -> GetJson:
    """`get_json` that leaves at least `interval` seconds between two requests, to go easy on the sites.

    The fallbacks can send a dozen requests for one unpriced name, so the real fetch is paced; the clock
    and the sleep are injected, as everywhere else.
    """
    last: list[float] = []

    def get(url: str) -> Any:
        if last and (wait := interval - (monotonic() - last[0])) > 0:
            sleep(wait)
        try:
            return get_json(url)
        finally:
            last[:] = [monotonic()]

    return get
