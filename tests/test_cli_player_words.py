"""Every sentence a player reads in the text report and in an error of the command is in a player's words (tickets #618, #586; OR-13, OR-26).

`test_cli_limit_words.py` reads the sentences that become a limit. This test reads the rest, and it finds them structurally so that
the next new sentence is read without anyone listing it:

* **Every sentence in the code.** Each string constant of the `cli` package that holds two or more words and is not a docstring is a
  sentence a person can read: a line of the report, a limit, a help line, the text of an error. Reading all of them (and not only those
  in a `Limit(...)` or a `raise`) means a sentence is covered whatever function builds it. Left out, with the reason: the benchmark
  command (`_benchmark*.py`, a developer's tool whose report is its own issue), the page's CSS and script (`_route_html.py`; the page lint
  reads the page), and the constant `COMMAND`, the program name that `argparse` prints in its usage line.
* **Every sentence a run writes.** The text of real plans (the report, the start options, the errors of a bought start item) and every
  text golden, which carry the words that are built at run time (an axis and its value, a mod name, a reason).

**The rule, one for all of them.** A sentence holds none of the internal names of `tests/oracle/page_lint.py` (`internal_names_in`: a
claim id, a file name, a ticket or ADR number, a workflow word, a base id, a snake_case token of even one underscore) and none of these:

* a module path or a program (`python -m crafting_system.cli trade`): the player is told the command by its name (the `trade` command);
* a command line option that the command does not have. A command line option is a thing the player types, so a sentence may name it
  (`--exact`, `--start-price`), but only an option that some `add_argument` of the `cli` package declares: the option is read from the code.

**What this test does not read yet.** The texts of exceptions raised below `cli/` and shown to a person, as the cause in a limit ("Left
out where the model has no rule") or as `Error: {error}` (`cli/_main.py`), are not read, because they are written outside the package this
test scans. Two open issues own them: #557 for the causes written in `actions/` and `abstraction/` (they still hold "ADR-0023",
"(ticket #212)", "(grill B2)" and a game mod id, as on `tests/golden/real_r10.html`), and #632 for the errors of `data`, `targets`,
`prices` and `config`. The benchmark command is #631, and the short figure names `p50`, `p90` and `CVaR` are #633. The header
`Target: <file>` is not read: it echoes the name of the player's own file.

The axis table (`cli/_axes.py`) has its own test below: every rule axis the code defines has words, and so has each of its values.
"""

import ast
import importlib
import pkgutil
import re
from fractions import Fraction
from pathlib import Path

import pytest
from cli_support import R12, given, price_file
from oracle import page_lint
from targets_support import DATA
from vendor_starts_support import BASE_PRICE, BOOTS_TARGET, FLASK_PRICE, TOY, WAND_TARGET, prices, toy_target

import crafting_system.actions as actions_package
from crafting_system.actions.contract import Axis
from crafting_system.cli import build_report, make_plan, plan_with_starts, render_text
from crafting_system.cli._axes import AXIS_WORDS, AxisWords, axis_name, axis_what, reading_pair, value_text
from crafting_system.cli._plan import PlanError, resolve_start_price
from crafting_system.items.vendor_recipes import RECIPES
from crafting_system.targets import load_target

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "src" / "crafting_system" / "cli"
GOLDEN = Path(__file__).resolve().parent / "golden"

NOT_READ = {"_route_html.py"}  # the page's CSS and script: the page lint reads the page
NOT_READ_PREFIX = "_benchmark"  # the benchmark command is a developer's tool; its words are filed as an issue (OR-29)
PROGRAM_NAME = "COMMAND"  # the constant that holds the program name for `argparse`'s usage line

OPTION = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")
PROGRAM = re.compile(r"\bpython\b|\bpip\b|\buv\b", re.IGNORECASE)


def declared_options() -> set[str]:
    """The command line options the `cli` package declares: the first string of each `add_argument` call that starts with `--`."""
    found = {"--help"}
    for path in CLI.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
                found |= {arg.value for arg in node.args if isinstance(arg, ast.Constant) and str(arg.value).startswith("--")}
    return found


OPTIONS = declared_options()


def reading_lines(text: str) -> list[str]:
    """The lines of a report a player reads, but not the header `Target: <file>`, which echoes the name of the player's own file."""
    return [line for line in text.splitlines() if not line.startswith("Target: ")]


def faults_in(text: str, options: set[str] = OPTIONS) -> list[str]:
    """What a player should not read in `text`: an internal name, a module path or program, an option the command does not have."""
    faults = [f"{kind}: {found}" for kind, found in page_lint.internal_names_in(text)]
    faults += [f"an option the command does not have: {option}" for option in OPTION.findall(text) if option not in options]
    faults += [f"a program name: {word}" for word in PROGRAM.findall(text)]
    return faults


def sentences_of(path: Path) -> list[tuple[int, str]]:
    """(line, text) of each string constant of the file with two words or more, but no docstring and no program name."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    left_out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                left_out.add(id(first.value))
        for annotation in (getattr(node, "annotation", None), getattr(node, "returns", None)):  # a type written as a string is code
            if annotation is not None:
                left_out |= {id(child) for child in ast.walk(annotation)}
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == PROGRAM_NAME for target in node.targets):
            left_out |= {id(child) for child in ast.walk(node.value)}
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in left_out and len(node.value.split()) >= 2
    ]


READ = sorted(path for path in CLI.glob("*.py") if path.name not in NOT_READ and not path.name.startswith(NOT_READ_PREFIX))


# --- the rule itself, on counter-examples and examples ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Start options: elemental_cap = wiki", "a snake_case token"),
        ("Rule axis changes the cheapest total (ADR-0059)", "an ADR number"),
        ("Price it with `python -m crafting_system.cli trade <target file>`", "a program name"),
        ("write it in price_overrides.toml", "a file name"),
        ("the setting recipe_starts of crafting.toml", "a snake_case token"),
        ("run again with --no-such-option", "an option the command does not have"),
        ("the bound fell (see #509)", "a ticket number"),
    ],
)
def test_the_rule_finds_what_it_is_meant_to_find(text, kind):
    assert any(fault.startswith(kind) for fault in faults_in(text)), text


@pytest.mark.parametrize(
    "text",
    [
        "--route is not available for an approximate answer yet; run again with --exact",
        "or give it with --start-price",
        "Price it on the trade site with the `trade` command",
        "an elemental recipe cap = the wiki's tier 3",
        "Not computed: the median cost, the cost 9 runs in 10 stay under, and the average of the worst tenth",
    ],
)
def test_the_rule_lets_a_player_read_an_option_and_the_words_of_the_report(text):
    assert faults_in(text) == [], text


def test_the_options_are_read_from_the_code():
    assert {"--exact", "--start-price", "--route", "--strands", "--no-recipe-starts", "--verify", "--budget", "--help"} <= OPTIONS


# --- every sentence in the code ------------------------------------------------------------------------------------------------


def test_the_reading_finds_the_sentences_it_is_meant_to_read():
    names = {path.name for path in READ}
    assert {"_main.py", "_plan.py", "_report.py", "_start_report.py", "_marking.py", "_limits.py", "_interval.py", "_trade.py", "_axes.py"} <= names
    assert not names & NOT_READ and not any(name.startswith(NOT_READ_PREFIX) for name in names)
    assert sum(len(sentences_of(path)) for path in READ) > 500
    texts = [text for path in READ for _, text in sentences_of(path)]
    assert any("run again with --exact" in text for text in texts)  # a sentence that names an option is read too
    assert any(text.startswith("Start options (") for text in texts)
    assert not any(text == "python -m crafting_system.cli" for text in texts)  # the program name is left out, nothing else


@pytest.mark.parametrize("path", READ, ids=lambda path: path.name)
def test_no_sentence_of_the_code_holds_an_internal_name(path):
    for line, text in sentences_of(path):
        assert faults_in(text) == [], f"{path.name}:{line}: {text!r}"


# --- every sentence a run writes -----------------------------------------------------------------------------------------------


def wand_prices():
    return prices(base=None, flask=None, **{"Toy_Wand_(ilvl_86)": BASE_PRICE, "Ruby_Flask": FLASK_PRICE})


@pytest.fixture(scope="module")
def texts() -> dict[str, str]:
    """The text of real plans: the R12 plan (no start options), and the toy wand whose elemental cap changes the cheapest total."""
    plan = make_plan(DATA, load_target(R12, DATA), price_file())
    capped = plan_with_starts(TOY, toy_target(WAND_TARGET), wand_prices())
    no_speed = plan_with_starts(TOY, toy_target(BOOTS_TARGET.replace("  - family: MovementVelocity\n    min_tier: 2\n", "")), prices())
    too_low = plan_with_starts(TOY, toy_target(BOOTS_TARGET.replace("min_tier: 2", "min_tier: 1")), prices())
    return {
        "R12 plan": render_text(build_report(plan, DATA)),
        "toy wand with a cap that matters": render_text(build_report(capped, TOY)),
        "toy boots, no requirement the recipe serves": render_text(build_report(no_speed, TOY)),
        "toy boots, a cap below the asked tier": render_text(build_report(too_low, TOY)),
    }


def test_the_text_of_real_plans_holds_no_internal_name(texts):
    assert "Start options" in texts["toy wand with a cap that matters"]  # the block of #618 is among the texts read
    assert "Cheapest total over the readings" in texts["toy wand with a cap that matters"]
    assert "refused (no target mod): no requirement of the target asks for what these recipes make: Boots with movement speed" in texts["toy boots, no requirement the recipe serves"]
    assert "refused: Boots with movement speed: " in texts["toy boots, a cap below the asked tier"]
    for where, text in texts.items():
        for number, line in enumerate(reading_lines(text), 1):
            assert faults_in(line) == [], f"{where}, line {number}: {line!r}"


def test_the_start_options_say_the_rule_axis_in_words(texts):
    text = texts["toy wand with a cap that matters"]
    assert "elemental recipe cap = the wiki's tier 3: " in text and "elemental recipe cap = Craft of Exile's tier 2: " in text
    assert "(only at elemental recipe cap = Craft of Exile's tier 2)" in text
    assert "A rule the sources leave open changes the cheapest total; the plan is the first reading:" in text
    assert "ADR" not in text and "elemental_cap" not in text and "weapon_fire" not in text


@pytest.mark.parametrize("path", sorted(GOLDEN.glob("*.txt")), ids=lambda path: path.name)
def test_a_text_golden_holds_no_internal_name(path):
    for number, line in enumerate(reading_lines(path.read_text(encoding="utf-8")), 1):
        assert faults_in(line) == [], f"{path.name}, line {number}: {line!r}"


def test_the_errors_a_bought_start_item_gives_are_in_player_words():
    target = load_target(R12, DATA)
    with pytest.raises(PlanError) as no_price:
        make_plan(DATA, target, price_file(start=None))
    with pytest.raises(PlanError) as given_start:
        make_plan(DATA, given(target), price_file(), start_price=5.0)
    with pytest.raises(PlanError) as not_above_zero:
        resolve_start_price(DATA, target, price_file(), 0.0)
    for error in (no_price, given_start, not_above_zero):
        assert faults_in(str(error.value)) == [], str(error.value)
    assert "--start-price" in str(no_price.value) and "`trade` command" in str(no_price.value)  # what to do, in the words of the report


# --- the axis table: every rule axis has words ---------------------------------------------------------------------------------


def defined_axes() -> dict[str, Axis]:
    """Every axis the code defines: an `Axis` that a module of `actions` holds, and the axis of each vendor recipe (as an `Axis`)."""
    found: dict[str, Axis] = {}
    for module in pkgutil.walk_packages(actions_package.__path__, "crafting_system.actions."):
        for value in vars(importlib.import_module(module.name)).values():
            if isinstance(value, Axis):
                found[value.name] = value
    for each in RECIPES.values():
        if each.axis is not None:
            found[each.axis] = Axis(each.axis, tuple(each.readings), each.readings[0])
    return found


def without_words(axes: dict[str, Axis], table: dict[str, AxisWords] = AXIS_WORDS) -> list[str]:
    """What is missing in `table` for `axes`: an axis with no entry, or a value of an axis with no words."""
    missing = []
    for name, axis in axes.items():
        entry = table.get(name)
        if entry is None:
            missing.append(f"{name}: no words for the axis")
        elif entry.values is not None:
            missing += [f"{name}: no words for the value {value!r}" for value in axis.readings if str(value) not in entry.values]
    return missing


def test_the_axes_of_the_code_are_found():
    assert {"recombinator.alpha", "awakener.group_conflict", "chromatic_forced_colour", "jeweller_table", "elemental_cap"} <= set(defined_axes())


def test_every_rule_axis_has_words_for_itself_and_each_of_its_values():
    assert without_words(defined_axes()) == []


def test_an_axis_without_words_fails_the_check():
    new = Axis("a_new_axis", ("one", "two"), "one")
    assert without_words({"a_new_axis": new}) == ["a_new_axis: no words for the axis"]
    half = {"a_new_axis": AxisWords("a new rule", "which of two things happens", {"one": "the first"})}
    assert without_words({"a_new_axis": new}, half) == ["a_new_axis: no words for the value 'two'"]
    with pytest.raises(KeyError):
        axis_name("a_new_axis")  # a run never prints an axis it cannot word


def test_the_words_of_every_axis_and_value_are_in_player_words():
    for name, axis in defined_axes().items():
        sentences = [axis_name(name), axis_what(name), *(reading_pair(name, value) for value in axis.readings)]
        assert all(sentences), name
        for text in sentences:
            assert faults_in(text) == [], (name, text)
        assert len({value_text(name, value) for value in axis.readings}) == len(axis.readings), f"{name}: two values read the same"


def test_a_number_is_shown_as_the_report_always_showed_it():
    assert [value_text("recombinator.alpha", Fraction(x)) for x in ("2/5", "1", "13/10")] == ["0.4", "1", "1.3"]
    assert reading_pair("recombinator.alpha", Fraction(1)) == "alpha = 1"
