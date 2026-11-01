"""The veils and the unveil offer in the compressed state (ticket #145, ADR-0026, ADR-0009).

The state of an item that holds a veiled placeholder is the item with a slot of the kind of the placeholder's family; a mod unveiled
from the pool is a slot of the kind `^<family>`; an unveil offer is held as the mods it shows, in the order a pick takes them. The tests
here run on the small amulet pool of `abstraction_veiled_support` (the veiled records of `veiled_support`, an ordinary mod in the family of an unveiled
one, two crafted mods in one family of which one is the craftable version of a veiled mod):

* layer 1 (ADR-0019): for every concrete item that the veiled actions reach from several starts, and every one of the actions, the kernel of the
  item's state equals the finished items of the action on the item, compressed one by one and added up exactly;
* the placeholder, the offer and the picks as states, the gating of the unveil and the picks, the offer state as a choice node;
* the two refusals of the veiled orbs on states (a veiled mod, however it came, against an ordinary mod of the same family);
* the order of the picks, the offer states counted, the pilot count against the graph, the refusal of the coarse levels.
"""

import dataclasses
from collections import deque
from fractions import Fraction

import pytest
from abstraction_pool import COLD_RESIST, DAMAGE_1, FIRE_RESIST, GEM, LIFE_1, MANA_1, RESIST_2
from abstraction_veiled_support import (
    DATA,
    OTHER_CRAFT_ARMOUR,
    PRE,
    SPEED_ORDINARY,
    SUF,
    amulet,
    closure,
    concrete_pushforward,
    holder,
    rolled,
)
from items_support import AMULET
from veiled_support import (
    ARMOUR,
    CRAFTED_ARMOUR,
    CRIT,
    HYBRID,
    MANA,
    SIGNATURE_PLACEHOLDER,
    SPEED,
    LIFE_1 as VEIL_LIFE_1,
    LIFE_2 as VEIL_LIFE_2,
)

from abstraction_pool import LEVEL
from crafting_system.abstraction import Abstraction, Coarsening, Goal, OfferedMod, Status, Wanted
from crafting_system.actions import (
    ActionError,
    AnnulmentOrb,
    BenchCraft,
    ChaosOrb,
    NotApplicableError,
    OutOfScopeError,
    Pick,
    Unveil,
    VeiledChaosOrb,
    VeiledExaltedOrb,
)
from crafting_system.items import ExplicitMod, Rarity

F = Fraction
ABSENT, BELOW, PASSING = Status.ABSENT, Status.BELOW, Status.PASSING
PICKS = (Pick(1), Pick(2), Pick(3))
GOAL_SPEED = Goal((Wanted(frozenset({SPEED})),))
GOAL_LIFE = Goal((Wanted(frozenset({VEIL_LIFE_1, VEIL_LIFE_2})),))
GOAL_LIFE_2 = Goal((Wanted(frozenset({VEIL_LIFE_2})),))
EVERY_ACTION = (VeiledChaosOrb(), VeiledExaltedOrb(), Unveil(), *PICKS, AnnulmentOrb())


def ab(goal: Goal = GOAL_SPEED, actions=EVERY_ACTION, **options) -> Abstraction:
    return Abstraction(DATA, goal, AMULET, LEVEL, actions, **options)


def fractured_veil(mod_id: str = PRE) -> ExplicitMod:
    return ExplicitMod(mod_id, 1, holder(mod_id).values, fractured=True)


# --- layer 1 -----------------------------------------------------------------------------------------


def starts():
    return {
        "veil_prefix": amulet(holder(PRE), rolled(RESIST_2)),
        "veil_suffix": amulet(holder(SUF), rolled(RESIST_2), rolled(LIFE_1)),
        "no_veil": amulet(rolled(LIFE_1), rolled(RESIST_2)),
        "ordinary_speed": amulet(holder(PRE), rolled(SPEED_ORDINARY), rolled(RESIST_2)),
        "jun_craft_and_veil": amulet(rolled(CRAFTED_ARMOUR, crafted=True), holder(PRE)),
        "other_craft": amulet(rolled(OTHER_CRAFT_ARMOUR, crafted=True), rolled(RESIST_2), rolled(LIFE_1)),
        "fractured_veil": amulet(fractured_veil(), rolled(RESIST_2)),
        "offer": amulet(holder(SUF), rolled(RESIST_2), veil_offer=(CRIT, SPEED)),
        "full_prefixes": amulet(rolled(LIFE_1), rolled(DAMAGE_1), rolled(GEM), holder(SUF)),
    }


def check_layer_1(ability: Abstraction, item, action) -> bool:
    """The kernel of `item`'s state equals the compressed finished items of `action` on `item`; where the game refuses, so does the kernel.

    An item that holds an offer is a choice node: the state allows no action there that does not read the offer. Returns whether the action applied.
    """
    state = ability.compress(item)
    if item.veil_offer and not action.reads(DATA).offer:
        with pytest.raises(NotApplicableError, match="choice node"):
            ability.kernel(state, action)
        return False
    try:
        expected = concrete_pushforward(ability, DATA, item, action)
    except ActionError as refusal:
        with pytest.raises(type(refusal)):
            ability.kernel(state, action)
        return False
    kernel = ability.kernel(state, action)
    assert dict(kernel) == expected, f"{action.label()} on {[e.mod_id for e in item.mods]}"
    assert sum(kernel.values()) == 1 and all(type(chance) is Fraction and chance > 0 for chance in kernel.values())
    return True


@pytest.mark.parametrize("goal", [GOAL_SPEED, GOAL_LIFE_2], ids=["wants_speed", "wants_life_2"])
def test_layer_1_every_veiled_action_on_every_item_they_reach_from_several_starts(goal):
    ability = ab(goal)
    cheap = [VeiledExaltedOrb(), Unveil(), *PICKS, AnnulmentOrb()]  # the veiled reroll is checked on a sample below: its closure is the whole pool
    items = closure(DATA, starts().values(), cheap)
    assert len(items) > 150
    applied = {action: 0 for action in cheap}
    for item in items:
        for action in cheap:
            applied[action] += check_layer_1(ability, item, action)
    assert all(applied.values()), applied  # every action applied somewhere, so none was only ever compared as a refusal


def test_layer_1_of_the_veiled_chaos_orb_on_items_of_every_kind_of_start():
    ability = ab()
    applied = {name: check_layer_1(ability, item, VeiledChaosOrb()) for name, item in starts().items()}
    # it is refused where a veiled mod would be kept (a fractured placeholder) and in an offer state (a choice node): both as refusals
    assert {name for name, took in applied.items() if not took} == {"fractured_veil", "offer"}


def test_layer_1_of_a_unveil_block_a_craft_taken_before_the_unveil():
    # the bench craft of the Jun mod clashes with the family of the unveiled Armour: the offer after the craft has no Armour
    ability = ab(actions=(*EVERY_ACTION, BenchCraft(CRAFTED_ARMOUR)))
    start = amulet(holder(PRE), rolled(RESIST_2))
    crafted = ability.kernel(ability.compress(start), BenchCraft(CRAFTED_ARMOUR))
    ((blocked, chance),) = crafted.items()
    assert chance == 1
    offers = ability.kernel(blocked, Unveil())
    assert {tuple(entry.mod_id for entry in state.offer) for state in offers} == {(VEIL_LIFE_1, MANA)}  # Life 2 is the same kind as Life 1, Armour is out
    item = start.add_mod(DATA, rolled(CRAFTED_ARMOUR, crafted=True))
    assert dict(offers) == concrete_pushforward(ability, DATA, item, Unveil())
    assert check_layer_1(ability, start, BenchCraft(CRAFTED_ARMOUR))


# --- the placeholder and the unveiled mods as slots -------------------------------------------------------------------------


def test_the_placeholder_is_a_slot_of_the_kind_of_its_family_and_gives_the_goal_nothing():
    ability = ab()
    for side, mod_id, kind in ((SUF, SUF, "VeiledSuffix"), (PRE, PRE, "VeiledPrefix")):
        state = ability.compress(amulet(holder(mod_id), rolled(RESIST_2)))
        veil = [slot for slot in state.slots if slot.kind == kind]
        assert len(veil) == 1 and veil[0].contribution == (ABSENT,) and not veil[0].crafted
        assert state.offer == () and state.status == (ABSENT,)
    assert ability.compress(amulet(holder(PRE))) != ability.compress(amulet(holder(SUF)))  # the side is part of the slot


def test_a_mod_unveiled_from_the_pool_is_never_the_slot_of_an_ordinary_mod_of_its_family():
    ability = ab()
    unveiled = ability.compress(amulet(rolled(SPEED), rolled(RESIST_2)))
    ordinary = ability.compress(amulet(rolled(SPEED_ORDINARY), rolled(RESIST_2)))
    assert unveiled != ordinary
    assert [slot.kind for slot in unveiled.slots if slot.kind not in ("", ) and slot.kind.startswith("^")] == ["^VeilTestSpeed"]
    assert "VeilTestSpeed" in {slot.kind for slot in ordinary.slots}
    # a state is rebuilt into an item that holds the kind of mod it stands for
    assert ability.kernel(ordinary, VeiledExaltedOrb())  # an ordinary mod is no veiled mod
    with pytest.raises(NotApplicableError, match="veiled mod"):
        ability.kernel(unveiled, VeiledExaltedOrb())  # the unveiled one is: the refusal after an unveil


def test_the_veiled_exalted_orb_refuses_a_state_by_whether_the_item_holds_a_veiled_mod_however_it_came():
    ability = ab()
    refused = {
        "placeholder": amulet(holder(PRE), rolled(RESIST_2)),
        "unveiled": amulet(rolled(VEIL_LIFE_1), rolled(RESIST_2)),
        "unveiled_hybrid": amulet(rolled(HYBRID), rolled(RESIST_2)),
        "craftable_version": amulet(rolled(CRAFTED_ARMOUR, crafted=True), rolled(RESIST_2)),
        "fractured_unveiled": amulet(rolled(VEIL_LIFE_1, fractured=True), rolled(RESIST_2)),
    }
    accepted = {
        "ordinary": amulet(rolled(SPEED_ORDINARY), rolled(RESIST_2)),
        "other_master_craft": amulet(rolled(OTHER_CRAFT_ARMOUR, crafted=True), rolled(RESIST_2)),
        "plain": amulet(rolled(LIFE_1), rolled(RESIST_2)),
    }
    for name, item in refused.items():
        with pytest.raises(NotApplicableError, match="veiled mod"):
            VeiledExaltedOrb().outcomes(DATA, item)
        with pytest.raises(NotApplicableError, match="veiled mod"):
            ability.kernel(ability.compress(item), VeiledExaltedOrb())
    for name, item in accepted.items():
        assert dict(ability.kernel(ability.compress(item), VeiledExaltedOrb())) == concrete_pushforward(ability, DATA, item, VeiledExaltedOrb()), name


def test_the_craftable_version_of_a_veiled_mod_is_not_merged_with_another_crafted_mod_of_its_family():
    ability = ab()
    jun = ability.compress(amulet(rolled(CRAFTED_ARMOUR, crafted=True), rolled(RESIST_2)))
    other = ability.compress(amulet(rolled(OTHER_CRAFT_ARMOUR, crafted=True), rolled(RESIST_2)))
    assert jun != other and ability.crafted_slot(CRAFTED_ARMOUR) != ability.crafted_slot(OTHER_CRAFT_ARMOUR)
    # without an action that looks for a veiled mod the two are one state, as they were before
    plain = ab(actions=(AnnulmentOrb(), ChaosOrb()))
    assert plain.compress(amulet(rolled(CRAFTED_ARMOUR, crafted=True), rolled(RESIST_2))) == plain.compress(
        amulet(rolled(OTHER_CRAFT_ARMOUR, crafted=True), rolled(RESIST_2))
    )


def test_a_fractured_placeholder_is_the_generic_placeholder_and_a_fractured_pick_stays_fractured():
    ability = ab(GOAL_LIFE)
    start = ability.compress(amulet(fractured_veil(), rolled(RESIST_2)))
    assert [entry.mod_id for entry in start.fractured] == [PRE]  # not the smallest id among the placeholders of the masters
    for offered in ability.kernel(start, Unveil()):
        for pick in PICKS:
            try:
                landed = ability.kernel(offered, pick)
            except NotApplicableError:
                continue
            ((state, chance),) = landed.items()
            assert chance == 1 and len(state.fractured) == 1 and state.fractured[0].mod_id.startswith("VeilTest")
            assert state.offer == () and "VeiledPrefix" not in {slot.kind for slot in state.slots}


@pytest.mark.parametrize(
    "item",
    [
        amulet(ExplicitMod(SIGNATURE_PLACEHOLDER, 1, holder(SIGNATURE_PLACEHOLDER).values), rolled(RESIST_2)),
        amulet(holder(PRE), holder(SUF)),
    ],
    ids=["signature_placeholder", "double_veil"],
)
def test_a_signature_placeholder_or_a_double_veil_is_out_of_scope_in_a_state(item):
    with pytest.raises(OutOfScopeError, match="grill B2"):
        ab().compress(item)
    ab(actions=(AnnulmentOrb(),)).compress(item)  # a model that never looks at the offer keeps it as the junk it is


# --- gating: the unveil and the picks follow the state -----------------------------------------------------------------------


def test_unveil_and_the_picks_are_gated_by_the_placeholder_and_the_offer_of_the_state():
    ability = ab()
    plain = ability.compress(amulet(rolled(LIFE_1), rolled(RESIST_2)))
    with_veil = ability.compress(amulet(holder(PRE), rolled(RESIST_2)))
    for pick in PICKS:
        with pytest.raises(NotApplicableError, match="nothing to pick"):
            ability.kernel(with_veil, pick)
    with pytest.raises(NotApplicableError, match="no veiled placeholder"):
        ability.kernel(plain, Unveil())
    offered = next(iter(ability.kernel(with_veil, Unveil())))
    assert offered.offer
    with pytest.raises(NotApplicableError, match="drawn already"):
        ability.kernel(offered, Unveil())  # drawn once, no second look
    short = ability.compress(amulet(holder(SUF), veil_offer=(CRIT, HYBRID)))
    assert ability.kernel(short, Pick(2)) and ability.kernel(short, Pick(1))
    with pytest.raises(NotApplicableError, match="no mod number 3"):
        ability.kernel(short, Pick(3))


def test_an_offer_state_is_a_choice_node_the_only_actions_there_are_the_picks():
    ability = ab()
    offered = ability.compress(amulet(holder(PRE), rolled(RESIST_2), veil_offer=(ARMOUR, VEIL_LIFE_1, MANA)))
    for refused in (VeiledChaosOrb(), VeiledExaltedOrb(), AnnulmentOrb()):
        with pytest.raises(NotApplicableError, match="choice node"):
            ability.kernel(offered, refused)
        with pytest.raises(NotApplicableError, match="choice node"):
            ability.kernel_key(offered, refused)
        with pytest.raises(NotApplicableError, match="choice node"):
            ability.signature(offered, refused)
    assert all(ability.kernel(offered, pick) for pick in PICKS)
    # after the pick the item is free again
    ((landed, _),) = ability.kernel(offered, Pick(1)).items()
    assert landed.offer == () and ability.kernel(landed, VeiledChaosOrb())


def test_a_pick_sees_a_clash_with_an_ordinary_mod_of_a_family_of_the_pool_even_when_nothing_else_is_enabled():
    # the offer was drawn before the ordinary Speed mod came on the item (a hand-made start item): the pick of the unveiled Speed is refused
    only_picks = ab(actions=PICKS)
    item = amulet(holder(SUF), rolled(SPEED_ORDINARY), veil_offer=(CRIT, SPEED))
    state = only_picks.compress(item)
    assert any(slot.kind == "VeilTestSpeed" for slot in state.slots)  # the ordinary Speed mod keeps its family
    with pytest.raises(NotApplicableError, match="shares a family"):
        Pick(2).outcomes(DATA, item)
    with pytest.raises(NotApplicableError, match="shares a family"):
        only_picks.kernel(state, Pick(2))
    assert dict(only_picks.kernel(state, Pick(1))) == concrete_pushforward(only_picks, DATA, item, Pick(1))


# --- the offer as a state --------------------------------------------------------------------------------------------------


def test_the_offers_of_a_placeholder_are_states_that_follow_what_the_goal_tells_apart():
    # the prefix pool offers Armour, one of the two Life tiers and Mana: two concrete offers (2/3 and 1/3)
    start = amulet(holder(PRE), rolled(RESIST_2))
    one = ab(GOAL_LIFE)  # the goal does not tell the Life tiers apart: one offer state
    shown = one.kernel(one.compress(start), Unveil())
    assert [tuple(entry.mod_id for entry in state.offer) for state in shown] == [(ARMOUR, VEIL_LIFE_1, MANA)] and set(shown.values()) == {1}
    two = ab(GOAL_LIFE_2)  # the second tier is what is wanted: two
    shown = two.kernel(two.compress(start), Unveil())
    assert {tuple(entry.mod_id for entry in state.offer): chance for state, chance in shown.items()} == {
        (ARMOUR, VEIL_LIFE_1, MANA): F(2, 3),
        (ARMOUR, VEIL_LIFE_2, MANA): F(1, 3),
    }
    assert {entry.contribution for state in shown for entry in state.offer if entry.mod_id.startswith("VeilTestLife")} == {(ABSENT,), (PASSING,)}


def test_a_pick_makes_the_slot_of_the_mod_it_takes_and_the_goal_sees_it():
    ability = ab(GOAL_SPEED)
    offered = ability.compress(amulet(holder(SUF), rolled(RESIST_2), veil_offer=(CRIT, SPEED)))
    assert offered.offer == (OfferedMod(CRIT, (ABSENT,)), OfferedMod(SPEED, (PASSING,)))
    ((missed, _),) = ability.kernel(offered, Pick(1)).items()
    ((hit, _),) = ability.kernel(offered, Pick(2)).items()
    assert not ability.is_goal(offered) and not ability.is_goal(missed) and ability.is_goal(hit)
    assert "^VeilTestSpeed" in {slot.kind for slot in hit.slots} and "^VeilTestCrit" in {slot.kind for slot in missed.slots}
    assert hit.offer == () and "VeiledSuffix" not in {slot.kind for slot in hit.slots}


def test_the_picks_keep_the_order_the_item_stores_the_offer_in_when_the_canonical_ids_would_reorder_it():
    # the offer's ids sort Flip M1 < Flip Z9 < Mana, but Z9 stands for the smaller A1 of its family: sorted by canonical id the state
    # would number the picks A1, M1, Mana and Pick(1) would take a different mod from the one the item gives
    flip = flip_data()
    ability = Abstraction(flip, Goal((Wanted(frozenset({MANA})),)), AMULET, LEVEL, (Unveil(), *PICKS))
    offer = ("VeilFlipH1", "VeilFlipZ9", MANA)
    item = amulet(holder(PRE, flip), rolled(RESIST_2, data=flip), veil_offer=offer, data=flip)
    assert item.veil_offer == offer
    state = ability.compress(item)
    assert tuple(entry.mod_id for entry in state.offer) == ("VeilFlipH1", "VeilFlipA1", MANA)  # in the item's order, not sorted
    other = amulet(holder(PRE, flip), rolled(RESIST_2, data=flip), veil_offer=("VeilFlipA1", "VeilFlipH1", MANA), data=flip)
    assert ability.compress(other) != state  # the same three kinds in another order: Pick(1) takes another mod
    for pick in PICKS:
        assert dict(ability.kernel(state, pick)) == concrete_pushforward(ability, flip, item, pick), pick.label()
        assert dict(ability.kernel(ability.compress(other), pick)) == concrete_pushforward(ability, flip, other, pick), pick.label()
    ((second, _),) = ability.kernel(state, Pick(2)).items()
    assert "^VeilFlipG" in {slot.kind for slot in second.slots}  # the second of the item is Z9 of the family G


def flip_data():
    from veiled_support import _mod  # a hand-written mod record of the same shape as the others

    mods = {mod.id: mod for mod in (
        _mod("VeilFlipA1", "prefix", "unveiled", ["VeilFlipG"], [("veil_flip_g", 10, 20)], 1000),
        _mod("VeilFlipZ9", "prefix", "unveiled", ["VeilFlipG"], [("veil_flip_g", 21, 30)], 1000),
        _mod("VeilFlipH1", "prefix", "unveiled", ["VeilFlipH"], [("veil_flip_h", 10, 20)], 1000),
    )}
    return dataclasses.replace(DATA, mods={**DATA.mods, **mods})


# --- the graph: sizes, the pilot count and the coarse levels ------------------------------------------------------------------


def real_graph(ability, starts_, actions):
    seen, queue, transitions = set(starts_), deque(starts_), 0
    while queue:
        state = queue.popleft()
        if ability.is_goal(state):
            continue
        for action in actions:
            try:
                kernel = ability.kernel(state, action)
            except ActionError:
                continue
            transitions += len(kernel)
            for successor in kernel:
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
    return seen, transitions


def test_the_pilot_count_of_a_veil_model_is_the_graph_the_kernels_make():
    ability = ab(GOAL_SPEED, actions=(VeiledChaosOrb(), Unveil(), *PICKS))
    start = ability.compress(amulet(rolled(LIFE_1, fractured=True), rolled(DAMAGE_1, fractured=True), rolled(GEM, fractured=True), holder(SUF)))
    actions = [VeiledChaosOrb(), Unveil(), *PICKS]

    pilot = ability.estimate([start], actions)

    seen, transitions = real_graph(ability, [start], actions)
    assert (pilot.states, pilot.transitions) == (len(seen), transitions)
    assert any(state.offer for state in seen) and any(ability.is_goal(state) for state in seen)


def test_the_offer_states_of_a_model_are_counted_by_the_placeholder_states_that_draw_them():
    ability = ab(GOAL_SPEED, actions=(VeiledChaosOrb(), Unveil(), *PICKS))
    start = ability.compress(amulet(rolled(LIFE_1, fractured=True), rolled(DAMAGE_1, fractured=True), rolled(GEM, fractured=True), holder(SUF)))
    seen, _ = real_graph(ability, [start], [VeiledChaosOrb(), Unveil(), *PICKS])
    offers = {state.offer for state in seen if state.offer}
    # a suffix offer is Speed and Crit (10/13) or Hybrid and Crit (3/13); the goal sees Speed, so the hybrid's offer is told apart from it.
    # An ordinary Speed mod that the reroll drew blocks the family: the pool is then Crit alone
    assert offers == {
        (OfferedMod(CRIT, (ABSENT,)), OfferedMod(SPEED, (PASSING,))),
        (OfferedMod(CRIT, (ABSENT,)), OfferedMod(HYBRID, (ABSENT,))),
        (OfferedMod(CRIT, (ABSENT,)),),
    }


def test_the_family_group_level_refuses_a_model_with_the_veiled_actions():
    ability = ab(GOAL_SPEED, actions=(VeiledChaosOrb(), Unveil(), *PICKS))
    with pytest.raises(OutOfScopeError):
        Coarsening.pooling_irrelevant(ability)  # no veiled action declares that its kernel is the same for every member of a block


def test_a_state_that_holds_an_offer_is_kept_by_the_free_slots_of_its_item_like_any_other():
    ability = ab(GOAL_SPEED, actions=(VeiledChaosOrb(), Unveil(), *PICKS))
    full = ability.compress(amulet(rolled(LIFE_1, fractured=True), rolled(DAMAGE_1, fractured=True), rolled(GEM, fractured=True), holder(SUF), rolled(FIRE_RESIST), rolled(COLD_RESIST)))
    assert ability.kernel(full, Unveil())  # the placeholder takes the last slot; the fixture's resistances do not block the Speed pool
    assert Rarity.RARE is full.flags.rarity
