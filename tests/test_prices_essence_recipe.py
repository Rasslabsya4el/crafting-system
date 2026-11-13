"""The lower essence tiers priced from the vendor upgrade recipe (#885): three of a tier make one of the next tier of the same type.

Every number is made up and worked by hand. With a Deafening tier at 2.7 Chaos: Shrieking 2.7 / 3 = 0.9, Screaming 0.9 / 3 = 0.3,
Wailing 0.1, Weeping 0.1 / 3, Muttering 0.1 / 9. With a Deafening tier at 3.0, Shrieking is 1.0 whatever its own row says (0.6 too),
and Screaming 1.0 / 3. A hand price of 5.0 on Shrieking stays, and Screaming is 5.0 / 3.
"""

from datetime import UTC, datetime

import pytest

from crafting_system.prices import PriceEntry, PriceFile, load_price_file, load_prices, write_price_file
from crafting_system.prices.essence_recipe import PER_UPGRADE, RECIPE_SOURCE, TIERS, apply_upgrade_recipe, has_recipe_rows, tier_of
from crafting_system.prices.price_marks import DEPTH, EARLIER, FROM_RECIPE, NO_DEPTH, NOT_RECORDED, price_marks
from crafting_system.prices.provenance import HISTORY, PREVIOUS_LEAGUE, RECIPE, TRADE, Provenance
from crafting_system.rules import get_rule

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
    assert PER_UPGRADE == get_rule("essence.vendor_upgrade_recipe").value == 3
    assert tier_of("Shrieking Essence of Spite") == (5, "Essence of Spite")
    assert tier_of("Whispering Essence of Greed") == (0, "Essence of Greed")
    assert tier_of("Essence of Horror") is None  # a corrupted essence has no tier
    assert tier_of("Deafening Catalyst") is None
    assert tier_of("Remnant of Corruption") is None
    assert tier_of("Deafening Essence of ") is None


def test_every_tier_below_the_top_is_a_third_of_the_next_tier_up_whatever_row_it_had():
    before = file_of(
        {
            "Deafening Essence of Fear": of_the_day(2.7),
            "Shrieking Essence of Fear": previous_league(0.5),
            "Screaming Essence of Fear": of_the_day(0.4),
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


def test_a_row_the_rule_writes_says_what_it_is_a_third_of_what_it_rests_on_and_what_it_replaced():
    after, _ = apply_upgrade_recipe(
        file_of({"Deafening Essence of Fear": of_the_day(2.7), "Shrieking Essence of Fear": later_stand_in(4.0), "Screaming Essence of Fear": of_the_day(0.4)})
    )

    row = after.prices["Shrieking Essence of Fear"]
    assert row.source == RECIPE_SOURCE == "upgrade-recipe"
    assert row.provenance == Provenance(RECIPE, "Allflame", DAY)  # the league and day of the market price it rests on
    assert row.detail == {
        "league": "Allflame", "date": DAY, "recipe": "essence-upgrade", "of": "Deafening Essence of Fear", "of_chaos": 2.7, "per": 3,
        "anchor": "Deafening Essence of Fear", "steps": 1, "replaced": {"chaos": 4.0, "source": "trade-api"},
    }  # fmt: skip
    assert row.note.startswith("vendor upgrade recipe (#885): one third of Deafening Essence of Fear (2.7 Chaos); 3 essences of a tier make one of the next tier")
    assert row.note.endswith("it replaces the row of 4 Chaos (trade-api)")
    below = after.prices["Screaming Essence of Fear"].detail
    assert (below["of"], below["anchor"], below["steps"]) == ("Shrieking Essence of Fear", "Deafening Essence of Fear", 2)


@pytest.mark.parametrize("own_row", [of_the_day(0.6), of_the_day(0.03, depth=0.4), previous_league(0.6), later_stand_in(0.6), PriceEntry(0.6, "poe.ninja-history"), of_the_day(7.0)])
def test_a_lower_tiers_own_row_never_wins_a_cheaper_one_too(own_row):
    """The owner's decision: one market price per type. A cheap row of a tier nobody trades (one seller, a fraction of a unit) is as odd
    as a dear one, and a plan priced at it would look cheaper than it is."""
    before = file_of({"Deafening Essence of Greed": of_the_day(3.0), "Shrieking Essence of Greed": own_row, "Screaming Essence of Greed": of_the_day(0.25)})

    after, notes = apply_upgrade_recipe(before)

    assert after.prices["Shrieking Essence of Greed"].chaos == pytest.approx(1.0)
    assert after.prices["Shrieking Essence of Greed"].source == RECIPE_SOURCE
    assert after.prices["Shrieking Essence of Greed"].detail["replaced"] == {"chaos": own_row.chaos, "source": own_row.source}
    assert after.prices["Screaming Essence of Greed"].chaos == pytest.approx(1.0 / 3)
    assert len(notes) == 2


def test_a_hand_price_is_kept_dearer_or_cheaper_and_the_tiers_below_are_a_third_of_it():
    dear, cheap = PriceEntry(5.0, "override"), PriceEntry(0.2, "override")
    after, _ = apply_upgrade_recipe(
        file_of(
            {
                "Deafening Essence of Hatred": of_the_day(3.0), "Shrieking Essence of Hatred": dear, "Screaming Essence of Hatred": later_stand_in(9.0),
                "Deafening Essence of Woe": of_the_day(3.0), "Shrieking Essence of Woe": cheap, "Screaming Essence of Woe": later_stand_in(9.0),
            }
        )
    )  # fmt: skip

    assert after.prices["Shrieking Essence of Hatred"] == dear and after.prices["Shrieking Essence of Woe"] == cheap
    assert after.prices["Screaming Essence of Hatred"].chaos == pytest.approx(5.0 / 3)
    assert after.prices["Screaming Essence of Woe"].chaos == pytest.approx(0.2 / 3)
    below = after.prices["Screaming Essence of Hatred"].detail
    assert (below["anchor"], below["steps"]) == ("Shrieking Essence of Hatred", 1)  # the hand price is what the tiers below it rest on


def test_a_type_with_no_deafening_row_starts_at_its_highest_market_row_and_the_notes_say_so():
    before = file_of({"Screaming Essence of Woe": of_the_day(0.9), "Wailing Essence of Woe": later_stand_in(2.0), "Muttering Essence of Fear": later_stand_in(87.18)})

    after, notes = apply_upgrade_recipe(before)

    assert after.prices["Screaming Essence of Woe"].chaos == 0.9
    assert after.prices["Wailing Essence of Woe"].chaos == pytest.approx(0.3)
    assert "Shrieking Essence of Woe" not in after.prices and "Deafening Essence of Woe" not in after.prices  # the recipe goes up, never down
    assert after.prices["Muttering Essence of Fear"] == before.prices["Muttering Essence of Fear"]  # nothing prices it from above
    assert notes == [
        "Screaming Essence of Woe: kept, the highest tier of Essence of Woe the file has a market row for; no Deafening row prices it from above",
        "Wailing Essence of Woe: 0.3 Chaos, one third of Screaming Essence of Woe; before: 2 Chaos (trade-api)",
        "Muttering Essence of Fear: kept, the highest tier of Essence of Fear the file has a market row for; no Deafening row prices it from above",
    ]


def test_a_wanted_lower_tier_gets_a_row_and_a_type_with_no_price_stays_unpriced():
    before = file_of({"Deafening Essence of Zeal": of_the_day(5.4)})

    after, notes = apply_upgrade_recipe(before, wanted=["Screaming Essence of Zeal", "Shrieking Essence of Envy", "Deafening Essence of Envy", "Orb of Alchemy", "Essence of Insanity"])

    assert after.prices["Shrieking Essence of Zeal"].chaos == pytest.approx(1.8)
    assert after.prices["Screaming Essence of Zeal"].chaos == pytest.approx(0.6)
    assert "replaced" not in after.prices["Screaming Essence of Zeal"].detail
    assert sorted(after.prices) == ["Deafening Essence of Zeal", "Screaming Essence of Zeal", "Shrieking Essence of Zeal"]  # Envy has no tier priced
    assert len(notes) == 2


def test_a_recipe_row_is_never_what_a_chain_starts_from():
    """A file whose market row of a type is gone keeps the recipe rows it has, says so, and prices no further tier from them."""
    built, _ = apply_upgrade_recipe(file_of({"Deafening Essence of Fear": of_the_day(2.7), "Shrieking Essence of Fear": later_stand_in(4.0)}))
    orphan = file_of({"Shrieking Essence of Fear": built.prices["Shrieking Essence of Fear"]})

    after, notes = apply_upgrade_recipe(orphan, wanted=["Screaming Essence of Fear"])

    assert after == orphan
    assert notes == ["Shrieking Essence of Fear: kept, a recipe row of Essence of Fear with no market row of its type left to rest on"]
    assert [mark.code for mark in price_marks(after.prices["Shrieking Essence of Fear"], after, 1.0)] == [FROM_RECIPE, NOT_RECORDED]


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
            assert entry.chaos == pytest.approx(upper.chaos / 3), name
    assert after.prices["Muttering Essence of Fear"].chaos == pytest.approx(2.03 / 243)  # five tiers below: 3 ** 5
    assert after.prices["Wailing Essence of Anguish"].chaos == pytest.approx(1.9 / 27)
    again, notes = apply_upgrade_recipe(after, wanted=["Wailing Essence of Anguish"])
    assert again == after and notes == []
    assert again.prices["Muttering Essence of Fear"].detail["replaced"] == {"chaos": 87.18, "source": "trade-api"}  # what it first replaced is kept


def test_a_recipe_row_with_a_broken_record_of_what_it_replaced_is_rewritten_without_it():
    built, _ = apply_upgrade_recipe(file_of({"Deafening Essence of Fear": of_the_day(2.7), "Shrieking Essence of Fear": later_stand_in(4.0)}))
    row = built.prices["Shrieking Essence of Fear"]
    broken = file_of({**built.prices, "Shrieking Essence of Fear": PriceEntry(row.chaos, row.source, row.note, {**row.detail, "replaced": {}}, row.provenance)})

    after, _ = apply_upgrade_recipe(broken)

    assert "replaced" not in after.prices["Shrieking Essence of Fear"].detail
    assert after.prices["Shrieking Essence of Fear"].chaos == pytest.approx(0.9)


def test_a_recipe_price_is_an_approximate_input_and_is_judged_by_the_market_price_it_rests_on():
    """Deafening Fear traded 100 units on the day. A plan that uses 270 Shrieking needs 90 Deafening (deep enough); one that uses 1,000
    Screaming needs 1,000 / 9 = 111 (not deep enough). Dread's only market row is Mirage's; Rage's has no recorded depth."""
    after, _ = apply_upgrade_recipe(
        file_of(
            {
                "Deafening Essence of Fear": of_the_day(2.7, depth=100.0),
                "Shrieking Essence of Fear": later_stand_in(4.0),
                "Screaming Essence of Fear": later_stand_in(4.0),
                "Deafening Essence of Dread": previous_league(1.5),
                "Shrieking Essence of Dread": later_stand_in(4.0),
                "Deafening Essence of Rage": later_stand_in(6.0),
                "Shrieking Essence of Rage": of_the_day(1.0),
            }
        )
    )

    def marks(name, uses):
        return [(mark.code, mark.reason) for mark in price_marks(after.prices[name], after, uses)]

    assert marks("Shrieking Essence of Fear", 270.0) == [(FROM_RECIPE, "priced from the vendor recipe: one third of Deafening Essence of Fear")]
    assert marks("Screaming Essence of Fear", 1000.0) == [
        (FROM_RECIPE, "priced from the vendor recipe: one third of Shrieking Essence of Fear"),
        (DEPTH, "Deafening Essence of Fear: price on 100 units"),
    ]
    assert marks("Screaming Essence of Fear", 900.0)[1:] == []  # 900 / 9 = 100 units: as deep as the plan needs
    assert marks("Shrieking Essence of Dread", 1.0)[1:] == [(EARLIER, "Deafening Essence of Dread: previous league's price (Mirage, 2026-03-13)")]
    assert [code for code, _ in marks("Shrieking Essence of Rage", 1.0)] == [FROM_RECIPE, "later-day", NO_DEPTH]
    assert after.prices["Shrieking Essence of Fear"].provenance.words == "vendor upgrade recipe, Allflame, 2026-07-31"
    assert after.prices["Shrieking Essence of Dread"].provenance.words == "vendor upgrade recipe, Mirage, 2026-03-13"


def test_a_recipe_row_is_written_to_the_price_file_and_read_back(tmp_path):
    after, _ = apply_upgrade_recipe(file_of({"Deafening Essence of Fear": of_the_day(2.7), "Shrieking Essence of Fear": later_stand_in(4.0)}))
    path = tmp_path / "prices.json"

    write_price_file(path, after)

    assert load_price_file(path) == after
    assert has_recipe_rows(after) and not has_recipe_rows(file_of({"Deafening Essence of Fear": of_the_day(2.7)}))


def test_a_hand_price_laid_over_the_file_reaches_the_tiers_below_it(tmp_path):
    """The overrides file is read after any fetch (`load_prices`). Deafening Fear 9 by hand: Shrieking 3, Screaming 1. Shrieking Greed 1.5
    by hand under a market Deafening of 3.0: it stays 1.5, and Screaming is 0.5, not the 1.0 / 3 the file was written with."""
    built, _ = apply_upgrade_recipe(
        file_of(
            {
                "Deafening Essence of Fear": of_the_day(2.7), "Shrieking Essence of Fear": later_stand_in(4.0), "Screaming Essence of Fear": later_stand_in(4.0),
                "Deafening Essence of Greed": of_the_day(3.0), "Shrieking Essence of Greed": later_stand_in(4.0), "Screaming Essence of Greed": later_stand_in(4.0),
            }
        )
    )  # fmt: skip
    path, overrides = tmp_path / "prices.json", tmp_path / "price_overrides.toml"
    write_price_file(path, built)
    overrides.write_text('[prices]\n"Deafening Essence of Fear" = 9\n"Shrieking Essence of Greed" = 1.5\n', encoding="utf-8")

    merged = load_prices(path, overrides)

    chaos = {name: entry.chaos for name, entry in merged.prices.items()}
    assert (chaos["Deafening Essence of Fear"], chaos["Shrieking Essence of Fear"], chaos["Screaming Essence of Fear"]) == (9.0, pytest.approx(3.0), pytest.approx(1.0))
    assert (chaos["Deafening Essence of Greed"], chaos["Shrieking Essence of Greed"], chaos["Screaming Essence of Greed"]) == (3.0, 1.5, pytest.approx(0.5))
    assert merged.prices["Shrieking Essence of Greed"].source == "override"
    assert merged.prices["Screaming Essence of Greed"].detail["anchor"] == "Shrieking Essence of Greed"
    assert load_prices(path, tmp_path / "none.toml") == built  # no overrides: the file as written


def test_a_file_with_no_recipe_row_is_read_with_its_overrides_and_nothing_else_changes(tmp_path):
    """A file written before the rule keeps its lower tiers as they are, with or without a hand price: it is priced anew at its next fetch."""
    old = file_of({"Deafening Essence of Fear": of_the_day(2.7), "Shrieking Essence of Fear": later_stand_in(4.0)})
    path, overrides = tmp_path / "prices.json", tmp_path / "price_overrides.toml"
    write_price_file(path, old)
    overrides.write_text('[prices]\n"Deafening Essence of Fear" = 9\n', encoding="utf-8")

    merged = load_prices(path, overrides)

    assert merged.prices["Shrieking Essence of Fear"] == old.prices["Shrieking Essence of Fear"]
    assert merged.prices["Deafening Essence of Fear"].chaos == 9.0
