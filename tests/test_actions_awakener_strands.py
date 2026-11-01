"""What the Awakener's Orb declares about Memory Strands (ticket #289, B5-11f, ADR-0041).

"Done when" and where it is shown: the claim for the declaration (`test_the_strand_claims_are_exactly_the_cut_the_law_and_the_ceiling`);
the spend is applied on the receiver (`test_a_stranded_receiver_gets_a_spent_result_with_the_uniform_law_of_the_ceiling_100`); the rerolled
mods are cut and the kept mods are not (`test_the_rerolled_mods_are_drawn_from_the_cut_pool_and_the_kept_mods_are_those_of_0_strands`).
Both readings of the group conflict behave the same way; at 0 strands nothing changes by a bit.
"""

import random
from fractions import Fraction

import pytest
from awakener_support import CRUSADER_CLASH, CRUSADER_SUFFIX
from contract_support import CONTRACT_DATA, fixture_items
from items_support import AMULET

from crafting_system.actions import AwakenersOrb, Reading, Spent, SpendLaw, strands_after
from crafting_system.actions.cut import Cut
from crafting_system.actions.strand_use import CUT_CLAIMS
from crafting_system.actions.pool import build_pool
from crafting_system.items import Influence

DATA = CONTRACT_DATA
READINGS = {name: Reading.of({"awakener.group_conflict": name}) for name in ("receiver", "donor")}
EXTRA_CLAIMS = {
    "memory_strands.spend_ranges_special_orbs",
    "memory_strands.cut_follows_spend_table",
    "memory_strands.spend_law_uniform",
}
ONE = Fraction(1)


def orb(donor_mod: str = CRUSADER_SUFFIX) -> AwakenersOrb:
    return AwakenersOrb(AMULET, 84, Influence.CRUSADER, donor_mod)


def receiver(strands: int):
    return fixture_items()["rare_awakener"].changed(DATA, memory_strands=strands)


def kept(part) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((entry.mod_id, entry.tier) for entry in part.retained.mods))


# --- the declaration and its claims -----------------------------------------------------------------------------------


def test_the_orb_declares_that_it_cuts_and_spends_0_to_100():
    use = orb().strand_use(DATA)

    assert use is not None and use.cuts is True and use.spend == SpendLaw.uniform(100)
    assert use.spend.ceiling(len(receiver(5).mods)) == 100  # whatever the item holds


def test_the_strand_claims_are_exactly_the_cut_the_law_and_the_ceiling():
    claims = orb().strand_claims(DATA)

    assert claims == {rule.id for rule in CUT_CLAIMS} | EXTRA_CLAIMS
    for name in ("memory_strands.spend_ranges_special_orbs", "memory_strands.cut_follows_spend_table"):
        assert name in claims


@pytest.mark.parametrize("donor_mod", [CRUSADER_SUFFIX, CRUSADER_CLASH])
def test_the_strand_claims_are_not_among_the_claims_of_an_answer(donor_mod):
    assert not (orb(donor_mod).claims(DATA) & orb(donor_mod).strand_claims(DATA))


# --- the spend is applied on the receiver -----------------------------------------------------------------------------


@pytest.mark.parametrize("reading", READINGS)
@pytest.mark.parametrize("donor_mod", [CRUSADER_SUFFIX, CRUSADER_CLASH])
@pytest.mark.parametrize("strands", [100, 3])
def test_a_stranded_receiver_gets_a_spent_result_with_the_uniform_law_of_the_ceiling_100(strands, donor_mod, reading):
    item = receiver(strands)
    result = orb(donor_mod).outcomes_under(DATA, item, READINGS[reading])

    assert isinstance(result, Spent) and result.before == strands
    expected = SpendLaw.uniform(100).after(strands, len(item.mods))
    assert result.strands_after == expected and strands_after(result, strands) == expected
    assert sum(expected.values()) == ONE
    if strands == 3:  # a spend of 3 or more (98 of the 101 values) empties it; 1 and 2 leave 2 and 1; 0 leaves 3
        assert expected == {0: Fraction(98, 101), 1: Fraction(1, 101), 2: Fraction(1, 101), 3: Fraction(1, 101)}
    else:
        assert expected == {left: Fraction(1, 101) for left in range(101)}  # 100 strands, a spend of 0 to 100: every count once
    seen = {result.sample(random.Random(seed)).memory_strands for seed in range(60)}
    assert seen <= set(expected)
    assert len(seen) > 1 or strands == 3  # at 100 strands the sampler is not stuck on one count


def test_the_sampler_follows_the_spend_and_keeps_the_rest_of_the_item_as_the_draw_gives_it():
    item = receiver(3)
    result = orb().outcomes(DATA, item)
    counts = [result.sample(random.Random(seed)).memory_strands for seed in range(200)]

    assert set(counts) <= {0, 1, 2, 3}
    assert counts.count(0) > 150  # 98/101 of the draws empty the count


# --- the cut -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("reading", READINGS)
@pytest.mark.parametrize("donor_mod", [CRUSADER_SUFFIX, CRUSADER_CLASH])
@pytest.mark.parametrize("strands", [3, 100])
def test_the_rerolled_mods_are_drawn_from_the_cut_pool_and_the_kept_mods_are_those_of_0_strands(strands, donor_mod, reading):
    stranded = orb(donor_mod).outcomes_under(DATA, receiver(strands), READINGS[reading])
    plain = orb(donor_mod).outcomes_under(DATA, receiver(0), READINGS[reading])

    assert [share for share, _ in stranded.components] == [share for share, _ in plain.components]
    for (_, cut_part), (_, plain_part) in zip(stranded.components, plain.components, strict=True):
        assert kept(cut_part) == kept(plain_part)  # the kept mods keep their tier: they are not cut
        assert cut_part.pool == build_pool(DATA, cut_part.retained, cut=Cut(strands))
        assert plain_part.pool == build_pool(DATA, plain_part.retained)
        assert cut_part.pool != plain_part.pool  # the cut bites on this fixture's tier tables
    assert stranded.distribution(lambda mod: mod.id) != plain.distribution(lambda mod: mod.id)


def test_the_two_readings_of_the_group_conflict_cut_alike():
    for strands in (3, 100):
        for name in READINGS:
            result = orb(CRUSADER_CLASH).outcomes_under(DATA, receiver(strands), READINGS[name])
            assert all(part.pool == build_pool(DATA, part.retained, cut=Cut(strands)) for _, part in result.components)
    receiver_reading = orb(CRUSADER_CLASH).outcomes_under(DATA, receiver(100), READINGS["receiver"])
    donor_reading = orb(CRUSADER_CLASH).outcomes_under(DATA, receiver(100), READINGS["donor"])
    assert [kept(part) for _, part in receiver_reading.components] != [kept(part) for _, part in donor_reading.components]


# --- 0 strands: nothing changes by a bit -------------------------------------------------------------------------------


@pytest.mark.parametrize("reading", READINGS)
@pytest.mark.parametrize("donor_mod", [CRUSADER_SUFFIX, CRUSADER_CLASH])
def test_at_0_strands_the_result_is_the_draw_itself_from_the_uncut_pool(donor_mod, reading):
    item = receiver(0)
    result = orb(donor_mod).outcomes_under(DATA, item, READINGS[reading])

    assert not isinstance(result, Spent)
    assert strands_after(result, 0) == {0: ONE}
    for _, part in result.components:
        assert part.pool == build_pool(DATA, part.retained)
        assert part.pool == build_pool(DATA, part.retained, cut=Cut(0))
        assert part.retained.memory_strands == 0
    assert result.sample(random.Random(1)).memory_strands == 0
