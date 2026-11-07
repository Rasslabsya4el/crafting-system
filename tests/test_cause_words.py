"""The cause of a model gap is said in player words at the place it is raised (tickets #557, #618, #586; OR-13, OR-26).

A refusal that is not the game's (`OutOfScopeError`, and `EstimateRefused` for the size estimate) reaches a person as the cause in a limit ("Left
out where the model has no rule"), as the reason no approximate answer was possible, and as an `Error:` line. Its first argument, `player`, is the
sentence the person reads; what a developer needs (an id, an ADR or ticket number) is the keyword `detail`, which the JSON answer and the log carry
and no text does. This test finds the sentences by the syntax tree of `actions/` and `abstraction/`, so a raise site added tomorrow is read without
anyone listing it:

* **Every site that makes one of these errors** (a `raise`, or a `return`/call of the class or of a class derived from it, found by the classes
  themselves and not by a list of names) gives `player` as its first argument and nothing but `detail` after it.
* **Every sentence is a player's.** The constant words of `player` (an f-string's fixed parts, a joined string, a module constant it names) hold no
  internal name of `tests/oracle/page_lint.py` (`faults_in`), none of the developer's words below, and no program or option the command does not have.
* **No id is interpolated.** A value written into the sentence (`{...}`) that is an id (`mod.id`, `entry.mod_id`, `base_id`, `donor_mod`...) goes
  through the game's words (`mod_words`, `mod_words_of`, `base_words`: a mod by its text as the page prints it, a base by its game name); an error
  or exception object is never written into the sentence (its text goes to `detail`).
* **The reasons handed to `refuse_unmodelled`** (the jewel reason) are sentences too, and are read the same way.
* **A site the rule would refuse is refused.** Fixtures below plant a site with an id, an ADR number, an exception written into the text and no
  `player`, and each is found.

Left out until #626 lands, with the reason: `abstraction/_pattern.py`, which the coder of #626 is changing at the same time (issue
`PATTERN_ISSUE`). The test fails when that file no longer has a fault, so the exemption cannot outlive the fix.
"""

import ast
import importlib
import pkgutil
import re
from pathlib import Path

import pytest
from test_cli_player_words import faults_in

import crafting_system.abstraction as abstraction_package
import crafting_system.actions as actions_package
from crafting_system.abstraction import EstimateRefused
from crafting_system.actions import OutOfScopeError

SRC = Path(__file__).resolve().parent.parent / "src" / "crafting_system"
PACKAGES = ("actions", "abstraction")

PATTERN_ISSUE = 647  # the follow-up of #557 for the files #626 changes (`abstraction/_pattern.py`)
EXEMPT = {"abstraction/_pattern.py": PATTERN_ISSUE}

WORDS_OF_THE_GAME = {"mod_words", "mod_words_of", "base_words"}  # the functions that say an id as the game does (`crafting_system.items.words`)
ID_NAME = re.compile(r"(?:^|_)(?:id|ids)$|_id$|^donor_(?:mod|base)$|^(?:mod|base)_id$")
EXCEPTION_NAME = re.compile(r"^(?:error|err|exc|refusal|gap|failed|problem|held|timeout)$")
DEVELOPER_WORDS = re.compile(
    r"\bkernel\b|\babstraction\b|\bcoarsening\b|\bcompressed\b|\bsolver\b|\bpilot\b|\bcanonical\b|\badmitted\b|\bclaims?\b|\bB\d\b|\bG\d+\b|\bgrill\b"
    r"|\bmetamods=|\bslots? by\b|\bfamily[- ]group\b|\bpolicy\b|\bADR\b|\bticket\b|\bclass key\b",
    re.IGNORECASE,
)


def derived(root: type) -> set[type]:
    found = {root}
    for sub in root.__subclasses__():
        found |= derived(sub)
    return found


def load_every_module() -> None:
    for package in (actions_package, abstraction_package):
        for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            importlib.import_module(module.name)


load_every_module()
FAMILY = {cls.__name__ for cls in derived(OutOfScopeError) | derived(EstimateRefused)}  # found by the classes: a new subclass is read too


def module_constants(tree: ast.Module) -> dict[str, ast.expr]:
    return {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def the_name_of(call: ast.Call) -> str | None:
    func = call.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None


def sentence_parts(node: ast.expr, constants: dict[str, ast.expr]) -> tuple[list[str], list[ast.expr]]:
    """(the fixed words, the written-in values) of an expression that makes a sentence: a string, an f-string, a joined string, a module constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value], []
    if isinstance(node, ast.JoinedStr):
        fixed, values = [], []
        for part in node.values:
            if isinstance(part, ast.Constant):
                fixed.append(str(part.value))
            elif isinstance(part, ast.FormattedValue):
                values.append(part.value)
        return fixed, values
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = sentence_parts(node.left, constants), sentence_parts(node.right, constants)
        return left[0] + right[0], left[1] + right[1]
    if isinstance(node, ast.Name) and node.id in constants:
        return sentence_parts(constants[node.id], constants)
    if isinstance(node, ast.IfExp):
        body, other = sentence_parts(node.body, constants), sentence_parts(node.orelse, constants)
        return body[0] + other[0], body[1] + other[1]
    return [], [node]  # a value we cannot read as words: written in as it is, and judged as a value


def faults_of_value(value: ast.expr) -> list[str]:
    """What is wrong with a value written into a sentence: an id not said in the game's words, or an exception object."""
    faults = []

    def walk(node: ast.AST) -> None:
        if isinstance(node, ast.Call) and the_name_of(node) in WORDS_OF_THE_GAME:
            return  # the id is said in the game's words from here down
        if isinstance(node, ast.Attribute):
            if ID_NAME.search(node.attr):
                faults.append(f"the id `{ast.unparse(node)}` is written into the sentence (say it with mod_words / mod_words_of / base_words)")
            walk(node.value)
            return
        if isinstance(node, ast.Name):
            if ID_NAME.search(node.id):
                faults.append(f"the id `{node.id}` is written into the sentence (say it with mod_words / mod_words_of / base_words)")
            elif EXCEPTION_NAME.match(node.id):
                faults.append(f"`{node.id}` (an exception or a reason of the code) is written into the sentence: its text goes to `detail`")
            return
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(value)
    return faults


def faults_of_sentence(node: ast.expr, constants: dict[str, ast.expr]) -> list[str]:
    fixed, values = sentence_parts(node, constants)
    text = " ".join(fixed)
    faults = [fault for fault in faults_in(text)]
    faults += [f"a developer's word: {found.group(0)}" for found in DEVELOPER_WORDS.finditer(text)]
    for value in values:
        faults += faults_of_value(value)
    if not fixed and not values:
        faults.append("no words")
    return faults


def faults_of_site(call: ast.Call, constants: dict[str, ast.expr]) -> list[str]:
    """What is wrong with one call that makes a model-gap error: `player` is the first argument, `detail` the only keyword, and it is a player's sentence."""
    if not call.args:
        return ["no player sentence: the first argument is the sentence a person reads"]
    if len(call.args) > 1:
        return ["more than one positional argument: the developer's text is the keyword `detail`"]
    if [keyword.arg for keyword in call.keywords] not in ([], ["detail"]):
        return [f"keywords {[keyword.arg for keyword in call.keywords]}: only `detail` is allowed"]
    return faults_of_sentence(call.args[0], constants)


def sites_in(source: str) -> list[tuple[int, ast.Call, dict[str, ast.expr]]]:
    """Every call of an error class of the family (a `raise`, a `return`, an assignment), by the syntax tree."""
    tree = ast.parse(source)
    constants = module_constants(tree)
    return [(node.lineno, node, constants) for node in ast.walk(tree) if isinstance(node, ast.Call) and the_name_of(node) in FAMILY]


def reasons_in(source: str) -> list[tuple[int, ast.expr, dict[str, ast.expr]]]:
    """The jewel reason of each `refuse_unmodelled(data, item, reason)`: a sentence that ends up as a cause."""
    tree = ast.parse(source)
    constants = module_constants(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and the_name_of(node) == "refuse_unmodelled":
            given = node.args[2] if len(node.args) > 2 else next((k.value for k in node.keywords if k.arg == "jewel_reason"), None)
            if given is not None:
                found.append((node.lineno, given, constants))
    return found


FILES = sorted(
    path
    for package in PACKAGES
    for path in (SRC / package).glob("*.py")
    if path.relative_to(SRC).as_posix() not in EXEMPT
)


# --- the rule on planted sites -----------------------------------------------------------------------------------------------


def call_of(text: str) -> ast.Call:
    (_, call, _), *_ = sites_in(text)
    return call


@pytest.mark.parametrize(
    ("source", "fault"),
    [
        ('raise OutOfScopeError(f"a roll limit on {mod.id} is not modelled")', "the id `mod.id`"),
        ('raise OutOfScopeError(f"no rule for {entry.mod_id}")', "the id `entry.mod_id`"),
        ('raise OutOfScopeError(f"{self.donor_mod} cannot be held")', "the id `self.donor_mod`"),
        ('raise OutOfScopeError("the item is not modelled (ADR-0023)")', "an ADR number"),
        ('raise OutOfScopeError("a start item with a double veil is out of scope (grill B2)")', "a workflow word"),
        ('raise OutOfScopeError("the planner does not price them yet (ticket #212)")', "a ticket number"),
        ('raise OutOfScopeError(f"the game refuses it ({refusal})")', "an exception or a reason of the code"),
        ('raise OutOfScopeError(f"the outcomes cannot be computed: {error}")', "an exception or a reason of the code"),
        ('raise OutOfScopeError("the kernel averages over one input")', "a developer's word: kernel"),
        ('raise OutOfScopeError("pass metamods=True to model it")', "a developer's word: metamods="),
        ('raise OutOfScopeError("the claim enchantment.mirrored_and_corruption says so")', "a dotted claim id"),
        ('raise OutOfScopeError("the mod is IncreasedLifeEssence6")', "a game mod id"),
        ('raise EstimateRefused("see the size_estimate module")', "a snake_case token"),
        ("raise OutOfScopeError()", "no player sentence"),
        ('raise OutOfScopeError("a sentence", "and the detail as a second argument")', "more than one positional"),
        ('raise OutOfScopeError("a sentence", player="x")', "keywords"),
        ('raise OutOfScopeError("a sentence", message="x")', "keywords"),
    ],
)
def test_a_site_without_player_words_is_found(source, fault):
    found = faults_of_site(call_of(source), {})
    assert any(fault in each for each in found), (source, found)


@pytest.mark.parametrize(
    "source",
    [
        'raise OutOfScopeError("a family with mods on both sides of the item (a jewel) is not modelled yet")',
        'raise OutOfScopeError(f"the item is {item.rarity.value}, and the model has no rule for that", detail=f"{mod.id} ADR-0023")',
        'raise OutOfScopeError(f"a roll limit on a mod ({mod_words(mod)}) is not modelled yet", detail=f"mod {mod.id}")',
        'raise OutOfScopeError(f"the input is an item on {base_words(data, donor.base_id)} at item level {donor.item_level}")',
        'raise OutOfScopeError(f"{mod_words_of(data, entry.mod_id)} is not an influence mod of {self.donor_influence.value}")',
        'raise EstimateRefused("an offered action rerolls the values of mods, which the size estimate has no rule for")',
    ],
)
def test_a_site_with_player_words_passes(source):
    assert faults_of_site(call_of(source), {}) == [], source


def test_a_constant_the_sentence_names_is_read():
    source = '_BAD = "see ADR-0023"\nraise OutOfScopeError(_BAD)\n'
    (_, call, constants), *_ = sites_in(source)
    assert any("an ADR number" in fault for fault in faults_of_site(call, constants))


def test_the_family_is_found_by_the_classes_not_by_a_list():
    assert {"OutOfScopeError", "ConsumesInputsError", "BlockHoldsMetamod", "EstimateRefused"} <= FAMILY


def test_an_error_of_the_family_needs_its_player_sentence_to_be_made():
    with pytest.raises(TypeError):
        OutOfScopeError()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        EstimateRefused()  # type: ignore[call-arg]
    error = OutOfScopeError("the sentence", detail="ADR-0023: the developer's text")
    assert str(error) == error.player == "the sentence" and error.detail == "ADR-0023: the developer's text"
    assert OutOfScopeError("only a sentence").detail == "only a sentence"


# --- every site of the code --------------------------------------------------------------------------------------------------


def test_the_reading_finds_the_sites_it_is_meant_to_read():
    found = {path.name: len(sites_in(path.read_text(encoding="utf-8"))) for path in FILES}
    assert sum(found.values()) > 80
    assert found["_kernel.py"] >= 18 and found["fossil.py"] >= 4 and found["_coarse.py"] >= 9
    assert "_pattern.py" not in found
    assert sum(len(reasons_in(path.read_text(encoding="utf-8"))) for path in FILES) >= 4  # the jewel reasons of the two harvest crafts and the two veiled actions


@pytest.mark.parametrize("path", FILES, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_every_site_gives_a_sentence_a_player_can_read(path):
    source = path.read_text(encoding="utf-8")
    bad = [f"{path.name}:{line}: {fault}" for line, call, constants in sites_in(source) for fault in faults_of_site(call, constants)]
    bad += [f"{path.name}:{line}: the jewel reason: {fault}" for line, node, constants in reasons_in(source) for fault in faults_of_sentence(node, constants)]
    assert bad == []


def test_a_file_left_out_until_its_issue_is_fixed_still_has_a_fault():
    for name, issue in EXEMPT.items():
        source = (SRC / name).read_text(encoding="utf-8")
        found = [fault for line, call, constants in sites_in(source) for fault in faults_of_site(call, constants)]
        assert found, f"{name} has no fault: take it out of EXEMPT (issue #{issue})"


def test_the_game_words_say_a_mod_by_its_text_and_a_base_by_its_name():
    from items_support import DATA

    from crafting_system.items.words import NO_BASE, NO_TEXT, base_words, mod_words, mod_words_of

    mod = DATA.mods["IncreasedLife1"]
    assert mod_words(mod) == mod_words_of(DATA, "IncreasedLife1") and "IncreasedLife1" not in mod_words(mod)
    assert mod_words_of(DATA, "NoSuchMod1") == NO_TEXT and faults_in(NO_TEXT) == []
    base = next(iter(DATA.base_items.values()))
    assert base_words(DATA, base.id) == base.name
    assert base_words(DATA, "NoSuchBase") == NO_BASE and faults_in(NO_BASE) == []


# --- where the sentence and the developer's text go -----------------------------------------------------------------------------


def test_a_gap_says_the_sentence_in_the_text_and_keeps_the_developers_text_for_the_json():
    from crafting_system.abstraction import Gap, ModelGaps
    from crafting_system.cli._limits import limit_document, limit_text, model_gap_limits

    gaps = ModelGaps()
    gaps.note(
        "Essence of Greed",
        "state-1",
        OutOfScopeError("a roll limit on a new mod is not modelled yet (+(30-35) to maximum Life)", detail="the mod IncreasedLifeEssence6, ADR-0023, ticket #212"),
    )
    (gap,) = gaps.entries()
    assert gap.cause == "a roll limit on a new mod is not modelled yet (+(30-35) to maximum Life)" and "IncreasedLifeEssence6" in gap.detail
    (limit,) = model_gap_limits([gap])
    text = limit_text(limit)
    assert "maximum Life" in text and faults_in(text) == [] and "IncreasedLifeEssence6" not in text and "ADR" not in text
    assert limit_document(limit)["detail"] == [gap.detail]  # the JSON keeps it for tools
    assert "detail" not in limit_document(model_gap_limits([Gap("Orb", 1, "no rule", False)])[0])  # no developer text, no key
