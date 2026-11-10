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
* a statistics or program word (`JARGON`): `p50`, `p90`, `CVaR`, `solver`, `percentile`, `quantile`, and a figure's label that is not the
  words of `cli/_limits.py` `PERCENTILE_WORDS` ("the success chance", "the median cost", "the cost 9 runs in 10 stay under", "the average of
  the worst tenth"), so that a figure is said as one table says it (ticket #633);
* a command line option that the command does not have. A command line option is a thing the player types, so a sentence may name it
  (`--exact`, `--start-price`), but only an option that some `add_argument` of the `cli` package declares: the option is read from the code.

**What this test does not read yet.** The texts of exceptions raised below `cli/` and shown to a person, as the cause in a limit ("Left
out where the model has no rule") or as `Error: {error}` (`cli/_main.py`), are not read, because they are written outside the package this
test scans. The causes written in `actions/` and `abstraction/` are read by `tests/test_cause_words.py` (by the syntax tree of their raise
sites, #557); #632 owns the errors of `data`, `targets`, `prices` and `config`. The benchmark command is #631. The header
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
from crafting_system.cli._verify import verify
from crafting_system.items.vendor_recipes import RECIPES
from crafting_system.targets import load_target

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "src" / "crafting_system" / "cli"
GOLDEN = Path(__file__).resolve().parent / "golden"

NOT_READ = {"_route_html.py"}  # the page's CSS and script: the page lint reads the page
NOT_READ_PREFIX = "_benchmark"  # the benchmark command is a developer's tool; its words are filed as an issue (OR-29)
PROGRAM_NAME = "COMMAND"  # the constant that holds the program name for `argparse`'s usage line

LEAF_LABEL_LEAK = ", mod "  # `leaf_labels` writes ", mod <id>" into the `Requirements:` line and the state lines (issue #649): the game-id pattern is not asked of a mod written so, on those lines only
LEAF_LABEL_LINES = re.compile(r"Requirements: |S\d+: |  the item: |  [0-9,]+ items take this action; what they all share: |  .* = [0-9.,]+%; chance of one use")  # the lines that carry a leaf label: the requirements, an item of a step ("  the item: rare; ... lacks <leaf>; has <leaf>"; the JSON state "S1: ..." too) and a chance line of the odds table


def leaked_by_a_leaf_label(line: str, fault: str) -> bool:
    """Whether `fault` is the game id of a mod that `leaf_labels` writes after ", mod " (issue #649)."""
    return bool(LEAF_LABEL_LINES.match(line)) and fault.startswith("a game mod id: ") and f"{LEAF_LABEL_LEAK}{fault.removeprefix('a game mod id: ')}" in line


OPTION = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")
PROGRAM = re.compile(r"\bpython\b|\bpip\b|\buv\b", re.IGNORECASE)
JARGON = {  # a word a player does not use; the figures are said as `_limits.PERCENTILE_WORDS` says them
    "p50": re.compile(r"\bp50\b"),
    "p90": re.compile(r"\bp90\b"),
    "CVaR": re.compile(r"\bCVaR\b", re.IGNORECASE),
    "solver": re.compile(r"\bsolvers?\b", re.IGNORECASE),
    "percentile": re.compile(r"\bpercentiles?\b", re.IGNORECASE),
    "quantile": re.compile(r"\bquantiles?\b", re.IGNORECASE),
    "a bare success chance": re.compile(r"(?<![Tt]he )\bsuccess chance\b"),  # `PERCENTILE_WORDS` says "the success chance"; the page card's field label "Success chance" is a label, not a row
}
FOR_A_PROGRAMMER = ("solver must be one of ", "risk: p50 ")  # the error about the library argument `solver=` and the progress line of a heavy run: not read by a player


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
    """The lines of a report a player reads, but not the headers `Target: <file>` and `Given route: <name> (<file>)`, which echo the name of the player's own file."""
    return [line for line in text.splitlines() if not line.startswith(("Target: ", "Given route: "))]


def faults_in(text: str, options: set[str] = OPTIONS) -> list[str]:
    """What a player should not read in `text`: an internal name, a module path or program, an option the command does not have."""
    faults = [f"{kind}: {found}" for kind, found in page_lint.internal_names_in(text)]
    faults += [f"an option the command does not have: {option}" for option in OPTION.findall(text) if option not in options]
    faults += [f"a program name: {word}" for word in PROGRAM.findall(text)]
    said = OPTION.sub(lambda found: "" if found.group(0) in options else found.group(0), text)  # an option the command declares is the player's own word (`--solver`, #535)
    faults += [f"jargon: {name}" for name, pattern in JARGON.items() if pattern.search(said)]
    return faults


PLACEHOLDER = "{}"  # what stands for a value in an f-string read as one sentence


def sentences_of(path: Path) -> list[tuple[int, str]]:
    """(line, text) of each string of the file with two words or more, but no docstring and no program name."""
    return sentences_in(path.read_text(encoding="utf-8"))


def sentences_in(source: str) -> list[tuple[int, str]]:
    """The sentences of Python source: each string constant, and each f-string read as ONE sentence with `PLACEHOLDER` for every value.

    An f-string is not read by its literal fragments: `f"  p90   {value}"` and `f"{value} p90"` would each have one fragment of a single word,
    and the two-word rule would pass them, though a player reads two words in each.
    """
    tree = ast.parse(source)
    left_out: set[int] = set()
    joined: list[ast.JoinedStr] = []
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
        if isinstance(node, ast.JoinedStr):
            joined.append(node)
    found = []
    for node in joined:
        if id(node) in left_out:
            continue
        found.append((node.lineno, "".join(part.value if isinstance(part, ast.Constant) else PLACEHOLDER for part in node.values)))
        left_out |= {id(child) for child in ast.walk(node)}  # its fragments are read as part of the whole
    found += [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in left_out
    ]
    return sorted((line, text) for line, text in found if len(text.split()) >= 2)


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
        ("  p50             597.04 Chaos (1.6 Divine)", "jargon: p50"),
        ("  p90             1,984.76 Chaos", "jargon: p90"),
        ("simulated CVaR 90% 2,000 Chaos", "jargon: CVaR"),
        ("Run time: solver 12 ms, risk figures 0.3 ms", "jargon: solver"),
        ("Run time: both solvers 12 ms", "jargon: solver"),
        ("the percentiles hold to within 1 Chaos", "jargon: percentile"),
        ("  success chance  100%", "jargon: a bare success chance"),
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
        "  the success chance                100%",
        "  the cost 9 runs in 10 stay under  1,984.76 Chaos (5.33 Divine), certified 1,980.82 to 1,988.70",
        "Run time: working out the plan took 12 ms, the risk figures 0.3 ms",
    ],
)
def test_the_rule_lets_a_player_read_an_option_and_the_words_of_the_report(text):
    assert faults_in(text) == [], text


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ('lines.append(f"  p90             {value}")', "jargon: p90"),
        ('lines.append(f"{value} p90")', "jargon: p90"),
        ('lines.append(f"  success chance  {value}")', "jargon: a bare success chance"),
        ('lines.append(f"Run time: solver {ms} ms")', "jargon: solver"),
        ('lines.append(f"{ms} ms by the solver")', "jargon: solver"),
        ('lines.append(f"{count} items, see ADR-0023")', "an ADR number"),
        ('lines.append(f"  simulated CVaR {level} {value}")', "jargon: CVaR"),
    ],
)
def test_an_f_string_is_read_as_one_sentence_so_a_short_fragment_cannot_hide(source, kind):
    sentences = sentences_in(source)

    assert sentences, source  # the two-word rule keeps it
    assert any(fault.startswith(kind) for _, text in sentences for fault in faults_in(text)), source


def test_a_docstring_a_one_word_string_and_a_plain_f_string_are_not_sentences():
    source = 'def f(x):\n    """p90 solver."""\n    a = "p90"\n    b = f"{x}"\n    c = f"{x} stay under"\n    return a, b, c\n'

    assert [text for _, text in sentences_in(source)] == ["{} stay under"]


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
        faults = faults_in(text)
        if text.startswith(FOR_A_PROGRAMMER):
            faults = [fault for fault in faults if not fault.startswith("jargon")]
        assert faults == [], f"{path.name}:{line}: {text!r}"


# --- every sentence a run writes -----------------------------------------------------------------------------------------------


def wand_prices():
    return prices(base=None, flask=None, **{"Toy_Wand_(ilvl_86)": BASE_PRICE, "Ruby_Flask": FLASK_PRICE})


def other_surfaces(tmp_path_factory) -> dict[str, str]:
    """The three texts that the plain R12 plan does not print: the `--verify` block of an approximate answer, the given-route block and the
    free-action note. Each is made by the plan of the test that owns it, so that the jargon list reads what a player reads."""
    from coarse_support import DATA as COARSE
    from items_support import DATA as ITEMS_DATA
    from test_cli_approximate import OFFERS, PRICES, RATES, TARGET
    from test_cli_approximate_inputs import lookup, toy_plan
    from test_cli_free_actions import DATA as VEIL_DATA
    from test_cli_free_actions import price_file as veil_prices
    from test_cli_free_actions import veil_target

    from crafting_system.abstraction import Coarsening
    from crafting_system.cli import _marking
    from crafting_system.cli._route import Route, RouteResult
    from crafting_system.cli._route_report import render_route_text
    from crafting_system.targets import parse_target

    target = parse_target(TARGET, COARSE, source="t.yaml")
    exact = make_plan(COARSE, target, PRICES, offers=OFFERS)
    forecast = exact.abstraction.estimate([exact.start], [offer.action for offer in OFFERS])
    pooling = Coarsening.pooling_irrelevant(exact.abstraction, None, exact.start)
    budget = (forecast.seconds(1.0, 1.0) + forecast.coarsened(pooling).seconds(1.0, 1.0)) / 2
    approximate = make_plan(COARSE, target, PRICES, offers=OFFERS, budget=budget, rates=RATES, solver="object")
    approximate_check = verify(COARSE, approximate, runs=300, seed=7)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_marking, "rule_by_id", lookup)  # the toy rules, as the autouse fixture of the test that owns the plan does
        planner = toy_plan("Marked Chaos")
        other = toy_plan("Untaken Chaos")  # the given route takes the other action
        result = RouteResult(dict(other.policy), other.risk, (), None, 0.0)
        route_text = render_route_text(build_report(planner, ITEMS_DATA), Route("Toy route", "toy.yaml", ()), result, ITEMS_DATA, file_name="toy.yaml")

    veil = make_plan(VEIL_DATA, veil_target(tmp_path_factory.mktemp("veil")), veil_prices(Veiled_Chaos_Orb=5.0))
    return {
        "approximate answer with --verify": render_text(build_report(approximate, COARSE), approximate_check),
        "given route": route_text,
        "plan with free actions": render_text(build_report(veil, VEIL_DATA)),
    }


@pytest.fixture(scope="module")
def texts(tmp_path_factory) -> dict[str, str]:
    """The text of real plans: the R12 plan (no start options), and the toy wand whose elemental cap changes the cheapest total."""
    plan = make_plan(DATA, load_target(R12, DATA), price_file())
    capped = plan_with_starts(TOY, toy_target(WAND_TARGET), wand_prices())
    no_speed = plan_with_starts(TOY, toy_target(BOOTS_TARGET.replace("  - family: MovementVelocity\n    min_tier: 2\n", "")), prices())
    too_low = plan_with_starts(TOY, toy_target(BOOTS_TARGET.replace("min_tier: 2", "min_tier: 1")), prices())
    check = verify(DATA, plan, runs=300, seed=7)
    return {
        "R12 plan": render_text(build_report(plan, DATA)),
        "R12 plan with --verify": render_text(build_report(plan, DATA), check),
        "toy wand with a cap that matters": render_text(build_report(capped, TOY)),
        "toy boots, no requirement the recipe serves": render_text(build_report(no_speed, TOY)),
        "toy boots, a cap below the asked tier": render_text(build_report(too_low, TOY)),
        **other_surfaces(tmp_path_factory),
    }


def test_the_text_of_real_plans_holds_no_internal_name(texts):
    assert "Start options" in texts["toy wand with a cap that matters"]  # the block of #618 is among the texts read
    assert "Cheapest total over the readings" in texts["toy wand with a cap that matters"]
    assert "refused (no target mod): no requirement of the target asks for what these recipes make: Boots with movement speed" in texts["toy boots, no requirement the recipe serves"]
    assert "refused: Boots with movement speed: " in texts["toy boots, a cap below the asked tier"]
    assert "Verification by simulation" in texts["R12 plan with --verify"] and "Run time: working out the plan took" in texts["R12 plan"]
    assert "Verification by simulation, not certified" in texts["approximate answer with --verify"]  # the block of `_marking.verification_lines`
    assert "Given route: Toy route" in texts["given route"] and "(policy " in texts["given route"]  # the block of `_route_report`
    assert "free actions are counted at" in texts["plan with free actions"]  # the note of `_report.free_action_lines`
    for where, text in texts.items():
        for number, line in enumerate(reading_lines(text), 1):
            faults = [fault for fault in faults_in(line) if not leaked_by_a_leaf_label(line, fault)]
            assert faults == [], f"{where}, line {number}: {line!r}"


def test_the_requirements_leak_is_still_there_so_its_exemption_is_still_needed(texts):
    leaks = [line for line in reading_lines(texts["R12 plan"]) if any(leaked_by_a_leaf_label(line, fault) for fault in faults_in(line))]
    assert leaks, "fixed: delete LEAF_LABEL_LEAK and leaked_by_a_leaf_label (issue #649)"


def test_the_result_block_and_the_verification_say_each_figure_as_the_table_does(texts):
    from crafting_system.cli._limits import PERCENTILE_WORDS

    text, verified = texts["R12 plan"], texts["R12 plan with --verify"]
    for name in ("success", "mean", "p50", "p90"):
        assert any(line.startswith(f"  {PERCENTILE_WORDS[name]} ") for line in text.splitlines()), name
    assert f"  {PERCENTILE_WORDS['p90']}: simulated " in verified
    assert "Run time: working out the plan took " in text


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


def test_an_option_the_command_declares_is_not_jargon_but_the_word_alone_is():
    """#535: a refusal may name `--solver packed`, the player's own option; "the solver" in a sentence is still jargon."""
    assert faults_in("choose the search that walks every possible item: `--solver packed`") == []
    assert faults_in("the solver gave up") == ["jargon: solver"]


def test_a_number_is_shown_as_the_report_always_showed_it():
    assert [value_text("recombinator.alpha", Fraction(x)) for x in ("2/5", "1", "13/10")] == ["0.4", "1", "1.3"]
    assert reading_pair("recombinator.alpha", Fraction(1)) == "alpha = 1"
