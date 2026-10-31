"""The coarse state with family groups (ticket #125, ADR-0023) on the committed fixture of `coarse_support.py`.

The fixture is a small amulet pool with a hybrid craft that the goal asks for, blocked by two families that
give the goal nothing (cold and fire resistance), three crafts that give it nothing, and a hybrid junk mod. The
checks are against something written without the code under test: the brute force lists concrete items, compresses
them with the exact abstraction and groups them by block, and `solve` on the exact graph gives the optimum that the
two coarse models must bracket.
"""

import dataclasses
import functools
from fractions import Fraction

import pytest
from abstraction_pool import COLD_RESIST, DAMAGE_1, FIRE_RESIST, GEM, LIFE_1, MANA_1, RESIST_1, RESIST_2
from coarse_support import (
    CHAOS,
    COLD,
    CRAFTS,
    DAMAGE_CRAFT,
    DATA,
    ENABLED,
    FIRE,
    HYBRID_CRAFT,
    HYBRID_JUNK,
    LIGHTNING_CRAFT,
    LIGHTNING_DAMAGE,
    LIGHTNING_RESIST,
    MANA,
    MANA_CRAFT,
    OFFERS,
    CoarseModel,
    ExactModel,
    abstraction,
    blocks_of,
    compare_members,
    concrete_items,
    item,
    roll,
)

from crafting_system.abstraction import Coarsening, Goal, Wanted
from crafting_system.actions import (
    Action,
    BenchCraft,
    NotApplicableError,
    OutOfScopeError,
    RegalOrb,
    Reads,
)
from crafting_system.items import Side
from crafting_system.solver import solve

AB = abstraction()
POOL_MODS = [MANA_1, COLD_RESIST, FIRE_RESIST, HYBRID_JUNK, DAMAGE_1, RESIST_2, LIFE_1, GEM]
ITEMS = list(concrete_items(DATA, POOL_MODS, crafted=[MANA_CRAFT, LIGHTNING_CRAFT, DAMAGE_CRAFT], largest=4))
LEVELS = {  # name -> groups of families
    "irrelevant_in_one_group": None,
    "two_strangers": [{MANA, LIGHTNING_RESIST}],
    "a_blocker_with_a_stranger": [{COLD, MANA}],
    "both_blockers_with_a_stranger": [{COLD, FIRE, MANA}],
    "blockers_in_two_groups": [{COLD, MANA}, {FIRE, LIGHTNING_RESIST}],
    "only_the_two_blockers": [{COLD, FIRE}],
}


def coarsening(level) -> Coarsening:
    if level is None or isinstance(level, int):
        return Coarsening.pooling_irrelevant(AB, level)
    return Coarsening(AB, level)


@functools.cache
def blocks_at(name: str):
    """The coarsening of a level and the exact states of the fixture items grouped by its blocks."""
    pooling = coarsening(LEVELS[name])
    return pooling, blocks_of(AB, pooling, ITEMS)


# --- which families are pooled ---------------------------------------------------------------------------------


def test_the_families_a_goal_craft_clashes_with_and_the_goal_families_are_relevant_the_others_pooled():
    pooling = Coarsening.pooling_irrelevant(AB)

    assert pooling.told_apart == {COLD, FIRE, MANA, LIGHTNING_RESIST, LIGHTNING_DAMAGE}
    assert pooling.relevant_families == {COLD, FIRE, "IncreasedLife"}  # the hybrid craft's two blockers, and the life family
    assert pooling.groups == (frozenset({MANA, LIGHTNING_RESIST, LIGHTNING_DAMAGE}),)


def test_groups_of_a_size_cut_the_irrelevant_families_in_name_order():
    assert Coarsening.pooling_irrelevant(AB, 2).groups == (
        frozenset({LIGHTNING_DAMAGE, LIGHTNING_RESIST}),
        frozenset({MANA}),
    )
    with pytest.raises(ValueError, match="at least one family"):
        Coarsening.pooling_irrelevant(AB, 0)


def test_a_goal_relevant_family_is_never_pooled():
    resist_goal = Goal((Wanted(frozenset({HYBRID_CRAFT})), Wanted(frozenset({RESIST_1, RESIST_2}))))
    ab = abstraction(resist_goal)

    pooling = Coarsening.pooling_irrelevant(ab)

    assert LIGHTNING_RESIST in pooling.relevant_families and LIGHTNING_RESIST in pooling.told_apart
    assert all(LIGHTNING_RESIST not in group for group in pooling.groups)
    with pytest.raises(ValueError, match="goal-relevant family is never pooled"):
        Coarsening(ab, [{LIGHTNING_RESIST, MANA}])


def test_a_family_the_state_already_merges_or_the_pool_does_not_have_cannot_be_pooled_and_none_twice():
    with pytest.raises(ValueError, match="not told apart"):
        Coarsening(AB, [{"IncreasedLife", MANA}])
    with pytest.raises(ValueError, match="not a family of the pool"):
        Coarsening(AB, [{"NoSuchFamily", MANA}])
    with pytest.raises(ValueError, match="in two groups"):
        Coarsening(AB, [{MANA, COLD}, {MANA, FIRE}])


# --- the map to blocks -----------------------------------------------------------------------------------------


def state(*mods):
    return AB.compress(item(*mods))


def test_the_slots_of_pooled_families_get_the_kind_of_their_group_and_the_rest_stay_exact():
    pooling = coarsening(None)
    start = state(roll(MANA_1), roll(COLD_RESIST), roll(LIFE_1))

    block = pooling.coarsen(start)

    kinds = sorted((slot.side, slot.kind) for slot in block.slots)
    assert kinds == [(Side.PREFIX, ""), (Side.SUFFIX, COLD), (Side.SUFFIX, "~g0")]  # life merges already, cold is a blocker
    assert pooling.coarsen(block) == block


def test_two_states_that_differ_in_the_pooled_family_are_one_block_and_other_families_are_not():
    pooling = coarsening(None)

    assert pooling.coarsen(state(roll(MANA_1), roll(LIFE_1))) == pooling.coarsen(state(roll("LightningResist1"), roll(LIFE_1)))
    assert pooling.coarsen(state(roll(MANA_1), roll(LIFE_1))) != pooling.coarsen(state(roll(COLD_RESIST), roll(LIFE_1)))


def test_hybrid_junk_fractured_and_hybrid_crafted_mods_are_never_pooled_a_plain_crafted_mod_is():
    pooling = Coarsening(AB, [{COLD, MANA}, {FIRE, LIGHTNING_RESIST}])

    hybrid = pooling.coarsen(state(roll(HYBRID_JUNK), roll(LIFE_1)))
    fractured = pooling.coarsen(state(roll(MANA_1, fractured=True), roll(LIFE_1)))
    crafted = pooling.coarsen(state(roll(LIFE_1), roll(MANA_CRAFT, crafted=True)))
    hybrid_crafted = pooling.coarsen(state(roll(LIFE_1), roll(HYBRID_CRAFT, crafted=True)))

    assert [slot.kind for slot in hybrid.slots if slot.side is Side.SUFFIX] == [f"{COLD}|{MANA}"]
    assert [entry.mod_id for entry in fractured.fractured] != [] and all(not slot.kind.startswith("~") for slot in fractured.slots)
    assert any(slot.crafted and slot.kind == "~g0" for slot in crafted.slots)  # the mana craft's slot is pooled with mana
    assert any(slot.crafted and slot.kind == HYBRID_CRAFT for slot in hybrid_crafted.slots)


# --- the members of a block ------------------------------------------------------------------------------------


@pytest.mark.parametrize("level", LEVELS)
def test_the_members_of_a_block_are_the_exact_states_that_map_to_it(level):
    pooling, blocks = blocks_at(level)

    assert len(blocks) > 50
    for block, states in blocks.items():
        assert set(pooling.members(block)) == states


# --- the kernels, member by member -------------------------------------------------------------------------------


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("action", OFFERS, ids=lambda action: action.label(DATA)[:30])
def test_every_member_of_a_block_gives_the_same_pushed_kernel_and_the_models_follow_the_members(level, action):
    pooling, blocks = blocks_at(level)

    compared = compare_members(action, AB, pooling, blocks)

    assert compared > 0


def test_the_per_member_comparison_covers_full_prefix_and_suffix_sides():
    pooling, blocks = blocks_at("irrelevant_in_one_group")

    full = {side: [b for b in blocks if b.count(side) == 3] for side in Side}

    assert all(full.values())
    assert any(b.count(Side.SUFFIX) == 3 and not b.crafted for b in blocks)
    for craft in CRAFTS:  # a craft needs a free slot of its side, so a full side refuses it in every member
        side = Side(DATA.mods[craft.mod_id].generation_type)
        for block in full[side]:
            for bound in ("lower", "upper"):
                with pytest.raises(NotApplicableError):
                    pooling.kernel(block, craft, bound)


# --- the legality rule of a craft in a group ---------------------------------------------------------------------


def legal(pooling, start, craft, bound) -> bool:
    try:
        pooling.kernel(pooling.coarsen(AB.compress(start)), craft, bound)
    except NotApplicableError:
        return False
    return True


@pytest.mark.parametrize("junk", range(4))
def test_a_craft_of_a_family_in_a_group_of_three_is_legal_in_the_lower_model_up_to_k_minus_one_and_in_the_upper_only_with_none(junk):
    pooling = Coarsening(AB, [{COLD, FIRE, MANA}])
    mods = [roll(mod_id) for mod_id in (COLD_RESIST, FIRE_RESIST, MANA_1)[:junk]]
    start = item(*mods, roll(LIFE_1))
    craft = BenchCraft(MANA_CRAFT)  # a suffix craft of the mana family

    assert legal(pooling, start, craft, "lower") == (junk <= 2)  # n <= k - 1; at n = 3 the suffix side is full as well
    assert legal(pooling, start, craft, "upper") == (junk == 0)


def test_a_craft_of_the_fractured_family_is_illegal_in_both_models_and_other_crafts_lose_a_free_family():
    pooling = Coarsening(AB, [{COLD, FIRE, MANA}])
    craft = BenchCraft(MANA_CRAFT)
    fractured_mana = item(roll(MANA_1, fractured=True), roll(LIFE_1))
    fractured_cold = item(roll(COLD_RESIST, fractured=True), roll(FIRE_RESIST), roll(LIFE_1))

    assert not legal(pooling, fractured_mana, craft, "lower") and not legal(pooling, fractured_mana, craft, "upper")
    assert not legal(pooling, fractured_cold, craft, "upper")
    assert legal(pooling, fractured_cold, craft, "lower")  # Cold held exactly, Fire pooled: n = 1 <= k - |H| - 1 = 1


def test_a_hybrid_junk_mod_holds_both_its_families_even_when_they_are_in_two_groups():
    craft = BenchCraft(MANA_CRAFT)
    start = item(roll(HYBRID_JUNK), roll(LIFE_1))  # cold and mana

    for groups in ([{COLD, MANA}], [{COLD, MANA}, {FIRE, LIGHTNING_RESIST}], [{COLD, FIRE}, {MANA, LIGHTNING_RESIST}]):
        pooling = Coarsening(AB, groups)
        assert not legal(pooling, start, craft, "lower") and not legal(pooling, start, craft, "upper")
        assert not legal(pooling, start, BenchCraft(HYBRID_CRAFT), "lower")  # cold blocks the hybrid craft as well


# --- the bounds bracket the exact optimum -------------------------------------------------------------------------------


EXACT = solve(ExactModel(AB), [AB.compress(item(roll(COLD_RESIST), roll(LIFE_1)))])


def bounds(level):
    pooling = coarsening(LEVELS[level])
    start = pooling.coarsen(AB.compress(item(roll(COLD_RESIST), roll(LIFE_1))))
    lower = solve(CoarseModel(pooling, "lower"), [start])
    upper = solve(CoarseModel(pooling, "upper"), [start])
    return lower.values[start] * (1 - lower.error_bound), upper.values[start] * (1 + upper.error_bound), len(lower.values)


@pytest.mark.parametrize("level", LEVELS)
def test_the_two_models_bracket_the_exact_optimum(level):
    start = AB.compress(item(roll(COLD_RESIST), roll(LIFE_1)))
    exact = EXACT.values[start]
    lower, upper, _ = bounds(level)

    assert lower <= exact * (1 + 1e-9) and exact * (1 - 1e-9) <= upper


def test_pooling_a_blocker_of_the_goal_craft_gives_a_gap_and_pooling_unrelated_families_none():
    start = AB.compress(item(roll(COLD_RESIST), roll(LIFE_1)))
    exact = EXACT.values[start]
    for level in ("irrelevant_in_one_group", "two_strangers", "only_the_two_blockers"):
        lower, upper, _ = bounds(level)
        assert upper / lower - 1 < 1e-8  # nothing in the best policy depends on the pooled families
        assert abs(upper - exact) < 1e-8 * exact
    for level in ("a_blocker_with_a_stranger", "both_blockers_with_a_stranger"):
        lower, upper, _ = bounds(level)
        assert upper / lower - 1 > 0.05  # a member may hold the stranger, so the craft is open in one model only
    # the two blockers alone: the craft is blocked by cold or fire, and the group holds only those
    assert bounds("only_the_two_blockers")[2] <= len(EXACT.values)


# --- what is refused --------------------------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AnnulmentLike(Action):
    """Removes one mod at random; nothing declares its block invariance, so the coarse state refuses it."""

    def label(self, data=None) -> str:
        return "Annulment-like"

    def resources(self, data=None):
        return {"Orb of Annulment": 1}

    def outcomes(self, data, item):  # pragma: no cover - never reached
        raise AssertionError("the coarse state refuses before asking")


@pytest.mark.parametrize("action", [AnnulmentLike(), RegalOrb()], ids=["annulment", "addition"])
def test_an_action_that_is_not_declared_block_invariant_is_refused_in_both_models(action):
    pooling = coarsening(None)
    block = pooling.coarsen(AB.compress(item(roll(MANA_1), roll(LIFE_1))))

    for bound in ("lower", "upper"):
        with pytest.raises(OutOfScopeError, match="not declared block-invariant"):
            pooling.kernel(block, action, bound)


def test_a_coarsening_cannot_be_built_over_an_enabled_action_that_is_not_block_invariant():
    with pytest.raises(OutOfScopeError, match="not declared block-invariant"):
        Coarsening(abstraction(actions=(*ENABLED, AnnulmentLike())), [{MANA, COLD}])


@dataclasses.dataclass(frozen=True)
class ReadsEveryFamily(AnnulmentLike):
    def reads(self, data) -> Reads:
        return Reads(junk=True, families=None, block_invariant=True)


def test_an_action_that_reads_every_family_has_no_family_group_even_if_it_says_it_is_invariant():
    with pytest.raises(OutOfScopeError, match="reads every family"):
        Coarsening(abstraction(actions=(*ENABLED, ReadsEveryFamily())), [{MANA, COLD}])


def test_the_kernel_asks_for_a_bound_and_for_a_block_of_the_coarsening():
    pooling = coarsening(None)
    block = pooling.coarsen(AB.compress(item(roll(MANA_1), roll(LIFE_1))))

    with pytest.raises(ValueError, match="'lower' or 'upper'"):
        pooling.kernel(block, CHAOS, "middle")
    other = Coarsening(AB, [{COLD, FIRE}, {MANA, LIGHTNING_RESIST}])
    with pytest.raises(ValueError, match="not a block of this coarsening"):
        pooling.kernel(other.coarsen(AB.compress(item(roll(MANA_1), roll(LIFE_1)))), CHAOS, "lower")


def test_a_reroll_has_the_same_kernel_in_both_models_whatever_the_block():
    pooling, blocks = blocks_at("irrelevant_in_one_group")

    for block in list(blocks)[:200]:
        assert pooling.kernel(block, CHAOS, "lower") == pooling.kernel(block, CHAOS, "upper")
        assert sum(pooling.kernel(block, CHAOS, "lower").values()) == Fraction(1)


def test_the_reachable_blocks_of_the_upper_model_are_among_those_of_the_lower_and_fewer_than_the_exact_states():
    start = AB.compress(item(roll(COLD_RESIST), roll(LIFE_1)))
    pooling = coarsening(None)

    exact = AB.reachable([start], OFFERS)
    lower = pooling.reachable([pooling.coarsen(start)], OFFERS, "lower")
    upper = pooling.reachable([pooling.coarsen(start)], OFFERS, "upper")

    assert upper <= lower and len(lower) < len(exact)
    assert {pooling.coarsen(s) for s in exact} <= lower


def test_reachable_and_a_model_refuse_an_action_that_is_not_block_invariant_instead_of_dropping_it():
    pooling = coarsening(None)
    start = pooling.coarsen(AB.compress(item(roll(MANA_1), roll(LIFE_1))))

    with pytest.raises(OutOfScopeError, match="not declared block-invariant"):
        pooling.reachable([start], [CHAOS, RegalOrb()])
    with pytest.raises(OutOfScopeError, match="not declared block-invariant"):
        CoarseModel(pooling, "lower", [CHAOS, RegalOrb()])


def test_a_crafted_goal_mod_is_held_exactly_and_its_family_can_still_host_a_plain_craft_in_a_group():
    goal = Goal((Wanted(frozenset({LIGHTNING_CRAFT})), Wanted(frozenset({LIFE_1, "IncreasedLife2"}))))
    ab = abstraction(goal)
    pooling = Coarsening(ab, [{LIGHTNING_RESIST, MANA}])
    blocks = blocks_of(ab, pooling, ITEMS)

    assert len(blocks) > 50
    for block, states in blocks.items():
        assert set(pooling.members(block)) == states
    for action in OFFERS:
        compare_members(action, ab, pooling, blocks)
