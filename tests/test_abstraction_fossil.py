"""Verification layer 1 for the fossil reforges: the compressed kernel against the brute force (ticket #62).

The world is the small synthetic boots of `test_actions_fossil.py` (13 pool mods in 10 families, the fossil
records and corrupted essences of that file). `abstraction_fossil.fossil_finished` lists every finished
item of a resonator and the kernel must be the same distribution once those items are compressed, in
exact fractions: single fossils, a summed pair, blocks, the Tangled mixture, the forced mods of Hollow and
Glyphic, the Fractured Fossil, with and without a fractured mod already on the item and with the junk
slots kept.
"""

from fractions import Fraction

import pytest
from abstraction_fossil import fossil_finished
from abstraction_oracle import assert_same_distribution, compressed_distribution
from test_actions_fossil import BOOTS, DATA, boots, roll

from crafting_system.abstraction import Abstraction, Goal, Status, Wanted
from crafting_system.actions import ApplyFossils, ChaosOrb, NotApplicableError, RemoveCraftedMods

LEVEL = 86
FIRE = Wanted(frozenset({"FireA", "FireB"}), min_tier=1)
LIFE = Wanted(frozenset({"LifeA", "LifeB"}))
RESIST = Wanted(frozenset({"FireResA"}))
GOAL = Goal((FIRE, LIFE, RESIST))


def abstraction(*actions):
    return Abstraction(DATA, GOAL, BOOTS, LEVEL, actions)


def fossils(*names):
    return ApplyFossils(tuple(f"{name} Fossil" for name in names))


STARTS = {
    "empty": lambda: boots(),
    "fractured": lambda: boots(roll("CasterA", fractured=True), roll("LifeA")),
    "two-fractured": lambda: boots(roll("CasterA", fractured=True), roll("FireB", fractured=True), roll("BareA")),
}
SETS = [
    ("Scorched",),
    ("Scorched", "Elemental"),
    ("Scorched", "Frigid"),
    ("Lucent", "Pale"),
    ("Opulent",),
    ("Sanctified", "Scorched"),
    ("Faceted", "Dull"),
    ("Tangled",),
    ("Tangled", "Elemental"),
    ("Hollow",),
    ("Hollow", "Scorched"),
    ("Glyphic",),
    ("Glyphic", "Lucent"),
]
FRACTURING = [("Fractured",), ("Fractured", "Scorched"), ("Fractured", "Hollow"), ("Fractured", "Glyphic"), ("Fractured", "Tangled"), ("Fractured", "Faceted")]


def check(ab, item, action):
    kernel = ab.kernel(ab.compress(item), action)
    assert_same_distribution(kernel, compressed_distribution(fossil_finished(DATA, action, item), ab.compress))
    return kernel


@pytest.mark.parametrize("start", STARTS)
@pytest.mark.parametrize("names", SETS, ids="+".join)
def test_a_resonator_kernel_equals_the_brute_force(names, start):
    check(abstraction(), STARTS[start](), fossils(*names))


@pytest.mark.parametrize("start", ["empty"])
@pytest.mark.parametrize("names", FRACTURING, ids="+".join)
def test_a_fractured_fossil_kernel_equals_the_brute_force(names, start):
    check(abstraction(), STARTS[start](), fossils(*names))


@pytest.mark.parametrize("names", [("Scorched",), ("Hollow",), ("Tangled",), ("Fractured", "Scorched"), ("Fractured", "Hollow"), ("Fractured", "Glyphic"), ("Fractured", "Tangled")], ids="+".join)
def test_the_kernel_with_the_junk_slots_kept_equals_the_brute_force(names):
    junk = boots(roll("CasterA"), roll("LifeA"), roll("FireResA"))
    ab = abstraction(RemoveCraftedMods())

    kernel = check(ab, junk, fossils(*names))

    assert all(state.slots for state in kernel)


def test_a_fractured_fossil_leaves_one_fractured_mod_and_the_wanted_ones_pass_with_it():
    ab = abstraction()

    kernel = check(ab, boots(), fossils("Fractured", "Scorched"))

    assert {len(state.fractured) for state in kernel} == {1}
    assert any(state.fractured and state.status[2] is Status.PASSING for state in kernel)


def test_a_fractured_fossil_is_refused_on_a_fractured_item_and_the_reroll_is_skipped_in_a_closure():
    ab = abstraction()
    state = ab.compress(boots(roll("CasterA", fractured=True)))

    with pytest.raises(NotApplicableError):
        ab.kernel(state, fossils("Fractured"))
    assert ab.reachable([state], [fossils("Fractured")]) == {state}


def test_sets_with_the_same_pool_share_one_kernel_whatever_their_fossils_are():
    ab = abstraction()
    state = ab.compress(boots())
    same = [ChaosOrb(), fossils("Gloveless"), fossils("Dull"), fossils("Gloveless", "Dull")]

    kernels = [ab.kernel(state, action) for action in same]

    assert all(kernel == kernels[0] for kernel in kernels)
    assert len({ab.signature(state, action) for action in same}) == 1
    assert ab.stats.kernels == 1 and ab.stats.hits == len(same) - 1


def test_sets_with_different_pools_have_different_signatures():
    ab = abstraction()
    state = ab.compress(boots())

    signatures = {ab.signature(state, fossils(*names)) for names in (("Scorched",), ("Frigid",), ("Scorched", "Elemental"))}

    assert len(signatures) == 3 and ab.signature(state, fossils("Scorched")) != ab.signature(state, ChaosOrb())


def test_a_mixture_is_cached_by_the_pool_of_each_part():
    ab = abstraction()
    state = ab.compress(boots())

    ab.kernel(state, fossils("Tangled"))
    before = ab.stats

    ab.kernel(state, fossils("Tangled"))

    assert before.kernels == 3  # the four outcome records make three different pools
    assert ab.stats.kernels == 3 and ab.stats.hits == before.hits + 3


def test_the_fractured_distribution_is_cached_by_pool_signature_and_forced_label():
    ab = abstraction()
    state = ab.compress(boots())

    ab.kernel(state, fossils("Fractured", "Dull"))
    ab.kernel(state, fossils("Fractured", "Gloveless"))

    assert ab.stats.kernels == 1 and ab.stats.hits == 1
    assert ab.signature(state, fossils("Fractured", "Dull")) == ab.signature(state, fossils("Fractured", "Gloveless"))
    assert ab.signature(state, fossils("Fractured", "Dull")) != ab.signature(state, fossils("Dull"))


def test_the_family_types_of_a_resonator_tell_apart_what_its_fossils_tell_apart():
    ab = abstraction()
    plain = ab.family_types()
    boosted = ab.family_types(fossils=fossils("Scorched"))

    assert sum(len(names) for names in plain.values()) == 10
    assert sum(len(names) for names in boosted.values()) == 9  # Scorched blocks the cold resistance
    assert set(boosted) != set(plain)
    assert any(chance == 10000 for _, mods in boosted for _, chance, _ in mods)  # the fire boost, x10
    assert ab.family_types(fossils=fossils("Dull")) == plain
    with pytest.raises(ValueError):
        ab.family_types(fossils=fossils("Tangled"))
