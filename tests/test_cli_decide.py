"""Exact or approximate (ticket #127, ADR-0023): `choose` with injected rates, the refusals, `decide` on the committed fixture.

No test reads a clock or asserts a time: the rates are numbers handed to the function, and a forecast is a count of
kernel outcomes and edges (ADR-0014). The refusal test reads the declarations of every action of the catalog (#108)
and checks that the CLI refuses a coarse level exactly for those that do not declare themselves block-invariant.
"""

import dataclasses
import datetime

import pytest
from abstraction_pool import MANA_1
from coarse_support import CHAOS, CRAFTS, DATA, HYBRID_CRAFT, REMOVE, abstraction, item, roll
from contract_support import contract_pairs, fixture_items, CONTRACT_DATA

from crafting_system.abstraction import Abstraction, Estimate, Goal
from crafting_system.actions import Adds, ChaosOrb, RegalOrb, Reads
from crafting_system.cli import Offer, PlanError, make_plan
from crafting_system.cli import _decide
from crafting_system.cli._decide import (
    EXACT_TRANSITIONS,
    LADDER,
    Candidate,
    Rates,
    choose,
    coarse_refusal,
    decide,
    exact_offer,
)
from crafting_system.cli._offers import PricedOffer
from crafting_system.prices import PriceFile
from crafting_system.targets import parse_target

BIG = Estimate(states=13_172, transitions=22_994_524, outcomes=22_994_524, kernel_rate=3.9e-5)
SMALL = Estimate(states=76, transitions=4_000, outcomes=4_000, kernel_rate=3.9e-5)
LEVELS = [
    Candidate(LADDER[0], Estimate(365, 90_000, 20_000, 3.9e-5, solves=2)),
    Candidate(LADDER[1], Estimate(1_582, 400_000, 30_000, 3.9e-5, solves=2)),
    Candidate(LADDER[2], Estimate(4_295, 1_200_000, 40_000, 3.9e-5, solves=2)),
]
R_KERNEL, R_SOLVE = 4e-5, 7e-6


# --- the decision function ---------------------------------------------------------------------------------


def test_a_query_whose_forecast_fits_the_budget_is_exact():
    decision = choose(SMALL, R_KERNEL, R_SOLVE, 60.0, levels=LEVELS)

    assert decision.action == "exact" and decision.levels == () and decision.message == ""
    assert decision.predicted == pytest.approx(4_000 * (R_KERNEL + R_SOLVE))


def test_the_forecast_is_outcomes_at_the_kernel_rate_plus_edges_at_the_solve_rate():
    exactly = SMALL.seconds(R_KERNEL, R_SOLVE)

    assert choose(SMALL, R_KERNEL, R_SOLVE, exactly).action == "exact"  # equal to the budget fits
    tiny = [Candidate(LADDER[0], Estimate(5, 10, 10, 1e-5, solves=2))]
    assert choose(SMALL, R_KERNEL, R_SOLVE, exactly * 0.999, levels=tiny).action == "approximate"


def test_a_slower_machine_moves_the_same_query_up_the_decision():
    tiny = [Candidate(LADDER[0], Estimate(5, 10, 10, 1e-5, solves=2))]
    assert choose(SMALL, 1e-6, 1e-6, 60.0, levels=tiny).action == "exact"
    assert choose(SMALL, 1e-2, 1e-2, 60.0, levels=tiny).action == "approximate"


def test_above_the_budget_the_levels_that_fit_are_offered_in_ladder_order():
    decision = choose(BIG, R_KERNEL, R_SOLVE, 60.0, levels=LEVELS)

    assert decision.action == "approximate"
    assert [found.level for found in decision.levels] == list(LADDER)
    assert decision.transitions == 22_994_524


def test_a_level_whose_own_forecast_does_not_fit_is_left_out():
    decision = choose(BIG, R_KERNEL, R_SOLVE, 60.0, levels=LEVELS)
    budget = LEVELS[1].estimate.seconds(R_KERNEL, R_SOLVE) - 0.001  # the second and third levels do not fit

    narrowed = choose(BIG, R_KERNEL, R_SOLVE, budget, levels=LEVELS)

    assert len(decision.levels) == 3
    assert [found.level for found in narrowed.levels] == [LADDER[0]]


def test_a_level_with_no_forecast_is_tried():
    unknown = [Candidate(LADDER[0], None)]

    assert choose(BIG, R_KERNEL, R_SOLVE, 60.0, levels=unknown).levels == tuple(unknown)


def test_an_estimate_that_could_not_be_made_means_the_exact_run():
    decision = choose(None, R_KERNEL, R_SOLVE, 60.0, levels=LEVELS)

    assert decision.action == "exact" and "could not be forecast" in decision.message


def test_an_action_that_is_not_block_invariant_leaves_no_level_so_a_small_query_is_exact_and_says_so():
    mid = Estimate(5_000, 1_500_000, 1_500_000, 3.9e-5)

    decision = choose(mid, R_KERNEL, R_SOLVE, 60.0, levels=LEVELS, refusal="Annulment is not declared block-invariant")

    assert decision.action == "exact"
    assert decision.message.startswith("no approximate level available (Annulment is not declared block-invariant)")
    assert "is run as it is" in decision.message


def test_an_action_that_is_not_block_invariant_refuses_a_query_past_what_the_exact_solver_has_run_on():
    decision = choose(BIG, R_KERNEL, R_SOLVE, 60.0, levels=LEVELS, refusal="Annulment is not declared block-invariant")

    assert decision.action == "refused"
    assert decision.message.startswith("no approximate level available (Annulment is not declared block-invariant). ")
    assert "22,994,524 transitions" in decision.message and "not offered" in decision.message
    assert decision.levels == ()


def test_no_level_that_fits_gives_the_same_two_ways_out():
    nowhere = [Candidate(LADDER[0], Estimate(365, 9_000_000, 9_000_000, 3.9e-5, solves=2))]
    medium = Estimate(9_000, 1_900_000, 1_900_000, 3.9e-5)

    assert choose(BIG, R_KERNEL, R_SOLVE, 60.0, levels=nowhere).action == "refused"
    assert choose(medium, R_KERNEL, R_SOLVE, 60.0, levels=nowhere).action == "exact"


def test_nothing_to_pool_is_said_as_such():
    decision = choose(BIG, R_KERNEL, R_SOLVE, 60.0, levels=())

    assert decision.action == "refused" and "too few to pool" in decision.message


def test_the_exact_run_is_offered_up_to_two_million_transitions_only():
    assert "run again with --exact (2,000,000 transitions, predicted at about 30 s)" in exact_offer(EXACT_TRANSITIONS, 30.0)
    assert "predicted at about 10 min" in exact_offer(EXACT_TRANSITIONS, 600.0)
    over = exact_offer(EXACT_TRANSITIONS + 1, 90.0)
    assert "not offered" in over and "2,000,000" in over and "smaller list of crafts" in over


# --- the refusal reads the declarations ----------------------------------------------------------------------


def declared_invariant(action, data) -> bool:
    reads = action.reads(data)
    if reads.variants:
        return reads.junk and reads.pool_weight and reads.families is not None
    return reads.block_invariant and not reads.pool_weight and not (reads.junk and reads.families is None)


def test_the_cli_refuses_a_coarse_level_for_exactly_the_actions_that_do_not_declare_block_invariance():
    items = fixture_items()
    seen = {"refused": 0, "accepted": 0}
    for _, action, name in contract_pairs():
        held = items[name]
        base = Abstraction(CONTRACT_DATA, Goal(()), held.base_id, held.item_level, [])
        refusal = coarse_refusal(base, [action])
        assert (refusal is None) == declared_invariant(action, CONTRACT_DATA), action.label(CONTRACT_DATA)
        seen["refused" if refusal else "accepted"] += 1
    assert seen["refused"] > 0 and seen["accepted"] > 0


@dataclasses.dataclass(frozen=True)
class UndeclaredRegal(RegalOrb):
    """An addition that declares neither block invariance nor variants."""

    def reads(self, data) -> Reads:
        return Reads.adding()


def test_the_reason_names_the_action_and_the_declaration():
    base = abstraction()

    reason = coarse_refusal(base, [CHAOS, UndeclaredRegal()])

    assert reason is not None and "Regal Orb" in reason
    assert coarse_refusal(base, [CHAOS, RegalOrb()]) is None  # the shipped addition declares variants


# --- decide on the committed fixture ---------------------------------------------------------------------------

CH = "Chaos Orb"
TARGET = f"""\
base: Paua Amulet
item_level: 84
requirements:
  - family: ColdResistance
    mod: {HYBRID_CRAFT}
  - family: IncreasedLife
start_item:
  rarity: rare
  mods:
    - mod: {MANA_1}
      tier: 1
      values: {[min(stat.min, stat.max) for stat in DATA.mods[MANA_1].stats]}
"""
OFFERS = [
    Offer("Chaos Orb", CHAOS, {CH: 1}),
    *(Offer(f"Craft {craft.mod_id}", craft, {CH: 2}) for craft in CRAFTS),
    Offer("Remove Crafted Mods", REMOVE, {CH: 1}),
]
PRICES = PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {})


@pytest.fixture(scope="module")
def target():
    return parse_target(TARGET, DATA, source="t.yaml")


@pytest.fixture(scope="module")
def exact(target):
    return make_plan(DATA, target, PRICES, offers=OFFERS, start_price=0.0)


def priced(offers=OFFERS):
    return tuple(PricedOffer(offer, float(sum(offer.resources.values())), ()) for offer in offers)


def test_decide_forecasts_the_exact_graph_and_picks_the_levels_that_fit(exact):
    ab, start = exact.abstraction, exact.start
    forecast = ab.estimate([start], [offer.action for offer in OFFERS])
    first = Candidate(LADDER[0], forecast.coarsened(_decide.Coarsening.pooling_irrelevant(ab, None, start)))
    between = (forecast.seconds(1.0, 1.0) + first.estimate.seconds(1.0, 1.0)) / 2

    fits = decide(ab, start, priced(), forecast.seconds(1.0, 1.0), Rates(1.0, 1.0))
    over = decide(ab, start, priced(), between, Rates(1.0, 1.0))

    assert fits.action == "exact" and fits.transitions == forecast.transitions
    assert over.action == "approximate"
    assert [found.level for found in over.levels] == [LADDER[0]]  # the finer rungs cut the same families again or do not fit
    assert over.levels[0].estimate.states < forecast.states


@dataclasses.dataclass(frozen=True)
class BrokenRegal(RegalOrb):
    """A Regal Orb whose outcomes cannot be computed (a `ValueError` that is no refusal): the pilot cannot count it."""

    def outcomes(self, data, item):
        raise ValueError("this action has no outcomes")


def test_decide_runs_exact_when_the_pilot_cannot_count_the_actions(exact):
    broken = BrokenRegal()
    regal = [*priced(), PricedOffer(Offer("Regal Orb", broken, {CH: 1}), 1.0, ())]
    ab = Abstraction(DATA, exact.abstraction.goal, exact.abstraction.base_id, 84, [*(offer.action for offer in OFFERS[1:]), broken])

    decision = decide(ab, exact.start, regal, 0.0, Rates(1.0, 1.0))

    assert decision.action == "exact" and "could not be forecast" in decision.message


@dataclasses.dataclass(frozen=True)
class UndeclaredReroll(ChaosOrb):
    """A reroll that does not declare block-invariance: the pilot counts it, a coarse level must refuse it."""

    def reads(self, data) -> Reads:
        return Reads.nothing()

    def label(self, data=None) -> str:
        return "Undeclared reroll"


def test_decide_refuses_the_ladder_for_an_offered_action_that_is_not_declared_block_invariant(exact):
    offers = [Offer("Undeclared reroll", UndeclaredReroll(), {CH: 1}), *OFFERS[1:]]

    decision = decide(exact.abstraction, exact.start, priced(offers), 0.0, Rates(1.0, 1.0))

    assert decision.action == "exact"  # small enough to run as it is
    assert "Undeclared reroll is not declared block-invariant" in decision.message


def test_make_plan_stops_with_the_refusal_when_the_exact_run_is_beyond_the_largest_size_run(target, monkeypatch):
    offers = [Offer("Undeclared reroll", UndeclaredReroll(), {CH: 1}), *OFFERS[1:]]
    monkeypatch.setattr(_decide, "EXACT_TRANSITIONS", 100)

    with pytest.raises(PlanError, match=r"no approximate level available \(Undeclared reroll is not declared block-invariant"):
        make_plan(DATA, target, PRICES, offers=offers, start_price=0.0, budget=0.0, rates=Rates(1.0, 1.0))


def test_make_plan_without_a_budget_never_decides(target, exact):
    plan = make_plan(DATA, target, PRICES, offers=OFFERS, start_price=0.0, rates=Rates(1e9, 1e9))

    assert plan.approximation is None and plan.note == "" and plan.mean_remaining == exact.mean_remaining


# --- a count that was cut short is only a lower bound ---------------------------------------------------------


def test_a_count_cut_short_is_never_taken_for_a_small_graph():
    cut = Estimate(states=400_001, transitions=300, outcomes=300, kernel_rate=3.9e-5, complete=False)

    fits = choose(cut, 1e-9, 1e-9, 60.0, levels=LEVELS)
    refused = choose(cut, R_KERNEL, R_SOLVE, 60.0, levels=(), refusal="Annulment is not declared block-invariant")

    assert fits.action != "exact"  # the forecast of the part that was counted fits, the rest is unknown
    assert refused.action == "refused" and "the count stopped at 300 transitions and the graph is larger" in refused.message
