"""A small world for the compressed state of the recombinator (ticket #217).

Boots with a pool of prefixes in classes that hold several families (so that the placement of a class in families matters), a family
of two tiers with two weights (a place in the type), two suffix classes, an essence-only suffix (exclusive, named by its family) and a
crafted prefix of the family of one of the junk prefixes (a named mod in a family that a class holds). Nothing of the fixture pool of
`contract_support` spawns on boots, so the pool of the world is exactly the mods below.

    prefixes: RTA1 (tier 1) and RTA2 (tier 2) of the family RTA, RTB1 (targets, weight 100 / 400 / 100);
              RJ1, RJ2, RJ3 (weight 500: a class of three families), RK1, RK2 (weight 1000: a class of two);
              RU1a, RU1b, RU2a, RU2b (two families of two tiers, weights 1000 and 250: a class of two families, two places);
    suffixes: RS1 (wanted), RS2 (weight 600: a class of two), RS3 (1500), RSE (essence-only, weight 0).
"""

import dataclasses
from fractions import Fraction

from abstraction_pool import LIFE_1, MANA_1
from contract_support import COLD_CRAFT
from item_state_support import BOOTS, ITEM_DATA, LEVEL

from crafting_system.abstraction import Goal, Wanted
from crafting_system.data import Weight
from crafting_system.items import ExplicitMod, Item, Rarity, spawn_weight, tier_table

TA1, TA2, TB1 = "RTA1", "RTA2", "RTB1"
J1, J2, J3 = "RJ1", "RJ2", "RJ3"
K1, K2 = "RK1", "RK2"
U1A, U1B, U2A, U2B = "RU1a", "RU1b", "RU2a", "RU2b"
S1, S2, S3, SE = "RS1", "RS2", "RS3", "RSE"
CRAFT_J3 = "RCraftJ3"  # a crafted prefix of the family of RJ3
BOOTS_TAGS = ITEM_DATA.base_items[BOOTS].tags


def build_world():
    data = ITEM_DATA
    prefix, suffix, crafted = data.mods[LIFE_1], data.mods[MANA_1], data.mods[COLD_CRAFT]
    mods = {mod_id: mod for mod_id, mod in data.mods.items() if spawn_weight(mod, BOOTS_TAGS) == 0}  # nothing of the fixture pool spawns on boots

    def add(mod_id, template, family, weight, level=1, **fields):
        mods[mod_id] = dataclasses.replace(
            template,
            id=mod_id,
            type=family,
            families=(family,),
            required_level=level,
            spawn_weights=(Weight("boots", weight), Weight("default", 0)),
            **fields,
        )

    add(TA1, prefix, "RTA", 100, 80)
    add(TA2, prefix, "RTA", 400, 40)
    add(TB1, prefix, "RTB", 100)
    for mod_id in (J1, J2, J3):
        add(mod_id, prefix, mod_id, 500)
    for mod_id in (K1, K2):
        add(mod_id, prefix, mod_id, 1000)
    for family, high, low in (("RU1", U1A, U1B), ("RU2", U2A, U2B)):
        add(high, prefix, family, 1000, 80)
        add(low, prefix, family, 250, 40)
    add(S1, suffix, S1, 600)
    add(S2, suffix, S2, 600)
    add(S3, suffix, S3, 1500)
    add(SE, suffix, SE, 0, is_essence_only=True)
    mods[CRAFT_J3] = dataclasses.replace(crafted, id=CRAFT_J3, type=CRAFT_J3, families=(J3,), generation_type="prefix")
    return dataclasses.replace(data, mods=mods)


def r25_world(junk: tuple[tuple[int, int], ...] = ((500, 3), (1000, 3), (1500, 3))):
    """The R25-sized world of ADR-0062 on boots: prefixes only, three target prefixes A, B, C of weight 100 (one family and one leaf each) and the
    junk prefixes of `junk`, `(weight, how many)` for each weight class, every mod its own family. Returns `(data, goal, targets, junk mod ids)`.

    With three prefix slots the items of the world are 63 compressed states by class (ADR-0062: "class (junk by weight)") and 299 by name.
    """
    data = ITEM_DATA
    prefix = data.mods[LIFE_1]
    mods = {mod_id: mod for mod_id, mod in data.mods.items() if spawn_weight(mod, BOOTS_TAGS) == 0}

    def add(mod_id, weight):
        mods[mod_id] = dataclasses.replace(
            prefix, id=mod_id, type=mod_id, families=(mod_id,), required_level=1, spawn_weights=(Weight("boots", weight), Weight("default", 0))
        )

    targets = ("R25A", "R25B", "R25C")
    for mod_id in targets:
        add(mod_id, 100)
    junk_ids = tuple(f"R25J{weight}_{index}" for weight, count in junk for index in range(count))
    for mod_id, weight in zip(junk_ids, (weight for weight, count in junk for _ in range(count))):
        add(mod_id, weight)
    goal = Goal(tuple(Wanted(frozenset({mod_id})) for mod_id in targets))
    return dataclasses.replace(data, mods=mods), goal, targets, junk_ids


WORLD = build_world()
TIERS = tier_table(WORLD, BOOTS)
GOAL = Goal((Wanted(frozenset({TA1, TA2}), min_tier=1), Wanted(frozenset({TB1})), Wanted(frozenset({S1}))))
GRID = (Fraction(2, 5), Fraction(7, 10), Fraction(1), Fraction(13, 10), Fraction(8, 5))


def roll(mod_id: str, **flags) -> ExplicitMod:
    mod = WORLD.mods[mod_id]
    return ExplicitMod(mod_id, TIERS.get(mod_id, 1), tuple(min(stat.min, stat.max) for stat in mod.stats), **flags)


def item(*mod_ids: str, rarity: Rarity = Rarity.RARE, flags: dict | None = None, **fields) -> Item:
    """A boots item of the world holding `mod_ids`; `flags` maps a mod id to its `fractured` / `crafted` flag."""
    flags = flags or {}
    return Item.build(
        WORLD, base_id=BOOTS, item_level=LEVEL, rarity=rarity, mods=tuple(roll(mod_id, **flags.get(mod_id, {})) for mod_id in mod_ids), **fields
    )
