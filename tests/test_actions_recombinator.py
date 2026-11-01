"""The recombinator as an exact two-input action (ticket #215, ADR-0033).

Done when: the contract suite passes at every grid point of the selection exponent (it runs on every kind of the catalog and the kind is
found on the fixture items; the grid is checked here on explicit donors too); `chance_all` equals exhaustive enumeration of the successive
draws (`recombinator_oracle.py`) on pools of up to 6 mods per side; the #175 example (a weight-25 mod in 25/1000/1000/400, count row 4)
gives 3.8% at alpha 1 and 55% at the off-grid alpha 0 under the wiki's row 4 (54.95% under the guide's once its row is renormalised; 55.5% is the unrenormalised 222/400); the count table sums to 1 per row
after renormalising. The rest checks the rules one at a time.
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_pool import LIFE_1, MANA_1
from contract_support import CONTRACT_DATA, GOAL as CONTRACT_GOAL, check_action, contract_pairs, fixture_items
from items_support import AMULET
from recombinator_oracle import chance_of_holding, distribution

from crafting_system.actions import (
    NotApplicableError,
    OutOfScopeError,
    Reading,
    Recombinator,
    kinds,
    model_readings,
)
from crafting_system.actions.recombinator import ALPHA_AXIS, TABLES, count_table
from crafting_system.data import BaseItem, Weight
from crafting_system.items import ExplicitMod, Influence, Item, Rarity
from crafting_system.rules import rule_by_id

GRID = (Fraction(2, 5), Fraction(7, 10), Fraction(1), Fraction(13, 10), Fraction(8, 5))
ALPHA = "recombinator.alpha"

# the guide's table and the wiki's, typed by hand from the research note (percent; the claim is checked against them)
GUIDE = {1: {0: 41, 1: 59}, 2: {1: 67, 2: 33}, 3: {1: 39, 2: 52, 3: 10}, 4: {1: 11, 2: 59, 3: 31}, 5: {2: 43, 3: 57}, 6: {2: 28, 3: 72}}
WIKI = {1: {0: 41, 1: 59}, 2: {1: 66.7, 2: 33.3}, 3: {1: 40, 2: 50, 3: 10}, 4: {1: 10, 2: 60, 3: 30}, 5: {2: 43, 3: 57}, 6: {2: 30, 3: 70}}

# --- a small world: twelve plain mods of known weights, a mod only the first base can roll, two bases of one class ---------------------

PREFIX_WEIGHTS = {"RP25": 25, "RP1000a": 1000, "RP1000b": 1000, "RP400": 400, "RP700": 700, "RP250": 250}
SUFFIX_WEIGHTS = {"RS1000": 1000, "RS500": 500, "RS250": 250, "RS800": 800, "RS600": 600, "RS1200": 1200}
ONLY_A = "RPOnlyA"  # a prefix that spawns on the tag only the first base has
VEILED = "RPVeiled"  # a veiled placeholder prefix
TIER2 = "RP25T2"  # a second tier of the family of RP25
ESSENCE = "RSEssence"  # an essence-only suffix: exclusive
BASE_A = "Metadata/Items/Amulets/RecombA"
BASE_JEWEL = "Metadata/Items/Jewels/RecombJewel"


def _world():
    prefix, suffix = CONTRACT_DATA.mods[LIFE_1], CONTRACT_DATA.mods[MANA_1]
    mods = dict(CONTRACT_DATA.mods)

    def add(mod_id, template, tag, weight, **fields):
        mods[mod_id] = dataclasses.replace(
            template, id=mod_id, type=mod_id, families=(mod_id,), required_level=1, spawn_weights=(Weight(tag, weight), Weight("default", 0)), **fields
        )

    for mod_id, weight in PREFIX_WEIGHTS.items():
        add(mod_id, prefix, "amulet", weight)
    for mod_id, weight in SUFFIX_WEIGHTS.items():
        add(mod_id, suffix, "amulet", weight)
    add(ONLY_A, prefix, "only_a", 600)
    add(TIER2, prefix, "amulet", 100)
    mods[TIER2] = dataclasses.replace(mods[TIER2], families=("RP25",))
    add(VEILED, prefix, "amulet", 0, domain="veiled")
    add(ESSENCE, suffix, "amulet", 0, is_essence_only=True)
    bases = dict(CONTRACT_DATA.base_items)
    plain = bases[AMULET]
    bases[BASE_A] = dataclasses.replace(plain, id=BASE_A, tags=(*plain.tags, "only_a"))
    bases[BASE_JEWEL] = BaseItem(BASE_JEWEL, "Test Jewel", "Jewel", "item", 1, ("jewel", "default"), (), "released")
    return dataclasses.replace(CONTRACT_DATA, mods=mods, base_items=bases)


DATA = _world()


def roll(mod_id: str, **flags) -> ExplicitMod:
    return ExplicitMod(mod_id, 1, tuple(min(stat.min, stat.max) for stat in DATA.mods[mod_id].stats), **flags)


def make(mod_ids, rarity=Rarity.RARE, base=AMULET, level=84, flags=None, **fields) -> Item:
    flags = flags or {}
    return Item.build(DATA, base_id=base, item_level=level, rarity=rarity, mods=tuple(roll(m, **flags.get(m, {})) for m in mod_ids), **fields)


def held(outcomes, mod_id: str) -> Fraction:
    return outcomes.chance_all([mod_id])


def finished(outcomes):
    return {item: chance for chance, item in ((c, r) for c, r in outcomes.results)}


# --- the count table -----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["guide", "wiki"])
def test_the_count_table_sums_to_one_per_row_after_renormalising(name):
    table = count_table(name)
    assert set(table) == {0, 1, 2, 3, 4, 5, 6}
    for pooled, row in table.items():
        assert sum(row.values()) == 1, (name, pooled)
        assert all(chance > 0 for chance in row.values())
    assert table[0] == {0: 1}


def test_rows_three_and_four_of_the_guide_sum_to_101_in_print_and_are_renormalised():
    printed = {pooled: sum(row.values()) for pooled, row in rule_by_id("recombinator.count_table").value.items()}
    assert printed == {1: 100, 2: 100, 3: 101, 4: 101, 5: 100, 6: 100}
    assert count_table("guide")[4] == {1: Fraction(11, 101), 2: Fraction(59, 101), 3: Fraction(31, 101)}


@pytest.mark.parametrize("name,typed", [("guide", GUIDE), ("wiki", WIKI)])
def test_the_claims_hold_the_tables_of_the_research_note(name, typed):
    claim = rule_by_id(f"recombinator.count_table{'_wiki' if name == 'wiki' else ''}")
    assert {pooled: dict(row) for pooled, row in claim.value.items()} == typed
    assert claim.approximate and claim.approximate_reason


def test_the_sample_sizes_of_the_guide_travel_with_the_claim():
    events = rule_by_id("recombinator.count_table_sample_sizes").value
    assert {pooled: sum(row) for pooled, row in events.items()} == {1: 217, 2: 280, 3: 321, 4: 424, 5: 345, 6: 301}


def test_the_axis_is_the_grid_of_adr_0033_with_the_plan_at_one():
    assert ALPHA_AXIS.name == ALPHA and ALPHA_AXIS.readings == GRID and ALPHA_AXIS.plan == 1
    assert rule_by_id("recombinator.selection_weighted_formula_unknown").approximate
    assert set(TABLES) == {"guide", "wiki"}


# --- the #175 example ----------------------------------------------------------------------------------------------------------------


def _example(table: str) -> Recombinator:
    donor = make(["RP1000b", "RP400"])
    return Recombinator(donor, table)


@pytest.mark.parametrize(
    "table,alpha,expected,places",
    [
        ("wiki", 1, 0.038, 0.0005),
        ("wiki", 0, 0.55, 0.005),
        ("guide", 0, 222 / 404, 1e-9),  # 55.5% when the row is left at 101 (222 / 400); renormalised it is 54.95%
        ("wiki", Fraction(1, 2), 0.17, 0.005),
    ],
)
def test_the_rare_mod_of_the_175_example(table, alpha, expected, places):
    item = make(["RP25", "RP1000a"])
    outcomes = _example(table).outcomes_under(DATA, item, Reading.of({ALPHA: Fraction(alpha)}))
    assert float(held(outcomes, "RP25")) == pytest.approx(expected, abs=places)


def test_the_175_example_matches_the_oracle_exactly():
    item = make(["RP25", "RP1000a"])
    donor = _example("wiki").donor
    for alpha in (Fraction(1), Fraction(0)):
        outcomes = _example("wiki").outcomes_under(DATA, item, Reading.of({ALPHA: alpha}))
        assert held(outcomes, "RP25") == chance_of_holding(DATA, item, donor, alpha, WIKI, {"RP25"})


def test_a_hand_figure_two_prefixes_one_on_each_magic_input():
    # pooled prefix count 2: one kept 67%, both 33% (guide); the suffix pool is empty. At alpha 1 the 250 mod is the one kept with
    # chance 250 / (250 + 1000) when one is kept: P = 33/100 + 67/100 * 1/5
    item, donor = make(["RP250"], Rarity.MAGIC), make(["RP1000a"], Rarity.MAGIC)
    outcomes = Recombinator(donor).outcomes(DATA, item)
    assert held(outcomes, "RP250") == Fraction(33, 100) + Fraction(67, 100) * Fraction(1, 5)
    assert held(outcomes, "RP1000a") == Fraction(33, 100) + Fraction(67, 100) * Fraction(4, 5)
    flat = Recombinator(donor).outcomes_under(DATA, item, Reading.of({ALPHA: Fraction(0)}))
    assert held(flat, "RP250") == Fraction(33, 100) + Fraction(67, 100) * Fraction(1, 2)


# --- chance_all equals exhaustive enumeration ----------------------------------------------------------------------------------------

SIX_EACH_A = ["RP25", "RP1000a", "RP400", "RS1000", "RS500", "RS250"]
SIX_EACH_B = ["RP1000b", "RP700", "RP250", "RS800", "RS600", "RS1200"]
SCENARIOS = {
    # three prefixes and three suffixes on each input: 6 pooled on each side
    "six_and_six": (make(SIX_EACH_A), make(SIX_EACH_B)),
    # doubling: the same mods on both inputs, and a family shared between two tiers of different inputs
    "doubled": (make(["RP25", "RP1000a", "RS500", "RS250"]), make(["RP25", "RP400", "RS500", "RS800"])),
    # two tiers of one mod group on different inputs: either one enters the pool, and picking one closes the other
    "tiers": (make(["RP25", "RP1000a", "RS500"]), make([TIER2, "RP400", "RS250"])),
    # magic inputs: one prefix and one suffix each
    "magic_pair": (make(["RP25", "RS500"], Rarity.MAGIC), make(["RP1000a", "RS250"], Rarity.MAGIC)),
    # one mod on each input, on opposite sides: 1p, 1s or 1p1s
    "one_each": (make(["RP25"], Rarity.MAGIC), make(["RS500"], Rarity.MAGIC)),
    # an exclusive (essence-only) suffix on each input and a crafted one: at most one exclusive stays
    "exclusive": (make(["RP250", "RP700", "RS500", ESSENCE]), make(["RP25", "RS800", ESSENCE])),
    # a crafted suffix on each input: exclusive too
    "crafted": (
        make(["RP250", "RP700", "ContractCraftCold"], flags={"ContractCraftCold": {"crafted": True}}),
        make(["RP25", "RS800", "ContractCraftFire"], flags={"ContractCraftFire": {"crafted": True}}),
    ),
    # a mod only the first base can roll: it counts in the pool and cannot appear when the second base is chosen
    "non_native": (make(["RP25", ONLY_A], base=BASE_A), make(["RP1000a", "RP400", "RS500"])),
    # a fractured mod counts always and is eligible on its own base only
    "fractured": (make(["RP25", "RP1000a", "RS500"], flags={"RP25": {"fractured": True}}), make(["RP1000b", "RS250", "RS800"])),
}


CASES = [(name, "guide", alpha) for name in SCENARIOS if name != "six_and_six" for alpha in (Fraction(1), Fraction(0), Fraction(7, 10))]
CASES += [("six_and_six", "guide", alpha) for alpha in (Fraction(1), Fraction(7, 10))]
CASES += [("doubled", "guide", alpha) for alpha in (Fraction(2, 5), Fraction(13, 10), Fraction(8, 5), Fraction(2))]
CASES += [(name, "wiki", Fraction(1)) for name in ("doubled", "six_and_six", "exclusive")]


@pytest.mark.parametrize("name,table,alpha", CASES, ids=lambda case: str(case))
def test_the_distribution_equals_the_exhaustive_enumeration(name, table, alpha):
    item, donor = SCENARIOS[name]
    outcomes = Recombinator(donor, table).outcomes_under(DATA, item, Reading.of({ALPHA: alpha}))
    expected = distribution(DATA, item, donor, alpha, GUIDE if table == "guide" else WIKI)
    mods = sorted({mod.mod_id for given in (item, donor) for mod in given.mods})
    for mod_id in mods:
        assert held(outcomes, mod_id) == sum((c for kept, c in expected.items() if mod_id in {m for _, m in kept}), Fraction(0)), mod_id
    # the whole law of the kept sets, not only the marginals
    got: dict = {}
    for chance, result in ((c, r) for c, r in outcomes.results):
        key = frozenset(entry.mod_id for entry in result.mods)
        got[key] = got.get(key, 0) + chance
    law: dict = {}
    for kept, chance in expected.items():
        key = frozenset(mod_id for _, mod_id in kept)
        law[key] = law.get(key, 0) + chance
    assert got == law
    assert sum(law.values()) == 1


def test_pairs_and_triples_of_mods_equal_the_enumeration_on_six_and_six():
    item, donor = SCENARIOS["six_and_six"]
    alpha = Fraction(1)
    outcomes = Recombinator(donor).outcomes_under(DATA, item, Reading.of({ALPHA: alpha}))
    expected = distribution(DATA, item, donor, alpha, GUIDE)
    for wanted in (
        {"RP25", "RP1000b"},
        {"RP25", "RS250"},
        {"RP1000a", "RP400", "RP700"},
        {"RP25", "RP400", "RP1000b", "RS500", "RS1200"},
        {"RS1000", "RS800", "RS1200"},
    ):
        assert outcomes.chance_all(wanted) == sum((c for kept, c in expected.items() if wanted <= {m for _, m in kept}), Fraction(0)), wanted


# --- the contract suite at every grid point --------------------------------------------------------------------------------------------


def test_the_kind_is_found_by_the_catalog_and_applies_on_fixture_items():
    assert "recombinator" in {entry.name for entry in kinds()}
    assert "recombinator" not in {entry.name for entry in kinds(planner_only=True)}
    applied = []
    for kind, action, name in contract_pairs():
        if kind != "recombinator":
            continue
        try:
            action.outcomes(CONTRACT_DATA, fixture_items()[name])
        except (NotApplicableError, OutOfScopeError):
            continue
        applied.append(name)
    assert {"rare_four", "rare_junk"} <= set(applied)


def test_there_are_five_readings_the_plan_first():
    readings = model_readings(DATA, [Recombinator(make(["RP25"], Rarity.MAGIC))])
    assert [reading[ALPHA] for reading in readings] == [Fraction(1), *[g for g in GRID if g != 1]]


CONTRACT_CASES = {
    "pair_of_rares": SCENARIOS["doubled"],
    "magic_pair": SCENARIOS["magic_pair"],
    "one_each": SCENARIOS["one_each"],
    "exclusive": SCENARIOS["exclusive"],
    # a Shaper prefix on the first input only: it cannot appear when the plain donor is the base (the influence goes with the base)
    "non_native": (
        Item.build(
            DATA,
            base_id=AMULET,
            item_level=84,
            rarity=Rarity.RARE,
            mods=(roll("ContractShaperPrefix1"), roll("RP25"), roll("RS500")),
            influences=frozenset({Influence.SHAPER}),
        ),
        make(["RP1000a", "RP400", "RS250"]),
    ),
    "fractured": SCENARIOS["fractured"],
    "three_and_three": (make(["RP25", "RP1000a", "RS500"]), make(["RP1000b", "RP400", "RS250"])),
}


@pytest.mark.parametrize("name", list(CONTRACT_CASES))
def test_the_contract_suite_passes_at_every_grid_point(name):
    item, donor = CONTRACT_CASES[name]
    action = Recombinator(donor)
    assert len(model_readings(DATA, [action])) == 5
    assert check_action(action, item, data=DATA)


def test_a_result_on_another_base_has_no_state_so_the_kernel_refuses_it():
    from crafting_system.abstraction import Abstraction

    item, donor = SCENARIOS["non_native"]  # the first input is on another base than the donor
    action = Recombinator(donor)
    ab = Abstraction(DATA, CONTRACT_GOAL, item.base_id, item.item_level, [action])
    with pytest.raises(OutOfScopeError, match="another base"):
        ab.kernel(ab.compress(item), action)


def test_the_contract_suite_passes_on_the_wiki_table_too():
    item, donor = CONTRACT_CASES["pair_of_rares"]
    assert check_action(Recombinator(donor, "wiki"), item, data=DATA)


# --- the rules one at a time ---------------------------------------------------------------------------------------------------------


def test_any_exponent_is_accepted_not_only_the_grid_and_the_plan_is_alpha_one():
    item, donor = SCENARIOS["magic_pair"]
    action = Recombinator(donor)
    plain = finished(action.outcomes(DATA, item))
    assert plain == finished(action.outcomes_under(DATA, item, Reading.of({ALPHA: Fraction(1)})))
    assert plain == finished(action.outcomes_under(DATA, item, Reading()))
    assert finished(action.outcomes_under(DATA, item, Reading.of({ALPHA: Fraction(0)}))) != plain
    action.outcomes_under(DATA, item, Reading.of({ALPHA: 0.5}))  # a float is a number too
    for bad in ("heavy", float("inf"), float("nan"), 10**9):
        with pytest.raises(ValueError):
            action.outcomes_under(DATA, item, Reading.of({ALPHA: bad}))


def test_a_higher_exponent_favours_the_heavy_mod_more():
    item = make(["RP25", "RP1000a"])
    action = _example("guide")
    chances = [held(action.outcomes_under(DATA, item, Reading.of({ALPHA: alpha})), "RP25") for alpha in (Fraction(0), *GRID)]
    assert chances == sorted(chances, reverse=True)


def test_the_item_level_is_the_average_plus_two_capped_at_the_higher():
    def level_of(a, b):
        item, donor = make(["RP25"], Rarity.MAGIC, level=a), make(["RP1000a"], Rarity.MAGIC, level=b)
        return {result.item_level for result in finished(Recombinator(donor).outcomes(DATA, item))}

    assert level_of(100, 1) == {52}
    assert level_of(84, 79) == {83}
    assert level_of(84, 84) == {84}
    assert level_of(70, 70) == {70}


def test_the_output_copies_the_base_and_each_input_is_the_base_half_the_time():
    item = make(["RP25", "RP1000a"], influences=frozenset({Influence.SHAPER}))
    donor = make(["RP25", "RP1000a"])
    outcomes = Recombinator(donor).outcomes(DATA, item)
    by_influence = {}
    for result, chance in finished(outcomes).items():
        by_influence[result.influences] = by_influence.get(result.influences, 0) + chance
    assert by_influence == {frozenset({Influence.SHAPER}): Fraction(1, 2), frozenset(): Fraction(1, 2)}


def test_the_output_takes_the_base_type_of_the_chosen_input():
    item = make(["RP25", ONLY_A], base=BASE_A)
    donor = make(["RP1000a", "RP400", "RS500"])
    bases = {}
    for result, chance in finished(Recombinator(donor).outcomes(DATA, item)).items():
        bases[result.base_id] = bases.get(result.base_id, 0) + chance
    assert bases == {BASE_A: Fraction(1, 2), AMULET: Fraction(1, 2)}


def test_a_non_native_mod_counts_in_the_pool_but_never_appears_on_the_other_base():
    item = make(["RP25", ONLY_A], base=BASE_A)
    donor = make(["RP1000a", "RP400"])
    for result in finished(Recombinator(donor).outcomes(DATA, item)):
        if result.base_id == AMULET:
            assert ONLY_A not in {entry.mod_id for entry in result.mods}
    assert held(Recombinator(donor).outcomes(DATA, item), ONLY_A) > 0
    # it still raised the pooled prefix count to 4: on the donor's base it kept at most 3 of the other 3, and the rows differ
    plain = make(["RP25"], Rarity.MAGIC, base=BASE_A)
    assert held(Recombinator(donor).outcomes(DATA, plain), "RP25") != held(Recombinator(donor).outcomes(DATA, item), "RP25")


def test_a_fractured_mod_is_eligible_only_on_its_own_base_and_stays_fractured():
    item = make(["RP25", "RP1000a"], flags={"RP25": {"fractured": True}})
    donor = make(["RP1000b", "RP400"])
    for result, chance in finished(Recombinator(donor).outcomes(DATA, item)).items():
        assert all(not entry.fractured or entry.mod_id == "RP25" for entry in result.mods)
    fractured_kept = sum(c for r, c in finished(Recombinator(donor).outcomes(DATA, item)).items() if any(e.fractured for e in r.mods))
    assert 0 < fractured_kept <= Fraction(1, 2)  # only when the item in hand is the base


def test_at_most_one_exclusive_mod_stays():
    item, donor = SCENARIOS["exclusive"]
    outcomes = Recombinator(donor).outcomes(DATA, item)
    for result in finished(outcomes):
        assert sum(1 for entry in result.mods if entry.mod_id == ESSENCE) <= 1
    crafted_a, crafted_b = SCENARIOS["crafted"]
    for result in finished(Recombinator(crafted_b).outcomes(DATA, crafted_a)):
        assert sum(1 for entry in result.mods if entry.crafted) <= 1


def test_a_mod_group_closes_when_one_of_it_is_picked():
    item = make(["RP25", "RS500"], Rarity.MAGIC)
    # the donor holds a second tier of the same group as the item's prefix: never both
    clash = dataclasses.replace(DATA.mods["RP400"], families=("RP25",))
    data = dataclasses.replace(DATA, mods={**DATA.mods, "RP400": clash})
    donor = Item.build(data, base_id=AMULET, item_level=84, rarity=Rarity.MAGIC, mods=(roll("RP400"), roll("RS250")))
    outcomes = Recombinator(donor).outcomes(data, Item.build(data, base_id=AMULET, item_level=84, rarity=Rarity.MAGIC, mods=item.mods))
    assert outcomes.chance_all(["RP25", "RP400"]) == 0
    for result in finished(outcomes):
        assert not {"RP25", "RP400"} <= {entry.mod_id for entry in result.mods}


def test_one_prefix_on_one_input_and_one_suffix_on_the_other_give_three_outcomes_a_third_each():
    item, donor = SCENARIOS["one_each"]
    law = {}
    for result, chance in finished(Recombinator(donor).outcomes(DATA, item)).items():
        key = frozenset(entry.mod_id for entry in result.mods)
        law[key] = law.get(key, 0) + chance
    assert law == {frozenset({"RP25"}): Fraction(1, 3), frozenset({"RS500"}): Fraction(1, 3), frozenset({"RP25", "RS500"}): Fraction(1, 3)}
    assert frozenset() not in law  # never a white item


def test_the_rarity_follows_the_mods():
    item, donor = SCENARIOS["doubled"]
    for result in finished(Recombinator(donor).outcomes(DATA, item)):
        per_side = [sum(1 for entry in result.mods if DATA.mods[entry.mod_id].generation_type == side) for side in ("prefix", "suffix")]
        expected = Rarity.NORMAL if not result.mods else Rarity.RARE if max(per_side) > 1 else Rarity.MAGIC
        assert result.rarity is expected
    nothing = {r.rarity for r in finished(Recombinator(make(["RP25"], Rarity.MAGIC)).outcomes(DATA, make(["RP1000a"], Rarity.MAGIC)))}
    assert Rarity.MAGIC in nothing


def test_the_output_never_exceeds_the_capacity_of_a_side():
    item, donor = SCENARIOS["six_and_six"]
    for result in finished(Recombinator(donor).outcomes(DATA, item)):
        for side in ("prefix", "suffix"):
            assert sum(1 for entry in result.mods if DATA.mods[entry.mod_id].generation_type == side) <= 3


def test_the_donor_is_the_need_of_the_action():
    item, donor = SCENARIOS["doubled"]
    (need,) = Recombinator(donor).inputs(DATA, item)
    assert need.want == donor and need.start.rarity is Rarity.NORMAL and need.start.base_id == donor.base_id
    need.start.validate(DATA)


# --- refusals ------------------------------------------------------------------------------------------------------------------------


def test_a_corrupted_input_a_normal_input_and_a_jewel_are_refused():
    item, donor = make(["RP25"], Rarity.MAGIC), make(["RP1000a"], Rarity.MAGIC)
    corrupted = dataclasses.replace(donor, corrupted=True)
    with pytest.raises(NotApplicableError):
        Recombinator(corrupted).outcomes(DATA, item)
    with pytest.raises(NotApplicableError):
        Recombinator(donor).outcomes(DATA, dataclasses.replace(item, corrupted=True))
    with pytest.raises(NotApplicableError):
        Recombinator(donor).outcomes(DATA, make([], Rarity.NORMAL))
    with pytest.raises(NotApplicableError):
        Recombinator(make([], Rarity.NORMAL)).outcomes(DATA, item)
    jewel = Item(base_id=BASE_JEWEL, item_level=84, rarity=Rarity.MAGIC)
    with pytest.raises(NotApplicableError, match="jewel"):
        Recombinator(donor).outcomes(DATA, jewel)
    with pytest.raises(NotApplicableError, match="jewel"):
        Recombinator(jewel).outcomes(DATA, item)


def test_two_item_classes_are_refused():
    item = make(["RP25"], Rarity.MAGIC)
    other_class = dataclasses.replace(DATA.base_items[AMULET], id="Metadata/Items/Rings/RecombRing", item_class="Ring")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, other_class.id: other_class})
    donor = Item.build(data, base_id=other_class.id, item_level=84, rarity=Rarity.MAGIC, mods=(roll("RP1000a"),))
    with pytest.raises(NotApplicableError, match="item class"):
        Recombinator(donor).outcomes(data, item)


def test_a_veiled_mod_is_out_of_scope():
    veiled = DATA.mods[VEILED]
    item = make(["RP25"], Rarity.MAGIC)
    donor = Item(base_id=AMULET, item_level=84, rarity=Rarity.MAGIC, mods=(roll(veiled.id),))
    with pytest.raises(OutOfScopeError):
        Recombinator(donor).outcomes(DATA, item)


def test_the_label_and_the_variant_tell_donors_apart_and_the_cost_is_priced_in_dust_and_gold():
    item, donor = SCENARIOS["doubled"]
    one, other = Recombinator(donor), Recombinator(item)
    assert one.variant != other.variant
    assert one.label(DATA).startswith("Recombinator with a donor of ")
    assert Recombinator(donor, "wiki").variant != one.variant
    assert set(one.resources(DATA)) == {"Thaumaturgic Dust", "Gold"}
    with pytest.raises(ValueError):
        Recombinator(donor, "nonsense")


def test_doubling_raises_the_chance_of_the_doubled_mod():
    item = make(["RP25", "RP1000a"])
    doubled = Recombinator(make(["RP25", "RP1000b"])).outcomes(DATA, item)  # RP25 on both inputs: two entries in the pool
    single = Recombinator(make(["RP400", "RP1000b"])).outcomes(DATA, item)
    assert held(doubled, "RP25") > held(single, "RP25")
