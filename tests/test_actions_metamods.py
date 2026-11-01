"""What the five metamods do to every B1 action, against a hand oracle (ticket #68).

Rules of issues #11 and #28: `Prefixes` / `Suffixes Cannot Be Changed` keep the mods of the locked side
through a reroll, a Scouring and an Annulment and let open slots fill; `Cannot roll Attack` / `Caster
Modifiers` keep the tagged mods out of a draw and out of an Annulment's candidates; the multimod raises the
crafted-mod limit to three; essences and resonators refuse the other four; Fracturing counts metamods and
may pick one; Remove Crafted Mods ends them. The oracle (`metamod_oracle.py`) walks every draw order by hand.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from actions_support import DATA, amulet, roll
from items_support import item
from metamod_oracle import ATTACK_FAMILIES, META, PREFIX, SUFFIX, add_one, alteration, harvest, reroll

from crafting_system.actions import (
    AlterationOrb,
    AnnulmentOrb,
    ApplyEssence,
    AugmentationOrb,
    BenchCraft,
    ChaosOrb,
    ExaltedOrb,
    FracturingOrb,
    HarvestReforge,
    NotApplicableError,
    RegalOrb,
    RemoveCraftedMods,
    ScouringOrb,
)
from crafting_system.items import Metamod, Rarity

PCBC = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix; locks the prefixes
SCBC = "DexMasterItemGenerationCannotChangeSuffixes"  # a prefix; locks the suffixes
MULTI = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"  # a suffix
NO_ATTACK = "IntMasterItemGenerationCannotRollAttackAffixes"  # a suffix
NO_CASTER = "StrDexMasterItemGenerationCannotRollCasterAffixes"  # a suffix
LIFE, ES, FIRE, COLD = "IncreasedLife1", "IncreasedEnergyShield1", "FireResist1", "ColdResist1"
ATTACK_PREFIX, ATTACK_SUFFIX = "AddedLightningDamage1", "LifeLeechPermyriadSuffix1"
CAST_PCT = "LightningDamagePercent1"  # the fixture has no caster-tagged mod: `caster_data` tags this family
SIDE = {
    "IncreasedLife": PREFIX,
    "IncreasedEnergyShield": PREFIX,
    "LightningDamage": PREFIX,
    "FireResistance": SUFFIX,
    "ColdResistance": SUFFIX,
    "LifeLeech": SUFFIX,
}
BY_FAMILY = lambda mod: mod.families[0]  # noqa: E731


def caster_data():
    """The fixture with the Caster tag on the Lightning Damage % family (the fixture amulet has no other)."""
    mods = {
        mod_id: dataclasses.replace(mod, implicit_tags=(*mod.implicit_tags, "caster")) if mod.families == ("LightningDamagePercentage",) else mod
        for mod_id, mod in DATA.mods.items()
    }
    return dataclasses.replace(DATA, mods=mods)


def seen(outcomes) -> dict[frozenset[str], Fraction]:
    """The distribution of the new mods as sets of families (every family is drawn at most once)."""
    result: dict[frozenset[str], Fraction] = {}
    for outcome, chance in outcomes.distribution(BY_FAMILY).items():
        assert all(count == 1 for _, count in outcome)
        key = frozenset(family for family, _ in outcome)
        result[key] = result.get(key, Fraction(0)) + chance
    return result


def ids(item) -> set[str]:
    return {entry.mod_id for entry in item.mods}


def kept(*families: str, meta_side: str | None = None) -> dict[str, str]:
    """The oracle's retained families (name -> side), and a metamod that stays as a pseudo family."""
    held = {family: SIDE[family] for family in families}
    if meta_side is not None:
        held[META] = meta_side
    return held


# --- Prefixes / Suffixes Cannot Be Changed ------------------------------------------------------------


def test_chaos_under_prefixes_cannot_be_changed_keeps_the_prefixes_and_loses_the_lock():
    item = amulet(roll(LIFE), roll(ES), roll(FIRE), roll(PCBC, crafted=True))

    outcomes = ChaosOrb().outcomes(DATA, item)

    assert ids(outcomes.retained) == {LIFE, ES}  # the suffix side goes, the metamod with it
    assert seen(outcomes) == reroll(86, kept("IncreasedLife", "IncreasedEnergyShield"))


def test_chaos_under_prefixes_cannot_be_changed_only_fills_the_open_slots():
    item = amulet(roll(LIFE), roll(ES), roll("AddedLightningDamage1"), roll(FIRE), roll(PCBC, crafted=True))
    outcomes = ChaosOrb().outcomes(DATA, item)

    shown = seen(outcomes)
    # three prefixes are kept, so every new mod is a suffix and the total (4, 5, 6) counts the kept three
    assert shown == reroll(86, kept("IncreasedLife", "IncreasedEnergyShield", "LightningDamage"))
    assert all(len(key) in (1, 2, 3) for key in shown)
    assert sum(shown.values()) == 1


def test_chaos_under_suffixes_cannot_be_changed_keeps_the_suffixes():
    item = amulet(roll(FIRE), roll(COLD), roll(LIFE), roll(SCBC, crafted=True))

    outcomes = ChaosOrb().outcomes(DATA, item)

    assert ids(outcomes.retained) == {FIRE, COLD}
    assert seen(outcomes) == reroll(86, kept("FireResistance", "ColdResistance"))


def test_chaos_with_both_locks_keeps_everything_and_draws_nothing_on_a_full_item():
    item = amulet(roll(LIFE), roll(ES), roll(FIRE), roll(COLD), roll(PCBC, crafted=True), roll(SCBC, crafted=True))

    outcomes = ChaosOrb().outcomes(DATA, item)

    assert outcomes.retained == item
    assert seen(outcomes) == {frozenset(): 1}
    assert outcomes.sample(random.Random(1)) == item


def test_chaos_with_both_locks_keeps_everything_and_fills_what_is_open():
    item = amulet(roll(LIFE), roll(FIRE), roll(PCBC, crafted=True), roll(SCBC, crafted=True))

    outcomes = ChaosOrb().outcomes(DATA, item)

    assert outcomes.retained == item  # both sides are locked: nothing is removed
    assert seen(outcomes) == reroll(86, {"IncreasedLife": PREFIX, META: PREFIX, "FireResistance": SUFFIX, META + "2": SUFFIX})


def test_chaos_keeps_the_locked_side_in_every_sample():
    item = amulet(roll(LIFE), roll(ES), roll(FIRE), roll(PCBC, crafted=True))
    outcomes = ChaosOrb().outcomes(DATA, item)
    for seed in range(20):
        result = outcomes.sample(random.Random(seed))
        assert {LIFE, ES} <= ids(result)
        assert PCBC not in ids(result)
        assert 4 <= len(result.mods) <= 6


def test_a_fractured_mod_and_the_locked_side_are_both_kept():
    item = amulet(roll(LIFE, fractured=True), roll(FIRE), roll(ES), roll(SCBC, crafted=True))

    outcomes = ChaosOrb().outcomes(DATA, item)

    assert ids(outcomes.retained) == {LIFE, FIRE}  # the fractured prefix, the locked suffix; ES and the lock go
    assert seen(outcomes) == reroll(86, kept("IncreasedLife", "FireResistance"))


def test_the_multimod_and_the_attack_metamod_alone_do_not_lock_anything():
    plain = reroll(86, {})
    for metamod in (MULTI, NO_ATTACK):
        item = amulet(roll(LIFE), roll(FIRE), roll(metamod, crafted=True))
        outcomes = ChaosOrb().outcomes(DATA, item)
        assert ids(outcomes.retained) == set()
        assert seen(outcomes) == plain


@pytest.mark.parametrize("level", (80, 86))
def test_harvest_under_a_lock_keeps_the_side_and_guarantees_the_tag(level):
    item = amulet(roll(LIFE), roll(ES), roll(FIRE), roll(PCBC, crafted=True), item_level=level)

    outcomes = HarvestReforge("lightning").outcomes(DATA, item)

    assert ids(outcomes.retained) == {LIFE, ES}
    assert seen(outcomes) == harvest(level, kept("IncreasedLife", "IncreasedEnergyShield"))


def test_harvest_under_a_lock_with_the_locked_side_full_draws_the_tag_from_the_open_side():
    # prefixes full and locked, suffixes open: only the Lightning suffixes fit the guaranteed draw
    full = amulet(roll(LIFE), roll(ES), roll(ATTACK_PREFIX), roll(FIRE), roll(PCBC, crafted=True))
    assert seen(HarvestReforge("lightning").outcomes(DATA, full)) == harvest(
        86, kept("IncreasedLife", "IncreasedEnergyShield", "LightningDamage")
    )


def test_alteration_under_a_lock_keeps_the_locked_mod_and_may_add_to_the_open_side():
    item = amulet(roll(LIFE), roll(PCBC, crafted=True), rarity=Rarity.MAGIC)

    outcomes = AlterationOrb().outcomes(DATA, item)

    assert ids(outcomes.retained) == {LIFE}
    assert seen(outcomes) == alteration(86, kept("IncreasedLife"))
    # one total of 1 mod keeps the item as it is, one of 2 adds a suffix
    assert seen(outcomes)[frozenset()] == Fraction(1, 2)


def test_alteration_under_suffixes_cannot_be_changed_keeps_the_suffix():
    item = amulet(roll(FIRE), roll(SCBC, crafted=True), rarity=Rarity.MAGIC)

    outcomes = AlterationOrb().outcomes(DATA, item)

    assert ids(outcomes.retained) == {FIRE}
    assert seen(outcomes) == alteration(86, kept("FireResistance"))


def test_alteration_that_keeps_an_attack_metamod_filters_the_draw_like_a_chaos_orb():
    item = amulet(roll(SCBC, crafted=True), roll(NO_ATTACK, crafted=True), rarity=Rarity.MAGIC)

    outcomes = AlterationOrb().outcomes(DATA, item)

    assert ids(outcomes.retained) == {NO_ATTACK}  # SCBC is a prefix: it goes; the suffix stays and fills the suffix slot
    assert seen(outcomes) == alteration(86, {META: SUFFIX}, blocked=ATTACK_FAMILIES)
    assert not any(family in ATTACK_FAMILIES for key in seen(outcomes) for family in key)


def test_alteration_that_removes_the_attack_metamod_is_the_plain_reroll():
    item = amulet(roll(LIFE), roll(NO_ATTACK, crafted=True), rarity=Rarity.MAGIC)

    assert seen(AlterationOrb().outcomes(DATA, item)) == alteration(86, {})


def test_exalted_and_the_adds_are_not_restricted_by_a_lock_and_fill_open_slots():
    item = amulet(roll(LIFE), roll(ES), roll(PCBC, crafted=True))

    shown = seen(ExaltedOrb().outcomes(DATA, item))

    assert shown == add_one(86, kept("IncreasedLife", "IncreasedEnergyShield", meta_side=SUFFIX))
    assert any(next(iter(key)) in {"ChaosResistance", "ColdResistance"} for key in shown)  # a suffix fills
    assert any(next(iter(key)) == "LightningDamage" for key in shown)  # and the third prefix too


def test_exalted_and_the_adds_keep_every_mod_under_a_lock():
    item = amulet(roll(LIFE), roll(FIRE), roll(SCBC, crafted=True))

    assert ExaltedOrb().outcomes(DATA, item).retained == item


# --- Cannot roll Attack / Caster Modifiers ---------------------------------------------------------------


def test_exalted_under_cannot_roll_attack_keeps_the_attack_tagged_families_out():
    item = amulet(roll(LIFE), roll(FIRE), roll(NO_ATTACK, crafted=True))

    shown = seen(ExaltedOrb().outcomes(DATA, item))

    assert shown == add_one(86, kept("IncreasedLife", "FireResistance", meta_side=SUFFIX), blocked=ATTACK_FAMILIES)
    assert not any(family in ATTACK_FAMILIES for key in shown for family in key)


def test_exalted_under_cannot_roll_caster_keeps_the_caster_tagged_family_out():
    data = caster_data()
    item = amulet(roll(LIFE), roll(FIRE), roll(NO_CASTER, crafted=True))

    shown = seen(ExaltedOrb().outcomes(data, item))

    assert shown == add_one(86, kept("IncreasedLife", "FireResistance", meta_side=SUFFIX), blocked=frozenset({"LightningDamagePercentage"}))
    # the attack-tagged families are in the pool under the Caster metamod
    assert frozenset({"LightningDamage"}) in shown


def test_a_mod_with_both_tags_is_blocked_by_either_metamod():
    data = caster_data()
    both = {
        mod_id: dataclasses.replace(mod, implicit_tags=(*mod.implicit_tags, "caster")) if mod.families == ("LightningDamage",) else mod
        for mod_id, mod in data.mods.items()
    }
    data = dataclasses.replace(data, mods=both)  # LightningDamage is attack and caster now
    for metamod in (NO_ATTACK, NO_CASTER):
        shown = seen(ExaltedOrb().outcomes(data, amulet(roll(FIRE), roll(metamod, crafted=True))))
        assert frozenset({"LightningDamage"}) not in shown


def test_both_tag_metamods_together_block_both_tags():
    data = caster_data()
    item = amulet(roll(FIRE), roll(NO_ATTACK, crafted=True), roll(NO_CASTER, crafted=True))

    shown = seen(ExaltedOrb().outcomes(data, item))

    both = ATTACK_FAMILIES | {"LightningDamagePercentage"}
    assert shown == add_one(86, {"FireResistance": SUFFIX, META: SUFFIX, META + "2": SUFFIX}, blocked=both)  # the suffixes are full
    assert not any(family in ATTACK_FAMILIES | {"LightningDamagePercentage"} for key in shown for family in key)


def test_augmentation_and_regal_under_cannot_roll_attack_filter_the_pool():
    magic = amulet(roll(NO_ATTACK, crafted=True), rarity=Rarity.MAGIC)  # a suffix; the prefix is open

    shown = seen(AugmentationOrb().outcomes(DATA, magic))
    assert shown == add_one(86, {META: SUFFIX}, blocked=ATTACK_FAMILIES, cap=1)
    assert shown.keys() == {frozenset({f}) for f in ("IncreasedLife", "IncreasedEnergyShield", "ItemFoundRarityIncreasePrefix", "GlobalSkillGemLevel", "GlobalDamageTypeGemLevel")}

    regal = amulet(roll(LIFE), roll(NO_ATTACK, crafted=True), rarity=Rarity.MAGIC)
    regal_shown = seen(RegalOrb().outcomes(DATA, regal))
    assert regal_shown == add_one(86, kept("IncreasedLife", meta_side=SUFFIX), blocked=ATTACK_FAMILIES, cap=3)
    assert not any(family in ATTACK_FAMILIES for key in regal_shown for family in key)


def test_chaos_under_cannot_roll_attack_alone_removes_the_metamod_and_is_the_plain_reroll():
    item = amulet(roll(LIFE), roll(FIRE), roll(NO_ATTACK, crafted=True))

    outcomes = ChaosOrb().outcomes(DATA, item)

    assert ids(outcomes.retained) == set()
    assert seen(outcomes) == reroll(86, {})  # the carrier is rerolled away: no filter


def test_chaos_under_cannot_roll_attack_with_suffixes_cannot_be_changed_filters_the_draw():
    item = amulet(roll(SCBC, crafted=True), roll(NO_ATTACK, crafted=True), roll(FIRE), roll(LIFE))

    outcomes = ChaosOrb().outcomes(DATA, item)

    assert ids(outcomes.retained) == {NO_ATTACK, FIRE}  # SCBC is a prefix: it goes
    shown = seen(outcomes)
    assert shown == reroll(86, kept("FireResistance", meta_side=SUFFIX), blocked=ATTACK_FAMILIES)
    assert not any(family in ATTACK_FAMILIES for key in shown for family in key)


def test_chaos_under_cannot_roll_caster_with_a_lock_filters_the_draw():
    data = caster_data()
    item = amulet(roll(SCBC, crafted=True), roll(NO_CASTER, crafted=True), roll(COLD))

    shown = seen(ChaosOrb().outcomes(data, item))

    assert shown == reroll(86, kept("ColdResistance", meta_side=SUFFIX), blocked=frozenset({"LightningDamagePercentage"}))


def test_chaos_keeps_a_fractured_attack_metamod_and_filters_with_it():
    item = amulet(roll(NO_ATTACK, crafted=True, fractured=True), roll(LIFE), roll(FIRE), roll(ES))

    outcomes = ChaosOrb().outcomes(DATA, item)

    assert ids(outcomes.retained) == {NO_ATTACK}
    assert seen(outcomes) == reroll(86, kept(meta_side=SUFFIX), blocked=ATTACK_FAMILIES)


def test_harvest_under_cannot_roll_attack_filters_the_first_mod_only():
    item = amulet(roll(SCBC, crafted=True), roll(NO_ATTACK, crafted=True), roll(FIRE))

    outcomes = HarvestReforge("lightning").outcomes(DATA, item)

    shown = seen(outcomes)
    assert shown == harvest(86, kept("FireResistance", meta_side=SUFFIX), first_blocked=frozenset({"LightningDamage"}))
    # D8: the draws after the guaranteed mod are not filtered, so an attack-tagged family can still come
    assert any(family in ATTACK_FAMILIES for key in shown for family in key)
    # but the guaranteed mod is never an attack-tagged one: it is the Lightning family drawn first
    plain = harvest(86, kept("FireResistance", meta_side=SUFFIX))
    assert shown != plain


def test_harvest_is_refused_when_the_attack_filter_leaves_no_tagged_mod():
    tagged = {
        mod_id: dataclasses.replace(mod, implicit_tags=(*mod.implicit_tags, "attack")) if "lightning" in mod.implicit_tags and "attack" not in mod.implicit_tags else mod
        for mod_id, mod in DATA.mods.items()
    }
    data = dataclasses.replace(DATA, mods=tagged)
    item = amulet(roll(SCBC, crafted=True), roll(NO_ATTACK, crafted=True), roll(FIRE))

    with pytest.raises(NotApplicableError, match="lightning"):
        HarvestReforge("lightning").outcomes(data, item)


def test_harvest_sampling_follows_the_first_mod_rule():
    item = amulet(roll(SCBC, crafted=True), roll(NO_ATTACK, crafted=True), roll(FIRE))
    outcomes = HarvestReforge("lightning").outcomes(DATA, item)
    rng = random.Random(7)
    for _ in range(40):
        result = outcomes.sample(rng)
        assert {NO_ATTACK, FIRE} <= ids(result)
        assert SCBC not in ids(result)


# --- Annulment ---------------------------------------------------------------------------------------------


def removed(outcomes, item) -> dict[str, Fraction]:
    return {next(iter(ids(item) - ids(result))): chance for chance, result in outcomes.results}


def test_annulment_under_prefixes_cannot_be_changed_may_remove_only_the_suffix_side_and_the_metamod():
    item = amulet(roll(LIFE), roll(ES), roll(FIRE), roll(PCBC, crafted=True))

    outcomes = AnnulmentOrb().outcomes(DATA, item)

    assert removed(outcomes, item) == {FIRE: Fraction(1, 2), PCBC: Fraction(1, 2)}


def test_annulment_under_suffixes_cannot_be_changed_may_remove_the_prefix_side_and_the_metamod():
    item = amulet(roll(LIFE), roll(FIRE), roll(COLD), roll(SCBC, crafted=True))

    assert removed(AnnulmentOrb().outcomes(DATA, item), item) == {LIFE: Fraction(1, 2), SCBC: Fraction(1, 2)}


def test_annulment_with_both_locks_has_nothing_to_remove():
    item = amulet(roll(LIFE), roll(FIRE), roll(PCBC, crafted=True), roll(SCBC, crafted=True))

    with pytest.raises(NotApplicableError, match="locked side"):
        AnnulmentOrb().outcomes(DATA, item)


def test_annulment_under_cannot_roll_attack_protects_the_attack_tagged_mods():
    item = amulet(roll(LIFE), roll(ATTACK_PREFIX), roll(FIRE), roll(ATTACK_SUFFIX), roll(NO_ATTACK, crafted=True))

    outcomes = AnnulmentOrb().outcomes(DATA, item)

    third = Fraction(1, 3)
    assert removed(outcomes, item) == {LIFE: third, FIRE: third, NO_ATTACK: third}


def test_annulment_under_cannot_roll_caster_protects_the_caster_tagged_mods_only():
    data = caster_data()
    item = amulet(roll(LIFE), roll(ATTACK_PREFIX), roll(CAST_PCT), roll(NO_CASTER, crafted=True))

    outcomes = AnnulmentOrb().outcomes(data, item)

    third = Fraction(1, 3)
    assert removed(outcomes, item) == {LIFE: third, ATTACK_PREFIX: third, NO_CASTER: third}


def test_annulment_with_a_lock_and_a_tag_metamod_applies_both_rules():
    item = amulet(roll(LIFE), roll(ES), roll(ATTACK_SUFFIX), roll(PCBC, crafted=True), roll(NO_ATTACK, crafted=True))

    outcomes = AnnulmentOrb().outcomes(DATA, item)

    # prefixes are locked and the attack-tagged leech is protected: the two metamods are the candidates
    half = Fraction(1, 2)
    assert removed(outcomes, item) == {PCBC: half, NO_ATTACK: half}


def test_annulment_is_refused_when_every_mod_is_protected_by_the_tag():
    item = amulet(roll(ATTACK_PREFIX, fractured=True), roll(ATTACK_SUFFIX, fractured=True), roll(NO_ATTACK, crafted=True, fractured=True))

    with pytest.raises(NotApplicableError):
        AnnulmentOrb().outcomes(DATA, item)


def test_annulment_distribution_covers_the_whole_item_minus_one_mod():
    item = amulet(roll(LIFE), roll(ES), roll(FIRE), roll(PCBC, crafted=True))
    outcomes = AnnulmentOrb().outcomes(DATA, item)

    assert sum(chance for chance, _ in outcomes.results) == 1
    assert all(result.rarity is Rarity.RARE and len(result.mods) == 3 for _, result in outcomes.results)


# --- Scouring -------------------------------------------------------------------------------------------------


def test_scouring_under_prefixes_cannot_be_changed_keeps_the_prefixes_and_removes_the_lock():
    item = amulet(roll(LIFE), roll(ES), roll(FIRE), roll(PCBC, crafted=True))

    result = ScouringOrb().outcomes(DATA, item).retained

    assert ids(result) == {LIFE, ES}
    assert result.rarity is Rarity.RARE  # two mods left


def test_scouring_under_suffixes_cannot_be_changed_keeps_the_suffixes():
    item = amulet(roll(LIFE), roll(FIRE), roll(COLD), roll(SCBC, crafted=True))

    result = ScouringOrb().outcomes(DATA, item).retained

    assert ids(result) == {FIRE, COLD}
    assert result.rarity is Rarity.RARE


def test_scouring_with_one_mod_left_by_a_lock_makes_the_item_magic():
    item = amulet(roll(LIFE), roll(FIRE), roll(PCBC, crafted=True))

    result = ScouringOrb().outcomes(DATA, item).retained

    assert ids(result) == {LIFE} and result.rarity is Rarity.MAGIC


def test_scouring_with_both_locks_changes_nothing():
    item = amulet(roll(LIFE), roll(FIRE), roll(PCBC, crafted=True), roll(SCBC, crafted=True))

    assert ScouringOrb().outcomes(DATA, item).retained == item


@pytest.mark.parametrize("metamod", (NO_ATTACK, NO_CASTER, MULTI))
def test_scouring_ignores_the_tag_metamods_and_the_multimod(metamod):
    item = amulet(roll(LIFE), roll(ATTACK_SUFFIX), roll(metamod, crafted=True))

    result = ScouringOrb().outcomes(DATA, item).retained

    assert result.mods == () and result.rarity is Rarity.NORMAL


# --- essences ----------------------------------------------------------------------------------------------


HYSTERIA = "Essence of Hysteria"  # a corrupted essence that reforges a rare item (fixture: forced suffix on an amulet)


@pytest.mark.parametrize("metamod", (PCBC, SCBC, NO_ATTACK, NO_CASTER))
def test_an_essence_is_refused_under_each_of_the_four_metamods(metamod):
    item = amulet(roll(LIFE), roll(metamod, crafted=True))

    with pytest.raises(NotApplicableError, match="metamod"):
        ApplyEssence(HYSTERIA).outcomes(DATA, item)


def test_the_multimod_does_not_block_an_essence_and_the_reroll_removes_it():
    item = amulet(roll(LIFE), roll(MULTI, crafted=True))
    plain = amulet(roll(LIFE))

    essence = ApplyEssence(HYSTERIA).outcomes(DATA, item)

    assert seen(essence) == seen(ApplyEssence(HYSTERIA).outcomes(DATA, plain))
    assert MULTI not in ids(essence.sample(random.Random(3)))


# --- the bench: three crafted mods and Remove Crafted Mods -------------------------------------------------


BELT = "Metadata/Items/Belts/Belt3"
HYBRID, DAMAGE_1, ELEMENTAL = "JunMaster2ArmourAndEnergyShield1", "JunMaster2AllDamage2_", "EinharMasterWeaponElementalDamage2"  # belt prefixes
RESIST = "LightningResist1"


def belt(*mods):
    return item(*mods, base_id=BELT, rarity=Rarity.RARE, item_level=86)


def test_the_multimod_lifts_the_crafted_limit_to_three_counting_itself():
    one = belt(roll(RESIST), roll(MULTI, crafted=True))
    two = BenchCraft(HYBRID).outcomes(DATA, one).sample(random.Random(1))
    assert len(two.crafted_mods) == 2

    three = BenchCraft(DAMAGE_1).outcomes(DATA, two).sample(random.Random(1))
    assert len(three.crafted_mods) == 3

    with pytest.raises(NotApplicableError, match=r"3 crafted mods.*limit \(3\)"):
        BenchCraft(ELEMENTAL).outcomes(DATA, three)


def test_without_the_multimod_one_crafted_mod_is_the_limit():
    one = belt(roll(RESIST), roll(DAMAGE_1, crafted=True))

    with pytest.raises(NotApplicableError, match=r"1 crafted mod, which is the limit \(1\)"):
        BenchCraft(HYBRID).outcomes(DATA, one)


def test_a_metamod_counts_toward_the_limit_of_three():
    held = belt(roll(RESIST), roll(MULTI, crafted=True), roll(NO_ATTACK, crafted=True), roll(DAMAGE_1, crafted=True))

    with pytest.raises(NotApplicableError, match=r"limit \(3\)"):
        BenchCraft(HYBRID).outcomes(DATA, held)


def test_the_multimod_does_not_change_a_chaos_orb_except_by_being_rerolled_away():
    item = amulet(roll(LIFE), roll(MULTI, crafted=True), roll(DAMAGE_1, crafted=True))

    outcomes = ChaosOrb().outcomes(DATA, item)

    assert ids(outcomes.retained) == set()
    assert seen(outcomes) == reroll(86, {})


def test_remove_crafted_mods_ends_every_metamod_whatever_the_lock():
    item = amulet(roll(LIFE), roll(FIRE), roll(PCBC, crafted=True), roll(NO_ATTACK, crafted=True), roll(DAMAGE_1, crafted=True))

    result = RemoveCraftedMods().outcomes(DATA, item).sample(random.Random(1))

    assert ids(result) == {LIFE, FIRE}
    assert not result.metamods(DATA)


def test_remove_crafted_mods_leaves_a_fractured_crafted_mod():
    item = amulet(roll(LIFE), roll(NO_ATTACK, crafted=True, fractured=True), roll(PCBC, crafted=True))

    result = RemoveCraftedMods().outcomes(DATA, item).sample(random.Random(1))

    assert ids(result) == {LIFE, NO_ATTACK}
    assert result.metamods(DATA) == {Metamod.NO_ATTACK_MODS}


def test_remove_crafted_mods_is_refused_when_only_fractured_crafted_mods_remain():
    item = amulet(roll(LIFE), roll(NO_ATTACK, crafted=True, fractured=True))

    with pytest.raises(NotApplicableError, match="not fractured"):
        RemoveCraftedMods().outcomes(DATA, item)


# --- the Fracturing Orb ---------------------------------------------------------------------------------------


def test_the_fracturing_orb_counts_metamods_and_may_fracture_one():
    item = amulet(roll(LIFE), roll(FIRE), roll(COLD), roll(NO_ATTACK, crafted=True))

    outcomes = FracturingOrb().outcomes(DATA, item)

    assert len(outcomes.results) == 4
    assert sum(chance for chance, _ in outcomes.results) == 1 and all(chance == Fraction(1, 4) for chance, _ in outcomes.results)
    fractured_ids = {next(entry.mod_id for entry in result.fractured_mods) for _, result in outcomes.results}
    assert fractured_ids == {LIFE, FIRE, COLD, NO_ATTACK}


def test_a_fractured_metamod_stays_through_a_chaos_orb_and_keeps_working():
    start = amulet(roll(LIFE), roll(FIRE), roll(COLD), roll(NO_ATTACK, crafted=True))
    fractured = next(result for _, result in FracturingOrb().outcomes(DATA, start).results if result.fractured_mods[0].mod_id == NO_ATTACK)
    assert fractured.fractured_mods[0].crafted
    assert Metamod.NO_ATTACK_MODS in fractured.metamods(DATA)

    outcomes = ChaosOrb().outcomes(DATA, fractured)

    assert ids(outcomes.retained) == {NO_ATTACK}
    assert seen(outcomes) == reroll(86, kept(meta_side=SUFFIX), blocked=ATTACK_FAMILIES)


def test_a_fractured_crafted_mod_survives_scouring_and_an_exalted_orb_keeps_it():
    fractured = amulet(roll(LIFE), roll(FIRE), roll(NO_ATTACK, crafted=True, fractured=True))
    assert ScouringOrb().outcomes(DATA, fractured).retained.mods == (roll(NO_ATTACK, crafted=True, fractured=True),)
    assert ExaltedOrb().outcomes(DATA, fractured).retained == fractured


def test_the_fracturing_orb_refuses_an_item_that_already_holds_a_fractured_crafted_mod():
    item = amulet(roll(LIFE), roll(FIRE), roll(COLD), roll(NO_ATTACK, crafted=True, fractured=True))

    with pytest.raises(NotApplicableError, match="fractured"):
        FracturingOrb().outcomes(DATA, item)


def test_regal_under_cannot_roll_caster_filters_the_caster_family():
    data = caster_data()
    magic = amulet(roll(LIFE), roll(NO_CASTER, crafted=True), rarity=Rarity.MAGIC)

    shown = seen(RegalOrb().outcomes(data, magic))

    assert shown == add_one(86, kept("IncreasedLife", meta_side=SUFFIX), blocked=frozenset({"LightningDamagePercentage"}), cap=3)


def test_harvest_under_cannot_roll_caster_filters_the_first_mod_only():
    data = caster_data()  # Lightning Damage % is Lightning-tagged and, here, Caster-tagged
    item = amulet(roll(SCBC, crafted=True), roll(NO_CASTER, crafted=True), roll(FIRE))

    shown = seen(HarvestReforge("lightning").outcomes(data, item))

    assert shown == harvest(86, kept("FireResistance", meta_side=SUFFIX), first_blocked=frozenset({"LightningDamagePercentage"}))
    assert any("LightningDamagePercentage" in key for key in shown)  # it can still come after the guaranteed mod
