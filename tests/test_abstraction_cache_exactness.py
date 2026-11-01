"""Cases where a cache or an identity of the `abstraction` kernel could give a wrong, but plausible, answer (ticket #69).

Three places that the other tests of the kernel do not pin down, each caught by a mutation of the kernel that left every
other test green; here each has a test that fails under it. Every check is `check` of `abstraction_removals_support.py`:
the kernel of the compressed start equals the brute force of `abstraction_metamod_oracle.py`, exactly.

* The pool signature that keys the cache of draws holds the tags a metamod keeps out of a guaranteed draw, and the family
  type of a draw tells which mods a guaranteed tag may pick. One `Abstraction` that meets two items whose pools look the same
  to everything else (a Harvest reforge under `Cannot roll Attack Modifiers` and under the multimod) must not give the
  answer of the first to the second.
* A mod that a Fracturing Orb fractures takes the identity of its slot's contribution to the goal, not the contribution of
  the table tier of the mod that stood for the slot (the two differ for a family whose mods are told apart by tier).
* The tags an Attack or Caster metamod looks at are part of the identity of a crafted or fractured mod and of a family type:
  two mods of one family with the same weight and the same contribution to the goal, one carrying the `attack` tag and one
  not, stay two states (a protected mod and one the Annulment may remove), and the kernel is exact for both.
"""

import dataclasses

import pytest
from abstraction_metamod_oracle import fracture_one
from abstraction_removals_support import (
    AS_5,
    BOW,
    BOW_DATA,
    COLD,
    CRAFT,
    FIRE,
    FIRE_RES,
    MM,
    NA,
    REMOVING,
    SL,
    SOCKET,
    SOCKET_LEAF,
    SPEC_1,
    SPEC_2,
    SPEED_TIER_1,
    abstraction,
    bow,
    build,
    check,
)

from crafting_system.abstraction import Goal
from crafting_system.actions import AnnulmentOrb, ChaosOrb, ExaltedOrb, FracturingOrb, HarvestReforge, Reads

# --- the pool signature and the family type: one Abstraction, two items --------------------------------------------------


@pytest.mark.parametrize("first", ["NA", "MM"])
def test_a_guaranteed_draw_is_exact_for_two_items_that_one_abstraction_meets_one_after_the_other(first):
    """The same pool, the same tag, the same free slots: the Attack metamod filters the guaranteed fire mod, the multimod does not."""
    fire = HarvestReforge("fire")
    ab = abstraction(actions=(*REMOVING, fire), metamods=True)
    starts = {
        "NA": bow(FIRE, SOCKET, SL, AS_5, NA),
        "MM": bow(FIRE, SOCKET, SL, AS_5, MM),
    }
    order = [first, "MM" if first == "NA" else "NA"]

    kernels = {name: check(ab, starts[name], fire) for name in order}

    assert kernels["NA"] != kernels["MM"]  # told apart: the filter changes what the reforge may draw


# --- a fractured mod keeps what its slot gave the goal ----------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ReadsEveryFamily(AnnulmentOrb):
    """An Annulment that declares that it reads every family of the junk: no family is replaced by its family type."""

    def reads(self, data) -> Reads:
        return Reads(junk=True, families=None)


def test_a_fractured_slot_has_the_identity_of_what_the_slot_gave_the_goal():
    """The attack speed of the start is the tier 1 mod; the mod that stands for its slot in the item is another tier."""
    goal = Goal((SOCKET_LEAF, SPEED_TIER_1))
    ab = abstraction(goal, actions=(FracturingOrb(), ReadsEveryFamily()), metamods=False)

    check(ab, bow(FIRE, SOCKET, AS_5, FIRE_RES), FracturingOrb())


# --- the tags of a mod in its identity -------------------------------------------------------------------------------------

CRAFT_2 = "EinharMasterWeaponElementalDamage2"  # the same family as CRAFT, the same weight (none) and tier effect for this goal


def _without_attack(mod):
    return dataclasses.replace(mod, implicit_tags=tuple(tag for tag in mod.implicit_tags if tag != "attack"))


# the second mod of the crafted family, the second bow-gem prefix and the cold damage prefix lose the Attack tag
# (the goal below asks for none of them, so each gives the goal what its twin gives: nothing)
TAGGED_DATA = dataclasses.replace(
    BOW_DATA,
    mods={**BOW_DATA.mods, **{mod_id: _without_attack(BOW_DATA.mods[mod_id]) for mod_id in (CRAFT_2, SPEC_2, COLD)}},
)
TAGS_GOAL = Goal((SOCKET_LEAF, SPEED_TIER_1))

# pairs of starts that differ in one mod: the one with the Attack tag, the one without
# each holds the Attack metamod (that protects attack-tagged mods from an Annulment and filters the draws)
STARTS = {
    "craft-tagged": (FIRE, CRAFT, AS_5, NA, MM),
    "craft-untagged": (FIRE, CRAFT_2, AS_5, NA, MM),
    "bow-gem-tagged": (FIRE, SPEC_1, AS_5, FIRE_RES, NA),
    "bow-gem-untagged": (FIRE, SPEC_2, AS_5, FIRE_RES, NA),
    "damage-tagged": (FIRE, SOCKET, AS_5, FIRE_RES, NA),
    "damage-untagged": (COLD, SOCKET, AS_5, FIRE_RES, NA),
}
ONE_STEP = {"annul": AnnulmentOrb(), "exalted": ExaltedOrb(), "fracture": FracturingOrb()}
SECOND_STEP = {"annul": AnnulmentOrb(), "chaos": ChaosOrb()}


def tagging(*, actions=(FracturingOrb(), AnnulmentOrb(), ExaltedOrb(), ChaosOrb())):
    return abstraction(TAGS_GOAL, actions=actions, metamods=True, data=TAGGED_DATA)


def tagged_start(name: str):
    """The start `name` of `STARTS`, built on the data where a mod of its pair has lost the Attack tag."""
    return build(TAGGED_DATA, BOW, STARTS[name])


@pytest.mark.parametrize("action", ONE_STEP.values(), ids=ONE_STEP.keys())
@pytest.mark.parametrize("name", STARTS)
def test_a_mod_with_and_a_mod_without_the_attack_tag_are_told_apart(name, action):
    check(tagging(), tagged_start(name), action)


@pytest.mark.parametrize("second", SECOND_STEP.values(), ids=SECOND_STEP.keys())
@pytest.mark.parametrize("name", STARTS)
def test_every_item_a_fracture_leaves_keeps_its_tags_for_the_next_action(name, second):
    ab = tagging()

    for after, _ in fracture_one(ab.data, tagged_start(name)):
        check(ab, after, second)


@pytest.mark.parametrize("pair", [("craft-tagged", "craft-untagged"), ("bow-gem-tagged", "bow-gem-untagged")])
def test_the_two_mods_of_a_pair_are_two_states_of_the_item(pair):
    ab = tagging()
    tagged, untagged = (ab.compress(tagged_start(name)) for name in pair)

    assert tagged != untagged


@pytest.mark.parametrize("tag", ["fire", "cold"])
def test_a_fractured_mod_whose_twin_family_has_other_tags_is_still_told_apart_from_it(tag):
    """Fire and cold damage have one weight and give the goal nothing, but only fire damage carries the Attack tag:
    two family types, so the fractured fire mod stands for one family and a tagged reforge may follow it exactly."""
    ab = tagging(actions=(FracturingOrb(), AnnulmentOrb(), ExaltedOrb(), HarvestReforge(tag)))
    start = build(TAGGED_DATA, BOW, (FIRE, SOCKET, AS_5, FIRE_RES))
    (after,) = [
        item for item, _ in fracture_one(ab.data, start) if any(e.mod_id == FIRE and e.fractured for e in item.mods)
    ]

    check(ab, after, HarvestReforge(tag))


def test_an_action_that_picks_a_metamod_among_the_families_it_reads_makes_the_state_model_metamods():
    from abstraction_removals_support import BOW_DATA, REMOVING
    from crafting_system.actions.beast_mods import WildBristleMatron

    assert abstraction(actions=REMOVING).models_metamods is False
    assert abstraction(actions=(*REMOVING, WildBristleMatron()), data=BOW_DATA).models_metamods is True
