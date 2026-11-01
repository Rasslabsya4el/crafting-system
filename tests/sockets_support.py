"""Shared helpers for the tests of the socket actions (ticket #228, ADR-0046 and ADR-0047).

The items live in the contract data (`contract_support.CONTRACT_DATA`: the repoe fixture excerpt plus the contract pool), which holds a
body armour (class maximum 6), a one-handed sword (3), a sceptre (3) and a bow (6). `HELMET_DATA` adds a helmet base (class maximum 4) so the
four-socket table has an item to roll on. The weights the tests compare with are written out here from ADR-0047, not read from the claims.
"""

import dataclasses
import functools
from fractions import Fraction

from items_support import BODY

from crafting_system.data import BaseItem
from crafting_system.items import Item, PlainQuality, Rarity, SocketColour, Sockets

R, G, B, W = SocketColour.RED, SocketColour.GREEN, SocketColour.BLUE, SocketColour.WHITE
SWORD = "Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1"
BOW = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
HELMET = "Metadata/Items/Armours/Helmets/ContractHelmet1"

# ADR-0047, "Jeweller's Orb": the item-generation table (the plan) and GGG's 2014 table (the second reading), counts 1 to 6; four-socket classes
PLAN_WEIGHTS = (50, 120, 100, 30, 5, 1)
SECOND_WEIGHTS = (100, 90, 80, 30, 5, 1)
FOUR_SOCKET_WEIGHTS = (100, 90, 80, 30)
GATE = {1: 1, 2: 1, 3: 2, 4: 25, 5: 35, 6: 50}  # the least item level for each count
# ADR-0047, "Orb of Fusing": the fitted weights for group sizes 1 to 6 at 20% quality, out of 100,000
FUSING_WEIGHTS = (17818, 34818, 26766, 19672, 826, 100)


@functools.cache
def socket_data():
    """The contract data with a helmet base added (a four-socket class)."""
    from contract_support import CONTRACT_DATA  # late: `contract_support` loads the fixture modules while it builds CONTRACT_DATA

    body = CONTRACT_DATA.base_items[BODY]
    helmet = dataclasses.replace(body, id=HELMET, name="Contract Helmet", item_class="Helmet", tags=("helmet", "armour", "default"))
    assert isinstance(helmet, BaseItem)
    return dataclasses.replace(CONTRACT_DATA, base_items={**CONTRACT_DATA.base_items, HELMET: helmet})


def sockets_of(*colours: SocketColour, links: tuple[int, ...] | None = None) -> Sockets:
    """Sockets of the given colours; `links` default to every socket on its own."""
    return Sockets(tuple(colours), links if links is not None else (1,) * len(colours))


def white(count: int, links: tuple[int, ...] | None = None) -> Sockets:
    return sockets_of(*([W] * count), links=links)


def socketed(
    sockets: Sockets | None,
    *,
    base_id: str = BODY,
    item_level: int = 84,
    rarity: Rarity = Rarity.RARE,
    quality: int = 20,
    mods: tuple[str, ...] = (),
    **fields,
) -> Item:
    """A weapon or armour with `sockets` and plain `quality` percent, holding the rolled `mods` (fixture mod ids)."""
    from contract_support import _roll

    data = socket_data()
    return Item.build(
        data,
        base_id=base_id,
        item_level=item_level,
        rarity=rarity,
        mods=tuple(_roll(mod_id) for mod_id in mods),
        sockets=sockets,
        quality=PlainQuality(quality) if quality else None,
        **fields,
    )


def jeweller_chances(weights: tuple[int, ...], count: int, reach: int) -> dict[int, Fraction]:
    """The chance of each new count of a Jeweller's Orb from `count` sockets when it can reach `reach` and rolls by `weights` (an independent restatement)."""
    pool = {new: weights[new - 1] for new in range(1, reach + 1) if new != count}
    total = sum(pool.values())
    return {new: Fraction(weight, total) for new, weight in pool.items()}


def expected_jeweller_orbs(weights: tuple[int, ...], start: int, wanted: int, reach: int) -> float:
    """Orbs to reach `wanted` sockets or more from `start`, by value iteration over the weights (the oracle the action is compared with)."""
    value = {count: 0.0 for count in range(1, reach + 1)}
    for _ in range(20_000):
        new = {}
        for count in range(1, reach + 1):
            if count >= wanted:
                new[count] = 0.0
                continue
            chances = jeweller_chances(weights, count, reach)
            new[count] = 1.0 + sum(float(chance) * value[target] for target, chance in chances.items())
        if max(abs(new[count] - value[count]) for count in value) < 1e-12:
            return new[start]
        value = new
    raise AssertionError("value iteration did not converge")


JEWELLERS_ORB_ID = "Metadata/Items/Currency/CurrencyRerollSocketNumbers"
FUSING_ORB_ID = "Metadata/Items/Currency/CurrencyRerollSocketLinks"
ABYSS_STAT = "local_has_X_abyss_sockets"
ABYSS_MOD = "AbyssSocketSuffix1"
BENCH_COUNT_COSTS = {2: 1, 3: 3, 4: 10, 5: 70, 6: 350}  # ADR-0047, "The bench": Jeweller's Orbs for 2 to 6 sockets
BENCH_LINK_COSTS = {2: 1, 3: 3, 4: 5, 5: 150, 6: 1500}  # Orbs of Fusing for 2 to 6 links


@functools.cache
def bench_data():
    """The socket data with the ten bench options of the real data (count 2 to 6, links 2 to 6) and the two orbs named as the game names them."""
    from crafting_system.data import CostEntry

    data = socket_data()
    template = next(option for option in data.bench_options if option.actions.change_socket_count is not None)
    bases = dict(data.base_items)
    for base_id, name in ((JEWELLERS_ORB_ID, "Jeweller's Orb"), (FUSING_ORB_ID, "Orb of Fusing")):
        bases[base_id] = BaseItem(base_id, name, "StackableCurrency", "currency", 1, (), (), "released")
    none = dataclasses.replace(template.actions, change_socket_count=None, link_sockets=None, color_sockets=None)
    options = [option for option in data.bench_options if option.actions.change_socket_count is None and option.actions.link_sockets is None]
    for count, price in BENCH_COUNT_COSTS.items():
        actions = dataclasses.replace(none, change_socket_count=count)
        options.append(dataclasses.replace(template, actions=actions, cost=(CostEntry(JEWELLERS_ORB_ID, price),)))
    for links, price in BENCH_LINK_COSTS.items():
        actions = dataclasses.replace(none, link_sockets=links)
        options.append(dataclasses.replace(template, actions=actions, cost=(CostEntry(FUSING_ORB_ID, price),)))
    return dataclasses.replace(data, base_items=bases, bench_options=tuple(options))


@functools.cache
def abyss_data():
    """The socket data plus a suffix that gives an Abyssal Socket (the stat `local_has_X_abyss_sockets`)."""
    from abstraction_pool import LIFE_1

    from crafting_system.data import StatRange

    data = socket_data()
    suffix = dataclasses.replace(
        data.mods[LIFE_1], id=ABYSS_MOD, families=("AbyssSocket",), type="AbyssSocket", text="Has 1 Abyssal Socket", stats=(StatRange(ABYSS_STAT, 1, 1),)
    )
    return dataclasses.replace(data, mods={**data.mods, ABYSS_MOD: suffix})
