"""The planner's price of an action that costs nothing, and a veil loop solved by it (ticket #145, ADR-0026).

The solver wants a positive cost on every action. An unveil and a pick consume nothing (`unveil.is_free_and_in_place`), so `price_offers` gives
them `FREE_ACTION_SHARE` (1e-6) of the cheapest offer that costs something. A loop of paid veils and free unveils and picks lies in one component
of the solver, whose certified error is about `epsilon * value / g` for the smallest constant term `g` of the component, here the free step: the
share is small enough for a route's value to move by a millionth of a Chaos a use and for the certified bound to stay at 1e-9 or so.
"""

import dataclasses
import math
import datetime

import pytest
from abstraction_pool import DAMAGE_1, GEM, LEVEL, LIFE_1
from abstraction_veiled_support import DATA as WITH_ORDINARY_SPEED
from abstraction_veiled_support import SPEED_ORDINARY, SUF, amulet, holder, rolled
from items_support import AMULET
from veiled_support import SPEED

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import Pick, Unveil, VeiledChaosOrb, VeiledExaltedOrb
from crafting_system.cli._offers import FREE_ACTION_SHARE, offer_of, offers_for, price_offers
from crafting_system.cli._plan import _Model, evaluate_risk
from crafting_system.cli._prune import solver_actions
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.solver import solve

# the veiled data without the ordinary mod of the Speed family: nothing a reroll draws can block the Speed mod of the pool, so the loop below has a hand figure
DATA = dataclasses.replace(WITH_ORDINARY_SPEED, mods={mod_id: mod for mod_id, mod in WITH_ORDINARY_SPEED.mods.items() if mod_id != SPEED_ORDINARY})
VEILED_CHAOS = "Veiled Chaos Orb"
GOAL = Goal((Wanted(frozenset({SPEED})),))
ACTIONS = [VeiledChaosOrb(), Unveil(), Pick(1), Pick(2), Pick(3)]


def price_file(**prices: float) -> PriceFile:
    entries = {name.replace("_", " "): PriceEntry(chaos, "test") for name, chaos in prices.items()}
    return PriceFile("Test", datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC), 300.0, entries)


def priced(actions, veiled_chaos: float = 5.0):
    return price_offers([offer_of(action, action.label(DATA), DATA) for action in actions], price_file(Veiled_Chaos_Orb=veiled_chaos))[0]


# --- the price of a free action -------------------------------------------------------------------------------------------


def test_an_action_that_consumes_nothing_costs_a_millionth_of_the_cheapest_offer_that_costs_something():
    found = {entry.label: entry for entry in priced(ACTIONS, veiled_chaos=5.0)}

    assert found[VEILED_CHAOS].cost == 5.0
    for label in ("Unveil", "Pick 1", "Pick 2", "Pick 3"):
        assert found[label].cost == pytest.approx(5.0 * FREE_ACTION_SHARE, rel=1e-12) and found[label].parts == ()  # no resource: the price is the solver's, not a purchase
    assert FREE_ACTION_SHARE == 1e-6


def test_the_share_is_of_the_cheapest_paid_offer_not_of_the_dearest_nor_of_a_free_one():
    both = [VeiledChaosOrb(), VeiledExaltedOrb(), Unveil()]
    offers = [offer_of(action, action.label(DATA), DATA) for action in both]
    entries = {entry.label: entry for entry in price_offers(offers, price_file(Veiled_Chaos_Orb=5.0, Veiled_Exalted_Orb=0.5))[0]}

    assert entries["Unveil"].cost == pytest.approx(0.5 * FREE_ACTION_SHARE)
    assert entries["Veiled Exalted Orb"].cost == 0.5 and entries[VEILED_CHAOS].cost == 5.0


def test_an_offer_of_free_actions_alone_costs_the_share_of_one_chaos():
    only_free = price_offers([offer_of(action, action.label(DATA), DATA) for action in (Unveil(), Pick(1))], price_file())[0]
    assert [entry.cost for entry in only_free] == [FREE_ACTION_SHARE, FREE_ACTION_SHARE]


def test_an_offer_with_a_missing_price_is_dropped_and_does_not_set_the_share():
    entries, dropped = price_offers(
        [offer_of(action, action.label(DATA), DATA) for action in (VeiledChaosOrb(), VeiledExaltedOrb(), Unveil())], price_file(Veiled_Chaos_Orb=5.0)
    )
    assert [drop.label for drop in dropped] == ["Veiled Exalted Orb"]
    assert {entry.label: entry.cost for entry in entries}["Unveil"] == pytest.approx(5.0 * FREE_ACTION_SHARE)


# --- the planner offers the veiled kinds only when a target names them -------------------------------------------------------------


def test_the_veiled_kinds_are_offered_only_when_a_target_names_them():
    start = amulet(rolled(LIFE_1, fractured=True), rolled(DAMAGE_1, fractured=True), rolled(GEM, fractured=True), holder(SUF))
    default = {offer.label for offer in offers_for(DATA, GOAL, AMULET, start, None).offers}
    assert not default & {VEILED_CHAOS, "Veiled Exalted Orb", "Unveil", "Pick 1", "Pick 2", "Pick 3"}
    named = {offer.label for offer in offers_for(DATA, GOAL, AMULET, start, ["veiled-chaos-orb", "unveil", "pick"]).offers}
    assert named == {VEILED_CHAOS, "Unveil", "Pick 1", "Pick 2", "Pick 3"}


# --- a veil loop solved by the planner ----------------------------------------------------------------------------------------


def loop(veiled_chaos: float):
    """The model: three fractured prefixes and a suffix placeholder, the goal the unveiled Speed suffix.

    The veil can only go to the suffix side, so each Veiled Chaos Orb is a fresh placeholder and each unveil offers Speed and Crit (10/13) or the
    hybrid and Crit (3/13); the pick of Speed ends it, the other offer is picked as it comes and the veil is rolled again.
    """
    entries = priced(ACTIONS, veiled_chaos)
    enabled = [entry.offer.action for entry in entries if entry.offer.action.reads(DATA).junk or entry.offer.action.reads(DATA).item_state]
    ability = Abstraction(DATA, GOAL, AMULET, LEVEL, enabled)
    item = amulet(rolled(LIFE_1, fractured=True), rolled(DAMAGE_1, fractured=True), rolled(GEM, fractured=True), holder(SUF))
    start = ability.compress(item)
    return ability, start, entries, solve(_Model(ability, start, entries), [start])


@pytest.mark.parametrize("veiled_chaos", [5.0, 500.0, 50_000.0])
def test_the_value_of_the_veil_loop_is_the_hand_figure_and_the_certified_error_stays_tiny(veiled_chaos):
    # each try: Veiled Chaos Orb c (once, after a miss), Unveil e, Pick e; a miss has chance 3/13
    #   E = 2e + 3/13 (c + E)  =>  E = (26 e + 3 c) / 10 = 0.3 c + 2.6 e,  e = 1e-6 c
    ability, start, entries, solution = loop(veiled_chaos)
    expected = 0.3 * veiled_chaos + 2.6 * FREE_ACTION_SHARE * veiled_chaos

    assert solution.values[start] == pytest.approx(expected, rel=1e-12)
    assert solution.error_bound < 1e-8  # ticket #145: "check error_bound"
    assert all(action.cost > 0 for action in solution.policy.values())
    # the policy: unveil at the placeholder states, the pick of the Speed mod when it is offered, the veil only after a miss
    labels = {action.label for action in solution.policy.values()}
    assert labels == {"Unveil", "Pick 1", "Pick 2", VEILED_CHAOS} or labels == {"Unveil", "Pick 1", "Pick 2"} | {VEILED_CHAOS}


def test_an_offer_state_offers_the_solver_nothing_but_the_picks_and_a_placeholder_state_no_pick():
    ability, start, entries, solution = loop(5.0)
    placeholder_actions = {action.label for action in solver_actions(ability, entries, start, start)}
    assert placeholder_actions == {VEILED_CHAOS, "Unveil"}  # a pick has nothing to pick from, the veiled orb rerolls the item
    offered = next(iter(ability.kernel(start, Unveil())))
    assert offered.offer
    assert {action.label for action in solver_actions(ability, entries, offered, start)} == {"Pick 1", "Pick 2"}


TARGET = """
base: Paua Amulet
item_level: 84
influence: []
requirements:
  - family: VeilTestSpeed
    mod: VeilTestSpeed1
start_item:
  rarity: rare
  mods:
{fractured}
    - mod: VeiledSuffix
actions: [veiled-chaos-orb, unveil, pick]
"""


def veil_target(tmp_path):
    from crafting_system.targets import load_target

    lines = []
    for mod_id in (LIFE_1, DAMAGE_1, GEM):
        entry = rolled(mod_id, data=DATA)
        lines.append(f"    - mod: {mod_id}\n      tier: {entry.tier}\n      values: {list(entry.values)}\n      fractured: true")
    path = tmp_path / "veil.yaml"
    path.write_text(TARGET.format(fractured="\n".join(lines)), encoding="utf-8")
    return load_target(path, DATA)


def test_a_target_that_names_the_veiled_kinds_is_planned_end_to_end_and_the_report_reads(tmp_path):
    from crafting_system.cli import build_report, make_plan, policy_document, render_text

    plan = make_plan(DATA, veil_target(tmp_path), price_file(Veiled_Chaos_Orb=5.0))
    report = build_report(plan, DATA)
    text = render_text(report)

    assert plan.mean_remaining == pytest.approx(1.5 + 2.6 * 5.0 * FREE_ACTION_SHARE, rel=1e-12)
    assert plan.solution.error_bound < 1e-8
    assert "do: Unveil (free; counted at 5e-06 Chaos" in text  # not "( = 0.00 Chaos each)"
    assert "unveil offer: 1. " in text and "2. " in text  # "Pick 2" names the second mod of the offer
    document = policy_document(report)
    assert {state["action"] for state in document["states"]} >= {"Unveil", "Pick 1", "Pick 2"}


def test_a_budget_that_the_exact_run_overshoots_falls_back_to_the_exact_run_for_a_veil_target(tmp_path):
    from crafting_system.cli import make_plan

    plan = make_plan(DATA, veil_target(tmp_path), price_file(Veiled_Chaos_Orb=5.0), budget=1e-9)

    assert plan.approximation is None and "no approximate level" in plan.note  # the family-group level refuses the veiled actions, and says so
    assert plan.mean_remaining == pytest.approx(1.5 + 2.6 * 5.0 * FREE_ACTION_SHARE, rel=1e-12)


def test_the_mean_and_the_odds_of_the_veil_loop_are_exact_in_the_risk_report():
    ability, start, entries, solution = loop(5.0)
    risk = evaluate_risk(solution.policy, start, ability.is_goal, solution.values[start])

    assert risk.success_probability.value == 1.0
    assert risk.mean.value == pytest.approx(solution.values[start], rel=1e-9)


# --- the risk run of a plan with free actions (ticket #349) ------------------------------------------------------------------------


def test_the_percentiles_and_the_cvar_of_the_veil_loop_resolve_and_the_bound_of_the_epsilon_is_stated():
    # a miss (3 in 13) costs a veil c and two free steps e more: C = (c + 2e) M + 2e with M geometric, so the 0.9 quantile (M = 1) is c + 4e
    from crafting_system.cli._offers import free_action_cost

    ability, start, entries, solution = loop(5.0)
    free = free_action_cost(entries)
    risk = evaluate_risk(solution.policy, start, ability.is_goal, solution.values[start], free_cost=free)

    assert free == pytest.approx(5.0 * FREE_ACTION_SHARE)
    assert math.isfinite(risk.p90.high) and math.isfinite(risk.cvar.high)
    assert risk.p90.low <= 5.0 + 4 * free <= risk.p90.high
    assert risk.p90.high - risk.p90.low == pytest.approx(risk.grid.free_allowance) and 0.0 < risk.grid.free_allowance < 1e-3
    assert risk.grid.free_tail == 1e-9
    assert risk.mean.value == pytest.approx(solution.values[start], rel=1e-9)  # the mean is still the exact one
    r = 3 / 13
    cvar = (5.0 + 4 * free) + (5.0 + 2 * free) * (r * r / (1 - r)) / 0.1
    assert risk.cvar.low <= cvar <= risk.cvar.high


def test_the_planner_names_no_free_cost_when_no_offer_is_free():
    from crafting_system.cli._offers import free_action_cost

    assert free_action_cost(priced([VeiledChaosOrb()])) is None
    assert free_action_cost(priced(ACTIONS)) == pytest.approx(5.0 * FREE_ACTION_SHARE)


def test_the_cut_follows_the_cheapest_action_that_costs_something_when_a_policy_holds_free_ones(monkeypatch):
    from crafting_system.cli import _plan
    from crafting_system.solver import Action as SolverAction
    from crafting_system.solver import Outcome

    seen = []
    real = _plan.evaluate
    monkeypatch.setattr(_plan, "evaluate", lambda *args, **kwargs: seen.append(kwargs) or real(*args, **kwargs))
    goal = "goal"
    policy = {
        "start": SolverAction("free", 1e-9, (Outcome("work", 1),)),
        "work": SolverAction("use", 1.0, (Outcome("work", 3), Outcome(goal, 1))),
    }

    risk = _plan.evaluate_risk(policy, "start", lambda state: state == goal, mean=4.0, free_cost=1e-9)
    _plan.evaluate_risk(policy, "start", lambda state: state == goal, mean=4.0)

    assert seen[0]["max_bins"] == _plan.RISK_BINS and seen[0]["free_cost"] == 1e-9  # a mean of 4 against a step of 1 is no cut
    assert seen[0]["free_fallback_bins"] == _plan.UNRESOLVED_BINS  # ... but against the epsilon (2 x 200,000 x 1e-9 < 4) it would have been
    assert "free_cost" not in seen[1]  # no free cost named: the call is the one of before
    assert seen[1]["max_bins"] == _plan.UNRESOLVED_BINS
    assert math.isfinite(risk.p90.high)


def test_the_text_and_the_json_of_a_veil_plan_show_the_percentiles_and_state_the_bound(tmp_path):
    from crafting_system.cli import build_report, make_plan, policy_document, render_text

    plan = make_plan(DATA, veil_target(tmp_path), price_file(Veiled_Chaos_Orb=5.0))
    report = build_report(plan, DATA)
    text = render_text(report)
    totals = policy_document(report)["totals"]

    assert math.isfinite(plan.risk.p90.high) and "not resolved on the grid" not in text
    assert "free actions are counted at 5e-06 Chaos each" in text and "the percentiles hold to within" in text and "and the CVaR to within" in text
    assert totals["quantiles_resolved"] is True
    assert totals["free_action_allowance"] == pytest.approx(plan.risk.grid.free_allowance) and totals["free_action_tail"] == 1e-9
    assert totals["free_action_cost"] == pytest.approx(5e-6) and totals["free_action_cvar_allowance"] > 0.0
    assert totals["solver_error_bound"] == plan.solution.error_bound < 1e-8  # the solver's bound is still reported
