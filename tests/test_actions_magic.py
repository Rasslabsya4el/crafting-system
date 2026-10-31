"""The exact odds of the magic-item orbs and the Alchemy, against the hand oracle (ticket #64).

The oracle (`magic_oracle.py`) walks every draw order by hand with `Fraction`s; the engine, read
through the family of each new mod, must equal it exactly, with and without a fractured mod. The
fixture amulet at item level 86 (or 80) is the item.
"""

import random
from fractions import Fraction

import pytest
from actions_oracle import chaos_chance
from actions_support import DATA, RESIST, TARGET, amulet, fractured_resist, roll
from magic_oracle import add_one, magic_roll

from crafting_system.actions import (
    AlchemyOrb,
    AlterationOrb,
    AugmentationOrb,
    RegalOrb,
    TransmutationOrb,
    add_one_mod,
)
from crafting_system.items import Rarity

LEVELS = (80, 86)
LIFE, FIRE = "IncreasedLife1", "FireResist1"
BY_FAMILY = lambda mod: mod.families[0]  # noqa: E731


def seen(outcomes) -> dict[frozenset[str], Fraction]:
    """The distribution of the sets of families the new mods belong to (one new mod per family)."""
    result: dict[frozenset[str], Fraction] = {}
    for outcome, chance in outcomes.distribution(BY_FAMILY).items():
        assert all(count == 1 for _, count in outcome)
        key = frozenset(family for family, _ in outcome)
        result[key] = result.get(key, Fraction(0)) + chance
    return result


def magic(*mods, level: int = 86):
    return amulet(*mods, item_level=level, rarity=Rarity.MAGIC)


def normal(level: int = 86):
    return amulet(item_level=level, rarity=Rarity.NORMAL)


@pytest.mark.parametrize("level", LEVELS)
def test_transmutation_matches_the_oracle(level):
    assert seen(TransmutationOrb().outcomes(DATA, normal(level))) == magic_roll(level)


@pytest.mark.parametrize("level", LEVELS)
def test_alteration_matches_the_oracle(level):
    assert seen(AlterationOrb().outcomes(DATA, magic(roll(LIFE), level=level))) == magic_roll(level)


@pytest.mark.parametrize("level", LEVELS)
def test_alteration_with_a_fractured_mod_matches_the_oracle(level):
    item = magic(fractured_resist(), level=level)

    assert seen(AlterationOrb().outcomes(DATA, item)) == magic_roll(level, ("LightningResistance",))


def test_a_fractured_mod_counts_inside_the_total_of_a_magic_item():
    shown = AlterationOrb().outcomes(DATA, magic(fractured_resist())).distribution(BY_FAMILY)

    assert shown[frozenset()] == Fraction(1, 2)  # a total of 1: the fractured mod is the whole item
    assert sum(shown.values()) == 1


def test_alteration_removes_a_mod_that_is_not_fractured_and_keeps_the_fractured_one():
    outcomes = AlterationOrb().outcomes(DATA, magic(fractured_resist(), roll(LIFE)))

    assert [entry.mod_id for entry in outcomes.retained.mods] == [RESIST]


def test_alteration_removes_an_ordinary_crafted_mod():
    item = magic(roll("JunMaster2AllDamage2_", crafted=True))

    assert AlterationOrb().outcomes(DATA, item).retained.mods == ()


def test_the_total_of_a_magic_roll_is_one_or_two_at_one_half_each():
    shown = TransmutationOrb().outcomes(DATA, normal()).distribution(lambda mod: "mod")
    counts = {sum(count for _, count in outcome): chance for outcome, chance in shown.items()}

    assert counts == {1: Fraction(1, 2), 2: Fraction(1, 2)}


@pytest.mark.parametrize("level", LEVELS)
def test_augmentation_on_a_magic_item_with_one_prefix_draws_a_suffix(level):
    shown = seen(AugmentationOrb().outcomes(DATA, magic(roll(LIFE), level=level)))

    assert shown == add_one(level, ("IncreasedLife",))
    assert all(family != "IncreasedLife" for key in shown for family in key)
    assert sum(shown.values()) == 1


@pytest.mark.parametrize("level", LEVELS)
def test_augmentation_on_a_magic_item_with_one_suffix_draws_a_prefix(level):
    assert seen(AugmentationOrb().outcomes(DATA, magic(roll(FIRE), level=level))) == add_one(level, ("FireResistance",))


def test_augmentation_with_a_fractured_suffix_draws_a_prefix():
    item = magic(fractured_resist())

    assert seen(AugmentationOrb().outcomes(DATA, item)) == add_one(86, ("LightningResistance",))


def test_augmentation_on_a_magic_item_without_mods_draws_from_both_sides():
    assert seen(AugmentationOrb().outcomes(DATA, magic())) == add_one(86, ())


@pytest.mark.parametrize("level", LEVELS)
def test_regal_adds_one_mod_to_a_two_mod_item_from_the_rare_pool(level):
    item = magic(roll(LIFE), roll(FIRE), level=level)

    shown = seen(RegalOrb().outcomes(DATA, item))

    assert shown == add_one(level, ("IncreasedLife", "FireResistance"), cap=3)
    assert len(shown) == 12  # the 14 families of the amulet, the two present ones out


def test_regal_makes_the_item_rare_and_keeps_its_mods():
    outcomes = RegalOrb().outcomes(DATA, magic(roll(LIFE), roll(FIRE)))

    assert outcomes.retained.rarity is Rarity.RARE
    assert {entry.mod_id for entry in outcomes.retained.mods} == {LIFE, FIRE}


def test_regal_with_a_fractured_mod_matches_the_oracle():
    item = magic(fractured_resist(), roll(LIFE))

    assert seen(RegalOrb().outcomes(DATA, item)) == add_one(86, ("LightningResistance", "IncreasedLife"), cap=3)


def test_regal_on_a_magic_item_with_one_mod_opens_both_sides():
    assert seen(RegalOrb().outcomes(DATA, magic(roll(LIFE)))) == add_one(86, ("IncreasedLife",), cap=3)


def test_a_family_on_the_item_is_out_of_the_pool_and_never_drawn():
    item = magic(roll(LIFE), roll(FIRE))
    for key in seen(RegalOrb().outcomes(DATA, item)):
        assert not key & {"IncreasedLife", "FireResistance"}


def test_the_chance_of_a_mod_is_the_family_share_of_its_weight():
    # Regal on Life + Fire resistance at level 86: the target is one of five mods of 200 in a family of 1000.
    pool = add_one(86, ("IncreasedLife", "FireResistance"), cap=3)
    outcomes = RegalOrb().outcomes(DATA, magic(roll(LIFE), roll(FIRE)))

    assert outcomes.chance_all([TARGET]) == pool[frozenset({"GlobalDamageTypeGemLevel"})] * Fraction(1, 5)
    assert outcomes.chance_all([TARGET, LIFE, FIRE]) == outcomes.chance_all([TARGET])


def test_chance_all_is_zero_for_two_mods_of_one_family():
    outcomes = AlterationOrb().outcomes(DATA, magic())

    assert outcomes.chance_all([RESIST, "LightningResist2"]) == 0


@pytest.mark.parametrize("level", (80, 84, 86))
def test_alchemy_on_a_normal_amulet_gives_the_chaos_odds_of_a_rare_without_mods(level):
    outcomes = AlchemyOrb().outcomes(DATA, normal(level))

    assert outcomes.chance_all([TARGET]) == chaos_chance(level)
    assert outcomes.retained.rarity is Rarity.RARE


def test_alchemy_gets_four_five_or_six_mods_at_8_3_1():
    shown = AlchemyOrb().outcomes(DATA, normal()).distribution(lambda mod: "mod")
    counts = {sum(count for _, count in outcome): chance for outcome, chance in shown.items()}

    assert counts == {4: Fraction(2, 3), 5: Fraction(1, 4), 6: Fraction(1, 12)}


def test_add_one_mod_is_the_seam_the_exalted_orb_will_use():
    rare = amulet(roll(LIFE), fractured_resist(), roll("LifeRegeneration1"))

    shown = seen(add_one_mod(DATA, rare, "an Exalted Orb"))

    assert shown == add_one(86, ("IncreasedLife", "LightningResistance", "LifeRegeneration"), cap=3)
    assert add_one_mod(DATA, rare, "an Exalted Orb").retained is rare


@pytest.mark.parametrize(
    ("action", "item"),
    [
        (TransmutationOrb(), normal()),
        (AlterationOrb(), magic(roll(LIFE))),
        (AugmentationOrb(), magic(roll(LIFE))),
        (RegalOrb(), magic(roll(LIFE), roll(FIRE))),
        (AlchemyOrb(), normal()),
        (AlterationOrb(), magic(fractured_resist())),
    ],
    ids=["transmutation", "alteration", "augmentation", "regal", "alchemy", "alteration-fractured"],
)
def test_the_sampler_yields_valid_items_that_follow_the_exact_total(action, item):
    outcomes = action.outcomes(DATA, item)
    rng = random.Random(7)
    for _ in range(200):
        finished = outcomes.sample(rng)
        finished.validate(DATA)
        assert {entry.mod_id for entry in outcomes.retained.mods} <= {entry.mod_id for entry in finished.mods}
        assert finished.rarity is outcomes.retained.rarity


def test_the_sampler_agrees_with_the_exact_chance_of_a_transmutation():
    outcomes = TransmutationOrb().outcomes(DATA, normal())
    chance = float(outcomes.chance_all(["IncreasedLife1"]))
    rng, runs, hits = random.Random(11), 20000, 0
    for _ in range(runs):
        hits += any(entry.mod_id == "IncreasedLife1" for entry in outcomes.sample(rng).mods)

    assert abs(hits / runs - chance) < 5 * (chance * (1 - chance) / runs) ** 0.5


def test_a_dry_pool_leaves_fewer_mods_on_a_magic_item():
    # At item level 1 the amulet has suffixes only: a total of 2 stops at one mod, a suffix.
    shown = TransmutationOrb().outcomes(DATA, normal(1)).distribution(lambda mod: mod.generation_type)

    assert shown == {frozenset({("suffix", 1)}): Fraction(1)}


def test_an_alteration_with_nothing_to_draw_leaves_the_item_as_a_chaos_orb_does():
    item = magic(fractured_resist(), level=1)  # one fractured suffix, no prefix in the pool at level 1

    outcomes = AlterationOrb().outcomes(DATA, item)

    assert outcomes.distribution(BY_FAMILY) == {frozenset(): Fraction(1)}
    assert outcomes.sample(random.Random(1)).mods == item.mods
