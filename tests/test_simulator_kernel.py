"""The simulator against the compressed kernel on the R12 actions (ticket #25 Done-when, ADR-0019 layer 2).

The simulator (`simulate`) knows nothing of `abstraction`: it samples concrete items with the actions.
The kernel (`Abstraction.kernel`) gives exact probabilities on compressed states. For each case here
both are asked about the same craft, and they must agree:

* one click: the compressed states of N = 20_000 sampled single clicks (3_000 runs for the slow R12 cases) against the exact kernel,
  state by state, within five binomial standard errors;
* a whole policy: the solver picks the cheapest action per compressed state from the kernel; the
  exact mean, success probability and p90 come from `risk.evaluate` on that chain, and the simulator
  runs the very same policy on concrete items. The mean is within five standard errors of the
  interval `risk` certifies, the success rate is 1, and the p90 follows the tolerance of
  `test_risk_simulation.py` (the share of runs at or below the high end is at least 0.9 minus five
  binomial standard errors, the share below the low end at most 0.9 plus five).

Only the test composes the two sides: the goal check on concrete items is written here by hand
(`Target.is_met_by` on the real amulet), not read back from the kernel. Seeds are fixed and the
tolerances are five standard errors, so a correct pair fails about once in 1.7 million runs. The
fixture cases run in CI. The real R12 amulet needs the cached 3.29.3.3 dump (`CRAFTING_CACHE_DIR`)
and skips cleanly without it.
"""

import math
from collections import Counter
from fractions import Fraction

import pytest
from abstraction_support import real_game_data
from actions_support import AMULET, DATA, RESIST, TARGET, amulet, fractured_resist
from simulator_support import Memoized
from targets_support import EXAMPLES

from crafting_system.abstraction import Abstraction, AtLeast, Goal, Wanted, integer_weights
from crafting_system.actions import ActionError, ChaosOrb, HarvestReforge
from crafting_system.risk import evaluate
from crafting_system.simulator import Step, simulate
from crafting_system.solver import Action, TabularModel, solve
from crafting_system.targets import load_target

CHAOS, REFORGE = ChaosOrb(), HarvestReforge("lightning")
CLICK_SAMPLES = 20_000
RUNS = 20_000
SLOW_RUNS = 3_000  # the R12 cases need about 1 / 0.013 clicks a run
REAL_RUNS = 3_000
REAL_CLICKS = 5_000
LEVEL = 86

RESISTS = frozenset(mod_id for mod_id, mod in DATA.mods.items() if "LightningResistance" in mod.families)
LIVES = frozenset(mod_id for mod_id, mod in DATA.mods.items() if mod_id.startswith("IncreasedLife"))
GEM = frozenset({TARGET})


def holds(item, mod_ids):
    return any(entry.mod_id in mod_ids for entry in item.mods)


# name -> (start item, goal as the abstraction reads it, the same goal written by hand, costs per action)
CASES = {
    "r12-fractured-resist": (
        amulet(fractured_resist()),
        Goal((Wanted(GEM), Wanted(RESISTS))),
        lambda item: holds(item, GEM) and holds(item, RESISTS),
        {CHAOS: 1.0, REFORGE: 3.0},
    ),
    "r12-plain-amulet-chaos": (
        amulet(),
        Goal((AtLeast(1, (Wanted(GEM), Wanted(RESISTS))),)),
        lambda item: holds(item, GEM) or holds(item, RESISTS),
        {CHAOS: 1.0},
    ),
    "two-of-three-fractured-resist": (
        amulet(fractured_resist()),
        Goal((AtLeast(2, (Wanted(GEM), Wanted(LIVES), Wanted(RESISTS))),)),
        lambda item: sum(holds(item, ids) for ids in (GEM, LIVES, RESISTS)) >= 2,
        {CHAOS: 1.0, REFORGE: 2.0},
    ),
    "two-of-three-plain-amulet": (
        amulet(),
        Goal((AtLeast(2, (Wanted(GEM), Wanted(LIVES), Wanted(RESISTS))),)),
        lambda item: sum(holds(item, ids) for ids in (GEM, LIVES, RESISTS)) >= 2,
        {CHAOS: 1.0, REFORGE: 2.5},
    ),
}


def kernel_policy(ab, start_state, costs):
    """The solver's cheapest policy over the kernel chain from `start_state`: compressed state -> solver `Action`."""
    states = ab.reachable([start_state], list(costs))
    table = {}
    for state in states:
        if ab.is_goal(state):
            continue
        choices = []
        for action, cost in costs.items():
            try:
                weights = integer_weights(ab.kernel(state, action))
            except ActionError:
                continue
            choices.append(Action(action, cost, tuple(weights.items())))
        table[state] = choices
    goals = [state for state in states if ab.is_goal(state)]
    return solve(TabularModel(goals, table), [start_state]).policy


def run_policy(data, ab, policy, start, is_goal, runs, seed):
    """The simulator on concrete items, choosing at each item the action the kernel's policy names."""
    cached = {action: Memoized(action) for action in {chosen.label for chosen in policy.values()}}

    def at(item):
        chosen = policy[ab.compress(item)]
        return Step(cached[chosen.label], chosen.cost)

    return simulate(data, at, start, is_goal, runs=runs, seed=seed)


def assert_one_click_follows_the_kernel(data, ab, start, action, clicks, seed):
    import random

    state = ab.compress(start)
    kernel = ab.kernel(state, action)
    outcomes = action.outcomes(data, start)
    rng = random.Random(seed)
    seen = Counter(ab.compress(outcomes.sample(rng)) for _ in range(clicks))

    assert set(seen) <= set(kernel)
    for next_state, chance in kernel.items():
        share, p = seen[next_state] / clicks, float(chance)
        assert abs(share - p) <= 5 * math.sqrt(p * (1 - p) / clicks), (next_state.status, share, p)


def assert_policy_agrees_with_the_chain(report, risk):
    assert risk.success_probability.value == 1.0
    assert report.successes == report.runs and report.stopped == report.unfinished == 0
    slack = 5 * report.cost.standard_error
    assert risk.mean.low - slack <= report.cost.value <= risk.mean.high + slack
    level = 0.9
    spread = 5 * math.sqrt(level * (1 - level) / report.runs)
    p90 = risk.p90
    assert sum(cost <= p90.high for cost in report.costs) / report.runs >= level - spread
    assert sum(cost < p90.low for cost in report.costs) / report.runs <= level + spread


@pytest.mark.parametrize("name", CASES)
@pytest.mark.parametrize("action", [CHAOS, REFORGE], ids=["chaos", "reforge"])
def test_a_sampled_click_follows_the_kernel_on_the_fixture_amulet(name, action):
    start, goal, _, _ = CASES[name]
    ab = Abstraction(DATA, goal, AMULET, LEVEL)

    assert_one_click_follows_the_kernel(DATA, ab, start, action, CLICK_SAMPLES, seed=4001)


@pytest.mark.parametrize("seed, name", list(enumerate(CASES)))
def test_a_simulated_policy_agrees_with_the_kernel_chain_on_the_fixture_amulet(seed, name):
    start, goal, is_goal, costs = CASES[name]
    ab = Abstraction(DATA, goal, AMULET, LEVEL)
    state = ab.compress(start)
    policy = kernel_policy(ab, state, costs)
    risk = evaluate(policy, state, ab.is_goal)

    runs = SLOW_RUNS if name == "r12-fractured-resist" else RUNS
    report = run_policy(DATA, ab, policy, start, is_goal, runs, seed=4100 + seed)

    assert_policy_agrees_with_the_chain(report, risk)


def test_the_expected_cost_of_r12_with_a_fractured_resist_is_cost_over_the_exact_chance():
    # An exact anchor for the same comparison: one state, so the kernel mean is cost / chance_all.
    start, goal, is_goal, costs = CASES["r12-fractured-resist"]
    ab = Abstraction(DATA, goal, AMULET, LEVEL)
    state = ab.compress(start)
    policy = kernel_policy(ab, state, {REFORGE: 3.0})
    chance = REFORGE.outcomes(DATA, start).chance_all([TARGET])
    exact = float(Fraction(3) / chance)

    report = run_policy(DATA, ab, policy, start, is_goal, SLOW_RUNS, seed=4200)

    assert report.cost.agrees_with(exact)
    assert evaluate(policy, state, ab.is_goal).mean.value == pytest.approx(exact, rel=1e-9)


@pytest.fixture(scope="module")
def r12():
    data = real_game_data()
    target = load_target(EXAMPLES / "r12-lightning-amulet.yaml", data)
    return data, target, Abstraction(data, Goal.from_target(target), target.base_id, target.item_level)


@pytest.mark.parametrize("action", [CHAOS, REFORGE], ids=["chaos", "reforge"])
def test_a_sampled_click_follows_the_kernel_on_the_real_r12_amulet(r12, action):
    data, target, ab = r12

    assert_one_click_follows_the_kernel(data, ab, target.start_item, action, REAL_CLICKS, seed=4301)


def test_a_simulated_r12_policy_agrees_with_the_kernel_chain_on_the_real_amulet(r12):
    data, target, ab = r12
    state = ab.compress(target.start_item)
    policy = kernel_policy(ab, state, {CHAOS: 1.0, REFORGE: 3.0})
    risk = evaluate(policy, state, ab.is_goal)

    report = run_policy(data, ab, policy, target.start_item, target.is_met_by, REAL_RUNS, seed=4302)

    assert_policy_agrees_with_the_chain(report, risk)
