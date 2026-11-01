"""Shared helpers for the `abstraction` tests: the goals on the small pool, an `Abstraction` builder and the oracle check.

`abstraction_pool.py` holds the small pool and its items, `abstraction_oracle.py` the brute force;
this module is the only one of the three that imports `crafting_system.abstraction`.
"""

import dataclasses
from collections.abc import Hashable
from fractions import Fraction

import pytest
from abstraction_oracle import assert_same_distribution, compressed_distribution, finished_items, guaranteed_tag
from abstraction_pool import (
    CRAFTED,
    DAMAGES,
    GEM,
    LEVEL,
    LIVES,
    MANAS,
    RESISTS,
    SMALL,
)
from items_support import AMULET

from crafting_system.abstraction import Abstraction, AtLeast, CompressedState, Goal, Status, Wanted
from crafting_system.actions import ChaosOrb, HarvestReforge
from crafting_system.data import MissingDataError, load_game_data
from crafting_system.items import Item

GEM_LEAF = Wanted(frozenset({GEM}))
RESIST_LEAF = Wanted(RESISTS)
RESIST_TIER_2 = Wanted(RESISTS, min_tier=2)
DAMAGE_LEAF = Wanted(DAMAGES)
LIFE_LEAF = Wanted(LIVES)
MANA_LEAF = Wanted(MANAS)

GOALS = {
    "r12": Goal((GEM_LEAF, RESIST_LEAF)),
    "tier": Goal((GEM_LEAF, RESIST_TIER_2)),
    "any": Goal((AtLeast(1, (GEM_LEAF, RESIST_TIER_2)),)),
    "two_of_three": Goal((AtLeast(2, (GEM_LEAF, DAMAGE_LEAF, RESIST_LEAF)),)),
    "nested": Goal((AtLeast(1, (GEM_LEAF, AtLeast(2, (DAMAGE_LEAF, RESIST_LEAF, LIFE_LEAF)))), MANA_LEAF)),
    "unspawnable": Goal((RESIST_LEAF, Wanted(frozenset({CRAFTED})))),
    "roll_not_asked": Goal((GEM_LEAF, Wanted(RESISTS, min_roll=(None,)))),
}
CHAOS = ChaosOrb()
REFORGE = HarvestReforge("lightning")
ACTIONS = {"chaos": CHAOS, "reforge": REFORGE}
PASSING, BELOW, ABSENT = Status.PASSING, Status.BELOW, Status.ABSENT


def abstraction(goal: Goal | str = "r12", level: int = LEVEL, *, metamods: bool = False) -> Abstraction:
    """A fresh `Abstraction` of the small pool for a goal of `GOALS` (or a goal) at an item level."""
    return Abstraction(SMALL, GOALS[goal] if isinstance(goal, str) else goal, AMULET, level, metamods=metamods)


_FINISHED: dict[tuple, list] = {}


def expected_kernel(
    ab: Abstraction, start: Item, action, *, data=SMALL, forced: str | None = None, cap: int | None = None
) -> dict[Hashable, Fraction]:
    """The brute-force kernel of `action` on `start`: every finished item, compressed and added up."""
    tag = guaranteed_tag(action)
    key = (id(data), start, tag, forced, cap)
    if key not in _FINISHED:
        _FINISHED[key] = finished_items(data, start, tag, forced=forced, cap=cap)
    return compressed_distribution(_FINISHED[key], ab.compress)


def check_kernel(ab: Abstraction, start: Item, action, **oracle) -> dict[CompressedState, Fraction]:
    """Assert that the kernel of `compress(start)` equals the brute force exactly, and return it.

    `oracle` is what the brute force needs to know about an essence: `data`, `forced` and `cap`.
    """
    kernel = ab.kernel(ab.compress(start), action)
    assert_same_distribution(kernel, expected_kernel(ab, start, action, **oracle))
    assert sum(kernel.values()) == 1
    return dict(kernel)


def with_fractured(state: CompressedState, other: CompressedState) -> CompressedState:
    """`state` with the fractured mods of `other`: the way to compare two states that differ only there."""
    return dataclasses.replace(state, fractured=other.fractured)


def passing_chance(kernel, leaf: int) -> Fraction:
    """The chance that leaf number `leaf` of the goal is met after the action."""
    return sum((chance for state, chance in kernel.items() if state.status[leaf] == PASSING), Fraction(0))


def real_game_data():
    """The real 3.29.3.3 dump from the cache, or a clean skip when it is not there (CI fetches it, ticket #165)."""
    try:
        return load_game_data()
    except MissingDataError as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")

