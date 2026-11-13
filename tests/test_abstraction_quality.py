"""Quality as the last requirement of a goal, and the catalysts that are offered only when everything else passes (ticket #158, ADR-0029, ADR-0027).

A goal may want a quality (`QualityWanted`: a catalyst type at a percent, or the plain quality of a weapon or armour). The state then holds the
quality as the item stores it, and the goal is met when every other requirement is and the quality is too. Catalysts change no odds, so an action
declared as a quality action (`Adds.only_quality`) is an action of a state only when every other requirement passes there and the quality does not
yet (`Abstraction.quality_offer_pruned`; `planner._prune.chosen_offers` applies it). Checked here:

* the goal: the quality is a requirement of its own, of the type asked, met at the percent asked or more; the plain quality has no type;
* **catalysts are not offered while another requirement fails and are offered once only the quality fails** (the offer, by the prune of the
  planner and by the abstraction), also for an implicit that is missing, and never when the quality is met or the goal wants none;
* layer 1 (ADR-0019) for the catalysts, against the finished items of the action, over starts that hold a quality of
  the type, of another type, 20% and none;
* the pruning is exact: the solver's value of the same small economy is the same with and without it, and from a state that meets everything but the
  quality it is the price of the expected number of catalysts (`expected_catalysts_for`);
* the exception: a goal that takes a corrupted item, with an enabled action that corrupts and rerolls the mods itself, keeps the catalysts on
  every state (a corrupted item takes none, so they must go on first).
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_b2_support import check_layer_1, closure
from abstraction_pool import LIFE_1, RESIST_2
from item_state_support import AMULET, ITEM_DATA, LEVEL, amulet, intrinsic, roll
from items_support import BODY

from crafting_system.abstraction import Abstraction, Goal, ImplicitWanted, QualityWanted, Status, Wanted, integer_weights
from crafting_system.actions import ActionError, Adds, ApplyCatalyst, ChaosOrb, expected_catalysts_for
from crafting_system.planner._offers import Offer, PricedOffer, offer_of
from crafting_system.planner._prune import chosen_offers
from crafting_system.items import CatalystType, ImplicitMod, Item, PlainQuality, Quality, Rarity
from crafting_system.solver import Action as SolverAction
from crafting_system.solver import Outcome, solve

INTRINSIC, TEMPERING = CatalystType.INTRINSIC, CatalystType.TEMPERING
CATALYST = ApplyCatalyst(INTRINSIC)
RESIST_LEAF = Wanted(frozenset({RESIST_2}))
QUALITY_20 = QualityWanted(INTRINSIC, 20)


def goal_of(quality: QualityWanted | None = QUALITY_20, *leaves: Wanted, **fields) -> Goal:
    return Goal(leaves or (RESIST_LEAF,), quality=quality, **fields)


def ability(goal: Goal | None = None, actions=(CATALYST,), base: str = AMULET) -> Abstraction:
    return Abstraction(ITEM_DATA, goal or goal_of(), base, LEVEL, actions)


def priced(action, label: str, cost: float) -> PricedOffer:
    return PricedOffer(offer_of(action, label, ITEM_DATA), cost, ())


# --- the goal ---------------------------------------------------------------------------------------------------


def test_quality_is_a_requirement_of_its_own_of_the_type_asked_met_at_the_percent_or_more():
    found = ability()
    held = amulet(roll(RESIST_2))
    assert found.tracks_quality
    assert not found.is_goal(found.compress(held))  # the mod is there, the quality is not
    assert not found.is_goal(found.compress(held.changed(ITEM_DATA, quality=intrinsic(19))))
    assert found.is_goal(found.compress(held.changed(ITEM_DATA, quality=intrinsic(20))))
    assert not found.is_goal(found.compress(held.changed(ITEM_DATA, quality=Quality(TEMPERING, 20))))  # another type is not it
    assert not found.is_goal(found.compress(amulet(quality=intrinsic(20))))  # the quality does not make up for a mod
    assert found.meets_all_but_quality(found.compress(held)) and not found.quality_is_met(found.compress(held))
    assert found.meets_requirements(found.compress(held.changed(ITEM_DATA, quality=intrinsic(20))))
    assert not found.meets_requirements(found.compress(held))


def test_a_goal_without_a_quality_is_met_whatever_the_quality():
    found = ability(goal_of(None))
    assert found.quality_is_met(found.compress(amulet())) and found.is_goal(found.compress(amulet(roll(RESIST_2))))
    assert found.is_goal(found.compress(amulet(roll(RESIST_2), quality=Quality(TEMPERING, 5))))


def test_the_plain_quality_of_a_weapon_or_armour_has_no_type():
    wanted = QualityWanted(None, 20)
    assert wanted.is_met_by(PlainQuality(20)) and wanted.is_met_by(PlainQuality(25)) and not wanted.is_met_by(PlainQuality(19))
    assert not wanted.is_met_by(None) and not wanted.is_met_by(intrinsic(20))  # a catalyst quality is not the plain one
    assert not QUALITY_20.is_met_by(PlainQuality(20))
    found = ability(Goal((), quality=wanted), (), BODY)
    body = Item.build(ITEM_DATA, base_id=BODY, item_level=LEVEL, rarity=Rarity.RARE, quality=PlainQuality(24))
    assert found.tracks_quality and found.compress(body).quality == PlainQuality(24)
    assert found.is_goal(found.compress(body)) and not found.is_goal(found.compress(body.changed(ITEM_DATA, quality=PlainQuality(10))))
    assert found.compress(body).order_key  # a plain quality has no type, and a state still sorts


def test_a_goal_built_from_a_target_reads_its_implicits_and_its_quality():
    from crafting_system.targets import ImplicitRequirement, QualityRequirement

    @dataclasses.dataclass
    class Target:
        requirements: tuple = ()
        implicits: tuple = ()
        quality: object = None

    wish = ImplicitRequirement(None, "x", frozenset({"A", "B"}), min_grade=2, min_roll=(5, None))
    corrupted = ImplicitRequirement(None, "y", frozenset({"C"}), corrupted=True)
    goal = Goal.from_target(Target(implicits=(wish, corrupted), quality=QualityRequirement(INTRINSIC, 15)))
    assert goal.implicits == (ImplicitWanted(frozenset({"A", "B"}), 2, (5, None)),)  # a corrupted implicit is decided by the action that corrupts
    assert goal.quality == QualityWanted(INTRINSIC, 15)
    bare = Goal.from_target(Target())
    assert bare.implicits == () and bare.quality is None


# --- what is offered -----------------------------------------------------------------------------------------------------


def test_catalysts_are_not_offered_while_another_requirement_fails_and_are_offered_once_only_quality_fails():
    found = ability(actions=[CATALYST, ChaosOrb()])
    failing = found.compress(amulet(roll(LIFE_1)))  # the mod it wants is missing
    only_quality = found.compress(amulet(roll(RESIST_2)))
    done = found.compress(amulet(roll(RESIST_2), quality=intrinsic(20)))
    halfway = found.compress(amulet(roll(RESIST_2), quality=intrinsic(10)))
    assert found.quality_offer_pruned(failing, CATALYST)
    assert not found.quality_offer_pruned(only_quality, CATALYST)
    assert not found.quality_offer_pruned(halfway, CATALYST)  # some quality is not all of it
    assert found.quality_offer_pruned(done, CATALYST)  # nothing left to do
    assert not found.quality_offer_pruned(failing, ChaosOrb())  # only an action that sets the quality and nothing else is held back
    # the planner's choice of offers at a state, by the same rule
    offers = [priced(ChaosOrb(), "Chaos Orb", 1), priced(CATALYST, "Intrinsic Catalyst", 3)]
    labels = lambda state, **options: [offer.label for offer in chosen_offers(found, offers, state, failing, **options)]  # noqa: E731
    assert labels(failing) == ["Chaos Orb"]
    assert labels(only_quality) == ["Chaos Orb", "Intrinsic Catalyst"]
    assert labels(halfway) == ["Chaos Orb", "Intrinsic Catalyst"]
    assert labels(failing, prune_quality=False) == ["Chaos Orb", "Intrinsic Catalyst"]  # the reference the values are compared with


def test_k13_a_catalyst_left_out_of_a_state_is_written_so_that_the_answer_can_say_it():
    from crafting_system.planner._limits import pruning_limits

    found = ability(actions=[CATALYST, ChaosOrb()])
    failing = found.compress(amulet(roll(LIFE_1)))
    only_quality = found.compress(amulet(roll(RESIST_2)))
    offers = [priced(ChaosOrb(), "Chaos Orb", 1), priced(CATALYST, "Intrinsic Catalyst", 3)]

    chosen_offers(found, offers, only_quality, failing)  # the catalyst is offered: nothing is left out
    assert found.prunings.labels("quality") == () and pruning_limits(found.prunings) == ()
    chosen_offers(found, offers, failing, failing, prune_quality=False)  # the reference run prunes nothing
    assert found.prunings.labels("quality") == ()
    chosen_offers(found, offers, failing, failing)

    (limit,) = pruning_limits(found.prunings)
    assert limit.labels == ("Intrinsic Catalyst",) and "quality changes no odds" in limit.why
    assert limit.guarantee == "The plan is the cheapest among the methods offered. Offering them in the other states would change no cost."


def test_a_missing_implicit_or_one_whose_roll_misses_holds_the_catalysts_back_too():
    goal = goal_of(QUALITY_20, RESIST_LEAF, implicits=())
    goal = dataclasses.replace(goal, implicits=(ImplicitWanted(frozenset({"AvoidShockEldritchImplicit2"})),))
    found = ability(goal)
    mod_only = found.compress(amulet(roll(RESIST_2)))
    assert found.tracks_implicits and found.quality_offer_pruned(mod_only, CATALYST)  # the implicit wanted is not there
    elsewhere = found.compress(amulet(roll(RESIST_2), implicits=(ImplicitMod("AvoidShockEldritchImplicit2", 2, (36,)),)))
    assert not found.quality_offer_pruned(elsewhere, CATALYST)


def test_a_goal_that_wants_no_quality_never_offers_a_catalyst():
    found = ability(goal_of(None))
    for held in (amulet(), amulet(roll(RESIST_2)), amulet(roll(RESIST_2), quality=intrinsic(5))):
        assert found.quality_offer_pruned(found.compress(held), CATALYST)


def test_a_goal_that_takes_a_corrupted_item_keeps_the_catalysts_while_an_action_corrupts_and_rerolls_the_mods():
    @dataclasses.dataclass(frozen=True)
    class Reroller(ChaosOrb):  # declared as a corrupting reroll (a Bloodstained resonator): nothing is kept
        def adds(self, data=None, item=None):
            return Adds.corrupting()

    @dataclasses.dataclass(frozen=True)
    class Brick(ChaosOrb):  # declared as a corrupting craft that keeps the mods (a Vaal Orb)
        def adds(self, data=None, item=None):
            return Adds.corrupting(keeps_mods=True)

    asking = goal_of(QUALITY_20, asks_corrupted=True)
    allowing = goal_of(QUALITY_20, allow_corrupted=True)
    failing = lambda found: found.compress(amulet(roll(LIFE_1)))  # noqa: E731
    cases = [
        (asking, (CATALYST,), True),  # no action corrupts: the catalysts wait
        (asking, (CATALYST, Brick()), True),  # it keeps the mods, and is itself offered only when everything else passes
        (asking, (CATALYST, Reroller()), False),  # it rerolls the mods, so the catalysts go on before it, on a state that fails the mods
        (allowing, (CATALYST, Brick()), False),  # its brick can end in the goal, so it is not held to the mods either
        (goal_of(QUALITY_20), (CATALYST,), True),
    ]
    for goal, actions, pruned in cases:
        found = ability(goal, actions)
        assert found.quality_offer_pruned(failing(found), CATALYST) is pruned, (goal, actions)


# --- layer 1 -----------------------------------------------------------------------------------------------------------------


def test_layer_1_for_the_catalysts():
    found = ability(actions=[CATALYST, ApplyCatalyst(TEMPERING)])
    starts = [
        amulet(roll(RESIST_2)),
        amulet(roll(LIFE_1), quality=intrinsic(5)),
        amulet(roll(RESIST_2), quality=intrinsic(10)),
        amulet(roll(RESIST_2), quality=intrinsic(20)),  # a catalyst is refused at 20% of its type
        amulet(roll(RESIST_2), quality=Quality(TEMPERING, 10)),  # another type is replaced
    ]
    actions = [CATALYST, ApplyCatalyst(TEMPERING)]
    applied = {action: 0 for action in actions}
    for item in closure(ITEM_DATA, starts, actions, limit=60):
        for action in actions:
            applied[action] += check_layer_1(found, ITEM_DATA, item, action)
    assert all(applied.values())


def test_the_kernel_of_a_catalyst_is_the_gain_law_and_the_quality_stays_a_requirement_until_it_is_met():
    found = ability()
    start = found.compress(amulet(roll(RESIST_2), quality=intrinsic(18)))
    kernel = found.kernel(start, CATALYST)
    assert {state.quality: chance for state, chance in kernel.items()} == {
        Quality(INTRINSIC, 19): kernel[dataclasses.replace(start, quality=intrinsic(19))],
        Quality(INTRINSIC, 20): kernel[dataclasses.replace(start, quality=intrinsic(20))],
    }  # one catalyst at item level 84 gives 1 point or 2: 18 reaches 19 or 20
    assert sum(kernel.values()) == 1 and all(found.meets_all_but_quality(state) for state in kernel)
    assert [found.is_goal(state) for state in kernel] == [state.quality.percent == 20 for state in kernel]


# --- the pruning is exact; the catalysts are priced as any action ---------------------------------------------------------------


class Economy:
    """A Chaos Orb and an Intrinsic Catalyst, with or without the prune, as the solver sees them."""

    def __init__(self, found: Abstraction, *, pruned: bool):
        self.found, self.pruned = found, pruned
        self.prices = {ChaosOrb(): 1.0, CATALYST: 3.0}

    def is_goal(self, state) -> bool:
        return self.found.is_goal(state)

    def actions(self, state) -> list[SolverAction]:
        result = []
        for action, price in self.prices.items():
            if self.pruned and self.found.quality_offer_pruned(state, action):
                continue
            try:
                weights = integer_weights(self.found.kernel(state, action))
            except ActionError:
                continue
            result.append(SolverAction(action, price, tuple(Outcome(next_state, weight) for next_state, weight in weights.items())))
        return result


def test_the_prune_changes_no_value_and_the_catalysts_cost_the_expected_number_of_them():
    found = ability(actions=[CATALYST, ChaosOrb()])
    held = amulet(roll(RESIST_2))
    start = found.compress(amulet())
    ready = found.compress(held)
    pruned = solve(Economy(found, pruned=True), [start, ready])
    unpruned = solve(Economy(found, pruned=False), [start, ready])
    chance = sum(chance for state, chance in found.kernel(start, ChaosOrb()).items() if found.meets_all_but_quality(state))
    assert 0 < chance < 1
    expected = float(expected_catalysts_for(held, INTRINSIC, 20))
    assert 13.3 < expected < 13.4  # 13.35 at item level 84 (ADR-0029)
    assert pruned.values[ready] == pytest.approx(3.0 * expected, rel=1e-9)  # a state that needs the quality only: the price of the expected catalysts
    assert pruned.values[start] == pytest.approx(1.0 / float(chance) + 3.0 * expected, rel=1e-9)  # rerolls until the mod is there, then the catalysts
    assert unpruned.values[start] == pytest.approx(pruned.values[start], rel=1e-9)
    assert unpruned.values[ready] == pytest.approx(pruned.values[ready], rel=1e-9)
    assert len(pruned.values) <= len(unpruned.values)
    assert all(not isinstance(action.label, ApplyCatalyst) or found.meets_all_but_quality(state) for state, action in pruned.policy.items())


def test_the_quality_a_start_item_holds_counts_toward_the_catalysts_it_needs():
    found = ability(actions=[CATALYST])
    ready = found.compress(amulet(roll(RESIST_2), quality=intrinsic(10)))
    solved = solve(Economy(found, pruned=True), [ready])
    assert solved.values[ready] == pytest.approx(3.0 * float(expected_catalysts_for(amulet(quality=intrinsic(10)), INTRINSIC, 20)), rel=1e-9)
    assert solved.values[ready] < 3.0 * float(expected_catalysts_for(amulet(), INTRINSIC, 20))


def test_only_a_state_that_keeps_the_quality_can_meet_it():
    plain = Abstraction(ITEM_DATA, goal_of(), AMULET, LEVEL, [ChaosOrb()])  # a goal that wants a quality keeps it even if no action reads it
    assert plain.tracks_quality
    start = plain.compress(amulet(roll(RESIST_2), quality=intrinsic(20)))
    assert plain.is_goal(start)
    after = plain.kernel(start, ChaosOrb())
    assert {state.quality for state in after} == {Quality(INTRINSIC, 20)}  # a reroll leaves the quality on the item
    assert Fraction(1) == sum(after.values())
