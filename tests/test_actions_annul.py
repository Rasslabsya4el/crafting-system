"""The Orb of Annulment against the hand oracle, and what it refuses (ticket #67).

Every mod that is not fractured is removed with the same chance 1/n (D5 of issue #28); the rarity
stays; a fractured mod is never a candidate. R14's published odds: Annulment takes the attack speed
off a 3-mod bow with chance 1/3 and off a 2-mod bow with chance 1/2 (reference routes).
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from actions_support import DATA, amulet, fractured_resist, roll
from items_support import item

from crafting_system.actions import AnnulmentOrb, NotApplicableError, OutOfScopeError, catalog, kinds
from crafting_system.items import Influence, Rarity

BOW = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
ATTACK_SPEED, SOCKET, ARROW = "LocalIncreasedAttackSpeed5", "LocalIncreaseSocketedGemLevel1", "AdditionalArrowBow1_"
HUNTER_MOD = "LocalAddedChaosDamageAndPenetrationInfluence1"
LIFE, FIRE, COLD = "IncreasedLife1", "FireResist1", "ColdResist1"
CRAFTED = "DexMasterItemGenerationCannotChangeSuffixes"
ORDINARY_CRAFTED = "JunMaster2AllDamage2_"
HUNTER = frozenset({Influence.HUNTER})


def bow(*mods, rarity=Rarity.RARE):
    return item(*mods, base_id=BOW, item_level=78, rarity=rarity, influences=HUNTER)


def kept(outcomes) -> dict[frozenset[str], Fraction]:
    """The mod ids left on the item, with the chance of each result."""
    return {frozenset(e.mod_id for e in result.mods): chance for chance, result in outcomes.results}


def test_r14_annulment_takes_the_attack_speed_off_a_three_mod_bow_with_chance_one_third():
    outcomes = AnnulmentOrb().outcomes(DATA, bow(roll(ATTACK_SPEED), roll(SOCKET), roll(HUNTER_MOD)))

    assert 1 - outcomes.chance_all([ATTACK_SPEED]) == Fraction(1, 3)
    assert outcomes.chance_all([ATTACK_SPEED]) == Fraction(2, 3)


def test_r14_annulment_takes_the_attack_speed_off_a_two_mod_bow_with_chance_one_half():
    outcomes = AnnulmentOrb().outcomes(DATA, bow(roll(ATTACK_SPEED), roll(SOCKET)))

    assert 1 - outcomes.chance_all([ATTACK_SPEED]) == Fraction(1, 2)


def test_r14_annulling_a_three_mod_bow_down_to_the_attack_speed_alone_succeeds_with_chance_one_third():
    # three mods, two annuls: the attack speed survives both with (2/3) * (1/2) = 1/3, the product of the guide's two steps
    three = bow(roll(ATTACK_SPEED), roll(SOCKET), roll(HUNTER_MOD))
    first = AnnulmentOrb().outcomes(DATA, three)
    survives = Fraction(0)
    for chance, result in first.results:
        if any(entry.mod_id == ATTACK_SPEED for entry in result.mods):
            survives += chance * AnnulmentOrb().outcomes(DATA, result).chance_all([ATTACK_SPEED])

    assert survives == Fraction(1, 3)


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 6])
def test_each_removable_mod_has_the_chance_one_over_n(count):
    mods = (LIFE, "IncreasedEnergyShield1", "AddedLightningDamage1", FIRE, COLD, "ManaLeechPermyriadSuffix1")[:count]
    outcomes = AnnulmentOrb().outcomes(DATA, amulet(*(roll(mod_id) for mod_id in mods)))

    assert sorted(kept(outcomes).values()) == [Fraction(1, count)] * count
    assert {mod_id: 1 - outcomes.chance_all([mod_id]) for mod_id in mods} == {mod_id: Fraction(1, count) for mod_id in mods}
    assert all(len(ids) == count - 1 for ids in kept(outcomes))


def test_the_distribution_has_no_new_mod_and_sums_to_one():
    outcomes = AnnulmentOrb().outcomes(DATA, amulet(roll(LIFE), roll(FIRE), roll(COLD)))

    assert dict(outcomes.distribution(lambda mod: mod.id)) == {frozenset(): 1}
    assert outcomes.fractures is False


def test_a_fractured_mod_stays_and_is_not_a_candidate():
    item_ = amulet(fractured_resist(), roll(LIFE), roll(FIRE), roll(COLD))
    outcomes = AnnulmentOrb().outcomes(DATA, item_)

    assert sorted(kept(outcomes).values()) == [Fraction(1, 3)] * 3  # three removable mods, not four
    assert all(any(entry.fractured for entry in result.mods) for _, result in outcomes.results)
    assert outcomes.chance_all(["LightningResist1"]) == 1


def test_an_ordinary_crafted_mod_is_one_of_the_candidates():
    item_ = amulet(roll(LIFE), roll(FIRE), roll(ORDINARY_CRAFTED, crafted=True))
    outcomes = AnnulmentOrb().outcomes(DATA, item_)

    assert outcomes.chance_all([ORDINARY_CRAFTED]) == Fraction(2, 3)
    assert any(not any(entry.crafted for entry in result.mods) for _, result in outcomes.results)


def test_the_rarity_stays_a_magic_item_left_with_no_mod_is_magic():
    magic = amulet(roll(LIFE), rarity=Rarity.MAGIC)
    outcomes = AnnulmentOrb().outcomes(DATA, magic)

    [(chance, result)] = outcomes.results
    assert chance == 1 and result.mods == () and result.rarity is Rarity.MAGIC


def test_a_rare_item_left_with_two_mods_stays_rare():
    outcomes = AnnulmentOrb().outcomes(DATA, amulet(roll(LIFE), roll(FIRE), roll(COLD)))

    assert {result.rarity for _, result in outcomes.results} == {Rarity.RARE}


def test_the_item_keeps_its_influences_and_its_values():
    item_ = bow(roll(ATTACK_SPEED), roll(SOCKET), roll(HUNTER_MOD))
    outcomes = AnnulmentOrb().outcomes(DATA, item_)

    for _, result in outcomes.results:
        assert result.influences == HUNTER
        assert {entry for entry in result.mods} < set(item_.mods)


def test_the_sampler_picks_each_removal_with_its_chance():
    item_ = amulet(roll(LIFE), roll(FIRE), roll(COLD), roll("ManaLeechPermyriadSuffix1"))
    outcomes = AnnulmentOrb().outcomes(DATA, item_)
    rng, runs, removed = random.Random(11), 4000, {}
    for _ in range(runs):
        drawn = outcomes.sample(rng)
        drawn.validate(DATA)
        (gone,) = {entry.mod_id for entry in item_.mods} - {entry.mod_id for entry in drawn.mods}
        removed[gone] = removed.get(gone, 0) + 1

    assert len(removed) == 4
    assert all(abs(count / runs - 0.25) < 5 * (0.25 * 0.75 / runs) ** 0.5 for count in removed.values())


def test_a_normal_item_is_refused_by_the_game():
    with pytest.raises(NotApplicableError, match="magic or rare item only"):
        AnnulmentOrb().outcomes(DATA, amulet(rarity=Rarity.NORMAL))


def test_a_corrupted_item_is_refused_by_the_game():
    with pytest.raises(NotApplicableError, match="corrupted.*Orb of Annulment"):
        AnnulmentOrb().outcomes(DATA, dataclasses.replace(amulet(roll(LIFE)), corrupted=True))


def test_an_item_with_no_mod_to_remove_is_refused_and_nothing_is_consumed():
    with pytest.raises(NotApplicableError, match="no mod that is not fractured"):
        AnnulmentOrb().outcomes(DATA, amulet(rarity=Rarity.MAGIC))
    all_fractured = amulet(fractured_resist(), fractured_resist("ColdResist1"))
    with pytest.raises(NotApplicableError, match="no mod that is not fractured"):
        AnnulmentOrb().outcomes(DATA, all_fractured)


def test_a_crafted_metamod_is_a_candidate_on_the_other_side_of_its_lock():
    # CRAFTED locks the suffixes and sits on the prefix side with the Life mod: both are candidates (D5)
    outcomes = AnnulmentOrb().outcomes(DATA, amulet(roll(LIFE), roll(CRAFTED, crafted=True)))

    assert outcomes.chance_all([LIFE]) == Fraction(1, 2)
    assert outcomes.chance_all([CRAFTED]) == Fraction(1, 2)


def test_an_influenced_item_of_any_class_is_in_scope_because_nothing_is_drawn():
    sword = dataclasses.replace(DATA.base_items[BOW], item_class="Fishing Rod")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, BOW: sword})

    assert AnnulmentOrb().outcomes(data, bow(roll(ATTACK_SPEED), roll(SOCKET))).chance_all([ATTACK_SPEED]) == Fraction(1, 2)


def test_the_orb_is_named_priced_and_declared():
    action = AnnulmentOrb()

    assert action.label(DATA) == "Orb of Annulment"
    assert action.resources(DATA) == {"Orb of Annulment": 1}
    reads, adds = action.reads(DATA), action.adds(DATA, amulet())
    assert reads.junk and reads.families == frozenset() and reads.block_invariant and not reads.pool_weight and not reads.variants
    assert adds.named == frozenset() and not adds.draws and adds.keeps_crafted


def test_the_kind_lists_magic_and_rare_items_and_is_not_a_planner_kind():
    assert AnnulmentOrb() in catalog(DATA, amulet(roll(LIFE), rarity=Rarity.MAGIC))
    assert AnnulmentOrb() in catalog(DATA, amulet(roll(LIFE)))
    assert AnnulmentOrb() not in catalog(DATA, amulet(rarity=Rarity.NORMAL))
    assert AnnulmentOrb() not in catalog(DATA, amulet(roll(LIFE)), planner_only=True)
    assert {entry.name: entry.planner for entry in kinds()}["annulment-orb"] is False
