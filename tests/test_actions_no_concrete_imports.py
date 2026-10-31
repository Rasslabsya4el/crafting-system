"""No module outside `actions` names a concrete action class: it uses the contract and the catalog only (ticket #108).

A new method then needs no edit outside `actions`. The check reads the source with `ast`: an import of
a concrete name from `crafting_system.actions`, an import from one of its submodules, or any use of a
concrete name outside `actions` is a violation. The concrete names are found by looking: every class of
`crafting_system.actions` that subclasses `Action`, plus the outcome classes that belong to one action.
"""

import ast
import inspect
from pathlib import Path

import crafting_system
from crafting_system import actions

PACKAGE = Path(crafting_system.__file__).parent
OUTCOME_CLASSES_OF_ONE_ACTION = {"BenchOutcomes", "ScourOutcomes", "FossilOutcomes", "Mixture"}


def concrete_names() -> set[str]:
    classes = {
        name
        for name, value in vars(actions).items()
        if inspect.isclass(value) and issubclass(value, actions.Action) and value is not actions.Action
    }
    return classes | OUTCOME_CLASSES_OF_ONE_ACTION


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


def test_the_check_catches_what_it_is_meant_to():
    names = concrete_names()
    assert violations("from crafting_system.actions import ChaosOrb, catalog\n", names)
    assert violations("from crafting_system.actions.chaos import ChaosOrb\n", names)
    assert violations("import crafting_system.actions as a\nx = a.BenchCraft('m')\n", names)
    assert not violations("from crafting_system.actions import Action, catalog\n", names)
