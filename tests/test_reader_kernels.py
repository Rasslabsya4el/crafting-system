"""The actions that read the ordinary mods are given one item for each state, and derived items skip only checks they cannot fail (ticket #935).

On the generated models of `test_kernel_projection.py` (bows with random mods, metamods and fractured mods, three pools, a random walk
through every kind of action, the Fracturing Orb added):

* the kernel of every action at every state equals, exactly, that of the reference (`Abstraction.share_items = False`: every
  prepared pair builds and validates its own item, and `Item.changed` checks every derived item, as before the ticket), a refused key is the same refusal, and one key
  has one kernel;
* at one state, every action that reads the ordinary mods is given the same item, built once;
* a removal or a fracture of a validated item, made without the checks, is the item made with them and passes them all; an item never
  validated, or one changed in another field, is checked as before.
"""

import contextlib
import random

import pytest
from test_kernel_projection import ACTIONS, CASES, READERS, WORLDS, answer, counted, generated, model, random_items, refused

from crafting_system.actions import AnnulmentOrb, FracturingOrb
from crafting_system.actions.bench import RemoveCraftedMods
from crafting_system.items import Item, ItemError
from crafting_system.items import model as item_model

WITH_FRACTURE = (*ACTIONS, FracturingOrb())


def reference(data):
    ab = model(data, WITH_FRACTURE)
    ab.share_items = False
    return ab


@contextlib.contextmanager
def every_check():
    """Every derived item validated, as before the ticket: `Item.changed` never skips the checks."""
    kept = item_model._kept_from
    item_model._kept_from = lambda before, after: False
    try:
        yield
    finally:
        item_model._kept_from = kept


def old_answer(call):
    with every_check():
        return answer(call)


@pytest.mark.parametrize(("name", "seed"), CASES)
def test_the_kernels_of_the_shared_item_are_the_kernels_of_an_item_per_action(name, seed):
    data, ab, states = generated(name, seed, WITH_FRACTURE)
    old = reference(data)
    by_key: dict = {}
    for state in states:
        for action in ab.enabled:
            made = answer(lambda: ab.kernel(state, action))
            assert made == old_answer(lambda: old.kernel(state, action)), (state, action)
            key = answer(lambda: ab.kernel_key(state, action))
            old_key = old_answer(lambda: old.kernel_key(state, action))
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


DERIVING = (AnnulmentOrb(), FracturingOrb(), RemoveCraftedMods())


@pytest.mark.parametrize("name", sorted(WORLDS))
def test_a_derived_item_made_without_the_checks_is_the_checked_item_and_passes_them(name):
    data = WORLDS[name]
    derived = 0
    for item in random_items(data, random.Random(7), 120):
        for action in DERIVING:
            made = answer(lambda: action.outcomes(data, item))
            with every_check():
                checked = answer(lambda: action.outcomes(data, item))
            if refused(made):
                assert made == checked
                continue
            results = [part.retained for _, part in made.components]
            assert results == [part.retained for _, part in checked.components]
            for result in results:
                result.validate(data)  # the checks skipped would have passed
                derived += getattr(result, "_valid_in", None) is data
    assert derived > 100


def test_an_item_never_validated_or_changed_elsewhere_is_checked():
    data = WORLDS["bow"]
    item = random_items(data, random.Random(3), 1)[0]
    raw = Item(item.base_id, item.item_level, item.rarity, item.mods)  # constructed, never validated
    assert getattr(raw, "_valid_in", None) is None
    assert getattr(raw.remove_mod(data, raw.mods[0].mod_id), "_valid_in", None) is data  # it was checked, and passed
    wrong = Item(item.base_id, item.item_level, item.rarity, (*item.mods, item.mods[0].__class__("no such mod", ())))
    with pytest.raises(ItemError):
        wrong.remove_mod(data, item.mods[0].mod_id)  # never validated: the checks run and find the unknown mod
    changed = item.changed(data, corrupted=True)  # another field: checked, as before
    assert getattr(changed, "_valid_in", None) is data
