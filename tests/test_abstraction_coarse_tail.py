"""The tail cut on the coarse state of the fixture (ticket #129, ADR-0023): expand the exact states the coarse policy enters.

The coarse bounds come from `solve_bounds` on the two models of a `Coarsening`; the exact model is the fixture's
`ExactModel`. The checks are against `solve` on the exact graph (the optimum of every state) and on the exact graph
restricted to the policy the cut yields (its cost): the bounds must bracket both for every `theta`, equal the coarse
bounds when nothing is expanded, and never be looser than them.
"""

import functools
import math

import pytest
from abstraction_pool import COLD_RESIST, LIFE_1
from coarse_support import COLD, FIRE, LIGHTNING_RESIST, MANA, CoarseModel, ExactModel, abstraction, item, roll

from crafting_system.abstraction import Coarsening
from crafting_system.solver import Action, TabularModel, solve, solve_bounds, solve_tail_cut

AB = abstraction()
LEVELS = {
    "irrelevant_in_one_group": None,
    "a_blocker_with_a_stranger": [{COLD, MANA}],
    "only_the_two_blockers": [{COLD, FIRE}],
}
NO_POLICY = {"blockers_in_two_groups": [{COLD, MANA}, {FIRE, LIGHTNING_RESIST}]}  # the upper model cannot reach the goal at all
LEVELS_ALL = {**LEVELS, **NO_POLICY}
STARTS = {"cold_and_life": (COLD_RESIST, LIFE_1)}  # every further start expands more exact states, and a Chaos Orb kernel of the fixture takes about 0.7 s each
THETAS = (math.inf, 1.0, 0.5, 0.1, 0.01, 0.0)  # largest first: the expanded sets grow
SLACK = 1e-9
POLICY_ITERATION = {"direct_solve_limit": 10**6}  # the components here are small enough to solve by policy iteration, far faster than value iteration


class Memo:
    """A model that remembers the actions of each state: the sweeps below solve the same graphs again and again."""

    def __init__(self, inner):
        self.inner, self.known = inner, {}

    def is_goal(self, state):
        return self.inner.is_goal(state)

    def actions(self, state):
        if state not in self.known:
            self.known[state] = tuple(self.inner.actions(state))
        return self.known[state]


EXACT = Memo(ExactModel(AB))


@functools.cache
def models(level):
    pooling = coarsening(LEVELS_ALL[level])
    return pooling, Memo(CoarseModel(pooling, "lower")), Memo(CoarseModel(pooling, "upper"))


def coarsening(level) -> Coarsening:
    return Coarsening.pooling_irrelevant(AB, level) if level is None else Coarsening(AB, level)


def start_of(name):
    return AB.compress(item(*(roll(mod_id) for mod_id in STARTS[name])))


def coarse_bounds(level, start):
    pooling, lower, upper = models(level)
    return solve_bounds(lower, upper, [pooling.coarsen(start)], **POLICY_ITERATION)


def cut(level, start, theta):
    pooling, lower, upper = models(level)
    return solve_tail_cut(EXACT, lower, upper, pooling.coarsen, start, theta, **POLICY_ITERATION)


class PolicyModel:
    """The exact model restricted to one action per state: its value is the cost of the policy."""

    def __init__(self, choose):
        self.choose = choose

    def is_goal(self, state):
        return AB.is_goal(state)

    def actions(self, state):
        return [self.choose(state)]


@pytest.mark.parametrize("name", STARTS)
@pytest.mark.parametrize("level", LEVELS)
def test_the_bounds_bracket_the_optimum_and_the_cost_of_the_policy_for_every_theta(level, name):
    pooling, start = models(level)[0], start_of(name)
    best = solve(EXACT, [start], **POLICY_ITERATION)

    def coarse_action(state):
        wanted = found.coarse.policy[pooling.coarsen(state)]
        return next(action for action in EXACT.actions(state) if action.label == wanted.label)

    for theta in THETAS:
        found = cut(level, start, theta)
        policy = found.bounds.policy
        cost = solve(PolicyModel(lambda state: policy[state] if state in policy else coarse_action(state)), [start, *found.expanded], **POLICY_ITERATION)
        for state in {start, *found.expanded}:
            assert found.bounds.lower[state] <= best.values[state] * (1 + SLACK)
            assert best.values[state] * (1 - SLACK) <= cost.values[state] <= found.bounds.upper[state] * (1 + SLACK)
        assert found.bounds.gap == found.bounds.gap_at(start)


@pytest.mark.parametrize("name", STARTS)
@pytest.mark.parametrize("level", LEVELS)
def test_nothing_expanded_gives_the_coarse_bounds_and_a_smaller_theta_never_loosens_them(level, name):
    pooling, start = models(level)[0], start_of(name)
    coarse = coarse_bounds(level, start)
    block = pooling.coarsen(start)

    before = cut(level, start, math.inf)
    assert (before.bounds.lower[start], before.bounds.upper[start], before.bounds.gap, before.expanded) == (
        coarse.lower[block], coarse.upper[block], coarse.gap, frozenset()
    )
    for theta in THETAS[1:]:
        found = cut(level, start, theta)
        assert before.expanded <= found.expanded
        assert before.bounds.lower[start] <= found.bounds.lower[start] * (1 + SLACK)
        assert found.bounds.upper[start] <= before.bounds.upper[start] * (1 + SLACK)
        before = found


def test_a_blocker_pooled_with_a_stranger_leaves_a_gap_that_the_cut_narrows():
    level, start = "a_blocker_with_a_stranger", start_of("cold_and_life")
    coarse = coarse_bounds(level, start)
    best = solve(EXACT, [start], **POLICY_ITERATION).values[start]

    assert coarse.gap > 0.05  # ADR-0023: a member may hold the stranger, so the goal craft is open in one model only
    closed = cut(level, start, 0.0)

    assert closed.bounds.gap < coarse.gap
    assert closed.bounds.lower[start] <= best * (1 + SLACK) and best * (1 - SLACK) <= closed.bounds.upper[start]
    assert closed.expanded <= set(solve(EXACT, [start], **POLICY_ITERATION).values)


def test_an_exact_model_that_does_not_offer_the_coarse_action_is_refused():
    pooling, lower, upper = models("irrelevant_in_one_group")

    with pytest.raises(ValueError, match="does not offer"):
        solve_tail_cut(TabularModel([], {}), lower, upper, pooling.coarsen, start_of("cold_and_life"), 0.0)


def test_the_policy_actions_are_exact_actions_whose_outcomes_are_exact_states():
    level, start = "a_blocker_with_a_stranger", start_of("cold_and_life")

    found = cut(level, start, 0.1)

    exact_actions = {action.label: action for action in EXACT.actions(start)}
    chosen = found.bounds.policy[start]
    assert isinstance(chosen, Action) and chosen.outcomes == exact_actions[chosen.label].outcomes


def test_a_level_whose_pessimistic_model_cannot_reach_the_goal_has_no_policy_to_follow():
    pooling, lower, upper = models("blockers_in_two_groups")  # the blockers are pooled with others in two groups: nothing is legal in every member

    with pytest.raises(ValueError, match="nothing to follow"):
        solve_tail_cut(EXACT, lower, upper, pooling.coarsen, start_of("cold_and_life"), 0.0)
