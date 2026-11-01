"""What the B1 actions declare about Memory Strands and what the contract does with it (ticket #276, ADR-0041).

"Done when" and where it is shown:

* the contract suite passes with `s`: `test_actions_contract.py` asks every kind about the stranded fixture items of
  `contract_fixtures_strands.py` and runs `check_strand_declarations` on them; the tests here add the table;
* `chance_all` equals an enumeration on a small pool for a cutting, spending action: `test_chance_all_equals_a_hand_enumeration_...`;
* the Chaos law is uniform on 0 to 50 (the amendment of ADR-0041 replaced the bins 45/27/25/21/12 of the first draft: claim
  `memory_strands.spend_law_uniform`): `test_the_chaos_and_alchemy_laws_are_uniform_on_0_to_50`;
* the Exalted ceilings follow the mods on the item before the craft: `test_the_exalted_ceilings_follow_the_mods_before_the_craft`;
* a spend larger than the count empties it: `test_a_spend_larger_than_the_count_empties_it`;
* a toy undeclared action is refused at `s = 1` and offered at `s = 0`: `test_a_toy_undeclared_action_is_refused_at_1_strand_and_offered_at_0`;
* a fossil at `s = 60` draws from the uncut pool: `test_a_fossil_at_60_strands_draws_from_the_uncut_pool`.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from abstraction_pool import COLD_RESIST, LIFE_1, RESIST_2, SMALL, small_item
from contract_support import CONTRACT_DATA, fixture_items

from crafting_system.actions import (
    Action,
    AlchemyOrb,
    AlterationOrb,
    AnnulmentOrb,
    ApplyFossils,
    AugmentationOrb,
    BenchCraft,
    ChaosOrb,
    DivineOrb,
    ExaltedOrb,
    FracturingOrb,
    HarvestQualityEnchant,
    Kind,
    OutOfScopeError,
    RegalOrb,
    RemoveCraftedMods,
    ScouringOrb,
    Spent,
    SpendLaw,
    StrandUse,
    TailoringOrb,
    TemperingOrb,
    TransmutationOrb,
    catalog,
    registered,
    strands_after,
)
from crafting_system.actions.catalog import kinds
from crafting_system.actions.cut import Cut
from crafting_system.actions.pool import build_pool, pool_candidates
from crafting_system.items import Rarity
from crafting_system.rules import rule_by_id

DATA = SMALL
ONE = Fraction(1)


def uniform(ceiling: int) -> dict[int, Fraction]:
    return {left: Fraction(1, ceiling + 1) for left in range(ceiling + 1)}


# --- the laws --------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "ceiling"),
    [
        (TransmutationOrb(), 8), (AlterationOrb(), 8), (AugmentationOrb(), 8), (RegalOrb(), 16),
        (AlchemyOrb(), 50), (ChaosOrb(), 50),
    ],
)  # fmt: skip
def test_the_basic_and_chaos_family_laws_are_the_uniform_ones_of_the_wiki_table(action, ceiling):
    use = action.strand_use(DATA)

    assert use.cuts is True and use.spend == SpendLaw.uniform(ceiling)
    assert dict(use.spend.after(100)) == {left: Fraction(1, ceiling + 1) for left in range(100 - ceiling, 101)}


def test_the_chaos_and_alchemy_laws_are_uniform_on_0_to_50():
    # The first draft of ADR-0041 had five measured bins for these two (45/27/25/21/12 for Chaos); its amendment of 2026-11-01
    # (claim `memory_strands.spend_law_uniform`) counted crafts instead of sheet rows and every law is uniform.
    for action in (ChaosOrb(), AlchemyOrb()):
        law = action.strand_use(DATA).spend

        assert law.ceiling() == 50
        assert dict(law.after(50)) == uniform(50)
        assert sum(law.after(80).values()) == 1 and min(law.after(80)) == 30 and set(law.after(80).values()) == {Fraction(1, 51)}
    assert rule_by_id("memory_strands.spend_law_uniform").value["shape"] == "uniform_integer"


def test_the_exalted_ceilings_follow_the_mods_before_the_craft():
    # the claim `memory_strands.spend_exalted_by_mod_count`: 16, 22, 26, 32, 34, 38 for 0 to 5 mods (the first five are the ticket's)
    law = ExaltedOrb().strand_use(DATA).spend

    assert [law.ceiling(mods) for mods in range(6)] == [16, 22, 26, 32, 34, 38]
    assert law.ceiling(9) == 38 and law.ceiling(-1) == 16
    for mods, ceiling in enumerate([16, 22, 26, 32, 34, 38]):
        assert dict(law.after(100, mods)) == {left: Fraction(1, ceiling + 1) for left in range(100 - ceiling, 101)}


def test_the_exalted_orb_reads_the_mods_on_the_item_it_is_used_on():
    items = {2: small_item(roll_of(RESIST_2), roll_of(LIFE_1), memory_strands=100), 4: fixture_items()["rare_four"]}
    for count, item in items.items():
        item = dataclasses.replace(item, memory_strands=100)
        after = strands_after(ExaltedOrb().outcomes(CONTRACT_DATA if count == 4 else DATA, item), 100)

        assert min(after) == 100 - [16, 22, 26, 32, 34, 38][len(item.mods)]


def roll_of(mod_id):
    from abstraction_pool import roll

    return roll(mod_id)


def test_essences_spend_0_to_80():
    from crafting_system.actions import ApplyEssence

    assert ApplyEssence("Screaming Essence of Greed").strand_use(None).spend == SpendLaw.uniform(80)


def test_every_declaration_cites_the_claims_it_rests_on_and_the_cut_cites_the_formula():
    for action in (TransmutationOrb(), AlterationOrb(), AugmentationOrb(), RegalOrb(), AlchemyOrb(), ChaosOrb(), ExaltedOrb()):
        claims = action.strand_claims(DATA)

        assert {"memory_strands.rollable_tiers", "memory_strands.spend_law_uniform", "memory_strands.weights_of_kept_tiers"} <= claims
        assert claims == action.strand_use(DATA).claims
        assert {rule_by_id(claim).id for claim in claims} == claims
    assert "memory_strands.spend_ranges_basic" in TransmutationOrb().strand_claims() and "memory_strands.spend_ranges_chaos_family" in ChaosOrb().strand_claims()
    assert "memory_strands.spend_exalted_by_mod_count" in ExaltedOrb().strand_claims()
    assert "memory_strands.annulment_keeps_strands" in AnnulmentOrb().strand_claims()
    assert "memory_strands.scouring_keeps_strands" in ScouringOrb().strand_claims()
    assert "memory_strands.divine_keeps_strands" in DivineOrb().strand_claims()


def test_the_strand_claims_stay_out_of_claims_so_no_answer_without_strands_lists_them():
    for action in (TransmutationOrb(), AlterationOrb(), AugmentationOrb(), RegalOrb(), AlchemyOrb(), ChaosOrb(), ExaltedOrb(), AnnulmentOrb()):
        assert not {claim for claim in action.claims(DATA) if claim.startswith(("memory_strands.", "foulborn."))}, action
        assert "affix_pool.no_memory_strands" not in action.claims(DATA)


def test_the_table_of_the_actions_that_neither_cut_nor_spend():
    for action in (
        AnnulmentOrb(), ScouringOrb(), DivineOrb(), FracturingOrb(), RemoveCraftedMods(), ApplyFossils(("Aetheric Fossil",)),
        TemperingOrb(), TailoringOrb(), HarvestQualityEnchant(),
    ):  # fmt: skip
        use = action.strand_use(CONTRACT_DATA)

        assert use == StrandUse.untouched(*(rule_by_id(claim) for claim in use.claims)) and use.claims
        assert use.cuts is False and use.spend is None and not use.reads_count and not use.changes_count
    assert StrandUse.cutting(SpendLaw.uniform(8)).reads_count and StrandUse.cutting(SpendLaw.uniform(8)).changes_count


# --- the spend -------------------------------------------------------------------------------------------------------------


def test_a_spend_larger_than_the_count_empties_it():
    law = SpendLaw.uniform(8)

    assert dict(law.after(3)) == {0: Fraction(6, 9), 1: Fraction(1, 9), 2: Fraction(1, 9), 3: Fraction(1, 9)}
    assert dict(law.after(0)) == {0: ONE}
    assert dict(law.after(8)) == uniform(8)  # a spend of exactly the count empties it too
    assert dict(law.after(9)) == {left: Fraction(1, 9) for left in range(1, 10)}  # from 9, a spend of 8 leaves 1: only a larger count keeps some
    assert min(law.after(1)) == 0 and sum(law.after(1).values()) == 1
    rng = random.Random(7)
    assert {law.sample_after(rng, 3) for _ in range(400)} == {0, 1, 2, 3}  # never below 0, and 0 is reached

    item = small_item(roll_of(LIFE_1), rarity=Rarity.MAGIC, memory_strands=3)
    outcomes = AugmentationOrb().outcomes(DATA, item)
    assert isinstance(outcomes, Spent) and dict(outcomes.strands_after) == dict(law.after(3))
    left = {outcomes.sample(rng).memory_strands for _ in range(400)}
    assert left == {0, 1, 2, 3}


def test_the_count_changes_only_by_the_spend_after_the_cut_that_used_the_count_before():
    # one strand: the cut is the cut of 1 strand; the craft then spends 0 to 8 of it
    item = small_item(roll_of(LIFE_1), rarity=Rarity.MAGIC, memory_strands=1)
    outcomes = AugmentationOrb().outcomes(DATA, item)

    assert dict(outcomes.strands_after) == {0: Fraction(8, 9), 1: Fraction(1, 9)}
    assert outcomes.pool == build_pool(DATA, outcomes.retained, cut=Cut(1))
    assert outcomes.pool != build_pool(DATA, outcomes.retained)


def test_the_result_at_0_strands_is_the_draw_itself_and_is_not_wrapped():
    item = small_item(roll_of(LIFE_1), rarity=Rarity.MAGIC)
    outcomes = AugmentationOrb().outcomes(DATA, item)

    assert not isinstance(outcomes, Spent) and strands_after(outcomes, 0) == {0: ONE}
    assert outcomes.pool == build_pool(DATA, outcomes.retained)


def test_a_subclass_that_calls_super_is_wrapped_once():
    @dataclasses.dataclass(frozen=True)
    class Twice(RegalOrb):
        def outcomes(self, data, item):
            return super().outcomes(data, item)

    item = small_item(roll_of(LIFE_1), rarity=Rarity.MAGIC, memory_strands=40)
    outcomes = Twice().outcomes(DATA, item)

    assert isinstance(outcomes, Spent) and not isinstance(outcomes.given, Spent)
    assert dict(outcomes.strands_after) == dict(SpendLaw.uniform(16).after(40))


# --- the cut ---------------------------------------------------------------------------------------------------------------


def hand_cut_pool(item, strands):
    """The pool of `item` after a cut by the integer formula and the refactored weight, written again here by hand.

    For each mod type (a tier table) of the uncut pool: T tiers (distinct required levels), K = 200 (T - 1) // (295 + 5 s) + 1 of them
    kept from the top, each kept weight times T / K.
    """
    base = [(c.mod, c.weight, c.family, c.side.value) for c in pool_candidates(DATA, item)]
    tables: dict[str, set[int]] = {}
    for mod, _, _, _ in base:
        tables.setdefault(mod.type, set()).add(mod.required_level)
    entries = []
    for mod, weight, family, side in base:
        levels = sorted(tables[mod.type], reverse=True)
        tiers, kept = len(levels), 200 * (len(levels) - 1) // (295 + 5 * strands) + 1
        if mod.required_level >= levels[kept - 1]:
            entries.append((mod.id, family, side, weight * Fraction(tiers, kept)))
    return entries


def hand_sets(entries, cap, picks, present=frozenset(), taken=frozenset()):
    """The chance of each set of mod ids that `picks` draws leave, by listing every order: the pool of both sides, a family once, `cap` per side."""
    if picks == 0:
        return {frozenset(): ONE}
    open_entries = [e for e in entries if e[1] not in present and sum(1 for t in taken if t[1] == e[2]) < cap]
    total = sum(e[3] for e in open_entries)
    if not total:
        return {frozenset(): ONE}
    result: dict[frozenset, Fraction] = {}
    for mod_id, family, side, weight in open_entries:
        for rest, chance in hand_sets(entries, cap, picks - 1, present | {family}, taken | {(mod_id, side)}).items():
            key = rest | {mod_id}
            result[key] = result.get(key, Fraction(0)) + weight / total * chance
    return result


@pytest.mark.parametrize("strands", [1, 21, 22, 30, 100])
def test_chance_all_equals_a_hand_enumeration_on_a_small_pool_for_a_cutting_spending_action(strands):
    # Transmutation: a normal item becomes magic with 1 or 2 mods, 1/2 each; one prefix and one suffix at most
    item = small_item(rarity=Rarity.NORMAL, memory_strands=strands)
    entries = hand_cut_pool(item, strands)
    expected: dict[str, Fraction] = {}
    for picks in (1, 2):
        for drawn, chance in hand_sets(entries, 1, picks).items():
            for mod_id in drawn:
                expected[mod_id] = expected.get(mod_id, Fraction(0)) + chance / 2

    outcomes = TransmutationOrb().outcomes(DATA, item)

    assert isinstance(outcomes, Spent)
    for mod_id in DATA.mods:
        assert outcomes.chance_all([mod_id]) == expected.get(mod_id, Fraction(0)), mod_id
    assert dict(outcomes.strands_after) == dict(SpendLaw.uniform(8).after(strands))
    assert expected  # the cut at 100 strands keeps the top tier of each table only
    if strands >= 22:
        assert expected.get("LightningResist1", 0) == 0 and expected.get("LightningResist2", 0) == 0 and expected["LightningResist3"] > 0


def test_the_cut_at_21_strands_keeps_two_of_three_tiers_and_at_22_one():
    # 3 tiers: K = floor(400 / (295 + 5 s)) + 1; 400 / 400 = 1 exactly at 21 strands, so 2 tiers; 400 / 405 < 1 at 22
    item = small_item(roll_of(LIFE_1), rarity=Rarity.MAGIC)
    for strands, kept in ((20, 2), (21, 2), (22, 1)):
        outcomes = AugmentationOrb().outcomes(DATA, dataclasses.replace(item, memory_strands=strands))
        resists = {entry.mod.id for family in outcomes.pool for entry in family.mods if entry.mod.type == "LightningResistance"}

        assert len(resists) == kept, strands


def test_a_cut_draw_is_exactly_the_cut_pool_of_the_count_before_the_craft():
    item = small_item(rarity=Rarity.RARE, memory_strands=100)
    outcomes = ChaosOrb().outcomes(DATA, item)

    assert outcomes.pool == build_pool(DATA, outcomes.retained, cut=Cut(100))
    assert outcomes.pool != build_pool(DATA, outcomes.retained)


@pytest.mark.parametrize(
    ("action", "rarity", "mods"),
    [
        (TransmutationOrb(), Rarity.NORMAL, ()), (AlchemyOrb(), Rarity.NORMAL, ()), (AlterationOrb(), Rarity.MAGIC, (LIFE_1,)),
        (AugmentationOrb(), Rarity.MAGIC, (LIFE_1,)), (RegalOrb(), Rarity.MAGIC, (LIFE_1,)), (ChaosOrb(), Rarity.RARE, (LIFE_1, RESIST_2)),
        (ExaltedOrb(), Rarity.RARE, (LIFE_1, RESIST_2)),
    ],
)  # fmt: skip
def test_every_cutting_action_draws_from_the_cut_pool_of_its_count(action, rarity, mods):
    item = small_item(*(roll_of(mod_id) for mod_id in mods), rarity=rarity, memory_strands=60)

    outcomes = action.outcomes(DATA, item)

    assert outcomes.pool == build_pool(DATA, outcomes.retained, cut=Cut(60))
    assert outcomes.pool != build_pool(DATA, outcomes.retained)


def test_an_essence_draws_its_random_mods_from_the_cut_pool_under_its_level_cap_and_its_forced_mod_is_not_cut():
    from crafting_system.actions import ApplyEssence
    from crafting_system.actions.errors import ActionError

    item = fixture_items()["normal_stranded"]
    checked = capped = 0
    for action in (member for entry in kinds() if entry.name == "essence" for member in entry.members(CONTRACT_DATA, item)):
        try:
            outcomes = action.outcomes(CONTRACT_DATA, item)
        except ActionError:
            continue
        assert isinstance(action, ApplyEssence)
        cap = action._record(CONTRACT_DATA).item_level_restriction if action._record(CONTRACT_DATA).level <= 4 else None
        assert outcomes.pool == build_pool(CONTRACT_DATA, outcomes.retained, cap, cut=Cut(45)), action
        assert outcomes.forced in {entry.mod_id for entry in outcomes.retained.mods}  # the forced mod sits on the item, outside the pool
        checked += 1
        capped += cap is not None
    assert checked and capped  # at least one essence of each kind applied to the stranded normal item


def test_a_fossil_at_60_strands_draws_from_the_uncut_pool():
    base = fixture_items()["rare_junk"]
    stranded = dataclasses.replace(base, memory_strands=60)
    fossils = next(action for action in catalog(CONTRACT_DATA, base, names={"fossil-set"}) if isinstance(action, ApplyFossils))

    outcomes = fossils.outcomes(CONTRACT_DATA, stranded)

    assert not isinstance(outcomes, Spent) and strands_after(outcomes, 60) == {60: ONE}
    plain = fossils.outcomes(CONTRACT_DATA, base)
    assert [part.pool for _, part in outcomes.components] == [part.pool for _, part in plain.components]
    assert dict(outcomes.distribution(lambda mod: mod.id)) == dict(plain.distribution(lambda mod: mod.id))


def test_an_action_that_neither_cuts_nor_spends_gives_the_same_mods_and_keeps_the_count():
    rare = fixture_items()["rare_junk"]
    stranded = dataclasses.replace(rare, memory_strands=77)
    for action in (AnnulmentOrb(), ScouringOrb(), FracturingOrb(), DivineOrb()):
        try:
            outcomes = action.outcomes(CONTRACT_DATA, stranded)
        except Exception:  # the game refuses it here, as at 0 strands (the contract suite compares the refusals)
            continue
        assert not isinstance(outcomes, Spent) and strands_after(outcomes, 77) == {77: ONE}
        assert all(finished.memory_strands == 77 for finished in (outcomes.sample(random.Random(seed)) for seed in range(20)))


# --- an action that has declared nothing ------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ToyReroll(Action):
    """A toy: erases the mods and adds nothing; it declares nothing about Memory Strands."""

    def label(self, data=None) -> str:
        return "Toy Reroll"

    def resources(self, data=None):
        return {"Toy Orb": 1}

    def outcomes(self, data, item):
        return AugmentationOrb().outcomes(data, item)  # any result will do: the guard is around `outcomes` itself


def _toy_members(data, item):
    yield ToyReroll()


def test_a_toy_undeclared_action_is_refused_at_1_strand_and_offered_at_0():
    magic = small_item(roll_of(LIFE_1), rarity=Rarity.MAGIC)
    with registered(Kind("toy-undeclared", _toy_members, order=950, planner=False, why_not="a toy")):
        assert ToyReroll() in catalog(DATA, magic)  # offered at 0 strands...
        assert ToyReroll().strand_use(DATA) is None and ToyReroll().strand_claims(DATA) == frozenset()
        assert ToyReroll().outcomes(DATA, magic).chance_all([COLD_RESIST]) > 0  # ...and works there as it always did
        one = dataclasses.replace(magic, memory_strands=1)
        with pytest.raises(OutOfScopeError, match="Toy Reroll has not declared what it does with Memory Strands"):
            ToyReroll().outcomes(DATA, one)  # ...and refused at 1
        with pytest.raises(OutOfScopeError):
            ToyReroll().outcomes_under(DATA, dataclasses.replace(magic, memory_strands=100))


def test_the_restart_is_not_refused_on_a_stranded_item_and_brings_back_the_start_item_with_its_own_count():
    from crafting_system.cli._offers import BuyStartItem

    start = small_item(roll_of(LIFE_1), rarity=Rarity.MAGIC, memory_strands=12)
    current = dataclasses.replace(start, memory_strands=90)

    assert BuyStartItem(start).outcomes(DATA, current).sample(random.Random(1)).memory_strands == 12
    assert BuyStartItem(start).strand_use(DATA) == StrandUse.untouched()


def test_the_toy_is_gone_with_its_registration():
    assert "toy-undeclared" not in {entry.name for entry in kinds()}


def test_a_declared_toy_is_run_and_spends_by_its_law():
    @dataclasses.dataclass(frozen=True)
    class DeclaredToy(ToyReroll):
        def strand_use(self, data=None):
            return StrandUse.cutting(SpendLaw.uniform(5), rule_by_id("memory_strands.spend_ranges_basic"))

    magic = small_item(roll_of(LIFE_1), rarity=Rarity.MAGIC, memory_strands=9)
    outcomes = DeclaredToy().outcomes(DATA, magic)

    assert isinstance(outcomes, Spent) and dict(outcomes.strands_after) == dict(SpendLaw.uniform(5).after(9))
    assert min(outcomes.strands_after) == 4 and max(outcomes.strands_after) == 9
    # the toy returns the result of an Augmentation Orb (already a Spent of 8): the spend is the toy's own declaration, applied once
    assert not isinstance(outcomes.given, Spent)
