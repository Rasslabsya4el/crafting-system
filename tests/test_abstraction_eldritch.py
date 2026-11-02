"""The Eldritch implicit pair in the compressed state: Embers, Ichors, the three Eldritch orbs and the Orb of Conflict (ticket #152, ADR-0025, ADR-0019).

The state keeps the grade of each side and what the implicit gives the goal (ticket #142); dominance is derived from the two grades, so the
actions that act on the dominant side (Chaos, Exalted, Annulment) are the generic kernel over an item rebuilt with the grades the state holds.
What #152 adds is checked here on the hand-made boots, gloves, helmets and body armours of `eldritch_support`:

* layer 1 (ADR-0019): for every concrete item that the five actions reach from several starts, the kernel of the item's state equals the finished
  items of the action on the item, compressed one by one and added up exactly (`abstraction_b2_support.check_layer_1`), for goals that want an
  Eldritch implicit of one line at some grades, of both sides, or none;
* dominance: Chaos, Exalted and Annulment act on the explicit side the dominant Eldritch side names, and are refused where nothing is dominant;
* a Conflict moves an implicit inside its line, so a state keeps the line when a requirement names a mod of it (`ImplicitSide.line`), and only then;
* the pair is linked to the explicit mods by dominance alone: the full product of explicit and implicit states is solved, and so is the same model
  assembled from an explicit kernel that sees only the dominance and an implicit kernel that sees no explicit mod; the two agree on every state.
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_b2_support import check_layer_1, closure
from abstraction_support import real_game_data
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
    LEVEL,
    LIFE,
    LOCK_SUFFIXES,
    NO_ATTACK,
    SPEED,
    build,
    boots,
    eater,
    eldritch_id,
    exarch,
    roll,
)

from crafting_system.abstraction import Abstraction, CompressedState, Goal, ImplicitSide, ImplicitWanted, Status, Wanted, integer_weights
from crafting_system.actions import (
    ActionError,
    EldritchAnnulmentOrb,
    EldritchChaosOrb,
    EldritchExaltedOrb,
    EldritchImplicitCurrency,
    NotApplicableError,
    OrbOfConflict,
)
from crafting_system.items import EldritchSide, Rarity, Side, eldritch_grade, eldritch_side
from crafting_system.solver import Action as SolverAction
from crafting_system.solver import Outcome, solve

ABSENT, BELOW, PASSING = Status.ABSENT, Status.BELOW, Status.PASSING
EXARCH_SIDE, EATER_SIDE = EldritchSide.EXARCH, EldritchSide.EATER
LIFE_LEAF, FIRE_LEAF = Wanted(frozenset({LIFE})), Wanted(frozenset({FIRE}))


def grades(family: str, first: int = 1) -> frozenset[str]:
    """The ids of one Eldritch line from grade `first` up."""
    return frozenset(eldritch_id(family, grade) for grade in range(first, 7))


# a goal that wants the AvoidShock line at grade 3 or more, one that wants a line on each side, and one that wants no implicit at all
GOAL_LINE = Goal((LIFE_LEAF, FIRE_LEAF), (ImplicitWanted(grades("AvoidShock", 3)),))
GOAL_BOTH = Goal((LIFE_LEAF,), (ImplicitWanted(grades("AvoidShock", 2), min_grade=3), ImplicitWanted(grades("ChanceToShock", 3))))
GOAL_PLAIN = Goal((LIFE_LEAF, FIRE_LEAF))

EMBERS = tuple(EldritchImplicitCurrency(side, grade) for side in EldritchSide for grade in (1, 2, 3))
ORBS = (EldritchChaosOrb(), EldritchExaltedOrb(), EldritchAnnulmentOrb(), OrbOfConflict())
ACTIONS = (*EMBERS, *ORBS)


def ability(goal: Goal, actions=ACTIONS, base: str = BOOTS, **options) -> Abstraction:
    return Abstraction(DATA, goal, base, LEVEL, actions, **options)


def starts(*, metamods: bool) -> dict:
    found = {
        "both": boots(roll(LIFE), roll(COLD), roll(FIRE), implicits=(exarch(2), eater(1))),
        "exarch_only": boots(roll(LIFE), roll(ARMOUR), roll(FIRE), roll(COLD), roll(SPEED), implicits=(exarch(2),)),
        "equal": boots(roll(LIFE), roll(FIRE), implicits=(exarch(2), eater(2))),
        "eater_fractured": boots(roll(LIFE), roll(ARMOUR), roll(FIRE, fractured=True), roll(COLD), implicits=(eater(3),)),
        "magic": boots(roll(LIFE), roll(COLD), implicits=(exarch(1),), rarity=Rarity.MAGIC),
        "no_implicit": boots(roll(LIFE), roll(ARMOUR), roll(FIRE), roll(COLD)),
        "pinnacle_line": boots(roll(LIFE), roll(FIRE), implicits=(exarch(2, variant="PinnaclePresence"), eater(1, "Leech"))),
    }
    if metamods:
        found["lock_on_suffixes"] = boots(roll(LIFE), roll(ARMOUR), roll(COLD), roll(LOCK_SUFFIXES, crafted=True), implicits=(exarch(1),))
        found["attack_blocked"] = boots(roll(LIFE), roll(COLD), roll(NO_ATTACK, crafted=True), implicits=(eater(2), exarch(1)))
    return found


# --- layer 1 -------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("goal", "metamods"),
    [(GOAL_LINE, False), (GOAL_BOTH, False), (GOAL_PLAIN, False), (GOAL_LINE, True)],
    ids=["line", "both_sides", "no_implicit_wanted", "line_with_metamods"],
)
def test_layer_1_for_every_action_that_touches_the_pair(goal, metamods):
    found = ability(goal, metamods=metamods)
    items = closure(DATA, starts(metamods=metamods).values(), ACTIONS, limit=260)
    applied = {action: 0 for action in ACTIONS}
    for item in items:
        for action in ACTIONS:
            applied[action] += check_layer_1(found, DATA, item, action)
    assert all(applied.values()), [action for action, count in applied.items() if not count]


@pytest.mark.parametrize("action", ORBS[:3], ids=["chaos", "exalted", "annulment"])
@pytest.mark.parametrize("base", [BODY, BOOTS])
def test_layer_1_on_other_classes_and_with_the_pair_unseen_by_the_goal(action, base):
    """The orbs on a body armour too, where the pool of the Eldritch implicits is another one; the goal names nothing of the pair."""
    found = ability(GOAL_PLAIN, (*EMBERS, action), base)
    start = build(base, roll(LIFE), roll(FIRE), implicits=(exarch(2, "Armour"), eater(1, "Leech"))) if base == BODY else boots(
        roll(LIFE), roll(FIRE), implicits=(exarch(2), eater(1))
    )
    for item in closure(DATA, [start], (*EMBERS, action), limit=80):
        check_layer_1(found, DATA, item, action)


# --- dominance -----------------------------------------------------------------------------------------------------------


def state_of(found: Abstraction, *mods, implicits=(), **fields) -> CompressedState:
    return found.compress(boots(*mods, implicits=implicits, **fields))


def sides_changed(kernel, start: CompressedState) -> set[Side]:
    """The explicit sides whose slots differ from the start's in some outcome."""
    changed = set()
    for outcome in kernel:
        for side in Side:
            if sorted((s.key for s in outcome.slots if s.side is side)) != sorted(s.key for s in start.slots if s.side is side):
                changed.add(side)
    return changed


@pytest.mark.parametrize(
    ("implicits", "side"),
    [((exarch(3), eater(1)), Side.PREFIX), ((exarch(1), eater(3)), Side.SUFFIX), ((exarch(1),), Side.PREFIX), ((eater(2),), Side.SUFFIX)],
    ids=["exarch_higher", "eater_higher", "exarch_alone", "eater_alone"],
)
def test_chaos_exalted_and_annulment_act_on_the_dominant_side_only(implicits, side):
    found = ability(GOAL_PLAIN)
    start = state_of(found, roll(LIFE), roll(COLD), roll(FIRE), implicits=implicits)
    for action in ORBS[:3]:
        assert sides_changed(found.kernel(start, action), start) == {side}, action


@pytest.mark.parametrize("implicits", [(), (exarch(2), eater(2)), (exarch(1), eater(1))], ids=["none", "equal_2", "equal_1"])
def test_nothing_dominant_refuses_the_three_orbs_in_the_kernel_as_in_the_action(implicits):
    found = ability(GOAL_PLAIN)
    item = boots(roll(LIFE), roll(FIRE), implicits=implicits)
    for action in ORBS[:3]:
        with pytest.raises(NotApplicableError):
            action.outcomes(DATA, item)
        with pytest.raises(NotApplicableError):
            found.kernel(found.compress(item), action)


def test_an_ember_can_make_a_side_dominant_and_the_next_orb_follows():
    """An Ember on an item with nothing dominant creates the dominance that the route's Exalted Orb then reads from the state."""
    found = ability(GOAL_PLAIN)
    start = state_of(found, roll(LIFE), roll(FIRE), implicits=(exarch(1), eater(1)))
    raised = found.kernel(start, EldritchImplicitCurrency(EATER_SIDE, 2))
    assert {state.implicits[1].grade for state in raised} == {2}
    for state in raised:
        assert sides_changed(found.kernel(state, EldritchExaltedOrb()), state) == {Side.SUFFIX}
    assert dict(found.kernel(state_of(found, roll(LIFE), implicits=(exarch(1),)), EldritchImplicitCurrency(EATER_SIDE, 1)))  # equal grades: no orb after it


# --- the line of an implicit ---------------------------------------------------------------------------------------------


def test_a_conflict_raises_a_line_the_goal_names_at_a_higher_grade():
    """AvoidShock 2 gives the goal nothing, AvoidShock 3 everything: a raised Conflict must know which line the grade 2 implicit was of."""
    found = ability(GOAL_LINE)
    avoid, fire_max = state_of(found, roll(LIFE), implicits=(exarch(2), eater(1))), state_of(found, roll(LIFE), implicits=(exarch(2, "FireMax"), eater(1)))
    assert avoid.implicits[0] == ImplicitSide(2, (ABSENT,), eldritch_id("AvoidShock", 0)[:-1])
    assert fire_max.implicits[0] == ImplicitSide(2, (ABSENT,))
    raised = {state.implicits[0] for state in found.kernel(avoid, OrbOfConflict())}
    assert ImplicitSide(3, (PASSING,), eldritch_id("AvoidShock", 0)[:-1]) in raised
    assert {state.implicits[0].contribution for state in found.kernel(fire_max, OrbOfConflict())} == {(ABSENT,)}


def test_the_line_is_kept_only_for_a_named_line_and_only_when_an_action_moves_it():
    with_conflict, without = ability(GOAL_LINE), ability(GOAL_LINE, (*EMBERS, *ORBS[:3]))
    item = boots(roll(LIFE), implicits=(exarch(2), eater(1, "Leech")))
    assert with_conflict.compress(item).implicits[0].line == eldritch_id("AvoidShock", 1)[:-1]
    assert with_conflict.compress(item).implicits[1].line == ""  # Leech is no line the goal names
    assert without.compress(item).implicits == (ImplicitSide(2, (ABSENT,)), ImplicitSide(1, (ABSENT,)))


def test_a_state_without_a_line_prints_as_it_did_before_the_line_existed():
    assert repr(ImplicitSide(2, (PASSING,))) == "ImplicitSide(grade=2, contribution=(<Status.PASSING: 2>,))"
    assert repr(ImplicitSide(2, (PASSING,), "x")).endswith(", line='x')")
    assert ImplicitSide(2, (PASSING,)) != ImplicitSide(2, (PASSING,), "x")


def test_the_representative_of_an_unnamed_line_is_of_an_unnamed_line():
    """Rebuilding a side whose line nobody names must not pick a mod of a named line (whose Conflict would move it to the goal)."""
    found = ability(GOAL_LINE)
    state = found.compress(boots(roll(LIFE), implicits=(exarch(2, "FireMax"), eater(1))))
    item, _ = found._item_of(state, False)
    assert len(item.implicits) == 2
    assert all(not entry.mod_id.startswith("AvoidShockEldritchImplicit") or "Presence" in entry.mod_id for entry in item.implicits)
    assert found.compress(item) == state


def test_every_eldritch_line_of_the_real_data_has_all_six_grades():
    """A Conflict moves a line up and down, and the state stands a side of an unnamed line for any mod of it: a line with a grade missing would make the two differ."""
    ladders: dict[str, set[int]] = {}
    for mod in real_game_data().mods.values():
        if eldritch_side(mod) is not None:
            ladders.setdefault(mod.id[:-1], set()).add(eldritch_grade(mod))
    assert ladders
    assert {line: grades for line, grades in ladders.items() if grades != {1, 2, 3, 4, 5, 6}} == {}


# --- the pair is linked to the explicit mods by dominance ------------------------------------------------------------------

PRICES = {  # chaos
    EldritchImplicitCurrency(EXARCH_SIDE, 1): 2, EldritchImplicitCurrency(EXARCH_SIDE, 2): 6,
    EldritchImplicitCurrency(EATER_SIDE, 1): 2, EldritchImplicitCurrency(EATER_SIDE, 2): 6,
    EldritchChaosOrb(): 5, EldritchExaltedOrb(): 12, EldritchAnnulmentOrb(): 8, OrbOfConflict(): 15,
}
SOLVED = tuple(PRICES)
GOAL_SOLVE = Goal((LIFE_LEAF, FIRE_LEAF), (ImplicitWanted(grades("AvoidShock", 3)),))
SMALL = dataclasses.replace(DATA, mods={mod_id: mod for mod_id, mod in DATA.mods.items() if mod_id not in (EVASION, ATTACK, SPEED, CASTER)})
# two prefix and two suffix families on the boots: the solved graph is the explicit subsets times the pairs, a thousand states and not fifteen thousand


def implicit_free(state: CompressedState) -> CompressedState:
    return dataclasses.replace(state, implicits=())


def representative_pair(found: Abstraction, dominant: EldritchSide | None) -> tuple[ImplicitSide, ImplicitSide]:
    """The smallest pair that has this dominance: nothing, or a Lesser implicit on the dominant side and none on the other."""
    none = ImplicitSide(0, (ABSENT,))
    if dominant is None:
        return none, none
    lesser = ImplicitSide(1, (ABSENT,))
    return (lesser, none) if dominant is EXARCH_SIDE else (none, lesser)


def dominance(pair: tuple[ImplicitSide, ImplicitSide]) -> EldritchSide | None:
    from crafting_system.items import dominant_side

    return dominant_side(pair[0].grade, pair[1].grade)


class FullProduct:
    """The model of the solver over the states of the abstraction, the pair and the mods together."""

    def __init__(self, found: Abstraction):
        self.found = found

    def is_goal(self, state: CompressedState) -> bool:
        return self.found.is_goal(state)

    def actions(self, state: CompressedState) -> list[SolverAction]:
        result = []
        for action, price in PRICES.items():
            try:
                weights = integer_weights(self.found.kernel(state, action))
            except ActionError:
                continue
            result.append(SolverAction(action, price, tuple(Outcome(next_state, weight) for next_state, weight in weights.items())))
        return result


class LinkedByDominance:
    """The same model assembled from two kernels that know nothing of each other but the dominance.

    A state is `(mods, pair)`. The Chaos, Exalted and Annulment Orbs are run on the mods with the smallest pair of the dominance of the pair
    (`representative_pair`), so the pair they see is its dominance and nothing else; the Embers, Ichors and Conflict are run on the pair with
    one fixed explicit part, so they see no explicit mod. The outcome of each is put together again from the part it changed and the part it did not.
    """

    def __init__(self, found: Abstraction, fixed_mods: CompressedState):
        self.found, self.fixed = found, fixed_mods

    def is_goal(self, state) -> bool:
        mods, pair = state
        return self.found.is_goal(dataclasses.replace(mods, implicits=pair))

    def actions(self, state) -> list[SolverAction]:
        mods, pair = state
        result = []
        for action, price in PRICES.items():
            if isinstance(action, EldritchImplicitCurrency | OrbOfConflict):
                probe = dataclasses.replace(self.fixed, implicits=pair)
                put_together = lambda successor: (mods, successor.implicits)  # noqa: E731
                check = lambda successor: successor.slots == self.fixed.slots and successor.status == self.fixed.status  # noqa: E731
            else:
                held = representative_pair(self.found, dominance(pair))
                probe = dataclasses.replace(mods, implicits=held)
                put_together = lambda successor: (implicit_free(successor), pair)  # noqa: E731
                check = lambda successor: successor.implicits == held  # noqa: E731
            try:
                weights = integer_weights(self.found.kernel(probe, action))
            except ActionError:
                continue
            assert all(check(successor) for successor in weights), action
            merged: dict = {}
            for successor, weight in weights.items():
                key = put_together(successor)
                merged[key] = merged.get(key, 0) + weight
            result.append(SolverAction(action, price, tuple(Outcome(next_state, weight) for next_state, weight in merged.items())))
        return result


def test_solving_the_full_product_equals_solving_it_linked_by_dominance():
    found = Abstraction(SMALL, GOAL_SOLVE, BOOTS, LEVEL, SOLVED)
    start = found.compress(build(BOOTS, roll(ARMOUR), roll(COLD)))
    product = solve(FullProduct(found), [start])
    linked = solve(LinkedByDominance(found, implicit_free(start)), [(implicit_free(start), start.implicits)])
    assert len(product.values) == len(linked.values) > 200
    assert {dataclasses.replace(mods, implicits=pair) for mods, pair in linked.values} == set(product.values)
    for (mods, pair), value in linked.values.items():
        assert value == pytest.approx(product.values[dataclasses.replace(mods, implicits=pair)], rel=1e-9, abs=1e-12), (mods, pair)
    assert 0 < product.values[start] < float("inf")
    assert any(isinstance(action.label, EldritchChaosOrb) for action in product.policy.values())  # the dominance link is used by the policy
