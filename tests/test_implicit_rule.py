"""One rule for which implicits of its base an item holds (ticket #528, merging #531 and #533; OR-3, OR-26).

The game: an Ember or an Ichor replaces every implicit but the other side's Eldritch one (`eldritch.ember_replaces_implicits`), and a corrupted
implicit takes the place of one implicit, chosen at random (`corruption.implicit_replaces_existing`). So:

* `Item.validate` refuses a base implicit beside an Eldritch implicit (no route makes such an item);
* `with_base_implicits` fills in the base implicits a list leaves out, but none beside an Eldritch implicit and, beside corrupted implicits, only
  when the list says which stayed: on a base with two implicits a list that names one keeps it, and one that names none is refused;
* the planner state says which base implicits a corrupted item no longer holds, so a Vaal outcome that keeps the base implicit comes back with it
  from `compress` then `_item_of`, and the implicit outcome comes back without it.

The oracle's copy of the rule, written from the game text alone, is checked in `test_goal_oracle.py`; the real Heavy Belt in
`test_base_implicits_real.py`.
"""

import dataclasses

import pytest
from corruption_support import ALL_RES, BASE_IMPLICIT, DATA, EATER, LEVEL, base_implicit, eater, exarch, on

from crafting_system.abstraction import Abstraction, Goal, ImplicitWanted
from crafting_system.actions import VaalOrb
from crafting_system.data import StatRange
from crafting_system.items import ImplicitError, ImplicitMod, Item, Rarity, is_corrupted_implicit, with_base_implicits

BELT = "Metadata/Items/Belts/Belt4"
TWO = "Metadata/Items/Belts/RuleTestTwoImplicits"  # a belt with two implicits of its own (no craftable base has two today, #533)
LIFE_IMPLICIT = "IncreasedLifeImplicitBelt1"


def low(mod_id: str) -> ImplicitMod:
    return ImplicitMod(mod_id, 0, tuple(min(stat.min, stat.max) for stat in TWO_DATA.mods[mod_id].stats))


def vaal() -> ImplicitMod:
    return low(ALL_RES)


_LIFE_MOD = dataclasses.replace(
    DATA.mods[BASE_IMPLICIT], id=LIFE_IMPLICIT, type="IncreasedLife", families=("IncreasedLife",), stats=(StatRange("base_maximum_life", 25, 40),)
)
TWO_DATA = dataclasses.replace(
    DATA,
    mods={**DATA.mods, LIFE_IMPLICIT: _LIFE_MOD},
    base_items={**DATA.base_items, TWO: dataclasses.replace(DATA.base_items[BELT], id=TWO, implicits=(BASE_IMPLICIT, LIFE_IMPLICIT))},
)
TWO_BASE = TWO_DATA.base_items[TWO]


# --- Item.validate ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("eldritch", [eater, exarch], ids=["eater", "exarch"])
def test_an_item_with_a_base_implicit_beside_an_eldritch_one_is_refused(eldritch):
    with pytest.raises(ImplicitError, match="Ember"):
        on(BELT, implicits=(base_implicit(), eldritch()))


def test_an_eldritch_implicit_alone_or_the_base_implicit_alone_is_an_item():
    assert on(BELT, implicits=(eater(),)).implicits == (eater(),)
    assert on(BELT, implicits=(exarch(), eater())).implicits
    assert on(BELT, implicits=(base_implicit(),)).implicits == (base_implicit(),)
    assert on(BELT, corrupted=True, implicits=(vaal(), eater())).corrupted  # a corrupted implicit beside an Eldritch one: it took the other side's


# --- with_base_implicits ---------------------------------------------------------------------------------------------


def test_a_list_with_no_replacer_gets_every_base_implicit_it_leaves_out():
    assert with_base_implicits(TWO_DATA, TWO_BASE, ()) == (low(BASE_IMPLICIT), low(LIFE_IMPLICIT))
    held = ImplicitMod(LIFE_IMPLICIT, 0, (40,))
    assert with_base_implicits(TWO_DATA, TWO_BASE, (held,)) == (held, low(BASE_IMPLICIT))


def test_an_eldritch_replacer_takes_both_base_implicits():
    assert with_base_implicits(TWO_DATA, TWO_BASE, (eater(),)) == (eater(),)
    assert with_base_implicits(TWO_DATA, TWO_BASE, (exarch(), vaal())) == (exarch(), vaal())


def test_a_corrupted_implicit_on_a_two_implicit_base_keeps_the_other_base_implicit():
    """#533: a Vaal implicit replaces one of two implicits at random, so the game keeps the other; the list names the one that stayed."""
    assert with_base_implicits(TWO_DATA, TWO_BASE, (vaal(), low(LIFE_IMPLICIT))) == (vaal(), low(LIFE_IMPLICIT))
    assert with_base_implicits(TWO_DATA, TWO_BASE, (low(BASE_IMPLICIT), vaal())) == (low(BASE_IMPLICIT), vaal())


def test_a_corrupted_implicit_on_a_two_implicit_base_that_names_neither_is_refused():
    """One of the two stayed and the list does not say which: it is not dropped (the game keeps one) nor guessed."""
    with pytest.raises(ImplicitError, match="list the base implicit that stayed"):
        with_base_implicits(TWO_DATA, TWO_BASE, (vaal(),))


def test_a_corrupted_implicit_on_a_one_implicit_base_took_its_place():
    belt = DATA.base_items[BELT]
    assert with_base_implicits(DATA, belt, (vaal(),)) == (vaal(),)
    assert with_base_implicits(DATA, belt, (vaal(), base_implicit())) == (vaal(), base_implicit())


def test_the_base_implicits_a_caller_says_are_gone_are_not_filled_in():
    assert with_base_implicits(TWO_DATA, TWO_BASE, (), gone=frozenset({BASE_IMPLICIT})) == (low(LIFE_IMPLICIT),)


# --- the planner state (#531) ----------------------------------------------------------------------------------------


def corrupted_belt(*implicits: ImplicitMod) -> Item:
    return on(BELT, rarity=Rarity.RARE, corrupted=True, implicits=implicits)


def abstraction(data=DATA, base_id=BELT) -> Abstraction:
    goal = Goal((), (ImplicitWanted(frozenset({EATER})),))  # names an Eldritch implicit: the base implicit decides nothing
    return Abstraction(data, goal, base_id, LEVEL, [VaalOrb()])


def test_a_corrupted_item_that_keeps_its_base_implicit_comes_back_with_it():
    ab = abstraction()
    kept = corrupted_belt(base_implicit())
    taken = corrupted_belt(vaal())

    assert ab._item_of(ab.compress(kept), False)[0].implicits == (base_implicit(),)
    assert ab._item_of(ab.compress(taken), False)[0].implicits == ()  # the state keeps no corrupted implicit (ADR-0036)
    assert ab.compress(kept) != ab.compress(taken)


def test_a_vaal_orb_s_outcomes_survive_compress_then_item_of():
    ab = abstraction()
    start = on(BELT, implicits=(base_implicit(),))
    for _, item in VaalOrb().outcomes(DATA, start).results:
        rebuilt = ab._item_of(ab.compress(item), False)[0]
        visible = tuple(entry for entry in item.implicits if not is_corrupted_implicit(DATA.mods[entry.mod_id]))
        assert rebuilt.implicits == visible
        assert ab.compress(rebuilt) == ab.compress(item)


def test_a_state_that_is_not_corrupted_reads_as_before():
    ab = abstraction()
    fresh = on(BELT, implicits=(base_implicit(),))
    embered = on(BELT, implicits=(eater(),))
    assert ab.compress(fresh).replaced == () and ab.compress(embered).replaced == ()
    assert "replaced" not in repr(ab.compress(fresh))
    assert ab._item_of(ab.compress(embered), False)[0].implicits == (eater(),)


def test_a_corrupted_item_with_an_eldritch_implicit_holds_no_base_implicit():
    ab = abstraction()
    state = ab.compress(corrupted_belt(vaal(), eater()))
    assert state.replaced == ()  # the Eldritch implicit says it
    assert ab._item_of(state, False)[0].implicits == (eater(),)


def test_on_a_two_implicit_base_the_state_says_which_base_implicit_stayed():
    ab = abstraction(TWO_DATA, TWO)
    strength = on_two(vaal(), low(BASE_IMPLICIT))
    life = on_two(vaal(), low(LIFE_IMPLICIT))
    both_gone = on_two(vaal())

    assert ab._item_of(ab.compress(strength), False)[0].implicits == (low(BASE_IMPLICIT),)
    assert ab._item_of(ab.compress(life), False)[0].implicits == (low(LIFE_IMPLICIT),)
    assert ab._item_of(ab.compress(both_gone), False)[0].implicits == ()
    assert len({ab.compress(strength), ab.compress(life), ab.compress(both_gone)}) == 3


def on_two(*implicits: ImplicitMod) -> Item:
    return Item.build(TWO_DATA, base_id=TWO, item_level=LEVEL, rarity=Rarity.RARE, corrupted=True, implicits=implicits)
