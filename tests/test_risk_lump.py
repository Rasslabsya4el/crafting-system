"""Lumping a fixed policy's states that behave alike before its risk is measured (ticket #717).

States of a policy whose action costs the same and whose outcomes fall, weight for weight, on the same blocks of states have the same future
cost distribution, so one stands for the block: the budget DP then runs over the blocks, not over every state (R13's given route has 2,887 states
and a handful of blocks; the DP took 4 to 18 minutes on them). The lumped policy has the cost distribution of the policy, the odds, the mean,
the variance, the quantiles and the CVaR included: nothing is approximated.
"""

import random

import pytest
from risk_support import GOAL, geometric_policy, is_goal

from crafting_system.risk import evaluate, lump
from crafting_system.solver import Action

DEAD = "dead"  # reachable, no policy entry: stuck


def copies_of(base, copies, rng):
    """`base` (state -> (cost, {target: weight})) with every state made `copies` times; each outcome falls on a random copy of its target."""
    policy = {}
    for state, (cost, outcomes) in base.items():
        for k in range(copies):
            spread = {}
            for target, weight in outcomes.items():
                if target in (GOAL, DEAD):
                    spread[target] = spread.get(target, 0) + weight
                    continue
                for _ in range(weight):  # `weight` unit outcomes, each to a random copy of the target: not the same distribution per copy
                    pick = (target, rng.randrange(copies))
                    spread[pick] = spread.get(pick, 0) + 1
            policy[(state, k)] = Action(f"{state}", cost, tuple(spread.items()))
    return policy


BASE = {
    "a": (1.0, {"a": 3, "b": 2, GOAL: 1}),
    "b": (2.0, {"a": 1, "b": 1, GOAL: 2}),
}


def twins_policy(copies=6):
    """Copies of `BASE` where every copy of a state has the same outcomes as the others, spread over the copies of its targets alike."""
    policy = {}
    for state, (cost, outcomes) in BASE.items():
        for k in range(copies):
            spread = {}
            for target, weight in outcomes.items():
                if target == GOAL:
                    spread[GOAL] = weight
                else:
                    for j in range(copies):
                        spread[(target, j)] = weight
            policy[(state, k)] = Action(state, cost, tuple(spread.items()))
    return policy


def same(report, other):
    assert report.success_probability.value == pytest.approx(other.success_probability.value, abs=1e-12)
    assert report.mean.value == pytest.approx(other.mean.value, rel=1e-9)
    assert report.variance.value == pytest.approx(other.variance.value, rel=1e-8)
    for level in report.quantiles:
        assert report.quantiles[level].low == pytest.approx(other.quantiles[level].low, rel=1e-9)
        assert report.quantiles[level].high == pytest.approx(other.quantiles[level].high, rel=1e-9)
    assert report.cvar.value == pytest.approx(other.cvar.value, rel=1e-9)


def test_copies_of_a_state_that_behave_alike_are_one_block():
    policy = twins_policy(copies=6)

    lumped = lump(policy, ("a", 0), is_goal)

    assert len(policy) == 12 and len(lumped.policy) == 2  # a and b


def test_the_lumped_policy_has_the_odds_the_mean_the_variance_the_quantiles_and_the_cvar_of_the_policy():
    policy = twins_policy(copies=6)
    lumped = lump(policy, ("a", 0), is_goal)

    whole = evaluate(policy, ("a", 0), is_goal)
    short = evaluate(lumped.policy, lumped.start, lumped.is_goal)

    same(short, whole)
    assert short.mean.value == pytest.approx(whole.mean.value, rel=1e-12) and 0.0 < short.mean.value < 100.0


def test_a_block_is_told_by_cost_and_by_where_its_weights_fall():
    policy = twins_policy(copies=3)
    policy[("b", 1)] = Action("b", 2.5, policy[("b", 1)].outcomes)  # dearer: not a twin
    policy[("a", 2)] = Action("a", 1.0, (*policy[("a", 2)].outcomes[:-1], (GOAL, 7)))  # a different chance of the goal: not a twin

    lumped = lump(policy, ("a", 0), is_goal)

    assert len(lumped.policy) == 4  # a, a with the other chance, b, and b at the other cost
    same(evaluate(lumped.policy, lumped.start, lumped.is_goal), evaluate(policy, ("a", 0), is_goal))


def test_weights_in_the_same_proportion_make_the_same_block():
    policy = {
        "s": Action("s", 1.0, (("x", 1), ("y", 1))),
        "x": Action("t", 1.0, (("x", 1), (GOAL, 1))),
        "y": Action("t", 1.0, (("y", 2), (GOAL, 2))),
    }

    lumped = lump(policy, "s", is_goal)

    assert len(lumped.policy) == 2  # s and one for x and y
    same(evaluate(lumped.policy, lumped.start, lumped.is_goal), evaluate(policy, "s", is_goal))


def test_the_start_is_kept_as_the_start_and_a_goal_stays_a_goal():
    lumped = lump(twins_policy(copies=4), ("b", 3), is_goal)

    assert lumped.start == ("b", 3)
    assert lumped.is_goal(GOAL) and not lumped.is_goal(lumped.start)


def test_a_policy_with_no_twins_is_returned_as_it_is():
    policy = geometric_policy(1, 3, 2.0)

    lumped = lump(policy, "S", is_goal)

    assert lumped.policy is policy and lumped.start == "S" and lumped.is_goal is is_goal


def test_a_policy_with_inputs_is_returned_as_it_is():
    policy = twins_policy(copies=3)
    policy[("a", 0)] = Action("a", 1.0, policy[("a", 0)].outcomes, extra_inputs=(("b", 0),))

    lumped = lump(policy, ("a", 0), is_goal)

    assert lumped.policy is policy


def test_stuck_states_are_one_block_and_the_lost_mass_is_the_same():
    policy = {
        "s": Action("s", 1.0, (("x", 1), ("y", 1), ("d1", 1), ("d2", 1), (GOAL, 2))),
        "x": Action("t", 1.0, (("x", 1), (GOAL, 1))),
        "y": Action("t", 1.0, (("y", 1), (GOAL, 1))),
    }  # d1 and d2 have no entry

    lumped = lump(policy, "s", is_goal)

    assert len(lumped.policy) == 2
    whole = evaluate(policy, "s", is_goal)
    short = evaluate(lumped.policy, lumped.start, lumped.is_goal)
    assert short.success_probability.value == pytest.approx(whole.success_probability.value, abs=1e-12) and short.success_probability.value < 1.0


@pytest.mark.parametrize("seed", range(30))
def test_random_policies_keep_their_risk_when_lumped(seed):
    rng = random.Random(seed)
    base = {}
    names = ["a", "b", "c"]
    for state in names:
        outcomes = {rng.choice([*names, GOAL]): rng.randint(1, 5) for _ in range(rng.randint(1, 3))}
        outcomes[GOAL] = outcomes.get(GOAL, 0) + rng.randint(1, 4)
        base[state] = (float(rng.randint(1, 4)), outcomes)
    policy = copies_of(base, rng.randint(1, 5), rng)
    start = ("a", 0)

    lumped = lump(policy, start, is_goal)
    whole = evaluate(policy, start, is_goal)
    short = evaluate(lumped.policy, lumped.start, lumped.is_goal)

    assert len(lumped.policy) <= len(policy)
    assert short.success_probability.value == pytest.approx(whole.success_probability.value, abs=1e-12)
    assert short.mean.value == pytest.approx(whole.mean.value, rel=1e-9)
    assert short.variance.value == pytest.approx(whole.variance.value, rel=1e-7)
