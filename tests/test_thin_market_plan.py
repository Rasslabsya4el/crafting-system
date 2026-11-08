"""A thin market on a planned route: the price and its mark reach the start line, the cost parts and the JSON (#718, OR-8).

R12 runs through the whole chain on the fixture data with a hand-made price file: no network, no snapshot. The start amulet
has no price in `prices`, only a `thin` trade record of the league (what `store_market` leaves after a thin reading) and,
in the first case, the league's last deep reading. Before the planner read through `planned_entry`, such a name failed with
"no price for the start item".
"""

import dataclasses
from datetime import date

from cli_support import START, price_file, read_json
from cli_support import run as run_command

from crafting_system.actions import ChaosOrb
from crafting_system.cli import Offer
from crafting_system.cli._offers import price_offers
from crafting_system.prices import DeepReading, MarketRecord, PriceEntry, planned_entry

OLD_MARK = "old price, read on 2026-10-25, the market has few offers now"
THIN_MARK = "few offers: the mean of the 4 listings there are"
OLD_SOURCE = f"trade-api, {OLD_MARK}"
THIN_SOURCE = f"trade-api, {THIN_MARK}"


def thin_file(deep: bool, *, mean: float | None = 9.0):
    """R12's start amulet read thin on 2026-10-30: 4 listings whose mean is `mean`; with `deep`, a deep reading of 4 Chaos on 2026-10-25."""
    record = MarketRecord("thin", "Test", date(2026, 10, 30), 4, 4, "hash", {"query": {}}, mean, 4 if mean else 0)
    memory = {START: DeepReading(4.0, "Test", date(2026, 10, 25), 40, 8)} if deep else {}
    return dataclasses.replace(price_file(start=None), markets={START: record}, deep=memory)


def test_a_thin_market_with_a_deep_memory_is_planned_at_the_old_price_with_its_mark_and_date(tmp_path, capsys):
    code, out = run_command(tmp_path, prices=thin_file(deep=True))

    text = capsys.readouterr().out
    assert code == 0
    assert f"Start item ({START}): 4.00 Chaos [{OLD_SOURCE}]" in text  # the start line
    document = read_json(out)
    assert document["start"]["price_chaos"] == 4.0 and document["start"]["price_source"] == OLD_SOURCE
    assert document["totals"]["mean_cost"]["value"] > 4.0


def test_a_thin_market_with_no_deep_memory_is_planned_at_the_thin_mean_with_its_mark(tmp_path, capsys):
    code, out = run_command(tmp_path, prices=thin_file(deep=False))

    text = capsys.readouterr().out
    assert code == 0
    assert f"Start item ({START}): 9.00 Chaos [{THIN_SOURCE}]" in text
    document = read_json(out)
    assert document["start"]["price_chaos"] == 9.0 and document["start"]["price_source"] == THIN_SOURCE
    assert document["totals"]["mean_cost"]["value"] > 9.0


def test_a_bought_input_priced_thin_keeps_its_offer_and_carries_the_mark_into_the_cost_breakdown():
    offer = Offer("Buy the amulet", ChaosOrb(), {START: 1})

    old, dropped_old = price_offers([offer], thin_file(deep=True))
    thin, dropped_thin = price_offers([offer], thin_file(deep=False))
    nothing, dropped_nothing = price_offers([offer], thin_file(deep=False, mean=None))

    assert dropped_old == dropped_thin == ()  # the offer is not silently lost (OR-8's counter-example)
    assert old[0].parts == ((START, 1, 4.0, OLD_SOURCE),) and old[0].cost == 4.0
    assert thin[0].parts == ((START, 1, 9.0, THIN_SOURCE),) and thin[0].cost == 9.0
    assert nothing == () and [each.missing for each in dropped_nothing] == [(START,)]  # nothing to show: dropped as it was


def test_a_thin_market_with_nothing_to_show_still_stops_with_no_price(tmp_path, capsys):
    code, _ = run_command(tmp_path, prices=thin_file(deep=False, mean=None))

    assert code == 1
    assert f"no price for the start item {START!r}" in capsys.readouterr().err


def test_a_deep_market_is_planned_as_before(tmp_path):
    code, out = run_command(tmp_path, prices=price_file())

    assert code == 0 and read_json(out)["start"]["price_source"] == "trade-api"


def test_a_thin_record_of_another_league_is_no_price_of_this_one():
    foreign = dataclasses.replace(thin_file(deep=True), league="Other")

    assert planned_entry(foreign, START) is None


def test_a_hand_override_wins_over_a_thin_record():
    file = thin_file(deep=True)
    file = dataclasses.replace(file, prices={**file.prices, START: PriceEntry(6.5, "override")})

    assert planned_entry(file, START) == PriceEntry(6.5, "override")
