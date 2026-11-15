"""The forecast of a plan with a budget runs on the twin-merged offers (tickets #63, #829).

`planner._offer_kinds.merge_twins` leaves out the dearer of offers with equal outcomes, so that `make_plan(..., budget=...)` forecasts
(`decide`) on the offers left and an approximate answer is climbed on them. The starting set of the retired bound pruning
(`starting_offers`) is gone with it (#829). This file checks, on the reduced boots world of `tests/test_prune_bound.py` (the
Sorcerer Boots pool cut to seven families, with the real fossil records and made-up prices):

1. `merge_twins` keeps the cheaper of a pair and `restart`, in the order of the list;
2. a plan with a budget that fits has the mean of the plan without a budget; a budget that does not fit is answered
   approximately (on the merged offers) or exactly with the message of `decide`.

The forecast and its ladder are retired (direction of 2026-11-13) and reached only by a walk asked for by name until #928
deletes them; these tests hold them as they are, nothing more. The real-data tests need the cached dump (`CRAFTING_CACHE_DIR`)
and skip cleanly without it, as in CI. No test asserts a run time (ADR-0014): the rates are injected.
"""

from types import SimpleNamespace

import pytest
from test_abstraction_b1_real import LEVEL, rolled, subset
from test_abstraction_fossil_real import BASE, FORCED, FRACTURED
from test_prune_bound import (
    FAMILIES,
    LIFE_CRAFT,
    RESTART_PRICE,
    fossil_sets,
    goals,
    made_up_prices,
    offers_of,
    requirement,
    world_data,
)
from abstraction_support import real_game_data
from limits_support import notes, only

from crafting_system.abstraction import Abstraction, Coarsening, Goal
from crafting_system.abstraction._pattern import PatternBuilder
from crafting_system.actions import BenchCraft, RemoveCraftedMods
from crafting_system.cli import RESTART, Offer, make_plan
from crafting_system.planner._offer_kinds import merge_twins
from crafting_system.planner._decide import LADDER, Rates
from crafting_system.planner._offers import BuyStartItem, PricedOffer, price_offers
from crafting_system.planner._pattern_bound import pattern_offers
from crafting_system.items import Item, Rarity
from crafting_system.targets import StartKind, Target

RATES = Rates(4e-5, 7e-6)


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.fixture(scope="module")
def world(real):
    """The reduced boots world: a start item with a fractured mod, 120 fossil sets and the Chaos Orb, two top-tier mods wanted."""
    data = world_data(real, FAMILIES)
    item = Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, mods=(rolled(data, FRACTURED, fractured=True),))
    target = Target(BASE, LEVEL, frozenset(), goals(data)["two-top-tier"], item, start=StartKind.GIVEN)
    offers = offers_of(data, item, fossil_sets(data, item)[:120])
    prices = made_up_prices(data, "Orb of Alteration", "Orb of Scouring")
    abstraction = Abstraction(data, Goal.from_target(target), BASE, LEVEL)
    priced, _ = price_offers(offers, prices)
    return SimpleNamespace(
        data=data, item=item, target=target, offers=offers, prices=prices, abstraction=abstraction,
        start=abstraction.compress(item), priced=priced,
    )


def restart_of(world, chaos: float = RESTART_PRICE):
    return PricedOffer(Offer(RESTART, BuyStartItem(world.item), {}, shares=False), chaos, ())


def labels(offers) -> list[str]:
    return [priced.label for priced in offers]


# --- 1. merge_twins -------------------------------------------------------------------------------------------------


def test_merge_twins_keeps_the_cheaper_of_each_pair_and_the_restart(world):
    priced = [*world.priced, restart_of(world)]
    cost_of = {offer.label: offer.cost for offer in priced}

    kept, twins = merge_twins(world.data, world.item, priced)

    assert len(twins) >= 1, "the world has no pair of twins to check"
    assert sorted(labels(priced)) == sorted([*labels(kept), *(dropped for dropped, _ in twins)])
    assert len(kept) == len(priced) - len(twins)
    for dropped, stays in twins:
        assert cost_of[stays] <= cost_of[dropped]
        assert stays in labels(kept) or stays in {d for d, _ in twins}  # a kept one may itself lose to a still cheaper twin
    assert any(cost_of[stays] < cost_of[dropped] for dropped, stays in twins), "no pair of twins with different costs"
    assert RESTART in labels(kept) and RESTART not in {dropped for dropped, _ in twins}
    assert labels(kept) == [label for label in labels(priced) if label not in {dropped for dropped, _ in twins}]  # the order is kept


def test_merge_twins_of_offers_without_twins_is_the_same_list(world):
    one_of_each = [world.priced[0], restart_of(world)]  # the Chaos Orb has no twin key

    kept, twins = merge_twins(world.data, world.item, one_of_each)

    assert kept == one_of_each and twins == []


# --- 2. make_plan with a budget -------------------------------------------------------------------------------------

CRAFT_FIRE, CRAFT_COLD = "HelenaMasterFireResist1", "HelenaMasterColdResist1_"


@pytest.fixture(scope="module")
def pooled_world(real):
    """The same boots world with 120 fossil sets, the life craft, and crafts for Fire and Cold Resistance.

    Those two crafts tell the two families apart from the rest, and no goal leaf needs them, so a coarse level can
    pool them: without such a craft the plan keeps no junk, there is nothing to pool and no coarse level exists.
    """
    families = {"IncreasedLife", "MovementVelocity", "IncreasedMana", "FireResistance", "ColdResistance"}
    item_class = real.base_items[BASE].item_class
    corruption = {e.mod_for(item_class) for e in real.essences.values() if e.is_corruption_only} - {None}
    fossil_mods = {mod for record in real.fossils.values() for mod in (*record.added_mods, *record.forced_mods)}
    data = subset(real, BASE, families, {FORCED, FRACTURED, LIFE_CRAFT, CRAFT_FIRE, CRAFT_COLD} | corruption | fossil_mods)
    item = Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, mods=(rolled(data, FRACTURED, fractured=True),))
    crafts = [BenchCraft(LIFE_CRAFT), BenchCraft(CRAFT_FIRE), BenchCraft(CRAFT_COLD), RemoveCraftedMods()]
    offers = offers_of(data, item, [*crafts, *fossil_sets(data, item)[:120]])
    prices = made_up_prices(data, "Orb of Alteration", "Orb of Scouring", "Orb of Transmutation")
    life, speed = requirement(data, "IncreasedLife"), requirement(data, "MovementVelocity", min_tier=1)
    target = Target(BASE, LEVEL, frozenset(), (life, speed), item, start=StartKind.BOUGHT)  # the restart of the budget tests buys it again
    return SimpleNamespace(data=data, item=item, target=target, offers=offers, prices=prices)


@pytest.fixture(scope="module")
def pooled(pooled_world):
    """The pooled world planned exactly, its twins merged, and the forecast's seconds on the merged offers and on the first coarse level."""
    data, item, target, offers, prices = (getattr(pooled_world, name) for name in ("data", "item", "target", "offers", "prices"))
    exact = make_plan(data, target, prices, offers=offers, start_price=RESTART_PRICE)  # `auto`: the envelope search (#829)
    merged = merge_twins(data, item, exact.offers)[0]
    forecast = exact.abstraction.estimate([exact.start], [p.offer.action for p in merged if not isinstance(p.offer.action, BuyStartItem)])
    pooling = Coarsening.pooling_irrelevant(exact.abstraction, None, exact.start)
    seconds = SimpleNamespace(
        merged=forecast.seconds(*(RATES.kernel, RATES.solve)),
        coarse=forecast.coarsened(pooling).seconds(*(RATES.kernel, RATES.solve)),
    )
    return SimpleNamespace(data=data, target=target, offers=offers, prices=prices, exact=exact, merged=merged, seconds=seconds)


def planned(pooled, budget):
    return make_plan(pooled.data, pooled.target, pooled.prices, offers=pooled.offers, start_price=RESTART_PRICE, budget=budget, rates=RATES, solver="object")


def test_the_world_of_the_budget_tests_has_twins_and_a_coarse_level(pooled):
    seconds = pooled.seconds

    assert len(pooled.exact.offers) > len(pooled.merged) > 40
    assert seconds.coarse < seconds.merged  # the order that the budgets below sit in


def test_a_budget_that_fits_gives_the_exact_mean_of_the_plan_without_a_budget(pooled):
    plan = planned(pooled, 60)

    assert plan.approximation is None and notes(plan.limits) == []
    assert plan.mean_remaining == pytest.approx(pooled.exact.mean_remaining, rel=1e-9)
    assert plan.risk is not None


def test_a_budget_that_the_merged_offers_exceed_and_the_first_coarse_level_fits_is_answered_approximately_on_them(pooled):
    seconds = pooled.seconds
    budget = (seconds.merged + seconds.coarse) / 2

    plan = planned(pooled, budget)

    found = plan.approximation
    assert seconds.coarse <= budget < seconds.merged
    assert found is not None and found.level == LADDER[0].name
    assert found.lower <= pooled.exact.mean_remaining <= found.upper
    assert found.within_tolerance and plan.mean_remaining == found.upper
    assert plan.risk is None and plan.start == found.coarsening.coarsen(plan.start)
    assert plan.start in plan.policy


def test_a_budget_that_no_coarse_level_fits_runs_exactly_and_says_why_the_graph_being_small(pooled):
    plan = planned(pooled, 0.001)

    assert plan.approximation is None
    assert only(plan.limits, "how-solved").why.startswith("no approximate answer was possible (none fits the time)")  # G12
    assert plan.mean_remaining == pytest.approx(pooled.exact.mean_remaining, rel=1e-9)


# --- 3. the bound's build on fossils that keep junk (ticket #829) -----------------------------------------------------


def test_a_build_that_grows_the_universe_begins_again_once_on_the_grown_universe(pooled_world):
    """A fossil adds mods the pool of an empty rare item does not list (a socket, gem levels); with bench crafts offered the junk is kept,
    so the build learns those slots from its kernels and begins again. It begins on the universe it grew: made afresh, the universe lost
    them, found them again in the same pass and began again forever (#829: 109 restarts in a minute, CI killed the test after 25 minutes)."""
    world = pooled_world
    enabled = [offer.action for offer in world.offers if not isinstance(offer.action, BuyStartItem)]
    abstraction = Abstraction(world.data, Goal.from_target(world.target), BASE, LEVEL, enabled)
    priced, _ = price_offers(world.offers, world.prices)
    crafts = [p for p in priced if not p.label.startswith("Fossils") and not isinstance(p.offer.action, BuyStartItem)]
    adding = [p for p in priced if p.label.startswith("Fossils") and ("Hollow" in p.label or "Faceted" in p.label)][:4]  # a socket, gem levels
    assert crafts and adding
    offers = pattern_offers([*crafts, *adding])
    builder = PatternBuilder(abstraction, abstraction.compress(world.item), approximate=True)
    builder.stop = lambda: "begins again forever" if builder.restarts > 3 else None

    model = builder.extend(offers)

    assert model.stopped is None
    assert model.stats.universe_growth == 1  # the fossils' slots are found in the first pass, and the second pass finds none


# --- 4. G17: the twins an answer leaves out are a limit on every path (ticket #506, OR-13) --------------------------------


def test_g17_the_packed_path_says_which_twins_it_left_out_as_the_search_does(pooled):
    """The packed solver solves the offers left after the twins are merged, and says so in the same limit as the envelope search."""
    twins = merge_twins(pooled.data, pooled.target.start_item, pooled.exact.offers)[1]
    assert len(twins) >= 1

    packed = make_plan(pooled.data, pooled.target, pooled.prices, offers=pooled.offers, start_price=RESTART_PRICE, solver="packed")
    searched = pooled.exact

    (left_out,) = [limit for limit in packed.limits if limit.what == "Not searched" and limit.why == "same outcome as a cheaper action"]
    assert packed.packed is not None
    assert left_out.labels == tuple(dropped for dropped, _ in twins)
    assert left_out in searched.limits  # the same limit, in the same words, whichever solver answered
    assert left_out.guarantee == "The answer is exact among the methods offered: a cheaper action does the same."


def test_g17_an_approximate_answer_says_which_twins_it_left_out_and_claims_only_the_gap(pooled):
    seconds = pooled.seconds
    plan = planned(pooled, (seconds.merged + seconds.coarse) / 2)

    (left_out,) = [limit for limit in plan.limits if limit.why == "same outcome as a cheaper action"]
    assert plan.approximation is not None
    assert left_out.labels == tuple(dropped for dropped, _ in merge_twins(pooled.data, pooled.target.start_item, plan.offers)[1])
    assert left_out.guarantee == "The plan is within the stated gap of the cheapest among the methods offered: a cheaper action does the same."
