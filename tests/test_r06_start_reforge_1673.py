"""R06's start: the first Deafening Essence of Rage reforges a Hunter Heavy Belt the same at any rarity (#1673, OR-43, OR-16).

R06 plans from a Normal Hunter belt, while the market sells Rare ones (the trade site, Covens, 2026-11-25: 1,146 Rare listings, 3 Normal).
The plan is the same from either because the first step, Deafening Essence of Rage, reforges the belt: on a Rare it removes every mod
(an essence of level 5 or higher reforges a Rare with no Scouring), on a Normal there is none to remove, and both leave a Rare belt with the
forced "+(51-58) to Strength" and 3, 4 or 5 more mods drawn from the same pool. So the route page may tell the player to buy the belt at any
rarity. These pin that law on hand-worked numbers: what the essence keeps (the forced mod alone), how many mods the reforged belt holds
(4, 5 or 6 at 8:3:1, as an Orb of Alchemy), and that the chance of each wanted mod is the same exact fraction from either start. The
planner's own evidence is #1673's probe: 900 s with six methods gave 1,236.50 Chaos from a Normal start and 1,236.52 from a Rare one.
They skip without the cached dump.
"""

from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import ApplyEssence
from crafting_system.items import ExplicitMod, Influence, Item, Rarity

BELT = "Metadata/Items/Belts/Belt4"  # Heavy Belt
RAGE = "Deafening Essence of Rage"
FORCED = "StrengthEssence7_"  # +(51-58) to Strength
ATTRIBUTES = "PercentageAllAttributesInfluence2"  # (10-12)% increased Attributes, the Hunter mod the target wants
LIFE = "IncreasedLife7"  # +(130-144) to maximum Life, the top Life tier at item level 75
RARE_MODS = (LIFE, ATTRIBUTES, "FireResist5", "IncreasedPhysicalDamageReductionRating5")  # a Rare the market might sell, wanted mods on it


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def belt(data, rarity: Rarity, mod_ids: tuple[str, ...] = ()) -> Item:
    mods = tuple(ExplicitMod(mod_id, tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)) for mod_id in mod_ids)
    return Item.build(data, base_id=BELT, item_level=75, rarity=rarity, influences=frozenset({Influence.HUNTER}), mods=mods)


def test_the_essence_keeps_only_its_forced_mod_whatever_the_belt_held(data):
    normal = ApplyEssence(RAGE).outcomes(data, belt(data, Rarity.NORMAL))
    rare = ApplyEssence(RAGE).outcomes(data, belt(data, Rarity.RARE, RARE_MODS))

    for outcomes in (normal, rare):
        assert outcomes.forced == FORCED
        assert outcomes.retained.rarity is Rarity.RARE and [mod.mod_id for mod in outcomes.retained.mods] == [FORCED]
        assert outcomes.retained.influences == frozenset({Influence.HUNTER})  # the influence stays: the Hunter pool is drawn again
        assert dict(outcomes.totals) == {4: Fraction(8, 12), 5: Fraction(3, 12), 6: Fraction(1, 12)}  # 4, 5 or 6 mods at 8:3:1
    assert normal.retained == rare.retained  # the Rare's Life, Attributes, Fire Resistance and Armour are all gone


@pytest.mark.parametrize("wanted", [(ATTRIBUTES,), (LIFE,), (ATTRIBUTES, LIFE)])
def test_each_wanted_mod_comes_with_the_same_exact_chance_from_a_normal_or_a_rare_belt(data, wanted):
    normal = ApplyEssence(RAGE).outcomes(data, belt(data, Rarity.NORMAL))
    rare = ApplyEssence(RAGE).outcomes(data, belt(data, Rarity.RARE, RARE_MODS))

    chance = normal.chance_all(wanted)
    assert type(chance) is Fraction and 0 < chance < 1
    assert rare.chance_all(wanted) == chance
