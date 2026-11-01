"""Embers, Ichors, the Eldritch orbs and the Orb of Conflict against a hand oracle (ticket #151, ADR-0025).

Every expected number is written down from the fixture table of `eldritch_support` (or from the issue), not computed by the code
under test. The oracle of a draw (`draw_sets`) walks every draw order of a handful of families by hand. The real 3.29.3.3 data
is in `test_actions_eldritch_real.py`.

"Done when" of #151: exact tests against a hand oracle; dominance as a truth table; Eldritch Chaos puts back a count per Craft
of Exile; the refusals (influenced items, other classes, no dominance).
"""

import itertools
import math
import random
from fractions import Fraction

import pytest
from contract_support import check_action
from eldritch_support import (
    ARMOUR,
    ATTACK,
    BODY,
    BOOTS,
    CASTER,
    COLD,
    DATA,
    EVASION,
    FIRE,
    GLOVES,
    HELMET,
    LIFE,
    LOCK_PREFIXES,
    LOCK_SUFFIXES,
    NO_ATTACK,
    NO_CASTER,
    SHAPER,
    SPEED,
    amulet,
    boots,
    build,
    eater,
    eldritch_id,
    exarch,
    roll,
)

from crafting_system.abstraction import Goal, ImplicitWanted, Wanted
from crafting_system.actions import (
    EldritchAnnulmentOrb,
    EldritchChaosOrb,
    EldritchExaltedOrb,
    EldritchImplicitCurrency,
    NotApplicableError,
    OrbOfConflict,
    catalog,
    conflict_raise_chance,
    item_dominant_side,
    kinds,
)
from crafting_system.actions.eldritch import conflict_is_extrapolated
from crafting_system.items import EldritchSide, Rarity, dominant_side

EXARCH_SIDE, EATER_SIDE = EldritchSide.EXARCH, EldritchSide.EATER


def draw_sets(weights: dict[str, int], picks: int) -> dict[frozenset[str], Fraction]:
    """The hand oracle of a draw: `picks` families one at a time, proportional to weight, without putting any back.

    Returns the chance of each set of families drawn, adding up every order (a permutation) that gives the set.
    """
    result: dict[frozenset[str], Fraction] = {}
    for order in itertools.permutations(weights, picks):
        left, chance = sum(weights.values()), Fraction(1)
        for family in order:
            chance *= Fraction(weights[family], left)
            left -= weights[family]
        key = frozenset(order)
        result[key] = result.get(key, Fraction(0)) + chance
    return result


def seen(outcomes) -> dict[frozenset[str], Fraction]:
    """The distribution of the new mods as sets of mod ids (a family is drawn at most once, so every count is 1)."""
    found: dict[frozenset[str], Fraction] = {}
    for outcome, chance in outcomes.distribution(lambda mod: mod.id).items():
        assert all(count == 1 for _, count in outcome)
        key = frozenset(mod_id for mod_id, _ in outcome)
        found[key] = found.get(key, Fraction(0)) + chance
    return found


def implicits_of(result) -> dict[str, str]:
    """`{side: mod id}` of the Eldritch implicits of an item."""
    return {side.value: entry.mod_id for side, entry in result.eldritch_implicits(DATA).items()}


def listed(finite) -> dict[tuple, Fraction]:
    """The results of a `Finite` action as `{(sorted implicit ids, sorted mod ids): chance}`."""
    found: dict[tuple, Fraction] = {}
    for chance, item in finite.results:
        key = (tuple(sorted(entry.mod_id for entry in item.implicits)), tuple(sorted(entry.mod_id for entry in item.mods)))
        found[key] = found.get(key, Fraction(0)) + chance
    return found


# --- Embers and Ichors: the pool, by the table of the fixture ------------------------------------------------------


# (class base, side, grade) -> {mod id: weight}, written from the table in `eldritch_support`
def ex(family, grade, variant=""):
    return eldritch_id(family, grade, variant)


POOLS = {
    # boots, Exarch, Lesser: the base mods only
    (BOOTS, EXARCH_SIDE, 1): {ex("AvoidShock", 1): 700, ex("FireMax", 1): 600, ex("Aggro", 1): 100},
    # Greater: base plus Unique-Presence at half
    (BOOTS, EXARCH_SIDE, 2): {
        ex("AvoidShock", 2): 700,
        ex("AvoidShock", 2, "UniquePresence"): 350,
        ex("FireMax", 2): 600,
        ex("FireMax", 2, "UniquePresence"): 300,
        ex("Aggro", 2): 100,
        ex("Aggro", 2, "UniquePresence"): 50,
    },
    # Grand and Exceptional: plus Pinnacle-Presence at a fifth
    (BOOTS, EXARCH_SIDE, 3): {
        ex("AvoidShock", 3): 700,
        ex("AvoidShock", 3, "UniquePresence"): 350,
        ex("AvoidShock", 3, "PinnaclePresence"): 140,
        ex("FireMax", 3): 600,
        ex("FireMax", 3, "UniquePresence"): 300,
        ex("FireMax", 3, "PinnaclePresence"): 120,
        ex("Aggro", 3): 100,
        ex("Aggro", 3, "UniquePresence"): 50,
        ex("Aggro", 3, "PinnaclePresence"): 20,
    },
    (BOOTS, EATER_SIDE, 1): {ex("ChanceToShock", 1): 400, ex("Flask", 1): 300, ex("Leech", 1): 200},
    (GLOVES, EXARCH_SIDE, 3): {
        ex("AvoidShock", 3): 500,
        ex("AvoidShock", 3, "UniquePresence"): 250,
        ex("AvoidShock", 3, "PinnaclePresence"): 100,
        ex("Pierce", 3): 500,
        ex("Pierce", 3, "UniquePresence"): 250,
        ex("Pierce", 3, "PinnaclePresence"): 100,
    },
    (HELMET, EXARCH_SIDE, 1): {ex("FireMax", 1): 400},
    (BODY, EXARCH_SIDE, 2): {ex("Armour", 2): 1000, ex("Armour", 2, "UniquePresence"): 500},
}
POOL_SIZES = {  # mods and total weight, by hand: the sums of the rows above
    (BOOTS, EXARCH_SIDE, 1): (3, 1400),
    (BOOTS, EXARCH_SIDE, 2): (6, 2100),
    (BOOTS, EXARCH_SIDE, 3): (9, 2380),
    (BOOTS, EATER_SIDE, 1): (3, 900),
    (GLOVES, EXARCH_SIDE, 3): (6, 1700),
    (HELMET, EXARCH_SIDE, 1): (1, 400),
    (BODY, EXARCH_SIDE, 2): (2, 1500),
}


def results_by_implicit(base, side, grade, item=None):
    """The Ember or Ichor outcomes as `{the new implicit of the side: chance}`."""
    action = EldritchImplicitCurrency(side, grade)
    found = {}
    for chance, result in action.outcomes(DATA, item if item is not None else build(base)).results:
        mod_id = implicits_of(result)[side.value]
        found[mod_id] = found.get(mod_id, Fraction(0)) + chance
    return found


@pytest.mark.parametrize("key", list(POOLS))
def test_an_ember_draws_by_the_spawn_weight_of_the_item_class_among_the_mods_of_its_grade(key):
    base, side, grade = key
    pool = POOLS[key]
    assert (len(pool), sum(pool.values())) == POOL_SIZES[key]
    assert results_by_implicit(base, side, grade) == {mod_id: Fraction(weight, sum(pool.values())) for mod_id, weight in pool.items()}


def test_an_exceptional_ember_draws_from_the_pool_of_a_grand_one_at_its_own_grade():
    grand = POOLS[(BOOTS, EXARCH_SIDE, 3)]
    expected = {mod_id[:-1] + "4": Fraction(weight, 2380) for mod_id, weight in grand.items()}
    assert results_by_implicit(BOOTS, EXARCH_SIDE, 4) == expected


def test_the_pinned_chance_of_one_mod_is_its_weight_over_the_total():
    # the issue's pinned example in the shape of the fixture: Avoid Shock on boots at Grand is 700 / 2,380
    assert results_by_implicit(BOOTS, EXARCH_SIDE, 3)[ex("AvoidShock", 3)] == Fraction(700, 2380) == Fraction(5, 17)


def test_a_variant_that_is_off_at_a_grade_never_comes_up():
    lesser, greater = results_by_implicit(BOOTS, EXARCH_SIDE, 1), results_by_implicit(BOOTS, EXARCH_SIDE, 2)
    assert not any("Presence" in mod_id for mod_id in lesser)
    assert not any("PinnaclePresence" in mod_id for mod_id in greater)
    assert any("UniquePresence" in mod_id for mod_id in greater)


def test_the_pool_does_not_depend_on_the_item_level_or_the_rarity():
    wanted = results_by_implicit(BOOTS, EXARCH_SIDE, 3)
    for rarity in Rarity:
        for level in (1, 60, 84):
            assert results_by_implicit(BOOTS, EXARCH_SIDE, 3, build(BOOTS, rarity=rarity, level=level)) == wanted


def test_an_ichor_puts_an_eater_implicit_and_leaves_the_exarch_one():
    item = boots(roll(LIFE), implicits=(exarch(2),))
    for chance, result in EldritchImplicitCurrency(EATER_SIDE, 1).outcomes(DATA, item).results:
        held = implicits_of(result)
        assert held["exarch"] == exarch(2).mod_id and held["eater"] in POOLS[(BOOTS, EATER_SIDE, 1)]
        assert [entry.mod_id for entry in result.mods] == [LIFE] and result.rarity is item.rarity


def test_an_ember_replaces_the_exarch_implicit_keeps_the_eater_one_and_drops_the_base_implicit():
    from eldritch_support import BASE_IMPLICIT, low

    from crafting_system.items import ImplicitMod

    base_implicit = ImplicitMod(BASE_IMPLICIT, 0, low(BASE_IMPLICIT))
    item = boots(roll(LIFE), implicits=(base_implicit, exarch(2), eater(1)))
    assert {entry.mod_id for entry in item.implicits} == {BASE_IMPLICIT, exarch(2).mod_id, eater(1).mod_id}
    for _, result in EldritchImplicitCurrency(EXARCH_SIDE, 1).outcomes(DATA, item).results:
        assert implicits_of(result)["eater"] == eater(1).mod_id
        assert len(result.implicits) == 2 and implicits_of(result)["exarch"] in POOLS[(BOOTS, EXARCH_SIDE, 1)]
        assert result.mods == item.mods


def test_an_ember_can_bring_back_the_mod_the_side_already_holds():
    item = boots(implicits=(exarch(3),))
    chances = results_by_implicit(BOOTS, EXARCH_SIDE, 3, item)
    assert chances[exarch(3).mod_id] == Fraction(5, 17)  # the same mod again, at its weight share, not excluded


def test_an_ember_lowers_a_higher_implicit_to_its_own_grade():
    item = boots(implicits=(exarch(3), eater(1)))
    for _, result in EldritchImplicitCurrency(EXARCH_SIDE, 1).outcomes(DATA, item).results:
        assert result.eldritch_implicits(DATA)[EXARCH_SIDE].grade == 1


def test_an_ember_works_on_a_fractured_item_and_keeps_every_mod():
    item = boots(roll(LIFE, fractured=True), roll(FIRE), roll(COLD))
    for _, result in EldritchImplicitCurrency(EXARCH_SIDE, 2).outcomes(DATA, item).results:
        assert result.mods == item.mods


@pytest.mark.parametrize(
    ("base", "family"), [(BOOTS, "AvoidShock"), (GLOVES, "AvoidShock"), (HELMET, "FireMax"), (BODY, "Armour")]
)
def test_an_ember_works_on_each_of_the_four_item_classes(base, family):
    item = build(base)
    assert catalog(DATA, item, names=["eldritch-implicit-currency"])
    chances = results_by_implicit(base, EXARCH_SIDE, 1)
    assert sum(chances.values()) == 1 and ex(family, 1) in chances


def test_labels_and_prices_are_the_names_of_the_currency_items():
    assert EldritchImplicitCurrency(EXARCH_SIDE, 1).label() == "Lesser Eldritch Ember"
    assert EldritchImplicitCurrency(EXARCH_SIDE, 4).resources() == {"Exceptional Eldritch Ember": 1}
    assert EldritchImplicitCurrency(EATER_SIDE, 3).label() == "Grand Eldritch Ichor"
    assert EldritchChaosOrb().resources() == {"Eldritch Chaos Orb": 1}
    assert EldritchExaltedOrb().resources() == {"Eldritch Exalted Orb": 1}
    assert EldritchAnnulmentOrb().resources() == {"Eldritch Orb of Annulment": 1}
    assert OrbOfConflict().resources() == {"Orb of Conflict": 1}


@pytest.mark.parametrize("grade", [0, 5, 6, -1, 2.0, "3", None])
def test_an_ember_or_ichor_has_a_grade_from_1_to_4(grade):
    with pytest.raises(ValueError):
        EldritchImplicitCurrency(EXARCH_SIDE, grade)


# --- dominance as a truth table ------------------------------------------------------------------------------------


# rows: the Searing Exarch grade 0..6, columns: the Eater of Worlds grade 0..6. X = Exarch dominant (prefixes), E = Eater
# dominant (suffixes), . = nobody. A lone implicit (a row or column of 0) is dominant by itself; equal grades give nobody.
TRUTH = (
    ".EEEEEE",
    "X.EEEEE",
    "XX.EEEE",
    "XXX.EEE",
    "XXXX.EE",
    "XXXXX.E",
    "XXXXXX.",
)
READ = {"X": EXARCH_SIDE, "E": EATER_SIDE, ".": None}


@pytest.mark.parametrize("exarch_grade", range(7))
def test_dominance_follows_the_truth_table(exarch_grade):
    for eater_grade in range(7):
        assert dominant_side(exarch_grade, eater_grade) is READ[TRUTH[exarch_grade][eater_grade]], (exarch_grade, eater_grade)


def test_dominance_of_a_real_item_is_derived_from_the_implicits_it_holds():
    assert item_dominant_side(DATA, boots()) is None
    assert item_dominant_side(DATA, boots(implicits=(exarch(1),))) is EXARCH_SIDE
    assert item_dominant_side(DATA, boots(implicits=(eater(1),))) is EATER_SIDE
    assert item_dominant_side(DATA, boots(implicits=(exarch(2), eater(2)))) is None
    assert item_dominant_side(DATA, boots(implicits=(exarch(2), eater(3)))) is EATER_SIDE
    assert item_dominant_side(DATA, boots(implicits=(exarch(4, "Aggro"), eater(3)))) is EXARCH_SIDE


# --- Eldritch Exalted Orb -----------------------------------------------------------------------------------------


PREFIX_POOL = {LIFE: 1000, ARMOUR: 500, EVASION: 300, ATTACK: 200}
SUFFIX_POOL = {FIRE: 1000, COLD: 600, SPEED: 400, CASTER: 100}


def test_an_exalted_orb_adds_one_prefix_when_the_exarch_dominates():
    item = boots(roll(LIFE), roll(FIRE), implicits=(exarch(2), eater(1)))
    pool = {family: weight for family, weight in PREFIX_POOL.items() if family != LIFE}  # the family on the item is out
    assert seen(EldritchExaltedOrb().outcomes(DATA, item)) == {frozenset({mod}): Fraction(weight, 1000) for mod, weight in pool.items()}


def test_an_exalted_orb_adds_one_suffix_when_the_eater_dominates():
    item = boots(roll(LIFE), roll(FIRE), implicits=(eater(2),))
    pool = {family: weight for family, weight in SUFFIX_POOL.items() if family != FIRE}
    assert seen(EldritchExaltedOrb().outcomes(DATA, item)) == {frozenset({mod}): Fraction(weight, 1100) for mod, weight in pool.items()}


def test_an_exalted_orb_keeps_every_mod_and_fills_only_the_dominant_side():
    item = boots(roll(LIFE), roll(ARMOUR), roll(FIRE), implicits=(exarch(2), eater(1)))
    outcomes = EldritchExaltedOrb().outcomes(DATA, item)
    assert outcomes.retained == item
    assert seen(outcomes) == {frozenset({EVASION}): Fraction(3, 5), frozenset({ATTACK}): Fraction(2, 5)}
    rng = random.Random(7)
    for _ in range(40):
        drawn = outcomes.sample(rng)
        assert len(drawn.prefixes(DATA)) == 3 and len(drawn.suffixes(DATA)) == 1


def test_an_exalted_orb_fills_an_open_slot_of_a_locked_side():
    locked = boots(roll(LIFE), roll(LOCK_PREFIXES, crafted=True), implicits=(exarch(2),))  # the lock sits on a suffix, locks prefixes
    assert seen(EldritchExaltedOrb().outcomes(DATA, locked)).keys() == {frozenset({m}) for m in (ARMOUR, EVASION, ATTACK)}


def test_an_exalted_orb_respects_the_attack_and_caster_metamods():
    attack = boots(roll(LIFE), roll(NO_ATTACK, crafted=True), implicits=(exarch(2),))
    assert seen(EldritchExaltedOrb().outcomes(DATA, attack)) == {
        frozenset({ARMOUR}): Fraction(5, 8),
        frozenset({EVASION}): Fraction(3, 8),
    }
    caster = boots(roll(FIRE), roll(NO_CASTER, crafted=True), implicits=(eater(2),))  # the metamod is a suffix of the dominant side
    assert frozenset({CASTER}) not in seen(EldritchExaltedOrb().outcomes(DATA, caster))


def test_an_exalted_orb_is_refused_when_the_dominant_side_is_full_even_if_the_other_has_room():
    item = boots(roll(LIFE), roll(ARMOUR), roll(EVASION), implicits=(exarch(2),))
    with pytest.raises(NotApplicableError, match="full"):
        EldritchExaltedOrb().outcomes(DATA, item)
    assert EldritchExaltedOrb().outcomes(DATA, boots(roll(LIFE), roll(ARMOUR), roll(EVASION), implicits=(eater(2),)))


def test_the_sampler_of_an_exalted_orb_rolls_a_valid_item():
    item = boots(roll(LIFE), implicits=(exarch(2),))
    rng = random.Random(3)
    for _ in range(20):
        drawn = EldritchExaltedOrb().outcomes(DATA, item).sample(rng)
        drawn.validate(DATA)
        assert len(drawn.mods) == 2 and drawn.implicits == item.implicits


# --- Eldritch Chaos Orb: the count per Craft of Exile ------------------------------------------------------------


def chaos_sets(stay_weights_removed: dict[str, int], kept: int, free_slots: int) -> dict[frozenset[str], Fraction]:
    """The hand oracle of an Eldritch Chaos Orb: the total 4, 5 or 6 (8:3:1 of 12) less `kept`, clamped to `free_slots`."""
    result: dict[frozenset[str], Fraction] = {}
    for total, share in ((4, Fraction(8, 12)), (5, Fraction(3, 12)), (6, Fraction(1, 12))):
        for family_set, chance in draw_sets(stay_weights_removed, max(0, min(free_slots, total - kept))).items():
            result[family_set] = result.get(family_set, Fraction(0)) + share * chance
    return result


def test_an_eldritch_chaos_orb_puts_back_the_total_less_the_mods_that_stay():
    item = boots(roll(LIFE), roll(ARMOUR), roll(FIRE), roll(COLD), implicits=(exarch(2), eater(1)))
    outcomes = EldritchChaosOrb().outcomes(DATA, item)
    assert {entry.mod_id for entry in outcomes.retained.mods} == {FIRE, COLD}  # the prefixes go, the suffixes stay
    expected = chaos_sets(PREFIX_POOL, kept=2, free_slots=3)  # 2 mods at 8/12, 3 at 4/12 (a total of 5 or 6 clamps to 3)
    assert seen(outcomes) == expected
    sizes: dict[int, Fraction] = {}
    for family_set, chance in seen(outcomes).items():
        sizes[len(family_set)] = sizes.get(len(family_set), Fraction(0)) + chance
    assert sizes == {2: Fraction(2, 3), 3: Fraction(1, 3)}


def test_a_chaos_orb_on_the_eater_side_rerolls_the_suffixes_and_leaves_the_prefixes():
    item = boots(roll(LIFE), roll(FIRE), roll(COLD), implicits=(eater(2), exarch(1)))
    outcomes = EldritchChaosOrb().outcomes(DATA, item)
    assert {entry.mod_id for entry in outcomes.retained.mods} == {LIFE}
    assert seen(outcomes) == chaos_sets(SUFFIX_POOL, kept=1, free_slots=3)
    assert outcomes.retained.implicits == item.implicits


def test_the_fractured_mods_of_the_dominant_side_stay_and_count_in_the_total():
    item = boots(roll(LIFE, fractured=True), roll(ARMOUR), roll(FIRE), roll(COLD), implicits=(exarch(3), eater(1)))
    outcomes = EldritchChaosOrb().outcomes(DATA, item)
    assert {entry.mod_id for entry in outcomes.retained.mods} == {LIFE, FIRE, COLD}
    pool = {family: weight for family, weight in PREFIX_POOL.items() if family != LIFE}  # the fractured family blocks its own
    assert seen(outcomes) == chaos_sets(pool, kept=3, free_slots=2)  # 1 at 8/12, 2 at 4/12


def test_nothing_is_put_back_when_the_mods_that_stay_already_reach_the_total():
    item = boots(roll(FIRE), roll(COLD), roll(SPEED), roll(LIFE, fractured=True), implicits=(exarch(2), eater(1)))
    outcomes = EldritchChaosOrb().outcomes(DATA, item)  # 4 stay: totals 4, 5, 6 put back 0, 1, 2 (clamped to 2 slots)
    assert seen(outcomes) == chaos_sets({k: v for k, v in PREFIX_POOL.items() if k != LIFE}, kept=4, free_slots=2)


def test_an_eldritch_chaos_orb_ignores_the_lock_that_protects_the_dominant_side():
    item = boots(roll(LIFE), roll(LOCK_PREFIXES, crafted=True), implicits=(exarch(2),))
    outcomes = EldritchChaosOrb().outcomes(DATA, item)
    assert {entry.mod_id for entry in outcomes.retained.mods} == {LOCK_PREFIXES}  # the lock itself is on the other side: it stays
    assert LIFE in {mod for family_set in seen(outcomes) for mod in family_set}  # Life is rerolled, and may come back


def test_an_eldritch_chaos_orb_respects_a_caster_or_attack_metamod_that_stays():
    stays = boots(roll(LIFE), roll(NO_ATTACK, crafted=True), implicits=(exarch(2),))  # on the suffix side, the other one
    assert ATTACK not in {mod for family_set in seen(EldritchChaosOrb().outcomes(DATA, stays)) for mod in family_set}
    goes = boots(roll(FIRE), roll(NO_CASTER, crafted=True), implicits=(eater(2), exarch(1)))  # on the dominant side: rerolled away
    assert CASTER in {mod for family_set in seen(EldritchChaosOrb().outcomes(DATA, goes)) for mod in family_set}


def test_a_crafted_mod_of_the_dominant_side_is_rerolled_like_any_other():
    item = boots(roll(LIFE), roll(FIRE), roll(LOCK_SUFFIXES, crafted=True), implicits=(exarch(2),))  # a crafted prefix
    assert {entry.mod_id for entry in EldritchChaosOrb().outcomes(DATA, item).retained.mods} == {FIRE}


def test_the_sampler_of_an_eldritch_chaos_orb_keeps_the_other_side_and_the_implicits():
    item = boots(roll(LIFE), roll(ARMOUR), roll(FIRE), roll(COLD), implicits=(exarch(2), eater(1)))
    outcomes = EldritchChaosOrb().outcomes(DATA, item)
    rng = random.Random(11)
    sizes = {2: 0, 3: 0}
    for _ in range(600):
        drawn = outcomes.sample(rng)
        drawn.validate(DATA)
        assert {entry.mod_id for entry in drawn.suffixes(DATA)} == {FIRE, COLD} and drawn.implicits == item.implicits
        sizes[len(drawn.prefixes(DATA))] += 1
    assert abs(sizes[2] / 600 - 2 / 3) < 5 * math.sqrt(2 / 9 / 600)


# --- Eldritch Orb of Annulment -------------------------------------------------------------------------------------


def test_an_eldritch_annulment_removes_one_mod_of_the_dominant_side_uniformly():
    item = boots(roll(LIFE), roll(ARMOUR), roll(FIRE), roll(COLD), implicits=(exarch(2), eater(1)))
    result = listed(EldritchAnnulmentOrb().outcomes(DATA, item))
    kept = lambda *mods: tuple(sorted(mods))  # noqa: E731
    imp = tuple(sorted((exarch(2).mod_id, eater(1).mod_id)))
    assert result == {(imp, kept(ARMOUR, FIRE, COLD)): Fraction(1, 2), (imp, kept(LIFE, FIRE, COLD)): Fraction(1, 2)}


def test_an_eldritch_annulment_on_the_eater_side_removes_a_suffix():
    item = boots(roll(LIFE), roll(FIRE), roll(COLD), roll(SPEED), implicits=(eater(3), exarch(1)))
    imp = tuple(sorted((exarch(1).mod_id, eater(3).mod_id)))
    assert listed(EldritchAnnulmentOrb().outcomes(DATA, item)) == {
        (imp, tuple(sorted((LIFE, COLD, SPEED)))): Fraction(1, 3),
        (imp, tuple(sorted((LIFE, FIRE, SPEED)))): Fraction(1, 3),
        (imp, tuple(sorted((LIFE, FIRE, COLD)))): Fraction(1, 3),
    }  # each suffix goes with 1/3, the prefix never


def test_an_eldritch_annulment_skips_fractured_locked_and_protected_mods():
    item = boots(roll(LIFE, fractured=True), roll(ARMOUR), roll(ATTACK), roll(NO_ATTACK, crafted=True), implicits=(exarch(2),))
    # Attack is protected by Cannot roll Attack Modifiers and the fractured Life stays: only Armour can go
    (chance, result), = EldritchAnnulmentOrb().outcomes(DATA, item).results
    assert chance == 1 and {entry.mod_id for entry in result.mods} == {LIFE, ATTACK, NO_ATTACK}
    locked = boots(roll(LIFE), roll(LOCK_PREFIXES, crafted=True), implicits=(exarch(2),))
    with pytest.raises(NotApplicableError, match="cannot be used here"):
        EldritchAnnulmentOrb().outcomes(DATA, locked)  # the dominant side is the locked one
    assert EldritchAnnulmentOrb().outcomes(DATA, boots(roll(LIFE), roll(LOCK_PREFIXES, crafted=True), implicits=(eater(2),)))


def test_an_eldritch_annulment_works_on_a_magic_item_and_keeps_its_rarity():
    item = boots(roll(LIFE), rarity=Rarity.MAGIC, implicits=(exarch(1),))
    (chance, result), = EldritchAnnulmentOrb().outcomes(DATA, item).results
    assert chance == 1 and result.rarity is Rarity.MAGIC and not result.mods


# --- the Orb of Conflict -------------------------------------------------------------------------------------------


def conflict(exarch_grade, eater_grade):
    """The Conflict outcomes as `{(exarch grade, eater grade): chance}` (0 for a removed implicit)."""
    outcomes = OrbOfConflict().outcomes(DATA, boots(roll(LIFE), implicits=(exarch(exarch_grade), eater(eater_grade))))
    found = {}
    for chance, item in outcomes.results:
        held = item.eldritch_implicits(DATA)
        key = (held[EXARCH_SIDE].grade if EXARCH_SIDE in held else 0, held[EATER_SIDE].grade if EATER_SIDE in held else 0)
        found[key] = found.get(key, Fraction(0)) + chance
    return found


# the fit p = 1 / (1 + exp(-(0.10 - 0.52 d))) for d = 1..5 to six places, computed by hand (a calculator) for this test
HAND_P = {1: Fraction(396517, 10**6), 2: Fraction(2809, 10**4), 3: Fraction(188467, 10**6), 4: Fraction(121319, 10**6), 5: Fraction(75858, 10**6)}


@pytest.mark.parametrize("difference", range(1, 6))
def test_the_raise_chance_of_the_higher_implicit_is_the_fit_rounded_to_six_places(difference):
    assert conflict_raise_chance(difference) == HAND_P[difference]
    assert abs(float(conflict_raise_chance(difference)) - 1 / (1 + math.exp(-(0.10 - 0.52 * difference)))) < 5e-7


def test_equal_grades_raise_each_side_with_one_half():
    assert conflict_raise_chance(0) == Fraction(1, 2)
    assert conflict(2, 2) == {(3, 1): Fraction(1, 2), (1, 3): Fraction(1, 2)}


def test_the_higher_implicit_is_raised_with_p_and_the_lower_with_the_rest():
    p = HAND_P[1]
    assert conflict(3, 2) == {(4, 1): p, (2, 3): 1 - p}  # the Exarch is the higher: raised 3 to 4 while the Eater goes 2 to 1, or the reverse
    assert conflict(2, 3) == {(1, 4): p, (3, 2): 1 - p}  # the Eater is the higher: the mirror image
    p2 = HAND_P[2]
    assert conflict(5, 3) == {(6, 2): p2, (4, 4): 1 - p2}  # the research's 5/3 to 6/2, about 28% in the sample, 0.2809 by the fit


def test_a_lowered_lesser_implicit_is_removed():
    p = HAND_P[2]
    assert conflict(3, 1) == {(4, 0): p, (2, 2): 1 - p}
    assert conflict(1, 3) == {(0, 4): p, (2, 2): 1 - p}
    assert conflict(1, 1) == {(2, 0): Fraction(1, 2), (0, 2): Fraction(1, 2)}


def test_raising_a_perfect_implicit_does_nothing_and_the_other_is_still_lowered():
    p = HAND_P[2]
    assert conflict(6, 4) == {(6, 3): p, (5, 5): 1 - p}  # 6/4 -> 5/5 in about 72% here (68% of 25 uses in the sample)
    assert conflict(6, 6) == {(6, 5): Fraction(1, 2), (5, 6): Fraction(1, 2)}
    assert conflict(4, 6) == {(3, 6): p, (5, 5): 1 - p}
    assert conflict(6, 1) == {(6, 0): HAND_P[5], (5, 2): 1 - HAND_P[5]}


def test_a_grade_difference_above_three_is_marked_as_an_extrapolation():
    assert [conflict_is_extrapolated(d) for d in range(0, 6)] == [False, False, False, False, True, True]


def test_conflict_moves_each_implicit_to_the_same_family_and_variant_one_grade_away():
    item = boots(implicits=(exarch(3, "FireMax", "UniquePresence"), eater(2, "Flask")))
    for _, result in OrbOfConflict().outcomes(DATA, item).results:
        held = {entry.mod_id for entry in result.implicits}
        assert held in (
            {eldritch_id("FireMax", 4, "UniquePresence"), eldritch_id("Flask", 1)},
            {eldritch_id("FireMax", 2, "UniquePresence"), eldritch_id("Flask", 3)},
        )


def test_conflict_keeps_the_mods_of_the_item_and_only_changes_its_implicits():
    item = boots(roll(LIFE), roll(FIRE, fractured=True), implicits=(exarch(2), eater(2)))
    for _, result in OrbOfConflict().outcomes(DATA, item).results:
        assert result.mods == item.mods and result.rarity is item.rarity


# --- the refusals --------------------------------------------------------------------------------------------------


def both_sides():
    return boots(roll(LIFE), roll(FIRE), implicits=(exarch(2), eater(1)))


ALL_ACTIONS = [
    EldritchImplicitCurrency(EXARCH_SIDE, 1),
    EldritchImplicitCurrency(EATER_SIDE, 4),
    EldritchChaosOrb(),
    EldritchExaltedOrb(),
    EldritchAnnulmentOrb(),
    OrbOfConflict(),
]


@pytest.mark.parametrize("action", ALL_ACTIONS, ids=lambda action: action.label())
def test_every_eldritch_action_refuses_an_influenced_item(action):
    influenced = build(BOOTS, roll(LIFE), implicits=(exarch(2), eater(1)), influences=SHAPER)
    with pytest.raises(NotApplicableError, match="influence"):
        action.outcomes(DATA, influenced)


@pytest.mark.parametrize("action", ALL_ACTIONS, ids=lambda action: action.label())
def test_every_eldritch_action_refuses_other_item_classes(action):
    with pytest.raises(NotApplicableError, match="Amulet"):
        action.outcomes(DATA, amulet())


@pytest.mark.parametrize("action", ALL_ACTIONS, ids=lambda action: action.label())
def test_every_eldritch_action_refuses_a_corrupted_item(action):
    corrupted = boots(roll(LIFE), implicits=(exarch(2), eater(1)), corrupted=True)
    with pytest.raises(NotApplicableError, match="corrupted"):
        action.outcomes(DATA, corrupted)


@pytest.mark.parametrize("action", [EldritchChaosOrb(), EldritchExaltedOrb(), EldritchAnnulmentOrb()], ids=lambda action: action.label())
@pytest.mark.parametrize("implicits", [(), (exarch(2), eater(2)), (exarch(6), eater(6))], ids=["no implicit", "equal 2/2", "equal 6/6"])
def test_the_three_eldritch_orbs_refuse_an_item_without_dominance(action, implicits):
    with pytest.raises(NotApplicableError, match="dominant"):
        action.outcomes(DATA, boots(roll(LIFE), roll(FIRE), implicits=implicits))


def test_the_chaos_and_exalted_orbs_need_a_rare_item_and_the_annulment_a_magic_or_rare_one():
    for rarity in (Rarity.NORMAL, Rarity.MAGIC):
        item = boots(implicits=(exarch(2),), rarity=rarity)
        for action in (EldritchChaosOrb(), EldritchExaltedOrb()):
            with pytest.raises(NotApplicableError, match="rare item only"):
                action.outcomes(DATA, item)
    with pytest.raises(NotApplicableError, match="magic or rare"):
        EldritchAnnulmentOrb().outcomes(DATA, boots(implicits=(exarch(2),), rarity=Rarity.NORMAL))


@pytest.mark.parametrize("implicits", [(), (exarch(2),), (eater(2),)], ids=["none", "exarch only", "eater only"])
def test_conflict_needs_an_implicit_on_both_sides(implicits):
    with pytest.raises(NotApplicableError, match="Searing Exarch and an Eater"):
        OrbOfConflict().outcomes(DATA, boots(roll(LIFE), implicits=implicits))


# --- the contract --------------------------------------------------------------------------------------------------


GOAL = Goal(
    (Wanted(frozenset({LIFE})), Wanted(frozenset({FIRE}))),
    (ImplicitWanted(frozenset(eldritch_id("AvoidShock", grade) for grade in range(1, 7)), 2),),
)
CONTRACT_CASES = {
    "ember on bare boots": (EldritchImplicitCurrency(EXARCH_SIDE, 2), lambda: boots(roll(LIFE), roll(FIRE))),
    "ember keeps the eater implicit": (EldritchImplicitCurrency(EXARCH_SIDE, 3), lambda: boots(roll(LIFE), implicits=(eater(1),))),
    "ichor replaces": (EldritchImplicitCurrency(EATER_SIDE, 1), lambda: boots(roll(LIFE), implicits=(exarch(2), eater(3)))),
    "exalted on prefixes": (EldritchExaltedOrb(), lambda: boots(roll(LIFE), roll(FIRE), implicits=(exarch(2), eater(1)))),
    "exalted on suffixes": (EldritchExaltedOrb(), lambda: boots(roll(LIFE), roll(FIRE), implicits=(eater(2),))),
    "exalted with a fractured mod": (EldritchExaltedOrb(), lambda: boots(roll(LIFE, fractured=True), roll(FIRE), implicits=(exarch(2),))),
    "annulment": (EldritchAnnulmentOrb(), lambda: boots(roll(LIFE), roll(ARMOUR), roll(FIRE), implicits=(exarch(2), eater(1)))),
    "annulment on suffixes": (EldritchAnnulmentOrb(), lambda: boots(roll(LIFE), roll(FIRE), roll(COLD), implicits=(eater(2),))),
    "chaos": (EldritchChaosOrb(), lambda: boots(roll(LIFE), roll(FIRE), implicits=(exarch(2), eater(1)))),
    "chaos with a fractured mod": (EldritchChaosOrb(), lambda: boots(roll(LIFE, fractured=True), roll(ARMOUR), roll(FIRE), implicits=(exarch(3),))),
    "conflict": (OrbOfConflict(), lambda: boots(roll(LIFE), implicits=(exarch(3), eater(1)))),
    "conflict at equal grades": (OrbOfConflict(), lambda: boots(roll(LIFE), implicits=(exarch(2), eater(2)))),
    "conflict at the top": (OrbOfConflict(), lambda: boots(roll(LIFE), implicits=(exarch(6), eater(4)))),
}


@pytest.mark.parametrize("name", list(CONTRACT_CASES))
def test_each_action_passes_the_contract_suite_and_layer_1(name):
    action, make = CONTRACT_CASES[name]
    assert check_action(action, make(), DATA, GOAL)


@pytest.mark.parametrize("name", ["exalted on prefixes", "chaos", "annulment", "conflict", "ember keeps the eater implicit"])
def test_layer_1_holds_for_a_goal_that_names_no_implicit(name):
    action, make = CONTRACT_CASES[name]
    assert check_action(action, make(), DATA, Goal((Wanted(frozenset({LIFE})), Wanted(frozenset({ARMOUR, EVASION})))))


def test_the_declarations_say_what_the_actions_read_and_change():
    for action in ALL_ACTIONS:
        reads, adds = action.reads(DATA), action.adds(DATA, None)
        assert reads.implicits and not reads.quality and not reads.offer and not reads.block_invariant and not reads.variants
        assert adds.implicits is isinstance(action, (EldritchImplicitCurrency, OrbOfConflict))
    assert EldritchAnnulmentOrb().adds().draws is False and EldritchChaosOrb().adds().draws and EldritchExaltedOrb().adds().draws
    assert EldritchChaosOrb().reads(DATA).families is None and EldritchExaltedOrb().reads(DATA).pool_weight


# --- the catalog and the claims ------------------------------------------------------------------------------------


KIND_NAMES = {
    "eldritch-implicit-currency",
    "eldritch-chaos-orb",
    "eldritch-exalted-orb",
    "eldritch-annulment-orb",
    "orb-of-conflict",
}


def test_the_catalog_lists_the_eldritch_actions_for_a_boots_item_and_none_for_an_amulet():
    registered = {entry.name: entry for entry in kinds()}
    assert KIND_NAMES <= registered.keys()
    assert not any(registered[name].planner for name in KIND_NAMES) and all(registered[name].why_not for name in KIND_NAMES)
    rare = catalog(DATA, boots(roll(LIFE)), names=KIND_NAMES)
    assert {type(action) for action in rare} == {EldritchImplicitCurrency, EldritchChaosOrb, EldritchExaltedOrb, EldritchAnnulmentOrb, OrbOfConflict}
    assert sum(isinstance(action, EldritchImplicitCurrency) for action in rare) == 8
    assert not catalog(DATA, amulet(), names=KIND_NAMES)
    normal = catalog(DATA, build(BOOTS, rarity=Rarity.NORMAL), names=KIND_NAMES)
    assert {type(action) for action in normal} == {EldritchImplicitCurrency, OrbOfConflict}
    assert not catalog(DATA, build(BOOTS, influences=SHAPER), names=KIND_NAMES)


def test_each_eldritch_kind_lists_and_applies_one_of_the_contract_cases():
    applied = set()
    for action, make in CONTRACT_CASES.values():
        item = make()
        for entry in kinds():
            if entry.name in KIND_NAMES and action in entry.members(DATA, item):
                action.outcomes(DATA, item)  # raises when the case is not one the action applies to
                applied.add(entry.name)
    assert applied == KIND_NAMES  # tests/test_actions_contract.py exempts these kinds because the amulet fixtures cannot apply them


def test_each_action_names_only_the_claims_it_reads_and_the_approximate_ones_of_the_orbs_that_use_them():
    from crafting_system.rules import rule_by_id

    def marked(action):
        return {rule_id for rule_id in action.claims() if rule_by_id(rule_id).approximate}

    assert marked(EldritchImplicitCurrency(EXARCH_SIDE, 1)) == {"eldritch.ember_may_return_same_family"}
    assert marked(EldritchChaosOrb()) == {"eldritch.chaos_count_follows_craft_of_exile"}
    assert marked(EldritchExaltedOrb()) == set()
    assert marked(EldritchAnnulmentOrb()) == {"eldritch.annul_removes_one_from_dominant_side"}
    assert marked(OrbOfConflict()) == {
        "eldritch.conflict_odds_fit",
        "eldritch.conflict_measured_odds",
        "eldritch.conflict_top_tier_raise_is_noop",
        "eldritch.conflict_keeps_the_variant_it_moves_to",
    }
    for action in ALL_ACTIONS:
        assert all(rule_id.startswith(("eldritch.", "chaos_orb.", "affix_count.")) for rule_id in action.claims())
