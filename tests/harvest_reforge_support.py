"""Shared data of the Harvest reforge tests (ticket #72): the wiki table typed by hand, the retagged small pool and the starting items.

`test_actions_harvest_reforges.py` checks the actions against hand numbers and the brute force; `test_abstraction_harvest_reforges.py`
checks the kernel of `abstraction` against the same brute force (layer 1).
"""

import dataclasses

from abstraction_pool import (
    COLD_GEM,
    COLD_RESIST,
    CRAFTED,
    DAMAGE_1,
    DAMAGE_2,
    FIRE_GEM,
    FIRE_RESIST,
    GEM,
    LIFE_1,
    LIFE_2,
    MANA_1,
    MANA_2,
    POOL_IDS,
    RESIST_1,
    RESIST_2,
    RESIST_3,
    SMALL,
    fractured_item,
    roll,
    small_item,
)
from items_support import item

from crafting_system.actions import build_pool
from crafting_system.items import Influence, Rarity

# --- the wiki table, typed by hand ----------------------------------------------------------------

WILD, VIVID, PRIMAL, SACRED = (f"{name} Crystallised Lifeforce" for name in ("Wild", "Vivid", "Primal", "Sacred"))
RANCOUR = "Crystallised Rancour"
# craft -> (the tag it guarantees, its cost)
TABLE = {
    "fire": ("fire", {WILD: 50}),
    "cold": ("cold", {VIVID: 50}),
    "lightning": ("lightning", {PRIMAL: 50}),
    "physical": ("physical", {VIVID: 50}),
    "life": ("life", {WILD: 75}),
    "defence": ("defences", {PRIMAL: 75}),
    "chaos": ("chaos", {VIVID: 100}),
    "attack": ("attack", {WILD: 75}),
    "caster": ("caster", {PRIMAL: 75}),
    "speed": ("speed", {VIVID: 150}),
    "critical": ("critical", {PRIMAL: 150}),
    "minion": ("minion", {PRIMAL: 200, RANCOUR: 3}),
    "elemental": ("elemental", {WILD: 200, RANCOUR: 1}),
    "attribute": ("attribute", {VIVID: 200, RANCOUR: 2}),
    "mana": ("mana", {PRIMAL: 200, RANCOUR: 2}),
    "drop": ("drop", {VIVID: 200, RANCOUR: 1}),
}
INFLUENCE_COST = {PRIMAL: 5000, SACRED: 1}
LIKELIHOOD_COST = {WILD: 200}

# The mods of the small amulet pool that carry each craft's tag in the test data: a set per craft, all different,
# on both sides, so that a wrong tag or a wrong cost-to-craft pairing changes a number.
TAGGED = {
    "fire": {FIRE_GEM, FIRE_RESIST},
    "cold": {COLD_GEM, COLD_RESIST},
    "lightning": {GEM, DAMAGE_1, DAMAGE_2, RESIST_1, RESIST_2, RESIST_3},
    "physical": {DAMAGE_2, LIFE_2},
    "life": {LIFE_1, LIFE_2, MANA_1},
    "defence": {LIFE_1, COLD_RESIST, FIRE_RESIST},
    "chaos": {DAMAGE_1, MANA_2},
    "attack": {DAMAGE_1, DAMAGE_2, MANA_1},
    "caster": {GEM, FIRE_GEM, COLD_GEM},
    "speed": {MANA_1, MANA_2},
    "critical": {GEM, LIFE_1},
    "minion": {RESIST_2, MANA_2},
    "elemental": {FIRE_RESIST, COLD_RESIST, DAMAGE_1, GEM},
    "attribute": {RESIST_3, LIFE_2, MANA_1},
    "mana": {MANA_1, MANA_2, COLD_GEM},
    "drop": {FIRE_GEM, RESIST_1},
}
SPAWNABLE = sorted(POOL_IDS - {CRAFTED})


def retagged():
    tags = {mod_id: tuple(TABLE[craft][0] for craft in TABLE if mod_id in TAGGED[craft]) for mod_id in SMALL.mods}
    return dataclasses.replace(
        SMALL, mods={mod_id: dataclasses.replace(mod, implicit_tags=tags[mod_id]) for mod_id, mod in SMALL.mods.items()}
    )


TAGGED_DATA = retagged()
STARTS = {
    "plain": (),
    "resist": (RESIST_2,),
    "two": (RESIST_2, LIFE_1),
}


def start_of(name: str):
    return fractured_item(*STARTS[name]) if STARTS[name] else small_item()




BOW = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
HUNTER = frozenset({Influence.HUNTER})
ATTACK_SPEED = "LocalIncreasedAttackSpeed5"


def bow(*mods, level=78, rarity=Rarity.RARE, influences=HUNTER, **fields):
    return item(*mods, base_id=BOW, item_level=level, rarity=rarity, influences=influences, **fields)



# the Hunter mods of the fixture bow, typed by hand: the test marks them for the brute force, since the data does not tag them
HUNTER_MODS = frozenset(
    {
        "LocalAddedChaosDamageAndPenetrationInfluence1",
        "LocalAddedChaosDamageAndPenetrationInfluence2",
        "LocalAddedChaosDamageAndPenetrationInfluence3",
        "LocalAddedChaosDamageAndPenetrationInfluence4",
        "LocalAddedChaosDamageAndPenetrationInfluence5",
        "AddedColdDamagePerDexterityInfluence1",
        "ArmourPenetrationTwoHandWeaponInfluence1_",
        "ArmourPenetrationTwoHandWeaponInfluence2_",
        "ChanceToIntimidateOnHitWeaponInfluence1",
        "ChanceToIntimidateOnHitWeaponInfluence2",
    }
)
HAND_TAG = "hunter_by_hand"


def hunter_marked_pool(data, start):
    """The pool of the reroll of `start` with the Hunter mods tagged by hand, for the brute force of the influence reforge."""
    retained = start.changed(data, mods=start.fractured_mods)
    return tuple(
        dataclasses.replace(
            family,
            mods=tuple(
                dataclasses.replace(
                    entry,
                    mod=dataclasses.replace(entry.mod, implicit_tags=(*entry.mod.implicit_tags, HAND_TAG))
                    if entry.mod.id in HUNTER_MODS
                    else entry.mod,
                )
                for entry in family.mods
            ),
        )
        for family in build_pool(data, retained)
    )


def held_weighted_pool(data, start, factor):
    """The pool of the reroll with every family the item holds weighed by hand."""
    retained = start.changed(data, mods=start.fractured_mods)
    held = {f for entry in start.mods for f in data.mods[entry.mod_id].families}
    return tuple(
        dataclasses.replace(
            family,
            mods=tuple(
                dataclasses.replace(entry, weight=entry.weight * (factor if family.family in held else 1))
                for entry in family.mods
            ),
        )
        for family in build_pool(data, retained)
    )


LIKELIHOOD_STARTS = {
    "plain": lambda: small_item(roll(RESIST_2), roll(LIFE_1)),
    "fractured": lambda: small_item(roll(RESIST_2, fractured=True), roll(LIFE_1), roll(MANA_1)),
    "six": lambda: small_item(*(roll(m) for m in (GEM, LIFE_1, DAMAGE_1, RESIST_1, COLD_RESIST, FIRE_RESIST))),
}



LIKELIHOOD_STARTS = {
    "plain": lambda: small_item(roll(RESIST_2), roll(LIFE_1)),
    "fractured": lambda: small_item(roll(RESIST_2, fractured=True), roll(LIFE_1), roll(MANA_1)),
    "six": lambda: small_item(*(roll(m) for m in (GEM, LIFE_1, DAMAGE_1, RESIST_1, COLD_RESIST, FIRE_RESIST))),
}
