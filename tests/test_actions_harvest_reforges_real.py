"""The Harvest reforges on the real 3.29.3.3 dump (ticket #72); these skip cleanly when the dump is not cached (CI has none).

* On an empty rare amulet of item level 86 the weight the guaranteed draw picks from, for each of the 16 crafts, equals a
  hand walk over the dump (first matching spawn tag, the mod's `implicit_tags` holding the craft's tag); Lightning's is the
  14,950 of the PoE Vault guide and the research (HRV-25).
* A likelihood reforge weighs the mods of the families an amulet holds x10 (more likely) or x1/10 (less likely) against
  the plain pool of the empty item, the factor of the game data's `HarvestCraftOptions` (+900 and -90 percent, issue #319).
* On the Hunter Thicket Bow of item level 78 the guaranteed draw of the influence reforge picks from 10,200 of weight, the
  weight the Hunter tag adds to the pool (`test_actions_rare_orbs_real.py` pins it by another hand walk); the data's own
  `influence_mod` tag marks none of it, which is why the reforge does not use that tag.
"""

from fractions import Fraction

import pytest
from abstraction_support import real_game_data
from harvest_reforge_support import TABLE

from crafting_system.actions import (
    HarvestReforge,
    HarvestReforgeInfluence,
    HarvestReforgeLikelihood,
    NotApplicableError,
    build_pool,
)
from crafting_system.items import ExplicitMod, Influence, Item, Rarity

HUNTER_WEIGHT_ADDED = 10200  # test_actions_rare_orbs_real.py: HUNTER_POOL minus PLAIN_POOL, 34 and 25 families


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def amulet(data) -> Item:
    base = next(b for b in data.base_items.values() if b.name == "Coral Amulet")
    return Item.build(data, base_id=base.id, item_level=86, rarity=Rarity.RARE)


def hand_tagged_weight(data, base, level, tag) -> Fraction:
    """The weight of the mods with `tag` that an empty rare item of `base` can roll, by a walk over the dump."""
    tags = set(base.tags)
    total = Fraction(0)
    for mod in data.mods.values():
        if mod.domain != base.domain or mod.generation_type not in ("prefix", "suffix") or mod.required_level > level:
            continue
        spawn = next((w.weight for w in mod.spawn_weights if w.tag in tags), 0)
        if spawn and tag in mod.implicit_tags:
            factor = next((Fraction(w.weight, 100) for w in mod.generation_weights if w.tag in tags), Fraction(1))
            total += spawn * factor
    return total


@pytest.mark.parametrize("craft", TABLE)
def test_the_guaranteed_draw_of_each_craft_picks_from_the_hand_walked_weight(craft, data):
    item = amulet(data)
    tag = TABLE[craft][0]
    expected = hand_tagged_weight(data, data.base_items[item.base_id], 86, tag)
    if expected == 0:
        with pytest.raises(NotApplicableError):
            HarvestReforge(craft).outcomes(data, item)
        return
    outcomes = HarvestReforge(craft).outcomes(data, item)
    engine = sum((entry.weight for family in outcomes.pool for entry in family.mods if tag in entry.mod.implicit_tags), Fraction(0))
    assert engine == expected


def test_a_craft_that_finds_nothing_on_an_amulet_works_on_a_base_that_has_its_tag(data):
    """Minion has no mod on a Coral Amulet at item level 86: the positive path is walked on the first base of a class that has one."""
    amulet_item = amulet(data)
    empty = [c for c, (tag, _) in TABLE.items() if hand_tagged_weight(data, data.base_items[amulet_item.base_id], 86, tag) == 0]
    for craft in empty:
        tag = TABLE[craft][0]
        classes = {}
        for base in data.base_items.values():
            if base.release_state == "released" and base.domain == "item":
                classes.setdefault(base.item_class, base)
        found = [b for b in classes.values() if hand_tagged_weight(data, b, 86, tag) > 0]
        assert found, craft
        base = found[0]
        item = Item.build(data, base_id=base.id, item_level=86, rarity=Rarity.RARE)
        outcomes = HarvestReforge(craft).outcomes(data, item)
        engine = sum((e.weight for f in outcomes.pool for e in f.mods if tag in e.mod.implicit_tags), Fraction(0))
        assert engine == hand_tagged_weight(data, base, 86, tag), (craft, base.name)


def test_lightning_on_an_amulet_is_the_research_total(data):
    assert hand_tagged_weight(data, data.base_items[amulet(data).base_id], 86, "lightning") == 14950


def test_the_influence_reforge_picks_from_the_hunter_weight_of_a_hunter_bow(data):
    base = next(b for b in data.base_items.values() if b.name == "Thicket Bow" and "bow" in b.tags)
    item = Item.build(data, base_id=base.id, item_level=78, rarity=Rarity.RARE, influences=frozenset({Influence.HUNTER}))
    outcomes = HarvestReforgeInfluence().outcomes(data, item)

    picked = sum((e.weight for f in outcomes.pool for e in f.mods if "influence" in e.mod.implicit_tags), Fraction(0))
    assert picked == HUNTER_WEIGHT_ADDED
    assert not any("influence_mod" in e.mod.implicit_tags for f in outcomes.pool for e in f.mods if e.mod.id.startswith("LocalAddedChaosDamageAndPenetrationInfluence"))


def test_without_influence_the_reforge_is_refused_on_the_real_bow(data):
    base = next(b for b in data.base_items.values() if b.name == "Thicket Bow" and "bow" in b.tags)
    with pytest.raises(NotApplicableError):
        HarvestReforgeInfluence().outcomes(data, Item.build(data, base_id=base.id, item_level=78, rarity=Rarity.RARE))


def test_with_two_influences_the_guaranteed_draw_picks_from_the_weight_of_both(data):
    base = next(b for b in data.base_items.values() if b.name == "Thicket Bow" and "bow" in b.tags)
    both = frozenset({Influence.HUNTER, Influence.SHAPER})
    item = Item.build(data, base_id=base.id, item_level=78, rarity=Rarity.RARE, influences=both)
    outcomes = HarvestReforgeInfluence().outcomes(data, item)

    tags = set(base.tags) | {"bow_basilisk", "bow_shaper"}
    expected = Fraction(0)
    for mod in data.mods.values():
        if mod.domain != base.domain or mod.generation_type not in ("prefix", "suffix") or mod.required_level > 78:
            continue
        deciding = next((w for w in mod.spawn_weights if w.tag in tags), None)
        if deciding is not None and deciding.tag in ("bow_basilisk", "bow_shaper") and deciding.weight:
            factor = next((Fraction(w.weight, 100) for w in mod.generation_weights if w.tag in tags), Fraction(1))
            expected += deciding.weight * factor
    picked = sum((e.weight for f in outcomes.pool for e in f.mods if "influence" in e.mod.implicit_tags), Fraction(0))
    assert picked == expected > HUNTER_WEIGHT_ADDED


@pytest.mark.parametrize(("more", "factor"), [(True, Fraction(10)), (False, Fraction(1, 10))], ids=["more", "less"])
def test_a_likelihood_reforge_weighs_the_held_families_ten_times_more_or_a_tenth(more, factor, data):
    """A Coral Amulet (item level 86) holding T1 Increased Life: every real mod of that family gets `factor`, the rest keep their weight."""
    item = amulet(data)
    life = data.mods["IncreasedLife10"]
    held = Item.build(
        data, base_id=item.base_id, item_level=86, rarity=Rarity.RARE,
        mods=(ExplicitMod(life.id, 1, tuple(min(s.min, s.max) for s in life.stats)),),
    )  # fmt: skip
    plain = {(f.family, e.mod.id): e.weight for f in build_pool(data, item) for e in f.mods}
    boosted = {(f.family, e.mod.id): e.weight for f in HarvestReforgeLikelihood(more).outcomes(data, held).pool for e in f.mods}

    assert boosted.keys() == plain.keys()
    in_family = [key for key in plain if key[0] in life.families]
    assert in_family and len(in_family) < len(plain)
    for key, weight in boosted.items():
        assert weight == plain[key] * (factor if key[0] in life.families else 1), key
