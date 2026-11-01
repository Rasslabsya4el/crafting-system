"""The Wild Bristle Matron and the Farric Wolf / Lynx side swaps against an exact hand oracle (ticket #147).

The Matron adds one of the five metamods, uniformly among those the item allows (`beastcraft.metamod_*`). A side swap
adds a mod on one side in proportion to weight at the level of the beast, then removes one mod of the other side,
uniformly among the non-fractured mods that were there before the add (`beastcraft.side_swap_*`). The pool of the
tests is the small one of `beast_mods_support.py`, whose odds are worked out by hand in each test.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from abstraction_pool import LIFE_1, RESIST_2
from beast_mods_support import (
    CHAOS1,
    COLD,
    CRAFTED,
    ES1,
    FIRE,
    GEM1,
    ITEM_LEVEL,
    LEECH,
    LIFE1,
    LIFE2,
    LIGHTNING1,
    LIGHTNING9,
    LPCT,
    METAMODS,
    MULTI,
    NO_ATTACK,
    NO_CASTER,
    PCBC,
    SCBC,
    SMALL,
    item_of,
    outcome_table,
    roll,
)
from contract_support import CONTRACT_DATA, check_action
from beasts_support import contract_item
from items_support import AMULET
from repoe_support import no_network  # noqa: F401

from crafting_system.actions import NotApplicableError, OutOfScopeError, catalog, kinds
from crafting_system.actions.beast_mods import BeastSideSwap, WildBristleMatron, wild_bristle_metamods
from crafting_system.items import Rarity, Side

F = Fraction
WOLF, LYNX = BeastSideSwap(Side.PREFIX, beast_level=74), BeastSideSwap(Side.SUFFIX, beast_level=74)
# beast level 74 on an empty prefix side: Life 1000+1000, Energy Shield 1000, Lightning 500 (the 76 and 75 mods are above it): 3500
# beast level 83 on an empty prefix side: also Lightning 9 (250) and Gem level (50): 3800


def tables(action, item) -> dict:
    return outcome_table(action.outcomes(SMALL, item))


def table(*rows) -> dict:
    """`{frozenset of ids: chance}` from `(ids, chance)` rows."""
    return {frozenset(ids): chance for ids, chance in rows}


# --- the Wild Bristle Matron: the case of the ticket -------------------------------------------------------


def test_with_the_suffixes_full_and_a_prefix_open_the_matron_gives_suffixes_cannot_be_changed_with_probability_one():
    item = item_of(FIRE, COLD, LEECH, ES1)  # three suffixes, one prefix, no crafted mod

    outcomes = WildBristleMatron().outcomes(SMALL, item)

    assert outcomes.chance_all([SCBC]) == Fraction(1)
    assert [chance for chance, _ in outcomes.results] == [Fraction(1)]
    assert tables(WildBristleMatron(), item) == table(([FIRE, COLD, LEECH, ES1, SCBC], F(1)))
    for other in (PCBC, NO_ATTACK, NO_CASTER, MULTI):
        assert outcomes.chance_all([other]) == 0
    assert dict(outcomes.distribution(lambda mod: mod.id)) == {frozenset({(SCBC, 1)}): Fraction(1)}


def test_the_metamod_is_added_as_a_crafted_mod_at_its_lowest_values_and_the_rest_stays():
    item = item_of(FIRE, COLD, LEECH, ES1)

    ((chance, result),) = WildBristleMatron().outcomes(SMALL, item).results

    assert chance == 1
    added = next(entry for entry in result.mods if entry.mod_id == SCBC)
    assert (added.crafted, added.fractured, added.tier) == (True, False, 1)
    assert added.values == tuple(min(stat.min, stat.max) for stat in SMALL.mods[SCBC].stats)
    assert [e for e in result.mods if e.mod_id != SCBC] == list(item.mods)
    assert (result.base_id, result.item_level, result.rarity) == (item.base_id, item.item_level, item.rarity)


# --- the Wild Bristle Matron: which metamods are allowed -----------------------------------------------------


def test_with_every_slot_open_each_of_the_five_metamods_has_chance_one_fifth():
    item = item_of(ES1, FIRE)

    assert tables(WildBristleMatron(), item) == table(*(([ES1, FIRE, metamod], F(1, 5)) for metamod in METAMODS))


def test_with_the_prefixes_full_the_four_suffix_metamods_share_the_draw():
    item = item_of(LIFE1, ES1, LIGHTNING1, FIRE)  # three prefixes: Suffixes Cannot Be Changed (a prefix) is out

    got = tables(WildBristleMatron(), item)

    assert got == table(*(([LIFE1, ES1, LIGHTNING1, FIRE, metamod], F(1, 4)) for metamod in (PCBC, NO_ATTACK, NO_CASTER, MULTI)))


def test_with_both_sides_full_no_metamod_is_allowed():
    item = item_of(LIFE1, ES1, LIGHTNING1, FIRE, COLD, LEECH)

    with pytest.raises(NotApplicableError, match="no metamod is allowed"):
        WildBristleMatron().outcomes(SMALL, item)


def test_a_metamod_of_a_family_the_item_holds_is_not_allowed_and_a_multimod_item_takes_more_crafted_mods():
    # the multimod makes the limit three and is itself one crafted mod; its own family is out of the draw
    one = item_of(MULTI, ES1, FIRE)
    two = item_of(MULTI, PCBC, ES1)
    three_slots = item_of(MULTI, SCBC, FIRE)  # a metamod on each side, both crafted: two held

    assert tables(WildBristleMatron(), one) == table(*(([MULTI, ES1, FIRE, m], F(1, 4)) for m in (PCBC, SCBC, NO_ATTACK, NO_CASTER)))
    assert tables(WildBristleMatron(), two) == table(*(([MULTI, PCBC, ES1, m], F(1, 3)) for m in (SCBC, NO_ATTACK, NO_CASTER)))
    assert tables(WildBristleMatron(), three_slots) == table(*(([MULTI, SCBC, FIRE, m], F(1, 3)) for m in (PCBC, NO_ATTACK, NO_CASTER)))


def test_a_multimod_item_with_a_full_suffix_side_takes_only_a_prefix_metamod():
    item = item_of(MULTI, FIRE, COLD, ES1)  # the multimod fills one of three suffix slots

    assert tables(WildBristleMatron(), item) == table(([MULTI, FIRE, COLD, ES1, SCBC], F(1)))


def test_the_limit_of_crafted_mods_is_reached_after_one_without_the_multimod_and_after_three_with_it():
    for held in (item_of(CRAFTED, FIRE), item_of(SCBC, FIRE), item_of(NO_ATTACK, ES1)):  # a craft, or a metamod: one crafted mod
        with pytest.raises(NotApplicableError, match=r"1 crafted mod, which is the limit \(1\)"):
            WildBristleMatron().outcomes(SMALL, held)
    with pytest.raises(NotApplicableError, match=r"3 crafted mods, which is the limit \(3\)"):
        WildBristleMatron().outcomes(SMALL, item_of(MULTI, SCBC, CRAFTED))


def test_a_magic_item_is_taken_like_the_bench_does():
    item = item_of(ES1, rarity=Rarity.MAGIC)  # a magic item holds one prefix and one suffix

    assert tables(WildBristleMatron(), item) == table(*(([ES1, m], F(1, 4)) for m in (PCBC, NO_ATTACK, NO_CASTER, MULTI)))


# --- the Wild Bristle Matron: refusals ---------------------------------------------------------------------


def test_a_normal_item_or_one_without_a_mod_is_out_of_scope():
    with pytest.raises(OutOfScopeError, match="normal"):
        WildBristleMatron().outcomes(SMALL, item_of(rarity=Rarity.NORMAL))
    with pytest.raises(OutOfScopeError, match="holds no mod"):
        WildBristleMatron().outcomes(SMALL, item_of())
    with pytest.raises(OutOfScopeError, match="holds no mod"):
        WildBristleMatron().outcomes(SMALL, item_of(rarity=Rarity.MAGIC))


def test_a_corrupted_item_is_refused_before_anything_else():
    with pytest.raises(NotApplicableError, match="corrupted"):
        WildBristleMatron().outcomes(SMALL, item_of(ES1, corrupted=True))
    with pytest.raises(NotApplicableError, match="corrupted"):
        WildBristleMatron().outcomes(SMALL, item_of(rarity=Rarity.NORMAL, corrupted=True))


def test_the_matron_samples_its_results_and_meets_the_contract_suite():
    item = item_of(ES1, FIRE)
    outcomes = WildBristleMatron().outcomes(SMALL, item)
    rng, runs, seen = random.Random(147), 3000, {}
    for _ in range(runs):
        drawn = outcomes.sample(rng)
        drawn.validate(SMALL)
        (new,) = drawn.crafted_mods
        seen[new.mod_id] = seen.get(new.mod_id, 0) + 1
    assert set(seen) == set(METAMODS) and all(abs(count / runs - 0.2) < 5 * (0.2 * 0.8 / runs) ** 0.5 for count in seen.values())

    pool = (RESIST_2, LIFE_1)
    assert check_action(WildBristleMatron(), contract_item(AMULET, pool, data=CONTRACT_DATA), CONTRACT_DATA) is True


def test_the_matron_meets_the_contract_on_a_full_suffix_side_and_on_a_refused_item():
    from abstraction_pool import COLD_RESIST, FIRE_RESIST
    full = contract_item(AMULET, (RESIST_2, COLD_RESIST, FIRE_RESIST, LIFE_1), data=CONTRACT_DATA)
    bare = contract_item(AMULET, (), data=CONTRACT_DATA)

    assert check_action(WildBristleMatron(), full, CONTRACT_DATA) is True
    assert check_action(WildBristleMatron(), bare, CONTRACT_DATA) is False  # a rare item with no mod is out of scope


def test_the_matrons_five_metamods_are_found_by_family_in_the_data():
    assert {mod.id for mod in wild_bristle_metamods(SMALL)} == set(METAMODS)
    assert wild_bristle_metamods(dataclasses.replace(SMALL, mods={k: v for k, v in SMALL.mods.items() if k not in METAMODS})) == ()
    fewer = dataclasses.replace(SMALL, mods={k: v for k, v in SMALL.mods.items() if k != MULTI})
    assert {mod.id for mod in wild_bristle_metamods(fewer)} == set(METAMODS) - {MULTI}


# --- the side swaps: the hand oracle ----------------------------------------------------------------------------


def test_the_wolf_adds_a_prefix_by_weight_and_removes_a_suffix_uniformly():
    item = item_of(ES1, FIRE, COLD)  # the Energy Shield family is on the item: Life 2000, Lightning 500 are left
    # added mod: Life1 1000/2500 = 2/5, Life2 2/5, Lightning1 500/2500 = 1/5; removed suffix: Fire or Cold, 1/2 each

    got = tables(WOLF, item)

    assert got == table(
        *(
            ([ES1, kept, added], share * F(1, 2))
            for kept in (COLD, FIRE)
            for added, share in ((LIFE1, F(2, 5)), (LIFE2, F(2, 5)), (LIGHTNING1, F(1, 5)))
        )
    )
    assert sum(got.values()) == 1 and len(got) == 6


def test_the_lynx_adds_a_suffix_by_weight_and_removes_a_prefix_uniformly():
    item = item_of(LIFE1, ES1, FIRE)  # Fire Resistance is on the item; at level 74: Cold 1000, Leech 1000, Chaos1 250, Lightning % 500
    # total 2750: Cold 4/11, Leech 4/11, Chaos 1/11, Lightning % 2/11; removed prefix: Life1 or Energy Shield, 1/2 each

    got = tables(LYNX, item)

    assert got == table(
        *(
            ([kept, FIRE, added], share * F(1, 2))
            for kept in (LIFE1, ES1)
            for added, share in ((COLD, F(4, 11)), (LEECH, F(4, 11)), (CHAOS1, F(1, 11)), (LPCT, F(2, 11)))
        )
    )
    assert sum(got.values()) == 1


def test_a_fractured_mod_is_never_removed():
    item = item_of(ES1, FIRE, COLD, fractured=(FIRE,))

    got = tables(WOLF, item)

    assert got == table(*(([ES1, FIRE, added], share) for added, share in ((LIFE1, F(2, 5)), (LIFE2, F(2, 5)), (LIGHTNING1, F(1, 5)))))


def test_a_crafted_mod_and_a_metamod_of_the_losing_side_are_among_the_removable_mods():
    # the Lynx removes a prefix: the prefix metamod and an ordinary prefix are 1/2 each (the lock of the suffixes does not protect it)
    item = item_of(SCBC, ES1, COLD)
    got = tables(LYNX, item)

    assert got[frozenset({ES1, COLD, "FireResist1"})] == F(4, 11) * F(1, 2)
    assert got[frozenset({SCBC, COLD, "FireResist1"})] == F(4, 11) * F(1, 2)
    assert sum(chance for ids, chance in got.items() if SCBC not in ids) == F(1, 2)
    assert sum(chance for ids, chance in got.items() if ES1 not in ids) == F(1, 2)
    assert len(got) == 8

    # a crafted suffix is removable by the Wolf the same way
    crafted_item = item_of(ES1, MULTI, COLD)
    assert sum(chance for ids, chance in tables(WOLF, crafted_item).items() if MULTI not in ids) == F(1, 2)


def test_a_lock_on_the_losing_side_makes_the_swap_add_without_removing():
    item = item_of(SCBC, ES1, FIRE, COLD)  # Suffixes Cannot Be Changed: the Wolf adds a prefix and removes no suffix
    # prefix pool at 74 without the Energy Shield family: Life 1000, 1000, Lightning 500

    got = tables(WOLF, item)

    assert got == table(*(([SCBC, ES1, FIRE, COLD, added], share) for added, share in ((LIFE1, F(2, 5)), (LIFE2, F(2, 5)), (LIGHTNING1, F(1, 5)))))
    for _, result in WOLF.outcomes(SMALL, item).results:
        assert len(result.mods) == len(item.mods) + 1


def test_a_lock_on_the_losing_side_works_even_when_that_side_is_empty():
    item = item_of(SCBC)

    got = tables(WOLF, item)

    assert got == table(*(([SCBC, added], share) for added, share in ((LIFE1, F(2, 7)), (LIFE2, F(2, 7)), (ES1, F(2, 7)), (LIGHTNING1, F(1, 7)))))
    # the same item without the lock has no suffix to remove: refused
    with pytest.raises(NotApplicableError, match="no suffix"):
        WOLF.outcomes(SMALL, item_of(ES1))


def test_the_lock_of_the_added_side_lets_its_open_slots_fill_and_does_not_protect_the_other_side():
    item = item_of(ES1, PCBC, COLD)  # Prefixes Cannot Be Changed: the Wolf still adds a prefix; the suffixes (the lock too) can lose one

    got = tables(WOLF, item)

    assert got == table(
        *(
            ([ES1, kept, added], share * F(1, 2))
            for kept in (PCBC, COLD)
            for added, share in ((LIFE1, F(2, 5)), (LIFE2, F(2, 5)), (LIGHTNING1, F(1, 5)))
        )
    )
    # and the Lynx on this item adds a suffix without removing a prefix
    lynx = tables(LYNX, item_of(ES1, PCBC))
    assert all(ES1 in ids and PCBC in ids for ids in lynx) and len(lynx) == 5  # Life leech, Fire, Cold, Chaos, Lightning % (the lock's own family is not in the pool)


def test_cannot_roll_attack_filters_the_added_mod_and_does_not_protect_an_attack_mod_from_the_removal():
    item = item_of(NO_ATTACK, LEECH)  # the attack-tagged Lightning1 prefix is out of the pool: Life1, Life2, Energy Shield 1000 each, 1/3 each

    got = tables(WOLF, item)

    assert got == table(
        *(
            ([kept, added], share * F(1, 2))
            for kept in (NO_ATTACK, LEECH)
            for added, share in ((LIFE1, F(1, 3)), (LIFE2, F(1, 3)), (ES1, F(1, 3)))
        )
    )
    assert LIGHTNING1 not in {mod for ids in got for mod in ids}


def test_cannot_roll_caster_filters_the_added_mod_of_the_lynx():
    item = item_of(NO_CASTER, LIFE1)  # Lightning % (caster tag) is out: Fire 1000, Cold 1000, Leech 1000, Chaos1 250 = 3250
    # the only prefix, Life1, is removed

    got = tables(LYNX, item)

    assert got == table(*(([NO_CASTER, added], share) for added, share in ((FIRE, F(4, 13)), (COLD, F(4, 13)), (LEECH, F(4, 13)), (CHAOS1, F(1, 13)))))


def test_the_added_mod_is_never_one_the_removal_could_take():
    item = item_of(ES1, FIRE, COLD)
    for _, result in WOLF.outcomes(SMALL, item).results:
        assert len([e for e in result.mods if SMALL.mods[e.mod_id].generation_type == "prefix"]) == 2  # the ES1 and the new prefix
        assert len([e for e in result.mods if SMALL.mods[e.mod_id].generation_type == "suffix"]) == 1


# --- the side swaps: the level of the beast, not of the item ----------------------------------------------------


def test_at_beast_level_83_the_pool_holds_every_prefix_whatever_the_item_level():
    # 3800: Life1 1000, Life2 1000, Energy Shield 1000, Lightning1 500 + Lightning9 250 (one family), Gem 50
    expected = table(
        *(
            ([added], share)
            for added, share in (
                (LIFE1, F(1000, 3800)),
                (LIFE2, F(1000, 3800)),
                (ES1, F(1000, 3800)),
                (LIGHTNING1, F(500, 3800)),
                (LIGHTNING9, F(250, 3800)),
                (GEM1, F(50, 3800)),
            )
        )
    )
    for item_level in (30, 86):  # an item of level 30 would not see the level 76 and 75 mods; the beast does
        assert tables(BeastSideSwap(Side.PREFIX, 83), item_of(COLD, item_level=item_level)) == expected
    assert BeastSideSwap(Side.PREFIX).beast_level == 83  # the default is the claim beastcraft.default_beast_level
    assert tables(BeastSideSwap(Side.PREFIX), item_of(COLD, item_level=60)) == expected


@pytest.mark.parametrize("item_level", [30, 86, 100])
def test_at_beast_level_74_the_mods_above_it_are_out_even_for_a_high_item_level(item_level):
    got = tables(WOLF, item_of(COLD, item_level=item_level))  # the one suffix, Cold, is removed

    assert got == table(*(([added], share) for added, share in ((LIFE1, F(2, 7)), (LIFE2, F(2, 7)), (ES1, F(2, 7)), (LIGHTNING1, F(1, 7)))))


def test_beast_level_75_lets_in_the_gem_level_prefix_and_beast_level_3_only_the_two_low_prefixes():
    at_75 = tables(BeastSideSwap(Side.PREFIX, 75), item_of(COLD, item_level=20))
    at_3 = tables(BeastSideSwap(Side.PREFIX, 3), item_of(COLD, item_level=86))

    assert at_75[frozenset({GEM1})] == F(50, 3550) and frozenset({LIGHTNING9}) not in at_75
    assert sum(at_75.values()) == 1
    assert at_3 == table(([ES1], F(2, 3)), ([LIGHTNING1], F(1, 3)))  # Energy Shield 1000, Lightning 500; level 5 Life1 is above 3


def test_a_beast_level_that_leaves_the_pool_empty_refuses_the_swap_whatever_the_item_level():
    with pytest.raises(NotApplicableError, match="no mod of its pool is legal"):
        BeastSideSwap(Side.PREFIX, 2).outcomes(SMALL, item_of(COLD, item_level=100))


def test_the_added_mod_is_new_at_its_lowest_values_and_table_tier():
    ((_, result),) = [pair for pair in BeastSideSwap(Side.PREFIX, 83).outcomes(SMALL, item_of(COLD)).results if any(e.mod_id == LIGHTNING1 for e in pair[1].mods)]

    added = next(e for e in result.mods if e.mod_id == LIGHTNING1)
    assert (added.tier, added.crafted, added.fractured) == (2, False, False)  # Lightning9 is the higher level: tier 1
    assert added.values == tuple(min(s.min, s.max) for s in SMALL.mods[LIGHTNING1].stats)
    assert result.item_level == ITEM_LEVEL  # the item keeps its own level


def test_chance_all_and_distribution_see_the_added_mod_and_the_mods_that_stay():
    item = item_of(ES1, FIRE, COLD)
    outcomes = WOLF.outcomes(SMALL, item)

    assert outcomes.chance_all([LIFE1]) == F(2, 5)
    assert outcomes.chance_all([ES1, LIFE1]) == F(2, 5)
    assert outcomes.chance_all([FIRE]) == F(1, 2)
    assert outcomes.chance_all([FIRE, COLD]) == 0
    assert outcomes.chance_all([LIFE1, LIFE2]) == 0
    assert outcomes.chance_all(["ChaosResist1"]) == 0
    assert dict(outcomes.distribution(lambda mod: mod.id)) == {
        frozenset({(LIFE1, 1)}): F(2, 5),
        frozenset({(LIFE2, 1)}): F(2, 5),
        frozenset({(LIGHTNING1, 1)}): F(1, 5),
    }
    with pytest.raises(ValueError, match="NoSuchMod is not in the game data"):
        outcomes.chance_all(["NoSuchMod"])


def test_the_swap_samples_its_results():
    item = item_of(ES1, FIRE, COLD)
    outcomes = WOLF.outcomes(SMALL, item)
    rng, runs, seen = random.Random(2147), 4000, {}
    for _ in range(runs):
        drawn = outcomes.sample(rng)
        drawn.validate(SMALL)
        seen[drawn.mods] = seen.get(drawn.mods, 0) + 1

    assert {frozenset(e.mod_id for e in mods) for mods in seen} == set(tables(WOLF, item))
    assert outcomes.sample(random.Random(3)) == outcomes.sample(random.Random(3))


# --- the side swaps: refusals --------------------------------------------------------------------------------------


@pytest.mark.parametrize("action", [WOLF, LYNX])
@pytest.mark.parametrize("rarity", [Rarity.NORMAL, Rarity.MAGIC])
def test_a_swap_on_an_item_that_is_not_rare_is_refused(action, rarity):
    item = item_of(rarity=rarity) if rarity is Rarity.NORMAL else item_of(ES1, rarity=rarity)

    with pytest.raises(NotApplicableError, match="rare item only"):
        action.outcomes(SMALL, item)


@pytest.mark.parametrize("action", [WOLF, LYNX])
def test_a_swap_on_a_corrupted_item_is_refused(action):
    with pytest.raises(NotApplicableError, match="corrupted"):
        action.outcomes(SMALL, item_of(ES1, FIRE, corrupted=True))


def test_a_swap_needs_an_open_slot_on_the_side_it_adds():
    full_prefixes = item_of(LIFE1, ES1, LIGHTNING1, FIRE)
    full_suffixes = item_of(LIFE1, FIRE, COLD, LEECH)

    with pytest.raises(NotApplicableError, match="no open prefix slot"):
        WOLF.outcomes(SMALL, full_prefixes)
    with pytest.raises(NotApplicableError, match="no open suffix slot"):
        LYNX.outcomes(SMALL, full_suffixes)
    assert tables(LYNX, full_prefixes) and tables(WOLF, full_suffixes)  # the other recipe of each is fine


def test_an_unlocked_losing_side_without_a_removable_mod_is_refused():
    with pytest.raises(NotApplicableError, match="no suffix that is not fractured"):
        WOLF.outcomes(SMALL, item_of(ES1))
    with pytest.raises(NotApplicableError, match="no suffix that is not fractured"):
        WOLF.outcomes(SMALL, item_of(ES1, FIRE, fractured=(FIRE,)))
    with pytest.raises(NotApplicableError, match="no prefix that is not fractured"):
        LYNX.outcomes(SMALL, item_of(FIRE))
    with pytest.raises(NotApplicableError, match="no prefix that is not fractured"):
        LYNX.outcomes(SMALL, item_of(ES1, FIRE, fractured=(ES1,)))


def test_a_swap_with_nothing_legal_to_add_is_refused():
    # at beast level 4 the prefix pool holds the Energy Shield and Lightning families only (Life1 needs level 5); the item holds both
    with pytest.raises(NotApplicableError, match="no mod of its pool is legal"):
        BeastSideSwap(Side.PREFIX, 4).outcomes(SMALL, item_of(ES1, LIGHTNING1, FIRE))
    assert tables(BeastSideSwap(Side.PREFIX, 5), item_of(ES1, LIGHTNING1, FIRE)) == table(([ES1, LIGHTNING1, LIFE1], F(1)))


def test_the_arguments_are_checked():
    for bad in (0, 101, -1, 74.0, True):
        with pytest.raises(ValueError, match="beast level"):
            BeastSideSwap(Side.PREFIX, bad)
    with pytest.raises(ValueError, match="Side"):
        BeastSideSwap("prefix")


# --- the contract every action meets ---------------------------------------------------------------------------


@pytest.mark.parametrize("side", [Side.PREFIX, Side.SUFFIX])
def test_the_swaps_meet_the_contract_suite(side):
    for mods in ((RESIST_2, LIFE_1), (LIFE_1,), (RESIST_2,)):
        item = contract_item(AMULET, mods, data=CONTRACT_DATA)
        check_action(BeastSideSwap(side), item, CONTRACT_DATA)
    both = contract_item(AMULET, (RESIST_2, LIFE_1), data=CONTRACT_DATA)
    assert check_action(BeastSideSwap(side), both, CONTRACT_DATA) is True
    assert check_action(BeastSideSwap(side, beast_level=40), both, CONTRACT_DATA) is True


# --- the actions around the outcomes ---------------------------------------------------------------------------


def test_the_labels_and_variants():
    assert WildBristleMatron().label() == "Beastcraft Wild Bristle Matron (add a metamod)"
    assert BeastSideSwap(Side.PREFIX).label() == "Beastcraft Add Prefix Remove Suffix"
    assert BeastSideSwap(Side.SUFFIX).label(SMALL) == "Beastcraft Add Suffix Remove Prefix"
    assert BeastSideSwap(Side.PREFIX).variant != BeastSideSwap(Side.PREFIX, 60).variant


def test_the_resources_are_the_named_beast_and_the_rare_beasts_as_chaos_orbs():
    assert WildBristleMatron().resources() == {"Wild Bristle Matron": 1, "Chaos Orb": 3}
    assert BeastSideSwap(Side.PREFIX).resources() == {"Farric Wolf Alpha": 1, "Chaos Orb": 3}
    assert BeastSideSwap(Side.SUFFIX).resources(SMALL) == {"Farric Lynx Alpha": 1, "Chaos Orb": 3}


def test_the_rare_creature_price_is_a_setting():
    assert WildBristleMatron(rare_creature_price=2).resources() == {"Wild Bristle Matron": 1, "Chaos Orb": 6}
    assert BeastSideSwap(Side.PREFIX, rare_creature_price=5).resources() == {"Farric Wolf Alpha": 1, "Chaos Orb": 15}
    assert BeastSideSwap(Side.SUFFIX, rare_creature_price=2).resources() == {"Farric Lynx Alpha": 1, "Chaos Orb": 6}
    assert WildBristleMatron() == WildBristleMatron(rare_creature_price=1) != WildBristleMatron(rare_creature_price=2)
    assert BeastSideSwap(Side.PREFIX) != BeastSideSwap(Side.SUFFIX) and BeastSideSwap(Side.PREFIX) != BeastSideSwap(Side.PREFIX, 74)


def test_the_declarations():
    matron, adds = WildBristleMatron().reads(SMALL), WildBristleMatron().adds(SMALL, item_of(ES1))
    assert matron.junk and matron.block_invariant and matron.families is not None
    assert len(matron.families) == 5 and "ItemGenerationCannotChangeSuffixes" in matron.families
    assert (adds.named, adds.crafted, adds.draws) == (None, True, True)

    swap, adds = WOLF.reads(SMALL), WOLF.adds(SMALL, item_of(COLD))
    assert swap.junk and swap.families is None and not swap.pool_weight and not swap.block_invariant
    assert adds.draws and adds.named is None and adds.keeps_crafted


def test_the_kinds_are_offered_for_a_rare_item_only_and_are_opt_in_planner_kinds():
    item = item_of(ES1, FIRE)
    offered = catalog(SMALL, item)

    assert [a for a in offered if isinstance(a, BeastSideSwap)] == [BeastSideSwap(Side.PREFIX), BeastSideSwap(Side.SUFFIX)]
    assert [a for a in offered if isinstance(a, WildBristleMatron)] == [WildBristleMatron()]
    magic = catalog(SMALL, item_of(ES1, rarity=Rarity.MAGIC))
    assert not [a for a in magic if isinstance(a, (BeastSideSwap, WildBristleMatron))]
    assert not [a for a in catalog(SMALL, item, planner_only=True) if isinstance(a, (BeastSideSwap, WildBristleMatron))]  # opt-in: a target names them
    named = {"beast-side-swap", "wild-bristle-matron"}
    assert [a for a in catalog(SMALL, item, planner_only=True, names=named) if isinstance(a, (BeastSideSwap, WildBristleMatron))]
    registered = {entry.name: entry for entry in kinds()}
    for name in named:
        assert registered[name].planner and registered[name].opt_in and not registered[name].why_not
    assert (registered["beast-side-swap"].order, registered["wild-bristle-matron"].order) == (85, 86)


def test_roll_helper_matches_the_item_model():
    assert roll(ES1, crafted=False).values == item_of(ES1).mods[0].values


# --- the item class: a metamod is a crafted mod, and the bench offers it for equipment classes only ---------------


def test_the_matron_is_offered_and_works_only_on_an_item_class_the_bench_offers_metamods_for():
    item = item_of(LIFE1, FIRE)
    jewel_base = dataclasses.replace(SMALL.base_items[AMULET], item_class="Jewel")
    jewel_data = dataclasses.replace(SMALL, base_items={**SMALL.base_items, AMULET: jewel_base})
    assert WildBristleMatron() in catalog(SMALL, item)
    assert WildBristleMatron() not in catalog(jewel_data, item)
    with pytest.raises(NotApplicableError, match="no metamod is allowed"):
        WildBristleMatron().outcomes(jewel_data, item)
