"""The compressed state holds the implicit pair, the quality and the unveil offer when an action reads or changes them (ticket #142, ADR-0027).

The state is tested through the toys of `item_state_support.py` and through B1 actions that know nothing of the
three: they must carry them. Layer 1 of the toys against the brute force is in `test_actions_item_state.py`.
"""

import dataclasses
import itertools
from collections import deque
from fractions import Fraction

import pytest
from abstraction_pool import FIRE_RESIST, GEM, LIFE_1, RESIST_2
from contract_support import GOAL
from item_state_support import (
    AILMENTS_1,
    AILMENTS_2,
    AMULET,
    AVOID_SHOCK,
    CHANCE_TO_SHOCK,
    ITEM_DATA,
    LEVEL,
    PINNACLE_2,
    SHOCK_PROLIFERATION,
    UNVEILED_LIFE,
    UNVEILED_MANA,
    ToyCatalyst,
    ToyConflict,
    ToyEmber,
    ToyPick,
    ToyUnveil,
    amulet,
    boots,
    exarch_goal,
    intrinsic,
    roll,
    veiled,
)

from crafting_system.abstraction import (
    Abstraction,
    Coarsening,
    Goal,
    ImplicitSide,
    ImplicitWanted,
    OfferedMod,
    Status,
    Wanted,
)
from crafting_system.actions import ActionError, Adds, AnnulmentOrb, ChaosOrb, NotApplicableError, OutOfScopeError, Reads
from crafting_system.items import CatalystType, ImplicitMod, Quality

BOOTS_BASE = boots().base_id
ABSENT, BELOW, PASSING = Status.ABSENT, Status.BELOW, Status.PASSING


def ab(goal: Goal = GOAL, actions=(), base: str = AMULET, **options) -> Abstraction:
    return Abstraction(ITEM_DATA, goal, base, LEVEL, actions, **options)


def boots_ab(goal: Goal = GOAL, actions=(ToyEmber(1),), **options) -> Abstraction:
    return ab(goal, actions, BOOTS_BASE, **options)


# --- what is kept ---------------------------------------------------------------------------------


def test_a_state_keeps_none_of_the_three_unless_an_enabled_action_reads_or_changes_it():
    plain = ab(actions=[AnnulmentOrb(), ChaosOrb()])
    held = amulet(roll(RESIST_2), quality=intrinsic(10))
    state = plain.compress(held)

    assert (plain.tracks_implicits, plain.tracks_quality, plain.tracks_offer) == (False, False, False)
    assert (state.implicits, state.quality, state.offer) == ((), None, ())
    assert state == plain.compress(amulet(roll(RESIST_2)))  # the quality of the item makes no difference to a state that does not keep it
    assert "implicits" not in repr(state) and "quality" not in repr(state) and "offer" not in repr(state)


def test_the_repr_of_a_state_that_keeps_nothing_is_the_one_it_had_before():
    state = ab().compress(amulet(roll(RESIST_2)))
    assert repr(state) == (
        f"CompressedState(flags={state.flags!r}, fractured={state.fractured!r}, status={state.status!r}, slots={state.slots!r})"
    )


@pytest.mark.parametrize(
    ("action", "implicits", "quality", "offer"),
    [
        (ToyEmber(1), True, False, False),  # it changes the implicits (adds)
        (ToyConflict(), True, False, False),  # it reads and changes them
        (ToyCatalyst(), False, True, False),
        (ToyUnveil(), False, False, True),
        (ToyPick(0), False, False, True),
    ],
)
def test_what_an_enabled_action_declares_is_what_the_state_keeps(action, implicits, quality, offer):
    found = ab(actions=[action])

    assert (found.tracks_implicits, found.tracks_quality, found.tracks_offer) == (implicits, quality, offer)


def test_an_action_that_only_reads_is_enough_to_keep_a_part():
    @dataclasses.dataclass(frozen=True)
    class Reader(ToyEmber):
        def reads(self, data):
            return Reads(junk=True, families=frozenset(), quality=True)

        def adds(self, data=None, item=None):
            return super().adds(data, item).__class__(named=frozenset(), draws=False)

    found = ab(actions=[Reader()])
    assert (found.tracks_implicits, found.tracks_quality, found.tracks_offer) == (False, True, False)


def test_an_implicit_wanted_by_the_goal_makes_the_state_keep_the_pair():
    assert ab(exarch_goal(*AVOID_SHOCK)).tracks_implicits
    assert not ab(GOAL).tracks_implicits


# --- the implicit pair ----------------------------------------------------------------------------


def test_a_state_holds_the_grade_and_what_the_implicit_gives_the_goal_for_each_side():
    goal = exarch_goal(*AVOID_SHOCK, min_grade=2)
    found = boots_ab(goal)

    both = found.compress(boots(AVOID_SHOCK[0], CHANCE_TO_SHOCK[1]))
    assert both.implicits == (ImplicitSide(1, (BELOW,)), ImplicitSide(2, (ABSENT,)))  # Searing Exarch first, then Eater of Worlds
    assert found.compress(boots(AVOID_SHOCK[2])).implicits == (ImplicitSide(3, (PASSING,)), ImplicitSide(0, (ABSENT,)))
    assert found.compress(boots()).implicits == (ImplicitSide(0, (ABSENT,)), ImplicitSide(0, (ABSENT,)))


def test_two_implicits_the_goal_cannot_tell_apart_are_one_state_and_the_goal_is_met_by_one_side():
    goal = exarch_goal(AVOID_SHOCK[1])
    found = boots_ab(goal)

    same = found.compress(boots(AVOID_SHOCK[0])), found.compress(boots(SHOCK_PROLIFERATION))
    assert same[0] == same[1]  # both are a grade 1 that gives the goal nothing
    assert not found.is_goal(same[0])
    wanted = found.compress(boots(AVOID_SHOCK[1], CHANCE_TO_SHOCK[1]))
    assert found.is_goal(wanted)
    assert not found.is_goal(found.compress(boots(CHANCE_TO_SHOCK[1])))  # the Eater of Worlds side does not give it
    assert found.is_goal(found.compress(boots(PINNACLE_2))) is False  # a variant of the same family, not a mod the goal names


def test_the_goal_needs_the_explicit_mods_and_the_implicit_both():
    goal = exarch_goal(AVOID_SHOCK[1], leaves=(Wanted(frozenset({LIFE_1})),))
    found = boots_ab(goal)

    assert not found.is_goal(found.compress(boots(AVOID_SHOCK[1])))
    assert not found.is_goal(found.compress(boots(AVOID_SHOCK[0], mods=(roll(LIFE_1),))))
    assert found.is_goal(found.compress(boots(AVOID_SHOCK[1], mods=(roll(LIFE_1),))))


def test_the_kernel_of_an_ember_keeps_the_other_side_and_replaces_this_one():
    goal = exarch_goal(AVOID_SHOCK[1], AVOID_SHOCK[2])
    found = boots_ab(goal, [ToyEmber(2)])
    start = found.compress(boots(AVOID_SHOCK[0], CHANCE_TO_SHOCK[1]))

    kernel = found.kernel(start, ToyEmber(2))

    eater = ImplicitSide(2, (ABSENT,))
    assert dict(kernel) == {
        dataclasses.replace(start, implicits=(ImplicitSide(2, (PASSING,)), eater)): Fraction(1, 2),  # AvoidShock2
        dataclasses.replace(start, implicits=(ImplicitSide(2, (ABSENT,)), eater)): Fraction(1, 2),  # the Pinnacle variant: not a mod the goal names
    }


def test_a_state_is_rebuilt_into_an_item_with_the_implicits_it_stands_for():
    found = boots_ab(exarch_goal(AVOID_SHOCK[2]), [ToyConflict(), ToyEmber(1)])
    start = found.compress(boots(AVOID_SHOCK[1], CHANCE_TO_SHOCK[1]))

    kernel = found.kernel(start, ToyConflict())

    # the Exarch side raised to grade 3 (AvoidShock3, the mod wanted) and the Eater side lowered to 1; or the reverse
    assert dict(kernel) == {
        dataclasses.replace(start, implicits=(ImplicitSide(3, (PASSING,)), ImplicitSide(1, (ABSENT,)))): Fraction(1, 2),
        dataclasses.replace(start, implicits=(ImplicitSide(1, (ABSENT,)), ImplicitSide(3, (ABSENT,)))): Fraction(1, 2),
    }
    for landed in kernel:  # the states that come out are rebuilt into items again: an Ember keeps the Eater side they hold
        after = found.kernel(landed, ToyEmber(1))
        assert sum(after.values()) == 1 and {state.implicits[1] for state in after} == {landed.implicits[1]}


def test_a_base_implicit_is_refused_while_the_pair_is_kept():
    belt = ImplicitMod("StrengthImplicitBelt1", 0, (25,))
    item = dataclasses.replace(boots(), implicits=(belt,))
    with pytest.raises(OutOfScopeError, match="#158"):
        boots_ab().compress(item)
    assert ab(actions=[]).compress(amulet()).implicits == ()  # not kept, not looked at


def test_a_roll_limit_on_an_implicit_is_refused_until_ticket_158():
    goal = Goal((), (ImplicitWanted(frozenset(AVOID_SHOCK), min_roll=(35,)),))
    with pytest.raises(OutOfScopeError, match="#158"):
        ab(goal, [ToyEmber(1)], BOOTS_BASE)
    Goal((), (ImplicitWanted(frozenset(AVOID_SHOCK), min_roll=(None,)),))  # a limit that asks for nothing is not a limit
    ab(Goal((), (ImplicitWanted(frozenset(AVOID_SHOCK), min_roll=(None,)),)), [ToyEmber(1)], BOOTS_BASE)


def test_no_eldritch_mod_gives_what_a_state_asks_is_refused():
    found = boots_ab(exarch_goal(*AVOID_SHOCK, SHOCK_PROLIFERATION, PINNACLE_2, "AvoidShockEldritchImplicitUniquePresence4"))
    state = found.compress(boots())
    odd = dataclasses.replace(state, implicits=(ImplicitSide(1, (ABSENT,)), state.implicits[1]))  # every grade 1 mod of the side is named by the goal
    with pytest.raises(OutOfScopeError, match="exarch"):
        found.kernel(odd, ToyEmber(1))


# --- quality --------------------------------------------------------------------------------------


def test_a_state_holds_the_quality_as_the_item_stores_it():
    found = ab(actions=[ToyCatalyst()])

    assert found.compress(amulet(roll(RESIST_2), quality=intrinsic(15))).quality == intrinsic(15)
    assert found.compress(amulet(roll(RESIST_2))).quality is None
    assert found.compress(amulet(roll(RESIST_2), quality=intrinsic(5))) != found.compress(amulet(roll(RESIST_2), quality=intrinsic(10)))


def test_the_kernel_of_a_catalyst_changes_the_quality_and_keeps_the_mods():
    found = ab(actions=[ToyCatalyst()])
    start = found.compress(amulet(roll(RESIST_2), quality=intrinsic(10)))

    kernel = found.kernel(start, ToyCatalyst())

    assert dict(kernel) == {
        dataclasses.replace(start, quality=intrinsic(15)): Fraction(1, 2),
        dataclasses.replace(start, quality=intrinsic(20)): Fraction(1, 2),
    }
    other = Quality(CatalystType.TEMPERING, 20)
    restart = found.kernel(dataclasses.replace(start, quality=other), ToyCatalyst())
    assert {state.quality for state in restart} == {intrinsic(5), intrinsic(10)}


def test_a_b1_action_carries_the_quality_and_the_implicits_it_knows_nothing_of():
    found = ab(actions=[AnnulmentOrb(), ToyCatalyst()])
    state = found.compress(amulet(roll(RESIST_2), roll(LIFE_1), quality=intrinsic(15)))

    kernel = found.kernel(state, AnnulmentOrb())

    assert len(kernel) == 2 and {successor.quality for successor in kernel} == {intrinsic(15)}
    assert all(len(successor.slots) == 1 for successor in kernel)

    on_boots = boots_ab(actions=[AnnulmentOrb(), ToyEmber(1)])
    held = on_boots.compress(boots(AVOID_SHOCK[1], CHANCE_TO_SHOCK[1], mods=(roll(LIFE_1), roll(FIRE_RESIST))))
    after = on_boots.kernel(held, AnnulmentOrb())
    assert {successor.implicits for successor in after} == {held.implicits}


def test_a_reroll_that_reads_no_mod_keeps_the_implicits_and_the_quality_too():
    found = ab(actions=[ToyCatalyst(), ToyEmber(1)])
    state = found.compress(amulet(roll(RESIST_2), quality=intrinsic(15)))

    kernel = found.kernel(state, ChaosOrb())  # not an enabled action: it reads no mod, so it needs no slot, and it leaves the rest alone

    assert kernel and {successor.quality for successor in kernel} == {intrinsic(15)}


# --- the offer ------------------------------------------------------------------------------------


def test_a_state_holds_each_offered_mod_by_its_canonical_id_and_what_it_gives_the_goal():
    goal = Goal((Wanted(frozenset({UNVEILED_LIFE})),))
    found = ab(goal, [ToyUnveil(), ToyPick(0)])

    state = found.compress(veiled(roll(RESIST_2), offer=(UNVEILED_MANA, AILMENTS_2, UNVEILED_LIFE)))

    assert state.offer == (
        OfferedMod(AILMENTS_1, (ABSENT,)),  # Ailments 2 is the same family and gives the goal the same: one id stands for both
        OfferedMod(UNVEILED_LIFE, (PASSING,)),
        OfferedMod(UNVEILED_MANA, (ABSENT,)),
    )
    assert found.compress(veiled(roll(RESIST_2), offer=(AILMENTS_1, UNVEILED_LIFE, UNVEILED_MANA))) == state
    assert found.compress(veiled(roll(RESIST_2))).offer == ()


def test_unveil_and_pick_make_the_two_nodes_of_adr_0026():
    goal = Goal((Wanted(frozenset({UNVEILED_LIFE})),))
    actions = [ToyUnveil(), ToyPick(0), ToyPick(1), ToyPick(2)]
    found = ab(goal, actions)
    start = found.compress(veiled(roll(RESIST_2)))

    drawn = found.kernel(start, ToyUnveil())

    assert sorted(drawn.values()) == [Fraction(1, 2)] * 2
    assert {successor.offer for successor in drawn} == {
        (OfferedMod(AILMENTS_1, (ABSENT,)), OfferedMod(UNVEILED_LIFE, (PASSING,)), OfferedMod(UNVEILED_MANA, (ABSENT,))),
        (OfferedMod(AILMENTS_1, (ABSENT,)), OfferedMod(UNVEILED_LIFE, (PASSING,))),
    }
    for offered in drawn:
        assert not found.is_goal(offered)  # an offer is not the mod
        with pytest.raises(ActionError):
            found.kernel(offered, ToyUnveil())  # drawn once
        picked = found.kernel(offered, ToyPick(1))  # the second of the offer in id order: Life
        ((landed, chance),) = picked.items()
        assert chance == 1 and landed.offer == () and found.is_goal(landed)
        assert all(slot.kind != "VeiledPrefix" for slot in landed.slots)
    with pytest.raises(ActionError):
        found.kernel(start, ToyPick(0))  # no offer yet


def test_an_action_that_erases_the_junk_erases_the_placeholder():
    found = ab(actions=[ToyUnveil(), ToyPick(0)])
    state = found.compress(veiled(roll(RESIST_2)))
    assert any(slot.kind == "VeiledPrefix" for slot in state.slots)

    kernel = found.kernel(state, ChaosOrb())

    assert kernel and all(successor.offer == () and all(slot.kind != "VeiledPrefix" for slot in successor.slots) for successor in kernel)


def test_an_offer_state_is_a_choice_node_only_an_action_that_reads_the_offer_is_taken_there():
    found = ab(actions=[ToyUnveil(), ToyPick(0), ToyPick(1), AnnulmentOrb()])
    state = found.compress(veiled(roll(RESIST_2), offer=(AILMENTS_1, UNVEILED_LIFE)))
    assert state.offer

    for refused in (ChaosOrb(), AnnulmentOrb()):  # nothing but a pick leaves an offer state (ADR-0026)
        with pytest.raises(NotApplicableError, match="choice node"):
            found.kernel(state, refused)
        with pytest.raises(NotApplicableError, match="choice node"):
            found.kernel_key(state, refused)
    assert found.kernel(state, ToyPick(1)) and found.kernel(state, ToyPick(0))


def test_an_action_that_reads_the_offer_must_read_the_junk():
    @dataclasses.dataclass(frozen=True)
    class Blind(ToyUnveil):
        def reads(self, data):
            return Reads(junk=False, offer=True)

    with pytest.raises(ValueError, match="placeholder"):
        ab(actions=[Blind()])


def test_an_action_that_reads_item_state_must_be_enabled():
    found = ab(actions=[ToyUnveil()])
    with pytest.raises(ValueError, match="not among the enabled actions"):
        found.kernel(found.compress(veiled(roll(RESIST_2))), ToyPick(0))


# --- the kernel keys and the memos of the pilot ---------------------------------------------------


def test_the_key_of_a_kernel_tells_states_that_differ_in_the_item_state_apart():
    found = boots_ab(actions=[ToyEmber(1), ToyConflict()])
    a = found.compress(boots(AVOID_SHOCK[0], CHANCE_TO_SHOCK[1]))
    b = found.compress(boots(AVOID_SHOCK[0], CHANCE_TO_SHOCK[0]))
    c = found.compress(boots(AVOID_SHOCK[0]))

    assert found.kernel_key(a, ToyEmber(1)) != found.kernel_key(b, ToyEmber(1))  # the Eater grade is kept
    assert found.kernel_key(a, ToyEmber(1)) != found.kernel_key(c, ToyEmber(1))
    assert found.kernel_key(a, ToyEmber(1)) == found.kernel_key(a, ToyEmber(1))


def _real_graph(found, starts, actions):
    seen, queue, transitions = set(starts), deque(starts), 0
    while queue:
        state = queue.popleft()
        if found.is_goal(state):
            continue
        for action in actions:
            try:
                kernel = found.kernel(state, action)
            except ActionError:
                continue
            transitions += len(kernel)
            for successor in kernel:
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
    return len(seen), transitions


@dataclasses.dataclass(frozen=True)
class KeepsCrafted(ChaosOrb):
    """A Chaos Orb that declares it keeps crafted mods: the pilot then keys its kernel by the crafted slots (the second branch of its key)."""

    def adds(self, data=None, item=None) -> Adds:
        return Adds(named=frozenset(), single_draw=True)


@pytest.mark.parametrize(
    ("reroll", "options"),
    [(ChaosOrb(), {}), (KeepsCrafted(), {}), (ChaosOrb(), {"metamods": True})],
    ids=["erases_crafted", "keeps_crafted", "models_metamods"],
)
def test_the_pilot_count_tells_states_apart_by_the_item_state_a_reroll_carries(reroll, options):
    """The three branches of the pilot's memo key for a reroll: states that differ only in the quality are not merged."""
    goal = Goal((Wanted(frozenset({GEM})),))
    found = ab(goal, [ToyCatalyst()], **options)
    starts = [found.compress(amulet(quality=intrinsic(percent))) for percent in (5, 10)]
    actions = [reroll, ToyCatalyst()]

    ticks = itertools.count()
    pilot = found.estimate(starts, actions, clock=lambda: float(next(ticks)))

    assert (pilot.states, pilot.transitions) == _real_graph(found, starts, actions)
    assert {state.quality for state in found.reachable(starts, actions)} >= {intrinsic(5), intrinsic(10), intrinsic(20)}


@dataclasses.dataclass(frozen=True)
class QualityChaos(ChaosOrb):
    """A Chaos Orb that says it reads the quality (an erasing reroll that does, so it is enabled): the family-group level keeps its block-invariance."""

    def reads(self, data) -> Reads:
        return dataclasses.replace(super().reads(data), quality=True)


def test_the_family_group_level_keeps_the_item_state_of_the_block_a_reroll_is_run_on():
    found = ab(GOAL, [QualityChaos()])
    assert found.tracks_quality
    coarse = Coarsening.pooling_irrelevant(found)
    low_quality = found.compress(amulet(roll(RESIST_2), quality=intrinsic(5)))
    high_quality = found.compress(amulet(roll(RESIST_2), quality=intrinsic(10)))

    for bound in ("lower", "upper"):
        for state in (low_quality, high_quality, low_quality):  # the second block must not get the cached result of the first
            kernel = coarse.kernel(coarse.coarsen(state), QualityChaos(), bound)
            assert kernel and {successor.quality for successor in kernel} == {state.quality}


def test_the_pilot_does_not_count_an_action_that_touches_the_item_state_as_a_closed_form_craft():
    from crafting_system.abstraction._estimate import _shape

    @dataclasses.dataclass(frozen=True)
    class CraftThatSetsQuality(ToyCatalyst):
        def reads(self, data):
            return Reads(junk=True, families=frozenset())

        def adds(self, data=None, item=None):
            return Adds(named=frozenset({"EinharMasterWeaponElementalDamage1_"}), crafted=True, draws=False, quality=True)

    @dataclasses.dataclass(frozen=True)
    class PlainCraft(CraftThatSetsQuality):
        def adds(self, data=None, item=None):
            return Adds(named=frozenset({"EinharMasterWeaponElementalDamage1_"}), crafted=True, draws=False)

    assert _shape(ITEM_DATA, PlainCraft()) == "craft"
    assert _shape(ITEM_DATA, CraftThatSetsQuality()) == "walked"
    assert _shape(ITEM_DATA, ToyCatalyst()) == "walked"


def test_the_pruning_by_bound_cuts_at_an_action_that_reads_the_item_state():
    from crafting_system.cli._bound_prune import REROLL, TERMINAL, _kind_of
    from crafting_system.cli._offers import Offer, PricedOffer

    def kind(action):
        return _kind_of(ITEM_DATA, amulet(roll(RESIST_2)), PricedOffer(Offer(action.label(), action, {}), 1.0, ()))[0]

    assert kind(ChaosOrb()) == REROLL
    assert kind(QualityChaos()) == TERMINAL  # an erasing reroll whose result depends on the quality: the chance read at one state does not hold at another
