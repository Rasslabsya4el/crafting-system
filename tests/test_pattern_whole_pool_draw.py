"""An addition from the whole pool keeps the extremes when another action draws by tag (#1311 root 1, coded for #1567).

The world of `test_abstraction_pattern.py` (a fixture Thicket Bow whose five attack-tagged prefix families have four weights) with one more
enabled action, the Harvest craft that adds a Fire mod and removes another: it declares a draw tag, so the family types carry the tags
(`Kinds._tagged`). An Exalted Orb, a Regal Orb and an Orb of Augmentation declare none: they read only the weight a held family takes out of
the whole pool, so the extreme members of a key are still at least as good as every member (`check_dominates`, brute force over every
member and random values of the successor keys). Before #1567 any tagged draw of another action sent them to every member (`Mode.ALL`).
"""

import random

import pytest
from abstraction_removals_support import BOW, build
from pattern_support import all_members, check_dominates, pushed
from test_abstraction_pattern import ACTIONS, GOAL, LEVEL, OTHER_STARTS, STARTS, pattern_data

from crafting_system.abstraction import Abstraction
from crafting_system.abstraction._pattern import Mode, Pattern
from crafting_system.actions import ActionError
from crafting_system.actions.harvest_augment import HarvestAddRemove

TAGGED = {**ACTIONS, "add-remove-fire": HarvestAddRemove("fire")}
WHOLE_POOL = ("exalted", "regal", "augment")


@pytest.fixture(scope="module")
def tagged_world():
    data = pattern_data()
    ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(TAGGED.values()), metamods=True)
    states = set()
    rng = random.Random(1311)
    starts = [ab.compress(build(data, BOW, ids)) for ids in STARTS]
    starts += [ab.compress(build(data, BOW, ids, rarity=rarity)) for ids, rarity in OTHER_STARTS]
    for start in starts:
        for _ in range(40):
            state = start
            for _ in range(8):
                states.add(state)
                if ab.is_goal(state):
                    break
                action = rng.choice(list(TAGGED.values()))
                try:
                    kernel = ab.kernel(state, action)
                except ActionError:
                    continue
                state = rng.choices(list(kernel), weights=[float(c) for c in kernel.values()])[0]
    return ab, sorted(states, key=repr)


def test_the_world_draws_by_tag(tagged_world):
    ab, _ = tagged_world
    assert ab._context(frozenset()).kinds._tagged, "the Harvest craft's tag makes the family types carry tags"


@pytest.mark.parametrize("name", WHOLE_POOL)
def test_a_whole_pool_addition_is_asked_at_the_extremes_and_they_dominate(tagged_world, name):
    ab, states = tagged_world
    pattern = Pattern(ab, True, list(TAGGED.values()))
    action = TAGGED[name]
    keys = list(dict.fromkeys(pattern.key(state) for state in states))
    rng = random.Random(2)
    compared = offered = fewer = 0
    for key in rng.sample(keys, len(keys)):
        if not any(pushed(pattern, ab, member, action) is not None for member in all_members(pattern, key)):
            continue
        assert pattern.mode_of(action, key) is Mode.EXTREMES, (name, key)
        members, legal = check_dominates(pattern, ab, key, action, Mode.EXTREMES, rng, trials=12)
        compared += members
        offered += legal
        fewer += len(pattern.members(key, Mode.EXTREMES)) < len(pattern.members(key, Mode.ALL))
        if offered >= 25:
            break
    assert compared and offered
    if name == "exalted":
        assert fewer, "some key has a choice of junk, so the extremes ask fewer members than every member"


def test_the_tagged_draw_itself_is_still_asked_at_every_member(tagged_world):
    ab, states = tagged_world
    pattern = Pattern(ab, True, list(TAGGED.values()))
    key = pattern.key(states[0])
    assert pattern.mode_of(TAGGED["add-remove-fire"], key) is Mode.ALL
