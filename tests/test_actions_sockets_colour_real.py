"""The colour and quality actions on the real 3.29.3.3 dump (ticket #229): the attribute requirements of the bases, the bench's colour options, the names.

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`). They skip cleanly when it is
not there; CI fetches it (ticket #165), so they run there.
"""

from fractions import Fraction

import pytest
from sockets_colour_support import BENCH_COLOUR_COSTS

from crafting_system.actions import ApplyQualityCurrency, BenchSocketColours, ChromaticOrb, catalog, colour_weights
from crafting_system.data import MissingDataError, load_game_data
from crafting_system.items import Item, PlainQuality, Rarity, SocketColour, Sockets
from crafting_system.prices.price_names import ARMOURERS_SCRAP, BLACKSMITHS_WHETSTONE, CHROMATIC_ORB, OMEN_OF_TRICHROMATISM

BODY = "Metadata/Items/Armours/BodyArmours/BodyInt1"
SCARE_MASK = "Metadata/Items/Armours/Helmets/HelmetDexInt1"  # a dexterity-intelligence helmet: 8 and 8
WHITE, RED, GREEN, BLUE = SocketColour.WHITE, SocketColour.RED, SocketColour.GREEN, SocketColour.BLUE


@pytest.fixture(scope="module")
def data():
    try:
        return load_game_data()
    except MissingDataError as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


def helmet(data, count=4, *, level=84, quality=20):
    return Item.build(data, base_id=SCARE_MASK, item_level=level, rarity=Rarity.RARE, sockets=Sockets((WHITE,) * count, (1,) * count), quality=PlainQuality(quality))


def test_the_bases_carry_their_attribute_requirements(data):
    assert data.base_items[SCARE_MASK].attribute_requirements == (0, 8, 8)
    assert data.base_items[BODY].attribute_requirements == (0, 0, 17)
    every = [base.attribute_requirements for base in data.base_items.values()]
    assert all(len(entry) == 3 and min(entry) >= 0 for entry in every) and any(sum(entry) > 0 for entry in every)


def test_the_bench_colour_options_are_priced_in_chromatic_orbs_by_the_name_of_the_dump(data):
    for minimum, price in BENCH_COLOUR_COSTS.items():
        assert BenchSocketColours(minimum).resources(data) == {CHROMATIC_ORB: price}
    assert {name for name in (CHROMATIC_ORB, OMEN_OF_TRICHROMATISM, BLACKSMITHS_WHETSTONE, ARMOURERS_SCRAP)} <= {base.name for base in data.base_items.values()}
    assert ChromaticOrb(omen=True).resources(data) == {CHROMATIC_ORB: 1, OMEN_OF_TRICHROMATISM: 1}


def test_a_real_helmet_is_offered_the_orb_the_omen_the_bench_crafts_and_a_scrap(data):
    labels = [action.label(data) for action in catalog(data, helmet(data, quality=5))]
    for label in ("Chromatic Orb", "Chromatic Orb with Omen of Trichromatism", "Armourer's Scrap", *(f"Bench craft {n} coloured sockets" for n in (2, 3, 4))):
        assert label in labels
    assert "Blacksmith's Whetstone" not in labels
    assert not any(action.label(data) == "Chromatic Orb with Omen of Trichromatism" for action in catalog(data, helmet(data, 2)))


def test_the_real_helmet_gets_red_green_and_blue_for_one_orb_in_78_and_for_certain_with_the_omen(data):
    item = helmet(data)
    chance = ChromaticOrb().outcomes(data, item).chance_colours(RED, GREEN, BLUE)
    assert round(float(chance) * 100, 2) == 1.28 and round(1 / float(chance)) == 78
    assert ChromaticOrb(omen=True).outcomes(data, item).chance_colours(RED, GREEN, BLUE) == 1


def test_the_real_colour_weights_of_a_strength_and_an_intelligence_base(data):
    weights = colour_weights(data.base_items[BODY].attribute_requirements)
    assert weights[2] == Fraction(9, 10) * Fraction(27, 37) and sum(weights) == 1


def test_a_scrap_buys_the_quality_of_a_real_helmet(data):
    outcome = ApplyQualityCurrency(ARMOURERS_SCRAP).outcomes(data, helmet(data, quality=0))
    assert sorted(result.quality.percent for _, result in outcome.results) == [1, 2]
