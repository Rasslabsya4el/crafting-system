"""A thin market on a planned route: the price and its mark reach the start line, the cost parts, the JSON and the HTML page (#718, OR-8).

R12 runs through the whole chain on the fixture data with a hand-made price file: no network, no snapshot. The start amulet
has no price in `prices`, only a `thin` trade record of the league (what `store_market` leaves after a thin reading) and,
in the first case, the league's last deep reading. The mark is a field of its own (`StartPrice.mark`, `PricedOffer.marks`),
never a part of the `source` text, which stays the plain name of the source.
"""

import dataclasses
import re
from datetime import date

from cli_support import START, price_file, read_json
from cli_support import run as run_command

from crafting_system.actions import ChaosOrb
from crafting_system.cli import Offer
from crafting_system.cli._offers import price_offers
from crafting_system.prices import DeepReading, MarketRecord, PriceEntry, planned_price

OLD_MARK = "old price, read on 2026-10-25, the market has few offers now"
THIN_MARK = "few offers: the mean of the 4 listings there are"


def thin_file(deep: bool, *, mean: float | None = 9.0):
    """R12's start amulet read thin on 2026-10-30: 4 listings whose mean is `mean`; with `deep`, a deep reading of 4 Chaos on 2026-10-25."""
    record = MarketRecord("thin", "Test", date(2026, 10, 30), 4, 4, "hash", {"query": {}}, mean, 4 if mean else 0)
    memory = {START: DeepReading(4.0, "Test", date(2026, 10, 25), 40, 8)} if deep else {}
    return dataclasses.replace(price_file(start=None), markets={START: record}, deep=memory)


def page_text(tmp_path) -> str:
    """The route page the command wrote beside the JSON, as the plain text of its tags: one line per element."""
    page = (tmp_path / "r12-lightning-amulet.route.html").read_text(encoding="utf-8")
    return "\n".join(line.strip() for line in re.sub(r"<[^>]+>", "\n", page).splitlines() if line.strip())


def test_a_thin_market_with_a_deep_memory_is_planned_at_the_old_price_with_its_mark_and_date(tmp_path, capsys):
    code, out = run_command(tmp_path, prices=thin_file(deep=True))

    text = capsys.readouterr().out
    assert code == 0
    assert f"Start item ({START}): 4.00 Chaos [trade-api]\n  {OLD_MARK}\n" in text  # the start line, source plain, mark beside it
    start = read_json(out)["start"]
    assert (start["price_chaos"], start["price_source"], start["price_mark"]) == (4.0, "trade-api", OLD_MARK)
    assert read_json(out)["totals"]["mean_cost"]["value"] > 4.0


def test_a_thin_market_with_no_deep_memory_is_planned_at_the_thin_mean_with_its_mark(tmp_path, capsys):
    code, out = run_command(tmp_path, prices=thin_file(deep=False))

    text = capsys.readouterr().out
    assert code == 0
    assert f"Start item ({START}): 9.00 Chaos [trade-api]\n  {THIN_MARK}\n" in text
    start = read_json(out)["start"]
    assert (start["price_chaos"], start["price_source"], start["price_mark"]) == (9.0, "trade-api", THIN_MARK)


def test_the_html_page_prints_the_old_price_mark_with_its_date_on_the_start_row(tmp_path):
    code, _ = run_command(tmp_path, prices=thin_file(deep=True))

    lines = page_text(tmp_path).splitlines()
    assert code == 0
    row = lines.index("4 c")  # the start row's "Cost per use" ...
    assert lines[row + 1] == OLD_MARK  # ... and the mark right under it, with the date of the reading
    assert OLD_MARK in lines and "2026-10-25" in OLD_MARK
    assert not any(THIN_MARK in line for line in lines)


def test_the_html_page_prints_the_thin_mean_mark_on_the_start_row(tmp_path):
    code, _ = run_command(tmp_path, prices=thin_file(deep=False))

    lines = page_text(tmp_path).splitlines()
    assert code == 0
    row = lines.index("9 c")
    assert lines[row + 1] == THIN_MARK
    assert not any(OLD_MARK in line for line in lines)


def test_the_html_page_and_the_json_of_an_unmarked_price_carry_nothing_new(tmp_path):
    code, out = run_command(tmp_path, prices=price_file())

    page = page_text(tmp_path)
    document = read_json(out)
    assert code == 0 and "price_mark" not in document["start"]
    assert "old price" not in page and "few offers" not in page
    assert all("price_mark" not in resource for state in document["states"] for resource in state["resources"])


def test_a_bought_input_priced_thin_keeps_its_offer_and_carries_the_mark_beside_the_part():
    offer = Offer("Buy the amulet", ChaosOrb(), {START: 1})

    old, dropped_old = price_offers([offer], thin_file(deep=True))
    thin, dropped_thin = price_offers([offer], thin_file(deep=False))
    nothing, dropped_nothing = price_offers([offer], thin_file(deep=False, mean=None))

    assert dropped_old == dropped_thin == ()  # the offer is not silently lost (OR-8's counter-example)
    assert old[0].parts == ((START, 1, 4.0, "trade-api"),) and old[0].marks == ((START, OLD_MARK),) and old[0].cost == 4.0
    assert thin[0].parts == ((START, 1, 9.0, "trade-api"),) and thin[0].marks == ((START, THIN_MARK),) and thin[0].cost == 9.0
    assert nothing == () and [each.missing for each in dropped_nothing] == [(START,)]  # nothing to show: dropped as it was


def test_an_unmarked_part_has_no_mark():
    offer = Offer("Buy the amulet", ChaosOrb(), {START: 1})

    (priced,), _ = price_offers([offer], price_file())

    assert priced.parts == ((START, 1, 4.0, "trade-api"),) and priced.marks == ()


def test_a_thin_market_with_nothing_to_show_still_stops_with_no_price(tmp_path, capsys):
    code, _ = run_command(tmp_path, prices=thin_file(deep=False, mean=None))

    assert code == 1
    assert f"no price for the start item {START!r}" in capsys.readouterr().err


def test_a_deep_market_is_planned_as_before(tmp_path):
    code, out = run_command(tmp_path, prices=price_file())

    assert code == 0 and read_json(out)["start"]["price_source"] == "trade-api"


def test_a_thin_record_of_another_league_is_no_price_of_this_one():
    foreign = dataclasses.replace(thin_file(deep=True), league="Other")

    assert planned_price(foreign, START) is None


def test_a_hand_override_wins_over_a_thin_record():
    file = thin_file(deep=True)
    file = dataclasses.replace(file, prices={**file.prices, START: PriceEntry(6.5, "override")})

    got = planned_price(file, START)

    assert got.entry == PriceEntry(6.5, "override") and got.mark is None


# -- the profile setting price_source ------------------------------------------------------------------------------------------


def test_a_ninja_profile_is_not_priced_from_a_thin_trade_record():
    file = thin_file(deep=True)

    assert planned_price(file, START, "ninja") is None
    assert planned_price(file, START, "trade").mark == OLD_MARK
    assert planned_price(file, START, "both").mark == OLD_MARK


def test_a_ninja_run_does_not_plan_a_thin_start_item_and_a_both_run_does(tmp_path, capsys):
    ninja, _ = run_command(tmp_path, "--price-source", "ninja", prices=thin_file(deep=True))
    assert ninja == 1 and f"no price for the start item {START!r}" in capsys.readouterr().err

    both, _ = run_command(tmp_path, "--price-source", "both", prices=thin_file(deep=True))
    assert both == 0


def test_a_ninja_setting_prices_an_input_without_the_thin_record():
    offer = Offer("Buy the amulet", ChaosOrb(), {START: 1})

    priced, dropped = price_offers([offer], thin_file(deep=True), "ninja")

    assert priced == () and [each.missing for each in dropped] == [(START,)]
