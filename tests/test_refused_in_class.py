"""The bound's build answers a pair from its refusal class, and makes a key's members with each side's status once (ticket #1256).

R04's round of bench crafts (73 offers) stopped its model growth at its quarter of the run after #1193. Its build asked 2.3 million pairs of
bench crafts, 2.28 million of them refused in a refusal class already met (#1178: the item without its junk, the junk's count per side and
the junk mods that share a family with the craft's): each went the whole way of `kernel_key` (the view, the item, the class, the exception) to
find the refusal it shared. And `Pattern.members` took the per-leaf best of every pair of a prefix and a suffix multiset (3.5 million
`best_of`), and made the members of `Mode.ANY` twice for each key.

* The class `Abstraction.refusal_class_of` gives a state is the class `_build` makes for it, and a pair whose class holds a refusal is one
  `kernel_key` refuses: on generated states, in the build's order.
* `_fitting` is `best_of` over the pair, on hand-worked statuses.
* An action that names no family (Remove Crafted Mods, a Fracturing Orb) has one refusal class at every member of a key: once a member is
  refused in it the others are counted as refused and their items are not made (#1193); the model, the pairs and the refusals are those of
  the build that looks each member's class up.
* The model the build makes is the model before the ticket (each pair asked, every pair's status made whole, the members of `ANY` made
  again): the same keys, actions, kernels and values, the same pairs and refusals, on the hand-worked bow world and on a real route up to a
  net of pairs, with fewer `kernel_key` calls (OR-10, OR-12).
"""

import contextlib

import pytest
from abstraction_support import real_game_data
from test_abstraction_pattern import ACTIONS, BOW, GOAL, LEVEL, STARTS, build, offers_of, pattern_data
from test_abstraction_pattern_real import CASES, E
from test_kernel_projection import answer, generated, refused
from test_pattern_items_kept import PIECES, same_model

from crafting_system.abstraction import Abstraction, _pattern
from crafting_system.abstraction._goal import Status
from crafting_system.abstraction._pattern import PatternOffer, build_pattern_model
from crafting_system.abstraction._state import best_of
from crafting_system.planner._pattern_bound import pattern_lower_bound

A, B, P = Status.ABSENT, Status.BELOW, Status.PASSING


def _every_pair(width, status, firsts, seconds):
    """`_fitting` as the build made it before: each multiset its own class, each pair's status made from all its contributions."""
    return (
        list(range(len(firsts))),
        list(range(len(seconds))),
        [[best_of(width, first + second) == status for second in seconds] for first in firsts],
    )


@contextlib.contextmanager
def as_before(monkeypatch):
    """The build before #1256: each pair asks `kernel_key`, each pair of multisets its status, and the members of `ANY` are made again."""
    asked = _pattern.PatternBuilder._offers_of_key
    with monkeypatch.context() as patch:
        patch.setattr(_pattern, "SHARE_REFUSED", False)
        patch.setattr(_pattern, "_fitting", _every_pair)
        patch.setattr(_pattern.PatternBuilder, "_offers_of_key", lambda self, i, first, tick, firsts=None: asked(self, i, first, tick))
        yield


def counting(ab: Abstraction, monkeypatch) -> list[int]:
    """Count the calls of `ab.kernel_key`."""
    calls = [0]
    inner = ab.kernel_key

    def counted(state, action):
        calls[0] += 1
        return inner(state, action)

    monkeypatch.setattr(ab, "kernel_key", counted)
    return calls


def test_the_status_of_a_pair_is_the_best_of_its_two_sides():
    # three leaves, the key's status (PASSING, PASSING, BELOW); the first side carries the key's own slots
    firsts = [[(P, A, A)], [(A, A, B), (P, A, A)], [(A, A, A)], [(P, A, B)]]
    seconds = [[], [(A, P, A)], [(A, P, B)]]
    status = (P, P, B)
    first_class, second_class, table = _pattern._fitting(3, status, firsts, seconds)
    assert first_class == [0, 1, 2, 1]  # the second and the fourth have one best, (PASSING, ABSENT, BELOW)
    assert second_class == [0, 1, 2]
    fits = {(i, j) for i in range(len(firsts)) for j in range(len(seconds)) if table[first_class[i]][second_class[j]]}
    assert fits == {(0, 2), (1, 1), (1, 2), (3, 1), (3, 2)}
    _, _, every = _every_pair(3, status, firsts, seconds)
    assert fits == {(i, j) for i in range(len(firsts)) for j in range(len(seconds)) if every[i][j]}


@pytest.mark.parametrize(("name", "seed"), [("tiny", 1), ("bow", 2), ("bow", 3)])
def test_a_refusal_met_in_the_class_is_the_refusal_of_the_pair(name, seed):
    data, ab, states = generated(name, seed, count=30, steps=150)
    ab.release_prepared()
    readers = [action for action in ab.enabled if ab._kinds.reads(action).refusal_by_families]
    assert readers
    answered = 0
    for action in readers:  # the build's order: offer after offer, at every state
        of = ab.refusal_class_of(action)
        for state in states:
            found = of(state)
            if found is not None:  # the class `_build` makes for the pair
                view = ab._view(state, False)
                item, _ = ab._item_of_view(view, False)
                assert found == ab._refusal_class(view, action, item)
            known = found is not None and found in ab._refused_by
            result = answer(lambda: ab.kernel_key(state, action))
            if known:
                assert refused(result) and result[0] == "NotApplicableError", (state, action, result)
                answered += 1
    assert answered > 0
    ab.share_refusals = False
    assert ab.refusal_class_of(readers[0]) is None  # the reference of #1178 asks every pair


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_the_build_of_the_hand_worked_world_is_the_build_before(tags, monkeypatch):
    data = pattern_data()
    offers = [*offers_of(), PatternOffer("bench-lock", ACTIONS["bench-lock"], 1.0), PatternOffer("bench-craft", ACTIONS["bench-craft"], 2.0)]

    def made(before: bool):
        ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
        start = ab.compress(build(data, BOW, STARTS[0]))
        calls = counting(ab, monkeypatch)
        with as_before(monkeypatch) if before else contextlib.nullcontext():
            return build_pattern_model(ab, start, offers, tags=tags), ab.refusals_shared, calls[0]

    (old, old_shared, old_calls), (new, new_shared, new_calls) = made(True), made(False)
    same_model(old, new)
    assert new.stats.pairs == old.stats.pairs > 100
    assert new.stats.refused_pairs == old.stats.refused_pairs and new.stats.members == old.stats.members
    assert new_shared == old_shared > 0
    assert new_calls == old_calls - new_shared  # each pair refused in its class is not asked


@pytest.mark.parametrize(("route", "tags"), [case for case in CASES if case.id == "r13-auto"])
def test_the_bound_of_a_real_route_is_the_bound_before(route, tags, monkeypatch):
    real_game_data()  # skips without the dump

    def made(before: bool):
        _, _, _, abstraction, start, priced, _ = E.build_model(route, "twins", True, False)
        calls = counting(abstraction, monkeypatch)
        with as_before(monkeypatch) if before else contextlib.nullcontext():
            return pattern_lower_bound(abstraction, start, priced, tags=tags, pieces=PIECES), abstraction.refusals_shared, calls[0]

    (old, old_shared, old_calls), (new, new_shared, new_calls) = made(True), made(False)
    same_model(old.model, new.model)
    assert list(new.value) == list(old.value)
    assert new.start_value == old.start_value
    assert new.model.stats.pairs == old.model.stats.pairs > 1_000
    assert new.model.stats.refused_pairs == old.model.stats.refused_pairs and new.model.stats.members == old.model.stats.members
    assert new_shared == old_shared > 0 and new_calls == old_calls - new_shared
    assert new.pieces == old.pieces and str(new.model.stopped) == str(old.model.stopped)  # the counted net (`PIECES`) stops where it did


def _profiles(ab: Abstraction, monkeypatch) -> list[int]:
    """Count the states whose refusal class parts `ab` makes (`_junk_profile`: the item of the state is built for it)."""
    calls = [0]
    inner = ab._junk_profile

    def counted(state):
        calls[0] += 1
        return inner(state)

    monkeypatch.setattr(ab, "_junk_profile", counted)
    return calls


def test_the_actions_that_name_no_family_are_the_orb_and_the_removal():
    ab = Abstraction(pattern_data(), GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
    assert {name for name, action in ACTIONS.items() if ab.refusal_names_no_junk(action)} == {"fracture", "remove"}
    ab.share_refusals = False
    assert not ab.refusal_names_no_junk(ACTIONS["fracture"])  # the reference of #1178 has no class


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_a_refusal_of_the_key_is_not_looked_up_at_each_member(tags, monkeypatch):
    """The hand-worked world: the Fracturing Orb is asked at every pure junk assignment of a key (`ALL`) and is refused by most keys (fewer
    than four mods, a fractured mod). With the refusal shared over the key, the same model with the same pairs, refusals and shared refusals,
    from fewer items made to look a class up."""
    data = pattern_data()
    offers = [*offers_of(), PatternOffer("bench-lock", ACTIONS["bench-lock"], 1.0), PatternOffer("bench-craft", ACTIONS["bench-craft"], 2.0)]

    def made(each: bool):
        ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
        start = ab.compress(build(data, BOW, STARTS[0]))
        calls, profiles = counting(ab, monkeypatch), _profiles(ab, monkeypatch)
        with monkeypatch.context() as patch:
            patch.setattr(_pattern, "SHARE_KEY_REFUSALS", not each)
            return build_pattern_model(ab, start, offers, tags=tags), ab.refusals_shared, calls[0], profiles[0]

    (old, old_shared, old_calls, old_profiles), (new, new_shared, new_calls, new_profiles) = made(True), made(False)
    same_model(old, new)
    assert new.stats.pairs == old.stats.pairs > 100
    assert new.stats.refused_pairs == old.stats.refused_pairs and new.stats.members == old.stats.members
    assert new_shared == old_shared > 0 and new_calls == old_calls
    assert new_profiles < old_profiles


@pytest.mark.parametrize(("route", "tags"), [case for case in CASES if case.id == "r13-auto"])
def test_a_refusal_of_the_key_leaves_the_bound_of_a_real_route(route, tags, monkeypatch):
    real_game_data()  # skips without the dump

    def made(each: bool):
        _, _, _, abstraction, start, priced, _ = E.build_model(route, "twins", True, False)
        profiles = _profiles(abstraction, monkeypatch)
        with monkeypatch.context() as patch:
            patch.setattr(_pattern, "SHARE_KEY_REFUSALS", not each)
            return pattern_lower_bound(abstraction, start, priced, tags=tags, pieces=PIECES), abstraction.refusals_shared, profiles[0]

    (old, old_shared, old_profiles), (new, new_shared, new_profiles) = made(True), made(False)
    same_model(old.model, new.model)
    assert list(new.value) == list(old.value) and new.start_value == old.start_value
    assert new.model.stats.pairs == old.model.stats.pairs > 1_000
    assert new.model.stats.refused_pairs == old.model.stats.refused_pairs and new.model.stats.members == old.model.stats.members
    assert new_shared == old_shared > 0
    assert new_profiles <= old_profiles
    assert new.pieces == old.pieces and str(new.model.stopped) == str(old.model.stopped)  # the counted net (`PIECES`) stops where it did


def test_only_the_actions_that_draw_are_prepared_ahead_for_the_process_pool(monkeypatch):
    """The build prepares, ahead of a key's offers, the pairs whose walks a process pool could make (`PatternBuilder._prime`). An action that
    draws nothing has no walk, and its pairs prepared there were the items of every member made a first time: the Fracturing Orb's at every
    pure junk assignment, refused by the key or not (#1193)."""
    monkeypatch.setattr(_pattern, "PRIME_FROM", 1)  # every key prepares its offers (the product does from 16)
    primed: list = []
    monkeypatch.setattr(Abstraction, "prime", lambda self, requests, **options: primed.extend(requests))
    data = pattern_data()
    offers = [*offers_of(), PatternOffer("bench-lock", ACTIONS["bench-lock"], 1.0), PatternOffer("bench-craft", ACTIONS["bench-craft"], 2.0)]
    ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
    model = build_pattern_model(ab, ab.compress(build(data, BOW, STARTS[0])), offers)
    names = {action: name for name, action in ACTIONS.items()}
    asked = {names[offer.action] for offer in offers if offer.action is not None}
    assert {"chaos", "exalted", "annul", "fracture", "remove", "bench-lock", "bench-craft"} <= asked
    assert {names[action] for _, action in primed} == {name for name in asked if ACTIONS[name].adds(data).draws}
    assert {names[action] for _, action in primed} == {"chaos", "exalted"}
    plain = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
    monkeypatch.setattr(_pattern, "PRIME_FROM", 10**9)
    same_model(build_pattern_model(plain, plain.compress(build(data, BOW, STARTS[0])), offers), model)
