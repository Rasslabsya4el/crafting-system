"""`Status`, `Wanted`, `AtLeast` and `Goal`: the goal as the compressed state sees it, with no dependency on `targets`."""

from types import SimpleNamespace

import pytest
from abstraction_pool import GEM, RESISTS
from abstraction_support import (
    ABSENT,
    BELOW,
    DAMAGE_LEAF,
    GEM_LEAF,
    GOALS,
    LIFE_LEAF,
    MANA_LEAF,
    PASSING,
    RESIST_LEAF,
)
from targets_support import parse

from crafting_system.abstraction import AtLeast, Goal, Status, Wanted


def leaves_of(goal):
    """The leaves of a goal, whether the API makes `leaves` a property or a method."""
    leaves = goal.leaves
    return leaves() if callable(leaves) else leaves


def test_a_status_is_ordered_so_that_the_best_of_several_mods_is_the_maximum():
    assert (Status.ABSENT, Status.BELOW, Status.PASSING) == (0, 1, 2)
    assert max(Status.ABSENT, Status.BELOW) is Status.BELOW
    assert max([Status.BELOW, Status.PASSING, Status.ABSENT]) is Status.PASSING


def test_the_requirements_are_values_with_defaults_that_ask_nothing_extra():
    wanted = Wanted(frozenset({GEM}))

    assert (wanted.min_tier, wanted.min_roll, wanted.not_crafted) == (None, None, False)
    assert wanted == Wanted(frozenset({GEM})) and hash(wanted) == hash(Wanted(frozenset({GEM})))
    assert AtLeast(1, (wanted,)) == AtLeast(1, (wanted,))
    assert hash(Goal((wanted,))) == hash(Goal((wanted,)))


def test_every_leaf_must_pass_for_a_flat_goal():
    goal = GOALS["r12"]

    assert goal.is_met([PASSING, PASSING])
    assert not goal.is_met([PASSING, BELOW])
    assert not goal.is_met([ABSENT, PASSING])
    assert not goal.is_met([ABSENT, ABSENT])


@pytest.mark.parametrize(
    ("statuses", "met"),
    [
        ((PASSING, PASSING, ABSENT), True),
        ((PASSING, ABSENT, PASSING), True),
        ((ABSENT, PASSING, PASSING), True),
        ((PASSING, PASSING, PASSING), True),
        ((PASSING, BELOW, ABSENT), False),
        ((BELOW, BELOW, PASSING), False),
        ((ABSENT, ABSENT, ABSENT), False),
    ],
)
def test_a_k_of_n_is_met_by_at_least_k_passing_members(statuses, met):
    assert GOALS["two_of_three"].is_met(statuses) is met


def test_a_nested_k_of_n_and_a_top_level_leaf_are_all_required():
    goal = GOALS["nested"]  # leaves: gem, damage, resist, life, mana

    assert goal.is_met([PASSING, ABSENT, ABSENT, ABSENT, PASSING])
    assert goal.is_met([ABSENT, PASSING, PASSING, ABSENT, PASSING])
    assert goal.is_met([ABSENT, ABSENT, PASSING, PASSING, PASSING])
    assert not goal.is_met([ABSENT, PASSING, BELOW, ABSENT, PASSING])
    assert not goal.is_met([PASSING, PASSING, PASSING, PASSING, ABSENT])


def test_the_leaves_are_listed_depth_first_in_file_order():
    assert leaves_of(GOALS["nested"]) == (GEM_LEAF, DAMAGE_LEAF, RESIST_LEAF, LIFE_LEAF, MANA_LEAF)
    assert leaves_of(GOALS["r12"]) == (GEM_LEAF, RESIST_LEAF)
    assert leaves_of(Goal((AtLeast(1, (AtLeast(1, (GEM_LEAF,)), RESIST_LEAF)), MANA_LEAF))) == (GEM_LEAF, RESIST_LEAF, MANA_LEAF)


TEXT = """
requirements:
  - stat: "+1 to Level of all Lightning Skill Gems"
  - family: LightningResistance
    min_tier: 2
  - at_least: 1
    of:
      - family: LightningDamage
        not_crafted: true
      - at_least: 1
        of:
          - family: IncreasedLife
            min_roll: 10
          - family: ManaLeech
"""


def test_a_goal_is_built_from_a_parsed_target_without_importing_targets():
    target = parse(TEXT)
    gem, resist, group = target.requirements
    damage, inner = group.of
    life, mana = inner.of

    goal = Goal.from_target(target)

    assert goal == Goal(
        (
            Wanted(gem.mod_ids),
            Wanted(resist.mod_ids, min_tier=2),
            AtLeast(
                1,
                (
                    Wanted(damage.mod_ids, not_crafted=True),
                    AtLeast(1, (Wanted(life.mod_ids, min_roll=(10,)), Wanted(mana.mod_ids))),
                ),
            ),
        )
    )
    assert len(leaves_of(goal)) == 5
    assert leaves_of(goal)[3].min_roll == (10,)


def test_from_target_reads_attributes_only_so_any_object_with_the_right_shape_works():
    leaf = SimpleNamespace(mod_ids=frozenset({GEM}), min_tier=1, min_roll=(None, 3), not_crafted=True)
    group = SimpleNamespace(at_least=2, of=(leaf, SimpleNamespace(mod_ids=RESISTS, min_tier=None, min_roll=None, not_crafted=False)))

    goal = Goal.from_target(SimpleNamespace(requirements=(group, leaf)))

    expected_leaf = Wanted(frozenset({GEM}), min_tier=1, min_roll=(None, 3), not_crafted=True)
    assert goal == Goal((AtLeast(2, (expected_leaf, Wanted(RESISTS))), expected_leaf))

