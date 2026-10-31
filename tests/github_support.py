"""A fake GitHub API for the data tests, serving the recorded answer in `fixtures/github`.

`repoe_commits.json` is a real answer of the commit list of repoe-fork.github.io (the 45 newest
commits when it was recorded: sha, commit.message, commit.committer.date). Not a test module:
`test_data_resolve.py` and `test_data_pin.py` import what they need.
"""

import io
import json
import re
import urllib.error
from collections.abc import Callable, Sequence
from pathlib import Path

from crafting_system.data.resolve import COMMITS_URL

COMMITS_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "github" / "repoe_commits.json"
PAGE = re.compile(r"\?per_page=100&page=(\d+)$")


def recorded_commits() -> list[dict]:
    """The recorded commit list, newest first."""
    return json.loads(COMMITS_FIXTURE.read_text(encoding="utf-8"))


def commit_entry(sha: str, message: str, date: str = "2026-01-01T00:00:00Z") -> dict:
    """A commit as the API shapes it."""
    return {"sha": sha, "commit": {"message": message, "committer": {"date": date}}}


def sha_of(prefix: str, nth: int = 0) -> str:
    """The full commit id of the recorded commit that starts with `prefix`."""
    return [entry["sha"] for entry in recorded_commits() if entry["sha"].startswith(prefix)][nth]


class FakeGitHub:
    """Stands in for `open_url` on the commit list: page N of `pages` (an empty list past the end).

    `urls` and `pages_asked` remember what was asked; a commit asked for by id is served from
    `commits` (id -> entry), else the API's answer for an unknown commit (HTTP 422).
    """

    def __init__(self, pages: Sequence[Sequence[dict]] | None = None, commits: dict[str, dict] | None = None):
        self.pages = [list(page) for page in (pages if pages is not None else [recorded_commits()])]
        self.commits = commits or {}
        self.urls: list[str] = []
        self.pages_asked: list[int] = []

    def __call__(self, url: str):
        self.urls.append(url)
        if url.startswith(COMMITS_URL + "/"):
            entry = self.commits.get(url.removeprefix(COMMITS_URL + "/"))
            if entry is None:
                raise urllib.error.HTTPError(url, 422, "Unprocessable Entity", None, None)
            return io.BytesIO(json.dumps(entry).encode("utf-8"))
        match = PAGE.search(url)
        if not url.startswith(COMMITS_URL + "?") or match is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        number = int(match.group(1))
        self.pages_asked.append(number)
        page = self.pages[number - 1] if number <= len(self.pages) else []
        return io.BytesIO(json.dumps(page).encode("utf-8"))


def routed(files: Callable, github: Callable) -> Callable:
    """One `open_url` that sends the API's URLs to `github` and every other URL to `files`."""

    def open_url(url: str):
        return (github if url.startswith("https://api.github.com/") else files)(url)

    return open_url


def files_world(candidates: dict[str, dict[str, bytes]], *, pin_version: str = "9.9.9", pin_commit: str = "a" * 40):
    """(an active pin made of the committed excerpt, an opener serving it and every commit in `candidates`).

    `candidates` maps a commit to the file bytes served at that commit, as `diff` and `pin` download them.
    """
    from repoe_support import FakeOpener, fixture_bytes, make_pin

    pin = make_pin(fixture_bytes(), version=pin_version, commit=pin_commit)
    opener = FakeOpener(pin, fixture_bytes())
    for commit, payloads in candidates.items():
        opener.served.update(FakeOpener(make_pin(payloads, version=commit, commit=commit), payloads).served)
    return pin, opener
