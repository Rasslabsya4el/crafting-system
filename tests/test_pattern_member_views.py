"""The members an action cannot tell apart (#1338): an action that reads of an ordinary slot only what the key reads of it is asked once
for each multiset of those views at a key.

`ONE` asked the Annulment Orb at every relevant multiset of a key: on R04's quiver thousands a key, each a kernel key and a kernel of its
own (596,911 kernels for 13,284 distinct ones in the first five minutes). The module docstring of `abstraction._pattern` ("The members an
action cannot tell apart") has the lemma and its argument; here every member of every key a seeded walk meets is compared with the members
of the same views, and the model built once per view with the model built at every member, on the hand-worked world and on R04's quiver.
"""

import contextlib
import dataclasses
import random
from pathlib import Path

from abstraction_support import real_game_data
from pattern_support import pushed as pushed_through_key
import test_pattern_eldritch as eldritch
from abstraction_removals_support import CASTER, FIRE, FIRE_RES, NC, SPEED_TIER_1
from test_abstraction_pattern import ACTIONS, BOW, EXTRA_PREFIXES, EXTRA_SUFFIXES, GOAL, LEVEL, OTHER_STARTS, STARTS, build, pattern_data
from test_pattern_items_kept import same_model

from crafting_system.abstraction import Abstraction, Goal, Wanted, _pattern
from crafting_system.abstraction._pattern import Mode, Pattern, PatternOffer, build_pattern_model
from crafting_system.actions import ActionError
from crafting_system.actions.eldritch import EldritchAnnulmentOrb
from crafting_system.cli import make_plan
from crafting_system.planner._pattern_bound import pattern_lower_bound
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
from crafting_system.targets.model import StartKind

CLASSIC_OFFERS = True  # the plans of real routes below are made with the classic offers (`tests/test_classic_offers.py`)
ROOT = Path(__file__).resolve().parents[1]
VIEWS_ONLY = {"annul", "remove"}  # of the hand-worked world's actions, the ones the lemma covers
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
PIECES = 100_000  # the pairs of the counted build on R04 (2,377 keys found, 89 expanded: about 2 s)


@contextlib.contextmanager
def every_member():
    """The build as it was before #1338: such an action is asked at every member of its policy."""
    before = _pattern.SHARE_VIEWS
    _pattern.SHARE_VIEWS = False
    try:
        yield
    finally:
        _pattern.SHARE_VIEWS = before


def walked_states(ab: Abstraction, actions, seed: int) -> list:
    """The states a seeded walk of the hand-worked world meets from every start."""
    data = ab.data
    starts = [ab.compress(build(data, BOW, ids)) for ids in STARTS]
    starts += [ab.compress(build(data, BOW, ids, rarity=rarity)) for ids, rarity in OTHER_STARTS]
    rng = random.Random(seed)
    states: dict = {}
    for start in starts:
        for _ in range(40):
            state = start
            for _ in range(8):
                states[state] = None
                try:
                    kernel = ab.kernel(state, rng.choice(actions))
                except ActionError:
                    continue
                state = rng.choices(list(kernel), weights=[float(chance) for chance in kernel.values()])[0]
    return list(states)


def test_the_actions_the_lemma_covers_are_the_ones_that_read_no_mod_and_add_none():
    data = pattern_data()
    ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
    pattern = Pattern(ab, True, list(ACTIONS.values()))
    assert {name for name, action in ACTIONS.items() if pattern.views_only(action)} == VIEWS_ONLY
    assert pattern.views_only(EldritchAnnulmentOrb())  # the Annulment of the dominant side
    with every_member():
        assert not Pattern(ab, True, list(ACTIONS.values())).views_only(ACTIONS["annul"])


def test_on_the_hand_worked_world_the_members_of_one_view_give_one_kernel():
    """Every member of every key a seeded walk meets, with a lock and without: the members with the same views refuse alike or give the
    same kernel through the key, for every action the lemma covers."""
    data = pattern_data()
    ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
    pattern = Pattern(ab, True, list(ACTIONS.values()))
    groups = shared = locked = 0
    for key in dict.fromkeys(map(pattern.key, walked_states(ab, list(ACTIONS.values()), 1338))):
        every = pattern.members(key, Mode.ALL)
        by_view: dict = {}
        for member in every:
            by_view.setdefault(pattern.view(member), []).append(member)
        for name in sorted(VIEWS_ONLY):
            action = ACTIONS[name]
            for members in by_view.values():
                answers = {_frozen(pushed_through_key(pattern, ab, member, action)) for member in members}
                assert len(answers) == 1, (key, name)
                groups += 1
                shared += len(members) - 1
                locked += len(members) > 1 and pattern.holds_lock(key)
    assert groups > 500 and shared > 1_000 and locked > 0


def _frozen(found):
    return None if found is None else frozenset(found.items())


def test_the_whole_model_of_the_hand_worked_world_is_the_model_built_at_every_member():
    """A complete build from several starts, both ways, for a goal that takes any of three prefixes (so several relevant slots give it
    the same, and the Annulment cannot tell them apart): the same keys in the same order, the same rows and kernels (so the same values),
    exact and approximate, from fewer kernels."""
    data = pattern_data()
    a, b, c = (name for name, _ in EXTRA_PREFIXES)
    goal = Goal((SPEED_TIER_1, Wanted(frozenset({FIRE, a, b}))))
    names = ("annul", "remove", "exalted", "chaos", "fracture", "bench-lock", "bench-craft")
    offers = [PatternOffer(name, ACTIONS[name], 1.0 + n) for n, name in enumerate(names)]
    shared = 0
    for ids in ((c, FIRE_RES, CASTER, EXTRA_SUFFIXES[1][0]), (c, CASTER, EXTRA_SUFFIXES[0][0], NC)):
        for approximate in (False, True):

            def made(before: bool):
                ab = Abstraction(data, goal, BOW, LEVEL, tuple(ACTIONS[name] for name in names), metamods=True)
                start = ab.compress(build(data, BOW, ids))
                with every_member() if before else contextlib.nullcontext():
                    return build_pattern_model(ab, start, offers, tags=True, approximate=approximate)

            old, new = made(True), made(False)
            same_model(old, new)
            assert new.stopped is None and all(new.expanded)
            assert new.stats.pairs == old.stats.pairs and new.stats.refused_pairs == old.stats.refused_pairs and old.stats.view_pairs == 0
            assert new.stats.kernels < old.stats.kernels
            shared += new.stats.view_pairs
    assert shared > 1_000


def test_on_the_eldritch_world_the_members_of_one_view_give_one_kernel():
    """The Eldritch Annulment, the Embers, the Ichor and the Orb of Conflict: every member of every key a seeded walk meets."""
    ab = eldritch.abstraction()
    actions = [action for action, _ in eldritch.OFFERED.values()]
    pattern = Pattern(ab, None, actions)
    covered = [action for action in actions if pattern.views_only(action)]
    assert len(covered) == len(actions) - 1  # all but the Eldritch Exalted Orb, which draws
    rng = random.Random(1338)
    states: dict = {}
    for _ in range(60):
        state = ab.compress(eldritch.START)
        for _ in range(8):
            states[state] = None
            try:
                kernel = ab.kernel(state, rng.choice(actions))
            except ActionError:
                continue
            state = rng.choices(list(kernel), weights=[float(chance) for chance in kernel.values()])[0]
    groups = 0
    for key in dict.fromkeys(map(pattern.key, states)):
        by_view: dict = {}
        for member in pattern.members(key, Mode.ALL):
            by_view.setdefault(pattern.view(member), []).append(member)
        for action in covered:
            for members in by_view.values():
                assert len({_frozen(pushed_through_key(pattern, ab, member, action)) for member in members}) == 1, (key, action)
                groups += 1
    assert groups > 100


def test_on_r04s_quiver_the_model_built_once_per_view_is_the_model_built_at_every_member():
    """R04's quiver, a build counted in pairs both ways (a pair answered by its view still counts): the same keys, rows and kernels, from
    fewer kernels made."""
    data = real_game_data()
    whole = load_target(ROOT / "examples" / "targets" / "r04-penetrating-quiver.yaml", data)
    target = dataclasses.replace(whole, start=StartKind.GIVEN, quality=None)
    methods = ("Deafening Essence of Rage", "annulment-orb", "exalted-orb", "bench-craft", "remove-crafted-mods")
    plan = make_plan(data, target, load_price_file(PRICES), methods=methods, solve_it=False)
    new = pattern_lower_bound(plan.abstraction, plan.start, plan.offers, pieces=PIECES).model
    with every_member():
        old = pattern_lower_bound(plan.abstraction, plan.start, plan.offers, pieces=PIECES).model
    same_model(old, new)
    assert len(new.keys) > 1_000 and new.stats.pairs == old.stats.pairs
    assert new.stats.view_pairs > 1_000 and new.stats.kernels < old.stats.kernels
