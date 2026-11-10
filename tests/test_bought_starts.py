"""The bought-base start options read from the price file (ticket #351, ADR-0061 decision 1, OR-8 as amended by #718, OR-12, OR-23).

The fixture `tests/fixtures/prices/bases-allflame-2026-11-01.json` holds the poe.ninja BaseType rows of research #337 (section 1.3, read
2026-11-01): Leather Belt at item level 84 / 85 / 86 for 1.7 / 1.0 / 10.0 Chaos (176 / 275 / 37 observations), Sorcerer Boots at
1.03 / 5.33 / 7.43 (36 / 84 / 32), influenced belts at 86 (Shaper 4.2, 13 observations; Elder 5.0, 20; Crusader 2.0 on 2, too thin to be a row),
and the two rarity orbs. These tests need the cached game data (`real_game_data` skips without it; CI fetches it). Nothing is solved.
"""

import dataclasses
from datetime import date
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import influence_mods
from crafting_system.cli import StartContext
from crafting_system.cli._bought_starts import MAGIC_ROW_MARK, ORB_OF_ALCHEMY, bought_base_starts, needed_influence_sets
from crafting_system.cli._start_types import NO_INFLUENCED_BASE, NO_PRICE, NOT_A_PLAIN_BASE, SOURCE_BOUGHT_BASE
from crafting_system.items import ExplicitMod, Influence, tier_table
from crafting_system.items.model import MAX_ITEM_LEVEL
from crafting_system.prices import PriceEntry, Provenance
from crafting_system.prices.price_file import DeepReading, MarketRecord, load_price_file
from crafting_system.prices.price_marks import NOT_RECORDED_WORDS
from crafting_system.targets import KOfN, StartKind, base_line_name, load_target
from crafting_system.targets.floor import target_at_level

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "examples" / "targets"
FIXTURE = ROOT / "tests" / "fixtures" / "prices" / "bases-allflame-2026-11-01.json"
ALCHEMY = 0.02716


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def prices():
    return load_price_file(FIXTURE)


@pytest.fixture(scope="module")
def r13(data):
    return load_target(TARGETS / "r13-life-resist-belt.yaml", data)


@pytest.fixture(scope="module")
def r08(data):
    return load_target(TARGETS / "r08-energy-shield-boots.yaml", data)


def rows(listed):
    return [(c.key, c.bought.level, c.bought.row_chaos, c.bought.ninja.observations) for c in listed.candidates]


def test_r13_lists_the_84_85_86_rows_at_the_fixture_prices(data, prices, r13):
    listed = bought_base_starts(StartContext(data, r13, prices))
    assert rows(listed) == [("base:84-84", 84, 1.7, 176.0), ("base:85-85", 85, 1.0, 275.0), ("base:86-100", 86, 10.0, 37.0)]
    assert listed.refused == ()
    first = listed.candidates[0]
    assert first.source == SOURCE_BOUGHT_BASE
    assert first.item.item_level == 84 and first.item.rarity.value == "magic"
    assert first.bought.group == (84, 84) and first.bought.rarity_orb is None
    # the Magic start is the belt the market sells (ADR-0064), not a Transmutation's: priced from the Normal row alone, and marked so
    assert first.price == 1.7 and [name for name, *_ in first.goods] == ["Leather Belt (ilvl 84)"]
    assert MAGIC_ROW_MARK in first.bought.input_marks
    assert listed.candidates[2].bought.group == (86, MAX_ITEM_LEVEL)


def test_r08_lists_the_84_85_86_rows_at_the_fixture_prices(data, prices, r08):
    listed = bought_base_starts(StartContext(data, r08, prices))
    assert rows(listed) == [("base:84-84", 84, 1.03, 36.0), ("base:85-85", 85, 5.33, 84.0), ("base:86-100", 86, 7.43, 32.0)]
    assert [c.price for c in listed.candidates] == pytest.approx([1.03 + ALCHEMY, 5.33 + ALCHEMY, 7.43 + ALCHEMY])
    assert all(c.bought.rarity_orb == ORB_OF_ALCHEMY for c in listed.candidates)


def test_a_poe_ninja_fallback_keeps_its_marks(data, prices, r13):
    """Under `both` with no trade price the poe.ninja row stands in, marked as the fallback it is and as no proof of a listing (OR-7)."""
    option = bought_base_starts(StartContext(data, r13, prices)).candidates[0]
    assert option.sourced.used == "poe.ninja" and option.sourced.fallback
    assert any(mark.startswith("fallback:") for mark in option.sourced.marks)
    assert "a poe.ninja row does not prove an instant-buyout listing exists" in option.sourced.marks
    assert option.bought.input_marks == (MAGIC_ROW_MARK,)  # 176 observations, one unit bought: the row itself is a plain fact of today's league


def test_a_base_with_no_price_from_the_chosen_source_has_no_option(data, prices, r13):
    """`trade` reads no poe.ninja row: no level has a price, so every group is refused and none is offered."""
    listed = bought_base_starts(StartContext(data, r13, prices, price_source="trade"))
    assert listed.candidates == ()
    assert [(r.recipe, r.reason) for r in listed.refused] == [("base:84-84", NO_PRICE), ("base:85-85", NO_PRICE), ("base:86-100", NO_PRICE)]
    assert "Leather Belt (ilvl 84)" in listed.refused[0].detail


def test_a_level_without_a_row_drops_only_its_group(data, prices, r13):
    without = dataclasses.replace(prices, prices={k: v for k, v in prices.prices.items() if k != "Leather Belt (ilvl 85)"})
    listed = bought_base_starts(StartContext(data, r13, without))
    assert [c.key for c in listed.candidates] == ["base:84-84", "base:86-100"]
    assert [(r.recipe, r.reason) for r in listed.refused] == [("base:85-85", NO_PRICE)]


def test_an_influenced_row(data, prices, r13):
    """A Shaper belt is priced from the Shaper row at 86; the 84 and 85 Shaper rows do not exist, so those groups are refused."""
    shaper = frozenset({Influence.SHAPER})
    target = dataclasses.replace(r13, influences=shaper, start_item=r13.start_item.changed(data, influences=shaper))
    listed = bought_base_starts(StartContext(data, target, prices))
    assert [(c.bought.influences, c.bought.level, c.bought.row_chaos, c.bought.ninja.observations) for c in listed.candidates] == [
        (("Shaper",), 86, 4.2, 13.0)
    ]
    option = listed.candidates[0]
    assert option.price_name == "Leather Belt (ilvl 86, Shaper)" and option.item.influences == shaper
    assert option.key.endswith(":Shaper")
    assert listed.refused and all(r.reason == NO_PRICE for r in listed.refused)


def test_a_poe_ninja_row_on_fewer_than_5_observations_is_not_a_row(data, prices, r13):
    crusader = frozenset({Influence.CRUSADER})
    target = dataclasses.replace(r13, influences=crusader, start_item=r13.start_item.changed(data, influences=crusader))
    listed = bought_base_starts(StartContext(data, target, prices))
    assert listed.candidates == ()
    assert any(
        "the poe.ninja row Leather Belt (ilvl 86, Crusader) rests on 2 observations, under 5" in r.detail for r in listed.refused
    )  # not dropped without a word


def test_a_thin_poe_ninja_row_beside_a_trade_price_is_said(data, prices, r13):
    """Under `both` a trade price is used; the thin row it would sit beside is named in the marks, not lost."""
    crusader = frozenset({Influence.CRUSADER})
    target = dataclasses.replace(r13, influences=crusader, start_item=r13.start_item.changed(data, influences=crusader))
    name = "Leather Belt (ilvl 86, Crusader)"
    record = MarketRecord("thin", "Allflame", date(2026, 11, 1), 4, 4, "hash", {"query": {}}, chaos=6.0, used=4)
    listed = bought_base_starts(StartContext(data, target, dataclasses.replace(prices, markets={name: record}), today=date(2026, 11, 1)))
    option = next(c for c in listed.candidates if c.bought.level == 86)
    assert option.bought.row_chaos == 6.0 and option.bought.ninja is None
    assert any("rests on 2 observations" in mark for mark in option.bought.input_marks)


def test_an_unpriced_rarity_orb_leaves_the_option_marked(data, prices, r08):
    """OR-23: a missing Orb of Alchemy price does not drop the option; it stands on the row, marked."""
    without = dataclasses.replace(prices, prices={k: v for k, v in prices.prices.items() if k != ORB_OF_ALCHEMY})
    listed = bought_base_starts(StartContext(data, r08, without))
    assert [c.price for c in listed.candidates] == [1.03, 5.33, 7.43]
    assert all(any(mark.startswith(f"no price for {ORB_OF_ALCHEMY}") for mark in c.bought.input_marks) for c in listed.candidates)


def test_the_rarity_orb_keeps_its_own_marks(data, prices, r08):
    option = bought_base_starts(StartContext(data, r08, prices)).candidates[0]
    assert f"{ORB_OF_ALCHEMY}: {NOT_RECORDED_WORDS}" in option.bought.input_marks  # the fixture's orb price carries no provenance


def test_a_requirement_only_an_influence_gives_adds_the_influenced_set(data, r13):
    """A plain belt whose requirement counts only Shaper mods may also start from a Shaper base."""
    shaper_mods = frozenset(influence_mods(data, r13.base_id, MAX_ITEM_LEVEL, Influence.SHAPER))
    asked = dataclasses.replace(r13.requirements[0], mod_ids=shaper_mods, tier_ok=None, min_tier=None)
    target = dataclasses.replace(r13, requirements=(asked, *r13.requirements[1:]))
    assert needed_influence_sets(data, target) == ((frozenset(), frozenset({Influence.SHAPER})), None)
    assert needed_influence_sets(data, r13) == ((frozenset(),), None)


def test_three_needed_influences_are_refused_with_words(data, prices, r13):
    leaf = next(each for each in r13.requirements if not isinstance(each, KOfN))
    asked = tuple(
        dataclasses.replace(leaf, mod_ids=frozenset(influence_mods(data, r13.base_id, MAX_ITEM_LEVEL, influence)), tier_ok=None, min_tier=None)
        for influence in (Influence.SHAPER, Influence.ELDER, Influence.CRUSADER)
    )
    target = dataclasses.replace(r13, requirements=asked)
    sets, why = needed_influence_sets(data, target)
    assert sets == (frozenset(),) and why is not None and "3 influences (Shaper, Elder, Crusader)" in why
    listed = bought_base_starts(StartContext(data, target, prices))
    assert any(r.reason == NO_INFLUENCED_BASE and r.detail == why for r in listed.refused)


def test_a_thin_trade_market_is_priced_old_and_keeps_its_mark(data, prices, r13):
    """OR-8 (#718): a thin trade book with a deep reading of the league is priced with that reading, marked old, beside the poe.ninja row."""
    name = "Leather Belt (ilvl 84)"
    record = MarketRecord("thin", "Allflame", date(2026, 11, 1), 4, 4, "hash", {"query": {}}, chaos=40.0, used=4)
    deep = DeepReading(2.5, "Allflame", date(2026, 10, 20), 30, 10)
    thin = dataclasses.replace(prices, markets={name: record}, deep={name: deep})
    option = bought_base_starts(StartContext(data, r13, thin, today=date(2026, 11, 1))).candidates[0]
    assert option.bought.row_chaos == 2.5 and option.bought.trade_chaos == 2.5
    assert option.sourced.used == "trade" and option.sourced.ninja_chaos == 1.7  # side by side under `both`
    assert option.price_mark == "old price, read on 2026-10-20, the market has few offers now"
    assert option.price_mark in option.sourced.marks


def test_a_thin_trade_market_with_no_deep_reading_is_its_mean_marked_thin(data, prices, r13):
    name = "Leather Belt (ilvl 84)"
    record = MarketRecord("thin", "Allflame", date(2026, 11, 1), 4, 4, "hash", {"query": {}}, chaos=40.0, used=4)
    thin = dataclasses.replace(prices, markets={name: record})
    option = bought_base_starts(StartContext(data, r13, thin, today=date(2026, 11, 1))).candidates[0]
    assert option.bought.row_chaos == 40.0 and option.price_mark is not None and "few offers" in option.price_mark


def test_a_price_with_no_recorded_provenance_is_marked(data, prices, r13):
    bare = dict(prices.prices)
    bare["Leather Belt (ilvl 84)"] = PriceEntry(1.7, "poe.ninja")
    option = bought_base_starts(StartContext(data, r13, dataclasses.replace(prices, prices=bare))).candidates[0]
    assert option.bought.ninja.observations is None  # not recorded: kept, and marked
    assert NOT_RECORDED_WORDS in option.bought.input_marks


def test_a_given_start_lists_nothing(data, prices, r13):
    listed = bought_base_starts(StartContext(data, dataclasses.replace(r13, start=StartKind.GIVEN), prices))
    assert listed.candidates == () and listed.refused == ()


def test_a_start_item_with_mods_is_not_a_plain_base(data, prices, r08):
    table = tier_table(data, r08.base_id)
    mod_id = min((m for m in r08.requirements[0].mod_ids if m in table and data.mods[m].generation_type in ("prefix", "suffix")), key=lambda m: data.mods[m].required_level)
    mod = data.mods[mod_id]
    item = r08.start_item.changed(data, mods=(ExplicitMod(mod_id, tuple(stat.min for stat in mod.stats)),))
    listed = bought_base_starts(StartContext(data, dataclasses.replace(r08, start_item=item), prices))
    assert listed.candidates == ()
    assert [r.reason for r in listed.refused] == [NOT_A_PLAIN_BASE]


def test_warnings_start_empty_for_the_rails_to_fill(data, prices, r13):
    """#353 annotates options with its rails' warnings without cutting them (OR-12): the field is there and empty."""
    assert all(c.warnings == () for c in bought_base_starts(StartContext(data, r13, prices)).candidates)


def test_every_bought_example_target_lists_without_raising(data, prices):
    """R14's file says 78 and its floor at 86 is 81: the levels come from the target planned at 86, so no level below its floor is asked."""
    for path in sorted(TARGETS.glob("*.yaml")):
        target = load_target(path, data)
        if target.start is StartKind.BOUGHT:
            listed = bought_base_starts(StartContext(data, target, prices))
            assert all(c.bought.level >= c.bought.group[0] for c in listed.candidates), path.name


def test_a_thin_row_on_another_level_of_the_group_is_said(data, prices):
    """R09's levels 69 to 71 are one pool: a thin row at 69 is set aside and named on the option priced from 70."""
    r09 = load_target(TARGETS / "r09-life-boots.yaml", data)
    names = {level: base_line_name(data, target_at_level(data, r09, level)) for level in (69, 70)}
    thin = PriceEntry(0.5, "poe.ninja", None, {"category": "BaseType"}, Provenance("ninja-stash", "Allflame", "2026-11-01", 2.0, "observations"))
    deep = PriceEntry(3.0, "poe.ninja", None, {"category": "BaseType"}, Provenance("ninja-stash", "Allflame", "2026-11-01", 40.0, "observations"))
    file = dataclasses.replace(prices, prices={**prices.prices, names[69]: thin, names[70]: deep})
    option = next(c for c in bought_base_starts(StartContext(data, r09, file)).candidates if c.bought.group == (69, 71))
    assert option.bought.level == 70 and option.bought.row_chaos == 3.0
    assert any(f"the poe.ninja row {names[69]} rests on 2 observations" in mark for mark in option.bought.input_marks)


def test_an_item_class_with_no_influence_key_says_so(data, prices):
    """A model gap is said, never silent: a jewel's class has no influence key, so no influenced set is listed and the refusal names the class."""
    from start_support import with_start

    from crafting_system.targets import parse_target

    text = "base: Cobalt Jewel\nitem_level: 84\nstart: bought\nstart_item:\n  rarity: magic\nrequirements:\n  - family: IncreasedLife\n"
    target = parse_target(with_start(text), data, source="jewel.yaml")
    sets, why = needed_influence_sets(data, target)
    assert sets == (frozenset(),)
    assert why == "the item class Jewel has no influence key in the model, so no requirement is checked for an influence mod"
    refusals = [r for r in bought_base_starts(StartContext(data, target, prices)).refused if r.reason == NO_INFLUENCED_BASE]
    assert [(r.recipe, r.detail) for r in refusals] == [("base:influence", why)]
