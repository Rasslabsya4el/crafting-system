"""R10 with a roll requirement end to end on the real 3.29.3.3 dump (ticket #71).

"Preferably at least 70" Life is asked as `min_roll: [70]` (`examples/targets/r10-fractured-boots-70-life.yaml`).
On the 3.29.3.3 dump 70 is exactly the border of two Life tiers (55..69 and 70..84), so every tier is all or nothing
there; a second target, the same file with 75, cuts a tier (70..84) in the middle, so a drawn Life may roll under
the requirement and a Divine Orb is worth offering. Both are planned at the committed prices and `--verify` replays
the policy with rolled values.

Needs the cached dump (`CRAFTING_CACHE_DIR`, CI fetches it) and skips cleanly without it.
"""

from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import make_plan, verify
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TARGET_70 = ROOT / "examples" / "targets" / "r10-fractured-boots-70-life.yaml"
RUNS = 3_000


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def plan_of(data, path: Path):
    return make_plan(data, load_target(path, data), load_price_file(PRICES))


@pytest.fixture(scope="module")
def plan_70(data):
    return plan_of(data, TARGET_70)


@pytest.fixture(scope="module")
def plan_75(data, tmp_path_factory):
    path = tmp_path_factory.mktemp("r10-75") / "r10-75-life.yaml"
    text = TARGET_70.read_text(encoding="utf-8")
    assert "min_roll: [70]" in text
    path.write_text(text.replace("min_roll: [70]", "min_roll: [75]"), encoding="utf-8")
    return plan_of(data, path)


def test_r10_with_at_least_70_life_reaches_the_goal(plan_70):
    risk = plan_70.risk

    assert risk.success_probability.value == pytest.approx(1.0)
    assert 0.0 < risk.mean.value < float("inf")


def test_verify_agrees_on_r10_with_at_least_70_life(plan_70, data):
    check = verify(data, plan_70, runs=RUNS, seed=11)

    assert check.agrees, check.reason
    assert check.report.successes == RUNS


def test_a_roll_inside_a_tier_makes_the_goal_dearer_and_verify_still_agrees(plan_70, plan_75, data):
    assert plan_75.risk.success_probability.value == pytest.approx(1.0)
    assert plan_75.risk.mean.value > plan_70.risk.mean.value  # a Life of 70..74 no longer counts

    check = verify(data, plan_75, runs=RUNS, seed=11)

    assert check.agrees, check.reason
    assert check.report.successes == RUNS


def test_a_divine_orb_is_offered_for_a_roll_inside_a_tier_and_not_for_a_tier_border(plan_70, plan_75):
    assert any(priced.label == "Divine Orb" for priced in plan_75.offers)
    assert not any(priced.label == "Divine Orb" for priced in plan_70.offers)
