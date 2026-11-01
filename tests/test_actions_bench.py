"""The crafting bench as exact actions on the fixture belt: a craft adds one fixed mod, Remove Crafted Mods removes all (#56)."""

import dataclasses
import random
from fractions import Fraction

import pytest
from items_support import DATA, item, roll
from repoe_support import no_network  # noqa: F401

from crafting_system.actions import (
    ActionError,
    BenchCraft,
    BenchOutcomes,
    CurrencyCost,
    NotApplicableError,
    OutOfScopeError,
    RemoveCraftedMods,
    bench_crafts,
)
from crafting_system.items import Item, Rarity

BELT = "Metadata/Items/Belts/Belt3"
AMULET = "Metadata/Items/Amulets/Amulet1"
DAMAGE_1, DAMAGE_2 = "JunMaster2AllDamage2_", "JunMaster2AllDamage3"  # levels 72 and 81, prefixes, Ring and Belt only
HYBRID = "JunMaster2ArmourAndEnergyShield1"  # level 60, prefix, families IncreasedPhysicalDamageReductionRating + IncreasedEnergyShield
ELEMENTAL = "EinharMasterWeaponElementalDamage1_"  # level 30, prefix
PREFIXES_LOCK = "StrMasterItemGenerationCannotChangePrefixes"  # suffix metamod
MULTIMOD = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"  # suffix metamod
LIFE, SHIELD, LIGHTNING_DAMAGE = "IncreasedLife1", "IncreasedEnergyShield1", "AddedLightningDamage1"
RESIST = "LightningResist1"


def belt(*mods, rarity: Rarity = Rarity.RARE, item_level: int = 86, **fields) -> Item:
    return item(*mods, base_id=BELT, rarity=rarity, item_level=item_level, **fields)


def crafted(mod_id: str):
    return roll(mod_id, crafted=True)


def ids(finished: Item) -> set[str]:
    return {entry.mod_id for entry in finished.mods}


# --- the craft adds its mod ---------------------------------------------------------------------


def test_a_craft_adds_its_crafted_mod_with_certainty():
    outcomes = BenchCraft(DAMAGE_1).outcomes(DATA, belt(roll(LIFE), roll(RESIST)))

    assert isinstance(outcomes, BenchOutcomes)
    assert outcomes.chance_all([DAMAGE_1]) == 1
    assert outcomes.chance_all([DAMAGE_1, LIFE, RESIST]) == 1
    assert outcomes.chance_all([DAMAGE_2]) == 0
    assert outcomes.chance_all([DAMAGE_1, "FireResist1"]) == 0
    assert outcomes.chance_all([]) == 1


def test_chance_all_of_two_mods_of_one_family_is_zero_and_an_unknown_id_is_an_error():
    outcomes = BenchCraft(DAMAGE_1).outcomes(DATA, belt(roll(LIFE)))

    assert outcomes.chance_all([DAMAGE_1, DAMAGE_2]) == 0
    with pytest.raises(ValueError, match="NoSuchMod is not in the game data"):
        outcomes.chance_all(["NoSuchMod"])


def test_the_distribution_has_the_one_new_mod_seen_through_the_label_with_probability_one():
    outcomes = BenchCraft(DAMAGE_1).outcomes(DATA, belt(roll(LIFE)))

    assert dict(outcomes.distribution(lambda mod: mod.generation_type)) == {frozenset({("prefix", 1)}): Fraction(1)}
    assert dict(outcomes.distribution(lambda mod: mod.id)) == {frozenset({(DAMAGE_1, 1)}): Fraction(1)}


def test_the_sample_is_the_item_with_the_crafted_mod_rolled_within_its_range_and_flagged_crafted():
    start = belt(roll(LIFE), roll(RESIST))
    outcomes = BenchCraft(DAMAGE_1).outcomes(DATA, start)

    seen = set()
    for seed in range(60):
        finished = outcomes.sample(random.Random(seed))
        finished.validate(DATA)
        assert ids(finished) == ids(start) | {DAMAGE_1}
        (mod,) = finished.crafted_mods
        assert mod.mod_id == DAMAGE_1 and not mod.fractured
        assert 12 <= mod.values[0] <= 14
        seen.add(mod.values[0])
        assert [entry for entry in finished.mods if not entry.crafted] == list(start.mods)
    assert seen == {12, 13, 14}


def test_a_metamod_is_crafted_like_any_other_option():
    outcomes = BenchCraft(PREFIXES_LOCK).outcomes(DATA, belt(roll(LIFE), roll(RESIST)))

    finished = outcomes.sample(random.Random(0))
    assert PREFIXES_LOCK in ids(finished) and len(finished.crafted_mods) == 1
    assert outcomes.distribution(lambda mod: mod.generation_type) == {frozenset({("suffix", 1)}): 1}


def test_a_craft_works_on_a_magic_item_with_a_free_side():
    magic = belt(roll(LIFE), rarity=Rarity.MAGIC)

    assert BenchCraft(PREFIXES_LOCK).outcomes(DATA, magic).chance_all([LIFE, PREFIXES_LOCK]) == 1


def test_a_craft_does_not_look_at_the_item_level():
    assert BenchCraft(DAMAGE_1).outcomes(DATA, belt(roll(LIFE), item_level=1)).chance_all([DAMAGE_1]) == 1


def test_a_craft_ignores_influence():
    from crafting_system.items import Influence

    start = dataclasses.replace(belt(roll(LIFE)), influences=frozenset({Influence.SHAPER}))

    assert BenchCraft(DAMAGE_1).outcomes(DATA, start).chance_all([DAMAGE_1]) == 1


# --- the refusals, each one --------------------------------------------------------------------


def test_a_craft_for_another_item_class_is_refused_by_the_game():
    amulet = item(roll(LIFE), base_id=AMULET, item_level=86)

    with pytest.raises(NotApplicableError, match="does not offer the craft JunMaster2AllDamage2_ for the item class Amulet"):
        BenchCraft(DAMAGE_1).outcomes(DATA, amulet)


def test_a_corrupted_item_is_refused_by_the_game():
    with pytest.raises(NotApplicableError, match="corrupted.*bench craft"):
        BenchCraft(DAMAGE_1).outcomes(DATA, dataclasses.replace(belt(roll(LIFE)), corrupted=True))


def test_a_family_already_on_the_item_is_refused_by_the_game():
    with pytest.raises(NotApplicableError, match="shares a family"):
        BenchCraft(DAMAGE_2).outcomes(DATA, belt(roll(LIFE), crafted(DAMAGE_1)))


def test_one_family_of_a_hybrid_craft_is_enough_to_clash():
    with pytest.raises(NotApplicableError, match=f"holds {SHIELD}, which shares a family"):
        BenchCraft(HYBRID).outcomes(DATA, belt(roll(SHIELD), roll(RESIST)))


def test_a_full_prefix_side_is_refused_by_the_game_and_a_full_suffix_side_too():
    with pytest.raises(NotApplicableError, match="no free prefix slot"):
        BenchCraft(DAMAGE_1).outcomes(DATA, belt(roll(LIFE), roll(SHIELD), roll(LIGHTNING_DAMAGE)))
    with pytest.raises(NotApplicableError, match="no free suffix slot"):
        BenchCraft(PREFIXES_LOCK).outcomes(
            DATA, belt(roll(LIFE), roll(RESIST), roll("FireResist1"), roll("ColdResist1"))
        )


def test_a_magic_item_takes_one_mod_per_side():
    with pytest.raises(NotApplicableError, match="no free prefix slot"):
        BenchCraft(DAMAGE_1).outcomes(DATA, belt(roll(LIFE), rarity=Rarity.MAGIC))


def test_an_item_that_holds_a_crafted_mod_is_refused_by_the_game_even_with_a_free_slot():
    start = belt(roll(LIFE), crafted(PREFIXES_LOCK))

    with pytest.raises(NotApplicableError, match="holds 1 crafted mod, which is the limit"):
        BenchCraft(DAMAGE_1).outcomes(DATA, start)


def test_a_metamod_counts_toward_the_limit_and_a_craft_after_it_is_refused():
    with pytest.raises(NotApplicableError, match="limit"):
        BenchCraft(ELEMENTAL).outcomes(DATA, belt(roll(LIFE), crafted(PREFIXES_LOCK)))


def test_a_normal_item_is_out_of_scope_and_not_a_game_refusal():
    with pytest.raises(OutOfScopeError, match="normal"):
        BenchCraft(DAMAGE_1).outcomes(DATA, belt(rarity=Rarity.NORMAL))


def test_an_item_holding_the_multimod_takes_a_craft_beside_it():
    start = belt(roll(RESIST), crafted(MULTIMOD))

    assert BenchCraft(DAMAGE_1).outcomes(DATA, start).chance_all([DAMAGE_1, MULTIMOD]) == 1


def test_an_item_with_no_mod_is_out_of_scope_for_a_craft():
    with pytest.raises(OutOfScopeError, match="holds no mod"):
        BenchCraft(DAMAGE_1).outcomes(DATA, belt(rarity=Rarity.MAGIC))
    with pytest.raises(OutOfScopeError, match="holds no mod"):
        BenchCraft(DAMAGE_1).outcomes(DATA, belt(rarity=Rarity.RARE))


def test_an_item_that_fails_validation_raises_its_item_error():
    from crafting_system.items import ExplicitMod, UnknownBaseError, UnknownModError

    unknown_mod = Item(base_id=BELT, item_level=86, rarity=Rarity.RARE, mods=(ExplicitMod("Nope", 1, (1,)),))
    with pytest.raises(UnknownModError):
        BenchCraft(DAMAGE_1).outcomes(DATA, unknown_mod)
    with pytest.raises(UnknownModError):
        RemoveCraftedMods().outcomes(DATA, unknown_mod)
    unknown_base = Item(base_id="Nope", item_level=86, rarity=Rarity.RARE)
    with pytest.raises(UnknownBaseError):
        BenchCraft(DAMAGE_1).outcomes(DATA, unknown_base)


def test_a_bench_option_that_names_a_mod_missing_from_the_data_is_a_value_error():
    mods = {key: mod for key, mod in DATA.mods.items() if key != DAMAGE_1}

    with pytest.raises(ValueError, match="names a mod that is not in the game data"):
        BenchCraft(DAMAGE_1).outcomes(dataclasses.replace(DATA, mods=mods), belt(roll(LIFE)))


def test_a_game_refusal_comes_before_an_out_of_scope_one():
    corrupted_normal = dataclasses.replace(belt(rarity=Rarity.NORMAL), corrupted=True)

    with pytest.raises(NotApplicableError):
        BenchCraft(DAMAGE_1).outcomes(DATA, corrupted_normal)
    with pytest.raises(NotApplicableError, match="does not offer"):
        BenchCraft(DAMAGE_1).outcomes(DATA, item(base_id=AMULET, rarity=Rarity.NORMAL))


def test_an_unknown_craft_is_a_value_error_and_not_an_action_error():
    with pytest.raises(ValueError, match="no option that adds the mod LightningResist1") as caught:
        BenchCraft(RESIST).outcomes(DATA, belt(roll(LIFE)))
    assert not isinstance(caught.value, ActionError)
    with pytest.raises(ValueError, match="NoSuchMod"):
        BenchCraft("NoSuchMod").cost(DATA)


# --- Remove Crafted Mods -----------------------------------------------------------------------


def test_remove_crafted_mods_removes_the_crafted_mod_and_keeps_the_rest():
    start = belt(roll(LIFE), roll(RESIST), crafted(DAMAGE_1))

    outcomes = RemoveCraftedMods().outcomes(DATA, start)

    finished = outcomes.sample(random.Random(0))
    assert ids(finished) == {LIFE, RESIST} and not finished.crafted_mods
    assert outcomes.chance_all([LIFE, RESIST]) == 1
    assert outcomes.chance_all([DAMAGE_1]) == 0
    assert dict(outcomes.distribution(lambda mod: mod.id)) == {frozenset(): Fraction(1)}


def test_remove_crafted_mods_removes_every_crafted_mod_metamods_included():
    start = belt(roll(LIFE), crafted(MULTIMOD), crafted(PREFIXES_LOCK), crafted(DAMAGE_1))

    finished = RemoveCraftedMods().outcomes(DATA, start).sample(random.Random(0))

    assert ids(finished) == {LIFE}
    assert not finished.metamods(DATA)


def test_remove_crafted_mods_keeps_fractured_mods():
    start = belt(roll(LIFE, fractured=True), roll(RESIST), crafted(DAMAGE_1))

    finished = RemoveCraftedMods().outcomes(DATA, start).sample(random.Random(0))

    assert [(entry.mod_id, entry.fractured) for entry in finished.mods] == [(LIFE, True), (RESIST, False)]


def test_remove_crafted_mods_on_a_rare_item_may_leave_it_with_fewer_than_four_mods():
    start = belt(roll(LIFE), roll(RESIST), roll("FireResist1"), crafted(DAMAGE_1))

    finished = RemoveCraftedMods().outcomes(DATA, start).sample(random.Random(0))

    assert finished.rarity is Rarity.RARE and len(finished.mods) == 3


def test_remove_crafted_mods_on_a_magic_item_with_another_mod_leaves_it_magic():
    start = belt(roll(LIFE), crafted(PREFIXES_LOCK), rarity=Rarity.MAGIC)

    finished = RemoveCraftedMods().outcomes(DATA, start).sample(random.Random(0))

    assert finished.rarity is Rarity.MAGIC and ids(finished) == {LIFE}


def test_remove_crafted_mods_refuses_an_item_without_a_crafted_mod():
    with pytest.raises(NotApplicableError, match="no crafted mod"):
        RemoveCraftedMods().outcomes(DATA, belt(roll(LIFE)))


def test_remove_crafted_mods_refuses_a_corrupted_item():
    with pytest.raises(NotApplicableError, match="corrupted.*Remove Crafted Mods"):
        RemoveCraftedMods().outcomes(DATA, dataclasses.replace(belt(roll(LIFE), crafted(DAMAGE_1)), corrupted=True))


def test_remove_crafted_mods_refuses_an_item_class_the_bench_does_not_offer_it_for():
    options = tuple(
        dataclasses.replace(option, item_classes=("Boots",)) if option.actions.remove_crafted_mods else option
        for option in DATA.bench_options
    )
    data = dataclasses.replace(DATA, bench_options=options)

    with pytest.raises(NotApplicableError, match="does not offer Remove Crafted Mods for the item class Belt"):
        RemoveCraftedMods().outcomes(data, belt(roll(LIFE), crafted(DAMAGE_1)))


@pytest.mark.parametrize("rarity", [Rarity.MAGIC, Rarity.RARE])
def test_remove_crafted_mods_on_an_item_left_without_a_mod_is_out_of_scope(rarity):
    with pytest.raises(OutOfScopeError, match=f"{rarity}.*only crafted mods"):
        RemoveCraftedMods().outcomes(DATA, belt(crafted(PREFIXES_LOCK), rarity=rarity))


# --- costs and the list of crafts -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (BenchCraft(DAMAGE_1), (CurrencyCost("Chaos Orb", 4),)),
        (BenchCraft(DAMAGE_2), (CurrencyCost("Exalted Orb", 4),)),
        (BenchCraft(HYBRID), (CurrencyCost("Orb of Alteration", 8),)),
        (BenchCraft(PREFIXES_LOCK), (CurrencyCost("Divine Orb", 2),)),
        (RemoveCraftedMods(), (CurrencyCost("Orb of Scouring", 1),)),
    ],
)
def test_the_cost_is_the_options_price_as_currency_names_and_counts(action, expected):
    data = _with_currency_names(DATA)

    assert action.cost(data) == expected


def test_a_cost_currency_missing_from_the_base_items_is_a_value_error():
    with pytest.raises(ValueError, match="CurrencyRerollRare, which is not a base item"):
        BenchCraft(DAMAGE_1).cost(DATA)


def test_bench_crafts_lists_one_craft_per_option_that_adds_a_mod_in_data_order():
    crafts = bench_crafts(DATA)

    assert [craft.mod_id for craft in crafts] == [
        option.actions.add_explicit_mod for option in DATA.bench_options if option.actions.add_explicit_mod
    ]
    assert BenchCraft(DAMAGE_1) in crafts and BenchCraft(PREFIXES_LOCK) in crafts
    assert all(craft.option(DATA).actions.add_explicit_mod == craft.mod_id for craft in crafts)


def _with_currency_names(data):
    """The fixture data with the five currency base items the costs above name (the fixture has none)."""
    template = next(iter(data.base_items.values()))
    names = {
        "CurrencyRerollRare": "Chaos Orb",
        "CurrencyAddModToRare": "Exalted Orb",
        "CurrencyRerollMagic": "Orb of Alteration",
        "CurrencyModValues": "Divine Orb",
        "CurrencyConvertToNormal": "Orb of Scouring",
    }
    extra = {
        f"Metadata/Items/Currency/{key}": dataclasses.replace(
            template, id=f"Metadata/Items/Currency/{key}", name=name, item_class="StackableCurrency"
        )
        for key, name in names.items()
    }
    return dataclasses.replace(data, base_items={**data.base_items, **extra})
