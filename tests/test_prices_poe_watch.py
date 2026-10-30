"""The poe.watch fallback stage on recorded responses (no network, no clock)."""

import copy
from datetime import date

import pytest

from watch_support import WATCH_HOST, FakeWatch, watch, watch_fixture  # noqa: F401  (watch is a fixture)
from crafting_system.prices.fallbacks import Context, Gap
from crafting_system.prices.http_json import SourceError
from crafting_system.prices.poe_watch import poe_watch_stage
from crafting_system.prices.price_names import BaseKey

TODAY = date(2026, 10, 30)
CONTEXT = Context(league="Allflame", today=TODAY)

HOLLOW = Gap("Hollow Fossil", exchange_id="hollow-fossil")
PRISMATIC = Gap("Prismatic Fossil", exchange_id="prismatic-fossil")
ALCHEMY_SHARD = Gap("Alchemy Shard", exchange_id="alchemy-shard")
WEEPING = Gap("Weeping Essence of Contempt", exchange_id="weeping-essence-of-contempt")
MATRON = Gap("Wild Bristle Matron", stash_kind="Beast", stash_id=49005)


def base_gap(name: str, item_level: int, *influences: str) -> Gap:
    shown = f", {'/'.join(influences)}" if influences else ""
    key = BaseKey(name, item_level, influences)
    return Gap(f"{name} (ilvl {item_level}{shown})", stash_kind="BaseType", stash_id=1, base=key)


VISE_REDEEMER = base_gap("Stygian Vise", 85, "Redeemer")
VISE_CRUSADER_HUNTER = base_gap("Stygian Vise", 85, "Crusader", "Hunter")
VISE_HUNTER_REDEEMER = base_gap("Stygian Vise", 85, "Hunter", "Redeemer")
VISE_SHAPER = base_gap("Stygian Vise", 85, "Shaper")
REGALIA = base_gap("Vaal Regalia", 86)


def paths(watch: FakeWatch, route: str) -> list[str]:
    return watch.asked(WATCH_HOST, route)


def categories(watch: FakeWatch) -> list[str]:
    return [url.split("category=")[1] for url in paths(watch, "/get")]


def run(watch: FakeWatch, *gaps: Gap, context: Context = CONTEXT):
    return poe_watch_stage(watch, context, gaps)


def set_history(watch: FakeWatch, item_id: int, rows: dict[str, tuple[float, bool]]) -> None:
    """Replace the history of an item by {date: (mean, lowConfidence)} rows, newest last."""
    watch.history[item_id] = [
        {"mean": mean, "date": f"{day}T22:20:00.123456Z", "id": item_id, "volume": 9, "lowConfidence": low}
        for day, (mean, low) in rows.items()
    ]


# --- /exchange/ratios -----------------------------------------------------------------------


def test_a_ratio_price_is_stamped_and_warned(watch):
    result = run(watch, HOLLOW)

    assert set(result.prices) == {"Hollow Fossil"}
    entry = result.prices["Hollow Fossil"]
    assert entry.chaos == watch_fixture("ratios")["items"][0]["price"]["chaos"] == 187.08333333333334
    assert entry.source == "poe.watch"
    assert entry.detail == {"league": "Allflame", "date": "2026-10-30"}
    assert "/exchange/ratios" in entry.note and "4-hour window" in entry.note
    assert result.warnings == [
        "Hollow Fossil: no usable poe.ninja price; used poe.watch 187.08 Chaos (exchange ratio, league Allflame, 2026-10-30)"
    ]
    assert len(paths(watch, "/exchange/ratios")) == 1
    assert categories(watch) == []


def test_the_warning_rounds_the_price_to_two_decimals(watch):
    result = run(watch, PRISMATIC)

    assert result.warnings == [
        "Prismatic Fossil: no usable poe.ninja price; used poe.watch 2.27 Chaos (exchange ratio, league Allflame, 2026-10-30)"
    ]


def test_the_league_is_url_encoded_in_every_request(watch):
    run(watch, PRISMATIC, context=Context("Hardcore Allflame", TODAY))

    assert "league=Hardcore%20Allflame" in paths(watch, "/exchange/ratios")[0]


def test_a_low_confidence_ratio_is_dropped(watch):
    result = run(watch, WEEPING)  # ratio 9.4 is low confidence, and so is its /get row

    assert result.prices == {} and result.warnings == []


def test_a_ratio_without_a_chaos_number_is_dropped(watch):
    for bad in (None, 0, -1, "2.27", True, float("nan")):
        watch.ratio_item("Prismatic Fossil")["price"]["chaos"] = bad
        assert run(watch, PRISMATIC).prices == {}, bad


def test_an_item_without_a_price_block_has_no_price_but_its_id_feeds_history(watch):
    assert "price" not in watch.ratio_item("Alchemy Shard")
    set_history(watch, 8360, {"2026-10-28": (3.0, False), "2026-10-29": (5.0, False)})

    result = run(watch, ALCHEMY_SHARD)

    assert paths(watch, "/history") == ["https://api.poe.watch/history?league=Allflame&id=8360"]
    entry = result.prices["Alchemy Shard"]
    assert (entry.chaos, entry.source) == (4.0, "poe.watch-history")
    assert entry.detail == {"league": "Allflame", "date": "2026-10-29"}


def test_ratios_are_fetched_once_and_only_when_a_gap_could_be_in_them(watch):
    run(watch, MATRON, VISE_REDEEMER)
    assert paths(watch, "/exchange/ratios") == []

    run(watch, MATRON, VISE_REDEEMER, HOLLOW, PRISMATIC)
    assert len(paths(watch, "/exchange/ratios")) == 1


def test_a_gap_not_in_ratios_goes_on_to_get_in_category_order(watch):
    result = run(watch, Gap("Nothing Like This"))

    assert result.prices == {}
    assert categories(watch) == ["currency", "essence", "beast"]


# --- /get ------------------------------------------------------------------------------------


def test_a_beast_is_priced_from_the_beast_category(watch):
    result = run(watch, MATRON)

    entry = result.prices["Wild Bristle Matron"]
    assert entry.chaos == 130
    assert entry.source == "poe.watch"
    assert entry.note == "poe.watch /get category beast, mean"
    assert entry.detail == {"league": "Allflame", "date": "2026-10-30"}
    assert result.warnings == [
        "Wild Bristle Matron: no usable poe.ninja price; used poe.watch 130 Chaos (/get category beast, league Allflame, 2026-10-30)"
    ]
    assert categories(watch) == ["beast"]


def test_a_low_confidence_beast_row_is_dropped(watch):
    for row in watch.get["beast"]:
        row["lowConfidence"] = True

    assert run(watch, MATRON).prices == {}


def test_an_essence_the_ratios_miss_is_priced_from_the_essence_category(watch):
    watch.get["essence"][0]["lowConfidence"] = False

    result = run(watch, WEEPING)

    assert result.prices["Weeping Essence of Contempt"].chaos == 1
    assert result.prices["Weeping Essence of Contempt"].note == "poe.watch /get category essence, mean"
    assert categories(watch) == ["currency", "essence"]  # the beast category is not asked once priced


def test_get_rows_of_one_item_are_priced_at_their_median(watch):
    watch.get["currency"] = [
        {"id": n, "name": "Chromatic Orb", "mean": mean, "lowConfidence": low}
        for n, (mean, low) in enumerate([(4, False), (30, False), (6, False), (1000, True), (None, False)])
    ]

    result = run(watch, Gap("Chromatic Orb"))

    assert result.prices["Chromatic Orb"].chaos == 6  # median of 4, 30, 6


def test_a_base_is_matched_by_item_level_and_influences(watch):
    result = run(watch, VISE_REDEEMER, VISE_CRUSADER_HUNTER, REGALIA)

    assert result.prices["Stygian Vise (ilvl 85, Redeemer)"].chaos == 500
    assert result.prices["Stygian Vise (ilvl 85, Crusader/Hunter)"].chaos == 1804.2724252491691
    assert result.prices["Vaal Regalia (ilvl 86)"].chaos == 5
    assert categories(watch) == ["bases"]
    assert result.prices["Stygian Vise (ilvl 85, Redeemer)"].note == "poe.watch /get category bases, mean"


def test_a_base_with_no_matching_row_is_not_priced_and_asks_no_history(watch):
    result = run(watch, VISE_SHAPER, base_gap("Stygian Vise", 86, "Redeemer"), base_gap("Vaal Regalia", 86, "Warlord", "Hunter"))

    assert result.prices == {}
    assert paths(watch, "/history") == []


def test_repeated_base_rows_are_priced_at_their_median(watch):
    redeemer = next(row for row in watch.get["bases"] if row["id"] == 24931)
    for n, mean in enumerate((900, 700)):
        watch.get["bases"].append({**redeemer, "id": 70000 + n, "mean": mean})

    assert run(watch, VISE_REDEEMER).prices["Stygian Vise (ilvl 85, Redeemer)"].chaos == 700


def test_a_low_confidence_base_row_gives_no_price(watch):
    result = run(watch, VISE_HUNTER_REDEEMER)

    assert result.prices == {}
    assert paths(watch, "/history") == ["https://api.poe.watch/history?league=Allflame&id=32739"]  # its id was seen


def test_the_bases_category_is_not_fetched_without_a_base_gap(watch):
    run(watch, HOLLOW, MATRON, Gap("Nothing Like This"))

    assert "bases" not in categories(watch)


# --- /history --------------------------------------------------------------------------------


def lowered_prismatic(watch: FakeWatch) -> None:
    watch.ratio_item("Prismatic Fossil")["price"]["lowConfidence"] = True


def test_history_rescues_a_low_confidence_ratio_at_the_median_of_the_window(watch):
    lowered_prismatic(watch)
    rows = {
        "2026-10-20": (99.0, False),  # before the window
        "2026-10-24": (4.0, False),
        "2026-10-25": (500.0, True),  # low confidence
        "2026-10-26": (8.0, False),
        "2026-10-27": (9.0, False),
        "2026-10-28": (700.0, True),
        "2026-10-29": (20.0, False),
        "2026-10-31": (1000.0, False),  # after the window
    }
    set_history(watch, 850, rows)

    result = run(watch, PRISMATIC)

    used = sorted(mean for day, (mean, low) in rows.items() if "2026-10-24" <= day <= "2026-10-30" and not low)
    middle = len(used) // 2
    expected = (used[middle - 1] + used[middle]) / 2
    entry = result.prices["Prismatic Fossil"]
    assert (entry.chaos, expected) == (8.5, 8.5)
    assert entry.source == "poe.watch-history"
    assert entry.detail == {"league": "Allflame", "date": "2026-10-29"}
    assert entry.note == "median of 4 poe.watch history rows in the 7 days ending 2026-10-30"
    assert result.warnings == [
        "Prismatic Fossil: no usable poe.ninja price; used poe.watch 8.5 Chaos (history, median of 4 rows, league Allflame, 2026-10-29)"
    ]
    assert paths(watch, "/history") == ["https://api.poe.watch/history?league=Allflame&id=850"]


def test_history_with_only_low_confidence_or_old_rows_gives_nothing(watch):
    lowered_prismatic(watch)

    assert run(watch, PRISMATIC).prices == {}  # the recorded rows are all low confidence
    set_history(watch, 850, {"2026-10-01": (5.0, False), "2026-10-29": (0.0, False)})
    assert run(watch, PRISMATIC).prices == {}


def test_a_history_window_date_is_the_utc_date_of_the_row(watch):
    lowered_prismatic(watch)
    watch.history[850] = [
        {"mean": 3.0, "date": "2026-10-23T23:59:59Z", "id": 850, "lowConfidence": False},  # day before the window
        {"mean": 7.0, "date": "2026-10-24T00:00:00Z", "id": 850, "lowConfidence": False},  # first day
        {"mean": 9.0, "date": "2026-10-30T23:59:59.5Z", "id": 850, "lowConfidence": False},  # last day
    ]

    entry = run(watch, PRISMATIC).prices["Prismatic Fossil"]

    assert (entry.chaos, entry.detail["date"]) == (8.0, "2026-10-30")


def test_the_ids_of_a_gap_are_tried_in_turn_until_one_has_rows(watch):
    redeemer = next(row for row in watch.get["bases"] if row["id"] == 24931)
    watch.get["bases"].append({**redeemer, "id": 70001})
    for row in watch.get["bases"]:
        row["lowConfidence"] = True
    watch.history[24931] = SourceError("HTTP 500")
    set_history(watch, 70001, {"2026-10-27": (600.0, False)})

    result = run(watch, VISE_REDEEMER)

    assert result.prices["Stygian Vise (ilvl 85, Redeemer)"].chaos == 600
    assert [url.split("id=")[1] for url in paths(watch, "/history")] == ["24931", "70001"]


def test_a_history_is_asked_once_per_id_and_nothing_is_asked_twice(watch):
    lowered_prismatic(watch)
    gaps = (
        HOLLOW, PRISMATIC, WEEPING, ALCHEMY_SHARD, MATRON,
        VISE_REDEEMER, VISE_HUNTER_REDEEMER, VISE_SHAPER, Gap("Nothing Like This"),
    )
    watch.ratio_item("Alchemy Shard")["id"] = 850  # two names sharing one id still ask once
    run(watch, *gaps)

    assert len(watch.requests) == len(set(watch.requests))
    assert len(paths(watch, "/history")) == len({url for url in paths(watch, "/history")})


def test_gaps_priced_by_an_earlier_step_are_not_asked_again(watch):
    run(watch, HOLLOW, PRISMATIC, MATRON)

    assert categories(watch) == ["beast"]
    assert paths(watch, "/history") == []


def test_no_gaps_ask_nothing(watch):
    assert run(watch).prices == {}
    assert watch.requests == []


# --- a failing source or a changed shape ------------------------------------------------------


BAD_ANSWERS = [
    SourceError("HTTP 500"),
    None,
    [],
    {},
    "text",
    {"items": "x"},
    {"items": [None, 5, "x", {"name": 3}, {"name": "Hollow Fossil", "price": "x"}, {"name": "Hollow Fossil", "price": []}]},
]


@pytest.mark.parametrize("bad", BAD_ANSWERS, ids=repr)
def test_a_failing_or_changed_ratios_answer_leaves_the_gap(watch, bad):
    watch.ratios = bad

    result = run(watch, HOLLOW)

    assert result.prices == {} and result.warnings == []


@pytest.mark.parametrize("bad", [SourceError("HTTP 500"), None, {}, "text", [None, 5, "x", {"name": 3}, {"name": "Wild Bristle Matron"}]], ids=repr)
def test_a_failing_or_changed_get_answer_leaves_the_gap(watch, bad):
    watch.get["beast"] = watch.get["bases"] = bad

    result = run(watch, MATRON, VISE_REDEEMER)

    assert result.prices == {} and result.warnings == []


@pytest.mark.parametrize(
    "bad",
    [
        SourceError("HTTP 500"),
        None,
        {},
        "text",
        [None, 5, "x", {}, {"mean": 3, "date": 5, "lowConfidence": False}, {"mean": 3, "date": "soon", "lowConfidence": False}],
        [{"mean": "3", "date": "2026-10-29T00:00:00Z", "lowConfidence": False}],
    ],
    ids=repr,
)
def test_a_failing_or_changed_history_answer_leaves_the_gap(watch, bad):
    lowered_prismatic(watch)
    watch.history[850] = bad

    result = run(watch, PRISMATIC)

    assert result.prices == {} and result.warnings == []


def test_a_failed_step_does_not_stop_the_next_one(watch):
    watch.ratios = SourceError("HTTP 500")
    watch.get["currency"] = SourceError("HTTP 500")
    watch.get["essence"] = copy.deepcopy(watch.get["essence"])
    watch.get["essence"][0]["lowConfidence"] = False

    assert run(watch, WEEPING).prices["Weeping Essence of Contempt"].chaos == 1

