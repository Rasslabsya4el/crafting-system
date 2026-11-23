"""The missing mods' table (`planner/_missing_mods.py`, #1496, H21 of #1434, OR-39, OR-40, OR-55): a lower bound of V* per state that counts
every missing mod, built from a round's offers' floors and read by the envelope search.

Hand-worked: on the veiled amulet of `test_free_action_floors` with the Life goal, the one way to Life is the Veiled Chaos Orb (an erasing
reroll at 5, chance `VEILED_CHAOS_LIFE` of Life, exact): V* = 5 / p, about 15.2205, and the table's exact law gives that figure (its
Veiled Exalted Orb is a veil, which removes and adds a placeholder and can pass no leaf). On the magic amulet of `test_pattern_imprint`
(three wanted mods, Alteration, Augmentation, Regal, Annulment) the table is checked state by state against the exact graph: it is at most V*
everywhere, and at the start within 1e-6 of it, where the offers' floor rho is 0.18. Each "off" case, and the check's fallback, gives 0.
"""

from dataclasses import replace

import pytest

import test_free_action_floors as veiled
import test_pattern_imprint as imprinted
from pattern_support import exact_values

from crafting_system.abstraction import Abstraction
from crafting_system.actions import AlterationOrb
from crafting_system.cli import Offer
from crafting_system.items import Rarity
from crafting_system.planner import _missing_mods
from crafting_system.planner._envelope import Beaten
from crafting_system.planner._envelope_plan import envelope_result
from crafting_system.planner._missing_mods import missing_mods_table
from crafting_system.planner._offer_floor import OfferFloors
from crafting_system.planner._offers import RESTART, BuyStartItem, PricedOffer
from crafting_system.planner import _pattern_bound
from crafting_system.planner._pattern_bound import TABLE_CLOSED, pattern_lower_bound

TOLERANCE = 1e-9


@pytest.fixture
def floors_on(monkeypatch):
    """The offers' floors, and so the table, for a round of a few offers (the planner builds them from `MIN_OFFERS` offers)."""
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 1)


@pytest.fixture
def short(monkeypatch):
    """A table iterated 200 times: weaker, as sound (the check decides), and quicker."""
    monkeypatch.setattr(_missing_mods, "ITERATIONS", 200)


def no_imprints():
    """The magic amulet without the Craicic Croaker: (abstraction, start state, priced offers)."""
    ab = imprinted.abstraction(None)
    offers = [PricedOffer(Offer(label, action, {label: 1}), cost, ()) for label, (action, cost) in imprinted.CRAFTS.items()]
    offers.append(PricedOffer(Offer(RESTART, BuyStartItem(imprinted.START), {}), imprinted.RESTART_PRICE, ()))
    return ab, ab.compress(imprinted.START), offers


@pytest.fixture(scope="module")
def amulet():
    ab, first, offers = no_imprints()
    floors = OfferFloors(ab, first, offers, imprinted.START)
    table = missing_mods_table(floors)
    exact = exact_values(ab, first, imprinted.pattern_offers(None))
    return ab, first, offers, floors, table, exact


def test_the_one_reroll_to_life_gives_its_cost_over_its_chance():
    floors = veiled.floors_of("life")
    table = missing_mods_table(floors)
    assert table.off is None
    assert table.start == pytest.approx(5.0 / float(veiled.VEILED_CHAOS_LIFE), rel=1e-8)
    assert table.start <= 5.0 / float(veiled.VEILED_CHAOS_LIFE)
    assert table.lower(floors.start) == table.start


def test_the_table_is_at_most_the_exact_cost_at_every_state_and_near_it_at_the_start(amulet):
    ab, first, _offers, floors, table, exact = amulet
    assert table.off is None
    for state, value in exact.items():
        assert table.lower(state) <= value * (1 + TOLERANCE)
    assert floors.rho == pytest.approx(0.18)
    assert table.start == pytest.approx(exact[first], rel=1e-6)  # the iteration stops at its cap of 3,000 here, 1.4e-7 below


def test_an_imprint_makes_a_state_off_and_the_croaker_is_a_cut():
    """With the Croaker offered (cap 1) a state holding an imprint is OFF (0), and the imprint is priced at its cost alone (a CUT), so the
    table's figure at the start is the beast's 2 (less the check's shrink), below the exact cost."""
    cap = 1
    ab = imprinted.abstraction(cap)
    first = ab.compress(imprinted.START)
    table = missing_mods_table(OfferFloors(ab, first, imprinted.priced_offers(cap), imprinted.START))
    exact = exact_values(ab, first, imprinted.pattern_offers(cap))
    assert table.off is None
    assert table.start == pytest.approx(imprinted.BEAST, rel=1e-8)
    held = [state for state in exact if state.imprints]
    assert held and all(table.lower(state) == 0.0 for state in held)
    assert all(table.lower(state) <= value * (1 + TOLERANCE) for state, value in exact.items())


def test_a_state_the_table_does_not_model_reads_zero(amulet, monkeypatch):
    ab, first, _offers, _floors, table, _exact = amulet
    assert table.lower(first) > 0
    assert table.lower(replace(first, strands=1)) == 0.0  # Memory Strands
    assert table.lower(replace(first, imprints=(first,))) == 0.0  # an imprint
    assert table.lower(replace(first, flags=replace(first.flags, corrupted=True))) == 0.0  # a shape the floors do not know
    monkeypatch.setattr(type(ab), "_holds_lock", lambda self, state: True)
    assert table.lower(first) == 0.0  # a lock


def test_the_table_is_off_without_junk_slots_and_reads_zero():
    ab = Abstraction(imprinted.SMALL, imprinted.GOAL, imprinted.AMULET, imprinted.LEVEL, (AlterationOrb(),))
    assert not ab.keeps_junk
    offers = [PricedOffer(Offer("Orb of Alteration", AlterationOrb(), {"Orb of Alteration": 1}), 0.1, ())]
    offers.append(PricedOffer(Offer(RESTART, BuyStartItem(imprinted.START), {}), imprinted.RESTART_PRICE, ()))
    first = ab.compress(imprinted.START)
    table = missing_mods_table(OfferFloors(ab, first, offers, imprinted.START))
    assert table.off is not None and "junk" in table.off
    assert table.start == 0.0 and table.lower(first) == 0.0


def test_the_table_is_off_when_the_check_fails(monkeypatch):
    """The check h <= T h is the proof: a table scaled up past its fixed point fails it, and the table is off, today's floors standing."""
    monkeypatch.setattr(_missing_mods, "SHRINK", (-1.0,))  # h doubled before the check
    ab, first, offers = no_imprints()
    table = missing_mods_table(OfferFloors(ab, first, offers, imprinted.START))
    assert table.off is not None and "check" in table.off
    assert table.lower(first) == 0.0


def test_the_table_is_off_when_the_net_is_reached():
    ab, first, offers = no_imprints()
    table = missing_mods_table(OfferFloors(ab, first, offers, imprinted.START), stop=lambda: "the clock")
    assert table.off is not None and "the clock" in table.off


def test_the_search_reads_the_table_and_gives_the_exact_plan(amulet, floors_on, short):
    ab, first, offers, _floors, _table, exact = amulet
    bound = pattern_lower_bound(ab, first, offers, item=imprinted.START)
    assert bound.table is not None and bound.table.off is None
    result = envelope_result(ab, first, offers, item=imprinted.START, bound=bound)
    info = result.info["envelope"]
    assert info.exact
    assert result.solution.values[first] == pytest.approx(exact[first], rel=TOLERANCE)
    assert bound.table.start <= info.lower * (1 + 1e-6) <= exact[first] * (1 + 1e-6)


def test_a_round_whose_table_reaches_the_plan_in_hand_closes_before_any_model_is_grown(amulet, floors_on):
    """A plan in hand at the exact cost: the table's figure at the start reaches it to the certified 1e-6, so the build grows no model
    (phase "table") and the search ends at once, beaten."""
    ab, first, offers, _floors, table, exact = amulet
    held = exact[first] * (1 + 1e-7)
    bound = pattern_lower_bound(ab, first, offers, item=imprinted.START, closes=lambda lower: held <= (1 + 1e-6) * lower)
    assert bound.phase == "table" and bound.stopped == TABLE_CLOSED
    with pytest.raises(Beaten) as beaten:
        envelope_result(ab, first, offers, item=imprinted.START, beaten_at=held)
    assert beaten.value.lower >= table.start


def test_a_search_of_other_offers_does_not_read_the_table(amulet, floors_on, short):
    ab, first, offers, _floors, _table, _exact = amulet
    bound = pattern_lower_bound(ab, first, offers, item=imprinted.START)
    assert bound.table.serves(offers) and not bound.table.serves(list(offers[:-1]))
    assert not bound.table.serves([replace(offer) for offer in offers])
