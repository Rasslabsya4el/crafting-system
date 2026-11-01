"""Layer 1 (ADR-0019) for the removals and the adds on the fixture Thicket Bow: Annulment, Exalted and Scouring (ticket #69).

Every kernel is checked against the brute force of `abstraction_metamod_oracle.py`: all the finished items of the
action on a concrete item, compressed one by one with the same `compress` and added up, in exact fractions. The
bows are the ones of `abstraction_removals_support.py` (a fire, a socketed-gem, an attack speed and a fire resistance
mod, a caster prefix in one kind, a crafted prefix in another) with and without each metamod: `Prefixes` and `Suffixes
Cannot Be Changed`, `Cannot roll Attack Modifiers`, `Cannot roll Caster Modifiers` and the multimod, and with two or
three of them together. An abstraction that may meet a lock or a tag metamod has `metamods=True`.

What the Annulment reads is the count of the mods and, through the slots, what it may remove: no family by name. So two
junk families of one type are one state, and a route that only removes has fewer states than one that tells every
family apart; the closure of a small route equals the compressed closure of the concrete items it reaches.
"""

from dataclasses import dataclass
from fractions import Fraction

import pytest
from abstraction_metamod_oracle import annulled, closure, crafted, exalted, fracture_one
from abstraction_removals_support import (
    AS_5,
    BLOCKING,
    BOW_DATA,
    COLD,
    COLD_RES,
    COMBOS,
    EXALT_COMBOS,
    FIRE,
    FIRE_RES,
    METAMODS,
    PL,
    SL,
    SOCKET,
    SOCKET_LEAF,
    TINY_DATA,
    abstraction,
    bow,
    build,
    check,
    check_or_refusal,
    passing,
    start_kinds,
    start_of,
)

from crafting_system.abstraction import Goal
from crafting_system.actions import ActionError, AnnulmentOrb, BenchCraft, ExaltedOrb, FracturingOrb, Reads, ScouringOrb
from crafting_system.items import Side

ANNUL, EXALT, SCOUR = AnnulmentOrb(), ExaltedOrb(), ScouringOrb()
GOAL_SOCKET = Goal((SOCKET_LEAF,))


def cases():
    """(kind, meta, flag): every start with each metamod; an ordinary bow and one with the multimod run with the flag off and on."""
    for meta in [None, *METAMODS]:
        for kind in start_kinds(meta):
            for flag in (True,) if meta in BLOCKING else (False, True):
                yield pytest.param(kind, meta, flag, id=f"{meta or 'plain'}-{kind}-{'flag' if flag else 'noflag'}")


# --- layer 1: the Annulment ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(("kind", "meta", "flag"), list(cases()))
def test_annulment_equals_the_brute_force(kind, meta, flag):
    ab = abstraction(metamods=flag)

    check(ab, start_of(kind, meta), ANNUL)


@pytest.mark.parametrize(("kind", "meta", "flag"), list(cases()))
def test_annulment_equals_the_brute_force_with_a_fractured_mod(kind, meta, flag):
    ab = abstraction(metamods=flag)

    check(ab, start_of(kind, meta, fractured=[AS_5]), ANNUL)


@pytest.mark.parametrize("name", COMBOS)
def test_annulment_equals_the_brute_force_with_several_metamods(name):
    check_or_refusal(abstraction(metamods=True), bow(*COMBOS[name]), ANNUL)  # both locks: nothing can be removed, the game refuses


def test_a_lock_protects_its_side_and_the_metamod_of_the_other_side_can_go():
    ab = abstraction(metamods=True)
    start = start_of("gem", "PL")  # the prefix lock is a suffix: the suffixes are candidates, the prefixes are not

    kernel = check(ab, start, ANNUL)

    assert len(kernel) == 3  # the attack speed, the resistance or the metamod goes, 1/3 each
    assert all(after.count(Side.PREFIX) == 2 and after.count(Side.SUFFIX) == 2 for after in kernel)
    assert sorted(after.crafted for after in kernel) == [False, True, True]


def test_a_tag_metamod_protects_the_mods_with_its_tag_from_an_annulment():
    ab = abstraction(metamods=True)
    start = start_of("mixed", "NA")  # the fire prefix and the attack speed are Attack mods; the caster prefix, the resistance and the metamod are not

    kernel = check(ab, start, ANNUL)

    assert len(kernel) == 3
    assert sum(chance for after, chance in kernel.items() if after.count(Side.PREFIX) == 1) == Fraction(1, 3)


def test_a_fractured_metamod_blocks_a_removal_like_any_fractured_mod():
    ab = abstraction(metamods=True)

    check(ab, start_of("gem", "NA", fractured=[METAMODS["NA"]]), ANNUL)
    check(ab, start_of("gem", "SL", fractured=[SL]), ANNUL)


# --- layer 1: the Exalted Orb ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(("kind", "meta", "flag"), list(cases()))
def test_exalted_equals_the_brute_force(kind, meta, flag):
    ab = abstraction(metamods=flag)

    check(ab, start_of(kind, meta), EXALT)


@pytest.mark.parametrize(("kind", "meta", "flag"), list(cases()))
def test_exalted_equals_the_brute_force_with_a_fractured_mod(kind, meta, flag):
    ab = abstraction(metamods=flag)

    check(ab, start_of(kind, meta, fractured=[FIRE_RES]), EXALT)


@pytest.mark.parametrize("name", EXALT_COMBOS)
def test_exalted_with_several_metamods_equals_the_brute_force(name):
    check(abstraction(metamods=True), bow(*EXALT_COMBOS[name]), EXALT)


def test_the_attack_metamod_leaves_one_prefix_to_an_exalted_orb():
    ab = abstraction(metamods=True)

    kernel = check(ab, start_of("gem", "NA"), EXALT)  # the free prefix slot: only the caster prefix has no Attack tag

    assert len(kernel) == 1


def test_the_caster_metamod_keeps_the_caster_prefix_out_of_the_pool_of_an_exalted_orb():
    ab = abstraction(metamods=True)

    kernel = check(ab, start_of("gem", "NC"), EXALT)  # the free prefix slot: Cold (1400) and the bow gems (1000 + 1000)

    assert len(kernel) == 3
    assert sum(chance for after, chance in kernel.items() if passing(after, 1)) == Fraction(1000, 3400)  # the tier 1 bow gem


# --- layer 1: the Orb of Scouring ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("kind", "meta", "flag"), list(cases()))
def test_scouring_equals_the_brute_force(kind, meta, flag):
    ab = abstraction(metamods=flag)

    check(ab, start_of(kind, meta), SCOUR)


@pytest.mark.parametrize(("kind", "meta", "flag"), list(cases()))
def test_scouring_keeps_the_fractured_mods_and_equals_the_brute_force(kind, meta, flag):
    ab = abstraction(metamods=flag)

    check(ab, start_of(kind, meta, fractured=[FIRE_RES, AS_5]), SCOUR)


@pytest.mark.parametrize("name", COMBOS)
def test_scouring_with_several_metamods_equals_the_brute_force(name):
    check(abstraction(metamods=True), bow(*COMBOS[name]), SCOUR)


def test_scouring_under_a_lock_keeps_the_locked_side_and_takes_the_metamod():
    ab = abstraction(metamods=True)

    ((after, chance),) = check(ab, start_of("gem", "PL"), SCOUR).items()

    assert chance == 1 and after.count(Side.PREFIX) == 2 and after.count(Side.SUFFIX) == 0 and not after.crafted
    assert after.flags.rarity.value == "rare"  # two prefixes are left


# --- states merge exactly what the Annulment treats alike -----------------------------------------------------


@pytest.mark.parametrize("flag", [False, True])
def test_two_junk_families_of_one_type_are_one_state_under_annulment(flag):
    ab = abstraction(GOAL_SOCKET, (ANNUL,), metamods=flag)
    fire, cold = ab.compress(bow(FIRE, SOCKET, FIRE_RES, AS_5)), ab.compress(bow(COLD, SOCKET, COLD_RES, AS_5))

    assert fire == cold
    assert ab.kernel(fire, ANNUL) == ab.kernel(cold, ANNUL)


def test_a_tag_tells_junk_apart_only_when_a_metamod_can_read_it():
    plain, tagged = abstraction(GOAL_SOCKET, (ANNUL,)), abstraction(GOAL_SOCKET, (ANNUL,), metamods=True)
    attack_suffix, other_suffix = bow(FIRE, SOCKET, AS_5), bow(FIRE, SOCKET, FIRE_RES)

    assert plain.compress(attack_suffix) == plain.compress(other_suffix)
    assert tagged.compress(attack_suffix) != tagged.compress(other_suffix)
    assert tagged.compress(bow(FIRE, SOCKET)) == tagged.compress(bow(COLD, SOCKET))  # two Attack prefixes: one type


@dataclass(frozen=True)
class ExactAnnulment(AnnulmentOrb):
    """An Annulment that declares nothing: every family of the junk is told apart (the default of the contract)."""

    def reads(self, data):
        return Reads()


@pytest.mark.parametrize("flag", [False, True])
def test_the_states_of_a_removing_route_are_fewer_than_telling_every_family_apart(flag):
    start = bow(FIRE, COLD, SOCKET, FIRE_RES, COLD_RES, AS_5)
    kinds = abstraction(GOAL_SOCKET, (ANNUL,), metamods=flag)
    every = abstraction(GOAL_SOCKET, (ExactAnnulment(),), metamods=flag)

    few = kinds.reachable([kinds.compress(start)], [ANNUL])
    many = every.reachable([every.compress(start)], [ExactAnnulment()])

    assert len(many) == 2**6  # every subset of the six mods is a state of its own
    assert len(few) < len(many)
    assert few == {kinds.compress(item) for item in closure(start, [lambda item: annulled(BOW_DATA, item)])}


# --- the reachable states of a small route -----------------------------------------------------------------------------------------

ROUTE = (ANNUL, EXALT, FracturingOrb(), BenchCraft(PL))  # a removal, an add, a fracture and a metamod craft


def route_abstraction():
    return abstraction(GOAL_SOCKET, ROUTE, data=TINY_DATA)


def test_the_closure_of_a_route_of_removals_adds_fractures_and_a_craft_equals_the_compressed_concrete_closure():
    ab = route_abstraction()
    start = build(TINY_DATA, ab.base_id, (FIRE, SOCKET, AS_5, FIRE_RES))
    steps = [
        lambda item: annulled(TINY_DATA, item),
        lambda item: exalted(TINY_DATA, item),
        lambda item: fracture_one(TINY_DATA, item),
        lambda item: crafted(TINY_DATA, item, PL),
    ]

    reached = ab.reachable([ab.compress(start)], ROUTE)

    assert len(reached) > 10
    assert reached == {ab.compress(item) for item in closure(start, steps)}


def test_every_kernel_row_of_the_route_sums_to_one():
    ab = route_abstraction()
    start = build(TINY_DATA, ab.base_id, (FIRE, SOCKET, AS_5, FIRE_RES))

    reached = ab.reachable([ab.compress(start)], ROUTE)

    rows = 0
    for state in reached:
        for action in (*ROUTE, SCOUR):
            try:
                kernel = ab.kernel(state, action)
            except ActionError:
                continue
            rows += 1
            assert sum(kernel.values()) == 1
            assert all(chance > 0 for chance in kernel.values())
    assert rows > len(reached)
