"""Test helpers for the poe.watch and previous-league stages: a fake of both hosts, from the recordings."""

import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from crafting_system.prices.http_json import SourceError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
WATCH_HOST = "api.poe.watch"
NINJA_HOST = "poe.ninja"


def recorded(host: str, name: str):
    return json.loads((FIXTURES / host / f"{name}.json").read_text(encoding="utf-8"))


def watch_fixture(name: str):
    return recorded("poe_watch", name)


def ninja_fixture(name: str):
    return recorded("poe_ninja", name)


class FakeWatch:
    """A `get_json` that maps a URL of poe.watch or poe.ninja to a recorded response; no network.

    A response is a parsed JSON value, or an exception to raise. `leagues`, `ratios` and `dumps` are
    one response each; `get[category]`, `history[id]`, `details[(league, type, id)]` and
    `stash[(league, type, id)]` are keyed. A keyed request nobody set up answers like a 404; a URL
    the stages should never ask raises `AssertionError`. Every URL asked for is kept in `requests`.
    """

    def __init__(self):
        self.requests: list[str] = []
        self.leagues = watch_fixture("leagues")
        self.ratios = watch_fixture("ratios")
        self.get = {name: watch_fixture(f"get_{name}") for name in ("beast", "essence", "bases")}
        self.history = {850: watch_fixture("history_850_allflame")}
        self.dumps = ninja_fixture("dumps")
        self.details = {
            ("Mirage", "Fossil", "hollow-fossil"): ninja_fixture("details_hollow_fossil_mirage"),
            ("Standard", "Fossil", "hollow-fossil"): ninja_fixture("details_hollow_fossil_standard"),
        }
        self.stash = {
            ("Mirage", "BaseType", 34026): ninja_fixture("stash_history_basetype_34026_mirage"),
            ("Standard", "BaseType", 34026): ninja_fixture("stash_history_basetype_34026_standard"),
        }

    def __call__(self, url: str):
        self.requests.append(url)
        parts = urlsplit(url)
        query = {key: values[0] for key, values in parse_qs(parts.query).items()}
        missing = SourceError(f"HTTP 404 for {url}")
        match parts.hostname, parts.path:
            case "api.poe.watch", "/leagues":
                return self._answer(self.leagues)
            case "api.poe.watch", "/exchange/ratios":
                assert query.get("game") == "poe1", url
                return self._answer(self.ratios)
            case "api.poe.watch", "/get":
                return self._answer(self.get.get(query["category"], missing))
            case "api.poe.watch", "/history":
                return self._answer(self.history.get(int(query["id"]), missing))
            case "poe.ninja", "/poe1/api/data/dumps":
                return self._answer(self.dumps)
            case "poe.ninja", "/poe1/api/economy/exchange/current/details":
                return self._answer(self.details.get((query["league"], query["type"], query["id"]), missing))
            case "poe.ninja", "/poe1/api/economy/stash/current/item/history":
                key = (query["league"], query["type"], int(query["id"]))
                return self._answer(self.stash.get(key, missing))
        raise AssertionError(f"unexpected URL {url}")

    @staticmethod
    def _answer(response):
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)

    def asked(self, host: str, path: str) -> list[str]:
        """The URLs asked on `host` for the route `path`."""
        return [url for url in self.requests if urlsplit(url).hostname == host and urlsplit(url).path == path]

    def ratio_item(self, name: str) -> dict:
        """The item of the `ratios` answer with this name, for the test to change in place."""
        return next(item for item in self.ratios["items"] if item["name"] == name)


@pytest.fixture
def watch() -> FakeWatch:
    return FakeWatch()
