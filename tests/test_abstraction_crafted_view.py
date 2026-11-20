"""The crafted mods an erasing reroll erases (#1358): such an action reads, of the crafted mods, the metamods alone.

A Chaos Orb, an essence, a fossil set, a Harvest reforge, an Alteration (`Reads.junk` False, `Adds.keeps_crafted` False) erase the ordinary
and the crafted mods: what they leave of an item with no lock is its fractured mods (`metamods.kept_by_reroll`), and their refusals read the
metamods (a blocking metamod, an Attack or Caster metamod). The abstraction gave them the item with every crafted mod, so on R04's model 6
the 1,132 fossil sets were prepared again at every key whose one crafted mod differed (23 views at 36 keys, one kernel key each). Now the
item given to them leaves out the crafted mods that hold no metamod (`Abstraction._reads_crafted`, `CRAFTED_VIEW`). The docstring of
`Abstraction.kernel_key` (step 1) has the lemma; here, on the hand-worked bow with fossils and every metamod: every kernel against the one
made from the item with its crafted mods, every state against the others of its view, and the model built both ways.
"""

import contextlib
import random

import pytest
from test_abstraction_pattern import ACTIONS, BOW, LEVEL, OTHER_STARTS, STARTS, GOAL, build
from test_pattern_items_kept import same_model
from test_pattern_kept_sides import ERASING, FOSSILS, actions, world_data

from crafting_system.abstraction import Abstraction, _kernel
from crafting_system.abstraction._pattern import PatternOffer, build_pattern_model
from crafting_system.actions import ActionError


@contextlib.contextmanager
def every_crafted_mod():
    """The kernels as they were before #1358: an erasing reroll is given every crafted mod."""
    before = _kernel.CRAFTED_VIEW
    _kernel.CRAFTED_VIEW = False
    try:
        yield
    finally:
        _kernel.CRAFTED_VIEW = before


def _answer(ab, state, action):
    try:
        return ab.kernel(state, action)
    except ActionError as error:
        return type(error)


def walked_states(ab: Abstraction, seed: int) -> list:
    """The states a seeded walk meets from every start, a bench craft (the crafted mod, or a metamod) taken first half the time."""
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
                action = (ACTIONS["bench-craft"], ACTIONS["bench-lock"])[walk % 4 // 2] if step == 0 and walk % 2 else rng.choice(every)
                try:
                    kernel = ab.kernel(state, action)
                except ActionError:
                    continue
                state = rng.choices(list(kernel), weights=[float(chance) for chance in kernel.values()])[0]
    return list(states)


def _plain_crafted(ab: Abstraction, state) -> bool:
    return any(slot.crafted and not ab._is_metamod(slot.kind) for slot in state.slots)


@pytest.mark.parametrize("metamods", [False, True], ids=["no-metamods", "metamods"])
def test_the_kernel_without_the_plain_crafted_mods_is_the_kernel_of_the_whole_item(metamods):
    """Every state a walk meets, every action that reads no junk and erases the crafted mods: where it erases the ordinary mods, the kernel
    made from the item without the crafted mods that hold no metamod is the kernel made with them, exactly (or the same refusal)."""
    data = world_data()
    new = Abstraction(data, GOAL, BOW, LEVEL, actions(), metamods=metamods)
    old = Abstraction(data, GOAL, BOW, LEVEL, actions(), metamods=metamods)
    erasing = (*(ACTIONS[name] for name in ERASING), *FOSSILS)
    # every action that reads no junk erases the crafted mods too (Remove Crafted Mods does not declare `keeps_crafted` either, but reads the junk)
    assert {action for action in actions() if not new._kinds.reads_junk(action) and not new._reads_crafted(action)} == set(erasing)
    compared = smaller = kernels = 0
    for state in walked_states(new, 1358):
        for action in erasing:
            made = _answer(new, state, action)
            with every_crafted_mod():
                assert old._reads_crafted(action)
                assert made == _answer(old, state, action), (state, action)
            compared += 1
            plain = new._erases(state, action) and _plain_crafted(new, state)
            smaller += plain
            kernels += plain and isinstance(made, dict)
    assert compared > 3_000 and smaller > 300 and kernels > 100


def test_the_states_of_one_view_give_one_kernel():
    """The states a walk meets that differ only in crafted mods holding no metamod: each erasing reroll refuses them alike or gives them the
    same kernel, and the abstraction prepares the pair once for them all."""
    data = world_data()
    ab = Abstraction(data, GOAL, BOW, LEVEL, actions(), metamods=True)
    groups: dict = {}
    for state in walked_states(ab, 58):
        for action in (*(ACTIONS[name] for name in ERASING), *FOSSILS):
            if ab._erases(state, action):
                groups.setdefault((action, ab._view(state, True, None, False)), []).append(state)
    shared = 0
    for (action, _), states in groups.items():
        answers = {_frozen(_answer(ab, state, action)) for state in states}
        assert len(answers) == 1, (action, states)
        shared += len({tuple(slot for slot in state.slots if slot.crafted) for state in states}) - 1
    assert shared > 50


def _frozen(found):
    return frozenset(found.items()) if isinstance(found, dict) else found


@pytest.mark.parametrize("approximate", [False, True], ids=["exact", "approximate"])
def test_the_model_built_with_the_plain_crafted_mods_left_out_is_the_same(approximate):
    """A complete build from the starts with a bench craft, the rerolls and the fossil sets offered, both ways: the same keys, rows and kernels,
    and fewer pairs prepared."""
    data = world_data()
    names = ("chaos", "essence-in-pool", "reforge-fire", "exalted", "annul", "bench-craft", "remove")
    offers = [PatternOffer(name, ACTIONS[name], 1.0 + n) for n, name in enumerate(names)]
    offers += [PatternOffer("+".join(action.fossils), action, 2.5 + n) for n, action in enumerate(FOSSILS)]
    every = tuple(offer.action for offer in offers)
    built = 0
    for ids in STARTS[:2]:

        def made(before: bool):
            ab = Abstraction(data, GOAL, BOW, LEVEL, every, metamods=True)
            start = ab.compress(build(data, BOW, ids))
            with every_crafted_mod() if before else contextlib.nullcontext():
                return build_pattern_model(ab, start, offers, tags=True, approximate=approximate)

        old, new = made(True), made(False)
        same_model(old, new)
        assert new.stopped is None and all(new.expanded)
        assert new.stats.pairs == old.stats.pairs and new.stats.kernels == old.stats.kernels
        built += 1
    assert built == 2
