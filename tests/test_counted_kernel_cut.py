"""A run counted in states stops inside the making of a kernel (ticket #1105; #1101, #886, OR-12, OR-13, OR-33).

Before: the envelope search asked its states net between two kernels, and one kernel of a drawing action is made whole from its pool's
distribution, so one expansion took the run far past its net (R05 at N = 1,000 knew 303,950 states; the coarse world below knew 95 at any N
from 2 to 94). Now a search counted in states makes each kernel on an allowance of the states it may still know (`budget.Allowance`): the
draw engine and the kernel's assembly count their outcomes as they make them and stop past it, and a kernel made whole is refused when its
new states would pass the net. The kernel is left unmade, its offer stays open, and the search ends there as at its net, with the plan in
hand: **the states known at a stop are at most N**, with no outcome count added. Under a time net nothing changes.

Worked by hand below (`Counted`, a world written out by hand whose kernels count what they make as the engine does), then through the
planner's entry on the coarse world, where the start's Chaos Orb has 94 outcomes.
"""

from fractions import Fraction

import pytest
from abstraction_pool import RESISTS, fractured_item
from abstraction_support import ACTIONS, abstraction
from coarse_support import DATA as COARSE
from proto_draw_support import draws, family
from test_cli_envelope import answer
from test_cli_envelope_plan import coarse  # noqa: F401 (the fixture: the coarse world of about 200 states, its start bought for 5 Chaos)
from test_envelope_gap_stop import Hand

from crafting_system import budget
from crafting_system.abstraction import Goal, Wanted
from crafting_system.abstraction._rolls import RollLaw
from crafting_system.actions import ChaosOrb, draw
from crafting_system.budget import Budget
from crafting_system.items import Side
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.planner._envelope import Net, Search
from crafting_system.planner._plan import PlanError

PREFIX, SUFFIX = Side.PREFIX, Side.SUFFIX
UNMADE = "it was left unmade"  # the words of a stop inside the making of a kernel


class Counted(Hand):
    """A hand world whose kernels count each outcome on the search's allowance as they make it, as `actions.draw.exact_distributions` does."""

    def kernel(self, state: int, position: int) -> dict[int, int]:
        weights = super().kernel(state, position)
        allowance = budget.allowed()
        made = {}
        for successor, weight in weights.items():
            if allowance is not None:
                allowance.add()
            made[successor] = weight
        return made


# ---- by hand -----------------------------------------------------------------------------------------------------------------------------
#
# Start 0, goal 9, the start item bought (offer 0, the restart, costs 3 and is offered everywhere but at the start).
#   state 0: offer 2, a craft for 10: the goal or state 1, half each; offer 4, a fossil for 1: one of 50 states 100..149, each 1 in 50.
#   state 1 and states 100..149: the restart alone.
# The problem's first plan is the craft at 0, the restart at 1: U = 10 + (3 + U) / 2, U = 23, over 3 states (0, 1, 9). The bound puts the fossil
# at 1 (its price), so round 1's lower graph takes it at 0, a tip: the round makes its kernel, 50 new states. The exact answer is 23 (the fossil
# costs 1 + 3 + 23 = 27), over 53 states.
# Under a count of N = 10 the fossil's kernel is made on an allowance of 10 - 3 = 7 outcomes and stops as it makes its 8th: the search ends
# with the plan in hand (23) and 3 states known. Before, it took all 50 and knew 53. Under N = 60 the kernel fits (57 left) and the search is exact.

FOSSIL = 50


def fossil_world(world=Counted) -> Hand:
    tips = range(100, 100 + FOSSIL)
    actions = {0: {2: {9: 1, 1: 1}, 4: {tip: 1 for tip in tips}}, 1: {0: {0: 1}}, 9: {}, **{tip: {0: {0: 1}} for tip in tips}}
    found = world(
        goal={9}, costs={0: 3.0, 2: 10.0, 4: 1.0}, actions=actions,
        la={(0, 2): 10.0, (0, 4): 1.0, (1, 0): 3.0, **{(tip, 0): 3.0 for tip in tips}}, lb={state: 0.0 for state in actions}, restart=0,
    )  # fmt: skip
    found.first_choice = {0: [2], 1: []}.get
    return found


def counted(states: int) -> Net:
    return Net(states=states, pieces=1)  # a run counted in states sets the build's pieces (`Budget.in_states`, `_plan.search_net`)


def test_a_kernel_that_would_pass_the_count_is_stopped_as_it_is_made_and_the_plan_in_hand_is_kept():
    world = fossil_world()
    result = Search(world, net=counted(10)).run()
    assert (0, 4) in world.asked  # the round began to make the fossil's kernel ...
    assert len(result.states) == 3 and result.stats.touched == 3 <= 10  # ... and none of its states is known: at most N
    assert result.stats.cut == 8  # stopped as it made its 8th outcome, of an allowance of 10 - 3 = 7
    assert not result.exact and UNMADE in result.stopped and "3 states were known, the limit is 10" in result.stopped
    assert answer(result)[0] == pytest.approx(23.0, rel=1e-9)  # the plan in hand: the craft, the restart at 1


def test_without_a_count_or_with_room_for_it_the_kernel_is_made_whole():
    # the same world on a states net that is not a count (no build's pieces: a net on the clock) asks the net between rounds only, as before
    stopped = Search(fossil_world(), net=Net(states=10)).run()
    assert stopped.stats.touched == 53 and stopped.stats.cut == 0 and UNMADE not in (stopped.stopped or "")
    roomy = Search(fossil_world(), net=counted(60)).run()  # 57 left: the 50 fit
    assert roomy.exact and roomy.stats.touched == 53 <= 60 and roomy.stats.cut == 0
    assert answer(roomy)[0] == pytest.approx(23.0, rel=1e-9)


def test_a_kernel_made_whole_uncounted_is_still_refused_when_its_new_states_would_pass_the_count():
    # a kernel whose making counts nothing (a fixed result, a reroll of values): its 50 new states against the 7 left, after it is made
    world = fossil_world(Hand)
    result = Search(world, net=counted(10)).run()
    assert result.stats.touched == 3 and result.stats.cut == FOSSIL
    assert "the next action's 50 new states would pass it" in result.stopped and UNMADE in result.stopped
    assert answer(result)[0] == pytest.approx(23.0, rel=1e-9)


def test_a_cut_offer_is_left_open_in_the_lower_figure():
    # the fossil is still to be made at 0: the lower figure of the stop counts it at its bound (1), below the craft, so it is no proof of 23
    result = Search(fossil_world(), net=counted(10)).run()
    assert result.lower < 23.0


def test_the_allowance_counts_on_and_stops_past_its_figure():
    assert budget.allowed() is None
    with budget.counting(2) as allowance:
        assert budget.allowed() is allowance
        allowance.add()
        allowance.add()
        with pytest.raises(budget.OutcomesCut) as cut:
            allowance.add()
    assert (cut.value.given, cut.value.made) == (2, 3) and budget.allowed() is None
    assert not isinstance(cut.value, Exception)  # no `except Exception` (nor a refusal's `except ValueError`) of the making swallows it


def test_each_stage_of_the_making_counts_on_its_own():
    # one outcome is met once at each stage of its making (an end state, a group, a way, a state added): each stage is held to the allowance
    # apart, so a kernel of 2 outcomes is made whole on an allowance of 2 (a sum over the stages would cut it at 8 of them, #1137)
    with budget.counting(2) as allowance:
        for stage in ("end state", "group", "way", "outcome", "state", "spread state"):
            allowance.add(stage)
            allowance.add(stage)
        with pytest.raises(budget.OutcomesCut) as cut:
            allowance.add("way")
    assert (cut.value.stage, cut.value.made, cut.value.given) == ("way", 3, 2)


# ---- through the planner's entry, on the coarse world --------------------------------------------------------------------------------------
#
# The start item is bought; the first plan's chain begins with a Chaos Orb at the start, whose kernel has 94 outcomes, none of them the start.
# A count of N <= 94 leaves no room for them (1 + 94 > N): before, the search knew 95 states at every such N; now it knows the start alone,
# says the stop, and has no plan (the start item is not given a restart). Its making counts the draw walk's 119 end states (merged into the 94
# outcomes), so it fits from N = 120; past it the states known stay at most N. (Until #1146 the bound's build had made that kernel already and
# the search found it made: it fitted from N = 95. The build now takes an erasing kernel from the alike twin, ADR-0065, and the search makes it.)
END_STATES = 119


def plan_counted(coarse, states: int):  # noqa: F811
    target, prices, _ = coarse
    clock = Budget.in_states(states).start()
    with budget.running(clock):
        try:
            plan = plan_target(COARSE, target, prices, PlanSettings(recipe_starts=False, start_price=5.0, solver="envelope", budget=Budget.in_states(states)))
        except PlanError as error:
            return None, str(error), clock.spent
    return plan, plan.packed.info["envelope"].stopped, clock.spent


def test_the_start_s_chaos_orb_has_94_outcomes(coarse):  # noqa: F811
    _, _, full = coarse
    outcomes = full.abstraction.kernel(full.start, ChaosOrb())
    assert len(outcomes) == 94 and full.start not in outcomes


@pytest.mark.parametrize("states", [2, 5, 50, 94, 95, END_STATES])
def test_through_the_entry_a_count_below_the_first_kernel_knows_at_most_its_states(coarse, states):  # noqa: F811
    plan, said, known = plan_counted(coarse, states)
    assert plan is None and known == 1 <= states  # before: 95
    assert f"1 states were known, the limit is {states:,}, and the next action's outcomes would pass it" in said and UNMADE in said


@pytest.mark.parametrize("states", [END_STATES + 1, END_STATES + 2, 150, 200])
def test_through_the_entry_the_states_known_never_pass_the_count(coarse, states):  # noqa: F811
    plan, said, known = plan_counted(coarse, states)
    assert known <= states and UNMADE not in (said or "")
    assert plan is not None and plan.search.touched == known


# ---- what a cut leaves, and what one making may hold (#1137) -----------------------------------------------------------------------------
#
# A kernel cut inside its making is left unmade: nothing of it may stay behind in the abstraction (its cached distributions and expanded
# entries are stored only once whole), so the same kernel made afterwards without a count is the kernel a fresh abstraction makes. Each
# stage counts what it builds as it builds it, the spreads of a part over its labels and of an outcome over roll laws included, so a cut
# making has made at most one piece past its allowance at each stage, and at most `len(STAGES)` stages: that is the multiplier
# `Budget.in_states` states.


def stages_of(abstraction_of, state, action) -> dict[str, int]:
    """What one whole making of the kernel counts, per stage, on a fresh abstraction."""
    with budget.counting(10**9) as allowance:
        abstraction_of().kernel(state, action)
    return dict(allowance.made)


def cut_then_whole(abstraction_of, state, action, given: int):
    """The kernel made on an allowance of `given`, then again with no count on the same abstraction: (the cut or None, the whole kernel)."""
    abstraction = abstraction_of()
    cut = None
    try:
        with budget.counting(given):
            abstraction.kernel(state, action)
    except budget.OutcomesCut as stopped:
        cut = stopped
    return cut, abstraction.kernel(state, action)


def check_cuts(abstraction_of, state, action) -> dict[str, int]:
    whole = stages_of(abstraction_of, state, action)
    assert set(whole) <= set(budget.STAGES)
    largest = max(whole.values())
    fresh = abstraction_of().kernel(state, action)
    for given in sorted({0, 1, 2, largest // 3, largest // 2, largest - 1, largest}):
        cut, kernel = cut_then_whole(abstraction_of, state, action, given)
        assert kernel == fresh  # nothing of the cut making was kept: the kernel made after it is a fresh abstraction's
        if given < largest:
            assert cut is not None and cut.made == given + 1 and cut.stage in budget.STAGES  # one piece past the allowance, at one stage
        else:
            assert cut is None  # the largest stage fits: the making is whole
    return whole


def test_a_cut_draw_leaves_the_coarse_abstraction_clean(coarse):  # noqa: F811
    _, _, full = coarse
    made = full.abstraction

    def fresh():
        return type(made)(made.data, made.goal, made.base_id, made.item_level, made._kinds.actions, metamods=made._kinds.metamods)

    whole = check_cuts(fresh, full.start, ChaosOrb())
    # the start's Chaos Orb: 119 states of the draw walk (every step's), 56 groups, 4 entries of the spreads, 76 ways, 94 outcomes and states
    assert whole == {"end state": 119, "group": 56, "spread": 4, "way": 76, "outcome": 94, "state": 94}


def test_a_cut_roll_law_spread_leaves_the_abstraction_clean():
    # a roll limit: each drawn resist mod spreads over the values of its law (`Abstraction._concrete`), counted as the spread is built
    goal = Goal((Wanted(RESISTS, min_roll=(10,)),))
    for action in ACTIONS.values():
        whole = check_cuts(lambda: abstraction(goal), abstraction(goal).compress(fractured_item()), action)
        assert "outcome" in whole and whole["outcome"] >= whole["state"]  # one law per outcome here: two laws are below


def test_a_cut_walk_with_views_is_made_again_whole():
    # `exact_distributions` holds what it makes in its own call: a walk cut at any allowance, then made with no count, gives what it gives fresh
    pool = (family("A", PREFIX, ("A1", 100), ("A2", 300)), family("B", PREFIX, ("B1", 100), ("B2", 50)), family("C", SUFFIX, ("C1", 70), ("C2", 30)), family("D", SUFFIX, 400))
    free = {PREFIX: 3, SUFFIX: 3}
    views = [(lambda mod: mod.id[0], None), (lambda mod: "any", None)]
    fresh = draw.exact_distributions(pool, free, None, draws(3), 0, lambda mod: mod.id, views)
    with budget.counting(10**9) as allowance:
        draw.exact_distributions(pool, free, None, draws(3), 0, lambda mod: mod.id, views)
    whole = dict(allowance.made)
    assert set(whole) <= set(budget.STAGES) and "spread" in whole
    for given in range(max(whole.values())):
        with pytest.raises(budget.OutcomesCut), budget.counting(given):
            draw.exact_distributions(pool, free, None, draws(3), 0, lambda mod: mod.id, views)
        assert draw.exact_distributions(pool, free, None, draws(3), 0, lambda mod: mod.id, views) == fresh


def test_an_outcome_over_two_roll_laws_counts_each_entry_as_it_is_built():
    # two mods of two laws (2 and 3 values): the first law's spread makes 2 entries ("roll"), the last's 2 x 3 = 6 outcomes ("outcome")
    first = RollLaw((((1,), Fraction(1, 2)), ((2,), Fraction(1, 2))))
    last = RollLaw((((10,), Fraction(1, 3)), ((20,), Fraction(1, 3)), ((30,), Fraction(1, 3))))
    outcome = frozenset({(first, 1), (last, 1)})
    model = abstraction(Goal((Wanted(RESISTS, min_roll=(10,)),)))
    assert not model._kinds.tracked
    whole = model._concrete(outcome)
    assert len(whole) == 6 and sum(chance for _, chance in whole) == 1
    with budget.counting(10**9) as allowance:
        assert model._concrete(outcome, allowance) == whole
    assert allowance.made == {"roll": 2, "outcome": 6}
    for given, stage in ((0, "roll"), (1, "roll"), (2, "outcome"), (5, "outcome")):
        with pytest.raises(budget.OutcomesCut) as cut, budget.counting(given) as allowance:
            model._concrete(outcome, allowance)
        assert (cut.value.stage, cut.value.made) == (stage, given + 1)
    assert model._concrete(outcome) == whole  # the law's spreads it keeps are whole: a cut leaves nothing behind
