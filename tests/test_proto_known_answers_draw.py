"""The prototype's hand-computed known answers KA01-KA26 and its identity counterexample, on today's exact draw (ticket #73).

Every expected value is hand arithmetic from `archive/prototype` (`docs/research/known-answers.md`,
`docs/specs/2026-09-21-known-answers.md`, `docs/specs/2026-09-21-bounded-policy-solver.md`), typed as
a `Fraction` with its derivation in the test id. The pools are synthetic; the probability of an event
is the sum of the probabilities of the outcomes of `exact_distribution` whose drawn labels match it.
"""

from fractions import Fraction as F

import pytest
from abstraction_pool import DAMAGE_1, LIFE_1, fractured_item
from abstraction_support import CHAOS, REFORGE, abstraction
from proto_draw_support import PREFIX, SUFFIX, chance, distribution, draws, drawn, family


def known(ka, derivation, event, expected):
    """One parameter: the stable id and the hand derivation in the pytest id, the event and the expected value."""
    return pytest.param(event, expected, id=f"{ka}-{derivation}")


def has(*names):
    return lambda found: set(names) <= found


def exactly(*names):
    return lambda found: found == set(names)


ABC = (family("A", PREFIX, 1), family("B", PREFIX, 1), family("C", PREFIX, 2))
ONE_EACH = {PREFIX: 1, SUFFIX: 1}


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        known("KA01", "exact AB: 1/4*1/3 + 1/4*1/3", exactly("A", "B"), F(1, 6)),
        known("KA02", "exact AC: two weighted orders", exactly("A", "C"), F(5, 12)),
        known("KA03", "exact BC: symmetry with AC", exactly("B", "C"), F(5, 12)),
        known("KA04", "has A: 1-(1/4*2/3+2/4*1/2)", has("A"), F(7, 12)),
        known("KA05", "has B: symmetry with A", has("B"), F(7, 12)),
        known("KA06", "has C: 1-P(AB)", has("C"), F(5, 6)),
        known("KA07", "no A: P(BC)", lambda found: "A" not in found, F(5, 12)),
        known("KA08", "A and not B: P(AC)", lambda found: "A" in found and "B" not in found, F(5, 12)),
    ],
)
def test_abc_prefixes_of_weight_1_1_2_two_draws(event, expected):
    assert chance(distribution(ABC, totals=draws(2)), event) == expected


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        known("KA09", "has A: in 3 of the 4 omissions", has("A"), F(3, 4)),
        known("KA10", "has A and B: in 2 of the 4 omissions", has("A", "B"), F(1, 2)),
        known("KA11", "exactly ABC: D omitted", exactly("A", "B", "C"), F(1, 4)),
    ],
)
def test_four_equal_families_three_draws(event, expected):
    pool = tuple(family(name, PREFIX, 1) for name in "ABCD")

    assert chance(distribution(pool, totals=draws(3)), event) == expected


# Family X holds the hit A1 (weight 1) and the junk A2 (weight 3); B and C weigh 2 each.
@pytest.mark.parametrize(
    ("event", "expected"),
    [
        known("KA12", "hit: X drawn 5/6 times hit share 1/4", has("A1"), F(5, 24)),
        known("KA13", "hit and B: X and B drawn 5/12 times 1/4", has("A1", "B"), F(5, 48)),
        known("KA14", "B and C: weighted pair", exactly("B", "C"), F(1, 6)),
    ],
)
def test_a_family_with_a_hit_and_a_junk_mod_two_draws(event, expected):
    pool = (family("X", PREFIX, ("A1", 1), ("A2", 3)), family("B", PREFIX, 2), family("C", PREFIX, 2))

    assert chance(distribution(pool, totals=draws(2)), event) == expected


# Prefix A (1) and suffix B (3), one free slot each, one or two mods with chance 1/2 each.
HALF = {1: F(1, 2), 2: F(1, 2)}
CAPPED_AB = (family("A", PREFIX, 1), family("B", SUFFIX, 3))


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        known("KA15", "only A: half the mass times P(A)=1/4", exactly("A"), F(1, 8)),
        known("KA16", "only B: half the mass times P(B)=3/4", exactly("B"), F(3, 8)),
        known("KA17", "A and B: the two-mod half always has both", exactly("A", "B"), F(1, 2)),
        known("KA18", "has A: 1/8 + 1/2", has("A"), F(5, 8)),
    ],
)
def test_one_or_two_mods_with_one_slot_a_side(event, expected):
    assert chance(distribution(CAPPED_AB, ONE_EACH, HALF), event) == expected


def test_ka19_the_expected_number_of_mods_is_one_and_a_half():
    """KA19: E[count] = (1 + 2) / 2."""
    shown = distribution(CAPPED_AB, ONE_EACH, HALF)

    assert sum(len(drawn(outcome)) * value for outcome, value in shown.items()) == F(3, 2)


def staged_chances():
    """P(the three drawn families) of prefixes A, B and suffixes C, D (weight 1): two draws with one slot a side,
    then one more draw with two slots a side from the families left. The two stages are chained by hand."""
    families = {
        "A": family("A", PREFIX, 1),
        "B": family("B", PREFIX, 1),
        "C": family("C", SUFFIX, 1),
        "D": family("D", SUFFIX, 1),
    }
    result: dict[frozenset, F] = {}
    for outcome, value in distribution(tuple(families.values()), ONE_EACH, draws(2)).items():
        rest = tuple(f for name, f in families.items() if name not in drawn(outcome))
        for second, inner in distribution(rest, {PREFIX: 2, SUFFIX: 2}, draws(1)).items():
            three = drawn(outcome) | drawn(second)
            result[three] = result.get(three, F(0)) + value * inner
    return result


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        known("KA20", "ABC: four equiprobable staged outcomes", exactly("A", "B", "C"), F(1, 4)),
        known("KA21", "ABD: four equiprobable staged outcomes", exactly("A", "B", "D"), F(1, 4)),
        known("KA22", "has A: absent only from BCD", has("A"), F(3, 4)),
    ],
)
def test_two_draws_then_one_more_from_the_families_left(event, expected):
    staged = staged_chances()

    assert sum(staged.values()) == 1
    assert sum((value for found, value in staged.items() if event(found)), F(0)) == expected


# Prefixes A (1) and B (3), suffix C (2), one slot a side, two draws: one prefix and C.
@pytest.mark.parametrize(
    ("event", "expected"),
    [
        known("KA23", "exact AC: A first 1/6 + C first 1/3*1/4", exactly("A", "C"), F(1, 4)),
        known("KA24", "exact BC: the rest of the mass", exactly("B", "C"), F(3, 4)),
    ],
)
def test_a_full_side_closes(event, expected):
    pool = (family("A", PREFIX, 1), family("B", PREFIX, 3), family("C", SUFFIX, 2))

    assert chance(distribution(pool, ONE_EACH, draws(2)), event) == expected


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        known("KA25", "B: remaining B:C weights 1:2", exactly("B"), F(1, 3)),
        known("KA26", "C: remaining B:C weights 1:2", exactly("C"), F(2, 3)),
    ],
)
def test_a_blocked_family_is_left_out_of_the_draw(event, expected):
    assert chance(distribution(ABC[1:]), event) == expected


@pytest.mark.parametrize(
    ("pool_left", "expected"),
    [
        pytest.param((family("A", PREFIX, 1), family("C", PREFIX, 9)), F(1, 10), id="B-on-item-1/(1+9)"),
        pytest.param((family("A", PREFIX, 1), family("B", PREFIX, 1)), F(1, 2), id="C-on-item-1/(1+1)"),
    ],
)
def test_one_junk_prefix_on_the_item_does_not_fix_the_chance_of_the_target(pool_left, expected):
    """Identity counterexample: target A (1), junk B (1) and C (9). Both states hold one junk prefix, yet differ."""
    assert chance(distribution(pool_left), has("A")) == expected


@pytest.mark.parametrize("action", [CHAOS, REFORGE])
def test_two_items_that_differ_only_in_the_weight_of_a_junk_prefix_have_different_signatures(action):
    """The same counterexample on the real compressed state: life (weight 1000 a mod) and added lightning
    damage (500 a mod) are both one fractured junk prefix of two mods, and only the weight tells them apart."""
    ab = abstraction()
    life, damage = ab.compress(fractured_item(LIFE_1)), ab.compress(fractured_item(DAMAGE_1))

    assert ab.signature(life, action) != ab.signature(damage, action)
