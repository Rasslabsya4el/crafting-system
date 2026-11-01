"""Pools of family types and the variants of the additions (ticket #172, ADR-0023) on the committed fixture of `coarse_support.py`.

The goal asks for a resistance and life, which are the two families of the small pool that give the goal
something. Of the rest, with the additions enabled and no craft that tells a family apart, the prefixes Gem (600)
and Lightning damage (1000) are one family type each, and the suffixes Cold and Fire Resistance (1000 each) are
one family type with two families and Mana Leech (2000) another. So the pools of a spread are made of kinds, and
the weights differ between them, which is what makes the members of a block differ.

The checks are against something written without the code under test: the brute force lists concrete items,
compresses them with the exact abstraction and groups them by block; every member of a block has its exact
kernel pushed through the block map, and the extremes claim (the backup of every member lies between the
smallest and the largest backup of the variants) is tried on random continuation values.
"""

import dataclasses
import functools

import pytest
from abstraction_pool import COLD_RESIST, DAMAGE_1, FIRE_RESIST, GEM, LEVEL, LIFE_1, LIVES, MANA_1, RESIST_2, RESISTS
from coarse_support import (
    COLD,
    DATA,
    FIRE,
    LIGHTNING_DAMAGE,
    LIGHTNING_RESIST,
    MANA,
    MANA_CRAFT,
    blocks_of,
    compare_members,
    compare_variants,
    concrete_items,
    exact_kernel,
    item,
    pushed,
    roll,
)
from items_support import AMULET

from crafting_system.abstraction import Abstraction, Coarsening, Goal, Wanted
from crafting_system.actions import (
    ActionError,
    AnnulmentOrb,
    AugmentationOrb,
    BenchCraft,
    ExaltedOrb,
    NotApplicableError,
    RegalOrb,
)
from crafting_system.items import Rarity, Side

GEM_FAMILY = "GlobalDamageTypeGemLevel"
LIFE_FAMILY = "IncreasedLife"
GOAL = Goal((Wanted(RESISTS), Wanted(LIVES)))
ADDITIONS = (AugmentationOrb(), RegalOrb(), ExaltedOrb())
ANNUL = AnnulmentOrb()
CRAFT = BenchCraft(MANA_CRAFT)
POOL_MODS = [MANA_1, COLD_RESIST, FIRE_RESIST, DAMAGE_1, GEM, LIFE_1, RESIST_2]
ITEMS = list(concrete_items(DATA, POOL_MODS, crafted=[MANA_CRAFT], largest=4, rarities=(Rarity.RARE, Rarity.MAGIC)))


def build(*actions) -> Abstraction:
    return Abstraction(DATA, GOAL, AMULET, LEVEL, (*ADDITIONS, ANNUL, *actions))


TYPED = build()  # no craft tells a family apart: the families are family types
MIXED = build(CRAFT)  # Mana Leech is told apart by the craft, Cold and Fire are a type


# --- pooling by spread ---------------------------------------------------------------------------------------------


def test_the_kinds_of_the_fixture_are_family_types_and_the_craft_tells_mana_apart():
    kinds = {family: TYPED.kind_of(next(m for m in DATA.mods.values() if family in m.families)) for family in (COLD, FIRE, MANA, LIGHTNING_DAMAGE, GEM_FAMILY)}

    assert kinds[COLD] == kinds[FIRE] != kinds[MANA]
    assert all(kind.startswith("~") for kind in kinds.values())
    assert MIXED.kind_of(DATA.mods[MANA_1]) == MANA


def groups_of(ab, spread):
    return sorted(sorted(group) for group in Coarsening.pooling_by_spread(ab, spread).groups)


def test_a_pool_takes_consecutive_kinds_within_the_spread_of_the_lightest_and_not_across_a_gap():
    assert groups_of(TYPED, 0) == []  # Cold and Fire are one kind: a single unit is no pool
    assert groups_of(TYPED, 399) == []  # Gem (600) and Lightning damage (1000) are 400 apart
    assert groups_of(TYPED, 400) == [sorted([GEM_FAMILY, LIGHTNING_DAMAGE])]
    assert groups_of(TYPED, 999) == [sorted([GEM_FAMILY, LIGHTNING_DAMAGE])]  # Mana (2000) is 1000 above the type of Cold and Fire
    assert groups_of(TYPED, 1000) == sorted([sorted([GEM_FAMILY, LIGHTNING_DAMAGE]), sorted([COLD, FIRE, MANA])])


def test_a_family_type_is_one_unit_with_all_its_families_and_a_mixed_pool_has_named_and_typed_kinds():
    pooling = Coarsening.pooling_by_spread(MIXED, 1000)

    assert {frozenset({COLD, FIRE, MANA}), frozenset({GEM_FAMILY, LIGHTNING_DAMAGE})} == set(pooling.groups)
    assert pooling.told_apart == {MANA}  # the others are family types


def test_a_goal_family_is_never_pooled_however_wide_the_spread_and_each_group_is_of_one_side():
    pooling = Coarsening.pooling_by_spread(TYPED, 100_000)

    assert len(pooling.groups) == 2
    assert all(LIFE_FAMILY not in group and LIGHTNING_RESIST not in group for group in pooling.groups)
    sides = [{pooling.side_of(family) for family in group} for group in pooling.groups]
    assert sorted(side for (side,) in sides) == [Side.PREFIX, Side.SUFFIX]


def test_the_families_a_start_item_fractures_are_left_out_when_told_apart_but_not_when_they_are_a_type():
    fractured = TYPED.compress(item(roll(MANA_1, fractured=True)))
    named = MIXED.compress(item(roll(MANA_1, fractured=True)))

    assert {frozenset({COLD, FIRE, MANA}), frozenset({GEM_FAMILY, LIGHTNING_DAMAGE})} == set(Coarsening.pooling_by_spread(TYPED, 1000, fractured).groups)
    assert set(Coarsening.pooling_by_spread(MIXED, 1000, named).groups) == {frozenset({GEM_FAMILY, LIGHTNING_DAMAGE})}


def test_no_pool_is_a_coarsening_that_pools_nothing_and_a_negative_spread_is_refused():
    assert Coarsening.pooling_by_spread(TYPED, 0).groups == ()
    with pytest.raises(ValueError, match="cannot be negative"):
        Coarsening.pooling_by_spread(TYPED, -1)


def test_a_group_that_splits_a_family_type_is_refused():
    with pytest.raises(ValueError, match=r"family type [~]\d+, so every family of that type"):
        Coarsening(TYPED, [{COLD, MANA}])
    with pytest.raises(ValueError, match="must be in its group"):
        Coarsening(MIXED, [{FIRE, MANA}])
    Coarsening(TYPED, [{COLD, FIRE, MANA}])  # the whole type is fine


# --- the members and the extremes of a block ------------------------------------------------------------------------


LEVELS = {  # name -> (abstraction, spread)
    "typed_prefixes_and_suffixes": (TYPED, 1000),
    "typed_prefixes": (TYPED, 400),
    "mixed": (MIXED, 1000),
}


@functools.cache
def world(name: str):
    ab, spread = LEVELS[name]
    pooling = Coarsening.pooling_by_spread(ab, spread)
    blocks = blocks_of(ab, pooling, ITEMS)
    start = pooling.coarsen(ab.compress(item(roll(MANA_1), rarity=Rarity.MAGIC)))
    reached = pooling.reachable([start], (*ADDITIONS, ANNUL), "lower", stop_at_goal=True)
    return ab, pooling, {**{block: set(pooling.members(block)) for block in reached}, **blocks}  # the reached blocks, with all their members


@pytest.mark.parametrize("name", LEVELS)
def test_the_members_of_a_block_of_typed_and_mixed_pools_are_the_exact_states_that_map_to_it(name):
    ab, pooling, blocks = world(name)
    brute = blocks_of(ab, pooling, ITEMS)

    assert len(brute) > 50
    for block, states in brute.items():
        members = list(pooling.members(block))
        assert set(members) == states
        assert len(members) == len(set(members)), "each member once, however many families of a type there are"
    for block in blocks:
        assert all(pooling.coarsen(member) == block for member in pooling.members(block))


@pytest.mark.parametrize("name", LEVELS)
@pytest.mark.parametrize("action", ADDITIONS, ids=lambda action: type(action).__name__)
def test_the_backup_of_every_member_lies_between_the_smallest_and_the_largest_over_the_variants(name, action):
    ab, pooling, blocks = world(name)

    compared = compare_variants(action, ab, pooling, blocks)

    assert compared > 0


@pytest.mark.parametrize("name", LEVELS)
def test_annulment_and_the_craft_give_the_same_pushed_kernel_on_every_member_of_a_block(name):
    ab, pooling, blocks = world(name)

    assert compare_members(ANNUL, ab, pooling, blocks) > 0
    if ab is MIXED:
        assert compare_members(CRAFT, ab, pooling, blocks) > 0


@pytest.mark.parametrize("name", LEVELS)
def test_the_variants_of_an_invariant_action_are_its_one_kernel(name):
    ab, pooling, blocks = world(name)

    for block in list(blocks)[:200]:
        for bound in ("lower", "upper"):
            try:
                kernel = pooling.kernel(block, ANNUL, bound)
            except ActionError:
                with pytest.raises(ActionError):
                    pooling.variants(block, ANNUL, bound)
                continue
            assert pooling.variants(block, ANNUL, bound) == (kernel,)


# --- what the variants are -------------------------------------------------------------------------------------------


def block_of(ab, pooling, *mods, rarity=Rarity.RARE):
    return pooling.coarsen(ab.compress(item(*mods, rarity=rarity)))


def test_a_pool_that_holds_a_slot_has_a_light_and_a_heavy_variant_and_kernel_then_asks_for_variants():
    pooling = Coarsening.pooling_by_spread(TYPED, 1000)
    block = block_of(TYPED, pooling, roll(COLD_RESIST), roll(LIFE_1))  # one pooled suffix slot

    light, heavy = pooling.variants(block, ExaltedOrb(), "lower")

    assert light != heavy and pooling.variants(block, ExaltedOrb(), "upper") == (light, heavy)
    with pytest.raises(ValueError, match="several variants"):
        pooling.kernel(block, ExaltedOrb(), "lower")
    # the light variant is the member that holds Cold or Fire (1000), the heavy one holds Mana (2000)
    by_kind = {
        next(slot.kind for slot in member.slots if slot.side is Side.SUFFIX): pushed(pooling, exact_kernel(TYPED, member, ExaltedOrb()))
        for member in pooling.members(block)
    }
    assert by_kind == {TYPED.kind_of(DATA.mods[COLD_RESIST]): light, TYPED.kind_of(DATA.mods[MANA_1]): heavy}


def test_a_pool_of_families_of_one_weight_and_a_block_without_a_pooled_slot_have_one_variant():
    pooling = Coarsening.pooling_by_spread(TYPED, 1000)
    none_pooled = block_of(TYPED, pooling, roll(LIFE_1), roll(RESIST_2))
    only_prefix = block_of(TYPED, pooling, roll(DAMAGE_1), roll(LIFE_1))  # Gem and Lightning damage differ: two variants
    exact = Coarsening(TYPED)  # no pool: the exact blocks

    assert len(pooling.variants(none_pooled, ExaltedOrb(), "lower")) == 1
    assert pooling.kernel(none_pooled, ExaltedOrb(), "upper") == pooling.variants(none_pooled, ExaltedOrb(), "lower")[0]
    assert len(pooling.variants(only_prefix, ExaltedOrb(), "lower")) == 2
    assert len(exact.variants(exact.coarsen(TYPED.compress(item(roll(COLD_RESIST), roll(LIFE_1)))), ExaltedOrb(), "lower")) == 1


def test_two_pools_with_a_slot_each_have_up_to_four_variants_and_they_are_distinct():
    pooling = Coarsening.pooling_by_spread(TYPED, 1000)
    block = block_of(TYPED, pooling, roll(COLD_RESIST), roll(DAMAGE_1))

    found = pooling.variants(block, ExaltedOrb(), "lower")

    assert len(found) == 4 and len({tuple(sorted(kernel.items(), key=repr)) for kernel in found}) == 4


def test_the_lower_model_offers_an_addition_when_one_variant_can_take_it_and_the_upper_only_when_all_can():
    pooling = Coarsening.pooling_by_spread(TYPED, 1000)
    full_suffix = block_of(TYPED, pooling, roll(COLD_RESIST), roll(FIRE_RESIST), roll(MANA_1))  # the suffix side is full: no member can add a suffix, but a prefix is free

    assert pooling.variants(full_suffix, ExaltedOrb(), "lower")
    magic = block_of(TYPED, pooling, roll(COLD_RESIST), roll(DAMAGE_1), rarity=Rarity.MAGIC)
    for bound in ("lower", "upper"):
        with pytest.raises(NotApplicableError):
            pooling.variants(magic, ExaltedOrb(), bound)  # Exalted needs a rare item, in every member
        with pytest.raises(NotApplicableError):
            pooling.variants(magic, AugmentationOrb(), bound)  # a magic item with a prefix and a suffix has no room


def test_a_crafted_slot_sits_only_on_a_family_that_has_a_crafted_mod():
    pooling = Coarsening.pooling_by_spread(MIXED, 1000)
    block = block_of(MIXED, pooling, roll(COLD_RESIST), roll(MANA_CRAFT, crafted=True))  # a plain suffix slot and a crafted one

    members = list(pooling.members(block))

    assert len(members) == 1  # the crafted slot takes Mana, the plain slot Cold or Fire (one kind)
    assert len(pooling.variants(block, ExaltedOrb(), "lower")) == 1


def test_a_pool_with_too_few_free_families_is_an_error_not_a_variant():
    pooling = Coarsening.pooling_by_spread(TYPED, 1000)
    block = block_of(TYPED, pooling, roll(DAMAGE_1), roll(LIFE_1))  # one slot in the prefix pool of two families
    pooled = next(slot for slot in block.slots if slot.kind.startswith("="))
    too_many = dataclasses.replace(block, slots=(*block.slots, pooled, pooled))

    with pytest.raises(ValueError, match="2 free families of 2 but the block puts 3 slots"):
        pooling.variants(too_many, ExaltedOrb(), "lower")
