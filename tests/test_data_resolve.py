"""Game version names: resolved to the newest export commit of repoe-fork.github.io, on a recorded GitHub answer."""

import io
import json
import urllib.error
import urllib.request

import pytest
from github_support import (
    FakeGitHub,
    commit_entry,
    files_world,
    recorded_commits,
    routed,
    sha_of,
)
from repoe_support import (
    no_network,  # noqa: F401
    raw_to_bytes,
)
from seeded_versions import seeded_raw

from crafting_system.data import FetchError, VersionNotFoundError, export_of_commit, is_version_name, resolve_version
from crafting_system.data import resolve as resolve_module
from crafting_system.data import __main__ as data_main
from crafting_system.data.__main__ import main
from crafting_system.data.resolve import COMMITS_URL, Export

PAGE_1 = f"{COMMITS_URL}?per_page=100&page=1"


def test_a_version_resolves_to_the_newest_of_its_export_commits_and_skips_version_commits():
    github = FakeGitHub()

    export = resolve_version("3.29.3.3", open_url=github)

    # the very newest commit of the record is "Version 3.29.3.3", then come the exports, newest first
    assert recorded_commits()[0]["commit"]["message"] == "[skip ci] Version 3.29.3.3"
    assert export == Export(
        commit=sha_of("ee2084de"),
        version="3.29.3.3",
        date="2026-10-19T04:13:16Z",
        message="[skip ci] Export 3.29.3.3",
    )
    assert github.urls == [PAGE_1]


@pytest.mark.parametrize(
    ("version", "prefix"),
    [
        ("3.29.3.2", "926da1c0"),
        ("3.29.3.1", "1ae640c8"),
        ("3.29.3.1.2", "76f2236c"),
        ("3.29.3.1.4", "e08ee75b"),
        ("3.29.2.1", "626b157b"),
    ],
)
def test_each_version_takes_its_own_newest_export(version, prefix):
    assert resolve_version(version, open_url=FakeGitHub()).commit == sha_of(prefix)


def test_a_version_is_the_whole_name_not_a_prefix_of_a_longer_one():
    only_longer = [entry for entry in recorded_commits() if "Export 3.29.3.1.4" in entry["commit"]["message"]]

    with pytest.raises(VersionNotFoundError, match="3.29.3.1"):
        resolve_version("3.29.3.1", open_url=FakeGitHub([only_longer]))
    assert resolve_version("3.29.3.1.4", open_url=FakeGitHub([only_longer])).commit == sha_of("e08ee75b")
    only_shorter = [entry for entry in recorded_commits() if entry["commit"]["message"].endswith("Export 3.29.3.1")]
    with pytest.raises(VersionNotFoundError):
        resolve_version("3.29.3.1.4", open_url=FakeGitHub([only_shorter]))


def test_a_version_with_no_export_is_refused_naming_the_newest_export_seen():
    with pytest.raises(VersionNotFoundError) as caught:
        resolve_version("3.29.9.9", open_url=FakeGitHub())

    message = str(caught.value)
    assert "no export of 3.29.9.9" in message
    assert f"last {len(recorded_commits())} commits of repoe-fork.github.io" in message
    assert "newest export seen is 3.29.3.3" in message
    assert sha_of("ee2084de")[:8] in message


def test_a_version_that_only_has_a_version_commit_is_not_found():
    only_version = [commit_entry("a" * 40, "[skip ci] Version 4.0.0.1")]

    with pytest.raises(VersionNotFoundError, match="no export of 4.0.0.1") as caught:
        resolve_version("4.0.0.1", open_url=FakeGitHub([only_version]))

    assert "newest export seen" not in str(caught.value)  # none was seen


@pytest.mark.parametrize(
    ("message", "matches"),
    [
        ("[skip ci] Export 4.0.0.1", True),
        ("Export 4.0.0.1", True),
        ("[skip ci] Export 4.0.0.1\n\nbody of the message", True),
        ("[skip ci] Version 4.0.0.1", False),
        ("[skip ci] Export 4.0.0.1.1", False),
        ("[skip ci] Export 4.0.0", False),
        ("[skip ci] Export 4.0.0.1 again", False),
        ("[skip ci] export 4.0.0.1", False),
        ("Merge: Export 4.0.0.1", False),
        ("[skip ci] Export Internal Server Error", False),
    ],
)
def test_only_the_message_export_and_the_whole_version_counts(message, matches):
    github = FakeGitHub([[commit_entry("a" * 40, message)]])

    if matches:
        assert resolve_version("4.0.0.1", open_url=github).commit == "a" * 40
    else:
        with pytest.raises(VersionNotFoundError):
            resolve_version("4.0.0.1", open_url=github)


def test_the_pages_are_read_in_order_and_reading_stops_at_the_match():
    entries = recorded_commits()
    page_1, page_2, page_3 = entries[:22], entries[22:40], entries[40:]
    github = FakeGitHub([page_1, page_2, page_3])

    export = resolve_version("3.29.3.1.2", open_url=github)  # the first export of it is on page 2

    assert export.commit == sha_of("76f2236c")
    assert github.pages_asked == [1, 2]
    assert github.urls == [f"{COMMITS_URL}?per_page=100&page=1", f"{COMMITS_URL}?per_page=100&page=2"]


def test_a_version_on_page_one_does_not_ask_for_page_two():
    github = FakeGitHub([recorded_commits()[:22], recorded_commits()[22:]])

    resolve_version("3.29.3.3", open_url=github)

    assert github.pages_asked == [1]


def test_reading_stops_after_max_pages_and_the_error_counts_the_commits_read():
    entries = recorded_commits()
    github = FakeGitHub([entries[:22], entries[22:40], entries[40:]])

    with pytest.raises(VersionNotFoundError, match=r"last 22 commits"):
        resolve_version("2.0.0.0", open_url=github, max_pages=1)
    assert github.pages_asked == [1]
    github.pages_asked.clear()
    with pytest.raises(VersionNotFoundError, match=r"last 45 commits"):
        resolve_version("2.0.0.0", open_url=github)
    assert github.pages_asked == [1, 2, 3, 4]  # page 4 is empty: the history ends there


def test_the_search_looks_through_every_page_before_giving_up():
    github = FakeGitHub()  # page 1 holds the record, page 2 and later are empty

    with pytest.raises(VersionNotFoundError):
        resolve_version("3.29.9.9", open_url=github)

    assert github.pages_asked == [1, 2]


@pytest.mark.parametrize("bad", ["", "3", "3.", ".3", "3..2", "3.29.x", "v3.29.3.3", "3.29.3.3 ", "../3.1", "pinned"])
def test_text_that_is_not_a_version_name_is_refused_before_any_request(bad):
    github = FakeGitHub()

    with pytest.raises(ValueError, match="not a game version name"):
        resolve_version(bad, open_url=github)

    assert github.urls == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [("3.29.3.3", True), ("3.29", True), ("10.0.1", True), ("3", False), ("3.29.3.3-x", False), ("a.b", False)],
)
def test_what_looks_like_a_version_name(text, expected):
    assert is_version_name(text) is expected


# --- the GitHub answer is wrong ------------------------------------------------------------------


def http_error(code):
    def opener(url):
        raise urllib.error.HTTPError(url, code, "refused", None, None)

    return opener


def test_an_http_403_names_the_url_and_says_the_rate_limit_may_be_hit():
    with pytest.raises(FetchError) as caught:
        resolve_version("3.29.3.3", open_url=http_error(403))

    assert PAGE_1 in str(caught.value)
    assert "403" in str(caught.value)
    assert "rate limit" in str(caught.value)
    assert "retry later" in str(caught.value)


def test_another_http_error_names_the_url_without_the_rate_limit_hint():
    with pytest.raises(FetchError) as caught:
        resolve_version("3.29.3.3", open_url=http_error(500))

    assert PAGE_1 in str(caught.value)
    assert "500" in str(caught.value)
    assert "rate limit" not in str(caught.value)


def test_a_network_error_names_the_url():
    def failing(url):
        raise urllib.error.URLError("no route to host")

    with pytest.raises(FetchError, match="no route to host") as caught:
        resolve_version("3.29.3.3", open_url=failing)

    assert PAGE_1 in str(caught.value)


@pytest.mark.parametrize(
    "answer",
    [
        b"<html>Service unavailable</html>",
        b"",
        b"\xff\xfe\x00",
        b"[" * 200_000,
        b'{"message": "API rate limit exceeded"}',
        b'"text"',
        b"[1, 2]",
        b'[{"sha": "abc"}]',
        b'[{"sha": 5, "commit": {"message": "Export 1.2"}}]',
        b'[{"sha": "abc", "commit": {"message": 7}}]',
        b'[{"sha": "abc", "commit": "Export 1.2"}]',
    ],
)
def test_an_answer_that_is_not_a_commit_list_is_a_fetch_error_naming_the_url(answer):
    with pytest.raises(FetchError) as caught:
        resolve_version("1.2", open_url=lambda url: io.BytesIO(answer))

    assert PAGE_1 in str(caught.value)
    assert "Traceback" not in str(caught.value)


def test_an_answer_that_is_too_large_is_refused(monkeypatch):
    from crafting_system.data import resolve

    monkeypatch.setattr(resolve, "MAX_ANSWER_BYTES", 100)

    with pytest.raises(FetchError, match="larger than 100 bytes"):
        resolve_version("3.29.3.3", open_url=FakeGitHub())


# --- the export a commit is -----------------------------------------------------------------------


def test_the_export_of_a_commit_is_read_from_its_message():
    commit = sha_of("926da1c0")
    entry = next(entry for entry in recorded_commits() if entry["sha"] == commit)
    github = FakeGitHub(commits={commit: entry})

    export = export_of_commit(commit, github)

    assert export == Export(commit, "3.29.3.2", "2026-08-27T11:23:45Z", "[skip ci] Export 3.29.3.2")
    assert github.urls == [f"{COMMITS_URL}/{commit}"]


@pytest.mark.parametrize("prefix", ["d8635430", "1bec308b", "29927533", "512c21b9"])
def test_a_commit_that_is_no_export_with_a_version_has_none(prefix):
    commit = sha_of(prefix)  # Version 3.29.3.3, a merge, Export Internal Server Error, a build fix
    entry = next(entry for entry in recorded_commits() if entry["sha"] == commit)

    assert export_of_commit(commit, FakeGitHub(commits={commit: entry})) is None


def test_an_unknown_commit_is_a_fetch_error_naming_the_url():
    with pytest.raises(FetchError, match="422") as caught:
        export_of_commit("f" * 40, FakeGitHub())

    assert f"{COMMITS_URL}/{'f' * 40}" in str(caught.value)


# --- the command line ------------------------------------------------------------------------------

EXPORT_COMMIT = sha_of("ee2084de")
OTHER_EXPORT_COMMIT = sha_of("926da1c0")


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.delenv("CRAFTING_CONFIG", raising=False)
    monkeypatch.setenv("CRAFTING_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(data_main, "find_repo_root", lambda: None)
    return tmp_path / "cache"


def cli(capsys, argv, pin, files, github):
    code = main(argv, pin=pin, open_url=routed(files, github))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_diff_with_a_version_name_prints_which_export_was_taken_before_the_diff(cache, capsys):
    pin, files = files_world({EXPORT_COMMIT: raw_to_bytes(seeded_raw())})
    github = FakeGitHub()

    code, out, err = cli(capsys, ["diff", "pinned", "3.29.3.3"], pin, files, github)

    assert code == 0
    assert err == ""
    lines = out.split("\n")
    assert lines[0] == f"Export of 3.29.3.3: commit {EXPORT_COMMIT}, committed 2026-10-19T04:13:16Z"
    assert lines[1] == f"Patch diff: 9.9.9 ({pin.commit[:8]}) -> 3.29.3.3 ({EXPORT_COMMIT[:8]})"
    assert out.endswith(f"\n\nTo move the pin to this export: python -m crafting_system.data pin {EXPORT_COMMIT} 3.29.3.3\n")


def test_a_name_equal_to_the_active_pins_version_but_a_newer_export_is_compared(cache, capsys):
    pin, files = files_world({EXPORT_COMMIT: raw_to_bytes(seeded_raw())}, pin_version="3.29.3.3")
    github = FakeGitHub()

    code, out, _ = cli(capsys, ["diff", "pinned", "3.29.3.3"], pin, files, github)

    assert code == 0
    assert github.urls == [PAGE_1]
    assert out.splitlines()[1] == f"Patch diff: 3.29.3.3 ({pin.commit[:8]}) -> 3.29.3.3 ({EXPORT_COMMIT[:8]})"


def test_a_name_whose_export_is_the_pin_commit_counts_as_pinned(cache, capsys):
    pin, files = files_world({OTHER_EXPORT_COMMIT: raw_to_bytes(seeded_raw())}, pin_commit=EXPORT_COMMIT)
    github = FakeGitHub()

    code, out, _ = cli(capsys, ["diff", "3.29.3.3", "3.29.3.2"], pin, files, github)

    assert code == 0
    assert out.split("\n")[2] == f"Patch diff: 9.9.9 ({EXPORT_COMMIT[:8]}) -> 3.29.3.2 ({OTHER_EXPORT_COMMIT[:8]})"
    assert not (cache / "repoe-fork" / EXPORT_COMMIT).exists()  # the pin's own commit is never learned from a manifest


def test_two_names_of_the_same_version_are_a_usage_error_without_a_request(cache, capsys):
    pin, files = files_world({})
    github = FakeGitHub()

    code, out, err = cli(capsys, ["diff", "3.29.3.3", "3.29.3.3"], pin, files, github)

    assert code == 2
    assert out == ""
    assert "same version" in err
    assert github.urls == []


def test_a_name_and_the_commit_it_resolves_to_are_the_same_version(cache, capsys):
    pin, files = files_world({EXPORT_COMMIT: raw_to_bytes(seeded_raw())})

    code, _, err = cli(capsys, ["diff", EXPORT_COMMIT, "3.29.3.3"], pin, files, FakeGitHub())

    assert code == 2
    assert "same version" in err
    assert files.urls == []  # nothing was downloaded


def test_diff_with_a_version_that_has_no_export_exits_one_and_says_so(cache, capsys):
    pin, files = files_world({})

    code, out, err = cli(capsys, ["diff", "pinned", "3.29.9.9"], pin, files, FakeGitHub())

    assert code == 1
    assert out == ""
    assert err.startswith("error: no export of 3.29.9.9")
    assert files.urls == []


def test_diff_with_the_rate_limit_hit_exits_one_and_says_so(cache, capsys):
    pin, files = files_world({})

    code, out, err = cli(capsys, ["diff", "pinned", "3.29.3.3"], pin, files, http_error(403))

    assert code == 1
    assert out == ""
    assert "rate limit" in err


def test_pin_with_a_version_name_prints_which_export_was_taken(cache, tmp_path, capsys):
    pin, files = files_world({OTHER_EXPORT_COMMIT: raw_to_bytes(seeded_raw())})
    pin_file = tmp_path / "PIN.json"
    github = FakeGitHub()

    code = main(["pin", "3.29.3.2"], pin=pin, open_url=routed(files, github), pin_file=pin_file)

    out = capsys.readouterr().out
    assert code == 0
    assert out.split("\n")[0] == f"Export of 3.29.3.2: commit {OTHER_EXPORT_COMMIT}, committed 2026-08-27T11:23:45Z"
    assert json.loads(pin_file.read_text(encoding="utf-8"))["commit"] == OTHER_EXPORT_COMMIT
    assert json.loads(pin_file.read_text(encoding="utf-8"))["version"] == "3.29.3.2"
    assert github.urls == [PAGE_1]


def test_the_help_of_diff_and_pin_names_the_version_names(capsys):
    assert main(["diff", "--help"]) == 0
    assert "version name" in capsys.readouterr().out
    assert main(["pin", "--help"]) == 0
    assert "version name" in capsys.readouterr().out


# --- the default opener ---------------------------------------------------------------------


class _Seen:
    request = None


def _capture(monkeypatch):
    seen = _Seen()

    class Opener:
        def open(self, request, timeout):
            seen.request = request
            return io.BytesIO(b"[]")

    monkeypatch.setattr(resolve_module, "_OPENER", Opener())
    return seen


def test_the_github_opener_sends_the_token_from_the_environment(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "t-1")
    seen = _capture(monkeypatch)

    resolve_module.github_open_url("https://api.github.com/x")

    assert seen.request.get_header("Authorization") == "Bearer t-1"
    assert seen.request.get_header("User-agent")


def test_the_github_opener_sends_no_authorization_without_a_token(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    seen = _capture(monkeypatch)

    resolve_module.github_open_url("https://api.github.com/x")

    assert seen.request.get_header("Authorization") is None


def test_the_token_is_not_sent_to_another_host(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t-1")
    seen = _capture(monkeypatch)

    resolve_module.github_open_url("https://example.test/x")

    assert seen.request.get_header("Authorization") is None


@pytest.mark.parametrize(
    ("newurl", "kept"),
    [("https://api.github.com/repositories/1/commits", True), ("https://evil.example/commits", False)],
)
def test_a_redirect_keeps_the_token_only_on_the_github_api(newurl, kept):
    request = urllib.request.Request("https://api.github.com/x", headers={"Authorization": "Bearer t-1"})

    redirected = resolve_module._KeepTokenOnGitHub().redirect_request(request, None, 301, "Moved", {}, newurl)

    assert (redirected.get_header("Authorization") == "Bearer t-1") is kept
