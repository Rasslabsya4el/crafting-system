"""The offers' floors of the free actions: the veiled choices (the Unveil and the picks) and the restore of an imprint (ticket #1074, OR-12, OR-13).

Until #1074 an Unveil and a Pick were TERMINAL offers of the Wald floor `rho` (`planner/_offer_kinds.py`): they read the offer
(`Reads.item_state`), so their pbar was 1 and their floor their price, the free action's epsilon (ADR-0026). Every search that offered them
had `rho` at that epsilon, and so the floor of every key outside the bound's model at about 0 (#1112: R05's single search, rho 1.048e-08).

They are veiled choices now: an action that needs the placeholder (`Reads.needs_veiled`) puts on the item at most a mod it names or a mod of
the unveiled pool of the base, in place of the placeholder, so it lands in E only when one of those mods can pass a leaf of U, like a bench craft
(`finishes`). The Unveil names none: pbar 0. A leaf a pick can pass leaves U when another remains, as a craft's does.

The world is the small amulet pool of `abstraction_veiled_support`: the ordinary Life of `abstraction_pool` (no unveiled mod passes it) and the
unveiled `VeilTestSpeed1`. The numbers are worked by hand: with U the Life leaf, the Veiled Exalted Orb (it puts a placeholder by a removal: of no
kind with a bound) is TERMINAL at 3, the Veiled Chaos Orb a reroll at 5 / pbar >= 5, the Unveil and the picks 0 / 0, the restart 0: rho is 3.

A restore of an imprint was TERMINAL too (it reads the imprints) and free, so once the veiled choices no longer set rho on R05 it did (#1074's
probe of the single search: rho 1.048e-08 at `Restore imprint 1`). An imprint is made only by a TERMINAL offer, so before the first terminal use no
state holds one and a restore is never used there: it is set aside, and a state that holds an imprint is of another shape (`OfferFloors.klass`).
The world is the magic amulet of `test_pattern_imprint` (Alteration 0.1, Augmentation 0.05, Regal 0.5, Annulment 5, the Croaker 2, the restore
1e-6, the restart 1).

Both worlds are checked state by state: at every state of the exact graph, every offer's floor in the state's class is at most its exact Q*, and
V* >= rho outside E (the claim of `_offer_floor`).
"""

import pytest
from abstraction_pool import LEVEL, LIFE_1, RESIST_2
from abstraction_veiled_support import DATA, PRE, amulet, holder, rolled
from items_support import AMULET
from pattern_support import exact_values
from veiled_support import SPEED

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.abstraction._pattern import PatternOffer
from fractions import Fraction

import test_pattern_imprint as imprinted
from crafting_system.actions import NotApplicableError, OutOfScopeError, Pick, Unveil, VeiledChaosOrb, VeiledExaltedOrb, unveil_pool_mods
from crafting_system.cli import Offer
from crafting_system.planner import _pattern_bound
from crafting_system.planner._envelope_plan import envelope_result
from crafting_system.planner._offer_floor import INSIDE, OTHER, OUTSIDE, OfferFloors
from crafting_system.planner._offer_kinds import REFUSED, REROLL, RESTART_KIND, SLACK, TERMINAL, VEILED, _kind_of
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


# --- every state of the exact graph -------------------------------------------------------------------------------


def assert_floors_below_exact_q(ab, start_item, priced, pattern) -> set[int]:
    """At every state of the exact graph: each offer's floor in the state's class is at most its exact Q*, and V* >= rho outside E. The classes met."""
    first = ab.compress(start_item)
    exact = exact_values(ab, first, pattern)
    floors = OfferFloors(ab, first, priced, start_item)
    for entry in floors.entries:
        if entry.kind == REROLL:
            floors._raise(entry, 2)  # the exact chance, the tightest floor
    seen = set()
    for state, value in exact.items():
        klass = floors.klass(state.flags, state.fractured, state.status, state.imprints)
        seen.add(klass)
        if ab.is_goal(state):
            continue
        if klass == OUTSIDE:
            assert value >= floors.rho * (1 - 1e-9), (state, value, floors.rho)
        for position, offer in enumerate(priced):
            action = offer.offer.action
            if isinstance(action, BuyStartItem):
                successors = {first: Fraction(1)}
            else:
                try:
                    successors = ab.kernel(state, action)
                except (NotApplicableError, OutOfScopeError):
                    continue
            q = offer.cost + float(sum(chance * exact[successor] for successor, chance in successors.items()))
            assert floors.lower(position, klass) <= q * (1 + 1e-9), (offer.label, klass, state)
    return seen


@pytest.mark.parametrize("goal", ["life", "life and speed"])
def test_the_veiled_choices_floors_are_below_the_exact_q_at_every_state(goal):
    ab = abstraction(goal)
    pattern = [PatternOffer(label, action, cost) for label, (action, cost) in ACTIONS.items()] + [PatternOffer(RESTART, None, RESTART_PRICE)]
    seen = assert_floors_below_exact_q(ab, START, priced_offers(START), pattern)

    assert {INSIDE, OUTSIDE} <= seen


def test_a_restore_with_no_imprint_at_the_start_is_set_aside_and_rho_is_no_longer_its_price():
    """By hand: U is the three wanted mods (none is PASSING on the magic amulet), the restore is set aside, the Croaker TERMINAL at 2 (it reads
    the imprints), the Regal Orb at 0.5 / 1 or more, the Alteration 0 (a magic item holds two mods: it never lands all three), the restart 0, and
    the Augmentation an addition whose one added mod completes the three at most 5/18 of the time (`add_bound`): rho is 0.05 / (5/18) = 0.18,
    where it was the restore's 1e-6."""
    ab = imprinted.abstraction(1)
    floors = OfferFloors(ab, ab.compress(imprinted.START), imprinted.priced_offers(1), imprinted.START)
    found = {entry.priced.label: (entry.kind, entry.pbar) for entry in floors.entries}

    assert found["Restore 0"] == (REFUSED, 1)
    assert found["Imprint None"] == (TERMINAL, 1)
    assert found["Orb of Augmentation"] == ("add", Fraction(5, 18))
    assert floors.chosen == (0, 1, 2)
    assert floors.rho == pytest.approx(0.18 * (1 - SLACK), rel=1e-12)


def test_a_state_that_holds_an_imprint_is_of_another_shape_when_the_restores_are_set_aside():
    ab = imprinted.abstraction(1)
    first = ab.compress(imprinted.START)
    floors = OfferFloors(ab, first, imprinted.priced_offers(1), imprinted.START)
    imprint = next(offer.offer.action for offer in imprinted.priced_offers(1) if offer.label == "Imprint None")
    (held,) = ab.kernel(first, imprint)

    assert held.imprints and (held.flags, held.fractured, held.status) == (first.flags, first.fractured, first.status)
    assert floors.klass(first.flags, first.fractured, first.status, first.imprints) == OUTSIDE
    assert floors.klass(held.flags, held.fractured, held.status, held.imprints) == OTHER


def test_the_imprint_floors_are_below_the_exact_q_at_every_state():
    seen = assert_floors_below_exact_q(imprinted.abstraction(1), imprinted.START, imprinted.priced_offers(1), imprinted.pattern_offers(1))

    assert {OTHER, OUTSIDE} <= seen


def test_the_envelope_search_with_the_floors_on_gives_the_exact_mean_with_an_imprint_offered(monkeypatch):
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 1)
    ab = imprinted.abstraction(1)
    first = ab.compress(imprinted.START)
    exact = exact_values(ab, first, imprinted.pattern_offers(1))[first]

    result = envelope_result(ab, first, imprinted.priced_offers(1), item=imprinted.START)

    info = result.info["envelope"]
    assert info.exact and info.bound_stopped is None
    assert result.solution.values[first] == pytest.approx(exact, rel=TOLERANCE)
