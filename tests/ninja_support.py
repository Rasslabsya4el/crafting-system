"""Test helpers for the price layer: a fake poe.ninja that answers from the recorded responses."""

import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from crafting_system.prices.poe_ninja import BASE_URL, SourceError

NINJA_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "poe_ninja"
OVERVIEW_TYPES = ("Currency", "Fossil", "Resonator", "Essence")
STASH_TYPES = ("Beast", "BaseType")


def ninja_fixture(name: str):
    return json.loads((NINJA_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeNinja:
    """A `get_json` that maps a URL to a recorded response; no network.

    `leagues`, `overviews[type]`, `details[(type, id)]`, `stash_overviews[type]` and
    `stash_histories[(league, type, id)]` hold the response to give: a parsed JSON value, or an
    exception to raise. A details or stash history request nobody set up answers like a 404.
    Every URL asked for is kept in `requests`.
    """

    def __init__(self):
        self.requests: list[str] = []
        self.leagues = ninja_fixture("leagues")
        self.overviews = {kind: ninja_fixture(f"overview_{kind.lower()}") for kind in OVERVIEW_TYPES}
        self.details = {("Fossil", "hollow-fossil"): ninja_fixture("details_hollow_fossil")}
        self.stash_overviews = {kind: ninja_fixture(f"stash_{kind.lower()}") for kind in STASH_TYPES}
        self.stash_histories: dict[tuple[str, str, int], object] = {}

    def __call__(self, url: str):
        self.requests.append(url)
        parts = urlsplit(url)
        query = {key: values[0] for key, values in parse_qs(parts.query).items()}
        route = url.split("?")[0].removeprefix(BASE_URL)
        if route == "/leagues":
            return self._answer(self.leagues)
        if route == "/exchange/current/overview":
            return self._answer(self.overviews[query["type"]])
        if route == "/exchange/current/details":
            key = (query["type"], query["id"])
            return self._answer(self.details.get(key, SourceError(f"HTTP 404 for {url}")))
        if route == "/stash/current/item/overview":
            return self._answer(self.stash_overviews[query["type"]])
        if route == "/stash/current/item/history":
            key = (query["league"], query["type"], int(query["id"]))
            return self._answer(self.stash_histories.get(key, SourceError(f"HTTP 404 for {url}")))
        if not url.startswith(BASE_URL):
            return self._answer(SourceError(f"HTTP 404 for {url}"))  # poe.watch and the league list: not recorded here
        raise AssertionError(f"unexpected URL {url}")

    @staticmethod
    def _answer(response):
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)

    def detail_requests(self) -> list[str]:
        return [url for url in self.requests if "/exchange/current/details" in url]

    def stash_history_requests(self) -> list[str]:
        return [url for url in self.requests if "/stash/current/item/history" in url]

    def set_stash_line(self, kind: str, line_id: int, **changes) -> None:
        """Change fields of one stash overview line; a value of None removes the field."""
        for line in self.stash_overviews[kind]["lines"]:
            if line["id"] == line_id:
                for field, value in changes.items():
                    if value is None:
                        line.pop(field, None)
                    else:
                        line[field] = value
                return
        raise AssertionError(line_id)

    def drop_line(self, kind: str, line_id: str) -> None:
        """Remove one item from an overview, as if poe.ninja had no line for it."""
        overview = self.overviews[kind]
        overview["lines"] = [line for line in overview["lines"] if line["id"] != line_id]
        overview["items"] = [item for item in overview["items"] if item["id"] != line_id]


@pytest.fixture
def ninja() -> FakeNinja:
    return FakeNinja()
