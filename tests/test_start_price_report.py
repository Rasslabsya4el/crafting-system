"""The price block under a start option: the side-by-side line, the GAP flag, the fallback mark (#357).

The choice is built by hand around candidates whose `sourced` price comes from `source_price` on small price files; the
last tests check that `plan_with_starts` hands the profile setting to a start source.
"""

from datetime import date

from trade_support import price_file
from vendor_starts_support import TOY, TOY_BOOTS, prices, toy_target

from crafting_system.cli import (
    StartCandidate,
    StartContext,
    StartList,
    plan_with_starts,
)
from crafting_system.cli._start_report import start_document, start_lines
from crafting_system.cli._start_types import ConsideredStart, ReadingChoice, StartChoice
from crafting_system.items import ExplicitMod, Item, Rarity
from crafting_system.prices import PriceEntry
from crafting_system.prices.price_source import SourcedPrice, source_price

TODAY = date(2026, 11, 1)
NAME = "Toy Boots (ilvl 86)"


def trade_entry(chaos: float, day: str) -> PriceEntry:
    detail = {"date": day, "league": "Allflame", "listings": 14, "usable": 5, "k": 5}
    return PriceEntry(chaos, "trade-api", detail=detail)


def sourced(trade: float, day: str, ninja: float) -> SourcedPrice:
    file = price_file(prices={**price_file().prices, NAME: trade_entry(trade, day)}, ninja={NAME: PriceEntry(ninja, "poe.ninja")})
    return source_price(file, NAME, "both", TODAY)


def boots() -> Item:
    return Item.build(TOY, base_id=TOY_BOOTS, item_level=86, rarity=Rarity.MAGIC, mods=(ExplicitMod("MovementVelocity5", 2, (30,)),))


def candidate(key: str, price: float, price_sourced: SourcedPrice | None) -> StartCandidate:
    return StartCandidate(key, "bought", f"bought {key}", boots(), price, NAME, f"a trade query, {price:,.2f} Chaos", sourced=price_sourced)


def choice_of(*candidates: StartCandidate) -> StartChoice:
    rows = tuple(
        ConsideredStart(c, "chosen" if n == 0 else "planned", 4.0, c.price + 4.0, False) for n, c in enumerate(candidates)
    )
    first = candidates[0]
    return StartChoice(first, rows, (), (), (ReadingChoice((), first.key, first.price + 4.0),), ())


GAP = sourced(125.0, "2026-11-01", 100.0)
FALLBACK = sourced(125.0, "2026-10-24", 100.0)


def test_the_precondition_prices_are_the_flagged_gap_and_the_fallback():
    assert GAP.gap_flagged and GAP.used == "trade" and FALLBACK.fallback and FALLBACK.used == "poe.ninja"


def test_the_text_prints_the_side_by_side_line_with_the_gap_flag_and_the_fallback_mark():
    lines = start_lines(choice_of(candidate("gap", 125.0, GAP), candidate("fallback", 100.0, FALLBACK)))

    assert "        trade 125.00 Chaos | poe.ninja 100.00 Chaos | gap 25.0%; GAP over 20%: check before relying on it" in lines
    assert "      price source both: 125.00 Chaos [trade-api, 14 listings, 0 d old]" in lines
    assert "      price source both: 100.00 Chaos [poe.ninja (fallback: trade price not usable)]" in lines
    assert any(line.startswith("        fallback: the trade price is not usable (stale") for line in lines)
    text = "\n".join(lines)
    assert text.count("GAP") == 1  # only the flagged candidate carries it


def test_the_price_block_sits_under_the_row_of_its_own_candidate():
    lines = start_lines(choice_of(candidate("gap", 125.0, GAP), candidate("fallback", 100.0, FALLBACK)))

    row = [n for n, line in enumerate(lines) if line.startswith("  chosen: bought gap")]
    other = [n for n, line in enumerate(lines) if line.startswith("  planned: bought fallback")]
    flag = next(n for n, line in enumerate(lines) if "GAP over" in line)
    mark = next(n for n, line in enumerate(lines) if "fallback: the trade price" in line)
    assert row[0] < flag < other[0] < mark


def test_the_json_option_carries_the_numbers_of_the_price():
    document = start_document(choice_of(candidate("gap", 125.0, GAP), candidate("fallback", 100.0, FALLBACK)))

    gap_price, fallback_price = (option["price"] for option in document["options"])
    assert (gap_price["used"], gap_price["chaos"], gap_price["trade_chaos"], gap_price["ninja_chaos"]) == ("trade", 125.0, 125.0, 100.0)
    assert gap_price["gap_percent"] == 25.0 and gap_price["gap_flagged"] is True and gap_price["gap_threshold_percent"] == 20.0
    assert gap_price["fallback"] is False and gap_price["marks"] == []
    assert (fallback_price["used"], fallback_price["chaos"], fallback_price["trade_chaos"], fallback_price["ninja_chaos"]) == (
        "poe.ninja", 100.0, None, 100.0,
    )  # fmt: skip
    assert fallback_price["fallback"] is True and fallback_price["gap_flagged"] is False
    assert fallback_price["marks"][0].startswith("fallback: the trade price is not usable")


def test_a_candidate_with_no_sourced_price_has_no_price_key_and_prints_no_price_line():
    choice = choice_of(candidate("plain-ish", 5.0, None))

    (option,) = start_document(choice)["options"]
    assert "price" not in option
    text = "\n".join(start_lines(choice))
    assert "price source" not in text and "GAP" not in text and "poe.ninja" not in text
    assert start_lines(choice)[1] == "  chosen: bought plain-ish: 9.00 Chaos = start 5.00 + crafting 4.00"


def test_a_not_offered_price_prints_no_price_and_documents_the_reason():
    refused = source_price(price_file(), NAME, "both", TODAY)
    choice = choice_of(candidate("nothing", 0.0, refused))

    assert "      price source both: no price, no trade price recorded; no poe.ninja row of this name" in start_lines(choice)
    (option,) = start_document(choice)["options"]
    assert option["price"]["chaos"] is None and option["price"]["used"] == "none"
    assert option["price"]["reason"] == "no trade price recorded; no poe.ninja row of this name"


# -- the setting reaches the start sources ----------------------------------------------------------------------------------


def test_plan_with_starts_hands_the_price_source_gap_and_day_to_every_source():
    seen: list[StartContext] = []

    def spy(context: StartContext) -> StartList:
        seen.append(context)
        return StartList()

    plan_with_starts(TOY, toy_target(), prices(), price_source="ninja", price_gap_percent=30, today=date(2026, 11, 1), sources=(spy,))

    (context,) = seen
    assert (context.price_source, context.gap_percent, context.today) == ("ninja", 30, date(2026, 11, 1))


def test_the_defaults_are_both_20_percent_and_no_day():
    seen: list[StartContext] = []

    def spy(context: StartContext) -> StartList:
        seen.append(context)
        return StartList()

    plan_with_starts(TOY, toy_target(), prices(), sources=(spy,))

    (context,) = seen
    assert (context.price_source, context.gap_percent, context.today) == ("both", 20.0, None)
    assert StartContext(TOY, toy_target(), prices()).price_source == "both"
