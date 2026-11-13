"""Stranded purchases (ticket #278, B5-5; ADR-0043, ADR-0040): the trade query's `memory_level` minimum and the offers a target gets.

A buy offer may name a minimum strand count: the query asks the trade site for `memory_level` at least `m`, instant buyout (OR-7), and the
price comes from the price file under the spec's own name; an offer without a price is dropped and the report lists it (ADR-0007). The
planner offers the counts at which a cut class begins for a tier table the target needs. The class boundaries below are worked by hand from
`K = floor(100 (T - 1) / (2.5 s + 147.5)) + 1` (ADR-0040), not read from the code: a table of four tiers keeps 4 at 0 strands, 3 at 1 strand
(300 / 150 = 2 exactly), 2 from 2 strands (300 / 152.5 < 2) and 1 from 62 strands (2.5 * 62 + 147.5 = 302.5 > 300; at 61 it is exactly 300),
so its classes begin at 1, 2 and 62: three offers.
"""

import dataclasses
from datetime import UTC, datetime

import pytest
from abstraction_pool import AMULET, LEVEL, LIFE_1, RESIST_1, SMALL

from crafting_system.items import Item, Rarity
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.query_compare import other_item
from crafting_system.prices.trade_query import BuySpec, TradeSpecError, build_query, load_buy_spec
from crafting_system.targets import Requirement, StartKind, Target, buy_spec_of
from crafting_system.targets.strand_offers import cut_class_starts, needed_tables, stranded_offer_counts, stranded_offers


def _spec(**fields) -> BuySpec:
    return BuySpec(name="Onyx Amulet", base_type="Onyx Amulet", rarity="normal", **fields)


# --- the query -------------------------------------------------------------------------------------------------------------------


def test_a_strand_minimum_writes_the_memory_level_filter_with_instant_buyout() -> None:
    body = build_query(_spec(memory_strands_min=22), ()).body()
    assert body["query"]["filters"]["misc_filters"]["filters"]["memory_level"] == {"min": 22}
    assert body["query"]["status"] == {"option": "securable"}  # instant buyout (OR-7)


def test_no_strand_minimum_writes_no_memory_level_filter() -> None:
    body = build_query(_spec(), ()).body()
    assert "memory_level" not in body["query"].get("filters", {}).get("misc_filters", {}).get("filters", {})


@pytest.mark.parametrize("bad", [0, 101, -1, True, 2.5])
def test_a_strand_minimum_is_a_whole_number_from_1_to_100(bad) -> None:
    with pytest.raises(TradeSpecError, match="memory_strands_min"):
        _spec(memory_strands_min=bad)


def test_a_buy_spec_file_reads_the_strand_minimum(tmp_path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_text("name: Onyx Amulet\nbase_type: Onyx Amulet\nrarity: normal\nmemory_strands_min: 62\n", encoding="utf-8")
    assert load_buy_spec(path).memory_strands_min == 62


def test_a_stored_search_with_another_strand_minimum_is_another_item() -> None:
    spec = _spec(memory_strands_min=22)
    plain = build_query(_spec(), ()).body()
    assert other_item(spec, build_query(spec, ()).body()) is None
    assert "another" in other_item(spec, plain) and "Memory Strands" in other_item(spec, plain)


# --- the target's offers ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tiers", "starts"),
    [
        (1, ()),  # one tier: nothing to cut
        (2, (1,)),  # 100 / 150 < 1: one tier from 1 strand
        (3, (1, 22)),  # 200 / (2.5 s + 147.5) >= 1 up to 21 strands (exactly 200 at 21)
        (4, (1, 2, 62)),
    ],
)
def test_a_cut_class_begins_where_the_kept_tiers_change(tiers: int, starts: tuple[int, ...]) -> None:
    assert cut_class_starts(tiers) == starts


def _target(*requirements: Requirement, start: StartKind = StartKind.BOUGHT) -> Target:
    item = Item.build(SMALL, base_id=AMULET, item_level=LEVEL, rarity=Rarity.NORMAL)
    return Target(AMULET, LEVEL, frozenset(), tuple(requirements), item, start)


def _needs(mod_id: str) -> Requirement:
    return Requirement(family=SMALL.mods[mod_id].families[0], stat=None, mod_ids=frozenset({mod_id}))


def test_the_tables_the_target_needs_are_those_of_its_wanted_mods() -> None:
    """Lightning Resistance has three tiers on the fixture amulet; Life two."""
    tables = needed_tables(SMALL, _target(_needs(RESIST_1), _needs(LIFE_1)))
    assert sorted(tables.values()) == [2, 3]
    assert stranded_offer_counts(SMALL, _target(_needs(RESIST_1))) == (1, 22)
    assert stranded_offer_counts(SMALL, _target(_needs(RESIST_1), _needs(LIFE_1))) == (1, 22)


def _four_tier_data():
    """The fixture with a fourth Lightning Resistance tier (required level 37), so its table has four tiers."""
    resist = SMALL.mods[RESIST_1]
    fourth = dataclasses.replace(resist, id="LightningResist4Fixture", required_level=37)
    return dataclasses.replace(SMALL, mods={**SMALL.mods, fourth.id: fourth})


def _price(chaos: float) -> PriceEntry:
    return PriceEntry(chaos=chaos, source="trade")


def _file(prices: dict[str, PriceEntry]) -> PriceFile:
    return PriceFile(league="Test", fetched_at=datetime(2026, 11, 1, 12, tzinfo=UTC), chaos_per_divine=200.0, prices=prices)


def test_a_target_with_a_four_tier_table_gets_two_to_four_offers_priced_by_their_own_search() -> None:
    data = _four_tier_data()
    target = _target(_needs(RESIST_1))
    assert needed_tables(data, target) == {(data.mods[RESIST_1].type, data.mods[RESIST_1].generation_type, data.mods[RESIST_1].domain): 4}
    counts = stranded_offer_counts(data, target)
    assert counts == (1, 2, 62)
    assert 2 <= len(counts) <= 4
    names = {count: buy_spec_of(data, target, strands=count).name for count in counts}
    prices = _file({name: _price(10.0 + count) for count, name in names.items()})
    result = stranded_offers(data, target, prices)
    assert [offer.strands for offer in result.offers] == [1, 2, 62]
    assert [offer.chaos for offer in result.offers] == [11.0, 12.0, 72.0]
    assert all(offer.spec.memory_strands_min == offer.strands for offer in result.offers)
    assert result.dropped == ()


def test_an_offer_without_a_price_is_dropped_and_reported() -> None:
    data = _four_tier_data()
    target = _target(_needs(RESIST_1))
    priced = buy_spec_of(data, target, strands=2).name
    result = stranded_offers(data, target, _file({priced: _price(5.0)}))
    assert [offer.strands for offer in result.offers] == [2]
    assert [dropped.strands for dropped in result.dropped] == [1, 62]
    lines = result.report_lines()
    assert len(lines) == 2
    assert all("no price" in line and "Memory Strands" in line for line in lines)


def test_the_spec_of_a_stranded_offer_is_the_start_items_with_the_strand_minimum_in_its_key() -> None:
    target = _target(_needs(RESIST_1))
    plain, stranded = buy_spec_of(SMALL, target), buy_spec_of(SMALL, target, strands=22)
    assert stranded.memory_strands_min == 22 and plain.memory_strands_min is None
    assert stranded.name != plain.name and stranded.name.startswith(plain.name)
    assert "22 or more Memory Strands" in stranded.name
    assert dataclasses.replace(stranded, name=plain.name, memory_strands_min=None) == plain
