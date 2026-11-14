"""The actions that read the ordinary mods are given one item for each state, and derived items skip only checks they cannot fail (ticket #935).

On the generated models of `test_kernel_projection.py` (bows with random mods, metamods and fractured mods, three pools, a random walk
through every kind of action, the Fracturing Orb added):

* the kernel of every action at every state equals, exactly, that of the reference (`Abstraction.share_items = False`: every
  prepared pair builds and validates its own item, as before the ticket), a refused key is the same refusal, and one key
  has one kernel;
* at one state, every action that reads the ordinary mods is given the same item, built once.
"""

import pytest
from test_kernel_projection import ACTIONS, CASES, READERS, answer, counted, generated, model, refused

from crafting_system.actions import FracturingOrb

WITH_FRACTURE = (*ACTIONS, FracturingOrb())


def reference(data):
    ab = model(data, WITH_FRACTURE)
    ab.share_items = False
    return ab


@pytest.mark.parametrize(("name", "seed"), CASES)
def test_the_kernels_of_the_shared_item_are_the_kernels_of_an_item_per_action(name, seed):
    data, ab, states = generated(name, seed, WITH_FRACTURE)
    old = reference(data)
    by_key: dict = {}
    for state in states:
        for action in ab.enabled:
            made = answer(lambda: ab.kernel(state, action))
            assert made == answer(lambda: old.kernel(state, action)), (state, action)
            key = answer(lambda: ab.kernel_key(state, action))
            old_key = answer(lambda: old.kernel_key(state, action))
            assert refused(key) == refused(old_key) and (not refused(key) or key == old_key), (state, action)  # the same refusal
            if isinstance(made, dict) and not refused(key):
                assert by_key.setdefault(key, made) == made, (state, action)  # one key, one kernel (the numbers of a key are its abstraction's)
        ab.release_prepared(keep_erased=True)
        old.release_prepared(keep_erased=True)
    assert len(states) > 20


def test_some_case_fractures():
    """The cases above reach states a Fracturing Orb works on, so its results are compared too."""
    found = 0
    for name, seed in CASES:
        _, ab, states = generated(name, seed, WITH_FRACTURE)
        for state in states:
            found += isinstance(answer(lambda: ab.kernel(state, FracturingOrb())), dict)
            ab.release_prepared(keep_erased=True)
    assert found > 0


@pytest.mark.parametrize("name", ["tiny", "bow"])
def test_the_readers_of_one_state_share_one_item(name, monkeypatch):
    data, ab, states = generated(name, 4, steps=80)
    ab.release_prepared()
    calls = counted(ab, monkeypatch)
    readers = [action for action in ab.enabled if action in READERS]
    assert len(readers) > 2
    built = 0
    for state in states:
        before = calls["_item_of"]
        for action in readers:
            answer(lambda: ab.kernel_key(state, action))
        built += calls["_item_of"] - before
        assert calls["_item_of"] - before <= 1, state  # one item, whatever the number of readers
        ab.release_prepared(keep_erased=True)
    assert built > len(states) / 2
