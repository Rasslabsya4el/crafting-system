"""The aspect and Talisman beasts on the real 3.29.3.3 dump (ticket #147).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there, with the reason; CI fetches it (ticket #165), so
they run there.
"""

import random
from fractions import Fraction

import pytest

from crafting_system.actions import NotApplicableError, catalog
from crafting_system.actions.beasts import AspectBeast, TalismanFracture
from crafting_system.data import MissingDataError, load_game_data
from crafting_system.items import ExplicitMod, Item, Rarity

AMULET = "Metadata/Items/Amulets/Amulet1"
TALISMAN = "Metadata/Items/Amulets/Talismans/Talisman1_1"
ASPECT_IDS = {
    ("avian", 20): "GrantsBirdAspectCrafted",
    ("avian", 30): "GrantsBirdAspectCrafted30",
    ("cat", 20): "GrantsCatAspectCrafted",
    ("cat", 30): "GrantsCatAspectCrafted30",
    ("crab", 20): "GrantsCrabAspectCrafted",
    ("crab", 30): "GrantsCrabAspectCrafted30",
    ("spider", 20): "GrantsSpiderAspectCrafted",
    ("spider", 30): "GrantsSpiderAspectCrafted30",
}
LIFE, FIRE, COLD = "IncreasedLife1", "FireResist1", "ColdResist1"
SHIELD, MANA = "IncreasedEnergyShield1", "ManaLeechPermyriadSuffix1"


@pytest.fixture(scope="module")
def data():
    try:
        return load_game_data()
    except MissingDataError as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


def rolled(data, mod_id, **flags):
    mod = data.mods[mod_id]
    return ExplicitMod(mod_id, 1, tuple(min(stat.min, stat.max) for stat in mod.stats), **flags)


def rare(data, base_id, *mod_ids, **fields):
    return Item.build(
        data, base_id=base_id, item_level=84, rarity=Rarity.RARE, mods=tuple(rolled(data, mod_id) for mod_id in mod_ids), **fields
    )


@pytest.mark.parametrize(("aspect", "level"), sorted(ASPECT_IDS))
def test_the_aspect_mod_is_a_suffix_of_the_family_granted_skill_that_grants_the_level(data, aspect, level):
    mod = data.mods[ASPECT_IDS[aspect, level]]

    assert AspectBeast(aspect, level).mod_id == mod.id
    assert mod.generation_type == "suffix" and mod.families == ("GrantedSkill",)
    assert mod.domain == "item" and mod.required_level == 20
    assert [(stat.min, stat.max) for stat in mod.stats] == [(level, level)]
    assert all(weight.weight == 0 for weight in mod.spawn_weights)  # never rolled naturally
    assert f"Level {level} Aspect of the" in (mod.text or "")


@pytest.mark.parametrize(("aspect", "level"), sorted(ASPECT_IDS))
def test_the_aspect_craft_adds_the_suffix_to_a_real_rare_amulet_as_an_ordinary_mod(data, aspect, level):
    amulet = rare(data, AMULET, LIFE, SHIELD, FIRE)

    outcomes = AspectBeast(aspect, level).outcomes(data, amulet)

    mod_id = ASPECT_IDS[aspect, level]
    assert outcomes.chance_all([mod_id, LIFE, SHIELD, FIRE]) == 1
    finished = outcomes.sample(random.Random(1))
    finished.validate(data)
    added = next(entry for entry in finished.mods if entry.mod_id == mod_id)
    assert (added.values, added.crafted) == ((level,), False) and finished.crafted_mods == ()
    assert dict(outcomes.distribution(lambda mod: mod.id)) == {frozenset({(mod_id, 1)}): Fraction(1)}


def test_two_aspects_exclude_each_other_and_a_full_suffix_side_refuses_the_craft(data):
    held = rare(data, AMULET, LIFE, ASPECT_IDS["cat", 20])
    full = rare(data, AMULET, LIFE, FIRE, COLD, MANA)

    for pair in ASPECT_IDS:
        with pytest.raises(NotApplicableError, match="shares a family"):
            AspectBeast(*pair).outcomes(data, held)
        with pytest.raises(NotApplicableError, match="no free suffix slot"):
            AspectBeast(*pair).outcomes(data, full)


def test_the_kind_offers_the_eight_aspects_for_a_real_rare_amulet(data):
    offered = [action for action in catalog(data, rare(data, AMULET, LIFE)) if isinstance(action, AspectBeast)]

    assert {(action.aspect, action.level) for action in offered} == set(ASPECT_IDS) and len(offered) == 8


def test_the_real_talisman_bases_carry_the_tag_the_fracture_needs(data):
    talismans = [base for base in data.base_items.values() if "talisman" in base.tags]

    assert len(talismans) >= 40 and {base.item_class for base in talismans} == {"Amulet"}
    assert data.base_items[TALISMAN].name == "Black Maw Talisman"
    assert "talisman" not in data.base_items[AMULET].tags


def test_the_talisman_fractures_work_on_a_real_rare_talisman_and_not_on_a_plain_amulet(data):
    six = ("AddedLightningDamage1", LIFE, SHIELD, FIRE, COLD, MANA)
    talisman = rare(data, TALISMAN, *six)

    one = TalismanFracture(1).outcomes(data, talisman)
    two = TalismanFracture(2).outcomes(data, talisman)

    assert len(one.results) == 6 and {chance for chance, _ in one.results} == {Fraction(1, 6)}
    assert len(two.results) == 15 and {chance for chance, _ in two.results} == {Fraction(1, 15)}
    for _, result in two.results:
        result.validate(data)
        assert len(result.fractured_mods) == 2
    with pytest.raises(NotApplicableError, match="not a Talisman base"):
        TalismanFracture(1).outcomes(data, rare(data, AMULET, *six))
    offered = [action for action in catalog(data, talisman) if isinstance(action, TalismanFracture)]
    assert offered == [TalismanFracture(1), TalismanFracture(2)]
