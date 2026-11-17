"""The bound's build builds the item of a member once, however many offers it asks there (ticket #1170).

The build asks every offer of a key at every member of it, offer after offer (`PatternBuilder._offers_of_key`). The items of the views
(`Abstraction._item_of_view`) were kept 64 at most, the oldest leaving first, so a key of more members went through them in a cycle and built
every item anew for each offer (R05 at N = 10,000: 1,000,318 items for 1,000,535 keys asked). They are now kept as long as the pairs, the
mod a slot stands for is found once (`Kinds._mod_of`), an action passed by the enabled check is not checked again, and an item validated
against the data is not validated again against it (each bench craft validated the item it was given).

* Asked offer after offer at more states than the old cache held, without a release, each state's item is built once.
* The model the build makes is the model of the code before the ticket (every pair its own item, every mod and enabled check searched
  anew): the same keys, actions, kernels and values, on the hand-worked bow world and on real routes, there up to a net of pairs (OR-10, OR-12).
"""

import contextlib

import pytest
from abstraction_support import real_game_data
from test_abstraction_pattern import ACTIONS, BOW, GOAL, LEVEL, STARTS, build, offers_of, pattern_data
from test_kernel_projection import answer, counted, generated
from test_abstraction_pattern_real import CASES, E

from crafting_system.abstraction import Abstraction
from crafting_system.abstraction._kinds import Kinds
from crafting_system.abstraction._pattern import build_pattern_model
from crafting_system.items import Item, ItemError
from crafting_system.planner._pattern_bound import pattern_lower_bound

OLD_ITEMS_KEPT = 64


@contextlib.contextmanager
def as_before(ab: Abstraction):
    """The code before #1170 on `ab`: every prepared pair builds its own item, every mod of a slot and every enabled check is searched anew,
    and an item is checked each time it is validated."""
    find, validate = Kinds._mod_of, Item.validate

    def every_time(item, data):
        with contextlib.suppress(AttributeError):
            object.__delattr__(item, "_valid_in")
        validate(item, data)

    ab.share_items = False
    Kinds._mod_of = lambda self, key, side, tags=frozenset(), *, unveiled=False: self._find_mod(key, side, tags, unveiled)
    Item.validate = every_time
    ab._check_enabled = ab._check_enabled_once
    try:
        yield ab
    finally:
        Kinds._mod_of, Item.validate = find, validate


def same_model(old, new) -> None:
    assert new.keys == old.keys
    assert new.goal == old.goal
    assert new.actions == old.actions
    assert new.kernels == old.kernels
    assert new.index == old.index
    assert new.expanded == old.expanded
    assert new.stopped == old.stopped


@pytest.mark.parametrize("name", ["tiny", "bow"])
def test_offers_asked_one_after_the_other_at_many_states_build_each_item_once(name, monkeypatch):
    data, ab, states = generated(name, 4, count=40, steps=150)
    ab.release_prepared()
    states = list(dict.fromkeys(state for state in states if not ab._holds_lock(state)))
    assert len(states) > OLD_ITEMS_KEPT  # more than the old cache held: in a cycle it found none of them
    calls = counted(ab, monkeypatch)
    readers = [action for action in ab.enabled if ab._kinds.reads_junk(action)]
    assert len(readers) > 2
    for action in readers:  # the build's order: offer after offer, at every member
        for state in states:
            answer(lambda: ab.kernel_key(state, action))
    assert calls["_item_of"] <= len(states)  # one item for each state, whatever the number of offers


def test_an_item_validated_against_the_data_is_not_checked_again_against_it(monkeypatch):
    data, ab, states = generated("bow", 4, steps=20)
    item = ab._item_of(states[0], False)[0]
    assert getattr(item, "_valid_in", None) is data
    checked = []
    monkeypatch.setattr(Item, "_check_capacity", lambda self, data: checked.append(data))
    item.validate(data)
    assert checked == []  # passed against this data: not checked again
    other = type(data)(**{name: getattr(data, name) for name in data.__slots__})
    item.validate(other)
    assert checked == [other]  # other data: checked
    raw = Item(item.base_id, item.item_level, item.rarity, item.mods)
    raw.validate(data)
    assert checked == [other, data]  # an equal item never validated: checked


def test_an_item_that_failed_is_checked_and_fails_again():
    data, ab, states = generated("bow", 4, steps=20)
    item = ab._item_of(states[0], False)[0]
    wrong = Item(item.base_id, item.item_level, item.rarity, (*item.mods, item.mods[0].__class__("no such mod", ())))
    for _ in range(2):
        with pytest.raises(ItemError):
            wrong.validate(data)


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_the_build_of_the_hand_worked_world_is_the_build_before(tags):
    data = pattern_data()

    def made(before: bool):
        ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
        start = ab.compress(build(data, BOW, STARTS[0]))
        with as_before(ab) if before else contextlib.nullcontext():
            return build_pattern_model(ab, start, offers_of(), tags=tags)

    old, new = made(True), made(False)
    same_model(old, new)
    assert new.stats.kernels == old.stats.kernels and new.stats.pairs == old.stats.pairs > 100


PIECES = 30_000  # the build stops after so many (member, offer) pairs: the whole build of these routes takes minutes, twice


@pytest.mark.parametrize(("route", "tags"), [case for case in CASES if case.id != "r13-no-tags"])
def test_the_bound_of_a_real_route_is_the_bound_before(route, tags):
    real_game_data()  # skips without the dump

    def made(before: bool):
        _, _, _, abstraction, start, priced, _ = E.build_model(route, "twins", True, False)
        with as_before(abstraction) if before else contextlib.nullcontext():
            return pattern_lower_bound(abstraction, start, priced, tags=tags, pieces=PIECES)

    old, new = made(True), made(False)
    same_model(old.model, new.model)
    assert list(new.value) == list(old.value)
    assert new.start_value == old.start_value
