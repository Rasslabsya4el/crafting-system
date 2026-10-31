"""Game version names and repoe-fork commits: which export of the site is the one for a patch.

repoe-fork.github.io commits a new export of the game data every few days, with the message
`Export <version>` (the game's version, like `3.29.3.3`, several times per patch as the data is
re-read) and, a few minutes earlier, `Version <version>`. GitHub's commit list of the repository
(newest first) is the only index of them, so a version name is resolved by reading that list.

A commit counts as the export of `<version>` when its message's first line, without a leading
`[skip ci] `, is exactly `Export <version>`: the whole name, so `3.29.3.1` never matches
`Export 3.29.3.1.4`, and `Version <version>` commits and `Export Internal Server Error` never match.
The first match in the list is the newest one, and that is the one taken.

The commit list is the one place besides the file downloads that needs the network; it is
unauthenticated unless `GITHUB_TOKEN` (or `GH_TOKEN`) is set in the environment, so GitHub's rate limit
(60 calls an hour per address) applies, and a refusal says so. The token goes to api.github.com only.
"""

import http.client
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, BinaryIO

from .errors import FetchError, VersionNotFoundError
from .fetch import TIMEOUT_SECONDS, USER_AGENT, OpenUrl

COMMITS_URL = "https://api.github.com/repos/repoe-fork/repoe-fork.github.io/commits"
PAGE_SIZE = 100
MAX_PAGES = 10
# One page of the commit list is a few hundred kilobytes; this keeps a wrong answer from filling memory.
MAX_ANSWER_BYTES = 32 * 1024 * 1024

GITHUB_API_HOST = "api.github.com"
TOKEN_VARIABLES = ("GITHUB_TOKEN", "GH_TOKEN")

_VERSION = re.compile(r"\d+(\.\d+)+")
_SKIP_CI = "[skip ci] "
_EXPORT = "Export "


@dataclass(frozen=True)
class Export:
    """One export commit of repoe-fork.github.io: its commit id, the game version it names, its date and full message."""

    commit: str
    version: str
    date: str
    message: str


class _KeepTokenOnGitHub(urllib.request.HTTPRedirectHandler):
    """Follow a redirect, but never carry the token to a host other than api.github.com."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and urllib.parse.urlparse(newurl).hostname != GITHUB_API_HOST:
            redirected.remove_header("Authorization")
        return redirected


_OPENER = urllib.request.build_opener(_KeepTokenOnGitHub)


def github_open_url(url: str) -> AbstractContextManager[BinaryIO]:
    """Open a GitHub API `url`; a token from the environment, when there is one, raises the rate limit."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = next((os.environ[name] for name in TOKEN_VARIABLES if os.environ.get(name)), None)
    if token and urllib.parse.urlparse(url).hostname == GITHUB_API_HOST:
        headers["Authorization"] = f"Bearer {token}"
    return _OPENER.open(urllib.request.Request(url, headers=headers), timeout=TIMEOUT_SECONDS)


def is_version_name(text: str) -> bool:
    """Whether `text` looks like a game version name: dot-separated numbers, such as `3.29.3.3`."""
    return bool(_VERSION.fullmatch(text))


def resolve_version(version: str, *, open_url: OpenUrl | None = None, max_pages: int = MAX_PAGES) -> Export:
    """The newest export commit of the game version `version`, from the newest `max_pages` pages of the commit list.

    Raises `VersionNotFoundError` when none of them is an export of that version (the message
    names the newest export that was seen) and `FetchError` when GitHub cannot be read.
    """
    if not is_version_name(version):
        raise ValueError(f"{version!r} is not a game version name: use dot-separated numbers like 3.29.3.3")
    open_url = open_url or github_open_url
    seen = 0
    newest = None
    for page in range(1, max_pages + 1):
        url = f"{COMMITS_URL}?per_page={PAGE_SIZE}&page={page}"
        entries = _read_json(url, open_url)
        if not isinstance(entries, list):
            raise _unexpected(url, "a list of commits was expected")
        if not entries:  # the history ends before max_pages
            break
        for entry in entries:
            seen += 1
            export = _as_export(entry, url)
            if export is None:
                continue
            if export.version == version:
                return export
            newest = newest or export
    raise VersionNotFoundError(
        f"no export of {version} among the last {seen} commits of repoe-fork.github.io"
        + (f" (the newest export seen is {newest.version}, commit {newest.commit[:8]})" if newest else "")
        + ". Check the version name against the game's patch notes; "
        "a patch that is only a few hours old may not have been exported yet."
    )


def export_of_commit(commit: str, open_url: OpenUrl | None = None) -> Export | None:
    """The export `commit` is (asked of GitHub), or None when its message does not name an export version."""
    url = f"{COMMITS_URL}/{commit}"
    entry = _read_json(url, open_url or github_open_url)
    return _as_export(entry, url)


def _as_export(entry: Any, url: str) -> Export | None:
    """The `Export` a commit entry of the API is, None when it is some other commit."""
    try:
        commit = entry["sha"]
        message = entry["commit"]["message"]
    except (KeyError, TypeError):
        raise _unexpected(url, "a commit without sha and message") from None
    if not isinstance(commit, str) or not isinstance(message, str):
        raise _unexpected(url, "a commit whose sha or message is not text")
    version = _export_version(message)
    if version is None:
        return None
    committer = entry["commit"].get("committer")
    date = committer.get("date") if isinstance(committer, dict) else None
    return Export(commit, version, date if isinstance(date, str) else "", message)


def _export_version(message: str) -> str | None:
    """The version of an `Export <version>` message (first line, a leading `[skip ci] ` ignored), else None."""
    first = message.split("\n", 1)[0].strip()
    first = first.removeprefix(_SKIP_CI)
    if not first.startswith(_EXPORT):
        return None
    name = first.removeprefix(_EXPORT)
    return name if is_version_name(name) else None


def _read_json(url: str, open_url: OpenUrl) -> Any:
    try:
        with open_url(url) as response:
            data = response.read(MAX_ANSWER_BYTES + 1)
    except urllib.error.HTTPError as error:
        hint = " (GitHub's rate limit may be hit: retry later, or set GITHUB_TOKEN)" if error.code == 403 else ""
        raise FetchError(f"could not read {url}: {error}{hint}") from error
    except (OSError, http.client.HTTPException) as error:
        raise FetchError(f"could not read {url}: {error}") from error
    if len(data) > MAX_ANSWER_BYTES:
        raise _unexpected(url, f"the answer is larger than {MAX_ANSWER_BYTES} bytes")
    try:
        return json.loads(data)
    except (ValueError, RecursionError) as error:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        raise _unexpected(url, f"it is not JSON ({error})") from error


def _unexpected(url: str, reason: str) -> FetchError:
    return FetchError(f"the answer of {url} is not the commit list GitHub gives: {reason}")
