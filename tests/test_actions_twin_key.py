"""The twin key of an action: sets with equal keys give equal outcomes, found without building a pool (ticket #118, piece D).

`Action.twin_key(data, item)` is None unless an action declares it. A set of fossils declares one; two sets
of one catalog listing with equal keys have the same kernel on every item of that base. Here that is
checked three ways: the default of the other actions, the whole fossil listing on the fixture world
(every key class against its first member, which is every pair by transitivity), and the real boots.
"""

import random
from collections import defaultdict

import pytest
from abstraction_support import real_game_data
from test_actions_fossil import DATA, boots, roll

from crafting_system.actions import (
    ActionError,
    ApplyEssence,
    ApplyFossils,
    BenchCraft,
    ChaosOrb,
    HarvestReforge,
    catalog,
    fossil_actions,
)
from crafting_system.items import Influence, Item, Rarity

# ---------------------------------------------------------------------------------------------
# what two sets must share when their keys are equal


def signature(action, data, item):
    """Everything `outcomes` says that a kernel reads, as a comparable value; a refusal is its type."""
    try:
        outcomes = action.outcomes(data, item)
    except ActionError as refusal:
        return ("refused", type(refusal))
    parts = []
    for share, part in outcomes.components:
        pool = tuple((family.family, tuple((entry.mod.id, entry.weight) for entry in family.mods)) for family in part.pool)
        parts.append((share, part.forced, tuple(entry.mod_id for entry in part.retained.mods), pool))
    return (tuple(parts), outcomes.fractures)


def classes_by_key(actions, data, item):
    classes = defaultdict(list)
    for action in actions:
        key = action.twin_key(data, item)
        if key is not None:
            classes[key].append(action)
    return classes


# ---------------------------------------------------------------------------------------------
# the default


def test_an_influenced_item_has_no_key():
    """The pool of an influenced item holds mods whose tags the key does not read, so no set is called a twin there."""
    import dataclasses

    influenced = dataclasses.replace(boots(), influences=frozenset({Influence.HUNTER}))

    assert all(action.twin_key(DATA, influenced) is None for action in fossil_actions(DATA, boots())[:20])
    assert fossil_actions(DATA, boots())[0].twin_key(DATA, boots()) is not None


def test_an_action_that_declares_no_key_has_none():
    item = boots()
    some = [ChaosOrb(), HarvestReforge("lightning"), ApplyEssence("Essence of Alpha")]
    some += [action for action in catalog(DATA, item) if isinstance(action, BenchCraft)][:1]
    assert len(some) >= 3
    for action in some:
        assert action.twin_key(DATA, item) is None


# ---------------------------------------------------------------------------------------------
# the fixture world

ITEMS = {
    "empty rare": boots(),
    "fractured mod": boots(roll("LifeA", fractured=True)),
    "fractured and ordinary": boots(roll("FireResA", fractured=True), roll("FireA")),
}


@pytest.mark.parametrize("name", ITEMS)
def test_equal_keys_give_equal_outcomes_on_the_fixture_world(name):
    item = ITEMS[name]
    actions = fossil_actions(DATA, item)
    classes = classes_by_key(actions, DATA, item)
    assert sum(map(len, classes.values())) == len(actions)  # a set declares a key
    for members in classes.values():
        first = signature(members[0], DATA, item)
        for other in members[1:]:
            assert signature(other, DATA, item) == first, (members[0].fossils, other.fossils)


@pytest.mark.parametrize("name", ITEMS)
def test_some_distinct_sets_are_twins_on_the_fixture_world(name):
    item = ITEMS[name]
    classes = classes_by_key(fossil_actions(DATA, item), DATA, item)
    twins = [members for members in classes.values() if len(members) > 1]
    assert twins
    assert len(classes) < sum(map(len, classes.values()))


def test_a_fossil_that_touches_nothing_is_a_twin_of_one_that_boosts_a_tag_no_mod_has():
    item = boots()
    # Gloveless only forbids a base tag; Dull boosts "attribute", which no mod of the pool carries
    gloveless = ApplyFossils(("Gloveless Fossil",))
    dull = ApplyFossils(("Dull Fossil",))
    assert gloveless.twin_key(DATA, item) == dull.twin_key(DATA, item)
    assert signature(gloveless, DATA, item) == signature(dull, DATA, item)


def test_the_tags_of_a_mod_the_set_adds_count():
    item = boots()
    # the Delve mod that Faceted adds carries "attribute", so Dull now changes its weight
    faceted_dull = ApplyFossils(("Dull Fossil", "Faceted Fossil"))
    faceted_gloveless = ApplyFossils(("Faceted Fossil", "Gloveless Fossil"))
    assert faceted_dull.twin_key(DATA, item) != faceted_gloveless.twin_key(DATA, item)
    assert signature(faceted_dull, DATA, item) != signature(faceted_gloveless, DATA, item)


def test_the_key_starts_with_the_family_name_and_is_hashable():
    key = ApplyFossils(("Scorched Fossil",)).twin_key(DATA, boots())
    assert key[0] == "fossils"
    hash(key)


def test_the_key_tells_flags_and_forcing_apart():
    item = boots()
    keys = {
        name: ApplyFossils((name,)).twin_key(DATA, item)
        for name in (
            "Gloveless Fossil", "Sanctified Fossil", "Opulent Fossil", "Hollow Fossil", "Glyphic Fossil",
            "Tangled Fossil", "Faceted Fossil", "Fractured Fossil",
        )
    }  # fmt: skip
    assert len(set(keys.values())) == len(keys)


# ---------------------------------------------------------------------------------------------
# the real boots

BOOTS = "Sorcerer Boots"


@pytest.fixture(scope="module")
def real():
    return real_game_data()


def test_the_twin_classes_of_the_real_boots(real):
    base = next(base.id for base in real.base_items.values() if base.name == BOOTS)
    item = Item.build(real, base_id=base, item_level=86, rarity=Rarity.RARE, mods=())
    actions = fossil_actions(real, item)
    keys = [action.twin_key(real, item) for action in actions]
    classes = defaultdict(list)
    for action, key in zip(actions, keys):
        classes[key].append(action)
    print(f"\ntwin_key of {len(actions)} sets: {len(classes)} distinct keys")
    assert None not in classes
    ways = {key: ("Tangled Fossil" in members[0].fossils) for key, members in classes.items()}
    plain_classes = sum(1 for tangled in ways.values() if not tangled)
    print(f"{plain_classes} keys of the sets without a Tangled Fossil, {len(classes) - plain_classes} of those with one")
    # 3,937 pools are distinct among the 10,670 sets without a Tangled Fossil (measured by building them all)
    assert plain_classes < 4_100
    assert len(classes) < 6_000

    rng = random.Random(118)
    plain = [members for members in classes.values() if len(members) > 1 and not any("Tangled Fossil" in m.fossils for m in members)]
    tangled = [members for members in classes.values() if len(members) > 1 and any("Tangled Fossil" in m.fossils for m in members)]
    assert plain and tangled
    pairs = [rng.sample(rng.choice(plain), 2) for _ in range(300)]
    pairs += [rng.sample(rng.choice(tangled), 2) for _ in range(10)]
    for first, second in pairs:
        assert signature(first, real, item) == signature(second, real, item), (first.fossils, second.fossils)
