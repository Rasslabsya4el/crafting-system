"""The lists an answer reads off the catalog are kept out of the recorded files (ticket #1277).

Three groups of "What this answer leaves out" are the catalog said again: the kinds the run's methods setting does not name
(`NOT_NAMED`), the kinds offered only when it names them (`OPT_IN`) and the methods the planner cannot use yet (`NOT_BUILT`). Every
new method moves one name between them on every answer, whatever the route, so a recorded page, text report, JSON policy or digest that
held them changed with every method (eleven files in each of eleven pull requests, 2026-11-15 to 2026-11-18), and two open method
pull requests always met in git on the one line of a page.

A recorded file holds `LIST` where the labels of such a limit stand: "Not offered: [a list ...] (methods the planner cannot use yet). The
plan is the cheapest among the methods the planner can use." What is left out, why, and what the answer still guarantees (OR-13) stay
recorded, and the page lint (`tests/oracle/page_lint.py`) still reads a line of the product's shape. The page the user reads is
untouched: only what a test writes and compares goes through here, and both sides the same way. The lists themselves are checked in
one place each:

* which kind stands in which list: the catalog's own record `tests/golden/reachability.md` (a row per kind, one line each) and
  `tests/test_classic_offers.py`; `tests/test_catalog_lists.py` holds a real answer's lists against the catalog;
* how a list is written (every label in the text and the JSON, the first three and a closed "details" on the page):
  `tests/test_cli_limits.py`.

A page of the fixture world plans with every method on, and the fixture price file holds two prices, so there a new method is one more
line of "Actions with no price", or one more label of a line. Those pages (`FIXTURE_WORLD`) record that group by its kinds of line only:
the labels and the items with no price are `LIST`, an action or a family that has no price of its own is one head, and a line said
twice is said once. `tests/test_catalog_lists.py` checks the group against the price file.

Everything else of a recorded answer is compared as before: the steps, the prices, the costs, and every other group of limits.

A recorded page is also written with one element to a line (`one_element_to_a_line`), so that two changes of one page merge in git.
"""

import re
from collections.abc import Collection, Iterable
from dataclasses import replace
from html import escape

from crafting_system.planner._limits import NOT_BUILT, NOT_NAMED, OPT_IN, TITLES, UNPRICED, Limit, limit_text, spent_kinds_named

__all__ = [
    "CATALOG_LISTS",
    "FIXTURE_WORLD",
    "LIST",
    "document_without",
    "limits_without",
    "one_element_to_a_line",
    "page_without",
    "text_without",
]

CATALOG_LISTS = (NOT_NAMED, OPT_IN, NOT_BUILT)
FIXTURE_WORLD = (*CATALOG_LISTS, UNPRICED)
LIST = "[a list that is not recorded here: every new method changes it]"

_DIV = re.compile(r"<div\b|</div>")
_DETAILS = re.compile(r"<details>.*?</details>")
# A line of the page as `planner._limits.limit_text` writes it: what, the labels, the cause in brackets when there is one, the guarantee.
_LINE = re.compile(r"^(?P<what>[^:]*?)(?:, [\d,]+ in all)?: (?P<labels>.*?)(?P<why> \((?:[^()]|\([^()]*\))*\))?\. (?P<guarantee>.*)$")
_NO_PRICE_FOR = re.compile(r"\(no price for [^()]*\)")
_OWN_PRICE = re.compile(r"^(This action has|These .+ have) no price$")  # `planner._limits.unpriced_limits`: one action, or a family by its name


def _end(html: str, start: int) -> int:
    """The end of the `div` whose content starts at `start`: the place of its closing tag."""
    depth = 1
    for tag in _DIV.finditer(html, start):
        depth += -1 if tag.group() == "</div>" else 1
        if depth == 0:
            return tag.start()
    raise AssertionError("a group of limits on the page is not closed")


def _line_without(line: str, kind: str) -> str:
    """One line of a group with `LIST` for its labels (and, in "Actions with no price", for the items that have none)."""
    found = _LINE.match(_DETAILS.sub("", line))
    assert found, f"a line of the group {TITLES[kind]!r} is not written as `limit_text` writes one: {line[:120]!r}; see tests/catalog_lists_support.py"
    what, why = found["what"], found["why"] or ""
    if kind == UNPRICED:
        what, why = _OWN_PRICE.sub("These actions have no price", what), _NO_PRICE_FOR.sub(f"(no price for {LIST})", why)
    return f"{what}: {LIST}{why}. {found['guarantee']}"


def page_without(html: str, kinds: Collection[str] = CATALOG_LISTS) -> str:
    """The page with each line of the groups `kinds` written without its labels (`LIST`), and a line that then reads as an earlier one of its group left out."""
    for kind in kinds:
        head = f'<div class="k">{escape(TITLES[kind])}</div><div class="v ml">'
        at = html.find(head)
        while at >= 0:
            start = at + len(head)
            end = _end(html, start)
            body = html[start:end]
            assert body.startswith("<div>") and body.endswith("</div>"), f"the group {TITLES[kind]!r} is not one `div` to a line; see tests/catalog_lists_support.py"
            lines = dict.fromkeys(_line_without(line, kind) for line in body[len("<div>") : -len("</div>")].split("</div><div>"))
            html = html[:start] + "".join(f"<div>{line}</div>" for line in lines) + html[end:]
            at = html.find(head, start)
    return html


_ELEMENT = re.compile(r"(?<=>)(?=<(?:div|section|h[1-6]|details|nav|table|tr|ul|ol|li)\b)")


def one_element_to_a_line(html: str) -> str:
    """The page with a line break before each block element that follows a tag.

    A page's body is one line of HTML, so two changes anywhere on a page were one changed line and could not be merged by git. A recorded
    page is written and compared like this, both sides the same way: the bytes between the breaks are the page's own.
    """
    return _ELEMENT.sub("\n", html)


def text_without(text: str, report) -> str:
    """The text report of `report` (`cli.render_text`) with `LIST` for the labels of each limit of `CATALOG_LISTS`."""
    for limit in spent_kinds_named(report.plan.limits, (use.name for use in report.prices_used)):  # as `cli._report.limit_lines` writes them
        if limit.kind in CATALOG_LISTS:
            line = f"  {limit_text(limit)}\n"
            assert line in text, f"the text report does not hold the limit {limit.kind!r} as `limit_lines` writes it; see tests/catalog_lists_support.py"
            text = text.replace(line, f"  {limit_text(replace(limit, labels=(LIST,)))}\n", 1)
    return text


def document_without(document: dict) -> dict:
    """The JSON policy with `LIST` for the labels and the count of each limit of `CATALOG_LISTS`; its words stay."""
    limits = [{**entry, "count": LIST, "labels": LIST} if entry["kind"] in CATALOG_LISTS else entry for entry in document["limits"]]
    return {**document, "limits": limits}


def limits_without(limits: Iterable[Limit]) -> list[Limit]:
    """The limits that are not of `CATALOG_LISTS`."""
    return [limit for limit in limits if limit.kind not in CATALOG_LISTS]
