"""The words of a limit are a player's (ticket #481, OR-13).

No `what` or `why` of a limit holds a ticket number, a setting key, a module name or a word of the solver. Two readings of the same fact:

* every limit the planner can write, by its source: the strings of every `Limit(...)` call of the `cli` package (and of the other sentences
  that end up in a limit: the decision's message, the notes of the percentile methods, the forecast's refusals), read from the code, so a limit
  nobody has run here is read too;
* the limits that real plans write, from the sources that fill a text in at run time.

What a refusal exception says (the cause of a model gap, of a refusal to approximate) is the exception's own text and is not read here.
"""

import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from cli_support import R12, given, price_file
from targets_support import DATA

from crafting_system.abstraction import Gap
from crafting_system.cli import STRANDS_OFF, make_plan
from crafting_system.cli import _decide, _plan
from crafting_system.cli._decide import Decision
from crafting_system.cli._limits import Limit, claim, model_gap_limits, risk_limits, unpriced_limits
from crafting_system.cli._report import NOT_COMPUTED, UNRESOLVED
from crafting_system.risk import Estimate
from crafting_system.risk._report import GridInfo
from crafting_system.targets import load_target

SRC = Path(__file__).resolve().parent.parent / "src" / "crafting_system"

# a ticket number, a flag, a settings file, a setting key (snake_case), an ADR, and the solver's own words
BANNED = re.compile(
    r"#\d+|--[a-z]|\.toml\b|\bADR\b|\b[a-z]+_[a-z_]+\b|\bpacked\b|\bcoarse\b|\blevels?\b|\bitem states?\b|\bpolic(?:y|ies)\b|\bsolver\b|\bpilot\b|\bgrid\b|\bkernel\b",
    re.IGNORECASE,
)

WATCHED = {"Limit", "Decision", "note", "EstimateRefused"}  # the calls whose strings end up in a limit
WRITERS = {"choose", "measure_solve_rate", "_packed_note"}  # the functions that write the sentence of a limit and hand it on


def without_docstring(function: ast.FunctionDef) -> list[ast.stmt]:
    body = function.body
    return body[1:] if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) else body


def strings_of(node: ast.AST) -> list[str]:
    return [child.value for child in ast.walk(node) if isinstance(child, ast.Constant) and isinstance(child.value, str)]


def watched_strings(path: Path) -> list[tuple[int, str]]:
    found = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
        if name in WATCHED:
            found += [(node.lineno, text) for text in strings_of(node)]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in WRITERS:
            found += [(node.lineno, text) for statement in without_docstring(node) for text in strings_of(statement)]
    return found


SOURCES = sorted(
    path
    for folder in ("cli", "risk", "abstraction")
    for path in (SRC / folder).glob("*.py")
    if any(word in path.read_text(encoding="utf-8") for word in ("Limit(", "note(", "EstimateRefused(", "def choose", "def measure_solve_rate"))
)


def test_the_reading_finds_the_limits_it_is_meant_to_read():
    names = {path.name for path in SOURCES}
    assert {"_plan.py", "_offers.py", "_limits.py", "_reach.py", "_route_flow.py", "_free.py", "_regen.py", "_fold.py", "_estimate.py", "_decide.py"} <= names
    assert sum(len(watched_strings(path)) for path in SOURCES) > 50


@pytest.mark.parametrize("path", SOURCES, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_no_limit_written_in_the_code_holds_an_internal_word(path):
    for line, text in watched_strings(path):
        assert not BANNED.search(text), f"{path.name}:{line}: {text!r} holds {BANNED.search(text).group(0)!r}"


def test_the_sentences_kept_in_constants_are_in_player_words():
    for text in (UNRESOLVED, *NOT_COMPUTED.values(), STRANDS_OFF.why):
        assert not BANNED.search(text), text


def read(limit: Limit) -> None:
    for text in (limit.what, limit.reason()):
        assert not BANNED.search(text), f"{limit.kind}: {text!r} holds {BANNED.search(text).group(0)!r}"


def estimate(value):
    return Estimate(value, value, value)


def test_the_limits_the_real_plans_write_are_in_player_words(monkeypatch):
    target = load_target(R12, DATA)
    plans = [
        make_plan(DATA, target, price_file()),
        make_plan(DATA, target, price_file(), budget=1e-9),  # the whole search run past the budget (G12), the guessed speed (M2)
        make_plan(DATA, given(target), price_file()),
    ]
    monkeypatch.setattr(_plan, "VIEW_FROM_STATES", 0)  # the tree of groups (G14)
    monkeypatch.setattr(_plan, "RISK_QUANTILE_TRANSITIONS", 0)  # the percentiles the memory cannot hold (G19)
    plans.append(make_plan(DATA, target, price_file(), solver="packed"))

    limits = [limit for plan in plans for limit in plan.limits]
    assert {"how-solved", "display", "risk", "strands", "unpriced", "start-item"} <= {limit.kind for limit in limits}
    for limit in limits:
        read(limit)


def test_the_limits_written_from_what_a_run_finds_are_in_player_words():
    grid = GridInfo(0.5, True, 100, 0.0, 0.0)
    unreached = SimpleNamespace(
        success_probability=estimate(1.0), mean=estimate(5.0), variance=estimate(1.0),
        p50=estimate(10.0), p90=estimate(float("inf")), cvar=estimate(float("inf")),
        grid=GridInfo(0.5, True, 100, 0.0, 0.0, gave_up=("a loop of states that cost almost nothing is longer than the 1 states",)),
    )  # fmt: skip
    cut = [*risk_limits(unreached)]
    for cause in ("subcritical", "improper", "unordered"):
        broken = SimpleNamespace(
            success_probability=estimate(0.5), mean=estimate(float("inf")), variance=estimate(float("inf")),
            p50=estimate(float("inf")), p90=estimate(float("inf")), cvar=estimate(float("inf")),
            grid=GridInfo(0.5, True, 100, 0.0, 0.0, cause=cause),
        )  # fmt: skip
        cut += risk_limits(broken)
    assert len(cut) >= 4
    gaps = [Gap("Some Orb", 3, "the cause", False, False), Gap("Other Orb", 1, "it consumes", True, False)]
    decision = Decision("refused", transitions=5_000_000, why="none fits the time")
    written = [
        *cut,
        *model_gap_limits(gaps),
        *unpriced_limits([("Some Essence", ("Some Essence",), "essence"), ("Reforge", ("Lifeforce",), "harvest-reforge")]),
        _plan.whole_search_limit(_plan._packed_note(decision)),
        _plan.lumped_limit(87_251, 12),
        _plan.strands_limit(),
        *_plan.skipped_level_limits([("a tail cut", "no plan to follow")]),
        _plan.guessed_rate_limit("the forecast covers only 6 possible moves between states, too few to time the search on"),
    ]
    for limit in written:
        read(limit)
    assert BANNED.search("the packed solver, ticket #190") and BANNED.search("memory_strands") and BANNED.search("--strands")  # the reading does catch them


def test_the_decision_in_player_words_names_no_level():
    exact = _decide.choose(None, 0.0, 0.0, 60.0, refusal="a cause")
    assert not BANNED.search(exact.message), exact.message
