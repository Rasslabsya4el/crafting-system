"""The integer formula of the tier cut (ticket #275, ADR-0040) against the numbers the sources publish.

"Done when": every cell of the wiki's breakpoint table agrees (`fixtures/strands/wiki_breakpoints.json`, which carries the page's URL); the
1,902 usable rows of the first author's raw sheet never fall below the bound and the bound equals the sheet's own `lowest_expected_tier`
(`fixtures/strands/sheet_rows.json`, a fixture of numbers); the Foulborn list 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7 at 0 strands, the
8-tier table at 81 and 82 strands, and the 491 Foulborn rows of the sheet agree with `+75`. These tests need no game data.
"""

import json
from collections import Counter
from fractions import Fraction
from math import floor
from pathlib import Path

import pytest

from crafting_system.actions.cut import Cut, rollable_tiers, strand_rating
from crafting_system.items import MemoryStrandsError
from crafting_system.rules import get_rule

FIXTURES = Path(__file__).parent / "fixtures" / "strands"
WIKI = json.loads((FIXTURES / "wiki_breakpoints.json").read_text(encoding="utf-8"))
SHEET = json.loads((FIXTURES / "sheet_rows.json").read_text(encoding="utf-8"))
ROWS = [dict(zip(SHEET["columns"], row, strict=True)) for row in SHEET["rows"]]
FOULBORN_LIST = [1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7]  # kept tiers for N = 1 to 13 eligible tiers, the wiki's Foulborn page


def is_foulborn(row: dict) -> bool:
    return row["currency"].startswith("Foulborn")


def wiki_formula(total_tiers: int, strands: int, foulborn: bool) -> int:
    """The wiki's formula as printed, in exact fractions: floor(100 / (2.5 s + 147.5 + 75 [Foulborn]) * (T - 1)) + 1.

    The page prints it for one strand or more. At 0 strands the rating is the base 100 alone, with no 2.5 s + 47.5.
    """
    rating = Fraction(100) + (Fraction(5 * strands + 95, 2) if strands >= 1 else 0) + (75 if foulborn else 0)
    return floor(Fraction(100 * (total_tiers - 1)) / rating) + 1


# --- the wiki's breakpoint table ----------------------------------------------------------------------------------------------


def test_the_fixture_of_the_wiki_table_carries_its_url():
    assert WIKI["url"] == "https://www.poewiki.net/wiki/Memory_Strands"
    assert WIKI["total_tiers"] == list(range(13, 1, -1))
    assert [row[0] for row in WIKI["rows"]][:3] == [0, 1, 2]


def test_every_cell_of_the_wikis_breakpoint_table_agrees():
    wrong = []
    cells = 0
    for strands, row in WIKI["rows"]:
        for tiers, shown in zip(WIKI["total_tiers"], row, strict=True):
            if shown is None:
                continue
            cells += 1
            if rollable_tiers(tiers, strands) != shown:
                wrong.append((strands, tiers, shown, rollable_tiers(tiers, strands)))
    assert cells == 61  # 12 cells of row 0 (no cut) and 49 breakpoints
    assert wrong == []


def test_each_cell_is_the_first_strand_count_that_gives_its_number_and_the_table_lists_all_of_them():
    # The wiki shows a cell only at the first strand count with that number, so one strand fewer must give a larger one,
    # and every strand count in 1..122 at which a column changes has its cell (the table runs past the 100 an item can hold).
    shown = {(strands, tiers) for strands, row in WIKI["rows"] if strands >= 1 for tiers, cell in zip(WIKI["total_tiers"], row) if cell is not None}
    changes = {
        (strands, tiers)
        for tiers in WIKI["total_tiers"]
        for strands in range(1, 123)
        if rollable_tiers(tiers, strands) != rollable_tiers(tiers, strands - 1)
    }

    assert shown == changes


def test_the_formula_in_the_claim_is_the_wikis_and_is_the_one_in_exact_fractions():
    assert "rollable_tiers = floor((100/(2.5 * strands + 147.5)) * (total_tiers - 1)) + 1" in get_rule("memory_strands.rollable_tiers").quote
    for foulborn in (False, True):
        for strands in range(0, 123):
            for tiers in range(1, 31):
                assert rollable_tiers(tiers, strands, foulborn) == wiki_formula(tiers, strands, foulborn)


# --- the raw sheet ------------------------------------------------------------------------------------------------------------


def test_the_sheet_fixture_holds_the_1902_rows_of_the_research_by_currency():
    assert SHEET["url"].startswith("https://docs.google.com/spreadsheets/d/1UKTS29e1XghGTQQJBiu7TR3vrancnZxiyN3tBzj30WI/")
    assert len(ROWS) == 1902
    assert Counter(row["currency"] for row in ROWS) == {
        "Chaos Orb": 615,
        "Orb of Alchemy": 649,
        "Foulborn Orb of Augmentation": 427,
        "Foulborn Regal Orb": 64,
        "Exalted Orb": 83,
        "Regal Orb": 13,
        "Scroll of Wisdom": 51,
    }


def bound(row: dict) -> int:
    return rollable_tiers(row["total_tiers"], row["strands_before"], is_foulborn(row))


def test_no_row_of_the_sheet_falls_below_the_bound():
    below = [row for row in ROWS if row["observed_tier"] > bound(row)]

    assert below == []


def test_the_bound_equals_the_sheets_own_lowest_expected_tier_on_every_row():
    wrong = [row for row in ROWS if bound(row) != row["lowest_expected_tier"]]

    assert wrong == []


def test_814_rows_sit_exactly_on_the_bound_and_the_counts_by_currency_are_the_researchs():
    on_the_bound = Counter(row["currency"] for row in ROWS if row["observed_tier"] == bound(row))

    assert sum(on_the_bound.values()) == 814
    assert on_the_bound == {
        "Chaos Orb": 238,
        "Orb of Alchemy": 274,
        "Foulborn Orb of Augmentation": 207,
        "Foulborn Regal Orb": 32,
        "Exalted Orb": 26,
        "Regal Orb": 6,
        "Scroll of Wisdom": 31,
    }


# --- the Foulborn orb ---------------------------------------------------------------------------------------------------------


def test_a_foulborn_orb_on_an_item_with_no_strands_keeps_the_wikis_list_for_one_to_thirteen_tiers():
    assert [rollable_tiers(tiers, 0, foulborn=True) for tiers in range(1, 14)] == FOULBORN_LIST


def test_the_foulborn_list_is_the_cut_of_eleven_strands():
    # D = 175 is the denominator of 11 strands: 2.5 * 11 + 147.5 = 175 (the author's "exactly matched that of 10-11 strands").
    assert strand_rating(0, foulborn=True) == strand_rating(11) == 350
    assert [rollable_tiers(tiers, 11) for tiers in range(1, 14)] == FOULBORN_LIST


def test_eight_tiers_keep_three_at_81_strands_and_two_at_82():
    assert Fraction(200 * (8 - 1), strand_rating(81)) == 2  # exactly 2.0 before the floor: a float could land either side of it
    assert Fraction(200 * (8 - 1), strand_rating(82)) < 2
    assert rollable_tiers(8, 81) == 3
    assert rollable_tiers(8, 82) == 2
    assert rollable_tiers(8, 80) == 3


def test_the_491_foulborn_rows_of_the_sheet_agree_with_plus_75():
    foulborn = [row for row in ROWS if is_foulborn(row)]

    assert len(foulborn) == 491
    assert [row for row in foulborn if bound(row) != row["lowest_expected_tier"]] == []
    assert [row for row in foulborn if row["observed_tier"] > bound(row)] == []
    # The +75 is added to the denominator (a Foulborn orb acts as 30 strands more), not the larger of two cuts, and it matters:
    assert all(rollable_tiers(row["total_tiers"], row["strands_before"], True) == rollable_tiers(row["total_tiers"], row["strands_before"] + 30) for row in foulborn)
    assert sum(rollable_tiers(row["total_tiers"], row["strands_before"], True) != rollable_tiers(row["total_tiers"], row["strands_before"]) for row in foulborn) > 100


def test_the_foulborn_bonus_in_the_cut_is_the_75_of_the_claim_doubled():
    assert get_rule("memory_strands.rollable_tiers").value["foulborn_rating"] == 2 * get_rule("foulborn.on_stranded_item").value["bonus_to_rating"]
    assert get_rule("memory_strands.rollable_tiers").value["foulborn_rating"] == 2 * get_rule("foulborn.bonus_is_added_to_the_strand_denominator").value["bonus_to_rating"]


# --- no strands, no cut; the shape of the answer ------------------------------------------------------------------------------


def test_with_no_strands_and_no_foulborn_orb_every_tier_stays():
    assert [rollable_tiers(tiers, 0) for tiers in range(1, 41)] == list(range(1, 41))
    assert strand_rating(0) == 200


def test_one_strand_already_cuts_thirteen_tiers_to_nine():
    assert rollable_tiers(13, 0) == 13
    assert rollable_tiers(13, 1) == 9


def test_the_kept_tiers_run_from_one_to_the_tiers_there_are_and_only_fall_as_strands_rise():
    for foulborn in (False, True):
        for tiers in range(1, 25):
            previous = None
            for strands in range(0, 101):
                kept = rollable_tiers(tiers, strands, foulborn)
                assert 1 <= kept <= tiers
                assert previous is None or kept <= previous
                previous = kept
            assert rollable_tiers(tiers, 40, True) <= rollable_tiers(tiers, 40)


def test_the_answer_is_an_int_and_a_float_is_never_involved():
    assert type(rollable_tiers(8, 81)) is int
    assert type(strand_rating(81)) is int


@pytest.mark.parametrize("tiers", [0, -1, 1.5, "8", None, True])
def test_a_table_without_a_whole_number_of_tiers_is_refused(tiers):
    with pytest.raises(ValueError):
        rollable_tiers(tiers, 10)


@pytest.mark.parametrize("strands", [-1, 1.0, "5", None])
def test_a_count_that_is_not_a_whole_number_from_zero_is_refused(strands):
    with pytest.raises(MemoryStrandsError):
        rollable_tiers(8, strands)


def test_the_formula_is_defined_past_the_100_an_item_can_hold_but_a_cut_is_not():
    assert (rollable_tiers(10, 121), rollable_tiers(10, 122)) == (3, 2)  # the last cell of the wiki table
    with pytest.raises(MemoryStrandsError):
        Cut(101)
    with pytest.raises(MemoryStrandsError):
        Cut(-1)
    with pytest.raises(MemoryStrandsError):
        Cut(1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Cut(5, foulborn=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Cut(5, reading="refactored")  # type: ignore[arg-type]
