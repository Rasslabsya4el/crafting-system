"""The readable before/after of golden files (ticket #436): `tests/golden_diff.py`, its use by `assert_golden`, and the script
`.github/scripts/golden_changes.py` that writes it for a pull request. Small hand-made pages; no game data.
"""

import html.parser
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import golden_diff
import pytest
import route_view_support
import targets_sockets_support

ROOT = Path(__file__).resolve().parents[1]
GOLDENS = sorted((ROOT / "tests" / "golden").iterdir())

spec = importlib.util.spec_from_file_location("golden_changes", ROOT / ".github" / "scripts" / "golden_changes.py")
changes = importlib.util.module_from_spec(spec)
sys.modules["golden_changes"] = changes
spec.loader.exec_module(changes)

PAGE = """<!doctype html>
<html lang="en"><head><title>R1</title>
<style>
body{margin:0}
@media (max-width:640px){.rw{display:block}}
</style></head>
<body><main><h1>Boots</h1>
<section id="policy"><div class="rw"><div class="cd"><h3>Goal</h3>
<div class="s w">30% increased   Movement Speed<span class="n"> &middot; T2</span></div>
<div class="s a">any mod or empty</div></div></div></section>
<!-- end -->
</main></body></html>
"""


# --- HTML --------------------------------------------------------------------------------------------------------------------------


def test_a_page_reads_as_its_structure_and_visible_text_one_block_per_line():
    assert golden_diff.html_lines(PAGE) == [
        "<!doctype html>",
        '<html lang="en">',
        "  <head>",
        "    <title> R1",
        "    <style>",
        "      body{margin:0}",
        "      @media (max-width:640px){",
        "        .rw{display:block}",
        "      }",
        "  <body>",
        "    <main>",
        "      <h1> Boots",
        '      <section id="policy">',
        '        <div class="rw">',
        '          <div class="cd">',
        "            <h3> Goal",
        '            <div class="s w"> 30% increased Movement Speed<span class="n"> · T2</span>',
        '            <div class="s a"> any mod or empty',
        "      <!-- end -->",
    ]


def test_a_changed_word_is_one_changed_line_with_its_neighbours_for_context():
    after = PAGE.replace("any mod or empty", "any mod")

    diff = golden_diff.readable_diff(PAGE, after, "html")

    changed = [line for line in diff.splitlines() if line[:1] in "+-" and line[:3] not in ("---", "+++")]
    assert changed == ['-            <div class="s a"> any mod or empty', '+            <div class="s a"> any mod']
    assert '            <div class="s w"> 30% increased Movement Speed<span class="n"> · T2</span>' in diff  # the line before, as context
    assert diff.endswith("(1 readable lines removed, 1 added)")


def test_a_changed_class_shows_on_the_start_tag_line():
    diff = golden_diff.readable_diff(PAGE, PAGE.replace('class="s w"', 'class="s m"'), "html")

    assert '-            <div class="s w"> 30% increased' in diff and '+            <div class="s m"> 30% increased' in diff


def test_a_changed_css_rule_is_one_line():
    diff = golden_diff.readable_diff(PAGE, PAGE.replace("body{margin:0}", "body{margin:4px}"), "html")

    assert "-      body{margin:0}" in diff and "+      body{margin:4px}" in diff


def test_whitespace_a_browser_ignores_is_not_a_readable_change_but_the_message_says_the_bytes_differ():
    spaced = PAGE.replace("<h1>Boots</h1>\n", "<h1>\n  Boots\n</h1>\n\n\n")

    assert golden_diff.html_lines(spaced) == golden_diff.html_lines(PAGE)
    diff = golden_diff.readable_diff(PAGE, spaced, "html")
    assert diff.startswith("The readable view is equal; the bytes differ (case, entity, encoding, key order or whitespace). First difference at character")


def test_a_link_address_is_shown_decoded_so_a_trade_query_reads_as_the_json_it_holds():
    page = '<div><a href="https://t.example/search?q=%7B%22min%22%3A30%7D" target="_blank">Search</a></div>'

    assert golden_diff.html_lines(page) == ["<div> <a href=\"https://t.example/search?q={\"min\":30}\" target=\"_blank\">Search</a>"]


def test_a_pre_block_keeps_its_lines():
    page = "<pre>first\n  second\nthird</pre><p>after</p>"

    assert golden_diff.html_lines(page) == ["<pre>", "  first", "    second", "  third", "<p> after"]


def test_a_single_line_page_of_fifteen_kilobytes_has_no_long_line_and_one_changed_row_moves_one_line():
    rows = "".join(f'<div class="s">row {i}: a mod with a value of {i * 7}, a tier of T{i % 5}, and some more words to make the row long</div>' for i in range(150))
    page = f'<main><section id="policy">{rows}</section></main>'
    assert len(page) > 15_000 and "\n" not in page

    lines = golden_diff.html_lines(page)
    assert len(lines) == 152 and max(map(len, lines)) <= golden_diff.WIDTH
    diff = golden_diff.readable_diff(page, page.replace("value of 700", "value of 701"), "html")
    assert [line for line in diff.splitlines() if line[:1] in "+-" and line[:3] not in ("---", "+++")] == [
        '-    <div class="s"> row 100: a mod with a value of 700, a tier of T0, and some more words to make the row long',
        '+    <div class="s"> row 100: a mod with a value of 701, a tier of T0, and some more words to make the row long',
    ]


# --- JSON, text, long lines --------------------------------------------------------------------------------------------------------


def test_json_is_pretty_printed_with_sorted_keys_whatever_its_layout():
    flat = '{"b": [1, 2], "a": {"y": 1, "x": 2}}'
    spread = '{\n "a": {"x": 2,\n "y": 1},\n "b": [1,\n 2]}'

    expected = ["{", '  "a": {', '    "x": 2,', '    "y": 1', "  },", '  "b": [', "    1,", "    2", "  ]", "}"]
    assert golden_diff.json_lines(flat) == golden_diff.json_lines(spread) == expected


def test_a_json_change_shows_the_path_of_keys_around_the_changed_value():
    before = '{"routes": {"R1": {"mean": 5.5, "states": 10}, "R2": {"mean": 7.0, "states": 12}}}'
    after = before.replace("7.0", "7.5")

    diff = golden_diff.readable_diff(before, after, "json")

    assert '-      "mean": 7.0,' in diff and '+      "mean": 7.5,' in diff and '"R2": {' in diff


def test_text_is_compared_line_by_line():
    diff = golden_diff.readable_diff("one\ntwo\nthree\n", "one\n2\nthree\n", "text")

    assert [line for line in diff.splitlines() if line[:1] in "+-" and line[:3] not in ("---", "+++")] == ["-two", "+2"]


def test_a_long_line_is_cut_after_its_commas_and_loses_nothing():
    fields = [f"field{i}=Value(low={i}, high={i + 1})" for i in range(60)]
    line = "Report(" + ", ".join(fields) + ")"
    assert len(line) > 1500

    pieces = golden_diff.wrap(line)

    assert max(map(len, pieces)) <= golden_diff.WIDTH
    assert "".join(piece.removeprefix("  ~ ") for piece in pieces).replace(" ", "") == line.replace(" ", "")


def test_a_word_longer_than_the_width_is_cut_hard():
    pieces = golden_diff.wrap("x" * 1000)

    assert max(map(len, pieces)) <= golden_diff.WIDTH and "".join(piece.removeprefix("  ~ ") for piece in pieces) == "x" * 1000


def test_a_diff_is_cut_at_the_limit_and_says_how_much_was_left_out():
    before = "\n".join(f"line {i}" for i in range(100))
    after = "\n".join(f"LINE {i}" for i in range(100))

    diff = golden_diff.readable_diff(before, after, "text", limit=10)

    assert len(diff.splitlines()) == 12 and "more diff lines left out" in diff and diff.endswith("(100 readable lines removed, 100 added)")


def test_equal_texts_have_no_diff():
    assert golden_diff.readable_diff(PAGE, PAGE, "html") == ""


def test_kind_follows_the_extension():
    assert [golden_diff.kind_of(name) for name in ("a.html", "b.json", "c.txt", "d.md")] == ["html", "json", "text", "text"]


# --- the test side ---------------------------------------------------------------------------------------------------------------------


def test_check_returns_on_equal_and_raises_with_the_title_and_the_diff_on_a_difference():
    golden_diff.check("same", "same", "text", "t")
    with pytest.raises(AssertionError) as caught:
        golden_diff.check("a\nb\n", "a\nc\n", "text", "the page moved")

    message = str(caught.value)
    assert message.startswith("the page moved\n") and "-b" in message and "+c" in message


def test_check_objects_compares_values_and_shows_sorted_key_json():
    golden_diff.check_objects({"a": [1, 2]}, {"a": [1, 2]}, "t")
    with pytest.raises(AssertionError) as caught:
        golden_diff.check_objects({"b": 1, "a": 1}, {"a": 2, "b": 1}, "values moved")

    assert 'values moved\n' in str(caught.value) and '-  "a": 1,' in str(caught.value) and '+  "a": 2,' in str(caught.value)


def test_check_objects_with_a_tolerance_accepts_floats_within_it_and_keeps_ints_and_strings_exact():
    golden_diff.check_objects({"mean": 69257.53649796372, "states": 177242}, {"mean": 69257.53649796372 * (1 + 5e-10), "states": 177242}, "t", rel=1e-9)
    with pytest.raises(AssertionError) as caught:
        golden_diff.check_objects({"mean": 5784.488692221155}, {"mean": 5784.488692221155 * (1 + 1e-6)}, "mean moved", rel=1e-9)
    with pytest.raises(AssertionError):
        golden_diff.check_objects({"states": 10}, {"states": 11}, "states moved", rel=1e-9)

    assert str(caught.value).startswith("mean moved\n") and '-  "mean": 5784.488692221155' in str(caught.value)


def test_a_golden_changed_only_in_line_endings_says_so_and_shows_no_empty_diff_block(repo):
    run_git(repo, "checkout", "-q", "branch")
    (repo / "tests" / "golden" / "same.json").write_bytes(b'{"k": 1}\r\n')
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "crlf")

    text = changes.report("main", "branch", "tests/golden", 150, root=repo)
    section = text.split("### `tests/golden/same.json`: changed", 1)[1].split("### ", 1)[0]

    assert "line endings" in section and "the readable view is equal" in section
    assert "````diff" not in section


def test_the_size_limit_of_the_summary_counts_utf8_bytes_not_characters(repo, monkeypatch):
    (repo / "tests" / "golden" / "zz.txt").write_text("ё" * 400 + "\n", encoding="utf-8", newline="\n")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "cyrillic")
    whole = changes.report("main", "branch", "tests/golden", 150, root=repo)
    assert len(whole) < len(whole.encode("utf-8")) and "(left out" not in whole

    monkeypatch.setattr(changes, "SUMMARY_LIMIT", len(whole.encode("utf-8")) - 1)
    cut = changes.report("main", "branch", "tests/golden", 150, root=repo)

    assert "(left out: the report would pass the size" in cut and "### `tests/golden/zz.txt`: added" in cut


def test_assert_golden_fails_with_the_readable_diff_not_two_page_strings(tmp_path, monkeypatch):
    monkeypatch.setattr(route_view_support, "GOLDEN", tmp_path)
    monkeypatch.delenv("UPDATE_GOLDEN", raising=False)
    (tmp_path / "toy.html").write_text(PAGE, encoding="utf-8", newline="\n")

    route_view_support.assert_golden("toy", PAGE)
    with pytest.raises(AssertionError) as caught:
        route_view_support.assert_golden("toy", PAGE.replace("Boots", "Shoes"))

    message = str(caught.value)
    assert message.startswith("toy differs from its golden file tests/golden/toy.html\n")
    assert "-      <h1> Boots" in message and "+      <h1> Shoes" in message
    assert max(map(len, message.splitlines())) <= golden_diff.WIDTH + 20


def test_assert_golden_still_writes_the_file_under_update_golden(tmp_path, monkeypatch):
    monkeypatch.setattr(route_view_support, "GOLDEN", tmp_path)
    monkeypatch.setenv("UPDATE_GOLDEN", "1")

    route_view_support.assert_golden("new", "line one\n", "txt")

    assert (tmp_path / "new.txt").read_bytes() == b"line one\n"


def test_assert_golden_json_fails_with_a_json_diff(tmp_path, monkeypatch):
    monkeypatch.setattr(targets_sockets_support, "GOLDEN", tmp_path)
    monkeypatch.delenv("UPDATE_GOLDEN", raising=False)
    (tmp_path / "toy.json").write_text('{"b": 2, "a": 1}\n', encoding="utf-8", newline="\n")

    with pytest.raises(AssertionError) as caught:
        targets_sockets_support.assert_golden_json("toy", '{"b": 3, "a": 1}\n')

    assert '-  "b": 2' in str(caught.value) and '+  "b": 3' in str(caught.value)


# --- the committed golden files ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", GOLDENS, ids=lambda path: path.name)
def test_every_committed_golden_file_reads_in_short_lines(path):
    lines = golden_diff.readable_lines(path.read_text(encoding="utf-8"), golden_diff.kind_of(path))

    assert lines and max(map(len, lines)) <= golden_diff.WIDTH


class _Words(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.words: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        self.skip += tag in ("style", "script")

    def handle_endtag(self, tag):
        self.skip -= tag in ("style", "script")

    def handle_data(self, data):
        if not self.skip:
            self.words.extend(data.split())


@pytest.mark.parametrize("path", [p for p in GOLDENS if p.suffix == ".html"], ids=lambda path: path.name)
def test_the_readable_view_of_a_page_keeps_every_visible_word(path):
    text = path.read_text(encoding="utf-8")
    reader = _Words()
    reader.feed(text)
    shown = re.sub(r"<[^>]*>", " ", "\n".join(golden_diff.html_lines(re.sub(r"<style.*?</style>", "", text, flags=re.S))))

    assert sorted(shown.replace(" ~ ", " ").split()) == sorted(reader.words)


# --- the script for a pull request -----------------------------------------------------------------------------------------------------


def run_git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=env)


@pytest.fixture
def repo(tmp_path):
    """A repository whose `main` holds three golden files and whose branch changes one, adds one and deletes one."""
    golden = tmp_path / "tests" / "golden"
    golden.mkdir(parents=True)
    run_git(tmp_path, "init", "-q", "-b", "main")
    run_git(tmp_path, "config", "core.autocrlf", "false")  # a line ending is kept as written, whatever the machine's git says
    (golden / "page.html").write_text(PAGE, encoding="utf-8", newline="\n")
    (golden / "gone.txt").write_text("a\nb\n", encoding="utf-8", newline="\n")
    (golden / "same.json").write_text('{"k": 1}\n', encoding="utf-8", newline="\n")
    run_git(tmp_path, "add", "-A")
    run_git(tmp_path, "commit", "-q", "-m", "main")
    run_git(tmp_path, "checkout", "-q", "-b", "branch")
    (golden / "page.html").write_text(PAGE.replace("any mod or empty", "any mod"), encoding="utf-8", newline="\n")
    (golden / "new.json").write_text('{"z": [1, 2]}\n', encoding="utf-8", newline="\n")
    (golden / "gone.txt").unlink()
    run_git(tmp_path, "add", "-A")
    run_git(tmp_path, "commit", "-q", "-m", "branch")
    return tmp_path


def test_the_script_writes_the_readable_before_and_after_of_each_changed_golden_file(repo):
    text = changes.report("main", "branch", "tests/golden", 150, root=repo)

    assert text.startswith("## Golden files changed against main\n\n3 file(s) under `tests/golden` changed.")
    assert "same.json" not in text
    assert "### `tests/golden/page.html`: changed" in text
    assert '-            <div class="s a"> any mod or empty' in text and '+            <div class="s a"> any mod' in text
    assert "### `tests/golden/new.json`: added" in text and '+  "z": [' in text
    assert "### `tests/golden/gone.txt`: deleted" in text and "-a\n-b\n" in text


def test_the_script_says_so_when_no_golden_file_changed(repo):
    text = changes.report("main", "main", "tests/golden", 150, root=repo)

    assert text == "## Golden files changed against main\n\nNo file under `tests/golden` changed.\n"


def test_the_script_compares_with_the_merge_base_not_with_the_tip_of_main(repo):
    run_git(repo, "checkout", "-q", "main")
    (repo / "tests" / "golden" / "other.txt").write_text("later\n", encoding="utf-8", newline="\n")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "main moved on")

    text = changes.report("main", "branch", "tests/golden", 150, root=repo)

    assert "other.txt" not in text and "page.html" in text


def test_the_script_cuts_a_long_diff_and_says_so(repo):
    golden = repo / "tests" / "golden"
    (golden / "same.json").write_text("{" + ", ".join(f'"k{i}": {i}' for i in range(300)) + "}\n", encoding="utf-8", newline="\n")
    run_git(repo, "commit", "-q", "-am", "long")

    text = changes.report("main", "branch", "tests/golden", 20, root=repo)

    assert "more diff lines left out" in text


def test_the_script_main_writes_the_report_to_out_and_to_the_job_summary(repo, tmp_path_factory, monkeypatch, capsys):
    out = tmp_path_factory.mktemp("out")
    summary = out / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(changes, "ROOT", repo)
    monkeypatch.setattr(changes, "report", lambda base, head, directory, lines, root=None: f"report {base} {head} {directory} {lines}\n")

    assert changes.main(["--base", "main", "--head", "branch", "--out", str(out / "r.md"), "--summary"]) == 0

    assert (out / "r.md").read_text(encoding="utf-8") == "report main branch tests/golden 150\n" == summary.read_text(encoding="utf-8")
    assert capsys.readouterr().out == "report main branch tests/golden 150\n"
