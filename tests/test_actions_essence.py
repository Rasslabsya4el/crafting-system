"""Essences as exact actions, against the hand oracle in exact fractions (ticket #55).

The oracle (`essence_oracle.py`) walks every draw order by hand. The fixture has the Whispering
Essence of Hatred (level 1, cap 35, forced suffix `ColdDamagePercentEssence1` on an amulet) and the
corrupted Essence of Hysteria (level 8, no cap, forced suffix `IncreasedLifeLeechRateEssence1`, a
required level of 63), and the Remnant of Corruption (a record that is no craft).
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from actions_support import AMULET, DATA, amulet, roll
from essence_oracle import essence_chance

from crafting_system.actions import (
    ApplyEssence,
    ChaosOrb,
    HarvestReforge,
    NotApplicableError,
    OutOfScopeError,
)
from crafting_system.data import Essence, EssenceMod
from crafting_system.items import ExplicitMod, Influence, Item, Rarity

HATRED = "Whispering Essence of Hatred"
HYSTERIA = "Essence of Hysteria"
HATRED_MOD = "ColdDamagePercentEssence1"
HYSTERIA_MOD = "IncreasedLifeLeechRateEssence1"
CRAFTED_PREFIX = "JunMaster2AllDamage2_"


def fractured(mod_id):
    return roll(mod_id, fractured=True)


def chance(action, item, target):
    return action.outcomes(DATA, item).chance_all([target])


def with_essences(data, *records):
    return dataclasses.replace(data, essences={**data.essences, **{e.id: e for e in records}})


def with_mod(data, mod):
    return dataclasses.replace(data, mods={**data.mods, mod.id: mod})


TARGETS = ("IncreasedLife3", "IncreasedLife1", "AddedLightningDamage5", "LightningDamagePercent3",
           "GlobalLightningGemLevel1", "LightningResist1", "ManaLeechPermyriadSuffix1")  # fmt: skip


@pytest.mark.parametrize("item_level", [20, 34, 35, 86])
@pytest.mark.parametrize("target", TARGETS)
def test_a_low_essence_on_a_normal_amulet_caps_the_random_mods_by_the_lower_of_item_level_and_cap(
    item_level, target
):
    item = amulet(rarity=Rarity.NORMAL, item_level=item_level)

    assert chance(ApplyEssence(HATRED), item, target) == essence_chance(target, item_level, cap=35)


def test_the_cap_and_the_item_level_both_decide_where_the_pool_ends():
    normal = lambda level: amulet(rarity=Rarity.NORMAL, item_level=level)  # noqa: E731
    action = ApplyEssence(HATRED)

    assert chance(action, normal(86), "AddedLightningDamage5") > 0  # level 35 = the cap: in
    assert chance(action, normal(86), "LightningDamagePercent3") == 0  # level 36: out
    assert chance(action, normal(34), "AddedLightningDamage5") == 0  # item level 34 binds: out
    assert chance(action, normal(86), "GlobalLightningGemLevel1") == 0


@pytest.mark.parametrize("target", ["IncreasedLife3", "LightningResist1"])
def test_the_forced_mod_is_on_the_item_whatever_else_is_drawn(target):
    outcomes = ApplyEssence(HATRED).outcomes(DATA, amulet(rarity=Rarity.NORMAL, item_level=10))

    assert outcomes.chance_all([HATRED_MOD]) == 1
    assert outcomes.chance_all([HATRED_MOD, target]) == outcomes.chance_all([target])


def test_the_forced_mod_applies_above_the_item_level():
    outcomes = ApplyEssence(HYSTERIA).outcomes(DATA, amulet(item_level=50))  # the forced mod needs 63

    assert outcomes.chance_all([HYSTERIA_MOD]) == 1
    assert HYSTERIA_MOD in {m.mod_id for m in outcomes.retained.mods}


FRACTURED_BY_FAMILY = {
    "LightningResistance": "LightningResist1",
    "IncreasedLife": "IncreasedLife1",
    "ChaosResistance": "ChaosResist1",
    "ColdResistance": "ColdResist1",
    "FireResistance": "FireResist1",
}
KEPT_FAMILIES = [(), ("LightningResistance",), ("IncreasedLife", "ChaosResistance"), ("ColdResistance", "FireResistance")]
# the oracle gives 0 for a family that is kept; the fractured mod itself is held with certainty
REROLL_CASES = [
    (level, target, kept)
    for level in (50, 86)
    for target in TARGETS
    for kept in KEPT_FAMILIES
    if target not in {FRACTURED_BY_FAMILY[family] for family in kept}
]


@pytest.mark.parametrize(("item_level", "target", "kept"), REROLL_CASES)
def test_a_corrupted_essence_on_a_rare_amulet_matches_the_oracle(item_level, target, kept):
    item = amulet(*(fractured(FRACTURED_BY_FAMILY[family]) for family in kept), item_level=item_level)

    assert chance(ApplyEssence(HYSTERIA), item, target) == essence_chance(target, item_level, kept=kept)


@pytest.mark.parametrize("item_level", [50, 86])
@pytest.mark.parametrize("target", TARGETS)
def test_a_corrupted_essence_on_a_normal_amulet_matches_the_oracle(item_level, target):
    item = amulet(rarity=Rarity.NORMAL, item_level=item_level)

    assert chance(ApplyEssence(HYSTERIA), item, target) == essence_chance(target, item_level)


def forcing(mod_id):
    """The fixture data with a corrupted essence whose forced mod on an amulet is `mod_id` (a mod of the pool)."""
    record = Essence("Metadata/Items/Currency/Test", "Essence of Test", 6, True, 8, None, 1, (EssenceMod("Amulet", mod_id),))
    return with_essences(DATA, record)


FORCED_IN_THE_POOL = [("IncreasedLife3", "IncreasedLife"), ("LightningResist8", "LightningResistance"),
                      ("AddedLightningDamage9", "LightningDamage")]  # fmt: skip


@pytest.mark.parametrize(("forced", "family"), FORCED_IN_THE_POOL)
@pytest.mark.parametrize("item_level", [50, 86])
@pytest.mark.parametrize("target", [t for t in TARGETS if t not in {"IncreasedLife3", "IncreasedLife1", "LightningResist1"}])
@pytest.mark.parametrize("kept", [(), ("ChaosResistance",)])
def test_a_forced_mod_of_a_pool_family_takes_the_family_and_a_slot_off_the_pool(
    forced, family, item_level, target, kept
):
    """The forced mod is a prefix (IncreasedLife3, AddedLightningDamage9) or a suffix (LightningResist8)."""
    item = amulet(*(fractured("ChaosResist1") for _ in kept), item_level=item_level)

    got = ApplyEssence("Essence of Test").outcomes(forcing(forced), item).chance_all([target])

    assert got == essence_chance(target, item_level, kept=kept, forced_family=family)


def test_a_forced_mod_of_a_pool_family_is_held_and_blocks_its_family():
    outcomes = ApplyEssence("Essence of Test").outcomes(forcing("IncreasedLife3"), amulet(item_level=50))

    assert outcomes.chance_all(["IncreasedLife3"]) == 1
    assert outcomes.chance_all(["IncreasedLife1"]) == 0
    assert all(f.family != "IncreasedLife" for f in outcomes.pool)


def test_a_low_essence_without_a_cap_in_the_data_is_out_of_scope():
    record = dataclasses.replace(DATA.essences["Metadata/Items/Currency/CurrencyEssenceHatred1"], item_level_restriction=None)
    data = with_essences(DATA, record)

    with pytest.raises(OutOfScopeError, match="no level cap"):
        ApplyEssence(HATRED).outcomes(data, amulet(rarity=Rarity.NORMAL))


def test_the_forced_mod_and_the_fractured_mods_count_inside_the_total():
    # three kept mods (two fractured and the forced one): a total of 4 draws one, 5 two, 6 three
    outcomes = ApplyEssence(HYSTERIA).outcomes(
        DATA, amulet(fractured("IncreasedLife1"), fractured("ChaosResist1"))
    )
    sizes = {}
    for outcome, probability in outcomes.distribution(lambda mod: "new").items():
        sizes[sum(count for _, count in outcome)] = probability

    assert sizes == {1: Fraction(8, 12), 2: Fraction(3, 12), 3: Fraction(1, 12)}


def test_when_the_kept_mods_reach_the_total_nothing_is_drawn():
    item = amulet(fractured("IncreasedLife1"), fractured("ChaosResist1"), fractured("ColdResist1"))
    outcomes = ApplyEssence(HYSTERIA).outcomes(DATA, item)

    assert dict(outcomes.distribution(lambda mod: "new")) == {
        frozenset(): Fraction(8, 12),
        frozenset({("new", 1)}): Fraction(3, 12),
        frozenset({("new", 2)}): Fraction(1, 12),
    }


def test_the_distribution_sums_to_one_and_the_chance_is_an_exact_fraction():
    outcomes = ApplyEssence(HATRED).outcomes(DATA, amulet(rarity=Rarity.NORMAL))

    assert sum(outcomes.distribution(lambda mod: mod.generation_type).values()) == 1
    assert type(outcomes.chance_all(["IncreasedLife3"])) is Fraction


def test_the_retained_item_is_a_rare_with_the_forced_mod_and_the_fractured_mods():
    outcomes = ApplyEssence(HYSTERIA).outcomes(DATA, amulet(fractured("LightningResist1")))

    assert outcomes.forced == HYSTERIA_MOD and outcomes.tag is None
    assert outcomes.retained.rarity is Rarity.RARE
    assert {m.mod_id for m in outcomes.retained.mods} == {"LightningResist1", HYSTERIA_MOD}
    normal = ApplyEssence(HATRED).outcomes(DATA, amulet(rarity=Rarity.NORMAL))
    assert normal.retained.rarity is Rarity.RARE and [m.mod_id for m in normal.retained.mods] == [HATRED_MOD]


def test_a_reroll_that_removes_a_crafted_mod_gives_the_chance_of_the_item_without_it():
    plain = amulet(fractured("LightningResist1"))
    crafted = amulet(fractured("LightningResist1"), roll(CRAFTED_PREFIX, crafted=True))

    for action in (ApplyEssence(HYSTERIA), ChaosOrb(), HarvestReforge("lightning")):
        for target in ("IncreasedLife3", "GlobalLightningGemLevel1"):
            assert chance(action, crafted, target) == chance(action, plain, target)
    assert chance(ApplyEssence(HYSTERIA), crafted, "IncreasedLife3") == essence_chance(
        "IncreasedLife3", 86, kept=("LightningResistance",)
    )


def test_the_crafted_mod_is_gone_and_the_fractured_one_stays_in_every_sample():
    item = amulet(fractured("LightningResist1"), roll(CRAFTED_PREFIX, crafted=True))
    outcomes = ApplyEssence(HYSTERIA).outcomes(DATA, item)
    rng = random.Random(7)

    for _ in range(100):
        result = outcomes.sample(rng)
        ids = {m.mod_id for m in result.mods}
        assert CRAFTED_PREFIX not in ids and result.crafted_mods == ()
        assert {"LightningResist1", HYSTERIA_MOD} <= ids and 4 <= len(ids) <= 6
        assert [m.mod_id for m in result.fractured_mods] == ["LightningResist1"]


def test_samples_of_a_low_essence_respect_the_cap_and_roll_the_forced_mod():
    outcomes = ApplyEssence(HATRED).outcomes(DATA, amulet(rarity=Rarity.NORMAL, item_level=86))
    rng = random.Random(11)
    forced_values = set()

    for _ in range(300):
        result = outcomes.sample(rng)
        assert result.rarity is Rarity.RARE and 4 <= len(result.mods) <= 6
        for entry in result.mods:
            mod = DATA.mods[entry.mod_id]
            if entry.mod_id == HATRED_MOD:
                forced_values.add(entry.values)
            else:
                assert mod.required_level <= 35
    assert len(forced_values) > 1  # rolled, not pinned at the lowest value


def test_the_sampler_frequency_follows_the_exact_chance():
    outcomes = ApplyEssence(HATRED).outcomes(DATA, amulet(rarity=Rarity.NORMAL, item_level=86))
    exact = float(outcomes.chance_all(["IncreasedLife3"]))
    rng = random.Random(3)
    runs = 4000
    hits = sum("IncreasedLife3" in {m.mod_id for m in outcomes.sample(rng).mods} for _ in range(runs))

    assert abs(hits / runs - exact) < 5 * (exact * (1 - exact) / runs) ** 0.5


def test_rune_dagger_takes_the_dagger_mod_and_warstaff_the_staff_mod():
    sword = DATA.base_items["Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1"]
    for item_class, expected in (("Rune Dagger", "LocalAddedColdDamage1"), ("Warstaff", None)):
        base = dataclasses.replace(sword, item_class=item_class)
        data = dataclasses.replace(DATA, base_items={**DATA.base_items, sword.id: base})
        item = dataclasses.replace(amulet(rarity=Rarity.NORMAL), base_id=sword.id)
        if expected is None:
            staff = data.essences["Metadata/Items/Currency/CurrencyEssenceHatred1"].mod_for("Staff")
            expected = staff
        outcomes = ApplyEssence(HATRED).outcomes(data, item)
        assert outcomes.forced == expected


def test_an_essence_can_be_named_by_its_record_id():
    record = "Metadata/Items/Currency/CurrencyEssenceHatred1"

    assert ApplyEssence(record).outcomes(DATA, amulet(rarity=Rarity.NORMAL)).forced == HATRED_MOD


# refusals -------------------------------------------------------------------------------------


def test_a_low_essence_on_a_rare_item_is_refused_by_the_game():
    with pytest.raises(NotApplicableError, match="normal item only"):
        ApplyEssence(HATRED).outcomes(DATA, amulet())


@pytest.mark.parametrize("name", [HATRED, HYSTERIA])
def test_a_magic_item_is_refused_by_the_game(name):
    with pytest.raises(NotApplicableError, match="normal or rare item only"):
        ApplyEssence(name).outcomes(DATA, amulet(roll("IncreasedLife1"), rarity=Rarity.MAGIC))


@pytest.mark.parametrize("rarity", [Rarity.NORMAL, Rarity.RARE])
def test_a_corrupted_item_is_refused_by_the_game(rarity):
    item = dataclasses.replace(amulet(rarity=rarity), corrupted=True)

    with pytest.raises(NotApplicableError, match="corrupted.*takes no essence"):
        ApplyEssence(HYSTERIA).outcomes(DATA, item)


def test_a_forced_mod_in_a_family_of_a_fractured_mod_is_refused_by_the_game():
    clash = dataclasses.replace(
        DATA.mods["LifeLeechPermyriadSuffix1"], id="ClashMod", families=("IncreasedLifeLeechRate",)
    )
    data = with_mod(DATA, clash)
    low = tuple(min(stat.min, stat.max) for stat in clash.stats)
    item = Item.build(
        data, base_id=AMULET, item_level=86, rarity=Rarity.RARE,
        mods=(ExplicitMod("ClashMod", 1, low, fractured=True),),
    )  # fmt: skip

    with pytest.raises(NotApplicableError, match="already has a mod of this type.*ClashMod"):
        ApplyEssence(HYSTERIA).outcomes(data, item)
    assert ApplyEssence(HYSTERIA).outcomes(data, amulet(fractured("LightningResist1"))).forced  # no clash


def test_an_item_class_with_no_forced_mod_is_refused_by_the_game():
    base = dataclasses.replace(DATA.base_items[AMULET], item_class="Jewel")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, AMULET: base})

    with pytest.raises(NotApplicableError, match="gives no mod on Jewel"):
        ApplyEssence(HYSTERIA).outcomes(data, amulet(rarity=Rarity.NORMAL))


def test_essence_of_desolation_is_not_a_b1_action():
    desolation = Essence(
        "Metadata/Items/Currency/CurrencyEssenceFaridun1", "Essence of Desolation", 0, False, 0, 15, 1,
        (EssenceMod("Amulet", HYSTERIA_MOD),),
    )  # fmt: skip
    data = with_essences(DATA, desolation)

    for item in (amulet(rarity=Rarity.NORMAL), amulet()):
        with pytest.raises(OutOfScopeError, match="Essence of Desolation is not a B1 action"):
            ApplyEssence("Essence of Desolation").outcomes(data, item)


def test_the_remnant_of_corruption_and_an_unknown_name_are_no_essence():
    with pytest.raises(ValueError, match="no essence craft"):
        ApplyEssence("Remnant of Corruption").outcomes(DATA, amulet(rarity=Rarity.NORMAL))
    with pytest.raises(ValueError, match="no essence 'Essence of Nothing'"):
        ApplyEssence("Essence of Nothing").outcomes(DATA, amulet(rarity=Rarity.NORMAL))
    with pytest.raises(ValueError):
        ApplyEssence("  ")


def test_a_metamod_refuses_the_essence():
    meta = amulet(roll("DexMasterItemGenerationCannotChangeSuffixes", crafted=True))  # a normal item holds no mod
    with pytest.raises(NotApplicableError, match="metamod"):
        ApplyEssence(HYSTERIA).outcomes(DATA, meta)


@pytest.mark.parametrize("name", [HATRED, HYSTERIA])
def test_an_influence_of_a_class_with_no_key_makes_the_item_out_of_scope(name):
    sword = dataclasses.replace(DATA.base_items[AMULET], item_class="Fishing Rod")
    rod_essences = {
        key: dataclasses.replace(e, mods=(*e.mods, EssenceMod("Fishing Rod", e.mod_for("Amulet"))))
        for key, e in DATA.essences.items()
    }  # the odd class takes the essence like an amulet, so only the influence key is missing
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, AMULET: sword}, essences=rod_essences)
    influenced = dataclasses.replace(amulet(rarity=Rarity.NORMAL), influences=frozenset({Influence.SHAPER}))
    with pytest.raises(OutOfScopeError, match="influence class key"):
        ApplyEssence(name).outcomes(data, influenced)


@pytest.mark.parametrize("name", [HATRED, HYSTERIA])
def test_an_influenced_amulet_takes_an_essence(name):
    influenced = dataclasses.replace(amulet(rarity=Rarity.NORMAL), influences=frozenset({Influence.SHAPER}))

    assert ApplyEssence(name).outcomes(DATA, influenced).retained.influences == influenced.influences


def test_fractured_mods_that_fill_the_side_of_the_forced_mod_are_out_of_scope():
    item = amulet(fractured("ColdResist1"), fractured("FireResist1"), fractured("LifeRegeneration1"))

    with pytest.raises(OutOfScopeError, match="fill every suffix slot"):
        ApplyEssence(HYSTERIA).outcomes(DATA, item)


def test_a_not_applicable_error_comes_before_an_out_of_scope_one():
    item = dataclasses.replace(amulet(), corrupted=True, influences=frozenset({Influence.HUNTER}))

    with pytest.raises(NotApplicableError):
        ApplyEssence(HYSTERIA).outcomes(DATA, item)
