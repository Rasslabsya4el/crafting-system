"""The crafted-pattern bound with the Eldritch currencies (#835, ADR-0025): the member policies of `abstraction/_pattern.py`, "The Eldritch
implicits", checked by brute force on the hand-made boots of `eldritch_support`.

The world: rare boots with two suffixes and no implicit, a goal that wants the Life prefix and a Searing Exarch Avoid Shock implicit of grade 2
or more, and the the Lesser Ember and Ichor, the three Eldritch orbs, the Orb of Conflict and a restart. Its exact graph is walked
(`pattern_support.exact_values`); on it:

* at 500 keys of the exact graph drawn at random, each Eldritch currency's offered members are at least as good as every member of the key, for random values
  of the successor keys (`check_dominates`: the brute force over all members);
* the model of the key is a lower bound of the exact value at every state, and the envelope search's mean is the exact graph's.
"""

import random

import pytest
from eldritch_support import BOOTS, COLD, DATA, FIRE, LEVEL, LIFE, LOCK_SUFFIXES, boots, eldritch_id, exarch, roll
from pattern_support import check_dominates, exact_values

from crafting_system.abstraction import Abstraction, Goal, ImplicitWanted, Wanted, pattern_refusal
from crafting_system.abstraction._pattern import Mode, Pattern, PatternOffer, build_pattern_model
from crafting_system.actions import EldritchAnnulmentOrb, EldritchChaosOrb, EldritchExaltedOrb, EldritchImplicitCurrency, OrbOfConflict
from crafting_system.cli import Offer
from crafting_system.items import EldritchSide
from crafting_system.planner._envelope_plan import envelope_result
from crafting_system.planner._offers import ELDRITCH_KINDS, RESTART, BuyStartItem, PricedOffer, eldritch_unreachable, offers_for
from crafting_system.planner._pattern_bound import pack_pattern_model
from crafting_system.solver import solve_packed

TOLERANCE = 1e-9
SAMPLED = 500  # keys of the exact graph the brute force compares at (of about 1,600; all of them take half a minute more)
RESTART_PRICE = 1.0
GOAL = Goal(
    (Wanted(frozenset({LIFE})),),
    (ImplicitWanted(frozenset(eldritch_id("AvoidShock", grade) for grade in range(2, 7))),),
)
START = boots(roll(FIRE), roll(COLD))
EMBERS = {  # the Lesser Ember and Ichor: grade 2 comes from the Conflict alone (a small exact graph)
    "Lesser Ember": (EldritchImplicitCurrency(EldritchSide.EXARCH, 1), 0.2),
    "Lesser Ichor": (EldritchImplicitCurrency(EldritchSide.EATER, 1), 0.1),
}
# the Eldritch Chaos Orb is `ALL` (exact by construction) and tells every junk family apart: with it the exact graph is ten times larger, so its
# policy is checked alone (`test_the_bound_is_built_for_the_eldritch_currencies`)
CHAOS = {"Eldritch Chaos": (EldritchChaosOrb(), 0.3)}
ORBS = {"Eldritch Exalted": (EldritchExaltedOrb(), 0.8), "Eldritch Annulment": (EldritchAnnulmentOrb(), 0.4), "Conflict": (OrbOfConflict(), 0.25)}  # fmt: skip
OFFERED = {**EMBERS, **ORBS}
POLICY = {  # the member policy each currency is shown to have (module docstring), without a lock
    "Eldritch Chaos": Mode.ALL,
    "Eldritch Exalted": Mode.EXTREMES,
    "Eldritch Annulment": Mode.ONE,
    "Conflict": Mode.ONE,
    **{label: Mode.ONE for label in EMBERS},
}


def abstraction() -> Abstraction:
    return Abstraction(DATA, GOAL, BOOTS, LEVEL, tuple(action for action, _ in OFFERED.values()))


def pattern_offers() -> list[PatternOffer]:
    return [PatternOffer(label, action, cost) for label, (action, cost) in OFFERED.items()] + [PatternOffer(RESTART, None, RESTART_PRICE)]


def priced_offers() -> list[PricedOffer]:
    offers = [PricedOffer(Offer(label, action, {label: 1}), cost, ()) for label, (action, cost) in OFFERED.items()]
    return [*offers, PricedOffer(Offer(RESTART, BuyStartItem(START), {}), RESTART_PRICE, ())]


@pytest.fixture(scope="module")
def world():
    """The abstraction, the start state, the exact values, the model of the key and its values, built once."""
    ab = abstraction()
    first = ab.compress(START)
    offers = pattern_offers()
    exact = exact_values(ab, first, offers)
    model = build_pattern_model(ab, first, offers)
    solved = solve_packed(pack_pattern_model(model, offers))
    return ab, first, exact, model, [float(value) for value in solved.value]


def test_the_bound_is_built_for_the_eldritch_currencies():
    ab = abstraction()
    assert ab.tracks_implicits and pattern_refusal(ab) is None
    pattern = Pattern(ab, None, [action for action, _ in OFFERED.values()])
    key = pattern.key(ab.compress(START))
    for label, (action, _) in {**OFFERED, **CHAOS}.items():
        assert pattern.mode_of(action, key) is POLICY[label], label


def test_under_a_lock_the_policies_take_every_member():
    ab = Abstraction(DATA, GOAL, BOOTS, LEVEL, tuple(action for action, _ in OFFERED.values()), metamods=True)
    pattern = Pattern(ab, None, [action for action, _ in OFFERED.values()])
    key = pattern.key(ab.compress(boots(roll(LIFE), roll(LOCK_SUFFIXES, crafted=True), implicits=(exarch(2),))))
    assert pattern.holds_lock(key)
    for label in ("Eldritch Annulment", "Conflict", next(iter(EMBERS)), "Eldritch Chaos"):
        assert pattern.mode_of({**OFFERED, **CHAOS}[label][0], key) is Mode.ALL, label


def test_every_member_of_every_key_is_matched_by_an_offered_one(world):
    """The brute force: at keys of the exact graph, for each Eldritch currency, the least backup over the members its policy offers is no
    higher than the backup of any member of the key, for random values of the successor keys; and it is offered wherever a member can take it."""
    ab, _first, exact, _model, _values = world
    pattern = Pattern(ab, None, [action for action, _ in OFFERED.values()])
    rng = random.Random(835)
    keys = sorted({pattern.key(state) for state in exact if not ab.is_goal(state)}, key=repr)
    compared = taken = 0
    by_policy = {Mode.ONE: 0, Mode.EXTREMES: 0, Mode.ALL: 0}
    for key in rng.sample(keys, min(SAMPLED, len(keys))):
        for label, (action, _) in OFFERED.items():
            mode, named = pattern.policy(action, key)
            members, legal = check_dominates(pattern, ab, key, action, mode, rng, trials=8, named=named)
            compared += members
            taken += legal
            by_policy[mode] += bool(legal)
    assert compared and taken
    assert by_policy[Mode.ONE] and by_policy[Mode.EXTREMES], by_policy


def test_the_model_is_a_lower_bound_at_every_state_of_the_exact_graph(world):
    ab, first, exact, model, values = world
    pattern = Pattern(ab, None, [action for action, _ in OFFERED.values()])
    assert model.stopped is None
    implicit_states = 0
    for state, value in exact.items():
        key = pattern.key(state)
        assert key in model.index, "a state of the exact graph has a key the model never reached"
        assert values[model.index[key]] <= value * (1 + TOLERANCE) + TOLERANCE, (state, value)
        implicit_states += bool(state.implicits and any(side.grade for side in state.implicits))
    assert implicit_states, "no state of the exact graph holds an Eldritch implicit"
    assert values[0] <= exact[first] * (1 + TOLERANCE) and exact[first] < float("inf")


def test_the_envelope_search_gives_the_exact_graphs_mean(world):
    ab, first, exact, _model, _values = world
    result = envelope_result(ab, first, priced_offers())
    info = result.info["envelope"]
    assert info.exact and info.bound_stopped is None
    assert result.solution.values[first] == pytest.approx(exact[first], rel=TOLERANCE)
    assert info.lower <= exact[first] * (1 + TOLERANCE)


def test_the_eldritch_currencies_are_offered_to_a_target_whether_or_not_it_asks_for_an_eldritch_implicit():
    """`offers_for` (#886 lifted the gate of #835, #919): every Eldritch kind the boots take is offered with the wish and without it, as tools."""
    for goal in (GOAL, Goal(GOAL.leaves)):
        kinds = {offer.kind for offer in offers_for(DATA, goal, BOOTS, START).offers}
        assert ELDRITCH_KINDS <= kinds, ELDRITCH_KINDS - kinds


def test_an_addition_that_reads_the_implicits_takes_every_member_where_a_family_has_mods_on_both_sides():
    """The guard of `Pattern.mode_of` (#835): a held family of the other side takes its partner's weight out of a draw of the dominant side,
    so the Eldritch Exalted Orb's corners do not hold there. No armour pool of 3.29.3.3 has such a family; the guard is set by hand."""
    ab = abstraction()
    pattern = Pattern(ab, None, [action for action, _ in OFFERED.values()])
    key = pattern.key(ab.compress(START))
    assert pattern.mode_of(ORBS["Eldritch Exalted"][0], key) is Mode.EXTREMES
    pattern._partners[key.flags.influences] = True
    assert pattern.mode_of(ORBS["Eldritch Exalted"][0], key) is Mode.ALL


def _wish(family: str, first: int = 1, min_grade: int | None = None) -> ImplicitWanted:
    return ImplicitWanted(frozenset(eldritch_id(family, grade) for grade in range(first, 7)), min_grade)


def test_a_target_no_offered_action_can_meet_is_told_before_the_search():
    """`eldritch_unreachable` (#835): one implicit per side, an Ember gives its own grade, and a Conflict with both sides held reaches the rest."""
    leaves = GOAL.leaves
    embers = [(action, "eldritch-implicit-currency") for action, _ in EMBERS.values()]
    conflict = [(ORBS["Conflict"][0], "orb-of-conflict")]
    assert eldritch_unreachable(DATA, Goal(leaves, (_wish("AvoidShock"),)), START, embers) is None
    assert eldritch_unreachable(DATA, Goal(leaves, (_wish("AvoidShock"), _wish("ChanceToShock"))), START, embers) is None
    assert eldritch_unreachable(DATA, Goal(leaves, (_wish("AvoidShock"), _wish("FireMax"))), START, embers)  # two on one side
    # one implicit passes several wishes that overlap (checker round 2): two wishes on one family, and a third on the other side
    overlapping = (_wish("AvoidShock"), _wish("AvoidShock", 1, 1), _wish("ChanceToShock"))
    assert eldritch_unreachable(DATA, Goal(leaves, overlapping), START, embers) is None
    assert eldritch_unreachable(DATA, Goal(leaves, (_wish("AvoidShock"), _wish("AvoidShock", 1, 2))), START, embers)  # grade 2: no Ember
    assert eldritch_unreachable(DATA, Goal(leaves, (_wish("AvoidShock"), _wish("AvoidShock", 1, 2))), START, embers + conflict) is None
    assert eldritch_unreachable(DATA, Goal(leaves, (_wish("AvoidShock", 3),)), START, embers)  # grade 3: no Ember of it
    assert eldritch_unreachable(DATA, Goal(leaves, (_wish("AvoidShock", 3),)), START, embers + conflict) is None
    assert eldritch_unreachable(DATA, Goal(leaves, (_wish("AvoidShock", 3),)), boots(roll(FIRE), implicits=(exarch(1),)), []) is None  # held


def test_a_start_item_that_takes_no_ember_is_told_before_the_search():
    """The refusals of `_implicits_made` (checker round 3): an Ember refused at the start item (influenced, corrupted, a class it does not take)
    gives nothing, and no later item takes it either, so a wish with Embers offered is refused before the search."""
    from eldritch_support import SHAPER, amulet

    embers = [(action, "eldritch-implicit-currency") for action, _ in EMBERS.values()]
    goal = Goal(GOAL.leaves, (_wish("AvoidShock"),))
    assert eldritch_unreachable(DATA, goal, START, embers) is None  # the same wish on plain boots
    assert eldritch_unreachable(DATA, goal, boots(roll(FIRE), influences=SHAPER), embers)
    assert eldritch_unreachable(DATA, goal, boots(roll(FIRE), corrupted=True), embers)
    assert eldritch_unreachable(DATA, goal, amulet(), embers)
