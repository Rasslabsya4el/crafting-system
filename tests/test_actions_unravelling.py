"""The Orb of Unravelling on the small amulet pool and on the published numbers (ticket #281, ADR-0044, ADR-0019 layer 1).

Every expected number is typed here, not read from the action code:

* the published cases of the post (ADR-0044, "Tests that are published numbers"): T9 attribute mods on an amulet of item level 86 have
  8,000 weight above them (eight tiers of 1,000) against a suffix pool of 125,250 (the sheet's own total, in the claim's quote), so the
  chance is 1 at 32 strands (310 of 310 rose) and 31 * 8,000 / 250,500 = 99.0% at 31 (14 of 15); the wand case, T4 lightning damage to
  spells with 800 / 250 / 60 above it, goes to the final tier 3 / 2 / 1 with 81.08 / 16.89 / 2.03% under the rank reading A and
  75.0 / 20.95 / 4.05% under the cumulative reading B, the plan;
* the small pool (`abstraction_pool.SMALL`): prefixes weigh 1,000 + 1,000 (Life, levels 5 and 11) + 500 + 500 (Lightning Damage, levels 3
  and 13) + 3 x 200 (the gem levels) = 3,600; suffixes 1,000 + 1,000 (Mana Leech) + 1,000 (Fire) + 1,000 (Cold) + 3 x 1,000 (Lightning
  Resistance, levels 1, 13, 25) = 7,000. At 5 strands `LightningResist1` rises with 5 * 2,000 / 14,000 = 5/7, `AddedLightningDamage1` with
  5 * 500 / 7,200 = 25/72, `IncreasedLife1` with 5 * 1,000 / 7,200 = 25/36. A raised `LightningResist1` goes to `LightningResist2` with
  (1,000 + 1,000) / 3,000 = 2/3 and to `LightningResist3` with 1/3 (A gives the same: 2 x 1,000 against 1 x 1,000).
"""

import random
from fractions import Fraction
from itertools import product

import pytest
from abstraction_oracle import assert_same_distribution, compressed_distribution
from abstraction_pool import AMULET, CRAFTED, DAMAGE_1, DAMAGE_2, GEM, LEVEL, LIFE_1, LIFE_2, RESIST_1, RESIST_2, RESIST_3, SMALL, roll, small_item
from abstraction_support import GOALS

from crafting_system.abstraction import Abstraction
from crafting_system.actions import (
    Destination,
    NotApplicableError,
    OrbOfUnravelling,
    OutOfScopeError,
    PLAN_DESTINATION,
    catalog,
    destination_shares,
    kinds,
    unravel_chance,
)
from crafting_system.actions.strand_use import SpendLaw, Spent, strands_after
from crafting_system.planner._limits import kind_title
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

ORB = OrbOfUnravelling()
P_RESIST, P_DAMAGE, P_LIFE = Fraction(5, 7), Fraction(25, 72), Fraction(25, 36)  # at 5 strands, see the module docstring


def _results(outcomes) -> dict[frozenset[str], Fraction]:
    found: dict[frozenset[str], Fraction] = {}
    for chance, item in outcomes.results:
        key = frozenset(entry.mod_id for entry in item.mods)
        found[key] = found.get(key, Fraction(0)) + chance
    return found


# --- the published numbers -----------------------------------------------------------------------------------


def test_the_t9_amulet_case_is_guaranteed_at_32_strands_and_99_percent_at_31() -> None:
    assert unravel_chance(32, Fraction(8000), Fraction(125250)) == 1  # 310 of 310
    at_31 = unravel_chance(31, Fraction(8000), Fraction(125250))
    assert at_31 == Fraction(31 * 8000, 2 * 125250)
    assert round(float(at_31), 2) == 0.99  # 14 of 15
    assert round(float(unravel_chance(15, Fraction(8000), Fraction(125250))), 3) == 0.479  # the post's 47.9%


def test_the_wand_case_under_both_readings() -> None:
    above = [Fraction(60), Fraction(250), Fraction(800)]  # T1, T2, T3 above the T4 mod, top first
    rank = destination_shares(above, Destination.RANK)
    cumulative = destination_shares(above, Destination.CUMULATIVE)
    assert [round(float(share) * 100, 2) for share in rank] == [2.03, 16.89, 81.08]
    assert [round(float(share) * 100, 2) for share in cumulative] == [4.05, 20.95, 75.0]
    assert cumulative == (Fraction(60, 1480), Fraction(310, 1480), Fraction(1110, 1480))
    assert sum(rank) == sum(cumulative) == 1


def test_the_plan_reads_the_cumulative_destination_of_the_claim() -> None:
    assert PLAN_DESTINATION is Destination.CUMULATIVE
    assert get_rule("memory_strands.unravelling_destination_tier").value["reading"] == "cumulative"
    assert ORB.destination is Destination.CUMULATIVE


def test_no_weight_above_gives_no_chance() -> None:
    assert unravel_chance(100, Fraction(0), Fraction(7000)) == 0
    with pytest.raises(ValueError):
        unravel_chance(5, Fraction(10), Fraction(0))


# --- the result on the small pool -----------------------------------------------------------------------------


def test_three_mods_rise_each_on_its_own() -> None:
    start = small_item(roll(RESIST_1), roll(DAMAGE_1), roll(LIFE_1), memory_strands=5)
    outcomes = ORB.outcomes(SMALL, start)
    assert isinstance(outcomes, Spent)
    resist = {RESIST_1: 1 - P_RESIST, RESIST_2: P_RESIST * Fraction(2, 3), RESIST_3: P_RESIST * Fraction(1, 3)}
    damage = {DAMAGE_1: 1 - P_DAMAGE, DAMAGE_2: P_DAMAGE}
    life = {LIFE_1: 1 - P_LIFE, LIFE_2: P_LIFE}
    expected = {frozenset({r, d, l}): resist[r] * damage[d] * life[l] for r, d, l in product(resist, damage, life)}
    assert _results(outcomes.given) == expected
    assert outcomes.chance_all([RESIST_3]) == P_RESIST / 3
    assert outcomes.chance_all([RESIST_1, DAMAGE_1, LIFE_1]) == (1 - P_RESIST) * (1 - P_DAMAGE) * (1 - P_LIFE)  # none rises


def test_the_count_becomes_zero() -> None:
    start = small_item(roll(RESIST_1), memory_strands=37)
    outcomes = ORB.outcomes(SMALL, start)
    assert strands_after(outcomes, 37) == {0: 1}
    assert ORB.strand_use(SMALL).spend == SpendLaw.everything()
    assert ORB.strand_use(SMALL).after(start) == {0: 1}
    rng = random.Random(281)
    for _ in range(50):
        finished = outcomes.sample(rng)
        finished.validate(SMALL)
        assert finished.memory_strands == 0


def test_a_raised_mod_is_sampled_inside_its_new_range() -> None:
    start = small_item(roll(RESIST_1), memory_strands=100)  # 100 * 2,000 / 14,000 >= 1: it always rises
    rng = random.Random(7)
    seen = set()
    for _ in range(200):
        (entry,) = ORB.outcomes(SMALL, start).sample(rng).mods
        assert entry.mod_id in (RESIST_2, RESIST_3)
        stat = SMALL.mods[entry.mod_id].stats[0]
        assert stat.min <= entry.values[0] <= stat.max
        seen.add(entry.mod_id)
    assert seen == {RESIST_2, RESIST_3}


def test_enough_strands_make_the_rise_certain() -> None:
    start = small_item(roll(RESIST_1), roll(LIFE_1), memory_strands=10)  # Resistance 10/7 and Life 50/36: both capped at 1
    assert _results(ORB.outcomes(SMALL, start).given) == {
        frozenset({RESIST_2, LIFE_2}): Fraction(2, 3),
        frozenset({RESIST_3, LIFE_2}): Fraction(1, 3),
    }


def test_a_mod_at_the_top_of_its_table_stays() -> None:
    start = small_item(roll(RESIST_3), roll(LIFE_1), memory_strands=5)
    assert _results(ORB.outcomes(SMALL, start).given) == {frozenset({RESIST_3, LIFE_1}): 1 - P_LIFE, frozenset({RESIST_3, LIFE_2}): P_LIFE}


def test_crafted_and_fractured_mods_are_left_and_a_protected_mod_can_rise() -> None:
    # CRAFTED is the crafted "Suffixes Cannot Be Changed": it locks the suffix side, yet the Lightning Resistance suffix rises
    start = small_item(roll(RESIST_1), roll(CRAFTED, crafted=True), roll(LIFE_1, fractured=True), memory_strands=5)
    results = _results(ORB.outcomes(SMALL, start).given)
    assert results == {
        frozenset({RESIST_1, CRAFTED, LIFE_1}): 1 - P_RESIST,
        frozenset({RESIST_2, CRAFTED, LIFE_1}): P_RESIST * Fraction(2, 3),
        frozenset({RESIST_3, CRAFTED, LIFE_1}): P_RESIST * Fraction(1, 3),
    }
    for _, item in ORB.outcomes(SMALL, start).given.results:
        assert {(entry.mod_id, entry.fractured, entry.crafted) for entry in item.mods} >= {(CRAFTED, False, True), (LIFE_1, True, False)}


def test_crafted_fractured_and_top_mods_alone_leave_nothing_to_raise() -> None:
    # the gem level has one tier; the crafted lock and the fractured Life are never raised
    with pytest.raises(NotApplicableError, match="higher tier"):
        ORB.outcomes(SMALL, small_item(roll(GEM), roll(CRAFTED, crafted=True), roll(LIFE_1, fractured=True), memory_strands=50))


# --- refusals ------------------------------------------------------------------------------------------------


def test_zero_strands_is_refused() -> None:
    with pytest.raises(NotApplicableError, match="no Memory Strand"):
        ORB.outcomes(SMALL, small_item(roll(RESIST_1)))


def test_a_corrupted_item_is_refused() -> None:
    with pytest.raises(NotApplicableError, match="corrupted"):
        ORB.outcomes(SMALL, small_item(roll(RESIST_1), corrupted=True, memory_strands=5))


def test_an_unidentified_item_is_refused() -> None:
    """The model's unidentified item is the bought listing not opened yet (`Item.unopened`), whose mods are not known."""
    listing = Item.build(SMALL, base_id=AMULET, item_level=LEVEL, rarity=Rarity.NORMAL, unopened=True, memory_strands=5)
    with pytest.raises(NotApplicableError, match="not identified"):
        ORB.outcomes(SMALL, listing)


def test_an_item_with_no_eligible_mod_is_refused() -> None:
    with pytest.raises(NotApplicableError, match="higher tier"):
        ORB.outcomes(SMALL, small_item(roll(RESIST_3), roll(LIFE_2), memory_strands=50))


# --- the declarations and the catalog ------------------------------------------------------------------------


def test_the_declarations() -> None:
    use = ORB.strand_use(SMALL)
    assert not use.cuts and use.count_sets_odds and use.reads_count and use.changes_count
    assert use.claims == {"memory_strands.unravelling_effect"}
    assert ORB.resources() == {"Orb of Unravelling": 1}
    claims = ORB.claims(SMALL)
    for name in ("chance_model", "destination_tier", "limits", "ignores_metamods", "needs_identified_item", "skips_fractured_and_veiled"):
        assert f"memory_strands.unravelling_{name}" in claims
    assert {"orb_of_unravelling.cost", "orb_of_unravelling.raises_natural_mods_only"} <= claims
    assert get_rule("orb_of_unravelling.raises_natural_mods_only").approximate
    reads = ORB.reads(SMALL)
    assert reads.junk and {"LightningResistance", "IncreasedLife", "LightningDamage", "ManaLeech"} <= reads.by_mod
    assert not {"FireResistance", "ColdResistance", "GlobalDamageTypeGemLevel"} & reads.by_mod  # one tier: never raised, no name needed


def test_a_result_past_the_limit_is_refused_and_says_its_size(monkeypatch) -> None:
    import crafting_system.actions.unravelling as unravelling

    start = small_item(roll(RESIST_1), roll(DAMAGE_1), roll(LIFE_1), memory_strands=5)  # 3 x 2 x 2 = 12 items
    assert len(ORB.outcomes(SMALL, start).given.results) == 12
    monkeypatch.setattr(unravelling, "RESULTS_LIMIT", 11)
    with pytest.raises(OutOfScopeError, match="12 different items"):
        ORB.outcomes(SMALL, start)


def test_the_kind_is_named_as_the_route_files_name_it() -> None:
    assert "unravelling-orb" in {entry.name for entry in kinds()}
    assert kind_title("unravelling-orb") == "Orb of Unravelling"


def test_the_kind_needs_strands() -> None:
    item = small_item(roll(RESIST_1))
    assert not any(isinstance(action, OrbOfUnravelling) for action in catalog(SMALL, item))
    assert any(isinstance(action, OrbOfUnravelling) for action in catalog(SMALL, item, strands=True))
    assert any(isinstance(action, OrbOfUnravelling) for action in catalog(SMALL, small_item(roll(RESIST_1), memory_strands=3)))


# --- layer 1: the kernel equals the enumeration ----------------------------------------------------------------


def _enumerated(start: Item) -> list[tuple[Item, Fraction]]:
    """The finished items of the three-mod start at 5 strands, written from the numbers of the module docstring, each at count 0."""
    resist = [(RESIST_1, 1 - P_RESIST), (RESIST_2, P_RESIST * Fraction(2, 3)), (RESIST_3, P_RESIST * Fraction(1, 3))]
    damage = [(DAMAGE_1, 1 - P_DAMAGE), (DAMAGE_2, P_DAMAGE)]
    life = [(LIFE_1, 1 - P_LIFE), (LIFE_2, P_LIFE)]
    return [
        (small_item(roll(r), roll(d), roll(l), memory_strands=0), pr * pd * pl)
        for (r, pr), (d, pd), (l, pl) in product(resist, damage, life)
    ]


@pytest.mark.parametrize("goal", ["tier", "two_of_three", "nested"])
def test_the_kernel_equals_the_enumeration_on_three_mods(goal: str) -> None:
    ab = Abstraction(SMALL, GOALS[goal], AMULET, LEVEL, [ORB])
    start = small_item(roll(RESIST_1), roll(DAMAGE_1), roll(LIFE_1), memory_strands=5)
    kernel = ab.kernel(ab.compress(start), ORB)
    assert_same_distribution(kernel, compressed_distribution(_enumerated(start), ab.compress))
    assert sum(kernel.values()) == 1
    assert {state.strands for state in kernel} == {0}


def test_the_state_tells_the_tiers_apart() -> None:
    """Two items that differ only in the tier of a mod no requirement names are two states, since their kernels differ."""
    ab = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL, [ORB])
    low = ab.compress(small_item(roll(LIFE_1), memory_strands=5))
    high = ab.compress(small_item(roll(LIFE_2), memory_strands=5))
    assert low != high
