"""The Awakener's Orb as an exact two-input action (ticket #213, ADR-0032).

Done when: the contract suite passes for both readings of the group conflict (it runs on every kind of the catalog, and the
kind is found on the fixture item `rare_awakener`: `test_actions_contract.py`; the two readings are checked here too);
`chance_all` equals an exhaustive enumeration written by hand (`awakener_oracle.py`) on a small pool; a pair with a group conflict
differs between the readings and a pair without one does not. The real-data check of R18's Assassin's Mark is
`test_actions_awakener_real.py`.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from abstraction_pool import DAMAGE_1, LIFE_1, LIFE_2, MANA_1, RESIST_1, RESIST_2, COLD_RESIST
from awakener_oracle import chance_of_holding
from contract_support import (
    CONTRACT_DATA,
    CRUSADER_CLASH,
    CRUSADER_SUFFIX,
    SHAPER_PREFIX,
    SHAPER_SUFFIX,
    _item,
    _roll,
    check_action,
    contract_pairs,
    fixture_items,
)
from items_support import AMULET

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    AwakenersOrb,
    ChaosOrb,
    Need,
    NotApplicableError,
    OutOfScopeError,
    Reading,
    catalog,
    kinds,
    model_readings,
)
from crafting_system.items import Influence, Item, Rarity
from crafting_system.rules import rule_by_id

CRAFTED_LOCK = "DexMasterItemGenerationCannotChangeSuffixes"
RECEIVER, DONOR = "receiver", "donor"
READINGS = {name: Reading.of({"awakener.group_conflict": name}) for name in (RECEIVER, DONOR)}


def orb(donor_mod: str, influence: Influence = Influence.CRUSADER) -> AwakenersOrb:
    return AwakenersOrb(AMULET, 84, influence, donor_mod)


def shaper_amulet(*mod_ids: str, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    fields.setdefault("influences", frozenset({Influence.SHAPER}))
    return _item(rarity, *(_roll(mod_id) for mod_id in mod_ids), **fields)


def held(outcomes, mod_id: str) -> Fraction:
    return outcomes.chance_all([mod_id])


def retained_sets(outcomes) -> list[tuple[Fraction, tuple[str, ...]]]:
    return [(share, tuple(entry.mod_id for entry in part.retained.mods)) for share, part in outcomes.components]


# --- the contract suite, both readings --------------------------------------------------------------


def test_the_kind_is_found_by_the_contract_suite_on_a_fixture_item_that_applies():
    pairs = [(action, item) for kind, action, item in contract_pairs() if kind == "awakeners-orb"]
    assert {(action.donor_mod, item) for action, item in pairs} >= {(CRUSADER_SUFFIX, "rare_awakener"), (CRUSADER_CLASH, "rare_awakener")}
    for action, item in pairs:
        if item == "rare_awakener":
            assert len(model_readings(CONTRACT_DATA, [action])) == 2
            action.outcomes(CONTRACT_DATA, fixture_items()[item])  # it applies to this one


@pytest.mark.parametrize("donor_mod", [CRUSADER_SUFFIX, CRUSADER_CLASH])
def test_the_contract_suite_passes_for_both_readings_on_a_receiver_with_one_influenced_mod(donor_mod):
    # one influenced mod (the Shaper prefix): the clash donor is a group conflict at every pair; the suffix donor never
    assert check_action(orb(donor_mod), shaper_amulet(SHAPER_PREFIX, LIFE_1))


def test_there_are_two_readings_the_receiver_first():
    readings = model_readings(CONTRACT_DATA, [orb(CRUSADER_SUFFIX)])
    assert [reading["awakener.group_conflict"] for reading in readings] == [RECEIVER, DONOR]
    item = fixture_items()["rare_awakener"]
    plain = orb(CRUSADER_CLASH).outcomes(CONTRACT_DATA, item)  # the plain call is the plan's reading
    assert retained_sets(plain) == retained_sets(orb(CRUSADER_CLASH).outcomes_under(CONTRACT_DATA, item, READINGS[RECEIVER]))
    assert retained_sets(plain) != retained_sets(orb(CRUSADER_CLASH).outcomes_under(CONTRACT_DATA, item, READINGS[DONOR]))


# --- chance_all equals exhaustive enumeration -------------------------------------------------------

SMALL_IDS = frozenset(
    {LIFE_1, LIFE_2, DAMAGE_1, RESIST_1, RESIST_2, MANA_1, COLD_RESIST, SHAPER_PREFIX, SHAPER_SUFFIX, CRUSADER_SUFFIX, CRUSADER_CLASH, CRAFTED_LOCK}
)
ORACLE_DATA = dataclasses.replace(CONTRACT_DATA, mods={mod_id: mod for mod_id, mod in CONTRACT_DATA.mods.items() if mod_id in SMALL_IDS})
TAGS = frozenset(ORACLE_DATA.base_items[AMULET].tags) | {"amulet_shaper", "amulet_crusader"}
DOMAIN = ORACLE_DATA.base_items[AMULET].domain


def small_item(*mod_ids: str) -> Item:
    mods = tuple(_roll(mod_id, crafted=mod_id == CRAFTED_LOCK) for mod_id in mod_ids)
    return Item.build(ORACLE_DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=mods, influences=frozenset({Influence.SHAPER}))


def wanted_sets():
    singles = sorted(SMALL_IDS - {CRAFTED_LOCK})
    some = [SHAPER_PREFIX, SHAPER_SUFFIX, CRUSADER_SUFFIX, CRUSADER_CLASH, LIFE_1, RESIST_1, RESIST_2, MANA_1]
    pairs = [{a, b} for index, a in enumerate(some) for b in some[index + 1 :]]
    return [{a} for a in singles] + pairs + [{SHAPER_PREFIX, SHAPER_SUFFIX, CRUSADER_CLASH}]


@pytest.mark.parametrize("reading", [RECEIVER, DONOR])
@pytest.mark.parametrize("donor_mod", [CRUSADER_SUFFIX, CRUSADER_CLASH])
@pytest.mark.parametrize(
    "mods,influenced",
    [
        ((SHAPER_PREFIX, SHAPER_SUFFIX, LIFE_1), [SHAPER_PREFIX, SHAPER_SUFFIX]),  # two influenced mods: the pair is drawn
        ((SHAPER_PREFIX, LIFE_1, CRAFTED_LOCK), [SHAPER_PREFIX]),  # one, and a crafted metamod that the reroll does not protect
    ],
    ids=["two_influenced", "one_influenced_and_a_lock"],
)
def test_chance_all_equals_the_exhaustive_enumeration_on_a_small_pool(mods, influenced, donor_mod, reading):
    item = small_item(*mods)
    outcomes = orb(donor_mod).outcomes_under(ORACLE_DATA, item, READINGS[reading])
    for wanted in wanted_sets():
        expected = chance_of_holding(ORACLE_DATA, TAGS, DOMAIN, 84, influenced, donor_mod, reading, set(wanted))
        assert outcomes.chance_all(wanted) == expected, wanted
    assert outcomes.chance_all([CRAFTED_LOCK]) == 0  # nothing but the kept mods and the draw survives


# --- the group conflict -----------------------------------------------------------------------------


def test_a_pair_with_a_group_conflict_differs_between_the_readings():
    item = shaper_amulet(SHAPER_PREFIX, LIFE_1)
    clash = orb(CRUSADER_CLASH)
    receiver = clash.outcomes_under(CONTRACT_DATA, item, READINGS[RECEIVER])
    donor = clash.outcomes_under(CONTRACT_DATA, item, READINGS[DONOR])
    assert retained_sets(receiver) == [(1, (SHAPER_PREFIX,))] and retained_sets(donor) == [(1, (CRUSADER_CLASH,))]
    assert (held(receiver, SHAPER_PREFIX), held(receiver, CRUSADER_CLASH)) == (1, 0)
    assert (held(donor, SHAPER_PREFIX), held(donor, CRUSADER_CLASH)) == (0, 1)
    # the new mods are drawn from the same pool either way (the family of the dropped mod is out of it): what differs is the mod kept
    assert receiver.distribution(lambda mod: mod.id) == donor.distribution(lambda mod: mod.id)
    assert retained_sets(receiver) != retained_sets(donor)


def test_a_pair_without_a_group_conflict_does_not_differ_between_the_readings():
    item = shaper_amulet(SHAPER_PREFIX, LIFE_1)
    plain = orb(CRUSADER_SUFFIX)
    receiver = plain.outcomes_under(CONTRACT_DATA, item, READINGS[RECEIVER])
    donor = plain.outcomes_under(CONTRACT_DATA, item, READINGS[DONOR])
    assert retained_sets(receiver) == retained_sets(donor) == [(1, tuple(sorted((SHAPER_PREFIX, CRUSADER_SUFFIX))))]
    for label in (lambda mod: mod.id, lambda mod: mod.generation_type):
        assert receiver.distribution(label) == donor.distribution(label)
    assert all(held(receiver, mod_id) == held(donor, mod_id) for mod_id in CONTRACT_DATA.mods)


def test_a_receiver_with_a_clashing_and_a_free_influenced_mod_differs_only_at_the_clashing_pair():
    item = fixture_items()["rare_awakener"]  # Shaper prefix (clashes with the donor's mod), Shaper suffix (does not)
    clash = orb(CRUSADER_CLASH)
    receiver = clash.outcomes_under(CONTRACT_DATA, item, READINGS[RECEIVER])
    donor = clash.outcomes_under(CONTRACT_DATA, item, READINGS[DONOR])
    assert retained_sets(receiver) == [(Fraction(1, 2), (SHAPER_PREFIX,)), (Fraction(1, 2), tuple(sorted((CRUSADER_CLASH, SHAPER_SUFFIX))))]
    assert retained_sets(donor) == [(Fraction(1, 2), (CRUSADER_CLASH,)), (Fraction(1, 2), tuple(sorted((CRUSADER_CLASH, SHAPER_SUFFIX))))]
    assert held(receiver, SHAPER_PREFIX) == Fraction(1, 2) and held(donor, SHAPER_PREFIX) == 0
    assert held(receiver, CRUSADER_CLASH) == Fraction(1, 2) and held(donor, CRUSADER_CLASH) == 1


def test_the_kernel_differs_between_the_readings_at_a_conflict_and_not_without_one():
    item = shaper_amulet(SHAPER_PREFIX, LIFE_1)
    goal = Goal((Wanted(frozenset({SHAPER_PREFIX})), Wanted(frozenset({CRUSADER_CLASH, CRUSADER_SUFFIX}))))
    kernels = {}
    for donor_mod in (CRUSADER_CLASH, CRUSADER_SUFFIX):
        action = orb(donor_mod)
        for name, reading in READINGS.items():
            ab = Abstraction(CONTRACT_DATA, goal, AMULET, 84, [action], reading=reading)
            kernels[donor_mod, name] = dict(ab.kernel(ab.compress(item), action))
            assert sum(kernels[donor_mod, name].values()) == 1
    assert kernels[CRUSADER_CLASH, RECEIVER] != kernels[CRUSADER_CLASH, DONOR]
    assert kernels[CRUSADER_SUFFIX, RECEIVER] == kernels[CRUSADER_SUFFIX, DONOR]


# --- the rules --------------------------------------------------------------------------------------


def new_mods(outcomes) -> dict[int, Fraction]:
    """The distribution of how many mods the draw adds (the kept mods are not counted)."""
    return {sum(count for _, count in outcome): chance for outcome, chance in outcomes.distribution(lambda mod: "new").items()}


def test_the_kept_mods_count_inside_the_total_and_one_remains_under_a_conflict():
    item = shaper_amulet(SHAPER_PREFIX, LIFE_1)
    both = orb(CRUSADER_SUFFIX).outcomes(CONTRACT_DATA, item)  # two kept mods: 2, 3 or 4 more for a total of 4, 5 or 6
    assert new_mods(both) == {2: Fraction(8, 12), 3: Fraction(3, 12), 4: Fraction(1, 12)}
    one = orb(CRUSADER_CLASH).outcomes(CONTRACT_DATA, item)  # the plan: the receiver's mod alone remains, so 3, 4 or 5 more
    assert new_mods(one) == {3: Fraction(8, 12), 4: Fraction(3, 12), 5: Fraction(1, 12)}
    other = orb(CRUSADER_CLASH).outcomes_under(CONTRACT_DATA, item, READINGS[DONOR])  # the donor's mod alone remains: the same counts
    assert new_mods(other) == new_mods(one)


def test_the_pair_is_drawn_uniformly_among_the_valid_pairs():
    item = fixture_items()["rare_awakener"]
    outcomes = orb(CRUSADER_SUFFIX).outcomes(CONTRACT_DATA, item)
    assert retained_sets(outcomes) == [
        (Fraction(1, 2), tuple(sorted((SHAPER_PREFIX, CRUSADER_SUFFIX)))),
        (Fraction(1, 2), tuple(sorted((SHAPER_SUFFIX, CRUSADER_SUFFIX)))),
    ]
    assert held(outcomes, CRUSADER_SUFFIX) == 1  # the donor's mod always comes over


def test_a_kept_mod_keeps_its_tier_and_gets_a_new_value_and_the_rest_is_replaced():
    item = Item.build(
        CONTRACT_DATA,
        base_id=AMULET,
        item_level=90,
        rarity=Rarity.MAGIC,
        mods=(dataclasses.replace(_roll(SHAPER_SUFFIX), tier=3), _roll(LIFE_1)),
        influences=frozenset({Influence.SHAPER}),
    )
    outcomes = orb(CRUSADER_SUFFIX).outcomes(CONTRACT_DATA, item)  # a magic receiver becomes a rare one
    rng = random.Random(213)
    seen_values = set()
    for _ in range(200):
        finished = outcomes.sample(rng)
        finished.validate(CONTRACT_DATA)
        assert finished.rarity is Rarity.RARE and finished.item_level == 90 and finished.base_id == AMULET
        assert finished.influences == {Influence.SHAPER, Influence.CRUSADER}
        by_id = {entry.mod_id: entry for entry in finished.mods}
        assert by_id[SHAPER_SUFFIX].tier == 3  # the tier stays
        assert by_id[CRUSADER_SUFFIX].tier == 1
        seen_values.add(by_id[SHAPER_SUFFIX].values)
        assert len(finished.mods) <= 6  # the draw may run dry, never over
    assert len(seen_values) > 1  # the value is rolled afresh, not kept


def test_the_metamods_and_crafted_mods_do_not_protect_anything():
    lock = _roll(CRAFTED_LOCK, crafted=True)  # Suffixes Cannot Be Changed
    item = _item(Rarity.RARE, _roll(SHAPER_PREFIX), _roll(RESIST_2), lock, influences=frozenset({Influence.SHAPER}))
    outcomes = orb(CRUSADER_SUFFIX).outcomes(CONTRACT_DATA, item)
    assert held(outcomes, CRAFTED_LOCK) == 0 and held(outcomes, RESIST_2) < 1
    for _, part in outcomes.components:
        assert not part.retained.crafted_mods  # a chaos orb under the lock would keep the suffix side; this reroll does not
    rng = random.Random(7)
    assert all(not outcomes.sample(rng).crafted_mods for _ in range(50))


def test_item_level_and_the_rest_of_the_item_stay():
    item = shaper_amulet(SHAPER_PREFIX, LIFE_1)
    for _, part in orb(CRUSADER_SUFFIX).outcomes(CONTRACT_DATA, item).components:
        assert part.retained.item_level == item.item_level and part.retained.base_id == item.base_id
        assert part.retained.implicits == item.implicits and part.retained.quality == item.quality
        assert part.retained.influences == {Influence.SHAPER, Influence.CRUSADER} and part.retained.rarity is Rarity.RARE


# --- the refusals -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "item,why",
    [
        (shaper_amulet(SHAPER_PREFIX, corrupted=True), "corrupted"),
        (shaper_amulet(rarity=Rarity.NORMAL), "normal"),
        (_item(Rarity.RARE, _roll(SHAPER_PREFIX)), "exactly one influence"),
        (shaper_amulet(SHAPER_PREFIX, influences=frozenset({Influence.SHAPER, Influence.ELDER})), "exactly one influence"),
        (shaper_amulet(SHAPER_PREFIX, influences=frozenset({Influence.CRUSADER})), "same influence"),
        (Item.build(CONTRACT_DATA, base_id=AMULET, item_level=67, rarity=Rarity.RARE, mods=(_roll(SHAPER_PREFIX),), influences=frozenset({Influence.SHAPER})), "item level 68"),
        (shaper_amulet(LIFE_1, RESIST_2), "no influenced mod"),
    ],
    ids=["corrupted", "normal", "no_influence", "two_influences", "same_influence_as_the_donor", "below_item_level_68", "no_influenced_mod"],
)
def test_the_game_refuses_what_it_refuses(item, why):
    with pytest.raises(NotApplicableError, match=why):
        orb(CRUSADER_SUFFIX).outcomes(CONTRACT_DATA, item)


def test_a_fractured_item_is_out_of_scope_not_refused_by_the_game():
    item = _item(Rarity.RARE, _roll(SHAPER_PREFIX, fractured=True), _roll(LIFE_1), influences=frozenset({Influence.SHAPER}))
    with pytest.raises(OutOfScopeError, match="fractured"):
        orb(CRUSADER_SUFFIX).outcomes(CONTRACT_DATA, item)


def test_a_donor_mod_that_is_no_influence_mod_of_its_influence_is_out_of_scope():
    item = shaper_amulet(SHAPER_PREFIX, LIFE_1)
    for wrong in (orb(CRUSADER_SUFFIX, Influence.HUNTER), orb(LIFE_1), orb("NoSuchMod")):
        with pytest.raises(OutOfScopeError, match="not an influence mod"):
            wrong.outcomes(CONTRACT_DATA, item)
        with pytest.raises(OutOfScopeError):
            wrong.inputs(CONTRACT_DATA)


def test_an_unknown_reading_is_refused():
    with pytest.raises(ValueError, match="awakener.group_conflict"):
        orb(CRUSADER_SUFFIX).outcomes(CONTRACT_DATA, shaper_amulet(SHAPER_PREFIX), Reading.of({"awakener.group_conflict": "neither"}))


def test_a_kept_mod_that_is_rolled_afresh_has_no_law_under_a_roll_limit():
    item = shaper_amulet(SHAPER_PREFIX, LIFE_1)
    goal = Goal((Wanted(frozenset({SHAPER_SUFFIX}), min_roll=(30,)),))
    action = orb(CRUSADER_SUFFIX)
    ab = Abstraction(CONTRACT_DATA, goal, AMULET, 84, [action])
    with pytest.raises(OutOfScopeError, match="roll limit"):
        ab.kernel(ab.compress(item), action)


# --- the inputs, the catalog and the claims ---------------------------------------------------------


def test_the_donor_is_a_need_that_holds_its_influence_and_the_mod_to_carry_over_and_nothing_else():
    action = orb(CRUSADER_CLASH)
    (need,) = action.inputs(CONTRACT_DATA, fixture_items()["rare_awakener"])
    assert isinstance(need, Need) and action.inputs(CONTRACT_DATA) == action.inputs(CONTRACT_DATA, None) == (need,)
    assert need.start.influences == need.want.influences == {Influence.CRUSADER}
    assert need.start.rarity is Rarity.NORMAL and need.want.rarity is Rarity.RARE
    assert [entry.mod_id for entry in need.want.mods] == [CRUSADER_CLASH] and need.want.base_id == AMULET
    assert action.reads(CONTRACT_DATA).input_mods and action.reads(CONTRACT_DATA).junk
    assert dict(action.resources()) == {"Awakener's Orb": 1}


def test_the_kind_lists_an_orb_for_each_donor_mod_of_every_other_influence_and_is_not_a_planner_kind():
    entry = {entry.name: entry for entry in kinds()}["awakeners-orb"]
    assert not entry.planner and "#212" in entry.why_not
    assert entry not in kinds(planner_only=True)
    listed = [action for action in catalog(CONTRACT_DATA, fixture_items()["rare_awakener"]) if isinstance(action, AwakenersOrb)]
    assert {(action.donor_influence, action.donor_mod) for action in listed} == {
        (Influence.CRUSADER, CRUSADER_SUFFIX),
        (Influence.CRUSADER, CRUSADER_CLASH),
    }
    assert len({(action.label(CONTRACT_DATA), action.variant) for action in listed}) == len(listed)
    for name in ("normal", "magic", "rare_junk", "rare_four"):  # no influence: nothing to receive
        assert not [a for a in catalog(CONTRACT_DATA, fixture_items()[name]) if isinstance(a, AwakenersOrb)]
    two = _item(Rarity.RARE, _roll(SHAPER_PREFIX), influences=frozenset({Influence.SHAPER, Influence.ELDER}))
    assert not [a for a in catalog(CONTRACT_DATA, two) if isinstance(a, AwakenersOrb)]
    assert not [a for a in catalog(CONTRACT_DATA, shaper_amulet(SHAPER_PREFIX, corrupted=True)) if isinstance(a, AwakenersOrb)]


def test_the_approximate_claims_it_reads_are_named():
    claims = orb(CRUSADER_CLASH).claims(CONTRACT_DATA)
    approximate = {
        "awakener.same_mod_group_keeps_one",
        "awakener.survivor_coe",
        "awakener.survivor_wiki",
        "awakener.kept_mods_count_in_total",
    }
    assert approximate <= claims
    assert all(rule_by_id(claim_id).approximate for claim_id in approximate)
    assert {"awakener.pair_choice_uniform", "awakener.cost", "awakener.ignores_metamods", "awakener.rest_rerolled_like_chaos"} <= claims


def test_the_fifteen_claims_of_the_research_note_are_in_the_registry():
    names = (
        "two_items_same_class receiver_reforged_rare_both_influences one_influence_each_and_different refused_on_corrupted "
        "keeps_base_level_sockets_quality_enchants one_influenced_mod_per_input_kept pair_choice_uniform same_mod_group_keeps_one "
        "survivor_wiki survivor_coe rest_rerolled_like_chaos kept_mods_count_in_total ignores_metamods imprint_restores_receiver_only "
        "survivor_player_report_2020"
    ).split()
    assert len(names) == 15
    for name in names:
        rule = rule_by_id(f"awakener.{name}")
        assert rule.quote and rule.url and rule.patch_verified
    for name in ("same_mod_group_keeps_one", "survivor_coe", "kept_mods_count_in_total"):  # the group conflict and the kept-in-total are marked
        assert rule_by_id(f"awakener.{name}").approximate and rule_by_id(f"awakener.{name}").approximate_reason
    assert not rule_by_id("awakener.pair_choice_uniform").approximate
    assert rule_by_id("awakener.cost").value["Awakener's Orb"] == 1


def test_an_action_that_rerolls_nothing_keeps_the_values_it_had():
    item = fixture_items()["rare_junk"]
    assert ChaosOrb().outcomes(CONTRACT_DATA, item).rerolled == frozenset()
    assert all(part.rerolled == {SHAPER_PREFIX, CRUSADER_SUFFIX} for _, part in orb(CRUSADER_SUFFIX).outcomes(CONTRACT_DATA, shaper_amulet(SHAPER_PREFIX)).components)
