"""A readable before/after for golden files (ticket #436, audit #396 class 6: TESTS-5, TESTS-13, PRES-10/11).

A golden page used to fail as "differs from its golden file": the two byte strings, with single lines of up to 15 KB, were
all pytest could show. This module reduces each kind of golden file to lines a person reads, and diffs those:

* HTML: the visible text and the structure, one block per line. Every block element (`div`, `li`, `tr`, `h2`, ...) opens a new
  line with its start tag, indented by its depth; inline elements (`span`, `a`, `b`, ...) stay inside the line of their block;
  `<style>` is one CSS rule per line. Whitespace is collapsed the way a browser collapses it.
* JSON: pretty-printed with sorted keys, indent 2.
* Text and Markdown: line by line.

A line longer than `WIDTH` is cut after its commas (so one changed field moves one line, not the rest of a paragraph), and a
piece that is still too long is cut at a space. No line of the output is longer than `WIDTH` plus a few characters.

The three entry points:

* `readable_lines(text, kind)`: the reduced lines of one file;
* `readable_diff(before, after, kind, ...)`: the unified diff of the two reduced files, `""` when the bytes are equal;
* `check(expected, actual, kind, title)` and `check_objects(expected, actual, title)`: the test side. They raise an
  `AssertionError` whose message is the title and the readable diff, and return when the two are equal. The pass or fail
  meaning is the one the caller gave: `check` compares the bytes, `check_objects` compares parsed values with `==`.

Standard library only: `.github/scripts/golden_changes.py` imports it to write the same diff for a pull request.
"""

import difflib
import html.parser
import json
import re
import urllib.parse
from pathlib import Path

WIDTH = 160  # the longest line of a readable view (a few characters more for the indent of a cut line)
TEST_DIFF_LINES = 120  # the longest diff a failing test prints

# Elements that start a line of their own. Everything else is inline: it stays in the line of the block that holds it.
BLOCK = frozenset(
    "html head body title meta link main nav header footer section article aside div p h1 h2 h3 h4 h5 h6 ul ol li dl dt dd "
    "table caption thead tbody tfoot tr td th details summary pre blockquote form fieldset figure figcaption hr br".split()
)
VOID = frozenset("meta link br hr img input col area base wbr".split())
RAW = frozenset({"style", "script"})  # their content is code, not text; shown as its own lines


def kind_of(path: str | Path) -> str:
    """`html`, `json` or `text` from the extension of a golden file."""
    suffix = Path(path).suffix.lower()
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix == ".json":
        return "json"
    return "text"


# --- cutting long lines ------------------------------------------------------------------------------------------------------------


def wrap(line: str, width: int = WIDTH) -> list[str]:
    """`line` as one or more lines of at most about `width` characters: cut after commas and semicolons, then at spaces, then anywhere."""
    if len(line) <= width:
        return [line]
    indent = line[: len(line) - len(line.lstrip())]
    mark = indent + "  ~ "
    room = width - len(mark)
    pieces: list[str] = []
    for chunk in re.split(r"(?<=[,;])(?!\d)", line.strip()):  # a comma or semicolon stays on the piece before the cut; 12,000 is not cut
        if pieces and len(pieces[-1]) + len(chunk) <= room:
            pieces[-1] += chunk
        else:
            pieces.extend(_cut(chunk.strip(), room))
    pieces = [piece.strip() for piece in pieces]
    return [(indent if index == 0 else mark) + piece for index, piece in enumerate(pieces)]


def _cut(chunk: str, width: int) -> list[str]:
    if len(chunk) <= width:
        return [chunk]
    out: list[str] = []
    while len(chunk) > width:
        cut = chunk.rfind(" ", 0, width)
        cut = cut + 1 if cut > width // 2 else width  # a space far enough in, else a hard cut
        out.append(chunk[:cut].rstrip())
        chunk = chunk[cut:]
    if chunk:
        out.append(chunk)
    return out


# --- HTML --------------------------------------------------------------------------------------------------------------------------


def _start_tag(tag: str, attrs: list[tuple[str, str | None]]) -> str:
    """The start tag; a link's address is shown percent-decoded, so a trade-site query reads as the JSON it holds."""
    shown = "".join(
        f' {name}="{urllib.parse.unquote(value) if name == "href" else value}"' if value is not None else f" {name}"
        for name, value in attrs
    )
    return f"<{tag}{shown}>"


def _css_lines(css: str) -> list[str]:
    """One rule per line: break after a `}` that closes a rule (depth 0 or 1) and after the `{` of an at-rule such as `@media`."""
    css = re.sub(r"\s+", " ", css).strip()
    out: list[str] = []
    depth = 0
    current: list[str] = []
    for char in css:
        current.append(char)
        if char == "{":
            depth += 1
            if "".join(current).lstrip().startswith("@") and depth == 1:
                out.append("".join(current).strip())
                current = []
        elif char == "}":
            depth -= 1
            if depth <= 1:
                out.append(("  " if depth == 1 else "") + "".join(current).strip())  # a rule inside an @media block is indented
                current = []
    if "".join(current).strip():
        out.append("".join(current).strip())
    return out


class _Reader(html.parser.HTMLParser):
    """Collects the readable lines of a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.stack: list[str] = []  # the open block elements
        self.buffer: list[str] = []  # the inline content of the line being built
        self.raw: str | None = None  # inside <style> or <script>
        self.raw_text: list[str] = []
        self.in_pre = 0
        self.open_line = -1  # index of the line holding the start tag of the innermost open block, while nothing follows it

    def _indent(self) -> str:
        return "  " * len(self.stack)

    def _flush(self) -> None:
        text = "".join(self.buffer)
        self.buffer = []
        text = re.sub(r"[ \t\r\n\f]+", " ", text).strip()
        if not text:
            return
        if self.open_line == len(self.lines) - 1 and self.stack:  # the text of a block sits on its start tag's line
            self.lines[-1] += " " + text
        else:
            self.lines.append(self._indent() + text)

    def handle_starttag(self, tag, attrs):
        if tag in RAW:
            self._flush()
            self.lines.append(self._indent() + _start_tag(tag, attrs))
            self.raw = tag
            self.raw_text = []
            return
        if tag in BLOCK:
            self._flush()
            self.lines.append(self._indent() + _start_tag(tag, attrs))
            if tag not in VOID:
                self.stack.append(tag)
                self.open_line = len(self.lines) - 1
                if tag == "pre":
                    self.in_pre += 1
        else:
            self.buffer.append(_start_tag(tag, attrs))

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK or tag in RAW:
            self._flush()
            self.lines.append(self._indent() + _start_tag(tag, attrs))
        else:
            self.buffer.append(_start_tag(tag, attrs))

    def handle_endtag(self, tag):
        if self.raw == tag:
            body = "".join(self.raw_text)
            indent = self._indent() + "  "
            if tag == "style":
                self.lines.extend(indent + rule for rule in _css_lines(body))
            else:
                self.lines.extend(indent + row.strip() for row in body.splitlines() if row.strip())
            self.raw = None
            return
        if tag in BLOCK and tag not in VOID and tag in self.stack:
            self._flush()
            while self.stack:
                closed = self.stack.pop()
                if closed == "pre":
                    self.in_pre -= 1
                if closed == tag:
                    break
        elif tag not in BLOCK and tag not in VOID:
            self.buffer.append(f"</{tag}>")

    def handle_data(self, data):
        if self.raw:
            self.raw_text.append(data)
        elif self.in_pre:
            rows = data.split("\n")
            for index, row in enumerate(rows):
                self.buffer.append(row)
                if index < len(rows) - 1:
                    self._flush_pre()
        else:
            self.buffer.append(data)

    def _flush_pre(self) -> None:
        text = "".join(self.buffer).rstrip()
        self.buffer = []
        if text:
            self.lines.append(self._indent() + text)

    def handle_comment(self, data):
        self._flush()
        self.lines.append(self._indent() + "<!-- " + re.sub(r"\s+", " ", data).strip() + " -->")

    def handle_decl(self, decl):
        self._flush()
        self.lines.append(f"<!{decl}>")

    def close(self) -> None:
        super().close()
        self._flush()


def html_lines(text: str) -> list[str]:
    """The readable lines of a page: its structure and visible text, one block per line (see the module doc)."""
    reader = _Reader()
    reader.feed(text)
    reader.close()
    return [piece for line in reader.lines for piece in wrap(line)]


# --- JSON and text -----------------------------------------------------------------------------------------------------------------


def json_text(value: object) -> str:
    """`value` pretty-printed with sorted keys (the form every JSON golden is compared in)."""
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=repr)


def json_lines(text: str) -> list[str]:
    """The pretty-printed, key-sorted lines of a JSON document; a text that is not JSON is shown as text."""
    try:
        value = json.loads(text)
    except ValueError:
        return text_lines(text)
    return [piece for line in json_text(value).splitlines() for piece in wrap(line)]


def text_lines(text: str) -> list[str]:
    return [piece for line in text.splitlines() for piece in wrap(line.rstrip())]


def readable_lines(text: str, kind: str) -> list[str]:
    """The lines a person reads for a golden file of `kind` (`html`, `json` or `text`)."""
    if kind == "html":
        return html_lines(text)
    if kind == "json":
        return json_lines(text)
    return text_lines(text)


# --- the diff ----------------------------------------------------------------------------------------------------------------------


def readable_diff(
    before: str,
    after: str,
    kind: str,
    before_label: str = "golden (before)",
    after_label: str = "now (after)",
    context: int = 3,
    limit: int | None = None,
) -> str:
    """The unified diff of the readable lines of `before` and `after`; `""` when the two texts are equal.

    When the bytes differ but the readable lines do not (whitespace a browser ignores, a line ending), it says so and shows the first
    place the bytes differ. `limit` cuts the diff to that many lines and says how many were left out.
    """
    if before == after:
        return ""
    old, new = readable_lines(before, kind), readable_lines(after, kind)
    body = list(difflib.unified_diff(old, new, before_label, after_label, lineterm="", n=context))
    if not body:
        return _bytes_differ(before, after, kind)
    removed = sum(1 for line in body if line.startswith("-") and not line.startswith("---"))
    added = sum(1 for line in body if line.startswith("+") and not line.startswith("+++"))
    if limit is not None and len(body) > limit:
        body = [*body[:limit], f"... {len(body) - limit} more diff lines left out"]
    return "\n".join([*body, f"({removed} readable lines removed, {added} added)"])


def _bytes_differ(before: str, after: str, kind: str) -> str:
    offset = next((i for i, (a, b) in enumerate(zip(before, after, strict=False)) if a != b), min(len(before), len(after)))
    return (
        f"The readable {kind} lines are equal; only whitespace or invisible bytes differ. First difference at character {offset}:\n"
        f"  before: {before[max(0, offset - 30) : offset + 30]!r}\n"
        f"  after:  {after[max(0, offset - 30) : offset + 30]!r}"
    )


# --- the test side -----------------------------------------------------------------------------------------------------------------


def check(expected: str, actual: str, kind: str, title: str, limit: int | None = TEST_DIFF_LINES) -> None:
    """Return when the two texts are byte-equal; else raise an `AssertionError` with `title` and the readable diff."""
    __tracebackhide__ = True  # pytest shows the message, not this frame with the two whole pages as its arguments
    if expected != actual:
        raise AssertionError(f"{title}\n{readable_diff(expected, actual, kind, limit=limit)}")


def check_objects(expected: object, actual: object, title: str, limit: int | None = TEST_DIFF_LINES) -> None:
    """Return when `expected == actual`; else raise an `AssertionError` with `title` and the diff of the two as sorted-key JSON."""
    __tracebackhide__ = True
    if expected != actual:
        raise AssertionError(f"{title}\n{readable_diff(json_text(expected), json_text(actual), 'json', limit=limit)}")
