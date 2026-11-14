"""On the real game data, every kind of action that does not read the junk gives the same parts from the projection as from the whole
state (ticket #827).

The actions are those the catalog lists for a bow whose `Reads.junk` is False (the rerolls: Chaos, Alchemy, Scouring, the essences, the
fossil sets, the Harvest reforges, the Awakener's and the like), a few of each kind, under `metamods=True` with a Fracturing Orb, on random
items with and without a lock, an Attack or Caster metamod, a fractured mod, plain and Hunter. What is compared is what a kernel is made
from (`Abstraction._mixture_kernel`): per part its share, its pool (the head of the draw and the whole family types, not their numbers,
which each abstraction gives its own), the forced mod and the split; or the refusal. The reference is `Abstraction.project = False`.
"""

import dataclasses
import random
from collections import Counter

import pytest
from abstraction_support import real_game_data

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import catalog
from crafting_system.actions.pool import pool_candidates
from crafting_system.items import ExplicitMod, Influence, Item, ItemError, Rarity, Side

BOW = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
LEVEL = 84
METAMODS = {
    "ItemGenerationCannotChangePrefixes",
    "ItemGenerationCannotChangeSuffixes",
    "ItemGenerationCannotRollAttackAffixes",
    "ItemGenerationCannotRollCasterAffixes",
    "ItemGenerationCanHaveMultipleCraftedMods",
}
ITEMS = 120
OF_A_KIND = 3


def low(mod) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in mod.stats)


def world(influences: frozenset):
    data = real_game_data()
    rng = random.Random(827)
    bare = Item.build(data, base_id=BOW, item_level=LEVEL, rarity=Rarity.RARE, influences=influences)
    drawable = [candidate.mod.id for candidate in pool_candidates(data, bare)]
    metas = sorted(mod.id for mod in data.mods.values() if mod.domain == "crafted" and METAMODS & set(mod.families))
    items = [bare, Item.build(data, base_id=BOW, item_level=LEVEL, rarity=Rarity.NORMAL, influences=influences)]
    while len(items) < ITEMS:
        rarity = rng.choice((Rarity.RARE, Rarity.RARE, Rarity.RARE, Rarity.MAGIC))
        ids = rng.sample(drawable, rng.randint(0, 6 if rarity is Rarity.RARE else 2))
        crafted = rng.sample(metas, rng.choice((0, 0, 1, 1, 2))) if rarity is Rarity.RARE else []
        fractured = set(ids[:1]) if rng.random() < 0.3 else set()
        mods = [ExplicitMod(mod_id, low(data.mods[mod_id]), fractured=mod_id in fractured) for mod_id in ids]
        mods += [ExplicitMod(mod_id, low(data.mods[mod_id]), crafted=True) for mod_id in crafted]
        try:
            items.append(Item.build(data, base_id=BOW, item_level=LEVEL, rarity=rarity, influences=influences, mods=tuple(mods)))
        except (ItemError, ValueError):
            continue
    by_kind: dict[str, dict] = {}
    fracturers: dict = {}
    for probe in items[:8]:
        for action in catalog(data, probe):
            try:
                reads = action.reads(data)
            except ValueError:
                continue
            if not reads.junk and action.imprint_move() is None:
                by_kind.setdefault(type(action).__name__, {})[action] = None
            elif reads.fractures:
                fracturers[action] = None
    erasers = [action for _, group in sorted(by_kind.items()) for action in rng.sample(list(group), min(OF_A_KIND, len(group)))]
    return data, items, erasers, list(fracturers), sorted(by_kind)


def model(data, actions, project: bool) -> Abstraction:
    goal = Goal((Wanted(frozenset(mod.id for mod in data.mods.values() if mod.families == ("IncreasedLife",))),))
    ab = Abstraction(data, goal, BOW, LEVEL, actions, metamods=True)
    ab.project = project
    return ab


def whole_types(ab: Abstraction, part) -> tuple:
    influences = part.retained.influences
    return (
        part.tag,
        part.guaranteed_blocked,
        len(part.retained.mods),
        part.free[Side.PREFIX],
        part.free[Side.SUFFIX],
        tuple(sorted(part.totals.items())),
        tuple(sorted(repr(ab._family_type(family, part.tag, influences, part.guaranteed_blocked, part.rolls_lucky)) for family in part.pool)),
    )


def parts(ab: Abstraction, state, action):
    """What the kernel of `action` at `state` is made from, or its refusal."""
    try:
        prepared = ab._prepared(state, action)
        splits = ab._splits_of(prepared)
    except ValueError as refusal:
        return (type(refusal).__name__, str(refusal))
    found = []
    for (share, part), split in zip(prepared.outcomes.components, splits):
        pool = whole_types(ab, part) if hasattr(part, "pool") else type(part).__name__
        found.append((share, pool, getattr(part, "forced", None), dataclasses.astuple(split)))
    return (prepared.outcomes.fractures, tuple(sorted(found, key=repr)))


@pytest.mark.parametrize("influences", [frozenset(), frozenset({Influence.HUNTER})], ids=["plain", "hunter"])
def test_every_kind_that_erases_the_junk_gives_the_same_parts_from_the_projection(influences):
    data, items, erasers, fracturers, kinds = world(influences)
    assert {"ChaosOrb", "ScouringOrb", "ApplyEssence", "ApplyFossils", "HarvestReforge"} <= set(kinds), kinds
    actions = [*(action for action in erasers if action.reads(data).item_state), *fracturers]
    projected, whole = model(data, actions, True), model(data, actions, False)
    seen: Counter = Counter()
    for item in items:
        try:
            state = projected.compress(item)
        except ValueError:
            continue
        lock = projected._holds_lock(state)
        for action in erasers:
            mine = parts(projected, state, action)
            assert mine == parts(whole, state, action), (action, state)
            seen[(lock, isinstance(mine[0], str))] += 1
        projected.release_prepared(keep_erased=True)
        whole.release_prepared()
    assert all(seen[(lock, refused)] > 20 for lock in (True, False) for refused in (True, False)), seen  # with and without a lock, refused and not
    assert projected.outcome_calls < whole.outcome_calls  # the items that differ only in their ordinary mods share a pair
