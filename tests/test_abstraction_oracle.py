"""The brute-force oracle of the `abstraction` tests checked against `actions`, without `abstraction`.

If the oracle were wrong, every kernel test built on it would be wrong in the same direction, so it
is checked here against what `actions` says: the chance of holding a mod (`Outcomes.chance_all`), the
whole distribution of the new mods (`Outcomes.distribution`), the 8:3:1 totals and the side limits.
The comparison helper that the kernel tests use is checked too: it must catch a dropped or a
double-counted probability.
"""

from collections import Counter
from fractions import Fraction

import pytest
from abstraction_oracle import (
    CAP,
    assert_same_distribution,
    compressed_distribution,
    differences,
    finished_items,
    guaranteed_tag,
    hold_chance,
)
from abstraction_pool import (
    COLD_RESIST,
    CRAFTED,
    DAMAGE_1,
    FIRE_GEM,
    FIRE_RESIST,
    GEM,
    LIFE_1,
    MANA_1,
    POOL_IDS,
    RESIST_1,
    RESIST_2,
    SMALL,
    fractured_item,
    roll,
    small_item,
)

from crafting_system.actions import ChaosOrb, HarvestReforge

ACTIONS = (ChaosOrb(), HarvestReforge("lightning"))
STARTS = {
    "plain": (),
    "resist": (RESIST_2,),
    "other_gem": (FIRE_GEM,),
    "two": (RESIST_2, LIFE_1),
    "three_suffixes": (COLD_RESIST, FIRE_RESIST, MANA_1),
}
SPAWNABLE = sorted(POOL_IDS - {CRAFTED})
RATIO = {4: Fraction(2, 3), 5: Fraction(1, 4), 6: Fraction(1, 12)}


def finished(start, action, level=84):
    return finished_items(SMALL, fractured_item(*start, level=level), guaranteed_tag(action))


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("start", STARTS.values(), ids=STARTS)
def test_the_probabilities_of_the_finished_items_sum_to_exactly_one(start, action):
    assert sum(chance for _, chance in finished(start, action)) == 1


@pytest.mark.parametrize("action", ACTIONS)
def test_the_enumeration_is_small_enough_to_run_in_every_test(action):
    assert len(finished((), action)) < 10_000


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("start", STARTS.values(), ids=STARTS)
def test_the_chance_of_holding_a_mod_equals_chance_all_of_the_engine(start, action):
    items = finished(start, action)
    outcomes = action.outcomes(SMALL, fractured_item(*start))

    for mod_id in SPAWNABLE:
        assert hold_chance(items, {mod_id}) == outcomes.chance_all([mod_id]), mod_id


@pytest.mark.parametrize("action", ACTIONS)
def test_the_chance_of_holding_two_mods_equals_chance_all_of_the_engine(action):
    items = finished((RESIST_2,), action)
    outcomes = action.outcomes(SMALL, fractured_item(RESIST_2))
    pairs = [(GEM, DAMAGE_1), (GEM, LIFE_1), (DAMAGE_1, MANA_1), (GEM, RESIST_2), (GEM, RESIST_1), (COLD_RESIST, FIRE_RESIST)]

    for pair in pairs:
        assert hold_chance(items, set(pair)) == outcomes.chance_all(pair), pair


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("start", STARTS.values(), ids=STARTS)
def test_the_distribution_of_the_new_mods_equals_the_engine_with_a_label_per_mod(start, action):
    retained = fractured_item(*start)
    kept = {entry.mod_id for entry in retained.mods}
    own = compressed_distribution(
        finished(start, action),
        lambda item: frozenset((entry.mod_id, 1) for entry in item.mods if entry.mod_id not in kept),
    )

    engine = action.outcomes(SMALL, retained).distribution(lambda mod: mod.id)

    assert_same_distribution(own, dict(engine))


@pytest.mark.parametrize("action", ACTIONS)
def test_a_plain_rare_gets_four_five_or_six_mods_at_8_3_1(action):
    counts = Counter()
    for item, chance in finished((), action):
        counts[len(item.mods)] += chance

    assert dict(counts) == RATIO


@pytest.mark.parametrize("action", ACTIONS)
def test_a_kept_mod_counts_inside_the_total(action):
    counts = Counter()
    for item, chance in finished((RESIST_2,), action):
        counts[len(item.mods)] += chance

    assert dict(counts) == RATIO


def test_a_chaos_orb_keeps_every_fractured_mod_and_never_fills_a_side_over_three():
    for start in STARTS.values():
        for item, _ in finished(start, ChaosOrb()):
            ids = {entry.mod_id for entry in item.mods}
            assert set(start) <= ids
            assert len(item.prefixes(SMALL)) <= CAP and len(item.suffixes(SMALL)) <= CAP


def test_three_fractured_suffixes_close_that_side_for_every_draw():
    for item, _ in finished(STARTS["three_suffixes"], ChaosOrb()):
        assert len(item.suffixes(SMALL)) == 3
        assert 4 <= len(item.mods) <= 6


def test_kept_mods_that_reach_the_total_leave_nothing_to_draw_for_a_chaos_orb():
    six = (LIFE_1, DAMAGE_1, FIRE_GEM, COLD_RESIST, FIRE_RESIST, MANA_1)

    [(item, chance)] = finished(six, ChaosOrb())

    assert chance == 1 and len(item.mods) == 6


def test_a_dry_pool_stops_the_reroll_with_fewer_mods():
    # At item level 12 only five families can spawn: life, lightning damage and three resistances.
    # A total of 5 and a total of 6 both end with all five of them.
    counts = Counter()
    for item, chance in finished((), ChaosOrb(), level=12):
        counts[len(item.mods)] += chance

    assert dict(counts) == {4: Fraction(2, 3), 5: Fraction(1, 3)}


def test_a_reforge_draws_a_tagged_mod_first_and_it_counts_inside_the_total():
    tagged = {GEM, "AddedLightningDamage1", "AddedLightningDamage2", "LightningResist1", "LightningResist2", "LightningResist3"}
    for start in ((), (RESIST_2,), (COLD_RESIST,)):
        for item, _ in finished(start, HarvestReforge("lightning")):
            new = {entry.mod_id for entry in item.mods} - set(start)
            assert new & tagged
            assert 4 <= len(item.mods) <= 6


def test_a_reforge_is_refused_by_the_oracle_when_nothing_tagged_can_be_drawn():
    blocked = fractured_item(GEM, DAMAGE_1, RESIST_1)

    with pytest.raises(ValueError, match="no lightning mod"):
        finished_items(SMALL, blocked, "lightning")
    assert finished_items(SMALL, blocked, None)


def test_junk_that_is_not_fractured_is_erased_by_the_reroll():
    with_junk = small_item(roll(RESIST_2, fractured=True), roll(LIFE_1), roll(GEM))

    assert finished_items(SMALL, with_junk, None) == finished_items(SMALL, fractured_item(RESIST_2), None)


def test_the_comparison_accepts_an_equal_distribution():
    shown = {"a": Fraction(1, 3), "b": Fraction(2, 3)}

    assert differences(dict(shown), shown) == []


@pytest.mark.parametrize(
    "broken",
    [
        {"a": Fraction(1, 3)},
        {"a": Fraction(1, 3), "b": Fraction(2, 3), "c": Fraction(1, 5)},
        {"a": Fraction(2, 3), "b": Fraction(2, 3)},
        {"a": Fraction(1, 3), "b": Fraction(1, 3), "c": Fraction(1, 3)},
        {"a": Fraction(1, 2), "b": Fraction(1, 2)},
        {"a": Fraction(1, 3), "b": Fraction(2, 3) - Fraction(1, 10**9)},
        {"a": Fraction(1, 3), "b": Fraction(2, 3), "c": Fraction(0)},
        {"a": 1 / 3, "b": 2 / 3},
        {"a": Fraction(1)},
    ],
    ids=["dropped", "extra", "double-counted", "split", "shifted", "off-by-a-billionth", "zero entry", "floats", "merged"],
)
def test_the_comparison_catches_a_dropped_or_double_counted_probability(broken):
    shown = {"a": Fraction(1, 3), "b": Fraction(2, 3)}

    assert differences(broken, shown)
    with pytest.raises(AssertionError):
        assert_same_distribution(broken, shown)


def test_the_comparison_states_that_the_sum_is_not_one_even_when_the_expected_side_is_wrong_too():
    wrong = {"a": Fraction(1, 3), "b": Fraction(1, 3)}

    assert any("not 1" in line for line in differences(wrong, wrong))
