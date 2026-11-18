"""The fills an action cannot tell apart (#1192): under `ALL` one member stands for the fills of the pure junk that show the action the same.

`ALL` asked an action at every multiset of family types a key's pure junk can hold: about 320 members a key for the Harvest craft that adds
a lightning mod to R17's talisman (it reads of a held family the weight of its lightning mods alone), 5,508 for a Harvest reforge at a key
of R20's helmet with a crafted lock (it reads nothing of the side it erases), each a pair with a kernel of its own. The module docstring
of `abstraction._pattern` ("The fills an action cannot tell apart") has the argument; here the members offered are compared with every
member of a key, and the model built so with the model built at every fill, on the hand-worked world and on the two real items.
"""

import contextlib
import dataclasses
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from test_abstraction_pattern import ACTIONS, BOW, GOAL, LEVEL, STARTS, build, offers_of, pattern_data
from test_pattern_impossible_corner_real import rows_by_key
from test_pattern_items_kept import same_model

from crafting_system.abstraction import Abstraction, _pattern
from crafting_system.abstraction._pattern import NOTHING, Mode, Pattern, build_pattern_model
from crafting_system.actions import NotApplicableError
from crafting_system.cli import make_plan
from crafting_system.items import Side
from crafting_system.planner._pattern_bound import pattern_lower_bound
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
from crafting_system.targets.model import StartKind

CLASSIC_OFFERS = True  # the plans of real routes below are made with the classic offers (`tests/test_classic_offers.py`)
ROOT = Path(__file__).resolve().parents[1]
WORLDS = {
    # the item, the requirements kept, the methods (each world's key holds the tags: a metamod is among them), the build's count of pairs
    "r17": ("r17-lightning-talisman.yaml", slice(0, 2), ("Harvest Add Remove Lightning", "annulment-orb", "regal-orb", "alchemy-orb", "chaos-orb", "transmutation-orb", "Bench craft Prefixes Cannot Be Changed"), 1_500),
    "r20": ("r20-rf-helmet.yaml", slice(1, 3), ("Harvest Reforge Fire", "annulment-orb", "exalted-orb", "Bench craft Prefixes Cannot Be Changed"), 1_500),
}  # fmt: skip
WIDER = 30  # every fill looks at this many times more pairs, at most, for the rows the build at one fill makes


@contextlib.contextmanager
def every_fill():
    """The build as it was before #1192: under `ALL` an action is asked at every fill of the pure junk."""
    before = _pattern.SHARE_ALIKE
    _pattern.SHARE_ALIKE = False
    try:
        yield
    finally:
        _pattern.SHARE_ALIKE = before


@pytest.fixture(scope="module", params=sorted(WORLDS))
def world(request):
    name, kept, methods, pieces = WORLDS[request.param]
    data = real_game_data()
    whole = load_target(ROOT / "examples" / "targets" / name, data)
    target = dataclasses.replace(whole, requirements=whole.requirements[kept], start=StartKind.GIVEN, quality=None)
    return make_plan(data, target, load_price_file(whole.price_file), methods=methods, solve_it=False), pieces


def pushed(pattern: Pattern, ab: Abstraction, member, action):
    """The kernel of `action` at `member` over the keys, or None where the game refuses it."""
    try:
        kernel = ab.kernel(member, action)
    except NotApplicableError:
        return None
    out: dict = defaultdict(Fraction)
    for successor, chance in kernel.items():
        out[pattern.key(successor)] += chance
    return frozenset(out.items())


def locked_keys(pattern: Pattern, ab: Abstraction, model, actions) -> list:
    """The keys a lock craft of `actions` leads to from the first key of the model that holds a prefix and one suffix (none without such a craft)."""
    locks = [action for action in actions if action.label(ab.data).startswith("Bench craft")]
    for key, done in zip(model.keys, model.expanded):
        if done and locks and key.counts[0] >= 1 and key.counts[1] == 1 and not key.crafted and not key.fractured:
            for member in pattern.members(key, Mode.ONE):
                try:
                    return [k for k in map(pattern.key, ab.kernel(member, locks[0])) if pattern.locked_sides(k)]
                except NotApplicableError:
                    continue
    return []


def test_the_members_offered_give_every_kernel_that_every_member_of_the_key_gives(world):
    plan, pieces = world
    ab = plan.abstraction
    actions = [p.offer.action for p in plan.offers if p.offer.action is not None]
    model = pattern_lower_bound(ab, plan.start, plan.offers, pieces=pieces).model
    pattern = Pattern(ab, None, actions)
    fewer = compared = 0
    reached = [key for key, done in zip(model.keys, model.expanded) if done]
    for key in (*locked_keys(pattern, ab, model, actions), *reached):  # a key that holds a lock first, then the keys as met
        if compared >= 6:
            break
        for action in actions:
            mode, _, alike = pattern.asked(action, key)
            if mode is not Mode.ALL or alike is None:
                continue
            offered, every = pattern.members(key, Mode.ALL, alike=alike), pattern.members(key, Mode.ALL)
            if len(offered) == len(every) or len(every) > 400:
                continue
            assert set(offered) <= set(every)
            assert {pushed(pattern, ab, member, action) for member in offered} == {pushed(pattern, ab, member, action) for member in every}, (key, action)
            fewer += len(every) - len(offered)
            compared += 1
    assert compared >= 2 and fewer > 100


def test_the_model_built_at_the_fills_told_apart_is_the_model_built_at_every_fill(world):
    plan, pieces = world
    new = pattern_lower_bound(plan.abstraction, plan.start, plan.offers, pieces=pieces)
    with every_fill():
        old = pattern_lower_bound(plan.abstraction, plan.start, plan.offers, pieces=pieces * WIDER)

    assert new.model.stopped is not None  # stopped by its count, with keys built
    built, before = rows_by_key(new.model), rows_by_key(old.model)
    shared = [key for key in built if key in before]
    assert len(shared) >= 5
    for key in shared:  # a key built both ways has the same row: the same offers, the same kernels over the keys
        assert built[key] == before[key], key
    assert new.model.stats.pairs < old.model.stats.pairs


def test_what_an_action_reads_of_the_pure_junk_is_its_own_declaration(world):
    plan, _ = world
    ab = plan.abstraction
    plan, pieces = world
    actions = {p.offer.label: p.offer.action for p in plan.offers if p.offer.action is not None}
    pattern = Pattern(ab, None, list(actions.values()))
    key = pattern.key(plan.start)
    assert pattern.alike_of(actions["Orb of Annulment"], key) == (NOTHING, NOTHING)  # the count and the class of the junk, by `Reads.families`
    if "Harvest Add Remove Lightning" in actions:
        tags, levels = pattern.alike_of(actions["Harvest Add Remove Lightning"], key)[0]
        assert tags and not levels  # the weight of the mods with the tag it draws by
        assert pattern.alike_of(actions["Regal Orb"], key) == (((), ()), ((), ()))  # the weight of every mod, at the item's level
    else:
        reforge = actions["Harvest Reforge Fire"]
        assert pattern.alike_of(reforge, key) is None  # no lock: its policy is `ANY`, nothing to share
        model = pattern_lower_bound(ab, plan.start, plan.offers, pieces=pieces).model
        locked = locked_keys(pattern, ab, model, list(actions.values()))[0]
        assert pattern.locked_sides(locked) == {Side.PREFIX}
        assert pattern.alike_of(reforge, locked) == (None, NOTHING)  # the side it keeps by type, the side it erases not at all


def test_the_whole_model_of_the_hand_worked_world_is_the_model_built_at_every_fill():
    """A complete build, both ways: the same keys in the same order, the same rows and kernels (so the same values), from fewer pairs."""
    data = pattern_data()

    def made(before: bool):
        ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
        start = ab.compress(build(data, BOW, STARTS[0]))
        with every_fill() if before else contextlib.nullcontext():
            return build_pattern_model(ab, start, offers_of(), tags=True)

    old, new = made(True), made(False)
    same_model(old, new)
    assert new.stopped is None and all(new.expanded)
    assert new.stats.pairs <= old.stats.pairs and new.stats.members <= old.stats.members  # its one `ALL` action is the Fracturing Orb, told apart by type
