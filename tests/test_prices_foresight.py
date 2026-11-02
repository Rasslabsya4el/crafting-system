"""The price of Hinekora's Lock and of its burns, in the price file and the fetchers (ticket #295, B8-3; ADR-0056).

"Done when" of the ticket, line by line (the legality lines are in `test_actions_burns.py`):

* A fixture price file prices the Lock and the burns: `test_the_fixture_price_file_prices_the_lock_and_every_burn`
  (`tests/fixtures/prices/foresight-allflame-2026-11-02.json`, recorded from poe.ninja's Currency and Oil overviews on 2026-11-02), and for the fetchers
  `test_the_fetcher_prices_the_lock_and_every_burn_from_the_overviews`, `test_the_lock_missing_from_the_overview_goes_down_the_fallback_chain_by_its_slug`
  and `test_the_command_always_wants_the_lock_and_the_burns`.
* With no Lock price the Lock is dropped and the report lists it: `test_with_no_lock_price_the_lock_is_dropped_and_listed_as_missing`.
* With two legal burns the cheaper at the file's prices is the one used: `test_with_two_legal_burns_the_cheaper_at_the_prices_of_the_file_is_the_one_used`.
"""

import dataclasses
from datetime import UTC, date, datetime
from pathlib import Path

from burn_support import DATA, build, helmet, ring
from ninja_support import ninja  # noqa: F401  (a fixture)
from test_prices_cli import run

from crafting_system.actions import ApplyQualityCurrency, BlessedOrb, BurnKeeps, ChromaticOrb, HinekoraLock, ReAnoint, burns_at
from crafting_system.cli._offers import Offer, price_offers
from crafting_system.prices import (
    BURN_PRICE_NAMES,
    FORESIGHT_PRICE_NAMES,
    HINEKORAS_LOCK,
    PriceEntry,
    cheapest_burn,
    fetch_price_file,
    load_price_file,
    lock_missing,
    lock_price,
    price_burns,
    resource_cost,
    to_divine,
)
from crafting_system.prices.price_names import ARMOURERS_SCRAP, BLACKSMITHS_WHETSTONE, BLESSED_ORB, CHROMATIC_ORB, CLEAR_OIL

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "prices" / "foresight-allflame-2026-11-02.json"
NOW = datetime(2026, 11, 2, 12, 0, 5, tzinfo=UTC)
LOCK_CHAOS = 115483.0  # poe.ninja, Allflame, 2026-11-02 (about 289 Divine Orbs at the file's rate)


def priced(**changes: float):
    """The fixture file with some prices changed (name -> Chaos), a price of None taken out."""
    base = load_price_file(FIXTURE)
    prices = {name: entry for name, entry in base.prices.items() if changes.get(name, 0) is not None}
    for name, chaos in changes.items():
        if chaos is not None:
            prices[name] = PriceEntry(chaos, "override")
    return dataclasses.replace(base, prices=prices)


# --- the price file -------------------------------------------------------------------------------------


def test_the_fixture_price_file_prices_the_lock_and_every_burn():
    prices = load_price_file(FIXTURE)
    assert prices.league == "Allflame" and prices.fetched_at.date() == date(2026, 11, 2)
    for name in FORESIGHT_PRICE_NAMES:
        assert prices.prices[name].chaos > 0 and prices.prices[name].source == "poe.ninja", name
    assert lock_price(prices) == LOCK_CHAOS and lock_missing(prices) == ()
    assert 280 < to_divine(LOCK_CHAOS, prices) < 300  # the research dated it 271 to 272 Divine Orbs on 2026-10-31; it moves
    assert [name for name in BURN_PRICE_NAMES if name not in prices.prices] == []


def test_the_price_names_are_the_names_the_actions_consume():
    assert HINEKORAS_LOCK == "Hinekora's Lock" and dict(HinekoraLock().resources()) == {HINEKORAS_LOCK: 1}
    assert dict(BlessedOrb().resources()) == {BLESSED_ORB: 1}
    assert dict(ChromaticOrb().resources()) == {CHROMATIC_ORB: 1}
    assert dict(ApplyQualityCurrency(BLACKSMITHS_WHETSTONE).resources()) == {BLACKSMITHS_WHETSTONE: 1}
    assert dict(ApplyQualityCurrency(ARMOURERS_SCRAP).resources()) == {ARMOURERS_SCRAP: 1}
    assert dict(ReAnoint().resources()) == {CLEAR_OIL: 3}
    consumed = {name for action in (BlessedOrb(), ChromaticOrb(), ReAnoint(), ApplyQualityCurrency(ARMOURERS_SCRAP), ApplyQualityCurrency(BLACKSMITHS_WHETSTONE))
                for name in action.resources()}
    assert consumed == set(BURN_PRICE_NAMES) and FORESIGHT_PRICE_NAMES == (HINEKORAS_LOCK, *BURN_PRICE_NAMES)


def test_with_no_lock_price_the_lock_is_dropped_and_listed_as_missing():
    prices = priced(**{HINEKORAS_LOCK: None})
    assert lock_price(prices) is None and lock_missing(prices) == (HINEKORAS_LOCK,)
    lock = HinekoraLock()
    offer = Offer(lock.label(), lock, dict(lock.resources()))
    kept, dropped = price_offers([offer], prices)
    assert kept == () and [(entry.label, entry.missing) for entry in dropped] == [("Hinekora's Lock", (HINEKORAS_LOCK,))]  # the report prints these two
    kept, dropped = price_offers([offer], priced())
    assert dropped == () and kept[0].cost == LOCK_CHAOS and kept[0].parts[0][3] == "poe.ninja"


def test_a_hand_override_prices_the_lock_as_it_prices_any_line():
    assert lock_price(priced(**{HINEKORAS_LOCK: 40.0})) == 40.0  # a cheap Lock can be tried


def test_resource_cost_counts_chaos_and_divine_like_the_offers_do():
    prices = priced()
    assert resource_cost({"Chaos Orb": 3, "Divine Orb": 2}, prices) == (3 + 2 * 399.04, ())
    assert resource_cost({"Clear Oil": 3}, prices) == (3 * 0.2128, ())
    assert resource_cost({"Clear Oil": 3, "Nope": 1, "Aaa": 1}, prices)[1] == ("Aaa", "Nope")
    bare = dataclasses.replace(prices, prices={})
    assert resource_cost({"Divine Orb": 1}, bare) == (399.04, ())


# --- the cheaper of two legal burns ------------------------------------------------------------------------


def test_with_two_legal_burns_the_cheaper_at_the_prices_of_the_file_is_the_one_used():
    quality = BurnKeeps(quality=True)
    # a ring with a ranged implicit: a Blessed Orb (0.7849) or a re-anoint (3 Clear Oil, 0.6384)
    burns = burns_at(DATA, ring(), BurnKeeps())
    assert {burn.action for burn in burns} == {BlessedOrb(), ReAnoint()}
    assert cheapest_burn(burns, DATA, priced()).burn.action == ReAnoint()
    assert cheapest_burn(burns, DATA, priced(**{CLEAR_OIL: 1.0})).burn.action == BlessedOrb()  # the oil got dear: the other is cheaper
    assert cheapest_burn(burns, DATA, priced(**{CLEAR_OIL: 1.0})).cost == 0.7849
    # an armour that keeps its quality: a Scrap (0.08963) or a Chromatic Orb (2.71)
    burns = burns_at(DATA, helmet(10), quality)
    assert {burn.action for burn in burns} == {ApplyQualityCurrency(ARMOURERS_SCRAP), ChromaticOrb()}
    assert cheapest_burn(burns, DATA, priced()).burn.action == ApplyQualityCurrency(ARMOURERS_SCRAP)
    assert cheapest_burn(burns, DATA, priced(**{ARMOURERS_SCRAP: 5.0})).burn.action == ChromaticOrb()
    # the order of the candidates does not matter
    assert cheapest_burn(reversed(burns), DATA, priced()).burn.action == ApplyQualityCurrency(ARMOURERS_SCRAP)
    assert [entry.burn.action for entry in price_burns(burns, DATA, priced())] == [ApplyQualityCurrency(ARMOURERS_SCRAP), ChromaticOrb()]


def test_a_burn_whose_currency_has_no_price_is_not_a_candidate():
    burns = burns_at(DATA, helmet(10), BurnKeeps(quality=True))
    assert cheapest_burn(burns, DATA, priced(**{ARMOURERS_SCRAP: None})).burn.action == ChromaticOrb()
    assert cheapest_burn(burns, DATA, priced(**{ARMOURERS_SCRAP: None, CHROMATIC_ORB: None})) is None
    assert cheapest_burn([], DATA, priced()) is None


def test_equal_prices_are_broken_by_label_not_by_order():
    burns = burns_at(DATA, helmet(10), BurnKeeps(quality=True))
    equal = priced(**{ARMOURERS_SCRAP: 2.0, CHROMATIC_ORB: 2.0})
    forward, backward = cheapest_burn(burns, DATA, equal), cheapest_burn(tuple(reversed(burns)), DATA, equal)
    assert forward == backward and forward.burn.label(DATA) == "Burn with Armourer's Scrap"


# --- the fetchers ----------------------------------------------------------------------------------------


def test_the_fetcher_prices_the_lock_and_every_burn_from_the_overviews(ninja):
    result = fetch_price_file(ninja, NOW, wanted=FORESIGHT_PRICE_NAMES)
    assert result.missing == []
    for name in FORESIGHT_PRICE_NAMES:
        entry = result.price_file.prices[name]
        assert entry.source == "poe.ninja" and entry.chaos > 0, name
    assert result.price_file.prices[HINEKORAS_LOCK].chaos == LOCK_CHAOS
    assert result.price_file.prices[CLEAR_OIL].chaos == 0.2128
    assert any("type=Oil" in url for url in ninja.requests)  # the oils come from their own overview
    assert not ninja.detail_requests()  # nothing needed the fallback chain


def test_the_lock_missing_from_the_overview_goes_down_the_fallback_chain_by_its_slug(ninja):
    ninja.drop_line("Currency", "hinekoras-lock")
    result = fetch_price_file(ninja, NOW, wanted=FORESIGHT_PRICE_NAMES)
    assert result.missing == [HINEKORAS_LOCK]  # the recorded history has no row for it
    assert any("id=hinekoras-lock" in url for url in ninja.detail_requests())
    assert HINEKORAS_LOCK not in result.price_file.prices


def test_the_command_always_wants_the_lock_and_the_burns(ninja, tmp_path, capsys):
    assert run(["fetch"], tmp_path, ninja) == 0
    saved = load_price_file(tmp_path / "data" / "prices.json")
    assert all(name in saved.prices for name in FORESIGHT_PRICE_NAMES)
    assert "No price for" not in capsys.readouterr().out
    ninja.drop_line("Currency", "hinekoras-lock")
    assert run(["fetch"], tmp_path, ninja) == 0
    assert "No price for 1 wanted resources:\n  Hinekora's Lock" in capsys.readouterr().out
