"""The tier cut in the pool of the real 3.29.3.3 dump (ticket #275, ADR-0040, ADR-0042).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`); they skip cleanly
when it is not there and run in CI (ticket #165). They check, on the pools of seven item classes at two item levels, what the unit tests
check on toy tables: 0 strands without a Foulborn orb is today's pool; every tier table keeps exactly its `K` highest tiers (counted on
the tiers the pool admits, the way a reader would count them from the ordinary pool); reading 1 keeps every family's total weight and
every mod type's, reading 2 multiplies by `T / K`, reading 3 leaves the weights.
"""

from collections import defaultdict
from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import build_pool
from crafting_system.actions.cut import Cut, WeightReading, rollable_tiers
from crafting_system.actions.pool import pool_candidates
from crafting_system.items import Item, Rarity

BASES = {
    "amulet": "Metadata/Items/Amulets/Amulet1",
    "belt": "Metadata/Items/Belts/Belt3",
    "body armour": "Metadata/Items/Armours/BodyArmours/BodyStr1",
    "boots": "Metadata/Items/Armours/Boots/BootsStr1",
    "wand": "Metadata/Items/Weapons/OneHandWeapons/Wands/Wand1",
    "bow": "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow1",
    "ring": "Metadata/Items/Rings/Ring1",
}
LEVELS = (75, 86)
COUNTS = (0, 1, 2, 22, 50, 81, 82, 100)


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def bare(data, base: str, level: int) -> Item:
    return Item.build(data, base_id=BASES[base], rarity=Rarity.RARE, mods=(), item_level=level)


def tables(candidates):
    """The candidates grouped by tier table, each table as {required level: [candidates]} (a level is a tier)."""
    found: dict[tuple[str, str, str], dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for candidate in candidates:
        mod = candidate.mod
        found[(mod.type, mod.generation_type, mod.domain)][mod.required_level].append(candidate)
    return found


def cut_expectation(candidates, cut: Cut):
    """{mod id: weight} the cut should leave, worked out from the ordinary candidates level by level."""
    expected: dict[str, Fraction] = {}
    for by_level in tables(candidates).values():
        levels = sorted(by_level, reverse=True)
        total = len(levels)
        kept = rollable_tiers(total, cut.strands, cut.foulborn)
        every = [candidate for level in levels for candidate in by_level[level]]
        stay = [candidate for level in levels[:kept] for candidate in by_level[level]]
        whole = sum((candidate.weight for candidate in every), Fraction(0))
        remaining = sum((candidate.weight for candidate in stay), Fraction(0))
        scale = {
            WeightReading.REDISTRIBUTION: whole / remaining,
            WeightReading.REFACTORED: Fraction(total, kept),
            WeightReading.DELETE_ONLY: Fraction(1),
        }[cut.reading]
        for candidate in stay:
            expected[candidate.mod.id] = candidate.weight * scale
    return expected


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("level", LEVELS)
def test_at_0_strands_without_a_foulborn_orb_the_real_pool_is_todays(data, base, level):
    item = bare(data, base, level)

    assert build_pool(data, item, cut=Cut(0)) == build_pool(data, item)
    assert pool_candidates(data, item, cut=Cut.of(item)) is pool_candidates(data, item)
    assert pool_candidates(data, item)  # a pool, not an empty one


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("reading", list(WeightReading))
def test_every_tier_table_of_the_real_pool_keeps_its_k_highest_tiers_with_the_weights_of_the_reading(data, base, level, reading):
    item = bare(data, base, level)
    ordinary = pool_candidates(data, item)
    for strands in COUNTS:
        for foulborn in (False, True):
            cut = Cut(strands, foulborn, reading)

            got = {candidate.mod.id: candidate.weight for candidate in pool_candidates(data, item, cut=cut)}

            assert got == cut_expectation(ordinary, cut), (strands, foulborn)
            assert [candidate.mod.id for candidate in pool_candidates(data, item, cut=cut)] == [
                candidate.mod.id for candidate in ordinary if candidate.mod.id in got
            ]  # the data order is kept


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("level", LEVELS)
def test_reading_1_keeps_the_total_weight_of_every_family_and_every_mod_type_of_the_real_pool(data, base, level):
    item = bare(data, base, level)
    ordinary = pool_candidates(data, item)
    totals = defaultdict(Fraction)
    for candidate in ordinary:
        totals[candidate.family] += candidate.weight

    for strands in COUNTS:
        for foulborn in (False, True):
            cut = build_pool(data, item, cut=Cut(strands, foulborn, WeightReading.REDISTRIBUTION))

            assert {family.family: family.weight for family in cut} == dict(totals), (strands, foulborn)


@pytest.mark.parametrize("base", BASES)
def test_the_top_tier_of_every_table_always_stays_and_a_table_of_one_tier_is_never_cut(data, base):
    item = bare(data, base, 86)
    ordinary = pool_candidates(data, item)
    stays = {candidate.mod.id for candidate in pool_candidates(data, item, cut=Cut(100, foulborn=True))}

    for by_level in tables(ordinary).values():
        assert all(candidate.mod.id in stays for candidate in by_level[max(by_level)])
        if len(by_level) == 1:
            assert all(candidate.mod.id in stays for candidate in by_level[next(iter(by_level))])


def test_a_real_eight_tier_table_keeps_three_tiers_at_81_strands_and_two_at_82(data):
    # Elemental resistances have 8 tiers on most bases (the wiki's own example); ring and amulet pools hold the three of them.
    item = bare(data, "ring", 86)
    ordinary = pool_candidates(data, item)
    cold = sorted((candidate for candidate in ordinary if candidate.family == "ColdResistance"), key=lambda candidate: -candidate.mod.required_level)
    assert len(cold) == 8

    kept = lambda strands: [c.mod.id for c in pool_candidates(data, item, cut=Cut(strands)) if c.family == "ColdResistance"]  # noqa: E731

    assert set(kept(81)) == {c.mod.id for c in cold[:3]}
    assert set(kept(82)) == {c.mod.id for c in cold[:2]}
    assert len(kept(0)) == 8


def test_the_cut_never_adds_a_mod_or_a_family_to_the_pool(data):
    item = bare(data, "wand", 86)
    ordinary = {candidate.mod.id for candidate in pool_candidates(data, item)}

    for strands in COUNTS:
        for foulborn in (False, True):
            assert {candidate.mod.id for candidate in pool_candidates(data, item, cut=Cut(strands, foulborn))} <= ordinary
