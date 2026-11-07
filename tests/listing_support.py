"""Toy games for the draw of a bought start item (ticket #640, ADR-0064): a boots base whose pool is small enough to be worked by hand.

`magic_toy()` holds two prefix families A and B (weights 3 and 1) and two suffix families C and D (weights 2 and 4): the pool of a boots base
weighs 10. `rare_toy()` holds three prefix families (weights 1, 2, 3) and three suffix families (1, 2, 3), so an Orb of Alchemy (4, 5 or 6 mods at
8:3:1) leaves a set of them that `rare_sets` works out by walking every draw order. Each family has one mod, spawnable on the boots at item level 86.
"""

import datetime
import itertools
import textwrap
from fractions import Fraction

from crafting_system.data import BaseItem, GameData, Mod, StatRange, Weight
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.targets import Target, parse_target

BOOTS_ID = "Metadata/Items/Armours/Boots/ToyListingBoots1"
BOOTS = "Toy Listing Boots"
ITEM_LEVEL = 86


def _mod(name: str, side: str, weight: int) -> Mod:
    return Mod(
        id=name, name=f"of {name}", text=f"+# to {name}", type=name, families=(name,), domain="item", generation_type=side, required_level=1,
        spawn_weights=(Weight("boots", weight), Weight("default", 0)), generation_weights=(), adds_tags=(), implicit_tags=(),
        stats=(StatRange(f"toy_{name}", 1, 5),), is_essence_only=False,
    )  # fmt: skip


def toy(prefixes: dict[str, int], suffixes: dict[str, int]) -> GameData:
    mods = {name: _mod(name, "prefix", weight) for name, weight in prefixes.items()}
    mods |= {name: _mod(name, "suffix", weight) for name, weight in suffixes.items()}
    boots = BaseItem(BOOTS_ID, BOOTS, "Boots", "item", 1, ("boots", "armour", "default"), (), "released")
    return GameData("toy", mods, {BOOTS_ID: boots}, {}, {}, ())


MAGIC_PREFIXES = {"ToyA": 3, "ToyB": 1}
MAGIC_SUFFIXES = {"ToyC": 2, "ToyD": 4}
RARE_PREFIXES = {"ToyP1": 1, "ToyP2": 2, "ToyP3": 3}
RARE_SUFFIXES = {"ToyS1": 1, "ToyS2": 2, "ToyS3": 3}


def magic_toy() -> GameData:
    return toy(MAGIC_PREFIXES, MAGIC_SUFFIXES)


def rare_toy() -> GameData:
    return toy(RARE_PREFIXES, RARE_SUFFIXES)


def magic_sets() -> dict[frozenset[str], Fraction]:
    """What an Orb of Alteration leaves on a magic boots base of `magic_toy`, by hand: 1 mod or 2 mods, 1/2 each.

    One mod: its weight over the pool (10). Two mods: a magic item holds one prefix and one suffix, so the first draw is any mod (weight over 10) and
    the second comes from the other side only (weight over that side's total: 6 for the suffixes, 4 for the prefixes), in either order.
    """
    whole = sum(MAGIC_PREFIXES.values()) + sum(MAGIC_SUFFIXES.values())
    half = Fraction(1, 2)
    found = {frozenset({name}): half * Fraction(weight, whole) for name, weight in (MAGIC_PREFIXES | MAGIC_SUFFIXES).items()}
    for prefix, p_weight in MAGIC_PREFIXES.items():
        for suffix, s_weight in MAGIC_SUFFIXES.items():
            prefix_first = Fraction(p_weight, whole) * Fraction(s_weight, sum(MAGIC_SUFFIXES.values()))
            suffix_first = Fraction(s_weight, whole) * Fraction(p_weight, sum(MAGIC_PREFIXES.values()))
            found[frozenset({prefix, suffix})] = half * (prefix_first + suffix_first)
    return found


def rare_sets() -> dict[frozenset[str], Fraction]:
    """What an Orb of Alchemy leaves on a normal boots base of `rare_toy`, by hand: 4, 5 or 6 mods at 8:3:1, each draw in proportion to the weight.

    Every draw order of `n` mods is walked: a draw takes one mod of the pool not yet on the item, in proportion to its weight, and a side that
    holds three mods is closed (a rare item holds at most three of each side).
    """
    weights = RARE_PREFIXES | RARE_SUFFIXES
    side = {name: "prefix" for name in RARE_PREFIXES} | {name: "suffix" for name in RARE_SUFFIXES}
    found: dict[frozenset[str], Fraction] = {}
    for total, share in ((4, Fraction(8, 12)), (5, Fraction(3, 12)), (6, Fraction(1, 12))):
        for order in itertools.permutations(weights, total):
            chance = Fraction(1)
            held: list[str] = []
            for name in order:
                open_pool = [other for other in weights if other not in held and sum(side[x] == side[other] for x in held) < 3]
                if name not in open_pool:
                    chance = Fraction(0)
                    break
                chance *= Fraction(weights[name], sum(weights[other] for other in open_pool))
                held.append(name)
            if chance:
                found[frozenset(order)] = found.get(frozenset(order), Fraction(0)) + share * chance
    return found


TARGET = """\
base: Toy Listing Boots
item_level: 86
start_item:
  rarity: {rarity}
{mods}start: {start}
actions: [{actions}]
requirements:
  - family: {first}
    min_tier: any
  - family: {second}
    min_tier: any
"""


def target(
    data: GameData, *, rarity: str = "magic", start: str = "bought", mods: str = "", actions: str = "alteration-orb, augmentation-orb",
    wanted: tuple[str, str] = ("ToyA", "ToyC"),
) -> Target:
    """The toy target: a magic item holding the A prefix and the C suffix, from a bought (or given) start item of `rarity`."""
    text = TARGET.format(rarity=rarity, start=start, mods=mods, actions=actions, first=wanted[0], second=wanted[1])
    return parse_target(textwrap.dedent(text), data, source="toy-listing.yaml")


ALTERATION = 1.0
AUGMENTATION = 0.5
LISTING = 10.0


def prices(start_key: str | None) -> PriceFile:
    entries = {"Orb of Alteration": PriceEntry(ALTERATION, "fixture"), "Orb of Augmentation": PriceEntry(AUGMENTATION, "fixture"),
               "Regal Orb": PriceEntry(2.0, "fixture"), "Orb of Transmutation": PriceEntry(0.2, "fixture")}  # fmt: skip
    if start_key is not None:
        entries[start_key] = PriceEntry(LISTING, "trade-api")
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, entries)
