"""The veiled orbs, the unveil and the pick against a hand oracle (ticket #144, ADR-0026).

Every expected number is typed here from the rules and the small hand-written pool of `veiled_support` (see its docstring for the
weights), not read from the code: the offers of the amulet prefix pool (Life 1000 and 500 in one family, Armour 1500, Mana 1000) and
suffix pool (Speed 2000, Crit 1000, a hybrid of 600 that shares Speed's family) with their chances by hand, the placement of the
veil by side room, the removal of the Veiled Exalted Orb (uniform, metamods included, side locks respected) and every refusal.
The figures on the real export are in `test_actions_veiled_real.py`.
"""

import random
from fractions import Fraction

import pytest
from abstraction_pool import COLD_RESIST, CRAFTED as LOCK_SUFFIXES, DAMAGE_1, FIRE_RESIST, GEM, LIFE_1, MANA_1, RESIST_2
from contract_support import CONTRACT_DATA as DATA, TIERS, _item, _roll, check_action
from veiled_support import (
    ARMOUR,
    CRAFTED_ARMOUR,
    CRIT,
    HYBRID,
    LIFE_1 as VEIL_LIFE_1,
    LIFE_2 as VEIL_LIFE_2,
    MANA,
    OTHER_MASTER_ARMOUR,
    PLACEHOLDER_PREFIX,
    PLACEHOLDER_SUFFIX,
    SIGNATURE_PLACEHOLDER,
    SPEED,
    ZERO,
)

from crafting_system.actions import (
    NotApplicableError,
    OutOfScopeError,
    Pick,
    Unveil,
    VeiledChaosOrb,
    VeiledExaltedOrb,
    catalog,
    kinds,
    offer_distribution,
    offer_pool,
)
from crafting_system.items import ExplicitMod, Item, Rarity, veiled_placeholder

F = Fraction
PRE, SUF = PLACEHOLDER_PREFIX, PLACEHOLDER_SUFFIX


def holder(mod_id: str) -> ExplicitMod:
    return veiled_placeholder(DATA, mod_id)


def rolled(mod_id: str, **flags) -> ExplicitMod:
    """Any mod of `DATA` at its lowest values (and its tier on the amulet, 1 for a mod with none)."""
    mod = DATA.mods[mod_id]
    return ExplicitMod(mod_id, TIERS.get(mod_id, 1), tuple(min(stat.min, stat.max) for stat in mod.stats), **flags)


def amulet(*mods: ExplicitMod, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    return _item(rarity, *mods, **fields)


def ids(item: Item) -> set[str]:
    return {entry.mod_id for entry in item.mods}


def offers_of(item: Item) -> dict[frozenset[str], Fraction]:
    """The offers `Unveil` gives on `item`, by the set of mod ids, summed over equal sets."""
    found: dict[frozenset[str], Fraction] = {}
    for chance, result in Unveil().outcomes(DATA, item).results:
        key = frozenset(result.veil_offer)
        found[key] = found.get(key, F(0)) + chance
    return found


def chance_of(outcomes, wanted: set[str]) -> Fraction:
    """The chance that a result holds all of `wanted` among its explicit mods."""
    return outcomes.chance_all(wanted)


# --- the offer: a chance node ----------------------------------------------------------------------------------------------


def test_the_prefix_offer_has_three_mods_one_per_family_and_the_heavier_life_variant_comes_twice_as_often():
    # three families (Life 1500 = 1000 + 500, Armour 1500, Mana 1000) and a zero-weight mod: the draw always ends with one of each
    # family; whenever the Life family is hit, its first mod is twice as likely as its second (1000 : 500)
    assert offers_of(amulet(holder(PRE), rolled(RESIST_2))) == {
        frozenset({ARMOUR, VEIL_LIFE_1, MANA}): F(2, 3),
        frozenset({ARMOUR, VEIL_LIFE_2, MANA}): F(1, 3),
    }


def test_a_family_on_the_item_leaves_the_pool_and_a_short_pool_gives_a_short_offer():
    # a crafted Armour (the craftable version of the veiled one) blocks the Armour family: two families are left
    blocked = amulet(holder(PRE), rolled(CRAFTED_ARMOUR, crafted=True))
    assert offers_of(blocked) == {frozenset({VEIL_LIFE_1, MANA}): F(2, 3), frozenset({VEIL_LIFE_2, MANA}): F(1, 3)}


def test_a_suffix_offer_by_hand_with_a_hybrid_that_takes_two_families():
    # W = 2000 + 1000 + 600. Speed first (5/9): Speed and the hybrid leave, Crit follows. Crit first (5/18): Speed 10/13 or the
    # hybrid 3/13 follows, and the other leaves. The hybrid first (1/6): Speed leaves with it (the shared family), Crit follows.
    assert offers_of(amulet(holder(SUF), rolled(RESIST_2))) == {
        frozenset({SPEED, CRIT}): F(5, 9) + F(5, 18) * F(10, 13),
        frozenset({HYBRID, CRIT}): F(5, 18) * F(3, 13) + F(1, 6),
    }
    assert F(5, 9) + F(5, 18) * F(10, 13) == F(10, 13) and F(5, 18) * F(3, 13) + F(1, 6) == F(3, 13)


def test_the_offer_chances_sum_to_one_and_the_zero_weight_mod_is_never_offered():
    for side in (PRE, SUF):
        shown = offers_of(amulet(holder(side)))
        assert sum(shown.values()) == 1
        assert all(ZERO not in offer for offer in shown)
        assert all(1 <= len(offer) <= 3 for offer in shown)


def test_the_offer_is_drawn_once_and_stays_fixed():
    drawn = amulet(holder(PRE), rolled(RESIST_2), veil_offer=(ARMOUR, VEIL_LIFE_1, MANA))
    with pytest.raises(NotApplicableError, match="drawn already"):
        Unveil().outcomes(DATA, drawn)
    for _, result in Unveil().outcomes(DATA, amulet(holder(PRE))).results:
        assert result.mods == amulet(holder(PRE)).mods  # unveiling changes nothing but the offer
        assert 1 <= len(result.veil_offer) <= 3 and list(result.veil_offer) == sorted(result.veil_offer)


def test_there_is_no_offer_filter_and_no_item_level_gate():
    # the unveiled records need level 60; an item level 30 amulet gets the same offers as one of level 84
    low = Item.build(DATA, base_id=amulet().base_id, item_level=30, rarity=Rarity.RARE, mods=(holder(PRE),))
    assert {frozenset(result.veil_offer) for _, result in Unveil().outcomes(DATA, low).results} == set(offers_of(amulet(holder(PRE))))


def test_an_offer_needs_a_placeholder_and_a_pool():
    with pytest.raises(NotApplicableError, match="no veiled placeholder"):
        Unveil().outcomes(DATA, amulet(rolled(RESIST_2)))
    # three suffixes on the item, two of them from the pool's families: the third slot is the placeholder, nothing is left to offer
    full = amulet(holder(SUF), rolled(SPEED), rolled(CRIT))
    with pytest.raises(NotApplicableError, match="no mod of the unveiled pool"):
        Unveil().outcomes(DATA, full)


def test_unveil_works_on_a_corrupted_item():
    assert offers_of(amulet(holder(PRE), corrupted=True))


def test_offer_pool_and_distribution_are_the_functions_unveil_uses():
    pool = offer_pool(DATA, amulet(holder(PRE)), DATA.mods[PRE])
    assert {mod.id: weight for mod, weight in pool} == {VEIL_LIFE_1: 1000, VEIL_LIFE_2: 500, ARMOUR: 1500, MANA: 1000}
    assert offer_distribution(pool) == offers_of(amulet(holder(PRE)))


# --- the pick: a choice node -----------------------------------------------------------------------------------------------


def test_a_pick_replaces_the_placeholder_with_the_mod_of_that_place_in_id_order():
    drawn = amulet(holder(PRE), rolled(RESIST_2), veil_offer=(MANA, ARMOUR, VEIL_LIFE_1))
    assert drawn.veil_offer == (ARMOUR, VEIL_LIFE_1, MANA)  # the item keeps the offer sorted by mod id
    for index, mod_id in ((1, ARMOUR), (2, VEIL_LIFE_1), (3, MANA)):
        ((chance, result),) = Pick(index).outcomes(DATA, drawn).results
        assert chance == 1 and result.veil_offer == ()
        assert ids(result) == {mod_id, RESIST_2}
        (picked,) = (entry for entry in result.mods if entry.mod_id == mod_id)
        assert picked.values == tuple(min(stat.min, stat.max) for stat in DATA.mods[mod_id].stats) and not picked.crafted and not picked.fractured
        assert picked.tier == TIERS.get(mod_id, 1)


def test_a_pick_needs_an_offer_and_a_mod_at_that_place():
    with pytest.raises(NotApplicableError, match="nothing to pick"):
        Pick(1).outcomes(DATA, amulet(holder(PRE)))
    short = amulet(holder(PRE), veil_offer=(VEIL_LIFE_1, MANA))
    Pick(2).outcomes(DATA, short)
    with pytest.raises(NotApplicableError, match="no mod number 3"):
        Pick(3).outcomes(DATA, short)


@pytest.mark.parametrize("index", [0, 4, -1, 2.0, True])
def test_a_pick_is_of_the_first_to_the_third_mod(index):
    with pytest.raises(ValueError):
        Pick(index)


def test_a_pick_refuses_a_mod_that_clashes_with_the_item():
    # the item was changed after the offer was drawn (a hand-made one): the Mana mod of the offer is on it already
    clash = amulet(holder(PRE), rolled(MANA), veil_offer=(ARMOUR, MANA))
    with pytest.raises(NotApplicableError, match="shares a family"):
        Pick(2).outcomes(DATA, clash)
    Pick(1).outcomes(DATA, clash)


def test_a_pick_works_on_a_corrupted_item_and_keeps_the_other_mods_as_they_are():
    drawn = amulet(holder(SUF), rolled(RESIST_2, fractured=True), rolled(LIFE_1), veil_offer=(SPEED, CRIT), corrupted=True)
    ((_, result),) = Pick(1).outcomes(DATA, drawn).results  # Crit sorts before Speed
    assert ids(result) == {CRIT, RESIST_2, LIFE_1} and result.corrupted
    assert {entry.mod_id for entry in result.mods if entry.fractured} == {RESIST_2}


def test_a_fractured_placeholder_stays_fractured_when_it_is_picked():
    # a fractured veil (a drop of the Syndicate maps, V-05) is unveiled and picked like any other: the chosen mod is fractured too
    start = amulet(ExplicitMod(PRE, 1, holder(PRE).values, fractured=True), rolled(RESIST_2))
    offered = [result for _, result in Unveil().outcomes(DATA, start).results]
    assert offered and all(result.mods == start.mods for result in offered)
    for result in offered:
        ((_, landed),) = Pick(1).outcomes(DATA, result).results
        fractured = {entry.mod_id for entry in landed.mods if entry.fractured}
        assert fractured == {result.veil_offer[0]} and not any(DATA.mods[entry.mod_id].domain == "veiled" for entry in landed.mods)
        assert landed.veil_offer == ()


def test_a_picked_hybrid_takes_both_of_its_families():
    drawn = amulet(holder(SUF), veil_offer=(CRIT, HYBRID))
    ((_, result),) = Pick(2).outcomes(DATA, drawn).results
    assert DATA.mods[HYBRID].families == ("VeilTestSpeed", "VeilTestStr") and ids(result) == {HYBRID}


def test_unveil_then_pick_is_the_whole_route_and_the_item_ends_without_a_placeholder():
    start = amulet(holder(PRE), rolled(RESIST_2))
    reached: dict[frozenset[str], Fraction] = {}
    for chance, offered in Unveil().outcomes(DATA, start).results:
        ((_, landed),) = Pick(1).outcomes(DATA, offered).results  # the first of the offer in id order
        key = frozenset(ids(landed))
        reached[key] = reached.get(key, F(0)) + chance
    assert reached == {frozenset({ARMOUR, RESIST_2}): F(1)}  # Armour sorts before both Life mods


# --- the Veiled Chaos Orb --------------------------------------------------------------------------------------------------


def test_a_veil_goes_to_the_only_side_with_room():
    # a suffix lock (the crafted Dex lock sits on a prefix) over three suffixes: the locked side is full, so the veil is a prefix
    full = amulet(rolled(LOCK_SUFFIXES, crafted=True), rolled(RESIST_2), rolled(COLD_RESIST), rolled(MANA_1))
    outcomes = VeiledChaosOrb().outcomes(DATA, full)
    assert [(share, part.forced) for share, part in outcomes.components] == [(F(1), PRE)]
    assert chance_of(outcomes, {PRE}) == 1 and chance_of(outcomes, {SUF}) == 0
    assert chance_of(outcomes, {RESIST_2, COLD_RESIST, MANA_1}) == 1  # the locked suffixes stay


def test_the_veil_ignores_a_lock_with_room_and_goes_to_either_side_half_and_half():
    # the suffix side is locked with one suffix on it and two open slots; the lock itself (a prefix) is rerolled away
    outcomes = VeiledChaosOrb().outcomes(DATA, amulet(rolled(LOCK_SUFFIXES, crafted=True), rolled(RESIST_2)))
    assert [(share, part.forced) for share, part in outcomes.components] == [(F(1, 2), PRE), (F(1, 2), SUF)]
    assert chance_of(outcomes, {PRE}) == F(1, 2) and chance_of(outcomes, {SUF}) == F(1, 2)
    assert chance_of(outcomes, {RESIST_2}) == 1 and chance_of(outcomes, {LOCK_SUFFIXES}) == 0


def test_the_veil_counts_inside_the_total_of_four_five_or_six_mods():
    # kept: one locked suffix. The veil is the second mod; the rest is drawn up to 4, 5 or 6 in all (8 : 3 : 1): 2, 3 or 4 more
    outcomes = VeiledChaosOrb().outcomes(DATA, amulet(rolled(LOCK_SUFFIXES, crafted=True), rolled(RESIST_2)))
    drawn = outcomes.distribution(lambda mod: "x")
    assert {sum(count for _, count in outcome): chance for outcome, chance in drawn.items()} == {2: F(2, 3), 3: F(1, 4), 4: F(1, 12)}
    # a suffix lock over three suffixes: they and the veil are 4 mods already, so 0, 1 or 2 more are drawn (a total of 4, 5 or 6)
    full = amulet(rolled(LOCK_SUFFIXES, crafted=True), rolled(RESIST_2), rolled(COLD_RESIST), rolled(MANA_1))
    more = VeiledChaosOrb().outcomes(DATA, full).distribution(lambda mod: "x")
    assert {sum(count for _, count in outcome): chance for outcome, chance in more.items()} == {0: F(2, 3), 1: F(1, 4), 2: F(1, 12)}


def test_a_veiled_chaos_orb_rerolls_everything_else_and_every_result_holds_one_placeholder():
    start = amulet(rolled(LIFE_1), rolled(DAMAGE_1), rolled(FIRE_RESIST, fractured=True), rolled(GEM))
    outcomes = VeiledChaosOrb().outcomes(DATA, start)
    rng = random.Random(144)
    for _ in range(60):
        result = outcomes.sample(rng)
        result.validate(DATA)
        assert sum(DATA.mods[entry.mod_id].domain == "veiled" for entry in result.mods) == 1
        assert FIRE_RESIST in ids(result) and 4 <= len(result.mods) <= 6 and result.veil_offer == ()
    assert chance_of(outcomes, {FIRE_RESIST}) == 1


def test_a_drawn_offer_goes_with_the_placeholder_it_belonged_to():
    drawn = amulet(holder(PRE), rolled(RESIST_2), veil_offer=(ARMOUR, VEIL_LIFE_1, MANA))
    outcomes = VeiledChaosOrb().outcomes(DATA, drawn)
    for _, part in outcomes.components:
        assert part.retained.veil_offer == ()  # the old placeholder is rerolled away, and its offer with it
    rng = random.Random(1441)
    assert all(outcomes.sample(rng).veil_offer == () for _ in range(30))


@pytest.mark.parametrize(
    "item, reason",
    [
        (lambda: amulet(rarity=Rarity.NORMAL), "rare item only"),
        (lambda: amulet(rolled(LIFE_1), rarity=Rarity.MAGIC), "rare item only"),
        (lambda: amulet(rolled(LIFE_1), corrupted=True), "corrupted"),
        (lambda: amulet(rolled(LOCK_SUFFIXES, crafted=True), holder(SUF)), "would keep the veiled mod"),  # a veil on the locked side
        (lambda: amulet(ExplicitMod(PRE, 1, holder(PRE).values, fractured=True)), "would keep the veiled mod"),
        (lambda: amulet(rolled(LOCK_SUFFIXES, crafted=True), rolled(VEIL_LIFE_1, fractured=True)), "would keep the veiled mod"),  # a mod unveiled from the pool, fractured
        (lambda: amulet(rolled(RESIST_2, fractured=True), rolled(COLD_RESIST, fractured=True), rolled(MANA_1, fractured=True), rolled(LIFE_1, fractured=True), rolled(DAMAGE_1, fractured=True), rolled(GEM, fractured=True)), "no room"),
    ],
    ids=["normal", "magic", "corrupted", "veil_on_locked_side", "fractured_placeholder", "fractured_unveiled", "every_slot_kept"],
)
def test_a_veiled_chaos_orb_refusals(item, reason):
    with pytest.raises(NotApplicableError, match=reason):
        VeiledChaosOrb().outcomes(DATA, item())


def test_a_veiled_mod_on_the_open_side_is_rerolled_away():
    on_open_side = amulet(rolled(LOCK_SUFFIXES, crafted=True), holder(PRE))  # the lock is a prefix, locking the suffixes: the veil is free
    assert [part.forced for _, part in VeiledChaosOrb().outcomes(DATA, on_open_side).components] == [PRE, SUF]


# --- the Veiled Exalted Orb ------------------------------------------------------------------------------------------------


def results_of(item: Item) -> dict[tuple[frozenset[str], str], Fraction]:
    """`{(mod ids without the placeholder, the placeholder): chance}` of a Veiled Exalted Orb on `item`."""
    found: dict[tuple[frozenset[str], str], Fraction] = {}
    for chance, result in VeiledExaltedOrb().outcomes(DATA, item).results:
        (veil,) = (entry.mod_id for entry in result.mods if DATA.mods[entry.mod_id].domain == "veiled")
        key = (frozenset(ids(result) - {veil}), veil)
        found[key] = found.get(key, F(0)) + chance
    return found


def test_one_mod_is_removed_uniformly_and_the_veil_goes_to_either_side_when_both_have_room():
    assert results_of(amulet(rolled(LIFE_1), rolled(RESIST_2))) == {
        (frozenset({RESIST_2}), PRE): F(1, 4),
        (frozenset({RESIST_2}), SUF): F(1, 4),
        (frozenset({LIFE_1}), PRE): F(1, 4),
        (frozenset({LIFE_1}), SUF): F(1, 4),
    }


def test_the_removal_frees_the_only_slot_the_veil_can_take():
    # three prefixes and one suffix: removing a suffix leaves the prefixes full, so the veil is a suffix; removing a prefix leaves room
    # on both sides (1/2 each). The veil is a suffix with 1/4 + 3/4 * 1/2 = 5/8 and a prefix with 3/8.
    start = amulet(rolled(LIFE_1), rolled(DAMAGE_1), rolled(GEM), rolled(RESIST_2))
    shown = results_of(start)
    assert sum(chance for (_, veil), chance in shown.items() if veil == SUF) == F(5, 8)
    assert sum(chance for (_, veil), chance in shown.items() if veil == PRE) == F(3, 8)
    assert shown[(frozenset({LIFE_1, DAMAGE_1, GEM}), SUF)] == F(1, 4)
    assert shown[(frozenset({DAMAGE_1, GEM, RESIST_2}), PRE)] == F(1, 8) and shown[(frozenset({DAMAGE_1, GEM, RESIST_2}), SUF)] == F(1, 8)


def test_a_lock_is_respected_by_the_removal_and_the_metamod_itself_can_be_removed_the_fifty_fifty_of_r22():
    # the suffixes are locked and full; the prefixes hold the lock and Life: the removal hits the lock or Life, 1/2 each, and the veil is a prefix
    start = amulet(rolled(LOCK_SUFFIXES, crafted=True), rolled(LIFE_1), rolled(RESIST_2), rolled(COLD_RESIST), rolled(MANA_1))
    assert results_of(start) == {
        (frozenset({LIFE_1, RESIST_2, COLD_RESIST, MANA_1}), PRE): F(1, 2),  # the lock is gone
        (frozenset({LOCK_SUFFIXES, RESIST_2, COLD_RESIST, MANA_1}), PRE): F(1, 2),  # Life is gone
    }


def test_the_veil_ignores_a_lock_with_room_after_the_removal_too():
    start = amulet(rolled(LOCK_SUFFIXES, crafted=True), rolled(LIFE_1), rolled(RESIST_2))
    shown = results_of(start)
    assert shown[(frozenset({LIFE_1, RESIST_2}), SUF)] == F(1, 4)  # the lock removed: the suffix side takes the veil
    assert shown[(frozenset({LOCK_SUFFIXES, RESIST_2}), SUF)] == F(1, 4)  # a locked suffix side with room takes the veil too
    assert sum(shown.values()) == 1


def test_fractured_mods_stay():
    # only the suffix can be removed; both sides then have room
    assert results_of(amulet(rolled(LIFE_1, fractured=True), rolled(RESIST_2))) == {
        (frozenset({LIFE_1}), PRE): F(1, 2),
        (frozenset({LIFE_1}), SUF): F(1, 2),
    }


@pytest.mark.parametrize(
    "item, reason",
    [
        (lambda: amulet(rarity=Rarity.NORMAL), "rare item only"),
        (lambda: amulet(rolled(LIFE_1), rarity=Rarity.MAGIC), "rare item only"),
        (lambda: amulet(rolled(LIFE_1), corrupted=True), "corrupted"),
        (lambda: amulet(holder(PRE), rolled(RESIST_2)), "holds the veiled mod"),
        (lambda: amulet(rolled(VEIL_LIFE_1), rolled(RESIST_2)), "holds the veiled mod"),  # a mod unveiled from the pool
        (lambda: amulet(rolled(CRAFTED_ARMOUR, crafted=True), rolled(RESIST_2)), "holds the veiled mod"),  # the craftable version of a veiled mod
        (lambda: amulet(), "every mod is fractured"),
        (lambda: amulet(rolled(LIFE_1, fractured=True), rolled(RESIST_2, fractured=True)), "every mod is fractured"),
    ],
    ids=["normal", "magic", "corrupted", "placeholder", "unveiled_mod", "craftable_version", "no_mod", "all_fractured"],
)
def test_a_veiled_exalted_orb_refusals(item, reason):
    with pytest.raises(NotApplicableError, match=reason):
        VeiledExaltedOrb().outcomes(DATA, item())


def test_a_crafted_mod_of_another_master_with_the_same_stats_is_not_a_craftable_version():
    assert results_of(amulet(rolled(OTHER_MASTER_ARMOUR, crafted=True), rolled(RESIST_2)))


def test_a_crafted_mod_can_be_the_one_removed():
    shown = results_of(amulet(rolled(OTHER_MASTER_ARMOUR, crafted=True), rolled(RESIST_2)))
    assert (frozenset({RESIST_2}), PRE) in shown and (frozenset({OTHER_MASTER_ARMOUR}), SUF) in shown


def test_a_mod_unveiled_from_the_pool_refuses_the_next_veiled_exalted_orb():
    # the owner's answer: unveil, pick, and the item takes no Veiled Exalted Orb
    _, veiled_item = VeiledExaltedOrb().outcomes(DATA, amulet(rolled(LIFE_1), rolled(RESIST_2))).results[0]
    _, offered = Unveil().outcomes(DATA, veiled_item).results[0]
    ((_, landed),) = Pick(1).outcomes(DATA, offered).results
    with pytest.raises(NotApplicableError, match="holds the veiled mod"):
        VeiledExaltedOrb().outcomes(DATA, landed)


# --- out of scope ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("action", [VeiledChaosOrb(), VeiledExaltedOrb(), Unveil(), Pick(1)], ids=lambda a: a.label())
def test_a_signature_or_a_double_veil_is_out_of_scope(action):
    signature = amulet(holder(SIGNATURE_PLACEHOLDER), rolled(RESIST_2))
    double = amulet(holder(PRE), holder(SUF))
    for item in (signature, double):
        with pytest.raises(OutOfScopeError):
            action.outcomes(DATA, item)


# --- labels, costs, the catalog and the contract ---------------------------------------------------------------------------


def test_labels_and_costs():
    assert [a.label() for a in (VeiledChaosOrb(), VeiledExaltedOrb(), Unveil(), Pick(2))] == [
        "Veiled Chaos Orb", "Veiled Exalted Orb", "Unveil", "Pick 2"
    ]
    assert VeiledChaosOrb().resources() == {"Veiled Chaos Orb": 1}
    assert VeiledExaltedOrb().resources() == {"Veiled Exalted Orb": 1}
    assert Unveil().resources() == {} and Pick(1).resources() == {}  # unveiling is free (the planner counts the solver's epsilon: `price_offers`)


def test_the_four_kinds_are_listed_for_a_rare_item_only_and_are_opt_in_planner_kinds():
    registered = {entry.name: entry for entry in kinds()}
    names = ("veiled-chaos-orb", "veiled-exalted-orb", "unveil", "pick")
    assert all(name in registered and registered[name].planner and registered[name].opt_in for name in names)  # named by a target, never offered by default
    rare = catalog(DATA, amulet(rolled(RESIST_2)), names=names)
    assert [a.label() for a in rare] == ["Veiled Chaos Orb", "Veiled Exalted Orb", "Unveil", "Pick 1", "Pick 2", "Pick 3"]
    assert catalog(DATA, amulet(rolled(LIFE_1), rarity=Rarity.MAGIC), names=names) == ()


def test_each_action_names_its_claims_and_the_approximate_ones_are_the_coe_readings():
    from crafting_system.rules import rule_by_id

    approximate = {
        rule_id
        for action in (VeiledChaosOrb(), VeiledExaltedOrb(), Unveil(), Pick(1))
        for rule_id in action.claims(DATA)
        if rule_by_id(rule_id).approximate
    }
    assert {
        "veiled.chaos_placement_side",  # the veil ignores a lock with room
        "veiled.exalted_refused_after_an_unveil",
        "unveil.offer_drawn_once_and_fixed",
        "unveil.no_offer_filter_no_level_gate",
        "unveil.offer_draw_three_families_no_repeat",
    } <= approximate
    assert "unveil.offer_drawn_once_and_fixed" in Pick(1).claims(DATA) and "veiled.chaos_cost" not in Unveil().claims(DATA)


@pytest.mark.parametrize(
    "action, item",
    [
        (VeiledChaosOrb(), lambda: amulet(rolled(LIFE_1), rolled(RESIST_2))),
        (VeiledChaosOrb(), lambda: amulet(holder(PRE), rolled(RESIST_2), veil_offer=(ARMOUR, VEIL_LIFE_1, MANA))),
        (VeiledExaltedOrb(), lambda: amulet(rolled(LIFE_1), rolled(RESIST_2))),
        (Unveil(), lambda: amulet(holder(PRE), rolled(RESIST_2))),
        (Unveil(), lambda: amulet(holder(SUF), rolled(LIFE_1))),
        (Pick(1), lambda: amulet(holder(PRE), rolled(RESIST_2), veil_offer=(ARMOUR, VEIL_LIFE_1, MANA))),
        (Pick(3), lambda: amulet(holder(PRE), rolled(RESIST_2), veil_offer=(ARMOUR, VEIL_LIFE_1, MANA))),
    ],
    ids=lambda value: value.label() if hasattr(value, "label") else "",
)
def test_the_actions_meet_the_contract_suite(action, item):
    assert check_action(action, item(), DATA)
