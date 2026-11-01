"""The forecast of a plan with a budget runs on the pruning's starting set (ticket #63).

`cli._bound_prune.merge_twins` is the twin step of `solve_pruned`, taken out so that `make_plan(..., budget=...)` can
use it; `starting_offers` is the set `solve_pruned` solves first (restart, the bench crafts, the K best rerolls after the
twins). `make_plan` forecasts (`decide`) on that set instead of on every offer, and an approximate answer is climbed on
the twin-merged offers. This file checks, on the reduced boots world of `tests/test_prune_bound.py` (the Sorcerer Boots
pool cut to seven families, with the real fossil records and made-up prices):

1. `merge_twins` leaves out exactly what `solve_pruned` reports as `twins`: the cheaper of a pair stays, `restart` stays;
2. `starting_offers` is a part of the twin-merged offers that holds `restart` and every bench craft, is smaller in a world
   with many rerolls, and is the whole list when there are fewer than `min_offers`;
3. a plan with a budget that fits has the mean of the plan without a budget; a budget that does not fit is answered
   approximately (on the merged offers) or refused with the message of `decide`.

The real-data tests need the cached dump (`CRAFTING_CACHE_DIR`) and skip cleanly without it, as in CI. No test asserts a
run time (ADR-0014): the rates are injected.
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

from crafting_system.abstraction import Abstraction, Coarsening, Goal
from crafting_system.actions import BenchCraft, RemoveCraftedMods
from crafting_system.cli import RESTART, Offer, _bound_prune, make_plan
from crafting_system.cli._bound_prune import merge_twins, solve_pruned, starting_offers
from crafting_system.cli._decide import LADDER, Rates
from crafting_system.cli._offers import BuyStartItem, PricedOffer, offer_of, price_offers
from crafting_system.items import Item, Rarity
from crafting_system.targets import Target

RATES = Rates(4e-5, 7e-6)


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.fixture(scope="module")
def world(real):
    """The reduced boots world: a start item with a fractured mod, 120 fossil sets and the Chaos Orb, two top-tier mods wanted."""
    data = world_data(real, FAMILIES)
    item = Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, mods=(rolled(data, FRACTURED, fractured=True),))
    target = Target(BASE, LEVEL, frozenset(), goals(data)["two-top-tier"], item)
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


def test_merge_twins_leaves_out_what_solve_pruned_reports_as_twins_and_keeps_the_cheaper_of_each_pair(world):
    priced = [*world.priced, restart_of(world)]
    cost_of = {offer.label: offer.cost for offer in priced}

    kept, twins = merge_twins(world.data, world.item, priced)
    found = solve_pruned(world.abstraction, world.start, priced, world.item, min_offers=0)

    assert len(twins) >= 1, "the world has no pair of twins to check"
    assert tuple(twins) == found.twins
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


# --- 2. starting_offers ---------------------------------------------------------------------------------------------


def test_the_starting_offers_are_a_part_of_the_merged_offers_with_the_restart_and_fewer_offers(world):
    priced = [*world.priced, restart_of(world)]
    merged = merge_twins(world.data, world.item, priced)[0]

    start_set = starting_offers(world.abstraction, world.start, merged, world.item, min_offers=40)

    assert set(labels(start_set)) <= set(labels(merged))
    assert RESTART in labels(start_set)
    assert len(merged) > 40 and len(start_set) < len(merged)
    assert labels(start_set) == [label for label in labels(merged) if label in set(labels(start_set))]  # in the order of the list


def test_the_starting_offers_hold_every_bench_craft(world):
    data, item = world.data, world.item
    actions = [BenchCraft(LIFE_CRAFT), RemoveCraftedMods()]
    crafts = [offer_of(action, action.label(data), data, item) for action in actions]
    priced, _ = price_offers([*world.offers, *crafts], made_up_prices(data, "Orb of Alteration", "Orb of Scouring"))
    merged = merge_twins(data, item, priced)[0]

    start_set = starting_offers(world.abstraction, world.start, merged, item, min_offers=40)

    assert {"Bench craft +# to maximum Life", "Remove Crafted Mods"} <= set(labels(start_set))
    assert len(start_set) < len(merged)


def test_with_fewer_than_min_offers_the_starting_offers_are_all_of_them_in_order(world):
    few = list(world.priced[:10])

    assert starting_offers(world.abstraction, world.start, few, world.item) == few  # the default is 40
    assert starting_offers(world.abstraction, world.start, few, world.item, min_offers=11) == few


def test_the_starting_set_is_where_the_first_solve_of_the_pruning_starts(world, monkeypatch):
    """`solve_pruned` solves the starting set first: its first round holds the offers `starting_offers` names."""
    priced = [*world.priced, restart_of(world)]
    merged = merge_twins(world.data, world.item, priced)[0]
    start_set = starting_offers(world.abstraction, world.start, merged, world.item, min_offers=0)
    solved: list[list[str]] = []
    real_solve = _bound_prune.solve

    def watch(model, starts):
        solved.append(labels(model.offers) if hasattr(model, "offers") else [])
        return real_solve(model, starts)

    monkeypatch.setattr(_bound_prune, "solve", watch)

    solve_pruned(world.abstraction, world.start, priced, world.item, min_offers=0)

    assert solved and solved[0] == labels(start_set)


# --- 3. make_plan with a budget -------------------------------------------------------------------------------------

CRAFT_FIRE, CRAFT_COLD = "HelenaMasterFireResist1", "HelenaMasterColdResist1_"


@pytest.fixture(scope="module")
def pooled(real):
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
    target = Target(BASE, LEVEL, frozenset(), (life, speed), item)
    exact = make_plan(data, target, prices, offers=offers, start_price=RESTART_PRICE)
    merged = merge_twins(data, item, exact.offers)[0]
    first = starting_offers(exact.abstraction, exact.start, merged, item, min_offers=40)
    forecast = {}
    for name, chosen in (("merged", merged), ("first", first)):
        actions = [p.offer.action for p in chosen if not isinstance(p.offer.action, BuyStartItem)]
        forecast[name] = exact.abstraction.estimate([exact.start], actions)
    pooling = Coarsening.pooling_irrelevant(exact.abstraction, None, exact.start)
    seconds = SimpleNamespace(
        merged=forecast["merged"].seconds(*(RATES.kernel, RATES.solve)),
        first=forecast["first"].seconds(*(RATES.kernel, RATES.solve)),
        coarse=forecast["first"].coarsened(pooling).seconds(*(RATES.kernel, RATES.solve)),
    )
    return SimpleNamespace(data=data, target=target, offers=offers, prices=prices, exact=exact, merged=merged, first=first, seconds=seconds)


def planned(pooled, budget):
    return make_plan(pooled.data, pooled.target, pooled.prices, offers=pooled.offers, start_price=RESTART_PRICE, budget=budget, rates=RATES)


def test_the_world_of_the_budget_tests_has_a_forecast_set_far_smaller_than_the_offers_and_a_coarse_level(pooled):
    seconds = pooled.seconds

    assert len(pooled.exact.offers) > len(pooled.merged) > 40 > len(pooled.first)
    assert seconds.coarse < seconds.first < seconds.merged  # the order that the three budgets below sit in


def test_a_budget_that_fits_gives_the_exact_mean_of_the_plan_without_a_budget(pooled):
    plan = planned(pooled, 60)

    assert plan.approximation is None and plan.note == ""
    assert plan.mean_remaining == pytest.approx(pooled.exact.mean_remaining, rel=1e-9)
    assert plan.risk is not None and plan.pruned is not None


def test_a_budget_the_starting_set_fits_but_all_the_merged_offers_would_not_is_answered_exactly(pooled):
    """The forecast is made on the starting set, not on the twin-merged offers (nor, as before, on every offer)."""
    seconds = pooled.seconds
    budget = (seconds.first + seconds.merged) / 2

    plan = planned(pooled, budget)

    assert seconds.first <= budget < seconds.merged
    assert plan.approximation is None and plan.note == ""
    assert plan.mean_remaining == pytest.approx(pooled.exact.mean_remaining, rel=1e-9)


def test_a_budget_that_the_starting_set_exceeds_and_the_first_coarse_level_fits_is_answered_approximately_on_the_merged_offers(pooled):
    seconds = pooled.seconds
    budget = (seconds.first + seconds.coarse) / 2

    plan = planned(pooled, budget)

    found = plan.approximation
    assert seconds.coarse <= budget < seconds.first
    assert found is not None and found.level == LADDER[0].name
    assert found.lower <= pooled.exact.mean_remaining <= found.upper
    assert found.within_tolerance and plan.mean_remaining == found.upper
    assert plan.risk is None and plan.start == found.coarsening.coarsen(plan.start)
    assert plan.start in plan.policy


def test_a_budget_that_no_coarse_level_fits_runs_exactly_and_says_why_the_graph_being_small(pooled):
    plan = planned(pooled, 0.001)

    assert plan.approximation is None
    assert plan.note.startswith("no approximate level available (no coarse level fits the time)")
    assert plan.mean_remaining == pytest.approx(pooled.exact.mean_remaining, rel=1e-9)
