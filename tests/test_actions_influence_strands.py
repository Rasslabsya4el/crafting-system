"""What the influence crafts declare about Memory Strands (ticket #286, ADR-0041 and its amendments).

"Done when" and where it is shown:

* the claim for each declaration: `test_each_declaration_cites_exactly_its_claims_and_none_is_among_claims`;
* the spend is applied by an influenced Exalted Orb: `test_an_influenced_exalted_orb_spends_by_the_mods_before_the_craft` (every mod count the
  fixture allows) and `test_the_sampler_of_an_influenced_exalted_orb_leaves_a_count_in_the_support`; its draw is cut:
  `test_the_pool_of_a_stranded_influenced_exalted_orb_is_the_cut_pool_of_the_item_with_the_influence`;
* the spend is absent for the rest: `test_the_orb_of_dominance_leaves_the_strands_and_the_results_alone` and
  `test_the_beast_recipe_leaves_the_strands_alone_and_draws_from_the_uncut_pool`.

The fixture is the Contract Helmet of `influence_support.py` at item level 84. Its Shaper prefix family P has three tiers (P1, P2, P3) and its Shaper
suffix family S two (S1, S2); the Elder, Hunter and Plain mods and the Shaper mod of level 90 are out of every Shaper pool. At 100 strands the cut keeps one
tier of each table (K = floor(200 (T - 1) / 795) + 1 = 1), reweighed by T / K under the chosen reading: P3 at 200 * 3 = 600 and S2 at 500 * 2 = 1000.
"""

import random
from fractions import Fraction

import pytest
from influence_support import ELEVATED, INFLUENCE_DATA, P1, P2, P3, PLAIN, S1, S2, helmet, roll

from crafting_system.actions import (
    BeastInfluenceRecipe,
    InfluencedExaltedOrb,
    OrbOfDominance,
    Spent,
    SpendLaw,
    influence_pool,
    strands_after,
)
from crafting_system.actions.cut import Cut
from crafting_system.items import Influence, Item

DATA = INFLUENCE_DATA
SHAPER = Influence.SHAPER
CEILINGS = (16, 22, 26, 32, 34, 38)  # claim `memory_strands.spend_exalted_by_mod_count`: 0 to 5 mods before the craft
ONE = Fraction(1)
BY_FAMILY = lambda mod: mod.families[0]  # noqa: E731

# Mods that cannot block the Shaper families (P, S) and fit a helmet; in the order a helmet gets its k mods: 3 prefixes and 2 suffixes at most, so the
# fifth leaves one open suffix slot for the orb.
FILLER = (PLAIN, "ColdResist1", "IncreasedLife1", "FireResist1", "AddedLightningDamage1")

CUT_CLAIMS = {
    "affix_pool.no_memory_strands",
    "memory_strands.rollable_tiers",
    "memory_strands.cull_counts_eligible_tiers",
    "memory_strands.zero_is_no_cull",
    "memory_strands.cut_uses_strands_before_spend",
    "memory_strands.weights_of_kept_tiers",
}


def with_mods(count: int, strands: int, **fields) -> Item:
    """A rare Contract Helmet with `count` filler mods and `strands` strands."""
    return helmet(*(roll(mod_id, 1) for mod_id in FILLER[:count]), memory_strands=strands, **fields)


def shaper_helmet(*mods, strands: int = 0) -> Item:
    return helmet(*mods, influences=frozenset({SHAPER}), memory_strands=strands)


def without_count(item: Item) -> Item:
    """`item` with its strand count set to 0: the item a 0-strand craft leaves, to compare with."""
    return item.changed(DATA, memory_strands=0)


# --- the influenced Exalted Orb: cuts and spends -----------------------------------------------------------------------------


def test_an_influenced_exalted_orb_declares_what_the_plain_exalted_orb_declares():
    from crafting_system.actions import ExaltedOrb

    plain = ExaltedOrb().strand_use(DATA)
    for influence in Influence:
        use = InfluencedExaltedOrb(influence).strand_use(DATA)

        assert use == plain and use.cuts is True
        assert use.spend == SpendLaw.by_mods(*CEILINGS) and [use.spend.ceiling(mods) for mods in range(6)] == list(CEILINGS)


@pytest.mark.parametrize("mods", range(6))
def test_an_influenced_exalted_orb_spends_by_the_mods_before_the_craft(mods):
    orb = InfluencedExaltedOrb(SHAPER)
    item = with_mods(mods, strands=100)

    result = orb.outcomes(DATA, item)

    assert isinstance(result, Spent) and result.before == 100 and result.mods_before == mods
    assert strands_after(result, 100) == SpendLaw.by_mods(*CEILINGS).after(100, mods)
    after = dict(strands_after(result, 100))
    assert min(after) == 100 - CEILINGS[mods] and max(after) == 100
    assert set(after.values()) == {Fraction(1, CEILINGS[mods] + 1)} and sum(after.values()) == ONE


def test_a_spend_larger_than_the_count_empties_the_count_of_an_influenced_exalted_orb():
    after = strands_after(InfluencedExaltedOrb(SHAPER).outcomes(DATA, with_mods(2, strands=3)), 3)

    assert after == SpendLaw.by_mods(*CEILINGS).after(3, 2)
    assert after[0] == Fraction(24, 27) and sum(after.values()) == ONE  # 2 mods: ceiling 26, and a spend of 3 to 26 (24 of 27 values) leaves 0


def test_the_sampler_of_an_influenced_exalted_orb_leaves_a_count_in_the_support():
    item = with_mods(2, strands=100)
    result = InfluencedExaltedOrb(SHAPER).outcomes(DATA, item)
    support = set(strands_after(result, 100))
    rng = random.Random(286)

    finished = [result.sample(rng) for _ in range(60)]

    assert all(done.memory_strands in support for done in finished)
    assert len({done.memory_strands for done in finished}) > 1  # the spend is random, not a constant
    assert all(done.influences == frozenset({SHAPER}) and len(done.mods) == 3 for done in finished)
    assert all(100 - CEILINGS[2] <= done.memory_strands <= 100 for done in finished)


def test_no_strands_no_change_for_an_influenced_exalted_orb():
    orb = InfluencedExaltedOrb(SHAPER)
    item = with_mods(2, strands=0)

    result = orb.outcomes(DATA, item)

    assert not isinstance(result, Spent) and strands_after(result, 0) == {0: ONE}
    assert result.pool == influence_pool(DATA, item.changed(DATA, influences=frozenset({SHAPER})), SHAPER)  # no cut: the ordinary Shaper pool


def test_the_pool_of_a_stranded_influenced_exalted_orb_is_the_cut_pool_of_the_item_with_the_influence():
    orb = InfluencedExaltedOrb(SHAPER)
    item = with_mods(0, strands=100)
    retained = item.changed(DATA, influences=frozenset({SHAPER}))

    # the cut reads the count the item has before the craft, and `changed` keeps it: the item and the item with the influence cut alike
    assert Cut.of(item) == Cut.of(retained) == Cut(100)
    result = orb.outcomes(DATA, item)
    assert result.pool == influence_pool(DATA, retained, SHAPER, Cut.of(item)) == influence_pool(DATA, retained, SHAPER, Cut.of(retained))

    # it differs from the pool at 0 strands, where the cut bites: one tier of each table is left, reweighed by T / K
    uncut = influence_pool(DATA, retained, SHAPER)
    assert result.pool != uncut
    cut_mods = {entry.mod.id: entry.weight for family in result.pool for entry in family.mods}
    assert cut_mods == {P3: 600, S2: 1000}
    assert {entry.mod.id: entry.weight for family in uncut for entry in family.mods} == {P1: 300, P2: 300, P3: 200, S1: 500, S2: 500}

    # and the odds of the finished item follow it: P3 600 of 1600, S2 1000 of 1600; the lower tiers cannot be drawn
    assert result.chance_all([P3]) == Fraction(3, 8) and result.chance_all([S2]) == Fraction(5, 8)
    assert result.chance_all([P1]) == 0 and result.chance_all([P2]) == 0 and result.chance_all([S1]) == 0
    plain_draw = orb.outcomes(DATA, with_mods(0, strands=0))
    assert plain_draw.chance_all([P3]) == Fraction(200, 1800) and plain_draw.chance_all([P1]) == Fraction(300, 1800)


def test_the_cut_of_a_stranded_influenced_exalted_orb_reads_the_count_before_the_craft_at_a_low_count():
    # 1 strand: D = 300 so the three tiers of P keep 2 (P2, P3) and the two of S keep 1 (S2)
    result = InfluencedExaltedOrb(SHAPER).outcomes(DATA, with_mods(0, strands=1))
    retained = with_mods(0, strands=1).changed(DATA, influences=frozenset({SHAPER}))

    assert result.pool == influence_pool(DATA, retained, SHAPER, Cut(1))
    assert {entry.mod.id for family in result.pool for entry in family.mods} == {P2, P3, S2}


def test_the_cut_follows_each_influenced_exalted_orb_and_a_mod_count():
    # the draw of every mod count is cut by the same count: the strands, not the mods, decide the tiers
    for mods in range(6):
        result = InfluencedExaltedOrb(SHAPER).outcomes(DATA, with_mods(mods, strands=100))

        assert {entry.mod.id for family in result.pool for entry in family.mods} <= {P3, S2}


# --- the Orb of Dominance: neither cuts nor spends ----------------------------------------------------------------------------


@pytest.mark.parametrize("strands", [1, 70, 100])
def test_the_orb_of_dominance_leaves_the_strands_and_the_results_alone(strands):
    orb = OrbOfDominance(elevated=ELEVATED)
    stranded = shaper_helmet(roll(P1, 3), roll(S1, 2), strands=strands)
    bare = shaper_helmet(roll(P1, 3), roll(S1, 2), strands=0)

    result, reference = orb.outcomes(DATA, stranded), orb.outcomes(DATA, bare)

    assert not isinstance(result, Spent) and strands_after(result, strands) == {strands: ONE}
    assert len(result.results) == len(reference.results) == 2
    # the finished items are those at 0 strands, with the count of the stranded item (it is not touched)
    assert [(chance, done.memory_strands) for chance, done in result.results] == [(chance, strands) for chance, _ in reference.results]
    assert [(chance, without_count(done)) for chance, done in result.results] == list(reference.results)
    assert {frozenset(entry.mod_id for entry in done.mods) for _, done in result.results} == {frozenset({S2}), frozenset({P2})}


def test_the_orb_of_dominance_is_not_cut():
    orb = OrbOfDominance(elevated=ELEVATED)

    assert orb.cut_of(DATA, shaper_helmet(roll(P1, 3), roll(S1, 2), strands=100)) is None


# --- the beast recipe: neither cuts nor spends, and borrows the pool without the cut --------------------------------------------


@pytest.mark.parametrize("strands", [1, 100])
def test_the_beast_recipe_leaves_the_strands_alone_and_draws_from_the_uncut_pool(strands):
    recipe = BeastInfluenceRecipe(SHAPER)
    stranded, bare = shaper_helmet(strands=strands), shaper_helmet(strands=0)

    result, reference = recipe.outcomes(DATA, stranded), recipe.outcomes(DATA, bare)

    assert recipe.cut_of(DATA, stranded) is None
    assert not isinstance(result, Spent) and strands_after(result, strands) == {strands: ONE}
    # the draw equals the 0-strand draw, even at a high count: the pool is not cut
    assert result.pool == reference.pool == influence_pool(DATA, stranded, SHAPER)
    assert {entry.mod.id: entry.weight for family in result.pool for entry in family.mods} == {P1: 300, P2: 300, P3: 200, S1: 500, S2: 500}
    assert result.chance_all([P3]) == reference.chance_all([P3]) == Fraction(200, 1800)
    assert result.distribution(BY_FAMILY) == reference.distribution(BY_FAMILY)
    # the finished item is the 0-strand one with the count of the stranded item
    finished, expected = result.sample(random.Random(5)), reference.sample(random.Random(5))
    assert finished.memory_strands == strands and without_count(finished) == expected


def test_the_beast_recipe_pool_differs_from_the_orb_pool_only_by_the_cut():
    item = shaper_helmet(strands=100)

    beast = BeastInfluenceRecipe(SHAPER).outcomes(DATA, item).pool
    orb = InfluencedExaltedOrb(SHAPER).outcomes(DATA, helmet(memory_strands=100)).pool

    assert beast != orb and {entry.mod.id for family in orb for entry in family.mods} < {entry.mod.id for family in beast for entry in family.mods}


# --- the claims ---------------------------------------------------------------------------------------------------------------


def test_each_declaration_cites_exactly_its_claims_and_none_is_among_claims():
    declared = {
        "the influenced Exalted Orb": (
            InfluencedExaltedOrb(SHAPER),
            CUT_CLAIMS | {"memory_strands.spend_law_uniform", "memory_strands.spend_exalted_by_mod_count"},
        ),
        "the Orb of Dominance": (OrbOfDominance(), {"memory_strands.cut_follows_spend_table"}),
        "the beast influence recipe": (
            BeastInfluenceRecipe(SHAPER),
            {"memory_strands.not_spent_by", "memory_strands.cut_follows_spend_table"},
        ),
    }
    for name, (action, claims) in declared.items():
        assert action.strand_claims(DATA) == action.strand_use(DATA).claims == frozenset(claims), name
        assert not {claim for claim in action.claims(DATA) if claim.startswith(("memory_strands.", "foulborn."))}, name
        assert "affix_pool.no_memory_strands" not in action.claims(DATA), name
    for influence in Influence:  # the six orbs and the six recipes declare alike
        assert InfluencedExaltedOrb(influence).strand_claims(DATA) == declared["the influenced Exalted Orb"][1]
        assert BeastInfluenceRecipe(influence).strand_claims(DATA) == declared["the beast influence recipe"][1]
    for action in (OrbOfDominance(), BeastInfluenceRecipe(SHAPER)):
        use = action.strand_use(DATA)
        assert use.cuts is False and use.spend is None and not use.reads_count and not use.changes_count


def test_the_influenced_pool_without_a_cut_is_the_pool_it_always_was():
    item = helmet(influences=frozenset({SHAPER}))

    assert influence_pool(DATA, item, SHAPER) == influence_pool(DATA, item, SHAPER, None) == influence_pool(DATA, item, SHAPER, Cut(0))
