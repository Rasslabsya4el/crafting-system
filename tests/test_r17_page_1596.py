"""R17's page says the plan is dearer than the guide (#1596, OR-59; the owner's condition for showing R17 at all, 2026-11-24).

Two faults kept every page of R17 that could be built from its saved plan from saying it:

* `page PLAN --route r17.yaml` refused the route: "unknown action "Intrinsic Catalyst"". The guide's own plan of the route's actions
  (`guide_plan`) was made on the saved plan's own target, which is the target the planner searched: the catalyst quality it leaves to a finish
  after the mods is taken out of it (`_quality_finish`), so no catalyst was offered. It is now made on the target as its file states it
  (`judged_on`'s `target`, the saved target).
* A page built with no `--route` said nothing of the guide. A target that is a reference craft's now has its guide's recorded figure said
  (`reference_guide`, from the route file's `recorded_cost`), on the page command, the plain command and the website.

The small saved plan is R17's Talisman with only its "+1 to Level of all Skill Gems" and its catalyst quality, made with an Orb of
Transmutation, Orbs of Alteration and the Intrinsic Catalyst (milliseconds); it is saved with R17's whole target, as a plan of R17 is.
"""

from __future__ import annotations

import dataclasses
import os
import re
from html import unescape
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import make_plan, reference_guide
from crafting_system.cli._page_main import page_main
from crafting_system.cli._plan_file import save_plan
from crafting_system.cli._route import recorded_cost_of, route_actions
from crafting_system.cli._route_view import judged_on
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

CLASSIC_OFFERS = True  # tests/conftest.py: this module plans a part of a real route (#886)

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "targets" / "r17-lightning-talisman.yaml"
ROUTE = ROOT / "examples" / "routes" / "r17-lightning-talisman.yaml"
PRICES = ROOT / "tests" / "fixtures" / "prices" / "references-allflame-2026-07-31.json"
R12 = ROOT / "examples" / "targets" / "r12-lightning-amulet.yaml"
RECORDED = "34,099.35 Chaos (the figure recorded for it: its steps as written do not finish on this item)"
CATALYST = "Intrinsic Catalyst"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def target(data):
    return load_target(TARGET, data)


@pytest.fixture(scope="module")
def small(data, target):
    """A plan of R17's Talisman with its first leaf and its quality only: the quality left to a finish, as on R17's own plan."""
    part = dataclasses.replace(target, requirements=target.requirements[:1])
    return make_plan(data, part, load_price_file(PRICES), methods=("Orb of Transmutation", "Orb of Alteration", CATALYST))


def _words(page: Path) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page.read_text(encoding="utf-8"))))


def test_the_guide_is_priced_on_the_target_as_its_file_states_it(data, target, small):
    labels = route_actions(ROUTE)
    assert CATALYST in labels
    assert target.quality is not None and small.target.quality is None  # the plan searched its mods; the quality is its finish
    assert CATALYST not in {priced.label for priced in small.offers}
    judged = judged_on(small, labels, data, target)
    assert judged is not small and judged.target.quality == target.quality
    assert CATALYST in {priced.label for priced in judged.offers}


def test_a_reference_craft_s_target_has_its_guide_s_recorded_figure(data, target, tmp_path):
    assert reference_guide(data, target) == 34_099.35
    moved = dataclasses.replace(target, price_file=tmp_path / "elsewhere.json", actions=("Exalted Orb",))  # neither is the item
    assert reference_guide(data, moved) == 34_099.35
    assert reference_guide(data, dataclasses.replace(target, item_level=84)) is None  # another item: not the reference's
    assert reference_guide(data, load_target(R12, data)) is None  # R12's guide finishes: its cost is its route's own, given with --route
    assert reference_guide(data, target, root=tmp_path) is None  # no reference files there


@pytest.mark.parametrize(
    "text, figure",
    [
        ("recorded_cost: 777.5\nrules:\n  - do: Chaos Orb\n", 777.5),
        ("recorded_cost: 12\nrules: []\n", 12.0),
        ("rules:\n  - do: Chaos Orb\n", None),
        ("recorded_cost: 0\nrules: []\n", None),
        ("recorded_cost: lots\nrules: []\n", None),
        ("recorded_cost: true\nrules: []\n", None),
        ("- not a mapping\n", None),
        ("rules: [unclosed\n", None),
    ],
)
def test_a_recorded_figure_is_read_before_any_plan(tmp_path, text, figure):
    path = tmp_path / "route.yaml"
    path.write_text(text, encoding="utf-8")
    assert recorded_cost_of(path) == figure
    assert recorded_cost_of(tmp_path / "missing.yaml") is None


def test_the_page_command_takes_r17_s_route_and_says_the_guide_s_figure(data, target, small, tmp_path):
    saved = save_plan(tmp_path / "r17.plan", small, target, data, TARGET.name)
    env = dict(os.environ)
    with_route, without = tmp_path / "with.html", tmp_path / "without.html"
    assert page_main([str(saved), "--route", str(ROUTE), "--out", str(with_route)], env=env, data=data) == 0
    assert page_main([str(saved), "--out", str(without)], env=env, data=data) == 0
    for page in (with_route, without):
        words = _words(page)
        assert f"less than the guide's route at {RECORDED}: this plan is cheaper than the guide's." in words, page.name
    assert "R17, Reddit guide" in _words(with_route)  # the guide's route is drawn below the plan
