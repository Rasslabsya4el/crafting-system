"""The cause of a model gap is said in player words at the place it is raised (tickets #557, #618, #586; OR-13, OR-26).

A refusal that is not the game's (`OutOfScopeError`, and `EstimateRefused` for the size estimate) reaches a person as the cause in a limit ("Left
out where the model has no rule"), as the reason no approximate answer was possible, and as an `Error:` line. Its first argument, `player`, is the
sentence the person reads; what a developer needs (an id, an ADR or ticket number) is the keyword `detail`. `detail` is carried to the JSON policy
by a `Limit` (`Limit.detail`) where the cause becomes one; no text prints it and nothing is logged. This test finds the sentences by the syntax tree
of the whole of `src/`, so a raise site added tomorrow is read without anyone listing it. **The rule is positive**: the first argument is a fault
unless it is one of these, and an interpolated value is a fault unless it is one of those.

The first argument (`player`) is
* a string, an f-string, or two of them joined;
* a module constant that is one of these;
* a local of the same function that is assigned only these (`msg = f"..."; raise OutOfScopeError(msg)`), found by the test;
* a call of a sentence maker: `mod_words`, `mod_words_of`, `base_words` (the game's words for a mod and a base, `crafting_system.items.words`) or a
  helper of the same module whose every `return` is one of these (the test reads the helper the same way).
Anything else (a parameter, a bare name it cannot resolve, `str(e)`, a call it does not know, a starred argument) is a fault.

A value written into an f-string is
* a number: a literal, `len(...)`, `int(...)`, arithmetic on numbers, a module constant that is one, a name of the same function assigned one, a
  parameter annotated `int` or `float`, an attribute that is a number (`item_level`, `grade`, ...), a subscript of a name annotated as a mapping to `int`;
* words: a call of a sentence maker, the name an action gives itself (`.label(...)`), an attribute that is a word (`.name`, `.value`, `.item_class`, ...),
  a name or an expression assigned only words, or a parameter named in `WORDS_BY_CONTRACT` with the reason (its callers' arguments are read too);
* an `if`/`or` of these.
A bare name that holds an id, a mod, a family or a key (`family`, `key`, `mod`), `', '.join(...)` of such, an exception (found from the `except ... as
name` handlers, not by its name) and `str(e)` are faults.

Also: the keyword is `detail` only and holds a string; the constant words hold no internal name of `tests/oracle/page_lint.py` (`faults_in`) and none of
the developer's words; the reasons handed to `refuse_unmodelled` are read as sentences; an alias of an import (`... import OutOfScopeError as G`), a
class derived from the family anywhere in `src/`, and a call anywhere in `src/` are found. Fixtures plant each bad shape and each must be found.

Left out until #626 lands, with the reason: `abstraction/_pattern.py`, which the coder of #626 is changing at the same time (issue #647). The test
fails when that file no longer has a fault, so the exemption cannot outlive the fix.
"""

import ast
import importlib
import pkgutil
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from test_cli_player_words import faults_in

import crafting_system
from crafting_system.abstraction import EstimateRefused
from crafting_system.actions import OutOfScopeError

SRC = Path(crafting_system.__file__).resolve().parent

PATTERN_ISSUE = 647  # the follow-up of #557 for the files #626 changes (`abstraction/_pattern.py`)
EXEMPT = {"abstraction/_pattern.py": PATTERN_ISSUE}

MAKERS = {"mod_words", "mod_words_of", "base_words"}  # the functions that say an id as the game does (`crafting_system.items.words`)
LABEL = "label"  # `action.label(data)`: the name an action gives itself, "Exalted Orb"
NUMBER_CALLS = {"len", "int", "float", "round", "abs", "sum", "min", "max"}
WORD_ATTRS = {"name", "value", "item_class", "LABEL", "version"}  # `essence.name`, `side.value`, `base.item_class`, `data.version`
NUMBER_ATTRS = {"item_level", "grade", "number", "tier_from_top", "required_level", "donor_level", "percent", "budget"}
WORDS_BY_CONTRACT: dict[tuple[str, str, str], str] = {  # (file, function, parameter) -> why its words are read elsewhere
    ("actions/draw.py", "refuse_unmodelled", "jewel_reason"): "the reason is an argument of the call: every call's argument is read as a sentence (`reasons_in`)",
    ("actions/fossil.py", "_glyphic_choices", "name"): "the fossil's name in the game, passed by its callers as `record.name`",
    ("actions/harvest_augment.py", "_swap_outcomes", "target"): "the element the swap goes to (\"cold\", \"lightning\"), a literal of the three callers",
    ("actions/recombinator.py", "_check", "who"): "\"item in hand\" or \"donor\", the two literals of the callers",
    ("actions/socket_orbs.py", "_accept", "what"): "the orb's name in the game, a string of the callers (\"Orb of Fusing\")",
}
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
    for module in pkgutil.walk_packages(crafting_system.__path__, "crafting_system."):
        if not module.name.endswith("__main__"):  # a command, not a library: importing it runs it
            importlib.import_module(module.name)


load_every_module()
FAMILY = {cls.__name__ for cls in derived(OutOfScopeError) | derived(EstimateRefused)}  # found by the classes themselves


# --- a module as the reader sees it --------------------------------------------------------------------------------------------


@dataclass
class Module:
    path: str
    tree: ast.Module
    constants: dict[str, ast.expr] = field(default_factory=dict)  # module-level `NAME = <expr>`
    aliases: dict[str, str] = field(default_factory=dict)  # local name -> the name it was imported as
    functions: dict[str, list[ast.FunctionDef]] = field(default_factory=dict)  # every def by name, methods included
    parents: dict[ast.AST, ast.AST] = field(default_factory=dict)
    family: set[str] = field(default_factory=set)

    @classmethod
    def of(cls, path: str, source: str, family: set[str] | None = None) -> "Module":
        tree = ast.parse(source)
        found = cls(path, tree)
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                found.parents[child] = node
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                found.functions.setdefault(node.name, []).append(node)
            if isinstance(node, ast.ImportFrom | ast.Import):
                for each in node.names:
                    found.aliases[each.asname or each.name.split(".")[0]] = each.name.split(".")[-1]
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found.constants[target.id] = node.value
        found.family = set(FAMILY if family is None else family)
        changed = True
        while changed:  # a class derived from the family, defined in this module, is in it
            changed = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name not in found.family and any(found.named(base) in found.family for base in node.bases):
                    found.family.add(node.name)
                    changed = True
        return found

    def named(self, node: ast.expr) -> str | None:
        """The name a callee or a base is known by, an alias resolved: `G` imported as `OutOfScopeError as G` is `OutOfScopeError`."""
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return self.aliases.get(node.attr, node.attr)
        return None

    def function_around(self, node: ast.AST) -> ast.FunctionDef | None:
        while node in self.parents:
            node = self.parents[node]
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                return node
        return None

    def sites(self) -> list[ast.Call]:
        """Every call of a class of the family, anywhere in the module (a `raise`, a `return`, an assignment)."""
        return [node for node in ast.walk(self.tree) if isinstance(node, ast.Call) and self.named(node.func) in self.family]


@dataclass
class Reading:
    fixed: list[str] = field(default_factory=list)
    faults: list[str] = field(default_factory=list)

    def __iadd__(self, other: "Reading") -> "Reading":
        self.fixed += other.fixed
        self.faults += other.faults
        return self


class Reader:
    """Reads an expression as a sentence or as a value of a sentence, in the scope of one function, and says what it cannot read."""

    def __init__(self, module: Module, function: ast.FunctionDef | None, depth: int = 0) -> None:
        self.module, self.function, self.depth = module, function, depth
        self.caught = {node.name for node in ast.walk(function or module.tree) if isinstance(node, ast.ExceptHandler) and node.name}
        self.seen: set[str] = set()  # names being resolved: a name that assigns itself is a fault, not a loop

    # -- what a name stands for in this function -------------------------------------------------------------------------------

    def assigned(self, name: str) -> list[ast.expr] | None:
        """The values assigned to `name` in the function (all of them), or None when it is not a plain local; a parameter and a loop name are not."""
        if self.function is None:
            return None
        values: list[ast.expr] = []
        for node in ast.walk(self.function):
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                values.append(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name and node.value is not None:
                values.append(node.value)
        return values or None

    def parameter(self, name: str) -> ast.arg | None:
        if self.function is None:
            return None
        args = self.function.args
        return next((arg for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs] if arg.arg == name), None)

    def annotation_of_local(self, name: str) -> ast.expr | None:
        if self.function is None:
            return None
        return next(
            (node.annotation for node in ast.walk(self.function) if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name),
            None,
        )

    # -- a sentence -----------------------------------------------------------------------------------------------------------------

    def sentence(self, node: ast.expr) -> Reading:
        match node:
            case ast.Constant(value=str() as text):
                return Reading([text])
            case ast.JoinedStr():
                reading = Reading()
                for part in node.values:
                    if isinstance(part, ast.Constant):
                        reading.fixed.append(str(part.value))
                    elif isinstance(part, ast.FormattedValue):
                        reading.faults += self.value(part.value)
                return reading
            case ast.BinOp(op=ast.Add()):
                reading = self.sentence(node.left)
                reading += self.sentence(node.right)
                return reading
            case ast.IfExp():
                reading = self.sentence(node.body)
                reading += self.sentence(node.orelse)
                return reading
            case ast.BoolOp():
                reading = Reading()
                for each in node.values:
                    reading += self.sentence(each)
                return reading
            case ast.Name():
                return self.name_as_sentence(node.id)
            case ast.Call():
                return self.call_as_sentence(node)
        return Reading(faults=[f"`{ast.unparse(node)}` is not a sentence (a string, an f-string, a constant, a local of words or a call of a sentence maker)"])

    def name_as_sentence(self, name: str) -> Reading:
        if name in self.caught:
            return Reading(faults=[f"`{name}` is an exception caught by this code: its text goes to `detail`"])
        if name in self.seen:
            return Reading(faults=[f"`{name}` is defined by itself"])
        values = self.assigned(name)
        if values is not None:
            self.seen.add(name)
            reading = Reading()
            for value in values:
                reading += self.sentence(value)
            self.seen.discard(name)
            return reading
        if name in self.module.constants and self.parameter(name) is None:
            return Reading(*Module_constant_reading(self, name))
        if self.parameter(name) is not None:
            return self.parameter_words(name)
        return Reading(faults=[f"`{name}` cannot be resolved to words (it is not a constant or a local assigned one)"])

    def parameter_words(self, name: str) -> Reading:
        where = (self.module.path, self.function.name if self.function else "", name)
        if where in WORDS_BY_CONTRACT:
            return Reading()
        return Reading(faults=[f"the parameter `{name}` holds words nobody has read (add it to WORDS_BY_CONTRACT with the reason, or build the sentence here)"])

    def call_as_sentence(self, call: ast.Call) -> Reading:
        name = self.module.named(call.func)
        if name in MAKERS or (name == LABEL and isinstance(call.func, ast.Attribute)):
            return Reading()
        if name is not None and self.depth < 3 and name in self.module.functions and name not in {"str", "repr", "format", "join"}:
            reading = Reading()
            for definition in self.module.functions[name]:
                returns = [node.value for node in ast.walk(definition) if isinstance(node, ast.Return) and node.value is not None]
                if not returns:
                    reading.faults.append(f"the helper `{name}` returns nothing")
                inner = Reader(self.module, definition, self.depth + 1)
                for value in returns:
                    reading += inner.sentence(value)
            return reading
        return Reading(faults=[f"the call `{ast.unparse(call)}` is not a sentence maker (mod_words, mod_words_of, base_words, or a helper of this module whose returns are sentences)"])

    # -- a value written into a sentence --------------------------------------------------------------------------------------

    def value(self, node: ast.expr) -> list[str]:
        """Why `node` may not be written into a sentence (empty: it is a number or words)."""
        match node:
            case ast.Constant(value=str() | int() | float()):
                return []
            case ast.BinOp() | ast.UnaryOp() | ast.BoolOp() | ast.Compare():
                return [fault for child in ast.iter_child_nodes(node) if not isinstance(child, ast.operator | ast.unaryop | ast.boolop | ast.cmpop) for fault in self.value(child)]
            case ast.IfExp():
                return [*self.value(node.body), *self.value(node.orelse)]
            case ast.JoinedStr():
                return self.sentence(node).faults
            case ast.Attribute():
                return [] if node.attr in WORD_ATTRS | NUMBER_ATTRS else [f"the attribute `{ast.unparse(node)}` is not known to be words or a number (an id? a mod?)"]
            case ast.Name():
                return self.name_as_value(node.id)
            case ast.Subscript():
                if isinstance(node.value, ast.Attribute) and node.value.attr == "value":
                    return []  # a value of a rule of the registry (`FUSING_GROUP_SIZE_WEIGHTS.value["at_quality"]`): a figure
                if isinstance(node.value, ast.Name):
                    note = self.annotation_of_local(node.value.id)
                    if note is not None and "int" in ast.unparse(note):
                        return []
                return [f"the subscript `{ast.unparse(node)}` is not known to be a number"]
            case ast.Call():
                return self.call_as_value(node)
        return [f"`{ast.unparse(node)}` cannot be written into a sentence"]

    def name_as_value(self, name: str) -> list[str]:
        if name in self.caught:
            return [f"`{name}` is an exception caught by this code: its text goes to `detail`"]
        if name in self.seen:
            return [f"`{name}` is defined by itself"]
        values = self.assigned(name)
        if values is not None:
            self.seen.add(name)
            faults = [fault for value in values for fault in self.value(value)]
            self.seen.discard(name)
            return faults
        argument = self.parameter(name)
        if argument is not None:
            note = ast.unparse(argument.annotation) if argument.annotation is not None else ""
            if note in {"int", "float"}:
                return []
            return self.parameter_words(name).faults
        if name in self.module.constants:
            return self.value(self.module.constants[name]) if not isinstance(self.module.constants[name], ast.Call) else []
        return [f"the name `{name}` holds an id, a key or an object the test cannot read as words or a number (say it with mod_words / base_words)"]

    def call_as_value(self, call: ast.Call) -> list[str]:
        name = self.module.named(call.func)
        if name in NUMBER_CALLS:
            return [fault for each in call.args for fault in self.value(each)] if name != "len" else []
        if name == "getattr" and len(call.args) == 3 and isinstance(call.args[2], ast.Constant) and isinstance(call.args[2].value, int | float):
            return []
        return self.call_as_sentence(call).faults


def Module_constant_reading(reader: Reader, name: str) -> tuple[list[str], list[str]]:
    """(fixed words, faults) of the module constant `name`, read as a sentence in the module's own scope."""
    reading = Reader(reader.module, None, reader.depth).sentence(reader.module.constants[name])
    return reading.fixed, reading.faults


# --- the rule -----------------------------------------------------------------------------------------------------------------


def faults_of_words(reading: Reading) -> list[str]:
    text = " ".join(reading.fixed)
    found = list(reading.faults)
    found += faults_in(text)
    found += [f"a developer's word: {each.group(0)}" for each in DEVELOPER_WORDS.finditer(text)]
    if not reading.fixed and not reading.faults:
        found.append("no words")
    return found


def faults_of_site(module: Module, call: ast.Call) -> list[str]:
    """What is wrong with one call that makes a model-gap error: `player` is the first argument, `detail` the only keyword, and it is a player's sentence."""
    if not call.args:
        return ["no player sentence: the first argument is the sentence a person reads"]
    if len(call.args) > 1:
        return ["more than one positional argument: the developer's text is the keyword `detail`"]
    if isinstance(call.args[0], ast.Starred):
        return ["a starred argument: the player sentence must be written out"]
    found = []
    keywords = [keyword.arg for keyword in call.keywords]
    if keywords not in ([], ["detail"]):
        found.append(f"keywords {keywords}: only `detail` is allowed")
    for keyword in call.keywords:
        if keyword.arg == "detail" and (
            (isinstance(keyword.value, ast.Constant) and not isinstance(keyword.value.value, str)) or isinstance(keyword.value, ast.List | ast.Tuple | ast.Dict | ast.Set)
        ):
            found.append(f"`detail={ast.unparse(keyword.value)}` is not a string")
    reader = Reader(module, module.function_around(call))
    return found + faults_of_words(reader.sentence(call.args[0]))


def reasons_in(module: Module) -> list[tuple[int, ast.expr]]:
    """The jewel reason of each `refuse_unmodelled(data, item, reason)`: a sentence that ends up as a cause."""
    found = []
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Call) and module.named(node.func) == "refuse_unmodelled":
            given = node.args[2] if len(node.args) > 2 else next((k.value for k in node.keywords if k.arg == "jewel_reason"), None)
            if given is not None:
                found.append((node.lineno, given))
    return found


def faults_of_module(module: Module) -> list[str]:
    found = [f"{module.path}:{call.lineno}: {fault}" for call in module.sites() for fault in faults_of_site(module, call)]
    for line, node in reasons_in(module):
        reader = Reader(module, module.function_around(node))
        found += [f"{module.path}:{line}: the jewel reason: {fault}" for fault in faults_of_words(reader.sentence(node))]
    return found


def check(source: str, path: str = "planted.py") -> list[str]:
    return faults_of_module(Module.of(path, source))


def every_module() -> list[Module]:
    return [Module.of(path.relative_to(SRC).as_posix(), path.read_text(encoding="utf-8")) for path in sorted(SRC.rglob("*.py"))]


MODULES = every_module()


# --- the rule on planted sites ------------------------------------------------------------------------------------------------

PLANTED = {  # a name -> (the source, what the rule says about it)
    "an id in an f-string": ('def f(mod):\n    raise OutOfScopeError(f"a roll limit on {mod.id} is not modelled")', "the attribute `mod.id`"),
    "a mod id attribute": ('def f(entry):\n    raise OutOfScopeError(f"no rule for {entry.mod_id}")', "the attribute `entry.mod_id`"),
    "an id of self": ('def f(self):\n    raise OutOfScopeError(f"{self.donor_mod} cannot be held")', "the attribute `self.donor_mod`"),
    "an ADR number": ('def f():\n    raise OutOfScopeError("the item is not modelled (ADR-0023)")', "an ADR number"),
    "a workflow word": ('def f():\n    raise OutOfScopeError("a start item with a double veil is out of scope (grill B2)")', "a workflow word"),
    "a ticket number": ('def f():\n    raise OutOfScopeError("the planner does not price them yet (ticket #212)")', "a ticket number"),
    "a game mod id": ('def f():\n    raise OutOfScopeError("the mod is IncreasedLifeEssence6")', "a game mod id"),
    "a snake_case token": ('def f():\n    raise EstimateRefused("see the size_estimate module")', "a snake_case token"),
    "a developer's word": ('def f():\n    raise OutOfScopeError("the kernel averages over one input")', "a developer's word: kernel"),
    "a local with an id": ('def f(mod):\n    msg = f"a roll limit on {mod.id} is not modelled"\n    raise OutOfScopeError(msg)', "the attribute `mod.id`"),
    "a local with an ADR number": ('def f():\n    msg = "not modelled (ADR-0023)"\n    raise OutOfScopeError(msg)', "an ADR number"),
    "a local built in two steps": ('def f(mod):\n    msg = "a roll limit on "\n    msg = msg + f"{mod.id}"\n    raise OutOfScopeError(msg)', "the attribute `mod.id`"),
    "a helper that is not read": ("def f(mod):\n    raise OutOfScopeError(_cause(mod))", "the call `_cause(mod)`"),
    "a method that is not read": ("def f(self, mod):\n    raise OutOfScopeError(self._describe(mod))", "the call `self._describe(mod)`"),
    "a helper that returns an id": ('def _cause(mod):\n    return f"no rule for {mod.id}"\n\n\ndef f(mod):\n    raise OutOfScopeError(_cause(mod))', "the attribute `mod.id`"),
    "a bare family": ('def f(family):\n    raise OutOfScopeError(f"no rule for {family}")', "the parameter `family`"),
    "a bare key": ('def f(key):\n    raise OutOfScopeError(f"no rule for {key}")', "the parameter `key`"),
    "a bare mod object": ('def f(mod):\n    raise OutOfScopeError(f"no rule for {mod}")', "the parameter `mod`"),
    "a bare name of nowhere": ('def f():\n    raise OutOfScopeError(f"no rule for {family}")', "holds an id, a key or an object"),
    "a local that holds a key": ('def f(mod):\n    fam = mod.families[0]\n    raise OutOfScopeError(f"no rule for {fam}")', "is not known to be a number"),
    "a joined list": ('def f(mods):\n    raise OutOfScopeError(f"no rule for {\', \'.join(sorted(mods))}")', "is not a sentence maker"),
    "an exception in an f-string": ('def f():\n    try:\n        g()\n    except ValueError as e:\n        raise OutOfScopeError(f"{e}")', "an exception caught by this code"),
    "an exception under another name": ('def f():\n    try:\n        g()\n    except ValueError as boom:\n        raise OutOfScopeError(f"it failed: {boom}")', "an exception caught by this code"),
    "str of an exception": ('def f():\n    try:\n        g()\n    except ValueError as e:\n        raise OutOfScopeError(str(e))', "the call `str(e)`"),
    "a parameter as the sentence": ("def f(text):\n    raise OutOfScopeError(text)", "the parameter `text`"),
    "a detail that is a number": ('def f():\n    raise OutOfScopeError("ok", detail=1)', "is not a string"),
    "a detail that is a list": ('def f():\n    raise OutOfScopeError("ok", detail=["a"])', "is not a string"),
    "a starred argument": ("def f(a):\n    raise OutOfScopeError(*a)", "a starred argument"),
    "no argument": ("def f():\n    raise OutOfScopeError()", "no player sentence"),
    "two positional arguments": ('def f():\n    raise OutOfScopeError("a sentence", "and the detail as a second argument")', "more than one positional"),
    "player as a keyword": ('def f():\n    raise OutOfScopeError("a sentence", player="x")', "keywords"),
    "another keyword": ('def f():\n    raise OutOfScopeError("a sentence", message="x")', "keywords"),
    "an aliased import": ('from crafting_system.actions import OutOfScopeError as Gap\n\n\ndef f(mod):\n    raise Gap(f"no rule for {mod.id}")', "the attribute `mod.id`"),
    "a module attribute": ('def f(mod):\n    raise errors.OutOfScopeError(f"no rule for {mod.id}")', "the attribute `mod.id`"),
    "a subclass defined in the module": ('class Mine(OutOfScopeError):\n    pass\n\n\ndef f(mod):\n    raise Mine(f"no rule for {mod.id}")', "the attribute `mod.id`"),
    "a subclass of a subclass": ('class Mine(OutOfScopeError):\n    pass\n\n\nclass Yours(Mine):\n    pass\n\n\ndef f():\n    raise Yours("see ADR-0023")', "an ADR number"),
    "an error made and returned": ('def f(mod):\n    return OutOfScopeError(f"no rule for {mod.id}")', "the attribute `mod.id`"),
    "a reason of the jewel": ('def f(data, item):\n    refuse_unmodelled(data, item, "see ADR-0023")', "an ADR number"),
    "a constant it names": ('_BAD = "see ADR-0023"\n\n\ndef f():\n    raise OutOfScopeError(_BAD)', "an ADR number"),
}


@pytest.mark.parametrize("name", sorted(PLANTED))
def test_a_site_without_player_words_is_found(name):
    source, fault = PLANTED[name]
    found = check(source)
    assert any(fault in each for each in found), (name, found)


GOOD = [
    'def f():\n    raise OutOfScopeError("a family with mods on both sides of the item (a jewel) is not modelled yet")',
    'def f(item):\n    raise OutOfScopeError(f"the item is {item.rarity.value}, and the model has no rule for that", detail=f"{item.mod.id} ADR-0023")',
    'def f(mod):\n    raise OutOfScopeError(f"a roll limit on a mod ({mod_words(mod)}) is not modelled yet", detail=f"mod {mod.id}")',
    'def f(data, donor):\n    raise OutOfScopeError(f"the input is an item on {base_words(data, donor.base_id)} at item level {donor.item_level}")',
    'def f(data, entry):\n    raise OutOfScopeError(f"{mod_words_of(data, entry.mod_id)} is not an influence mod of {self.donor_influence.value}")',
    'def f():\n    msg = f"{len(wants)} items"\n    raise OutOfScopeError(msg)',
    'def f(mod):\n    msg = "a roll limit on " + mod_words(mod)\n    raise OutOfScopeError(msg)',
    'def _cause(mod):\n    return f"no rule for {mod_words(mod)}"\n\n\ndef f(mod):\n    raise OutOfScopeError(_cause(mod))',
    '_WHY = "a pool draw is not modelled"\n\n\ndef f():\n    raise OutOfScopeError(_WHY)',
    'def f(action, data):\n    raise OutOfScopeError(f"{action.label(data)} has no rule")',
    'def f(count: int):\n    raise OutOfScopeError(f"the item holds {count} strands")',
    'from crafting_system.actions import OutOfScopeError as Gap\n\n\ndef f():\n    raise Gap("an alias of a good site")',
    'def f():\n    raise EstimateRefused("an offered action rerolls the values of mods, which the size estimate has no rule for")',
]


@pytest.mark.parametrize("source", GOOD)
def test_a_site_with_player_words_passes(source):
    assert check(source) == [], source


def test_the_family_is_found_by_the_classes_and_by_the_syntax_tree_not_by_a_list():
    assert {"OutOfScopeError", "ConsumesInputsError", "BlockHoldsMetamod", "EstimateRefused"} <= FAMILY


def test_an_error_of_the_family_needs_its_player_sentence_to_be_made():
    with pytest.raises(TypeError):
        OutOfScopeError()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        EstimateRefused()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        OutOfScopeError("ok", detail=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        OutOfScopeError(7)  # type: ignore[arg-type]
    error = OutOfScopeError("the sentence", detail="ADR-0023: the developer's text")
    assert str(error) == error.player == "the sentence" and error.detail == "ADR-0023: the developer's text"
    assert OutOfScopeError("only a sentence").detail == "only a sentence"


# --- every site of the code ----------------------------------------------------------------------------------------------------

CHECKED = [module for module in MODULES if module.path not in EXEMPT]


def test_the_reading_finds_the_sites_it_is_meant_to_read():
    found = {module.path: len(module.sites()) for module in CHECKED}
    assert sum(found.values()) > 80
    assert found["abstraction/_kernel.py"] >= 18 and found["actions/fossil.py"] >= 4 and found["abstraction/_coarse.py"] >= 9
    assert "abstraction/_pattern.py" not in found
    assert any(path.startswith("cli/") for path in found) and any(path.startswith("items/") for path in found)  # the whole of `src/` is read, not two folders
    assert sum(len(reasons_in(module)) for module in CHECKED) >= 4  # the jewel reasons of the two harvest crafts and the two veiled actions


@pytest.mark.parametrize("module", CHECKED, ids=lambda module: module.path)
def test_every_site_gives_a_sentence_a_player_can_read(module):
    assert faults_of_module(module) == []


def test_a_file_left_out_until_its_issue_is_fixed_still_has_a_fault():
    for name, issue in EXEMPT.items():
        module = next(each for each in MODULES if each.path == name)
        assert faults_of_module(module), f"{name} has no fault: take it out of EXEMPT (issue #{issue})"


def test_the_game_words_say_a_mod_by_its_text_and_a_base_by_its_name():
    from items_support import DATA

    from crafting_system.items.words import NO_BASE, NO_TEXT, base_words, mod_words, mod_words_of

    mod = DATA.mods["IncreasedLife1"]
    assert mod_words(mod) == mod_words_of(DATA, "IncreasedLife1") and "IncreasedLife1" not in mod_words(mod)
    assert mod_words_of(DATA, "NoSuchMod1") == NO_TEXT and faults_in(NO_TEXT) == []
    base = next(iter(DATA.base_items.values()))
    assert base_words(DATA, base.id) == base.name
    assert base_words(DATA, "NoSuchBase") == NO_BASE and faults_in(NO_BASE) == []
