"""The side an erasing reroll erases under a lock (#1352): such an action reads, of the ordinary slots, those of the side the lock keeps.

A Chaos Orb, an essence, a fossil set (`Reads.junk` False) keep the fractured mods and the mods of the side a lock keeps, and draw the rest
(`metamods.kept_by_reroll`). The abstraction gave them the whole item at a state with a lock, so the bound's build made the outcomes again at
every member of a key, for every relevant multiset of the side they erase: on R04's model 6, 1,245 fossil sets at thousands of members a key,
15 to 50 s a key. Now the item given to them leaves the erased side out (`Abstraction._kept_sides`), and the build asks one member for each
multiset of the kept side's slots (`Pattern.kept_sides`). The module docstring of `abstraction._pattern` ("The side an erasing reroll
erases") has the lemma; here, on the hand-worked bow with fossils and a lock: every kernel against the one made from the whole item, every
member against the others of its kept slots, and the model built both ways.
"""

import contextlib
import dataclasses
import random

from pattern_support import pushed as pushed_through_key
import test_actions_fossil as fossil_world
from abstraction_removals_support import SL, SPEED_TIER_1
from test_abstraction_pattern import ACTIONS, BOW, EXTRA_PREFIXES, GOAL, LEVEL, OTHER_STARTS, STARTS, build, pattern_data
from test_pattern_items_kept import same_model

from crafting_system.abstraction import Abstraction, Goal, Wanted, _kernel, _pattern
from crafting_system.abstraction._pattern import Mode, Pattern, PatternOffer, build_pattern_model
from crafting_system.actions import ActionError, ApplyFossils
from crafting_system.items import Side

SETS = (("Scorched",), ("Scorched", "Pale"), ("Sanctified", "Lucent"), ("Glyphic",), ("Fractured",), ("Dull", "Jagged", "Serrated"))
FOSSILS = tuple(ApplyFossils(tuple(f"{name} Fossil" for name in names)) for names in SETS)
ERASING = ("chaos", "essence-outside-pool", "essence-in-pool", "reforge-fire", "reforge-caster", "transmute", "alter")  # the world's actions that read no junk


def world_data():
    """The hand-worked bow (`test_abstraction_pattern.pattern_data`: synthetic junk families, the lock crafts) with the fixture fossils that
    add and force no mod of their own (the boots' mods are not on it)."""
    kept = {key: record for key, record in fossil_world.DATA.fossils.items() if record.name and not record.added_mods and not record.forced_mods}
    return dataclasses.replace(pattern_data(), fossils=kept)


def actions():
    return (*ACTIONS.values(), *FOSSILS)


@contextlib.contextmanager
def whole_items():
    """The build and the kernels as they were before #1352: the whole item, at every member."""
    before = _kernel.KEPT_VIEW, _pattern.SHARE_KEPT
    _kernel.KEPT_VIEW, _pattern.SHARE_KEPT = False, False
    try:
        yield
    finally:
        _kernel.KEPT_VIEW, _pattern.SHARE_KEPT = before


def walked_locked_states(ab: Abstraction, seed: int) -> list:
    """The states with a lock that a seeded walk meets from every start (the lock craft is taken first half the time)."""
    data = ab.data
    starts = [ab.compress(build(data, BOW, ids)) for ids in STARTS]
    starts += [ab.compress(build(data, BOW, ids, rarity=rarity)) for ids, rarity in OTHER_STARTS]
    rng = random.Random(seed)
    every = actions()
    states: dict = {}
    for start in starts:
        for walk in range(40):
            state = start
            for step in range(8):
                states[state] = None
                action = ACTIONS["bench-lock"] if step == 0 and walk % 2 else rng.choice(every)
                try:
                    kernel = ab.kernel(state, action)
                except ActionError:
                    continue
                state = rng.choices(list(kernel), weights=[float(chance) for chance in kernel.values()])[0]
    return [state for state in states if ab._holds_lock(state)]


def _answer(ab, state, action):
    try:
        return ab.kernel(state, action)
    except ActionError as error:
        return type(error)


def test_the_kernel_from_the_kept_side_is_the_kernel_of_the_whole_item():
    """Every state with a lock a walk meets, every action that reads no junk: the kernel made from the item without the erased side is the
    kernel made from the whole item, exactly (or the same refusal)."""
    data = world_data()
    new = Abstraction(data, GOAL, BOW, LEVEL, actions(), metamods=True)
    old = Abstraction(data, GOAL, BOW, LEVEL, actions(), metamods=True)
    compared = smaller = kernels = 0
    for state in walked_locked_states(new, 1352):
        for action in (*(ACTIONS[name] for name in ERASING), *FOSSILS):
            kept = new._kept_sides(state, action)
            assert kept == frozenset({Side.PREFIX}) or kept == frozenset({Side.SUFFIX}) or kept is None
            made = _answer(new, state, action)
            with whole_items():
                assert old._kept_sides(state, action) is None
                assert made == _answer(old, state, action), (state, action)
            compared += 1
            smaller += kept is not None and any(slot.side not in kept and not slot.crafted for slot in state.slots)
            kernels += isinstance(made, dict)
    assert compared > 1_000 and smaller > 1_000 and kernels > 200


def test_the_members_of_one_kept_side_give_one_kernel_through_the_key():
    """Every member of every key with a lock a walk meets: the members with the same ordinary slots on the kept side refuse alike or give the
    same kernel through the key, for every action that reads no junk; and those are the actions the build shares so."""
    data = world_data()
    ab = Abstraction(data, GOAL, BOW, LEVEL, actions(), metamods=True)
    pattern = Pattern(ab, True, list(actions()))
    assert {action for action in actions() if not ab._kinds.reads_junk(action)} == {*FOSSILS, *(ACTIONS[name] for name in ERASING)}
    groups = shared = 0
    for key in dict.fromkeys(map(pattern.key, walked_locked_states(ab, 7))):
        for action in actions():
            kept = pattern.kept_sides(action, key)
            assert (kept is not None) == (not ab._kinds.reads_junk(action)), (action, key)
            if kept is None:
                continue
            by_kept: dict = {}
            for member in pattern.members(key, Mode.ALL):
                by_kept.setdefault(pattern.kept_view(member, kept), []).append(member)
            for members in by_kept.values():
                answers = {_frozen(pushed_through_key(pattern, ab, member, action)) for member in members}
                assert len(answers) == 1, (key, action)
                groups += 1
                shared += len(members) - 1
    assert groups > 3_000 and shared > 5_000


def _frozen(found):
    return None if found is None else frozenset(found.items())


def test_the_model_built_once_per_kept_side_is_the_model_built_at_every_member():
    """A complete build from the starts with the suffixes locked, both ways, for a goal that three prefixes give alike (so a key holds
    several multisets of the side a reroll erases): the same keys in the same order, the same rows and kernels (so the same values),
    exact and approximate, with the same pairs counted; without the share no pair is answered by another member's."""
    data = world_data()
    goal = Goal((Wanted(frozenset(name for name, _ in EXTRA_PREFIXES)), SPEED_TIER_1))  # three prefixes alike to it
    names = ("chaos", "essence-in-pool", "reforge-fire", "exalted", "annul", "bench-craft", "remove")
    offers = [PatternOffer(name, ACTIONS[name], 1.0 + n) for n, name in enumerate(names)]
    offers += [PatternOffer("+".join(action.fossils), action, 2.5 + n) for n, action in enumerate(FOSSILS)]
    every = tuple(offer.action for offer in offers)
    shared = built = 0
    for ids in (ids for ids in STARTS if SL in ids):  # the suffixes locked: a reroll erases the prefixes
        for approximate in (False, True):

            def made(before: bool):
                ab = Abstraction(data, goal, BOW, LEVEL, every, metamods=True)
                start = ab.compress(build(data, BOW, ids))
                assert ab._holds_lock(start) and not ab.is_goal(start)
                with whole_items() if before else contextlib.nullcontext():
                    return build_pattern_model(ab, start, offers, tags=True, approximate=approximate)

            old, new = made(True), made(False)
            built += 1
            same_model(old, new)
            assert new.stopped is None and all(new.expanded)
            assert new.stats.pairs == old.stats.pairs and new.stats.refused_pairs == old.stats.refused_pairs
            assert old.stats.kept_pairs == 0
            shared += new.stats.kept_pairs
    assert built == 6 and shared > 1_000
