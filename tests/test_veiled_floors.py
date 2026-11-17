"""The offers' floors of the veiled choices, the Unveil and the picks (ticket #1074, OR-12, OR-13).

Until #1074 an Unveil and a Pick were TERMINAL offers of the Wald floor `rho` (`planner/_offer_kinds.py`): they read the offer
(`Reads.item_state`), so their pbar was 1 and their floor their price, the free action's epsilon (ADR-0026). Every search that offered them
had `rho` at that epsilon, and so the floor of every key outside the bound's model at about 0 (#1112: R05's single search, rho 1.048e-08).

They are veiled choices now: an action that needs the placeholder (`Reads.needs_veiled`) puts on the item at most a mod it names or a mod of
the unveiled pool of the base, in place of the placeholder, so it lands in E only when one of those mods can pass a leaf of U, like a bench craft
(`finishes`). The Unveil names none: pbar 0. A leaf a pick can pass leaves U when another remains, as a craft's does.

The world is the small amulet pool of `abstraction_veiled_support`: the ordinary Life of `abstraction_pool` (no unveiled mod passes it) and the
unveiled `VeilTestSpeed1`. The numbers are worked by hand: with U the Life leaf, the Veiled Exalted Orb (it puts a placeholder by a removal: of no
kind with a bound) is TERMINAL at 3, the Veiled Chaos Orb a reroll at 5 / pbar >= 5, the Unveil and the picks 0 / 0, the restart 0: rho is 3.
"""

import pytest
from abstraction_pool import LEVEL, LIFE_1, RESIST_2
from abstraction_veiled_support import DATA, PRE, amulet, holder, rolled
from items_support import AMULET
from pattern_support import exact_values
from veiled_support import SPEED

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.abstraction._pattern import PatternOffer
from crafting_system.actions import Pick, Unveil, VeiledChaosOrb, VeiledExaltedOrb, unveil_pool_mods
from crafting_system.cli import Offer
from crafting_system.planner import _pattern_bound
from crafting_system.planner._envelope_plan import envelope_result
from crafting_system.planner._offer_floor import OUTSIDE, OfferFloors
from crafting_system.planner._offer_kinds import REROLL, RESTART_KIND, SLACK, TERMINAL, VEILED, _kind_of
from crafting_system.planner._offers import RESTART, BuyStartItem, PricedOffer

FREE = 1e-6  # what `price_offers` gives an action that consumes nothing (ADR-0026, the epsilon)
ACTIONS = {
    "Veiled Chaos Orb": (VeiledChaosOrb(), 5.0), "Veiled Exalted Orb": (VeiledExaltedOrb(), 3.0), "Unveil": (Unveil(), FREE),
    **{f"Pick {index}": (Pick(index), FREE) for index in (1, 2, 3)},
}  # fmt: skip
RESTART_PRICE = 2.0
LIFE, VEILED_SPEED = Wanted(frozenset({LIFE_1})), Wanted(frozenset({SPEED}))
GOALS = {"life": Goal((LIFE,)), "speed": Goal((VEILED_SPEED,)), "life and speed": Goal((LIFE, VEILED_SPEED))}
START = amulet(rolled(RESIST_2))
TOLERANCE = 1e-9


def priced_offers(start) -> list[PricedOffer]:
    offers = [PricedOffer(Offer(label, action, {label: 1}), cost, ()) for label, (action, cost) in ACTIONS.items()]
    return [*offers, PricedOffer(Offer(RESTART, BuyStartItem(start), {}), RESTART_PRICE, ())]


def abstraction(goal: str) -> Abstraction:
    """Without the metamods (no lock to tell apart): the exact graph of the Life goal is 144 states, against 939 with them."""
    return Abstraction(DATA, GOALS[goal], AMULET, LEVEL, tuple(action for action, _ in ACTIONS.values()))


def floors_of(goal: str, start=START) -> OfferFloors:
    ab = abstraction(goal)
    return OfferFloors(ab, ab.compress(start), priced_offers(start), start)


def kinds(floors: OfferFloors) -> dict[str, tuple[str, object]]:
    return {entry.priced.label: (entry.kind, entry.pbar) for entry in floors.entries}


def test_the_unveil_and_the_picks_are_veiled_choices_with_the_mods_they_may_add():
    pool = unveil_pool_mods(DATA, AMULET)
    offers = {offer.label: offer for offer in priced_offers(START)}

    assert SPEED in pool and LIFE_1 not in pool
    assert _kind_of(DATA, START, offers["Unveil"]) == (VEILED, frozenset())  # it draws the offer and puts no mod on the item
    assert _kind_of(DATA, START, offers["Pick 2"]) == (VEILED, pool)
    assert _kind_of(DATA, START, offers["Veiled Chaos Orb"]) == (REROLL, frozenset())
    assert _kind_of(DATA, START, offers["Veiled Exalted Orb"]) == (TERMINAL, frozenset())
    assert _kind_of(DATA, START, offers[RESTART]) == (RESTART_KIND, frozenset())


def test_a_veiled_choice_cannot_land_on_a_leaf_no_unveiled_mod_passes_so_rho_is_no_longer_its_price():
    """The hand-worked floor of the module text: rho 3, the Veiled Exalted Orb's price, where it was the free action's epsilon."""
    floors = floors_of("life")
    found = kinds(floors)

    assert floors.chosen == (0,)
    assert found["Unveil"] == (VEILED, 0)
    assert all(found[f"Pick {index}"] == (VEILED, 0) for index in (1, 2, 3))
    assert found["Veiled Exalted Orb"] == (TERMINAL, 1)
    assert floors.rho == pytest.approx(3.0 * (1 - SLACK), rel=1e-15)
    pick = next(entry.index for entry in floors.entries if entry.priced.label == "Pick 1")
    assert floors.lower(pick, OUTSIDE) == pytest.approx(FREE + floors.rho, rel=1e-12)  # cost + (1 - 0) rho


def test_a_pick_that_can_pass_the_only_leaf_lands_in_e_and_rho_is_its_price():
    floors = floors_of("speed")

    assert floors.chosen == (0,)  # the leaf a pick can pass stays: nothing else would remain
    assert kinds(floors)["Pick 3"] == (VEILED, 1)
    assert kinds(floors)["Unveil"] == (VEILED, 0)
    assert floors.rho == pytest.approx(FREE * (1 - SLACK), rel=1e-15)


def test_the_leaf_a_pick_can_pass_leaves_the_goal_set_when_another_remains():
    floors = floors_of("life and speed")

    assert floors.chosen == (0,)  # the Life leaf; the veiled speed is the pick's
    assert kinds(floors)["Pick 1"] == (VEILED, 0)
    assert floors.rho == pytest.approx(3.0 * (1 - SLACK), rel=1e-15)


def test_a_start_that_holds_a_placeholder_keeps_the_unveil_and_the_picks_terminal():
    """There the placeholder may be fractured, so a pick may change the fractured mods: the shape the claim holds fixed (see the module text)."""
    start = amulet(rolled(RESIST_2), holder(PRE))
    found = kinds(floors_of("life", start))

    assert found["Unveil"] == (TERMINAL, 1)
    assert found["Pick 1"] == (TERMINAL, 1)


@pytest.mark.parametrize("goal", ["life"])  # "life and speed" ends exact too, but its search takes 150 s here (as long with the floors off)
def test_the_envelope_search_with_the_floors_on_gives_the_exact_graphs_mean(goal, monkeypatch):
    """The floors are on (`MIN_OFFERS` lowered to this world's seven offers), so the bound's model starts on the offers `OfferFloors.initial`
    gives and the search reads rho at every key outside it: with rho 3 the search still ends exact, at the mean of the whole graph."""
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 1)
    ab = abstraction(goal)
    first = ab.compress(START)
    offers = [PatternOffer(label, action, cost) for label, (action, cost) in ACTIONS.items()] + [PatternOffer(RESTART, None, RESTART_PRICE)]
    exact = exact_values(ab, first, offers)[first]

    result = envelope_result(ab, first, priced_offers(START), item=START)

    info = result.info["envelope"]
    assert info.exact and info.bound_stopped is None
    assert result.solution.values[first] == pytest.approx(exact, rel=TOLERANCE)
    assert info.lower <= exact * (1 + TOLERANCE)
