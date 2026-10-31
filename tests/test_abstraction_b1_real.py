"""Verification layer 1 on boots, a helmet and a ring of the real 3.29.3.3 dump (ticket #59).

The real pools have 18 to 35 families, too many for the brute force of `abstraction_oracle.py`, so each
case keeps a few families of the real pool (a few mods each, the real weights and levels) and the
fractured mod, the forced mod and the crafted mods it uses. The kernel is compared with the brute
force on that subset, in exact fractions, with and without a fractured mod and a crafted mod.

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there, which is the case in CI.
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_oracle import assert_same_distribution, crafted_item, uncrafted_item
from abstraction_support import PASSING, check_kernel, real_game_data

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import ApplyEssence, BenchCraft, ChaosOrb, RemoveCraftedMods, build_pool
from crafting_system.items import ExplicitMod, Item, Rarity, Side, tier_table

LEVEL = 86
MODS_PER_FAMILY = 3


@pytest.fixture(scope="module")
def real():
    return real_game_data()


def rolled(data, mod_id, **flags):
    return ExplicitMod(mod_id, 1, tuple(min(s.min, s.max) for s in data.mods[mod_id].stats), **flags)


def subset(data, base_id, families, extra_ids):
    """The data with only `extra_ids` and the first few mods of each of `families` of the pool of `base_id`."""
    pool = build_pool(data, Item.build(data, base_id=base_id, item_level=LEVEL, rarity=Rarity.RARE))
    keep = set(extra_ids)
    for family in pool:
        if family.family in families:
            keep.update(sorted(entry.mod.id for entry in family.mods)[:MODS_PER_FAMILY])
    return dataclasses.replace(data, mods={mod_id: data.mods[mod_id] for mod_id in data.mods if mod_id in keep})


def life_of(small):
    return Wanted(frozenset(mod.id for mod in small.mods.values() if mod.families == ("IncreasedLife",)))


CASES = {
    "boots": dict(
        base="Metadata/Items/Armours/Boots/BootsInt1",
        families={"IncreasedLife", "MovementVelocity", "IncreasedMana", "Intelligence", "FireResistance", "StunRecovery", "ColdResistance"},
        fractured="MovementVelocity6", forced="Intelligence8", essence="Shrieking Essence of Spite",
        crafts=("HelenaMasterIncreasedLife1", "EinharMasterAvoidElementalAilments1"),
        junk=("IncreasedMana", "FireResistance"),
    ),
    "helmet": dict(
        base="Metadata/Items/Armours/Helmets/HelmetDex1",
        families={"IncreasedLife", "DefencesPercent", "BaseLocalDefences", "Intelligence", "FireResistance", "StunRecovery", "ChaosResistance"},
        fractured="ChaosResist6", forced="ManaReservationEfficiencyEssence6_", essence="Shrieking Essence of Loathing",
        crafts=("HelenaMasterIncreasedLife1", "HelenaMasterColdResist1_"),
        junk=("DefencesPercent", "FireResistance"),
    ),
    "ring": dict(
        base="Metadata/Items/Rings/Ring1",
        families={"IncreasedLife", "IncreasedMana", "IncreasedEnergyShield", "AllAttributes", "Strength", "FireResistance", "LifeRegeneration"},
        fractured="AllAttributes7", forced="StrengthEssence7_", essence="Deafening Essence of Rage",
        crafts=("HelenaMasterIncreasedLife1", "HelenaMasterColdResist1_"),
        junk=("IncreasedMana", "FireResistance"),
    ),
}


def first_of(data, family):
    """The mod of `family` (an ordinary prefix or suffix) with the smallest id: a junk mod of that family."""
    return min(
        mod.id
        for mod in data.mods.values()
        if mod.families == (family,) and mod.generation_type in ("prefix", "suffix") and mod.domain == "item"
    )


def build(real, name):
    case = CASES[name]
    ids = {case["fractured"], case["forced"], *case["crafts"]}
    data = subset(real, case["base"], case["families"], ids)
    goal = Goal((life_of(data), Wanted(frozenset({case["forced"]}))))
    enabled = [ApplyEssence(case["essence"]), RemoveCraftedMods(), *(BenchCraft(mod_id) for mod_id in case["crafts"])]
    return case, data, Abstraction(data, goal, case["base"], LEVEL, enabled)


def item_on(data, case, *mods, rarity=Rarity.RARE):
    return Item.build(data, base_id=case["base"], item_level=LEVEL, rarity=rarity, mods=tuple(mods))


def starts(data, case):
    """Rare items of the case: junk only, a fractured mod and junk, and the same with a crafted mod."""
    junk = [rolled(data, first_of(data, family)) for family in case["junk"]]
    fractured = rolled(data, case["fractured"], fractured=True)
    plain = item_on(data, case, *junk)
    fixed = item_on(data, case, fractured, *junk)
    craft = case["crafts"][0]
    return {
        "junk": plain,
        "fractured": fixed,
        "crafted": crafted_item(data, plain, craft),
        "fractured_and_crafted": crafted_item(data, fixed, craft),
    }


@pytest.mark.parametrize("start", ["junk", "fractured", "crafted", "fractured_and_crafted"])
@pytest.mark.parametrize("name", CASES)
def test_the_essence_kernel_equals_the_brute_force(real, name, start):
    case, data, ab = build(real, name)
    item = starts(data, case)[start]

    kernel = check_kernel(ab, item, ApplyEssence(case["essence"]), data=data, forced=case["forced"])

    assert all(state.status[1] is PASSING and not state.crafted for state in kernel)


@pytest.mark.parametrize("name", CASES)
def test_a_chaos_orb_on_a_fractured_item_equals_the_brute_force(real, name):
    case, data, ab = build(real, name)

    check_kernel(ab, starts(data, case)["fractured_and_crafted"], ChaosOrb(), data=data)


@pytest.mark.parametrize("start", ["junk", "fractured"])
@pytest.mark.parametrize("name", CASES)
def test_a_bench_craft_equals_the_deterministic_result(real, name, start):
    case, data, ab = build(real, name)
    item = starts(data, case)[start]
    craft = case["crafts"][1]  # the first craft clashes with the Life family, which the junk does not hold

    kernel = ab.kernel(ab.compress(item), BenchCraft(craft))

    assert_same_distribution(kernel, {ab.compress(crafted_item(data, item, craft)): Fraction(1)})


@pytest.mark.parametrize("name", CASES)
def test_remove_crafted_mods_equals_the_deterministic_result(real, name):
    case, data, ab = build(real, name)
    item = starts(data, case)["fractured_and_crafted"]

    kernel = ab.kernel(ab.compress(item), RemoveCraftedMods())

    assert_same_distribution(kernel, {ab.compress(uncrafted_item(data, item)): Fraction(1)})


def test_a_low_essence_on_a_normal_item_equals_the_brute_force(real):
    data = subset(real, CASES["boots"]["base"], CASES["boots"]["families"] | {"LifeRegeneration"}, {"ColdResist1", "IncreasedLife1"})
    ab = Abstraction(data, Goal((life_of(data), Wanted(frozenset({"ColdResist1"})))), CASES["boots"]["base"], LEVEL)
    normal = Item.build(data, base_id=CASES["boots"]["base"], item_level=LEVEL, rarity=Rarity.NORMAL)

    kernel = check_kernel(ab, normal, ApplyEssence("Whispering Essence of Hatred"), data=data, forced="ColdResist1", cap=35)

    assert {state.flags.rarity for state in kernel} == {Rarity.RARE}


def test_the_craft_that_clashes_with_a_family_tells_that_family_apart_on_the_real_pool(real):
    case, data, ab = build(real, "boots")
    life = ab.compress(item_on(data, case, rolled(data, first_of(data, "IncreasedLife"))))
    mana = ab.compress(item_on(data, case, rolled(data, first_of(data, "IncreasedMana"))))

    assert {slot.kind for slot in life.slots} == {"IncreasedLife"} and {slot.kind for slot in mana.slots} == {""}
    assert life.slots[0].side is Side.PREFIX


def test_a_crafted_mod_of_two_families_keeps_both_out_of_the_representative_item(real):
    craft = "JunMaster2DexterityAndIntelligence1_"  # a suffix of the families Dexterity and Intelligence
    case = CASES["boots"]
    data = subset(real, case["base"], case["families"] | {"Dexterity"}, {craft, case["crafts"][0]})
    ab = Abstraction(data, Goal((life_of(data),)), case["base"], LEVEL, [RemoveCraftedMods(), BenchCraft(case["crafts"][0])])
    item = item_on(data, case, rolled(data, first_of(data, "ColdResistance")), rolled(data, craft, crafted=True))

    (after,) = ab.kernel(ab.compress(item), RemoveCraftedMods())

    assert not after.crafted and len(after.slots) == 1
