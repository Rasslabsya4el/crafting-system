"""The default price file of the tests and benchmarks prices every method in scope, and its lower essence tiers by the recipe (#885).

The file is `tests/fixtures/prices/routes-allflame-2026-07-31.json`: league Allflame (3.29) on its league day 7 (#838). The owner
looked through it on 2026-11-13 and asked for two things: the lower essence tiers priced from the vendor upgrade recipe (three of a
tier make one of the next tier of the same type), and a price for every ingredient a method of the beta spends, beasts included.
The walk over the action catalog reads the real 3.29.3.3 data (skipped where the cache is absent; CI fetches it).
"""

from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.prices import load_price_file
from crafting_system.prices.essence_recipe import RECIPE_SOURCE, TIERS, apply_upgrade_recipe, tier_of
from crafting_system.prices.price_marks import price_marks
from crafting_system.prices.provenance import ESTIMATE, HISTORY, OVERRIDE, PREVIOUS_LEAGUE
from crafting_system.prices.spends import spends, unpriced

PRICES = Path(__file__).resolve().parent / "fixtures" / "prices"
DEFAULT_FILE = PRICES / "routes-allflame-2026-07-31.json"


@pytest.fixture(scope="module")
def prices():
    return load_price_file(DEFAULT_FILE)


@pytest.fixture(scope="module")
def walked():
    return spends(real_game_data())


def test_no_action_in_scope_spends_a_name_the_default_file_does_not_price(prices, walked):
    """The ticket's test: it fails when a method in scope (every kind but the deferred batches) spends something with no price."""
    missing = {kind: unpriced(spent, prices) for kind, spent in walked.items()}

    assert {kind: names for kind, names in missing.items() if names} == {}


def test_every_beast_a_recipe_spends_is_a_reading_of_the_leagues_own_day(prices, walked):
    beast_kinds = ("beast-side-swap", "wild-bristle-matron", "aspect-beast", "talisman-fracture", "imprint", "beast-influence-recipe")
    beasts = {name for kind in beast_kinds for name in walked[kind]} - {"Chaos Orb"}

    assert len(beasts) == 18
    for name in beasts:
        p = prices.prices[name].provenance
        assert (p.kind, p.league, p.date, p.depth_unit) == (HISTORY, "Allflame", "2026-07-31", "observations") and p.depth >= 5, name
    assert prices.prices["Wild Bristle Matron"].chaos == 235.0 and prices.prices["Farric Wolf Alpha"].chaos == 2.0


def test_the_beast_poe_ninja_spells_differently_is_a_day_reading_and_the_file_holds_no_hand_price_or_estimate(prices):
    """poe.ninja lists The Black Mórrígan as "Black Mórrigan"; read under that name it is a market row like the other beasts
    (147 Chaos on Allflame's day 7), so the file needs no hand-set number (OR-44 keeps those for a market nobody buys from)."""
    row = prices.prices["The Black Mórrígan"]

    assert not [name for name, entry in prices.prices.items() if entry.provenance is not None and entry.provenance.kind in (OVERRIDE, ESTIMATE)]
    assert row.chaos == 147.0 and row.source == "poe.ninja-history" and row.provenance.depth == 399
    assert price_marks(row, prices, 1.0) == ()


def test_the_currency_of_the_other_methods_is_read_on_the_day_and_two_catalysts_from_the_previous_league(prices, walked):
    kinds = (
        "influenced-exalted-orb", "orb-of-dominance", "awakeners-orb", "veiled-chaos-orb", "veiled-exalted-orb", "catalyst",
        "eldritch-implicit-currency", "eldritch-chaos-orb", "eldritch-exalted-orb", "eldritch-annulment-orb", "orb-of-conflict",
    )  # fmt: skip
    names = {name for kind in kinds for name in walked[kind]}

    assert len(names) == 34
    assert {name for name in names if prices.prices[name].provenance.kind == PREVIOUS_LEAGUE} == {"Dextral Catalyst", "Sinistral Catalyst"}
    assert all(prices.prices[name].provenance.kind == HISTORY and prices.prices[name].provenance.date == "2026-07-31" for name in names - {"Dextral Catalyst", "Sinistral Catalyst"})
    assert prices.prices["Awakener's Orb"].chaos == pytest.approx(171.5) and prices.prices["Veiled Chaos Orb"].chaos == pytest.approx(18.48)


def test_no_lower_essence_tier_costs_more_than_a_third_of_its_upper_tier(prices):
    tiered = {name: tier_of(name) for name in prices.prices if tier_of(name) is not None}

    assert len(tiered) == 100  # every tiered essence of the game data
    for name, (index, kind) in tiered.items():
        if index == len(TIERS) - 1:
            p = prices.prices[name].provenance
            assert (p.kind, p.league, p.date) == (HISTORY, "Allflame", "2026-07-31"), name  # each type's one market price: its Deafening tier on the day
            assert price_marks(prices.prices[name], prices, 1.0) == (), name
        else:
            upper = prices.prices[f"{TIERS[index + 1]} {kind}"]
            assert prices.prices[name].chaos == pytest.approx(upper.chaos / 3), name
            assert prices.prices[name].source == RECIPE_SOURCE, name
    assert sum(index == len(TIERS) - 1 for index, _ in tiered.values()) == 20
    assert prices.prices["Muttering Essence of Fear"].chaos == pytest.approx(prices.prices["Deafening Essence of Fear"].chaos / 3**5)  # 87 Chaos before
    assert prices.prices["Muttering Essence of Fear"].detail["replaced"]["chaos"] == pytest.approx(87.18, abs=0.01)


def test_the_rule_applied_to_the_default_file_again_changes_nothing(prices):
    again, notes = apply_upgrade_recipe(prices)

    assert again == prices and notes == []
