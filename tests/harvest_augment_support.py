"""Shared data of the Harvest add and remove tests (ticket #148): the wiki table and the research prices typed by hand, the
small amulet pool with its hand tags (`harvest_reforge_support.TAGGED_DATA`) plus the three metamods the small pool lacks.

Nothing here reads the claims registry or the code under test: the cost of each craft, the lifeforce prices and the
expected cost in chaos are typed from the wiki table and the research of 2026-10-31.
"""

import dataclasses
from fractions import Fraction

from abstraction_pool import LEVEL
from harvest_reforge_support import TAGGED_DATA
from items_support import AMULET, DATA

from crafting_system.items import ExplicitMod, Item, Rarity

WILD, VIVID, PRIMAL, SACRED = (f"{name} Crystallised Lifeforce" for name in ("Wild", "Vivid", "Primal", "Sacred"))

# craft -> (the tag it adds, the lifeforce it takes and how many, the cost in chaos to one decimal)
# The count and the lifeforce are the wiki table "List of harvest crafting options"; each craft also takes one Sacred.
CRAFTS = {
    "fire": ("fire", WILD, 15000, 283.8),
    "cold": ("cold", VIVID, 15000, 2581.8),
    "lightning": ("lightning", PRIMAL, 15000, 579.1),
    "physical": ("physical", VIVID, 15000, 2581.8),
    "life": ("life", WILD, 17500, 322.8),
    "defence": ("defences", PRIMAL, 17500, 667.3),
    "chaos": ("chaos", VIVID, 17500, 3003.8),
    "attack": ("attack", WILD, 17500, 322.8),
    "caster": ("caster", PRIMAL, 17500, 667.3),
    "speed": ("speed", VIVID, 20000, 3425.8),
    "critical": ("critical", PRIMAL, 20000, 755.6),
}
# the prices of 2026-10-31 in chaos
PRICES = {WILD: 0.0156, VIVID: 0.1688, PRIMAL: 0.03529, SACRED: 49.75}

# the three metamods of the fixture that the small pool leaves out; the two locks and the two tag filters are
# the fixture's names ("PCBC" a suffix that locks the prefixes, "NO_ATTACK" and "NO_CASTER" suffixes that filter the draw)
PCBC = "StrMasterItemGenerationCannotChangePrefixes"
NO_ATTACK = "IntMasterItemGenerationCannotRollAttackAffixes"
NO_CASTER = "StrDexMasterItemGenerationCannotRollCasterAffixes"
EXTRA = (PCBC, NO_ATTACK, NO_CASTER)

META_DATA = dataclasses.replace(TAGGED_DATA, mods={**TAGGED_DATA.mods, **{mod_id: DATA.mods[mod_id] for mod_id in EXTRA}})


def lowest(mod_id: str, *, data=META_DATA, tier: int = 1, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    """`mod_id` at the low end of every range, at the tier given (1 for a mod that cannot spawn, a metamod)."""
    return ExplicitMod(mod_id, tier, tuple(min(s.min, s.max) for s in data.mods[mod_id].stats), fractured=fractured, crafted=crafted)


def amulet(*mods: ExplicitMod, data=META_DATA, rarity: Rarity = Rarity.RARE, level: int = LEVEL, **fields) -> Item:
    """A validated amulet of `data` (the small pool, hand-tagged, with the extra metamods)."""
    return Item.build(data, base_id=AMULET, item_level=level, rarity=rarity, mods=mods, **fields)


def pairs(outcomes) -> dict[tuple[str, str], Fraction]:
    """Each result as (the one mod it adds, the one mod it removes) -> chance; fails when a result differs by more or less."""
    before = {entry.mod_id for entry in outcomes.given.mods}
    found: dict[tuple[str, str], Fraction] = {}
    for chance, result in outcomes.results:
        after = {entry.mod_id for entry in result.mods}
        (added,) = after - before
        (removed,) = before - after
        assert (added, removed) not in found
        found[(added, removed)] = chance
    return found
