"""What a fossil set declares without building its outcomes (`ApplyFossils.reach_batch`, `actions/fossil_reach.py`, #1073), against the
built outcomes of every set of the fixture listing.

For each item and each list of leaves (each leaf a set X of mods), every set of the listing is compared with its own outcomes: the declared
shape with what the outcomes do (a fracture, a corruption), every declared chance with the EXACT chance that one use puts on the item a
mod of X (the forced mod, or a drawn one: `Outcomes.distribution` per part, by its share), the bound on every leaf at once with the exact
chance of that, and a zero is declared only where the exact chance is zero. The leaves cover a forced mod (Hollow's, Glyphic's) that passes a
leaf and one that only takes a slot, the mods only a Faceted Fossil adds, an essence-only mod (no weight anywhere: zero but where Glyphic forces
it), the Tangled sets (a mixture of outcome records), a Sanctified set (the level factor), a fractured item and a lower item level.
"""

import random
from collections import defaultdict
from fractions import Fraction

import pytest
from test_actions_fossil import BOOTS, DATA, GLOVES, boots, roll

from crafting_system.actions import ActionError, ApplyFossils, fossil_actions
from crafting_system.actions.fossil_reach import MARGIN

LEAVES = {
    # two disjoint leaves (the joint bound is used) on mods of ordinary weight
    "life and fire resistance": ({"LifeA", "LifeB"}, {"FireResA"}),
    # overlapping leaves, one with a Glyphic mod that only a forced draw puts on and one with Hollow's forced mod
    "fire, forced": ({"FireA", "FireB", "FireResA", "GlyA", "GlyX"}, {"AbyssSocketA", "ColdResA"}),
    # an essence-only mod: no draw puts it on, only a Glyphic Fossil that forces it
    "essence only": ({"GlyB"},),
    # the mod a Faceted Fossil adds to the pool, and a leaf of mods every set drops or keeps
    "added mod": ({"DelveGemA"}, {"BleedPhysA", "BleedAtkA", "CasterA"}),
    # three leaves, two of them disjoint
    "three": ({"RarityA"}, {"MinionA", "BareA"}, {"RarityA", "BareB"}),
}
ITEMS = {
    "boots": lambda: boots(),
    "boots fractured": lambda: boots(roll("ColdResA", fractured=True)),
    "boots level 45": lambda: boots(item_level=45),
    "gloves": lambda: boots(base=GLOVES),
}


def passes_of(leaves):
    return lambda mod: tuple(mod.id in leaf for leaf in leaves)


def exact(outcomes, leaves, data=DATA) -> tuple[tuple[Fraction, ...], Fraction]:
    """The exact chance that one use puts on the item a mod of each leaf (the forced mod or a drawn one), and of every leaf at once."""
    passes = passes_of(leaves)
    single = [Fraction(0)] * len(leaves)
    together = Fraction(0)
    for share, part in outcomes.components:
        forced = passes(data.mods[part.forced]) if part.forced else (False,) * len(leaves)
        for outcome, chance in part.distribution(passes).items():
            hit = [forced[leaf] or any(label[leaf] for label, count in outcome if count > 0) for leaf in range(len(leaves))]
            for leaf in range(len(leaves)):
                if hit[leaf]:
                    single[leaf] += share * chance
            if all(hit):
                together += share * chance
    return tuple(single), together


def keeps(outcomes, item) -> bool:
    """Whether the outcomes keep the shape of `item`: no fracture, and a sample has its rarity, corruption, influences and fractured mods."""
    if outcomes.fractures:
        return False
    rng = random.Random(1073)
    for _ in range(3):
        result = outcomes.sample(rng)
        same = (result.rarity, result.corrupted, result.influences) == (item.rarity, item.corrupted, item.influences)
        if not same or {mod.mod_id for mod in result.fractured_mods} != {mod.mod_id for mod in item.fractured_mods}:
            return False
    return True


SAMPLE = 450  # twin classes per item whose exact chances are worked out (about 3 ms per class and list of leaves; all of them take 3 minutes)


def representatives(actions, item):
    """A fixed sample of `SAMPLE` twin classes (equal outcomes on the base, `tests/test_actions_twin_key.py`; a set with no key is a class of its
    own); every member of a class is checked against the exact chances of its first."""
    classes = defaultdict(list)
    for position, action in enumerate(actions):
        key = action.twin_key(DATA, item)
        classes[("set", position) if key is None else key].append(position)
    found = list(classes.values())
    return random.Random(1073).sample(found, min(SAMPLE, len(found)))


@pytest.mark.parametrize("item_name", ITEMS)
def test_every_set_of_the_listing_declares_its_shape_and_never_a_chance_below_the_exact_one(item_name):
    item = ITEMS[item_name]()
    actions = fossil_actions(DATA, item)
    assert len(actions) > 1000
    declared_by_leaves = {name: ApplyFossils.reach_batch(DATA, item, tuple(actions), passes_of(leaves)) for name, leaves in LEAVES.items()}
    checked = zeros = tangled = forced = refused = 0
    for members in representatives(actions, item):
        try:
            outcomes = actions[members[0]].outcomes(DATA, item)
        except ActionError:
            refused += 1
            for name in LEAVES:
                assert all(declared_by_leaves[name][position] is None for position in members), actions[members[0]].fossils
            continue
        shape = keeps(outcomes, item)
        for name, leaves in LEAVES.items():
            single, together = exact(outcomes, leaves) if shape else (None, None)
            for position in members:
                declared = declared_by_leaves[name][position]
                label = (name, actions[position].fossils)
                if declared is None:
                    continue  # no declaration is always allowed (the planner then builds the outcomes)
                assert declared.keeps_shape == shape, label
                if not shape:
                    continue
                assert declared.chances is not None and len(declared.chances) == len(leaves), label
                for leaf, (bound, chance) in enumerate(zip(declared.chances, single)):
                    assert bound >= chance, (label, leaf, bound, float(chance))
                    assert (bound == 0) == (chance == 0) or bound > 0, label
                    if bound == 0:
                        assert chance == 0, label
                        zeros += 1
                if declared.together is not None:
                    assert declared.together >= together, (label, declared.together, float(together))
                    if declared.together == 0:
                        assert together == 0, label
                checked += 1
                tangled += "Tangled Fossil" in actions[position].fossils
                forced += bool({"Hollow Fossil", "Glyphic Fossil"} & set(actions[position].fossils))
    # the listing reaches every case the bound has a branch for
    assert checked > 3 * SAMPLE and zeros > 0 and tangled > 0 and forced > 0, (checked, zeros, tangled, forced, refused)


def test_a_declared_zero_is_exact_and_a_forced_mod_that_passes_makes_the_chance_one():
    """GlyB (essence only, no spawn weight) is put on only by a Glyphic Fossil, which may force it: 0 for every other set, more than 0 there."""
    item = boots()
    actions = [ApplyFossils(("Scorched Fossil",)), ApplyFossils(("Glyphic Fossil",)), ApplyFossils(("Hollow Fossil",)), ApplyFossils(("Faceted Fossil",))]
    found = ApplyFossils.reach_batch(DATA, item, tuple(actions), passes_of(({"GlyB"}, {"AbyssSocketA"}, {"DelveGemA"})))
    scorched, glyphic, hollow, faceted = found
    assert scorched.keeps_shape and scorched.chances == (0.0, 0.0, 0.0)
    assert glyphic.chances[0] > 0 and glyphic.chances[1] == 0.0
    assert hollow.chances[1] == 1.0  # Hollow forces the abyssal socket mod on every use
    assert faceted.chances[2] > 0 and faceted.chances[0] == 0.0
    assert ApplyFossils(("Glyphic Fossil",)).outcomes(DATA, item)  # it applies: the zero of the others is not a refusal


def test_a_bound_is_raised_by_its_margin_and_never_above_one():
    """Every positive declared chance carries the float margin of the module text: it is above the level 1 argument worked in fractions."""
    item = boots()
    found = ApplyFossils.reach_batch(DATA, item, (ApplyFossils(("Lucent Fossil",)),), passes_of(({"LifeA", "LifeB"},)))[0]
    assert 0 < found.chances[0] <= 1
    single, _together = exact(ApplyFossils(("Lucent Fossil",)).outcomes(DATA, item), ({"LifeA", "LifeB"},))
    assert found.chances[0] >= float(single[0]) * (1 + MARGIN / 2)


def test_bloodstained_and_fractured_sets_declare_that_they_leave_the_shape():
    item = boots()
    found = ApplyFossils.reach_batch(
        DATA, item, (ApplyFossils(("Bloodstained Fossil",)), ApplyFossils(("Fractured Fossil", "Scorched Fossil"))), passes_of(({"LifeA"},))
    )
    assert [answer.keeps_shape for answer in found] == [False, False]
    assert all(answer.chances is None for answer in found)


def test_a_forced_mod_whose_family_is_a_pool_family_of_the_other_side_is_charged_on_that_side():
    """GlyA is a suffix; given the family of the prefix `LifeA`, forcing it takes a prefix family out of the pool and a suffix slot (checker
    round 1: a bound that charged the forced mod to one side only was below the exact chance). Every Glyphic set, on bare boots and on boots
    with one free slot per side, against the exact chance."""
    import dataclasses

    mods = dict(DATA.mods)
    mods["GlyA"] = dataclasses.replace(DATA.mods["GlyA"], families=DATA.mods["LifeA"].families)
    data = dataclasses.replace(DATA, mods=mods)
    leaves = ({"RarityA"}, {"BleedAtkA", "CasterA"})  # each with a candidate on both items (a leaf with none would make the others 1)
    tight = boots(*(roll(mod_id, fractured=True) for mod_id in ("FireA", "BareA", "ColdResA", "MinionA")))
    checked = 0
    for item in (boots(), tight):
        actions = tuple(action for action in fossil_actions(data, item) if "Glyphic Fossil" in action.fossils and len(action.fossils) <= 2)
        for action, declared in zip(actions, ApplyFossils.reach_batch(data, item, actions, passes_of(leaves))):
            if declared is None or not declared.keeps_shape:
                continue
            single, together = exact(action.outcomes(data, item), leaves, data)
            assert all(bound >= chance for bound, chance in zip(declared.chances, single)), (action.fossils, declared.chances, [float(c) for c in single])
            assert declared.together is None or declared.together >= together
            checked += 1
    assert checked > 10


def test_a_tangled_glyphic_set_takes_the_largest_bound_over_its_forced_mods_per_outcome_record():
    """In a Tangled set the Glyphic Fossil's forced mod follows the outcome record, so the bound takes the largest over the forced mods for each
    record and then the mean over records (the largest of the means over records may be below the exact chance). Every Tangled set with a
    Glyphic Fossil, with GlyA given a prefix family (its forced use then takes a prefix family as well as a suffix slot, unlike GlyB's), on
    bare boots and on boots with one free slot per side, against the exact chance."""
    import dataclasses

    mods = dict(DATA.mods)
    mods["GlyA"] = dataclasses.replace(DATA.mods["GlyA"], families=DATA.mods["LifeA"].families)
    data = dataclasses.replace(DATA, mods=mods)
    leaves = ({"RarityA"}, {"BleedAtkA", "CasterA"}, {"LifeB", "FireResA"})
    tight = boots(*(roll(mod_id, fractured=True) for mod_id in ("FireA", "BareA", "ColdResA", "MinionA")))
    checked = 0
    for item in (boots(), tight):
        actions = tuple(
            action for action in fossil_actions(data, item) if {"Glyphic Fossil", "Tangled Fossil"} <= set(action.fossils) and len(action.fossils) <= 3
        )
        for action, declared in zip(actions, ApplyFossils.reach_batch(data, item, actions, passes_of(leaves))):
            if declared is None or not declared.keeps_shape:
                continue
            single, together = exact(action.outcomes(data, item), leaves, data)
            assert all(bound >= chance for bound, chance in zip(declared.chances, single)), (action.fossils, declared.chances, [float(c) for c in single])
            assert declared.together is None or declared.together >= together
            checked += 1
    assert checked > 5


def test_on_a_shield_with_four_fractured_mods_the_glyphic_set_declares_a_bound_at_or_above_the_exact_chance():
    """The checker's counterexample on the real data: SpellBlockOnLowLifeEssence1, a suffix a Glyphic Fossil may force, has the family of the
    prefix pool family SpellBlockPercentage; with one prefix slot left, the bound read without that family was 0.031684 against an exact
    0.032397 for the caster damage prefixes; the forced mod is now charged on the side of the family it takes."""
    from abstraction_support import real_game_data

    from crafting_system.items import ExplicitMod, Item, Rarity

    data = real_game_data()
    mods = ("IncreasedLife0", "IncreasedMana1", "Intelligence1", "LifeRegeneration1")
    item = Item.build(
        data, base_id="Metadata/Items/Armours/Shields/ShieldInt3", rarity=Rarity.RARE, item_level=86,
        mods=tuple(ExplicitMod(mod_id, tuple(stat.min for stat in data.mods[mod_id].stats), fractured=True) for mod_id in mods),
    )
    action = ApplyFossils(("Glyphic Fossil",))
    leaves = ({mod.id for mod in data.mods.values() if "WeaponCasterDamagePrefix" in mod.families},)
    declared = ApplyFossils.reach_batch(data, item, (action,), passes_of(leaves))[0]
    single, _together = exact(action.outcomes(data, item), leaves, data)
    assert single[0] > Fraction(31684, 1000000) and declared.chances[0] >= single[0]
    # a set that forces nothing still declares its bound there
    plain = ApplyFossils(("Pristine Fossil",))
    bound = ApplyFossils.reach_batch(data, item, (plain,), passes_of(leaves))[0]
    assert bound.chances[0] >= exact(plain.outcomes(data, item), leaves, data)[0][0]


def test_a_set_the_item_refuses_declares_nothing():
    """The Hollow Fossil works on boots only, and the Gloveless Fossil on no gloves: no declaration on gloves."""
    item = boots(base=GLOVES)
    found = ApplyFossils.reach_batch(DATA, item, (ApplyFossils(("Hollow Fossil",)), ApplyFossils(("Gloveless Fossil",))), passes_of(({"LifeA"},)))
    assert found == (None, None)
    assert BOOTS != GLOVES
