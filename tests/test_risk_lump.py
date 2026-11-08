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


def deep_split_policy(with_twin):
    """x1 and x2 cost the same and lead to states that cost the same, but those lead to a cheap and a dear retry: only the SECOND refinement pass tells x1 from x2.

    s -> x -> y -> z -> goal; z1 retries at 1 Chaos, z2 at 5. With `with_twin` a third branch x3 -> y3 -> z3 is alike x1 all the way down
    (z3 retries at 1 as well): x3 is x1's twin and must merge into it, x2 never.
    """
    branches = [1, 2, 3] if with_twin else [1, 2]
    retry = {1: 1.0, 2: 5.0, 3: 1.0}
    policy = {"s": Action("s", 1.0, tuple((f"x{k}", 1) for k in branches))}
    for k in branches:
        policy[f"x{k}"] = Action("x", 1.0, ((f"y{k}", 1),))
        policy[f"y{k}"] = Action("y", 1.0, ((f"z{k}", 1),))
        policy[f"z{k}"] = Action("z", retry[k], ((GOAL, 1), (f"z{k}", 1)))
    return policy


def test_two_states_alike_after_the_first_pass_but_apart_two_steps_down_are_not_merged():
    policy = deep_split_policy(with_twin=False)

    lumped = lump(policy, "s", is_goal)

    assert "x1" in lumped.policy and "x2" in lumped.policy  # a single pass would stand x2 for x1 (and y2 for y1, ...)
    assert "y1" in lumped.policy and "y2" in lumped.policy
    assert len(lumped.policy) == len(policy)
    same(evaluate(lumped.policy, lumped.start, lumped.is_goal), evaluate(policy, "s", is_goal))


def test_a_twin_alike_all_the_way_down_merges_and_the_one_that_parts_two_steps_down_does_not():
    policy = deep_split_policy(with_twin=True)

    lumped = lump(policy, "s", is_goal)

    assert set(lumped.policy) == {"s", "x1", "x2", "y1", "y2", "z1", "z2"}  # x3, y3 and z3 stand as x1, y1 and z1
    assert lumped.is_goal(GOAL)
    same(evaluate(lumped.policy, lumped.start, lumped.is_goal), evaluate(policy, "s", is_goal))


def test_the_start_has_a_twin_inside_its_block_and_the_risk_of_the_merged_policy_is_that_of_the_whole_one():
    policy = {
        "s0": Action("s", 1.0, (("m", 1), ("s1", 1), (GOAL, 1))),
        "s1": Action("s", 1.0, (("m", 1), ("s1", 1), (GOAL, 1))),
        "m": Action("m", 2.0, ((GOAL, 1), ("m", 1))),
    }

    lumped = lump(policy, "s0", is_goal)

    assert lumped.start == "s0" and set(lumped.policy) == {"s0", "m"}  # s1 stands as s0, the start
    whole = evaluate(policy, "s0", is_goal)
    short = evaluate(lumped.policy, lumped.start, lumped.is_goal)
    same(short, whole)
    assert short.success_probability.value == pytest.approx(1.0) and short.mean.value > 1.0
