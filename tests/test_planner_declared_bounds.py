"""The floors of the planner start from the bound each fossil set declares (`declared_pbars`, `ApplyFossils.reach_batch`, #1073), through the
planner's entry on two benchmark routes with a few fossils priced and the fossil sets offered.

The declared bound feeds only the floors (a lower figure): it cuts no offer. So the plan and its lower figure must be those of the planner
without it, every set it bounds must still be offered (a set whose chance of the goal's open leaves is 0 looks dominated by any other and is
not dropped: a later bench craft or the restart may still need what it leaves), and the bound must have been asked and used:
* R05 needs `StrengthEssence7_`, an essence-only mod no fossil draws: every set the class bounds declares 0, exactly (its tests compare it
  with the exact chance), so its ratio is infinite and the floors never build its outcomes;
* R12 needs the +1 to Lightning gems mod (spawn weight 200): every set declares a chance above 0 and below 1.
That a declared chance is never below the exact one, with forced mods and Tangled sets, is `tests/test_actions_fossil_reach.py`.

Every test here plans with the CLASSIC offers (`cli_support.CLASSIC_KINDS`, `CLASSIC_OFFERS` below): what a target with no
`actions:` was offered before #886 turned every beta method on, so its records of before hold. It is not a test of the default plan:
with every method on, a real route gives no plan within CI's time and memory, and the heavy benchmark records those plans.
"""

import dataclasses
import importlib
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.budget import Budget
from crafting_system.planner import PlanSettings, _offer_floor, _offer_kinds, plan_target

CLASSIC_OFFERS = True  # tests/conftest.py: this module plans with `cli_support.CLASSIC_KINDS` (#886)

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
FOSSILS = {"R05": ("Metallic Fossil", "Prismatic Fossil", "Pristine Fossil", "Scorched Fossil"), "R12": ("Metallic Fossil", "Prismatic Fossil", "Scorched Fossil")}


def plan_with_fossils(route: str, monkeypatch, declared: bool):
    from crafting_system.cli import _benchmark
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    data = real_game_data()
    catalog = importlib.import_module("crafting_system.actions.catalog")
    monkeypatch.setitem(catalog._KINDS, "fossil-set", dataclasses.replace(catalog._KINDS["fossil-set"], opt_in=False))
    names = {record.name for record in data.fossils.values() if record.name}
    prices = load_price_file(PRICES)
    prices = dataclasses.replace(prices, prices={name: entry for name, entry in prices.prices.items() if name not in names or name in FOSSILS[route]})
    bench = next(entry for entry in _benchmark.BENCHMARKS if entry.id == route)
    target = load_target(ROOT / bench.target, data)
    asked: list = []
    real = _offer_kinds.declared_bounds

    def spy(*args):
        found = real(*args)
        asked.extend(found)
        return found

    monkeypatch.setattr(_offer_kinds, "declared_bounds", spy)
    if not declared:
        monkeypatch.setattr(_offer_floor, "declared_pbars", lambda *args: None)
    settings = PlanSettings(recipe_starts=False, budget=Budget(aim_seconds=None, seconds=300, memory_mb=None))
    plan = plan_target(data, target, prices, settings)
    labels = sorted(offer.offer.action.label(data) for offer in plan.offers if "Fossil" in offer.offer.action.label(data))
    return plan, labels, asked


@pytest.mark.parametrize("route", ["R05", "R12"])
def test_the_declared_bounds_change_no_plan_and_no_lower_figure_and_drop_no_set(route, monkeypatch):
    plan, labels, asked = plan_with_fossils(route, monkeypatch, declared=True)
    with monkeypatch.context() as inner:
        without, labels_without, _ = plan_with_fossils(route, inner, declared=False)
    sets = 2 ** len(FOSSILS[route]) - 1
    assert len(labels) == sets and labels == labels_without  # every set offered either way: none is cut by its bound
    assert plan.search.stopped is None and without.search.stopped is None
    assert plan.mean_remaining == pytest.approx(without.mean_remaining, rel=1e-9)
    assert plan.search.lower == pytest.approx(without.search.lower, rel=1e-9)
    assert plan.search.lower <= plan.mean_remaining * (1 + 1e-9)
    bounded = [bound for bound in asked if bound is not None]
    assert bounded, "the floors asked the class for its bounds"
    if route == "R05":
        assert all(bound == 0 for bound in bounded)  # the essence-only mod: no set can put it on
    else:
        assert all(0 < bound < 1 for bound in bounded)
