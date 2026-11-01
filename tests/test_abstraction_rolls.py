"""Roll requirements on drawn mods and the rerolled values of a Divine Orb (#71), layer 1 of ADR-0019.

A requirement leaf with `min_roll` is a roll limit. The mods a reroll draws roll their values, and the exact
chance of each outcome is built (`_rolls.py`); a Divine Orb (here a toy `Rerolled` action, `ToyDivine`) rerolls
the values of the mods already on the item, so the state tells the rollable mods apart by mod id. Every kernel
is compared, exactly, with the brute force of `abstraction_rolls_oracle`, which lists every concrete item with
its values on the tiny pool (`TINY`: ranges of two to four integers).
"""

import collections
import dataclasses
import itertools
from fractions import Fraction

import pytest
from abstraction_adds_oracle import augmented, regaled
from abstraction_oracle import assert_same_distribution, compressed_distribution, guaranteed_tag
from abstraction_pool import CRAFTED, DAMAGES, GEM, LEVEL, LIFE_1, LIFE_2, LIVES, MANAS, RESIST_1, RESIST_2, RESISTS, DAMAGE_1, DAMAGE_2
from abstraction_rolls_oracle import (
    TINY,
    ToyDivine,
    ToyLuckyChaos,
    divine_items,
    finished_with_values,
    rolled,
    tiny_item,
    value_cases,
    with_new_values,
)
from items_support import AMULET

from crafting_system.abstraction import Abstraction, Coarsening, EstimateRefused, Goal, Status, Wanted, reach_bound
from crafting_system.abstraction._rolls import is_rollable, multinomial, roll_law
from crafting_system.abstraction._state import status_of
from crafting_system.abstraction._kinds import MOD_PREFIX
from crafting_system.actions import (
    Action,
    Adds,
    AugmentationOrb,
    ChaosOrb,
    ExaltedOrb,
    Finite,
    HarvestReforge,
    OutOfScopeError,
    Reads,
    RegalOrb,
)
from crafting_system.data.model import StatRange
from crafting_system.items import Rarity

PASSING, BELOW, ABSENT = Status.PASSING, Status.BELOW, Status.ABSENT
CHAOS, REFORGE, DIVINE, LUCKY_DIVINE, LUCKY_CHAOS = ChaosOrb(), HarvestReforge("lightning"), ToyDivine(), ToyDivine(lucky=True), ToyLuckyChaos()

LIFE_ROLL = Wanted(LIVES, min_roll=(3,))  # Life 1 (1..4) passes with 3 and 4, Life 2 (5..8) always
RESIST_ROLL = Wanted(RESISTS, min_roll=(2,))  # Resist 1 (1..2) passes with 2, the others always
HYBRID_ROLL = Wanted(DAMAGES, min_roll=(2, 2))  # Damage 1 (1..2, 1..2) with both 2; Damage 2 (3..4, 1..2) with the second 2
GOALS = {
    "life": Goal((LIFE_ROLL,)),
    "life_resist": Goal((LIFE_ROLL, RESIST_ROLL)),
    "hybrid": Goal((HYBRID_ROLL,)),
    "two_leaves": Goal((Wanted(LIVES, min_roll=(2,)), Wanted(LIVES, min_roll=(4,)))),
    "tier_bad": Goal((Wanted(LIVES, min_tier=1, min_roll=(7,)),)),  # Life 1 is tier 2: BELOW whatever it rolls
    "mixed": Goal((LIFE_ROLL, HYBRID_ROLL, Wanted(RESISTS))),
    "crafted": Goal((Wanted(frozenset({CRAFTED}), min_roll=(2,)), LIFE_ROLL)),
}
_FINISHED: dict = {}


def build(goal: str, *actions, metamods: bool = False) -> Abstraction:
    return Abstraction(TINY, GOALS[goal], AMULET, LEVEL, actions, metamods=metamods)


def finished(start, action, lucky: bool = False):
    tag = guaranteed_tag(action)
    key = (start, tag, lucky)
    if key not in _FINISHED:
        _FINISHED[key] = finished_with_values(TINY, start, tag, lucky=lucky)
    return _FINISHED[key]


def check_reroll(ab: Abstraction, start, action, *, lucky: bool = False):
    """The kernel of the reroll `action` on `start` equals the brute force over every item with its values."""
    kernel = ab.kernel(ab.compress(start), action)
    assert_same_distribution(kernel, compressed_distribution(finished(start, action, lucky), ab.compress))
    return kernel


def check_divine(ab: Abstraction, start, action: ToyDivine = DIVINE):
    """The kernel of the Divine Orb on `start` equals the brute force over the values of the changed mods."""
    changed = action.outcomes(TINY, start).changed
    kernel = ab.kernel(ab.compress(start), action)
    assert_same_distribution(kernel, compressed_distribution(divine_items(TINY, start, changed, action.lucky), ab.compress))
    return kernel


def passing(kernel, leaf: int) -> Fraction:
    return sum((chance for state, chance in kernel.items() if state.status[leaf] == PASSING), Fraction(0))


STARTS = {
    "empty": lambda: tiny_item(),
    "fractured_life_low": lambda: tiny_item(rolled(LIFE_1, 1, fractured=True)),
    "fractured_life_high": lambda: tiny_item(rolled(LIFE_1, 4, fractured=True)),
    "fractured_resist": lambda: tiny_item(rolled(RESIST_1, 2, fractured=True)),
    "fractured_damage": lambda: tiny_item(rolled(DAMAGE_1, 1, 2, fractured=True)),
}


# --- a roll limit on a mod that a reroll draws --------------------------------------------------------------


@pytest.mark.parametrize("start", STARTS)
@pytest.mark.parametrize("goal", GOALS.keys() - {"crafted"})
@pytest.mark.parametrize("action", [CHAOS, REFORGE], ids=["chaos", "reforge"])
def test_the_chances_of_the_rolls_of_a_drawn_mod_are_exact(goal, start, action):
    check_reroll(build(goal), STARTS[start](), action)


@pytest.mark.parametrize("start", ["empty", "fractured_life_high", "fractured_damage"])
@pytest.mark.parametrize("goal", ["life_resist", "hybrid", "two_leaves", "mixed"])
def test_the_rolls_are_exact_when_the_junk_is_kept_as_slots_by_mod(goal, start):
    """With a Divine Orb enabled the junk is kept and a rollable mod is a slot by mod id: the drawn slots carry the rolled contribution."""
    check_reroll(build(goal, DIVINE), STARTS[start](), CHAOS)


@pytest.mark.parametrize("action", [CHAOS, REFORGE], ids=["chaos", "reforge"])
def test_a_roll_limit_that_every_roll_meets_is_no_limit_at_all(action):
    """The law of the mod is one outcome: the label is the old one, so the kernel is the kernel of the goal without the limit."""
    limited = Abstraction(TINY, Goal((Wanted(LIVES, min_roll=(1,)),)), AMULET, LEVEL)
    plain = Abstraction(TINY, Goal((Wanted(LIVES),)), AMULET, LEVEL)
    assert limited.kernel(limited.compress(tiny_item()), action) == plain.kernel(plain.compress(tiny_item()), action)


def test_a_roll_limit_that_no_roll_meets_is_below_at_every_roll():
    ab = Abstraction(TINY, Goal((Wanted(LIVES, min_roll=(9,)),)), AMULET, LEVEL)
    kernel = check_reroll(ab, tiny_item(), CHAOS)
    assert {state.status for state in kernel} <= {(ABSENT,), (BELOW,)}


@pytest.mark.parametrize("goal", ["life", "hybrid", "two_leaves"])
@pytest.mark.parametrize("start", ["empty", "fractured_life_low"])
@pytest.mark.parametrize("enabled", [(), (DIVINE,)], ids=["by_label", "by_mod"])
def test_a_lucky_roll_keeps_the_better_of_two(goal, start, enabled):
    """A Sanctified Fossil's reroll (`Outcomes.rolls_lucky`): each value rolled twice, the nearer to the stat's max kept."""
    check_reroll(build(goal, *enabled), STARTS[start](), LUCKY_CHAOS, lucky=True)


def test_a_lucky_draw_passes_more_often_than_a_fair_one():
    ab = build("life")
    fair = passing(ab.kernel(ab.compress(tiny_item()), CHAOS), 0)
    lucky = passing(ab.kernel(ab.compress(tiny_item()), LUCKY_CHAOS), 0)
    assert lucky > fair


def test_the_pool_signature_tells_a_lucky_draw_from_a_fair_one():
    ab = build("life")
    state = ab.compress(tiny_item())
    assert ab.signature(state, CHAOS) != ab.signature(state, LUCKY_CHAOS)
    plain = build("hybrid")
    assert plain.signature(plain.compress(tiny_item()), CHAOS) != plain.signature(plain.compress(tiny_item()), LUCKY_CHAOS)


def test_a_goal_without_a_roll_limit_has_the_same_signature_for_a_lucky_draw():
    ab = Abstraction(TINY, Goal((Wanted(LIVES),)), AMULET, LEVEL)
    state = ab.compress(tiny_item())
    assert ab.signature(state, CHAOS) == ab.signature(state, LUCKY_CHAOS)


# --- the Divine Orb: values rerolled in place ---------------------------------------------------------------


def test_a_divine_orb_on_a_rollable_mod_below_the_roll_passes_half_the_time():
    ab = build("life", DIVINE)
    kernel = check_divine(ab, tiny_item(rolled(LIFE_1, 1)))
    assert passing(kernel, 0) == Fraction(1, 2)  # 3 and 4 of 1..4
    assert sorted(kernel.values()) == [Fraction(1, 2), Fraction(1, 2)]


def test_a_divine_orb_on_a_passing_mod_gives_the_same_chances():
    ab = build("life", DIVINE)
    below = ab.kernel(ab.compress(tiny_item(rolled(LIFE_1, 1))), DIVINE)
    above = check_divine(ab, tiny_item(rolled(LIFE_1, 4)))
    assert above == below


def test_a_lucky_divine_orb_passes_three_times_in_four():
    ab = build("life", LUCKY_DIVINE)
    kernel = check_divine(ab, tiny_item(rolled(LIFE_1, 1)), LUCKY_DIVINE)
    assert passing(kernel, 0) == Fraction(3, 4)  # one minus both rolls under 3: (2/4) squared


def test_a_hybrid_mod_needs_every_stat_and_the_stats_roll_independently():
    ab = build("hybrid", DIVINE, LUCKY_DIVINE)
    assert passing(check_divine(ab, tiny_item(rolled(DAMAGE_1, 1, 1))), 0) == Fraction(1, 4)
    assert passing(check_divine(ab, tiny_item(rolled(DAMAGE_1, 1, 1)), LUCKY_DIVINE), 0) == Fraction(9, 16)
    assert passing(check_divine(ab, tiny_item(rolled(DAMAGE_2, 3, 1))), 0) == Fraction(1, 2)  # the first stat always meets 2


def test_two_leaves_on_one_mod_share_the_one_roll():
    ab = build("two_leaves", DIVINE)
    kernel = check_divine(ab, tiny_item(rolled(LIFE_1, 1)))
    by_status = {state.status: chance for state, chance in kernel.items()}
    assert by_status == {
        (BELOW, BELOW): Fraction(1, 4),
        (PASSING, BELOW): Fraction(1, 2),
        (PASSING, PASSING): Fraction(1, 4),
    }


STATES = {
    "life_and_resist": lambda: tiny_item(rolled(LIFE_1, 1), rolled(RESIST_1, 1)),
    "life_two_tiers_of_the_family": lambda: tiny_item(rolled(LIFE_2, 5), rolled(RESIST_2, 3)),
    "fractured_life_and_resist": lambda: tiny_item(rolled(LIFE_1, 1, fractured=True), rolled(RESIST_1, 1)),
    "fractured_life_high_and_resist": lambda: tiny_item(rolled(LIFE_1, 4, fractured=True), rolled(RESIST_1, 1)),
    "damage_and_resist": lambda: tiny_item(rolled(DAMAGE_1, 1, 1), rolled(RESIST_1, 2)),
    "magic": lambda: tiny_item(rolled(LIFE_1, 1), rarity=Rarity.MAGIC),
    "one_fractured_only": lambda: tiny_item(rolled(RESIST_1, 1, fractured=True)),
}


@pytest.mark.parametrize("name", STATES)
@pytest.mark.parametrize("goal", ["life_resist", "mixed"])
@pytest.mark.parametrize("divine", [DIVINE, LUCKY_DIVINE], ids=["fair", "lucky"])
def test_the_kernel_of_the_divine_orb_is_exact(name, goal, divine):
    check_divine(build(goal, divine), STATES[name](), divine)


def test_a_fractured_mod_keeps_its_value_whatever_the_divine_orb_does():
    ab = build("life_resist", DIVINE)
    kernel = check_divine(ab, tiny_item(rolled(LIFE_1, 1, fractured=True), rolled(RESIST_1, 1)))
    assert {state.status[0] for state in kernel} == {BELOW}  # the fractured Life stays below
    assert passing(kernel, 1) == Fraction(1, 2)  # the Resistance rolls 1 or 2
    assert all(state.fractured == ab.compress(tiny_item(rolled(LIFE_1, 1, fractured=True))).fractured for state in kernel)


def test_a_mod_on_a_locked_side_keeps_its_value():
    ab = build("life_resist", DIVINE, metamods=True)
    lock = rolled(CRAFTED, 1, crafted=True)  # Suffixes Cannot Be Changed
    start = tiny_item(rolled(LIFE_1, 1), rolled(RESIST_1, 1), lock)
    changed = DIVINE.outcomes(TINY, start).changed
    assert changed == {(LIFE_1, False, False), (CRAFTED, False, True)}  # the Resistance sits on a locked side
    kernel = check_divine(ab, start)
    assert {state.status[1] for state in kernel} == {BELOW}  # the locked Resistance stays at 1
    assert passing(kernel, 0) == Fraction(1, 2)


def test_a_tier_bad_mod_of_a_rollable_family_stays_below_and_its_better_tier_rolls():
    ab = build("tier_bad", DIVINE)
    bad = check_divine(ab, tiny_item(rolled(LIFE_1, 4)))  # tier 2 of a leaf that wants tier 1: below at every roll
    assert {state.status for state in bad} == {(BELOW,)} and sum(bad.values()) == 1
    good = check_divine(ab, tiny_item(rolled(LIFE_2, 5)))
    assert passing(good, 0) == Fraction(1, 2)  # 7 and 8 of 5..8


def test_a_crafted_mod_that_a_leaf_limits_the_roll_of_is_out_of_scope():
    ab = build("crafted", DIVINE, metamods=True)
    start = tiny_item(rolled(CRAFTED, 1, crafted=True))
    with pytest.raises(OutOfScopeError, match="crafted"):
        ab.kernel(ab.compress(start), DIVINE)
    # the same item is fine when the Divine Orb is not used on it, and the reroll that erases the crafted mod too
    assert ab.kernel(ab.compress(start), CHAOS)


def test_a_divine_orb_changes_nothing_a_goal_without_a_roll_limit_can_see():
    ab = Abstraction(TINY, Goal((Wanted(LIVES), Wanted(RESISTS))), AMULET, LEVEL, [DIVINE])
    state = ab.compress(tiny_item(rolled(LIFE_1, 1), rolled(RESIST_1, 1)))
    assert dict(ab.kernel(state, DIVINE)) == {state: Fraction(1)}
    assert not ab.kind_of(TINY.mods[LIFE_1]).startswith(MOD_PREFIX)


# --- the orbs that add a mod keep the junk, and tell its families apart by weight ----------------------------

ADDS = {
    "augmentation_on_a_prefix": (AugmentationOrb(), lambda: tiny_item(rolled(LIFE_1, 1), rarity=Rarity.MAGIC)),
    "augmentation_on_a_suffix": (AugmentationOrb(), lambda: tiny_item(rolled(RESIST_1, 1), rarity=Rarity.MAGIC)),
    "regal": (RegalOrb(), lambda: tiny_item(rolled(RESIST_2, 3), rarity=Rarity.MAGIC)),
    "exalted": (ExaltedOrb(), lambda: tiny_item(rolled(LIFE_2, 5), rolled(RESIST_1, 1))),
    "exalted_on_a_fracture": (ExaltedOrb(), lambda: tiny_item(rolled(DAMAGE_1, 1, 1, fractured=True), rolled(RESIST_1, 2))),
}


@pytest.mark.parametrize("enabled", [(), (DIVINE,)], ids=["by_weight", "by_weight_and_mod"])
@pytest.mark.parametrize("goal", ["life_resist", "hybrid", "mixed"])
@pytest.mark.parametrize("name", ADDS)
def test_an_orb_that_adds_a_mod_rolls_it(name, goal, enabled):
    """The drawn mod is one slot with the contribution of its roll; the family types are told apart by the law of their mods."""
    orb, maker = ADDS[name]
    start = maker()
    ab = build(goal, orb, *enabled)
    oracle = regaled if isinstance(orb, RegalOrb) else augmented  # an Exalted Orb is one more mod on a rare item, as an Augmentation on a magic one
    expected = compressed_distribution(with_new_values(TINY, oracle(TINY, start), start), ab.compress)
    assert_same_distribution(ab.kernel(ab.compress(start), orb), expected)


# --- the law itself, against the listing of every roll --------------------------------------------------------


def listed_law(leaves, data, mod_id, lucky):
    """The law of a mod found by rolling it in every way (`value_cases`) and asking `status_of` of each."""
    law: dict = {}
    for values, chance in value_cases(data, mod_id, lucky):
        ints = tuple(int(status_of(leaf, mod_id, 1, values, False)) for leaf in leaves)
        law[ints] = law.get(ints, Fraction(0)) + chance
    return tuple(sorted(law.items()))


RANGES_UNDER_TEST = {"rising": ((1, 6),), "falling": ((6, 1),), "two_stats": ((1, 4), (4, 1)), "one_value": ((3, 3),)}
LEAVES_UNDER_TEST = {
    "one_cut": (Wanted(frozenset({"M"}), min_roll=(4,)),),
    "two_leaves": (Wanted(frozenset({"M"}), min_roll=(2,)), Wanted(frozenset({"M"}), min_roll=(5,))),
    "second_stat": (Wanted(frozenset({"M"}), min_roll=(None, 2)), Wanted(frozenset({"M"}), min_roll=(3, 3))),
    "outside": (Wanted(frozenset({"M"}), min_roll=(0,)), Wanted(frozenset({"M"}), min_roll=(9,))),
    "tier_and_roll": (Wanted(frozenset({"M"}), min_tier=1, min_roll=(3,)), Wanted(frozenset({"M"}), min_roll=(3,))),
    "another_number_of_stats": (Wanted(frozenset({"M"}), min_roll=(2, 2, 2)), Wanted(frozenset({"M"}), min_roll=(3,))),
}


@pytest.mark.parametrize("lucky", [False, True], ids=["fair", "lucky"])
@pytest.mark.parametrize("leaves", LEAVES_UNDER_TEST)
@pytest.mark.parametrize("ranges", RANGES_UNDER_TEST)
def test_the_roll_law_is_the_listing_of_every_roll(ranges, leaves, lucky):
    base = TINY.mods[LIFE_1]
    stats = tuple(StatRange(f"s{index}", low, high) for index, (low, high) in enumerate(RANGES_UNDER_TEST[ranges]))
    mod = dataclasses.replace(base, id="M", stats=stats)
    data = dataclasses.replace(TINY, mods={"M": mod})
    wanted = LEAVES_UNDER_TEST[leaves]
    law = roll_law(wanted, mod, 1, False, lucky)
    assert law == listed_law(wanted, data, "M", lucky)
    assert sum(chance for _, chance in law) == 1 and all(type(chance) is Fraction for _, chance in law)


def test_a_mod_is_rollable_when_its_law_has_more_than_one_outcome():
    assert is_rollable(roll_law((Wanted(frozenset({LIFE_1}), min_roll=(3,)),), TINY.mods[LIFE_1], 2))
    assert not is_rollable(roll_law((Wanted(frozenset({LIFE_1}), min_roll=(1,)),), TINY.mods[LIFE_1], 2))  # every roll meets it
    assert not is_rollable(roll_law((Wanted(frozenset({LIFE_1}), min_roll=(5,)),), TINY.mods[LIFE_1], 2))  # none does
    assert not is_rollable(roll_law((Wanted(frozenset({LIFE_1}), min_tier=1, min_roll=(3,)),), TINY.mods[LIFE_1], 2))  # tier 2 is below
    assert not is_rollable(roll_law((Wanted(frozenset({LIFE_2}), min_roll=(3,)),), TINY.mods[LIFE_1], 2))  # not its mod


@pytest.mark.parametrize("count", [1, 2, 3])
def test_mods_that_share_a_law_spread_over_its_outcomes_by_the_multinomial(count):
    leaves = (Wanted(frozenset({LIFE_1}), min_roll=(2,)), Wanted(frozenset({LIFE_1}), min_roll=(4,)))
    cells = roll_law(leaves, TINY.mods[LIFE_1], 2)
    listed: dict = {}
    for rolls in itertools.product(range(1, 5), repeat=count):  # every way `count` mods roll 1..4 each
        spread = frozenset(
            collections.Counter(tuple(int(status_of(leaf, LIFE_1, 2, (roll,), False)) for leaf in leaves) for roll in rolls).items()
        )
        listed[spread] = listed.get(spread, Fraction(0)) + Fraction(1, 4**count)
    assert {frozenset(spread): chance for spread, chance in multinomial(cells, count)} == listed


# --- how the mods are told apart ----------------------------------------------------------------------------


def test_with_a_divine_orb_every_mod_of_a_rollable_family_is_told_apart_by_its_id():
    ab = build("life_resist", DIVINE)
    for mod_id in (LIFE_1, LIFE_2, RESIST_1, RESIST_2, "LightningResist3"):
        assert ab.kind_of(TINY.mods[mod_id]) == MOD_PREFIX + mod_id
    assert not ab.kind_of(TINY.mods[DAMAGE_1]).startswith(MOD_PREFIX)  # no requirement limits its roll
    assert not ab.kind_of(TINY.mods[GEM]).startswith(MOD_PREFIX)


def test_without_a_divine_orb_no_mod_is_told_apart_by_its_id():
    ab = build("life_resist")
    assert not any(ab.kind_of(mod).startswith(MOD_PREFIX) for mod in TINY.mods.values())


def test_an_item_with_a_rollable_mod_compresses_to_a_slot_of_its_id_with_the_contribution_of_its_values():
    ab = build("life", DIVINE)
    low, high = (ab.compress(tiny_item(rolled(LIFE_1, value))) for value in (1, 4))
    assert [slot.kind for slot in low.slots] == [slot.kind for slot in high.slots] == [MOD_PREFIX + LIFE_1]
    assert (low.slots[0].contribution, high.slots[0].contribution) == ((BELOW,), (PASSING,))
    assert (low.status, high.status) == ((BELOW,), (PASSING,))


# --- through the graph --------------------------------------------------------------------------------------


def test_two_divine_orbs_reach_exactly_the_states_one_reaches_and_roll_again_independently():
    ab = build("life_resist", DIVINE)
    start = tiny_item(rolled(LIFE_1, 1), rolled(RESIST_1, 1))
    state = ab.compress(start)
    once = ab.kernel(state, DIVINE)
    expected = {ab.compress(item) for item, _ in divine_items(TINY, start, DIVINE.outcomes(TINY, start).changed)} | {state}
    assert ab.reachable([state], [DIVINE]) == expected
    twice: dict = {}
    for middle, chance in once.items():
        for last, each in ab.kernel(middle, DIVINE).items():
            twice[last] = twice.get(last, Fraction(0)) + chance * each
    assert twice == dict(once)  # the second roll forgets the first


def test_the_graph_of_a_reroll_and_a_divine_orb_matches_the_brute_force_two_steps():
    ab = build("life_resist", DIVINE)
    start = tiny_item(rolled(LIFE_1, 1, fractured=True))
    reached = ab.reachable([ab.compress(start)], [DIVINE, CHAOS])
    expected = {ab.compress(item) for item, _ in finished(start, CHAOS)}
    shapes = {}
    for item, _ in finished(start, CHAOS):  # the values a Divine Orb leads to do not depend on the values it starts from
        shapes.setdefault(tuple((entry.mod_id, entry.fractured, entry.crafted) for entry in item.mods), item)
    for item in shapes.values():
        expected |= {ab.compress(after) for after, _ in divine_items(TINY, item, DIVINE.outcomes(TINY, item).changed)}
    assert reached == expected | {ab.compress(start)}


def test_equal_kernel_keys_give_equal_kernels_and_the_changed_slots_are_in_the_key():
    ab = build("life_resist", DIVINE, metamods=True)
    states = [ab.compress(maker()) for maker in STATES.values()]
    by_key: dict = {}
    for state in states:
        by_key.setdefault(ab.kernel_key(state, DIVINE), []).append(ab.kernel(state, DIVINE))
    assert all(kernels.count(kernels[0]) == len(kernels) for kernels in by_key.values())
    locked = ab.compress(tiny_item(rolled(LIFE_1, 1), rolled(RESIST_1, 1), rolled(CRAFTED, 1, crafted=True)))
    open_ = ab.compress(tiny_item(rolled(LIFE_1, 1), rolled(RESIST_1, 1)))
    assert ab.kernel_key(locked, DIVINE) != ab.kernel_key(open_, DIVINE)


# --- where it stops -----------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ToyFracturingChaos(ChaosOrb):
    """A Chaos Orb that also fractures one finished mod (what a Fractured Fossil adds)."""

    def outcomes(self, data, item):
        return super().outcomes(data, item).fracturing()


def test_a_fracturing_pool_with_a_rollable_mod_is_out_of_scope():
    ab = build("life", ToyFracturingChaos())
    state = ab.compress(tiny_item())
    with pytest.raises(OutOfScopeError, match="roll"):
        ab.kernel(state, ToyFracturingChaos())
    with pytest.raises(OutOfScopeError, match="roll"):
        ab.kernel_key(state, ToyFracturingChaos())


def test_a_fracturing_pool_of_mods_that_cannot_roll_differently_still_works():
    ab = Abstraction(TINY, Goal((Wanted(MANAS, min_roll=(1,)), Wanted(RESISTS))), AMULET, LEVEL, [ToyFracturingChaos()])
    assert sum(ab.kernel(ab.compress(tiny_item()), ToyFracturingChaos()).values()) == 1


@dataclasses.dataclass(frozen=True)
class ToyCraft(Action):
    """Puts the crafted lock on the item as a fixed result, rolled at its lowest value (what a bench craft does)."""

    def label(self, data=None) -> str:
        return "Toy Craft"

    def resources(self, data=None) -> dict[str, int]:
        return {"Toy Craft Orb": 1}

    def reads(self, data) -> Reads:
        return Reads(junk=True, families=frozenset())

    def adds(self, data=None, item=None) -> Adds:
        return Adds(named=frozenset({CRAFTED}), crafted=True, draws=False)

    def outcomes(self, data, item):
        return Finite(data, item, ((Fraction(1), item.add_mod(data, rolled(CRAFTED, 1, crafted=True))),))


def test_a_new_crafted_or_fixed_result_mod_that_a_roll_limit_looks_at_is_still_out_of_scope():
    ab = build("crafted", ToyCraft(), metamods=True)
    with pytest.raises(OutOfScopeError, match="roll"):
        ab.kernel(ab.compress(tiny_item()), ToyCraft())
    plain = build("life_resist", ToyCraft(), metamods=True)  # the goal does not look at its value
    assert sum(plain.kernel(plain.compress(tiny_item()), ToyCraft()).values()) == 1


def test_the_pilot_count_the_family_groups_and_the_bound_refuse_a_divine_orb():
    ab = build("life_resist", DIVINE)
    state = ab.compress(tiny_item(rolled(LIFE_1, 1)))
    assert reach_bound(ab, state, DIVINE, [0]) is None
    with pytest.raises(EstimateRefused):
        ab.estimate([state], [DIVINE])
    with pytest.raises(OutOfScopeError):
        Coarsening(ab, [])


def test_the_bound_still_refuses_a_roll_limit_on_a_drawn_mod():
    ab = build("life")
    assert reach_bound(ab, ab.compress(tiny_item()), CHAOS, [0]) is None
