"""The Locus of Corruption as an exact action (ticket #262, ADR-0038), against the hand oracle of `locus_support.py` and on the real 3.29.3.3 export.

"Done when" of the ticket, and where each line is tested:

1. *The contract suite passes.* `test_actions_contract.py` asks the kind about the items of `contract_fixtures_locus.py`;
   `test_the_contract_suite_runs_on_the_kind` runs `check_action` here too.
2. *The pair chance equals `wA/W * wB/(W - gA) + wB/W * wA/(W - gB)` and the ring all-resistances case gives 1.686% per use.*
   `test_the_pair_chance_is_the_formula_of_adr_0038` (every pair of the toy pool, two of one group included) and
   `test_the_ring_all_resistances_case_is_1_686_percent_per_use` (the real export).
3. *Changing the price entry changes the cost.* `test_the_use_is_priced_by_its_entry_and_an_override_changes_the_cost`.
4. *Leaving `locus` out of `actions:` removes it from the plan.* `test_a_target_that_leaves_locus_out_of_its_actions_gets_no_locus`.

The rest: the replaced implicits, the dead ends, the refusals, the sampler, the declarations and the claims.
"""

import dataclasses
import random
from collections import Counter
from datetime import UTC, datetime
from fractions import Fraction
from itertools import combinations

import pytest
from abstraction_oracle import assert_same_distribution, compressed_distribution
from abstraction_pool import LIFE_1, LIFE_2, RESIST_2, RESISTS
from abstraction_support import real_game_data
from contract_support import _roll, check_action
from corruption_support import ABYSS, ALL_RES, BELT, FLASK, LATE, LEVEL, SECOND, THIRD, base_implicit, eater, exarch
from implicits_support import BOOTS
from items_support import AMULET as AMULET_ID
from locus_support import DATA, GROUPS, TWIN, oracle, pair_chance, pool

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import LOCUS_USE, LocusOfCorruption, NotApplicableError, OutOfScopeError, VaalOrb, catalog, kinds
from crafting_system.actions.corruption import dead_end
from crafting_system.actions.locus import LocusOutcomes
from crafting_system.cli._limits import kind_title
from crafting_system.cli._offers import free_action_cost, offers_for, price_offers
from crafting_system.items import ImplicitMod, Item, Rarity, is_corrupted_implicit
from crafting_system.prices import LOCUS_USE as PRICE_NAME
from crafting_system.prices import PriceEntry, PriceFile, standing_defaults
from crafting_system.rules import get_rule

QUARTER = Fraction(1, 4)
LOCUS = LocusOfCorruption()


def item_on(base_id: str, *mods, implicits=(), rarity=Rarity.RARE, **fields) -> Item:
    return Item.build(DATA, base_id=base_id, item_level=fields.pop("item_level", LEVEL), rarity=rarity, mods=mods, implicits=implicits, **fields)


JUNK = (_roll(RESIST_2), _roll(LIFE_1))
STARTS = {
    "none": item_on(AMULET_ID, *JUNK),
    "one": item_on(BOOTS, *JUNK, implicits=(exarch(),)),
    "two": item_on(BOOTS, *JUNK, implicits=(exarch(), eater())),
    "belt-stored": item_on(BELT, *JUNK, implicits=(base_implicit(),)),
    "three": item_on(BELT, *JUNK, implicits=(base_implicit(), exarch(), eater())),  # the model allows it; it shows two of three replaced
    "fractured": item_on(AMULET_ID, _roll(RESIST_2, fractured=True), _roll(LIFE_1)),
    "normal": item_on(AMULET_ID, rarity=Rarity.NORMAL),
    "magic": item_on(AMULET_ID, _roll(LIFE_1), rarity=Rarity.MAGIC),
}


def ends_of(item: Item, outcomes: LocusOutcomes) -> dict:
    """The finished items of the altar by kind of end: the implicits an item holds, nothing, or the dead end."""
    nothing = dataclasses.replace(item, corrupted=True)
    dead = Item.build(
        DATA, base_id=item.base_id, item_level=item.item_level, rarity=Rarity.RARE, mods=tuple(e for e in item.mods if e.fractured),
        implicits=item.implicits, corrupted=True, influences=item.influences,
    )  # fmt: skip
    assert nothing != dead
    ends: dict = {}
    for chance, result in outcomes.results:
        assert result.corrupted
        if result == nothing:
            key = "nothing"
        elif result == dead:
            key = "dead"
        else:
            drawn = [e.mod_id for e in result.implicits if is_corrupted_implicit(DATA.mods[e.mod_id])]
            assert len(drawn) == 2 and GROUPS[drawn[0]] != GROUPS[drawn[1]]  # two corrupted implicits, never of one group
            assert result.mods == item.mods and result.rarity is item.rarity  # the implicits outcome touches no explicit mod
            key = ("implicits", frozenset(e.mod_id for e in result.implicits))
        ends[key] = ends.get(key, Fraction(0)) + chance
    return ends


# --- the four outcomes and the replaced implicits -------------------------------------------------------------


@pytest.mark.parametrize("name", STARTS)
def test_the_finished_items_are_the_hand_oracle_s(name):
    item = STARTS[name]
    outcomes = LOCUS.outcomes(DATA, item)
    assert ends_of(item, outcomes) == oracle([e.mod_id for e in item.implicits])
    assert sum(chance for chance, _ in outcomes.results) == 1


def test_two_of_three_implicits_are_replaced_each_pair_alike_and_one_stays():
    item = STARTS["three"]
    ends = ends_of(item, LOCUS.outcomes(DATA, item))
    held = [e.mod_id for e in item.implicits]
    for mod_id in held:  # each held implicit stays in the third of the pairs that leave it
        stays = sum((c for e, c in ends.items() if isinstance(e, tuple) and mod_id in e[1]), Fraction(0))
        assert stays == QUARTER * Fraction(1, 3)
    assert all(len(e[1]) == 3 for e in ends if isinstance(e, tuple))  # one kept, two drawn


@pytest.mark.parametrize("name", ["one", "two"])
def test_an_item_with_one_or_two_implicits_keeps_none(name):
    ends = ends_of(STARTS[name], LOCUS.outcomes(DATA, STARTS[name]))
    assert all(len(e[1]) == 2 and not e[1] & {exarch().mod_id, eater().mod_id} for e in ends if isinstance(e, tuple))


# --- Done when 2: the pair chance and the ring --------------------------------------------------------------


@pytest.mark.parametrize("name", ["none", "two", "three"])
def test_the_pair_chance_is_the_formula_of_adr_0038(name):
    outcomes = LOCUS.outcomes(DATA, STARTS[name])
    ids = sorted(pool())
    for a, b in combinations(ids, 2):
        assert outcomes.chance_all([a, b]) == QUARTER * pair_chance(a, b), (a, b)
    assert outcomes.chance_all([ALL_RES, TWIN]) == 0  # one group: never together
    # the hand numbers of the toy pool (W = 2450, gALL_RES = 1500): ALL_RES then SECOND, or SECOND then ALL_RES
    assert pair_chance(ALL_RES, SECOND) == Fraction(1000, 2450) * Fraction(500, 950) + Fraction(500, 2450) * Fraction(1000, 1950)
    assert sum(QUARTER * pair_chance(a, b) for a, b in combinations(ids, 2)) == QUARTER  # some pair in every double corruption
    assert outcomes.chance_all([ALL_RES]) == QUARTER * sum(pair_chance(ALL_RES, other) for other in ids if other != ALL_RES)


def test_the_item_level_gates_both_draws():
    low = LOCUS.outcomes(DATA, item_on(AMULET_ID, *JUNK, item_level=60))
    assert low.chance_all([LATE]) == 0  # required level 75
    assert ends_of(STARTS["none"].changed(DATA, item_level=60), low) == oracle([], level=60)
    assert low.chance_all([ALL_RES, THIRD]) == QUARTER * pair_chance(ALL_RES, THIRD, level=60)


def test_the_ring_all_resistances_case_is_1_686_percent_per_use():
    data = real_game_data()
    ring = next(base for base in data.base_items.values() if base.item_class == "Ring" and not base.implicits)
    item = Item.build(data, base_id=ring.id, item_level=84, rarity=Rarity.RARE)
    outcomes = LOCUS.outcomes(data, item)
    all_resistances = "V2AllResistancesCorrupted"
    chance = outcomes.chance_all([all_resistances])
    assert float(chance) == pytest.approx(0.01686, abs=5e-6)  # ADR-0038: 1/4 * (3.14% + 3.60%), 59.3 uses for one hit
    assert 1 / float(chance) == pytest.approx(59.3, abs=0.05)
    first = Fraction(1000, 31850)  # drawn first
    assert float(first) == pytest.approx(0.0314, abs=5e-5)
    assert float(chance * 4 - first) == pytest.approx(0.0360, abs=5e-5)  # drawn second, after a mod of another group
    vaal = VaalOrb().outcomes(data, item).chance_all([all_resistances])
    assert chance > 2 * vaal  # the Locus hits more than twice as often per use as the Vaal Orb (0.785%)
    assert sum(c for c, _ in outcomes.results) == 1
    drawn = [e for _, result in outcomes.results for e in result.implicits if is_corrupted_implicit(data.mods[e.mod_id])]
    assert len({e.mod_id for e in drawn}) == 39


def test_the_ring_pair_chance_on_the_real_export_is_the_formula():
    """Two named ring mods of different groups, against the formula computed from the export's weights and families."""
    from crafting_system.actions.corrupted_pool import corrupted_implicit_pool
    from crafting_system.data import conflicts

    data = real_game_data()
    ring = next(base for base in data.base_items.values() if base.item_class == "Ring" and not base.implicits)
    item = Item.build(data, base_id=ring.id, item_level=84, rarity=Rarity.RARE)
    real = corrupted_implicit_pool(data, ring.id, 84)
    weights = {entry.mod.id: entry.weight for entry in real.mods}
    whole = sum(weights.values())
    assert whole == 31850
    a = "V2AllResistancesCorrupted"
    b = next(mod_id for mod_id in sorted(weights) if not conflicts(data.mods[a], data.mods[mod_id]) and any(
        conflicts(data.mods[mod_id], data.mods[other]) for other in weights if other != mod_id))  # a mod whose group has other members

    def group(x):
        return sum(w for mod_id, w in weights.items() if mod_id == x or conflicts(data.mods[x], data.mods[mod_id]))

    assert group(b) > weights[b]
    formula = Fraction(weights[a], whole) * Fraction(weights[b], whole - group(a)) + Fraction(weights[b], whole) * Fraction(weights[a], whole - group(b))
    assert LOCUS.outcomes(data, item).chance_all([a, b]) == QUARTER * formula


# --- the dead ends -------------------------------------------------------------------------------------------


def test_the_influenced_rare_and_the_destruction_are_one_dead_state_never_a_goal_of_a_target_that_asks():
    goal = Goal((Wanted(RESISTS), Wanted(frozenset({LIFE_1, LIFE_2}))), asks_corrupted=True)
    for name in ("none", "magic", "normal"):
        item = STARTS[name]
        ab = Abstraction(DATA, goal, item.base_id, item.item_level, [LOCUS])
        kernel = ab.kernel(ab.compress(item), LOCUS)
        dead = ab.compress(dead_end(DATA, item))
        assert kernel[dead] == 2 * QUARTER and not ab.is_goal(dead)
        assert all(state.flags.corrupted for state in kernel)  # a corrupted item is final


@pytest.mark.parametrize("name", ["none", "one", "two", "fractured", "normal", "magic"])
def test_the_kernel_equals_the_hand_items(name):
    goal = Goal((Wanted(RESISTS), Wanted(frozenset({LIFE_1, LIFE_2}))), asks_corrupted=True)
    item = STARTS[name]
    ab = Abstraction(DATA, goal, item.base_id, item.item_level, [LOCUS])
    listed = []
    for end, chance in oracle([e.mod_id for e in item.implicits]).items():
        if end == "nothing":
            built = dataclasses.replace(item, corrupted=True)
        elif end == "dead":
            built = dead_end(DATA, item)
        else:
            implicits = tuple(ImplicitMod(m, 0, tuple(min(s.min, s.max) for s in DATA.mods[m].stats)) for m in sorted(end[1]))
            built = dataclasses.replace(item, corrupted=True, implicits=implicits)
        listed.append((built, chance))
    assert_same_distribution(ab.kernel(ab.compress(item), LOCUS), compressed_distribution(listed, ab.compress))


def test_the_dead_ends_keep_the_strands():
    item = item_on(AMULET_ID, *JUNK, memory_strands=40)
    assert {result.memory_strands for _, result in LOCUS.outcomes(DATA, item).results} == {40}
    use = LOCUS.strand_use(DATA)
    assert not use.cuts and use.spend is None


# --- the refusals and the listing ----------------------------------------------------------------------------


def test_a_corrupted_item_is_refused_and_not_listed():
    corrupted = STARTS["none"].changed(DATA, corrupted=True)
    with pytest.raises(NotApplicableError, match="already corrupted"):
        LOCUS.outcomes(DATA, corrupted)
    assert LOCUS not in catalog(DATA, corrupted)


def test_a_base_whose_class_has_no_pool_is_refused_and_not_listed():
    flask = Item.build(DATA, base_id=FLASK, item_level=LEVEL, rarity=Rarity.NORMAL)
    with pytest.raises(NotApplicableError, match="no corrupted implicit pool"):
        LOCUS.outcomes(DATA, flask)
    assert LOCUS not in catalog(DATA, flask)


def test_a_pool_with_no_second_draw_is_out_of_scope_and_not_listed():
    abyss = Item.build(DATA, base_id=ABYSS, item_level=LEVEL, rarity=Rarity.RARE)  # its pool is one mod: nothing is left for the second
    with pytest.raises(OutOfScopeError, match="no second implicit"):
        LOCUS.outcomes(DATA, abyss)
    assert LOCUS not in catalog(DATA, abyss)
    assert VaalOrb() in catalog(DATA, abyss)  # the Vaal Orb needs one draw only


@pytest.mark.parametrize("name", ["none", "normal", "magic", "fractured", "one", "belt-stored"])
def test_the_altar_takes_normal_magic_and_rare_items_and_is_listed_once(name):
    listed = [action for action in catalog(DATA, STARTS[name]) if isinstance(action, LocusOfCorruption)]
    assert listed == [LOCUS]
    entry = next(entry for entry in kinds() if entry.name == "locus")
    assert entry.corrupting and kind_title("locus") == "Locus of Corruption"


# --- the sampler ---------------------------------------------------------------------------------------------


def test_the_sampler_rolls_both_drawn_implicits_and_keeps_the_explicit_mods():
    item = STARTS["none"]
    outcomes = LOCUS.outcomes(DATA, item)
    rng = random.Random(262)
    rolled = Counter()
    seen_pairs = 0
    for _ in range(4000):
        finished = outcomes.sample(rng)
        finished.validate(DATA)
        drawn = [e for e in finished.implicits if is_corrupted_implicit(DATA.mods[e.mod_id])]
        if drawn:
            seen_pairs += 1
            assert len(drawn) == 2 and finished.mods == item.mods
            for entry in drawn:
                if entry.mod_id == SECOND:
                    rolled[entry.values] += 1
    assert seen_pairs / 4000 == pytest.approx(0.25, abs=0.03)
    assert set(rolled) == {(a, b) for a in range(3, 6) for b in range(8, 10)}  # both stats cover their whole integer range


# --- Done when 3 and 4: the price entry and the `actions:` list ---------------------------------------------


def _prices(**entries) -> PriceFile:
    return PriceFile(league="Test", fetched_at=datetime(2026, 11, 12, tzinfo=UTC), chaos_per_divine=200.0, prices={"Vaal Orb": PriceEntry(1.5, "test"), **entries})


def test_the_use_is_priced_by_its_entry_and_an_override_changes_the_cost():
    assert LOCUS_USE == PRICE_NAME == "Locus of Corruption (use)"
    assert dict(LOCUS.resources(DATA)) == {PRICE_NAME: 1}
    default = standing_defaults()[PRICE_NAME]
    assert (default.chaos, default.source) == (0.0, "default")
    start = STARTS["none"]
    offers = [o for o in offers_for(DATA, Goal((Wanted(RESISTS),), asks_corrupted=True), start.base_id, start).offers if o.label in ("Locus of Corruption", "Vaal Orb")]
    assert {o.label for o in offers} == {"Locus of Corruption", "Vaal Orb"}

    priced, dropped = price_offers(offers, _prices())  # a price file that does not name it: the standing default, 0 Chaos
    assert not dropped
    by_label = {entry.label: entry for entry in priced}
    assert by_label["Locus of Corruption"].parts == ((PRICE_NAME, 1, 0.0, "default"),)
    assert 0 < by_label["Locus of Corruption"].cost < 1e-5  # the free share of the cheapest paid offer: the solver needs a positive cost
    assert free_action_cost(priced) == by_label["Locus of Corruption"].cost

    dearer, _ = price_offers(offers, _prices(**{PRICE_NAME: PriceEntry(4.0, "override")}))  # the owner's entry
    assert {entry.label: entry.cost for entry in dearer}["Locus of Corruption"] == 4.0
    assert free_action_cost(dearer) is None
    assert {entry.label: entry.cost for entry in dearer}["Vaal Orb"] == by_label["Vaal Orb"].cost == 1.5


def test_a_target_that_leaves_locus_out_of_its_actions_gets_no_locus():
    start = STARTS["none"]
    goal = Goal((Wanted(RESISTS),), asks_corrupted=True)
    by_default = [o.label for o in offers_for(DATA, goal, start.base_id, start).offers]
    assert "Locus of Corruption" in by_default  # on by default, as `DEFAULT_CORRUPTING_KINDS` says
    named = [o.label for o in offers_for(DATA, goal, start.base_id, start, kinds_named=("vaal", "chaos-orb")).offers]
    assert "Locus of Corruption" not in named and "Vaal Orb" in named
    with_it = [o.label for o in offers_for(DATA, goal, start.base_id, start, kinds_named=("locus",)).offers]
    assert "Locus of Corruption" in with_it
    for goal, offered in ((Goal((Wanted(RESISTS),), allow_corrupted=True), True), (Goal((Wanted(RESISTS),)), False)):
        assert ("Locus of Corruption" in [o.label for o in offers_for(DATA, goal, start.base_id, start).offers]) is offered


# --- the declarations and the claims -------------------------------------------------------------------------


def test_the_altar_declares_that_it_corrupts_and_keeps_the_mods():
    adds, reads = LOCUS.adds(DATA), LOCUS.reads(DATA)
    assert adds.corrupts and adds.keeps_mods and adds.implicits and not adds.asked_only
    assert reads.implicits and reads.junk
    assert LOCUS.label(DATA) == "Locus of Corruption"
    assert LOCUS.previewable(DATA).value == "no"  # `corruption.locus_no_preview`


def test_the_claims_name_the_share_and_the_second_group_and_the_share_is_read_from_its_claim():
    claims = LOCUS.claims(DATA)
    assert {
        "corruption.locus_four_outcomes",
        "corruption.locus_two_implicit_share_decision",
        "corruption.locus_second_implicit_other_group",
        "corruption.locus_no_preview",
        "locus.replaces_two_implicits",
        "locus.cost",
    } <= claims
    share = get_rule("corruption.locus_two_implicit_share_decision")
    assert share.approximate and share.value == {"share": 0.25, "interval_low": 0.088, "interval_high": 0.265}
    assert get_rule("corruption.locus_second_implicit_other_group").approximate
    assert get_rule("locus.cost").value == {PRICE_NAME: 1}
    outcomes = LOCUS.outcomes(DATA, STARTS["none"])
    two = sum((c for c, item in outcomes.results if sum(is_corrupted_implicit(DATA.mods[e.mod_id]) for e in item.implicits) == 2), Fraction(0))
    assert two == Fraction(str(share.value["share"]))


def test_the_contract_suite_runs_on_the_kind():
    for name in ("none", "fractured", "normal", "one", "two"):
        assert check_action(LOCUS, STARTS[name], DATA)
    assert not check_action(LOCUS, STARTS["none"].changed(DATA, corrupted=True), DATA)
