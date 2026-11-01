"""The Sanctified Fossil's lucky values: every value a resonator rolls is rolled twice and the better kept (ticket #71).

The fossil's claim is `fossils.sanctified_values_lucky`. "Better" is the value nearer the stat's `max`. The exact
mean and variance of the better of two uniform rolls over low..high (n values) come from P(max <= k) = (k / n)^2,
counted from the bottom; a sample must lie within five standard errors of it, and a fair roll must not.
"""

import dataclasses
import math
import random
from fractions import Fraction

from actions_support import DATA, amulet

from crafting_system.actions import ApplyFossils, ChaosOrb, Outcomes
from crafting_system.actions.rolls import roll_value
from crafting_system.data import Fossil, StatRange
from crafting_system.items import ExplicitMod

LIFE = "IncreasedLife1"  # 10 to 24
SIGMAS = 5.0


def values_of(result, mod_id: str) -> tuple[int, ...]:
    return next(entry.values for entry in result.mods if entry.mod_id == mod_id)


SANCTIFIED_ID = "Metadata/Items/Currency/CurrencyDelveCraftingLuckyModRolls"
FRACTURED_ID = "Metadata/Items/Currency/CurrencyDelveCraftingFractured"


def _fossil(fossil_id: str, name: str, lucky: bool = False) -> Fossil:
    return Fossil(fossil_id, name, (), (), (), (), (), (), False, lucky, False, False, 0)


LUCKY_DATA = dataclasses.replace(
    DATA,
    fossils={
        **DATA.fossils,
        SANCTIFIED_ID: _fossil(SANCTIFIED_ID, "Sanctified Fossil", lucky=True),
        FRACTURED_ID: _fossil(FRACTURED_ID, "Fractured Fossil"),
    },
)


def _better_of_two(low: int, high: int, nearer_high: bool = True) -> tuple[Fraction, Fraction]:
    """The exact mean and variance of the better of two uniform rolls over low..high (the larger when `nearer_high`)."""
    n = high - low + 1
    chances = {}
    for number, value in enumerate(range(low, high + 1), start=1):
        below = Fraction(number, n) ** 2 - Fraction(number - 1, n) ** 2  # P(max = value)
        chances[value if nearer_high else low + high - value] = below
    mean = sum(value * chance for value, chance in chances.items())
    return mean, sum((value - mean) ** 2 * chance for value, chance in chances.items())


def _z_of_sums(results, lucky: bool) -> float:
    """How many standard errors the values of the new mods lie from the mean of a fair roll (lucky false) or a lucky one."""
    total, count = 0.0, 0
    for result in results:
        for entry in result.mods:
            for value, stat in zip(entry.values, LUCKY_DATA.mods[entry.mod_id].stats, strict=True):
                low, high = min(stat.min, stat.max), max(stat.min, stat.max)
                if low == high:
                    continue
                if lucky:
                    mean, variance = _better_of_two(low, high)
                else:
                    mean, variance = Fraction(low + high, 2), Fraction((high - low + 1) ** 2 - 1, 12)
                total += (value - float(mean)) / math.sqrt(float(variance))
                count += 1
    return total / math.sqrt(count)


def test_the_better_of_two_rolls_of_1_to_3_has_the_chances_1_3_5_ninths():
    # P(max = 1, 2, 3) = 1/9, 3/9, 5/9, so the mean is (1 + 6 + 15) / 9 = 22/9, against 2 for one roll
    mean, variance = _better_of_two(1, 3)

    assert mean == Fraction(22, 9)
    assert variance == Fraction(1, 9) * Fraction(13, 9) ** 2 + Fraction(3, 9) * Fraction(4, 9) ** 2 + Fraction(5, 9) * Fraction(5, 9) ** 2


def test_a_sanctified_resonator_marks_every_part_of_its_result_lucky_and_others_do_not():
    sanctified = ApplyFossils(("Sanctified Fossil",)).outcomes(LUCKY_DATA, amulet())
    fractured = ApplyFossils(("Sanctified Fossil", "Fractured Fossil")).outcomes(LUCKY_DATA, amulet())
    plain = ApplyFossils(("Fractured Fossil",)).outcomes(LUCKY_DATA, amulet())

    assert sanctified.components and all(part.rolls_lucky for _, part in sanctified.components)
    assert fractured.fractures and all(part.rolls_lucky for _, part in fractured.components)
    assert not any(part.rolls_lucky for _, part in plain.components)
    assert not any(part.rolls_lucky for _, part in ChaosOrb().outcomes(DATA, amulet()).components)


def test_the_sanctified_fossil_is_sampled_with_lucky_values():
    outcomes = ApplyFossils(("Sanctified Fossil",)).outcomes(LUCKY_DATA, amulet())
    rng = random.Random(61)
    results = [outcomes.sample(rng) for _ in range(500)]

    assert abs(_z_of_sums(results, lucky=True)) <= SIGMAS  # the mean is that of the better of two
    assert _z_of_sums(results, lucky=False) > 2 * SIGMAS  # and a fair roll would be far off: the check has power


def test_a_chaos_orb_still_rolls_every_value_once():
    outcomes = ChaosOrb().outcomes(DATA, amulet())
    rng = random.Random(61)
    results = [outcomes.sample(rng) for _ in range(500)]

    assert abs(_z_of_sums(results, lucky=False)) <= SIGMAS


def test_the_forced_mod_of_a_lucky_reroll_is_rolled_twice_too():
    forced = DATA.mods[LIFE]
    outcomes = dataclasses.replace(Outcomes.reroll(DATA, amulet(), None, forced=forced), rolls_lucky=True)
    rng = random.Random(8)
    values = [values_of(outcomes.sample(rng), LIFE)[0] for _ in range(1500)]
    mean, variance = _better_of_two(10, 24)

    z = (sum(values) / len(values) - float(mean)) / math.sqrt(float(variance) / len(values))
    assert abs(z) <= SIGMAS
    assert abs((sum(values) / len(values)) - 10 - 14 / 2) > 0.5  # far from the fair mean 17: the check has power


def test_a_lucky_roll_of_1_to_3_gives_1_2_3_with_the_chances_one_three_five_ninths():
    rng, count = random.Random(3), 9000
    seen = [roll_value(rng, StatRange("test_stat", 1, 3), lucky=True) for _ in range(count)]

    for value, chance in ((1, Fraction(1, 9)), (2, Fraction(3, 9)), (3, Fraction(5, 9))):
        share = float(chance)
        assert abs(seen.count(value) / count - share) <= SIGMAS * math.sqrt(share * (1 - share) / count)


def test_a_stat_that_runs_from_a_high_minimum_to_a_low_maximum_keeps_the_lower_roll_when_lucky():
    # the better value is the one nearer `max`: for 3 down to 1 that is the lower, so 1, 2, 3 have the chances 5, 3, 1 ninths
    rng, count = random.Random(4), 9000
    seen = [roll_value(rng, StatRange("test_stat", 3, 1), lucky=True) for _ in range(count)]

    for value, chance in ((1, Fraction(5, 9)), (2, Fraction(3, 9)), (3, Fraction(1, 9))):
        share = float(chance)
        assert abs(seen.count(value) / count - share) <= SIGMAS * math.sqrt(share * (1 - share) / count)


def test_a_fair_roll_uses_one_draw_per_stat_so_seeded_runs_do_not_change():
    rng, same = random.Random(9), random.Random(9)

    assert [roll_value(rng, StatRange("test_stat", 10, 24)) for _ in range(5)] == [same.randint(10, 24) for _ in range(5)]


def test_the_mods_a_sanctified_resonator_keeps_keep_their_values():
    kept = ExplicitMod("LightningResist1", 8, (9,), fractured=True)
    outcomes = ApplyFossils(("Sanctified Fossil",)).outcomes(LUCKY_DATA, amulet(kept))
    rng = random.Random(12)

    for _ in range(40):
        assert values_of(outcomes.sample(rng), "LightningResist1") == (9,)
