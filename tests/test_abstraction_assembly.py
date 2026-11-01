"""Assembling a kernel from the cached distribution: faster, with the very same result (ticket #118, piece F).

(a) The kernel of every catalog action on the fixture worlds equals, key for key and fraction for fraction,
what the assembly written before the change gave (`reference_add_drawn`, copied from it); (b)
`integer_weights` equals a plain reference; (c) `Slot` and `CompressedState` keep their equality, order and
copies, with a precomputed `Slot.key` and cached hashes.
"""

import copy
import dataclasses
import math
import pickle
import random
import types
from fractions import Fraction

import pytest
import test_abstraction_b1 as belt_world
import test_abstraction_fossil as fossil_world
import test_prune_equal as prune

from crafting_system.abstraction import CompressedState, Flags, FracturedMod, Slot, Status, integer_weights
from crafting_system.abstraction._state import best_of
from crafting_system.actions import ChaosOrb, RemoveCraftedMods
from crafting_system.items import Influence, Rarity, Side

PASSING, BELOW, ABSENT = Status.PASSING, Status.BELOW, Status.ABSENT


def reference_add_drawn(self, result, share, part, signature, split):
    """`Abstraction._add_drawn` as it was before the assembly was rewritten."""
    width = len(self.goal.leaves)
    tracked = self._kinds.tracked
    stays = [*split.kept, *split.new]
    for drawn, chance in self._distribution(signature, part).items():
        if tracked:
            best = best_of(width, (ints for (ints, _, _), _ in drawn))
            slots = stays + [
                Slot(Side(side), kind, tuple(Status(value) for value in ints))
                for (ints, side, kind), count in drawn
                for _ in range(count)
            ]
            slots.sort(key=lambda slot: (slot.side.value, slot.kind, tuple(int(v) for v in slot.contribution), slot.crafted))
        else:
            best = tuple(Status(value) for value in drawn)
            slots = sorted(stays, key=lambda slot: (slot.side.value, slot.kind, tuple(int(v) for v in slot.contribution), slot.crafted))
        status = tuple(max(a, b) for a, b in zip(split.status, best))
        result[CompressedState(split.flags, split.fractured, status, tuple(slots))] += share * chance


def referenced(ab):
    """`ab` with the assembly of the reference."""
    ab._add_drawn = types.MethodType(reference_add_drawn, ab)
    return ab


def _tracked_mixtures():
    """The fossil boots with the junk kept and the sets whose parts differ (Tangled, Glyphic, Hollow)."""
    sets = [("Tangled",), ("Tangled", "Elemental"), ("Glyphic",), ("Glyphic", "Lucent"), ("Hollow", "Scorched"), ("Scorched",)]
    actions = [ChaosOrb(), RemoveCraftedMods(), *(fossil_world.fossils(*names) for names in sets)]
    boots, roll = fossil_world.boots, fossil_world.roll
    starts = [
        boots(),
        boots(roll("CasterA", fractured=True), roll("LifeA")),
        boots(roll("CasterA"), roll("LifeA"), roll("FireResA")),
    ]
    ab = fossil_world.abstraction(RemoveCraftedMods())
    return ab, actions, [ab.compress(item) for item in starts]


WORLDS = {**prune.WORLDS, "fossil-tracked-mixtures": _tracked_mixtures}


@pytest.fixture(scope="module", params=list(WORLDS))
def both(request):
    """(name, new abstraction, reference abstraction, states, actions) of a world."""
    ab, actions, starts = WORLDS[request.param]()
    states = prune._spread(ab, actions, starts)
    reference = referenced(WORLDS[request.param]()[0])
    return request.param, ab, reference, states, actions


def test_every_kernel_equals_the_reference_assembly(both):
    name, ab, reference, states, actions = both
    compared = 0
    for state in states:
        for action in actions:
            new = prune._outcome_of(lambda: ab.kernel(state, action))
            old = prune._outcome_of(lambda: reference.kernel(state, action))
            assert new[0] == old[0], f"{name}: {action!r} at {state!r}"
            if new[0] != "ok":
                continue
            assert dict(new[1]) == dict(old[1]), f"{name}: {action!r} at {state!r}"
            for key, chance in new[1].items():
                assert type(chance) is Fraction
                assert chance == old[1][key]
                assert hash(key) == hash(next(k for k in old[1] if k == key))
                assert list(key.slots) == sorted(key.slots, key=lambda slot: slot.key)
            assert sum(new[1].values()) == 1
            compared += 1
    assert compared > 50


def test_a_second_request_on_a_warm_cache_gives_the_same_kernel(both):
    _, ab, reference, states, actions = both
    for state in states[:15]:
        for action in actions:
            first = prune._outcome_of(lambda: dict(ab.kernel(state, action)))
            again = prune._outcome_of(lambda: dict(ab.kernel(state, action)))
            assert first == again


def test_the_cache_statistics_count_as_before():
    ab, actions, starts = _tracked_mixtures()
    reference = referenced(_tracked_mixtures()[0])
    for state in starts:
        for action in actions:
            prune._outcome_of(lambda: ab.kernel(state, action))
            prune._outcome_of(lambda: reference.kernel(state, action))
    assert ab.stats == reference.stats
    assert ab.stats.kernels > 0 and ab.stats.hits > 0


def test_the_worlds_hold_tracked_and_untracked_junk_and_fractured_mods(both):
    name, ab, _, states, _ = both
    assert any(state.fractured for state in states)
    if name in ("fossil-junk-kept", "fossil-tracked-mixtures"):
        assert ab.keeps_junk and any(len(state.slots) > 1 for state in states)
    if name == "fossil-junk-erased":
        assert not ab.keeps_junk


# --- integer_weights ----------------------------------------------------------------------------------


def reference_integer_weights(kernel):
    if not kernel:
        return {}
    common = 1
    for chance in kernel.values():
        common = math.lcm(common, chance.denominator)
    scaled = {state: int(chance * common) for state, chance in kernel.items()}
    divisor = 0
    for weight in scaled.values():
        divisor = math.gcd(divisor, weight)
    return {state: weight // divisor for state, weight in scaled.items()}


def _random_kernel(rng, size, bound):
    weights = [rng.randint(1, bound) for _ in range(size)]
    total = sum(weights)
    return {index: Fraction(weight, total) for index, weight in enumerate(weights)}


def test_integer_weights_equals_the_reference_on_random_kernels():
    rng = random.Random(118)
    for _ in range(300):
        kernel = _random_kernel(rng, rng.randint(1, 40), rng.choice([1, 3, 12, 1000, 10**9]))
        assert integer_weights(kernel) == reference_integer_weights(kernel)


def test_integer_weights_with_one_entry_and_with_large_denominators():
    assert integer_weights({"a": Fraction(1)}) == {"a": 1}
    large = {"a": Fraction(1, 3**80), "b": Fraction(2, 5**70), "c": Fraction(1) - Fraction(1, 3**80) - Fraction(2, 5**70)}
    assert integer_weights(large) == reference_integer_weights(large)
    assert sum(Fraction(w) for w in integer_weights(large).values()) > 0
    zero_entry = {"a": Fraction(0), "b": Fraction(1, 2), "c": Fraction(1, 2)}
    assert integer_weights(zero_entry) == reference_integer_weights(zero_entry) == {"a": 0, "b": 1, "c": 1}


def test_integer_weights_empty_and_result_types():
    assert integer_weights({}) == {}
    weights = integer_weights({"a": Fraction(1, 4), "b": Fraction(3, 4)})
    assert weights == {"a": 1, "b": 3}
    assert all(type(weight) is int for weight in weights.values())


def test_integer_weights_equals_the_reference_on_the_kernels_of_the_worlds(both):
    _, ab, _, states, actions = both
    checked = 0
    for state in states:
        for action in actions:
            kernel = prune._outcome_of(lambda: ab.kernel(state, action))
            if kernel[0] == "ok":
                assert integer_weights(kernel[1]) == reference_integer_weights(kernel[1])
                checked += 1
    assert checked > 50


# --- Slot and CompressedState ---------------------------------------------------------------------------


def old_key(slot):
    return (slot.side.value, slot.kind, tuple(int(value) for value in slot.contribution), slot.crafted)


def make_slot(side=Side.PREFIX, kind="k", contribution=(PASSING, ABSENT), crafted=False):
    return Slot(side, kind, contribution, crafted)


def make_state(**changes):
    parts = dict(
        flags=Flags(Rarity.RARE, False, frozenset({Influence.SHAPER})),
        fractured=(FracturedMod("m", (PASSING, ABSENT)),),
        status=(PASSING, BELOW),
        slots=(make_slot(), make_slot(Side.SUFFIX, "x", (ABSENT, BELOW), True)),
    )
    parts.update(changes)
    return CompressedState(**parts)


def test_slot_key_is_the_old_value_and_sorting_is_unchanged():
    rng = random.Random(7)
    slots = [
        make_slot(rng.choice(list(Side)), rng.choice(["", "a", "b"]), tuple(rng.choice(list(Status)) for _ in range(2)), rng.random() < 0.3)
        for _ in range(200)
    ]
    assert all(slot.key == old_key(slot) for slot in slots)
    assert sorted(slots, key=lambda slot: slot.key) == sorted(slots, key=old_key)


def test_equal_slots_have_equal_hashes_and_unequal_slots_differ():
    one, same = make_slot(), make_slot(contribution=(int(PASSING), 0))  # ints equal the Status members
    assert one == same and hash(one) == hash(same) and one.key == same.key
    for other in (
        make_slot(Side.SUFFIX),
        make_slot(kind="other"),
        make_slot(contribution=(ABSENT, ABSENT)),
        make_slot(crafted=True),
    ):
        assert one != other
        assert one.key != other.key
    assert len({one, same}) == 1


def test_equal_states_have_equal_hashes_and_unequal_states_differ():
    one, same = make_state(), make_state()
    assert one == same and hash(one) == hash(same) and hash(one) == hash(one)
    for other in (
        make_state(flags=Flags(Rarity.MAGIC, False, frozenset({Influence.SHAPER}))),
        make_state(fractured=()),
        make_state(status=(PASSING, PASSING)),
        make_state(slots=(make_slot(),)),
    ):
        assert one != other
    assert len({one, same, make_state(slots=())}) == 2


def test_the_cached_hash_is_not_part_of_equality_repr_or_fields():
    state = make_state()
    before = repr(state)
    hash(state)
    assert repr(state) == before
    assert "hash" not in repr(make_slot()) and "key" not in repr(make_slot())
    assert state == make_state()


@pytest.mark.parametrize("make", [make_slot, make_state, lambda: Flags(Rarity.RARE, True, frozenset()), lambda: FracturedMod("m", (PASSING,))])
def test_replace_copy_and_pickle_round_trips(make):
    original = make()
    hash(original)
    for clone in (copy.copy(original), copy.deepcopy(original), pickle.loads(pickle.dumps(original))):
        assert clone == original and hash(clone) == hash(original) and clone is not original
        assert repr(clone) == repr(original)
    assert dataclasses.replace(original) == original
    assert hash(dataclasses.replace(original)) == hash(original)


def test_replace_recomputes_key_and_hash():
    slot = make_slot()
    hash(slot)
    changed = dataclasses.replace(slot, kind="other", crafted=True)
    assert changed.key == old_key(changed) and changed.key != slot.key
    assert changed != slot and changed == make_slot(kind="other", crafted=True)
    assert hash(changed) == hash(make_slot(kind="other", crafted=True))
    state = make_state()
    hash(state)
    other = dataclasses.replace(state, status=(PASSING, PASSING))
    assert other != state and hash(other) == hash(make_state(status=(PASSING, PASSING)))


def test_a_pickle_does_not_carry_the_hash_of_this_process():
    """Hashes of strings change from one process to the next: the cache must not travel."""
    for original in (make_slot(), make_state()):
        hash(original)
        assert "_hash" not in original.__reduce_ex__(2)[2]


# --- the signature that keys the caches ---------------------------------------------------------------


def test_a_pool_signature_equals_and_hashes_as_the_plain_tuple_and_is_one_object_per_value():
    ab, _, starts = prune._fossil_world(False)
    one = ab.signature(starts[0], ChaosOrb())
    other = ab.signature(starts[0], fossil_world.fossils("Gloveless"))  # a set whose pool is the Chaos Orb's
    assert one == other and hash(one) == hash(other)
    assert one is other
    plain = tuple(one)
    assert plain == one and hash(plain) == hash(one) == hash(one)
    assert {plain: 1}[one] == 1
