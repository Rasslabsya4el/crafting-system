"""The extra crafted slot in the limit of crafted mods (ticket #241, ADR-0053, claim `enchantment.crafted_slot_with_multimod_takes_the_larger`).

The limit is 1 with neither the enchantment "Can have 1 additional Crafted Modifier" nor the multimod, 2 with the enchantment,
3 with the multimod (itself one of them) and 3 with both: the larger, never the sum. The actions read it from the item
(`crafted_limit`); the search does not hold the enchantment in its state, so the abstraction carries it as a constant of the
problem (`Abstraction(enchantment=...)`) and the pilot count and the kernel must agree with the action on the concrete item.
"""

import dataclasses
import random
from collections import deque
from types import SimpleNamespace

import pytest
from enchant_support import ARMOUR_EXTRA_SLOT, BODY, DATA as ENCHANT_DATA, LIFE, QUALITY_LIFE, WEAPON_EXTRA_SLOT, SWORD
from items_support import AMULET

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    ActionError,
    BenchCraft,
    NotApplicableError,
    RemoveCraftedMods,
    WildBristleMatron,
    crafted_limit_of,
    grants_extra_crafted_slot,
)
from crafting_system.actions.metamods import crafted_limit
from crafting_system.cli._marking import approximate_inputs
from crafting_system.items import EnchantmentError, ExplicitMod, Item, ItemError, Metamod, Rarity
from crafting_system.rules import get_rule

MULTI = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"  # a suffix metamod
PCBC = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix metamod
LIFE_MOD, RESIST = "IncreasedLife1", "ColdResist1"
CRAFTS = ("TestCraftA", "TestCraftB", "TestCraftC")

_template_mod = ENCHANT_DATA.mods["JunMaster2AllDamage2_"]
_template_option = next(o for o in ENCHANT_DATA.bench_options if o.actions.add_explicit_mod == "JunMaster2AllDamage2_")
DATA = dataclasses.replace(
    ENCHANT_DATA,
    mods={
        **ENCHANT_DATA.mods,
        **{
            name: dataclasses.replace(
                _template_mod, id=name, type=name, families=(name,), required_level=1,
                generation_type="suffix" if name == CRAFTS[2] else "prefix",
            )
            for name in CRAFTS
        },
    },
    bench_options=(
        *ENCHANT_DATA.bench_options,
        *(
            dataclasses.replace(
                _template_option,
                item_classes=("Body Armour",),
                actions=dataclasses.replace(_template_option.actions, add_explicit_mod=name),
            )
            for name in (*CRAFTS, MULTI)
        ),
    ),
)

LIMITS = {  # (multimod held, extra slot) -> the limit
    (False, False): 1,
    (False, True): 2,
    (True, False): 3,
    (True, True): 3,
}


def roll(mod_id: str, *, crafted: bool = False) -> ExplicitMod:
    mod = DATA.mods[mod_id]
    return ExplicitMod(mod_id, 1, tuple(min(stat.min, stat.max) for stat in mod.stats), crafted=crafted)


def body(*extra, enchantment=None, multimod=False, rarity=Rarity.RARE) -> Item:
    mods = [roll(LIFE_MOD), roll(RESIST), *extra]
    if multimod:
        mods.append(roll(MULTI, crafted=True))
    return Item.build(DATA, base_id=BODY, item_level=84, rarity=rarity, mods=tuple(mods), enchantment=enchantment)


# --- the limit, on the four combinations -------------------------------------------------------------------


@pytest.mark.parametrize(("multimod", "extra"), list(LIMITS))
def test_the_limit_is_1_2_3_3_on_the_four_combinations_of_the_action_side(multimod, extra):
    held = body(enchantment=ARMOUR_EXTRA_SLOT if extra else None, multimod=multimod)

    assert crafted_limit(DATA, held) == LIMITS[(multimod, extra)]
    assert crafted_limit_of(DATA, multimod=multimod, enchantment=ARMOUR_EXTRA_SLOT if extra else None) == LIMITS[(multimod, extra)]


def test_the_table_repeats_the_rules_the_actions_already_name():
    assert crafted_limit_of(DATA, multimod=False, enchantment=None) == get_rule("bench_craft.one_crafted_mod_by_default").value
    assert crafted_limit_of(DATA, multimod=True, enchantment=None) == get_rule("metamods.multimod_raises_crafted_limit").value
    both = crafted_limit_of(DATA, multimod=True, enchantment=ARMOUR_EXTRA_SLOT)
    assert both == max(crafted_limit_of(DATA, multimod=True, enchantment=None), crafted_limit_of(DATA, multimod=False, enchantment=ARMOUR_EXTRA_SLOT))
    assert both != 4  # never the sum


def test_the_weapon_pool_extra_slot_counts_too_and_other_enchantments_do_not():
    sword = dataclasses.replace(body(), base_id=SWORD)
    assert grants_extra_crafted_slot(DATA, WEAPON_EXTRA_SLOT)
    assert grants_extra_crafted_slot(DATA, ARMOUR_EXTRA_SLOT)
    assert not grants_extra_crafted_slot(DATA, LIFE)
    assert not grants_extra_crafted_slot(DATA, QUALITY_LIFE)
    assert not grants_extra_crafted_slot(DATA, None)
    assert not grants_extra_crafted_slot(DATA, "NotAMod")
    assert crafted_limit(DATA, body(enchantment=LIFE)) == 1
    assert crafted_limit(DATA, dataclasses.replace(sword, enchantment=WEAPON_EXTRA_SLOT)) == 2


def test_removing_the_multimod_from_an_item_with_the_enchant_leaves_the_limit_2():
    held = body(roll(CRAFTS[0], crafted=True), enchantment=ARMOUR_EXTRA_SLOT, multimod=True)
    assert crafted_limit(DATA, held) == 3

    after = RemoveCraftedMods().outcomes(DATA, held).sample(random.Random(1))

    assert not after.crafted_mods
    assert Metamod.MULTIPLE_CRAFTED_MODS not in after.metamods(DATA)
    assert after.enchantment == ARMOUR_EXTRA_SLOT  # the enchantment stays
    assert crafted_limit(DATA, after) == 2
    two = BenchCraft(CRAFTS[1]).outcomes(DATA, after).sample(random.Random(1))
    three = BenchCraft(CRAFTS[2]).outcomes(DATA, two).sample(random.Random(1))
    assert len(three.crafted_mods) == 2


# --- a bench route of two crafts -----------------------------------------------------------------------------


def two_crafts(start):
    first = BenchCraft(CRAFTS[0]).outcomes(DATA, start).sample(random.Random(1))
    return BenchCraft(CRAFTS[1]).outcomes(DATA, first).sample(random.Random(1))


def test_a_bench_route_with_two_crafts_is_accepted_with_the_enchant():
    done = two_crafts(body(enchantment=ARMOUR_EXTRA_SLOT))

    assert {entry.mod_id for entry in done.crafted_mods} == {CRAFTS[0], CRAFTS[1]}
    with pytest.raises(NotApplicableError, match=r"2 crafted mods, which is the limit \(2\)"):
        BenchCraft(CRAFTS[2]).outcomes(DATA, done)


def test_the_same_route_is_refused_without_the_enchant():
    with pytest.raises(NotApplicableError, match=r"1 crafted mod, which is the limit \(1\)"):
        two_crafts(body())


def test_the_same_route_is_refused_with_an_enchant_that_gives_no_slot():
    with pytest.raises(NotApplicableError, match=r"limit \(1\)"):
        two_crafts(body(enchantment=LIFE))


def test_with_both_the_multimod_and_the_enchant_the_third_craft_fits_and_the_fourth_does_not():
    held = body(enchantment=ARMOUR_EXTRA_SLOT, multimod=True)
    first = BenchCraft(CRAFTS[0]).outcomes(DATA, held).sample(random.Random(1))
    second = BenchCraft(CRAFTS[1]).outcomes(DATA, first).sample(random.Random(1))

    with pytest.raises(NotApplicableError, match=r"3 crafted mods, which is the limit \(3\)"):
        BenchCraft(CRAFTS[2]).outcomes(DATA, second)


def test_the_beast_craft_reads_the_same_limit():
    held = body(roll(CRAFTS[0], crafted=True), enchantment=ARMOUR_EXTRA_SLOT)
    free = body(roll(CRAFTS[0], crafted=True))

    assert WildBristleMatron().outcomes(DATA, held)  # a second crafted mod fits
    with pytest.raises(NotApplicableError, match=r"limit \(1\)"):
        WildBristleMatron().outcomes(DATA, free)


# --- the search agrees with the action on the concrete item ---------------------------------------------------------


GOAL = Goal((Wanted(frozenset({"FireResist1"})),))  # a mod the start item does not hold, so the walk expands it
ACTIONS = [BenchCraft(name) for name in CRAFTS] + [BenchCraft(MULTI), RemoveCraftedMods()]


def abstraction(enchantment, actions=ACTIONS):
    return Abstraction(DATA, GOAL, BODY, 84, actions, enchantment=enchantment)


def reachable(ab, start, actions=ACTIONS):
    """The states the solver's graph holds (a goal is not expanded) and the transitions."""
    seen, queue, transitions = {start}, deque([start]), 0
    while queue:
        state = queue.popleft()
        if ab.is_goal(state):
            continue
        for action in actions:
            try:
                kernel = ab.kernel(state, action)
            except ActionError:
                continue
            transitions += len(kernel)
            for successor in kernel:
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
    return seen, transitions


def count(ab, start):
    return ab.estimate([start], ACTIONS)


@pytest.mark.parametrize("enchantment", [None, ARMOUR_EXTRA_SLOT, LIFE])
@pytest.mark.parametrize("multimod", [False, True])
def test_the_pilot_count_equals_the_real_expansion_with_and_without_the_enchant(enchantment, multimod):
    start_item = body(enchantment=enchantment, multimod=multimod, rarity=Rarity.RARE)
    ab = abstraction(enchantment)
    start = ab.compress(start_item)

    states, transitions = reachable(ab, start)
    found = count(ab, start)

    assert (found.states, found.transitions) == (len(states), transitions)
    assert found.complete


def test_the_enchant_lets_the_search_hold_two_crafts_and_a_graph_of_plain_crafts_is_larger_for_it():
    crafts = [BenchCraft(name) for name in CRAFTS]
    sizes, deepest = {}, {}
    for enchantment in (None, ARMOUR_EXTRA_SLOT):
        ab = abstraction(enchantment, crafts)
        start = ab.compress(body(enchantment=enchantment))
        states, _ = reachable(ab, start, crafts)
        sizes[enchantment] = len(states)
        deepest[enchantment] = max(sum(1 for slot in state.slots if slot.crafted) for state in states)

    assert deepest == {None: 1, ARMOUR_EXTRA_SLOT: 2}
    assert sizes[ARMOUR_EXTRA_SLOT] > sizes[None]


@pytest.mark.parametrize("enchantment", [None, ARMOUR_EXTRA_SLOT])
def test_the_kernel_and_the_action_agree_on_every_state_for_every_craft(enchantment):
    ab = abstraction(enchantment)
    start = ab.compress(body(enchantment=enchantment))
    states, _ = reachable(ab, start)

    checked = refused = 0
    for state in states:
        concrete, _ = ab._item_of(state, False)
        assert concrete.enchantment == enchantment  # what the action sees on the item the state stands for
        for action in ACTIONS:
            try:
                action.outcomes(DATA, concrete)
                on_item = True
            except NotApplicableError:
                on_item = False
            try:
                ab.kernel(state, action)
                in_search = True
            except ActionError:
                in_search = False
            assert in_search == on_item
            checked += 1
            refused += not on_item
    assert checked > 20
    assert refused > 5


def test_the_second_craft_is_legal_in_the_search_only_with_the_enchant_and_a_third_is_not():
    without = abstraction(None)
    first = next(iter(without.kernel(without.compress(body()), BenchCraft(CRAFTS[0]))))
    with pytest.raises(ActionError):
        without.kernel(first, BenchCraft(CRAFTS[1]))

    ab = abstraction(ARMOUR_EXTRA_SLOT)
    first = next(iter(ab.kernel(ab.compress(body(enchantment=ARMOUR_EXTRA_SLOT)), BenchCraft(CRAFTS[0]))))
    second = next(iter(ab.kernel(first, BenchCraft(CRAFTS[1]))))
    with pytest.raises(ActionError):
        ab.kernel(second, BenchCraft(CRAFTS[2]))


def test_a_start_item_with_the_multimod_has_the_limit_3_whether_or_not_the_enchant_is_there():
    for enchantment in (None, ARMOUR_EXTRA_SLOT):
        ab = abstraction(enchantment)
        start = ab.compress(body(enchantment=enchantment, multimod=True))
        first = next(iter(ab.kernel(start, BenchCraft(CRAFTS[0]))))
        second = next(iter(ab.kernel(first, BenchCraft(CRAFTS[1]))))  # three crafted mods now: the multimod and two
        with pytest.raises(ActionError):
            ab.kernel(second, BenchCraft(CRAFTS[2]))


def test_the_abstraction_refuses_an_item_with_another_enchantment_and_an_enchantment_that_does_not_fit_the_base():
    ab = abstraction(None)
    with pytest.raises(ValueError, match="enchantment"):
        ab.compress(body(enchantment=ARMOUR_EXTRA_SLOT))
    with pytest.raises(ValueError, match="enchantment"):
        abstraction(ARMOUR_EXTRA_SLOT).compress(body())
    with pytest.raises(ItemError):
        Abstraction(DATA, GOAL, AMULET, 84, [], enchantment=ARMOUR_EXTRA_SLOT)  # an amulet holds no enchantment
    with pytest.raises(EnchantmentError):
        Abstraction(DATA, GOAL, BODY, 84, [], enchantment=WEAPON_EXTRA_SLOT)  # a weapon enchantment on body armour


# --- the answer names the unsourced stacking rule when the start item holds the enchantment ---------------------------------


def a_plan(enchantment):
    """A stand-in for a `Plan` with a one-step policy that takes a bench craft: all `approximate_inputs` reads."""
    craft = BenchCraft(CRAFTS[0])
    step = SimpleNamespace(outcomes=(("goal", 1),))
    plan = SimpleNamespace(
        start="start",
        is_goal=lambda state: state == "goal",
        offer_of=lambda action: SimpleNamespace(offer=SimpleNamespace(action=craft)),
        abstraction=SimpleNamespace(enchantment=enchantment),
        target=SimpleNamespace(base_id=BODY),
    )
    return plan, {"start": step}


def test_a_plan_from_a_start_item_with_the_enchant_lists_the_stacking_claim_as_approximate():
    plan, policy = a_plan(ARMOUR_EXTRA_SLOT)

    listed = {entry.claim for entry in approximate_inputs(plan, policy, DATA)}

    assert listed == {"enchantment.crafted_slot_with_multimod_takes_the_larger"}


@pytest.mark.parametrize("enchantment", [None, LIFE])
def test_a_plan_without_the_extra_slot_lists_nothing_for_the_bench(enchantment):
    plan, policy = a_plan(enchantment)

    assert approximate_inputs(plan, policy, DATA) == ()
