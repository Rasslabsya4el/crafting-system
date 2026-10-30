"""The price file: shape, validation, round trip, overrides, staleness, missing prices (ADR-0007)."""

import json
from datetime import UTC, date, datetime

import pytest

from crafting_system.config import Config
from crafting_system.prices import (
    PriceEntry,
    PriceFile,
    PriceFileNotFound,
    default_overrides_path,
    default_price_file_path,
    load_overrides,
    load_price_file,
    load_prices,
    missing_prices,
    stale_warning,
    to_divine,
    write_price_file,
)

FETCHED_AT = datetime(2026, 10, 30, 20, 24, 0, tzinfo=UTC)


def sample_file(**changes) -> PriceFile:
    fields = {
        "league": "Allflame",
        "fetched_at": FETCHED_AT,
        "chaos_per_divine": 359.7,
        "prices": {
            "Chaos Orb": PriceEntry(1.0, "poe.ninja"),
            "Divine Orb": PriceEntry(359.7, "poe.ninja"),
            "Hollow Fossil": PriceEntry(
                158.5, "poe.ninja-history", "median of 7 daily rows up to 2026-10-30"
            ),
        },
    }
    fields.update(changes)
    return PriceFile(**fields)


def raw_document(**changes) -> dict:
    document = {
        "unit": "chaos",
        "league": "Allflame",
        "fetched_at": "2026-10-30T20:24:00Z",
        "chaos_per_divine": 359.7,
        "prices": {"Chaos Orb": {"chaos": 1, "source": "poe.ninja"}},
    }
    document.update(changes)
    return document


def write_raw(path, document) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


def test_a_written_price_file_reads_back_equal(tmp_path):
    path = tmp_path / "prices.json"
    original = sample_file()

    write_price_file(path, original)

    assert load_price_file(path) == original


def test_write_creates_the_parent_folder_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "data" / "deeper" / "prices.json"

    write_price_file(path, sample_file())

    assert [p.name for p in path.parent.iterdir()] == ["prices.json"]


def test_the_file_on_disk_has_sorted_keys_the_chaos_unit_and_a_utc_timestamp(tmp_path):
    path = tmp_path / "prices.json"

    write_price_file(path, sample_file())

    text = path.read_text(encoding="utf-8")
    document = json.loads(text)
    assert document["unit"] == "chaos"
    assert document["fetched_at"] == "2026-10-30T20:24:00Z"
    assert list(document) == sorted(document)
    assert list(document["prices"]) == sorted(document["prices"])
    assert text.startswith('{\n  "chaos_per_divine"')


def test_writing_over_an_existing_file_replaces_it(tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, sample_file(league="Old"))

    write_price_file(path, sample_file(league="New"))

    assert load_price_file(path).league == "New"


def test_to_divine_divides_by_the_divine_price():
    assert to_divine(719.4, sample_file()) == pytest.approx(2.0)


def test_default_paths_sit_in_the_data_folder(tmp_path):
    config = Config(data_dir=tmp_path / "d", cache_dir=tmp_path / "c", output_dir=tmp_path / "o")

    assert default_price_file_path(config) == tmp_path / "d" / "prices.json"
    assert default_overrides_path(config) == tmp_path / "d" / "price_overrides.toml"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"unit": "divine"}, "unit"),
        ({"league": ""}, "league"),
        ({"league": 5}, "league"),
        ({"fetched_at": "yesterday"}, "fetched_at"),
        ({"fetched_at": "2026-10-30T20:24:00"}, "fetched_at"),
        ({"fetched_at": 5}, "fetched_at"),
        ({"chaos_per_divine": 0}, "chaos_per_divine"),
        ({"chaos_per_divine": "359"}, "chaos_per_divine"),
        ({"prices": []}, "prices"),
        ({"prices": {"X": 5}}, "'X'"),
        ({"prices": {"X": {"source": "poe.ninja"}}}, "'X'"),
        ({"prices": {"X": {"chaos": 0, "source": "poe.ninja"}}}, "'X'"),
        ({"prices": {"X": {"chaos": -3, "source": "poe.ninja"}}}, "'X'"),
        ({"prices": {"X": {"chaos": "5", "source": "poe.ninja"}}}, "'X'"),
        ({"prices": {"X": {"chaos": True, "source": "poe.ninja"}}}, "'X'"),
        ({"prices": {"X": {"chaos": float("inf"), "source": "poe.ninja"}}}, "'X'"),
        ({"prices": {"X": {"chaos": 5}}}, "'X'"),
        ({"prices": {"X": {"chaos": 5, "source": "poe.ninja", "note": 3}}}, "'X'"),
        ({"prices": {"Chaos Orb": {"chaos": 2, "source": "poe.ninja"}}}, "Chaos Orb"),
    ],
)
def test_a_malformed_price_file_raises_value_error_naming_the_file(tmp_path, changes, message):
    path = tmp_path / "prices.json"
    write_raw(path, raw_document(**changes))

    with pytest.raises(ValueError, match="prices.json") as error:
        load_price_file(path)

    assert message in str(error.value)


@pytest.mark.parametrize(
    "missing_key", ["unit", "league", "fetched_at", "chaos_per_divine", "prices"]
)
def test_a_price_file_without_a_required_key_is_rejected(tmp_path, missing_key):
    path = tmp_path / "prices.json"
    document = raw_document()
    del document[missing_key]
    write_raw(path, document)

    with pytest.raises(ValueError, match=missing_key):
        load_price_file(path)


@pytest.mark.parametrize("text", ["", "not json", "[1, 2]", "5"])
def test_a_price_file_that_is_not_a_json_object_is_rejected(tmp_path, text):
    path = tmp_path / "prices.json"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="prices.json"):
        load_price_file(path)


def test_a_missing_price_file_says_to_run_the_fetcher(tmp_path):
    with pytest.raises(PriceFileNotFound, match="prices fetch"):
        load_price_file(tmp_path / "prices.json")


def test_a_timestamp_with_an_offset_is_read_as_the_same_instant_in_utc(tmp_path):
    path = tmp_path / "prices.json"
    write_raw(path, raw_document(fetched_at="2026-10-30T22:24:00+02:00"))

    assert load_price_file(path).fetched_at == FETCHED_AT


# --- overrides -----------------------------------------------------------------------------


def write_overrides(path, text) -> None:
    path.write_text(text, encoding="utf-8")


def test_a_missing_overrides_file_is_fine(tmp_path):
    assert load_overrides(tmp_path / "price_overrides.toml") == {}


def test_overrides_are_read_from_the_prices_table(tmp_path):
    path = tmp_path / "price_overrides.toml"
    write_overrides(path, '[prices]\n"Fracturing Orb" = 250\n"Hollow Fossil" = 12.5\n')

    assert load_overrides(path) == {"Fracturing Orb": 250.0, "Hollow Fossil": 12.5}


@pytest.mark.parametrize(
    "text",
    [
        '[prices]\n"Fracturing Orb" = -1\n',
        '[prices]\n"Fracturing Orb" = 0\n',
        '[prices]\n"Fracturing Orb" = "250"\n',
        '[prices]\n"Fracturing Orb" = true\n',
        '[prices]\n"Fracturing Orb" = inf\n',
        '[prices]\n"Chaos Orb" = 2\n',
        "prices = 5\n",
        'prices = ["a"]\n',
        "[other]\nx = 1\n",
        "[prices\n",
    ],
)
def test_bad_overrides_raise_value_error_naming_the_file(tmp_path, text):
    path = tmp_path / "price_overrides.toml"
    write_overrides(path, text)

    with pytest.raises(ValueError, match="price_overrides.toml"):
        load_overrides(path)


def test_an_override_wins_over_the_fetched_price_and_is_marked_as_such(tmp_path):
    prices_path = tmp_path / "prices.json"
    overrides_path = tmp_path / "price_overrides.toml"
    write_price_file(prices_path, sample_file())
    write_overrides(overrides_path, '[prices]\n"Hollow Fossil" = 20\n')

    merged = load_prices(prices_path, overrides_path)

    assert merged.prices["Hollow Fossil"] == PriceEntry(20.0, "override")
    assert merged.prices["Divine Orb"] == PriceEntry(359.7, "poe.ninja")


def test_an_override_adds_a_name_the_fetch_lacks(tmp_path):
    prices_path = tmp_path / "prices.json"
    overrides_path = tmp_path / "price_overrides.toml"
    write_price_file(prices_path, sample_file())
    write_overrides(overrides_path, '[prices]\n"Fracturing Orb" = 250\n')

    merged = load_prices(prices_path, overrides_path)

    assert merged.prices["Fracturing Orb"] == PriceEntry(250.0, "override")
    assert merged.league == "Allflame"
    assert merged.fetched_at == FETCHED_AT


def test_load_prices_works_without_an_overrides_file(tmp_path):
    prices_path = tmp_path / "prices.json"
    write_price_file(prices_path, sample_file())

    assert load_prices(prices_path, tmp_path / "price_overrides.toml") == sample_file()


def test_an_overridden_divine_price_also_sets_the_divine_equivalent(tmp_path):
    prices_path = tmp_path / "prices.json"
    overrides_path = tmp_path / "price_overrides.toml"
    write_price_file(prices_path, sample_file())
    write_overrides(overrides_path, '[prices]\n"Divine Orb" = 300\n')

    merged = load_prices(prices_path, overrides_path)

    assert merged.chaos_per_divine == 300.0
    assert to_divine(600, merged) == pytest.approx(2.0)


def test_overrides_without_a_price_file_say_to_run_the_fetcher(tmp_path):
    overrides_path = tmp_path / "price_overrides.toml"
    write_overrides(overrides_path, '[prices]\n"Fracturing Orb" = 250\n')

    with pytest.raises(PriceFileNotFound, match="prices fetch"):
        load_prices(tmp_path / "prices.json", overrides_path)


def test_a_refetch_leaves_the_overrides_file_byte_identical(tmp_path):
    prices_path = tmp_path / "prices.json"
    overrides_path = tmp_path / "price_overrides.toml"
    write_overrides(
        overrides_path, '# my hand edits\n[prices]\n"Fracturing Orb" = 250   # owner price\n'
    )
    before = overrides_path.read_bytes()

    write_price_file(prices_path, sample_file())
    write_price_file(prices_path, sample_file(league="Next"))

    assert overrides_path.read_bytes() == before


# --- staleness and missing prices ----------------------------------------------------------


def test_a_snapshot_exactly_seven_days_old_gives_no_warning():
    assert stale_warning(sample_file(), today=date(2026, 11, 6)) is None


def test_a_snapshot_eight_days_old_warns_with_its_date_and_age():
    warning = stale_warning(sample_file(), today=date(2026, 11, 7))

    assert warning is not None
    assert "2026-10-30" in warning
    assert "8 days" in warning


def test_a_fresh_snapshot_gives_no_warning():
    assert stale_warning(sample_file(), today=date(2026, 10, 30)) is None


def test_today_must_be_a_date_not_a_datetime():
    with pytest.raises(TypeError, match="today must be a date, not a datetime"):
        stale_warning(sample_file(), today=datetime(2026, 11, 7, 12, 0, tzinfo=UTC))


def test_the_age_limit_can_be_changed():
    assert stale_warning(sample_file(), today=date(2026, 11, 2), max_age_days=2) is not None
    assert stale_warning(sample_file(), today=date(2026, 11, 1), max_age_days=2) is None


def test_the_age_counts_from_the_utc_date_of_the_fetch():
    late_evening_utc = sample_file(fetched_at=datetime(2026, 10, 30, 23, 59, tzinfo=UTC))

    assert stale_warning(late_evening_utc, today=date(2026, 11, 6)) is None
    assert stale_warning(late_evening_utc, today=date(2026, 11, 7)) is not None


def test_missing_prices_are_sorted_and_listed_once():
    prices = sample_file().prices

    missing = missing_prices(["Zed", "Hollow Fossil", "Alpha", "Zed", "Chaos Orb"], prices)

    assert missing == ["Alpha", "Zed"]


def test_nothing_is_missing_when_everything_is_priced():
    assert missing_prices(["Chaos Orb"], sample_file().prices) == []


# --- the detail of a price (#39) ---------------------------------------------------------------

DETAIL = {"league": "Allflame", "listings": 910, "query": {"query": {"type": "x"}}}


def test_a_price_detail_is_written_and_reads_back_equal(tmp_path):
    path = tmp_path / "prices.json"
    original = sample_file(prices={"Chaos Orb": PriceEntry(1.0, "poe.ninja"), "Amulet": PriceEntry(2.0, "trade-api", "n", DETAIL)})

    write_price_file(path, original)

    assert load_price_file(path) == original
    assert json.loads(path.read_text(encoding="utf-8"))["prices"]["Amulet"]["detail"] == DETAIL


def test_a_price_without_a_detail_writes_no_detail_key(tmp_path):
    path = tmp_path / "prices.json"

    write_price_file(path, sample_file())

    assert all("detail" not in entry for entry in json.loads(path.read_text(encoding="utf-8"))["prices"].values())


def test_a_file_written_before_the_detail_existed_still_loads_with_no_detail(tmp_path):
    path = tmp_path / "prices.json"
    write_raw(path, raw_document())

    assert load_price_file(path).prices["Chaos Orb"].detail is None


@pytest.mark.parametrize("detail", [[1], "text", 5, True])
def test_a_detail_that_is_not_an_object_is_rejected_naming_file_and_price(tmp_path, detail):
    path = tmp_path / "prices.json"
    write_raw(path, raw_document(prices={"X": {"chaos": 5, "source": "trade-api", "detail": detail}}))

    with pytest.raises(ValueError, match="prices.json") as error:
        load_price_file(path)

    assert "'X'" in str(error.value) and "detail" in str(error.value)


def test_an_override_wins_over_a_price_that_carries_a_detail(tmp_path):
    write_price_file(
        tmp_path / "prices.json",
        sample_file(prices={"Amulet": PriceEntry(2.0, "trade-api", "n", DETAIL)}),
    )
    (tmp_path / "price_overrides.toml").write_text('[prices]\nAmulet = 9\n', encoding="utf-8")

    entry = load_prices(tmp_path / "prices.json", tmp_path / "price_overrides.toml").prices["Amulet"]

    assert entry == PriceEntry(9.0, "override")
    assert entry.detail is None


def test_a_hand_price_with_influences_in_any_order_is_the_canonical_wanted_name(tmp_path):
    path = tmp_path / "price_overrides.toml"
    write_overrides(
        path,
        '[prices]\n"Stygian Vise (ilvl 85, Warlord/Hunter)" = 900\n"Vaal Regalia (ilvl 86, warlord/ELDER)" = 50\n'
        '"Stygian Vise (ilvl 85)" = 7\n"Wild Bristle Matron" = 3\n',
    )

    assert load_overrides(path) == {
        "Stygian Vise (ilvl 85, Hunter/Warlord)": 900.0,
        "Vaal Regalia (ilvl 86, Elder/Warlord)": 50.0,
        "Stygian Vise (ilvl 85)": 7.0,
        "Wild Bristle Matron": 3.0,
    }


def test_a_hand_price_with_reordered_influences_prices_the_wanted_name(tmp_path):
    prices_path = tmp_path / "prices.json"
    overrides_path = tmp_path / "price_overrides.toml"
    write_price_file(prices_path, sample_file())
    write_overrides(overrides_path, '[prices]\n"Stygian Vise (ilvl 85, Warlord/Hunter)" = 900\n')

    merged = load_prices(prices_path, overrides_path)

    wanted = "Stygian Vise (ilvl 85, Hunter/Warlord)"
    assert merged.prices[wanted] == PriceEntry(900.0, "override")
    assert missing_prices([wanted], merged.prices) == []


def test_two_hand_prices_that_become_one_name_are_refused(tmp_path):
    path = tmp_path / "price_overrides.toml"
    write_overrides(
        path,
        '[prices]\n"Stygian Vise (ilvl 85, Warlord/Hunter)" = 900\n"Stygian Vise (ilvl 85, Hunter/Warlord)" = 800\n',
    )

    with pytest.raises(ValueError, match="price_overrides.toml.*same price name"):
        load_overrides(path)
