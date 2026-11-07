"""The line a report writes for an item counts only the mods it does not already name (ticket #613).

R04's state S309 said `has family Strength; has family AdditionalArrows; ...; other mods: 1 prefix, 2 suffixes`, and the two suffixes were the Strength
and the arrow the line had just named, so a reader took them for two more mods (a quiver with four suffixes, which it cannot hold). "Other mods"
is now the mods no requirement of the line names.
"""

from types import SimpleNamespace

from crafting_system.abstraction import CompressedState, Flags, FracturedMod, Slot, Status
from crafting_system.cli._report import describe_state
from crafting_system.items import Rarity, Side

ABSENT, BELOW, PASSING = Status.ABSENT, Status.BELOW, Status.PASSING
LABELS = ("family Strength", "family AdditionalArrows", "family IncreasedLife")


def item(status, slots, fractured=(), rarity=Rarity.RARE):
    return CompressedState(Flags(rarity, False, frozenset()), tuple(fractured), tuple(status), tuple(slots))


def slot(side, *contribution):
    return Slot(side, "", tuple(contribution))


def describe(state):
    return describe_state(SimpleNamespace(leaf_labels=LABELS), None, state)


def test_r04_s309_the_mods_the_line_names_are_not_counted_again():
    """The shape of S309: two suffixes that are the Strength and the arrow, one prefix that is neither."""
    state = item(
        (PASSING, PASSING, ABSENT),
        [slot(Side.PREFIX, ABSENT, ABSENT, ABSENT), slot(Side.SUFFIX, PASSING, ABSENT, ABSENT), slot(Side.SUFFIX, ABSENT, PASSING, ABSENT)],
    )

    text = describe(state)

    assert "has family Strength; has family AdditionalArrows; lacks family IncreasedLife" in text
    assert text.endswith("other mods: 1 prefix")
    assert "suffix" not in text


def test_a_mod_that_the_line_calls_too_weak_is_named_too():
    state = item((ABSENT, ABSENT, BELOW), [slot(Side.PREFIX, ABSENT, ABSENT, BELOW), slot(Side.SUFFIX, ABSENT, ABSENT, ABSENT)])

    text = describe(state)

    assert "too weak: family IncreasedLife" in text and text.endswith("other mods: 1 suffix")


def test_a_mod_that_meets_two_requirements_is_taken_once_and_the_next_mod_stays_counted():
    two = item((PASSING, PASSING, ABSENT), [slot(Side.SUFFIX, PASSING, PASSING, ABSENT), slot(Side.SUFFIX, ABSENT, ABSENT, ABSENT)])
    assert describe(two).endswith("other mods: 1 suffix")

    apart = item((PASSING, PASSING, ABSENT), [slot(Side.SUFFIX, PASSING, ABSENT, ABSENT), slot(Side.SUFFIX, ABSENT, PASSING, ABSENT)])
    assert "other mods" not in describe(apart)  # both are named: no part at all


def test_a_requirement_a_fractured_mod_meets_takes_no_other_mod_with_it():
    state = item(
        (PASSING, ABSENT, ABSENT),
        [slot(Side.PREFIX, PASSING, ABSENT, ABSENT)],
        fractured=[FracturedMod("~1", (PASSING, ABSENT, ABSENT))],
    )
    plan = SimpleNamespace(leaf_labels=LABELS)
    data = SimpleNamespace(mods={})  # a family type ("~1"): the line says the state does not tell which mod it is

    assert describe_state(plan, data, state).endswith("other mods: 1 prefix")  # the fractured mod meets the requirement, so this one is another mod


def test_the_count_keeps_the_plural_and_both_sides():
    state = item((ABSENT, ABSENT, ABSENT), [slot(Side.PREFIX, ABSENT, ABSENT, ABSENT)] * 2 + [slot(Side.SUFFIX, ABSENT, ABSENT, ABSENT)])

    assert describe(state).endswith("other mods: 2 prefixes, 1 suffix")
