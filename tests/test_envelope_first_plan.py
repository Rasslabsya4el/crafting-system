"""The first plan of the envelope search on a blind bound, and a round the solver cannot certify (ticket #948, OR-13, OR-26, OR-32, OR-33, OR-39, OR-40).

On seven large generated targets the plan in hand cost 1e7 to 1e13 Chaos against a lower figure of tens. Two causes, each worked by hand below:

* **The first plan on a blind bound.** The least `la` is the action the bound thinks best only where the bound saw the state's future. Where the build of
  the bound was stopped by its net, `la` is about the offer's own price, so the cheapest offer wins everywhere: a reroll that nearly always gives the
  same item back, a plan of a million steps. The problem then gives its own order (`Problem.first_choice`; the crafting problem: the model solved on
  what its build finished, `CraftingProblem._closed`). The search proves the same figures whatever the order: only the plan in hand changes.
* **A round whose lower solve the solver cannot certify** (a plan of 10^9 steps or more, #867) ended the search with a refusal although it held a plan
  within a few percent of its lower figure. It is now a stop: the plan in hand, and the lower figure of the last round that was certified.
"""

import math
import random

import pytest
from coarse_support import abstraction
from envelope_support import ExplicitProblem, dense_optimum, random_graph
from test_cli_envelope import answer, check_exact
from test_cli_envelope_build import counting_stop, world  # noqa: F401  (`world` is a fixture)
from test_envelope_gap_stop import Hand
from test_packed_walk_light import START_ITEM

from crafting_system.planner import _envelope, _envelope_plan
from crafting_system.planner._envelope import FAKE, Net, Search
from crafting_system.planner._envelope_plan import CraftingProblem, certified_upper, envelope_limits, envelope_result
from crafting_system.planner._limits import limit_text
from crafting_system.planner._pattern_bound import pattern_lower_bound
from crafting_system.solver import ConvergenceError

# ---- the near-absorbing first plan, by hand ----------------------------------------------------------------------------------------------
#
# Start 0, the start item bought (offer 0, the restart, costs 3 and is offered everywhere but at the start), goal 9.
#   state 0: offer 1, a reroll for 0.1: the same item back with chance 1 - 1e-6, the goal with 1e-6 (alone: 0.1 / 1e-6 = 100,000);
#            offer 2, a craft for 10: state 1.
#   state 1: offer 3, a finish for 10: the goal; offer 1, the reroll, as at 0 (state 1 back, or the goal); the restart.
# V*(1) = 10 (finish), V*(0) = 10 + 10 = 20.
# A blind bound (a build stopped before it saw anything): every state 0, every offer its price. The least `la` at 0 is the reroll (0.1): the first plan
# is the reroll alone, 100,000 Chaos, 2,000 times the optimum, a million steps on average. With the problem's order (craft, then finish) the first plan
# is the optimum itself, 20. The exact search ends on 20 from either.

REROLL_STAY = 999_999


def absorbing(**changes) -> Hand:
    world = Hand(
        goal={9},
        costs={0: 3.0, 1: 0.1, 2: 10.0, 3: 10.0},
        actions={
            0: {1: {0: REROLL_STAY, 9: 1}, 2: {1: 1}},
            1: {3: {9: 1}, 1: {1: REROLL_STAY, 9: 1}, 0: {0: 1}},
            9: {},
        },
        la={(0, 1): 0.1, (0, 2): 10.0, (1, 3): 10.0, (1, 1): 0.1, (1, 0): 3.0},
        lb={0: 0.0, 1: 0.0, 9: 0.0},
        restart=0,
    )
    for name, value in changes.items():
        setattr(world, name, value)
    return world


def test_the_least_lower_cost_on_a_blind_bound_is_a_near_absorbing_first_plan():
    world = absorbing()
    result = Search(world).run()
    assert result.stats.first_upper == pytest.approx(0.1 / 1e-6, rel=1e-6)  # 100,000: the reroll at the start, a million steps
    assert result.stats.seeded == 1 and world.asked[0] == (0, 1)
    assert result.exact and answer(result)[0] == pytest.approx(20.0, rel=1e-9)  # the proof is not at fault: it ends on the optimum


def test_the_problems_own_order_gives_a_first_plan_that_finishes():
    world = absorbing()
    world.first_choice = {0: [2, 1], 1: [3, 0, 1]}.get
    result = Search(world).run()
    assert result.stats.first_upper == pytest.approx(20.0, rel=1e-9)  # the optimum itself: craft, then finish
    assert world.asked[:2] == [(0, 2), (1, 3)] and result.stats.seeded == 2
    assert result.exact and answer(result) == (pytest.approx(20.0, rel=1e-9), {0: 2, 1: 3})  # the same answer as from the least `la`


def test_a_stop_at_a_gap_from_the_problems_order_returns_that_plan():
    world = absorbing()
    world.first_choice = {0: [2, 1], 1: [3, 0, 1]}.get
    result = Search(world, gap=0.01, gap_after=0.0).run()
    mean, plan = answer(result)
    assert mean == pytest.approx(20.0, rel=1e-9) and plan == {0: 2, 1: 3}
    assert result.lower <= 20.0 * (1 + 1e-12)


# The same world on a finished bound whose `la` of the reroll is its loose floor, its price (#829: an offer the bound's model left out, carried by its
# own floor). The problem's `tighten` works out the offer's own floor: Q*(0, 1) = 0.1 + (1 - 1e-6) 20 = 20.09998 and Q*(1, 1) = 10.09999, so 20.05
# and 10.05 are lower bounds of them, above the craft (10) and the finish (10); the restart at 1 is Q*(1, 0) = 3 + 20, so 23. The first plan settles
# the least `la` against the next before it takes it: craft, then finish, the optimum (20), not the reroll chain (100,000; R08: 1,062 Chaos against
# 72.7 before the fix). The rounds ask `tighten` before they build an offer whose `la` is below the best at its state: the reroll is never built.


def test_the_first_plan_and_the_rounds_take_the_lower_cost_the_problem_tightens():
    world = absorbing()
    asked = []

    def tighten(state, position, above):
        asked.append((state, position))
        return {(0, 1): 20.05, (1, 1): 10.05, (1, 0): 23.0}.get((state, position))

    world.tighten = tighten
    result = Search(world).run()
    assert result.stats.first_upper == pytest.approx(20.0, rel=1e-9)
    assert world.asked[:2] == [(0, 2), (1, 3)] and result.stats.seeded == 2
    assert (0, 1) in asked and (1, 1) in asked and result.stats.tightened >= 2
    assert (0, 1) not in world.asked and (1, 1) not in world.asked  # never built: its own floor is above the optimum at its state
    assert result.exact and answer(result) == (pytest.approx(20.0, rel=1e-9), {0: 2, 1: 3})


# State 1 of a world where the craft finishes half the time: the problem takes no offer there, so the first plan leaves it to the restart.
# The first plan: craft at 0 (10, the goal or state 1 half each), restart at 1 (3): U = 10 + (3 + U) / 2, U = 23.


def test_a_state_where_the_problem_takes_no_offer_is_left_to_the_restart():
    world = absorbing(actions={0: {1: {0: REROLL_STAY, 9: 1}, 2: {1: 1, 9: 1}}, 1: {3: {9: 1}, 1: {1: REROLL_STAY, 9: 1}, 0: {0: 1}}, 9: {}})
    world.first_choice = {0: [2], 1: []}.get
    result = Search(world).run()
    assert result.stats.seeded == 1 and world.asked[0] == (0, 2)  # nothing was built at state 1 by the first plan
    assert result.stats.first_upper == pytest.approx(23.0, rel=1e-9)
    assert result.exact and answer(result)[0] == pytest.approx(15.0, rel=1e-9)  # V*(0) = 10 + 10 / 2


def test_with_no_restart_the_least_lower_cost_follows_the_problems_order():
    world = absorbing(restart=None, actions={0: {1: {0: REROLL_STAY, 9: 1}, 2: {1: 1}}, 1: {3: {9: 1}, 1: {1: REROLL_STAY, 9: 1}}, 9: {}})
    world.first_choice = {0: [2], 1: []}.get  # nothing at state 1, and no restart to stand in: the least `la` there, the reroll
    result = Search(world).run()
    assert world.asked[:2] == [(0, 2), (1, 1)]
    assert result.stats.first_upper == pytest.approx(10.0 + 0.1 / 1e-6, rel=1e-6)
    assert result.exact and answer(result)[0] == pytest.approx(20.0, rel=1e-9)


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("alpha", [0.0, 0.5])
def test_whatever_order_the_problem_gives_the_search_proves_the_dense_optimum(seed, alpha):
    graph = random_graph(seed, 50)
    value, _ = dense_optimum(graph)
    problem = ExplicitProblem(graph, value, alpha)
    shuffle = random.Random(seed)

    def first_choice(state):
        offers = list(graph.actions[state])
        shuffle.shuffle(offers)
        return offers[: shuffle.randrange(len(offers) + 1)]  # any order, any part of the offers (none: the restart, or the least `la`)

    problem.first_choice = first_choice
    check_exact(graph, value, Search(problem).run())


# ---- a round the solver cannot certify ---------------------------------------------------------------------------------------------------
#
# The world above with the problem's order: the first plan is 20 (certified). Round 1's lower graph: state 0 holds the craft (10 + L(1)) and a fake
# action for the reroll (0.1); state 1 holds the finish (10) and fakes for the reroll and the restart: L(0) = 0.1. Round 2's lower solve is refused here
# (planted: a certificate of 5e-3, as on beasts/large's 185,029 states). With a net the search holds the first plan and stops on it, with round 1's
# lower figure; with no net it holds no plan and refuses, as before.


def refusing_second_lower_solve(monkeypatch, error=None):
    real = _envelope.solve_graph
    lower_solves = []
    error = error or ConvergenceError("the policy iteration on 3 states certifies only a relative bound of 0.005 (planted)", 5e-3)

    def solve(graph, **options):
        if (graph.act_tag == FAKE).any():
            lower_solves.append(1)
            if len(lower_solves) == 2:
                raise error
        return real(graph, **options)

    monkeypatch.setattr(_envelope, "solve_graph", solve)


@pytest.mark.parametrize("gap", [0.0, 0.01])
def test_a_round_the_solver_cannot_certify_ends_a_search_that_holds_a_plan_with_that_plan(monkeypatch, gap):
    refusing_second_lower_solve(monkeypatch)
    world = absorbing()
    world.first_choice = {0: [2, 1], 1: [3, 0, 1]}.get
    result = Search(world, net=Net(seconds=1e9), gap=gap, gap_after=0.0 if gap else None).run()
    assert not result.exact and result.within is None
    assert result.stopped.startswith("the search could not go further: the lowest possible cost of its round 2 could be worked out only to within 0.005")
    assert result.stats.rounds == 1 and result.stats.lower_refused == 1
    assert result.lower == result.stats.lower_history[0] and result.lower <= 0.1
    assert result.upper == pytest.approx(20.0, rel=1e-9)
    assert answer(result) == (pytest.approx(20.0, rel=1e-9), {0: 2, 1: 3})


def test_a_round_the_solver_cannot_certify_is_a_refusal_when_the_search_holds_no_plan(monkeypatch):
    refusing_second_lower_solve(monkeypatch)
    world = absorbing()
    world.first_choice = {0: [2, 1], 1: [3, 0, 1]}.get
    with pytest.raises(ConvergenceError, match="planted"):
        Search(world).run()  # no net: the search keeps no plan to fall back on


# The solver raises the same error with no figure at all (an infinite bound) for faults that are not the arithmetic limit: a policy whose linear system
# is singular, values that are not finite, an exact merge that did not settle. Those are faults, not a round beyond float64: raised even with a plan held.


@pytest.mark.parametrize(
    "message", ["policy is improper: its linear system is singular (planted)", "the solve did not give finite values (planted)"]
)
def test_a_solver_fault_with_no_figure_is_raised_even_when_the_search_holds_a_plan(monkeypatch, message):
    refusing_second_lower_solve(monkeypatch, ConvergenceError(message, math.inf))
    world = absorbing()
    world.first_choice = {0: [2, 1], 1: [3, 0, 1]}.get
    with pytest.raises(ConvergenceError, match="planted"):
        Search(world, net=Net(seconds=1e9)).run()


# ---- the crafting problem: the closed model of a stopped build ----------------------------------------------------------------------------
#
# The world of `test_cli_envelope_light.py` (about a hundred states, seven offers). A finished build gives no order of its own: the first plan is the
# least `la`, as before, so nothing of a finished bound changes. A build stopped after twelve asks (eleven of its 32 keys expanded) gives the order of
# the closed model: at a key the build did not reach, only the restart.


def test_a_finished_build_leaves_the_first_plan_to_the_least_lower_cost(world):  # noqa: F811
    ab, start, offers, _, _, bound = world
    assert bound.complete
    assert getattr(CraftingProblem(ab, start, offers, bound), "first_choice", None) is None


def test_a_stopped_build_orders_the_offers_by_the_model_of_what_it_finished(world):  # noqa: F811
    _, _, offers, full, _, _ = world
    fresh = abstraction()
    begin = fresh.compress(START_ITEM)
    bound = pattern_lower_bound(fresh, begin, offers, stop=counting_stop(12))
    assert not bound.complete and 0 < sum(bound.model.expanded) < len(bound.model.keys)
    problem = CraftingProblem(fresh, begin, offers, bound)
    assert problem.first_choice is not None and math.isfinite(problem.closed_start)
    assert problem.closed_start >= bound.start_value  # the closed model is the stopped one without its shortcuts: never below it
    order = problem.first_choice(begin)
    backups = problem.closed_lowest[problem._key(begin)]
    assert order and order[0] == min(backups, key=backups.get)
    assert [backups[p] for p in order] == sorted(backups[p] for p in order)
    # a state whose key the build never expanded: the restart alone
    tips = [state for state in full.solution.values if (k := problem._key(state)) is not None and problem.tip[k] and not problem.closed_lowest[k]]
    assert tips
    assert problem.first_choice(tips[0]) == [problem.restart]


# On the same world, stopped after 12 or 20 asks, the first plan that follows the closed model costs less than the one of the least `la` (measured by the
# review of #948: 8.28 against 16.93 after 12 asks, 11.0 against 13.1 after 20), and the exact search ends on the same mean from either.


@pytest.mark.parametrize("asks", [12, 20])
def test_on_a_stopped_build_the_closed_order_gives_a_cheaper_first_plan_and_the_same_exact_mean(world, monkeypatch, asks):  # noqa: F811
    _, _, offers, full, _, _ = world
    means, firsts = {}, {}
    for closed in (True, False):
        if not closed:
            monkeypatch.setattr(_envelope_plan.CraftingProblem, "_closed", lambda self, model, bound: None)
        fresh = abstraction()
        begin = fresh.compress(START_ITEM)
        bound = pattern_lower_bound(fresh, begin, offers, stop=counting_stop(asks))
        assert not bound.complete
        result = envelope_result(fresh, begin, offers, bound=bound)
        info = result.info["envelope"]
        assert info.exact
        means[closed] = result.solution.values[begin]
        firsts[closed] = info.first_upper
    assert firsts[True] < firsts[False]
    assert means[True] == pytest.approx(full.solution.values[begin], rel=1e-9)
    assert means[True] == pytest.approx(means[False], rel=1e-12)


def test_the_crafting_plan_of_a_search_a_refused_round_ended_says_so_with_its_gap(world, monkeypatch):  # noqa: F811
    ab, start, offers, full, _, bound = world
    refusing_second_lower_solve(monkeypatch)
    result = envelope_result(ab, start, offers, bound=bound, net=Net(seconds=1e9), gap=0.001, gap_after=0.0)
    info = result.info["envelope"]
    assert not info.exact and info.within is None and info.stopped.startswith("the search could not go further")
    assert info.lower <= full.solution.values[start] <= certified_upper(info)  # the gap stated holds the cheapest plan
    text = limit_text(envelope_limits(info)[0])
    assert "The search was stopped" in text and "the search could not go further" in text and "costs at most" in text


# ---- a first plan that reaches no goal, and the walk toward the goal (#1142) -------------------------------------------------------------
#
# Start 0, the start item bought (offer 0, the restart, costs 3, offered everywhere but at the start), goal 9. A blind bound: every state 0, every
# offer at its price.
#   state 0: offer 1, a reroll for 0.1: state 1; offer 2, a craft for 10: state 1 or state 2, half each.
#   state 1: offer 1, the reroll: state 0 back; offer 3, a finish for 10: the goal; the restart.
#   state 2: offer 1, the reroll: state 0; the restart.
# The least `la` takes the reroll at 0 and at 1: a chain of two states that never meets the goal, so no policy of what it realized reaches it and
# the plan in hand costs infinity (R04, R14, R20, R24 on the heavy benchmark's records: 352 to 750,477 states and no goal). The distance to the
# goal (the requirements a state lacks) is 2 at 0 and 2, 1 at 1. The walk pops state 1 first (nearest) and realizes what it has left: the finish
# reaches the goal. The plan in hand: reroll at 0 (0.1), finish at 1 (10): U = 10.1, the optimum itself; one offer realized by the walk.

def looping(**changes) -> Hand:
    world = Hand(
        goal={9},
        costs={0: 3.0, 1: 0.1, 2: 10.0, 3: 10.0},
        actions={0: {1: {1: 1}, 2: {1: 1, 2: 1}}, 1: {1: {0: 1}, 3: {9: 1}, 0: {0: 1}}, 2: {1: {0: 1}, 0: {0: 1}}, 9: {}},
        la={(0, 1): 0.1, (0, 2): 10.0, (1, 1): 0.1, (1, 3): 10.0, (1, 0): 3.0, (2, 1): 0.1, (2, 0): 3.0},
        lb={0: 0.0, 1: 0.0, 2: 0.0, 9: 0.0},
        restart=0,
    )
    for name, value in changes.items():
        setattr(world, name, value)
    return world


DISTANCE = {0: 2, 1: 1, 2: 2, 9: 0}.__getitem__


def test_a_chain_that_reaches_no_goal_has_no_plan_in_hand():
    result = Search(looping()).run()
    assert result.stats.first_upper is None and result.stats.seeded == 2 and result.stats.reached == 0  # the reroll at 0 and at 1, nothing more
    assert result.exact and answer(result)[0] == pytest.approx(10.1, rel=1e-9)  # the proof is not at fault: with no net it ends on the optimum


def test_the_walk_toward_the_goal_realizes_a_path_to_it_when_the_chain_reaches_none():
    world = looping()
    world.distance = DISTANCE
    result = Search(world).run()
    assert world.asked[:3] == [(0, 1), (1, 1), (1, 3)]  # the chain's two rerolls, then the finish at state 1, the nearest state
    assert result.stats.seeded == 2 and result.stats.reached == 1
    assert result.stats.first_upper == pytest.approx(10.1, rel=1e-9)
    assert result.exact and answer(result) == (pytest.approx(10.1, rel=1e-9), {0: 1, 1: 3})  # the same answer as without the walk


def test_a_net_that_ends_the_search_after_the_walk_returns_its_plan():
    world = looping()
    world.distance = DISTANCE
    result = Search(world, net=Net(give_way=lambda standing: "the caller's rule")).run()  # the first stop there is: right after the first plan
    assert not result.exact and result.stopped == "the caller's rule"
    assert answer(result)[0] == pytest.approx(10.1, rel=1e-9)


def test_on_a_stopped_build_with_no_order_the_walk_replaces_the_chain():
    world = looping()
    world.distance = DISTANCE
    world.reach_first = True  # the problem's bound was stopped and gives no order: the least-`la` chain is not walked
    result = Search(world).run()
    # state 0 is the only one known: its offers are realized (reroll, craft), then state 1 (nearest) and its offers until the finish meets the goal
    assert world.asked[:4] == [(0, 1), (0, 2), (1, 1), (1, 3)]
    assert result.stats.seeded == 0 and result.stats.reached == 4
    assert result.stats.first_upper == pytest.approx(10.1, rel=1e-9)
    assert result.exact and answer(result)[0] == pytest.approx(10.1, rel=1e-9)


def test_with_no_restart_the_walk_is_not_taken():
    world = looping(restart=None, actions={0: {1: {1: 1}, 2: {1: 1, 2: 1}}, 1: {1: {0: 1}, 3: {9: 1}}, 2: {1: {0: 1}}, 9: {}})
    world.distance = DISTANCE
    world.reach_first = True  # a given start: a path to the goal is no executable plan (a tip has no action), so the chain stays
    result = Search(world).run()
    assert result.stats.reached == 0 and result.stats.seeded == 2


def test_the_crafting_problem_measures_the_distance_by_the_parts_of_the_goal_a_state_lacks(world, monkeypatch):  # noqa: F811
    ab, start, offers, full, _, bound = world
    problem = CraftingProblem(ab, start, offers, bound)
    assert problem.distance == ab.unmet and not problem.reach_first  # a finished build: the chain is walked first
    states = list(full.solution.values)
    assert states and all((problem.distance(state) == 0) == ab.is_goal(state) for state in states)
    assert any(problem.distance(state) > 0 for state in states)
    monkeypatch.setattr(_envelope_plan.CraftingProblem, "_closed", lambda self, model, bound: None)  # a stopped build whose model gives no order
    fresh = abstraction()
    begin = fresh.compress(START_ITEM)
    stopped = pattern_lower_bound(fresh, begin, offers, stop=counting_stop(12))
    assert CraftingProblem(fresh, begin, offers, stopped).reach_first  # the walk replaces the least-`la` chain
    result = envelope_result(fresh, begin, offers, bound=stopped)
    info = result.info["envelope"]
    assert info.exact and result.solution.values[begin] == pytest.approx(full.solution.values[begin], rel=1e-9)  # the same exact mean
    assert info.first_upper is not None and math.isfinite(info.first_upper)
