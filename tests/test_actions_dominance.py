"""The Orb of Dominance against a hand oracle (ticket #154).

The fixture is the Contract Helmet of `influence_support.py`. Its Shaper prefix family P has tiers P1 (level 68, tier 3), P2 (75, tier 2)
and P3 (80, tier 1); the Shaper suffix family S has S1 (tier 2) and S2 (tier 1); the Elder suffix E1 is alone in its family, so a top
tier. Their Elevated versions are P3Maven, S2Maven and E1Maven (`ELEVATED`). An Orb of Dominance on `n` influenced mods removes one
and upgrades another by one tier: each ordered pair is a result with chance 1/(n(n-1)).
"""

from fractions import Fraction

import pytest
from influence_support import (
    ELDER_P,
    ELDER_S,
    ELDER_S_MAVEN,
    ELEVATED,
    INFLUENCE_DATA,
    OLD,
    P1,
    P2,
    P3,
    P3_MAVEN,
    PLAIN,
    S1,
    S2,
    S2_MAVEN,
    helmet,
    roll,
)

from crafting_system.actions import NotApplicableError, OrbOfDominance, OutOfScopeError, catalog
from crafting_system.items import Influence, Rarity

DATA = INFLUENCE_DATA
SHAPER, ELDER = Influence.SHAPER, Influence.ELDER
BOTH = frozenset({SHAPER, ELDER})
LOCK_PREFIXES = "StrMasterItemGenerationCannotChangePrefixes"  # crafted, on the suffix side
NO_ATTACK = "IntMasterItemGenerationCannotRollAttackAffixes"
DOMINANCE = OrbOfDominance(elevated=ELEVATED)


def results(outcomes) -> dict[frozenset[str], Fraction]:
    """The result items as sets of mod ids, with their chances added up."""
    found: dict[frozenset[str], Fraction] = {}
    for chance, item in outcomes.results:
        key = frozenset(entry.mod_id for entry in item.mods)
        found[key] = found.get(key, Fraction(0)) + chance
    return found


# --- the odds ---------------------------------------------------------------------------------------------------------


def test_two_influenced_mods_remove_one_and_upgrade_the_other_with_chance_one_half_each():
    item = helmet(roll(P1, 3), roll(S1, 2), influences=frozenset({SHAPER}))
    outcomes = DOMINANCE.outcomes(DATA, item)

    assert results(outcomes) == {frozenset({S2}): Fraction(1, 2), frozenset({P2}): Fraction(1, 2)}
    assert [chance for chance, _ in outcomes.results] == [Fraction(1, 2)] * 2  # n(n-1) = 2 ordered pairs


def test_three_influenced_mods_give_six_ordered_pairs_of_chance_one_sixth():
    # P2 -> P3, S1 -> S2 and the top-tier Elder mod -> its Elevated version
    item = helmet(roll(P2, 2), roll(S1, 2), roll(ELDER_S, 1), influences=BOTH)
    outcomes = DOMINANCE.outcomes(DATA, item)

    assert len(outcomes.results) == 6 and all(chance == Fraction(1, 6) for chance, _ in outcomes.results)
    assert results(outcomes) == {
        frozenset({S2, ELDER_S}): Fraction(1, 6),  # removed P2, upgraded S1
        frozenset({S1, ELDER_S_MAVEN}): Fraction(1, 6),  # removed P2, upgraded Elder
        frozenset({P3, ELDER_S}): Fraction(1, 6),  # removed S1, upgraded P2
        frozenset({P2, ELDER_S_MAVEN}): Fraction(1, 6),  # removed S1, upgraded Elder
        frozenset({P3, S1}): Fraction(1, 6),  # removed Elder, upgraded P2
        frozenset({P2, S2}): Fraction(1, 6),  # removed Elder, upgraded S1
    }


@pytest.mark.parametrize("count", [2, 3, 4])
def test_a_pair_has_chance_one_over_n_times_n_minus_one(count):
    held = [roll(P1, 3), roll(S1, 2), roll(ELDER_S, 1), roll(ELDER_P, 1)][:count]
    outcomes = DOMINANCE.outcomes(DATA, helmet(*held, influences=BOTH))

    assert len(outcomes.results) == count * (count - 1)
    assert {chance for chance, _ in outcomes.results} == {Fraction(1, count * (count - 1))}
    assert sum(chance for chance, _ in outcomes.results) == 1


def test_a_given_mod_is_upgraded_with_chance_one_over_n():
    item = helmet(roll(P2, 2), roll(S1, 2), roll(ELDER_S, 1), influences=BOTH)
    outcomes = DOMINANCE.outcomes(DATA, item)
    # P3 is on the item after the orb exactly when P2 was the upgraded mod
    assert outcomes.chance_all([P3]) == Fraction(1, 3)
    assert outcomes.chance_all([S2]) == Fraction(1, 3) and outcomes.chance_all([ELDER_S_MAVEN]) == Fraction(1, 3)


def test_the_result_lists_exactly_one_mod_fewer_and_keeps_the_influences_and_other_mods():
    item = helmet(roll(PLAIN, 1), roll(P1, 3), roll(S1, 2), influences=frozenset({SHAPER}))
    for _, result in DOMINANCE.outcomes(DATA, item).results:
        assert len(result.mods) == 2 and result.influences == {SHAPER}
        assert any(entry.mod_id == PLAIN for entry in result.mods)  # an uninfluenced mod is neither removed nor upgraded


def test_the_upgraded_mod_is_the_next_tier_of_the_same_mod_at_its_lowest_values():
    item = helmet(roll(P1, 3), roll(S1, 2), influences=frozenset({SHAPER}))
    upgraded = next(r for _, r in DOMINANCE.outcomes(DATA, item).results if any(e.mod_id == P2 for e in r.mods))
    entry = next(e for e in upgraded.mods if e.mod_id == P2)
    assert entry.tier == 2 and entry.values == tuple(min(s.min, s.max) for s in DATA.mods[P2].stats)


# --- Elevated mods ---------------------------------------------------------------------------------------------------------


def test_a_top_tier_mod_becomes_its_elevated_version():
    item = helmet(roll(P3, 1), roll(S1, 2), influences=frozenset({SHAPER}))
    assert results(DOMINANCE.outcomes(DATA, item)) == {frozenset({S2}): Fraction(1, 2), frozenset({P3_MAVEN}): Fraction(1, 2)}
    elevated = next(e for _, r in DOMINANCE.outcomes(DATA, item).results for e in r.mods if e.mod_id == P3_MAVEN)
    assert elevated.tier == 1  # the best tier an item can store


def test_an_elevated_mod_stays_the_same_mod_when_it_is_upgraded():
    item = helmet(roll(P3_MAVEN, 1), roll(S1, 2), influences=frozenset({SHAPER}))
    assert results(DOMINANCE.outcomes(DATA, item)) == {frozenset({S2}): Fraction(1, 2), frozenset({P3_MAVEN}): Fraction(1, 2)}


def test_a_top_tier_mod_with_no_known_elevated_version_is_out_of_scope_not_guessed():
    item = helmet(roll(P3, 1), roll(S1, 2), influences=frozenset({SHAPER}))
    with pytest.raises(OutOfScopeError, match="Elevated"):
        OrbOfDominance().outcomes(DATA, item)  # the committed mapping is for the real export, not for the fixture's
    with pytest.raises(OutOfScopeError, match=P3):
        OrbOfDominance(elevated=((S2, S2_MAVEN),)).outcomes(DATA, item)
    assert OrbOfDominance(elevated=((P3, P3_MAVEN),)).outcomes(DATA, item)


def test_a_lower_tier_needs_no_elevated_mapping():
    item = helmet(roll(P1, 3), roll(S1, 2), influences=frozenset({SHAPER}))
    assert OrbOfDominance().outcomes(DATA, item)


# --- the metamods ---------------------------------------------------------------------------------------------------------------


def test_prefixes_cannot_be_changed_takes_the_prefixes_out_of_both_picks():
    # P1 is locked; S1 and the Elder suffix are the two candidates (the lock sits on the suffix side: 3 suffixes in all)
    item = helmet(roll(P1, 3), roll(S1, 2), roll(ELDER_S, 1), roll(LOCK_PREFIXES, 1, crafted=True), influences=BOTH)
    outcomes = DOMINANCE.outcomes(DATA, item)
    assert results(outcomes) == {
        frozenset({P1, S2, LOCK_PREFIXES}): Fraction(1, 2),  # removed the Elder suffix, upgraded S1
        frozenset({P1, ELDER_S_MAVEN, LOCK_PREFIXES}): Fraction(1, 2),  # removed S1, upgraded the Elder suffix
    }


def test_a_lock_that_leaves_fewer_than_two_candidates_refuses_the_orb():
    item = helmet(roll(P1, 3), roll(S1, 2), roll(LOCK_PREFIXES, 1, crafted=True), influences=frozenset({SHAPER}))
    with pytest.raises(NotApplicableError, match="1"):
        DOMINANCE.outcomes(DATA, item)


def test_the_attack_and_caster_blocks_are_ignored():
    # the Shaper prefixes carry the attack tag; Cannot roll Attack Modifiers does not stop Dominance from upgrading one
    item = helmet(roll(P1, 3), roll(S1, 2), roll(NO_ATTACK, 1, crafted=True), influences=frozenset({SHAPER}))
    assert results(DOMINANCE.outcomes(DATA, item)) == {
        frozenset({S2, NO_ATTACK}): Fraction(1, 2),
        frozenset({P2, NO_ATTACK}): Fraction(1, 2),
    }


# --- the refusals ------------------------------------------------------------------------------------------------------------------


def test_fewer_than_two_influenced_mods_refuse_the_orb():
    with pytest.raises(NotApplicableError, match="influenced mods"):
        DOMINANCE.outcomes(DATA, helmet(roll(P1, 3), roll(PLAIN, 1), influences=frozenset({SHAPER})))


def test_mods_of_an_influence_the_item_does_not_have_are_not_influenced_mods():
    with pytest.raises(NotApplicableError, match="influenced mods"):
        DOMINANCE.outcomes(DATA, helmet(roll(P1, 3), roll(S1, 2)))


def test_the_orb_works_on_a_magic_item_and_refuses_a_normal_or_corrupted_one():
    assert DOMINANCE.outcomes(DATA, helmet(roll(P1, 3), roll(S1, 2), rarity=Rarity.MAGIC, influences=frozenset({SHAPER})))
    with pytest.raises(NotApplicableError, match="normal"):
        DOMINANCE.outcomes(DATA, helmet(rarity=Rarity.NORMAL))
    with pytest.raises(NotApplicableError, match="corrupted"):
        DOMINANCE.outcomes(DATA, helmet(roll(P1, 3), roll(S1, 2), corrupted=True, influences=frozenset({SHAPER})))


def test_only_body_armour_boots_gloves_and_helmets_take_it():
    from items_support import AMULET

    from crafting_system.items import Item

    amulet = Item.build(DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=(), influences=frozenset({SHAPER}))
    with pytest.raises(NotApplicableError, match="Amulet"):
        DOMINANCE.outcomes(DATA, amulet)


def test_an_influenced_item_with_a_fractured_mod_is_out_of_scope():
    item = helmet(roll(P1, 3, fractured=True), roll(S1, 2), influences=frozenset({SHAPER}))
    with pytest.raises(OutOfScopeError, match="fractured"):
        DOMINANCE.outcomes(DATA, item)


def test_a_legacy_influence_mod_with_no_tier_is_out_of_scope():
    item = helmet(roll(OLD, 1), roll(S1, 2), influences=frozenset({SHAPER}))
    with pytest.raises(OutOfScopeError, match="no tier"):
        DOMINANCE.outcomes(DATA, item)


# --- names, claims and the catalog -----------------------------------------------------------------------------------------------------


def test_the_orb_has_its_name_price_and_approximate_claims():
    assert OrbOfDominance().label() == "Orb of Dominance" and dict(OrbOfDominance().resources()) == {"Orb of Dominance": 1}
    claims = OrbOfDominance().claims()
    assert {"dominance.picks_uniform_remove_first", "dominance.elevated_mapping_is_coe_table", "dominance.upgrade_ignores_item_level"} <= claims
    assert not claims & {"influence.exalt_refused_on_eldritch_implicit", "influence_beast.adds_a_mod_of_that_influence"}


def test_the_catalog_offers_the_orb_on_an_influenced_armour_piece_only():
    shaper = helmet(roll(P1, 3), roll(S1, 2), influences=frozenset({SHAPER}))
    assert [a for a in catalog(DATA, shaper) if isinstance(a, OrbOfDominance)] == [OrbOfDominance()]
    assert not [a for a in catalog(DATA, helmet(roll(P1, 3), roll(S1, 2))) if isinstance(a, OrbOfDominance)]
