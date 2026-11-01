"""The socket actions on the real 3.29.3.3 dump: the 13 bench socket options, their classes, prices and names, and the orbs on real bases (ticket #228).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`). They skip cleanly when it is
not there; CI fetches it (ticket #165), so they run there.
"""

import pytest
from sockets_support import BENCH_COUNT_COSTS, BENCH_LINK_COSTS

from crafting_system.actions import (
    BenchSocketCount,
    BenchSocketLinks,
    JewellersOrb,
    OrbOfFusing,
    bench_crafts,
    catalog,
)
from crafting_system.data import MissingDataError, load_game_data
from crafting_system.items import PlainQuality, Rarity, Sockets, SocketColour, Item, SOCKET_ITEM_CLASSES
from crafting_system.prices.price_names import (
    ARMOURERS_SCRAP,
    BLACKSMITHS_WHETSTONE,
    CHROMATIC_ORB,
    JEWELLERS_ORB,
    OMEN_OF_CONNECTIONS,
    OMEN_OF_THE_JEWELLER,
    OMEN_OF_TRICHROMATISM,
    ORB_OF_BINDING,
    ORB_OF_FUSING,
)

BODY = "Metadata/Items/Armours/BodyArmours/BodyInt1"
HELMET = "Metadata/Items/Armours/Helmets/HelmetInt1"
WHITE = SocketColour.WHITE


@pytest.fixture(scope="module")
def data():
    try:
        return load_game_data()
    except MissingDataError as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


def socket_options(data):
    return [option for option in data.bench_options if option.actions.change_socket_count or option.actions.link_sockets or option.actions.color_sockets]


def test_the_bench_holds_exactly_thirteen_socket_options_on_the_twenty_classes(data):
    options = socket_options(data)
    assert len(options) == 13
    assert sorted(o.actions.change_socket_count for o in options if o.actions.change_socket_count) == [2, 3, 4, 5, 6]
    assert sorted(o.actions.link_sockets for o in options if o.actions.link_sockets) == [2, 3, 4, 5, 6]
    assert sorted(o.actions.color_sockets for o in options if o.actions.color_sockets) == ["NN", "NNN", "NNNN"]
    for option in options:
        assert set(option.item_classes) == SOCKET_ITEM_CLASSES and option.bench_tier == 0 and len(option.cost) == 1


def test_the_bench_prices_and_the_names_of_the_orbs_are_those_of_the_claims(data):
    names = {"change_socket_count": JEWELLERS_ORB, "link_sockets": ORB_OF_FUSING, "color_sockets": CHROMATIC_ORB}
    for option in socket_options(data):
        for field, name in names.items():
            number = getattr(option.actions, field)
            if number is None:
                continue
            (entry,) = option.cost
            assert data.base_items[entry.item_id].name == name
            if field == "change_socket_count":
                assert entry.count == BENCH_COUNT_COSTS[number]
            elif field == "link_sockets":
                assert entry.count == BENCH_LINK_COSTS[number]
            else:
                assert entry.count == {"NN": 5, "NNN": 20, "NNNN": 75}[number]


def test_the_socket_options_are_not_mod_crafts(data):
    crafts = bench_crafts(data)
    assert len(crafts) == 732
    assert not any(craft.option(data) in socket_options(data) for craft in crafts)


def test_the_price_names_are_item_names_of_the_dump(data):
    names = {base.name for base in data.base_items.values()}
    for name in (JEWELLERS_ORB, ORB_OF_FUSING, CHROMATIC_ORB, ORB_OF_BINDING, OMEN_OF_THE_JEWELLER, OMEN_OF_CONNECTIONS, OMEN_OF_TRICHROMATISM,
                 BLACKSMITHS_WHETSTONE, ARMOURERS_SCRAP):
        assert name in names, name


def body(data, sockets, *, quality=20, level=84):
    return Item.build(data, base_id=BODY, item_level=level, rarity=Rarity.RARE, sockets=sockets, quality=PlainQuality(quality))


def test_a_body_armour_is_offered_the_orbs_and_every_bench_count_and_link_craft(data):
    item = body(data, Sockets((WHITE, WHITE), (1, 1)))
    found = catalog(data, item)
    assert {type(action) for action in found} >= {JewellersOrb, OrbOfFusing, BenchSocketCount, BenchSocketLinks}
    assert [a.count for a in found if isinstance(a, BenchSocketCount)] == [2, 3, 4, 5, 6]
    assert [a.links for a in found if isinstance(a, BenchSocketLinks)] == [2, 3, 4, 5, 6]


def test_the_bench_crafts_cost_their_orbs_by_the_names_of_the_dump(data):
    assert [dict(BenchSocketCount(n).resources(data)) for n in range(2, 7)] == [{JEWELLERS_ORB: BENCH_COUNT_COSTS[n]} for n in range(2, 7)]
    assert [dict(BenchSocketLinks(n).resources(data)) for n in range(2, 7)] == [{ORB_OF_FUSING: BENCH_LINK_COSTS[n]} for n in range(2, 7)]


def test_the_orbs_work_on_a_real_body_armour_and_a_real_helmet(data):
    item = body(data, Sockets((WHITE, WHITE, WHITE), (1, 1, 1)))
    assert JewellersOrb().outcomes(data, item).chance_count(6) > 0
    assert OrbOfFusing().outcomes(data, item).chance_all_linked() > 0
    helmet = Item.build(data, base_id=HELMET, item_level=84, rarity=Rarity.RARE, sockets=Sockets((WHITE, WHITE), (1, 1)), quality=PlainQuality(20))
    assert max(sockets.count for sockets in JewellersOrb().outcomes(data, helmet).by_sockets) == 4
    assert BenchSocketCount(6).outcomes(data, body(data, Sockets((WHITE,), (1,)), level=1)).by_sockets  # the bench ignores the item level
