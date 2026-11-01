"""The contract declares the implicits, the quality and the unveil offer, and a toy of each passes the contract suite (ticket #142).

"Done when": a toy implicit, quality and offer action passes `check_action` with no change to a check; layer 1 (the kernel of
`abstraction` equals the brute force on the compressed finished items) passes for a toy Ember on boots. The toys are in
`item_state_support.py`; the compressed state they run through is tested in `test_abstraction_item_state.py`.
"""

import dataclasses
from fractions import Fraction

import pytest
from contract_support import check_action, check_block_invariance
from item_state_support import (
    AILMENTS_1,
    AILMENTS_2,
    AVOID_SHOCK,
    CHANCE_TO_SHOCK,
    ITEM_DATA,
    PINNACLE_2,
    SHOCK_PROLIFERATION,
    ToyCatalyst,
    ToyConflict,
    ToyEmber,
    ToyPick,
    ToyUnveil,
    UNVEILED_LIFE,
    UNVEILED_MANA,
    amulet,
    boots,
    exarch_goal,
    intrinsic,
    roll,
    veiled,
)
from abstraction_pool import RESIST_2, LIFE_1, FIRE_RESIST

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import Action, Adds, Finite, NotApplicableError, Reads, kinds
from contract_support import GOAL

# --- the declarations ------------------------------------------------------------------------------


def test_the_declarations_default_to_leaving_the_implicits_the_quality_and_the_offer_alone():
    reads, adds = Reads(), Adds()
    assert (reads.implicits, reads.quality, reads.offer) == (False, False, False) and not reads.item_state
    assert (adds.implicits, adds.quality, adds.offer) == (False, False, False) and not adds.item_state
    for builder in (Reads.adding, Reads.nothing):
        assert not builder().item_state
    assert not Adds.removal().item_state and not Adds.rerolling().item_state and not Adds.erasing().item_state


def test_item_state_says_what_is_read_or_changed():
    assert Reads(implicits=True).item_state and Reads(quality=True).item_state and Reads(offer=True).item_state
    assert Adds(implicits=True).item_state and Adds(quality=True).item_state and Adds(offer=True).item_state


@dataclasses.dataclass(frozen=True)
class Undeclared(ToyEmber):
    """An action that declares nothing: it reads and adds everything, like it reads every mod."""

    def reads(self, data):
        return Action.reads(self, data)

    def adds(self, data=None, item=None):
        return Action.adds(self, data, item)


def test_an_action_that_declares_nothing_reads_and_adds_everything():
    reads, adds = Undeclared().reads(ITEM_DATA), Undeclared().adds(ITEM_DATA, None)
    assert (reads.junk, reads.implicits, reads.quality, reads.offer) == (True, True, True, True)
    assert (adds.implicits, adds.quality, adds.offer) == (True, True, True)


def test_no_kind_of_the_catalog_declares_item_state_yet():
    # B1 touches none of the three: the planner and the cache see no change in any registered kind
    for kind in kinds():
        for action in kind.members(ITEM_DATA, amulet(roll(RESIST_2))):
            reads, adds = action.reads(ITEM_DATA), action.adds(ITEM_DATA, None)
            assert not reads.item_state and not adds.item_state, kind.name


# --- the toys pass the contract suite -------------------------------------------------------------


EMBER_CASES = {
    "plain": lambda: boots(),
    "with_eater": lambda: boots(CHANCE_TO_SHOCK[1]),
    "replaced": lambda: boots(AVOID_SHOCK[0], CHANCE_TO_SHOCK[1]),
    "with_mods": lambda: boots(AVOID_SHOCK[2], mods=(roll(LIFE_1), roll(FIRE_RESIST))),
}


@pytest.mark.parametrize("grade", [1, 2])
@pytest.mark.parametrize("name", list(EMBER_CASES))
def test_a_toy_ember_passes_the_contract_suite_and_layer_1_on_boots(grade, name):
    assert check_action(ToyEmber(grade), EMBER_CASES[name](), ITEM_DATA)


@pytest.mark.parametrize(
    "goal",
    [
        exarch_goal(*AVOID_SHOCK),
        exarch_goal(*AVOID_SHOCK, min_grade=2),
        exarch_goal(*AVOID_SHOCK, PINNACLE_2, SHOCK_PROLIFERATION, leaves=(Wanted(frozenset({LIFE_1})),)),
    ],
    ids=["any_avoid_shock", "grade_2_up", "with_a_mod"],
)
@pytest.mark.parametrize("name", ["plain", "replaced", "with_mods"])
def test_layer_1_of_the_toy_ember_holds_for_goals_that_ask_for_an_implicit(goal, name):
    assert check_action(ToyEmber(1), EMBER_CASES[name](), ITEM_DATA, goal)
    assert check_action(ToyEmber(2), EMBER_CASES[name](), ITEM_DATA, goal)


def test_a_toy_conflict_reads_both_grades_and_passes_the_contract_suite():
    both = boots(AVOID_SHOCK[1], CHANCE_TO_SHOCK[1])
    assert check_action(ToyConflict(), both, ITEM_DATA)
    assert check_action(ToyConflict(), both, ITEM_DATA, exarch_goal(*AVOID_SHOCK, min_grade=3))
    assert check_action(ToyConflict(), boots(AVOID_SHOCK[0], CHANCE_TO_SHOCK[1]), ITEM_DATA)  # a lowered grade 1 is removed
    assert not check_action(ToyConflict(), boots(AVOID_SHOCK[1]), ITEM_DATA)  # one side only: refused


@pytest.mark.parametrize("percent", [0, 5, 10, 15, 20])
def test_a_toy_catalyst_passes_the_contract_suite(percent):
    item = amulet(roll(RESIST_2), quality=intrinsic(percent)) if percent else amulet(roll(RESIST_2))
    assert check_action(ToyCatalyst(), item, ITEM_DATA) is (percent < 20)


def test_a_toy_catalyst_restarts_a_quality_of_another_type():
    from crafting_system.items import CatalystType, Quality

    other = amulet(roll(RESIST_2), quality=Quality(CatalystType.IMBUED, 15))
    assert check_action(ToyCatalyst(), other, ITEM_DATA)


def test_a_toy_unveil_and_pick_pass_the_contract_suite():
    drawn = veiled(roll(RESIST_2), offer=(AILMENTS_1, UNVEILED_LIFE, UNVEILED_MANA))
    assert check_action(ToyUnveil(), veiled(roll(RESIST_2)), ITEM_DATA)
    assert not check_action(ToyUnveil(), drawn, ITEM_DATA)  # the offer is drawn once
    assert not check_action(ToyUnveil(), amulet(roll(RESIST_2)), ITEM_DATA)  # no placeholder
    for index in range(3):
        assert check_action(ToyPick(index), drawn, ITEM_DATA)
    assert not check_action(ToyPick(0), veiled(roll(RESIST_2)), ITEM_DATA)  # nothing to pick from


@pytest.mark.parametrize("goal", [GOAL, Goal((Wanted(frozenset({UNVEILED_LIFE, UNVEILED_MANA})), Wanted(frozenset({AILMENTS_1, AILMENTS_2}))))], ids=["fixture", "asks_unveiled"])
def test_the_pick_holds_layer_1_when_the_goal_names_the_offered_mods(goal):
    drawn = veiled(roll(RESIST_2), offer=(AILMENTS_2, UNVEILED_LIFE))
    for index in range(2):
        assert check_action(ToyPick(index), drawn, ITEM_DATA, goal)


def test_the_toys_declare_neither_block_invariance_nor_variants_so_the_coarse_state_refuses_them():
    for action in (ToyEmber(1), ToyConflict(), ToyCatalyst(), ToyUnveil(), ToyPick(0)):
        assert check_block_invariance(action, ITEM_DATA, GOAL) == 0


# --- the suite catches a wrong declaration --------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SilentEmber(ToyEmber):
    """An Ember that changes the implicits and does not say so."""

    def adds(self, data=None, item=None):
        return Adds(named=frozenset(), draws=False)


@dataclasses.dataclass(frozen=True)
class SilentCatalyst(ToyCatalyst):
    def adds(self, data=None, item=None):
        return Adds(named=frozenset(), draws=False)


@dataclasses.dataclass(frozen=True)
class SilentUnveil(ToyUnveil):
    def adds(self, data=None, item=None):
        return Adds(named=frozenset(), draws=False)


@dataclasses.dataclass(frozen=True)
class BlindConflict(ToyConflict):
    """A Conflict that says it reads no implicit although it needs both."""

    def reads(self, data):
        return Reads(junk=True, families=frozenset())


@dataclasses.dataclass(frozen=True)
class BlindQualityGate(ToyCatalyst):
    """An action that works only from 10% quality and changes nothing, yet says it reads no quality."""

    def reads(self, data):
        return Reads(junk=True, families=frozenset())

    def adds(self, data=None, item=None):
        return Adds(named=frozenset(), draws=False)

    def outcomes(self, data, item):
        if item.quality is None or item.quality.percent < 10:
            raise NotApplicableError("the toy needs 10% quality")
        return Finite(data, item, ((Fraction(1), item),))


@dataclasses.dataclass(frozen=True)
class BlindPick(ToyPick):
    def reads(self, data):
        return Reads(junk=True, families=frozenset())


def test_an_action_that_changes_the_implicits_without_adds_implicits_is_caught():
    with pytest.raises(AssertionError, match="adds.implicits"):
        check_action(SilentEmber(1), boots(AVOID_SHOCK[0]), ITEM_DATA)


def test_an_action_that_changes_the_quality_without_adds_quality_is_caught():
    with pytest.raises(AssertionError, match="adds.quality"):
        check_action(SilentCatalyst(), amulet(roll(RESIST_2)), ITEM_DATA)


def test_an_action_that_draws_the_offer_without_adds_offer_is_caught():
    with pytest.raises(AssertionError, match="adds.offer"):
        check_action(SilentUnveil(), veiled(roll(RESIST_2)), ITEM_DATA)


def test_an_action_that_needs_the_implicits_without_reads_implicits_is_caught():
    with pytest.raises(AssertionError, match="reads.implicits"):
        check_action(BlindConflict(), boots(AVOID_SHOCK[1], CHANCE_TO_SHOCK[1]), ITEM_DATA)


def test_an_action_that_depends_on_the_quality_without_reads_quality_is_caught():
    with pytest.raises(AssertionError, match="reads.quality"):
        check_action(BlindQualityGate(), amulet(roll(RESIST_2), quality=intrinsic(15)), ITEM_DATA)


def test_an_action_that_needs_the_offer_without_reads_offer_is_caught():
    with pytest.raises(AssertionError, match="reads.offer"):
        check_action(BlindPick(0), veiled(roll(RESIST_2), offer=(AILMENTS_1, UNVEILED_LIFE)), ITEM_DATA)
