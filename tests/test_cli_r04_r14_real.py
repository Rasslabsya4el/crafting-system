"""R04 and R14 on the real 3.29.3.3 dump, at the committed prices (ticket #70).

R04 is the Insanity-fractured additional-arrow Penetrating Arrow Quiver, R14 the Toxic Rain Hunter bow. What the ticket
asked for and what was measured (see the pull request): the targets, the start items at their prices, the actions the
guides use, the guides' routes, and the published odds all exist and are checked here. The planner's policy for either
route is solved by the packed solver (ticket #374; R04's exact graph holds 177,242 states and 535,910,746 transitions, R14's
816,153 states) and neither has an approximate level, because both model an Attack/Caster metamod (ADR-0023, #69): the
default budget run goes on to the packed solver instead of refusing, which `test_the_decision_finds_no_approximate_level...`
pins. The policies themselves (CLI, `--verify`, `benchmark`) are in `test_cli_r04_r14_heavy.py`, a heavy run.
These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`; CI fetches it) and skip cleanly without it.
"""

import math
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from limits_support import labels_of, of_kind

from crafting_system.actions import DRAW_LABEL
from crafting_system.cli import PlanError, When, load_route, make_plan
from crafting_system.cli._benchmark import BENCHMARKS, run_route
from crafting_system.cli._benchmark_outcomes import PublishedOutcome, published_outcomes
from crafting_system.cli._decide import decide
from crafting_system.cli._plan import _packed_note
from crafting_system.cli._route_sim import route_policy, simulate_route
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
        "Orb of Alteration", "Orb of Augmentation", "Regal Orb", "Orb of Annulment", "Exalted Orb",
        "Remove Crafted Mods", "Bench craft Can have up to 3 Crafted Modifiers", "Bench craft Cannot roll Attack Modifiers",
        "Bench craft +2 to Level of Socketed Support Gems", "Bench craft +(18-20)% to Chaos Damage over Time Multiplier", "restart",
        DRAW_LABEL,  # the bought Magic bow is the item the market sells (ADR-0064): the plan opens with the draw of its mods
    },
}
START = {"R04": ("Penetrating Arrow Quiver [QuiverNew5], normal, item level 81", "poe.ninja", 9.0), "R14": ("Thicket Bow, magic, item level 78-79, Hunter influence", "trade-api", 13.0)}


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
    assert of_kind(unsolved.limits, "unpriced") == []
    assert "Chaos Orb" in labels_of(unsolved.limits, "kinds-not-named")  # named out by the target's `actions:`


def test_an_unsolved_plan_has_no_policy_and_an_infinite_value(unsolved):
    assert unsolved.policy == {} and unsolved.risk is None and unsolved.solve_seconds == 0.0
    assert math.isinf(unsolved.mean_remaining)


def test_the_guides_route_and_its_completed_form_are_read_against_the_offers(unsolved, data, route_id):
    target_path, route_path = ROUTES[route_id]
    as_written = load_route(ROOT / route_path, unsolved, data)
    completed = load_route(ROOT / route_path.replace(".yaml", "-restart.yaml"), unsolved, data)

    same = [(rule.when, rule.do) for rule in as_written.rules]
    assert completed.rules[-1].do == "restart" and completed.rules[-1].when == When()  # the last rule catches every state the rules before it do not
    assert as_written.rules[-1].when != When()  # the guide's own rules do not: what they leave out is a gap
    if route_id == "R14":
        assert [(rule.when, rule.do) for rule in completed.rules[: len(same)]] == same
        assert len(completed.rules) == len(as_written.rules) + 1
        return
    # R04 (ticket #599): a last `restart` alone bought a new quiver at every gap and lost the fractured Pierce (297,863 Chaos against the planner's 69,267).
    # The guide's rules stay, in order, but for step 7, which also asks a free prefix; what is added is a Remove Crafted Mods, an essence and the restart.
    every = [(rule.when, rule.do) for rule in completed.rules]
    assert [pair for pair in every if pair in same] == [pair for pair in same if pair in every]  # the guide's rules that stayed keep their order
    assert [pair[1] for pair in same if pair not in every] == ["Bench craft Cannot roll Attack Modifiers"]
    assert sorted(pair[1] for pair in every if pair not in same) == [
        "Bench craft Cannot roll Attack Modifiers", "Deafening Essence of Rage", "Remove Crafted Mods", "restart",
    ]


def test_the_completed_r04_keeps_the_fractured_pierce_where_the_guide_has_no_word(data, prices):
    """Ticket #599: at the guide's 13 gaps (the metamod on, the prefixes full of the wrong tiers) a last `restart` bought a new quiver and lost the
    fractured Pierce. A player takes the craft off (the game refuses an essence under it) and rerolls with the essence; and does not craft the metamod
    when no prefix is free for the Exalted Orbs that follow it."""
    from crafting_system.items import ExplicitMod, Item, Rarity

    plan = make_plan(data, load_target(ROOT / ROUTES["R04"][0], data), prices, solve_it=False)
    completed = load_route(ROOT / "examples/routes/r04-penetrating-quiver-restart.yaml", plan, data)
    price = {priced.label: priced.cost for priced in plan.offers}
    policy = route_policy(plan, completed, data, skip_refused=True)

    def held(*mod_ids, fractured="AdditionalPierceEssence7"):
        mods = tuple(
            ExplicitMod(mod_id, tuple(min(s.min, s.max) for s in data.mods[mod_id].stats), fractured=mod_id == fractured, crafted=data.mods[mod_id].domain == "crafted")
            for mod_id in mod_ids
        )
        return Item.build(data, base_id="Metadata/Items/Quivers/QuiverNew5", item_level=81, rarity=Rarity.RARE, mods=mods)

    metamod = "IntMasterItemGenerationCannotRollAttackAffixes"
    core = ("AdditionalPierceEssence7", "StrengthEssence7_", "AdditionalArrowQuiver1_")
    wrong_prefixes = ("IncreasedLife1", "DamageWithBowSkills1")  # the lowest tiers: the two Exalted Orbs landed, not on the target's tiers
    assert policy(held(*core, metamod, *wrong_prefixes)).cost == price["Remove Crafted Mods"]  # the guide's gap; before: restart
    assert policy(held(*core, *wrong_prefixes)).cost == price["Deafening Essence of Rage"]  # no prefix free: no metamod craft
    assert policy(held(*core)).cost == price["Bench craft Cannot roll Attack Modifiers"]  # the guide's step 7, two prefixes free
    assert price["restart"] not in {policy(held(*core, metamod, *wrong_prefixes)).cost, policy(held(*core, *wrong_prefixes)).cost}


def test_the_published_odds_are_recomputed_from_the_actions(data, route_id):
    bench = next(bench for bench in BENCHMARKS if bench.id == route_id)
    found = published_outcomes(data, load_target(ROOT / bench.target, data), bench.outcomes)

    rows = [(row["action"], row["published"], row["computed"], row["matches"]) for row in found]
    if route_id == "R04":
        assert rows == [
            ("Fracturing Orb", "25%", "25%", True),  # the guide's 1 in 4
            ("Exalted Orb", "100%", "100%", True),  # the two prefixes are the only ones the metamod leaves, at any tier
            ("Exalted Orb", None, "13%", None),  # ... at the top tier of each (OR-1) it is 2 in 15: the guide's 100% is of the family, so no number is published
            ("Exalted Orb", "100%", "100%", True),  # the second one: Life is on, the Bow Skills damage is the only prefix left
            ("Exalted Orb", None, "20%", None),  # ... at its top tier, 1 in 5: no number published
        ]
    else:
        assert rows == [
            ("Orb of Annulment", "33%", "33%", True),  # 3 mods: 1 in 3
            ("Orb of Annulment", "50%", "50%", True),  # 2 mods: 1 in 2
            ("Exalted Orb", "100%", "100%", True),  # gems or Chaos Damage over Time, at any tier
            ("Exalted Orb", None, "55%", None),  # ... at the top tier of the damage it is 11 in 20: no number published
            ("Exalted Orb", "100%", "100%", True),  # the second one: +1 gems is on, Chaos Damage over Time is the only prefix left
            ("Exalted Orb", None, "10%", None),  # ... at its top tier, 1 in 10: no number published
        ]


def test_no_benchmark_route_writes_one_published_number_on_two_rows_of_the_same_item():
    """The root of #599, checked on every route: the same figure on two rows of one (action, item) means one of the rows reads another event."""
    for bench in BENCHMARKS:
        seen = [(odds.action, odds.on, odds.published) for odds in bench.outcomes if odds.published is not None]
        assert len(seen) == len(set(seen)), bench.id


def test_a_published_number_stands_on_one_row_and_a_reading_without_one_is_not_a_difference(data, prices, route_id):
    """Ticket #599: the guide's 100% for "two Exalted Orbs guarantee the prefixes" is of the family (OR-4). It was also written on the row for
    the top tier of the same Exalted Orb, so the summary printed "DIFFERS" for 13% and 20% (R04), 55% and 10% (R14) against a number
    nobody published. A number belongs to one (action, item) row; a reading with no number is shown as our odds and is no difference."""
    bench = next(bench for bench in BENCHMARKS if bench.id == route_id)
    entry, _ = run_route(bench, data, find_project_root(), load_config({}), prices, None)
    tiers = [row for row in entry["published_odds"] if row["published"] is None]
    assert len(tiers) == 2 and all(row["matches"] is None for row in tiers)

    from crafting_system.cli._benchmark import render_summary

    machine = {"os": "test", "cpu_count": 1, "python": "3", "commit": "0" * 12}
    text = render_summary({"machine": machine, "routes": [entry]})
    assert text.count("DIFFERS") == 0 and text.count("our odds") == 2 and text.count("the guide publishes no number") == 2


def test_benchmark_checks_the_odds_and_leaves_the_heavy_route_unsolved(data, prices, route_id):
    bench = next(bench for bench in BENCHMARKS if bench.id == route_id)

    entry, _ = run_route(bench, data, find_project_root(), load_config({}), prices, None)

    assert entry["solver"] is None and entry["error"].startswith("not solved: ") and "--heavy" in entry["error"]
    assert len(entry["published_odds"]) == len(bench.outcomes)


def test_the_decision_finds_no_approximate_level_and_the_planner_goes_on_to_the_packed_solver(unsolved, route_id):
    """Ticket #70: what was a refusal ("no approximate answer was possible") is now an exact answer of the packed solver, with the reason in the note."""
    decision = decide(unsolved.abstraction, unsolved.start, unsolved.offers, 60.0)

    assert decision.action == "refused" and "Attack/Caster tags" in decision.why
    note = _packed_note(decision)
    assert "Attack/Caster tags" in note and "whole search ran" in note


def test_no_vendor_recipe_makes_a_quiver_or_a_bow_so_the_default_run_plans_the_target_once(data, prices, route_id):
    """The CLI compares the start options (ADR-0059); with none but the plain item it is one plan, not several 10-minute walks."""
    from crafting_system.cli._start_options import StartContext, combine
    from crafting_system.cli._starts import SOURCES

    target = load_target(ROOT / ROUTES[route_id][0], data)

    listing = combine([source(StartContext(data, target, prices)) for source in SOURCES])

    assert not listing.candidates


def test_a_budget_run_with_the_object_solver_asked_for_still_refuses_with_the_reason(data, prices, route_id):
    target = load_target(ROOT / ROUTES[route_id][0], data)

    with pytest.raises(PlanError, match=r"no approximate answer was possible.*Attack/Caster tags"):
        make_plan(data, target, prices, budget=60.0, solver="object")


def test_a_route_can_be_played_on_concrete_items(unsolved, data, route_id):
    route = load_route(ROOT / ROUTES[route_id][1].replace(".yaml", "-restart.yaml"), unsolved, data)

    report = simulate_route(data, unsolved, route, runs=3, seed=1, max_steps=300)

    assert report.runs == 3 and report.successes + report.stopped + report.unfinished == 3
    assert all(cost >= unsolved.start_price.chaos for cost in report.costs)


def test_an_outcome_naming_an_action_the_target_does_not_offer_is_a_value_error(data):
    held = ("LocalIncreasedAttackSpeed5",)
    odds = PublishedOutcome("Fracturing Orb", "fractures the Speed", "a bow", held, "fractured", held, "25%")

    with pytest.raises(ValueError, match="which the target does not offer"):
        published_outcomes(data, load_target(ROOT / ROUTES["R14"][0], data), [odds])
