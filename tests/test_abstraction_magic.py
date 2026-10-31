"""Compressed state and kernels for the magic-item orbs on the fixture belt (ticket #65, verification layer 1).

The belt has seven families: two prefix (Life with three mods, Energy Shield with one) and five
suffix (Life Regeneration, Fire, Cold, Lightning with eight mods, Chaos at a quarter of the weight).
Every kernel is checked against the brute force of `abstraction_adds_oracle.py`: all the finished
items of the orb on a concrete item, compressed one by one with the same `compress` and added up, in
exact fractions. The orbs are Transmutation, Alteration, Augmentation, Regal, Alchemy and Scouring.

An add keeps the junk, so its families count by the weight they take out of the pool: Fire, Cold and
Life Regeneration (one mod of weight 1000 each, nothing asked of them) are one family type.
"""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

import pytest
from abstraction_adds_oracle import altered, augmented, regaled, scoured, transmuted
from abstraction_oracle import assert_same_distribution, compressed_distribution, crafted_item, finished_items
from abstraction_support import PASSING
from items_support import DATA, item, roll

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    AlchemyOrb,
    AlterationOrb,
    AugmentationOrb,
    BenchCraft,
    ChaosOrb,
    NotApplicableError,
    Reads,
    RegalOrb,
    RemoveCraftedMods,
    ScouringOrb,
    TransmutationOrb,
)
from crafting_system.items import Rarity, Side

BELT = "Metadata/Items/Belts/Belt3"
LEVEL = 86
DAMAGE = "JunMaster2AllDamage2_"
LIFE, LIFE_2, SHIELD, REGEN = "IncreasedLife1", "IncreasedLife2", "IncreasedEnergyShield1", "LifeRegeneration1"
FIRE, COLD, LIGHTNING, LIGHTNING_8, CHAOS_RES = "FireResist1", "ColdResist1", "LightningResist1", "LightningResist8", "ChaosResist1"

LIFE_LEAF = Wanted(frozenset({LIFE, LIFE_2, "IncreasedLife3"}))
COLD_LEAF = Wanted(frozenset({COLD}))
LIGHTNING_LEAF = Wanted(frozenset({LIGHTNING_8}), min_tier=1)
ORBS = (TransmutationOrb(), AlterationOrb(), AugmentationOrb(), RegalOrb(), AlchemyOrb(), ScouringOrb())


def belt(*mods, rarity: Rarity = Rarity.MAGIC, **fields):
    return item(*mods, base_id=BELT, rarity=rarity, item_level=LEVEL, **fields)


def abstraction(*leaves: Wanted, actions=ORBS) -> Abstraction:
    return Abstraction(DATA, Goal(leaves or (LIFE_LEAF, COLD_LEAF)), BELT, LEVEL, actions)


def check(ab: Abstraction, start, action, finished):
    """Assert that the kernel of `start` equals the brute force `finished` (concrete items with their chances), and return it."""
    kernel = ab.kernel(ab.compress(start), action)
    assert_same_distribution(kernel, compressed_distribution(finished, ab.compress))
    assert sum(kernel.values()) == 1
    return kernel


@dataclass(frozen=True)
class ExactAugmentation(AugmentationOrb):
    """An Augmentation that declares nothing: every family of the junk is told apart (the default of the contract)."""

    def reads(self, data):
        return Reads()


@dataclass(frozen=True)
class ExactRegal(RegalOrb):
    def reads(self, data):
        return Reads()


GOALS = {
    "life_cold": (LIFE_LEAF, COLD_LEAF),
    "life_lightning_tier": (LIFE_LEAF, LIGHTNING_LEAF),
    "cold_only": (COLD_LEAF,),
}


# --- layer 1: Transmutation and Alteration --------------------------------------------------------


@pytest.mark.parametrize("goal", GOALS)
def test_transmutation_equals_the_brute_force(goal):
    ab = abstraction(*GOALS[goal])
    start = belt(rarity=Rarity.NORMAL)

    kernel = check(ab, start, TransmutationOrb(), transmuted(DATA, start))

    assert {state.flags.rarity for state in kernel} == {Rarity.MAGIC}
    assert all(1 <= len(state.slots) <= 2 for state in kernel)


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize(
    "mods",
    [
        pytest.param((roll(LIFE),), id="prefix"),
        pytest.param((roll(FIRE),), id="suffix"),
        pytest.param((roll(LIFE), roll(COLD)), id="two_mods"),
        pytest.param((roll(FIRE, fractured=True),), id="fractured_suffix"),
        pytest.param((roll(LIFE, fractured=True), roll(COLD)), id="fractured_and_junk"),
        pytest.param((roll(LIFE, fractured=True), roll(COLD, fractured=True)), id="two_fractured"),
    ],
)
def test_alteration_equals_the_brute_force(goal, mods):
    ab = abstraction(*GOALS[goal])
    start = belt(*mods)

    check(ab, start, AlterationOrb(), altered(DATA, start))


def test_alteration_removes_a_crafted_mod_and_keeps_a_fractured_one():
    ab = abstraction()
    start = crafted_item(DATA, belt(roll(COLD, fractured=True)), DAMAGE)

    kernel = check(ab, start, AlterationOrb(), altered(DATA, start))

    assert all(not state.crafted for state in kernel) and all(len(state.fractured) == 1 for state in kernel)


def test_alteration_on_a_magic_item_with_two_fractured_mods_changes_nothing():
    ab = abstraction()
    start = belt(roll(LIFE, fractured=True), roll(COLD, fractured=True))

    (state,) = check(ab, start, AlterationOrb(), altered(DATA, start))

    assert state == ab.compress(start)


# --- layer 1: Augmentation and Regal ---------------------------------------------------------------


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize(
    "mods",
    [
        pytest.param((roll(LIFE),), id="prefix_opens_the_suffix_side"),
        pytest.param((roll(SHIELD),), id="other_prefix"),
        pytest.param((roll(FIRE),), id="suffix_opens_the_prefix_side"),
        pytest.param((roll(LIGHTNING_8),), id="lightning"),
        pytest.param((roll(CHAOS_RES),), id="chaos_resistance"),
        pytest.param((roll(FIRE, fractured=True),), id="fractured"),
        pytest.param((), id="no_mod"),
    ],
)
def test_augmentation_equals_the_brute_force(goal, mods):
    ab = abstraction(*GOALS[goal])
    start = belt(*mods)

    kernel = check(ab, start, AugmentationOrb(), augmented(DATA, start))

    assert {state.flags.rarity for state in kernel} == {Rarity.MAGIC}


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize(
    "mods",
    [
        pytest.param((roll(LIFE),), id="one_prefix"),
        pytest.param((roll(FIRE),), id="one_suffix"),
        pytest.param((roll(LIFE), roll(FIRE)), id="two_mods"),
        pytest.param((roll(SHIELD), roll(LIGHTNING)), id="two_mods_other_types"),
        pytest.param((roll(LIFE), roll(CHAOS_RES)), id="chaos_resistance"),
        pytest.param((roll(COLD, fractured=True), roll(LIFE)), id="fractured_and_junk"),
        pytest.param((roll(FIRE, fractured=True),), id="fractured"),
        pytest.param((), id="no_mod"),
    ],
)
def test_regal_equals_the_brute_force(goal, mods):
    ab = abstraction(*GOALS[goal])
    start = belt(*mods)

    kernel = check(ab, start, RegalOrb(), regaled(DATA, start))

    assert {state.flags.rarity for state in kernel} == {Rarity.RARE}


@pytest.mark.parametrize(("action", "oracle"), [(AugmentationOrb(), augmented), (RegalOrb(), regaled)])
def test_an_add_keeps_a_crafted_mod(action, oracle):
    ab = abstraction()
    start = crafted_item(DATA, belt(), DAMAGE)  # a crafted prefix: the suffix side is open

    kernel = check(ab, start, action, oracle(DATA, start))

    assert all(state.crafted for state in kernel)


def test_augmentation_on_a_full_magic_item_is_refused_and_consumes_nothing():
    ab = abstraction()

    with pytest.raises(NotApplicableError, match="open prefix or suffix slot"):
        ab.kernel(ab.compress(belt(roll(LIFE), roll(COLD))), AugmentationOrb())


def test_regal_on_a_full_magic_item_opens_the_rare_capacity():
    ab = abstraction()
    start = belt(roll(LIFE, fractured=True), roll(FIRE, fractured=True))

    kernel = check(ab, start, RegalOrb(), regaled(DATA, start))

    assert {state.flags.rarity for state in kernel} == {Rarity.RARE}


# --- layer 1: Alchemy and Scouring -----------------------------------------------------------------


@pytest.mark.parametrize("goal", GOALS)
def test_alchemy_equals_the_brute_force(goal):
    ab = abstraction(*GOALS[goal])
    start = belt(rarity=Rarity.NORMAL)

    kernel = check(ab, start, AlchemyOrb(), finished_items(DATA, start))

    assert {state.flags.rarity for state in kernel} == {Rarity.RARE}
    assert all(4 <= len(state.slots) <= 5 for state in kernel)  # two prefix families, so a side holds two mods at most


@pytest.mark.parametrize(
    ("mods", "rarity", "left"),
    [
        pytest.param((roll(LIFE), roll(FIRE)), Rarity.MAGIC, 0, id="magic_to_normal"),
        pytest.param((roll(LIFE), roll(FIRE, fractured=True)), Rarity.MAGIC, 1, id="magic_keeps_fractured"),
        pytest.param((roll(LIFE, fractured=True), roll(FIRE, fractured=True)), Rarity.MAGIC, 2, id="magic_two_fractured_stay_rare"),
        pytest.param((roll(LIFE), roll(COLD), roll(FIRE), roll(REGEN)), Rarity.RARE, 0, id="rare_to_normal"),
        pytest.param((roll(LIFE), roll(COLD, fractured=True), roll(FIRE)), Rarity.RARE, 1, id="rare_to_magic"),
        pytest.param((roll(LIFE, fractured=True), roll(COLD, fractured=True), roll(FIRE)), Rarity.RARE, 2, id="rare_stays_rare"),
    ],
)
def test_scouring_equals_the_deterministic_result(mods, rarity, left):
    ab = abstraction()
    start = belt(*mods, rarity=rarity)

    (state,) = check(ab, start, ScouringOrb(), scoured(DATA, start))

    assert len(state.fractured) == left and state.slots == ()
    assert state.flags.rarity is (Rarity.NORMAL if left == 0 else Rarity.MAGIC if left == 1 else Rarity.RARE)


def test_scouring_drops_a_crafted_mod_and_keeps_the_influences():
    ab = abstraction()
    start = crafted_item(DATA, belt(roll(COLD, fractured=True)), DAMAGE)

    (state,) = check(ab, start, ScouringOrb(), scoured(DATA, start))

    assert not state.crafted and state.flags.rarity is Rarity.MAGIC


def test_scouring_refuses_a_normal_item():
    ab = abstraction()

    with pytest.raises(NotApplicableError, match="normal"):
        ab.kernel(ab.compress(belt(rarity=Rarity.NORMAL)), ScouringOrb())


# --- the state: family types ----------------------------------------------------------------------


def test_junk_of_one_family_type_is_one_state_and_other_types_stay_apart():
    ab = abstraction(LIFE_LEAF)
    fire, cold, regen = (ab.compress(belt(roll(mod))) for mod in (FIRE, COLD, REGEN))
    chaos, lightning, shield = (ab.compress(belt(roll(mod))) for mod in (CHAOS_RES, LIGHTNING, SHIELD))

    assert fire == cold == regen  # a suffix of weight 1000 that no leaf asks for
    assert len({fire, chaos, lightning}) == 3  # a lighter family and a family of eight mods are other types
    assert ab.compress(belt(roll(LIFE))).slots != shield.slots  # a prefix the goal asks for is its own type
    assert fire.slots[0].side is Side.SUFFIX and fire.slots[0].kind.startswith("~")


def test_two_junk_families_of_one_type_share_the_kernel_of_an_add():
    ab = abstraction(LIFE_LEAF)
    fire, cold = belt(roll(FIRE)), belt(roll(COLD))

    first, second = ab.kernel(ab.compress(fire), AugmentationOrb()), ab.kernel(ab.compress(cold), AugmentationOrb())

    assert first == second
    assert ab.signature(ab.compress(fire), AugmentationOrb()) == ab.signature(ab.compress(cold), AugmentationOrb())
    assert ab.stats.kernels == 1 and ab.stats.hits >= 1


def test_the_cache_is_shared_between_an_add_and_the_same_pool_of_a_chaos_orb():
    ab = abstraction(LIFE_LEAF, actions=(AugmentationOrb(), ChaosOrb(), RemoveCraftedMods()))
    start = ab.compress(belt(roll(LIFE), roll(FIRE, fractured=True), rarity=Rarity.RARE))

    ab.kernel(start, ChaosOrb())
    ab.kernel(start, ChaosOrb())

    assert ab.stats.kernels == 1 and ab.stats.hits == 1


def test_the_family_types_cut_the_reachable_states_and_keep_the_answer():
    exact = (TransmutationOrb(), AlterationOrb(), ExactAugmentation(), ExactRegal(), AlchemyOrb(), ScouringOrb())
    coarse, fine = abstraction(), abstraction(actions=exact)
    start = belt(rarity=Rarity.NORMAL)

    few = coarse.reachable([coarse.compress(start)], ORBS)
    many = fine.reachable([fine.compress(start)], exact)

    assert len(few) < len(many)
    assert any(state.flags.rarity is Rarity.RARE and len(state.slots) == 5 for state in few)

    def shape(state):
        return state.flags.rarity, state.status, state.count(Side.PREFIX), state.count(Side.SUFFIX), len(state.fractured)

    def shaped(ab, state, action):
        result = defaultdict(Fraction)
        for after, chance in ab.kernel(state, action).items():
            result[shape(after)] += chance
        return dict(result)

    for state in few:
        for action, twin in ((AugmentationOrb(), ExactAugmentation()), (RegalOrb(), ExactRegal())):
            try:
                coarse_result = shaped(coarse, state, action)
            except NotApplicableError:
                continue
            concrete = coarse._item_of(state, erasing=False)[0]  # the representative item the kernel runs on
            assert coarse_result == shaped(fine, fine.compress(concrete), twin), (state, action)


def test_a_bench_craft_and_an_add_together_tell_apart_only_the_family_of_the_craft():
    craft = BenchCraft("JunMaster2ArmourAndEnergyShield1")  # shares the family IncreasedEnergyShield with the pool
    ab = abstraction(LIFE_LEAF, actions=(AugmentationOrb(), craft, RemoveCraftedMods()))
    shield, life = ab.compress(belt(roll(SHIELD))), ab.compress(belt(roll(LIFE)))
    fire, cold = ab.compress(belt(roll(FIRE))), ab.compress(belt(roll(COLD)))

    assert shield.slots[0].kind == "IncreasedEnergyShield" and life.slots[0].kind.startswith("~")
    assert fire == cold


@pytest.mark.parametrize("action", [AugmentationOrb(), RegalOrb()])
def test_an_add_with_the_goal_mod_drawn_gives_it_to_the_status(action):
    ab = abstraction(COLD_LEAF)
    start = belt(roll(LIFE), rarity=Rarity.MAGIC)

    kernel = ab.kernel(ab.compress(start), action)

    hit = sum((chance for state, chance in kernel.items() if state.status[0] is PASSING), Fraction(0))
    open_pool = Fraction(3 * 1000 + 8 * 1000 + 6 * 250)  # the suffix side: Life Regeneration, Fire, Cold, Lightning, Chaos
    if action == RegalOrb():
        open_pool += 1000  # the rare item opens the prefix side too: Energy Shield (Life is on the item)
    assert hit == Fraction(1000) / open_pool


def test_a_chaos_orb_still_equals_the_brute_force_while_the_add_orbs_are_enabled():
    from abstraction_support import check_kernel

    ab = abstraction(actions=(*ORBS, ChaosOrb()))
    start = belt(roll(FIRE, fractured=True), roll(LIFE), roll(COLD), roll(SHIELD), rarity=Rarity.RARE)

    kernel = check_kernel(ab, start, ChaosOrb(), data=DATA)

    assert all(state.flags.rarity is Rarity.RARE and len(state.fractured) == 1 for state in kernel)
