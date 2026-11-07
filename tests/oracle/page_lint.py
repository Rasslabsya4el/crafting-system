"""The page lint: an independent judge of "does this route page keep the owner's page rules" (ticket #543, rebuild step 2d).

Why it exists. A page can break the owner's page rules and pass every test: R14's page had 87,272 steps and V01's 11 rows for 3
actions (audit #396, TESTS-20), because every test of the page compared the builder with itself. This module has no part of the
builder in it: it reads the rendered `.html` file with the standard library (`html.parser`), takes the text and the structure the
reader sees, and judges them against `docs/owner-rules.md`, group "The answer and the page" (OR-13 to OR-23 and OR-31). It imports
the standard library only, nothing from `crafting_system` (a test scans this file for that, as for the goal oracle).

What it reads on a page (the markup of the route page, learned from the page and not from its builder)
  * a `<section>` is one route; `div.rw` is a row; the first row is the goal card (`h3` "Route goal", the fields, and the part
    "What this answer leaves out") beside the target item card;
  * a later row is a step card (`div.cd#sN`, `h3` "N. Title", a grid `div.f` of `div.k` label and `div.v` / `div.vl` value, each
    value a list of `div` lines) beside the item card after the step (`div.nm` name, `span.pl` properties, `div.sd` caption
    "Prefixes" / "Suffixes", `div.s` slot whose class says the tone: `w` wanted, `m` a mod, `c` crafted, `a` "any mod or empty",
    `e` empty, `i` implicit; `span.n` its note, `span.b` its marks); a step with branches puts further item cards under captions.

The checks, one per rule that can be seen on a page. A check takes a `Page` and returns the list of faults it finds, each a
`Fault` that names the rule (`or_id`), the check and the place. `lint(page)` runs every check of `CHECKS`.

  OR-13  a cut says what it still guarantees      `check_cut_guarantee`
  OR-15  every mod line is in one format          `check_mod_format`, `check_bench_line_is_its_craft`, `check_group_printed_once`
  OR-16  every in-game step is shown              `check_no_hidden_step`
  OR-17  the bought item's other mods             `check_bought_item_not_empty`
  OR-18  one page step is one player step         `check_one_step_per_action`
  OR-19  the same route is never shown twice      `check_route_not_twice`
  OR-20  a known mechanic is never a range        `check_no_range`
  OR-23  an unknown is marked approximate         `check_approximate_marked`, `check_no_dropped_for_price`
  OR-31  a step shows the chance of each tier     `check_tier_lines`, `check_tier_step_has_tier_line`

No page check for the rest of the group, and why: OR-21 (build on today's snapshot) and OR-22 (a rule names its source) are about
the registry of mechanics, which a page does not print; OR-26 (a defect is traced to its root) and OR-29 (open points become
issues) are about how a change is made. This lint is the "independent check" OR-26 asks for, and a test holds OR-29 (every known
fault of a page is an issue named in a strict `xfail`).

One check keeps a decision of the main chat and not a rule of the file: `check_no_internal_names` (#481 plain words, decided in #553):
no internal id on a page (a dotted claim id, a snake_case token, a `Metadata/` path, a ticket number, a base id in brackets). No rule of
`docs/owner-rules.md` says it, so the file is not touched; its faults carry `#481 and #553` where the others carry an `OR-n`.

The percentages a page prints are rounded (two significant digits, "≈0.93%"); a sum of them is judged within the rounding.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

# --- the page as a tree --------------------------------------------------------------------------------------

_VOID = {"meta", "link", "br", "hr", "img", "input"}


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    children: list[Node | str] = field(default_factory=list)

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def elements(self) -> Iterator[Node]:
        return (child for child in self.children if isinstance(child, Node))

    def walk(self) -> Iterator[Node]:
        yield self
        for child in self.elements():
            yield from child.walk()

    def text(self, skip: tuple[str, ...] = ()) -> str:
        """All the text under the node, a tag in `skip` left out."""
        parts = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag not in skip:
                parts.append(child.text(skip))
        return "".join(parts)


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root", {})
        self.stack = [self.root]
        self.hidden = 0  # inside <style> or <script>: not page text

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag in ("style", "script"):
            self.hidden += 1
        if tag not in _VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.hidden -= 1
        for depth in range(len(self.stack) - 1, 0, -1):  # close the nearest open element of that name
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                return

    def handle_data(self, data):
        if not self.hidden:
            self.stack[-1].children.append(data)


def parse_tree(html: str) -> Node:
    builder = _Builder()
    builder.feed(html)
    builder.close()
    return builder.root


# --- the page as the reader sees it --------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    text: str  # the text of the line, a closed "details" list not in it
    more: str = ""  # the text of its "details" (the entries a line does not name)
    href: str = ""  # the first link in the line


@dataclass(frozen=True)
class Slot:
    tone: str  # wanted, mod, crafted, any, empty, implicit
    text: str  # the mod text
    note: str  # the note after it (" · T2"), stripped of the dot
    marks: tuple[str, ...]


@dataclass(frozen=True)
class Item:
    name: str
    properties: tuple[str, ...]
    sides: tuple[tuple[str, tuple[Slot, ...]], ...]  # (caption, slots): "Implicit", "Prefixes", "Suffixes", ...
    caption: str = ""  # the caption above it when it is a branch

    @property
    def slots(self) -> list[Slot]:
        return [slot for _, slots in self.sides for slot in slots]

    @property
    def rarity(self) -> str:
        return next((p for p in self.properties if p in ("Normal", "Magic", "Rare", "Unique")), "")


@dataclass(frozen=True)
class Step:
    number: int
    title: str
    anchor: str
    fields: tuple[tuple[str, tuple[Line, ...]], ...]
    after: Item | None
    branches: tuple[Item, ...] = ()

    def lines(self, label: str) -> list[Line]:
        return [line for name, lines in self.fields if name == label for line in lines]

    def has(self, label: str) -> bool:
        return any(name == label for name, _ in self.fields)


@dataclass(frozen=True)
class Route:
    anchor: str
    title: str
    goal: tuple[tuple[str, tuple[Line, ...]], ...]
    leaves_out: tuple[tuple[str, tuple[Line, ...]], ...]
    has_leaves_out_heading: bool
    target: Item | None
    steps: tuple[Step, ...]

    def goal_lines(self, label: str) -> list[Line]:
        return [line for name, lines in self.goal if name == label for line in lines]


@dataclass(frozen=True)
class Page:
    title: str
    routes: tuple[Route, ...]
    text: str  # every text of the body, for the checks that read the page as a whole


LEAVES_OUT = "What this answer leaves out"
_TONES = {"w": "wanted", "m": "mod", "c": "crafted", "a": "any", "e": "empty", "i": "implicit"}


def _line(node: Node) -> Line:
    href = next((el.attrs.get("href", "") for el in node.walk() if el.tag == "a"), "")
    more = " ".join(el.text().strip() for el in node.walk() if el.tag == "details")
    return Line(_squash(node.text(skip=("details",))), _squash(more), href)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _fields(grid: Node) -> tuple[tuple[str, tuple[Line, ...]], ...]:
    """The label and the lines of each pair `div.k`, `div.v` / `div.vl` of a grid."""
    found: list[tuple[str, tuple[Line, ...]]] = []
    label = None
    for child in grid.elements():
        if "k" in child.classes:
            label = _squash(child.text())
        elif ("v" in child.classes or "vl" in child.classes) and label is not None:
            found.append((label, tuple(_line(div) for div in child.elements() if div.tag == "div")))
            label = None
    return tuple(found)


def _slot(node: Node) -> Slot:
    tone = next((_TONES[c] for c in node.classes if c in _TONES), "")
    notes = [el for el in node.elements() if el.tag == "span" and "n" in el.classes]
    marks = tuple(_squash(el.text()) for el in node.elements() if el.tag == "span" and "b" in el.classes)
    text = _squash(node.text(skip=("span",)))
    note = _squash(" ".join(el.text() for el in notes)).strip(" ·").strip()
    return Slot(tone, text, note, marks)


def _item(card: Node, caption: str = "") -> Item:
    name, props = "", []
    sides: list[tuple[str, list[Slot]]] = []
    for child in card.elements():
        if "nm" in child.classes:
            name = _squash(child.text())
        elif "pr" in child.classes:
            props = [_squash(el.text()) for el in child.elements() if el.tag == "span"]
        elif "sd" in child.classes:
            sides.append((_squash(child.text()), []))
        elif "s" in child.classes and sides:
            sides[-1][1].append(_slot(child))
    return Item(name, tuple(props), tuple((cap, tuple(slots)) for cap, slots in sides), caption)


def _is_item_card(node: Node) -> bool:
    return node.tag == "div" and "cd" in node.classes and any("nm" in el.classes for el in node.elements())


def _items_of(side: Node) -> tuple[Item | None, tuple[Item, ...]]:
    """The item card after a step, and the branch cards under it (a wrapper `div` holds them with captions)."""
    if _is_item_card(side):
        return _item(side), ()
    cards: list[Item] = []
    caption = ""
    for child in side.elements():
        if "sd" in child.classes and not _is_item_card(child):
            caption = _squash(child.text())
        elif _is_item_card(child):
            cards.append(_item(child, caption))
            caption = ""
    return (cards[0] if cards else None), tuple(cards[1:])


def _route(section: Node) -> Route:
    heading = next((_squash(el.text()) for el in section.elements() if el.tag == "h2"), "")
    goal: tuple = ()
    leaves: tuple = ()
    leaves_heading = False
    target = None
    steps: list[Step] = []
    for row in (el for el in section.elements() if "rw" in el.classes):
        cards = list(row.elements())
        if not cards:
            continue
        head = next((el for el in cards[0].elements() if el.tag == "h3"), None)
        title = _squash(head.text()) if head is not None else ""
        if title == "Route goal":
            grid = next((el for el in cards[0].elements() if "f" in el.classes), None)
            goal = _fields(grid) if grid is not None else ()
            for extra in cards[0].elements():
                if extra.tag == "div" and any(_squash(el.text()) == LEAVES_OUT for el in extra.elements() if "sd" in el.classes):
                    leaves_heading = True
                    leaves = _fields(extra)
            target = _items_of(cards[1])[0] if len(cards) > 1 else None
            continue
        match = re.match(r"(\d+)\.\s*(.*)", title)
        if not match:
            continue
        grid = next((el for el in cards[0].elements() if "f" in el.classes), None)
        after, branches = _items_of(cards[1]) if len(cards) > 1 else (None, ())
        steps.append(Step(int(match.group(1)), match.group(2), cards[0].attrs.get("id", ""), _fields(grid) if grid is not None else (), after, branches))
    return Route(section.attrs.get("id", ""), heading, goal, leaves, leaves_heading, target, tuple(steps))


def read_page(html: str) -> Page:
    """The page a reader sees, from the text of a rendered `.html` file.

    A page the lint cannot read (no route section, or no step in any of them: an empty file, a markup the lint does not know) raises
    `PageUnreadable`. A lint that read nothing would find no fault, and every check would pass on it."""
    root = parse_tree(html)
    title = next((_squash(el.text()) for el in root.walk() if el.tag == "title"), "")
    body = next((el for el in root.walk() if el.tag == "body"), root)
    routes = tuple(_route(section) for section in root.walk() if section.tag == "section")
    if not any(route.steps for route in routes):
        raise PageUnreadable(f"the lint read {len(routes)} route(s) and no step from a page of {len(html)} characters")
    return Page(title, routes, _squash(body.text()))


class PageUnreadable(ValueError):
    """The page has no route with a step, so the lint cannot judge it."""


def read_page_file(path: Path) -> Page:
    return read_page(Path(path).read_text(encoding="utf-8"))


# --- the faults ----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Fault:
    or_id: str  # the rule: "OR-18"
    check: str  # the check that found it
    where: str  # the place on the page: "step 3", "goal card"
    what: str  # what is wrong, in a line

    def __str__(self) -> str:
        return f"{self.or_id} {self.check} at {self.where}: {self.what}"


def _fault(or_id: str, check: Callable, where: str, what: str) -> Fault:
    return Fault(or_id, check.__name__, where, what)


# --- percentages ---------------------------------------------------------------------------------------------

_PERCENT = re.compile(r"(?P<approx>≈\s*)?(?P<sign>[<>]\s*)?(?P<num>\d[\d,]*(?:\.\d+)?)\s*%")


def percent_value(text: str) -> tuple[float, float] | None:
    """(value, half a unit of its last printed digit) of the first percentage in `text`, in percent; None when there is none."""
    match = _PERCENT.search(text)
    if not match:
        return None
    number = match.group("num").replace(",", "")
    decimals = len(number.split(".")[1]) if "." in number else 0
    value = float(number)
    slack = 0.5 * 10 ** (-decimals)
    if match.group("sign"):
        slack = max(slack, 0.1)  # "> 99.9%", "< 0.001%": a bound, not a value
    return value, slack


# --- OR-13: a cut says what it still guarantees --------------------------------------------------------------

_FIRST_SENTENCE = re.compile(r"^.*?[.)](?=\s+[A-Z]|$)")
GUARANTEE = re.compile(r"\b(the plan|the answer|the odds|the mean)\b", re.I)


def check_cut_guarantee(page: Page) -> list[Fault]:
    """OR-13: every line of the part "What this answer leaves out" says, after what is left out, what the answer still guarantees
    ("The plan is the cheapest among the kinds offered."), and a plan that is "Cheapest policy of the planner" has that part (R13's
    and R14's pages said "Cheapest policy of the planner" and named no kind left out)."""
    faults = []
    for route in page.routes:
        route_says = [line.text for line in route.goal_lines("Route")]
        if any("cheapest" in text.lower() for text in route_says) and not route.leaves_out and not route.has_leaves_out_heading:
            faults.append(_fault("OR-13", check_cut_guarantee, "goal card", f'"{route_says[0]}" with no part "{LEAVES_OUT}"'))
        for label, lines in route.leaves_out:
            for line in lines:
                rest = _FIRST_SENTENCE.sub("", line.text, count=1)
                if not GUARANTEE.search(rest):
                    faults.append(_fault("OR-13", check_cut_guarantee, f'"{LEAVES_OUT}", {label}', f"says what is left out and not what the answer still guarantees: {line.text[:100]}"))
    return faults


# --- OR-15: one format for a mod line ------------------------------------------------------------------------

_TIER_NOTE = re.compile(r"T\d+")
# The one shape of a note after a mod line: what the mod is (a tier, crafted, essence only, a grade of an implicit, a tier too
# low for the target), then how the target holds it ("at least 1 of 4", "in some" of the states the card shows).
_NOTE_OK = re.compile(r"^(?:T\d+|crafted|essence only|any tier|grade \d[^,]*|tier too low)?(?:,? ?(?:at least \d+ of \d+|in some))?$")
_BAD_INSIDE_TEXT = re.compile(r"(^|[\s(])T\d+\b|\bTier \d+\b|\[[A-Za-z]+\d*\]")


def _mod_slots(page: Page) -> Iterator[tuple[Route, str, Slot]]:
    for route in page.routes:
        cards = ([("target card", route.target)] if route.target else []) + [
            (f"step {step.number} ({step.title})", card) for step in route.steps for card in ([step.after] if step.after else []) + list(step.branches)
        ]
        for where, card in cards:
            for slot in card.slots:
                if slot.tone in ("wanted", "mod", "crafted", "implicit"):
                    yield route, where, slot


def check_mod_format(page: Page) -> list[Fault]:
    """OR-15: every mod line is `<mod text>` and, after a dot, one note (`T2`, `crafted`, ...); the tier is never inside the text,
    a mod text never carries a tier, a mark or an id of its own."""
    faults = []
    for route, where, slot in _mod_slots(page):
        if not slot.text:
            faults.append(_fault("OR-15", check_mod_format, where, "a mod line with no text"))
        elif _BAD_INSIDE_TEXT.search(slot.text):
            faults.append(_fault("OR-15", check_mod_format, where, f"the note is inside the mod text, not after it: {slot.text!r}"))
        if not _NOTE_OK.match(slot.note):
            faults.append(_fault("OR-15", check_mod_format, where, f"a note that is not `T<n>`, `crafted` or `tier too low`: {slot.note!r} on {slot.text!r}"))
        if (slot.tone == "crafted" or slot.note.startswith("crafted")) and _TIER_NOTE.search(slot.note):
            faults.append(_fault("OR-15", check_mod_format, where, f"a bench-crafted mod with a spawn tier: {slot.text!r} {slot.note}"))
    return faults


_BENCH = re.compile(r"^Bench ?craft:\s*(.+)$", re.I)
_NOT_A_MOD = {"remove crafted mods"}  # a bench option that takes the crafted mods off and adds none


def check_bench_line_is_its_craft(page: Page) -> list[Fault]:
    """OR-15: a mod never shows a different mod's text. After a step "Benchcraft: <text>" the crafted line of the item card says
    exactly `<text>` (R05 drew a bench step with the Life craft's id and another mod's range)."""
    faults = []
    for route in page.routes:
        for step in route.steps:
            match = _BENCH.match(step.title)
            if not match or step.after is None or match.group(1).strip().lower() in _NOT_A_MOD:
                continue
            crafted = [slot.text for slot in step.after.slots if slot.tone == "crafted"]
            if match.group(1).strip() not in crafted:
                faults.append(_fault("OR-15", check_bench_line_is_its_craft, f"step {step.number} ({step.title})", f"the crafted line is {crafted}, the craft is {match.group(1)!r}"))
    return faults


_GROUP = re.compile(r"\bat least (\d+) of (\d+)\b", re.I)


def check_group_printed_once(page: Page) -> list[Fault]:
    """OR-15: a group "at least k of n" is printed once on a card, as one line. The same "at least k of n" on several lines of
    one card is the group flattened into its members, each with a note (R05: "at least 1 of 4" on four lines)."""
    faults = []
    for route in page.routes:
        cards = ([("target card", route.target)] if route.target else []) + [(f"step {s.number} ({s.title})", s.after) for s in route.steps if s.after]
        for where, card in cards:
            groups: dict[tuple[str, str], int] = {}
            for slot in card.slots:
                for match in _GROUP.finditer(f"{slot.text} {slot.note}"):
                    groups[match.groups()] = groups.get(match.groups(), 0) + 1
            for (k, n), lines in groups.items():
                if lines > 1:
                    faults.append(_fault("OR-15", check_group_printed_once, where, f"'at least {k} of {n}' is printed on {lines} lines, not once"))
                if int(k) > int(n) or int(n) < 2:
                    faults.append(_fault("OR-15", check_group_printed_once, where, f"'at least {k} of {n}' is not a group"))
    return faults


# --- OR-16: every in-game step is shown ----------------------------------------------------------------------

# What the game needs of the item an action is used on (a fact of the game, and the one reason a card above can show that a step is
# missing). Only the actions that the game refuses on a Normal or a Magic item are listed.
_RARE_ONLY = re.compile(r"^(Chaos Orb|Exalted Orb|Veiled Chaos Orb|Veiled Exalted Orb|Eldritch (Chaos|Exalted)|Fossil|Harvest reforge|Orb of Fracturing|Fracturing Orb)", re.I)
_MAKES_RARE = re.compile(r"(Alchemy|Essence|Buy|recipe|Restart|Recombinator)", re.I)


def check_no_hidden_step(page: Page) -> list[Fault]:
    """OR-16: a step the player does in the game is on the page. The item before a step is the item after each step that links to it
    (a page is a graph: a restart goes back to step 2, a branch to a later row); a step with no link to it follows the row above.
    A page hides a step when (a) an action the game allows on a Rare item only follows Normal or Magic cards, (b) a Normal card is a
    Rare one after a step that does not make an item rare (R08 and R09: the Alchemy between the bought boots and the fossil is on no
    page), or (c) an essence is used on Rare cards and no note says that it reforges the rare with no Scouring Orb. Each is judged
    when every card the step can follow says so."""
    faults = []
    for route in page.routes:
        links: dict[str, list[Step]] = {}
        for step in route.steps:
            for _, lines in step.fields:
                for line in lines:
                    if line.href.startswith("#") and step not in links.setdefault(line.href[1:], []):
                        links[line.href[1:]].append(step)
        for index, step in enumerate(route.steps):
            where = f"step {step.number} ({step.title})"
            before = [source.after for source in links.get(step.anchor, []) if source is not step and source.after is not None]
            if not before and index > 0 and route.steps[index - 1].after is not None:
                before = [route.steps[index - 1].after]
            rarities = {card.rarity for card in before}
            if before and rarities <= {"Normal", "Magic"} and _RARE_ONLY.match(step.title):
                faults.append(_fault("OR-16", check_no_hidden_step, where, f"{step.title!r} needs a Rare item and the card above is {sorted(rarities)}: a step is missing between"))
            if before and rarities == {"Normal"} and step.after is not None and step.after.rarity == "Rare" and not _MAKES_RARE.search(step.title):
                faults.append(_fault("OR-16", check_no_hidden_step, where, f"a Normal item becomes Rare by {step.title!r}: the step that makes it rare is missing"))
            if re.search(r"Essence", step.title) and before and rarities == {"Rare"}:
                note = " ".join(line.text.lower() for line in step.lines("Note"))
                if "scouring" not in note and "reforge" not in note:
                    faults.append(_fault("OR-16", check_no_hidden_step, where, "an essence on a rare item with no note that it reforges the rare with no Scouring Orb"))
    return faults


# --- OR-17: the bought item's other mods ---------------------------------------------------------------------


def check_bought_item_not_empty(page: Page) -> list[Fault]:
    """OR-17: the item after a "Buy ..." step is never drawn empty: a slot that is not the wanted mod reads "any mod or empty",
    not "empty" (the R10 page the owner rejected drew the bought boots empty). A bought Normal base has no mods, so it is empty
    and nothing is hidden (R04 and R14 buy one)."""
    faults = []
    for route in page.routes:
        for step in route.steps:
            if re.match(r"Buy\b", step.title) and step.after is not None and step.after.rarity != "Normal":
                empties = [slot for slot in step.after.slots if slot.tone == "empty"]
                if empties:
                    faults.append(_fault("OR-17", check_bought_item_not_empty, f"step {step.number} ({step.title})", f"the bought item is drawn with {len(empties)} empty slot(s)"))
    return faults


# --- OR-18: one page step is one player step -----------------------------------------------------------------


def check_one_step_per_action(page: Page) -> list[Fault]:
    """OR-18: no two steps of a route share the action, the goal and the accepts. States that take the same action are one step;
    what splits them (a chance, a detail the search does not track) is no reason for a second step (V01: 11 rows for 3 actions)."""
    faults = []
    for route in page.routes:
        seen: dict[tuple, Step] = {}
        for step in route.steps:
            key = (step.title, tuple(line.text for line in step.lines("Goal")), tuple(line.text for line in step.lines("Accepts")))
            if key in seen:
                faults.append(_fault("OR-18", check_one_step_per_action, f"step {step.number} ({step.title})", f"same action, goal and accepts as step {seen[key].number}"))
            else:
                seen[key] = step
    return faults


# --- OR-19: the same route is never shown twice --------------------------------------------------------------


def _signature(step: Step) -> tuple:
    return (step.title, tuple(line.text for line in step.lines("Goal")), tuple(line.text for line in step.lines("Accepts")), tuple(line.text for line in step.lines("Chance per use")))


def check_route_not_twice(page: Page) -> list[Fault]:
    """OR-19: the guide's route is on the page once when it equals the plan's ("Same as the given route", one section) and only by
    the steps that differ otherwise. So no step of a later section is a step of the first (same action, goal, accepts and chance),
    and a page that says "Same as the given route" has one section."""
    faults = []
    said_same = any("same as the given route" in line.text.lower() for route in page.routes for line in route.goal_lines("Given route"))
    if said_same and len(page.routes) > 1:
        faults.append(_fault("OR-19", check_route_not_twice, "page", f"the page says the given route is the same and draws {len(page.routes)} sections"))
    if page.routes:
        first = {_signature(step) for step in page.routes[0].steps}
        for route in page.routes[1:]:
            twice = [step.number for step in route.steps if _signature(step) in first]
            if twice:
                faults.append(_fault("OR-19", check_route_not_twice, f"section {route.anchor}", f"steps {twice} are steps of the first section, drawn again"))
    return faults


# --- OR-20: a fully known mechanic is not a range ------------------------------------------------------------

_RANGE = re.compile(r"(?:between\s+)?≈?\s*\d[\d.,]*\s*%\s*(?:to|and|–|—|-)\s*≈?\s*\d[\d.,]*\s*%", re.I)


def check_no_range(page: Page) -> list[Fault]:
    """OR-20: a chance on the page is one number. Where nothing of the case is approximate (no "Approximate inputs" in the goal
    card) a chance line is never "x% to y%", "between x% and y%" or "x%-y%": the states that take the same action are one step
    with the mixture of their chances (V01 drew eight Regal rows between 0.88% and 0.95%)."""
    faults = []
    for route in page.routes:
        if route.goal_lines("Approximate inputs"):
            continue  # a case with an approximate input may print what it does not know
        for step in route.steps:
            for label in ("Chance per use", "On failure", "Accepts", "Goal"):
                for line in step.lines(label):
                    if _RANGE.search(line.text):
                        faults.append(_fault("OR-20", check_no_range, f"step {step.number} ({step.title})", f"{label}: a range, not a chance: {line.text[:100]}"))
    return faults


# --- OR-23: an unknown is estimated and marked approximate ---------------------------------------------------

_UNMARKED = re.compile(r"\b(APPROXIMATE|UNVERIFIED)\b")


def check_approximate_marked(page: Page) -> list[Fault]:
    """OR-23: what the planner estimates is listed in the goal card as "Approximate inputs", each line saying what is approximate and
    where the claim comes from ("statement Source: source."; a line may end with its "Spread: ..."); a claim that says APPROXIMATE or
    UNVERIFIED in its own words is not left in a step's text or on an item card (15 claims said so with no flag)."""
    faults = []
    for route in page.routes:
        for line in route.goal_lines("Approximate inputs"):
            statement, found, rest = line.text.partition(" Source: ")
            source = rest.partition(" Spread: ")[0].rstrip(".")
            if len(statement.split()) < 4:
                faults.append(_fault("OR-23", check_approximate_marked, "goal card", f"an approximate input that does not say what is approximate: {line.text[:100]}"))
            elif not found or len(source.split()) < 2:
                faults.append(_fault("OR-23", check_approximate_marked, "goal card", f"an approximate input that does not name its source: {line.text[:100]}"))
        for step in route.steps:
            for label, lines in step.fields:
                for line in lines:
                    found = _UNMARKED.search(line.text)
                    if found:
                        faults.append(_fault("OR-23", check_approximate_marked, f"step {step.number} ({step.title})", f"{label}: {found.group(0)} in the text of a step, not in the approximate inputs"))
    return faults


_NO_PRICE = re.compile(r"\(no price for ([^)]*)\)", re.I)


def check_no_dropped_for_price(page: Page) -> list[Fault]:
    """OR-23: an action with an unpriced resource is estimated, not dropped: the part "What this answer leaves out" has no
    "(no price for X)" line (audit PLANNING-4)."""
    faults = []
    for route in page.routes:
        for label, lines in route.leaves_out:
            for line in lines:
                for found in _NO_PRICE.finditer(line.text):
                    faults.append(_fault("OR-23", check_no_dropped_for_price, f'"{LEAVES_OUT}", {label}', f"an action is dropped for want of a price for {found.group(1)}"))
    return faults


# --- OR-31: a step that can add a wanted mod shows the chance of each tier -----------------------------------

_TIER_PART = re.compile(r"^T(?P<a>\d+)(?:\s+(?P<join>and|to)\s+T(?P<b>\d+))?\s+(?P<chance>[<>≈\s\d.,]*%)(?P<each>\s+each)?(?P<mark>\s+\(target\))?$")


def parse_tier_line(text: str) -> tuple[str, list[dict], dict | None, bool] | None:
    """`family: T1 ≈0.93% (target) · T2 to T10 ≈0.93% each · none ≈91%` -> (family, parts, none, every); None when it is not one.

    Each part is {"first", "last", "chance" (value, slack), "each", "target"}; none is {"chance"}; every says "every tier is the target"."""
    if ":" not in text:
        return None
    family, rest = text.split(":", 1)
    pieces = [piece.strip() for piece in rest.split("·")]
    every = False
    parts: list[dict] = []
    none = None
    for piece in pieces:
        if piece == "every tier is the target":
            every = True
        elif piece.startswith("none"):
            value = percent_value(piece)
            if value is None:
                return None
            none = {"chance": value}
        else:
            match = _TIER_PART.match(piece)
            value = percent_value(piece)
            if not match or value is None:
                return None
            parts.append({"first": int(match["a"]), "last": int(match["b"] or match["a"]), "join": match["join"], "chance": value, "each": bool(match["each"]), "target": bool(match["mark"])})
    return family.strip(), parts, none, every


def check_tier_lines(page: Page) -> list[Fault]:
    """OR-31: each line of "Tier chances" lists the tiers of one family in order and with no gap, joins runs of equal chances
    ("T2 to T10 1.4% each") and never a target tier with one that is not, marks the target tier "(target)" (or says "every tier is the
    target"), ends with "none", and its chances sum to 1 within the rounding of the page."""
    faults = []
    for route in page.routes:
        for step in route.steps:
            for line in step.lines("Tier chances"):
                where = f"step {step.number} ({step.title})"
                parsed = parse_tier_line(line.text)
                if parsed is None:
                    faults.append(_fault("OR-31", check_tier_lines, where, f"a tier line the reader cannot take apart: {line.text[:120]}"))
                    continue
                family, parts, none, every = parsed
                if none is None:
                    faults.append(_fault("OR-31", check_tier_lines, where, f"{family}: no 'none' chance"))
                    continue
                if not parts:
                    faults.append(_fault("OR-31", check_tier_lines, where, f"{family}: no tier"))
                    continue
                expected = parts[0]["first"]
                total, slack = none["chance"]
                for part in parts:
                    if part["first"] != expected:
                        faults.append(_fault("OR-31", check_tier_lines, where, f"{family}: tiers are not in order and without a gap (T{part['first']} where T{expected} should be)"))
                    expected = part["last"] + 1
                    count = part["last"] - part["first"] + 1
                    if part["join"] and count > 1 and not part["each"]:
                        faults.append(_fault("OR-31", check_tier_lines, where, f"{family}: a run of tiers whose chance is not 'each'"))
                    if part["join"] == "and" and count != 2 or part["join"] == "to" and count < 3:
                        faults.append(_fault("OR-31", check_tier_lines, where, f"{family}: 'and' joins two tiers and 'to' three or more"))
                    value, slop = part["chance"]
                    total += value * count
                    slack += slop * count
                if not any(part["target"] for part in parts) and not every:
                    faults.append(_fault("OR-31", check_tier_lines, where, f"{family}: the target's tier is not marked"))
                if every and any(part["target"] for part in parts):
                    faults.append(_fault("OR-31", check_tier_lines, where, f"{family}: 'every tier is the target' and a tier marked too"))
                for left, right in zip(parts, parts[1:]):
                    if left["target"] == right["target"] and left["chance"] == right["chance"]:
                        faults.append(_fault("OR-31", check_tier_lines, where, f"{family}: T{left['last']} and T{right['first']} have one chance and are not joined"))
                if abs(total - 100.0) > slack + 1e-6:
                    faults.append(_fault("OR-31", check_tier_lines, where, f"{family}: the chances sum to {total:.2f}%, not 100%"))
    return faults


_ADDS_NO_TIERED_MOD = re.compile(r"^(Orb of Annulment|Annulment Orb|Orb of Fracturing|Fracturing Orb|Orb of Scouring|Scouring Orb|Bench ?craft|Restart|Remove)", re.I)


def check_tier_step_has_tier_line(page: Page) -> list[Fault]:
    """OR-31: a step that names a goal mod and draws it by chance (a "Chance per use") shows "Tier chances", not only whether the
    requirement is met (R04's check of the published odds gave two numbers). The rule is about a step that can add a mod of a wanted
    family, so an action that adds no mod to spawn by tier (an Annulment, a Fracturing Orb, a Scouring Orb, a bench craft, a restart)
    is not asked for one."""
    faults = []
    for route in page.routes:
        for step in route.steps:
            if _ADDS_NO_TIERED_MOD.match(step.title):
                continue
            wants = [line for line in step.lines("Goal") if "crafted" not in line.text and re.search(r"\bT\d+\b", line.text)]
            if wants and step.has("Chance per use") and not step.has("Tier chances"):
                faults.append(_fault("OR-31", check_tier_step_has_tier_line, f"step {step.number} ({step.title})", "the step can add a wanted mod and shows no 'Tier chances'"))
    return faults


# --- the decision of #553, not a rule of the file ------------------------------------------------------------

RULE_NO_INTERNAL_NAMES = "#481 and #553"

_FILE_TYPES = "js|py|yaml|yml|json|md|txt|html|toml|csv|cfg"
_SITES = "com|net|org|io|gg|ninja|watch"  # `poe.ninja`, `pathofexile.com`: a source a person may read, not an id

_INTERNAL = [  # in this order: a dotted id is taken out of the text before its snake_case part is looked for
    ("a dotted claim id", re.compile(r"\b[a-z]+(?:_[a-z0-9]+)*\.[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")),
    ("a file name", re.compile(rf"\b[\w-]+\.(?:{_FILE_TYPES})\b")),
    ("a dotted claim id", re.compile(rf"\b[a-z]{{3,}}\.(?!(?:{_SITES})\b)[a-z]{{3,}}\b")),  # `conflict.odds`: no underscore in it
    ("a Metadata/ path", re.compile(r"\bMetadata/\S*")),
    ("a ticket number", re.compile(r"(?<![\w&])#\d{2,}\b")),
    ("an issue or ticket number", re.compile(r"\b(?:issue|ticket|PR|pull request)s?\s+#?\d+\b", re.I)),
    ("an ADR number", re.compile(r"\bADR-?\d+\b")),
    ("a workflow word", re.compile(r"\b(?:grill(?:\s+[A-Z]\d+)?|main chat|open points?|in-game list|GPT researcher|research note)\b", re.I)),
    ("a base id in brackets", re.compile(r"\[(?=[A-Za-z0-9_]*[0-9A-Z])[A-Za-z][A-Za-z0-9_]*\]")),
    ("a snake_case token", re.compile(r"\b[a-z]+(?:_[a-z0-9]+){2,}\b")),
]


def internal_names_in(text: str) -> list[tuple[str, str]]:
    """(kind, text) of each internal name in `text`: what `check_no_internal_names` finds, for a test of the claims' own words."""
    found = []
    for name, pattern in _INTERNAL:
        found += [(name, match.group(0)) for match in pattern.finditer(text)]
        text = pattern.sub(" ", text)
    return found


def check_no_internal_names(page: Page) -> list[Fault]:
    """#481 and #553: no internal id or workflow word on the page (a dotted claim id, a snake_case token, a `Metadata/` path, a file name,
    a ticket, issue or ADR number, a word such as "grill" or "main chat", a base id in brackets). The owner reads the page and is not a
    developer: a base is named by its game name, a claim by its plain statement and its source; the id may stay in the JSON answer, which
    is for tools. A decision of the main chat under #481, not a rule of the file."""
    faults = []
    for route in page.routes:
        for where, text in _all_texts(route):
            for name, found in internal_names_in(text):
                faults.append(Fault(RULE_NO_INTERNAL_NAMES, "check_no_internal_names", where, f"{name}: {found}"))
    return faults


def _all_texts(route: Route) -> Iterator[tuple[str, str]]:
    for label, lines in (*route.goal, *route.leaves_out):
        for line in lines:
            yield f"goal card, {label}", line.text + " " + line.more
    for step in route.steps:
        yield f"step {step.number}", step.title
        for label, lines in step.fields:
            for line in lines:
                yield f"step {step.number}, {label}", line.text + " " + line.more
        for card in ([step.after] if step.after else []) + list(step.branches):
            yield f"step {step.number}, item card", " ".join([card.name, *card.properties] + [f"{s.text} {s.note}" for s in card.slots])


# --- the lint ------------------------------------------------------------------------------------------------

CHECKS: tuple[Callable[[Page], list[Fault]], ...] = (
    check_cut_guarantee,
    check_mod_format,
    check_bench_line_is_its_craft,
    check_group_printed_once,
    check_no_hidden_step,
    check_bought_item_not_empty,
    check_one_step_per_action,
    check_route_not_twice,
    check_no_range,
    check_approximate_marked,
    check_no_dropped_for_price,
    check_tier_lines,
    check_tier_step_has_tier_line,
    check_no_internal_names,
)


def or_of(check: Callable[[Page], list[Fault]]) -> str:
    """The rule a check keeps: the `OR-n` its docstring opens with (or the issues `#481 and #553` of the one decision that is no rule)."""
    match = re.match(r"\s*(OR-\d+|#\d+ and #\d+)", check.__doc__ or "")
    if not match:
        raise ValueError(f"{check.__name__} cites no rule")
    return match.group(1)


def lint(page: Page, checks: tuple[Callable[[Page], list[Fault]], ...] = CHECKS) -> list[Fault]:
    return [fault for check in checks for fault in check(page)]


def lint_file(path: Path) -> list[Fault]:
    return lint(read_page_file(path))
