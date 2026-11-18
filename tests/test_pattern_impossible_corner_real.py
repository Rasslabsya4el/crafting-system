"""The impossible corner (#1192): a composition whose lightest fill is no item is offered, under `ANY` and `ONE`, at one fill that is.

On a Shaper and Elder Eternal Burgonet (R20's helmet) the one family of critical strike chance for socketed gems holds an attack mod and
a caster mod, so with the protected tags in the key it is the lightest kind of two classes at once, and the lightest member of a key that
holds one suffix of each is no item. The build then offered every fill of the composition (hundreds to thousands of members a key, each a
pair of every offer) where one stands for them all. The module docstring of `abstraction._pattern` ("The impossible corner") has the
argument; here the one member is compared with every member of the key, and the model built so with the model built at every fill.
"""

import contextlib
import dataclasses
import random
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from pattern_support import check_dominates
from test_abstraction_pattern import ACTIONS, BOW, GOAL, LEVEL, STARTS, build, offers_of, pattern_data
from test_pattern_items_kept import same_model

from crafting_system.abstraction import Abstraction, _pattern
from crafting_system.abstraction._pattern import Mode, Pattern, build_pattern_model
from crafting_system.cli import make_plan
from crafting_system.planner._pattern_bound import pattern_lower_bound
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
from crafting_system.targets.model import StartKind

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "targets" / "r20-rf-helmet.yaml"
METHODS = ("annulment-orb", "exalted-orb", "wild-bristle-matron", "Bench craft Suffixes Cannot Be Changed")  # metamods: the key holds the tags
PIECES = 4_000  # the build's count of pairs: it stops there, at every fill and at one alike in what it has built (the whole build takes minutes)


@contextlib.contextmanager
def every_fill():
    """The build as it was before #1192: a composition whose corner is no item is offered at every fill, under every policy."""
    before = _pattern.SHARE_FILLS
    _pattern.SHARE_FILLS = False
    try:
        yield
    finally:
        _pattern.SHARE_FILLS = before


@pytest.fixture(scope="module")
def plan():
    data = real_game_data()
    whole = load_target(TARGET, data)
    target = dataclasses.replace(whole, requirements=whole.requirements[1:3], start=StartKind.GIVEN)  # two rolled mods of the pool, a held helmet
    return make_plan(data, target, load_price_file(whole.price_file), methods=METHODS, solve_it=False)


def corner_key(pattern: Pattern, plan):
    """A key with one prefix and one suffix of each protected-tag class, read off an item: its lightest suffixes share their one family."""
    from crafting_system.items import ExplicitMod, Influence, Item, Rarity

    data = plan.abstraction.data
    low = lambda mod_id: tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)  # noqa: E731
    mods = ("IncreasedLife1", "FireResist1", "IncreasedAccuracyNew1_", "SocketedSpellCriticalStrikeChanceUber1_")  # no tag, no tag, attack, caster
    item = Item.build(
        data, base_id=plan.target.base_id, item_level=plan.target.item_level, rarity=Rarity.RARE,
        influences=frozenset({Influence.SHAPER, Influence.ELDER}), mods=tuple(ExplicitMod(mod_id, low(mod_id)) for mod_id in mods),
    )  # fmt: skip
    return pattern.key(plan.abstraction.compress(item))


def test_one_fill_stands_for_every_fill_of_a_composition_whose_lightest_is_no_item(plan):
    ab = plan.abstraction
    actions = [p.offer.action for p in plan.offers if p.offer.action in ab.enabled]
    pattern = Pattern(ab, None, actions)
    key = corner_key(pattern, plan)
    assert key.tags is not None and len(key.tags) == 4  # a prefix, and a suffix of each of three classes

    one = pattern.members(key, Mode.ONE)
    with every_fill():
        every = Pattern(ab, None, actions).members(key, Mode.ONE)

    assert pattern.fallbacks > 0  # the lightest fill of some composition is no item
    assert set(one) <= set(every) and 20 * len(one) < len(every)
    assert len(pattern.members(key, Mode.ANY)) == 1
    rng = random.Random(1192)
    compared = 0
    for action in actions:
        if pattern.mode_of(action, key) is Mode.ONE and not pattern.named_of(action, key):
            members, offered = check_dominates(pattern, ab, key, action, Mode.ONE, rng, trials=10)
            assert members > len(one)
            compared += offered > 0
    assert compared >= 2  # the Annulment and the Matron at least: each one member's kernel is no worse than any member's


def rows_by_key(model) -> dict:
    """The model's rows as keys, not numbers (the order keys are met in follows the members asked): key -> {(offer, its kernel over keys)}."""

    def kernel(number: int) -> frozenset:
        successors, weights = model.kernels[number]
        return frozenset((model.keys[successor], weight) for successor, weight in zip(successors, weights))

    return {model.keys[i]: {(offer, kernel(number)) for offer, number in model.actions[i]} for i, done in enumerate(model.expanded) if done}


def test_the_model_built_at_one_fill_is_the_model_built_at_every_fill(plan):
    new = pattern_lower_bound(plan.abstraction, plan.start, plan.offers, pieces=PIECES)
    with every_fill():
        old = pattern_lower_bound(plan.abstraction, plan.start, plan.offers, pieces=PIECES * 25)  # every fill looks at more pairs for the same rows

    assert new.model.stats.fallbacks > 0
    assert new.model.stopped is not None  # stopped by its count, with keys built
    built, before = rows_by_key(new.model), rows_by_key(old.model)
    shared = [key for key in built if key in before]
    assert len(shared) > 20
    for key in shared:  # a key built both ways has the same row: the same offers, the same kernels over the keys
        assert built[key] == before[key], key
    assert new.model.stats.pairs < old.model.stats.pairs


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
    assert new.stats.fallbacks > 100  # the corner is met at hundreds of compositions of this world
    assert new.stats.pairs < old.stats.pairs and new.stats.members < old.stats.members
