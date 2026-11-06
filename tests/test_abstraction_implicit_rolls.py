"""The roll of an implicit in the compressed state: implicit roll status per requirement (ticket #158, ADR-0027, ADR-0019).

A requirement on an implicit (`ImplicitWanted`) may carry a roll limit and may name an implicit of the base (grade 0) as well as an Eldritch one.
The state holds, for every implicit it keeps, what the implicit gives each requirement, the roll included; an action that rolls an implicit
afresh (a Blessed Orb: every ranged implicit of the base; an Ember, an Ichor, an Orb of Conflict: the implicit it puts on) leaves a
state per outcome of the roll, with the exact chance of each. Checked here:

* layer 1 (ADR-0019) against an oracle that lists every integer value the roll can take, one finished item each, with no roll law
  (`abstraction_b2_support.rolled`): the Blessed Orb on a belt (one stat) and on a ring (two stats, two correlated requirements), on items that
  store the implicit and on items that do not; the Embers, the Ichors, the Orb of Conflict and the Blessed Orb together on boots that hold
  a base implicit, for goals with roll limits on an Eldritch implicit and on the base implicit;
* the exact chances of the roll, written down by hand;
* a requirement that names an implicit nobody rolls, and one that no roll can fail, make no state apart;
* a state is rebuilt into an item that holds the roll it stands for.
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_b2_support import check_layer_1, closure
from eldritch_support import BASE_IMPLICIT, BOOTS, FIRE, LEVEL, LIFE, boots, eater, eldritch_id, exarch, roll
from eldritch_support import DATA as BOOTS_DATA
from implicits_support import BELT, EXTENDED, _mod

from crafting_system.abstraction import Abstraction, Goal, ImplicitWanted, Status, Wanted
from crafting_system.actions import (
    ActionError,
    BlessedOrb,
    EldritchImplicitCurrency,
    NotApplicableError,
    OrbOfConflict,
    OutOfScopeError,
)
from crafting_system.data import BaseItem
from crafting_system.items import EldritchSide, ImplicitMod, Item, Rarity

ABSENT, BELOW, PASSING = Status.ABSENT, Status.BELOW, Status.PASSING
STRENGTH = "StrengthImplicitBelt1"  # +(25-35) to Strength: the implicit of the Heavy Belt
TWO_STAT, FIXED = "TwoStatImplicitRing", "FixedImplicitRing"
RING = "Metadata/Items/Rings/RingRollsTest"
LIFE_RING = "IncreasedLife1"  # an explicit mod of the fixture data

DATA = dataclasses.replace(
    EXTENDED,
    mods={
        **EXTENDED.mods,
        **{
            mod.id: mod
            for mod in (
                _mod(TWO_STAT, "unique", "item", "TwoStat", [("first_stat", 1, 2), ("second_stat", 5, 7)]),
                _mod(FIXED, "unique", "item", "Fixed", [("fixed_stat", 3, 3)]),
            )
        },
    },
    base_items={**EXTENDED.base_items, RING: BaseItem(RING, "Test Ring", "Ring", "item", 1, ("ring", "default"), (TWO_STAT, FIXED), "released")},
)


def belt(value: int | None, *mods, **fields) -> Item:
    """A rare Heavy Belt. `value` None: built as it is bought, carrying its base implicit at the low end, 25 (#484, #449)."""
    implicits = {} if value is None else {"implicits": (ImplicitMod(STRENGTH, 0, (value,)),)}
    return Item.build(DATA, base_id=BELT, item_level=84, rarity=Rarity.RARE, mods=mods, **implicits, **fields)


def replaced_belt(*mods, **fields) -> Item:
    """A belt whose base implicit a replacer took (it lists none): the implicit is not there, for the goal or for the Blessed Orb."""
    return Item.build(DATA, base_id=BELT, item_level=84, rarity=Rarity.RARE, mods=mods, implicits=(), **fields)


def ring(first: int | None = None, second: int = 5, *mods, **fields) -> Item:
    """A rare ring with two base implicits. `first` None: built as it is bought, with both at the low end of their ranges."""
    implicits = {} if first is None else {"implicits": (ImplicitMod(TWO_STAT, 0, (first, second)),)}
    return Item.build(DATA, base_id=RING, item_level=84, rarity=Rarity.RARE, mods=mods, **implicits, **fields)


def want(*mod_ids: str, **limits) -> ImplicitWanted:
    return ImplicitWanted(frozenset(mod_ids), **limits)


def belt_ability(*implicits: ImplicitWanted, leaves: tuple[Wanted, ...] = (), actions=(BlessedOrb(),)) -> Abstraction:
    return Abstraction(DATA, Goal(leaves, implicits), BELT, 84, actions)


def ring_ability(*implicits: ImplicitWanted) -> Abstraction:
    return Abstraction(DATA, Goal((), implicits), RING, 84, [BlessedOrb()])


def entries(state) -> list[tuple[int, tuple[Status, ...]]]:
    """The implicits a state keeps after the Eldritch pair, as `(grade, contribution)`."""
    return [(side.grade, side.contribution) for side in state.implicits[2:]]


# --- what a state holds -------------------------------------------------------------------------------------------------


def test_a_state_holds_what_the_roll_of_a_base_implicit_gives_each_requirement():
    found = belt_ability(want(STRENGTH, min_roll=(30,)), want(STRENGTH, min_roll=(34,)))
    assert found.tracks_implicits
    assert entries(found.compress(belt(25))) == [(0, (BELOW, BELOW))]
    assert entries(found.compress(belt(30))) == [(0, (PASSING, BELOW))]
    assert entries(found.compress(belt(35))) == [(0, (PASSING, PASSING))]
    assert entries(found.compress(belt(None))) == entries(found.compress(belt(25))) == [(0, (BELOW, BELOW))]  # carried at the low end
    assert entries(found.compress(replaced_belt())) == [(0, (ABSENT, ABSENT))]  # a replacer took it: it gives nothing
    assert found.compress(belt(31)) == found.compress(belt(33))  # two rolls no requirement tells apart are one state
    assert found.compress(belt(31)) != found.compress(belt(34))
    assert not found.is_goal(found.compress(belt(30)))
    assert found.is_goal(found.compress(belt(34)))


def test_each_requirement_is_met_by_one_implicit_and_a_roll_that_misses_is_below():
    found = belt_ability(want(STRENGTH, min_roll=(30,)), want(TWO_STAT))  # the second names an implicit the belt cannot hold
    assert not found.is_goal(found.compress(belt(35)))
    assert Abstraction(DATA, Goal((), (want(STRENGTH, min_roll=(None,)),)), BELT, 84, []).is_goal(
        Abstraction(DATA, Goal((), (want(STRENGTH, min_roll=(None,)),)), BELT, 84, []).compress(belt(25))
    )  # a limit that asks for no value is not a limit


def test_a_base_implicit_no_requirement_names_is_not_kept_and_does_not_make_two_states():
    found = belt_ability(want("AvoidShockEldritchImplicit1"))
    assert len(found.compress(belt(25)).implicits) == 2
    assert found.compress(belt(25)) == found.compress(belt(None)) == found.compress(belt(35))


def test_the_state_of_an_implicit_is_rebuilt_into_an_item_that_holds_a_roll_that_gives_it():
    found = belt_ability(want(STRENGTH, min_roll=(30,)), want(STRENGTH, min_roll=(34,)))
    for value in (25, 30, 35, None):
        item = belt(value)
        state = found.compress(item)
        rebuilt = found._item_of(state, False)[0]  # what an action is given in place of the state
        assert found.compress(rebuilt) == state
    assert found._item_of(found.compress(belt(30)), False)[0].implicits == (ImplicitMod(STRENGTH, 0, (30,)),)  # the lowest roll that gives it
    assert found._item_of(found.compress(belt(None)), False)[0].implicits == (ImplicitMod(STRENGTH, 0, (25,)),)
    assert found._item_of(found.compress(replaced_belt()), False)[0].implicits == ()  # it does not come back


# --- the Blessed Orb ----------------------------------------------------------------------------------------------------


def test_a_blessed_orb_leaves_the_chance_of_the_roll_it_is_asked_for():
    found = belt_ability(want(STRENGTH, min_roll=(33,)))  # 33, 34 and 35 pass: 3 of the 11 values
    for value in (25, 30, 33, 35, None):
        kernel = found.kernel(found.compress(belt(value)), BlessedOrb())
        assert {entries(state)[0]: chance for state, chance in kernel.items()} == {
            (0, (BELOW,)): Fraction(8, 11),
            (0, (PASSING,)): Fraction(3, 11),
        }  # whatever the belt held, also what passes now: the old value can roll again


def test_two_requirements_on_one_roll_are_correlated():
    found = belt_ability(want(STRENGTH, min_roll=(28,)), want(STRENGTH, min_roll=(33,)))
    kernel = found.kernel(found.compress(belt(25)), BlessedOrb())
    assert {entries(state)[0][1]: chance for state, chance in kernel.items()} == {
        (BELOW, BELOW): Fraction(3, 11),  # 25, 26, 27
        (PASSING, BELOW): Fraction(5, 11),  # 28 to 32
        (PASSING, PASSING): Fraction(3, 11),  # 33 to 35
    }  # (BELOW, PASSING) cannot happen: one roll


def test_the_stats_of_an_implicit_roll_independently():
    found = ring_ability(want(TWO_STAT, min_roll=(2, 6)))  # the first stat is 2 (1 of 2), the second 6 or 7 (2 of 3)
    kernel = found.kernel(found.compress(ring()), BlessedOrb())
    assert {entries(state)[0][1]: chance for state, chance in kernel.items()} == {(BELOW,): Fraction(2, 3), (PASSING,): Fraction(1, 3)}
    both = ring_ability(want(TWO_STAT, min_roll=(2, None)), want(TWO_STAT, min_roll=(None, 7)))
    kernel = both.kernel(both.compress(ring(1, 5)), BlessedOrb())
    assert {entries(state)[0][1]: chance for state, chance in kernel.items()} == {
        (BELOW, BELOW): Fraction(1, 2) * Fraction(2, 3),
        (PASSING, BELOW): Fraction(1, 2) * Fraction(2, 3),
        (BELOW, PASSING): Fraction(1, 2) * Fraction(1, 3),
        (PASSING, PASSING): Fraction(1, 2) * Fraction(1, 3),
    }


def test_a_roll_no_value_can_change_is_one_state():
    for limit in (20, 25):  # everything passes
        found = belt_ability(want(STRENGTH, min_roll=(limit,)))
        assert set(found.kernel(found.compress(belt(30)), BlessedOrb())) == {found.compress(belt(30))}
    found = belt_ability(want(STRENGTH, min_roll=(36,)))  # nothing passes
    assert set(found.kernel(found.compress(belt(30)), BlessedOrb())) == {found.compress(belt(30))}
    found = belt_ability(want(STRENGTH))  # no limit: any roll does
    assert set(found.kernel(found.compress(belt(None)), BlessedOrb())) == {found.compress(belt(25))}


def test_the_blessed_orb_is_refused_where_the_game_refuses_it():
    found = belt_ability(want(STRENGTH, min_roll=(33,)))
    for item in (belt(30, corrupted=True),):
        with pytest.raises(NotApplicableError):
            found.kernel(found.compress(item), BlessedOrb())
    nothing = ring_ability(want(FIXED))
    assert nothing.kernel(nothing.compress(ring()), BlessedOrb())  # the ring has a ranged implicit besides the fixed one


@pytest.mark.parametrize("stored", [True, False])
def test_the_explicit_mods_are_kept_and_the_goal_is_met_when_the_roll_passes(stored):
    leaves = (Wanted(frozenset({LIFE_RING})),)
    found = belt_ability(want(STRENGTH, min_roll=(33,)), leaves=leaves)
    item = belt(30 if stored else None, ExplicitModOf(LIFE_RING))
    kernel = found.kernel(found.compress(item), BlessedOrb())
    assert sum(chance for state, chance in kernel.items() if found.is_goal(state)) == Fraction(3, 11)
    assert all(state.slots == found.compress(item).slots and state.status == found.compress(item).status for state in kernel)


def ExplicitModOf(mod_id: str):
    from crafting_system.items import ExplicitMod

    return ExplicitMod(mod_id, tuple(min(stat.min, stat.max) for stat in DATA.mods[mod_id].stats))


# --- layer 1: against every value the roll can take ------------------------------------------------------------------------


BELT_GOALS = {
    "limit": ((want(STRENGTH, min_roll=(33,)),), ()),
    "two_limits": ((want(STRENGTH, min_roll=(28,)), want(STRENGTH, min_roll=(33,))), ()),
    "never": ((want(STRENGTH, min_roll=(36,)),), ()),
    "always": ((want(STRENGTH, min_roll=(25,)),), ()),
    "no_limit": ((want(STRENGTH),), ()),
    "with_an_explicit_mod": ((want(STRENGTH, min_roll=(30,)),), (Wanted(frozenset({LIFE_RING})),)),
}


@pytest.mark.parametrize("name", BELT_GOALS)
def test_layer_1_for_the_blessed_orb_on_a_belt(name):
    implicits, leaves = BELT_GOALS[name]
    found = belt_ability(*implicits, leaves=leaves)
    starts = [belt(None), belt(25), belt(30), belt(35), belt(30, ExplicitModOf(LIFE_RING)), belt(None, ExplicitModOf(LIFE_RING))]
    applied = 0
    for item in closure(DATA, starts, [BlessedOrb()], limit=80, rolls=True):
        applied += check_layer_1(found, DATA, item, BlessedOrb(), rolls=True)
    assert applied


RING_GOALS = {
    "one_leaf": (want(TWO_STAT, min_roll=(2, 6)),),
    "correlated": (want(TWO_STAT, min_roll=(2, None)), want(TWO_STAT, min_roll=(None, 7))),
    "fixed_next_to_ranged": (want(TWO_STAT, min_roll=(None, 6)), want(FIXED)),
}


@pytest.mark.parametrize("name", RING_GOALS)
def test_layer_1_for_the_blessed_orb_on_a_ring_with_two_stats(name):
    found = ring_ability(*RING_GOALS[name])
    starts = [ring(), ring(1, 5), ring(2, 7)]
    for item in closure(DATA, starts, [BlessedOrb()], limit=30, rolls=True):
        assert check_layer_1(found, DATA, item, BlessedOrb(), rolls=True)


# --- the Eldritch implicits and the base implicit together ------------------------------------------------------------------


def base_roll(mod_id: str, values: tuple[int, ...]) -> ImplicitMod:
    return ImplicitMod(mod_id, 0, values)


AVOID_SHOCK = tuple(eldritch_id("AvoidShock", grade) for grade in range(1, 7))
CHANCE_TO_SHOCK = tuple(eldritch_id("ChanceToShock", grade) for grade in range(1, 7))
EMBERS = tuple(EldritchImplicitCurrency(side, grade) for side in EldritchSide for grade in (1, 3))
ACTIONS = (*EMBERS, OrbOfConflict(), BlessedOrb())


def eldritch_ability(*implicits: ImplicitWanted, actions=ACTIONS) -> Abstraction:
    return Abstraction(BOOTS_DATA, Goal((Wanted(frozenset({LIFE})),), implicits), BOOTS, LEVEL, actions)


ELDRITCH_GOALS = {
    # AvoidShock grade g rolls 10g to 10g+2: 41 or 42 at grade 4, any roll at grade 5 and 6, none below 4
    "exarch_roll": (want(*AVOID_SHOCK, min_roll=(41,)),),
    "exarch_grade_and_roll": (want(*AVOID_SHOCK, min_grade=3, min_roll=(31,)),),
    "both_sides": (want(*AVOID_SHOCK, min_roll=(41,)), want(*CHANCE_TO_SHOCK, min_roll=(21,))),
    "base_implicit": (want(BASE_IMPLICIT, min_roll=(4,)), want(*AVOID_SHOCK, min_roll=(31,))),
}


def eldritch_starts() -> list[Item]:
    return [
        boots(roll(LIFE), implicits=(exarch(3), eater(2))),
        boots(roll(LIFE), roll(FIRE), implicits=(exarch(4), eater(1))),
        boots(roll(LIFE), implicits=(base_roll(BASE_IMPLICIT, (4,)),)),  # no start lists none: an item carries its base implicit until a replacer takes its place (#484)
        boots(roll(LIFE), implicits=(base_roll(BASE_IMPLICIT, (3,)),)),
        boots(roll(LIFE), implicits=(eater(2),)),  # the base implicit went to an Ember (#484)
    ]


@pytest.mark.parametrize("name", ELDRITCH_GOALS)
def test_layer_1_for_embers_conflict_and_the_blessed_orb_on_boots(name):
    found = eldritch_ability(*ELDRITCH_GOALS[name])
    items = closure(BOOTS_DATA, eldritch_starts(), ACTIONS, limit=120, rolls=True)
    applied = {action: 0 for action in ACTIONS}
    for item in items:
        for action in ACTIONS:
            applied[action] += check_layer_1(found, BOOTS_DATA, item, action, rolls=True)
    assert all(applied.values()), [action for action, count in applied.items() if not count]


def test_an_ember_rolls_the_implicit_it_puts_on_and_leaves_the_other_side_alone():
    found = eldritch_ability(want(*AVOID_SHOCK, min_roll=(31,)), want(*CHANCE_TO_SHOCK, min_roll=(21,)))
    start = found.compress(boots(roll(LIFE), implicits=(exarch(1), eater(2))))  # the Eater implicit rolled 20: below the limit
    assert start.implicits[1].contribution == (ABSENT, BELOW)
    kernel = found.kernel(start, EldritchImplicitCurrency(EldritchSide.EXARCH, 3))
    assert all(state.implicits[1] == start.implicits[1] for state in kernel)  # the other side stays as it was
    # a grade 3 AvoidShock rolls 30, 31 or 32: it passes the limit of 31 two times in three; the rest of the pool is not a requirement
    assert {state.implicits[0].contribution[0] for state in kernel} == {BELOW, PASSING, ABSENT}
    passing = sum(chance for state, chance in kernel.items() if state.implicits[0].contribution[0] is PASSING)
    gives_nothing = sum(chance for state, chance in kernel.items() if state.implicits[0].contribution[0] is ABSENT)
    assert passing == Fraction(2, 3) * (1 - gives_nothing)


def test_an_ember_on_boots_replaces_the_base_implicit_it_finds():
    found = eldritch_ability(want(BASE_IMPLICIT, min_roll=(4,)))
    start = found.compress(boots(roll(LIFE), implicits=(base_roll(BASE_IMPLICIT, (4,)),)))
    assert entries(start) == [(0, (PASSING,))]
    for state in found.kernel(start, EldritchImplicitCurrency(EldritchSide.EXARCH, 1)):
        assert entries(state) == [(0, (ABSENT,))]


def test_the_orb_of_conflict_rolls_the_two_implicits_it_moves():
    found = eldritch_ability(want(*AVOID_SHOCK, min_roll=(41,)))
    start = found.compress(boots(roll(LIFE), implicits=(exarch(3), eater(2))))
    kernel = found.kernel(start, OrbOfConflict())
    # the Exarch implicit (grade 3) is higher: raised to grade 4 (rolls 40, 41, 42: two in three pass 41) with the chance of the fit, else lowered to 2
    raised = {state: chance for state, chance in kernel.items() if state.implicits[0].grade == 4}
    assert {state.implicits[0].contribution for state in raised} == {(BELOW,), (PASSING,)}
    total = sum(raised.values())
    passing = sum(chance for state, chance in raised.items() if state.implicits[0].contribution == (PASSING,))
    assert passing == total * Fraction(2, 3)


def test_the_blessed_orb_is_refused_on_an_eldritch_implicit_in_the_kernel_as_in_the_action():
    found = eldritch_ability(want(BASE_IMPLICIT, min_roll=(4,)))
    state = found.compress(boots(roll(LIFE), implicits=(exarch(2),)))
    with pytest.raises(OutOfScopeError):
        found.kernel(state, BlessedOrb())
    with pytest.raises(ActionError):
        found.kernel(found.compress(boots(roll(LIFE), implicits=(), corrupted=True)), BlessedOrb())
