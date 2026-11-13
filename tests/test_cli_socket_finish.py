"""The socket finish attached to the goal states of a plan (ticket #231, B6 S5; ADR-0045).

`make_plan` no longer refuses a target that names sockets: it plans the mods as for the same target without sockets, solves the finish on its own from
the start item's sockets and adds its value to every goal state (`Plan.finish_value`, `Plan.value_of`, `Plan.total_mean`). The answer says the finish
in one limit until it is a sub-route of its own (ticket #233). On the Simple Robe of the target fixtures, with the socket orbs priced by hand.
"""

import dataclasses
import datetime

import pytest
from sockets_colour_support import CHROMATIC_ID
from sockets_support import FUSING_ORB_ID, JEWELLERS_ORB_ID
from targets_sockets_support import DATA as TARGET_DATA
from targets_sockets_support import parse

from crafting_system.abstraction import FinishStep, SocketWanted, solve_finish
from crafting_system.actions.burn import burns_at
from crafting_system.actions.contract import BurnKeeps
from crafting_system.actions.socket_colours import ChromaticOrb
from crafting_system.actions.socket_orbs import JewellersOrb, OrbOfFusing
from crafting_system.cli import make_plan
from crafting_system.cli._limits import FINISH, NOT_BUILT
from crafting_system.cli._plan import PlanError
from crafting_system.data import BaseItem
from crafting_system.items import SocketColour, Sockets
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.provenance import EXCHANGE, Provenance

W = SocketColour.WHITE
CURRENCY = ((JEWELLERS_ORB_ID, "Jeweller's Orb"), (FUSING_ORB_ID, "Orb of Fusing"), (CHROMATIC_ID, "Chromatic Orb"))
# the bench prices its socket crafts in currency the fixture data does not hold: the three orbs, named as the game names them
DATA = dataclasses.replace(
    TARGET_DATA,
    base_items={**TARGET_DATA.base_items, **{key: BaseItem(key, name, "StackableCurrency", "currency", 1, (), (), "released") for key, name in CURRENCY}},
)
JEWELLER, FUSING = 0.1, 0.2
START = "start_item:\n  rarity: rare\n  sockets: {colours: [W, W, W]}\n  quality: {percent: 20}\n"  # a rare robe: the Chaos Orb plans its mods


def prices() -> PriceFile:
    entries = {
        name: PriceEntry(chaos, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", "2026-10-30", 1e9))
        for name, chaos in (("Jeweller's Orb", JEWELLER), ("Orb of Fusing", FUSING))
    }
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, entries)


@pytest.fixture(scope="module")
def plans():
    with_sockets = parse("sockets: {count: 4, links: 3}\n" + START)
    without = dataclasses.replace(with_sockets, sockets=None)
    return make_plan(DATA, with_sockets, prices()), make_plan(DATA, without, prices())


def test_a_target_with_sockets_is_planned_and_its_finish_is_added_to_every_goal_state(plans):
    plan, plain = plans
    assert plan.finish is not None and plain.finish is None
    steps = [FinishStep("Jeweller's Orb", JewellersOrb(), JEWELLER), FinishStep("Orb of Fusing", OrbOfFusing(), FUSING)]
    alone = solve_finish(DATA, plan.target.base_id, 84, SocketWanted(count=4, links=3), Sockets.unlinked((W, W, W)), steps, quality=20)
    assert plan.finish_value == pytest.approx(alone.value, rel=1e-12) and plan.finish_value > 0
    assert plan.total_mean == pytest.approx(plan.mean_remaining + plan.finish_value, rel=1e-15)
    goal = next(state for state in plan.solution.values if plan.is_goal(state))
    assert plan.value_of(goal) == plan.finish_value  # a goal state's value is the finish


def test_the_finish_changes_no_step_of_the_mods(plans):
    plan, plain = plans
    assert plan.solution.values == plain.solution.values
    assert {state: action.label for state, action in plan.policy.items()} == {state: action.label for state, action in plain.policy.items()}
    assert plan.mean_remaining == plain.mean_remaining


def test_the_answer_says_the_finish_and_the_total(plans):
    plan, plain = plans
    finish = [limit for limit in plan.limits if limit.kind == FINISH]
    assert len(finish) == 1
    assert f"{plan.total_mean:,.2f} Chaos" in finish[0].why and f"{plan.finish_value:,.2f} Chaos" in finish[0].why
    assert set(finish[0].labels) <= {"Jeweller's Orb", "Orb of Fusing"} and finish[0].labels
    assert not any(limit.kind == FINISH for limit in plain.limits)
    built = [label for limit in plan.limits if limit.kind == NOT_BUILT for label in limit.labels]
    assert not any("Jeweller" in label or "Fusing" in label or "Chromatic" in label for label in built)


def test_a_start_item_that_meets_the_sockets_adds_nothing():
    target = parse("sockets: {count: 3}\n" + START)
    plan = make_plan(DATA, target, prices())
    assert plan.finish is not None and plan.finish.finish.met and plan.finish_value == 0.0
    assert plan.total_mean == plan.mean_remaining


def test_a_start_item_whose_sockets_are_not_stated_is_refused():
    target = parse("sockets: {count: 4}\n")  # the start item says `sockets: any`
    with pytest.raises(PlanError, match="does not say which"):
        make_plan(DATA, target, prices())


def test_a_finish_no_offered_action_completes_is_refused_with_what_was_offered():
    target = parse("sockets: {count: 4, links: 4}\nstart_item:\n  rarity: rare\n  sockets: {colours: [W, W, W]}\n")  # no quality: no Fusing table, no Scrap priced
    with pytest.raises(PlanError, match="no way of finishing the sockets"):
        make_plan(DATA, target, prices())


def test_the_target_s_actions_name_the_finish_kinds_it_may_use():
    target = dataclasses.replace(parse("sockets: {count: 4, links: 3}\n" + START), actions=("chaos-orb", "jewellers-orb"))
    with pytest.raises(PlanError, match="no way of finishing the sockets"):  # Fusing not named, so nothing links
        make_plan(DATA, target, prices())
    named = dataclasses.replace(target, actions=("chaos-orb", "jewellers-orb", "orb-of-fusing"))
    assert make_plan(DATA, named, prices()).finish_value > 0


def test_a_lock_burn_never_changes_the_sockets_of_a_target_that_names_them():
    item = parse("sockets: {count: 4}\n" + START).start_item
    assert ChromaticOrb() in [burn.action for burn in burns_at(DATA, item, BurnKeeps())]
    assert ChromaticOrb() not in [burn.action for burn in burns_at(DATA, item, BurnKeeps(sockets=True))]
