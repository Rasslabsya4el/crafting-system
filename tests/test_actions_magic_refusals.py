"""What the magic-item orbs and the Alchemy refuse, with which error, and in which order (ticket #64)."""

import dataclasses

import pytest
from actions_support import AMULET, DATA, amulet, fractured_resist, roll

from crafting_system.actions import (
    AlchemyOrb,
    AlterationOrb,
    AugmentationOrb,
    NotApplicableError,
    OutOfScopeError,
    RegalOrb,
    ScouringOrb,
    TransmutationOrb,
    add_one_mod,
)
from crafting_system.items import Influence, Rarity

LIFE, FIRE = "IncreasedLife1", "FireResist1"
CRAFTED = "DexMasterItemGenerationCannotChangeSuffixes"

# (orb, the one rarity it accepts)
ORBS = [
    (TransmutationOrb(), Rarity.NORMAL),
    (AlterationOrb(), Rarity.MAGIC),
    (AugmentationOrb(), Rarity.MAGIC),
    (RegalOrb(), Rarity.MAGIC),
    (AlchemyOrb(), Rarity.NORMAL),
]
RARITIES = {
    Rarity.NORMAL: lambda: amulet(rarity=Rarity.NORMAL),
    Rarity.MAGIC: lambda: amulet(roll(LIFE), rarity=Rarity.MAGIC),
    Rarity.RARE: lambda: amulet(),
}
IDS = [type(orb).__name__ for orb, _ in ORBS]


@pytest.mark.parametrize(("orb", "accepts"), ORBS, ids=IDS)
@pytest.mark.parametrize("rarity", list(Rarity))
def test_an_item_of_another_rarity_is_refused_by_the_game(orb, accepts, rarity):
    if rarity is accepts:
        orb.outcomes(DATA, RARITIES[rarity]())
        return

    with pytest.raises(NotApplicableError, match=f"{accepts} item only.*{rarity}"):
        orb.outcomes(DATA, RARITIES[rarity]())


@pytest.mark.parametrize(("orb", "accepts"), ORBS, ids=IDS)
def test_a_corrupted_item_is_refused_by_the_game(orb, accepts):
    item = dataclasses.replace(RARITIES[accepts](), corrupted=True)

    with pytest.raises(NotApplicableError, match="corrupted"):
        orb.outcomes(DATA, item)


@pytest.mark.parametrize(("orb", "accepts"), ORBS, ids=IDS)
@pytest.mark.parametrize("item_class", ["Jewel", "AbyssJewel"])
def test_a_jewel_base_is_in_scope(orb, accepts, item_class):
    jewel = dataclasses.replace(DATA.base_items[AMULET], item_class=item_class)
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, AMULET: jewel})

    assert orb.outcomes(data, RARITIES[accepts]()).components  # jewel.ordinary_orbs_work_on_jewels


@pytest.mark.parametrize(("orb", "accepts"), ORBS, ids=IDS)
def test_a_cluster_jewel_base_is_out_of_scope(orb, accepts):
    cluster = dataclasses.replace(DATA.base_items[AMULET], item_class="Jewel", domain="affliction_jewel")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, AMULET: cluster})

    with pytest.raises(OutOfScopeError, match="cluster jewel"):
        orb.outcomes(data, RARITIES[accepts]())


@pytest.mark.parametrize(("orb", "accepts"), ORBS, ids=IDS)
def test_an_influenced_item_of_a_class_with_no_influence_class_key_is_out_of_scope(orb, accepts):
    sword = dataclasses.replace(DATA.base_items[AMULET], item_class="Fishing Rod")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, AMULET: sword})
    item = dataclasses.replace(RARITIES[accepts](), influences=frozenset({Influence.SHAPER}))

    with pytest.raises(OutOfScopeError, match="influence class key"):
        orb.outcomes(data, item)


@pytest.mark.parametrize(("orb", "accepts"), ORBS, ids=IDS)
def test_an_influenced_amulet_is_in_scope(orb, accepts):
    item = dataclasses.replace(RARITIES[accepts](), influences=frozenset({Influence.SHAPER}))

    assert orb.outcomes(DATA, item).retained.influences == item.influences


@pytest.mark.parametrize("orb", [AlterationOrb(), AugmentationOrb(), RegalOrb()], ids=lambda orb: type(orb).__name__)
def test_a_crafted_metamod_leaves_a_magic_item_in_scope(orb):
    item = amulet(roll(CRAFTED, crafted=True), rarity=Rarity.MAGIC)

    assert sum(orb.outcomes(DATA, item).distribution(lambda mod: mod.id).values()) == 1


@pytest.mark.parametrize(("orb", "accepts"), ORBS, ids=IDS)
def test_a_not_applicable_error_comes_before_an_out_of_scope_one(orb, accepts):
    wrong = Rarity.RARE if accepts is not Rarity.RARE else Rarity.NORMAL
    item = dataclasses.replace(RARITIES[wrong](), influences=frozenset({Influence.HUNTER}))

    with pytest.raises(NotApplicableError):
        orb.outcomes(DATA, item)


def test_augmentation_on_a_full_magic_item_is_refused():
    item = amulet(roll(LIFE), roll(FIRE), rarity=Rarity.MAGIC)

    with pytest.raises(NotApplicableError, match="no open prefix or suffix slot"):
        AugmentationOrb().outcomes(DATA, item)


def test_augmentation_is_refused_when_the_open_side_has_no_legal_mod():
    # At item level 1 only FireResist1 (level 1) is in the pool of an amulet: no prefix can be drawn.
    item = amulet(roll(FIRE), rarity=Rarity.MAGIC, item_level=1)

    with pytest.raises(NotApplicableError, match="no mod of the pool is legal"):
        AugmentationOrb().outcomes(DATA, item)


def only_mods(*mod_ids):
    """The fixture data cut down to a few mods, to build a pool whose every candidate is blocked."""
    return dataclasses.replace(DATA, mods={mod_id: DATA.mods[mod_id] for mod_id in mod_ids})


def test_an_add_is_refused_when_the_family_of_every_candidate_is_on_the_item():
    data = only_mods(LIFE, "IncreasedLife2", "LightningResist1", "LightningResist2")
    item = amulet(roll(LIFE), rarity=Rarity.MAGIC)

    with pytest.raises(NotApplicableError, match="a Regal Orb cannot add a mod.*blocked by a family"):
        RegalOrb().outcomes(data, dataclasses.replace(item, mods=(roll(LIFE), roll("LightningResist1"))))
    with pytest.raises(NotApplicableError, match="an Orb of Augmentation cannot add a mod"):
        AugmentationOrb().outcomes(only_mods(LIFE, "IncreasedLife2"), item)


def test_a_regal_orb_with_no_legal_mod_is_refused_and_consumes_nothing():
    # Level 1 and the first suffix on the item: the prefixes of the amulet all need a higher level,
    # and the rare item has open suffix slots, but the data cut to one suffix family leaves no candidate.
    data = only_mods(LIFE, FIRE)
    item = amulet(roll(FIRE), rarity=Rarity.MAGIC, item_level=1)

    with pytest.raises(NotApplicableError, match="a Regal Orb cannot add a mod"):
        RegalOrb().outcomes(data, item)


def test_the_shared_add_refuses_a_full_rare_item():
    full = amulet(
        roll(LIFE), roll("IncreasedEnergyShield1"), roll("AddedLightningDamage1"),
        roll(FIRE), roll("LifeRegeneration1"), fractured_resist(),
    )  # fmt: skip

    with pytest.raises(NotApplicableError, match="no open prefix or suffix slot"):
        add_one_mod(DATA, full, "an Exalted Orb")


def test_a_refused_add_names_the_action():
    with pytest.raises(NotApplicableError, match="an Exalted Orb cannot add a mod"):
        add_one_mod(DATA, amulet(roll(FIRE), rarity=Rarity.MAGIC, item_level=1), "an Exalted Orb")


def test_scouring_refuses_what_it_cannot_scour():
    with pytest.raises(NotApplicableError, match="magic or rare item only"):
        ScouringOrb().outcomes(DATA, amulet(rarity=Rarity.NORMAL))
    with pytest.raises(NotApplicableError, match="corrupted"):
        ScouringOrb().outcomes(DATA, dataclasses.replace(amulet(), corrupted=True))
