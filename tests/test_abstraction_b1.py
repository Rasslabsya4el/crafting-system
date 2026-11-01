"""Compressed state and kernels for essences and bench crafts on the fixture belt (ticket #59, verification layer 1).

The belt has seven families (two prefix, five suffix). Every kernel is checked against the brute
force of `abstraction_oracle.py`: all the finished items of the action on a concrete item, compressed
one by one with the same `compress` and added up, in exact fractions.

The enabled actions are the two bench crafts of the fixture that the belt takes, `JunMaster2AllDamage2_`
(family AllDamage, not in the belt pool) and `JunMaster2ArmourAndEnergyShield1` (it shares the family
`IncreasedEnergyShield` with the belt pool, so that family is told apart), Remove Crafted Mods and an essence.
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_oracle import assert_same_distribution, crafted_item, uncrafted_item
from abstraction_support import ABSENT, BELOW, PASSING, check_kernel
from items_support import DATA, item, roll

from crafting_system.abstraction import Abstraction, Goal, Slot, Wanted
from crafting_system.actions import (
    ApplyEssence,
    BenchCraft,
    ChaosOrb,
    NotApplicableError,
    OutOfScopeError,
    RemoveCraftedMods,
)
from crafting_system.items import Rarity, Side

BELT = "Metadata/Items/Belts/Belt3"
LEVEL = 86
DAMAGE = "JunMaster2AllDamage2_"  # a prefix craft, family AllDamage (not in the belt pool)
HYBRID = "JunMaster2ArmourAndEnergyShield1"  # a prefix craft, shares IncreasedEnergyShield with the pool
PREFIXES_LOCK = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix metamod
LIFE, LIFE_3, SHIELD = "IncreasedLife1", "IncreasedLife3", "IncreasedEnergyShield1"
COLD, FIRE, LIGHTNING, LIGHTNING_3, CHAOS_RES, REGEN = (
    "ColdResist1", "FireResist1", "LightningResist1", "LightningResist3", "ChaosResist2", "LifeRegeneration1",
)  # fmt: skip
HATRED = ApplyEssence("Whispering Essence of Hatred")  # level 1: normal items, forced ColdResist1, cap 35
HYSTERIA = ApplyEssence("Essence of Hysteria")  # level 8: forced ElementalPenetrationDuringFlaskEffectEssence1
HYSTERIA_MOD = "ElementalPenetrationDuringFlaskEffectEssence1"

LIFE_LEAF = Wanted(frozenset({LIFE, "IncreasedLife2", LIFE_3}))
COLD_LEAF = Wanted(frozenset({COLD}))
SHIELD_LEAF = Wanted(frozenset({SHIELD}))
HYSTERIA_LEAF = Wanted(frozenset({HYSTERIA_MOD}))
CRAFTS = (BenchCraft(DAMAGE), BenchCraft(HYBRID), RemoveCraftedMods(), HATRED, HYSTERIA)


def belt(*mods, rarity: Rarity = Rarity.RARE, **fields):
    return item(*mods, base_id=BELT, rarity=rarity, item_level=LEVEL, **fields)


def abstraction(*leaves: Wanted, actions=CRAFTS) -> Abstraction:
    return Abstraction(DATA, Goal(leaves), BELT, LEVEL, actions)


def crafted_damage(start):
    return crafted_item(DATA, start, DAMAGE)


# --- layer 1: the essences ----------------------------------------------------------------------


def test_an_essence_on_a_normal_item_makes_it_rare_and_equals_the_brute_force():
    ab = abstraction(LIFE_LEAF, COLD_LEAF)

    kernel = check_kernel(ab, belt(rarity=Rarity.NORMAL), HATRED, data=DATA, forced=COLD, cap=35)

    assert {state.flags.rarity for state in kernel} == {Rarity.RARE}
    assert all(state.status[1] is PASSING for state in kernel)  # the forced cold resistance


@pytest.mark.parametrize(
    "start",
    [
        pytest.param(lambda: belt(roll(FIRE, fractured=True)), id="fractured"),
        pytest.param(lambda: belt(roll(FIRE, fractured=True), roll(LIFE), roll(REGEN)), id="fractured_and_junk"),
        pytest.param(lambda: belt(roll(LIGHTNING, fractured=True), roll(LIFE_3), roll(COLD)), id="with_a_goal_mod"),
        pytest.param(lambda: crafted_damage(belt(roll(FIRE, fractured=True), roll(LIFE))), id="crafted_is_erased"),
    ],
)
def test_a_reforging_essence_on_a_rare_item_equals_the_brute_force(start):
    ab = abstraction(LIFE_LEAF, COLD_LEAF, HYSTERIA_LEAF)

    kernel = check_kernel(ab, start(), HYSTERIA, data=DATA, forced=HYSTERIA_MOD)

    assert all(state.status[2] is PASSING and not state.crafted for state in kernel)


def test_the_forced_mod_is_a_slot_of_its_side_and_the_draws_come_with_their_kinds():
    ab = abstraction(HYSTERIA_LEAF)
    start = ab.compress(belt(roll(FIRE, fractured=True)))

    kernel = ab.kernel(start, HYSTERIA)

    for state in kernel:
        suffixes = [slot for slot in state.slots if slot.side is Side.SUFFIX]
        assert Slot(Side.SUFFIX, "ElementalPenetrationDuringFlaskEffect", (PASSING,)) in suffixes  # the kind is the family
        assert 3 <= len(state.slots) <= 5  # 4 to 6 mods, one of them fractured
        assert state.count(Side.PREFIX) <= 3 and state.count(Side.SUFFIX) <= 2


def test_a_low_essence_caps_the_drawn_mods_and_a_rare_item_refuses_it():
    ab = abstraction(COLD_LEAF)

    with pytest.raises(NotApplicableError, match="normal item only"):
        ab.kernel(ab.compress(belt(roll(FIRE, fractured=True))), HATRED)


def test_two_fractured_families_of_one_type_share_one_essence_distribution():
    ab = abstraction(HYSTERIA_LEAF)
    fire, cold = ab.compress(belt(roll(FIRE, fractured=True))), ab.compress(belt(roll(COLD, fractured=True)))

    first, second = ab.kernel(fire, HYSTERIA), ab.kernel(cold, HYSTERIA)

    assert fire != cold and ab.signature(fire, HYSTERIA) == ab.signature(cold, HYSTERIA)
    assert ab.stats.kernels == 1 and ab.stats.hits == 1
    assert {state.slots for state in first} == {state.slots for state in second}


def test_the_two_essences_have_different_pools_so_different_signatures():
    ab = abstraction(COLD_LEAF)
    normal, rare = ab.compress(belt(rarity=Rarity.NORMAL)), ab.compress(belt(roll(FIRE, fractured=True)))

    assert ab.signature(normal, HATRED) != ab.signature(rare, HYSTERIA)


# --- layer 1: the bench ---------------------------------------------------------------------------

BENCH_STARTS = {
    "junk": lambda: belt(roll(REGEN), roll(CHAOS_RES), roll(LIFE)),
    "fractured": lambda: belt(roll(FIRE, fractured=True), roll(LIFE), roll(LIGHTNING)),
    "fractured_and_junk": lambda: belt(roll(FIRE, fractured=True), roll(REGEN), roll(LIFE_3), roll(COLD)),
    "a_full_suffix_side": lambda: belt(roll(FIRE), roll(REGEN), roll(CHAOS_RES), roll(LIFE)),
}


@pytest.mark.parametrize("name", BENCH_STARTS)
def test_a_craft_adds_a_crafted_slot_and_equals_the_deterministic_result(name):
    ab = abstraction(LIFE_LEAF, COLD_LEAF)
    start = BENCH_STARTS[name]()

    kernel = ab.kernel(ab.compress(start), BenchCraft(DAMAGE))

    assert_same_distribution(kernel, {ab.compress(crafted_damage(start)): Fraction(1)})
    (state,) = kernel
    assert state.crafted and [slot.side for slot in state.slots if slot.crafted] == [Side.PREFIX]


def test_the_crafted_slot_gives_the_goal_what_the_crafted_mod_gives():
    ab = abstraction(Wanted(frozenset({DAMAGE})), Wanted(frozenset({DAMAGE}), not_crafted=True))

    (state,) = ab.kernel(ab.compress(belt(roll(LIFE))), BenchCraft(DAMAGE))

    assert state.status == (PASSING, BELOW)


@pytest.mark.parametrize("name", ["junk", "fractured", "fractured_and_junk"])
def test_remove_crafted_mods_drops_the_crafted_slots_and_equals_the_deterministic_result(name):
    ab = abstraction(LIFE_LEAF, COLD_LEAF)
    start = crafted_damage(BENCH_STARTS[name]())

    kernel = ab.kernel(ab.compress(start), RemoveCraftedMods())

    assert_same_distribution(kernel, {ab.compress(uncrafted_item(DATA, start)): Fraction(1)})


def test_removing_the_crafted_mod_takes_its_contribution_off_the_status():
    ab = abstraction(Wanted(frozenset({DAMAGE})))
    crafted = ab.compress(crafted_damage(belt(roll(LIFE))))

    (after,) = ab.kernel(crafted, RemoveCraftedMods())

    assert crafted.status == (PASSING,) and after.status == (ABSENT,)


# --- the slots merge exactly what the enabled actions treat alike -----------------------------------


def test_junk_of_different_families_with_the_same_side_and_kind_is_one_state():
    ab = abstraction(COLD_LEAF)
    a = ab.compress(belt(roll(REGEN), roll(FIRE)))
    b = ab.compress(belt(roll(CHAOS_RES), roll(LIGHTNING_3)))

    assert a == b
    assert [slot.side for slot in a.slots] == [Side.SUFFIX, Side.SUFFIX]
    assert ab.kernel(a, BenchCraft(DAMAGE)) == ab.kernel(b, BenchCraft(DAMAGE))


def test_a_family_that_an_enabled_craft_clashes_with_is_told_apart():
    ab = abstraction(COLD_LEAF)
    life, shield = ab.compress(belt(roll(LIFE))), ab.compress(belt(roll(SHIELD)))

    assert life != shield
    assert {slot.kind for slot in life.slots} == {""} and {slot.kind for slot in shield.slots} == {"IncreasedEnergyShield"}
    assert ab.kernel(life, BenchCraft(HYBRID))  # the craft needs no family the item holds
    with pytest.raises(NotApplicableError, match="shares a family"):
        ab.kernel(shield, BenchCraft(HYBRID))


def test_the_count_per_side_decides_whether_a_craft_has_room():
    ab = abstraction(COLD_LEAF, actions=(BenchCraft(PREFIXES_LOCK),))  # a suffix metamod
    three_suffixes = belt(roll(REGEN), roll(FIRE), roll(CHAOS_RES))
    two_suffixes = belt(roll(REGEN), roll(FIRE), roll(LIFE))

    with pytest.raises(NotApplicableError, match="no free suffix slot"):
        ab.kernel(ab.compress(three_suffixes), BenchCraft(PREFIXES_LOCK))
    (after,) = ab.kernel(ab.compress(two_suffixes), BenchCraft(PREFIXES_LOCK))
    assert after.count(Side.SUFFIX) == 3 and after.crafted


def test_a_reroll_only_abstraction_keeps_no_junk_slot():
    plain = Abstraction(DATA, Goal((COLD_LEAF,)), BELT, LEVEL)

    state = plain.compress(belt(roll(REGEN), roll(FIRE), roll(LIFE)))

    assert state.slots == () and state.status == (ABSENT,)


def test_a_reroll_only_abstraction_still_keeps_a_crafted_mod():
    plain = Abstraction(DATA, Goal((COLD_LEAF,)), BELT, LEVEL)

    state = plain.compress(crafted_damage(belt(roll(REGEN))))

    assert state.crafted and len(state.slots) == 1
    assert all(not after.crafted for after in plain.kernel(state, ChaosOrb()))


def test_an_action_that_reads_the_junk_must_be_enabled():
    plain = Abstraction(DATA, Goal((COLD_LEAF,)), BELT, LEVEL)

    with pytest.raises(ValueError, match="not among the enabled actions"):
        plain.kernel(plain.compress(belt(roll(LIFE))), BenchCraft(DAMAGE))


# --- a reroll drops the crafted flag, a metamod is still refused (by the state or by the game) ------------------------------------


@pytest.mark.parametrize("action", [ChaosOrb(), HYSTERIA], ids=["chaos", "essence"])
def test_a_reroll_removes_an_ordinary_crafted_mod_and_equals_the_brute_force(action):
    ab = abstraction(LIFE_LEAF, COLD_LEAF)
    start = crafted_damage(belt(roll(FIRE, fractured=True), roll(LIFE)))
    oracle = {"forced": HYSTERIA_MOD} if action is HYSTERIA else {}

    kernel = check_kernel(ab, start, action, data=DATA, **oracle)

    assert not any(state.crafted for state in kernel)


@pytest.mark.parametrize(
    ("action", "error"), [(ChaosOrb(), OutOfScopeError), (HYSTERIA, NotApplicableError)], ids=["chaos", "essence"]
)
def test_a_metamod_still_refuses_a_reroll(action, error):
    # the compressed state does not model a lock yet (Chaos); an essence is refused by the game under it
    ab = abstraction(COLD_LEAF)
    start = belt(roll(FIRE, fractured=True), roll(PREFIXES_LOCK, crafted=True))

    with pytest.raises(error, match="metamod"):
        ab.kernel(ab.compress(start), action)


# --- refusals of the bench, with the item the state stands for ---------------------------------------


def test_a_craft_on_a_state_that_holds_a_crafted_mod_is_refused():
    ab = abstraction(COLD_LEAF)
    state = ab.compress(crafted_damage(belt(roll(LIFE))))

    with pytest.raises(NotApplicableError, match="crafted mod"):
        ab.kernel(state, BenchCraft(HYBRID))


def test_a_craft_on_a_normal_state_and_on_an_empty_rare_state_is_out_of_scope():
    ab = abstraction(COLD_LEAF)

    with pytest.raises(OutOfScopeError, match="normal"):
        ab.kernel(ab.compress(belt(rarity=Rarity.NORMAL)), BenchCraft(DAMAGE))
    with pytest.raises(OutOfScopeError, match="no mod"):
        ab.kernel(ab.compress(belt()), BenchCraft(DAMAGE))


def test_remove_crafted_mods_is_refused_without_a_crafted_mod_and_on_a_crafted_only_item():
    ab = abstraction(COLD_LEAF)

    with pytest.raises(NotApplicableError, match="no crafted mod"):
        ab.kernel(ab.compress(belt(roll(LIFE))), RemoveCraftedMods())
    with pytest.raises(OutOfScopeError, match="only crafted mods"):
        ab.kernel(ab.compress(belt(roll(DAMAGE, crafted=True))), RemoveCraftedMods())


def test_a_corrupted_state_is_refused_by_every_action():
    ab = abstraction(COLD_LEAF)
    corrupted = ab.compress(dataclasses.replace(belt(roll(LIFE), roll(FIRE, fractured=True)), corrupted=True))

    for action in (BenchCraft(DAMAGE), ChaosOrb(), HYSTERIA):
        with pytest.raises(NotApplicableError, match="corrupted"):
            ab.kernel(corrupted, action)


# --- the reachable states of a small route -----------------------------------------------------------


def test_the_states_reachable_by_an_essence_a_craft_and_a_removal_are_finite_and_every_kernel_sums_to_one():
    ab = abstraction(LIFE_LEAF, COLD_LEAF, HYSTERIA_LEAF)
    start = ab.compress(belt(roll(FIRE, fractured=True), roll(LIFE_3), roll(REGEN)))

    reached = ab.reachable([start], [HYSTERIA, BenchCraft(DAMAGE), RemoveCraftedMods()])

    assert start in reached and len(reached) > 10
    for state in reached:
        for action in (HYSTERIA, BenchCraft(DAMAGE), RemoveCraftedMods()):
            try:
                assert sum(ab.kernel(state, action).values()) == 1
            except (NotApplicableError, OutOfScopeError):
                pass


def test_two_starts_with_one_compressed_state_have_one_kernel_and_both_equal_the_brute_force():
    ab = abstraction(COLD_LEAF)
    one, other = belt(roll(FIRE, fractured=True), roll(REGEN)), belt(roll(FIRE, fractured=True), roll(CHAOS_RES))

    assert ab.compress(one) == ab.compress(other)
    first = check_kernel(ab, one, HYSTERIA, data=DATA, forced=HYSTERIA_MOD)
    second = check_kernel(ab, other, HYSTERIA, data=DATA, forced=HYSTERIA_MOD)
    assert first == second


# --- the metamods (ticket #68): only the multimod is a bench limit; the others the state does not model yet ---

MULTIMOD = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"  # a suffix metamod


def test_the_multimod_is_only_a_bench_limit_and_the_kernels_equal_the_brute_force():
    ab = abstraction(COLD_LEAF)
    start = belt(roll(REGEN, fractured=True), roll(MULTIMOD, crafted=True))

    (after,) = ab.kernel(ab.compress(start), BenchCraft(DAMAGE))
    reroll = check_kernel(ab, start, ChaosOrb(), data=DATA)

    assert len([slot for slot in after.slots if slot.crafted]) == 2  # the multimod and the craft
    assert not any(state.crafted for state in reroll)  # the reroll removes the multimod


def test_a_fractured_crafted_mod_is_a_fractured_mod_of_the_state_and_stays_through_a_reroll():
    ab = abstraction(COLD_LEAF)
    start = belt(roll(DAMAGE, crafted=True, fractured=True), roll(LIFE), roll(REGEN))

    state = ab.compress(start)
    kernel = check_kernel(ab, start, ChaosOrb(), data=DATA)

    assert len(state.fractured) == 1 and not state.crafted
    assert all(len(after.fractured) == 1 for after in kernel)


def test_a_fractured_metamod_is_refused_by_the_compressed_state_for_a_reroll():
    ab = abstraction(COLD_LEAF)
    start = belt(roll(PREFIXES_LOCK, crafted=True, fractured=True), roll(LIFE))

    ChaosOrb().outcomes(DATA, start)  # the action models it
    with pytest.raises(OutOfScopeError, match="metamod"):
        ab.kernel(ab.compress(start), ChaosOrb())
