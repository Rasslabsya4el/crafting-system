"""A tiny world for the planner with donors (ticket #225): boots whose only pool is two prefixes A and B of weight 100, each its own family.

The boots and the fixture data are those of `item_state_support`; nothing of its pool spawns on boots, so the pool is exactly A and B. The
target asks for both; the start is a given magic pair of boots with A; the offers are the Orb of Transmutation, the Orb of Alteration and the
recombinator (`actions:` names the three kinds). The prices are round numbers so the hand-worked mean of `test_cli_plan_donors` is exact:
a Transmutation `T`, an Alteration `ALT`, and a combine at the real cost rule (100,000 Dust and 12,000 Gold) priced to `R`.
"""

import dataclasses
import datetime
from functools import cache

from item_state_support import BOOTS, ITEM_DATA, LEVEL

from crafting_system.actions.recombinator import DUST_NAME, GOLD_NAME
from crafting_system.data import GameData, Weight
from crafting_system.items import ExplicitMod, Item, Rarity, spawn_weight
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.targets import Requirement, StartKind, Target
from abstraction_pool import LIFE_1

A, B = "DonorPlanA", "DonorPlanB"
T, ALT = 0.5, 0.25  # Chaos per Orb of Transmutation and per Orb of Alteration
R = 7.0  # Chaos per combine: 100,000 Dust at 1/50,000 Chaos and 12,000 Gold at 1/2,400 Chaos is 2 + 5
BOOTS_TAGS = ITEM_DATA.base_items[BOOTS].tags
KINDS = ("transmutation-orb", "alteration-orb", "recombinator")

PRICES = PriceFile(
    "Test",
    datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC),
    300.0,
    {
        "Orb of Transmutation": PriceEntry(T, "test"),
        "Orb of Alteration": PriceEntry(ALT, "test"),
        DUST_NAME: PriceEntry(1 / 50_000, "test"),
        GOLD_NAME: PriceEntry(1 / 2_400, "test"),
    },
)


@cache
def world() -> GameData:
    data = ITEM_DATA
    prefix = data.mods[LIFE_1]
    mods = {mod_id: mod for mod_id, mod in data.mods.items() if spawn_weight(mod, BOOTS_TAGS) == 0}
    for mod_id in (A, B):
        mods[mod_id] = dataclasses.replace(
            prefix, id=mod_id, type=mod_id, families=(mod_id,), required_level=1, spawn_weights=(Weight("boots", 100), Weight("default", 0))
        )
    return dataclasses.replace(data, mods=mods)


def boots(data: GameData, *mod_ids: str, rarity: Rarity = Rarity.MAGIC) -> Item:
    mods = tuple(ExplicitMod(mod_id, tuple(min(s.min, s.max) for s in data.mods[mod_id].stats)) for mod_id in mod_ids)
    return Item.build(data, base_id=BOOTS, item_level=LEVEL, rarity=rarity, mods=mods)


def donor_target(data: GameData, kinds: tuple[str, ...] = KINDS) -> Target:
    """A and B on boots, from a given magic pair with A."""
    wanted = tuple(Requirement(family=mod_id, stat=None, mod_ids=frozenset({mod_id})) for mod_id in (A, B))
    return Target(BOOTS, LEVEL, frozenset(), wanted, boots(data, A), start=StartKind.GIVEN, actions=kinds)
