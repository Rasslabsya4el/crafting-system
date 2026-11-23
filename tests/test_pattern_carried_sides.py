"""The sides an action reads only as carried (#1192): a Beastcraft side swap is asked once at a key for each multiset of the views of the
ordinary slots of the side it removes from, with the slots of the side it adds to as they are.

The swap was asked at every member of a key (`ALL`), each a kernel key and a kernel built from one item per mod of its pool: on R04's
15 offers 466 of the first 600 s of the bound's build, 238,509 pairs for 65,670 distinct carried views. The module docstring of
`abstraction._pattern` ("The sides an action carries") has the lemma and its argument; here the members of one carried view are compared
by brute force on the hand-worked world, the model built once per carried view with the model built at every member (the hand-worked world
and R04's quiver), and the view itself on members made by hand.
"""

import contextlib
import dataclasses
import random
from pathlib import Path

from abstraction_support import real_game_data
from pattern_support import pushed as pushed_through_key
from test_abstraction_pattern import ACTIONS, BOW, ESSENCE_ONLY, EXTRA_SUFFIXES, GOAL, LEVEL, STARTS, build, pattern_data
from test_pattern_items_kept import same_model
from test_pattern_member_views import _frozen, walked_states

from crafting_system.abstraction import Abstraction, _pattern
from crafting_system.abstraction._pattern import Pattern, PatternOffer, _Carried, build_pattern_model
from crafting_system.abstraction._state import CompressedState, Slot
from crafting_system.actions import ActionError
from crafting_system.actions.beast_mods import BeastSideSwap
from crafting_system.cli import make_plan
from crafting_system.items import Side
from crafting_system.planner._pattern_bound import pattern_lower_bound
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
from crafting_system.targets.model import StartKind

CLASSIC_OFFERS = True  # the plans of real routes below are made with the classic offers (`tests/test_classic_offers.py`)
ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
SWAPS = (BeastSideSwap(Side.PREFIX, beast_level=80), BeastSideSwap(Side.SUFFIX, beast_level=80), BeastSideSwap(Side.PREFIX), BeastSideSwap(Side.SUFFIX))
PIECES = 20_000  # the pairs of the counted build on R04's quiver


@contextlib.contextmanager
def every_member():
    """The build as it was before #1192's carried sides: a side swap is asked at every member of its policy."""
    before = _pattern.SHARE_CARRIED
    _pattern.SHARE_CARRIED = False
    try:
        yield
    finally:
        _pattern.SHARE_CARRIED = before


def world():
    data = pattern_data()
    actions = (*ACTIONS.values(), *SWAPS)
    ab = Abstraction(data, GOAL, BOW, LEVEL, actions, metamods=True)
    return data, ab, Pattern(ab, True, list(actions))


def test_a_side_swap_carries_the_side_it_removes_from_and_no_other_action_carries_a_side():
    data = pattern_data()
    assert [swap.reads(data).carried for swap in SWAPS[:2]] == [frozenset({Side.SUFFIX}), frozenset({Side.PREFIX})]
    assert all(not action.reads(data).carried for action in ACTIONS.values())
    _, ab, pattern = world()
    key = pattern.key(ab.compress(build(data, BOW, STARTS[0])))
    assert pattern.carried_sides(SWAPS[0], key) == _Carried(frozenset({Side.SUFFIX}), frozenset())
    assert pattern.carried_sides(ACTIONS["exalted"], key) is None
    with every_member():
        assert pattern.carried_sides(SWAPS[0], key) is None


def test_a_swap_that_declares_no_draw_carries_no_side(monkeypatch):
    """Where the pool at the beast's level holds a family on both sides the swap declares no draw (`added_draw`): nothing is carried."""
    data, ab, pattern = world()
    key = pattern.key(ab.compress(build(data, BOW, STARTS[0])))
    monkeypatch.setattr(BeastSideSwap, "added_draw", lambda self, data, item: None)
    assert pattern.carried_sides(SWAPS[0], key) is None


def essence_world():
    """The hand-worked world with the essence's forced prefix (outside the pool) of the family of a suffix the pool holds: that prefix takes
    the suffix out of a swap's draw (the checker's case of #1192)."""
    data = pattern_data()
    family = EXTRA_SUFFIXES[0][0]
    data = dataclasses.replace(data, mods={**data.mods, ESSENCE_ONLY: dataclasses.replace(data.mods[ESSENCE_ONLY], families=(family,))})
    actions = (*ACTIONS.values(), *SWAPS[:2])
    ab = Abstraction(data, GOAL, BOW, LEVEL, actions, metamods=True)
    return data, ab, Pattern(ab, True, list(actions))


def _walked(ab: Abstraction, actions, seed: int) -> list:
    """`walked_states` for the essence world, whose made-up family makes some kernels no item (`ValueError`): a walk stops there."""
    rng = random.Random(seed)
    states: dict = {}
    for start in [ab.compress(build(ab.data, BOW, ids)) for ids in STARTS]:
        for _ in range(40):
            state = start
            for _ in range(8):
                states[state] = None
                try:
                    kernel = ab.kernel(state, rng.choice(actions))
                except ActionError:
                    continue
                except ValueError:
                    break
                state = rng.choices(list(kernel), weights=[float(chance) for chance in kernel.values()])[0]
    return list(states)


def test_a_carried_slot_of_a_family_the_draw_holds_is_read_as_it_is():
    """The essence's prefix shares a family with the suffix pool: the swap that adds a suffix reads its kind; the other swap reads no kind."""
    data, ab, pattern = essence_world()
    key = pattern.key(ab.compress(build(data, BOW, STARTS[0])))
    kind = _pattern._base(ab.kind_of(data.mods[ESSENCE_ONLY]))
    assert pattern.carried_sides(SWAPS[1], key).blockers == {kind}  # adds a suffix, carries the prefixes
    assert pattern.carried_sides(SWAPS[0], key).blockers == frozenset()


def test_on_the_essence_world_the_members_of_one_carried_view_give_one_kernel():
    """Every member of every key a seeded walk meets: with that prefix read as it is, the members of one carried view give one kernel (as
    the prefix's view alone they did not: 110 of 2,161 groups differed)."""
    data, ab, pattern = essence_world()
    groups = blocked = 0
    for key in dict.fromkeys(map(pattern.key, _walked(ab, [*ACTIONS.values(), *SWAPS[:2]], 1192))):
        for swap in SWAPS[:2]:
            carried = pattern.carried_sides(swap, key)
            by_view: dict = {}
            for member in pattern.members(key, *pattern.asked(swap, key)):
                by_view.setdefault(pattern.carried_view(member, carried), []).append(member)
            for view, members in by_view.items():
                try:
                    answers = {_frozen(pushed_through_key(pattern, ab, member, swap)) for member in members}
                except ValueError:  # the made-up family gives the essence's prefix a type the pool lacks: no item there
                    continue
                assert len(answers) == 1, (key, swap)
                groups += 1
                blocked += any(_pattern._base(slot.kind) in carried.blockers for slot in view[1])
    assert groups > 1_000 and blocked > 50


def test_the_carried_view_holds_what_the_key_reads_of_a_carried_slot_and_the_other_side_whole():
    """Members made by hand: two suffixes of one view but other kinds give one carried view of the suffix side; two prefixes of one view but
    other kinds do not."""
    _, _, pattern = world()
    zero = pattern.zero
    p1, p2 = Slot(Side.PREFIX, "~1", zero), Slot(Side.PREFIX, "~2", zero)
    s1, s2 = Slot(Side.SUFFIX, "~3", zero), Slot(Side.SUFFIX, "~4", zero)

    def member(*slots):
        return CompressedState(None, (), (), tuple(slots))

    carried = _Carried(frozenset({Side.SUFFIX}), frozenset())
    assert pattern.carried_view(member(p1, s1), carried) == pattern.carried_view(member(p1, s2), carried)
    assert pattern.carried_view(member(p1, s1), carried) != pattern.carried_view(member(p2, s1), carried)
    assert pattern.carried_view(member(p1, s1), carried) == (frozenset({((Side.SUFFIX, (), zero), 1)}), (p1,))
    crafted = Slot(Side.SUFFIX, "~3", zero, crafted=True)  # a crafted slot is the key's: it is in no view
    assert pattern.carried_view(member(p1, crafted), carried) == (frozenset(), (p1,))
    blocking = _Carried(frozenset({Side.SUFFIX}), frozenset({"~3"}))  # a kind some mod of a family of the draw's pool has: read as it is
    assert pattern.carried_view(member(p1, s1), blocking) == (frozenset(), (p1, s1))
    assert pattern.carried_view(member(p1, s1), blocking) != pattern.carried_view(member(p1, s2), blocking)


def test_on_the_hand_worked_world_the_members_of_one_carried_view_give_one_kernel():
    """Every member a side swap is asked at, at every key a seeded walk meets: the members with the same carried view refuse alike or give
    the same kernel through the key."""
    _, ab, pattern = world()
    groups = shared = taken = 0
    for key in dict.fromkeys(map(pattern.key, walked_states(ab, [*ACTIONS.values(), *SWAPS], 1192))):
        for swap in SWAPS:
            sides = pattern.carried_sides(swap, key)
            assert sides is not None
            by_view: dict = {}
            for member in pattern.members(key, *pattern.asked(swap, key)):
                by_view.setdefault(pattern.carried_view(member, sides), []).append(member)
            for members in by_view.values():
                answers = {_frozen(pushed_through_key(pattern, ab, member, swap)) for member in members}
                assert len(answers) == 1, (key, swap)
                groups += 1
                shared += len(members) - 1
                taken += answers != {None}
    assert groups > 1_000 and shared > 2_000 and taken > 500


def test_the_whole_model_of_the_hand_worked_world_is_the_model_built_at_every_member():
    """A complete build from several starts, both ways: the same keys in the same order, the same rows and kernels (so the same values),
    exact and approximate, from fewer kernels."""
    data = pattern_data()
    names = ("annul", "remove", "exalted", "chaos", "bench-lock", "bench-craft")
    offers = [PatternOffer(name, ACTIONS[name], 1.0 + n) for n, name in enumerate(names)]
    offers += [PatternOffer(swap.label(data) + swap.variant, swap, 2.5 + n) for n, swap in enumerate(SWAPS[:2])]
    shared = 0
    for ids in STARTS[:2]:
        for approximate in (False, True):

            def made(before: bool):
                ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(offer.action for offer in offers), metamods=True)
                start = ab.compress(build(data, BOW, ids))
                with every_member() if before else contextlib.nullcontext():
                    return build_pattern_model(ab, start, offers, tags=True, approximate=approximate)

            old, new = made(True), made(False)
            same_model(old, new)
            assert new.stopped is None and all(new.expanded)
            assert new.stats.pairs == old.stats.pairs and new.stats.refused_pairs == old.stats.refused_pairs
            assert new.stats.kernels < old.stats.kernels
            shared += new.stats.view_pairs - old.stats.view_pairs
    assert shared > 500


def test_on_r04s_quiver_the_bound_built_once_per_carried_view_is_the_bound_built_at_every_member():
    """R04's quiver with the two side swaps, a build counted in pairs both ways (a pair answered by its carried view still counts): the same
    keys, rows and kernels, the same start value to the last bit, from fewer kernels made."""
    data = real_game_data()
    whole = load_target(ROOT / "examples" / "targets" / "r04-penetrating-quiver.yaml", data)
    target = dataclasses.replace(whole, start=StartKind.GIVEN, quality=None)
    methods = ("Deafening Essence of Rage", "annulment-orb", "exalted-orb", "bench-craft", "beast-side-swap")
    plan = make_plan(data, target, load_price_file(PRICES), methods=methods, solve_it=False)
    assert sum(isinstance(offer.offer.action, BeastSideSwap) for offer in plan.offers) == 2
    new = pattern_lower_bound(plan.abstraction, plan.start, plan.offers, pieces=PIECES)
    with every_member():
        old = pattern_lower_bound(plan.abstraction, plan.start, plan.offers, pieces=PIECES)
    same_model(old.model, new.model)
    assert new.start_value == old.start_value
    assert len(new.model.keys) > 300 and new.model.stats.pairs == old.model.stats.pairs
    assert new.model.stats.view_pairs > old.model.stats.view_pairs + 1_000 and new.model.stats.kernels < old.model.stats.kernels
