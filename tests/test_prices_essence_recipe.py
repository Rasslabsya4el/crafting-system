"""The lower essence tiers priced from the vendor upgrade recipe (#885): three of a tier make one of the next tier of the same type.

Every number is made up and worked by hand. With a Deafening tier at 2.7 Chaos: Shrieking 2.7 / 3 = 0.9, Screaming 0.9 / 3 = 0.3,
Wailing 0.1, Weeping 0.1 / 3, Muttering 0.1 / 9. With a Shrieking row of the day at 0.6 under a Deafening tier at 3.0 (a third is 1.0),
the row is cheaper and stays, and Screaming is 0.6 / 3 = 0.2.
"""

from datetime import UTC, datetime

import pytest

from crafting_system.prices import PriceEntry, PriceFile, load_price_file, write_price_file
from crafting_system.prices.essence_recipe import PER_UPGRADE, RECIPE_SOURCE, TIERS, apply_upgrade_recipe, tier_of
from crafting_system.prices.price_marks import FROM_RECIPE, OTHER_LEAGUE, price_marks
from crafting_system.prices.provenance import HISTORY, PREVIOUS_LEAGUE, RECIPE, TRADE, Provenance

DAY = "2026-07-31"
FETCHED = datetime(2026, 7, 31, tzinfo=UTC)


def of_the_day(chaos: float, depth: float = 100.0) -> PriceEntry:
    """A poe.ninja daily row of the file's own league and day: a plain fact."""
    return PriceEntry(chaos, "poe.ninja-history", None, {"league": "Allflame", "date": DAY}, Provenance(HISTORY, "Allflame", DAY, depth))


def previous_league(chaos: float) -> PriceEntry:
    return PriceEntry(chaos, "poe.ninja-previous-league", None, {"league": "Mirage", "date": "2026-03-13"}, Provenance(PREVIOUS_LEAGUE, "Mirage", "2026-03-13", 50.0))


def later_stand_in(chaos: float) -> PriceEntry:
    """A trade reading of the league's end kept in a file of league day 7 (#838): marked as a later day's price."""
    return PriceEntry(chaos, "trade-api", "stand-in", {"league": "Allflame", "date": "2026-11-10"}, Provenance(TRADE, "Allflame", "2026-11-10"))


def file_of(prices: dict[str, PriceEntry]) -> PriceFile:
    return PriceFile("Allflame", FETCHED, 176.6, prices)


def test_a_tiered_essence_is_told_by_its_tier_word_and_its_type():
    assert TIERS == ("Whispering", "Muttering", "Weeping", "Wailing", "Screaming", "Shrieking", "Deafening")
    assert PER_UPGRADE == 3
    assert tier_of("Shrieking Essence of Spite") == (5, "Essence of Spite")
    assert tier_of("Whispering Essence of Greed") == (0, "Essence of Greed")
    assert tier_of("Essence of Horror") is None  # a corrupted essence has no tier
    assert tier_of("Deafening Catalyst") is None
    assert tier_of("Remnant of Corruption") is None


def test_every_tier_below_the_top_is_a_third_of_the_next_tier_up_whatever_row_it_had():
    before = file_of(
        {
            "Deafening Essence of Fear": of_the_day(2.7),
            "Shrieking Essence of Fear": previous_league(0.5),  # cheaper than 0.9, but a previous league's price is no evidence of this market
            "Screaming Essence of Fear": of_the_day(0.4),  # a row of the day, dearer than 0.3: nobody pays it
            "Muttering Essence of Fear": later_stand_in(87.18),
            "Essence of Horror": of_the_day(25.6),
            "Chaos Orb": PriceEntry(1.0, "poe.ninja"),
        }
    )

    after, notes = apply_upgrade_recipe(before)

    chaos = {name: entry.chaos for name, entry in after.prices.items()}
    assert chaos["Deafening Essence of Fear"] == 2.7
    assert chaos["Shrieking Essence of Fear"] == pytest.approx(0.9)
    assert chaos["Screaming Essence of Fear"] == pytest.approx(0.3)
    assert chaos["Wailing Essence of Fear"] == pytest.approx(0.1)  # no row before: the chain passes through it
    assert chaos["Weeping Essence of Fear"] == pytest.approx(0.1 / 3)
    assert chaos["Muttering Essence of Fear"] == pytest.approx(0.1 / 9)
    assert "Whispering Essence of Fear" not in chaos  # nothing names it: the chain stops at the lowest tier named
    assert after.prices["Essence of Horror"] == before.prices["Essence of Horror"] and after.prices["Chaos Orb"] == before.prices["Chaos Orb"]
    assert after.prices["Deafening Essence of Fear"] == before.prices["Deafening Essence of Fear"]
    assert [note.split(":")[0] for note in notes] == [f"{tier} Essence of Fear" for tier in ("Shrieking", "Screaming", "Wailing", "Weeping", "Muttering")]
    assert notes[0] == "Shrieking Essence of Fear: 0.9 Chaos, one third of Deafening Essence of Fear; before: 0.5 Chaos (poe.ninja-previous-league)"
    assert notes[2] == "Wailing Essence of Fear: 0.1 Chaos, one third of Screaming Essence of Fear; before: no row"


def test_a_row_the_rule_writes_says_what_it_is_a_third_of_and_what_it_replaced():
    after, _ = apply_upgrade_recipe(file_of({"Deafening Essence of Fear": of_the_day(2.7), "Shrieking Essence of Fear": later_stand_in(4.0)}))

    row = after.prices["Shrieking Essence of Fear"]
    assert row.source == RECIPE_SOURCE == "upgrade-recipe"
    assert row.provenance == Provenance(RECIPE, "Allflame", DAY)  # the league and day of the price it rests on
    assert row.detail == {
        "league": "Allflame", "date": DAY, "recipe": "essence-upgrade", "of": "Deafening Essence of Fear", "of_chaos": 2.7, "per": 3,
        "replaced": {"chaos": 4.0, "source": "trade-api"},
    }  # fmt: skip
    assert row.note.startswith("vendor upgrade recipe (#885): one third of Deafening Essence of Fear (2.7 Chaos); 3 essences of a tier make one of the next tier")
    assert row.note.endswith("it replaces the row of 4 Chaos (trade-api)")


def test_a_cheaper_row_of_the_day_wins_and_the_tier_below_is_a_third_of_it():
    before = file_of(
        {
            "Deafening Essence of Greed": of_the_day(3.0),
            "Shrieking Essence of Greed": of_the_day(0.6),  # below 3.0 / 3 = 1.0: a player buys it
            "Screaming Essence of Greed": of_the_day(0.25),  # above 0.6 / 3 = 0.2
        }
    )

    after, notes = apply_upgrade_recipe(before)

    assert after.prices["Shrieking Essence of Greed"] == before.prices["Shrieking Essence of Greed"]
    assert after.prices["Screaming Essence of Greed"].chaos == pytest.approx(0.2)
    assert after.prices["Screaming Essence of Greed"].detail["of"] == "Shrieking Essence of Greed"
    assert len(notes) == 1


@pytest.mark.parametrize("marked", [previous_league(0.6), later_stand_in(0.6), PriceEntry(0.6, "poe.ninja-history")])
def test_a_cheaper_row_that_is_no_plain_fact_does_not_win(marked):
    """A previous league's price, a stand-in of another day and a row with no recorded provenance are marked: no evidence of a cheaper market."""
    after, _ = apply_upgrade_recipe(file_of({"Deafening Essence of Greed": of_the_day(3.0), "Shrieking Essence of Greed": marked}))

    assert after.prices["Shrieking Essence of Greed"].chaos == pytest.approx(1.0)
    assert after.prices["Shrieking Essence of Greed"].source == RECIPE_SOURCE


def test_a_hand_price_is_kept_even_when_dearer_and_the_tier_below_is_a_third_of_it():
    hand = PriceEntry(5.0, "override")
    after, _ = apply_upgrade_recipe(file_of({"Deafening Essence of Hatred": of_the_day(3.0), "Shrieking Essence of Hatred": hand, "Screaming Essence of Hatred": later_stand_in(9.0)}))

    assert after.prices["Shrieking Essence of Hatred"] == hand
    assert after.prices["Screaming Essence of Hatred"].chaos == pytest.approx(5.0 / 3)


def test_the_highest_tier_the_file_prices_is_the_start_when_it_has_no_deafening_row():
    after, _ = apply_upgrade_recipe(file_of({"Screaming Essence of Woe": of_the_day(0.9), "Wailing Essence of Woe": later_stand_in(2.0)}))

    assert after.prices["Screaming Essence of Woe"].chaos == 0.9
    assert after.prices["Wailing Essence of Woe"].chaos == pytest.approx(0.3)
    assert "Shrieking Essence of Woe" not in after.prices and "Deafening Essence of Woe" not in after.prices  # the recipe goes up, never down


def test_a_wanted_lower_tier_gets_a_row_and_a_type_with_no_price_stays_unpriced():
    before = file_of({"Deafening Essence of Zeal": of_the_day(5.4)})

    after, notes = apply_upgrade_recipe(before, wanted=["Screaming Essence of Zeal", "Shrieking Essence of Envy", "Orb of Alchemy", "Essence of Insanity"])

    assert after.prices["Shrieking Essence of Zeal"].chaos == pytest.approx(1.8)
    assert after.prices["Screaming Essence of Zeal"].chaos == pytest.approx(0.6)
    assert "replaced" not in after.prices["Screaming Essence of Zeal"].detail
    assert sorted(after.prices) == ["Deafening Essence of Zeal", "Screaming Essence of Zeal", "Shrieking Essence of Zeal"]  # Envy has no tier priced
    assert len(notes) == 2


def test_no_lower_tier_costs_more_than_a_third_of_its_upper_tier_and_the_rule_applied_twice_changes_nothing():
    before = file_of(
        {
            "Deafening Essence of Fear": of_the_day(2.03),
            "Shrieking Essence of Fear": previous_league(0.85),
            "Screaming Essence of Fear": of_the_day(0.4),
            "Wailing Essence of Fear": later_stand_in(2.62),
            "Weeping Essence of Fear": later_stand_in(2.99),
            "Muttering Essence of Fear": later_stand_in(87.18),
            "Deafening Essence of Anguish": of_the_day(1.9),
            "Shrieking Essence of Anguish": of_the_day(0.38),
            "Screaming Essence of Anguish": previous_league(0.43),
        }
    )

    after, _ = apply_upgrade_recipe(before, wanted=["Wailing Essence of Anguish"])

    for name, entry in after.prices.items():
        index, kind = tier_of(name)
        upper = after.prices.get(f"{TIERS[index + 1]} {kind}") if index + 1 < len(TIERS) else None
        if upper is not None:
            assert entry.chaos <= upper.chaos / 3 + 1e-12, name
    assert after.prices["Shrieking Essence of Anguish"].chaos == 0.38  # 0.38 < 1.9 / 3: the row of the day
    assert after.prices["Wailing Essence of Anguish"].chaos == pytest.approx(0.38 / 9)
    again, notes = apply_upgrade_recipe(after, wanted=["Wailing Essence of Anguish"])
    assert again == after and notes == []
    assert again.prices["Muttering Essence of Fear"].detail["replaced"] == {"chaos": 87.18, "source": "trade-api"}  # what it first replaced is kept


def test_a_recipe_price_is_an_approximate_input_marked_with_the_tier_it_is_a_third_of():
    after, _ = apply_upgrade_recipe(
        file_of(
            {
                "Deafening Essence of Fear": of_the_day(2.7),
                "Shrieking Essence of Fear": later_stand_in(4.0),
                "Deafening Essence of Dread": previous_league(1.5),  # the type's only price is a previous league's
                "Shrieking Essence of Dread": later_stand_in(4.0),
            }
        )
    )

    marks = price_marks(after.prices["Shrieking Essence of Fear"], after, 1000.0)  # a recipe price has no depth to fall short of
    assert [(mark.code, mark.reason) for mark in marks] == [(FROM_RECIPE, "priced from the vendor recipe: one third of Deafening Essence of Fear")]
    rests_on_mirage = price_marks(after.prices["Shrieking Essence of Dread"], after, 1.0)
    assert [mark.code for mark in rests_on_mirage] == [OTHER_LEAGUE, FROM_RECIPE]
    assert rests_on_mirage[0].reason == "price of league Mirage (2026-03-13)"
    assert after.prices["Shrieking Essence of Fear"].provenance.words == "vendor upgrade recipe, Allflame, 2026-07-31"


def test_a_recipe_row_is_written_to_the_price_file_and_read_back(tmp_path):
    after, _ = apply_upgrade_recipe(file_of({"Deafening Essence of Fear": of_the_day(2.7), "Shrieking Essence of Fear": later_stand_in(4.0)}))
    path = tmp_path / "prices.json"

    write_price_file(path, after)

    assert load_price_file(path) == after
