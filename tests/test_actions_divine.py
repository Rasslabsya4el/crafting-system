"""The Divine Orb: values rerolled in place (ticket #71).

A Divine Orb rerolls the values of every explicit mod that is not fractured and not on a side a lock
protects, uniformly over the integers of each stat's range, independently per stat; the mods, their
tiers and their order stay (claims `divine_orb.*`, issue #7 CUR-18..CUR-23). The planner's offer of it is
in `test_cli_offers_divine.py`, the Sanctified Fossil's lucky values in `test_actions_sanctified.py`.
"""

import dataclasses
import math
import random
from collections import Counter
from fractions import Fraction

import pytest
from actions_support import DATA, amulet, fractured_resist
from items_support import AMULET, roll

from crafting_system.actions import DivineOrb, NotApplicableError, Rerolled, catalog, kinds
from crafting_system.items import ExplicitMod, Item, Rarity
from crafting_system.rules import get_rule

LIFE, LIFE_2 = "IncreasedLife1", "IncreasedLife2"  # 10 to 24 (tier 3) and 25 to 39 (tier 2)
RESIST = "LightningResist1"  # 6 to 11
MANA = "ManaLeechPermyriadSuffix1"  # 20 to 40
DAMAGE = "AddedLightningDamage1"  # two stats, both fixed: 1 and 5
GEM = "GlobalLightningGemLevel1"  # fixed: 1
LOCKS_SUFFIXES = "DexMasterItemGenerationCannotChangeSuffixes"  # a prefix that protects the suffixes
LOCKS_PREFIXES = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix that protects the prefixes
MULTIMOD = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"  # a suffix
ORDINARY_CRAFTED = "JunMaster2AllDamage2_"  # 12 to 14

SIGMAS = 5.0


def life(value: int = 10, **flags) -> ExplicitMod:
    return ExplicitMod(LIFE, 3, (value,), **flags)


def values_of(result, mod_id: str) -> tuple[int, ...]:
    return next(entry.values for entry in result.mods if entry.mod_id == mod_id)


def samples(item_, count: int, seed: int = 71):
    outcomes = DivineOrb().outcomes(DATA, item_)
    rng = random.Random(seed)
    return [outcomes.sample(rng) for _ in range(count)]


# --- refusals, each citing a claim ----------------------------------------------------------------


def test_a_normal_item_is_refused_by_the_game():
    with pytest.raises(NotApplicableError, match="magic, rare or unique item only"):
        DivineOrb().outcomes(DATA, amulet(rarity=Rarity.NORMAL))


def test_a_corrupted_item_is_refused_by_the_game():
    with pytest.raises(NotApplicableError, match="corrupted.*Divine Orb"):
        DivineOrb().outcomes(DATA, dataclasses.replace(amulet(roll(LIFE)), corrupted=True))


def test_an_item_with_no_mod_to_change_is_refused_and_nothing_is_consumed():
    with pytest.raises(NotApplicableError, match="no mod that is not fractured"):
        DivineOrb().outcomes(DATA, amulet(rarity=Rarity.MAGIC))
    with pytest.raises(NotApplicableError, match="no mod that is not fractured"):
        DivineOrb().outcomes(DATA, amulet(fractured_resist(), fractured_resist("ColdResist1")))


def test_an_item_whose_every_mod_is_fractured_or_on_a_locked_side_is_refused():
    # the suffix lock is a prefix and the prefix lock a suffix: each sits on the side the other locks, and the multimod is a suffix
    item_ = amulet(
        roll(LOCKS_SUFFIXES, crafted=True), roll(LOCKS_PREFIXES, crafted=True), roll(MULTIMOD, crafted=True), roll(LIFE, fractured=True)
    )
    with pytest.raises(NotApplicableError, match="no mod that is not fractured"):
        DivineOrb().outcomes(DATA, item_)


def test_the_refusals_cite_a_claim_of_the_registry():
    assert {
        "divine_orb.accepts_magic_rare_unique",
        "divine_orb.refused_on_corrupted",
        "divine_orb.refused_without_changeable_mod",
    } <= DivineOrb().claims()


# --- which mods are changed ------------------------------------------------------------------------


def test_every_unfractured_mod_is_changed_and_the_key_names_its_flags():
    item_ = amulet(roll(LIFE), roll(RESIST), roll(MANA))
    [(chance, part)] = DivineOrb().outcomes(DATA, item_).components

    assert chance == 1 and isinstance(part, Rerolled) and part.lucky is False
    assert part.changed == frozenset({(LIFE, False, False), (RESIST, False, False), (MANA, False, False)})
    assert part.given is item_ and part.retained is item_


def test_a_fractured_mod_is_not_changed():
    item_ = amulet(roll(LIFE), roll(RESIST, fractured=True), roll(MANA))
    [(_, part)] = DivineOrb().outcomes(DATA, item_).components

    assert part.changed == frozenset({(LIFE, False, False), (MANA, False, False)})


def test_a_mod_on_a_locked_side_is_not_changed_and_a_mod_on_the_other_side_is():
    # the lock keeps the suffixes; the lock itself is a crafted prefix and an ordinary candidate (D5 of issue #28 reads alike)
    item_ = amulet(roll(LIFE), roll(RESIST), roll(MANA), roll(LOCKS_SUFFIXES, crafted=True))
    [(_, part)] = DivineOrb().outcomes(DATA, item_).components

    assert part.changed == frozenset({(LIFE, False, False), (LOCKS_SUFFIXES, False, True)})


def test_an_ordinary_crafted_mod_is_changed():
    item_ = amulet(roll(LIFE), roll(ORDINARY_CRAFTED, crafted=True))
    [(_, part)] = DivineOrb().outcomes(DATA, item_).components

    assert (ORDINARY_CRAFTED, False, True) in part.changed


def test_a_magic_item_is_in_scope():
    [(_, part)] = DivineOrb().outcomes(DATA, amulet(roll(LIFE), rarity=Rarity.MAGIC)).components

    assert part.changed == frozenset({(LIFE, False, False)})


# --- the exact answers -----------------------------------------------------------------------------


def test_nothing_is_added_and_the_distribution_has_one_empty_outcome():
    outcomes = DivineOrb().outcomes(DATA, amulet(roll(LIFE), roll(RESIST)))

    assert dict(outcomes.distribution(lambda mod: mod.id)) == {frozenset(): Fraction(1)}
    assert outcomes.fractures is False


def test_the_chance_of_holding_the_mods_is_one_for_the_mods_it_holds_and_zero_for_the_others():
    outcomes = DivineOrb().outcomes(DATA, amulet(roll(LIFE), roll(RESIST)))

    assert outcomes.chance_all([LIFE]) == 1
    assert outcomes.chance_all([LIFE, RESIST]) == 1
    assert outcomes.chance_all([MANA]) == 0
    assert outcomes.chance_all([LIFE, MANA]) == 0
    assert outcomes.chance_all([LIFE, LIFE_2]) == 0  # one family
    with pytest.raises(ValueError, match="not in the game data"):
        outcomes.chance_all(["NoSuchMod"])


# --- the sampler -----------------------------------------------------------------------------------


def test_a_sample_keeps_the_mods_their_tiers_their_order_and_their_flags():
    item_ = amulet(life(), roll(RESIST, tier=2), roll(ORDINARY_CRAFTED, crafted=True), roll(MANA, fractured=True))

    for drawn in samples(item_, 50):
        drawn.validate(DATA)
        assert [(e.mod_id, e.tier, e.fractured, e.crafted) for e in drawn.mods] == [
            (e.mod_id, e.tier, e.fractured, e.crafted) for e in item_.mods
        ]
        assert drawn.rarity is item_.rarity and drawn.item_level == item_.item_level


def test_a_fractured_mod_and_a_mod_on_a_locked_side_keep_their_values():
    item_ = amulet(
        life(17), ExplicitMod(RESIST, 8, (9,)), ExplicitMod(MANA, 2, (33,), fractured=True), roll(LOCKS_SUFFIXES, crafted=True)
    )

    for drawn in samples(item_, 60):
        assert values_of(drawn, RESIST) == (9,) and values_of(drawn, MANA) == (33,)  # a suffix under the suffix lock; a fractured one


def test_a_changed_value_stays_in_its_range_and_is_uniform_over_it():
    count = 6000
    drawn = Counter(values_of(result, LIFE)[0] for result in samples(amulet(life(10)), count))

    assert set(drawn) == set(range(10, 25))  # 15 values, all reached, none outside
    share = 1 / 15
    error = SIGMAS * math.sqrt(share * (1 - share) / count)
    assert all(abs(number / count - share) <= error for number in drawn.values())


def test_the_stats_of_one_mod_roll_independently():
    data = _hybrid_data()
    item_ = Item.build(data, base_id=AMULET, item_level=86, rarity=Rarity.RARE, mods=(ExplicitMod(LIFE, 3, (10, 1)),))
    outcomes = DivineOrb().outcomes(data, item_)
    rng, count = random.Random(5), 6000
    pairs = Counter(outcomes.sample(rng).mods[0].values for _ in range(count))

    assert set(pairs) == {(a, b) for a in (10, 11, 12) for b in (1, 2)}  # the product of the two ranges: 6 cells
    share = 1 / 6
    error = SIGMAS * math.sqrt(share * (1 - share) / count)
    assert all(abs(number / count - share) <= error for number in pairs.values())


def test_a_mod_with_fixed_stats_samples_to_the_same_values():
    for drawn in samples(amulet(roll(GEM), roll(DAMAGE)), 20):
        assert values_of(drawn, GEM) == (1,) and values_of(drawn, DAMAGE) == (1, 5)


def test_the_same_seed_gives_the_same_items():
    item_ = amulet(roll(LIFE), roll(RESIST))

    assert samples(item_, 10, seed=3) == samples(item_, 10, seed=3)
    assert samples(item_, 10, seed=3) != samples(item_, 10, seed=4)


def _hybrid_data():
    """The fixture with `LIFE` turned into a two-stat mod: 10 to 12 and 1 to 2."""
    mod = DATA.mods[LIFE]
    first = dataclasses.replace(mod.stats[0], min=10, max=12)
    second = dataclasses.replace(mod.stats[0], id="test_second_stat", min=1, max=2)
    return dataclasses.replace(DATA, mods={**DATA.mods, LIFE: dataclasses.replace(mod, stats=(first, second))})


# --- the action's declarations ---------------------------------------------------------------------


def test_the_orb_is_named_priced_and_declared():
    action = DivineOrb()

    assert action.label(DATA) == "Divine Orb"
    assert action.resources(DATA) == {"Divine Orb": 1}
    reads, adds = action.reads(DATA), action.adds(DATA, amulet())
    assert reads.junk and reads.families == frozenset() and reads.rerolls_values and not reads.pool_weight
    assert reads.block_invariant is False and reads.fractures is False
    assert not adds.draws and not adds.fractures and adds.keeps_crafted and adds.needs_roll_limit


def test_its_claims_name_the_cost_the_rerolls_and_the_independence_assumption():
    claims = DivineOrb().claims()

    assert {
        "divine_orb.cost",
        "divine_orb.rerolls_values_within_the_tier",
        "divine_orb.fractured_mods_stay",
        "divine_orb.locks_protect_existing_mods",
        "divine_orb.rerolls_crafted_mods",
        "divine_orb.hybrid_stats_roll_independently",
        "affix_pool.values_uniform_integers",
    } <= claims
    assert get_rule("divine_orb.cost").value["Divine Orb"] == 1
    assert get_rule("divine_orb.hybrid_stats_roll_independently").approximate


def test_the_kind_lists_magic_and_rare_items_and_is_a_planner_kind():
    assert DivineOrb() in catalog(DATA, amulet(roll(LIFE), rarity=Rarity.MAGIC))
    assert DivineOrb() in catalog(DATA, amulet(roll(LIFE)))
    assert DivineOrb() not in catalog(DATA, amulet(rarity=Rarity.NORMAL))
    assert DivineOrb() in catalog(DATA, amulet(roll(LIFE)), planner_only=True)
    assert {entry.name: entry.planner for entry in kinds()}["divine-orb"] is True
