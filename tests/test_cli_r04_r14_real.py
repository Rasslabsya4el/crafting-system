"""R04 and R14 on the real 3.29.3.3 dump, at the committed prices (ticket #70).

R04 is the Insanity-fractured additional-arrow Penetrating Arrow Quiver, R14 the Toxic Rain Hunter bow. What the ticket
asked for and what was measured (see the pull request): the targets, the start items at their prices, the actions the
guides use, the guides' routes, and the published odds all exist and are checked here. The planner's policy for either
route was NOT produced: R04's exact graph holds 177,242 states and 535,910,746 transitions (a 16 GB runner is out of
memory in about ten minutes), R14's holds at least 570,000 states, and neither has an approximate level, because both
model an Attack/Caster metamod (ADR-0023, #69). The CLI says so, which `test_the_default_run_is_refused...` pins.
These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`; CI fetches it) and skip cleanly without it.
"""

import math
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import PlanError, When, load_route, make_plan
from crafting_system.cli._benchmark import BENCHMARKS, run_route
from crafting_system.cli._benchmark_outcomes import published_outcomes
from crafting_system.cli._route_sim import simulate_route
from crafting_system.config import find_project_root, load_config
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
ROUTES = {
    "R04": ("examples/targets/r04-penetrating-quiver.yaml", "examples/routes/r04-penetrating-quiver.yaml"),
    "R14": ("examples/targets/r14-hunter-bow.yaml", "examples/routes/r14-hunter-bow.yaml"),
}
OFFERS = {
    "R04": {
        "Essence of Insanity", "Deafening Essence of Rage", "Orb of Annulment", "Fracturing Orb", "Exalted Orb",
        "Remove Crafted Mods", "Bench craft Cannot roll Attack Modifiers", "restart",
    },
    "R14": {
        "Orb of Transmutation", "Orb of Alteration", "Orb of Augmentation", "Regal Orb", "Orb of Annulment", "Exalted Orb",
        "Remove Crafted Mods", "Bench craft Can have up to 3 Crafted Modifiers", "Bench craft Cannot roll Attack Modifiers",
        "Bench craft +2 to Level of Socketed Support Gems", "Bench craft +#% to Chaos Damage over Time Multiplier", "restart",
    },
}
START = {"R04": ("Penetrating Arrow Quiver (ilvl 81)", "poe.ninja", 9.0), "R14": ("Thicket Bow (ilvl 78, Hunter)", "trade-api", 13.0)}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def prices():
    return load_price_file(PRICES)


@pytest.fixture(scope="module", params=["R04", "R14"])
def route_id(request):
    return request.param


@pytest.fixture(scope="module")
def unsolved(data, prices, route_id):
    """The plan of the route with nothing solved: its offers, abstraction and start item."""
    return make_plan(data, load_target(ROOT / ROUTES[route_id][0], data), prices, solve_it=False)


def test_the_start_item_costs_its_committed_price(unsolved, route_id):
    name, source, chaos = START[route_id]

    assert unsolved.start_price.name == name and unsolved.start_price.source == source
    assert unsolved.start_price.chaos == pytest.approx(chaos)


def test_the_plan_offers_the_guides_actions_all_priced(unsolved, route_id):
    assert {priced.label for priced in unsolved.offers} == OFFERS[route_id]
    assert unsolved.dropped == ()
    assert "chaos-orb" in {name for entry in unsolved.left_out for name in entry.labels}  # named out by the target's `actions:`


def test_an_unsolved_plan_has_no_policy_and_an_infinite_value(unsolved):
    assert unsolved.policy == {} and unsolved.risk is None and unsolved.solve_seconds == 0.0
    assert math.isinf(unsolved.mean_remaining)


def test_the_guides_route_and_its_completed_form_are_read_against_the_offers(unsolved, data, route_id):
    target_path, route_path = ROUTES[route_id]
    as_written = load_route(ROOT / route_path, unsolved, data)
    completed = load_route(ROOT / route_path.replace(".yaml", "-restart.yaml"), unsolved, data)

    same = [(rule.when, rule.do) for rule in as_written.rules]
    assert [(rule.when, rule.do) for rule in completed.rules[: len(same)]] == same
    assert len(completed.rules) == len(as_written.rules) + 1 and completed.rules[-1].do == "restart"
    assert completed.rules[-1].when == When()  # the added rule catches every state the guide's rules do not
    assert as_written.rules[-1].when != When()  # the guide's own rules do not: what they leave out is a gap


def test_the_published_odds_are_recomputed_from_the_actions(data, route_id):
    bench = next(bench for bench in BENCHMARKS if bench.id == route_id)
    found = published_outcomes(data, load_target(ROOT / bench.target, data), bench.outcomes)

    rows = [(row["action"], row["published"], row["computed"], row["matches"]) for row in found]
    if route_id == "R04":
        assert rows == [
            ("Fracturing Orb", "25%", "25%", True),  # the guide's 1 in 4
            ("Exalted Orb", "100%", "100%", True),  # the two prefixes are the only ones the metamod leaves, at any tier
            ("Exalted Orb", "100%", "13%", False),  # ... but at the top tier of each (the owner's reading) it is 2 in 15
            ("Exalted Orb", "100%", "100%", True),  # the second one: Life is on, the Bow Skills damage is the only prefix left
            ("Exalted Orb", "100%", "20%", False),  # ... at its top tier, 1 in 5
        ]
    else:
        assert rows == [
            ("Orb of Annulment", "33%", "33%", True),  # 3 mods: 1 in 3
            ("Orb of Annulment", "50%", "50%", True),  # 2 mods: 1 in 2
            ("Exalted Orb", "100%", "100%", True),  # gems or Chaos Damage over Time, at any tier
            ("Exalted Orb", "100%", "55%", False),  # ... at the top tier of the damage it is 11 in 20
            ("Exalted Orb", "100%", "100%", True),  # the second one: +1 gems is on, Chaos Damage over Time is the only prefix left
            ("Exalted Orb", "100%", "10%", False),  # ... at its top tier, 1 in 10
        ]


def test_benchmark_checks_the_odds_and_leaves_the_heavy_route_unsolved(data, prices, route_id):
    bench = next(bench for bench in BENCHMARKS if bench.id == route_id)

    entry, _ = run_route(bench, data, find_project_root(), load_config({}), prices, None)

    assert entry["solver"] is None and entry["error"].startswith("not solved: ") and "--heavy" in entry["error"]
    assert len(entry["published_odds"]) == len(bench.outcomes)


def test_the_default_run_is_refused_with_the_reason(data, prices, route_id):
    target = load_target(ROOT / ROUTES[route_id][0], data)

    with pytest.raises(PlanError, match=r"no approximate level available.*Attack/Caster tags"):
        make_plan(data, target, prices, budget=60.0)


def test_a_route_can_be_played_on_concrete_items(unsolved, data, route_id):
    route = load_route(ROOT / ROUTES[route_id][1].replace(".yaml", "-restart.yaml"), unsolved, data)

    report = simulate_route(data, unsolved, route, runs=3, seed=1, max_steps=300)

    assert report.runs == 3 and report.successes + report.stopped + report.unfinished == 3
    assert all(cost >= unsolved.start_price.chaos for cost in report.costs)
