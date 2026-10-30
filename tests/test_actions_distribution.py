"""The exact distribution of the new mods through a label, and the chance of holding given mods."""

from fractions import Fraction

import pytest
from actions_oracle import chaos_chance
from actions_support import DATA, RESIST, TARGET, amulet, fractured_resist, roll

from crafting_system.actions import ChaosOrb, HarvestReforge

ACTIONS = (ChaosOrb(), HarvestReforge("lightning"))
SIDE = lambda mod: mod.generation_type  # noqa: E731
CONSTANT = lambda mod: "mod"  # noqa: E731
RATIO = {4: Fraction(2, 3), 5: Fraction(1, 4), 6: Fraction(1, 12)}


def mod_counts(outcomes, label=CONSTANT):
    """The distribution of the number of new mods, read through a constant label."""
    counts: dict[int, Fraction] = {}
    for outcome, chance in outcomes.distribution(label).items():
        number = sum(count for _, count in outcome)
        counts[number] = counts.get(number, 0) + chance
    return counts


@pytest.mark.parametrize("action", ACTIONS)
def test_the_probabilities_sum_to_exactly_one(action):
    for item in (amulet(), amulet(fractured_resist())):
        shown = action.outcomes(DATA, item).distribution(SIDE)

        assert sum(shown.values()) == 1


@pytest.mark.parametrize("action", ACTIONS)
def test_a_plain_rare_gets_four_five_or_six_mods_at_8_3_1(action):
    assert mod_counts(action.outcomes(DATA, amulet())) == RATIO


@pytest.mark.parametrize("action", ACTIONS)
def test_a_kept_mod_counts_inside_the_total(action):
    shifted = {total - 1: chance for total, chance in RATIO.items()}

    assert mod_counts(action.outcomes(DATA, amulet(fractured_resist()))) == shifted


def test_the_guaranteed_draw_is_made_even_when_the_kept_mods_reach_the_total():
    four = amulet(
        roll("LightningResist1", fractured=True),
        roll("LifeRegeneration1", fractured=True),
        roll("IncreasedLife1", fractured=True),
        roll("IncreasedEnergyShield1", fractured=True),
    )

    assert mod_counts(ChaosOrb().outcomes(DATA, four)) == {0: Fraction(2, 3), 1: Fraction(1, 4), 2: Fraction(1, 12)}
    # Harvest: the guaranteed mod is drawn at a total of 4 and of 5 as well; only a 6 leaves room for one more.
    shown = HarvestReforge("lightning").outcomes(DATA, four)
    assert mod_counts(shown) == {1: Fraction(11, 12), 2: Fraction(1, 12)}


def test_an_item_level_1_amulet_has_a_tiny_pool_so_a_chaos_orb_stops_early():
    # Only three families can spawn at item level 1, all suffixes (LifeRegeneration, ColdResistance,
    # LightningResistance), and a side holds three: every total of 4 to 6 ends with exactly 3 mods.
    assert mod_counts(ChaosOrb().outcomes(DATA, amulet(item_level=1))) == {3: Fraction(1)}
    # With one of them kept, two are left to draw.
    assert mod_counts(ChaosOrb().outcomes(DATA, amulet(fractured_resist(), item_level=1))) == {2: Fraction(1)}


def test_a_harvest_reforge_at_item_level_1_works_through_its_one_tagged_mod():
    outcomes = HarvestReforge("lightning").outcomes(DATA, amulet(item_level=1))

    assert mod_counts(outcomes) == {3: Fraction(1)}
    assert outcomes.chance_all([RESIST]) == 1


def test_the_label_sees_the_side_of_every_new_mod():
    shown = ChaosOrb().outcomes(DATA, amulet(item_level=1)).distribution(SIDE)

    assert shown == {frozenset({("suffix", 3)}): 1}


def test_a_label_on_the_family_gives_the_oracle_chance_of_drawing_that_family():
    # The gem-level family is a fifth part target: P(family) = 5 * P(target mod).
    outcomes = ChaosOrb().outcomes(DATA, amulet())
    gem_family = lambda mod: mod.families[0] == "GlobalDamageTypeGemLevel"  # noqa: E731

    drawn = sum(c for o, c in outcomes.distribution(gem_family).items() if (True, 1) in o)

    assert drawn == 5 * chaos_chance()


def test_the_chance_of_a_mod_already_kept_is_one():
    outcomes = ChaosOrb().outcomes(DATA, amulet(fractured_resist()))

    assert outcomes.chance_all([RESIST]) == 1


def test_the_chance_of_nothing_is_one():
    assert ChaosOrb().outcomes(DATA, amulet()).chance_all([]) == 1


def test_a_kept_mod_and_a_drawn_mod_are_a_joint_chance():
    outcomes = ChaosOrb().outcomes(DATA, amulet(fractured_resist()))

    assert outcomes.chance_all([RESIST, TARGET]) == outcomes.chance_all([TARGET])


def test_two_mods_of_one_family_have_chance_zero():
    outcomes = ChaosOrb().outcomes(DATA, amulet())

    assert outcomes.chance_all(["LightningResist1", "LightningResist2"]) == 0
    assert outcomes.chance_all([TARGET, "GlobalColdGemLevel1__"]) == 0


def test_a_mod_of_a_kept_family_cannot_be_drawn():
    outcomes = ChaosOrb().outcomes(DATA, amulet(fractured_resist()))

    assert outcomes.chance_all(["LightningResist2"]) == 0


def test_a_mod_that_is_not_in_the_pool_has_chance_zero():
    assert ChaosOrb().outcomes(DATA, amulet(item_level=74)).chance_all([TARGET]) == 0


def test_two_drawn_mods_are_a_joint_chance_not_a_product():
    outcomes = ChaosOrb().outcomes(DATA, amulet())
    both = outcomes.chance_all([TARGET, "LightningResist1"])

    assert 0 < both < outcomes.chance_all([TARGET])
    assert both != outcomes.chance_all([TARGET]) * outcomes.chance_all(["LightningResist1"])


def test_an_unknown_mod_id_is_a_value_error():
    with pytest.raises(ValueError, match="NoSuchMod"):
        ChaosOrb().outcomes(DATA, amulet()).chance_all(["NoSuchMod"])


def test_the_retained_item_holds_only_the_fractured_mods():
    item = amulet(fractured_resist(), roll("IncreasedLife1"))

    retained = ChaosOrb().outcomes(DATA, item).retained

    assert [m.mod_id for m in retained.mods] == [RESIST]
    assert retained.mods[0].fractured
