"""The Blessed Orb as an exact action (ticket #157, ADR-0027).

"Done when": exact tests against a hand oracle. The oracle here is the law the claims state, written out by hand:
every ranged implicit gets a fresh value per stat, uniform over the integers of its range, both ends included, and the
**previous value can roll again** (`blessed_orb.previous_value_can_repeat`). The Heavy Belt of R06 holds
`+(25-35) to Strength` (11 values, 1/11 each, the old one included); a made-up ring holds a two-stat implicit
(`(1-2)` and `(5-7)`, 6 value pairs, 1/6 each) and a fixed one that is never rerolled.

The contract suite cannot run its kernel check on an item that holds a base implicit before ticket #158 (the compressed state
refuses it), so the checks that do not need the kernel are run one by one here, and the whole `check_action` on the
refusals.
"""

import dataclasses
import random
from collections import Counter
from fractions import Fraction

import pytest
from abstraction_support import real_game_data
from contract_support import (
    check_action,
    check_chances_agree,
    check_declarations_agree,
    check_item_state_declarations,
    check_resources_are_priced,
    check_sampler_follows_the_chances,
    check_sums_to_one,
    finished,
)
from implicits_support import BELT, BOOTS, EXTENDED, _mod, implicit, make

from crafting_system.abstraction import Abstraction
from crafting_system.actions import (
    Action,
    BlessedOrb,
    BlessedOutcomes,
    NotApplicableError,
    OutOfScopeError,
    catalog,
    kinds,
)
from crafting_system.data import BaseItem
from crafting_system.items import ExplicitMod, ImplicitMod, Item, Rarity
from crafting_system.rules import rule_by_id

STRENGTH = "StrengthImplicitBelt1"
TWO_STAT, FIXED = "TwoStatImplicitRing", "FixedImplicitRing"
RING = "Metadata/Items/Rings/RingBlessedTest"
FIXED_RING = "Metadata/Items/Rings/RingBlessedFixed"
PLAIN_RING = "Metadata/Items/Rings/RingBlessedPlain"
AVOID_SHOCK_1 = "AvoidShockEldritchImplicit1"


def _ring(base_id: str, implicits: tuple[str, ...]) -> BaseItem:
    return BaseItem(base_id, "Test Ring", "Ring", "item", 1, ("ring", "default"), implicits, "released")


DATA = dataclasses.replace(
    EXTENDED,
    mods={
        **EXTENDED.mods,
        **{
            mod.id: mod
            for mod in (
                _mod(TWO_STAT, "unique", "item", "TwoStat", [("first_stat", 1, 2), ("second_stat", 5, 7)]),
                _mod(FIXED, "unique", "item", "Fixed", [("fixed_stat", 3, 3)]),
            )
        },
    },
    base_items={
        **EXTENDED.base_items,
        RING: _ring(RING, (TWO_STAT, FIXED)),
        FIXED_RING: _ring(FIXED_RING, (FIXED,)),
        PLAIN_RING: _ring(PLAIN_RING, ()),
    },
)
LIFE = "IncreasedLife1"  # an explicit mod of the fixture data, to see that the explicit mods stay


def _item(base_id: str, *mods: ExplicitMod, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    return Item.build(DATA, base_id=base_id, item_level=84, rarity=rarity, mods=mods, **fields)


def held(item: Item, mod_id: str) -> ImplicitMod:
    return next(entry for entry in item.implicits if entry.mod_id == mod_id)


def belt(value: int | None = 30, **fields) -> Item:
    return _item(BELT, **({"implicits": (ImplicitMod(STRENGTH, 0, (value,)),)} if value is not None else {}), **fields)


# --- the law ----------------------------------------------------------------------------------------


def test_the_value_of_a_ranged_implicit_is_uniform_over_its_range_and_the_old_value_can_repeat():
    outcomes = BlessedOrb().outcomes(DATA, belt(30))
    law = outcomes.value_law(STRENGTH, 0)
    assert law == {value: Fraction(1, 11) for value in range(25, 36)}  # 25 to 35 inclusive: 11 values
    assert law[30] == Fraction(1, 11)  # the value the belt held is as likely as any other
    assert sum(law.values()) == 1


def test_a_two_stat_implicit_rolls_each_stat_alone_over_its_own_range():
    outcomes = BlessedOrb().outcomes(DATA, _item(RING))
    assert outcomes.value_law(TWO_STAT, 0) == {1: Fraction(1, 2), 2: Fraction(1, 2)}
    assert outcomes.value_law(TWO_STAT, 1) == {5: Fraction(1, 3), 6: Fraction(1, 3), 7: Fraction(1, 3)}
    rng = random.Random(157)
    pairs = Counter(held(outcomes.sample(rng), TWO_STAT).values for _ in range(6000))
    assert set(pairs) == {(a, b) for a in (1, 2) for b in (5, 6, 7)}  # the six pairs, nothing else
    for count in pairs.values():  # 1/6 each, within 5 standard errors of 6000 draws
        assert abs(count / 6000 - 1 / 6) <= 5 * (1 / 6 * 5 / 6 / 6000) ** 0.5


def test_the_sampler_follows_the_law_and_repeats_the_old_value_one_time_in_eleven():
    outcomes = BlessedOrb().outcomes(DATA, belt(30))
    rng = random.Random(20261101)
    draws = [held(outcomes.sample(rng), STRENGTH).values[0] for _ in range(5500)]
    counts = Counter(draws)
    assert set(counts) == set(range(25, 36))
    for value in range(25, 36):
        assert abs(counts[value] / 5500 - 1 / 11) <= 5 * (1 / 11 * 10 / 11 / 5500) ** 0.5, value
    assert counts[30] > 0  # the previous value rolled again


def test_the_exact_result_holds_the_implicit_at_its_lowest_value_and_a_sample_validates():
    outcomes = BlessedOrb().outcomes(DATA, belt(30))
    ((chance, result),) = outcomes.results
    assert chance == 1 and held(result, STRENGTH) == ImplicitMod(STRENGTH, 0, (25,))
    outcomes.sample(random.Random(1)).validate(DATA)


# --- what it changes --------------------------------------------------------------------------------


def test_only_the_implicit_values_change_the_explicit_mods_and_the_rest_stay():
    given = _item(RING, ExplicitMod(LIFE, 1, (DATA.mods[LIFE].stats[0].min,)), implicits=(ImplicitMod(TWO_STAT, 0, (2, 7)),))
    outcomes = BlessedOrb().outcomes(DATA, given)
    sampled = outcomes.sample(random.Random(5))
    assert sampled.mods == given.mods and sampled.rarity == given.rarity and sampled.influences == given.influences
    assert outcomes.distribution(lambda mod: mod.id) == {frozenset(): 1}  # no mod is new
    assert outcomes.chance_all([LIFE]) == 1 and outcomes.chance_all([]) == 1
    other = next(mod_id for mod_id, mod in DATA.mods.items() if mod.generation_type == "suffix" and mod_id != LIFE)
    assert outcomes.chance_all([other]) == 0
    assert outcomes.fractures is False


def test_an_item_built_without_implicits_stores_the_ranged_base_implicits_rolled_and_not_the_fixed_one():
    given = _item(RING)
    assert given.implicits == ()
    ((_, result),) = BlessedOrb().outcomes(DATA, given).results
    assert [entry.mod_id for entry in result.implicits] == [TWO_STAT]  # the fixed implicit has no range: not rerolled, not stored
    assert held(BlessedOrb().outcomes(DATA, given).sample(random.Random(3)), TWO_STAT).grade == 0


def test_a_fixed_implicit_the_item_stores_is_kept_as_it_is_next_to_a_rerolled_one():
    given = _item(RING, implicits=(ImplicitMod(FIXED, 0, (3,)), ImplicitMod(TWO_STAT, 0, (1, 5))))
    ((_, result),) = BlessedOrb().outcomes(DATA, given).results
    assert held(result, FIXED) == ImplicitMod(FIXED, 0, (3,))
    assert BlessedOrb().outcomes(DATA, given).rerolled == (TWO_STAT,)
    assert held(BlessedOrb().outcomes(DATA, given).sample(random.Random(9)), FIXED).values == (3,)


def test_any_rarity_takes_it():
    for rarity in (Rarity.NORMAL, Rarity.MAGIC, Rarity.RARE):
        mods = (ExplicitMod(LIFE, 1, (DATA.mods[LIFE].stats[0].min,)),) if rarity is not Rarity.NORMAL else ()
        assert BlessedOrb().outcomes(DATA, _item(RING, *mods, rarity=rarity))


# --- the refusals -----------------------------------------------------------------------------------


def test_a_corrupted_item_is_refused():
    with pytest.raises(NotApplicableError, match="corrupted"):
        BlessedOrb().outcomes(DATA, belt(30, corrupted=True))


def test_an_item_with_no_implicit_with_a_range_is_refused():
    with pytest.raises(NotApplicableError, match="range"):
        BlessedOrb().outcomes(DATA, _item(PLAIN_RING))  # no implicit at all
    with pytest.raises(NotApplicableError, match="range"):
        BlessedOrb().outcomes(DATA, _item(FIXED_RING))  # a fixed implicit only
    with pytest.raises(NotApplicableError, match="range"):
        BlessedOrb().outcomes(DATA, _item(FIXED_RING, implicits=(ImplicitMod(FIXED, 0, (3,)),)))


def test_an_eldritch_implicit_is_out_of_scope_whatever_else_the_item_holds():
    eldritch = implicit(AVOID_SHOCK_1, 1)
    boots = Item.build(DATA, base_id=BOOTS, item_level=84, rarity=Rarity.RARE, implicits=(eldritch,))
    with pytest.raises(OutOfScopeError, match="Eldritch"):
        BlessedOrb().outcomes(DATA, boots)
    with pytest.raises(OutOfScopeError, match="Eldritch"):  # a ranged base implicit next to it does not change that
        BlessedOrb().outcomes(DATA, _item(BELT, implicits=(eldritch, ImplicitMod(STRENGTH, 0, (30,)))))


# --- the declarations and the contract ------------------------------------------------------------------


def test_the_declarations_name_the_implicits_and_a_roll_limit():
    reads, adds = BlessedOrb().reads(DATA), BlessedOrb().adds(DATA, None)
    assert reads.implicits and not reads.quality and not reads.offer and not reads.rerolls_values
    assert reads.junk and reads.families == frozenset()  # the explicit mods stay as counts
    assert adds.implicits and not adds.quality and not adds.offer
    assert adds.needs_roll_limit and adds.named is None and not adds.draws  # it matters only for a requirement on a roll
    assert BlessedOrb().label(DATA) == "Blessed Orb" and BlessedOrb().resources(DATA) == {"Blessed Orb": 1}


HAPPY = {
    "belt": lambda: belt(30),
    "belt_without_stored_implicit": lambda: belt(None),
    "ring": lambda: _item(RING, ExplicitMod(LIFE, 1, (DATA.mods[LIFE].stats[0].min,))),
    "ring_stored": lambda: _item(RING, implicits=(ImplicitMod(FIXED, 0, (3,)), ImplicitMod(TWO_STAT, 0, (2, 6)))),
}


@pytest.mark.parametrize("name", list(HAPPY))
def test_the_checks_of_the_contract_suite_that_need_no_kernel_pass(name):
    item = HAPPY[name]()
    action = BlessedOrb()
    outcomes = action.outcomes(DATA, item)
    reads, adds = action.reads(DATA), action.adds(DATA, item)
    check_sums_to_one(outcomes, DATA)
    items = finished(outcomes, DATA)
    check_chances_agree(outcomes, items, DATA)
    check_sampler_follows_the_chances(outcomes, items, DATA)
    check_declarations_agree(action, reads, adds, outcomes, items, item)
    check_item_state_declarations(action, reads, adds, items, item, DATA)
    check_resources_are_priced(action, item, DATA)


def test_an_action_that_rerolls_an_implicit_without_saying_so_is_caught():
    @dataclasses.dataclass(frozen=True)
    class Silent(BlessedOrb):
        def adds(self, data=None, item=None):
            return dataclasses.replace(BlessedOrb.adds(self, data, item), implicits=False)

    item = belt(30)
    action = Silent()
    outcomes = action.outcomes(DATA, item)
    with pytest.raises(AssertionError, match="adds.implicits"):
        check_item_state_declarations(action, action.reads(DATA), action.adds(DATA, item), finished(outcomes, DATA), item, DATA)


def test_the_refusals_pass_the_whole_contract_suite_the_kernel_refuses_the_same_way():
    # the kernel of the compressed state rebuilds the item from its state and the action refuses it there too
    plain = _item(PLAIN_RING)
    assert check_action(BlessedOrb(), plain, DATA) is False
    assert check_action(BlessedOrb(), _item(FIXED_RING), DATA) is False
    assert check_action(BlessedOrb(), _item(RING, corrupted=True), DATA) is False


def test_the_compressed_state_does_not_hold_a_base_implicit_before_ticket_158():
    from contract_support import GOAL

    ab = Abstraction(DATA, GOAL, BELT, 84, [BlessedOrb()])
    with pytest.raises(OutOfScopeError, match="158"):
        ab.compress(belt(30))


# --- the kind and the claims ----------------------------------------------------------------------------


def test_the_kind_is_registered_for_items_that_can_hold_an_implicit_and_is_no_planner_kind_yet():
    entry = next(entry for entry in kinds() if entry.name == "blessed-orb")
    assert entry.planner is False and "158" in entry.why_not
    assert BlessedOrb() in catalog(DATA, belt(30), names={"blessed-orb"})
    assert BlessedOrb() in catalog(DATA, _item(RING), names={"blessed-orb"})
    assert catalog(DATA, _item(PLAIN_RING), names={"blessed-orb"}) == ()
    assert catalog(DATA, belt(30, corrupted=True), names={"blessed-orb"}) == ()
    assert BlessedOrb() not in catalog(DATA, belt(30), planner_only=True)


def test_the_orb_names_its_claims_and_marks_the_ones_no_other_source_settles():
    claims = BlessedOrb().claims(DATA)
    assert {
        "blessed_orb.previous_value_can_repeat",
        "blessed_orb.new_value_uniform_in_range",
        "blessed_orb.special_implicits_allowed",
        "blessed_orb.cost",
    } <= claims
    assert rule_by_id("blessed_orb.new_value_uniform_in_range").approximate  # only Craft of Exile's code gives the law
    assert rule_by_id("blessed_orb.previous_value_can_repeat").source_kind.value == "owner"
    assert rule_by_id("blessed_orb.cost").value["Blessed Orb"] == 1


def test_the_outcomes_are_a_finite_result_of_one_part():
    outcomes = BlessedOrb().outcomes(DATA, belt(30))
    assert isinstance(outcomes, BlessedOutcomes) and len(outcomes.components) == 1
    assert isinstance(BlessedOrb(), Action)


# --- the real Heavy Belt of R06 ---------------------------------------------------------------------------


def test_the_real_heavy_belt_rerolls_its_strength_between_25_and_35():
    data = real_game_data()
    base = next(base for base in data.base_items.values() if base.name == "Heavy Belt" and base.item_class == "Belt")
    given = Item.build(
        data, base_id=base.id, item_level=84, rarity=Rarity.RARE, implicits=(ImplicitMod(base.implicits[0], 0, (35,)),)
    )
    outcomes = BlessedOrb().outcomes(data, given)
    assert outcomes.value_law(base.implicits[0], 0) == {value: Fraction(1, 11) for value in range(25, 36)}
    assert outcomes.chance_all([]) == 1
