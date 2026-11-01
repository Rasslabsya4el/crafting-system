"""The Bloodstained Fossil (ticket #261, ADR-0038), against hand oracles on the small boots world of `bloodstained_support.py`.

"Done when" of the ticket, and where each line is tested:

1. *Layer 1 equals the fossil kernel times the implicit enumeration.* `test_the_kernel_equals_the_brute_force_of_the_fossil_times_the_implicit_cases`
   lists every finished item of the same resonator without the Bloodstained Fossil (`abstraction_fossil.fossil_finished`, which does
   not touch `exact_distribution`), puts on each the implicits of every case of a hand-written draw (`implicit_cases`: the weights of the
   pool and the rule of replacement written again as plain fractions), compresses them and adds up. The kernel of the resonator must be
   that distribution, exactly. `test_the_chance_of_the_goal_is_the_fossils_times_the_implicits` states the product itself: the chance
   that the finished item holds the wanted explicit mods and the wanted implicit is, three ways and in exact fractions, the sum over
   the enumerated items, `chance_all` of the resonator, and the plain resonator's `chance_all` times the draw's chance.
2. *A Bloodstained set is absent for a target without a corrupted implicit.* `test_offers_*`: the offers of a target that does not take
   corruption, and of one that only allows a corrupted item, hold the ordinary fossil sets and none with the Bloodstained Fossil; a
   target that asks for a corrupted implicit gets them.
3. *Existing fossil kernels are byte-identical.* `test_actions_fossil_unchanged.py`.

The rest: the draw itself (`ImplicitDraw`), the item level gate, the refusals, the sampler, the declarations the planner reads.
"""

import dataclasses
import random
from collections import Counter
from fractions import Fraction
from functools import cache

import pytest
from abstraction_fossil import fossil_finished
from abstraction_oracle import assert_same_distribution, compressed_distribution
from bloodstained_support import (
    ALL_RES,
    BASE_IMPLICIT,
    BLOODSTAINED,
    CHAOS_RES,
    COLD_DAMAGE,
    DATA,
    EXARCH,
    GILDED,
    IMPLICIT_BOOTS,
    JEWEL,
    JEWEL_LATE,
    LATE,
    LEVEL,
    NO_POOL_GLOVES,
    POOL,
    bloodstained,
    boots,
    forbidding,
    implicit_cases,
    plain,
    pool_weights,
    starts,
    unstored_of,
)
from test_actions_fossil import roll

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    Action,
    ApplyFossils,
    ChaosOrb,
    NotApplicableError,
    OutOfScopeError,
    fossil_actions,
    usable_fossils,
)
from crafting_system.actions.bloodstained import BloodstainedOutcomes, ImplicitDraw
from crafting_system.cli._offers import offers_for
from crafting_system.items import ImplicitMod, Influence

FIRE = Wanted(frozenset({"FireA", "FireB"}), min_tier=1)
LIFE = Wanted(frozenset({"LifeA", "LifeB"}))
RESIST = Wanted(frozenset({"FireResA"}))
EXPLICIT = (FIRE, LIFE, RESIST)

# the sets that carry the Bloodstained Fossil, by the other fossils; "Gilded" is the one that makes the implicit replace them all
SETS = [
    (),
    ("Scorched",),
    ("Scorched", "Elemental"),
    ("Gilded",),
    ("Gilded", "Scorched"),
    ("Tangled",),
    ("Hollow",),
    ("Glyphic", "Lucent"),
    ("Fractured", "Scorched"),
    ("Opulent", "Gilded"),
]
STARTS = list(starts())


def the_plain_reroll(others: tuple[str, ...]) -> Action:
    """The resonator without the Bloodstained Fossil, or a Chaos Orb when it holds no other (a set without weights rerolls like one)."""
    return plain(*others) or ChaosOrb()


def refused(others: tuple[str, ...], start: str) -> bool:
    """A Fractured Fossil is refused on an item that has a fractured mod, with or without the Bloodstained Fossil."""
    return "Fractured" in others and start == "fractured"


def ids_of(item) -> frozenset[str]:
    return frozenset(entry.mod_id for entry in item.mods)


@cache
def the_fossil_finished(others: tuple[str, ...], start: str):
    """Every finished item of the resonator without the Bloodstained Fossil, with its chance: the fossil kernel, enumerated by hand."""
    return fossil_finished(DATA, the_plain_reroll(others), starts()[start])


def implicit_of(item, mod_id: str) -> ImplicitMod:
    held = {entry.mod_id: entry for entry in item.implicits}
    if mod_id in held:
        return held[mod_id]
    mod = DATA.mods[mod_id]
    return ImplicitMod(mod_id, 0, tuple(min(stat.min, stat.max) for stat in mod.stats))


def the_cases(others: tuple[str, ...], start: str):
    item = starts()[start]
    return implicit_cases([entry.mod_id for entry in item.implicits], pool_weights(item.item_level), "Gilded" in others, unstored_of(item))


@cache
def enumerated(others: tuple[str, ...], start: str):
    """Every finished item of the Bloodstained resonator with its chance: the fossil's items times the hand cases of the implicit draw."""
    item = starts()[start]
    listed = []
    for finished, chance in the_fossil_finished(others, start):
        for case_chance, ids in the_cases(others, start):
            implicits = tuple(implicit_of(item, mod_id) for mod_id in sorted(ids))
            listed.append((finished.changed(DATA, corrupted=True, implicits=implicits), chance * case_chance))
    assert sum(chance for _, chance in listed) == 1
    return listed


# --- Done when 1: layer 1 -------------------------------------------------------------------------------


@pytest.mark.parametrize("start", STARTS)
@pytest.mark.parametrize("others", SETS, ids=lambda others: "+".join(("Bloodstained", *others)))
def test_the_kernel_equals_the_brute_force_of_the_fossil_times_the_implicit_cases(others, start):
    """Layer 1. The compressed state keeps no corrupted implicit (ADR-0036), so the drawn mod collapses in it; what the draw leaves of the
    state is the Eldritch pair that the replacement keeps, which the brute force plays by hand. Which implicit was drawn, and its chance
    with the explicit goal, is the next test."""
    item = starts()[start]
    action = bloodstained(*others)
    ab = Abstraction(DATA, Goal(EXPLICIT, asks_corrupted=True), item.base_id, item.item_level, [action])
    if start == "base-and-eldritch":  # the state holds the Eldritch pair only: a base implicit has no state until ticket #158
        with pytest.raises(OutOfScopeError, match="base implicit"):
            ab.compress(item)
        return
    if refused(others, start):
        with pytest.raises(NotApplicableError):
            ab.kernel(ab.compress(item), action)
        return

    kernel = ab.kernel(ab.compress(item), action)

    assert_same_distribution(kernel, compressed_distribution(enumerated(others, start), ab.compress))
    assert all(state.flags.corrupted for state in kernel)  # a corrupted item is final


@pytest.mark.parametrize("start", ["none", "two"])
@pytest.mark.parametrize("others", [(), ("Scorched",), ("Fractured", "Scorched"), ("Gilded", "Tangled")], ids=lambda o: "+".join(("B", *o)))
def test_the_goal_mass_of_the_kernel_is_the_fossils(others, start):
    """The state keeps no corrupted implicit (ADR-0036): the mass on goal states is the plain resonator's, whatever the draw gives."""
    item = starts()[start]
    action = bloodstained(*others)
    asking = Abstraction(DATA, Goal(EXPLICIT, asks_corrupted=True), item.base_id, item.item_level, [action])
    reroll = the_plain_reroll(others)
    ordinary = Abstraction(DATA, Goal(EXPLICIT), item.base_id, item.item_level, [])

    corrupting = asking.kernel(asking.compress(item), action)
    rerolling = ordinary.kernel(ordinary.compress(item), reroll)

    assert sum(chance for state, chance in corrupting.items() if asking.is_goal(state)) == sum(
        chance for state, chance in rerolling.items() if ordinary.is_goal(state)
    )


WANTED = {
    "all resistances": ALL_RES,
    "chaos resistance": CHAOS_RES,
    "the level 75 mod": LATE,
    "a held Eldritch implicit": EXARCH,
    "the base implicit": BASE_IMPLICIT,
}


CHANCE_CASES = [
    pytest.param(wanted, others, start, id=f"{name}-{'+'.join(('B', *others))}-{start}")
    for name, wanted in WANTED.items()
    for others in [(), ("Scorched",), ("Gilded", "Scorched"), ("Fractured", "Scorched")]
    for start in STARTS
    if not refused(others, start)
]


@pytest.mark.parametrize(("wanted", "others", "start"), CHANCE_CASES)
def test_the_chance_of_the_goal_is_the_fossils_times_the_implicits(wanted, others, start):
    item = starts()[start]
    explicit = ["FireA", "LifeA"]
    outcomes = bloodstained(*others).outcomes(DATA, item)

    # 1. the enumeration of the finished items
    both = sum(
        (chance for found, chance in enumerated(others, start) if set(explicit) <= ids_of(found) and wanted in {e.mod_id for e in found.implicits}),
        Fraction(0),
    )
    # 2. the resonator's own answer
    answered = outcomes.chance_all([*explicit, wanted])
    # 3. the fossil kernel times the implicit chance
    fossil = sum((chance for found, chance in the_fossil_finished(others, start) if set(explicit) <= ids_of(found)), Fraction(0))
    implicit = sum((chance for chance, ids in the_cases(others, start) if wanted in ids), Fraction(0))

    assert both == answered == fossil * implicit
    assert outcomes.chance_all(explicit) == fossil  # the draw adds no explicit mod
    assert outcomes.chance_all([wanted]) == implicit  # and the reroll adds no implicit


def test_the_ring_like_case_one_mod_of_weight_1000_in_a_pool_of_1950_when_the_item_has_no_implicit():
    outcomes = bloodstained("Scorched").outcomes(DATA, starts()["none"])

    assert outcomes.chance_all([ALL_RES]) == Fraction(1000, 1950)
    assert outcomes.chance_all([CHAOS_RES]) == Fraction(250, 1950)
    assert outcomes.chance_all([ALL_RES, CHAOS_RES]) == 0  # one corrupted implicit only


# --- the draw: which implicit goes ----------------------------------------------------------------------


def draw_of(start: str, replaces_all: bool = False) -> ImplicitDraw:
    return ImplicitDraw.for_item(DATA, starts()[start], replaces_all)


@pytest.mark.parametrize("replaces_all", [False, True], ids=["ordinary", "gilded"])
@pytest.mark.parametrize("start", STARTS)
def test_the_cases_of_the_draw_are_the_hand_cases(start, replaces_all):
    item = starts()[start]
    draw = draw_of(start, replaces_all)
    expected = Counter()
    for chance, ids in implicit_cases([e.mod_id for e in item.implicits], pool_weights(item.item_level), replaces_all, unstored_of(item)):
        expected[ids] += chance

    got = Counter()
    for case in draw.cases:
        got[frozenset(entry.mod_id for entry in case.implicits)] += case.chance

    assert got == expected and sum(got.values()) == 1
    assert all(case.drawn.grade == 0 and case.drawn.mod_id in POOL for case in draw.cases)


def test_an_item_with_no_implicit_gains_the_drawn_one():
    assert {tuple(case.kept) for case in draw_of("none").cases} == {()}


def test_an_item_with_one_implicit_loses_it_and_one_with_two_loses_one_of_them_at_random():
    assert {case.kept for case in draw_of("one").cases} == {()}
    kept = Counter()
    for case in draw_of("two").cases:
        kept[tuple(entry.mod_id for entry in case.kept)] += case.chance
    assert dict(kept) == {(EXARCH,): Fraction(1, 2), ("EldritchEaterImplicit2",): Fraction(1, 2)}


def test_a_gilded_fossil_replaces_every_implicit():
    gilded = draw_of("two", replaces_all=True)
    assert {case.kept for case in gilded.cases} == {()}
    assert sum(case.chance for case in gilded.cases) == 1
    outcomes = bloodstained("Gilded").outcomes(DATA, starts()["two"])
    assert outcomes.chance_all([EXARCH]) == 0  # nothing stays
    assert bloodstained("Scorched").outcomes(DATA, starts()["two"]).chance_all([EXARCH]) == Fraction(1, 2)


def test_the_base_implicit_is_replaced_like_any_other():
    outcomes = bloodstained().outcomes(DATA, starts()["base-and-eldritch"])
    assert outcomes.chance_all([BASE_IMPLICIT]) == Fraction(1, 2)
    assert outcomes.chance_all([BASE_IMPLICIT, "EldritchEaterImplicit2"]) == 0  # one of the two goes


def test_a_base_implicit_the_item_does_not_store_is_a_candidate_for_the_replacement_all_the_same():
    """`Item` stores an implicit only when given one, but the game's boots have the base implicit: the Eldritch one goes with chance 1/2, not 1."""
    item = starts()["unstored-base-implicit"]
    assert [entry.mod_id for entry in item.implicits] == ["EldritchEaterImplicit2"] and unstored_of(item) == [BASE_IMPLICIT]

    outcomes = bloodstained().outcomes(DATA, item)
    assert outcomes.chance_all(["EldritchEaterImplicit2"]) == Fraction(1, 2)
    assert outcomes.chance_all([BASE_IMPLICIT]) == 0  # not on the finished item: it is not stored, and it is not drawn
    assert bloodstained("Gilded").outcomes(DATA, item).chance_all(["EldritchEaterImplicit2"]) == 0
    only = starts()["none"]  # a base with no implicit of its own: nothing to replace
    assert ImplicitDraw.for_item(DATA, dataclasses.replace(only, base_id=IMPLICIT_BOOTS), False).unstored == 1
    assert ImplicitDraw.for_item(DATA, only, False).unstored == 0


def test_the_pool_is_cut_at_the_item_level():
    low = boots(roll("LifeA"), item_level=60)
    high = starts()["none"]

    assert bloodstained().outcomes(DATA, high).chance_all([LATE]) == Fraction(200, 1950)
    assert bloodstained().outcomes(DATA, low).chance_all([LATE]) == 0
    assert bloodstained().outcomes(DATA, low).chance_all([ALL_RES]) == Fraction(1000, 1750)


def test_a_chance_of_an_unknown_mod_is_a_value_error():
    with pytest.raises(ValueError, match="not in the game data"):
        bloodstained().outcomes(DATA, starts()["none"]).chance_all(["NoSuchMod"])


def test_the_chance_of_no_mod_is_one():
    assert bloodstained("Scorched").outcomes(DATA, starts()["none"]).chance_all([]) == 1


# --- what the outcomes are -----------------------------------------------------------------------------


def test_the_outcomes_are_a_corrupting_mixture_over_the_fossil_components_and_the_cases():
    outcomes = bloodstained("Tangled").outcomes(DATA, starts()["two"])
    reroll = plain("Tangled").outcomes(DATA, starts()["two"])

    assert isinstance(outcomes, BloodstainedOutcomes)
    assert len(outcomes.components) == len(reroll.components) * len(outcomes.draw.cases)
    assert sum(share for share, _ in outcomes.components) == 1
    for _, part in outcomes.components:
        assert part.retained.corrupted and len(part.retained.implicits) == 2
    assert outcomes.fractures is False and bloodstained("Fractured").outcomes(DATA, starts()["none"]).fractures is True


def test_the_distribution_of_the_new_mods_is_the_fossils():
    for others in SETS:
        item = starts()["one"]
        label = lambda mod: mod.generation_type  # noqa: E731
        assert bloodstained(*others).outcomes(DATA, item).distribution(label) == the_plain_reroll(others).outcomes(DATA, item).distribution(label)


def test_a_corrupted_part_keeps_the_pool_and_the_forced_mod_of_the_reroll():
    outcomes = bloodstained("Hollow").outcomes(DATA, starts()["none"])
    assert {part.forced for _, part in outcomes.components} == {"AbyssSocketA"}
    reroll = plain("Hollow").outcomes(DATA, starts()["none"])
    assert {part.pool for _, part in outcomes.components} == {part.pool for _, part in reroll.components}


@pytest.mark.parametrize("others", [(), ("Scorched",), ("Gilded", "Sanctified"), ("Fractured", "Scorched")], ids=lambda o: "+".join(("B", *o)))
@pytest.mark.parametrize("start", ["none", "two"])
def test_the_sampler_holds_the_implicits_as_often_as_the_chances_say(others, start):
    item = starts()[start]
    outcomes = bloodstained(*others).outcomes(DATA, item)
    rng = random.Random(261)
    runs = 4_000
    seen = Counter()
    for _ in range(runs):
        drawn = outcomes.sample(rng)
        drawn.validate(DATA)
        assert drawn.corrupted and drawn.rarity is item.rarity
        held = [entry.mod_id for entry in drawn.implicits]
        corrupted = [mod_id for mod_id in held if DATA.mods[mod_id].generation_type == "corrupted"]
        assert len(corrupted) == 1  # one corrupted implicit, never none, never two
        seen.update(held)
        entry = next(e for e in drawn.implicits if e.mod_id == corrupted[0])
        for value, stat in zip(entry.values, DATA.mods[corrupted[0]].stats):
            assert stat.min <= value <= stat.max
    for mod_id in (ALL_RES, CHAOS_RES, COLD_DAMAGE, LATE, EXARCH, "EldritchEaterImplicit2"):
        chance = float(outcomes.chance_all([mod_id]))
        assert abs(seen[mod_id] / runs - chance) <= 5 * (chance * (1 - chance) / runs) ** 0.5 + 1e-9, mod_id


def test_a_sanctified_fossil_does_not_make_the_implicit_lucky():
    """`fossils.sanctified_values_lucky` rolls the values of the mods the reroll puts on twice; the implicit is not affected by the other fossils."""
    outcomes = bloodstained("Sanctified").outcomes(DATA, starts()["none"])
    rng = random.Random(7)
    values = Counter()
    for _ in range(3_000):
        drawn = outcomes.sample(rng)
        values.update(entry.values[0] for entry in drawn.implicits if entry.mod_id == ALL_RES)
    assert set(values) == {14, 15, 16}
    low = values[14] / sum(values.values())
    assert abs(low - 1 / 3) < 0.05  # a lucky roll of 14..16 would give 14 one time in nine


# --- refusals -------------------------------------------------------------------------------------------


def test_a_corrupted_item_takes_no_resonator_with_a_bloodstained_fossil_either():
    corrupted = dataclasses.replace(starts()["none"], corrupted=True)
    with pytest.raises(NotApplicableError, match="corrupted"):
        bloodstained().outcomes(DATA, corrupted)


def test_a_base_with_no_corrupted_pool_refuses_the_set_and_does_not_list_the_fossil():
    gloves = boots(roll("LifeA"), base=NO_POOL_GLOVES)
    with pytest.raises(NotApplicableError, match="no corrupted implicit pool"):
        bloodstained("Scorched").outcomes(DATA, gloves)
    assert BLOODSTAINED not in usable_fossils(DATA, gloves) and "Scorched Fossil" in usable_fossils(DATA, gloves)
    assert BLOODSTAINED in usable_fossils(DATA, starts()["none"])


def test_an_empty_pool_at_the_item_level_is_out_of_scope():
    low_jewel = boots(base=JEWEL, item_level=30)
    with pytest.raises(OutOfScopeError, match="pool .* is empty"):
        bloodstained().outcomes(DATA, low_jewel)
    assert BLOODSTAINED not in usable_fossils(DATA, low_jewel)
    assert bloodstained().outcomes(DATA, boots(base=JEWEL, item_level=45)).chance_all([JEWEL_LATE]) == 1


def test_a_cluster_jewel_is_out_of_scope():
    cluster = dataclasses.replace(DATA.base_items[JEWEL], domain="affliction_jewel")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, JEWEL: cluster})
    with pytest.raises(OutOfScopeError, match="[Cc]luster"):
        bloodstained().outcomes(data, boots(base=JEWEL))


def test_hollow_and_glyphic_in_one_resonator_stay_out_of_scope_with_a_bloodstained_fossil():
    with pytest.raises(OutOfScopeError, match="Hollow and Glyphic"):
        bloodstained("Hollow", "Glyphic").outcomes(DATA, starts()["none"])


def test_a_refusal_of_the_game_comes_before_a_set_that_is_out_of_scope():
    """The order of the module text: `NotApplicableError` (no pool on these gloves) before `OutOfScopeError` (Hollow with Glyphic)."""
    gloves = boots(roll("LifeA"), base=NO_POOL_GLOVES)
    with pytest.raises(NotApplicableError, match="no corrupted implicit pool"):
        bloodstained("Hollow", "Glyphic").outcomes(DATA, gloves)


def test_a_fractured_fossil_is_still_refused_on_a_fractured_item():
    with pytest.raises(NotApplicableError, match="fractured"):
        bloodstained("Fractured").outcomes(DATA, starts()["fractured"])


def test_a_fossil_that_forbids_the_item_refuses_it_and_is_not_listed():
    data = forbidding("boots")
    with pytest.raises(NotApplicableError, match="does not work on an item with the tag boots"):
        bloodstained().outcomes(data, starts()["none"])
    assert BLOODSTAINED not in usable_fossils(data, starts()["none"])


def test_a_metamod_refuses_the_resonator_as_before():
    with pytest.raises(NotApplicableError, match="metamod"):
        bloodstained().outcomes(DATA, boots(roll("MetaNoSuffixChange", crafted=True)))


def test_an_influenced_item_takes_the_resonator_and_stays_influenced():
    influenced = dataclasses.replace(starts()["none"], influences=frozenset({Influence.ELDER}))
    outcomes = bloodstained("Scorched").outcomes(DATA, influenced)
    assert {part.retained.influences for _, part in outcomes.components} == {influenced.influences}


# --- what the planner reads -----------------------------------------------------------------------------


def test_the_set_declares_that_it_corrupts_rerolls_the_mods_and_is_offered_only_when_asked():
    adds = bloodstained("Scorched").adds(DATA, starts()["none"])
    assert (adds.corrupts, adds.asked_only, adds.implicits, adds.keeps_mods) == (True, True, True, False)
    assert adds.keeps_crafted is False and adds.named == frozenset()  # it erases the crafted mods like any reroll
    assert bloodstained("Hollow").adds(DATA).named == frozenset({"AbyssSocketA"})
    assert bloodstained("Glyphic").adds(DATA).named is None
    assert bloodstained("Fractured").adds(DATA).fractures and bloodstained().adds(None).corrupts  # the name is enough without data

    reads = bloodstained("Scorched").reads(DATA)
    assert (reads.junk, reads.implicits, reads.block_invariant, reads.pool_weight) == (False, True, False, False)


def test_a_set_without_the_bloodstained_fossil_declares_what_it_did():
    adds, reads = plain("Scorched").adds(DATA, starts()["none"]), plain("Scorched").reads(DATA)
    assert (adds.corrupts, adds.asked_only, adds.implicits, adds.keeps_mods) == (False, False, False, False)
    assert reads.block_invariant and not reads.junk and not reads.implicits
    assert plain("Gilded", "Scorched").adds(DATA).corrupts is False  # a Gilded Fossil alone corrupts nothing


def test_the_claims_of_the_draw_belong_to_the_sets_that_hold_the_bloodstained_fossil():
    drawn = {
        "corruption.bloodstained_never_fails",
        "corruption.bloodstained_fossil_implicit",
        "corruption.implicit_replaces_existing",
        "corruption.implicit_pool_by_item_class",
        "fossils.bloodstained_gilded_replaces_all_implicits",
    }
    assert drawn <= bloodstained("Scorched").claims(DATA)
    assert drawn <= bloodstained().claims()  # the data is optional
    assert not drawn & plain("Scorched").claims(DATA)
    assert bloodstained("Scorched").claims(DATA) - drawn == plain("Scorched").claims(DATA)
    assert not drawn & plain("Gilded", "Scorched").claims(DATA)


def test_the_resonator_and_the_prices_name_the_fossil_like_every_other():
    action = bloodstained("Scorched", "Elemental")
    assert action.resources(DATA) == {"Powerful Chaotic Resonator": 1, BLOODSTAINED: 1, "Elemental Fossil": 1, "Scorched Fossil": 1}
    assert action.label(DATA) == "Fossils Bloodstained Fossil + Elemental Fossil + Scorched Fossil"


def test_twins_keep_the_corruption_and_the_gilded_fossil_apart():
    item = starts()["none"]
    key = lambda action: action.twin_key(DATA, item)  # noqa: E731

    assert key(bloodstained("Scorched")) != key(plain("Scorched"))  # corrupting and not
    assert key(bloodstained("Dull")) == key(bloodstained("Gloveless"))  # the same pools, both corrupt: twins as before
    assert key(plain("Dull")) == key(plain("Gloveless")) == key(plain("Gilded"))
    assert key(bloodstained("Dull")) != key(bloodstained("Gilded"))  # a Gilded Fossil changes which implicit goes
    assert key(bloodstained("Gilded", "Dull")) == key(bloodstained("Gilded", "Gloveless"))
    assert key(bloodstained("Scorched")) != key(bloodstained("Frigid"))  # other pools


def test_twins_have_equal_outcomes():
    """What `twin_key` promises: equal keys, equal outcomes (components and chances) on every start."""
    for start, item in starts().items():
        one, two = bloodstained("Dull").outcomes(DATA, item), bloodstained("Gloveless").outcomes(DATA, item)
        assert [(share, part.retained, part.pool) for share, part in one.components] == [
            (share, part.retained, part.pool) for share, part in two.components
        ], start


def test_the_listing_adds_the_bloodstained_sets_where_the_item_has_a_pool():
    item = starts()["none"]
    actions = fossil_actions(DATA, item)
    with_it = [action for action in actions if BLOODSTAINED in action.fossils]
    assert with_it and len(set(actions)) == len(actions)
    assert not any({"Hollow Fossil", "Glyphic Fossil"} <= set(action.fossils) for action in actions)
    names = usable_fossils(DATA, item)
    assert {BLOODSTAINED, GILDED} <= set(names)
    assert [action for action in actions if BLOODSTAINED not in action.fossils] == fossil_actions(without_bloodstained(), item)


def without_bloodstained():
    """The world without the Bloodstained record, which lists exactly the sets that existed before the ticket."""
    return dataclasses.replace(DATA, fossils={key: value for key, value in DATA.fossils.items() if value.name != BLOODSTAINED})


# --- Done when 2: the offers ----------------------------------------------------------------------------

PLAIN_TARGET = Goal(EXPLICIT)
ALLOWING_TARGET = Goal(EXPLICIT, allow_corrupted=True)
ASKING_TARGET = Goal(EXPLICIT, asks_corrupted=True)


@cache
def offered(goal: Goal, names=("fossil-set",)) -> list[str]:
    item = starts()["none"]
    return [offer.label for offer in offers_for(DATA, goal, item.base_id, item, names).offers]


def test_offers_hold_no_bloodstained_set_for_a_target_without_a_corrupted_implicit():
    labels = offered(PLAIN_TARGET)
    assert labels and not any(BLOODSTAINED in label for label in labels)


def test_offers_hold_no_bloodstained_set_for_a_target_that_only_allows_a_corrupted_item():
    """The same set without the Bloodstained Fossil is offered and meets the target uncorrupted, so the corrupting one is only a price."""
    labels = offered(ALLOWING_TARGET)
    assert labels == offered(PLAIN_TARGET)


def test_offers_hold_the_bloodstained_sets_for_a_target_that_asks_for_a_corrupted_implicit():
    labels = offered(ASKING_TARGET)
    with_it = [label for label in labels if BLOODSTAINED in label]
    assert with_it
    assert [label for label in labels if BLOODSTAINED not in label] == offered(PLAIN_TARGET)  # and every ordinary set stays, in order


def test_offers_do_not_list_the_bloodstained_sets_unless_the_fossil_sets_are_named():
    assert not any(BLOODSTAINED in label for label in offered(ASKING_TARGET, names=None))
    assert not any(BLOODSTAINED in label for label in offered(ASKING_TARGET, names=("chaos-orb",)))


def test_a_set_named_by_its_label_is_still_filtered_by_the_goal():
    label = bloodstained("Scorched").label(DATA)
    assert label in offered(ASKING_TARGET, names=(label,))
    assert label not in offered(PLAIN_TARGET, names=(label,)) and label not in offered(ALLOWING_TARGET, names=(label,))


def test_the_report_says_nothing_of_a_bloodstained_set_that_is_left_out():
    item = starts()["none"]
    for goal in (PLAIN_TARGET, ALLOWING_TARGET):
        chosen = offers_for(DATA, goal, item.base_id, item, ("fossil-set",))
        assert not any(BLOODSTAINED in label for entry in chosen.left_out for label in entry.labels)


def test_a_bloodstained_offer_is_not_pruned_from_a_state_that_misses_a_requirement():
    """It rerolls the explicit mods itself: unlike a Vaal Orb it can reach the goal from any state (ADR-0036)."""
    from crafting_system.cli import PricedOffer
    from crafting_system.cli._offers import offer_of
    from crafting_system.cli._prune import corrupting_offer_pruned

    item = starts()["none"]
    action = bloodstained("Scorched")
    ab = Abstraction(DATA, Goal(EXPLICIT, asks_corrupted=True), item.base_id, item.item_level, [action])
    offer = PricedOffer(offer_of(action, action.label(DATA), DATA, item), 5.0, ())
    failing = ab.compress(item)

    assert not ab.meets_requirements(failing)
    assert corrupting_offer_pruned(ab, offer, failing) is False
