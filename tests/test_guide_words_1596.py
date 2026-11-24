"""The plan's cost against the guide's, in plain words (#1596, OR-59): dearer or cheaper, how many times when dearer; and where the guide's
route has gaps (its rules never finish, so it prices nothing), the figure its route file records (`recorded_cost`), said as recorded.

Hand figures for the words; a tiny world for the route file's key: Paua Amulet, a bare rare start, the gem and a Lightning Resistance of any
tier, rerolled with a Chaos Orb (the world of `test_cli_benchmark_divergence.tiny`). A route of "Chaos Orb" at every state finishes; a route
whose one rule is for a magic item leaves the rare start a gap, so it never finishes.
"""

import math
from types import SimpleNamespace

import pytest
from cli_support import price_file
from targets_support import DATA

from crafting_system.cli import evaluate_route, make_plan, parse_route
from crafting_system.cli._route import RouteError
from crafting_system.cli._route_view import guide_figure
from crafting_system.planner._proof_words import _guide_words

CLASSIC_OFFERS = True  # tests/conftest.py: this module plans a tiny target with `cli_support.CLASSIC_KINDS` (#886)

RECORDED = " (the figure recorded for it: its steps as written do not finish on this item)"


def test_a_dearer_plan_says_so_and_how_many_times():
    # R17's figures: the plan at the 1 h net against the guide's recorded figure
    assert _guide_words(59_734.75, 33_140.41, recorded=True) == (
        f" It costs 59,734.75 Chaos in all, 1.80 times the guide's route at 33,140.41 Chaos{RECORDED}: this plan is dearer than the guide's."
    )
    assert _guide_words(1_500.0, 1_000.0) == " It costs 1,500.00 Chaos in all, 1.50 times the guide's route at 1,000.00 Chaos: this plan is dearer than the guide's."


def test_a_cheaper_plan_and_an_equal_one():
    assert _guide_words(4_000.0, 5_000.0) == " It costs 4,000.00 Chaos in all, less than the guide's route at 5,000.00 Chaos: this plan is cheaper than the guide's."
    assert _guide_words(38.801, 38.799) == " It costs 38.80 Chaos in all, the same as the guide's route."  # as the goldens say it
    assert _guide_words(10.0, None) == "" and _guide_words(10.0, math.inf) == "" and _guide_words(math.inf, 10.0) == ""


def test_the_recorded_figure_stands_only_where_the_route_prices_nothing():
    plan = SimpleNamespace(start_price=SimpleNamespace(chaos=533.0))
    finishes = SimpleNamespace(risk=SimpleNamespace(mean=SimpleNamespace(value=1_000.0)))
    gaps = SimpleNamespace(risk=SimpleNamespace(mean=SimpleNamespace(value=math.inf)))
    recorded = SimpleNamespace(recorded_cost=33_140.41)
    plain = SimpleNamespace(recorded_cost=None)
    assert guide_figure(plan, finishes, recorded) == (1_533.0, False)  # the route's own cost, with the start, wins
    assert guide_figure(plan, gaps, recorded) == (33_140.41, True)
    assert guide_figure(plan, gaps, plain) == (None, False)
    assert guide_figure(plan, None, None) == (None, False)


@pytest.fixture(scope="module")
def tiny():
    text = """\
base: Paua Amulet
item_level: 84
requirements:
  - stat: "+1 to Level of all Lightning Skill Gems"
  - family: LightningResistance
    min_tier: any
start_item:
  rarity: rare
start: given
"""
    from crafting_system.targets import parse_target

    target = parse_target(text, DATA, source="tiny.yaml")
    return make_plan(DATA, target, price_file(start=None), judges_route=True)


def test_the_route_file_records_a_figure_and_the_page_words_use_it(tiny):
    walked = parse_route("recorded_cost: 777.5\nrules:\n  - do: Chaos Orb\n", tiny, DATA)
    assert walked.recorded_cost == 777.5
    cost, said = guide_figure(tiny, evaluate_route(tiny, walked, DATA), walked)
    assert not said and math.isfinite(cost) and cost != 777.5  # it finishes: its own cost
    stuck = parse_route("recorded_cost: 777.5\nrules:\n  - when: {rarity: magic}\n    do: Chaos Orb\n", tiny, DATA)
    given = evaluate_route(tiny, stuck, DATA)
    assert given.gaps and guide_figure(tiny, given, stuck) == (777.5, True)
    assert parse_route("rules:\n  - do: Chaos Orb\n", tiny, DATA).recorded_cost is None


@pytest.mark.parametrize("value", ["0", "-5", "lots", "true", ".nan"])
def test_a_recorded_figure_must_be_a_positive_number(tiny, value):
    with pytest.raises(RouteError, match="recorded_cost: must be a positive number of Chaos"):
        parse_route(f"recorded_cost: {value}\nrules:\n  - do: Chaos Orb\n", tiny, DATA)


def test_r17_records_the_guides_figure():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "examples" / "routes" / "r17-lightning-talisman.yaml").read_text(encoding="utf-8")
    assert "\nrecorded_cost: 33140.41\n" in text
