"""The Awakener's Orb in the compressed state: a ring that gets a second influence, and the key of the donor's want (ticket #214, ADR-0032, ADR-0062, ADR-0019).

The data is a Contract Ring (item class Ring, whose influence class key is `ring`) with the shape of R18: a Crusader ring that needs its tier 1 prefix and a Shaper
suffix carried over, and a curse suffix of one family that a Crusader ring and a Shaper ring both hold (the Shaper one at weight 0, as the Assassin's Mark mods are),
so that the two kept mods can meet in a group conflict.

    id                   side    family            level  weight  on tag          influence
    ContractRingPlainP1  prefix  ContractRingPlP1    1     1000   ring            -
    ContractRingPlainP2  prefix  ContractRingPlP2    1      800   ring            -
    ContractRingPlainS1  suffix  ContractRingPlS1    1      900   ring            -
    ContractRingPlainS2  suffix  ContractRingPlS2    1      700   ring            -
    ContractRingCrusP1   prefix  ContractRingCrusP  68      300   ring_crusader   Crusader
    ContractRingCrusP2   prefix  ContractRingCrusP  80      200   ring_crusader   Crusader
    ContractRingCrusCurse suffix ContractRingCurse  70      400   ring_crusader   Crusader
    ContractRingShapS1   suffix  ContractRingShapS  68      500   ring_shaper     Shaper
    ContractRingShapP1   prefix  ContractRingShapP  75      300   ring_shaper     Shaper
    ContractRingShapCurse suffix ContractRingCurse  75        0   ring_shaper     Shaper (weight 0: carried over only)

* layer 1 (ADR-0019): for every concrete ring that the four Awakener's Orbs reach from Crusader and Shaper starts, at each reading of the group conflict, the kernel
  of the item's state equals the finished items of the orb on it, compressed one by one and added up exactly (`abstraction_b2_support.check_layer_1`); the rings it
  reaches hold two influences;
* the key of the donor's want (`Abstraction.donor_key`): the donor's influence, whether it is corrupted and its influence mods by mod id, nothing else. Two donors with one
  key give the orb one kernel (the orb is built from the key's fields); a donor that holds another influence mod, a second one, another influence or is corrupted has
  another key; an action that declares nothing about its input has the whole compressed state as its key.
"""

import dataclasses

import pytest
from abstraction_b2_support import check_layer_1, closure
from influence_support import INFLUENCE_DATA, PREFIX_TEMPLATE, SUFFIX_TEMPLATE

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import AnnulmentOrb, AwakenersOrb, ChaosOrb, NotApplicableError, Reading, tiers_of
from crafting_system.data import BaseItem, Weight
from crafting_system.items import ExplicitMod, Influence, Item, Rarity

CRUSADER, SHAPER = Influence.CRUSADER, Influence.SHAPER
RING = "Metadata/Items/Rings/ContractRing"
LEVEL = 84

PLAIN_P1, PLAIN_P2, PLAIN_S1, PLAIN_S2 = "ContractRingPlainP1", "ContractRingPlainP2", "ContractRingPlainS1", "ContractRingPlainS2"
CRUS_P1, CRUS_P2, CRUS_CURSE = "ContractRingCrusP1", "ContractRingCrusP2", "ContractRingCrusCurse"
SHAP_S1, SHAP_P1, SHAP_CURSE = "ContractRingShapS1", "ContractRingShapP1", "ContractRingShapCurse"
# id: (side, family, required level, weight, tag)
RING_MODS = {
    PLAIN_P1: ("prefix", "ContractRingPlP1", 1, 1000, "ring"),
    PLAIN_P2: ("prefix", "ContractRingPlP2", 1, 800, "ring"),
    PLAIN_S1: ("suffix", "ContractRingPlS1", 1, 900, "ring"),
    PLAIN_S2: ("suffix", "ContractRingPlS2", 1, 700, "ring"),
    CRUS_P1: ("prefix", "ContractRingCrusP", 68, 300, "ring_crusader"),
    CRUS_P2: ("prefix", "ContractRingCrusP", 80, 200, "ring_crusader"),
    CRUS_CURSE: ("suffix", "ContractRingCurse", 70, 400, "ring_crusader"),
    SHAP_S1: ("suffix", "ContractRingShapS", 68, 500, "ring_shaper"),
    SHAP_P1: ("prefix", "ContractRingShapP", 75, 300, "ring_shaper"),
    SHAP_CURSE: ("suffix", "ContractRingCurse", 75, 0, "ring_shaper"),
}


def build_data():
    ring = BaseItem(RING, "Contract Ring", "Ring", "item", 1, ("ring", "default", "jewellery"), (), "released")
    mods = {}
    for mod_id, (side, family, level, weight, tag) in RING_MODS.items():
        template = INFLUENCE_DATA.mods[PREFIX_TEMPLATE if side == "prefix" else SUFFIX_TEMPLATE]
        mods[mod_id] = dataclasses.replace(
            template,
            id=mod_id,
            name=family,
            type=family,
            families=(family,),
            generation_type=side,
            required_level=level,
            spawn_weights=(Weight(tag, weight), Weight("default", 0)),
            generation_weights=(),
        )
    # only these mods: a pool of eight families keeps the exact oracle (every finished ring, one by one) to a few thousand items
    return dataclasses.replace(INFLUENCE_DATA, mods=mods, base_items={**INFLUENCE_DATA.base_items, RING: ring})


DATA = build_data()

# the four orbs: a Crusader or a Shaper receiver takes a donor of the other influence that holds one of its influence mods
ORBS = (
    AwakenersOrb(RING, LEVEL, SHAPER, SHAP_S1),
    AwakenersOrb(RING, LEVEL, SHAPER, SHAP_CURSE),
    AwakenersOrb(RING, LEVEL, CRUSADER, CRUS_P2),
    AwakenersOrb(RING, LEVEL, CRUSADER, CRUS_CURSE),
)
SHAPER_S1_ORB, SHAPER_CURSE_ORB, CRUSADER_P2_ORB, CRUSADER_CURSE_ORB = ORBS

READINGS = {name: Reading.of({"awakener.group_conflict": name}) for name in ("receiver", "donor")}

TOP_PREFIX = Wanted(frozenset({CRUS_P1, CRUS_P2}), min_tier=1)  # tier 1 of the Crusader prefixes
SHAPER_SUFFIX = Wanted(frozenset({SHAP_S1}))
CURSE = Wanted(frozenset({CRUS_CURSE, SHAP_CURSE}))
GOAL = Goal((TOP_PREFIX, SHAPER_SUFFIX, CURSE))


def ring(*mods: str, influences=(), rarity=Rarity.RARE, **fields) -> Item:
    """A Contract Ring holding `mods`, each at the tier it has on the ring's pool, at its lowest values."""
    bare = Item.build(DATA, base_id=RING, item_level=LEVEL, rarity=rarity, influences=frozenset(influences))
    tiers = tiers_of(DATA, bare)
    entries = tuple(
        ExplicitMod(mod_id, tiers.get(mod_id, 1), tuple(min(stat.min, stat.max) for stat in DATA.mods[mod_id].stats)) for mod_id in mods
    )
    return bare.changed(DATA, mods=entries, **fields)


def ability(actions, goal=GOAL, **options) -> Abstraction:
    return Abstraction(DATA, goal, RING, LEVEL, actions, **options)


def starts() -> dict:
    return {
        "crusader_two": ring(CRUS_P1, PLAIN_S1, PLAIN_P1, influences={CRUSADER}),
        "crusader_curse": ring(CRUS_P2, CRUS_CURSE, PLAIN_P2, PLAIN_S2, influences={CRUSADER}),
        "crusader_all_influenced": ring(CRUS_P1, CRUS_CURSE, PLAIN_S1, influences={CRUSADER}),
        "crusader_magic": ring(CRUS_P1, influences={CRUSADER}, rarity=Rarity.MAGIC),
        "shaper_two": ring(SHAP_S1, SHAP_P1, PLAIN_P1, influences={SHAPER}),
        "shaper_curse": ring(SHAP_CURSE, PLAIN_S1, PLAIN_P2, influences={SHAPER}),
        "shaper_one": ring(SHAP_P1, PLAIN_S2, influences={SHAPER}),
        "plain": ring(PLAIN_P1, PLAIN_S1),
    }


# --- layer 1 -------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["receiver", "donor"])
def test_layer_1_of_the_awakeners_orb_on_a_ring_that_gets_a_second_influence(name):
    reading = READINGS[name]
    found = ability(ORBS, reading=reading)
    assert found.tells_influenced
    items = closure(DATA, starts().values(), ORBS, limit=120, reading=reading)
    applied = dict.fromkeys(ORBS, 0)
    for held in items:
        for orb in ORBS:
            applied[orb] += check_layer_1(found, DATA, held, orb)
    assert all(applied.values()), applied
    assert any(len(held.influences) == 2 for held in items)  # the orbs make rings of two influences
    assert any(held.influences == {CRUSADER, SHAPER} and {m.mod_id for m in held.mods} >= {CRUS_P1, SHAP_S1} for held in items)  # both kept mods are held


def test_the_two_readings_of_a_group_conflict_differ_in_the_state_and_agree_without_one():
    receiver, donor = (ability(ORBS, reading=READINGS[name]) for name in READINGS)
    clash = ring(CRUS_P1, CRUS_CURSE, PLAIN_S1, influences={CRUSADER})  # the orb with a Shaper curse donor meets the Crusader curse
    free = ring(CRUS_P1, PLAIN_S1, influences={CRUSADER})  # nothing to clash with
    assert check_layer_1(receiver, DATA, clash, SHAPER_CURSE_ORB) and check_layer_1(donor, DATA, clash, SHAPER_CURSE_ORB)
    assert receiver.kernel(receiver.compress(clash), SHAPER_CURSE_ORB) != donor.kernel(donor.compress(clash), SHAPER_CURSE_ORB)
    assert receiver.kernel(receiver.compress(free), SHAPER_S1_ORB) == donor.kernel(donor.compress(free), SHAPER_S1_ORB)


@pytest.mark.parametrize(
    "goal",
    [Goal((TOP_PREFIX,)), Goal((SHAPER_SUFFIX, CURSE)), Goal((Wanted(frozenset({CRUS_P1, CRUS_P2}), min_tier=2),))],
    ids=["tier_one", "carried_over", "tier_two"],
)
def test_layer_1_for_other_goals(goal):
    found = ability(ORBS, goal)
    items = closure(DATA, starts().values(), ORBS, limit=60)
    applied = dict.fromkeys(ORBS, 0)
    for held in items:
        for orb in ORBS:
            applied[orb] += check_layer_1(found, DATA, held, orb)
    assert all(applied.values()), applied


def test_layer_1_beside_an_annulment_and_a_chaos_orb():
    actions = (*ORBS, AnnulmentOrb(), ChaosOrb())
    found = ability(actions)
    items = closure(DATA, starts().values(), actions, limit=80)
    for held in items:
        for action in actions:
            check_layer_1(found, DATA, held, action)


# --- the donor's want ----------------------------------------------------------------------------------------------------


def shaper_donor(*mods: str, **fields) -> Item:
    return ring(*mods, influences={SHAPER}, **fields)


def orb_of(found: Abstraction, donor: Item) -> AwakenersOrb:
    """The orb a donor calls for, made from the fields of its key: its influence and the one influence mod it holds."""
    influences, _, named = found.donor_key(found.compress(donor), SHAPER_S1_ORB)
    (influence,), (kind,) = influences, named
    return AwakenersOrb(RING, LEVEL, influence, kind[1:])


def test_donors_with_one_key_are_the_same_want_and_give_the_orb_one_kernel():
    found = ability(ORBS)
    (need,) = found.inputs(found.compress(starts()["crusader_two"]), SHAPER_S1_ORB)
    wanted = found.donor_key(found.compress(need.want), SHAPER_S1_ORB)
    assert wanted == (frozenset({SHAPER}), False, (f"${SHAP_S1}",))
    reach = found.reaches_donor(SHAPER_S1_ORB)
    # the donor of the need, and donors that hold more of the ordinary mods, another rarity, other tiers of the junk: one key
    same = [
        shaper_donor(SHAP_S1),
        shaper_donor(SHAP_S1, PLAIN_P1),
        shaper_donor(SHAP_S1, PLAIN_P1, PLAIN_P2, PLAIN_S1),
        shaper_donor(SHAP_S1, PLAIN_P1, rarity=Rarity.MAGIC),
    ]
    for donor in same:
        state = found.compress(donor)
        assert found.donor_key(state, SHAPER_S1_ORB) == wanted
        assert reach(state, found.compress(need.want))
    assert len({found.compress(donor) for donor in same}) == len(same)  # whole items they are different states
    # the orb a donor calls for is built from the key's fields, so donors with one key give equal orbs and one kernel
    orbs = {orb_of(found, donor) for donor in same}
    assert orbs == {SHAPER_S1_ORB}
    receiver = found.compress(starts()["crusader_curse"])
    assert {frozenset(found.kernel(receiver, orb).items()) for orb in orbs} == {frozenset(found.kernel(receiver, SHAPER_S1_ORB).items())}


def test_a_donor_with_another_influence_mod_another_influence_or_corruption_is_another_want():
    found = ability(ORBS)
    reach = found.reaches_donor(SHAPER_S1_ORB)
    want = found.compress(shaper_donor(SHAP_S1))
    others = [
        shaper_donor(SHAP_P1),  # another Shaper mod
        shaper_donor(SHAP_S1, SHAP_P1),  # a second influence mod
        shaper_donor(PLAIN_P1),  # none
        ring(CRUS_P1, influences={CRUSADER}),  # another influence
        shaper_donor(SHAP_S1, corrupted=True),  # the game refuses a corrupted donor
    ]
    for donor in others:
        assert not reach(found.compress(donor), want), donor
    assert found.donor_key(found.compress(shaper_donor(SHAP_S1)), SHAPER_S1_ORB) != found.donor_key(found.compress(shaper_donor(SHAP_CURSE)), SHAPER_S1_ORB)


def test_an_action_that_declares_nothing_about_its_input_has_the_whole_state_as_the_key():
    found = ability((*ORBS, AnnulmentOrb()))
    state = found.compress(starts()["crusader_two"])
    assert found.donor_key(state, AnnulmentOrb()) is state
    assert not AnnulmentOrb().reads(DATA).input_influenced
    assert SHAPER_S1_ORB.reads(DATA).input_influenced and SHAPER_S1_ORB.reads(DATA).input_mods


def test_a_donor_of_the_receivers_own_influence_is_refused_by_the_orb_whatever_its_key():
    found = ability(ORBS)
    with pytest.raises(NotApplicableError):
        found.kernel(found.compress(starts()["shaper_two"]), SHAPER_S1_ORB)
