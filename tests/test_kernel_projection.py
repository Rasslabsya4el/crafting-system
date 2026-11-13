"""A kernel and its key are made from the projection of the state by what the action reads (ticket #827).

On generated models: bows of the fixture with random mods, random metamods and random fractured mods, three pools of different sizes and
weights, walked at random through every kind of action the fixture has (rerolls, adds, removals, a fracture, bench crafts of every metamod).

* the kernel made from the projection equals, exactly, the kernel made from the whole state (`Abstraction.project = False`: every slot of
  the state goes to the action whenever a lock could be there, as before the ticket), and a refusal is the same refusal;
* two pairs with one key have one kernel, across states and actions;
* an action is asked for its outcomes once for each projection, however many states share it, and a second state does none of the work that
  grows with the pool (no item is built, no action asked, no family read): the cost is counted in calls, a test reads no clock;
* the pool of an item read off the flat table (`actions.pool._Table`) equals the pool made mod by mod, and the numbered pool signature
  splits the pools exactly as the signature of whole family types does.
"""

import dataclasses
import random
from collections import Counter
from fractions import Fraction

import pytest
from abstraction_removals_support import (
    AS_5,
    BOW,
    BOW_DATA,
    CASTER,
    CRAFT,
    FIRE,
    FIRE_RES,
    GOAL,
    HUNTER_MID_DATA,
    LEVEL,
    MM,
    NA,
    NC,
    PL,
    SL,
    SOCKET,
    TINY_DATA,
    build,
)

from crafting_system.abstraction import Abstraction
from crafting_system.abstraction import _kernel as kernel_module
from crafting_system.actions import (
    AnnulmentOrb,
    BenchCraft,
    ChaosOrb,
    ExaltedOrb,
    HarvestReforge,
    NotApplicableError,
    OutOfScopeError,
    ScouringOrb,
    allowed_by_tags,
    build_pool,
    partners,
)
from crafting_system.actions import pool as pool_module
from crafting_system.actions.bench import RemoveCraftedMods
from crafting_system.actions.metamods import blocked_tags
from crafting_system.actions.pool import Candidate, _admitted, group_pool, item_tags, pool_candidates
from crafting_system.items import Item, ItemError, Side

REROLLS = (ChaosOrb(), HarvestReforge("attack"), ScouringOrb())
BENCH = {option.actions.add_explicit_mod for option in BOW_DATA.bench_options}
READERS = (ExaltedOrb(), AnnulmentOrb(), RemoveCraftedMods(), *(BenchCraft(mod_id) for mod_id in (PL, SL, NA, NC, MM, CRAFT) if mod_id in BENCH))
ACTIONS = (*REROLLS, *READERS)
WORLDS = {"bow": BOW_DATA, "tiny": TINY_DATA, "hunter-mid": HUNTER_MID_DATA}
METAMODS = (PL, SL, NA, NC, MM)


def reweighed(data, seed: int):
    """`data` with the weight of every drawable mod of the bow drawn anew (1 to 3 times a round figure), so pools differ in their weights."""
    rng = random.Random(seed)
    drawable = {candidate.mod.id for candidate in pool_candidates(data, build(data, BOW, ()))}
    mods = dict(data.mods)
    for mod_id in sorted(drawable):
        mod = mods[mod_id]
        mods[mod_id] = dataclasses.replace(mod, spawn_weights=(dataclasses.replace(mod.spawn_weights[0], weight=rng.choice((250, 500, 1000, 1500))), *mod.spawn_weights[1:]))
    return dataclasses.replace(data, mods=mods)


def random_items(data, rng: random.Random, count: int) -> list[Item]:
    """Legal rare bows with up to five drawable mods of distinct families, maybe fractured, and up to two crafted mods (metamods among them)."""
    drawable = [candidate.mod.id for candidate in pool_candidates(data, build(data, BOW, ()))]
    crafted = [mod_id for mod_id in (*METAMODS, CRAFT) if mod_id in data.mods]
    items = []
    while len(items) < count:
        ids = rng.sample(drawable, min(len(drawable), rng.randint(0, 5)))
        ids += rng.sample(crafted, rng.choice((0, 0, 1, 1, 2)))
        fractured = [mod_id for mod_id in ids[:1] if rng.random() < 0.3 and data.mods[mod_id].domain != "crafted"]
        try:
            items.append(build(data, BOW, ids, fractured=fractured))
        except (ItemError, ValueError):
            continue
    return items


def model(data, actions=ACTIONS, *, project: bool = True) -> Abstraction:
    actions = tuple(action for action in actions if not isinstance(action, BenchCraft) or action.mod_id in data.mods)
    ab = Abstraction(data, GOAL, BOW, LEVEL, actions, metamods=True)
    ab.project = project
    return ab


def walked(ab: Abstraction, items, rng: random.Random, actions, steps: int) -> list:
    """The states of `items` and the states a random walk of `steps` kernels reaches from them."""
    states = []
    for item in items:
        try:
            states.append(ab.compress(item))
        except (OutOfScopeError, ValueError):
            continue
    seen = set(states)
    for _ in range(steps):
        state, action = rng.choice(states), rng.choice(actions)
        try:
            successors = sorted(ab.kernel(state, action), key=repr)
        except (NotApplicableError, OutOfScopeError):
            continue
        for found in rng.sample(successors, min(3, len(successors))):
            if found not in seen:
                seen.add(found)
                states.append(found)
        ab.release_prepared(keep_erased=True)
    return states


def answer(call):
    """The result of `call`, or the family and the words of its refusal (or of the `ValueError` of a state that is no item)."""
    try:
        return call()
    except ValueError as refusal:
        return (type(refusal).__name__, str(refusal))


def refused(found) -> bool:
    return isinstance(found, tuple) and len(found) == 2 and found[0] in ("NotApplicableError", "OutOfScopeError", "ValueError")


def generated(name: str, seed: int, actions=ACTIONS, count: int = 12, steps: int = 60):
    rng = random.Random(seed)
    data = reweighed(WORLDS[name], seed) if seed % 2 else WORLDS[name]
    ab = model(data, actions)
    return data, ab, walked(ab, random_items(data, rng, count), rng, ab.enabled, steps)


CASES = [(name, seed) for name in WORLDS for seed in (1, 2)]


@pytest.mark.parametrize(("name", "seed"), CASES)
def test_the_kernel_from_the_projection_is_the_kernel_from_the_whole_state(name, seed):
    data, ab, states = generated(name, seed)
    whole = model(data, project=False)
    by_key: dict = {}
    shared = 0
    for state in states:
        for action in ab.enabled:
            made = answer(lambda: ab.kernel(state, action))
            assert made == answer(lambda: whole.kernel(state, action)), (state, action)
            key = answer(lambda: ab.kernel_key(state, action))
            assert refused(key) == refused(answer(lambda: whole.kernel_key(state, action))), (state, action)
            if isinstance(made, dict) and not refused(key):
                before = by_key.setdefault(key, made)
                shared += before is not made
                assert before == made, (state, action)  # one key, one kernel, whatever the state and the action
        ab.release_prepared(keep_erased=True)
        whole.release_prepared()
    assert len(states) > 20 and shared > 0  # the case has states, and keys that more than one pair has


@pytest.mark.parametrize(("name", "seed"), CASES)
def test_a_refused_key_is_a_refused_kernel_of_the_same_family(name, seed):
    _, ab, states = generated(name, seed, steps=30)
    for state in states:
        for action in ab.enabled:
            key, made = answer(lambda: ab.kernel_key(state, action)), answer(lambda: ab.kernel(state, action))
            if refused(key):
                assert refused(made) and key[0] == made[0], (state, action)  # no kernel where there is no key, and the same family
            assert key == answer(lambda: ab.kernel_key(state, action))  # the second call, from the kept pair, says the same


def counted(ab: Abstraction, monkeypatch) -> Counter:
    """Counts the calls of the work a prepared pair costs: the item of a state, the action's outcomes, the type of a pool family."""
    calls: Counter = Counter()
    for name in ("_item_of", "_outcomes", "_family_type", "_split"):
        original = getattr(ab, name)

        def wrapped(*args, _original=original, _name=name, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(ab, name, wrapped)
    return calls


@pytest.mark.parametrize("name", ["tiny", "bow"])
def test_an_action_is_asked_once_for_each_projection_however_many_states_share_it(name, monkeypatch):
    data, ab, states = generated(name, 3, steps=150)
    ab.release_prepared()  # what the walk kept
    asked = Counter()
    views = set()
    calls = counted(ab, monkeypatch)
    for state in states:
        if ab._holds_lock(state):
            continue  # a reroll reads the mods of an item with a lock: its projection is the whole state
        for action in REROLLS:
            assert ab._erases(state, action)
            answer(lambda: ab.kernel_key(state, action))
            answer(lambda: ab.kernel(state, action))
            views.add((action, ab._view(state, True)))
            asked[action] += 1
        ab.release_prepared(keep_erased=True)
    locked = sum(ab._holds_lock(state) for state in states)
    assert 0 < locked < len(states)  # the case has items with a lock and items without
    assert calls["_outcomes"] == len(views) == calls["_item_of"]  # once for each projection ...
    assert len(views) < sum(asked.values()) / 3  # ... which many states share


def test_a_second_state_of_a_projection_does_no_work_that_grows_with_the_pool(monkeypatch):
    work = {}
    for name in ("tiny", "bow"):
        data = WORLDS[name]
        ab = model(data)
        first, second = (ab.compress(build(data, BOW, ids)) for ids in ((FIRE, AS_5, FIRE_RES), (SOCKET, CASTER, AS_5)))
        assert first != second
        for action in REROLLS:
            ab.kernel_key(first, action)
        ab.release_prepared(keep_erased=True)
        calls = counted(ab, monkeypatch)
        keys = [ab.kernel_key(second, action) for action in REROLLS]
        assert keys == [ab.kernel_key(first, action) for action in REROLLS]
        work[name] = dict(calls)
    assert len(pool_candidates(WORLDS["bow"], build(WORLDS["bow"], BOW, ()))) > 2 * len(pool_candidates(WORLDS["tiny"], build(WORLDS["tiny"], BOW, ())))
    assert work == {"tiny": {}, "bow": {}}  # no item, no outcomes, no family type, no split: the same for a pool many times the size


def test_the_pairs_kept_from_state_to_state_are_bounded(monkeypatch):
    monkeypatch.setattr(kernel_module, "SHARED_PAIRS", 4)
    data, ab, states = generated("tiny", 5, steps=120)
    reference = model(data, project=False)
    for state in states:
        for action in REROLLS:
            assert answer(lambda: ab.kernel(state, action)) == answer(lambda: reference.kernel(state, action))
        ab.release_prepared(keep_erased=True)
        assert len(ab._shared_by) <= 4 and not ab._prepared_by
    ab.release_prepared()
    assert not ab._shared_by


def test_a_lock_is_a_crafted_mod_in_the_game_data():
    """What `_holds_lock` rests on: every mod of a lock's family is of the crafted domain, so an ordinary slot never stands for one."""
    from abstraction_support import real_game_data

    data = real_game_data()
    locks = {"ItemGenerationCannotChangePrefixes", "ItemGenerationCannotChangeSuffixes"}
    held = [mod for mod in data.mods.values() if locks.intersection(mod.families)]
    assert held and all(mod.domain == "crafted" for mod in held)
    ab = Abstraction(BOW_DATA, GOAL, BOW, LEVEL, ACTIONS, metamods=True)
    assert ab._holds_lock(ab.compress(build(BOW_DATA, BOW, (FIRE, PL)))) and not ab._holds_lock(ab.compress(build(BOW_DATA, BOW, (FIRE, NA))))
    loose = dataclasses.replace(BOW_DATA, mods={**BOW_DATA.mods, FIRE: dataclasses.replace(BOW_DATA.mods[FIRE], families=("ItemGenerationCannotChangePrefixes",))})
    other = Abstraction(loose, GOAL, BOW, LEVEL, ACTIONS, metamods=True)
    assert other._holds_lock(other.compress(build(loose, BOW, (AS_5,))))  # a lock outside the crafted domain: no state is taken to be without one


# --- the flat pool table ------------------------------------------------------------------------------------------------------------


def candidates_mod_by_mod(data, item: Item, max_level=None, tag_filter=True) -> tuple[Candidate, ...]:
    """`pool_candidates` as it was before the table: every admitted mod asked whether the item blocks it."""
    base = data.base_items[item.base_id]
    blocked = blocked_tags(data, item) if tag_filter else frozenset()
    level = item.item_level if max_level is None else min(item.item_level, max_level)
    found = []
    for mod, weight in _admitted(data, base, item_tags(data, item), level, ()):
        if item.blocks(data, mod) or not allowed_by_tags(mod, blocked):
            continue
        if len(mod.families) != 1:
            raise OutOfScopeError("more than one family")
        found.append(Candidate(mod, weight, mod.families[0], Side(mod.generation_type)))
    return tuple(found)


@pytest.mark.parametrize(("name", "seed"), CASES)
def test_the_pool_of_the_table_is_the_pool_made_mod_by_mod(name, seed):
    data = reweighed(WORLDS[name], seed)
    rng = random.Random(seed)
    for item in random_items(data, rng, 60):
        for max_level, tag_filter in ((None, True), (None, False), (40, True)):
            pool_module._POOLS.clear()
            expected = candidates_mod_by_mod(data, item, max_level, tag_filter)
            assert pool_candidates(data, item, max_level, tag_filter=tag_filter) == expected
            assert build_pool(data, item, max_level, tag_filter=tag_filter) == group_pool(expected)
            half = lambda mod: Fraction(len(mod.id) % 3, 2)  # noqa: E731  (a factor drops some mods: the pool is grouped anew)
            assert build_pool(data, item, max_level, half, tag_filter=tag_filter) == group_pool(expected, half)


def test_a_mod_of_two_families_is_refused_unless_the_item_blocks_it():
    two = dataclasses.replace(BOW_DATA.mods[SOCKET], families=(*BOW_DATA.mods[SOCKET].families, *BOW_DATA.mods[FIRE].families))
    data = dataclasses.replace(BOW_DATA, mods={**BOW_DATA.mods, SOCKET: two})
    blocking = build(data, BOW, (FIRE, AS_5))  # holds a family of the mod: it is no candidate
    assert pool_candidates(data, blocking) == candidates_mod_by_mod(data, blocking)
    assert build_pool(data, blocking) == group_pool(candidates_mod_by_mod(data, blocking))
    for call in (pool_candidates, build_pool):
        with pytest.raises(OutOfScopeError, match="families"):
            call(data, build(data, BOW, (AS_5,)))


def signature_of_whole_types(ab: Abstraction, part):
    """The pool signature as it was before the numbers: the sorted family types themselves."""
    influences = part.retained.influences
    return (
        part.tag,
        part.guaranteed_blocked,
        len(part.retained.mods),
        part.free[Side.PREFIX],
        part.free[Side.SUFFIX],
        tuple(sorted(part.totals.items())),
        tuple(sorted(ab._family_type(family, part.tag, influences, part.guaranteed_blocked, part.rolls_lucky) for family in part.pool)),
        tuple(sorted(tuple(sorted(ab._family_type(side, part.tag, influences, part.guaranteed_blocked) for side in sides)) for sides in partners(part.pool).values())),
    )


@pytest.mark.parametrize(("name", "seed"), CASES)
def test_the_numbered_signature_splits_the_pools_as_the_family_types_do(name, seed):
    _, ab, states = generated(name, seed)
    numbered, whole = [], []
    for state in states:
        for action in (ChaosOrb(), HarvestReforge("attack"), ExaltedOrb()):
            try:
                prepared = ab._prepared(state, action)
            except (NotApplicableError, OutOfScopeError):
                continue
            for (_, part), signature in zip(prepared.outcomes.components, ab._signatures_of(prepared)):
                if hasattr(part, "pool"):
                    numbered.append(signature)
                    whole.append(signature_of_whole_types(ab, part))
        ab.release_prepared(keep_erased=True)
    assert len(set(whole)) > 3
    groups: dict = {}
    for mine, theirs in zip(numbered, whole):
        assert groups.setdefault(mine, theirs) == theirs  # one number, one signature of whole types ...
    assert len(set(numbered)) == len(set(whole))  # ... and as many of the one as of the other
