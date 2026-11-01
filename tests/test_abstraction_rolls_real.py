"""Roll requirements on the real 3.29.3.3 data (#71): the law of a Life tier, counted by hand, and what it does to a kernel.

The amulet's Life tiers are `IncreasedLife0` to `IncreasedLife12`, 15 integers wide from tier 3 on: `IncreasedLife4`
rolls 55..69, `IncreasedLife5` 70..84, `IncreasedLife6` 85..99. So "at least 70 Life" is exactly the border between
the tiers 4 and 5 (no tier rolls across it: every law is one outcome), and the cut inside a tier is at a higher
number: "at least 75" cuts `IncreasedLife5` into 75..84 (10 of 15 values) and 70..74 (5 of 15). The hybrid mod
`IncreasedLifeEnhancedMod` rolls Life 70..79 and Life % 3..5. Skipped without the data, like its siblings.
"""

from fractions import Fraction

import pytest
from abstraction_rolls_oracle import ToyDivine
from abstraction_support import real_game_data
from items_support import AMULET

from crafting_system.abstraction import Abstraction, Goal, Status, Wanted
from crafting_system.abstraction._rolls import is_rollable, roll_law
from crafting_system.actions import ChaosOrb
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table

LEVEL = 86
LIFE_TIERS = tuple(f"IncreasedLife{number}" for number in range(13))
LIFE_5, LIFE_4, LIFE_6 = "IncreasedLife5", "IncreasedLife4", "IncreasedLife6"
HYBRID = "IncreasedLifeEnhancedMod"
ABSENT, BELOW, PASSING = Status.ABSENT, Status.BELOW, Status.PASSING


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def law_of(data, mod_id: str, min_roll: tuple, *, lucky: bool = False, tier: int = 1):
    leaf = Wanted(frozenset(LIFE_TIERS) | {HYBRID}, min_roll=min_roll)
    return dict(roll_law((leaf,), data.mods[mod_id], tier, False, lucky))


def test_at_least_70_life_is_the_border_between_two_tiers_so_no_tier_rolls_across_it(data):
    assert [(data.mods[mod_id].stats[0].min, data.mods[mod_id].stats[0].max) for mod_id in (LIFE_4, LIFE_5, LIFE_6)] == [
        (55, 69),
        (70, 84),
        (85, 99),
    ]
    assert law_of(data, LIFE_4, (70,)) == {(int(BELOW),): 1}  # 55..69: no roll reaches 70
    assert law_of(data, LIFE_5, (70,)) == {(int(PASSING),): 1}  # 70..84: every roll does
    assert law_of(data, LIFE_6, (70,)) == {(int(PASSING),): 1}
    assert not any(is_rollable(roll_law((Wanted(frozenset(LIFE_TIERS), min_roll=(70,)),), data.mods[mod_id], 1)) for mod_id in LIFE_TIERS)


def test_at_least_75_life_cuts_tier_5_in_ten_values_of_fifteen(data):
    assert law_of(data, LIFE_5, (75,)) == {(int(BELOW),): Fraction(5, 15), (int(PASSING),): Fraction(10, 15)}  # 70..74 and 75..84
    assert law_of(data, LIFE_4, (75,)) == {(int(BELOW),): 1}
    assert law_of(data, LIFE_6, (75,)) == {(int(PASSING),): 1}


def test_a_lucky_roll_of_tier_5_misses_75_only_when_both_rolls_do(data):
    assert law_of(data, LIFE_5, (75,), lucky=True) == {
        (int(BELOW),): Fraction(5, 15) ** 2,  # both of two rolls in 70..74
        (int(PASSING),): 1 - Fraction(1, 9),
    }


def test_a_hybrid_mod_needs_both_stats(data):
    leaf = Wanted(frozenset({HYBRID}), min_roll=(75, 4))  # Life 70..79 (5 of 10 reach 75) and Life % 3..5 (2 of 3 reach 4)
    assert dict(roll_law((leaf,), data.mods[HYBRID], 1)) == {(int(BELOW),): 1 - Fraction(1, 2) * Fraction(2, 3), (int(PASSING),): Fraction(1, 3)}
    assert dict(roll_law((leaf,), data.mods[HYBRID], 1, False, True)) == {
        (int(PASSING),): (1 - Fraction(1, 4)) * (1 - Fraction(1, 9)),  # each stat: not both rolls under the wanted value
        (int(BELOW),): 1 - Fraction(3, 4) * Fraction(8, 9),
    }


def test_a_divine_orb_on_a_tier_5_life_mod_passes_75_in_two_cases_of_three(data):
    leaf = Wanted(frozenset(LIFE_TIERS), min_roll=(75,))
    ab = Abstraction(data, Goal((leaf,)), AMULET, LEVEL, [ToyDivine(), ToyDivine(lucky=True)])
    tier = tier_table(data, AMULET)[LIFE_5]
    item = Item.build(data, base_id=AMULET, item_level=LEVEL, rarity=Rarity.RARE, mods=(ExplicitMod(LIFE_5, tier, (70,)),))
    state = ab.compress(item)
    assert state.status == (BELOW,)

    kernel = ab.kernel(state, ToyDivine())
    assert {s.status: chance for s, chance in kernel.items()} == {(BELOW,): Fraction(1, 3), (PASSING,): Fraction(2, 3)}
    lucky = ab.kernel(state, ToyDivine(lucky=True))
    assert {s.status: chance for s, chance in lucky.items()} == {(BELOW,): Fraction(1, 9), (PASSING,): Fraction(8, 9)}


def test_a_chaos_orb_on_a_real_amulet_passes_75_life_by_the_chance_of_each_tier(data):
    """P(Life passes) = P(a tier from 6 up) + 2/3 P(tier 5), each P from one run of the engine over the groups of tiers."""
    leaf = Wanted(frozenset(LIFE_TIERS), min_roll=(75,))
    ab = Abstraction(data, Goal((leaf,)), AMULET, LEVEL)
    empty = Item.build(data, base_id=AMULET, item_level=LEVEL, rarity=Rarity.RARE)
    chaos = ChaosOrb().outcomes(data, empty)

    def tier_group(mod) -> str | None:
        if mod.id not in LIFE_TIERS:
            return None
        number = int(mod.id.removeprefix("IncreasedLife"))
        return "from 6" if number >= 6 else "5" if number == 5 else "up to 4"

    held: dict = {}  # a finished item holds at most one Life mod: the chance of each group is the sum over the outcomes that show it
    for outcome, chance in chaos.distribution(tier_group).items():
        for group in {label for label, _ in outcome if label is not None}:
            held[group] = held.get(group, Fraction(0)) + chance
    expected_passing = held["from 6"] + Fraction(2, 3) * held["5"]
    expected_below = Fraction(1, 3) * held["5"] + held["up to 4"]

    kernel = ab.kernel(ab.compress(empty), ChaosOrb())

    assert {s.status: chance for s, chance in kernel.items()} == {
        (PASSING,): expected_passing,
        (BELOW,): expected_below,
        (ABSENT,): 1 - expected_passing - expected_below,
    }
