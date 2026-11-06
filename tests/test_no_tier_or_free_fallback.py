"""No tier fallback of 1 and no "a price of 0 means free" path comes back (ticket #453, OR-1, OR-2, OR-6, OR-26).

Two roots, one scan of `src/crafting_system` each (the tree, parsed; nothing is imported or run):

* **A mod outside the tier table has no tier.** A forced, crafted, veiled or fractured mod meets a tier leaf only by its values on the natural
  ladder (`status_of`, ticket #457); the item stores no tier (`ExplicitMod` has none, ticket #484). So nowhere may `get(<mod>, 1)` turn "no
  tier" into tier 1, `tier if tier is not None else 1` may not exist, and no call passes `tier=` a number.
* **A price of 0 is never "free".** A given start item is `start: given` and a bought one has a price above 0 (ticket #505). So no code
  decides on `start_price.chaos` being 0, and no price is made up with `or 0`.

The detectors are tried on bad snippets first, so a scan that cannot fail is caught here (the red half of the test).
"""

import ast
import dataclasses
from pathlib import Path

import pytest

from crafting_system.items import ExplicitMod

SRC = Path(__file__).resolve().parent.parent / "src" / "crafting_system"

PRICE_WORDS = ("start_price", "price_of_start", "start.chaos", "start_chaos")


def _text(node: ast.AST) -> str:
    return ast.unparse(node)


def _is_number(node: ast.AST, *values: int) -> bool:
    return isinstance(node, ast.Constant) and not isinstance(node.value, bool) and isinstance(node.value, int | float) and node.value in values


def _mod_key(node: ast.AST) -> bool:
    """`mod.id`, `mod_id`, `forced.id`, `chosen.id`: the key of a table of mods."""
    text = _text(node).lower()
    return text.endswith(".id") or "mod_id" in text or text.endswith("mod")


def _is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _is_none_check(node: ast.AST) -> bool:
    """`x is None`, `x == None` or `not x`."""
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, ast.Not)
    return isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Is | ast.Eq) and _is_none(node.comparators[0])


def _assigns_tier_1(node: ast.AST) -> bool:
    """`tier = 1` or `tier: int = 1`."""
    if isinstance(node, ast.Assign):
        targets, value = node.targets, node.value
    elif isinstance(node, ast.AnnAssign):
        targets, value = [node.target], node.value
    else:
        return False
    return _is_number(value, 1) and any("tier" in _text(target).lower() for target in targets)


def tier_fallbacks(source: str) -> list[str]:
    """One line per place that turns "no tier" into a tier number."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("get", "setdefault") and node.args:
            owner, key = node.func.value, node.args[0]
            default = node.args[1] if len(node.args) == 2 else next((keyword.value for keyword in node.keywords if keyword.arg == "default"), None)
            if default is not None and _is_number(default, 1) and ("tier" in _text(owner).lower() or _mod_key(key)):
                found.append(f"line {node.lineno}: {_text(node)} gives tier 1 to a mod that has none")
        elif isinstance(node, ast.Call) and _text(node.func) == "getattr" and len(node.args) == 3:
            name, default = node.args[1], node.args[2]
            if isinstance(name, ast.Constant) and isinstance(name.value, str) and "tier" in name.value.lower() and _is_number(default, 1):
                found.append(f"line {node.lineno}: {_text(node)} reads a missing tier as 1")
        elif isinstance(node, ast.If) and _is_none_check(node.test) and "tier" in _text(node.test).lower():
            if any(_assigns_tier_1(inner) for stmt in node.body for inner in ast.walk(stmt)):
                found.append(f"line {node.lineno}: {_text(node.test)} sets a missing tier to 1")
        elif isinstance(node, ast.IfExp) and _is_number(node.orelse, 1) and "tier" in (_text(node.test) + _text(node.body)).lower():
            found.append(f"line {node.lineno}: {_text(node)} reads a missing tier as 1")
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and _is_number(node.values[-1], 1):
            if any("tier" in _text(value).lower() for value in node.values[:-1]):
                found.append(f"line {node.lineno}: {_text(node)} reads a missing tier as 1")
        elif isinstance(node, ast.keyword) and node.arg is not None and node.arg.lower() in ("tier", "min_tier_default"):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int) and not isinstance(node.value.value, bool):
                found.append(f"line {node.value.lineno}: {node.arg}={node.value.value} passes a made-up tier")
    return found


def free_prices(source: str) -> list[str]:
    """One line per place that reads a price of 0 as "free" or makes a price up as 0."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            if any(word in _text(side) for side in sides for word in PRICE_WORDS) and any(_is_number(side, 0) for side in sides):
                found.append(f"line {node.lineno}: {_text(node)} decides on a start price being 0")
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and _is_number(node.values[-1], 0):
            if any(word in _text(value).lower() for value in node.values[:-1] for word in ("price", "cost", "chaos")):
                found.append(f"line {node.lineno}: {_text(node)} makes a missing price 0")
        elif isinstance(node, ast.Dict):
            pairs = zip(node.keys, node.values)
            if any(isinstance(key, ast.Constant) and isinstance(key.value, str) and "start_price" in key.value and _is_number(value, 0) for key, value in pairs):
                found.append(f"line {node.lineno}: {_text(node)} writes a start price of 0")
        elif isinstance(node, ast.Call) and _text(node.func).split(".")[-1] == "StartPrice":
            given = any(keyword.arg == "given" and _text(keyword.value) == "True" for keyword in node.keywords)
            chaos = node.args[1] if len(node.args) > 1 else next((keyword.value for keyword in node.keywords if keyword.arg == "chaos"), None)
            if not given and chaos is not None and _is_number(chaos, 0):
                found.append(f"line {node.lineno}: {_text(node)} is a start price of 0 that is not `given`")
    return found


@pytest.mark.parametrize(
    "source",
    [
        "x = tier_table(data, base).get(forced.id, 1)",
        "x = tiers.get(mod.id, 1)",
        "x = table.get(chosen.id, 1)",
        "x = tier if tier is not None else 1",
        "x = mod_tier(data, base, mod_id) or 1",
        "ExplicitMod(mod_id, values, tier=1)",
        "x = tiers.get(mod_id, 1)",
        "if tier is None:\n    tier = 1",
        "if not mod_tier:\n    mod_tier = 1",
        "x = getattr(m, 'tier', 1)",
        "x = tiers.get(mod.id, default=1)",
        "x = tiers.setdefault(mod.id, 1)",
    ],
)
def test_the_tier_detector_fires_on_a_fallback(source):
    assert tier_fallbacks(source)


@pytest.mark.parametrize(
    "source",
    [
        "x = tiers.get(mod.id)",
        "x = tiers.get(mod.id, None)",
        "x = tiers[mod.id] if mod.id in tiers else None",
        "x = planner.get('max_imprints', 1)",
        "x = tier if tier is not None else 'any'",
        "ExplicitMod(mod_id, values, fractured=True)",
        "if tier is None:\n    tier = 'any'",
        "x = getattr(m, 'tier', None)",
        "x = cache.setdefault(key, [])",
    ],
)
def test_the_tier_detector_lets_the_honest_forms_through(source):
    assert not tier_fallbacks(source)


@pytest.mark.parametrize(
    "source",
    [
        "if plan.start_price.chaos > 0: restart = 1",
        "x = start_price.chaos == 0",
        "if price_of_start.chaos <= 0: pass",
        "x = prices.get(name) or 0",
        "x = entry.chaos or 0.0",
        "x = StartPrice('x', 0.0, 'file')",
        "x = StartPrice(name, chaos=0, source='file')",
        "if plan.start.chaos > 0: pass",
        "x = start_chaos == 0",
        "x = {'start_price': 0}",
    ],
)
def test_the_price_detector_fires_on_a_zero_that_means_free(source):
    assert free_prices(source)


@pytest.mark.parametrize(
    "source",
    [
        "if price.given: pass",
        "x = StartPrice('x', 4.0, 'file')",
        "x = StartPrice(None, 0.0, GIVEN, given=True)",
        "x = row.mean_remaining or 0.0",
        "if self.chaos > 0: pass",
        "x = {'start_price': 4.0}",
    ],
)
def test_the_price_detector_lets_the_honest_forms_through(source):
    assert not free_prices(source)


def _scan(detector) -> list[str]:
    found = []
    for path in sorted(SRC.rglob("*.py")):
        found += [f"{path.relative_to(SRC.parent.parent).as_posix()} {line}" for line in detector(path.read_text(encoding="utf-8"))]
    return found


def test_no_tier_fallback_of_1_is_in_the_source():
    assert _scan(tier_fallbacks) == []


def test_no_price_of_0_means_free_in_the_source():
    assert _scan(free_prices) == []


def test_an_explicit_mod_has_no_tier_field():
    assert "tier" not in {field.name for field in dataclasses.fields(ExplicitMod)}
