"""The line a report writes for an item counts only the mods it does not already name (ticket #613).

R04's state S309 said `has family Strength; has family AdditionalArrows; ...; other mods: 1 prefix, 2 suffixes`, and the two suffixes were the Strength
and the arrow the line had just named, so a reader took them for two more mods (a quiver with four suffixes, which it cannot hold). "Other mods"
is now the mods no requirement of the line names.
"""

import itertools
from pathlib import Path
from types import SimpleNamespace

from abstraction_support import real_game_data

from crafting_system.abstraction import CompressedState, Flags, FracturedMod, Slot, Status
from crafting_system.planner._plan import leaf_labels
from crafting_system.cli._report import describe_state
from crafting_system.items import Rarity, Side
from crafting_system.targets import KOfN, load_target

ABSENT, BELOW, PASSING = Status.ABSENT, Status.BELOW, Status.PASSING
LABELS = ("family Strength", "family AdditionalArrows", "family IncreasedLife")


def item(status, slots, fractured=(), rarity=Rarity.RARE):
    return CompressedState(Flags(rarity, False, frozenset()), tuple(fractured), tuple(status), tuple(slots))


def slot(side, *contribution):
    return Slot(side, "", tuple(contribution))


def plain_plan():
    """A plan of three plain requirements (the leaf of a requirement is any node that is not a k-of-n group)."""
    leaf = SimpleNamespace(mod_ids=frozenset())
    return SimpleNamespace(leaf_labels=LABELS, target=SimpleNamespace(requirements=(leaf, leaf, leaf)))


def describe(state):
    return describe_state(plain_plan(), None, state)


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
    plan = plain_plan()
    data = SimpleNamespace(mods={})  # a family type ("~1"): the line says the state does not tell which mod it is

    assert describe_state(plan, data, state).endswith("other mods: 1 prefix")  # the fractured mod meets the requirement, so this one is another mod


def test_the_count_keeps_the_plural_and_both_sides():
    state = item((ABSENT, ABSENT, ABSENT), [slot(Side.PREFIX, ABSENT, ABSENT, ABSENT)] * 2 + [slot(Side.SUFFIX, ABSENT, ABSENT, ABSENT)])

    assert describe(state).endswith("other mods: 2 prefixes, 1 suffix")


# --- a k-of-n group is said once (ticket #644, OR-15) ---------------------------------------------------------------------------

R05 = Path(__file__).resolve().parents[1] / "examples" / "targets" / "r05-strength-ring.yaml"


def r05_plan():
    data = real_game_data()
    target = load_target(R05, data)
    return data, SimpleNamespace(target=target, leaf_labels=leaf_labels(target), abstraction=SimpleNamespace(data=data))


def r05_state(plan, group_status):
    """Every plain requirement met; the four members of the 1-of-4 group (Life and three resistances) stand as `group_status`."""
    group = next(each for each in plan.target.requirements if isinstance(each, KOfN))
    first = sum(1 for each in plan.target.requirements[: plan.target.requirements.index(group)] if not isinstance(each, KOfN))
    status = [PASSING] * len(plan.leaf_labels)
    status[first : first + len(group.of)] = group_status
    return item(status, [])


def test_r05_an_item_with_the_life_mod_does_not_lack_the_three_resistances():
    data, plan = r05_plan()
    text = describe_state(plan, data, r05_state(plan, [PASSING, ABSENT, ABSENT, ABSENT]))

    assert "lacks" not in text
    assert text.count("(the group needs 1 of 4)") == 1
    assert "Resistance" not in text  # the resistances are not said at all: the group is met


def test_r05_an_item_with_none_of_the_group_lacks_one_of_the_four_and_says_so_once():
    data, plan = r05_plan()
    text = describe_state(plan, data, r05_state(plan, [ABSENT] * 4))

    (lacks,) = [part for part in text.split("; ") if part.startswith("lacks")]
    assert lacks.startswith("lacks 1 of: ") and lacks.count(",") == 3 and lacks.endswith("(the group needs 1 of 4)")


def test_a_weak_member_of_a_group_that_is_not_met_is_said_once_among_those_still_to_find():
    data, plan = r05_plan()
    text = describe_state(plan, data, r05_state(plan, [BELOW, ABSENT, ABSENT, ABSENT]))

    assert "too weak: " not in text and text.count("(held, too weak)") == 1  # not "too weak: Z; lacks 1 of: Z, W"
    (lacks,) = [part for part in text.split("; ") if part.startswith("lacks")]
    assert lacks.startswith("lacks 1 of: ") and "(held, too weak)" in lacks


def test_a_weak_member_of_a_group_that_is_met_is_still_said():
    data, plan = r05_plan()
    text = describe_state(plan, data, r05_state(plan, [PASSING, BELOW, ABSENT, ABSENT]))

    assert "lacks" not in text and text.count("too weak: ") == 1  # the item holds it, and its mod is not counted as another one


# a nested group: X, and 2 of [Y, 1 of [Z, W]]
NESTED = ("leafX", "leafY", "leafZ", "leafW")


def nested_plan():
    leaf = [SimpleNamespace(mod_ids=frozenset()) for _ in NESTED]
    inner = KOfN(1, (leaf[2], leaf[3]))
    return SimpleNamespace(leaf_labels=NESTED, target=SimpleNamespace(requirements=(leaf[0], KOfN(2, (leaf[1], inner)))))


def test_a_weak_member_inside_a_nested_group_is_said_where_it_is_listed():
    state = item((PASSING, PASSING, BELOW, ABSENT), [])

    text = describe_state(nested_plan(), None, state)

    assert "has leafX" in text and "has leafY (the group needs 2 of 2)" in text
    assert "lacks 1 of: at least 1 of 2 of: leafZ (held, too weak), leafW" in text


def test_the_mod_of_a_weak_member_inside_a_nested_group_is_not_counted_as_another_mod():
    state = item((PASSING, PASSING, BELOW, ABSENT), [slot(Side.SUFFIX, ABSENT, ABSENT, BELOW, ABSENT), slot(Side.PREFIX, ABSENT, ABSENT, ABSENT, ABSENT)])

    text = describe_state(nested_plan(), None, state)

    assert text.endswith("other mods: 1 prefix")  # the suffix is the weak Z, which the line says


def test_a_leaf_that_is_held_is_on_the_line_once_and_no_leaf_is_said_twice_at_any_standing():
    """All 81 standings of the four leaves of the nested group."""
    for standing in itertools.product((ABSENT, BELOW, PASSING), repeat=4):
        text = describe_state(nested_plan(), None, item(standing, []))
        for label, status in zip(NESTED, standing):
            assert text.count(label) <= 1, (standing, label, text)
            assert status is ABSENT or text.count(label) == 1, (standing, label, text)
