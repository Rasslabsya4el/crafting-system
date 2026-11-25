"""The page says how the plan stands against the guide's route and where the two part, in one block near the top (#1584, OR-46, OR-59).

The crafter named it on seven of nine reference pages (2026-11-25): a page built with no `--route` said nothing of the guide, or only the
figure a route file records (R17). A reference craft's guide's route is now priced on the plan's model (`reference_beside`, as the
benchmark prices it), and the goal card says the two costs, their ratio and the kinds of step whose spend differs most (`against_guide`).

Three cases, each through the page command on a saved plan, as the reference pages are built:

* R12, whose guide's rules finish: a plan of R12's own Lightning reforge only, the guide's route walked on it; the two are the same route,
  so the block says the same cost and names no step.
* R17, whose rules have gaps and whose file records the figure (33,140.41 Chaos): the small plan of `test_r17_page_1596` (Transmutation,
  Alterations, the catalyst); the guide's rules are priced with a restart where they stop, which gives the recorded figure, and the block
  names the steps where the two part. The proof sentence still says the recorded figure as recorded.
* A target that is no reference craft (R12's amulet one item level lower): no guide, no block.
"""

from __future__ import annotations

import dataclasses
import os
import re
from html import escape, unescape
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import make_plan, reference_beside
from crafting_system.cli._page_main import page_main
from crafting_system.cli._plan_file import save_plan
from crafting_system.cli._route_view import AGAINST_GUIDE, RESTART_READING
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

CLASSIC_OFFERS = True  # tests/conftest.py: this module plans a part of a real route (#886)

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "references-allflame-2026-07-31.json"
R12 = ROOT / "examples" / "targets" / "r12-lightning-amulet.yaml"
R17 = ROOT / "examples" / "targets" / "r17-lightning-talisman.yaml"
REFORGE = "Harvest Reforge Lightning"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def _block(page: Path) -> list[str]:
    """The lines of the block against the guide, as the page shows them (empty when the page has none)."""
    html = page.read_text(encoding="utf-8")
    at = html.find(f">{escape(AGAINST_GUIDE)}</div>")
    if at < 0:
        return []
    value = html[at:].split('<div class="k">', 1)[0]
    return [unescape(re.sub(r"<[^>]+>", "", line)).strip() for line in re.findall(r"<div>(.*?)</div>", value)]


def _page(data, plan, target, name: str, tmp_path: Path) -> tuple[Path, str]:
    saved = save_plan(tmp_path / f"{name}.plan", plan, target, data, name)
    out = tmp_path / f"{name}.html"
    assert page_main([str(saved), "--out", str(out)], env=dict(os.environ), data=data) == 0
    return out, unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", out.read_text(encoding="utf-8"))))


@pytest.fixture(scope="module")
def r12(data):
    target = load_target(R12, data)
    return target, make_plan(data, target, load_price_file(PRICES), methods=(REFORGE,))


def test_a_guide_whose_rules_finish_is_walked_on_the_plan_and_the_block_says_the_same_cost(data, r12, tmp_path):
    target, plan = r12
    beside = reference_beside(data, plan, target)
    assert beside is not None and beside.reading == "" and not beside.recorded
    guide, recorded = beside.cost()
    assert guide is not None and not recorded

    page, words = _page(data, plan, target, "r12", tmp_path)

    lines = _block(page)
    assert len(lines) == 1 and lines[0].endswith("the same cost, to within 1%"), lines
    figure = f"{guide:,.2f} Chaos"
    assert f"the guide's route at {figure}" in words or "the same as the guide's route" in words  # the proof sentence says the guide's cost too (OR-59)
    assert f"the guide's route at {figure} (the figure recorded" not in words  # walked on the plan, not recorded


def test_a_guide_with_gaps_is_priced_with_a_restart_and_the_block_names_where_the_two_part(data, tmp_path):
    target = load_target(R17, data)
    part = dataclasses.replace(target, requirements=target.requirements[:1])
    plan = make_plan(data, part, load_price_file(PRICES), methods=("Orb of Transmutation", "Orb of Alteration", "Intrinsic Catalyst"))
    beside = reference_beside(data, plan, target)
    assert beside is not None and beside.reading == RESTART_READING and beside.recorded
    assert beside.cost() == (33_140.41, True)  # the proof sentence keeps the recorded figure (#1596)

    page, words = _page(data, plan, target, "r17", tmp_path)

    lines = _block(page)
    assert lines and f"({RESTART_READING})" in lines[0] and "the guide's route ≈ 33,100 c" in lines[0], lines
    assert 2 <= len(lines) <= 5  # the ratio, then at most three kinds of step and the line of the rest
    assert any("Imprint with the Fenumal Plagued Arachnid" in line for line in lines[1:])  # the guide's dearest step, by name and Chaos
    assert "33,140.41 Chaos (the figure recorded for it: its steps as written do not finish on this item)" in words


def test_a_target_that_is_no_reference_craft_has_no_guide_and_no_block(data, r12, tmp_path):
    target, plan = r12
    other = dataclasses.replace(target, item_level=target.item_level - 1)
    assert reference_beside(data, plan, other) is None

    page, words = _page(data, plan, other, "own", tmp_path)

    assert _block(page) == [] and "guide" not in words.lower()
