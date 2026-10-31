"""No module outside `actions` names a concrete action class: it uses the contract and the catalog only (ticket #108).

A new method then needs no edit outside `actions`. The check reads the source with `ast`: an import of
a concrete name from `crafting_system.actions`, an import from one of its submodules, or any use of a
concrete name outside `actions` is a violation. The concrete names are found by looking: every class of
`crafting_system.actions` that subclasses `Action`, plus the outcome classes that belong to one action.
"""

import ast
import dataclasses
import inspect
from pathlib import Path

import crafting_system
from crafting_system import actions

PACKAGE = Path(crafting_system.__file__).parent
OUTCOME_CLASSES_OF_ONE_ACTION = {"BenchOutcomes", "ScourOutcomes", "FossilOutcomes", "Mixture"}
LAYERS_THAT_HANDLE_ACTIONS = ("abstraction", "solver", "risk", "simulator", "cli")  # the others know no action
ALLOWED_ACTION_SUBCLASSES_OUTSIDE = {"BuyStartItem"}  # the restart of the planner (cli/_offers.py): no kind, no catalog entry


def concrete_names() -> set[str]:
    classes = {
        name
        for name, value in vars(actions).items()
        if inspect.isclass(value) and issubclass(value, actions.Action) and value is not actions.Action
    }
    return classes | OUTCOME_CLASSES_OF_ONE_ACTION


def kind_specific_fields() -> set[str]:
    """The fields of the concrete actions that the contract does not have (`mod_id`, `fossils`, ...)."""
    fields = set()
    for name in concrete_names() & vars(actions).keys():
        value = getattr(actions, name)
        if dataclasses.is_dataclass(value):
            fields |= {field.name for field in dataclasses.fields(value)}
    return fields - {"data", "retained", "result", "added", "name"}


def is_label(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "label") or (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "label"
    )


def is_string(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def behaviour_violations(source: str, fields: set[str], local_actions: set[str]) -> list[str]:
    """What an action is told by, other than its class name: its label as a string, its class name, a kind-specific attribute, a local subclass."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare) and any(is_label(n) for n in (node.left, *node.comparators)):
            if any(is_string(n) for n in (node.left, *node.comparators)):
                found.append(f"line {node.lineno}: compares a label with a string")
        elif isinstance(node, ast.Attribute) and node.attr in ("__name__", "__qualname__"):
            if isinstance(node.value, ast.Attribute) and node.value.attr == "__class__":
                found.append(f"line {node.lineno}: reads the class name")
            elif isinstance(node.value, ast.Call) and getattr(node.value.func, "id", "") == "type":
                found.append(f"line {node.lineno}: reads the class name")
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("hasattr", "getattr", "setattr"):
            if len(node.args) >= 2 and is_string(node.args[1]) and node.args[1].value in fields:
                found.append(f"line {node.lineno}: looks for the kind-specific attribute {node.args[1].value}")
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("isinstance", "issubclass"):
            used = {n.id for n in ast.walk(node.args[1]) if isinstance(n, ast.Name)} if len(node.args) > 1 else set()
            found.extend(f"line {node.lineno}: tests for the action class {name}" for name in sorted(used & local_actions))
    return found


def actions_defined_outside(source: str) -> set[str]:
    return {
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ClassDef) and any(getattr(base, "id", "") == "Action" for base in node.bases)
    }


def violations(source: str, names: set[str]) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.split(".")
            if module[:2] == ["crafting_system", "actions"] and len(module) > 2:
                found.append(f"line {node.lineno}: imports from the submodule {node.module}")
            if node.level > 0 and module[0] == "actions" and len(module) > 1:
                found.append(f"line {node.lineno}: imports from the submodule {node.module}")
            found.extend(f"line {node.lineno}: imports {alias.name}" for alias in node.names if alias.name in names)
        elif isinstance(node, ast.Import):
            found.extend(
                f"line {node.lineno}: imports the submodule {alias.name}"
                for alias in node.names
                if alias.name.startswith("crafting_system.actions.")
            )
        elif isinstance(node, ast.Name) and node.id in names:
            found.append(f"line {node.lineno}: uses {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in names:
            found.append(f"line {node.lineno}: uses {node.attr}")
    return found


def test_the_concrete_names_are_found():
    names = concrete_names()
    assert {"ChaosOrb", "BenchCraft", "ApplyFossils", "RemoveCraftedMods", "RegalOrb", "BenchOutcomes"} <= names
    assert not names & {"Action", "Outcomes", "Fixed", "Finite", "Kind"}


def test_no_module_outside_actions_names_a_concrete_action_class():
    names = concrete_names()
    problems = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE)
        if relative.parts[0] == "actions":
            continue
        problems.extend(f"{relative.as_posix()}: {text}" for text in violations(path.read_text(encoding="utf-8"), names))
    assert not problems, "\n".join(problems)


def test_no_module_outside_actions_tests_what_an_action_is_by_its_label_class_or_fields():
    sources = {
        path.relative_to(PACKAGE).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(PACKAGE.rglob("*.py"))
        if path.relative_to(PACKAGE).parts[0] in LAYERS_THAT_HANDLE_ACTIONS
    }
    local = set().union(*(actions_defined_outside(text) for text in sources.values())) - ALLOWED_ACTION_SUBCLASSES_OUTSIDE
    fields = kind_specific_fields()
    problems = []
    for name, text in sources.items():
        problems.extend(f"{name}: {found}" for found in behaviour_violations(text, fields, local))
    assert not problems, "\n".join(problems)
    assert {"mod_id", "fossils", "tag"} <= fields
    assert not local, f"an action is defined outside actions: {sorted(local)}"


def test_the_behaviour_check_catches_what_it_is_meant_to():
    fields = {"mod_id"}
    assert behaviour_violations("if action.label == 'Chaos Orb': pass\n", fields, set())
    assert behaviour_violations("if offer.action.label(data) == 'Chaos Orb': pass\n", fields, set())
    assert behaviour_violations("n = type(action).__name__\n", fields, set())
    assert behaviour_violations("n = action.__class__.__name__\n", fields, set())
    assert behaviour_violations("if hasattr(action, 'mod_id'): pass\n", fields, set())
    assert behaviour_violations("isinstance(action, (Mine, Other))\n", fields, {"Mine"})
    assert not behaviour_violations("if action.label == RESTART: pass\nisinstance(x, Item)\n", fields, {"Mine"})
    assert actions_defined_outside("class Mine(Action):\n    pass\n") == {"Mine"}


def test_the_check_catches_what_it_is_meant_to():
    names = concrete_names()
    assert violations("from crafting_system.actions import ChaosOrb, catalog\n", names)
    assert violations("from crafting_system.actions.chaos import ChaosOrb\n", names)
    assert violations("import crafting_system.actions as a\nx = a.BenchCraft('m')\n", names)
    assert violations("import crafting_system.actions.chaos\n", names)
    assert not violations("from crafting_system.actions import Action, catalog\n", names)
