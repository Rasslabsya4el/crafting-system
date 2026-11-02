"""The compressed state of the recombinator (ticket #217, ADR-0033, ADR-0062 decisions 1 and 3, ADR-0019 layer 1).

The recombinator declares `Reads.input_classes`: a junk mod of the item in hand and of the donor is a class (its family type and its place
in it: `Slot.kind` `"~n%p"`), and the kernel of `(state, recombinator)` is the average of the action over the concrete items the state of the
item and the state of the donor stand for. Checked here, each against an oracle that lists those items one by one
(`recombinator_state_support`) and reads no placement and no hypergeometric law:

* **done when**: the kernel equals the brute force on the compressed finished items at each grid point of alpha (0.4, 0.7, 1, 1.3, 1.6), on
  cases with classes of several families, a family of two tiers with two weights (the places of a type), a doubled target, a fractured mod,
  a crafted mod in a family of a class, an essence-only (exclusive) mod, one prefix and one suffix on opposite inputs, and a goal that wants
  an implicit and a quality (both copied from the base, ADR-0027);
* a hand figure of the averaging: two single-mod magic items whose mods are in one class of three families share a family one time in three;
* a class of one family is the plain kernel, the one of the two concrete items;
* the key of a donor (`Abstraction.donor_key`): two donors with one key give one kernel on every state, and a different class is a different key;
* what the state does not model is refused with its reason: other influences, another item level, a pool with a two-sided family;
* the state count of the world against the one with every mod named.
"""

import dataclasses
import itertools
from fractions import Fraction

import pytest
from contract_support import finished
from item_state_support import BOOTS, LEVEL, implicit
from recombinator_state_support import check_input_classes_kernel
from recombinator_world import (
    CRAFT_J3,
    GOAL,
    GRID,
    J1,
    J2,
    J3,
    K1,
    K2,
    S1,
    S2,
    S3,
    SE,
    TA1,
    TA2,
    TB1,
    U1A,
    U1B,
    U2A,
    U2B,
    WORLD,
    item,
)

from crafting_system.abstraction import Abstraction, Goal, ImplicitWanted, QualityWanted, Wanted
from crafting_system.actions import OutOfScopeError, Reading, Reads, Recombinator
from crafting_system.actions.recombinator import ALPHA_AXIS
from crafting_system.items import Influence, PlainQuality, Rarity

CRAFTED = {CRAFT_J3: {"crafted": True}}
CASES = {
    # classes of three families (weight 500) and two (1000) on both inputs: the placements overlap in some and not in others
    "classes": (item(TA1, J1, K1), item(TB1, J2, K2)),
    # the same target on both inputs (one family: doubled for sure), and two places of one type (a family of two tiers on each side)
    "doubled_and_places": (item(TA1, U1A, S3), item(TA1, U2B, S3)),
    # a tier-2 target against a tier-1: the family RTA is shared, and picking one closes the other
    "tiers": (item(TA1, J1), item(TA2, J2)),
    # a suffix class of two families on both inputs
    "suffixes": (item(J1, S1, S3), item(K1, S2, S3)),
    # a fractured target on the item in hand: eligible on its own base only
    "fractured": (item(TA1, J1, flags={TA1: {"fractured": True}}), item(TB1, J2, K1)),
    # a fractured junk mod of a class of three families against a junk mod of the same class
    "fractured_junk": (item(J1, K1, flags={J1: {"fractured": True}}), item(J2, TB1)),
    # a crafted prefix in the family of a class of three: the other input's junk may sit in that very family
    "crafted": (item(TA1, CRAFT_J3, K1, flags=CRAFTED), item(TB1, J1, J2)),
    # the crafted mod on both sides is one name: the same family, for sure
    "crafted_both": (item(J1, CRAFT_J3, flags=CRAFTED), item(K1, CRAFT_J3, flags=CRAFTED)),
    # an essence-only suffix on each input: named by its family, exclusive
    "exclusive": (item(J1, S1, SE), item(K1, S2, SE)),
    # one prefix on one input and one suffix on the other: 1p, 1s or 1p1s
    "one_each": (item(J1, rarity=Rarity.MAGIC), item(S2, rarity=Rarity.MAGIC)),
    # two magic items of one prefix each, in one class of three families
    "magic_pair": (item(J1, S2, rarity=Rarity.MAGIC), item(J2, S1, rarity=Rarity.MAGIC)),
}


@pytest.mark.parametrize("alpha", GRID, ids=str)
@pytest.mark.parametrize("name", list(CASES))
def test_the_kernel_equals_the_action_averaged_over_the_items_at_each_grid_point(name, alpha):
    given, donor = CASES[name]
    action = Recombinator(donor)
    ab = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [action], reading=Reading.of({ALPHA_AXIS.name: alpha}))
    check_input_classes_kernel(ab, WORLD, given, action, Reading.of({ALPHA_AXIS.name: alpha}))


def test_the_cases_have_classes_that_hold_several_families_and_places():
    """The cases are not trivial: some class has more than one family, and the places of a type are told apart."""
    ab = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [Recombinator(CASES["classes"][1])])
    kinds = ab._context(frozenset()).kinds
    assert kinds.classed
    types = {kinds.of(WORLD.mods[mod_id]) for mod_id in (J1, J2, J3, K1, K2, U1A, U1B, U2A, U2B, S1, S2, S3, TA1, TA2, TB1)}
    assert kinds.of(WORLD.mods[J1]) == kinds.of(WORLD.mods[J2]) == kinds.of(WORLD.mods[J3])  # one class of three families
    assert kinds.of(WORLD.mods[K1]) == kinds.of(WORLD.mods[K2]) != kinds.of(WORLD.mods[J1])
    assert kinds.of(WORLD.mods[U1A]) == kinds.of(WORLD.mods[U2A]) != kinds.of(WORLD.mods[U1B])  # two places of one family type
    assert kinds.of(WORLD.mods[U1B]) == kinds.of(WORLD.mods[U2B])
    assert kinds.families_of_type(kinds.side_of(kinds.of(WORLD.mods[J1])), kinds.of(WORLD.mods[J1])) == [J1, J2, J3]
    assert len(types) == 10 and kinds.of(WORLD.mods[TA1]) != kinds.of(WORLD.mods[TA2])  # a target and its lower tier give different things
    assert kinds.of(WORLD.mods[SE]) == "RSE"  # the essence-only suffix is in no pool: named by its family


# --- a hand figure ----------------------------------------------------------------------------------------------------------------


def test_two_single_mod_magic_items_in_one_class_share_a_family_one_time_in_three():
    """Pooled count 2: both kept 33%, one 67%. If the two mods are in one family the second pick finds the pool dry, so two mods stay only
    when the families differ: P(two prefixes) = 2/3 * 33/100 = 11/50, whatever alpha is (the three junk prefixes weigh alike)."""
    given, donor = item(J1, rarity=Rarity.MAGIC), item(J2, rarity=Rarity.MAGIC)
    action = Recombinator(donor)
    for alpha in GRID:
        ab = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [action], reading=Reading.of({ALPHA_AXIS.name: alpha}))
        kernel = ab.kernel(ab.compress(given), action)
        two = sum((chance for state, chance in kernel.items() if state.count(state.slots[0].side) == 2), Fraction(0))
        assert two == Fraction(2, 3) * Fraction(33, 100)
        assert sum(kernel.values()) == 1


def test_a_class_of_one_family_is_the_plain_kernel_of_the_two_items():
    """Where each class is one family the names are known and the kernel is the one of the concrete items (no averaging)."""
    given, donor = item(TA1, TB1, S3), item(TA2, TB1, S3)
    action = Recombinator(donor)
    for alpha in (Fraction(1), Fraction(8, 5)):
        reading = Reading.of({ALPHA_AXIS.name: alpha})
        ab = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [action], reading=reading)
        expected: dict = {}
        for chance, result in finished(action.outcomes_under(WORLD, given, reading), WORLD):
            expected[ab.compress(result)] = expected.get(ab.compress(result), Fraction(0)) + chance
        assert dict(ab.kernel(ab.compress(given), action)) == expected


# --- quality and implicits are copied from the base ----------------------------------------------------------------------------------


def test_the_implicits_and_the_quality_of_the_chosen_base_are_the_result_s():
    """The goal wants an Exarch implicit of grade 2 or more and 20% quality: the result holds the item's with chance 1/2 and the donor's with 1/2
    (an implicit of the donor, never rolled afresh), at every grid point, against the average of the action over the items."""
    goal = Goal((Wanted(frozenset({TB1})),), (ImplicitWanted(frozenset({"AvoidShockEldritchImplicit1", "AvoidShockEldritchImplicit2", "AvoidShockEldritchImplicit3"}), 2),), quality=QualityWanted(None, 20))
    given = item(TB1, J1, implicits=(implicit("AvoidShockEldritchImplicit3"),), quality=PlainQuality(0))
    donor = item(J2, K1, quality=PlainQuality(20))
    action = Recombinator(donor)
    for alpha in GRID:
        reading = Reading.of({ALPHA_AXIS.name: alpha})
        ab = Abstraction(WORLD, goal, BOOTS, LEVEL, [action], reading=reading)
        assert ab.tracks_implicits and ab.tracks_quality
        check_input_classes_kernel(ab, WORLD, given, action, reading)
        kernel = ab.kernel(ab.compress(given), action)
        has_implicit = sum((chance for state, chance in kernel.items() if state.implicits[0].grade == 3), Fraction(0))
        has_quality = sum((chance for state, chance in kernel.items() if state.quality == PlainQuality(20)), Fraction(0))
        assert has_implicit == Fraction(1, 2) == has_quality  # the base is the item in hand or the donor, one half each
        assert all((state.implicits[0].grade == 3) != (state.quality == PlainQuality(20)) for state in kernel)  # they come from the same base


# --- the key of a donor -----------------------------------------------------------------------------------------------------------


def test_two_donors_with_one_key_give_one_kernel_and_another_class_is_another_key():
    given = item(TA1, J1, K1)
    donors = {
        "rare_j2_k2": item(TB1, J2, K2),
        "rare_j3_k1": item(TB1, J3, K1),  # other names in the same classes
        "magic": item(J3, S2, rarity=Rarity.MAGIC),
    }
    action = Recombinator(donors["rare_j2_k2"])
    ab = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [action])
    keys = {name: ab.donor_key(ab.compress(donor), action) for name, donor in donors.items()}
    assert keys["rare_j2_k2"] == keys["rare_j3_k1"] != keys["magic"]
    state = ab.compress(given)
    assert dict(ab.kernel(state, Recombinator(donors["rare_j2_k2"]))) == dict(ab.kernel(state, Recombinator(donors["rare_j3_k1"])))
    # the key forgets what the action never reads: the rarity (one prefix kept in a rare 1-mod item and a magic one), the offer and the imprints
    rare_one, magic_one = item(J2), item(J2, rarity=Rarity.MAGIC)
    assert ab.donor_key(ab.compress(rare_one), action) == ab.donor_key(ab.compress(magic_one), action)
    assert dict(ab.kernel(state, Recombinator(rare_one))) == dict(ab.kernel(state, Recombinator(magic_one)))


def test_the_key_of_an_action_that_reads_no_classes_is_the_state_itself():
    from crafting_system.actions import ChaosOrb

    ab = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [Recombinator(item(J1))])
    state = ab.compress(item(J1))
    assert ab.donor_key(state, ChaosOrb()) is state


# --- what the state does not model ---------------------------------------------------------------------------------------------------


def test_an_input_with_other_influences_is_refused_with_its_reason():
    given = item(TA1, J1)
    donor = item(TB1, J2, influences=frozenset({Influence.SHAPER}))
    action = Recombinator(donor)
    ab = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [action])
    with pytest.raises(OutOfScopeError, match="other influences"):
        ab.kernel(ab.compress(given), action)


def test_a_donor_of_another_item_level_that_leaves_the_result_in_this_one_has_no_state():
    given, donor = item(TA1, J1), item(TB1, J2)
    donor = dataclasses.replace(donor, item_level=LEVEL - 1)  # (84 + 83) // 2 + 2 = 85, capped at 84: the result is at 84, the donor is not
    action = Recombinator(donor)
    ab = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [action])
    with pytest.raises(OutOfScopeError, match="another base or item level"):
        ab.kernel(ab.compress(given), action)


def test_a_planner_that_prices_no_inputs_still_refuses_the_action():
    given, donor = item(TA1, J1), item(TB1, J2)
    action = Recombinator(donor)
    ab = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [action], allow_inputs=False)
    with pytest.raises(OutOfScopeError, match="consumes other items"):
        ab.kernel(ab.compress(given), action)


# --- the state count --------------------------------------------------------------------------------------------------------------


class NamedRecombinator(Recombinator):
    """The recombinator as it was before ticket #217: every family told apart by name, so the state is the multiset of mods (the raw state)."""

    def reads(self, data):
        return Reads(junk=True, families=None, input_mods=True, implicits=True, quality=True)


def test_the_classes_merge_the_items_the_names_keep_apart_and_keep_the_tiers_the_names_lose():
    """Of the items of up to three prefixes of the world, the classes give fewer states than the names (the junk of one class is one state), and tell
    apart what the names merge: two tiers of one family have one name and two weights, so a state by name cannot give the recombinator its pool."""
    prefixes = [TA1, TA2, TB1, J1, J2, J3, K1, K2, U1A, U1B, U2A, U2B]
    items = [item(*chosen) for size in range(1, 4) for chosen in itertools.combinations(prefixes, size) if len({WORLD.mods[m].families for m in chosen}) == size]
    donor = item(TB1, J2)
    by_class = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [Recombinator(donor)])
    by_name = Abstraction(WORLD, GOAL, BOOTS, LEVEL, [NamedRecombinator(donor)])
    classed = {by_class.compress(each) for each in items}
    named = {by_name.compress(each) for each in items}
    assert len(classed) < len(named) < len(items)
    assert by_name.compress(item(U1A)) == by_name.compress(item(U1B))  # one family, the weights 1000 and 250 lost
    assert by_class.compress(item(U1A)) != by_class.compress(item(U1B))
    assert by_class.compress(item(J1, K1)) == by_class.compress(item(J2, K2)) != by_class.compress(item(J1, J2))
