"""The brute-force oracles of ticket #69 against the actions themselves (no `abstraction` involved).

`abstraction_metamod_oracle.py` plays the claims of the removals, the Exalted Orb, the Fracturing Orb and the
metamods as plain code. Before a kernel is held to it, the oracle is held to `crafting_system.actions`: its
chances add up to 1, its removals, fractures and scourings list the very items the actions list, and the chance
that its finished item holds a mod (or two) equals `chance_all` of the action. A fault here is the oracle's (or
the action's), never the kernel's.
"""

from fractions import Fraction
from itertools import combinations

import pytest
from abstraction_metamod_oracle import (
    annulled,
    exalted,
    fracture_one,
    hold_chance,
    rerolled,
    scoured,
    then,
    tier_table,
)
from abstraction_removals_support import (
    AS_5,
    BASES,
    BOW,
    BOW_DATA,
    FIRE,
    FIRE_RES,
    HUNTER,
    HYBRID,
    METAMODS,
    SOCKET,
    bow,
    start_kinds,
    start_of,
)

from crafting_system.actions import AnnulmentOrb, ChaosOrb, ExaltedOrb, FracturingOrb, HarvestReforge, ScouringOrb
from crafting_system.actions.pool import tiers_of
from crafting_system.items import Rarity
from crafting_system.items import tier_table as items_tier_table

METAS = [None, *METAMODS]
CASES = [pytest.param(kind, meta, id=f"{meta or 'plain'}-{kind}") for meta in METAS for kind in start_kinds(meta)]


def sums_to_one(items):
    assert sum((chance for _, chance in items), Fraction(0)) == 1
    assert len({item for item, _ in items}) == len(items)
    assert all(chance > 0 for _, chance in items)


def mod_ids(items):
    return sorted({entry.mod_id for item, _ in items for entry in item.mods})


def agrees_with_chance_all(items, outcomes, start):
    """The chance of each finished mod, and of each pair of them, equals `outcomes.chance_all`."""
    held = {entry.mod_id for entry in start.mods}
    ids = [mod_id for mod_id in mod_ids(items) if mod_id not in held][:8] + sorted(held)[:2]
    for mod_id in ids:
        assert hold_chance(items, {mod_id}) == outcomes.chance_all({mod_id}), mod_id
    for pair in combinations(ids[:6], 2):
        assert hold_chance(items, set(pair)) == outcomes.chance_all(set(pair)), pair


@pytest.mark.parametrize(("kind", "meta"), CASES)
def test_the_annulment_oracle_lists_the_items_of_the_action(kind, meta):
    start = start_of(kind, meta)
    items = annulled(BOW_DATA, start)
    results = AnnulmentOrb().outcomes(BOW_DATA, start).results

    sums_to_one(items)
    assert {item: chance for item, chance in items} == {item: chance for chance, item in results}
    agrees_with_chance_all(items, AnnulmentOrb().outcomes(BOW_DATA, start), start)


@pytest.mark.parametrize(("kind", "meta"), CASES)
def test_the_fracture_oracle_lists_the_items_of_the_action(kind, meta):
    start = start_of(kind, meta)
    items = fracture_one(BOW_DATA, start)

    sums_to_one(items)
    assert {item: chance for item, chance in items} == {item: chance for chance, item in FracturingOrb().outcomes(BOW_DATA, start).results}
    assert all(len(item.fractured_mods) == 1 for item, _ in items)


@pytest.mark.parametrize(("kind", "meta"), CASES)
def test_the_scouring_oracle_gives_the_scoured_item_of_the_action(kind, meta):
    start = bow(*BASES[kind], *([METAMODS[meta]] if meta else []), fractured=[BASES[kind][-1]])

    ((item, chance),) = scoured(BOW_DATA, start)

    assert chance == 1 and item == ScouringOrb().outcomes(BOW_DATA, start).retained


@pytest.mark.parametrize(("kind", "meta"), CASES)
def test_the_exalted_oracle_has_the_chances_of_the_action(kind, meta):
    start = start_of(kind, meta)
    items = exalted(BOW_DATA, start)

    sums_to_one(items)
    agrees_with_chance_all(items, ExaltedOrb().outcomes(BOW_DATA, start), start)


@pytest.mark.parametrize(("kind", "meta"), CASES)
@pytest.mark.parametrize("tag", [None, "fire", "caster"])
def test_the_reroll_oracle_has_the_chances_of_the_action(kind, meta, tag):
    start = start_of(kind, meta, fractured=[BASES[kind][0]])
    action = ChaosOrb() if tag is None else HarvestReforge(tag)
    try:
        outcomes = action.outcomes(BOW_DATA, start)
    except Exception as refusal:  # the game refuses (no tagged mod can come first): the oracle says the same
        with pytest.raises(ValueError):
            rerolled(BOW_DATA, start, tag)
        assert "pool holds no" in str(refusal)
        return
    items = rerolled(BOW_DATA, start, tag)

    sums_to_one(items)
    agrees_with_chance_all(items, outcomes, start)


def test_the_two_locks_keep_every_mod_through_a_reroll_and_a_scouring():
    start = bow(FIRE, SOCKET, AS_5, METAMODS["PL"], METAMODS["SL"], FIRE_RES)

    assert rerolled(BOW_DATA, start) == [(start, 1)]
    assert scoured(BOW_DATA, start) == [(start, 1)]


def test_the_oracle_tiers_are_the_tiers_of_the_item_model():
    assert tier_table(BOW_DATA, BOW) == dict(items_tier_table(BOW_DATA, BOW))
    hunter = bow(influences=HUNTER, level=78)
    assert tier_table(BOW_DATA, BOW, HUNTER) == dict(tiers_of(BOW_DATA, hunter))
    assert [tier_table(BOW_DATA, BOW, HUNTER)[mod_id] for mod_id in HYBRID] == [5, 4, 3, 2, 1]
    assert not set(HYBRID) & set(tier_table(BOW_DATA, BOW))  # without the Hunter tag they cannot spawn: no tier


def test_then_composes_two_actions_over_each_finished_item():
    start = start_of("gem", None)

    after = then(fracture_one(BOW_DATA, start), lambda item: rerolled(BOW_DATA, item))

    sums_to_one(after)
    assert all(len(item.fractured_mods) == 1 and item.rarity is Rarity.RARE for item, _ in after)
    assert sum(chance for item, chance in after) == 1
