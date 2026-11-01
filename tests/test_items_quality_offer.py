"""Catalyst quality and the unveil offer of an item, and the canonical seed of a veiled placeholder (ADR-0026, ADR-0029)."""

import dataclasses

import pytest
from implicits_support import BELT, BOOTS, EXTENDED, make, on_body, placeholder
from items_support import BODY, DATA, roll
from repoe_support import no_network  # noqa: F401

from crafting_system.data import Weight
from crafting_system.items import (
    CATALYST_ITEM_CLASSES,
    MAX_QUALITY,
    VEILED_SEED_STAT,
    CatalystType,
    ExplicitMod,
    Item,
    ItemError,
    ModSlotError,
    Quality,
    QualityError,
    Rarity,
    UnknownModError,
    ValueRangeError,
    VeilOfferError,
    veiled_placeholder,
)

INTRINSIC_20 = Quality(CatalystType.INTRINSIC, 20)
OFFER = ("UnveiledPrefixAilments1", "UnveiledPrefixLife1", "UnveiledPrefixMana1")


# quality


def test_the_catalyst_types_are_the_twelve_lowercase_names():
    assert sorted(CatalystType) == sorted(
        "abrasive accelerating fertile imbued intrinsic noxious prismatic tempering turbulent unstable sinistral dextral".split()
    )
    assert MAX_QUALITY == 20
    assert CATALYST_ITEM_CLASSES == {"Ring", "Amulet", "Belt"}


def test_quality_on_a_belt_is_accepted():
    assert make(quality=INTRINSIC_20).quality == INTRINSIC_20


def test_quality_on_a_fixture_amulet_is_accepted():
    built = Item.build(
        DATA,
        base_id="Metadata/Items/Amulets/Amulet1",
        item_level=84,
        rarity=Rarity.RARE,
        quality=Quality(CatalystType.IMBUED, 5),
    )

    assert built.quality.percent == 5


def test_quality_on_boots_is_rejected():
    with pytest.raises(QualityError, match=rf"item on {BOOTS}: quality intrinsic 20%.*Amulet, Belt, Ring.*is Boots"):
        make(base_id=BOOTS, quality=INTRINSIC_20)


def test_quality_on_a_body_armour_is_rejected():
    with pytest.raises(QualityError, match=rf"^item on {BODY}: quality"):
        on_body(quality=INTRINSIC_20)


@pytest.mark.parametrize("percent", [0, 1, 19, 20])
def test_the_edge_percents_are_accepted(percent):
    assert Quality(CatalystType.FERTILE, percent).percent == percent


@pytest.mark.parametrize("percent", [21, -1, 100])
def test_a_percent_outside_0_to_20_is_rejected(percent):
    with pytest.raises(QualityError, match=rf"fertile has percent {percent}, outside 0 to 20"):
        Quality(CatalystType.FERTILE, percent)


@pytest.mark.parametrize("percent", [10.0, "10", None, True])
def test_a_percent_that_is_not_an_integer_is_rejected(percent):
    with pytest.raises(QualityError, match="not an integer"):
        Quality(CatalystType.FERTILE, percent)


@pytest.mark.parametrize("kind", ["intrinsic", None, 3])
def test_a_quality_type_that_is_not_a_catalyst_type_is_rejected(kind):
    with pytest.raises(QualityError, match="is not a CatalystType"):
        Quality(kind, 10)


def test_a_quality_of_zero_percent_is_no_quality():
    zero = make(quality=Quality(CatalystType.INTRINSIC, 0))

    assert zero.quality is None
    assert zero == make()
    assert hash(zero) == hash(make())


def test_a_quality_of_zero_percent_is_fine_on_a_base_that_takes_none():
    assert make(base_id=BOOTS, quality=Quality(CatalystType.INTRINSIC, 0)).quality is None


def test_the_type_distinguishes_two_qualities():
    assert make(quality=Quality(CatalystType.INTRINSIC, 5)) != make(quality=Quality(CatalystType.NOXIOUS, 5))
    assert make(quality=Quality(CatalystType.INTRINSIC, 5)) != make(quality=Quality(CatalystType.INTRINSIC, 6))


@pytest.mark.parametrize("bad", ["intrinsic", (CatalystType.INTRINSIC, 20), 20])
def test_an_item_quality_must_be_a_quality_or_none(bad):
    with pytest.raises(QualityError, match=rf"item on {BELT}: quality .* is not a Quality or None"):
        make(quality=bad)


def test_changed_keeps_and_sets_the_quality():
    built = make(quality=INTRINSIC_20)

    assert built.changed(EXTENDED, corrupted=True).quality == INTRINSIC_20
    assert built.changed(EXTENDED, quality=None).quality is None
    assert built.changed(EXTENDED, quality=Quality(CatalystType.NOXIOUS, 3)).quality.type is CatalystType.NOXIOUS
    with pytest.raises(QualityError):
        built.changed(EXTENDED, base_id=BOOTS)


# the veiled placeholder and its seed


def test_a_veiled_placeholder_builds_with_tier_1_and_the_minimum_seed():
    built = make(veiled_placeholder(EXTENDED, "VeiledPrefix"))

    assert built.mods == (ExplicitMod("VeiledPrefix", 1, (1, 1)),)
    assert VEILED_SEED_STAT == "veiled_mod_seed"


def test_veiled_placeholder_of_a_mod_that_is_not_veiled_is_refused():
    with pytest.raises(ModSlotError, match="UnveiledPrefixLife1 is of domain unveiled, not veiled"):
        veiled_placeholder(EXTENDED, "UnveiledPrefixLife1")
    with pytest.raises(UnknownModError, match="NoSuchMod"):
        veiled_placeholder(EXTENDED, "NoSuchMod")


def test_the_seed_is_made_canonical_by_build():
    odd = make(placeholder(seed=777))

    assert odd.mods[0].values == (1, 1)
    assert odd == make(placeholder(seed=1))
    assert hash(odd) == hash(make(placeholder(seed=1)))


def test_a_second_placeholder_has_the_type_stat_of_its_own_mod():
    built = make(placeholder("VeiledPrefix", seed=29999), placeholder("VeiledSuffix", seed=5))

    assert [mod.values for mod in built.mods] == [(1, 1), (2, 1)]


def test_add_mod_makes_the_seed_canonical():
    added = make().add_mod(EXTENDED, placeholder(seed=12345))

    assert added.mods[0].values == (1, 1)
    assert added == make(placeholder(seed=1))


def test_changed_makes_the_seed_canonical():
    assert make().changed(EXTENDED, mods=(placeholder(seed=30000),)).mods[0].values == (1, 1)


def test_a_direct_item_with_a_non_canonical_seed_fails_validate():
    direct = Item(base_id=BELT, item_level=84, rarity=Rarity.RARE, mods=(placeholder(seed=777),))

    with pytest.raises(ValueRangeError, match=rf"item on {BELT}: mod VeiledPrefix has veiled seed 777.*canonical 1.*Item.build"):
        direct.validate(EXTENDED)
    direct.canonical(EXTENDED).validate(EXTENDED)


def test_build_sets_any_seed_to_the_canonical_one_even_out_of_range():
    assert make(placeholder(seed=999999)).mods[0].values == (1, 1)


def test_canonical_leaves_unknown_mods_and_other_domains_alone():
    odd = Item(
        base_id=BELT,
        item_level=84,
        rarity=Rarity.RARE,
        mods=(ExplicitMod("NoSuchMod", 1, (777,)), roll("ColdResist1")),
    )

    assert odd.canonical(EXTENDED) is odd
    with pytest.raises(UnknownModError):
        Item.build(EXTENDED, base_id=BELT, item_level=84, rarity=Rarity.RARE, mods=odd.mods)


def test_canonical_leaves_a_wrong_count_of_values_for_validate():
    wrong = ExplicitMod("VeiledPrefix", 1, (1,))

    with pytest.raises(ValueRangeError, match="VeiledPrefix has 1 rolled value.*2 stat"):
        make(wrong)


def test_a_veiled_mod_flagged_crafted_is_rejected_like_any_natural_mod():
    with pytest.raises(ModSlotError, match="VeiledPrefix.*flagged crafted"):
        make(dataclasses.replace(placeholder(), crafted=True))


# the unveil offer


def test_a_veil_offer_of_three_is_accepted():
    built = make(placeholder(), veil_offer=OFFER)

    assert built.veil_offer == OFFER


def test_an_offer_of_one_or_two_is_accepted():
    assert make(placeholder(), veil_offer=("UnveiledPrefixMana1",)).veil_offer == ("UnveiledPrefixMana1",)
    assert len(make(placeholder(), veil_offer=OFFER[:2]).veil_offer) == 2


def test_a_suffix_placeholder_takes_a_suffix_offer():
    offer = ("UnveiledSuffixCrit1", "UnveiledSuffixSpeed1")

    assert make(placeholder("VeiledSuffix"), veil_offer=offer).veil_offer == offer


def test_the_order_of_the_offer_does_not_matter():
    first = make(placeholder(), veil_offer=OFFER)
    second = make(placeholder(), veil_offer=tuple(reversed(OFFER)))

    assert first == second
    assert hash(first) == hash(second)
    assert first.veil_offer == tuple(sorted(OFFER))


def test_an_offer_of_four_is_rejected():
    with pytest.raises(VeilOfferError, match=rf"item on {BELT}: veil offer holds 4 mods, at most 3"):
        make(placeholder(), veil_offer=(*OFFER, "UnveiledPrefixAilments2"))


def test_a_repeated_offered_mod_is_rejected():
    with pytest.raises(VeilOfferError, match="mod UnveiledPrefixLife1 is offered twice"):
        make(placeholder(), veil_offer=("UnveiledPrefixLife1", "UnveiledPrefixLife1"))


def test_an_unknown_offered_mod_is_rejected():
    with pytest.raises(UnknownModError, match=rf"item on {BELT}: offered mod NoSuchMod is not in the game data"):
        make(placeholder(), veil_offer=("NoSuchMod",))


def test_an_offered_mod_of_the_wrong_domain_is_rejected():
    with pytest.raises(VeilOfferError, match="offered mod ColdResist1 is of domain item, not unveiled"):
        make(placeholder(), veil_offer=("ColdResist1",))


def test_an_offered_mod_of_the_other_side_is_rejected():
    with pytest.raises(VeilOfferError, match="offered mod UnveiledSuffixCrit1 is a suffix, but the placeholder VeiledPrefix is a prefix"):
        make(placeholder(), veil_offer=("UnveiledPrefixLife1", "UnveiledSuffixCrit1"))


def test_two_offered_mods_of_one_family_are_rejected():
    with pytest.raises(VeilOfferError, match="offered mods UnveiledPrefixAilments1 and UnveiledPrefixAilments2 share the family AvoidAilments"):
        make(placeholder(), veil_offer=("UnveiledPrefixAilments1", "UnveiledPrefixAilments2"))


def test_an_offer_without_a_placeholder_is_rejected():
    with pytest.raises(VeilOfferError, match=rf"item on {BELT}: a veil offer needs exactly one veiled placeholder.*has 0"):
        make(veil_offer=OFFER)


def test_an_offer_beside_a_plain_mod_but_no_placeholder_is_rejected():
    with pytest.raises(VeilOfferError, match="has 0"):
        make(roll("ColdResist1"), veil_offer=OFFER)


def test_an_offer_with_two_placeholders_is_rejected():
    with pytest.raises(VeilOfferError, match="has 2"):
        make(placeholder("VeiledPrefix"), placeholder("VeiledSuffix"), veil_offer=("UnveiledPrefixLife1",))


def test_an_offer_beside_other_explicit_mods_is_accepted():
    assert make(placeholder(), roll("ColdResist1"), veil_offer=OFFER).veil_offer == OFFER


@pytest.mark.parametrize("bad", [["UnveiledPrefixLife1"], ("UnveiledPrefixLife1", 3), "UnveiledPrefixLife1"])
def test_an_offer_must_be_a_tuple_of_strings(bad):
    with pytest.raises(VeilOfferError, match="veil_offer must be a tuple of mod ids"):
        make(placeholder(), veil_offer=bad)


def test_changed_keeps_sets_and_clears_the_offer():
    built = make(placeholder(), veil_offer=OFFER)

    assert built.changed(EXTENDED, corrupted=True).veil_offer == OFFER
    assert built.changed(EXTENDED, veil_offer=()).veil_offer == ()


def test_the_offer_vanishes_with_its_placeholder_on_boots():
    built = make(placeholder(), base_id=BOOTS, veil_offer=OFFER)

    assert built.remove_mod(EXTENDED, "VeiledPrefix").veil_offer == ()
    assert built.changed(EXTENDED, mods=()).veil_offer == ()
    assert built.changed(EXTENDED, mods=built.fractured_mods).veil_offer == ()


def test_the_offer_stays_when_other_mods_change_and_the_placeholder_stays():
    built = make(placeholder(), base_id=BOOTS, veil_offer=OFFER)
    life = ExplicitMod("IncreasedLife1", 1, (10,))

    assert built.add_mod(EXTENDED, life).veil_offer == OFFER
    assert built.add_mod(EXTENDED, life).remove_mod(EXTENDED, "IncreasedLife1").veil_offer == OFFER
    assert built.changed(EXTENDED, mods=(*built.mods, life)).veil_offer == OFFER


def test_an_explicit_offer_given_with_mods_is_still_checked():
    built = make(placeholder(), veil_offer=OFFER)

    with pytest.raises(VeilOfferError, match="has 0"):
        built.changed(EXTENDED, mods=(), veil_offer=OFFER)


def test_a_build_with_an_offer_and_no_placeholder_is_still_rejected():
    with pytest.raises(VeilOfferError, match="has 0"):
        make(veil_offer=OFFER)


def test_an_offered_mod_with_spawn_weight_zero_on_the_base_is_rejected():
    with pytest.raises(VeilOfferError, match="UnveiledPrefixZeroWeight1 has spawn weight 0"):
        make(placeholder(), veil_offer=("UnveiledPrefixLife1", "UnveiledPrefixZeroWeight1"))


def test_an_offered_mod_whose_tag_the_base_lacks_is_rejected():
    only_boots = dataclasses.replace(
        EXTENDED.mods["UnveiledPrefixLife1"], spawn_weights=(Weight("boots", 1500), Weight("default", 0))
    )
    data = dataclasses.replace(EXTENDED, mods={**EXTENDED.mods, only_boots.id: only_boots})

    Item.build(data, base_id=BOOTS, rarity=Rarity.RARE, item_level=84, mods=(placeholder(),), veil_offer=(only_boots.id,))
    with pytest.raises(VeilOfferError, match="UnveiledPrefixLife1 has spawn weight 0"):
        Item.build(data, base_id=BELT, rarity=Rarity.RARE, item_level=84, mods=(placeholder(),), veil_offer=(only_boots.id,))


# items made before the new fields


def test_an_item_without_the_new_fields_equals_the_same_item_and_hashes_the_same():
    first = make(roll("ColdResist1"), roll("IncreasedEnergyShield1"))
    second = make(roll("IncreasedEnergyShield1"), roll("ColdResist1"))

    assert first == second
    assert hash(first) == hash(second)
    assert first.implicits == () and first.quality is None and first.veil_offer == ()


def test_an_item_with_a_new_field_differs_from_one_without():
    plain = make()

    assert plain != make(quality=INTRINSIC_20)
    assert plain != make(placeholder(), veil_offer=OFFER)
    assert make(placeholder(), veil_offer=OFFER) != make(placeholder())


def test_the_new_errors_are_item_errors():
    assert issubclass(QualityError, ItemError)
    assert issubclass(VeilOfferError, ItemError)


def test_a_scouring_orb_on_an_item_with_an_offer_no_longer_crashes():
    from crafting_system.actions import ScouringOrb

    built = make(placeholder(), ExplicitMod("IncreasedLife1", 1, (10,)), base_id=BOOTS, veil_offer=OFFER)

    results = ScouringOrb().outcomes(EXTENDED, built)

    assert results.retained.veil_offer == () and results.retained.mods == ()
