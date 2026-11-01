"""What the Eldritch actions declare about Memory Strands (ADR-0041, ticket #285, B5-11b).

"Done when" of #285: the claim for each declaration; one test that the spend is applied (Eldritch Chaos Orb) or absent (the rest).

* `EldritchChaosOrb` cuts (its draw is made from the cut pool of the count before the craft) and spends a uniform 0 to 60.
* Embers, Ichors and the Orb of Conflict neither cut nor spend (`approximate`, no source speaks of them).
* `EldritchExaltedOrb` and `EldritchAnnulmentOrb` declare nothing and are refused on an item with strands.

The fixture is that of `eldritch_support`, plus three higher tiers of the Life prefix, so that a cut at 60 strands (4 tiers keep 2) removes
the base tier of Life and the pool visibly differs from the uncut one.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from eldritch_support import COLD, DATA as FIXTURE, FIRE, LIFE, SPEED, eater, exarch, roll

from crafting_system.actions import (
    EldritchAnnulmentOrb,
    EldritchChaosOrb,
    EldritchExaltedOrb,
    EldritchImplicitCurrency,
    OrbOfConflict,
    OutOfScopeError,
)
from crafting_system.actions.cut import Cut
from crafting_system.actions.pool import build_pool
from crafting_system.actions.strand_use import Spent, SpendLaw, strands_after
from crafting_system.items import EldritchSide, Item, Rarity, Side

STRANDS = 60
ONE = Fraction(1)
CLAIM_SPEND = "memory_strands.spend_ranges_special_orbs"
CLAIM_CUT_FOLLOWS = "memory_strands.cut_follows_spend_table"
CLAIM_UNIFORM = "memory_strands.spend_law_uniform"
CUT_CLAIM_IDS = {  # the claims every cutting action rests on, written down by hand
    "affix_pool.no_memory_strands",
    "memory_strands.rollable_tiers",
    "memory_strands.cull_counts_eligible_tiers",
    "memory_strands.zero_is_no_cull",
    "memory_strands.cut_uses_strands_before_spend",
    "memory_strands.weights_of_kept_tiers",
}

# three higher tiers of the Life prefix (the fixture's FxPrefixLife1 is the lowest, level 1): 4 tiers, and 60 strands keep 2 of them
LIFE_TIERS = {f"FxPrefixLife{n}": level for n, level in ((2, 20), (3, 40), (4, 60))}
DATA = dataclasses.replace(
    FIXTURE,
    mods={**FIXTURE.mods, **{mod_id: dataclasses.replace(FIXTURE.mods[LIFE], id=mod_id, required_level=level) for mod_id, level in LIFE_TIERS.items()}},
)


def item(*mods, implicits=(), strands: int = 0, rarity: Rarity = Rarity.RARE, base: str = "Fixture/Boots") -> Item:
    return Item.build(DATA, base_id=base, item_level=84, rarity=rarity, mods=mods, implicits=implicits, memory_strands=strands)


def uncounted(finished: Item) -> Item:
    """`finished` with the strand count set to 0, to compare a stranded result with the one at 0 strands."""
    return dataclasses.replace(finished, memory_strands=0)


# --- Eldritch Chaos Orb: cuts and spends ---------------------------------------------------------------------------


def test_the_eldritch_chaos_orb_declares_a_cut_and_a_uniform_spend_of_up_to_60_with_its_claims():
    use = EldritchChaosOrb().strand_use(DATA)

    assert use.cuts and use.spend == SpendLaw.uniform(60)
    assert use.claims == CUT_CLAIM_IDS | {CLAIM_UNIFORM, CLAIM_SPEND, CLAIM_CUT_FOLLOWS}
    assert EldritchChaosOrb().strand_claims(DATA) == use.claims
    assert use.claims.isdisjoint(EldritchChaosOrb().claims(DATA))  # kept apart from the claims of an answer that ignores strands


def test_the_eldritch_chaos_orb_on_a_stranded_rare_item_spends_a_uniform_0_to_60_of_the_count():
    stranded = item(roll(LIFE), roll(FIRE), roll(COLD), implicits=(exarch(3),), strands=17)

    outcomes = EldritchChaosOrb().outcomes(DATA, stranded)

    assert isinstance(outcomes, Spent)
    assert outcomes.strands_after == SpendLaw.uniform(60).after(17, len(stranded.mods))
    assert outcomes.strands_after[0] == Fraction(44, 61)  # a spend of 17 to 60 empties the count
    assert sum(outcomes.strands_after.values()) == 1
    rng = random.Random(5)
    for _ in range(40):
        drawn = outcomes.sample(rng)
        assert drawn.memory_strands in outcomes.strands_after
        assert {entry.mod_id for entry in drawn.suffixes(DATA)} == {FIRE, COLD}  # the other side stays, as at 0 strands
        drawn.validate(DATA)


def test_the_eldritch_chaos_orb_draws_from_the_cut_pool_of_the_count_before_the_craft():
    stranded = item(roll(FIRE), implicits=(exarch(3),), strands=STRANDS)
    plain = item(roll(FIRE), implicits=(exarch(3),))

    outcomes = EldritchChaosOrb().outcomes(DATA, stranded)

    cut_pool = tuple(family for family in build_pool(DATA, outcomes.retained, cut=Cut.of(stranded)) if family.side is Side.PREFIX)
    uncut_pool = tuple(family for family in build_pool(DATA, outcomes.retained) if family.side is Side.PREFIX)
    assert outcomes.pool == cut_pool != uncut_pool
    life = next(family for family in outcomes.pool if family.family == "FxPrefixLife")
    assert {entry.mod.id for entry in life.mods} == {"FxPrefixLife3", "FxPrefixLife4"}  # 4 tiers keep the best 2: the level 1 tier is gone
    assert EldritchChaosOrb().outcomes(DATA, plain).pool == uncut_pool  # at 0 strands the ordinary pool, bit for bit
    assert uncut_pool != cut_pool


def test_the_eldritch_chaos_orb_at_0_strands_is_as_it_always_was():
    plain = item(roll(LIFE), roll(FIRE), implicits=(exarch(3),))

    outcomes = EldritchChaosOrb().outcomes(DATA, plain)

    assert not isinstance(outcomes, Spent) and strands_after(outcomes, 0) == {0: ONE}


# --- Embers, Ichors and the Orb of Conflict: neither cut nor spend -------------------------------------------------


UNTOUCHED = [
    EldritchImplicitCurrency(EldritchSide.EXARCH, 1),
    EldritchImplicitCurrency(EldritchSide.EATER, 3),
    EldritchImplicitCurrency(EldritchSide.EXARCH, 4),
    OrbOfConflict(),
]


@pytest.mark.parametrize("action", UNTOUCHED, ids=repr)
def test_embers_ichors_and_the_orb_of_conflict_declare_no_cut_and_no_spend_with_the_emulator_claim(action):
    use = action.strand_use(DATA)

    assert not use.cuts and use.spend is None
    assert use.claims == {CLAIM_CUT_FOLLOWS}
    assert action.strand_claims(DATA) == {CLAIM_CUT_FOLLOWS}
    assert CLAIM_CUT_FOLLOWS not in action.claims(DATA)


@pytest.mark.parametrize("action", UNTOUCHED, ids=repr)
def test_embers_ichors_and_the_orb_of_conflict_leave_the_count_alone_and_give_the_result_of_0_strands(action):
    held = (exarch(2), eater(1))  # both implicits: an Orb of Conflict needs them, an Ember or Ichor replaces what it must
    stranded = item(roll(LIFE), roll(FIRE), implicits=held, strands=STRANDS)
    plain = item(roll(LIFE), roll(FIRE), implicits=held)

    outcomes = action.outcomes(DATA, stranded)

    assert not isinstance(outcomes, Spent)
    assert strands_after(outcomes, STRANDS) == {STRANDS: ONE}
    assert [(chance, uncounted(result)) for chance, result in outcomes.results] == list(action.outcomes(DATA, plain).results)
    assert all(result.memory_strands == STRANDS for _, result in outcomes.results)


# --- Eldritch Exalted and Annulment orbs: undeclared, refused on a stranded item -----------------------------------


UNDECLARED = [EldritchExaltedOrb(), EldritchAnnulmentOrb()]


@pytest.mark.parametrize("action", UNDECLARED, ids=repr)
def test_the_eldritch_exalted_and_annulment_orbs_declare_nothing_and_are_refused_on_a_stranded_item(action):
    mods, implicits = (roll(LIFE), roll(FIRE)), (exarch(3),)  # a rare item with a dominant side and a free prefix slot

    assert action.strand_use(DATA) is None and action.strand_claims(DATA) == frozenset()
    with pytest.raises(OutOfScopeError, match="has not declared"):
        action.outcomes(DATA, item(*mods, implicits=implicits, strands=1))
    with pytest.raises(OutOfScopeError, match="has not declared"):
        action.outcomes(DATA, item(*mods, implicits=implicits, strands=STRANDS))
    assert action.outcomes(DATA, item(*mods, implicits=implicits)).components  # at 0 strands they still work
